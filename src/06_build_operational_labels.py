"""Phase 5B.3: offline labels for recorded discounts, not true sale participation.

python3 -B src/06_build_operational_labels.py --verify
No predictors, historical price interpolation, API calls or prior-output writes.
"""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import date
import importlib.util
import io
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('operational_coverage', ROOT / 'src/05_investigate_sale_coverage.py')
coverage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(coverage)
audit = coverage.audit
require = coverage.require
RULE = 'operational_observed_v1'
LABELS = 'data/intermediate/autumn_sale_operational_labels.csv'
PU = 'data/intermediate/autumn_sale_pu_labels.csv'
REPORT = 'reports/autumn_sale_operational_labeling.md'
RECEIPT = 'reports/autumn_sale_operational_label_validation.json'
PRIOR_RECEIPT = 'reports/autumn_sale_ground_truth_validation.json'
OUTPUTS = (LABELS, PU, REPORT, RECEIPT)
INPUTS = {
    'pairs': ('data/intermediate/autumn_sale_evidence_audit.csv',
              ['AppID', 'Name', 'sale_year', 'window_start_utc', 'window_end_exclusive_utc', 'evidence_category',
               'in_window_record_count', 'in_window_discount_count', 'in_window_full_price_count',
               'in_window_ambiguous_count', 'in_window_null_deal_count', 'release_date',
               'eligible_for_sale', 'eligibility_reason', 'cache_path', 'cache_status']),
    'records': ('data/intermediate/autumn_sale_evidence_records.csv', ['AppID', 'Name', 'sale_year'] + audit.OBS_FIELDS),
    'diagnostics': (coverage.DIAGNOSTICS,
                    ['appid', 'name', 'sale_year', 'evidence_category', 'sale_start_utc', 'sale_end_utc',
                     'eligible_for_sale', 'eligibility_reason', 'release_date', 'cache_status',
                     'in_window_record_count', 'in_window_discount_count', 'in_window_full_price_count',
                     'in_window_ambiguous_count', 'in_window_null_deal_count', 'in_window_raw_indices_json',
                     'in_window_records_json', 'empty_raw_history', 'in_window_conflicting_timestamp_groups']),
    'games': ('data/intermediate/pilot_games.csv', ['AppID', 'Name', 'release_date']),
    'manifest': ('data/intermediate/itad_collection_manifest.csv', ['AppID', 'Name', 'country', 'steam_shop_id', 'cache_path']),
}


def protected_hashes(root):
    """Chain the completed 5B.2 receipt and protect its own bytes as well."""
    previous = json.loads((root / PRIOR_RECEIPT).read_text())
    expected = {}
    for group in ('protected_after_sha256', 'source_sha256', 'output_sha256'):
        for path, value in previous[group].items():
            require(path not in expected or expected[path] == value, 'Conflicting prior hash inventories')
            expected[path] = value
    actual = {}
    for path, value in sorted(expected.items()):
        require((root / path).is_file(), f'Missing protected input: {path}')
        actual[path] = audit.digest(root / path)
        require(actual[path] == value, f'Protected input changed: {path}')
    actual[PRIOR_RECEIPT] = audit.digest(root / PRIOR_RECEIPT)
    return actual


def source_hashes(root):
    return {p: audit.digest(root / p) for p in
            ('src/06_build_operational_labels.py', 'tests/test_operational_labels.py')}


def read_inputs(root):
    result = {}
    for name, (path, required) in INPUTS.items():
        with (root / path).open(encoding='utf-8', newline='') as stream:
            header = next(csv.reader(stream), [])
        require(len(header) == len(set(header)), f'Duplicate CSV headers: {path}')
        require(set(required) <= set(header), f'Missing required columns: {path}: {sorted(set(required) - set(header))}')
        rows = audit.read_csv(root / path)
        require(all(None not in r and all(v is not None for v in r.values()) for r in rows), f'Malformed CSV row: {path}')
        result[name] = rows
    return result


def integer(value, description, minimum=0):
    require(isinstance(value, str) and re.fullmatch(r'0|[1-9]\d*', value) is not None, f'Invalid {description}: {value!r}')
    number = int(value)
    require(number >= minimum, f'Invalid {description}: {value!r}')
    return number


def pair_key(row, appid_field='AppID'):
    integer(row[appid_field], 'AppID', 1)
    year = integer(row['sale_year'], 'sale year', 1)
    require(year in (2023, 2024, 2025), f'Unsupported sale year: {year}; 2026 excluded')
    return row[appid_field], year


def unique_index(rows, description, appid_field='AppID'):
    indexed = {}
    for row in rows:
        key = pair_key(row, appid_field)
        require(key not in indexed, f'Duplicate game-year pair in {description}: {key}')
        indexed[key] = row
    return indexed


def mapping(category):
    require(isinstance(category, str) and category in 'ABCD' and len(category) == 1, f'Invalid evidence category: {category!r}')
    return dict(discount_observed=1 if category == 'A' else '' if category == 'C' else 0,
                pu_status='positive' if category == 'A' else 'unlabeled',
                ambiguity_flag=category == 'C', requires_review=category == 'C')


def construct_labels(inputs, windows):
    """Reconcile saved evidence using the existing observation parser/category rule."""
    pairs = unique_index(inputs['pairs'], 'audit')
    diagnostics = unique_index(inputs['diagnostics'], 'coverage diagnostics', 'appid')
    require(set(pairs) == set(diagnostics), 'Audit and coverage pair keys differ')
    games, manifests = {}, {}
    for name, table in (('games', games), ('manifest', manifests)):
        for r in inputs[name]:
            integer(r['AppID'], 'AppID', 1)
            require(r['AppID'] not in table, f'Duplicate AppID in {name}')
            table[r['AppID']] = r
    expected = {(appid, y) for appid in games for y in windows}
    require(set(pairs) == expected and set(games) == set(manifests), 'Expected every pilot AppID for every sale year')
    observed = defaultdict(list)
    seen = set()
    for r in inputs['records']:
        key = pair_key(r)
        require(key in pairs, f'Evidence outside pilot: {key}')
        index = integer(r['source_record_index'], 'raw record index')
        require((*key, index) not in seen, f'Duplicate evidence raw index: {key} / {index}')
        seen.add((*key, index))
        try:
            raw = json.loads(r['raw_record_json'])
            require(type(raw['shop']['id']) is int and raw['shop']['id'] == 61, 'Only Steam shop 61 evidence permitted')
            parsed = audit.observation(raw, index)
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f'Malformed Steam evidence {key} / {index}: {exc}') from exc
        require(all(str(parsed[f]) == r[f] for f in audit.OBS_FIELDS), f'Raw/parsed evidence disagrees: {key} / {index}')
        start, end = windows[key[1]][2:]
        require(start <= audit.utc_stamp(parsed['timestamp_utc']) < end, f'Evidence outside half-open sale interval: {key} / {index}')
        require(r['Name'] == pairs[key]['Name'], f'Evidence name mismatch: {key}')
        observed[key].append(parsed)
    rows = []
    for key, r in sorted(pairs.items(), key=lambda item: (int(item[0][0]), item[0][1])):
        appid, year = key
        d, game, manifest = diagnostics[key], games[appid], manifests[appid]
        mapped = mapping(r['evidence_category'])
        start_date, _, start, end = windows[year]
        require(r['window_start_utc'] == d['sale_start_utc'] == audit.fmt(start) and
                r['window_end_exclusive_utc'] == d['sale_end_utc'] == audit.fmt(end), f'Exact UTC calendar mismatch: {key}')
        require(r['Name'] == d['name'] == game['Name'] == manifest['Name'] and r['Name'].strip(), f'Game name mismatch: {key}')
        require(r['release_date'] == d['release_date'] == game['release_date'], f'Release date mismatch: {key}')
        require(r['cache_status'] == d['cache_status'] == 'ok', f'Invalid audited cache: {key}')
        release = date.fromisoformat(game['release_date'])
        eligible = release <= date.fromisoformat(start_date)
        require(r['eligible_for_sale'] == d['eligible_for_sale'] == str(eligible), f'Release eligibility mismatch: {key}')
        require(r['eligibility_reason'] == d['eligibility_reason'], f'Eligibility reason mismatch: {key}')
        status = ('uncertain_release_hour' if release.isoformat() == start_date else
                  'eligible_by_release_date' if eligible else 'ineligible_by_release_date')
        require(manifest['country'] == 'US' and manifest['steam_shop_id'] == '61', f'Collection scope mismatch: {key}')
        require(r['cache_path'] == manifest['cache_path'] == f'data/raw/itad/{appid}.json', f'Cache path mismatch: {key}')
        inside = sorted(observed[key], key=lambda o: (audit.utc_stamp(o['timestamp_utc']), o['source_record_index']))
        require(r['evidence_category'] == d['evidence_category'] == audit.category(inside), f'Evidence category mismatch: {key}')
        kinds = Counter(o['observation_kind'] for o in inside)
        counts = dict(in_window_record_count=len(inside), in_window_discount_count=kinds['discount'],
                      in_window_full_price_count=kinds['full_price'], in_window_ambiguous_count=kinds['ambiguous'],
                      in_window_null_deal_count=sum(o['deal_status'] == 'null' for o in inside))
        for field, count in counts.items():
            require(integer(r[field], field) == integer(d[field], field) == count, f'Evidence count mismatch: {key} / {field}')
        indices = [o['source_record_index'] for o in inside]
        require(json.loads(d['in_window_raw_indices_json']) == indices and
                json.loads(d['in_window_records_json']) == inside, f'Coverage raw provenance mismatch: {key}')
        require(d['empty_raw_history'] in ('True', 'False'), f'Invalid empty-history flag: {key}')
        require(integer(d['in_window_conflicting_timestamp_groups'], 'conflict count') == len(coverage.conflicts(inside)),
                f'Conflict count mismatch: {key}')
        rows.append(dict(appid=appid, game_name=r['Name'], sale_year=year, sale_start_utc=audit.fmt(start),
                         sale_end_utc=audit.fmt(end), evidence_category=r['evidence_category'],
                         **mapped, label_rule_version=RULE,
                         label_source='cached ITAD /games/history/v2; Steam shop 61; US; Phase 5A.1 in-window evidence',
                         label_limitation_flag=True, eligibility_status=status,
                         eligibility_reason=r['eligibility_reason'], release_date=r['release_date'],
                         in_window_record_count=len(inside), discounted_record_count=kinds['discount'],
                         full_price_record_count=kinds['full_price'], ambiguous_record_count=kinds['ambiguous'],
                         null_deal_record_count=counts['in_window_null_deal_count'],
                         supporting_record_indices=coverage.compact([o['source_record_index'] for o in inside if o['observation_kind'] == 'discount']),
                         in_window_record_indices=coverage.compact(indices), source_shop_id=int(manifest['steam_shop_id']),
                         source_region=manifest['country'], source_currencies=';'.join(sorted({o['price_currency'] for o in inside if o['price_currency']})),
                         cache_path=r['cache_path'], empty_raw_history=d['empty_raw_history'] == 'True',
                         in_window_conflicting_timestamp_groups=integer(d['in_window_conflicting_timestamp_groups'], 'conflict count')))
        rows[-1]['requires_review'] |= status != 'eligible_by_release_date'
    return rows


def distributions(rows):
    def counts(pool):
        return dict(total_rows=len(pool), category_counts={c: sum(r['evidence_category'] == c for r in pool) for c in 'ABCD'},
                    operational_label_counts={str(label) if label != '' else 'null': sum(r['discount_observed'] == label for r in pool) for label in (1, 0, '')},
                    pu_status_counts={s: sum(r['pu_status'] == s for r in pool) for s in ('positive', 'unlabeled')})
    result = counts(rows)
    result['year_counts'] = {str(y): counts([r for r in rows if r['sale_year'] == y]) for y in (2023, 2024, 2025)}
    result.update(null_label_count=sum(r['discount_observed'] == '' for r in rows),
                  eligibility_uncertainty_count=sum(r['eligibility_status'] == 'uncertain_release_hour' for r in rows),
                  eligibility_status_counts=dict(Counter(r['eligibility_status'] for r in rows)),
                  review_required_count=sum(r['requires_review'] for r in rows),
                  duplicate_count=len(rows) - len({(r['appid'], r['sale_year']) for r in rows}))
    return result


def check_current_pilot(stats):
    require(stats['total_rows'] == 300 and stats['duplicate_count'] == 0, 'Expected 300 unique operational rows')
    require(stats['category_counts'] == dict(A=175, B=3, C=0, D=122), 'Current pilot categories differ; review required')
    require(stats['operational_label_counts'] == {'1': 175, '0': 125, 'null': 0}, 'Unexpected operational label counts')
    require(stats['pu_status_counts'] == {'positive': 175, 'unlabeled': 125}, 'Unexpected PU counts')
    for year, ones, zeros in ((2023, 55, 45), (2024, 60, 40), (2025, 60, 40)):
        require(stats['year_counts'][str(year)]['operational_label_counts'] == {'1': ones, '0': zeros, 'null': 0}, f'Unexpected {year} label counts')
    require(stats['eligibility_uncertainty_count'] == 1, 'Expected unresolved same-day release-hour pair')


def run(root=ROOT, execution_checks=None):
    root = Path(root)
    with coverage.offline_guard() as attempts:
        before = protected_hashes(root)
        frozen = audit.frozen_hashes(root)
        windows = audit.canonical_windows(root)
        inputs = read_inputs(root)
        require(len(inputs['games']) == 100, 'Expected unchanged 100-game pilot')
        rows = construct_labels(inputs, windows)
        stats = distributions(rows)
        check_current_pilot(stats)
        sources = source_hashes(root)
        if execution_checks is None:
            old = json.loads((root / RECEIPT).read_text()) if (root / RECEIPT).exists() else {}
            execution_checks = old.get('execution_checks', {})
            if execution_checks.get('source_sha256') != sources or execution_checks.get('protected_sha256') != before:
                execution_checks = dict(full_offline_test_suite='NOT RUN: use --verify',
                                        deterministic_full_runs='NOT RUN: use --verify', source_sha256=sources, protected_sha256=before)
        require(execution_checks['source_sha256'] == sources and execution_checks['protected_sha256'] == before, 'Verification fingerprint mismatch')
        pu = [{f: r[f] for f in ('appid', 'sale_year', 'evidence_category', 'pu_status', 'label_rule_version')} for r in rows]
        for path, values in ((LABELS, rows), (PU, pu)):
            audit.write_csv(root / path, values, list(values[0]))
            require(audit.read_csv(root / path) == [{k: str(v) for k, v in r.items()} for r in values], f'CSV round-trip mismatch: {path}')
        receipt = dict(phase='5B.3', script_execution_status='PASS', label_rule_version=RULE,
                       target='recorded Steam-store discount occurrence; not verified participation', **stats,
                       execution_checks=execution_checks,
                       checks=dict(evidence_categories_unchanged=True, exact_boundaries=True, steam_only=True,
                                   provenance_reconciled=True, pu_projection_reconciled=True, saved_csv_round_trip=True,
                                   eligible_uncertainty_retained=True, no_2026_rows=True, feature_table_created=False,
                                   diagnostic_network_attempts=len(attempts), api_requests=0, new_histories=0,
                                   protected_inputs_unchanged=True),
                       frozen_phase4_before_sha256=frozen, frozen_phase4_after_sha256=audit.frozen_hashes(root),
                       protected_before_sha256=before, protected_after_sha256=protected_hashes(root), source_sha256=sources,
                       output_sha256={p: audit.digest(root / p) for p in (LABELS, PU)})
        (root / REPORT).write_text(build_report(rows, receipt, audit.calendar_data(root)), encoding='utf-8')
        receipt['output_sha256'][REPORT] = audit.digest(root / REPORT)
        (root / RECEIPT).write_text(json.dumps(receipt, sort_keys=True, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        require(before == protected_hashes(root), 'Protected inputs changed during execution')
    return rows, pu, receipt


def verify_execution(root=ROOT):
    root = Path(root)
    before = protected_hashes(root)
    with coverage.offline_guard():
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream).run(unittest.defaultTestLoader.discover(str(root / 'tests')))
        print(stream.getvalue(), end='')
        require(result.wasSuccessful(), 'Offline tests failed')
        checks = dict(full_offline_test_suite='PASS', tests_run=result.testsRun, failures=len(result.failures),
                      errors=len(result.errors), skipped=len(result.skipped), deterministic_full_runs='PENDING',
                      source_sha256=source_hashes(root), protected_sha256=before)
        run(root, checks)
        first = {p: (root / p).read_bytes() for p in OUTPUTS}
        run(root, checks)
        require(first == {p: (root / p).read_bytes() for p in OUTPUTS}, 'Repeated full executions differ')
        checks['deterministic_full_runs'] = 'PASS: all four outputs byte-identical in two full executions'
        run(root, checks)
        final = {p: (root / p).read_bytes() for p in OUTPUTS}
        result = run(root, checks)
        require(final == {p: (root / p).read_bytes() for p in OUTPUTS}, 'Verified full executions differ')
        require(before == protected_hashes(root), 'Protected input changed during tests/reruns')
    print(f'Phase 5B.3 PASS: {len(result[0])} operational rows; stop before Phase 6.')
    return result


def build_report(rows, receipt, calendar):
    stats = receipt
    lines = ['# Phase 5B.3 — Operational Label Construction', '',
             '**Status:** operational labels constructed; human review required before Phase 6. No predictive features, models, accuracy estimates or PU algorithms were created.', '',
             '## Research objective and decision', '',
             '> Can historical Steam game metadata and pre-sale pricing behavior predict whether a Steam-store discount will be RECORDED during the Steam Autumn Sale?', '',
             'The broader motivation remains actual Autumn Sale discount participation. Phase 5B.2 did not establish independently verified full-sale negatives using the accessible sources. The authorized operational target measures recorded discount occurrence so that a reproducible pipeline can proceed without asserting complete historical capture. No additional historical-source research was conducted.', '',
             '## Formal target and evidence mapping', '',
             '`discount_observed = 1` when at least one qualifying Steam-store discounted-price observation is timestamped inside the verified sale interval. `discount_observed = 0` when no qualifying discounted observation exists. Category C is withheld as a blank/null label with `ambiguity_flag=True` and `requires_review=True`. This ambiguity exception deliberately avoids silently converting unusable in-window evidence into zero.', '',
             'The implementation reuses `observation()` and `category()` from the unchanged Phase 5A.1 script. Qualifying discount observations require valid consistent money/currency information, explicit cut > 0 and price < regular. No new discount detector or price persistence assumption is introduced.', '',
             audit.md_table(['Evidence category', 'discount_observed', 'pu_status', 'Meaning'], [
                 ['A', 1, 'positive', 'At least one recorded in-window discount'],
                 ['B', 0, 'unlabeled', 'Full-price-only in-window records; discount not observed'],
                 ['C', 'null', 'unlabeled', 'Ambiguous/null in-window evidence without a discount; review required'],
                 ['D', 0, 'unlabeled', 'No directly timestamped in-window records; discount not observed']]), '',
             'Rule version: **operational_observed_v1**. Collection scope: **Steam shop 61, US**. `label_limitation_flag=True` for every row because complete historical event capture is unproven.', '',
             '### Methodological disclosure', '',
             '> Games with at least one qualifying Steam-store discount observation during the official Autumn Sale window were assigned a positive operational label. Games without such an observation were assigned a negative operational label, except that Category C remains null for review. Because historical price coverage is incomplete, negative operational labels do not establish that a game was never discounted. The resulting target measures recorded discount occurrence rather than independently verified sale participation.', '',
             '**Operational negatives must not be interpreted as verified non-discounts, non-participation or uninterrupted full price. These labels are not ground truth for actual sale participation or formal Valve event enrollment.**', '',
             '## Exact event windows', '',
             'Intervals are half-open: **start <= timestamp < end**. Exact start is included; exact end is excluded. The unchanged centralized calendar and existing Valve verification supply both boundaries:', '',
             audit.md_table(['Year', 'Start UTC (inclusive)', 'End UTC (exclusive)', 'Pacific', 'Existing verification'],
                            [[e['sale_year'], e['sale_start_utc'], e['sale_end_utc'], '10 AM PST' if e['sale_year'] < 2025 else '10 AM PDT',
                              f"[Valve]({e['source_url']})"] for e in calendar['events']]), '',
             'No approximate calendar-day boundaries or 2026 sale rows are used.', '',
             '## Label distributions', '',
             audit.md_table(['Year', 'Rows', '1: discount recorded', '0: discount not observed', 'Null', 'A / B / C / D'], [
                 [y, s['total_rows'], s['operational_label_counts']['1'], s['operational_label_counts']['0'],
                  s['operational_label_counts']['null'], ' / '.join(str(s['category_counts'][c]) for c in 'ABCD')]
                 for y, s in list(stats['year_counts'].items()) + [('All', stats)]]), '',
             'PU status totals: **175 positive / 125 unlabeled**. All 300 original game-year pairs remain, with unchanged categories. There are zero current C cases and zero null labels. Label counts are checked against the approved frozen pilot; an unexpected scope/count change stops execution for review rather than forcing results.', '',
             '## Dataset provenance and eligibility', '',
             'The label builder reads the existing audit, long evidence records, coverage diagnostics, pilot and collection manifest. Raw JSON embedded in each in-window record is reparsed with the shared parser, checked against the saved fields, and reconciled with the coverage JSON and counts. The preceding receipt chain protects the cached original histories and all earlier source/evidence/verification artifacts with SHA-256. No evidence input or previous receipt is regenerated.', '',
             '`supporting_record_indices` contains only raw-array indices of qualifying in-window discounts; B/C/D have an empty array. `in_window_record_indices` retains all actual in-window indices. Shop and region come from the manifest, including for empty histories; they describe the collection request, not an invented observed price. `source_currencies` is blank if none is observed. Currency, counts and conflict indicators remain target provenance.', '',
             f"Eligibility uncertainty: **{stats['eligibility_uncertainty_count']} pair**. nekowater (AppID 2650840), 2023, retains its B category and operational zero, with `eligibility_status=uncertain_release_hour` and `requires_review=True`. The source release date matches the sale start date; the release hour remains unknown. The remaining 299 pairs are `eligible_by_release_date`, which certifies the existing date rule, not continuous purchase availability. No row was excluded.", '',
             'Three empty-history games contribute nine D operational zeros. Their missing histories are visible via `empty_raw_history`; no price state or actual absence of discount is inferred. Known historical timestamp conflicts are not repaired. In-window conflicts, if present, remain explicit diagnostics; the current in-window conflict count is zero.', '',
             '## Limitations and evaluation implications', '',
             '- **False negatives relative to actual discounts:** a discount may have occurred without being recorded. A zero is correct for this observation-based target but can be incorrect if interpreted as actual non-discounting. No true false-negative rate was estimated.',
             '- **Coverage:** change-oriented records, missing histories, irregular gaps and unproven complete capture remain. Before/after records do not fill the sale interval. No coverage threshold, interpolation or persistence is used.',
             '- **Sampling:** the 100-game pilot was designed for diagnostic diversity, not representativeness. Its operational class balance and future performance cannot establish population rates or accuracy.',
             '- **Evaluation:** future training uses 2023–2024 (115 operational ones / 85 zeros); 2025 is temporal validation (60 / 40). Evaluate agreement with recorded discounts, not ground-truth participation. Coverage differences across games/years can confound apparent performance. Repeated AppIDs across years and uncertain eligibility require transparent handling.',
             '- **Probability interpretation:** any future probability concerns a discount being recorded under these data-source/scope conditions. It is not an independently calibrated probability of actual discount participation. Coverage and publisher/game characteristics may affect recording availability; associations are not causal effects.', '',
             '## PU view and future feature safeguards', '',
             'The separate PU CSV projects only identifiers, original evidence category, PU status and rule version. All non-A pairs are unlabeled; none is a verified negative. It supports an optional later sensitivity experiment. No PU algorithm, class-prior estimate or assumption that positives are selected completely at random is implemented.', '',
             'The operational CSV is a **target/provenance table, not a predictor table**. Constructing retrospective targets from in-sale records is valid; feeding those observations into predictors would leak the target. Do not use evidence categories, PU status, supporting indices, in-window counts, ambiguity/coverage flags, future history emptiness/conflicts or collection metadata as predictors. They can reflect the sale or later collection, even where no post-sale prices are copied.', '',
             'After human review, Phase 6 must construct predictors separately from information available strictly before each sale start. Current snapshot Price, Discount, reviews, playtime and Peak CCU are not automatically historically valid. Any pre-sale pricing behavior must use timestamp-filtered pre-event observations; no sale/post-sale observation or 2026 outcome may influence historical predictors. No feature selection, exclusion policy for uncertain eligibility, modeling or tuning was performed here.', '',
             '## Reproducibility and validation', '',
             '```bash', 'python3 -B src/06_build_operational_labels.py --verify', '```', '',
             'Standard-library-only execution reads local files under a socket/DNS prohibition. Outputs are sorted by numeric AppID then sale year. Null labels are blank CSV cells; booleans use the established `True`/`False` CSV convention. A normal run only reuses execution checks for matching source/protected fingerprints; `--verify` runs the whole offline suite and proves repeated byte-identical CSVs, report and receipt.', '',
             audit.md_table(['Check', 'Result'], [
                 ['Full offline tests', f"{receipt['execution_checks']['full_offline_test_suite']}; {receipt['execution_checks'].get('tests_run', 'not run')} tests"],
                 ['Repeated full execution', receipt['execution_checks']['deterministic_full_runs']],
                 ['Protected preceding files / frozen Phase 4 inputs', f"{len(receipt['protected_before_sha256'])} / {len(receipt['frozen_phase4_before_sha256'])}; unchanged before/after"],
                 ['Unique pairs / duplicates / null labels', f"300 / {stats['duplicate_count']} / {stats['null_label_count']}"],
                 ['API/network attempts / new histories', '0 / 0'],
                 ['Predictive features / trained models / 2026 target rows', 'None']]), '',
             'Artifacts: [operational labels](../data/intermediate/autumn_sale_operational_labels.csv), [PU view](../data/intermediate/autumn_sale_pu_labels.csv), [validation receipt](autumn_sale_operational_label_validation.json). Earlier context: [exact audit](autumn_sale_evidence_audit.md), [coverage investigation](autumn_sale_coverage_investigation.md), [ground-truth feasibility](autumn_sale_ground_truth_feasibility.md).', '',
             '**Stop:** Phase 5B.3 is complete. Human review precedes Phase 6. There are no unresolved implementation failures; source completeness, true participation, release-hour precision and later predictor timing remain scientific limitations.', '']
    return '\n'.join(lines)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true', help='Run all offline tests and verify deterministic full executions')
    args = parser.parse_args()
    if args.verify:
        verify_execution()
    else:
        run()
