"""Offline contract/safety tests. Synthetic evidence is confined to temp directories."""
import contextlib
import copy
import csv
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse

spec = importlib.util.spec_from_file_location('itad', Path(__file__).resolve().parents[1] / 'src/03_fetch_itad.py')
itad = importlib.util.module_from_spec(spec)
spec.loader.exec_module(itad)
TEST_KEY = 'synthetic-credential-for-offline-testing-only'
GID = '018d937f-07fc-72ed-8517-d8e24cb1eb22'
RECORD = {'timestamp': '2022-12-27T11:21:08+01:00', 'shop': {'id': 61, 'name': 'Steam'},
          'deal': {'price': {'amount': 9.99, 'amountInt': 999, 'currency': 'USD'},
                   'regular': {'amount': 39.99, 'amountInt': 3999, 'currency': 'USD'}, 'cut': 75,
                   'voucher': None, 'url': 'https://example.test/raw?affiliate=keep'}}


class Response:
    status = 200
    headers = {'Content-Type': 'application/json'}

    def __init__(self, body):
        self.body = body.encode() if isinstance(body, str) else body

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class FakeOpener:
    def __init__(self):
        self.calls = []

    def open(self, req, timeout):
        self.calls.append(req)
        query = parse_qs(urlparse(req.full_url).query)
        if urlparse(req.full_url).path == itad.LOOKUP:
            assert set(query) == {'appid'}
            result = {'found': True, 'game': {'id': GID}}
        else:
            assert query == {'id': [GID], 'country': ['US'], 'shops': ['61'],
                             'since': ['2021-01-01T00:00:00Z']}
            result = [RECORD, dict(RECORD, deal=None)]
        assert TEST_KEY not in req.full_url
        assert req.get_header('Itad-api-key') == TEST_KEY
        return Response(json.dumps(result))


class ContractTests(unittest.TestCase):
    def test_nullable_deal_and_raw_preservation(self):
        data = [RECORD, dict(RECORD, deal=None)]
        before = copy.deepcopy(data)
        facts = itad.history_diagnostics(data)
        self.assertEqual(facts['steam_record_count'], 2)
        self.assertEqual(facts['null_deal_record_count'], 1)
        self.assertEqual(facts['earliest_history_timestamp'], '2022-12-27T10:21:08Z')
        self.assertEqual(data, before)
        self.assertEqual(itad.history_diagnostics([])['history_record_count'], 0)

    def test_invalid_structures(self):
        for data in ({}, [None], [dict(RECORD, timestamp='2023-01-01')],
                     [dict(RECORD, deal={})], [dict(RECORD, shop={'id': '61', 'name': 'Steam'})],
                     [dict(RECORD, deal=dict(RECORD['deal'], cut=float('nan'))) ]):
            with self.subTest(data=data), self.assertRaises(ValueError):
                itad.history_diagnostics(data)
        for data in ({}, {'found': 1}, {'found': True, 'game': {'id': 'bad'}}):
            with self.assertRaises(ValueError):
                itad.lookup_id(data)
        self.assertIsNone(itad.lookup_id({'found': False}))

    def test_shop_anomaly_preserved(self):
        data = [dict(RECORD, shop={'id': 35, 'name': 'GOG'})]
        self.assertEqual(itad.history_diagnostics(data)['unexpected_shop_record_count'], 1)
        self.assertEqual(data[0]['shop']['id'], 35)

    def test_credential_reflection_not_written(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'response.json'
            with self.assertRaises(ValueError):
                itad.save_json(path, {'reflection': TEST_KEY}, TEST_KEY)
            self.assertFalse(path.exists())


class RequestTests(unittest.TestCase):
    def client(self, side_effect):
        client = itad.Client(TEST_KEY, delay=0)
        from unittest.mock import Mock
        client.opener = Mock()
        client.opener.open.side_effect = side_effect
        return client

    def http_error(self, code, headers=None):
        return HTTPError('https://example.test', code, 'error', headers or {}, io.BytesIO(b'{"error":"raw"}'))

    def test_4xx_no_retry_and_auth_stops(self):
        for code in (400, 401, 403, 404):
            client = self.client([self.http_error(code)])
            _, evidence, error = client.get(itad.LOOKUP, {'appid': '7830'})
            self.assertEqual(client.calls, 1)
            self.assertEqual(error, f'HTTP_{code}')
            self.assertEqual(json.loads(evidence['body']), {'error': 'raw'})
            self.assertEqual(client.abort, code in (401, 403))

    def test_transient_retries_bounded(self):
        for failure in (URLError('connection failure'), self.http_error(503)):
            client = self.client([failure, failure, failure])
            with patch.object(itad.time, 'sleep'):
                _, _, error = client.get(itad.LOOKUP, {'appid': '7830'})
            self.assertEqual(client.calls, 3)
            self.assertTrue(error)

    def test_retry_after_respected(self):
        client = self.client([self.http_error(429, {'Retry-After': '7'}), Response('{"found":false}')])
        with patch.object(itad.time, 'sleep') as sleep:
            payload, _, error = client.get(itad.LOOKUP, {'appid': '7830'})
        self.assertEqual(payload, {'found': False})
        self.assertFalse(error)
        self.assertTrue(any(call.args == (7.0,) for call in sleep.call_args_list))
        client = self.client([self.http_error(429, {'Retry-After': '120'})])
        _, _, error = client.get(itad.LOOKUP, {'appid': '7830'})
        self.assertEqual(client.calls, 1)
        self.assertIn('stop', error)
        self.assertTrue(client.abort)

    def test_malformed_json_and_reflection(self):
        for body, expected in [('not-json', 'malformed_json'), (TEST_KEY, 'credential_reflection_response_withheld')]:
            client = self.client([Response(body)])
            _, evidence, error = client.get(itad.LOOKUP, {'appid': '7830'})
            self.assertEqual(error, expected)
            self.assertEqual(client.calls, 1)
            self.assertNotIn(TEST_KEY, json.dumps(evidence))


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        pilot = root / 'data/intermediate/pilot_games.csv'
        pilot.parent.mkdir(parents=True)
        pilot.write_bytes(itad.PILOT.read_bytes())
        master = root / 'data/intermediate/games_master.csv'
        master.write_text('offline source sentinel\n')
        self.patches = [patch.object(itad, name, value) for name, value in {
            'ROOT': root, 'PILOT': pilot, 'MASTER': master, 'CACHE': root / 'data/raw/itad',
            'MANIFEST': root / 'data/intermediate/itad_collection_manifest.csv',
            'REPORT': root / 'reports/itad_collection_report.md'}.items()]
        for p in self.patches:
            p.start()
        self.opener = FakeOpener()
        self.patches += [patch.object(itad, 'build_opener', return_value=self.opener),
                         patch.object(itad.time, 'sleep')]
        for p in self.patches[-2:]:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    def run_main(self, argv, key=TEST_KEY):
        with patch.dict(os.environ, {'ITAD_API_KEY': key}), contextlib.redirect_stdout(io.StringIO()):
            return itad.main(argv)

    def test_absent_auth_zero_calls_all_manifest_rows(self):
        self.assertEqual(self.run_main(['--limit', '3'], key=''), 1)
        self.assertEqual(len(self.opener.calls), 0)
        with itad.MANIFEST.open() as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 100)
        self.assertEqual(len({r['AppID'] for r in rows}), 100)
        self.assertTrue(all(r['history_status'] == 'not_collected' for r in rows))

    def test_smoke_then_cache_reuse_and_full_gate(self):
        self.assertEqual(self.run_main([]), 1)
        self.assertEqual(len(self.opener.calls), 0)
        self.assertEqual(self.run_main(['--limit', '3']), 0)
        self.assertEqual(len(self.opener.calls), 6)
        paths = list(itad.CACHE.glob('[0-9]*.json'))
        before = {p: p.read_bytes() for p in paths}
        self.assertEqual(self.run_main(['--limit', '3']), 0)
        self.assertEqual(len(self.opener.calls), 6)
        self.assertEqual(before, {p: p.read_bytes() for p in paths})
        self.assertTrue(itad.smoke_receipt_valid(itad.digest(itad.PILOT)))

    def test_corrupt_cache_and_force_archival(self):
        self.run_main(['--limit', '3'])
        path = itad.CACHE / '7830.json'
        path.write_text('{bad cache')
        self.assertFalse(itad.smoke_receipt_valid(itad.digest(itad.PILOT)))
        self.assertEqual(self.run_main(['--limit', '3']), 1)
        self.assertEqual(len(self.opener.calls), 6)
        self.assertEqual(self.run_main(['--limit', '3', '--force']), 0)
        archives = list((itad.CACHE / 'archive').glob('7830_*.json'))
        self.assertEqual(len(archives), 1)
        self.assertEqual(archives[0].read_text(), '{bad cache')

    def test_raw_configuration_and_mapping_checked(self):
        self.run_main(['--limit', '3'])
        path = itad.CACHE / '7830.json'
        obj = json.loads(path.read_text())
        self.assertEqual(obj['history_response'][0], RECORD)
        self.assertNotIn(TEST_KEY, path.read_text())
        obj['steam_appid'] = 8930
        itad.save_json(path, obj)
        self.assertEqual(itad.read_cache('7830')[1], 'invalid')

    def test_incomplete_lookup_reused_on_deliberate_retry(self):
        self.run_main(['--limit', '3'])
        path = itad.CACHE / '7830.json'
        obj = json.loads(path.read_text())
        obj['collection_metadata']['history_status'] = 'request_failed'
        obj['history_response'] = None
        itad.save_json(path, obj)
        self.assertEqual(self.run_main(['--limit', '3', '--retry-failed']), 0)
        self.assertEqual(len(self.opener.calls), 7)  # History only; lookup preserved.
        self.assertEqual(urlparse(self.opener.calls[-1].full_url).path, itad.HISTORY)

    def test_full_offline_fixture_then_audit(self):
        (itad.ROOT / 'PROJECT_STATUS.md').write_text('# Project Status\n\n## Current Phase\n\nPhase 3\n\n## Next Phase\n\nPhase 4\n')
        self.run_main(['--limit', '3'])
        self.assertEqual(self.run_main([]), 0)
        self.assertEqual(len(self.opener.calls), 200)
        self.assertEqual(self.run_main(['--validate-cache'], key=''), 0)
        self.assertEqual(len(self.opener.calls), 200)
        self.assertIn('Phase 5 — Historical Coverage', (itad.ROOT / 'PROJECT_STATUS.md').read_text())

    def test_lookup_error_retained_and_retried_explicitly(self):
        with patch.object(self.opener, 'open', side_effect=HTTPError('https://example.test', 400, 'bad', {}, io.BytesIO(b'{"error":"bad"}'))):
            self.assertEqual(self.run_main(['--limit', '1']), 1)
        obj, status, _ = itad.read_cache('7830')
        self.assertEqual(status, 'incomplete')
        self.assertEqual(obj['collection_metadata']['lookup_status'], 'lookup_error')
        self.run_main(['--limit', '1'])
        self.assertEqual(len(self.opener.calls), 0)
        self.run_main(['--limit', '1', '--retry-failed'])
        self.assertEqual(len(self.opener.calls), 2)

    def test_history_structure_anomaly_stops_smoke(self):
        original = self.opener.open
        def broken(req, timeout):
            if urlparse(req.full_url).path == itad.HISTORY:
                self.opener.calls.append(req)
                return Response('{"unexpected":"history object"}')
            return original(req, timeout)
        self.opener.open = broken
        self.assertEqual(self.run_main(['--limit', '3']), 1)
        self.assertEqual(len(self.opener.calls), 2)
        obj = json.loads((itad.CACHE / '7830.json').read_text())
        self.assertEqual(obj['history_response'], {'unexpected': 'history object'})
        self.assertEqual(obj['collection_metadata']['history_status'], 'invalid_response')
        self.assertFalse((itad.CACHE / 'smoke_test.json').exists())


if __name__ == '__main__':
    unittest.main()
