"""Phase 4: preserve raw ITAD evidence; no sale labels or coverage decisions.

Set ITAD_API_KEY in the process environment, then run --limit 3 first.
Uses Python's standard library; .env files are not loaded automatically.
"""
import argparse
import csv
import hashlib
from http.client import HTTPException
import io
import json
import math
import os
from pathlib import Path
import re
import socket
import statistics
import sys
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / 'data/intermediate/pilot_games.csv'
MASTER = ROOT / 'data/intermediate/games_master.csv'
CACHE = ROOT / 'data/raw/itad'
MANIFEST = ROOT / 'data/intermediate/itad_collection_manifest.csv'
REPORT = ROOT / 'reports/itad_collection_report.md'
BASE = 'https://api.isthereanydeal.com'
LOOKUP = '/games/lookup/v1'
HISTORY = '/games/history/v2'
CONFIG = {'api_base': BASE, 'lookup_endpoint': LOOKUP, 'history_endpoint': HISTORY,
          'country': 'US', 'requested_since': '2021-01-01T00:00:00Z', 'steam_shop_id': 61}
FIELDS = ['AppID', 'Name', 'itad_game_id', 'lookup_status', 'history_status',
          'history_record_count', 'earliest_history_timestamp', 'latest_history_timestamp',
          'steam_record_count', 'unexpected_shop_record_count', 'null_deal_record_count',
          'cache_path', 'country', 'requested_since', 'steam_shop_id', 'collected_at',
          'cache_status', 'reason']
SUCCESS = {'history_received', 'empty_history'}
DOCS = 'https://docs.isthereanydeal.com/'
SPEC = 'https://github.com/IsThereAnyDeal/API/blob/master/dist/openapi.json'


def utcnow():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def stamp(value):
    if not isinstance(value, str):
        raise ValueError('timestamp must be an ISO date-time string')
    value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if value.tzinfo is None:
        raise ValueError('timestamp must include timezone')
    return value.astimezone(timezone.utc)


def load_pilot():
    with PILOT.open(encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream))
    ids = [r['AppID'] for r in rows]
    if len(rows) != 100 or len(set(ids)) != 100:
        raise ValueError('Expected exactly 100 unique pilot AppIDs')
    if any(not re.fullmatch(r'[1-9][0-9]*', x) or int(x) > 2**32-1 for x in ids):
        raise ValueError('Invalid pilot AppID')
    if any(not r['Name'].strip() for r in rows):
        raise ValueError('Blank pilot game name')
    return rows


def lookup_id(payload):
    if not isinstance(payload, dict) or type(payload.get('found')) is not bool:
        raise ValueError('lookup response must contain boolean found')
    if not payload['found']:
        return None
    game = payload.get('game')
    if not isinstance(game, dict) or not isinstance(game.get('id'), str):
        raise ValueError('found lookup requires game.id')
    UUID(game['id'])
    return game['id']


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def history_diagnostics(payload):
    if not isinstance(payload, list):
        raise ValueError('history response must be an array')
    timestamps, steam, other, nulls = [], 0, 0, 0
    for i, record in enumerate(payload):
        try:
            if not isinstance(record, dict) or not {'timestamp', 'shop', 'deal'} <= record.keys():
                raise ValueError('missing timestamp/shop/deal')
            ts = stamp(record['timestamp'])
            shop = record['shop']
            if (not isinstance(shop, dict) or type(shop.get('id')) is not int
                    or not isinstance(shop.get('name'), str)):
                raise ValueError('invalid shop object')
            if shop['id'] == 61:
                steam += 1
                timestamps.append(ts)
            else:
                other += 1
            deal = record['deal']
            if deal is None:
                nulls += 1
                continue
            if not isinstance(deal, dict) or not {'price', 'regular', 'cut'} <= deal.keys():
                raise ValueError('invalid deal object')
            if not number(deal['cut']) or not 0 <= deal['cut'] <= 100:
                raise ValueError('invalid cut')
            for field in ('price', 'regular'):
                price = deal[field]
                if (not isinstance(price, dict) or not number(price.get('amount'))
                        or price['amount'] < 0 or type(price.get('amountInt')) is not int
                        or price['amountInt'] < 0 or not isinstance(price.get('currency'), str)
                        or not re.fullmatch(r'[A-Z]{3}', price['currency'])):
                    raise ValueError(f'invalid {field}')
        except (ValueError, TypeError, KeyError, OverflowError) as error:
            raise ValueError(f'history record {i}: {error}') from None
    fmt = lambda t: t.isoformat().replace('+00:00', 'Z')
    return {'history_record_count': len(payload), 'steam_record_count': steam,
            'unexpected_shop_record_count': other, 'null_deal_record_count': nulls,
            'earliest_history_timestamp': fmt(min(timestamps)) if timestamps else '',
            'latest_history_timestamp': fmt(max(timestamps)) if timestamps else ''}


def safe_write(path, body, key=''):
    """Atomic replacement; refuse to write a response that reflects credentials."""
    if key and (key in body or json.dumps(key)[1:-1] in body):
        raise ValueError('credential reflection detected; response withheld')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(body, encoding='utf-8')
    temporary.replace(path)


def save_json(path, payload, key=''):
    safe_write(path, json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + '\n', key)


def read_cache(appid):
    path = CACHE / f'{appid}.json'
    if not path.exists():
        return None, 'absent', ''
    try:
        obj = json.loads(path.read_text(encoding='utf-8'))
        if obj.get('steam_appid') != int(appid) or obj.get('request_configuration') != CONFIG:
            raise ValueError('AppID or request configuration mismatch')
        meta = obj['collection_metadata']
        stamp(meta['collected_at'])
        if meta['lookup_status'] == 'lookup_error':
            if obj['lookup_evidence']['params'] != {'appid': appid}:
                raise ValueError('lookup request provenance mismatch')
            return obj, 'incomplete', meta.get('reason', 'cached lookup failed')
        gid = lookup_id(obj['lookup_response'])
        if gid != obj.get('itad_game_id'):
            raise ValueError('cached mapping disagrees with lookup response')
        evidence = obj['lookup_evidence']
        if evidence['params'] != {'appid': appid} or evidence['http_status'] != 200:
            raise ValueError('missing AppID lookup request provenance')
        if json.loads(evidence['body']) != obj['lookup_response']:
            raise ValueError('lookup body disagrees with parsed response')
        if gid is None:
            if meta['lookup_status'] != 'not_found' or meta['history_status'] != 'lookup_not_found':
                raise ValueError('inconsistent unmatched cache status')
            return obj, 'valid', ''
        if meta['lookup_status'] != 'matched':
            raise ValueError('inconsistent matched cache status')
        if meta['history_status'] not in SUCCESS | {'shop_anomaly'}:
            return obj, 'incomplete', meta.get('reason', 'cached history request failed')
        evidence = obj['history_evidence']
        if evidence['params'] != history_params(gid) or evidence['http_status'] != 200:
            raise ValueError('history request provenance mismatch')
        if json.loads(evidence['body']) != obj['history_response']:
            raise ValueError('history body disagrees with parsed response')
        diagnostics = history_diagnostics(obj['history_response'])
        expected = ('shop_anomaly' if diagnostics['unexpected_shop_record_count'] else
                    'history_received' if diagnostics['history_record_count'] else 'empty_history')
        if meta['history_status'] != expected:
            raise ValueError('history status disagrees with response')
        return obj, 'valid', ''
    except (ValueError, KeyError, TypeError, AttributeError, OSError) as error:
        # Never print cached response content or arbitrary exception values.
        return None, 'invalid', 'corrupt, inconsistent, or incompatible cache; use --force to archive and refresh'


def history_params(gid):
    return {'id': gid, 'country': CONFIG['country'], 'shops': str(CONFIG['steam_shop_id']),
            'since': CONFIG['requested_since']}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Do not forward authentication to another URL.


class Client:
    def __init__(self, key, delay=1.0, attempts=3, timeout=30):
        self.key, self.delay, self.attempts, self.timeout = key, delay, attempts, timeout
        self.opener = build_opener(NoRedirect())
        self.calls, self.last_request, self.abort = 0, None, False

    def get(self, endpoint, params):
        evidence = {'endpoint': endpoint, 'params': params, 'attempts': []}
        for attempt in range(self.attempts):
            if self.last_request is not None:
                time.sleep(max(0, self.delay - (time.monotonic() - self.last_request)))
            req = Request(BASE + endpoint + '?' + urlencode(params), headers={
                'ITAD-API-Key': self.key, 'Accept': 'application/json',
                'User-Agent': 'SteamSaleResearch-Phase4/1.0'})
            self.last_request = time.monotonic()
            self.calls += 1
            code, body, headers, reason = None, None, {}, ''
            try:
                with self.opener.open(req, timeout=self.timeout) as response:
                    code, body, headers = response.status, response.read().decode('utf-8'), response.headers
            except HTTPError as error:
                code, body, headers = error.code, error.read().decode('utf-8', errors='replace'), error.headers
            except (URLError, TimeoutError, socket.timeout, ConnectionError, OSError, HTTPException):
                reason = 'timeout_or_connection_failure'
            except UnicodeDecodeError:
                reason = 'invalid_utf8_response'
            if body is not None and (self.key in body or json.dumps(self.key)[1:-1] in body):
                body, reason, self.abort = None, 'credential_reflection_response_withheld', True
            selected = {k: headers[k] for k in ('Retry-After', 'Date', 'Content-Type') if k in headers}
            evidence.update(http_status=code, body=body, response_headers=selected, received_at=utcnow())
            evidence['attempts'].append({'http_status': code, 'reason': reason, 'at': evidence['received_at']})
            if code == 200 and not reason:
                try:
                    payload = json.loads(body, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
                    return payload, evidence, ''
                except (ValueError, TypeError):
                    reason = 'malformed_json'
            reason = reason or f'HTTP_{code}'
            if code in (401, 403, 429) or (code is not None and 300 <= code < 400):
                self.abort = True
            transient = code in (408, 429, 500, 502, 503, 504) or reason == 'timeout_or_connection_failure'
            if not transient or attempt + 1 == self.attempts:
                return None, evidence, reason
            pause = 2 ** (attempt + 1)
            if 'Retry-After' in headers:
                try:
                    raw = headers['Retry-After']
                    pause = max(pause, float(raw) if raw.isdigit() else
                                (parsedate_to_datetime(raw) - datetime.now(timezone.utc)).total_seconds())
                except (ValueError, TypeError, OverflowError):
                    return None, evidence, 'invalid_retry_after; collection stopped'
            elif code == 429:
                return None, evidence, 'HTTP_429_missing_retry_after; collection stopped'
            if pause > 60:
                self.abort = True
                return None, evidence, 'retry_after_exceeds_60s; stop and resume later'
            print(f'Transient request failure; waiting {pause:g}s before bounded retry.', flush=True)
            time.sleep(pause)
        return None, evidence, reason


def archive(path):
    if path.exists():
        target = CACHE / 'archive' / f'{path.stem}_{time.time_ns()}.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        path.rename(target)


def collect(appid, client, previous=None):
    obj = previous or {'steam_appid': int(appid), 'itad_game_id': None,
                       'request_configuration': CONFIG.copy(), 'lookup_response': None,
                       'history_response': None}
    meta = {'collected_at': utcnow(), 'lookup_status': 'lookup_error',
            'history_status': 'not_requested', 'reason': ''}
    obj['collection_metadata'] = meta
    if previous is None:
        payload, evidence, error = client.get(LOOKUP, {'appid': appid})
        obj.update(lookup_response=payload, lookup_evidence=evidence)
        if error:
            meta['reason'] = error
            return obj
        try:
            obj['itad_game_id'] = lookup_id(payload)
        except ValueError:
            meta['reason'] = 'unexpected_lookup_structure'
            client.abort = True
            return obj
    gid = obj['itad_game_id']
    if gid is None:
        meta.update(lookup_status='not_found', history_status='lookup_not_found', reason='AppID lookup returned found=false')
        return obj
    meta['lookup_status'] = 'matched'
    # Persist the authoritative lookup even if interrupted before history completes.
    save_json(CACHE / f'{appid}.json', obj, client.key)
    payload, evidence, error = client.get(HISTORY, history_params(gid))
    obj.update(history_response=payload, history_evidence=evidence)
    if error:
        meta.update(history_status='request_failed', reason=error)
        return obj
    try:
        facts = history_diagnostics(payload)
    except ValueError:
        meta.update(history_status='invalid_response', reason='unexpected_history_structure; raw response preserved')
        client.abort = True
        return obj
    status = 'history_received' if payload else 'empty_history'
    if facts['unexpected_shop_record_count']:
        status = 'shop_anomaly'
        meta['reason'] = 'non-Steam records returned despite shops=61; raw response preserved'
        client.abort = True
    meta['history_status'] = status
    return obj


def manifest_row(game, obj, cache_status, reason=''):
    row = dict.fromkeys(FIELDS, '')
    row.update(AppID=game['AppID'], Name=game['Name'], country=CONFIG['country'],
               requested_since=CONFIG['requested_since'], steam_shop_id=CONFIG['steam_shop_id'],
               lookup_status='not_collected', history_status='not_collected',
               cache_status=cache_status, reason=reason)
    if obj is None:
        return row
    meta = obj['collection_metadata']
    row.update(itad_game_id=obj.get('itad_game_id') or '', lookup_status=meta['lookup_status'],
               history_status=meta['history_status'], collected_at=meta['collected_at'],
               cache_path=f'data/raw/itad/{game["AppID"]}.json', reason=meta.get('reason', ''))
    if meta['history_status'] in SUCCESS | {'shop_anomaly'}:
        row.update(history_diagnostics(obj['history_response']))
    return row


def table(headers, rows):
    def line(values):
        return '| ' + ' | '.join(str(v).replace('|', '\\|').replace('\n', ' ') for v in values) + ' |'
    return '\n'.join([line(headers), line(['---'] * len(headers))] + [line(r) for r in rows])


def write_outputs(games, rows, run, hashes, key=''):
    if len(rows) != 100 or {r['AppID'] for r in rows} != {g['AppID'] for g in games}:
        raise ValueError('Manifest must represent all 100 pilot AppIDs')
    if any(digest(path) != value for path, value in hashes.items()):
        raise ValueError('Phase 2/3 dataset changed')
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(rows)
    safe_write(MANIFEST, output.getvalue(), key)
    good = [r for r in rows if r['history_status'] in SUCCESS]
    nonempty = [r for r in good if r['steam_record_count']]
    failures = [r for r in rows if r['lookup_status'] in {'not_found', 'lookup_error'}
                or r['history_status'] in {'request_failed', 'invalid_response', 'shop_anomaly'}
                or r['cache_status'] in {'invalid', 'incomplete'}]
    count = lambda field, status: sum(r[field] == status for r in rows)
    facts = [('Pilot games', len(rows)), ('Matched', count('lookup_status', 'matched')),
             ('Not found', count('lookup_status', 'not_found')), ('Lookup errors', count('lookup_status', 'lookup_error')),
             ('Not collected', count('lookup_status', 'not_collected')),
             ('Successful histories (including empty)', len(good)),
             ('Nonempty histories', count('history_status', 'history_received')),
             ('Empty histories', count('history_status', 'empty_history')),
             ('History request failures', count('history_status', 'request_failed')),
             ('Failed/unmatched/invalid games (unique)', len(failures)),
             ('Total history records', sum(int(r['history_record_count'] or 0) for r in rows)),
             ('Steam records', sum(int(r['steam_record_count'] or 0) for r in rows)),
             ('Unexpected shop records', sum(int(r['unexpected_shop_record_count'] or 0) for r in rows))]
    earliest = [r['earliest_history_timestamp'] for r in nonempty]
    latest = [r['latest_history_timestamp'] for r in nonempty]
    counts = [int(r['history_record_count']) for r in good]
    lines = ['# ITAD Collection Report — Phase 4', '', f'**Validation: {run["validation"]}.** {run["reason"]}', '',
             '## Configuration and verified API contract', '',
             f'Official [documentation]({DOCS}) and [OpenAPI schema]({SPEC}) verified 2026-10-05; API 2.11.0.',
             'Header authentication: `ITAD-API-Key`, supplied only from environment variable `ITAD_API_KEY`.',
             f'Lookup: `GET {LOOKUP}?appid=<Steam AppID>`. History: `GET {HISTORY}`.',
             '`id=<ITAD UUID>`, `country=US`, `shops=61`, `since=2021-01-01T00:00:00Z`.',
             'The official default without since is three months. Shops use comma-separated integer IDs; Steam is 61.',
             'Lookup returns boolean found and, when matched, game.id. History is an array of timestamp/shop/deal records.',
             'The schema permits deal=null; non-null deals contain price, regular, and cut. All extra fields and original response text are retained.',
             'Documented responses: 200, 400 and generic errors. Handle 401/403 by stopping, and transient 408/5xx with at most three attempts.',
             'Verified-email default limit: 1,000 requests per five minutes; actual account limits may differ. HTTP 429 supplies Retry-After.',
             'One second minimum between requests. Respect Retry-After; stop rather than shorten waits longer than 60 seconds. Never follow redirects.',
             'No material API differences from the requested methodology. Nullable deals are explicitly preserved.', '',
             f'Run time (UTC): {run["at"]}. Authenticated requests this run: {run["api_calls"]}.',
             f'Cache reuse this run: {run["cache_reused"]}. Smoke test: {run["smoke_test"]}.',
             'Valid same-configuration caches are reused. Corrupt or incompatible caches require --force; prior artifacts are archived.',
             'Incomplete matched caches retain lookup evidence; --retry-failed deliberately retries history. --force refreshes lookup and history.',
             'Full collection requires a three-game smoke receipt bound to the pilot hash, request configuration and cache hashes.', '',
             '## Lookup and history results', '', table(['Metric', 'Count'], facts), '',
             'Uncollected games are not request failures or empty histories. A blocked authentication run makes zero authenticated calls.', '',
             '## Temporal diagnostics (Steam records only)', '',
             f'Global earliest/latest: {min(earliest) if earliest else "unavailable"} / {max(latest) if latest else "unavailable"}.',
             f'Earliest-timestamp range: {min(earliest) if earliest else "unavailable"} to {max(earliest) if earliest else "unavailable"}.',
             f'Latest-timestamp range: {min(latest) if latest else "unavailable"} to {max(latest) if latest else "unavailable"}.',
             f'Records per successful game min/median/max: {min(counts) if counts else "unavailable"} / {statistics.median(counts) if counts else "unavailable"} / {max(counts) if counts else "unavailable"}.', '']
    boundaries = [('Before Autumn 2023 start', 'earliest_history_timestamp', '2023-11-21', 'before'),
                  ('After Autumn 2023 end date', 'latest_history_timestamp', '2023-11-28', 'after'),
                  ('Before Autumn 2024 start', 'earliest_history_timestamp', '2024-11-27', 'before'),
                  ('After Autumn 2024 end date', 'latest_history_timestamp', '2024-12-04', 'after')]
    diagnostics = [(label, sum(bool(r[field]) and (r[field][:10] < date if side == 'before' else r[field][:10] > date)
                               for r in good)) for label, field, date, side in boundaries]
    lines += [table(['Descriptive calendar-date comparison', 'Games'], diagnostics), '',
              'Boundaries come from PROJECT_CONTEXT.md. Strict calendar-date comparisons exclude the boundary date; these counts do not establish sale coverage.', '',
              '## Shop validation', '', 'Expected shop.id=61. Unexpected records are preserved and flagged; anomalies stop further requests.',
              'No returned records means shop validation is untested, rather than evidence of Steam-only collection.', '',
              'Offline safety checks: `python3 -m unittest discover -s tests -v`. Tests use synthetic responses in temporary directories and do not establish live API success.', '',
              '## Failures and blockers', '', table(['AppID', 'Name', 'Reason'],
                [(r['AppID'], r['Name'], r['reason'] or r['history_status']) for r in failures]) if failures else 'No observed API failures/unmatched games.',
              '', run['reason'], '', '## Human sanity view', '']
    selected = []
    for reason in ['edge_high_activity', 'edge_zero_ccu', 'edge_oldest', 'edge_near_cutoff', 'edge_high_price']:
        game = next(g for g in games if reason in g['pilot_selection_reason'].split(';'))
        row = next(r for r in rows if r['AppID'] == game['AppID'])
        selected.append([row[f] or 'unavailable' for f in ['AppID', 'Name', 'itad_game_id',
                        'history_record_count', 'earliest_history_timestamp', 'latest_history_timestamp']])
    lines += [table(['AppID', 'Name', 'ITAD ID', 'Records', 'Earliest UTC', 'Latest UTC'], selected), '',
              '## Validation and limitations', '',
              'Manifest: 100 unique AppIDs matching the pilot. Every accepted cache is checked for AppID, ITAD ID, raw-body agreement, request configuration, shop IDs and record structure.',
              'pilot_games.csv and games_master.csv SHA-256 unchanged:', '',
              *[f'- `{path.relative_to(ROOT)}`: `{value}`' for path, value in hashes.items()], '',
              'Presence of ITAD history does not by itself establish sufficient coverage for an Autumn Sale.', '',
              'Absence of a price-change record during a sale does not imply that the game was not discounted.', '',
              'Phase 5 will implement event-specific coverage and labeling rules. No discount labels or event-specific coverage decisions were created.', '',
              '## Execution', '', 'Set ITAD_API_KEY securely in your process environment; the collector does not read apikey or automatically load .env.',
              'Never put credentials in command-line arguments or paste them into reports.', '',
              '```bash', 'python3 src/03_fetch_itad.py --limit 3',
              'python3 src/03_fetch_itad.py --limit 3  # confirm cache reuse',
              'python3 src/03_fetch_itad.py            # only after smoke PASS',
              'python3 src/03_fetch_itad.py --validate-cache  # offline audit', '```', '']
    safe_write(REPORT, '\n'.join(lines), key)
    return facts


def smoke_receipt_valid(pilot_hash):
    try:
        receipt = json.loads((CACHE / 'smoke_test.json').read_text())
        if receipt['request_configuration'] != CONFIG or receipt['pilot_sha256'] != pilot_hash:
            return False
        if len(receipt['cache_sha256']) != 3:
            return False
        for appid, expected in receipt['cache_sha256'].items():
            obj, status, _ = read_cache(appid)
            if status != 'valid' or obj['collection_metadata']['history_status'] not in SUCCESS:
                return False
            if digest(CACHE / f'{appid}.json') != expected:
                return False
        return receipt['steam_record_count'] > 0
    except (OSError, ValueError, KeyError, TypeError):
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit', type=int, help='Collect first N pilot games (start with 3)')
    parser.add_argument('--force', action='store_true', help='Archive and deliberately refresh caches')
    parser.add_argument('--retry-failed', action='store_true', help='Retry incomplete caches, reusing valid lookup evidence')
    parser.add_argument('--validate-cache', action='store_true', help='Offline audit; zero API calls, no key required')
    args = parser.parse_args(argv)
    if args.limit is not None and not 1 <= args.limit <= 100:
        parser.error('--limit must be between 1 and 100')
    games = load_pilot()
    hashes = {PILOT: digest(PILOT), MASTER: digest(MASTER)}
    key = os.environ.get('ITAD_API_KEY', '').strip()
    run = {'at': utcnow(), 'api_calls': 0, 'cache_reused': 0, 'validation': 'FAIL',
           'smoke_test': 'not run', 'reason': ''}
    blocked = ''
    if not args.validate_cache:
        if not key:
            blocked = 'ITAD_API_KEY is absent. Set it securely in the process environment and rerun --limit 3. Zero authenticated API calls; live collection stopped.'
        elif any(c in key for c in '\r\n'):
            blocked = 'ITAD_API_KEY contains invalid header characters; zero API calls.'
        elif (args.limit or 100) > 3 and not smoke_receipt_valid(hashes[PILOT]):
            blocked = 'Full collection blocked: run --limit 3 successfully first.'
    rows, selected_rows = [], []
    client = Client(key) if not blocked and not args.validate_cache else None
    for i, game in enumerate(games):
        appid = game['AppID']
        obj, status, reason = read_cache(appid)
        selected = i < (args.limit or 100)
        if status == 'valid' and not (args.force and selected and client):
            run['cache_reused'] += 1
        elif client and selected and not client.abort:
            if status == 'absent' or args.force or (args.retry_failed and status == 'incomplete'):
                previous = (obj if status == 'incomplete' and not args.force
                            and obj['collection_metadata']['lookup_status'] == 'matched' else None)
                if args.force:
                    archive(CACHE / f'{appid}.json')
                elif status == 'incomplete':
                    archive(CACHE / f'{appid}.json')
                obj = collect(appid, client, previous)
                save_json(CACHE / f'{appid}.json', obj, key)
                status, reason = 'fetched', ''
        if obj is None and blocked:
            reason = blocked
        row = manifest_row(game, obj, status, reason)
        rows.append(row)
        if selected:
            selected_rows.append(row)
            if client:
                print(f'{appid}: {row["lookup_status"]}; {row["history_status"]}', flush=True)
    run['api_calls'] = client.calls if client else 0
    smoke_ok = (args.limit == 3 and len(selected_rows) == 3 and not blocked
                and not args.validate_cache and all(r['history_status'] in SUCCESS for r in selected_rows)
                and sum(int(r['steam_record_count']) for r in selected_rows) > 0)
    if smoke_ok:
        save_json(CACHE / 'smoke_test.json', {'at': utcnow(), 'request_configuration': CONFIG.copy(),
                  'pilot_sha256': hashes[PILOT], 'steam_record_count': sum(int(r['steam_record_count']) for r in selected_rows),
                  'cache_sha256': {r['AppID']: digest(CACHE / f'{r["AppID"]}.json') for r in selected_rows}}, key)
        run['smoke_test'] = 'PASS'
    elif smoke_receipt_valid(hashes[PILOT]):
        run['smoke_test'] = 'previous smoke PASS; receipt and artifacts verified'
    complete = (not blocked and run['smoke_test'] != 'not run'
                and all(r['history_status'] in SUCCESS | {'lookup_not_found'} for r in rows)
                and all(r['cache_status'] not in {'invalid', 'incomplete', 'absent'} for r in rows))
    run['validation'] = 'PASS' if complete else 'FAIL'
    run['reason'] = blocked or ('All 100 pilot games accounted for; received histories structurally validated. Unmatched AppIDs remain explicit.' if complete else
                               'Collection incomplete; inspect manifest failures/uncollected rows. Phase 5 has not begun.')
    facts = write_outputs(games, rows, run, hashes, key)
    print(table(['Metric', 'Count'], facts))
    print(f'Smoke: {run["smoke_test"]}; API calls: {run["api_calls"]}; reused caches: {run["cache_reused"]}')
    print(f'Phase 4 validation: {run["validation"]}. {run["reason"]}')
    if complete:
        update_status(rows, run)
    return 0 if complete or smoke_ok else 1


def update_status(rows, run):
    path = ROOT / 'PROJECT_STATUS.md'
    text = path.read_text(encoding='utf-8')
    text = re.sub(r'(?<=## Current Phase\n\n).*?(?=\n\n)',
                  'Phase 4 — ITAD Historical Price Collection ✅ (Phases 1–3 complete)', text, count=1, flags=re.S)
    text = text.split('\n## Phase 4')[0].split('\n## Next Phase')[0].rstrip()
    count = lambda f, s: sum(r[f] == s for r in rows)
    successes = sum(r['history_status'] in SUCCESS for r in rows)
    unmatched = count('lookup_status', 'not_found')
    text += ('\n\n## Phase 4 completed\n\n'
             f'- Validation PASS at {run["at"]}; pilot: 100; matched: {count("lookup_status", "matched")}; '
             f'history success: {successes}; empty: {count("history_status", "empty_history")}; '
             f'unmatched: {unmatched}; request failures: 0.\n'
             '- AppID lookup /games/lookup/v1; history /games/history/v2; US; shops=61; since=2021-01-01T00:00:00Z.\n'
             '- Cache: data/raw/itad/; manifest: data/intermediate/itad_collection_manifest.csv; report: reports/itad_collection_report.md.\n'
             '- Smoke receipt and raw cache provenance validated; Phase 2/3 datasets unchanged.\n'
             f'- Unresolved collection issues: {unmatched} unmatched AppIDs (see report). Event-specific historical coverage remains unassessed.\n'
             '- No sale labels or event-specific coverage decisions; Phase 5 has not begun.\n\n'
             '## Next Phase\n\n**Phase 5 — Historical Coverage Assessment and Autumn Sale Labels**\n')
    safe_write(path, text)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyboardInterrupt):
        # Avoid rendering exception objects that could contain headers or raw secrets.
        print('Collector stopped: input, cache, filesystem, credential-reflection error, or interruption. '
              'Preserved caches can be audited with --validate-cache.', file=sys.stderr)
        sys.exit(1)
