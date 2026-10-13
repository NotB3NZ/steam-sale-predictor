"""Offline scalable regression. Every generated artifact is in a temp directory."""
import copy
from contextlib import contextmanager
import io
import json
from pathlib import Path
import socket
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
import cohort_io as c
import cohort_pipeline as p
import incremental_itad as inc

KEY = 'synthetic-scalable-offline-only-key'
GID = '018d937f-07fc-72ed-8517-d8e24cb1eb22'
RECORD = dict(timestamp='2023-11-22T18:00:00Z', shop=dict(id=61, name='Steam'),
              deal=dict(price=dict(amount=10, amountInt=1000, currency='USD'),
                        regular=dict(amount=20, amountInt=2000, currency='USD'), cut=50))


class Response:
    status = 200
    headers = {'Content-Type': 'application/json'}
    def __init__(self, payload):
        self.body = json.dumps(payload).encode()
    def read(self):
        return self.body
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass


class FakeOpener:
    def __init__(self, history=None, outcomes=()):
        self.history = [RECORD] if history is None else history
        self.outcomes = list(outcomes)
        self.calls = []
        self.lookup_appids = []
    def open(self, req, timeout):
        url = urlparse(req.full_url)
        query = parse_qs(url.query)
        assert KEY not in req.full_url
        assert req.get_header('Itad-api-key') == KEY
        assert timeout == 30
        if url.path == inc.itad.HISTORY:
            assert query == {'id': [GID], 'country': ['US'], 'shops': ['61'], 'since': ['2021-01-01T00:00:00Z']}
        else:
            assert url.path == inc.itad.LOOKUP and set(query) == {'appid'}
            self.lookup_appids.append(query['appid'][0])
        self.calls.append(url.path)
        if self.outcomes:
            outcome = self.outcomes.pop(0)
            if isinstance(outcome, BaseException):
                raise outcome
            if outcome is not None:
                return Response(outcome)
        return Response({'found': True, 'game': {'id': GID}} if url.path == inc.itad.LOOKUP else self.history)


def error(code, headers=None):
    return HTTPError('https://example.test', code, 'synthetic', headers or {}, io.BytesIO(b'{"error":"synthetic"}'))


class FakeClock:
    def __init__(self):
        self.now = 2000000000.0
        self.sleeps = []

    def time(self):
        return self.now

    def sleep(self, seconds):
        assert seconds >= 0
        self.sleeps.append(seconds)
        self.now += seconds

    @contextmanager
    def installed(self):
        with patch.object(inc.time, 'time', self.time), \
             patch.object(inc.time, 'monotonic', self.time), \
             patch.object(inc.time, 'sleep', self.sleep):
            yield self


class TimedOpener(FakeOpener):
    def __init__(self, clock, latency=0.4, **kwargs):
        super().__init__(**kwargs)
        self.clock, self.latency, self.starts = clock, latency, []

    def open(self, req, timeout):
        self.starts.append(self.clock.now)
        self.clock.now += self.latency
        return super().open(req, timeout)


class ScalableTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name).resolve()
        self.cohort = self.directory/'cohort.csv'
        self.cache = self.directory/'cache'
        self.output = self.directory/'reports'
        c.write_csv(self.cohort, [dict(AppID='999999991', Name='Synthetic game', release_date='2020-01-01',
                                     evaluation_group='development')], ['AppID', 'Name', 'release_date', 'evaluation_group'])
        self.sleep = patch.object(inc.time, 'sleep')
        self.sleep_mock = self.sleep.start()
        self.addCleanup(self.sleep.stop)

    def collect(self, opener=None, **kwargs):
        return inc.run(self.cohort, self.cache, self.output, reuse_dirs=[],
                       live=opener is not None, opener=opener, key=KEY if opener is not None else '', **kwargs)

    def batch_cohort(self, ids=('999999993', '999999991', '999999992')):
        c.write_csv(self.cohort, [dict(AppID=appid, Name='Synthetic '+appid,
                                     release_date='2020-01-01', evaluation_group='development')
                                    for appid in ids],
                    ['AppID', 'Name', 'release_date', 'evaluation_group'])
        return list(ids)

    def test_configurable_pacing_covers_lookup_history_and_next_game(self):
        self.batch_cohort()
        clock = FakeClock()
        opener = TimedOpener(clock)
        with clock.installed():
            report = self.collect(opener, raw_only=True, max_new_games=2,
                                  request_interval_seconds=3)
        self.assertEqual(opener.calls, [inc.itad.LOOKUP, inc.itad.HISTORY]*2)
        self.assertEqual([b-a for a, b in zip(opener.starts, opener.starts[1:])], [3, 3, 3])
        self.assertEqual(report['request_interval_seconds'], 3)
        self.assertEqual(report['run_requests']['total_http_attempts'], 4)

    def test_pacing_default_is_one_second_and_zero_is_supported(self):
        for interval in (None, 0):
            with self.subTest(interval=interval):
                self.cache = self.directory/f'interval_{interval}'
                clock = FakeClock()
                opener = TimedOpener(clock, latency=0)
                kwargs = {} if interval is None else {'request_interval_seconds': interval}
                with clock.installed():
                    report = self.collect(opener, raw_only=True, **kwargs)
                expected = 1 if interval is None else 0
                self.assertEqual(opener.starts[1]-opener.starts[0], expected)
                self.assertEqual(report['request_interval_seconds'], expected)

    def test_retries_obey_configured_pacing_and_keep_bounded_backoff(self):
        clock = FakeClock()
        opener = TimedOpener(clock, latency=0, outcomes=[error(503), None, None])
        with clock.installed():
            report = self.collect(opener, raw_only=True, request_interval_seconds=3)
        self.assertEqual(opener.calls, [inc.itad.LOOKUP, inc.itad.LOOKUP, inc.itad.HISTORY])
        self.assertEqual([b-a for a, b in zip(opener.starts, opener.starts[1:])], [3, 3])
        self.assertIn(2, clock.sleeps)
        self.assertEqual(report['cumulative_requests']['total_http_attempts'], 3)

    def test_slow_responses_do_not_add_a_full_interval_after_completion(self):
        clock = FakeClock()
        opener = TimedOpener(clock, latency=5)
        with clock.installed():
            self.collect(opener, raw_only=True, request_interval_seconds=3)
        self.assertEqual(opener.starts[1]-opener.starts[0], 5)
        self.assertFalse(any(clock.sleeps))

    def test_pacing_measures_actual_start_after_journal_persistence(self):
        clock = FakeClock()
        opener = TimedOpener(clock, latency=0)
        append = inc.Journal.append
        delayed = []

        def persist(journal, event):
            append(journal, event)
            if event['kind'] == 'attempt' and not delayed:
                clock.now += 1
                delayed.append(True)

        with clock.installed(), patch.object(inc.Journal, 'append', persist):
            self.collect(opener, raw_only=True, request_interval_seconds=3)
        self.assertEqual(opener.starts[1]-opener.starts[0], 3)

    def test_pacing_survives_restart_and_reuses_partial_lookup(self):
        clock = FakeClock()
        first = TimedOpener(clock, latency=0)
        with clock.installed():
            self.collect(first, raw_only=True, maximum=1, request_interval_seconds=3)
            path = self.cache/'http_attempts.jsonl'
            prefix = path.read_bytes()
            # Model a restart one second after the saved HTTP reservation.
            clock.now = first.starts[0]+1
            resume = TimedOpener(clock, latency=0)
            report = self.collect(resume, raw_only=True, maximum=2, request_interval_seconds=3)
        self.assertEqual(resume.calls, [inc.itad.HISTORY])
        self.assertEqual(resume.starts[0]-first.starts[0], 3)
        self.assertTrue(path.read_bytes().startswith(prefix))
        self.assertEqual(report['games_with_complete_caches'], 1)

    def test_invalid_pacing_is_rejected_before_files_or_requests(self):
        for interval in (-1, float('nan'), float('inf'), -float('inf'), True, None, 'invalid'):
            with self.subTest(interval=str(interval)), \
                 patch.object(inc, 'cache_lock') as lock, \
                 patch.object(inc, 'RecordingClient') as client:
                opener = FakeOpener()
                with self.assertRaises(ValueError):
                    self.collect(opener, raw_only=True, request_interval_seconds=interval)
                with self.assertRaises(ValueError):
                    inc.Journal(self.cache, 2, request_interval_seconds=interval)
                lock.assert_not_called()
                client.assert_not_called()
                self.assertEqual(opener.calls, [])
        self.assertFalse(self.cache.exists())
        self.assertFalse(self.output.exists())

    def test_cli_rejects_invalid_pacing_before_running(self):
        for interval in ('-1', 'nan', 'inf', '-inf', 'invalid'):
            with self.subTest(interval=interval), patch.object(inc, 'run') as run, \
                 patch('sys.stderr', io.StringIO()):
                with self.assertRaises(SystemExit) as stopped:
                    inc.cli(['--cohort', str(self.cohort), '--cache-dir', str(self.cache),
                             '--output-dir', str(self.output), '--request-interval-seconds='+interval])
                self.assertEqual(stopped.exception.code, 2)
                run.assert_not_called()

    def test_raw_only_bypasses_all_downstream_calculations(self):
        with patch.dict(sys.modules, {'cohort_pipeline': None}), \
             patch.object(p.features_core, 'build_features', side_effect=AssertionError('No features')), \
             patch.object(p.labels_core, 'construct_labels', side_effect=AssertionError('No labels')):
            report = self.collect(FakeOpener(), raw_only=True)
        self.assertTrue(report['raw_only'])
        self.assertEqual(report['games_with_complete_caches'], 1)
        self.assertEqual(report['successful_lookups'], 1)
        self.assertEqual(report['successful_histories'], 1)
        self.assertNotIn('coverage_by_sale_year', report)
        self.assertNotIn('missing_or_uncertain_labels', report)
        self.assertEqual({p.name for p in self.output.iterdir()},
                         {'collection_manifest.csv', 'collection_quality.json'})

    def test_raw_only_offline_has_no_key_client_or_cache_creation(self):
        with patch.object(inc, 'RecordingClient', side_effect=AssertionError('No client')), \
             patch.dict(sys.modules, {'cohort_pipeline': None}):
            report = self.collect(raw_only=True, max_new_games=1)
        self.assertEqual(report['planned_games'], 1)
        self.assertEqual(report['cumulative_requests']['total_http_attempts'], 0)
        self.assertFalse(self.cache.exists())

    def test_batch_limit_and_selection_preserve_frozen_order(self):
        ids = self.batch_cohort()
        frozen = self.cohort.read_bytes()
        first = FakeOpener()
        report = self.collect(first, raw_only=True, max_new_games=2)
        self.assertEqual(first.lookup_appids, ids[:2])
        self.assertEqual(report['planned_appids'], ids[:2])
        self.assertEqual(report['games_with_complete_caches'], 2)
        self.assertFalse((self.cache/(ids[2]+'.json')).exists())
        second = FakeOpener()
        again = self.collect(second, raw_only=True, max_new_games=2)
        self.assertEqual(second.lookup_appids, ids[2:])
        self.assertEqual(again['games_with_complete_caches'], 3)
        self.assertEqual(self.cohort.read_bytes(), frozen)

    def test_complete_games_do_not_consume_batch_limit(self):
        ids = self.batch_cohort()
        self.collect(FakeOpener(), raw_only=True, max_new_games=1)
        cached = (self.cache/(ids[0]+'.json')).read_bytes()
        opener = FakeOpener()
        report = self.collect(opener, raw_only=True, max_new_games=1)
        self.assertEqual(opener.lookup_appids, [ids[1]])
        self.assertEqual(report['already_cached_games'], 1)
        self.assertEqual(report['planned_games'], 1)
        self.assertEqual((self.cache/(ids[0]+'.json')).read_bytes(), cached)

    def test_original_reused_cache_does_not_consume_batch_limit(self):
        original = c.load_cohort(c.ROOT/'data/intermediate/pilot_games.csv')[0]
        fresh = dict(AppID='999999991', Name='Synthetic', release_date='2020-01-01',
                     evaluation_group='development')
        fields = ['AppID', 'Name', 'release_date', 'evaluation_group']
        c.write_csv(self.cohort, [{k: original[k] for k in fields}, fresh], fields)
        path = c.ORIGINAL_CACHE/(original['AppID']+'.json')
        before = c.digest(path)
        opener = FakeOpener()
        report = inc.run(self.cohort, self.cache, self.output, live=True, key=KEY,
                         opener=opener, raw_only=True, max_new_games=1)
        self.assertEqual(report['already_cached_games'], 1)
        self.assertEqual(opener.lookup_appids, [fresh['AppID']])
        self.assertFalse((self.cache/path.name).exists())
        self.assertEqual(c.digest(path), before)

    def test_zero_batch_and_invalid_limits(self):
        opener = FakeOpener()
        report = self.collect(opener, raw_only=True, max_new_games=0)
        self.assertEqual(opener.calls, [])
        self.assertEqual(report['planned_games'], 0)
        for limit in (-1, 1.5, True):
            with self.assertRaises(ValueError):
                self.collect(opener, raw_only=True, max_new_games=limit)
        self.assertEqual(opener.calls, [])

    def test_raw_batch_resumes_interrupted_history_without_reset(self):
        ids = self.batch_cohort()
        first = self.collect(FakeOpener(outcomes=[None, KeyboardInterrupt()]),
                             raw_only=True, max_new_games=1)
        self.assertIn('Interrupted', first['stopped'])
        path = self.cache/'http_attempts.jsonl'
        prefix = path.read_bytes()
        opener = FakeOpener()
        report = self.collect(opener, raw_only=True, max_new_games=1)
        self.assertEqual(opener.calls, [inc.itad.HISTORY])
        self.assertEqual(report['planned_appids'], [ids[0]])
        self.assertEqual(report['games_with_complete_caches'], 1)
        journal = inc.Journal(self.cache, 18, readonly=True)
        self.assertEqual(journal.counts()['total_http_attempts'], 3)
        self.assertEqual(journal.counts()['interrupted_or_unknown_attempts'], 1)
        self.assertFalse(any(e['kind'] == 'round' for e in journal.events))
        self.assertTrue(path.read_bytes().startswith(prefix))

    def test_batch_failures_keep_counters_until_explicit_retry(self):
        ids = self.batch_cohort()
        self.collect(FakeOpener(outcomes=[error(503), error(503), error(503)]),
                     raw_only=True, max_new_games=1)
        failed = (self.cache/(ids[0]+'.json')).read_bytes()
        next_batch = FakeOpener()
        self.collect(next_batch, raw_only=True, max_new_games=1)
        self.assertEqual(next_batch.lookup_appids, [ids[1]])
        journal = inc.Journal(self.cache, 18, readonly=True)
        self.assertEqual(journal.used(ids[0], inc.itad.LOOKUP, 0), 3)
        self.assertFalse(any(e['kind'] == 'round' for e in journal.events))
        retry = FakeOpener()
        self.collect(retry, raw_only=True, max_new_games=1, retry_failed=True)
        self.assertEqual(retry.lookup_appids, [ids[0]])
        self.assertEqual(next((self.cache/'archive'/ids[0]).glob('*.json')).read_bytes(), failed)
        journal = inc.Journal(self.cache, 18, readonly=True)
        self.assertEqual(journal.used(ids[0], inc.itad.LOOKUP, 0), 3)
        self.assertEqual(journal.round_for(ids[0]), 1)

    def test_raw_batch_budget_survives_restart_and_keeps_partial_lookup(self):
        ids = self.batch_cohort()
        report = self.collect(FakeOpener(), raw_only=True, max_new_games=1, maximum=1)
        self.assertIn('budget', report['stopped'])
        prefix = (self.cache/'http_attempts.jsonl').read_bytes()
        blocked = FakeOpener()
        self.collect(blocked, raw_only=True, max_new_games=1, maximum=1)
        self.assertEqual(blocked.calls, [])
        self.assertEqual((self.cache/'http_attempts.jsonl').read_bytes(), prefix)
        resume = FakeOpener()
        report = self.collect(resume, raw_only=True, max_new_games=1, maximum=2)
        self.assertEqual(resume.calls, [inc.itad.HISTORY])
        self.assertEqual(report['cumulative_requests']['total_http_attempts'], 2)
        final = FakeOpener()
        report = self.collect(final, raw_only=True, max_new_games=1, maximum=4)
        self.assertEqual(final.lookup_appids, [ids[1]])
        self.assertEqual(report['cumulative_requests']['total_http_attempts'], 4)
        self.assertTrue((self.cache/'http_attempts.jsonl').read_bytes().startswith(prefix))

    def test_429_immediately_stops_and_saves_lookup_or_history_checkpoint(self):
        self.batch_cohort()
        for stage in ('lookup', 'history'):
            for retry_after in (None, '0', '7', '120', 'invalid'):
                with self.subTest(stage=stage, retry_after=retry_after):
                    self.cache = self.directory/f'429_{stage}_{retry_after}'
                    headers = {} if retry_after is None else {'Retry-After': retry_after}
                    outcomes = ([None] if stage == 'history' else []) + [error(429, headers)]
                    opener = FakeOpener(outcomes=outcomes)
                    self.sleep_mock.reset_mock()
                    report = self.collect(opener, raw_only=True, max_new_games=2)
                    self.assertEqual(len(opener.calls), 2 if stage == 'history' else 1)
                    self.assertTrue(report['stopped'])
                    obj = c.read_json(self.cache/'999999993.json')
                    self.assertEqual(obj['collection_metadata']['reason'], 'HTTP_429')
                    self.assertEqual(obj[stage+'_evidence']['http_status'], 429)
                    self.assertEqual(obj[stage+'_evidence']['response_headers'], headers)
                    journal = inc.Journal(self.cache, 18, readonly=True)
                    self.assertEqual(journal.events[-1]['kind'],
                                     'cooldown' if retry_after in ('7', '120') else 'result')
                    self.assertFalse(any(call.args == (7.0,) or call.args == (120.0,)
                                         for call in self.sleep_mock.call_args_list))

    def test_cooldown_is_persistent_and_recovery_works_after_expiration(self):
        clock = time.time()
        with patch.object(inc.time, 'time', return_value=clock):
            self.collect(FakeOpener(outcomes=[None, error(429, {'Retry-After': '120'})]), raw_only=True)
            journal = inc.Journal(self.cache, 6, readonly=True)
            self.assertEqual(journal.events[-1]['not_before_epoch'], clock+120)
            prefix = (self.cache/'http_attempts.jsonl').read_bytes()
            blocked = FakeOpener()
            report = self.collect(blocked, raw_only=True, retry_failed=True)
            self.assertEqual(blocked.calls, [])
            self.assertIn('cooldown', report['stopped'])
            self.assertEqual(report['cumulative_requests']['total_http_attempts'], 2)
        with patch.object(inc.time, 'time', return_value=clock+121):
            retry = FakeOpener()
            report = self.collect(retry, raw_only=True, retry_failed=True)
        self.assertEqual(retry.calls, [inc.itad.HISTORY])
        self.assertEqual(report['games_with_complete_caches'], 1)
        self.assertEqual(report['cumulative_requests']['total_http_attempts'], 3)
        self.assertTrue((self.cache/'http_attempts.jsonl').read_bytes().startswith(prefix))

    def test_401_and_403_immediately_stop_batch_and_preserve_checkpoint(self):
        ids = self.batch_cohort()
        for status in (401, 403):
            for stage in ('lookup', 'history'):
                with self.subTest(status=status, stage=stage):
                    self.cache = self.directory/f'auth_{status}_{stage}'
                    outcomes = ([None] if stage == 'history' else []) + [error(status)]
                    opener = FakeOpener(outcomes=outcomes)
                    report = self.collect(opener, raw_only=True, max_new_games=2)
                    self.assertEqual(len(opener.calls), 2 if stage == 'history' else 1)
                    self.assertTrue(report['stopped'])
                    obj = c.read_json(self.cache/(ids[0]+'.json'))
                    self.assertEqual(obj['collection_metadata']['reason'], f'HTTP_{status}')
                    self.assertFalse((self.cache/(ids[1]+'.json')).exists())

    def test_raw_batch_cli_passes_both_flags_to_collector(self):
        ids = self.batch_cohort()
        opener = FakeOpener()
        with patch.dict(inc.os.environ, {'ITAD_API_KEY': ' \t'+KEY+'\r\n'}), \
             patch.object(inc.itad, 'build_opener', return_value=opener), \
             patch.dict(sys.modules, {'cohort_pipeline': None}), \
             patch('sys.stdout', io.StringIO()):
            status = inc.cli(['--cohort', str(self.cohort), '--cache-dir', str(self.cache),
                              '--output-dir', str(self.output), '--reuse-cache',
                              str(self.directory/'unused'), '--live', '--raw-only',
                              '--max-new-games', '1', '--max-total-attempts', '2',
                              '--request-interval-seconds', '3'])
        self.assertEqual(status, 0)
        self.assertEqual(opener.lookup_appids, [ids[0]])
        report = c.read_json(self.output/'collection_quality.json')
        self.assertEqual(report['max_new_games'], 1)
        self.assertEqual(report['maximum_cumulative_attempts'], 2)
        self.assertEqual(report['request_interval_seconds'], 3)

    def test_dry_run_requires_no_key_no_network_no_cache_creation(self):
        with patch.object(inc.itad, 'Client', side_effect=AssertionError('No client offline')):
            report = self.collect()
        self.assertEqual(report['planned_games'], 1)
        self.assertEqual(report['estimated_requests_without_retries'], 2)
        self.assertEqual(report['cumulative_requests']['total_http_attempts'], 0)
        self.assertEqual(report['missing_or_uncertain_labels'], 3)
        self.assertFalse(self.cache.exists())

    def test_valid_key_reaches_mocked_requests(self):
        opener = FakeOpener()
        report = inc.run(self.cohort, self.cache, self.output, reuse_dirs=[],
                         live=True, key=KEY, opener=opener)
        self.assertEqual(opener.calls, [inc.itad.LOOKUP, inc.itad.HISTORY])
        self.assertEqual(report['cumulative_requests']['successful_api_requests'], 2)

    def test_key_surrounding_whitespace_is_stripped_before_mocked_requests(self):
        opener = FakeOpener()
        report = inc.run(self.cohort, self.cache, self.output, reuse_dirs=[],
                         live=True, key=' \t\r\n'+KEY+'\r\n\t ', opener=opener)
        self.assertEqual(opener.calls, [inc.itad.LOOKUP, inc.itad.HISTORY])
        self.assertEqual(report['newly_retrieved_games'], 1)
        for path in self.directory.rglob('*'):
            if path.is_file():
                self.assertNotIn(KEY.encode(), path.read_bytes())

    def assert_key_rejected_before_side_effects(self, key, message):
        opener = FakeOpener()
        with patch.object(inc, 'cache_lock') as lock, \
             patch.object(inc, 'Journal') as journal, \
             patch.object(inc, 'RecordingClient') as client:
            with self.assertRaises(ValueError) as caught:
                inc.run(self.cohort, self.cache, self.output, reuse_dirs=[],
                        live=True, key=key, opener=opener)
            self.assertEqual(str(caught.exception), message)
            lock.assert_not_called()
            journal.assert_not_called()
            client.assert_not_called()
        self.assertEqual(opener.calls, [])
        self.assertFalse(self.cache.exists())
        self.assertFalse(self.output.exists())

    def test_empty_key_is_rejected(self):
        self.assert_key_rejected_before_side_effects(
            '', 'ITAD_API_KEY is required only for explicit live collection')

    def test_whitespace_only_key_is_rejected(self):
        self.assert_key_rejected_before_side_effects(
            ' \t\r\n ', 'ITAD_API_KEY is required only for explicit live collection')

    def test_embedded_newline_in_key_is_rejected(self):
        self.assert_key_rejected_before_side_effects(
            KEY+'\nembedded', 'ITAD_API_KEY contains invalid header characters; zero API calls.')

    def test_embedded_carriage_return_in_key_is_rejected(self):
        self.assert_key_rejected_before_side_effects(
            KEY+'\rembedded', 'ITAD_API_KEY contains invalid header characters; zero API calls.')

    def test_live_cli_normalizes_synthetic_environment_key(self):
        opener = FakeOpener()
        output = io.StringIO()
        with patch.dict(inc.os.environ, {'ITAD_API_KEY': ' \t'+KEY+'\r\n'}), \
             patch.object(inc.itad, 'build_opener', return_value=opener), \
             patch('sys.stdout', output):
            status = inc.cli(['--cohort', str(self.cohort), '--cache-dir', str(self.cache),
                              '--output-dir', str(self.output), '--reuse-cache',
                              str(self.directory/'unused'), '--live'])
        self.assertEqual(status, 0)
        self.assertEqual(opener.calls, [inc.itad.LOOKUP, inc.itad.HISTORY])
        self.assertNotIn(KEY, output.getvalue())

    def test_incremental_collection_skips_valid_and_restart_makes_zero_requests(self):
        first = FakeOpener()
        report = self.collect(first)
        self.assertEqual(report['newly_retrieved_games'], 1)
        self.assertEqual(report['cumulative_requests']['successful_api_requests'], 2)
        self.assertEqual(report['coverage_by_sale_year']['2023']['observed_discount_games'], 1)
        second = FakeOpener(outcomes=[AssertionError('Cache should skip HTTP')])
        again = self.collect(second)
        self.assertEqual(again['already_cached_games'], 1)
        self.assertEqual(second.calls, [])
        self.assertEqual(again['run_requests']['total_http_attempts'], 0)
        self.assertEqual(again['cumulative_requests']['total_http_attempts'], 2)

    def test_retries_count_every_attempt_and_preserve_original_endpoint_semantics(self):
        report = self.collect(FakeOpener(outcomes=[error(503), None, None]))
        self.assertEqual(report['cumulative_requests']['total_http_attempts'], 3)
        self.assertEqual(report['cumulative_requests']['failed_api_requests'], 1)
        self.assertEqual(report['cumulative_requests']['successful_api_requests'], 2)

    def test_three_attempt_bound_and_explicit_retry_round_stay_within_global_cap(self):
        opener = FakeOpener(outcomes=[error(503), error(503), error(503)])
        first = self.collect(opener)
        self.assertEqual(opener.calls, [inc.itad.LOOKUP]*3)
        self.assertEqual(first['newly_retrieved_games'], 0)
        self.assertEqual(first['cumulative_requests']['failed_api_requests'], 3)
        implicit = FakeOpener()
        self.collect(implicit)
        self.assertEqual(implicit.calls, [])
        again = FakeOpener(outcomes=[error(503), error(503), error(503)])
        report = self.collect(again, retry_failed=True)
        self.assertEqual(again.calls, [inc.itad.LOOKUP]*3)
        self.assertEqual(report['cumulative_requests']['total_http_attempts'], 6)
        capped = FakeOpener()
        stopped = self.collect(capped, retry_failed=True)
        self.assertEqual(capped.calls, [])
        self.assertIn('budget', stopped['stopped'])

    def test_failed_history_is_unknown_not_zero_and_never_replaced(self):
        report = self.collect(FakeOpener(outcomes=[None, error(404)]))
        self.assertEqual(report['newly_retrieved_games'], 0)
        self.assertEqual(report['games_with_usable_historical_records'], 0)
        self.assertEqual(report['missing_or_uncertain_labels'], 3)
        labels = p.run(self.cohort, self.cache, self.directory/'processing', [], 'labels')['labels']
        self.assertTrue(all(r['discount_observed'] == '' and r['pu_status'] == 'unknown' for r in labels))
        again = FakeOpener()
        self.collect(again)
        self.assertEqual(again.calls, [])
        self.assertEqual({x.stem for x in self.cache.glob('[0-9]*.json')}, {'999999991'})

    def test_explicit_retry_reuses_lookup_and_counts_across_runs(self):
        self.collect(FakeOpener(outcomes=[None, error(404)]))
        retry = FakeOpener()
        report = self.collect(retry, retry_failed=True)
        self.assertEqual(retry.calls, [inc.itad.HISTORY])
        self.assertEqual(report['newly_retrieved_games'], 1)
        self.assertEqual(report['cumulative_requests']['total_http_attempts'], 3)

    def test_interrupted_history_resumes_without_duplicate_lookup(self):
        interrupted = self.collect(FakeOpener(outcomes=[None, KeyboardInterrupt()]))
        self.assertIn('Interrupted', interrupted['stopped'])
        self.assertEqual(interrupted['cumulative_requests']['interrupted_or_unknown_attempts'], 1)
        retry = FakeOpener()
        report = self.collect(retry)
        self.assertEqual(retry.calls, [inc.itad.HISTORY])
        self.assertEqual(report['cumulative_requests']['total_http_attempts'], 3)
        self.assertEqual(report['cumulative_requests']['interrupted_or_unknown_attempts'], 1)

    def test_global_attempt_budget_survives_restart(self):
        first = self.collect(FakeOpener(), maximum=1)
        self.assertIn('budget', first['stopped'])
        opener = FakeOpener()
        report = self.collect(opener, maximum=1)
        self.assertEqual(opener.calls, [])
        self.assertEqual(report['cumulative_requests']['total_http_attempts'], 1)
        self.collect(opener, maximum=2)
        self.assertEqual(opener.calls, [inc.itad.HISTORY])

    def test_evidence_only_preserves_labels_without_feature_calculation(self):
        self.collect(FakeOpener())
        games = c.load_cohort(self.cohort)
        resolver = lambda appid: inc.resolve_cache(appid, self.cache, [])
        full = p.evidence(games, resolver)
        with patch.object(p.features_core, 'build_features', side_effect=AssertionError('No features in audit')):
            audited = p.evidence(games, resolver, include_features=False)
        for field in ('pairs', 'records', 'diagnostics', 'labels', 'usable_history_ids'):
            self.assertEqual(audited[field], full[field])
        self.assertEqual(audited['features'], [])
        self.assertEqual(audited['provenance'], [])
        self.assertEqual(audited['modeling'], [])

    def test_unmatched_and_empty_success_are_not_sufficient_modeling_evidence(self):
        unmatched = self.collect(FakeOpener(outcomes=[{'found': False}]))
        self.assertEqual(unmatched['newly_retrieved_games'], 0)
        self.assertEqual(unmatched['cumulative_requests']['total_http_attempts'], 1)
        self.assertEqual(unmatched['missing_or_uncertain_labels'], 3)
        self.assertEqual(self.collect(FakeOpener())['run_requests']['total_http_attempts'], 0)
        # A separate namespace receives a successful empty history.
        self.cache = self.directory/'empty_cache'
        empty = self.collect(FakeOpener(history=[]))
        self.assertEqual(empty['newly_retrieved_games'], 1)
        self.assertEqual(empty['games_with_incomplete_historical_records'], 1)
        result = p.run(self.cohort, self.cache, self.directory/'empty_processing', [])
        self.assertTrue(all(r['discount_observed'] == 0 and not r['model_eligible'] for r in result['labels']))

    def test_labelability_view_keeps_empty_and_missing_histories_unknown(self):
        from audit_cohort_labelability import labelability_view
        games = c.load_cohort(self.cohort)
        resolver = lambda appid: inc.resolve_cache(appid, self.cache, [])
        missing = p.evidence(games, resolver, include_features=False)
        self.assertTrue(all(r['discount_observed'] == '' for r in labelability_view(missing['labels'])))
        self.collect(FakeOpener(history=[]), raw_only=True)
        empty = p.evidence(games, resolver, include_features=False)
        self.assertTrue(all(r['evidence_category'] == 'D' and r['discount_observed'] == 0 for r in empty['labels']))
        self.assertTrue(all(r['empty_raw_history'] and r['discount_observed'] == '' and
                            r['labelability_status'] == 'unknown_or_excluded'
                            for r in labelability_view(empty['labels'])))

    def test_schema_failure_http200_is_not_retrieval_success(self):
        report = self.collect(FakeOpener(history={'invalid': 'history'}))
        self.assertEqual(report['cumulative_requests']['successful_api_requests'], 2)
        self.assertEqual(report['newly_retrieved_games'], 0)
        self.assertEqual(report['missing_or_uncertain_labels'], 3)
        self.assertTrue(report['stopped'])

    def test_future_only_or_null_only_history_is_incomplete_for_historical_use(self):
        for i, history in enumerate([[dict(RECORD, timestamp='2026-01-01T00:00:00Z')],
                                      [dict(RECORD, deal=None)]]):
            self.cache = self.directory/f'cache_{i}'
            report = self.collect(FakeOpener(history=history))
            self.assertEqual(report['newly_retrieved_games'], 1)
            self.assertEqual(report['games_with_usable_historical_records'], 0)
            self.assertEqual(report['games_with_incomplete_historical_records'], 1)
            self.assertEqual(report['missing_or_uncertain_labels'], 3)

    def test_original_cache_and_input_overlap_rejected(self):
        for cache, output, reuse in [(c.ORIGINAL_CACHE, self.output, []),
                                     (self.cache, self.directory, []),
                                     (self.cache, self.cache/'reports', []),
                                     (self.cache, self.output, [self.directory])]:
            with self.assertRaises(ValueError):
                inc.paths(self.cohort, cache, reuse, output)

    def test_stale_refresh_preserves_exact_backup_and_reused_cache_is_readonly(self):
        self.collect(FakeOpener())
        old = (self.cache/'999999991.json').read_bytes()
        self.collect(FakeOpener(history=[]), stale=['999999991'])
        backups = list((self.cache/'archive/999999991').glob('*.json'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), old)
        original = c.load_cohort(c.ROOT/'data/intermediate/pilot_games.csv')[0]
        c.write_csv(self.cohort, [original], list(original))
        with self.assertRaises(ValueError):
            inc.run(self.cohort, self.directory/'other_cache', self.output, stale=[original['AppID']])

    def test_corrupt_cache_requires_explicit_stale_refresh(self):
        self.cache.mkdir()
        (self.cache/'999999991.json').write_bytes(b'broken cache\n')
        skipped = FakeOpener()
        self.collect(skipped)
        self.assertEqual(skipped.calls, [])
        self.collect(FakeOpener(), stale=['999999991'])
        self.assertEqual(next((self.cache/'archive/999999991').glob('*.json')).read_bytes(), b'broken cache\n')

    def test_invalid_journal_binding_truncation_and_sequence_fail_closed(self):
        self.collect(FakeOpener())
        path = self.cache/'http_attempts.jsonl'
        body = path.read_text()
        for invalid in ['', body[:-1], body.replace('"schema_version": 1', '"schema_version": 2'),
                        body.replace('"sequence": 1', '"sequence": 9')]:
            path.write_text(invalid)
            opener = FakeOpener()
            with self.assertRaises(ValueError):
                self.collect(opener)
            self.assertEqual(opener.calls, [])
        path.write_text(body)
        before = path.read_bytes()
        self.collect()
        self.assertEqual(path.read_bytes(), before)

    def test_provider_retry_after_cooldown_persists_across_restart(self):
        report = self.collect(FakeOpener(outcomes=[error(429, {'Retry-After': '120'})]))
        self.assertTrue(report['stopped'])
        retry = FakeOpener()
        again = self.collect(retry, retry_failed=True)
        self.assertTrue(again['stopped'])
        self.assertEqual(retry.calls, [])
        self.assertEqual(again['cumulative_requests']['total_http_attempts'], 1)
        self.cache = self.directory/'invalid_retry_after'
        invalid = self.collect(FakeOpener(outcomes=[error(503, {'Retry-After': 'invalid'})]))
        self.assertTrue(invalid['stopped'])
        self.assertEqual(invalid['cumulative_requests']['total_http_attempts'], 1)

    def test_concurrent_collectors_and_symlinks_rejected(self):
        with inc.cache_lock(self.cache):
            with self.assertRaises(ValueError):
                self.collect(FakeOpener())
        link = self.directory/'symlink'
        link.symlink_to(self.cache, target_is_directory=True)
        with self.assertRaises(ValueError):
            inc.run(self.cohort, link, self.output)

    def test_credentials_never_written_or_reported(self):
        report = self.collect(FakeOpener(outcomes=[{'found': True, 'secret': KEY}]))
        self.assertTrue(report['stopped'])
        for path in self.directory.rglob('*'):
            if path.is_file():
                self.assertNotIn(KEY.encode(), path.read_bytes())

    def test_cohort_schema_rejects_duplicates_bad_ids_dates_and_groups(self):
        base = dict(AppID='1', Name='Game', release_date='2020-01-01', evaluation_group='development')
        for rows in [[base, base], [dict(base, AppID='01')], [dict(base, AppID=str(2**32))],
                     [dict(base, release_date='2020-1-01')], [dict(base, evaluation_group='other')]]:
            c.write_csv(self.cohort, rows, list(base))
            with self.assertRaises(ValueError):
                c.load_cohort(self.cohort)

    def test_planned_sizes_are_reproducible_nested_and_outcome_independent(self):
        previous = set()
        groups = {}
        for n in c.SIZES:
            destination = self.directory/f'cohort_{n}.csv'
            selected = c.select_cohort(n, destination)
            games = c.load_cohort(destination)
            self.assertEqual(len(games), n)
            self.assertEqual(selected['target_games'], n)
            ids = {g['AppID'] for g in games}
            self.assertTrue(previous <= ids)
            for g in games:
                if g['AppID'] in groups:
                    self.assertEqual(groups[g['AppID']], g['evaluation_group'])
                groups[g['AppID']] = g['evaluation_group']
                if g['pilot_membership']:
                    self.assertEqual(g['evaluation_group'], 'development')
            previous = ids
            duplicate = self.directory/f'duplicate_{n}.csv'
            c.select_cohort(n, duplicate)
            self.assertEqual(destination.read_bytes(), duplicate.read_bytes())
            with self.assertRaises(ValueError):
                c.select_cohort(n, destination)
        first = c.load_cohort(self.directory/'cohort_500.csv')
        missing = {g['AppID']: inc.resolve_cache(g['AppID'], self.cache, [c.ORIGINAL_CACHE]) for g in first}
        r = p.evidence(first, missing)
        self.assertEqual(len(r['labels']), 1500)
        self.assertEqual(sum(v[1] == 'valid' for v in missing.values()), 100)
        train, evaluation = p.model_frames(r)
        self.assertFalse(set(train.appid) & set(evaluation.appid))
        self.assertTrue(evaluation.empty)  # No new games have been retrieved yet.

    def test_1000_game_selection_preserves_frozen_500_prefix_byte_reproducibly(self):
        first, repeated = self.directory/'1000.csv', self.directory/'1000_repeat.csv'
        receipt = c.select_cohort(1000, first)
        c.select_cohort(1000, repeated)
        self.assertEqual(first.read_bytes(), repeated.read_bytes())
        rows = c.read_csv(first)
        old = c.read_csv(c.ROOT/'data/cohorts/cohort_500.csv')
        self.assertEqual(rows[:500], old)
        self.assertEqual(len(rows), 1000)
        self.assertEqual(len({r['AppID'] for r in rows}), 1000)
        self.assertEqual(len({r['AppID'] for r in rows}-{r['AppID'] for r in old}), 500)
        self.assertEqual(receipt['cohort_sha256'], c.digest(first))

    def test_configurable_model_preparation_never_fits_or_overwrites_models(self):
        self.collect(FakeOpener())
        for stage in ['baseline', 'ensemble']:
            destination = self.directory/stage
            result = p.run(self.cohort, self.cache, destination, [], stage=stage)
            protocol = c.read_json(destination/f'{stage}_protocol.json')
            self.assertEqual(protocol['mode'], 'prepare_only')
            self.assertFalse((destination/f'{stage}_models').exists())
            self.assertEqual(len(protocol['predictors']), 15)
            self.assertEqual(len(result['features']), 3)

    def test_group_split_is_game_disjoint_and_ignores_evaluation_outcomes(self):
        rows = []
        for appid, group in [(999999991, 'development'), (999999992, 'evaluation')]:
            for year in [2023, 2024, 2025]:
                rows.append(dict(appid=appid, sale_year=year, discount_observed=year % 2,
                                 evaluation_group=group, model_eligible=True))
        result = dict(modeling=rows)
        train, evaluation = p.model_frames(result)
        self.assertEqual(set(train.appid), {999999991})
        self.assertEqual(set(train.sale_year), {2023, 2024})
        self.assertEqual(set(evaluation.appid), {999999992})
        self.assertEqual(set(evaluation.sale_year), {2025})
        altered = copy.deepcopy(result)
        for row in altered['modeling']:
            if row['evaluation_group'] == 'evaluation':
                row['discount_observed'] = 1-row['discount_observed']
        self.assertTrue(train.equals(p.model_frames(altered)[0]))

    def test_lookup_provenance_corruption_prevents_skip_and_does_not_become_negative(self):
        self.collect(FakeOpener())
        path = self.cache/'999999991.json'
        obj = c.read_json(path)
        obj['lookup_evidence']['params']['appid'] = '999999992'
        c.write_json(path, obj)
        opener = FakeOpener()
        report = self.collect(opener)
        self.assertEqual(opener.calls, [])
        self.assertEqual(report['already_cached_games'], 0)
        self.assertEqual(report['missing_or_uncertain_labels'], 3)


class PilotRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.games = c.load_cohort(ROOT/'data/intermediate/pilot_games.csv')
        caches = {g['AppID']: inc.resolve_cache(g['AppID'], Path(tempfile.gettempdir())/'unused-scalable-cache',
                                               [c.ORIGINAL_CACHE]) for g in cls.games}
        cls.result = p.evidence(cls.games, caches)

    def test_all_original_artifacts_and_100_caches_match_prior_sha256(self):
        inventory = c.read_json(ROOT/'tests/scalable_artifact_hashes.json')
        self.assertEqual(len(inventory), 219)
        for relative, expected in inventory.items():
            with self.subTest(path=relative):
                path = ROOT/relative
                self.assertEqual(path.stat().st_size, expected['size_bytes'])
                self.assertEqual(c.digest(path), expected['sha256'])
        caches = list(c.ORIGINAL_CACHE.glob('[0-9]*.json'))
        self.assertEqual(len(caches), 100)

    def test_all_300_labels_and_all_15_predictors_match_original_exactly(self):
        for key, filename in [('labels', 'autumn_sale_operational_labels.csv'), ('features', 'autumn_sale_features.csv')]:
            old = c.read_csv(ROOT/'data/intermediate'/filename)
            new = {(r['appid'], r['sale_year']): r for r in p.strings(self.result[key])}
            self.assertEqual(len(new), 300)
            for row in old:
                self.assertEqual(row, {k: new[(row['appid'], row['sale_year'])][k] for k in row})
        self.assertEqual(sum(r['discount_observed'] == 1 for r in self.result['labels']), 175)
        self.assertEqual(sum(r['discount_observed'] == 0 for r in self.result['labels']), 125)

    def test_reusing_original100_is_zero_http_and_does_not_copy_or_write_cache(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            report = inc.run(ROOT/'data/intermediate/pilot_games.csv', root/'cache', root/'run')
            self.assertEqual(report['already_cached_games'], 100)
            self.assertEqual(report['planned_games'], 0)
            self.assertFalse((root/'cache').exists())
            self.assertEqual(report['games_with_usable_historical_records'], 97)
            self.assertEqual(report['games_with_incomplete_historical_records'], 3)

    def test_temp_outputs_reproduce_original_csv_values_without_model_fitting(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            p.run(ROOT/'data/intermediate/pilot_games.csv', root/'cache', root/'processing')
            for filename, original in [('features.csv', 'autumn_sale_features.csv'),
                                        ('operational_labels.csv', 'autumn_sale_operational_labels.csv')]:
                actual = {(r['appid'], r['sale_year']): r for r in c.read_csv(root/'processing'/filename)}
                for row in c.read_csv(ROOT/'data/intermediate'/original):
                    self.assertEqual(row, {k: actual[(row['appid'], row['sale_year'])][k] for k in row})

    def test_saved_four_model_predictions_match_original_without_fitting(self):
        import pandas as pd
        import numpy as np
        b = c.module('regression_baseline', '08_train_baseline_models.py')
        e = c.module('regression_ensemble', '09_train_ensemble_models.py')
        frame = pd.read_csv(ROOT/'data/intermediate/autumn_sale_modeling_table.csv')
        valid = frame[frame.sale_year.eq(2025)]
        baseline = {name: b.joblib.load(ROOT/'models'/f'{name}.joblib') for name in ['bernoulli_baseline', 'logistic_regression']}
        ensemble = {'random_forest': b.joblib.load(ROOT/'models/random_forest.joblib'),
                    'xgboost': b.joblib.load(ROOT/'models/xgboost_model.joblib')}
        with patch.object(b, 'fit_models', side_effect=AssertionError('No pilot refitting')), \
             patch.object(e, 'fit_models', side_effect=AssertionError('No pilot refitting')):
            for predictions, filename in [(b.predict(baseline, valid), 'autumn_sale_2025_baseline_predictions.csv'),
                                           (e.predict(ensemble, valid), 'autumn_sale_2025_ensemble_predictions.csv')]:
                old = pd.read_csv(ROOT/'data/processed'/filename).sort_values(['model_name', 'appid']).reset_index(drop=True)
                predictions = predictions.sort_values(['model_name', 'appid']).reset_index(drop=True)
                for column in ['appid', 'sale_year', 'model_name', 'actual_label', 'predicted_class']:
                    self.assertEqual(predictions[column].tolist(), old[column].tolist())
                self.assertTrue(np.allclose(predictions.predicted_probability, old.predicted_probability, rtol=1e-12, atol=1e-14))
            self.assertEqual(len(b.predict(baseline, valid.head(7))), 14)
            self.assertEqual(len(e.predict(ensemble, valid.head(7))), 14)


if __name__ == '__main__':
    unittest.main()
