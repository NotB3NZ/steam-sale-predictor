"""Phase 5A: offline descriptive evidence audit; no coverage rules or target labels.

Run from any directory: python3 src/04_audit_autumn_evidence.py
Only standard-library local file operations are used. Phase 4 is never executed.
"""
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from itertools import groupby
from pathlib import Path
import re
import statistics

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_WINDOWS = {2023: ('2023-11-21', '2023-11-28'),
                    2024: ('2024-11-27', '2024-12-04')}
CATEGORIES = {
    'A': 'At least one directly observed in-window discount',
    'B': 'In-window records exist and every record shows full price',
    'C': 'In-window records exist; no discount and some ambiguous/null information',
    'D': 'No directly timestamped in-window records',
}
OBS_FIELDS = ['source_record_index', 'timestamp_raw', 'timestamp_utc', 'shop_id',
              'shop_name', 'deal_status', 'price', 'price_amountInt', 'price_currency',
              'regular_price', 'regular_amountInt', 'regular_currency', 'cut',
              'observation_kind', 'information_issue', 'raw_record_json']


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def frozen_hashes(root):
    paths = sorted((root / 'data/raw/itad').rglob('*.json'))
    paths += [root / 'data/intermediate' / name for name in
              ('pilot_games.csv', 'games_master.csv', 'itad_collection_manifest.csv')]
    paths += [root / 'src/03_fetch_itad.py', root / 'reports/itad_collection_report.md']
    return {str(p.relative_to(root)): digest(p) for p in paths}


def utc_stamp(value):
    if not isinstance(value, str) or 'T' not in value:
        raise ValueError('timestamp must be an ISO datetime with timezone')
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('timestamp lacks timezone')
    return dt.astimezone(timezone.utc)


def fmt(dt):
    return dt.isoformat().replace('+00:00', 'Z')


def canonical_windows(root):
    text = (root / 'PROJECT_CONTEXT.md').read_text(encoding='utf-8')
    windows = {}
    for year, expected in EXPECTED_WINDOWS.items():
        matches = re.findall(rf'^Autumn {year}: (\d{{4}}-\d{{2}}-\d{{2}}) to (\d{{4}}-\d{{2}}-\d{{2}})', text, re.M)
        if matches != [expected]:
            raise ValueError(f'Canonical {year} dates missing/changed; review before running')
        start, end = matches[0]
        windows[year] = (start, end, utc_stamp(start + 'T00:00:00Z'),
                         utc_stamp(end + 'T00:00:00Z') + timedelta(days=1))
    return windows


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def require(condition):
    if not condition:
        raise ValueError('provenance mismatch')


def observation(raw, index):
    """Usable temporal evidence needs a timestamp and Steam ID, not a non-null deal.

    Descriptive price kinds require explicit, consistent price/regular/cut fields.
    A null/missing/contradictory deal remains ambiguous, never full price.
    Raw fields are always preserved, including zeros and original timestamps.
    """
    row = dict.fromkeys(OBS_FIELDS, '')
    row.update(source_record_index=index, timestamp_raw=raw['timestamp'],
               timestamp_utc=fmt(utc_stamp(raw['timestamp'])),
               shop_id=raw['shop']['id'], shop_name=raw['shop'].get('name', ''),
               raw_record_json=json.dumps(raw, ensure_ascii=False, separators=(',', ':')))
    deal = raw.get('deal')
    row['deal_status'] = ('missing' if 'deal' not in raw else 'null' if deal is None
                          else 'object' if isinstance(deal, dict) else 'invalid')
    row['observation_kind'] = 'ambiguous'
    if not isinstance(deal, dict):
        row['information_issue'] = f"deal_{row['deal_status']}"
        return row
    row['cut'] = deal.get('cut', '')
    for field, prefix in [('price', 'price'), ('regular', 'regular')]:
        money = deal.get(field)
        if isinstance(money, dict):
            row['price' if field == 'price' else 'regular_price'] = money.get('amount', '')
            row[prefix + '_amountInt'] = money.get('amountInt', '')
            row[prefix + '_currency'] = money.get('currency', '')
    p, r, cut = row['price'], row['regular_price'], row['cut']
    if not all(number(x) for x in (p, r, cut)) or min(p, r) < 0 or not 0 <= cut <= 100:
        row['information_issue'] = 'missing_or_invalid_price_regular_cut'
    elif (not re.fullmatch(r'[A-Z]{3}', str(row['price_currency']))
          or row['price_currency'] != row['regular_currency']):
        row['information_issue'] = 'missing_or_mismatched_currency'
    elif cut > 0 and p < r:
        row['observation_kind'] = 'discount'
    elif cut == 0 and p == r:
        row['observation_kind'] = 'full_price'
    else:
        row['information_issue'] = 'price_regular_cut_disagree'
    return row


def parse_history(history):
    records, issues, non_steam = [], [], 0
    for i, raw in enumerate(history):
        if not isinstance(raw, dict):
            issues.append({'record_index': i, 'issue': 'record_not_object'})
            continue
        shop = raw.get('shop')
        if not isinstance(shop, dict) or type(shop.get('id')) is not int:
            issues.append({'record_index': i, 'issue': 'invalid_shop_id'})
            continue
        if shop['id'] != 61:
            non_steam += 1
            continue
        try:
            records.append(observation(raw, i))
        except (ValueError, TypeError, KeyError, OverflowError):
            issues.append({'record_index': i, 'issue': 'invalid_timestamp'})
    # Do not collapse duplicates. Index is only a deterministic tie-break, not a time order.
    records.sort(key=lambda r: (utc_stamp(r['timestamp_utc']), r['source_record_index']))
    return records, issues, non_steam


def read_csv(path):
    with path.open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def load_cache(root, game, manifest):
    path = root / 'data/raw/itad' / f"{game['AppID']}.json"
    if not path.exists():
        return [], {'cache_status': 'missing', 'issue': 'cache_file_missing'}
    try:
        obj = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError):
        return [], {'cache_status': 'unreadable', 'issue': 'cache_file_unreadable'}
    except ValueError:
        return [], {'cache_status': 'invalid', 'issue': 'invalid_json'}
    try:
        cfg = obj['request_configuration']
        hist = obj['history_response']
        require(obj['steam_appid'] == int(game['AppID']))
        require(obj['itad_game_id'] == manifest['itad_game_id'] == obj['lookup_response']['game']['id'])
        require(obj['lookup_response']['found'] is True)
        require(cfg['country'] == manifest['country'] == 'US')
        require(cfg['steam_shop_id'] == int(manifest['steam_shop_id']) == 61)
        require(cfg['requested_since'] == manifest['requested_since'] == '2021-01-01T00:00:00Z')
        require(cfg['history_endpoint'] == '/games/history/v2')
        require(cfg['lookup_endpoint'] == '/games/lookup/v1')
        require(obj['history_evidence']['http_status'] == 200)
        require(obj['history_evidence']['params'] == {
            'id': obj['itad_game_id'], 'country': 'US', 'shops': '61',
            'since': cfg['requested_since']})
        require(json.loads(obj['history_evidence']['body']) == hist)
        require(isinstance(hist, list))
        require(len(hist) == int(manifest['history_record_count']))
        expected_status = 'history_received' if hist else 'empty_history'
        require(obj['collection_metadata']['history_status'] == manifest['history_status'] == expected_status)
    except (ValueError, KeyError, TypeError):
        return [], {'cache_status': 'invalid', 'issue': 'wrapper_or_manifest_provenance_mismatch'}
    records, issues, other = parse_history(hist)
    return records, {'cache_status': 'partial' if issues else 'ok', 'issue': '',
                     'raw_history_record_count': len(hist), 'record_parsing_failures': issues,
                     'non_steam_records_excluded': other}


def partition(records, start, end_exclusive):
    before, inside, after = [], [], []
    for r in records:
        dt = utc_stamp(r['timestamp_utc'])
        (before if dt < start else inside if dt < end_exclusive else after).append(r)
    return before, inside, after


def category(inside):
    if not inside:
        return 'D'
    kinds = Counter(r['observation_kind'] for r in inside)
    if kinds['discount']:
        return 'A'
    if kinds['full_price'] == len(inside):
        return 'B'
    return 'C'


def context_fields(side, records, boundary):
    row = {f'{side}_{f}': '' for f in OBS_FIELDS}
    row.update({f'{side}_gap_days': '', f'{side}_nearest_timestamp_tie_count': 0,
                f'{side}_tied_records_json': ''})
    if not records:
        return row
    nearest = records[-1] if side == 'before' else records[0]
    ties = [r for r in records if r['timestamp_utc'] == nearest['timestamp_utc']]
    # Representative is lowest original index; all ties retained, no state preference.
    nearest = min(ties, key=lambda r: r['source_record_index'])
    row.update({f'{side}_{k}': nearest[k] for k in OBS_FIELDS})
    gap = abs((boundary - utc_stamp(nearest['timestamp_utc'])).total_seconds()) / 86400
    row.update({f'{side}_gap_days': gap, f'{side}_nearest_timestamp_tie_count': len(ties),
                f'{side}_tied_records_json': json.dumps([json.loads(r['raw_record_json']) for r in ties],
                                                       ensure_ascii=False, separators=(',', ':'))})
    return row


def audit_pair(game, year, window, records, cache_info):
    start_date, end_date, start, end = window
    before, inside, after = partition(records, start, end)
    kinds = Counter(r['observation_kind'] for r in inside)
    currencies = sorted({r['price_currency'] for r in inside if number(r['price'])})
    regular_currencies = {r['regular_currency'] for r in inside if number(r['regular_price'])}
    money_comparable = len(set(currencies) | regular_currencies) == 1 and '' not in currencies
    amounts = [r['price'] for r in inside if number(r['price']) and r['price'] >= 0]
    regulars = [r['regular_price'] for r in inside if number(r['regular_price']) and r['regular_price'] >= 0]
    cuts = [r['cut'] for r in inside if number(r['cut']) and 0 <= r['cut'] <= 100]
    row = dict(AppID=game['AppID'], Name=game['Name'], sale_year=year,
               sale_start=start_date, sale_end=end_date, window_timezone='UTC',
               window_start_utc=fmt(start), window_end_exclusive_utc=fmt(end),
               cache_path=f"data/raw/itad/{game['AppID']}.json",
               cache_status=cache_info['cache_status'], cache_issue=cache_info['issue'],
               record_parsing_failure_count=len(cache_info.get('record_parsing_failures', [])),
               non_steam_records_excluded=cache_info.get('non_steam_records_excluded', 0),
               total_timestamp_usable_steam_records=len(records),
               in_window_record_count=len(inside), has_in_window_records=bool(inside),
               in_window_price_usable_count=kinds['discount'] + kinds['full_price'],
               in_window_discount_count=kinds['discount'], in_window_full_price_count=kinds['full_price'],
               in_window_ambiguous_count=kinds['ambiguous'],
               in_window_null_deal_count=sum(r['deal_status'] == 'null' for r in inside),
               in_window_start_date_count=sum(r['timestamp_utc'][:10] == start_date for r in inside),
               in_window_end_date_count=sum(r['timestamp_utc'][:10] == end_date for r in inside),
               earliest_in_window_timestamp=inside[0]['timestamp_utc'] if inside else '',
               latest_in_window_timestamp=inside[-1]['timestamp_utc'] if inside else '',
               in_window_currencies=';'.join(currencies),
               min_observed_in_window_price=min(amounts) if amounts and money_comparable else '',
               max_observed_in_window_regular_price=max(regulars) if regulars and money_comparable else '',
               max_observed_in_window_cut=max(cuts) if cuts else '',
               in_window_mixed_discount_full_price=bool(kinds['discount'] and kinds['full_price']),
               evidence_category=category(inside))
    if cache_info['cache_status'] != 'ok':
        # Missing/failed input is not a successfully audited zero-observation case.
        row['evidence_category'] = ''
        if cache_info['cache_status'] != 'partial':
            for key in list(row):
                if key.startswith('in_window_') or key in ('has_in_window_records', 'total_timestamp_usable_steam_records'):
                    row[key] = ''
    row.update(context_fields('before', before, start))
    row.update(context_fields('after', after, end))
    long = [dict(AppID=game['AppID'], Name=game['Name'], sale_year=year, **r) for r in inside]
    return row, long


def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def md_table(headers, rows):
    def line(values):
        return '| ' + ' | '.join(str(v).replace('|', '\\|').replace('\n', ' ') for v in values) + ' |'
    return '\n'.join([line(headers), line(['---'] * len(headers)), *[line(r) for r in rows]])


def stat_values(values):
    if not values:
        return [0, *['unavailable'] * 6]
    quartiles = statistics.quantiles(values, n=4, method='inclusive') if len(values) > 1 else values * 3
    return [len(values), *[round(x, 6) for x in
                         (min(values), quartiles[0], statistics.median(values),
                          statistics.mean(values), quartiles[2], max(values))]]


def state_signature(r):
    return tuple(r[k] for k in ('price', 'price_amountInt', 'price_currency',
                               'regular_price', 'regular_amountInt', 'regular_currency', 'cut', 'deal_status'))


def empirical_semantics(histories):
    counts = Counter()
    transitions = Counter()
    gaps, repeated_examples, conflicting_examples, full_change_examples = [], [], [], []
    for appid, records in histories.items():
        groups = [list(g) for _, g in groupby(records, key=lambda r: r['timestamp_utc'])]
        counts['nonempty_games'] += bool(records)
        counts['records'] += len(records)
        counts['null_deals'] += sum(r['deal_status'] == 'null' for r in records)
        counts['ambiguous'] += sum(r['observation_kind'] == 'ambiguous' for r in records)
        counts['full_price'] += sum(r['observation_kind'] == 'full_price' for r in records)
        counts['discount'] += sum(r['observation_kind'] == 'discount' for r in records)
        counts['zero_price_regular'] += sum(r['price'] == r['regular_price'] == 0 for r in records)
        counts['requested_since_timestamp'] += sum(r['timestamp_utc'] == '2021-01-01T00:00:00Z' for r in records)
        original_order = sorted(records, key=lambda r: r['source_record_index'])
        counts['reverse_chronological_games'] += bool(records) and all(
            utc_stamp(a['timestamp_utc']) >= utc_stamp(b['timestamp_utc'])
            for a, b in zip(original_order, original_order[1:]))
        for group in groups:
            if len(group) > 1:
                counts['duplicate_timestamp_groups'] += 1
                if len({state_signature(r) for r in group}) > 1:
                    counts['conflicting_timestamp_groups'] += 1
                    conflicting_examples.append((appid, group))
        for ga, gb in zip(groups, groups[1:]):
            gaps.append((utc_stamp(gb[0]['timestamp_utc']) - utc_stamp(ga[0]['timestamp_utc'])).total_seconds() / 86400)
            shared = {state_signature(r) for r in ga} & {state_signature(r) for r in gb}
            if shared:
                counts['consecutive_groups_sharing_state'] += 1
                shared_rows = [r for r in ga + gb if state_signature(r) in shared]
                repeated_examples.append((appid, shared_rows))
            if len(ga) != 1 or len(gb) != 1:
                counts['adjacent_groups_excluded_from_directional_counts'] += 1
                continue
            a, b = ga[0], gb[0]
            counts['singleton_adjacent_pairs'] += 1
            transitions[(a['observation_kind'], b['observation_kind'])] += 1
            if a['price'] == b['price'] and a['price_currency'] == b['price_currency']:
                counts['same_price_adjacent_pairs'] += 1
            if a['cut'] == b['cut'] == 0:
                counts['consecutive_cut_zero'] += 1
                if state_signature(a) == state_signature(b):
                    counts['identical_full_price_pairs'] += 1
                else:
                    full_change_examples.append((appid, [a, b]))
    return counts, transitions, gaps, repeated_examples, conflicting_examples, full_change_examples


def evidence_table(records, side='in-window'):
    return md_table(['Relation', 'Raw index', 'UTC timestamp', 'Price', 'Regular', 'Cut', 'Currency', 'Kind'],
                    [(side, r['source_record_index'], r['timestamp_utc'], r['price'], r['regular_price'],
                      r['cut'], r['price_currency'], r['observation_kind']) for r in records])


def build_report(games, rows, long, histories, infos, windows, receipt):
    valid = [r for r in rows if r['cache_status'] == 'ok']
    lines = ['# Autumn Sale In-Window Evidence Audit — Phase 5A', '',
             '**Exploratory audit completed; pending human review. No final labels or coverage rules.**', '',
             '## Scope and overall results', '',
             f'Pilot games: **{len(games)}**. Expected pairs: **{len(games) * 2}**. '
             f'Actual rows considered: **{len(rows)}**. Successfully analyzed pairs: **{len(valid)}**. '
             f'Actual in-window records: **{len(long)}**.', '',
             md_table(['Cache/parse diagnostic', 'Games/records'], [
                 ('Missing cache files (games)', sum(i['cache_status'] == 'missing' for i in infos.values())),
                 ('Unreadable cache files (games)', sum(i['cache_status'] == 'unreadable' for i in infos.values())),
                 ('Invalid JSON/wrapper/provenance (games)', sum(i['cache_status'] == 'invalid' for i in infos.values())),
                 ('Games with record parsing failures', sum(i['cache_status'] == 'partial' for i in infos.values())),
                 ('Record parsing failures', sum(len(i.get('record_parsing_failures', [])) for i in infos.values())),
                 ('Non-Steam records excluded', sum(i.get('non_steam_records_excluded', 0) for i in infos.values())),
                 ('Empty successful histories', sum(not histories[a] and i['cache_status'] == 'ok' for a, i in infos.items()))]), '',
             'All pilot games satisfy the existing release-date cutoff for both years. No games were silently dropped. '
             'The 100-game pilot is a diagnostic diversity sample; these results do not estimate population participation.', '',
             '## Canonical dates and boundary convention', '',
             'Dates are read from `PROJECT_CONTEXT.md`, not from external sources. '
             'The repository supplies calendar dates, without exact sale hours or a sale timezone. '
             'This audit uses both endpoint dates inclusively in UTC: start midnight <= timestamp < midnight after the end date. '
             'This is a documented calendar-date convention, not verification of exact live sale hours. '
             'Original offsets are preserved; comparisons use timezone-aware UTC instants.', '',
             md_table(['Year', 'Canonical start', 'Canonical end (inclusive)', 'UTC start', 'UTC end (exclusive)'],
                      [(y, s, e, fmt(a), fmt(b)) for y, (s, e, a, b) in windows.items()]), '',
             'Before means strictly earlier than start midnight. After means at or later than end-exclusive midnight. '
             'Gap days are elapsed seconds / 86,400 relative to those boundaries, not rounded calendar-day distances. '
             'An observation at end-exclusive midnight has an after-gap of zero. '
             'Full-price records on the documented sale end date may be post-sale-hour observations. '
             'No hour boundary is silently substituted and no boundary sensitivity establishes coverage.', '',
             '## Actual cached schema and extraction semantics', '',
             'Phase 4 wrapper fields are `steam_appid`, `itad_game_id`, `request_configuration`, '
             '`lookup_response`, `history_response`, `collection_metadata`, `lookup_evidence`, and `history_evidence`. '
             '`history_response` is an array, and `history_evidence.body` contains its original JSON response text; '
             'agreement is verified before analysis. The manifest mapping, record count, collection status and request configuration are checked.', '',
             'Every observed record has exactly `timestamp`, `shop`, and `deal`. '
             '`shop` is `{id: 61, name: "Steam"}`. Every observed deal has exactly `price`, `regular`, and `cut`; '
             'each price object contains `amount`, `amountInt`, and `currency`. All currencies are USD. '
             'There is no separate deal-active/status flag. Full price is represented by a non-null deal with cut zero and equal price/regular amounts. '
             'The existing Phase 4 contract permits null deals but assigns them no sale meaning. '
             'There are no null/missing deal records in this pilot, so their empirical semantics cannot be investigated here.', '',
             'A timestamp-usable observation has an explicitly parsed timezone and integer Steam shop ID 61. '
             'Such observations count as records even when deal information is null or ambiguous. '
             'Price-usable observations require finite nonnegative price/regular amounts, matching currency, and explicit cut in [0,100]. '
             'A descriptive discount requires cut > 0 and price < regular; full price requires cut = 0 and price = regular. '
             'Any missing or contradictory information is ambiguous. This validates what a record says; '
             'it does not select a sufficient number of observations or infer state between timestamps. '
             'Zero-price/equal-zero-regular records are retained as reported cut-zero observations, with no claim about permanent free-to-play status.', '',
             '## Descriptive evidence categories', '',
             md_table(['Category', 'Description'], CATEGORIES.items()), '',
             'Category A takes precedence if any directly discounted observation exists, even alongside full-price or ambiguous records. '
             'B requires all timestamp-usable in-window records to show full price; full-price plus ambiguous records without a discount are C. '
             'These letters are evidence descriptions, not 1/0/UNKNOWN labels. Unreadable/invalid/partial inputs have a blank category, '
             'rather than being presented as an audited D.', '',
             md_table(['Year', 'Games analyzed', 'Any records', 'Zero records', 'A', 'B', 'C', 'D',
                       'Pairs with any ambiguous record', 'Pairs with null deal', 'Mixed discount/full'],
                      [(y, len(rr), sum(r['has_in_window_records'] for r in rr),
                        sum(not r['has_in_window_records'] for r in rr),
                        *[sum(r['evidence_category'] == c for r in rr) for c in CATEGORIES],
                        sum(r['in_window_ambiguous_count'] > 0 for r in rr),
                        sum(r['in_window_null_deal_count'] > 0 for r in rr),
                        sum(r['in_window_mixed_discount_full_price'] for r in rr))
                       for y in windows for rr in [[r for r in valid if r['sale_year'] == y]]]), '',
             md_table(['Year', 'In-window records', 'Discount records', 'Full-price records', 'Ambiguous', 'Null deals'],
                      [(y, sum(r['in_window_record_count'] for r in rr),
                        sum(r['in_window_discount_count'] for r in rr),
                        sum(r['in_window_full_price_count'] for r in rr),
                        sum(r['in_window_ambiguous_count'] for r in rr),
                        sum(r['in_window_null_deal_count'] for r in rr))
                       for y in windows for rr in [[r for r in valid if r['sale_year'] == y]]]), '',
             '## In-window record density', '',
             'Statistics include zero-observation games. Quartiles use inclusive interpolation. No density cutoff is adopted.', '',
             md_table(['Year', 'N', 'Min', 'Q1', 'Median', 'Mean', 'Q3', 'Max'],
                      [(y, *stat_values([r['in_window_record_count'] for r in valid if r['sale_year'] == y])) for y in windows]), '',
             md_table(['Observation count', *windows],
                      [(n, *[sum(r['sale_year'] == y and r['in_window_record_count'] == n for r in valid) for y in windows])
                       for n in sorted({r['in_window_record_count'] for r in valid})]), '',
             '### Endpoint-date observations', '',
             md_table(['Year', 'Records on start date', 'Records on end date', 'B cases only on end date'],
                      [(y, sum(r['in_window_start_date_count'] for r in rr),
                        sum(r['in_window_end_date_count'] for r in rr),
                        sum(r['evidence_category'] == 'B' and r['in_window_record_count'] == r['in_window_end_date_count'] for r in rr))
                       for y in windows for rr in [[r for r in valid if r['sale_year'] == y]]]), '',
             '## Before/after gaps — contextual diagnostics only', '',
             'Nearest usable here means nearest timestamp-usable Steam observation; it does not require an interpretable deal. '
             'The deal status/kind and raw JSON remain explicit, so null contextual evidence would never imply full price. '
             'All ties at the nearest timestamp are retained in contextual JSON; the scalar representative uses the lowest raw array index, '
             'without choosing a preferred price. No preceding observation is carried into the window. '
             'Missing surrounding observations stay blank and are excluded from gap statistics, never treated as zero.', '']
    gaps_rows = []
    for y in windows:
        for group in ('all analyzed pairs', 'zero in-window pairs'):
            rr = [r for r in valid if r['sale_year'] == y and (group == 'all analyzed pairs' or not r['has_in_window_records'])]
            for side in ('before', 'after'):
                vals = [r[f'{side}_gap_days'] for r in rr if number(r[f'{side}_gap_days'])]
                gaps_rows.append((y, group, side, len(rr) - len(vals), *stat_values(vals)))
    lines += [md_table(['Year', 'Subset', 'Side', 'Missing', 'N', 'Min days', 'Q1', 'Median', 'Mean', 'Q3', 'Max days'], gaps_rows), '',
              '## All full-price-only cases (category B)', '',
              'Each has exactly one directly timestamped full-price observation. This list describes observed records only; '
              'none is a negative label. Endpoint dates have no verified hour boundary in the repository.', '',
              md_table(['Year', 'AppID', 'Name', 'UTC timestamp', 'Price', 'Regular', 'Cut'],
                       [(r['sale_year'], r['AppID'], r['Name'], obs['timestamp_utc'], obs['price'], obs['regular_price'], obs['cut'])
                        for r in valid if r['evidence_category'] == 'B'
                        for obs in long if obs['AppID'] == r['AppID'] and obs['sale_year'] == r['sale_year']]), '',
              '## Representative game-sale cases', '',
              'Examples use only actual pilot records. “Closest”/“most distant” below rank the sum of available before and after gaps '
              'among zero-record pairs having both sides; these are relative descriptions, not coverage thresholds.', '']
    examples = []
    def choose(title, predicate):
        candidates = [r for r in valid if predicate(r)]
        if candidates:
            examples.append((title, candidates[0]))
        else:
            lines.extend([f'**{title}:** no example exists in this pilot.', ''])
    choose('Clear in-window discount', lambda r: r['in_window_discount_count'] and not r['in_window_full_price_count'])
    choose('One full-price observation', lambda r: r['evidence_category'] == 'B' and r['in_window_record_count'] == 1)
    choose('Multiple full-price observations with no discounted evidence', lambda r: r['evidence_category'] == 'B' and r['in_window_record_count'] > 1)
    choose('Mixed discounted and full-price observations', lambda r: r['in_window_mixed_discount_full_price'])
    for y in windows:
        candidates = [r for r in valid if r['sale_year'] == y and not r['has_in_window_records']
                      and number(r['before_gap_days']) and number(r['after_gap_days'])]
        if candidates:
            key = lambda r: (r['before_gap_days'] + r['after_gap_days'], int(r['AppID']))
            examples.extend([(f'{y}: zero records, closest two-sided context', min(candidates, key=key)),
                             (f'{y}: zero records, most distant two-sided context', max(candidates, key=key))])
    choose('No in-window records and absent subsequent history', lambda r: r['evidence_category'] == 'D' and r['before_timestamp_utc'] and not r['after_timestamp_utc'])
    choose('Completely empty cached history', lambda r: r['total_timestamp_usable_steam_records'] == 0)
    choose('Three in-window observations', lambda r: r['in_window_record_count'] >= 3)
    choose('Pilot game released on 2023 sale start date', lambda r: r['AppID'] == '2650840' and r['sale_year'] == 2023)
    choose('Full-price-only evidence on 2024 end date', lambda r: r['AppID'] == '7830' and r['sale_year'] == 2024)
    choose('Null or ambiguous in-window deal', lambda r: r['in_window_ambiguous_count'])
    for title, row in examples:
        app, year = row['AppID'], row['sale_year']
        before, inside, after = partition(histories[app], windows[year][2], windows[year][3])
        lines += [f'### {title}: {row["Name"]} — AppID {app}, {year}', '',
                  f'Category {row["evidence_category"]}; {len(inside)} directly timestamped records. '
                  f'Before gap: {round(row["before_gap_days"], 6) if number(row["before_gap_days"]) else "unavailable"} days; '
                  f'after gap: {round(row["after_gap_days"], 6) if number(row["after_gap_days"]) else "unavailable"} days.', '']
        if inside:
            lines += [evidence_table(inside), '']
        else:
            lines += ['No in-window observations. Surrounding prices do not establish in-window behavior.', '']
        if before:
            lines += [evidence_table([r for r in before if r['timestamp_utc'] == before[-1]['timestamp_utc']], 'before context'), '']
        if after:
            lines += [evidence_table([r for r in after if r['timestamp_utc'] == after[0]['timestamp_utc']], 'after context'), '']
    counts, transitions, all_gaps, repeats, conflicts, full_changes = empirical_semantics(histories)
    lines += ['## Empirical ITAD history semantics', '', '### Observed facts', '',
              'These diagnostics use all cached Steam history, not just the two sale windows. '
              'Records are sorted by UTC timestamp. Equal-time records are preserved; transitions are counted only between adjacent '
              'timestamp groups containing exactly one record each, so conflicting equal-time states have no invented order.', '',
              md_table(['Diagnostic', 'Count'], [
                  ('All Steam records', counts['records']), ('Discount records', counts['discount']),
                  ('Full-price records', counts['full_price']), ('Ambiguous records', counts['ambiguous']),
                  ('Null deals', counts['null_deals']), ('Equal-zero price/regular records', counts['zero_price_regular']),
                  ('Records exactly at requested since boundary', counts['requested_since_timestamp']),
                  ('Nonempty histories', counts['nonempty_games']),
                  ('Nonempty histories in reverse chronological array order', counts['reverse_chronological_games']),
                  ('Timestamp groups containing multiple records', counts['duplicate_timestamp_groups']),
                  ('Those groups with different price states', counts['conflicting_timestamp_groups']),
                  ('Adjacent timestamp groups sharing an identical price/regular/cut state', counts['consecutive_groups_sharing_state']),
                  ('Adjacent singleton-timestamp pairs', counts['singleton_adjacent_pairs']),
                  ('Adjacent groups excluded from directional counts because of timestamp ties', counts['adjacent_groups_excluded_from_directional_counts']),
                  ('Singleton pairs with identical price/currency (regular/cut may differ)', counts['same_price_adjacent_pairs']),
                  ('Singleton pairs with consecutive cut=0', counts['consecutive_cut_zero']),
                  ('Singleton pairs with identical full-price state', counts['identical_full_price_pairs'])]), '',
              md_table(['Earlier kind', 'Later kind', 'Adjacent singleton pairs'], [(a, b, n) for (a, b), n in sorted(transitions.items())]), '',
              'Elapsed gaps between distinct adjacent timestamp groups (zero-time ties are reported separately):', '',
              md_table(['N', 'Min days', 'Q1', 'Median', 'Mean', 'Q3', 'Max days'], [stat_values(all_gaps)]), '',
              'Repeated cut-zero records occur, but unchanged normal-price states are not common in these adjacent observations. '
              'Repeated price states do occur, so a strict “every record is a price change” claim would be too strong. '
              'No empirical null/deal transitions can be examined because the caches have no null deals.', '']
    name_by_id = {g['AppID']: g['Name'] for g in games}
    for title, examples_to_show in [('Repeated identical price-state timestamps', repeats),
                                    ('Consecutive full-price records with changed amounts', full_changes[:1]),
                                    ('Conflicting records at the same timestamp', conflicts)]:
        lines += [f'### {title}', '']
        for appid, records in examples_to_show:
            lines += [f'**{name_by_id[appid]} — AppID {appid}**', '', evidence_table(records, 'all-history diagnostic'), '']
    lines += ['### Interpretation / hypotheses', '',
              'The frequent discount-to-full-price and full-price-to-discount transitions, sparse irregular gaps, and lack of repeated '
              'unchanged normal-price records are consistent with a change-oriented history rather than a regular observation log. '
              'Some identical-state repeats and same-timestamp conflicting states show that a simple one-record-per-price-change model is incomplete. '
              'Records at the exact requested-since instant could be boundary snapshots or truncated earlier states; '
              'their original observation times cannot be inferred. These are hypotheses, not established API semantics.', '',
              'The cached data alone cannot confidently distinguish event notifications, periodic polling with change retention, '
              'synthetic boundary records, corrections, or a combination. Same-timestamp conflicts could reflect correction or product/price variants, '
              'but the returned record fields do not identify the cause. '
              'The absence of a timestamp inside a window proves only that this cache has no such timestamp. '
              'It does not prove stable price, nonparticipation, complete observation, or lack of a sale.', '',
              '## Audit artifacts and column definitions', '',
              '- `data/intermediate/autumn_sale_evidence_audit.csv`: one row per AppID/year with explicit cache status, '
              'UTC boundaries, record/deal diagnostics, amounts, category and separate nearest before/after context.',
              '- `data/intermediate/autumn_sale_evidence_records.csv`: one row per actual timestamp-usable in-window Steam record; '
              'raw index, original timestamp/offset, normalized UTC timestamp, shop, deal status, amounts/amountInt/currencies/cut, '
              'observation kind, issue and complete serialized raw record.',
              '- `reports/autumn_sale_evidence_validation.json`: individual frozen-input SHA-256 before/after values, '
              'validation checks and per-game parsing/provenance diagnostics.', '',
              '`in_window_record_count` includes null/ambiguous timestamp-usable records; `in_window_price_usable_count` excludes them. '
              '`in_window_ambiguous_count` includes null/missing/contradictory deals; null count is a subset. '
              'Extrema use explicitly available finite amounts/cut, never filled values; amount extrema are blank if currencies cannot be pooled. '
              'Zero is preserved. Empty evidence has blank timestamps/extrema. Context columns never contribute to the category. '
              'Raw indices are zero-based offsets into `history_response`. Duplicate timestamp records are never deduplicated. '
              'Before/after ties include all raw records in `*_tied_records_json`.', '',
              '## Validation and preservation', '',
              md_table(['Validation', 'Result'], receipt['checks'].items()), '',
              f'Frozen input files checked: **{len(receipt["frozen_input_sha256"])}** '
              '(all raw ITAD JSON including smoke receipt/archive, three frozen intermediate CSVs, Phase 4 script/report). '
              'Every file has identical SHA-256 before/after; the file inventory is unchanged. '
              'Individual digests are in the validation receipt. No API, web, or network requests were made. '
              'The standalone audit has no network client and does not execute/import the Phase 4 collector.', '',
              'Reproduce: `python3 src/04_audit_autumn_evidence.py`. '
              'Tests: `python3 -m unittest discover -s tests -v` (offline synthetic fixtures; includes Phase 4 regression tests). '
              'The report/datasets are deterministic for identical frozen inputs and canonical dates; '
              'the audit does not modify project status/context itself.', '',
              '## Remaining ambiguities and stop gate', '',
              'Exact sale-hour boundaries are unspecified in the repository. End-date full-price observations and mixed records '
              'must be reviewed with that limitation in mind. All B cases have only one full-price observation; '
              'whether any such case provides sufficient negative coverage remains undecided. '
              'There are no multiple-full-price-only, null, or ambiguous in-window examples in this pilot. '
              'Several histories are empty, stop long before the window, or have very distant surrounding observations. '
              'Same-timestamp conflicting records and possible requested-since boundary artifacts need later semantic review.', '',
              '**Stopped after Phase 5A. Phase 4 remains COMPLETE. Phase 5A is completed/pending review. '
              'Phase 5B coverage and final labeling methodology are NOT YET IMPLEMENTED.** '
              'No labels, UNKNOWN mapping, observation sufficiency threshold, state persistence, feature engineering, or modeling changes were created.', '']
    return '\n'.join(lines)


def run(root=ROOT):
    before_hashes = frozen_hashes(root)
    games = read_csv(root / 'data/intermediate/pilot_games.csv')
    manifest = read_csv(root / 'data/intermediate/itad_collection_manifest.csv')
    ids = [g['AppID'] for g in games]
    if len(ids) != 100 or len(set(ids)) != 100 or any(not re.fullmatch(r'[1-9][0-9]*', a) for a in ids):
        raise ValueError('Expected all 100 unique valid pilot AppIDs')
    if len(manifest) != 100 or {r['AppID'] for r in manifest} != set(ids):
        raise ValueError('Manifest must match all pilot AppIDs uniquely')
    windows = canonical_windows(root)
    if any(g['release_date'] > windows[2023][0] for g in games):
        raise ValueError('Pilot release eligibility differs from documented Phase 3 cutoff')
    manifest_by_id = {r['AppID']: r for r in manifest}
    rows, long, histories, infos = [], [], {}, {}
    for game in games:
        appid = game['AppID']
        records, info = load_cache(root, game, manifest_by_id[appid])
        histories[appid], infos[appid] = records, info
        for year, window in windows.items():
            row, observations = audit_pair(game, year, window, records, info)
            rows.append(row)
            long.extend(observations)
    if len(rows) != 200 or len({(r['AppID'], r['sale_year']) for r in rows}) != 200:
        raise ValueError('Expected 200 unique game-sale pairs')
    if any(r['shop_id'] != 61 for r in long):
        raise ValueError('Non-Steam record included')
    if any(not windows[r['sale_year']][2] <= utc_stamp(r['timestamp_utc']) < windows[r['sale_year']][3] for r in long):
        raise ValueError('In-window boundary validation failed')
    for r in rows:
        if r['cache_status'] == 'ok' and r['in_window_record_count'] != sum(
                r[k] for k in ('in_window_discount_count', 'in_window_full_price_count', 'in_window_ambiguous_count')):
            raise ValueError('In-window record counts fail reconciliation')
    after_hashes = frozen_hashes(root)
    if before_hashes != after_hashes:
        raise ValueError('Frozen inputs changed during audit')
    receipt = {
        'phase': '5A', 'api_calls': 0, 'network_requests': 0,
        'pilot_games': len(games), 'expected_pairs': 200, 'actual_pairs': len(rows),
        'in_window_records': len(long),
        'checks': {'All 100 pilot AppIDs, both eligible years': 'PASS',
                   '200 unique AppID × sale_year rows': 'PASS',
                   'Timezone-aware UTC parsing and inclusive calendar-date boundaries': 'PASS',
                   'Long-file counts reconcile to audit rows': 'PASS',
                   'Discount/full/ambiguous counts reconcile': 'PASS',
                   'Only integer Steam shop ID 61 included': 'PASS',
                   'Frozen input hashes and inventory unchanged': 'PASS',
                   'Cache provenance and record parsing': 'PASS' if all(i['cache_status'] == 'ok' for i in infos.values()) else 'ISSUES — inspect per_game',
                   'Network/API requests': '0', 'Final labeling/coverage decisions': 'NOT IMPLEMENTED'},
        'per_game': infos,
        'frozen_input_sha256': {p: {'before': h, 'after': after_hashes[p]} for p, h in before_hashes.items()}}
    # Explicit long/summary reconciliation; keep a header even with no actual records.
    count_by_pair = Counter((r['AppID'], r['sale_year']) for r in long)
    if any(r['cache_status'] == 'ok' and r['in_window_record_count'] != count_by_pair[(r['AppID'], r['sale_year'])] for r in rows):
        raise ValueError('Long-file counts disagree with summary')
    intermediate = root / 'data/intermediate'
    reports = root / 'reports'
    reports.mkdir(parents=True, exist_ok=True)
    write_csv(intermediate / 'autumn_sale_evidence_audit.csv', rows, list(rows[0]))
    write_csv(intermediate / 'autumn_sale_evidence_records.csv', long, ['AppID', 'Name', 'sale_year', *OBS_FIELDS])
    (reports / 'autumn_sale_evidence_validation.json').write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    (reports / 'autumn_sale_evidence_audit.md').write_text(build_report(games, rows, long, histories, infos, windows, receipt), encoding='utf-8')
    if frozen_hashes(root) != before_hashes:
        raise ValueError('Frozen inputs changed while writing outputs')
    for year in windows:
        rr = [r for r in rows if r['sale_year'] == year]
        density = Counter(r['in_window_record_count'] for r in rr if r['cache_status'] == 'ok')
        print(f'{year}: categories={dict(Counter(r["evidence_category"] for r in rr))}; '
              f'record density={dict(sorted(density.items()))}; input issues={sum(r["cache_status"] != "ok" for r in rr)}')
    print(f'Phase 5A: {len(rows)} pairs; {len(long)} actual in-window records; frozen hashes unchanged; zero network calls.')
    return rows, long, receipt


if __name__ == '__main__':
    run()
