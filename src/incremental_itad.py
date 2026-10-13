"""Incremental ITAD collection. CLI is offline unless --live is explicit."""
import argparse
from collections import Counter
from contextlib import contextmanager
import copy
import fcntl
import json
import math
import os
from pathlib import Path
import shutil
import re
import time
from urllib.error import HTTPError

from cohort_io import (ROOT, ORIGINAL_CACHE, checked_path, digest, load_cohort,
                       module, read_json, require, write_csv, write_json)

itad = module('scalable_itad_core', '03_fetch_itad.py')


def resolve_cache(appid, cache_dir, reuse_dirs):
    """The writable namespace takes precedence, including its failure markers."""
    for directory in [cache_dir, *reuse_dirs]:
        path = checked_path(Path(directory)/f'{appid}.json')
        if path.exists():
            try:
                read_json(path)  # Reject duplicate keys/nonfinite values before legacy validation.
            except (ValueError, OSError, UnicodeError):
                return None, 'invalid', 'Invalid cache JSON', path
            obj, status, reason = itad.read_cache(appid, directory)
            return obj, status, reason, path
    return None, 'absent', '', Path(cache_dir)/f'{appid}.json'


class BudgetStop(RuntimeError):
    pass


def validated_interval(value):
    message = 'Request interval must be a finite, nonnegative number'
    try:
        interval = float(value)
    except (ValueError, TypeError, OverflowError):
        raise ValueError(message) from None
    require(not isinstance(value, bool) and math.isfinite(interval) and interval >= 0, message)
    return interval


class Journal:
    """Append-only reservations count even an interrupted, unknown HTTP attempt."""
    def __init__(self, cache_dir, maximum, readonly=False, request_interval_seconds=1.0):
        self.request_interval_seconds = validated_interval(request_interval_seconds)
        self.path = checked_path(Path(cache_dir)/'http_attempts.jsonl', write=True)
        self.maximum = maximum
        self.events = []
        if self.path.exists():
            body = self.path.read_bytes()
            require(bool(body) and body.endswith(b'\n'), 'Empty/incomplete journal; stop for manual recovery')
            def unique(items):
                out = {}
                for k, v in items:
                    require(k not in out, 'Duplicate journal field')
                    out[k] = v
                return out
            self.events = [json.loads(line, object_pairs_hook=unique,
                           parse_constant=lambda _: require(False, 'Nonfinite journal')) for line in body.splitlines()]
        binding = dict(kind='binding', schema_version=1, configuration=itad.CONFIG,
                       cache_directory=str(self.path.parent))
        if self.events:
            require(self.events[0] == binding, 'Journal configuration/directory mismatch')
            seen = set()
            completed = set()
            rounds = {}
            for e in self.events[1:]:
                require(e['kind'] in {'attempt', 'result', 'round', 'cooldown'}, 'Unknown journal event')
                if e['kind'] in {'attempt', 'round'}:
                    require(isinstance(e['appid'], str) and re.fullmatch(r'[1-9][0-9]*', e['appid']) and
                            int(e['appid']) <= 2**32-1 and type(e['round']) is int, 'Invalid journal game/round')
                if e['kind'] == 'round':
                    require(e['round'] == rounds.get(e['appid'], 0)+1, 'Invalid retry round sequence')
                    rounds[e['appid']] = e['round']
                if e['kind'] == 'attempt':
                    require(type(e['sequence']) is int and e['sequence'] == len(seen)+1 and
                            e['endpoint'] in {itad.LOOKUP, itad.HISTORY} and
                            e['round'] == rounds.get(e['appid'], 0) and math.isfinite(e['started_epoch']),
                            'Invalid attempt sequence or endpoint')
                    seen.add(e['sequence'])
                elif e['kind'] == 'result':
                    require(e['sequence'] in seen and e['sequence'] not in completed, 'Invalid journal result')
                    require(e['http_status'] is None or (type(e['http_status']) is int and
                            100 <= e['http_status'] < 600), 'Invalid journal HTTP status')
                    completed.add(e['sequence'])
                elif e['kind'] == 'cooldown':
                    require(math.isfinite(e['not_before_epoch']), 'Invalid provider cooldown')
        elif not readonly:
            self.append(binding)
        else:
            raise ValueError('Empty journal; stop for manual recovery')

    def append(self, event):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open('ab') as f:
            f.write((json.dumps(event, sort_keys=True, allow_nan=False)+'\n').encode())
            f.flush()
            os.fsync(f.fileno())
        self.events.append(event)

    def counts(self):
        attempts = [e for e in self.events if e['kind'] == 'attempt']
        results = [e for e in self.events if e['kind'] == 'result']
        return dict(total_http_attempts=len(attempts), successful_api_requests=sum(e['http_status'] == 200 for e in results),
                    failed_api_requests=sum(e['http_status'] != 200 for e in results),
                    interrupted_or_unknown_attempts=len(attempts)-len(results))

    def round_for(self, appid):
        return max((e['round'] for e in self.events if e.get('appid') == appid), default=0)

    def new_round(self, appid):
        value = self.round_for(appid)+1
        self.append(dict(kind='round', appid=appid, round=value))
        return value

    def used(self, appid, endpoint, round_id):
        return sum(e['kind'] == 'attempt' and e['appid'] == appid and e['endpoint'] == endpoint and
                   e['round'] == round_id for e in self.events if e['kind'] == 'attempt')

    def reserve(self, appid, endpoint, round_id):
        if any(e['kind'] == 'cooldown' and e['not_before_epoch'] > time.time() for e in self.events):
            raise BudgetStop('Provider cooldown has not elapsed')
        number = self.counts()['total_http_attempts']+1
        if number > self.maximum or self.used(appid, endpoint, round_id) >= 3:
            raise BudgetStop('Attempt budget or endpoint limit reached')
        attempts = [e for e in self.events if e['kind'] == 'attempt']
        if attempts:
            time.sleep(max(0, self.request_interval_seconds-(time.time()-attempts[-1]['started_epoch'])))
        self.append(dict(kind='attempt', sequence=number, appid=appid, endpoint=endpoint,
                         round=round_id, started_epoch=time.time()))
        return number


class RecordingOpener:
    def __init__(self, client, opener, journal):
        self.client, self.opener, self.journal = client, opener, journal

    def open(self, request, timeout):
        c = self.client
        number = self.journal.reserve(c.appid, c.endpoint, c.round_id)
        # Journal pacing/fsync may delay the actual start beyond the client's
        # initial timestamp. Measure the next interval from this HTTP start.
        c.last_request = time.monotonic()
        try:
            response = self.opener.open(request, timeout=timeout)
        except HTTPError as error:
            self.journal.append(dict(kind='result', sequence=number, http_status=error.code))
            self.cooldown(error.headers)
            raise
        except (OSError, TimeoutError, itad.HTTPException):
            self.journal.append(dict(kind='result', sequence=number, http_status=None))
            raise
        self.journal.append(dict(kind='result', sequence=number, http_status=response.status))
        self.cooldown(response.headers)
        return response

    def cooldown(self, headers):
        if headers and 'Retry-After' in headers:
            try:
                value = headers['Retry-After']
                until = (time.time()+float(value) if value.isdigit() else
                         itad.parsedate_to_datetime(value).timestamp())
                if until > time.time():
                    self.journal.append(dict(kind='cooldown', not_before_epoch=until))
            except (ValueError, TypeError, OverflowError):
                pass  # The original client handles invalid Retry-After and stops.


class RecordingClient(itad.Client):
    stop_on_rate_limit = True

    def __init__(self, key, journal, opener=None):
        super().__init__(key, delay=journal.request_interval_seconds, attempts=3, timeout=30)
        self.journal = journal
        self.opener = RecordingOpener(self, opener or self.opener, journal)
        self.appid, self.endpoint, self.round_id = '', '', 0

    def get(self, endpoint, params):
        self.endpoint = endpoint
        self.attempts = 3-self.journal.used(self.appid, endpoint, self.round_id)
        if self.attempts <= 0:
            raise BudgetStop('Endpoint attempt limit reached; explicit retry needed')
        return super().get(endpoint, params)


@contextmanager
def cache_lock(directory):
    directory.mkdir(parents=True, exist_ok=True)
    path = checked_path(directory/'.collection.lock', write=True)
    with path.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Another collector is using this cache') from None
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def paths(cohort, cache_dir, reuse_dirs, output_dir):
    cohort = checked_path(cohort)
    cache_dir, output_dir = checked_path(cache_dir, write=True), checked_path(output_dir, write=True)
    reuse_dirs = [checked_path(p) for p in reuse_dirs]
    require(cache_dir != output_dir and not cache_dir.is_relative_to(output_dir) and
            not output_dir.is_relative_to(cache_dir), 'Cache and run outputs must be separate directories')
    for directory in [cache_dir, output_dir]:
        require(not cohort.is_relative_to(directory), 'Output directory contains the input cohort')
        for reuse in reuse_dirs:
            require(not directory.is_relative_to(reuse) and not reuse.is_relative_to(directory),
                    'Output overlaps a read-only cache')
    require(not cache_dir.is_relative_to(ORIGINAL_CACHE), 'Original caches are read-only')
    return cohort, cache_dir, reuse_dirs, output_dir


def run(cohort, cache_dir, output_dir, reuse_dirs=(ORIGINAL_CACHE,), live=False,
        retry_failed=False, stale=(), maximum=None, key='', opener=None,
        raw_only=False, max_new_games=None, request_interval_seconds=1.0):
    request_interval_seconds = validated_interval(request_interval_seconds)
    started = time.monotonic()
    cohort, cache_dir, reuse_dirs, output_dir = paths(cohort, cache_dir, reuse_dirs, output_dir)
    games = load_cohort(cohort)
    require(len(games) <= 5000, 'Cohorts above 5000 require an explicit capacity review')
    stale = set(stale)
    require(stale <= {g['AppID'] for g in games}, 'Stale AppID outside frozen cohort')
    maximum = maximum if maximum is not None else 6*len(games)
    require(maximum >= 0, 'Invalid cumulative attempt budget')
    require(max_new_games is None or (type(max_new_games) is int and max_new_games >= 0),
            'Invalid new-game limit')
    already = 0
    planned, planned_requests, newly = [], 0, 0
    for g in games:
        appid = g['AppID']
        obj, status, _, path = resolve_cache(appid, cache_dir, reuse_dirs)
        if appid in stale:
            require(path.parent == cache_dir, 'Refresh cannot overwrite read-only reused caches')
        already += status == 'valid'
        interrupted = (obj and obj['collection_metadata']['lookup_status'] == 'matched' and
                       obj['collection_metadata']['history_status'] == 'not_requested')
        if status == 'valid' and appid not in stale:
            continue
        if status == 'invalid' and appid not in stale:
            continue
        if status == 'incomplete' and not (retry_failed or interrupted):
            continue
        # Limit eligible work in frozen cohort order, including partial checkpoints.
        # Keep scanning so already_cached_games covers the entire cohort.
        if max_new_games is not None and len(planned) >= max_new_games:
            continue
        reuse_lookup = obj and status == 'incomplete' and obj['collection_metadata']['lookup_status'] == 'matched'
        planned.append((appid, copy.deepcopy(obj) if reuse_lookup and appid not in stale else None,
                        bool((retry_failed and status == 'incomplete' and not interrupted) or appid in stale)))
        planned_requests += 1 if reuse_lookup and appid not in stale else 2
    before = dict(total_http_attempts=0, successful_api_requests=0, failed_api_requests=0,
                  interrupted_or_unknown_attempts=0)
    after = before.copy()
    stopped = ''
    if live:
        # Match the original collector: normalize before validating header content.
        key = key.strip()
        require(bool(key), 'ITAD_API_KEY is required only for explicit live collection')
        require(not any(c in key for c in '\r\n'),
                'ITAD_API_KEY contains invalid header characters; zero API calls.')
        with cache_lock(cache_dir):
            journal = Journal(cache_dir, maximum, request_interval_seconds=request_interval_seconds)
            before = journal.counts()
            client = RecordingClient(key, journal, opener)
            try:
                for appid, previous, new_round in planned:
                    # Recheck under the lock; dry-run planning does not grant permission to overwrite.
                    current, status, _, path = resolve_cache(appid, cache_dir, reuse_dirs)
                    if status == 'valid' and appid not in stale:
                        continue
                    if path.exists() and path.parent == cache_dir:
                        saved = checked_path(cache_dir/'archive'/appid/(digest(path)+'.json'), write=True)
                        if not saved.exists():
                            # Preserve exact old bytes, including an invalid cache being
                            # explicitly refreshed. Originals in reuse_dirs never enter here.
                            saved.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copyfile(path, saved)
                        require(digest(saved) == digest(path), 'Refresh backup integrity failed')
                    client.appid = appid
                    client.round_id = journal.new_round(appid) if new_round else journal.round_for(appid)
                    destination = cache_dir/f'{appid}.json'
                    persist = lambda obj, p=destination: write_json(p, obj, key)
                    obj = itad.collect(appid, client, previous, persist=persist)
                    persist(obj)
                    if obj['collection_metadata']['history_status'] in itad.SUCCESS:
                        newly += 1
                    if client.abort:
                        stopped = 'Provider, credential-reflection, or schema safeguard stopped collection'
                        break
            except BudgetStop as error:
                stopped = str(error)+'; checkpoints preserved'
            except KeyboardInterrupt:
                stopped = 'Interrupted; checkpoints preserved'
            after = journal.counts()
    elif (cache_dir/'http_attempts.jsonl').exists():
        # Read-only journal validation/counting; existing binding prevents append.
        journal = Journal(cache_dir, maximum, readonly=True,
                          request_interval_seconds=request_interval_seconds)
        before = after = journal.counts()
    report = dict(mode='live' if live else 'offline', target_games=len(games), already_cached_games=already,
                  newly_retrieved_games=newly, planned_games=len(planned),
                  estimated_requests_without_retries=planned_requests, maximum_cumulative_attempts=maximum,
                  request_interval_seconds=request_interval_seconds,
                  run_requests={k: after[k]-before[k] for k in after}, cumulative_requests=after,
                  cohort_sha256=digest(cohort), configuration=itad.CONFIG, stopped=stopped,
                  collection_duration_seconds=round(time.monotonic()-started, 6))
    if not raw_only:
        from cohort_pipeline import evidence, quality
        result = evidence(games, lambda appid: resolve_cache(appid, cache_dir, reuse_dirs))
        report.update(quality(result))
        report['collection_duration_seconds'] = round(time.monotonic()-started, 6)
    rows = []
    for g in games:
        obj, status, reason, path = resolve_cache(g['AppID'], cache_dir, reuse_dirs)
        row = itad.manifest_row(g, obj, status, reason)
        row['cache_path'] = str(path) if path.exists() else ''
        row['evaluation_group'] = g['evaluation_group']
        rows.append(row)
    if raw_only:
        complete = sum(row['cache_status'] == 'valid' for row in rows)
        report.update(raw_only=True, max_new_games=max_new_games,
                      planned_appids=[appid for appid, _, _ in planned],
                      games_with_complete_caches=complete,
                      games_with_unresolved_failures=len(games)-complete,
                      successful_lookups=sum(row['lookup_status'] in {'matched', 'not_found'} for row in rows),
                      successful_histories=sum(row['history_status'] in itad.SUCCESS for row in rows),
                      cache_status_counts=dict(Counter(row['cache_status'] for row in rows)))
    write_csv(output_dir/'collection_manifest.csv', rows, itad.FIELDS+['evaluation_group'])
    write_json(output_dir/'collection_quality.json', report, key)
    return report


def cli(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cohort', type=Path, required=True)
    p.add_argument('--cache-dir', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--reuse-cache', type=Path, action='append', default=None)
    p.add_argument('--live', action='store_true', help='Explicitly enable HTTP; omitted means offline')
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--retry-failed', action='store_true')
    p.add_argument('--stale-appid', action='append', default=[])
    p.add_argument('--max-total-attempts', type=int)
    p.add_argument('--raw-only', action='store_true',
                   help='Write collection summaries without labels, features or modeling calculations')
    p.add_argument('--max-new-games', type=int,
                   help='Limit eligible incomplete/uncached games in frozen cohort order; complete caches are skipped')
    p.add_argument('--request-interval-seconds', type=validated_interval, default=1.0,
                   help='Minimum seconds between HTTP request starts, including retries and restarts (default: 1)')
    args = p.parse_args(argv)
    require(not (args.live and args.dry_run), '--live and --dry-run are mutually exclusive')
    key = os.environ.get('ITAD_API_KEY', '') if args.live else ''
    report = run(args.cohort, args.cache_dir, args.output_dir,
                 args.reuse_cache if args.reuse_cache is not None else (ORIGINAL_CACHE,), args.live,
                 args.retry_failed, args.stale_appid, args.max_total_attempts, key,
                 raw_only=args.raw_only, max_new_games=args.max_new_games,
                 request_interval_seconds=args.request_interval_seconds)
    print(json.dumps({k: report[k] for k in ('mode', 'target_games', 'already_cached_games',
                     'newly_retrieved_games', 'planned_games', 'estimated_requests_without_retries', 'stopped')}))
    return 2 if report['stopped'] else 0
