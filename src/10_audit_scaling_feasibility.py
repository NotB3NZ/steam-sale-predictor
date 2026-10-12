"""Phase 8A: offline catalog/evidence audit and sampling plan; no collection or fitting.

python3 -B src/10_audit_scaling_feasibility.py --verify
"""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import date
from fractions import Fraction
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import platform
import re
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir())/'steam-scaling-matplotlib'))
spec = importlib.util.spec_from_file_location('scaling_features', ROOT/'src/07_build_autumn_features.py')
features = importlib.util.module_from_spec(spec)
spec.loader.exec_module(features)
audit, coverage = features.audit, features.coverage
from plotting_style import BLUE, ORANGE, GRAY, light_style, save_figure, plt

MASTER = 'data/intermediate/games_master.csv'
PILOT = 'data/intermediate/pilot_games.csv'
COLLECTION = 'data/intermediate/itad_collection_manifest.csv'
CANDIDATES = 'data/intermediate/autumn_sale_scaling_candidates.csv'
FEASIBILITY = 'reports/autumn_sale_scaling_feasibility.json'
REPORT = 'reports/autumn_sale_scaling_feasibility.md'
PLAN = 'reports/autumn_sale_sampling_plan.md'
VALIDATION = 'reports/autumn_sale_scaling_validation.json'
FIGURES = ['scaling_catalog_release_years', 'scaling_historical_coverage',
           'scaling_sampling_composition', 'scaling_population_funnel']
OUTPUTS = [CANDIDATES, FEASIBILITY, REPORT, PLAN, VALIDATION] + [f'reports/figures/{f}.png' for f in FIGURES]
SOURCE_FILES = ['src/10_audit_scaling_feasibility.py', 'tests/test_scaling_feasibility.py']
EDITABLE_DOCS = ['README.md', 'PROJECT_CONTEXT.md', 'PROJECT_STATUS.md']
SIZES = [500, 1000, 2000, 5000]
SEED = 42
STRATA = ['before_2015', '2015_2019', '2020_2022', '2023_before_sale']
APPROVED = ['game_age_days', 'release_year', 'release_month', 'release_quarter',
            'prior_price_record_count', 'prior_discount_count', 'prior_discount_rate',
            'days_since_last_price_record', 'days_since_last_discount', 'max_prior_discount_pct',
            'mean_prior_discount_pct', 'last_observed_price', 'last_observed_discount_pct',
            'has_prior_price_history', 'has_prior_discount_observation']
FIELDS = ['appid', 'pilot_membership', 'release_date', 'release_year'] + \
         [f'eligibility_{y}' for y in (2023, 2024, 2025)] + \
         [f'release_hour_uncertain_{y}' for y in (2023, 2024, 2025)] + \
         ['sampling_stratum', 'sampling_priority', 'probability_sample_rank', 'selection_status'] + \
         [f'included_in_{n}' for n in SIZES]
require = coverage.require


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+'\n', encoding='utf-8')


def validate_prior(root=ROOT):
    """Fail before output writes if a completed required artifact is absent/changed."""
    root = Path(root)
    for p in [MASTER, PILOT, COLLECTION, 'src/03_fetch_itad.py', 'src/06_build_operational_labels.py',
              'src/07_build_autumn_features.py', 'src/08_train_baseline_models.py', 'src/09_train_ensemble_models.py',
              'src/plotting_style.py', 'reports/autumn_sale_feature_manifest.json',
              'reports/autumn_sale_ensemble_validation.json'] + EDITABLE_DOCS:
        require((root/p).is_file(), f'Missing required completed artifact: {p}')
    receipt = read_json(root/'reports/autumn_sale_ensemble_validation.json')
    require(receipt['status'] == 'PASS' and set(receipt['comparison_metrics']['models']) ==
            {'bernoulli_baseline', 'logistic_regression', 'random_forest', 'xgboost'}, 'Expected verified four-model Phase 7B')
    expected = {}
    for group in ['protected_after_sha256', 'source_sha256', 'output_sha256']:
        for p, h in receipt[group].items():
            require(p not in expected or expected[p] == h, f'Conflicting prior integrity entry: {p}')
            expected[p] = h
    for p, h in expected.items():
        require((root/p).is_file(), f'Missing completed artifact: {p}')
        require(audit.digest(root/p) == h, f'Completed artifact changed: {p}')
    manifest = read_json(root/'reports/autumn_sale_feature_manifest.json')
    require(manifest['baseline_feature_allowlist'] == APPROVED == list(features.ALLOWLIST), 'Approved feature manifest disagrees')
    return receipt


def protected_hashes(root=ROOT):
    root = Path(root)
    validate_prior(root)
    paths = set()
    for base in ['src', 'tests', 'data', 'reports', 'models']:
        for p in (root/base).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts and p.name != '.DS_Store':
                paths.add(str(p.relative_to(root)))
    for p in ['games.csv', 'games.json', 'test.py', 'requirements.txt', 'requirements-baseline.txt', 'requirements-ensemble.txt']:
        if (root/p).is_file(): paths.add(p)
    paths -= set(OUTPUTS + SOURCE_FILES)
    current = {p: audit.digest(root/p) for p in sorted(paths)}
    if (root/VALIDATION).exists():
        require(read_json(root/VALIDATION)['protected_after_sha256'] == current,
                'Earlier-file inventory changed since the scaling audit; review before proceeding')
    return current


def valid_appid(value):
    return isinstance(value, str) and re.fullmatch(r'[1-9][0-9]*', value) is not None and int(value) <= 2**32-1


def release_date(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value): return None
    try: return date.fromisoformat(value)
    except ValueError: return None


def read_catalog(path):
    """Stream wide rows and retain only predeclared identity/release fields."""
    with Path(path).open(encoding='utf-8', newline='') as stream:
        reader = csv.DictReader(stream)
        require(len(reader.fieldnames or []) == len(set(reader.fieldnames or [])) and
                {'AppID', 'release_date', 'release_year'} <= set(reader.fieldnames or []), 'Invalid master catalog schema')
        rows = []
        for row in reader:
            require(None not in row and all(v is not None for v in row.values()), 'Malformed master row')
            rows.append({k: row[k] for k in ['AppID', 'release_date', 'release_year']})
    return rows


def eligibility(release, window):
    if release is None: return dict(eligible=None, uncertain=None, timing='unknown_release_date')
    start, end = map(date.fromisoformat, window[:2])
    timing = ('before_start_date' if release < start else 'on_start_date' if release == start else
              'interior_sale_dates' if release < end else 'on_end_date' if release == end else 'after_end_date')
    return dict(eligible=int(release <= start), uncertain=int(release == start), timing=timing)


def audit_catalog(rows, windows):
    ids = Counter(r['AppID'] for r in rows if valid_appid(r['AppID']))
    dates = [release_date(r['release_date']) for r in rows]
    invalid = sum(not valid_appid(r['AppID']) and bool(r['AppID'].strip()) for r in rows)
    result = dict(path=MASTER, total_records=len(rows), unique_valid_appids=len(ids),
                  duplicate_appid_values=sum(n > 1 for n in ids.values()),
                  duplicate_excess_rows=sum(n-1 for n in ids.values()),
                  missing_appids=sum(not r['AppID'].strip() for r in rows), invalid_identifiers=invalid,
                  missing_release_dates=sum(not r['release_date'].strip() for r in rows),
                  invalid_release_dates=sum(d is None and bool(r['release_date'].strip()) for r, d in zip(rows, dates)),
                  release_year_mismatches=sum(d is not None and r['release_year'] != str(d.year) for r, d in zip(rows, dates)),
                  release_year_distribution=dict(sorted(Counter(str(d.year) for d in dates if d is not None).items())),
                  release_precision='Date-only YYYY-MM-DD; no release time or purchase-availability guarantee.',
                  duplicate_rule='All rows with a repeated valid AppID are excluded from candidates; no arbitrary deduplication or source repair.',
                  eligibility_by_year={})
    for y, w in windows.items():
        stats = Counter(eligibility(d, w)['timing'] for d in dates)
        stats.update(eligible_by_existing_date_rule=sum(eligibility(d, w)['eligible'] == 1 for d in dates),
                     denominator_catalog_records=len(rows), definitely_before_start_date=stats['before_start_date'])
        result['eligibility_by_year'][str(y)] = {k: int(stats[k]) for k in
            ['denominator_catalog_records', 'before_start_date', 'on_start_date', 'interior_sale_dates',
             'on_end_date', 'after_end_date', 'unknown_release_date', 'eligible_by_existing_date_rule', 'definitely_before_start_date']}
    result['eligible_all_three_date_rule'] = sum(d is not None and all(eligibility(d, w)['eligible'] for w in windows.values()) for d in dates)
    result['definitely_before_all_three_start_dates'] = sum(d is not None and all(d < date.fromisoformat(w[0]) for w in windows.values()) for d in dates)
    return result


def stratum(release):
    if release is None: return 'unknown_release_date'
    if release.year < 2015: return 'before_2015'
    if release.year <= 2019: return '2015_2019'
    if release.year <= 2022: return '2020_2022'
    if release.year == 2023: return '2023_before_sale'  # Applied to the sampling frame only.
    return 'outside_historical_frame'


def sample_candidates(rows, pilot_ids, windows, sizes=SIZES):
    """Target/coverage-free, order-invariant stratified priorities and nested cohorts."""
    require(sorted(set(sizes)) == list(sizes) and min(sizes) > len(pilot_ids), 'Cohort totals must exceed pilot size')
    counts = Counter(r['AppID'] for r in rows if valid_appid(r['AppID']))
    candidates = []; pools = defaultdict(list)
    for r in rows:
        if not valid_appid(r['AppID']) or counts[r['AppID']] != 1: continue
        appid = int(r['AppID']); d = release_date(r['release_date'])
        release_consistent = d is not None and r['release_year'] == str(d.year)
        member = appid in pilot_ids
        in_frame = release_consistent and all(d < date.fromisoformat(w[0]) for w in windows.values())
        same_day = d is not None and d == date.fromisoformat(windows[2023][0])
        status = ('pilot_cohort' if member else 'eligible_reserve' if in_frame else
                  'excluded_invalid_release' if not release_consistent else
                  'excluded_uncertain_release_hour' if same_day else 'excluded_after_2023_start')
        s = ('pilot_start_day_uncertain' if member and same_day else stratum(d) if in_frame or member else
             'outside_historical_frame' if d is not None else 'unknown_release_date')
        item = dict(appid=appid, pilot_membership=int(member), release_date=r['release_date'],
                    release_year=d.year if d is not None else '', sampling_stratum=s,
                    sampling_priority='', probability_sample_rank='', selection_status=status)
        for y, w in windows.items():
            v = eligibility(d, w)
            item[f'eligibility_{y}'] = '' if v['eligible'] is None else v['eligible']
            item[f'release_hour_uncertain_{y}'] = '' if v['uncertain'] is None else v['uncertain']
        if in_frame and not member:
            item['sampling_priority'] = hashlib.sha256(f'{SEED}|{appid}'.encode()).hexdigest()
            pools[s].append(item)
        candidates.append(item)
    require({r['appid'] for r in candidates if r['pilot_membership']} == set(pilot_ids), 'Pilot IDs missing or ambiguous in master')
    weighted = []
    for s, pool in sorted(pools.items()):
        for rank, r in enumerate(sorted(pool, key=lambda r: (r['sampling_priority'], r['appid'])), 1):
            # Rational arithmetic makes cross-stratum allocation exact and platform-independent.
            weighted.append((Fraction(2*rank-1, 2*len(pool)), s, r['sampling_priority'], r['appid'], r))
    weighted.sort(key=lambda v: v[:4])
    require(len(weighted) >= max(sizes)-len(pilot_ids), 'Insufficient eligible nonpilot frame for requested cohort')
    for rank, (_, _, _, _, r) in enumerate(weighted, 1): r['probability_sample_rank'] = rank
    for r in candidates:
        rank = r['probability_sample_rank']
        for n in sizes: r[f'included_in_{n}'] = int(bool(r['pilot_membership']) or bool(rank and rank <= n-len(pilot_ids)))
        if rank and rank <= max(sizes)-len(pilot_ids): r['selection_status'] = 'selected_expansion_candidate'
    candidates.sort(key=lambda r: r['appid'])
    strata_counts = {s: len(pools[s]) for s in STRATA}
    cohort_stats = {}
    for n in sizes:
        new = [r for r in candidates if r[f'included_in_{n}'] and not r['pilot_membership']]
        selected = Counter(r['sampling_stratum'] for r in new)
        cohort_stats[str(n)] = dict(total_games=n, pilot_games=len(pilot_ids), new_probability_sample_games=len(new),
            new_sample_by_stratum={s: selected[s] for s in STRATA},
            within_stratum_inclusion_probability={s: selected[s]/strata_counts[s] if strata_counts[s] else None for s in STRATA})
    plan = dict(seed=SEED, nested_cohorts=True, sizes_are_total_including_pilot=True,
        sampling_frame='Unique valid nonpilot AppIDs with consistent release dates strictly before every 2023–2025 sale start date.',
        frame_nonpilot_games=len(weighted), frame_by_stratum=strata_counts,
        pilot_games=len(pilot_ids), cohorts=cohort_stats,
        priority_definition='SHA-256 of UTF-8 42|appid, ascending within each release stratum; ties by integer AppID.',
        interleaving='Sort within-stratum rank r by exact rational (r-0.5)/stratum_size; ties by stratum, SHA-256 and AppID. Take prefixes.',
        inclusion_probability_note='k_h/n_h describes the stratified pseudorandom sampling design over randomized priorities; the realized fixed-seed sample is deterministic. Apply weights only to the new cohort, never to the diagnostic pilot.',
        later_release_limitation='New games released on/after the 2023 start date are outside this balanced historical frame; no claim of representation for them or the full Steam catalog.',
        selection_variables=['AppID', 'release_date', 'release_year', 'pilot membership'],
        prohibited_selection_variables='Discount outcomes, evidence categories, price histories, snapshot prices/reviews/activity and provider matching success.',
        evidence_coverage_role='Known only after collection for new games; diagnostic strata, not inclusion filters or replacement rules.')
    return candidates, plan


def summarize_histories(histories, windows):
    n = len(histories)
    result = dict(local_cohort_denominator=n, games_with_any_temporal_record=sum(bool(rs) for rs in histories.values()),
        games_with_any_valid_price_record=sum(any(r['observation_kind'] in ('discount','full_price') for r in rs) for rs in histories.values()),
        games_with_any_discount_record=sum(any(r['observation_kind'] == 'discount' for r in rs) for rs in histories.values()),
        games_with_no_temporal_observations=sum(not rs for rs in histories.values()),
        temporal_records=sum(len(rs) for rs in histories.values()),
        valid_price_records=sum(sum(r['observation_kind'] in ('discount','full_price') for r in rs) for rs in histories.values()),
        discounted_records=sum(sum(r['observation_kind'] == 'discount' for r in rs) for rs in histories.values()),
        by_year={})
    for y, w in windows.items():
        buckets = {side: [] for side in ['before', 'inside', 'after']}
        for rs in histories.values():
            for side, part in zip(buckets, audit.partition(rs, w[2], w[3])): buckets[side].append(part)
        stats = dict(denominator_local_games=n)
        for side, groups in buckets.items():
            stats[side] = dict(games_with_temporal_records=sum(bool(rs) for rs in groups),
                games_with_valid_price_records=sum(any(r['observation_kind'] in ('discount','full_price') for r in rs) for rs in groups),
                games_with_discount_records=sum(any(r['observation_kind'] == 'discount' for r in rs) for rs in groups),
                temporal_records=sum(len(rs) for rs in groups))
        stats['games_without_in_window_record'] = n-stats['inside']['games_with_temporal_records']
        result['by_year'][str(y)] = stats
    result['partition_rule'] = 'Before timestamp < start; inside start <= timestamp < end; after timestamp >= end. Observations, not continuous price coverage.'
    return result


def local_evidence(root, catalog_ids, pilot, windows):
    manifest = features.read_table(root/COLLECTION, ['AppID','itad_game_id','history_record_count','cache_path'])
    indexed = {r['AppID']: r for r in manifest}
    require(len(manifest) == len(indexed) == len(pilot) and set(indexed) == {r['AppID'] for r in pilot}, 'Pilot/collection identities disagree')
    histories = {}; infos = {}; sizes = []
    for game in pilot:
        appid = int(game['AppID']); p = root/'data/raw/itad'/f'{appid}.json'
        require(p.is_file(), f'Missing required historical cache: {p}')
        records, info = audit.load_cache(root, game, indexed[game['AppID']])
        require(info['cache_status'] == 'ok', f'Historical cache provenance/parser issue: {appid}: {info}')
        histories[appid] = records; infos[appid] = info; sizes.append(p.stat().st_size)
    cache_ids = {int(p.stem) for p in (root/'data/raw/itad').glob('*.json') if valid_appid(p.stem)}
    require(cache_ids == set(histories), 'Unaccounted local historical cache; inspect before reporting coverage')
    result = summarize_histories(histories, windows)
    labels = features.read_table(root/features.LABELS, ['appid','sale_year','evidence_category','discount_observed'])
    require(len(labels) == 3*len(pilot), 'Existing label row count disagrees')
    for r in labels:
        rs = audit.partition(histories[int(r['appid'])], *windows[int(r['sale_year'])][2:])[1]
        require(audit.category(rs) == r['evidence_category'], 'Saved evidence categories disagree with local records')
    result.update(catalog_denominator=len(catalog_ids), catalog_games_with_local_cache=len(histories),
        catalog_games_without_local_cache=len(catalog_ids)-len(histories),
        provider_coverage_for_uncached_games='UNKNOWN: no requests made; no provider-side availability inference.',
        continuous_sale_coverage_unestablished_games=len(pilot), uncertain_complete_capture_games=len(pilot),
        malformed_cache_count=0, collection_status_counts=dict(Counter(r['history_status'] for r in manifest)),
        existing_evidence_categories=dict(Counter(r['evidence_category'] for r in labels)),
        cache_wrapper_bytes=dict(total=sum(sizes), min=min(sizes), max=max(sizes), mean=sum(sizes)/len(sizes)),
        record_count_range=dict(min=min(map(len,histories.values())),max=max(map(len,histories.values()))),
        known_external_potential='The existing lookup/history contract can be queried for new AppIDs in an approved future collection. Match rate and historical completeness are unestablished.',
        observation_warning='An empty response is observed local absence of returned records, not absence of discounts or a verified complete negative.')
    return result


def collection_feasibility(local):
    scenarios = {}
    for n in SIZES:
        u = n-local['local_cohort_denominator']
        scenarios[str(n)] = dict(total_games=n, reusable_pilot_caches=local['local_cohort_denominator'], uncached_candidates=u,
            all_matched_no_retry_requests=2*u, cold_start_all_matched_requests=2*n,
            mapping_fraction_scenarios={str(q): u*(1+q) for q in [0.5,0.8,1.0]},
            at_most_three_attempts_per_endpoint_all_matched_bound=6*u,
            pacing_floor_minutes_all_matched=max(2*u-1,0)/60,
            hypothetical_120_requests_per_5_minutes_floor_minutes=2*u/24,
            pilot_mean_wrapper_size_scenario_bytes=n*local['cache_wrapper_bytes']['mean'])
    return dict(provider='IsThereAnyDeal', lookup_endpoint='/games/lookup/v1', history_endpoint='/games/history/v2',
        authentication='ITAD-API-Key header from ITAD_API_KEY environment variable; no credential needed for this audit.',
        configuration=dict(country='US',shops='61',since='2021-01-01T00:00:00Z'),
        pagination='Current code sends one array-returning history request per matched game; no cursor, offset, page or pagination loop. Provider limits/truncation remain unestablished offline.',
        recorded_quota='Existing Phase 4 report records a verified-email default of 1,000 requests per five minutes, reviewed 2026-10-05. Account-specific/current quota is NOT verified by this audit.',
        retries='At most three attempts. Exponential waits 2s/4s for transient connection/408/5xx failures; 429 honors Retry-After. Missing/invalid Retry-After or waits >60s stop; 401/403 and redirects abort. Per-request timeout 30s.',
        pacing='Default serial request-start spacing at least one second. Latency, throttles, retries and checkpoints add time; floors are not completion-time forecasts.',
        caching='Atomic JSON replacement, configuration/provenance checks, compatible cache reuse, deliberate retry of incomplete matched histories, forced refresh archives old files.',
        checkpoint_resume='Each completed game is cached; restart reuses valid cache. Manifest/report written after traversal; no durable per-attempt scheduler or bulk progress checkpoint. Existing smoke gate is pilot-hash-bound.',
        response_size_constraints='No documented response-size cap or truncation detector in current code; entire response/body and decoded history retained in memory and duplicated in cache wrappers. Provider cap unknown.',
        request_formula='U uncached games: Q=U + q*U*H before retries, where q is mapping fraction and H history requests per match (current implementation H=1). Add retry attempts; apply actual account quota.',
        workload=scenarios,
        storage_note='Wrapper-size scenarios use the nonrepresentative pilot mean; new-history size may differ substantially. No full-catalog coverage or storage forecast is established.',
        next_authorization='First parameterize a separate collection namespace and approve a bounded smoke/coverage trial; no collection in Phase 8A.')


def validate_candidates(rows, plan, pilot_ids, windows):
    sizes = sorted(map(int, plan['cohorts']))
    expected_fields = FIELDS[:-len(SIZES)] + [f'included_in_{n}' for n in sizes]
    require(all(set(r) == set(expected_fields) for r in rows), 'Candidate schema contains unexpected or missing fields')
    ids = [int(r['appid']) for r in rows]
    require(len(ids) == len(set(ids)) and all(valid_appid(str(r['appid'])) for r in rows), 'Candidate AppID uniqueness failure')
    require({int(r['appid']) for r in rows if int(r['pilot_membership'])} == set(pilot_ids), 'Candidate pilot membership mismatch')
    previous = set(); counts = {}
    for n in sizes:
        selected = {int(r['appid']) for r in rows if int(r[f'included_in_{n}'])}
        require(len(selected) == n and previous <= selected, 'Candidate cohort count/nesting mismatch')
        require(set(pilot_ids) <= selected, 'Candidate cohort omitted pilot game')
        for r in rows:
            flag = int(r[f'included_in_{n}']); require(flag in (0,1), 'Invalid candidate cohort flag')
            rank = int(r['probability_sample_rank']) if r['probability_sample_rank'] != '' else 0
            require(flag == int(int(r['pilot_membership']) == 1 or 0 < rank <= n-len(pilot_ids)), 'Candidate rank/cohort disagreement')
        new_counts = Counter(r['sampling_stratum'] for r in rows if int(r[f'included_in_{n}']) and not int(r['pilot_membership']))
        require({s:new_counts[s] for s in STRATA} == plan['cohorts'][str(n)]['new_sample_by_stratum'], 'Candidate stratum composition disagrees')
        previous = selected; counts[str(n)] = len(selected)
    for r in rows:
        require(int(r['pilot_membership']) in (0,1), 'Invalid pilot flag')
        d = release_date(r['release_date'])
        for y,w in windows.items():
            value = eligibility(d,w)
            for key, field in [('eligible',f'eligibility_{y}'),('uncertain',f'release_hour_uncertain_{y}')]:
                require(str(r[field]) == ('' if value[key] is None else str(value[key])), 'Candidate release eligibility disagreement')
        if r['probability_sample_rank'] != '':
            require(not int(r['pilot_membership']) and d is not None and
                    all(d < date.fromisoformat(w[0]) for w in windows.values()), 'Candidate rank outside historical frame')
    return dict(rows=len(rows),unique_appids=True,no_labels=True,nested_cohorts=True,cohort_counts=counts)


def readiness(root):
    def references(path, patterns):
        lines = (root/path).read_text().splitlines()
        return [dict(path=path,line=i,text=line.strip()) for i,line in enumerate(lines,1) if any(p in line for p in patterns)]
    modeling = features.read_table(root/features.MODELING, APPROVED)
    return dict(approved_features=APPROVED, feature_definitions_unchanged=True, existing_modeling_rows=len(modeling),
        existing_feature_missingness={f:sum(r[f]==' ' or r[f]=='' for r in modeling) for f in APPROVED},
        labeling=dict(evidence_categories={'A':'Recorded qualifying discount -> 1','B':'Only directly observed full-price records -> 0; continuity unverified',
            'C':'Ambiguous in-window evidence without qualifying discount -> null/review','D':'No in-window records -> 0; not verified absence of a discount'},
            barriers=references('src/06_build_operational_labels.py',['== 100','== 300','175','125','Expected every pilot','data/intermediate/pilot_games.csv','data/raw/itad/']),
            upstream_barriers=references('src/03_fetch_itad.py',['!= 100','<= 100','or 100','PILOT =','MANIFEST =','CACHE =','smoke_receipt_valid']),
            upstream_audit_barriers=references('src/04_audit_autumn_evidence.py',['pilot_games.csv','== 100','== 300','PILOT','itad_collection_manifest.csv']),
            changes_needed='Parameterize cohort/input/output namespace, reject duplicate keys, construct only historically eligible pairs, preserve A/B/C/D semantics and nullable labels; keep legacy pilot regression checks in their own fixtures. Missing/failed retrieval is a collection status, not an operational zero.'),
        features=dict(barriers=references('src/07_build_autumn_features.py',['== 100','== 300','100 / 100','pilot_games.csv','len(rows) == 300','Approved target counts differ']),
            changes_needed='Parameterize paths and expected cohort/pair counts; construct release-eligible pairs with same-day flags; validate labels/catalog/cache identities; keep exact 15-feature schema and strictly pre-cutoff observation selection.',
            missingness='Existing counts/flags distinguish no valid history; ratios, recencies and prices remain null. Preserve currency/conflict rules. Future preprocessing must fit only training data and explicitly retain/drop all-missing columns by a training-only rule.',
            cutoff='timestamp < exact UTC sale start. No carry-forward, interpolation, contemporary predictors or future observations.',
            performance='Current loader parses all game histories and keeps raw-record provenance in memory; three passes per game filter/sort history. For 5,000 games at three years, at most 15,000 pairs. Stream/chunk by game and bound provenance size after measuring actual records; no benchmark of expanded histories is possible here.',
            determinism='Sort AppIDs, game-year keys, timestamps and raw indices; preserve duplicates, tied conflicts, currencies and exact cutoffs. Freeze source/configuration hashes.'),
        modeling_handoff=dict(barriers=references('src/08_train_baseline_models.py',['== 200','== 100','== 300','nunique() == 100','Invalid operational labels','target count mismatch'])+
            references('src/09_train_ensemble_models.py',['100*len','nunique()==100','==100']),
            recommendation='A later authorized modeling phase needs cohort-aware expected counts and grouped chronological evaluation. Existing model wrappers reject null targets; ambiguous C labels and failed retrievals need a preregistered missing-target accounting policy, not relabeling or silent exclusion. Do not change or execute approved fitting scripts in this audit.'))


def evaluation_design():
    return dict(represented_games='Lock a new-sample development cohort before collection. Train on eligible 2023–2024 rows, evaluate its 2025 rows separately; pilot 2025 remains an examined diagnostic.',
        unseen_games='Within each new-sample release stratum, preassign AppIDs by an independent seed/hash to development versus sealed game-level holdout before collecting outcomes. Exclude EVERY holdout AppID from all training years; evaluate eligible 2025 holdout rows only.',
        tuning='Predefine training-only grouped/temporal resampling. No tuning on the examined pilot 2025 labels, new 2025 evaluation labels, missingness in evaluation, or importance computed on evaluation.',
        coverage='Report evaluation sizes and performance by pre-cutoff coverage flags/count bands fixed using development data. Separately report retrieval failure, empty response, ambiguity and date uncertainty; never select replacements for abundant histories or favorable targets.',
        pilot_vs_sample='Report pilot and probability-sample results separately; use new-sample stratum inclusion weights for its restricted sampling frame where justified. Do not pool the pilot as a probability sample.',
        confirmatory_feasibility='New held-out games have uninspected local outcomes, but the 2025 event and model choices have already informed methodology. A preregistered sealed cohort offers untouched game outcomes, not an entirely fresh event-level confirmatory test. A future unexamined sale could provide stronger confirmation only after separate authorization and verified dates/data; none are assumed here.',
        preprocessing='All imputation, scaling, feature-selection rules and calibration (if later authorized) fit exclusively on chronological development training; exact historical cutoffs preserved.',
        uncertainty='Cluster uncertainty calculations by AppID, account for sampling design and small coverage strata; no generalization to post-2023-release titles, permanent-free titles, missing snapshot entries or the full Steam catalog is established.')


def plotted_data(catalog, local, plan):
    return dict(release_years=catalog['release_year_distribution'],
        historical_coverage=dict(denominator=local['local_cohort_denominator'],
            before=[local['by_year'][str(y)]['before']['games_with_valid_price_records'] for y in (2023,2024,2025)],
            inside=[local['by_year'][str(y)]['inside']['games_with_temporal_records'] for y in (2023,2024,2025)],
            after=[local['by_year'][str(y)]['after']['games_with_temporal_records'] for y in (2023,2024,2025)]),
        sampling_composition={n:c['new_sample_by_stratum'] for n,c in plan['cohorts'].items()},
        funnel=dict(labels=['Master catalog','Before all three starts','Nonpilot sampling frame','Largest planned new cohort'],
            counts=[catalog['total_records'],catalog['definitely_before_all_three_start_dates'],plan['frame_nonpilot_games'],
                    plan['cohorts'][str(max(SIZES))]['new_probability_sample_games']]))


def generate_figures(out, data):
    directory = out/'reports/figures'; directory.mkdir(parents=True, exist_ok=True)
    with light_style():
        fig,ax=plt.subplots(); years=list(data['release_years']); ax.bar(years,list(data['release_years'].values()),color=BLUE)
        ax.set(title='Catalog release years',xlabel='Reported release year',ylabel='Games in cleaned catalog')
        ax.set_xticks(range(0,len(years),4)); ax.set_xticklabels(years[::4]); ax.grid(axis='y'); ax.set_axisbelow(True)
        save_figure(fig,directory/f'{FIGURES[0]}.png','Denominator: cleaned master catalog. Reported release dates; snapshot selection applies.')
        fig,ax=plt.subplots(); x=[0,1,2]; d=data['historical_coverage']
        for offset,key,label,color in [(-.24,'before','Valid prices before cutoff',BLUE),(0,'inside','Any record during sale',ORANGE),(.24,'after','Any record after sale',GRAY)]:
            ax.bar([i+offset for i in x],d[key],width=.23,label=label,color=color)
        ax.set_xticks(x); ax.set_xticklabels(['2023','2024','2025']); ax.set(ylim=(0,d['denominator']),xlabel='Sale year',ylabel=f"Games / {d['denominator']} cached pilot games",title='Observed local historical evidence')
        ax.set_title('Observed local historical evidence',pad=30)
        ax.grid(axis='y');ax.set_axisbelow(True);ax.legend(loc='lower left',bbox_to_anchor=(0,1.015),ncol=3,fontsize=7,handlelength=1.2,columnspacing=.8)
        save_figure(fig,directory/f'{FIGURES[1]}.png','Uncached catalog games: provider availability unknown. Records do not establish continuous coverage.')
        fig,ax=plt.subplots(); sizes=sorted(data['sampling_composition'],key=int); bottom=[0]*len(sizes)
        for s,color in zip(STRATA,[BLUE,ORANGE,GRAY,'#779584']):
            values=[data['sampling_composition'][n][s] for n in sizes]
            ax.bar(sizes,values,bottom=bottom,label=s.replace('_',' '),color=color)
            bottom=[a+b for a,b in zip(bottom,values)]
        ax.set(xlabel='Planned total cohort size (includes 100 pilot games)',ylabel='New probability-sample candidates',title='Nested sampling composition')
        ax.grid(axis='y');ax.set_axisbelow(True);ax.legend(fontsize=8)
        save_figure(fig,directory/f'{FIGURES[2]}.png','Bars exclude the separately identified 100-game pilot. Candidates are planning records, not collected games.')
        fig,ax=plt.subplots(); f=data['funnel']; ax.barh(f['labels'],f['counts'],color=[GRAY,BLUE,BLUE,ORANGE]);ax.invert_yaxis()
        ax.set(xlabel='Games',title='Historical sampling population'); ax.set_xlim(0,max(f['counts'])*1.16);ax.grid(axis='x');ax.set_axisbelow(True)
        for i,n in enumerate(f['counts']):ax.text(n+max(f['counts'])*.012,i,f'{n:,}',va='center',fontsize=9)
        save_figure(fig,directory/f'{FIGURES[3]}.png','Population restrictions and planned selection only. No historical evidence availability is implied.')
    return {f:dict(path=f'reports/figures/{f}.png',status='generated',dpi=300,mode='light',sha256=audit.digest(directory/f'{f}.png')) for f in FIGURES}


def sampling_report(plan):
    rows=[[n,c['pilot_games'],c['new_probability_sample_games']]+[c['new_sample_by_stratum'][s] for s in STRATA] for n,c in plan['cohorts'].items()]
    return f'''# Historical expansion sampling plan

This is a deterministic planning manifest, not a collected or labeled expanded dataset. Cohort sizes are totals including the original 100-game diagnostic pilot. The pilot is identified separately and has no probability-sample inclusion weight.

## Sampling frame and selection

Use the authoritative `data/intermediate/games_master.csv`. Exclude invalid/duplicate identifiers and inconsistent or missing release dates from planning eligibility. For the new balanced historical cohort, require reported release date strictly before every official 2023–2025 sale start date. The existing date-level eligibility rule remains release date <= start date; the stricter sampling rule avoids new release-on-start-day ambiguity without rewriting pilot rules. The pilot retains its one uncertain 2023 pair.

There are {plan['frame_nonpilot_games']:,} eligible nonpilot games. Stratify by reported release period: before 2015, 2015–2019, 2020–2022 and 2023 before sale. Game age is derivable from the same date and would be redundant as a second sampling dimension. Snapshot genre/publisher/OS fields exist but are mutable and are not used; snapshot price/owners/activity are excluded. The master itself was already selected by positive snapshot price, so selection bias persists.

Within each stratum sort SHA-256 priorities from UTF-8 `42|appid`, then integer AppID. Interleave strata by exact rational `(within_stratum_rank - 0.5) / stratum_population`, with deterministic ties by stratum, priority and AppID. Take prefixes of 400, 900, 1,900 and 4,900 new games. This gives approximately proportional release-stratum allocations and nested cohorts without future-label or coverage selection. For each size, the design inclusion fraction is `selected_in_stratum / frame_in_stratum`; those fractions are saved in JSON. They describe the pseudorandom design, not uncertainty about the fixed realized manifest.

{audit.md_table(['Total','Pilot','New']+STRATA,rows)}

## Manifest fields

`appid` is the normalized linkage identifier. `pilot_membership` is 0/1. `release_date` and `release_year` reproduce reported historical release information. `eligibility_2023/2024/2025` apply the existing date-only rule (blank if unknown); `release_hour_uncertain_*` flags equality with the start date. `sampling_stratum` identifies a release-period stratum or the outside/unknown frame. `sampling_priority` is the within-stratum SHA-256 priority for eligible nonpilot games; `probability_sample_rank` is the interleaved rank. Both are blank outside that frame and for pilot games. `selection_status` distinguishes pilot, selected expansion candidate, eligible reserve, uncertain start-day exclusion, later-release exclusion and invalid-release exclusion. `included_in_500/1000/2000/5000` are 0/1 planned cohort flags, including pilot membership.

The manifest contains all unique valid catalog AppIDs, with later releases explicitly outside the sampling frame. The pilot's same-start-day case uses the separate `pilot_start_day_uncertain` stratum. It contains no operational targets, inferred evidence categories, histories, matching-success claims or new feature vectors. Adding unavailable histories or changing future labels cannot change selection. No candidate is guaranteed to be labelable or modelable.

## Collection and nonresponse

Pre-collection variables are AppID, pilot membership and reported release dates/years. Coverage, matching success, empty histories, ambiguity and discount observations become known only after an approved collection. Keep failures and sparse/empty evidence in a collection-accounting ledger; do not replace them with high-coverage games. A failed/missing retrieval cannot be silently converted into an operational zero. Assess inclusion/nonresponse by release stratum before any population claim.

New post-2023-release titles require a separately defined later-entry cohort and eligible game-year panel in a future phase. This plan represents only the restricted balanced historical sampling frame, not all 99,194 catalog entries or the full Steam store.
'''


def feasibility_report(result):
    c,l,p,q=result['catalog'],result['local_evidence'],result['sampling'],result['collection']
    eligibility_rows=[[y]+[v[k] for k in ['before_start_date','on_start_date','eligible_by_existing_date_rule','interior_sale_dates','on_end_date','after_end_date']] for y,v in c['eligibility_by_year'].items()]
    evidence_rows=[[y]+[v[side]['games_with_temporal_records'] for side in ['before','inside','after']]+[v['before']['games_with_valid_price_records'],v['inside']['games_with_discount_records']] for y,v in l['by_year'].items()]
    workloads=[[n,v['uncached_candidates'],v['all_matched_no_retry_requests'],v['cold_start_all_matched_requests'],f"{v['pacing_floor_minutes_all_matched']:.1f}"] for n,v in q['workload'].items()]
    barriers=[]
    for group in ['labeling','features','modeling_handoff']:
        for ref in result['pipeline_readiness'][group]['barriers']:
            barriers.append(f"- `{ref['path']}:{ref['line']}`: `{ref['text']}`")
    return f'''# Historical data scaling feasibility

## Executive summary

The local catalog supports a deterministic candidate plan for totals of 500, 1,000, 2,000 and 5,000 games, with the original pilot reported separately. This establishes sampling feasibility, not historical coverage or a completed expanded dataset. Responsible collection feasibility is conditional on account quota, matching success, response completeness, timing provenance and changes to pilot-specific pipeline guards. No collection, new labels, feature generation or model fitting occurs in this audit.

## Master catalog audit

Authoritative catalog: `{MASTER}`, {c['total_records']:,} rows and {c['unique_valid_appids']:,} unique valid AppIDs. Missing IDs: {c['missing_appids']}; invalid IDs: {c['invalid_identifiers']}; duplicate excess rows: {c['duplicate_excess_rows']}. Missing release dates: {c['missing_release_dates']}; invalid dates: {c['invalid_release_dates']}; inconsistent release years: {c['release_year_mismatches']}.

The catalog is the cleaned positive-source-price population from the local metadata snapshot, not the complete Steam population. Unknown snapshot time, excluded zero-price products, delisted/missing titles, software/non-game products and corrected/early-access release interpretation limit representativeness. No contemporary metadata is approved as a historical predictor. The source-stage report describes 125,855 raw entries; this audit counts the authoritative cleaned master directly rather than treating that report as a new raw-source audit.

## Sale-year eligibility

Release dates are date-only. Use the existing official Pacific calendar dates and exact UTC observation boundaries from `src/autumn_sale_calendar.json`. No midnight release timestamp is invented. Existing eligibility includes a start-day release with uncertainty. End-day releases may be inside or after the 10 AM boundary; report them separately. Interior-date counts describe releases strictly between the boundary dates, not confirmed purchase availability.

{audit.md_table(['Year','Before start date','Start day uncertain','Date-rule eligible','Interior sale dates','End day uncertain','After end date'],eligibility_rows)}

Eligible for all three by the existing date rule: {c['eligible_all_three_date_rule']:,}. Strictly before all three starts: {c['definitely_before_all_three_start_dates']:,}. New sampling excludes start-day uncertainty; the separately retained pilot is unchanged. Date eligibility is not independent evidence of actual Steam sale participation or continuous availability.

## Existing historical evidence

All {l['local_cohort_denominator']} cached pilot games reconcile with the collection manifest and original response bodies. Local temporal records: {l['temporal_records']:,}; valid price records: {l['valid_price_records']:,}; discounted observations: {l['discounted_records']:,}. Games with any temporal records: {l['games_with_any_temporal_record']}; any valid price records: {l['games_with_any_valid_price_record']}; any qualifying discount observations: {l['games_with_any_discount_record']}; empty histories: {l['games_with_no_temporal_observations']}.

{audit.md_table(['Year','Any before','Any inside','Any after','Valid prices before','Discount inside'],evidence_rows)}

Every row above has denominator {l['local_cohort_denominator']} cached games. At catalog level only {l['catalog_games_with_local_cache']} / {l['catalog_denominator']:,} have local caches; {l['catalog_games_without_local_cache']:,} have no local cached evidence and unknown provider-side availability. Cached empty responses are distinct from uncollected games. Complete continuous capture remains unestablished for all 100 cached games. No interpolation, price continuity or discount campaign duration is inferred. Existing A/B/C/D categories reconcile with local observations, but no new operational labels are emitted. Recorded absence does not establish actual non-discounting.

Potential external evidence is limited to the existing provider lookup/history contract. Matching and historical availability for new games cannot be determined without separately authorized requests. No estimate transfers the pilot's 97% nonempty-history rate to the wider population.

## Collection feasibility

Provider: {q['provider']}. Endpoints: `{q['lookup_endpoint']}` and `{q['history_endpoint']}`; header authentication comes from `ITAD_API_KEY`. Scope remains US / Steam shop 61 / since 2021-01-01. {q['pagination']}

{q['recorded_quota']} {q['pacing']} {q['retries']}

{audit.md_table(['Planned total','New uncached','Requests, all matched','Cold start requests','Pacing floor, minutes'],workloads)}

The totals include 100 reusable pilot caches. New-game request formula: `U + q*U*H`, plus retries; mapping fractions 0.5, 0.8 and 1.0 and a hypothetical stricter quota scenario are saved in JSON. Current code assumes H=1, but provider-side limits or a future revised pagination contract could change that. At most three attempts per endpoint gives 6U requests in the all-matched worst-attempt scenario; authentication/rate-limit aborts can stop earlier. Pacing figures are request-start lower bounds, not wall-clock completion forecasts. Latency, 30-second timeouts, retries, quota and manual resume can dominate.

{q['caching']} {q['checkpoint_resume']} {q['response_size_constraints']}

Pilot cache wrappers total {l['cache_wrapper_bytes']['total']:,} bytes. They duplicate parsed history and original body. Storage scenarios in JSON use the observed nonrepresentative mean and are sensitivity calculations only; they are not a coverage or response-size forecast. The history request date boundary does not establish earlier history or contemporaneous availability; initialized boundary timestamps and backfills remain unresolved.

## Sampling strategy

{p['frame_nonpilot_games']:,} nonpilot games enter the restricted balanced historical frame. Use release-period strata, seed 42, within-stratum SHA-256 priorities and exact rational proportional interleaving to form nested cohorts. Totals include the separately identified 100-game pilot. Selection ignores discount outcomes, evidence abundance, matching success and contemporary snapshots. The [sampling plan](autumn_sale_sampling_plan.md) documents fields, allocations and inclusion fractions. The [candidate manifest](../data/intermediate/autumn_sale_scaling_candidates.csv) is planning only.

## Labeling pipeline readiness

The operational definition is reusable: A -> recorded discount (1); B/D -> no qualifying recorded discount (0); C -> null/review. None provides verified sale participation. Current labeling assumes the pilot input paths, 100 games, 300 rows and exact pilot category/target counts. Upstream auditing and collection likewise use pilot paths and a pilot-bound smoke gate. Parameterize cohort identity and output namespace, separate legacy regression checks, and validate historically eligible pairs before producing new labels. Keep failed/unmatched/missing collection statuses separate from operational negatives; do not fabricate negative labels for absent retrievals.

## Feature pipeline readiness

The unchanged 15-feature allowlist is verified against the Phase 6 manifest and source. The current feature builder requires 100 pilot/manifests, a complete 300-pair panel and exactly 175 positive / 125 negative labels; static features reject negative age. A later-entry panel needs eligibility-aware construction instead of every game in every year. Existing model wrappers reject null targets, while evidence category C correctly remains nullable. Future analysis needs an explicit missing-target/failed-retrieval accounting policy; do not recode ambiguity as zero or silently discard it to pass legacy guards. Date uncertainty, null history summaries, mixed currencies and latest-timestamp conflicts must retain existing semantics. Pricing inputs must remain strictly before exact UTC cutoffs; no snapshot price, reviews or activity enters historical predictors. Feature functions can be reused once paths/count checks are parameterized; feature definitions must not change.

At 5,000 games, a balanced three-year panel has at most 15,000 rows, but response/provenance size is unknown. Current all-history loading and repeated filter/sort operations can amplify memory; measure records and stream/chunk by game in Phase 8B. Do not extrapolate a latency or memory benchmark from uncollected games. Training-only missing-value handling belongs to later authorized modeling.

Concrete source barriers (line references to unchanged files):

{chr(10).join(barriers)}

Additional collector/upstream audit references are saved in JSON. No source barrier is repaired in Phase 8A.

## Generalization evaluation plan

Preassign new AppIDs to development and sealed game-level evaluation groups within release strata using an independent deterministic priority. For represented-game evaluation, train development games on eligible 2023–2024 rows and report their 2025 rows. For unseen-game evaluation, remove every held-out AppID from all training years, and evaluate only eligible 2025 rows for those games. Fit all preprocessing on development training only; choose configurations by training-only temporal/grouped resampling, never the examined pilot 2025 holdout.

Report pilot versus probability sample separately, and evaluate pre-cutoff coverage sensitivity using bins defined in development data. Account for retrieval failure, ambiguous labels and date uncertainty. Do not choose replacements or favorable targets after collection. Sampling weights apply only to the new restricted frame; repeated-game uncertainty should be clustered by AppID.

New held-out game outcomes could remain untouched if allocation and access controls are preregistered before collection. However, the 2025 event and model choices have already been inspected through the pilot. This can provide an untouched game-level evaluation, not a fully fresh event-level confirmatory test. Stronger confirmation requires a separately authorized unexamined event and verified dates/data. No 2026 dates, predictions or collection are created here.

## Risks and limitations

Provider matching/coverage, actual account quota, truncation limits, historical backfill, requested-since initialization, changing product availability, date revisions and early-access interpretation remain unresolved. Observation coverage may predict the operational labels. The catalog itself is snapshot-selected and includes some non-game products; the balanced frame excludes later releases. Increasing sample size alone does not fix these limitations or produce verified non-discounting labels.

## Recommended Phase 8B scope

Parameterize separate cohort-aware collection/evidence/label/feature namespaces and preserve the original pilot artifacts. Obtain explicit collection approval and confirm the account quota and current endpoint limits. Conduct a bounded smoke/coverage trial across release strata, retaining failures and empty histories. Assess retrieval sizes, timestamp provenance, ambiguity and nonresponse before approving 2,000–5,000 games. Freeze candidate and sealed evaluation memberships before outcomes are accessed. Bulk collection, model retraining, Phase 8B/8C and Phase 9 remain unstarted.

## Reproduction and visualizations

```bash
python3 -B src/10_audit_scaling_feasibility.py --verify
```

This command reads local files, executes only the Phase 8A offline tests (older model tests would retrain models), compares two complete audit executions and preserves all earlier artifacts. Four light-mode 300-DPI PNGs under `reports/figures/` show catalog release years, observed local evidence, planned sampling composition and the restricted population funnel. Every plotted value is stored in the feasibility JSON. Catalog and local-cache denominators are distinct; no chart portrays unknown external availability as observed absence.
'''


def run(root=ROOT, output_root=None, execution_checks=None):
    root=Path(root); out=Path(output_root or root)
    with coverage.offline_guard() as attempts:
        before=protected_hashes(root)
        windows=audit.canonical_windows(root)
        require(set(windows)=={2023,2024,2025}, 'Only approved historical events permitted')
        rows=read_catalog(root/MASTER); catalog=audit_catalog(rows,windows)
        require(catalog['total_records'] == catalog['unique_valid_appids'] and
                not any(catalog[k] for k in ['missing_appids','invalid_identifiers','duplicate_excess_rows',
                                           'missing_release_dates','invalid_release_dates','release_year_mismatches']),
                'Authoritative master integrity/schema inconsistency; no repair performed')
        pilot=features.read_table(root/PILOT,['AppID','release_date','release_year'])
        pilot_ids={int(r['AppID']) for r in pilot}
        require(len(pilot)==len(pilot_ids)==100, 'Original pilot identities inconsistent')
        catalog_dates={int(r['AppID']):(r['release_date'],r['release_year']) for r in rows}
        require(all(catalog_dates.get(int(r['AppID']))==(r['release_date'],r['release_year']) for r in pilot), 'Master/pilot releases disagree')
        candidates,plan=sample_candidates(rows,pilot_ids,windows)
        local=local_evidence(root,set(catalog_dates),pilot,windows)
        data=plotted_data(catalog,local,plan)
        result=dict(phase='8A',status='AUDIT_COMPLETE_SCALING_NOT_STARTED',catalog=catalog,local_evidence=local,
            sampling=plan,collection=collection_feasibility(local),pipeline_readiness=readiness(root),
            evaluation_design=evaluation_design(),plot_data=data,
            event_windows=read_json(root/'src/autumn_sale_calendar.json')['events'],
            scope='Offline feasibility only; no new histories/labels/features, collection, training, Phase 8B/8C or Phase 9.')
        for p in OUTPUTS: (out/p).parent.mkdir(parents=True,exist_ok=True)
        with (out/CANDIDATES).open('w',encoding='utf-8',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=FIELDS);writer.writeheader();writer.writerows(candidates)
        saved=features.read_table(out/CANDIDATES,FIELDS)
        require(len(saved)==len(candidates) and len({r['appid'] for r in saved})==len(saved), 'Candidate manifest identity failure')
        require(all(all(str(r[k])==s[k] for k in FIELDS) for r,s in zip(candidates,saved)), 'Candidate CSV round-trip mismatch')
        candidate_checks=validate_candidates(saved,plan,pilot_ids,windows)
        write_json(out/FEASIBILITY,result)
        (out/PLAN).write_text(sampling_report(plan),encoding='utf-8')
        (out/REPORT).write_text(feasibility_report(result),encoding='utf-8')
        figures=generate_figures(out,data)
        after=protected_hashes(root);require(before==after,'Completed artifact mutation detected')
        receipt=dict(phase='8A',status='PASS',catalog_schema='PASS',feature_allowlist='PASS',
            input_row_counts=dict(catalog=len(rows),pilot=len(pilot),existing_modeling_rows=result['pipeline_readiness']['existing_modeling_rows']),
            candidate_checks=candidate_checks,
            local_evidence_checks=dict(cache_provenance='PASS',saved_evidence_category_alignment='PASS',
                provider_side_coverage='NOT ESTABLISHED: offline audit only'),
            figures=figures,plotted_data=data,protected_before_sha256=before,protected_after_sha256=after,
            source_sha256={p:audit.digest(root/p) for p in SOURCE_FILES},
            output_sha256={p:audit.digest(out/p) for p in OUTPUTS if p!=VALIDATION},
            execution_checks=execution_checks or dict(offline_tests='NOT RUN: use --verify',determinism='NOT RUN: use --verify'),
            network_attempts=len(attempts),api_requests=0,models_fitted=0,new_history_records=0,
            versions=dict(python=platform.python_version()),
            unresolved_feasibility_risks=['Provider coverage/response limits and account quota unknown offline',
                'Historical completeness/backfill/initialization unestablished','Snapshot and sampling frame selection bias',
                'Date-only release/purchase availability uncertainty','Pilot-specific pipeline guards require a separately authorized change'])
        write_json(out/VALIDATION,receipt)
        return result,receipt


def verify_execution(root=ROOT):
    root=Path(root)
    before=protected_hashes(root)
    with coverage.offline_guard():
        stream=io.StringIO()
        suite=unittest.defaultTestLoader.discover(str(root/'tests'),pattern='test_scaling_feasibility.py')
        tested=unittest.TextTestRunner(stream=stream).run(suite)
        print(stream.getvalue(),end='');require(tested.wasSuccessful(),'Offline scaling tests failed')
        checks=dict(offline_tests='PASS',tests_run=tested.testsRun,failures=len(tested.failures),errors=len(tested.errors),
            skipped=len(tested.skipped),test_scope='Phase 8A only; model-fitting test suites deliberately not executed.')
        with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
            first=run(root,Path(a),checks);second=run(root,Path(b),checks)
            require(first==second,'Repeated audit structured outputs differ')
            identical={p:audit.digest(Path(a)/p)==audit.digest(Path(b)/p) for p in OUTPUTS}
            require(all(identical.values()),'Repeated audit bytes differ')
            checks.update(determinism='PASS: two complete isolated audit runs',structured_outputs_identical=True,
                candidate_manifest_bytes_identical=True,figure_bytes_identical=True,all_output_bytes_identical=True,
                artifact_byte_checks=identical,determinism_scope='Recorded environment; cross-platform font/PNG identity not guaranteed.')
        final=run(root,execution_checks=checks)
        require(protected_hashes(root)==before,'Audit changed completed artifacts')
        require(all(audit.digest(root/p)==h for p,h in final[1]['output_sha256'].items()),'Final output hashes disagree')
    print(f'Phase 8A verified: {tested.testsRun} tests; {final[0]["catalog"]["total_records"]:,} catalog games; no collection or model fitting. STOP before Phase 8B.')
    return final


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify',action='store_true')
    args=parser.parse_args()
    verify_execution() if args.verify else run()
