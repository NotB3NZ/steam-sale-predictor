"""Phase 6: local pre-cutoff features; no models or price-state reconstruction.

python3 -B src/07_build_autumn_features.py --verify
"""
import argparse
from collections import Counter
import csv
from datetime import date
import importlib.util
import io
import json
from pathlib import Path
import statistics
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('feature_coverage', ROOT / 'src/05_investigate_sale_coverage.py')
coverage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(coverage)
audit, require = coverage.audit, coverage.require
VERSION = 'pre_sale_observations_v1'
LABELS = 'data/intermediate/autumn_sale_operational_labels.csv'
PRIOR_RECEIPT = 'reports/autumn_sale_operational_label_validation.json'
FEATURES = 'data/intermediate/autumn_sale_features.csv'
MODELING = 'data/intermediate/autumn_sale_modeling_table.csv'
MANIFEST = 'reports/autumn_sale_feature_manifest.json'
AVAILABILITY = 'reports/autumn_sale_feature_availability.md'
RECEIPT = 'reports/autumn_sale_feature_validation.json'
OUTPUTS = (FEATURES, MODELING, MANIFEST, AVAILABILITY, RECEIPT)
STATIC = ('game_age_days', 'release_year', 'release_month', 'release_quarter')
PRICE = ('prior_price_record_count', 'prior_discount_count', 'prior_discount_rate',
         'days_since_last_price_record', 'days_since_last_discount', 'max_prior_discount_pct',
         'mean_prior_discount_pct', 'last_observed_price', 'last_observed_discount_pct',
         'has_prior_price_history', 'has_prior_discount_observation')
ALLOWLIST = STATIC + PRICE
IDENTIFIERS = ('appid', 'sale_year', 'prediction_cutoff_utc')
AUDIT_FIELDS = ('audit_release_hour_uncertain',)
FIELDS = IDENTIFIERS + ALLOWLIST + AUDIT_FIELDS
DEFINITIONS = {
    'game_age_days': 'Sale-start Pacific calendar date minus source-reported release date; date-resolution days.',
    'release_year': 'Year of the normalized source-reported release date.',
    'release_month': 'Month (1–12) of the normalized source-reported release date.',
    'release_quarter': 'Quarter (1–4) of the normalized source-reported release date.',
    'prior_price_record_count': 'Count of independently parser-valid pre-cutoff Steam price observations; duplicates retained.',
    'prior_discount_count': 'Count of qualifying discounted observations among prior_price_record_count; not campaigns.',
    'prior_discount_rate': 'prior_discount_count / prior_price_record_count; observation-level ratio, not discounted-day share.',
    'days_since_last_price_record': 'Elapsed UTC days since latest valid pre-cutoff price observation.',
    'days_since_last_discount': 'Elapsed UTC days since latest qualifying pre-cutoff discount observation.',
    'max_prior_discount_pct': 'Maximum explicit cut percentage among qualifying pre-cutoff discounts.',
    'mean_prior_discount_pct': 'Arithmetic mean explicit cut percentage among qualifying pre-cutoff discounts.',
    'last_observed_price': 'Amount at latest valid pre-cutoff observation, only with exclusively USD prior valid prices and no latest-timestamp conflict.',
    'last_observed_discount_pct': 'Explicit cut at latest valid pre-cutoff observation; null for conflicting latest timestamp.',
    'has_prior_price_history': '1 if at least one valid pre-cutoff price observation exists, otherwise 0.',
    'has_prior_discount_observation': '1 if at least one qualifying pre-cutoff discount observation exists, otherwise 0.',
}


def protected_hashes(root):
    """Verify the preceding receipt chain, including the prior receipt itself."""
    previous = json.loads((root / PRIOR_RECEIPT).read_text(encoding='utf-8'))
    expected = {}
    for group in ('protected_after_sha256', 'source_sha256', 'output_sha256'):
        for path, value in previous[group].items():
            require(path not in expected or expected[path] == value, 'Conflicting protected hashes')
            expected[path] = value
    actual = {}
    for path, value in sorted(expected.items()):
        require((root / path).is_file(), f'Missing protected input: {path}')
        actual[path] = audit.digest(root / path)
        require(actual[path] == value, f'Protected input changed: {path}')
    actual[PRIOR_RECEIPT] = audit.digest(root / PRIOR_RECEIPT)
    return actual


def source_hashes(root):
    paths = ['src/07_build_autumn_features.py'] + [str(p.relative_to(root)) for p in sorted((root / 'tests').glob('test_*.py'))]
    return {p: audit.digest(root / p) for p in paths}


def read_table(path, required):
    with path.open(encoding='utf-8', newline='') as stream:
        reader = csv.DictReader(stream)
        header = reader.fieldnames or []
        require(len(header) == len(set(header)) and set(required) <= set(header), f'Invalid CSV schema: {path}')
        rows = list(reader)
    require(all(None not in r and all(v is not None for v in r.values()) for r in rows), f'Malformed CSV row: {path}')
    return rows


def identifier(value):
    require(isinstance(value, str) and value.isascii() and value.isdecimal() and str(int(value)) == value and int(value) > 0,
            f'Invalid positive identifier: {value!r}')
    return int(value)


def authorized_pairs(label_rows, windows):
    """Project identities/cutoffs only. Targets and all evidence fields are ignored."""
    pairs = []
    for row in label_rows:
        appid, year = identifier(row['appid']), identifier(row['sale_year'])
        require(year in windows, f'Unsupported sale year: {year}')
        require(row['sale_start_utc'] == audit.fmt(windows[year][2]), f'Exact cutoff mismatch: {appid}/{year}')
        pairs.append((appid, year))
    require(len(pairs) == len(set(pairs)), 'Duplicate appid/sale_year pairs')
    return sorted(pairs)


def static_features(release_value, window):
    release = date.fromisoformat(release_value)
    require(release.isoformat() == release_value, 'Release date must be normalized YYYY-MM-DD')
    start_date = date.fromisoformat(window[0])
    require(release <= start_date, 'Negative game age / release after sale start date')
    return dict(game_age_days=(start_date - release).days, release_year=release.year,
                release_month=release.month, release_quarter=(release.month - 1) // 3 + 1,
                audit_release_hour_uncertain=int(release == start_date))


def price_features(records, cutoff):
    """Only pre-cutoff Steam observations influence any feature or pair diagnostic.

    Ambiguous deals are not price-usable. Same-time valid observations remain
    separate observations; conflicting latest values are never chosen arbitrarily.
    Latest valid price is an observation, not an assertion about price at cutoff.
    """
    prior = sorted([r for r in records if r['shop_id'] == 61 and audit.utc_stamp(r['timestamp_utc']) < cutoff],
                   key=lambda r: (audit.utc_stamp(r['timestamp_utc']), r['source_record_index']))
    valid = [r for r in prior if r['observation_kind'] in ('discount', 'full_price')]
    discounts = [r for r in valid if r['observation_kind'] == 'discount']
    row = dict.fromkeys(PRICE, None)
    row.update(prior_price_record_count=len(valid), prior_discount_count=len(discounts),
               has_prior_price_history=int(bool(valid)), has_prior_discount_observation=int(bool(discounts)))
    currencies = sorted({r['price_currency'] for r in valid})
    latest = [r for r in valid if r['timestamp_utc'] == valid[-1]['timestamp_utc']] if valid else []
    conflict = bool(coverage.conflicts(latest))
    money_issue = ('no_valid_prior_price' if not valid else 'mixed_prior_currencies' if len(currencies) > 1 else
                   'non_USD_prior_currency' if currencies != ['USD'] else 'conflicting_latest_timestamp' if conflict else '')
    if valid:
        row['prior_discount_rate'] = len(discounts) / len(valid)
        row['days_since_last_price_record'] = (cutoff - audit.utc_stamp(valid[-1]['timestamp_utc'])).total_seconds() / 86400
        if not conflict:
            row['last_observed_discount_pct'] = latest[0]['cut']
            if not money_issue:
                row['last_observed_price'] = latest[0]['price']
    if discounts:
        row.update(days_since_last_discount=(cutoff - audit.utc_stamp(discounts[-1]['timestamp_utc'])).total_seconds() / 86400,
                   max_prior_discount_pct=max(r['cut'] for r in discounts),
                   mean_prior_discount_pct=statistics.mean(r['cut'] for r in discounts))
    diagnostics = dict(valid_prior_raw_indices=[r['source_record_index'] for r in valid],
                       ambiguous_prior_raw_indices=[r['source_record_index'] for r in prior if r['observation_kind'] == 'ambiguous'],
                       discount_prior_raw_indices=[r['source_record_index'] for r in discounts],
                       latest_valid_prior_timestamp=valid[-1]['timestamp_utc'] if valid else None,
                       latest_discount_prior_timestamp=discounts[-1]['timestamp_utc'] if discounts else None,
                       latest_valid_raw_indices=[r['source_record_index'] for r in latest],
                       pre_cutoff_ambiguous_count=len(prior) - len(valid),
                       pre_cutoff_null_deal_count=sum(r['deal_status'] == 'null' for r in prior),
                       pre_cutoff_conflicting_timestamp_groups=len(coverage.conflicts(prior)),
                       latest_valid_timestamp_conflict=conflict, prior_currencies=currencies,
                       monetary_missing_reason=money_issue,
                       cutoff_violations=sum(audit.utc_stamp(r['timestamp_utc']) >= cutoff for r in valid))
    return row, diagnostics


def build_features(pairs, games, histories, windows):
    rows, provenance = [], []
    require(len(pairs) == len(set(pairs)), 'Duplicate appid/sale_year pairs')
    for appid, year in sorted(pairs):
        require(year in windows, f'Unsupported sale year: {year}')
        require(appid in games and appid in histories, f'Missing game/history: {appid}')
        window = windows[year]
        pricing, diagnostic = price_features(histories[appid], window[2])
        row = dict(appid=appid, sale_year=year, prediction_cutoff_utc=audit.fmt(window[2]))
        row.update(static_features(games[appid]['release_date'], window))
        row.update(pricing)
        rows.append({f: row[f] for f in FIELDS})
        selected = set(diagnostic['valid_prior_raw_indices'])
        valid_prior = [r for r in histories[appid] if r['source_record_index'] in selected]
        diagnostic.update(valid_prior_observations_before_reported_release_date=sum(
            r['timestamp_utc'][:10] < games[appid]['release_date'] for r in valid_prior),
            valid_prior_observations_at_requested_since=sum(r['timestamp_utc'] == '2021-01-01T00:00:00Z' for r in valid_prior))
        provenance.append(dict(appid=appid, sale_year=year, **diagnostic))
    return rows, provenance


def modeling_table(features, labels, windows):
    pairs = authorized_pairs(labels, windows)
    require(set(pairs) == {(r['appid'], r['sale_year']) for r in features}, 'Target join keys differ')
    targets = {}
    for r in labels:
        require(r['discount_observed'] in ('0', '1', ''), 'Invalid operational target')
        targets[(identifier(r['appid']), identifier(r['sale_year']))] = int(r['discount_observed']) if r['discount_observed'] else None
    return [dict(r, discount_observed=targets[(r['appid'], r['sale_year'])]) for r in features]


def feature_manifest():
    entries = []
    missing = {
        'prior_price_record_count': 'Never null; zero means no parser-valid pre-cutoff price observations.',
        'prior_discount_count': 'Never null; zero means no qualifying pre-cutoff discount observations.',
        'has_prior_price_history': 'Never null; zero denotes no valid pre-cutoff price observations, not full-history emptiness.',
        'has_prior_discount_observation': 'Never null; zero denotes no recorded qualifying pre-cutoff discount, not proof of no discount.',
        'prior_discount_rate': 'Null when no valid prior price observations; zero if prices exist but no discounts were observed.',
        'days_since_last_price_record': 'Null when no valid prior price observation; never zero-filled.',
        'days_since_last_discount': 'Null when no qualifying prior discount observation; never zero-filled.',
        'max_prior_discount_pct': 'Null when no qualifying prior discount observation.',
        'mean_prior_discount_pct': 'Null when no qualifying prior discount observation.',
        'last_observed_price': 'Null for no valid prior price, mixed/non-USD prior currencies, or conflicting latest timestamp.',
        'last_observed_discount_pct': 'Null for no valid prior price or conflicting latest timestamp.',
    }
    for name in FIELDS:
        static = name in STATIC
        numeric_type = 'integer' if name in STATIC or name in ('appid', 'sale_year', *AUDIT_FIELDS,
                        'prior_price_record_count', 'prior_discount_count', 'has_prior_price_history', 'has_prior_discount_observation') else 'number'
        administrative = {'appid': 'Stable Steam AppID; row linkage only.', 'sale_year': 'Authorized Autumn Sale year; split/identity only.',
                          'prediction_cutoff_utc': 'Verified official sale start in UTC; all price inputs must precede it.',
                          'audit_release_hour_uncertain': '1 if reported release date equals sale-start Pacific date; release hour unknown. Audit only.'}
        entries.append(dict(feature_name=name, definition=DEFINITIONS.get(name, administrative.get(name)),
                            source='normalized pilot release_date (master cross-checked)' if static or name in AUDIT_FIELDS else
                            'cached ITAD Steam shop 61 / US; shared Phase 5A.1 parser' if name in PRICE else 'authorized pair identity / verified event calendar',
                            type='UTC datetime string' if name == 'prediction_cutoff_utc' else numeric_type,
                            missing_value_meaning=missing.get(name, 'Not permitted to be missing.'),
                            historical_availability_justification='Phase 2 classifies release date as historically derivable; assume the reported date accurately describes release. No release hour or retrospective metadata revisions established.' if static else
                            'Strict observation_timestamp < sale start; no state propagation. Retrospective provider backfill/initialization remains unverified.' if name in PRICE else 'Identity/calendar or date-level eligibility audit, excluded from predictors.',
                            baseline_allowlist=name in ALLOWLIST,
                            leakage_risk='Conditional on source release-date accuracy/stability.' if static else
                            'Future timestamps excluded; historical provider availability not proven.' if name in PRICE else 'Excluded from baseline predictors.',
                            feature_generation_version=VERSION))
    return dict(feature_generation_version=VERSION, baseline_feature_allowlist=list(ALLOWLIST),
                identifier_columns=list(IDENTIFIERS), audit_only_columns=list(AUDIT_FIELDS),
                target_column='discount_observed', target_in_feature_only_csv=False,
                monetary_unit='USD only; no conversion or mixed-currency monetary aggregation',
                missing_csv_representation='blank cells; JSON null in validation', features=entries)


def availability_report(root, rows, stats):
    header = read_table(root / 'data/intermediate/pilot_games.csv', ['AppID'])[0].keys()
    meanings = {'AppID': 'Steam application identity', 'Name': 'Human-readable product title',
                'release_date': 'Reported release calendar date', 'release_year': 'Derived reported release year',
                'Estimated owners': 'Snapshot estimated ownership range', 'Peak CCU': 'Snapshot lifetime peak concurrent players',
                'Required age': 'Snapshot age restriction', 'Price': 'Contemporary store price; not historical base price',
                'Discount': 'Contemporary discount; not historical target', 'DLC count': 'Snapshot DLC catalog size',
                'Supported languages': 'Snapshot supported languages', 'Full audio languages': 'Snapshot audio languages',
                'Windows': 'Snapshot platform support', 'Mac': 'Snapshot platform support', 'Linux': 'Snapshot platform support',
                'Metacritic score': 'Snapshot critic score', 'User score': 'Snapshot user score',
                'Positive': 'Accumulated positive reviews', 'Negative': 'Accumulated negative reviews',
                'Achievements': 'Snapshot achievement count', 'Recommendations': 'Accumulated recommendations',
                'Developers': 'Current developer attribution', 'Publishers': 'Current publisher attribution',
                'Categories': 'Current store categories', 'Genres': 'Current genre attribution', 'Tags': 'Current user/store tags'}
    candidates = []
    for field in header:
        if field in ('AppID', 'Name'):
            cls, decision, reason = 'A: identity', 'exclude from predictors', 'Row linkage only; titles/IDs do not establish historical characteristics.'
        elif field in ('release_date', 'release_year'):
            cls, decision, reason = 'A: historical date fact (conditional)', 'include derived date features', 'Phase 2 historically derivable classification; source accuracy/stability assumed, hours absent. Master/pilot date equality checked.'
        else:
            cls, decision, reason = 'C: undated snapshot', 'exclude', 'No timestamped historical snapshot; metadata may change after prediction. Pilot sampling diagnostics additionally reflect selection using snapshots.'
        meaning = meanings.get(field, 'Sampling diagnostic; not a predictor' if field.startswith('pilot_') else 'Snapshot playtime statistic in minutes')
        candidates.append([field, meaning, 'master / pilot metadata', cls, decision, reason])
    for field in ('timestamp', 'shop.id', 'deal.price.amount / currency', 'deal.regular.amount / currency', 'deal.cut', 'deal=null / ambiguous'):
        candidates.append([field, 'Observed historical time, storefront or price/deal field', 'cached ITAD history', 'B: timestamp filtering', 'conditional', 'UTC timestamp strictly before cutoff; shop 61; shared parser price/regular/cut/currency validity. Null/ambiguous deals excluded from price statistics and retained in validation.'])
    for field in ('discount_observed', 'evidence_category', 'pu_status', 'in-window counts / supporting indices',
                  'post-sale records / coverage diagnostics', 'future verification / full-history empty flags', 'label limitation / review flags', '2026 outcomes'):
        candidates.append([field, 'Outcome or retrospective diagnostic', 'labels / previous evidence artifacts', 'D: prohibited predictor', 'exclude', 'Outcome/future/collection-derived information; labels supply pair identities and a separate target join only.'])
    candidates.append(['current concurrent player count', 'Current activity; distinct from lifetime Peak CCU', 'not present as a separate source field',
                       'C: unavailable historical snapshot', 'exclude', 'No historical snapshot is available; never substitute current or peak activity.'])
    lines = ['# Phase 6 — Historical Feature Availability', '',
             '**Completed feature engineering; human review required before Phase 7. No model or predictive performance was produced.**', '',
             '## Availability audit', '',
             'A denotes static/historical information; B requires strict timestamp filtering; C is unavailable or potentially contaminated; D is target-derived or prohibited. Source-snapshot time is unknown. The Phase 2 report classifies release dates as historically derivable while explicitly retaining a source-accuracy assumption. Only date-derived metadata is admitted; other relatively stable metadata is excluded. Earlier Phase 1 suggestions that snapshot prices/DLC/tags are safe are superseded by this audit.', '',
             audit.md_table(['Candidate', 'Meaning', 'Source', 'Availability / risk', 'Decision', 'Reason'], candidates), '',
             '## Prediction cutoffs', '',
             audit.md_table(['Year', 'Strict upper bound UTC'], [[y, audit.fmt(w[2])] for y, w in audit.canonical_windows(root).items()]), '',
             'Only `observation_timestamp < prediction_cutoff_utc` enters any pricing calculation. Exact cutoff, current-sale, post-sale and future-year observations are excluded. Prior years\' sale observations are legitimate past observations. No 2026 outcome information is used.', '',
             '## Included definitions and allowlist', '',
             audit.md_table(['Feature', 'Definition'], [[f, DEFINITIONS[f]] for f in ALLOWLIST]), '',
             'The explicit 15-feature baseline allowlist is stored in [the manifest](autumn_sale_feature_manifest.json). AppID, sale year, cutoff and `audit_release_hour_uncertain` are excluded. The audit flag preserves same-day uncertainty without copying target-derived review/eligibility flags. All 300 rows remain. nekowater (2650840), 2023, has date-resolution age zero and unknown release hour; no midnight release time is invented.', '',
             'Release date is used as a reported historical fact, conditional on the existing source being accurate and stable. Age subtracts dates in the event calendar\'s Pacific timezone and is not an exact elapsed release-time duration. Release-date corrections, early-access/full-release interpretation and continuous purchase availability remain unverified.', '',
             '## Observation validity, currency and conflicts', '',
             'A valid price observation has the unchanged parser\'s `discount` or `full_price` kind. This requires finite nonnegative price/regular amounts, valid matching three-letter currencies, finite cut in [0,100], and consistent price/regular/cut direction. Discount means cut > 0 and price < regular. Ambiguous/null deals are temporal evidence but do not enter the price denominator. Their pre-cutoff indices/conflict diagnostics remain in the validation receipt.', '',
             'All current cached price/regular currencies are USD. `last_observed_price` is emitted only when all valid prior currencies are USD and latest-timestamp values do not conflict. Mixed/non-USD monetary values are withheld, with reasons in validation; no conversion is performed. Cut is dimensionless and validated within each record\'s matching currency pair, so cut statistics may combine valid percentages across currencies without comparing money amounts.', '',
             'Duplicates and independently valid conflicting records are counted separately as observations. They are not unique discount campaigns. Max/mean cut describe the returned observation multiset, not verified states or campaign prevalence. A conflict at the latest valid timestamp makes last price/cut null; all tied raw indices remain inspectable. A newer ambiguous temporal observation does not erase an older valid observation: recency refers explicitly to the latest valid price, not a carried-forward price at cutoff.', '',
             '## Missingness and distribution audit', '',
             'No valid prior prices gives zero counts/flags, with ratio, recencies and values missing. Valid prices without a qualifying discount give ratio zero, missing discount recency/max/mean, and discount flag zero. Missing recency is never zero-filled. CSV nulls are blank; JSON uses null.', '',
             audit.md_table(['Feature', 'Missing', 'Min', 'Median', 'Max'], [[f, s['missing'], s['min'], s['median'], s['max']] for f, s in stats['feature_statistics'].items()]), '',
             f"Rows: **{len(rows)}**; year counts: **100 / 100 / 100**. Currency conflicts: **{stats['currency_conflict_pair_count']}**; uncertain release-hour pairs: **{stats['uncertain_release_hour_count']}**. Constant baseline features: **{', '.join(stats['constant_features']) or 'none'}**. Unusual values are retained; no target-based feature selection is performed.", '',
             '## Historical availability limitations', '',
             'Filtering retrospective observation timestamps prevents direct temporal leakage but does not prove records were available from ITAD at that historical instant. Backfill and initial requested-since records remain unresolved. Observation counts, recency and flags describe the returned pre-cutoff evidence, not complete history, uninterrupted price states or true discount frequency. They may predict recording coverage as well as discount behavior. Sampling used undated snapshot information, so population selection bias persists even though those fields are excluded from predictors.', '',
             f"**Observed alignment caveats:** {stats['pairs_with_observations_before_reported_release_date']} pairs across {stats['games_with_observations_before_reported_release_date']} games contain valid pre-cutoff observations whose UTC calendar date precedes the source-reported release date. The six games are Evil Genius 2 (700600), CryoFall (829590), New World: Aeternum (1063730), The Great Ace Attorney Chronicles (1158850), Have a Nice Death (1740720), and Workplace Fantasy (2544720). Earlier access, preorders, release-date interpretation, backfill or source errors are possible explanations, not established facts. These records satisfy the existing parser and are retained with explicit diagnostics; neither source is silently corrected. Separately, {stats['pairs_with_requested_since_observations']} pairs contain observations at the exact 2021-01-01 request boundary ({stats['requested_since_unique_record_count']} records across {stats['games_with_requested_since_observations']} cached games, repeated across sale-year feature sets). An initialized timestamp is possible; true contemporaneous availability remains unverified.", '',
             'Extremes in the distribution table are retained, including very old price/discount gaps, zero observed prices and 100% cuts. These are returned-record summaries, not imputed daily states. No unusual value is removed.', '',
             'The operational target remains recorded discount occurrence, not independently verified participation. Pre-cutoff histories and static dates calculate features independently of the target; targets are joined only afterward. [Features](../data/intermediate/autumn_sale_features.csv) omit targets, categories and PU status. [Modeling table](../data/intermediate/autumn_sale_modeling_table.csv) adds only `discount_observed`. Future modeling must use the manifest allowlist, handle missing values with training-only preprocessing, train on 2023–2024 and reserve 2025 for temporal validation; repeated games across years and uncertain eligibility need transparent treatment.', '',
             '## Reproduction and stop gate', '',
             '```bash', 'python3 -B src/07_build_autumn_features.py --verify', '```', '',
             'Standard library only, local cached inputs, no credentials. Socket/DNS access is blocked. Verification runs the full offline test suite, adversarial future/target invariance tests, protected-input hashes and repeated byte-identical outputs. [Validation receipt](autumn_sale_feature_validation.json) records actual execution results and pre-cutoff raw-index provenance. Earlier artifacts are never regenerated. Stop before Phase 7; no imputation, scaling, encoding, training or evaluation is implemented.', '']
    return '\n'.join(lines)


def feature_statistics(rows):
    stats = {}
    for f in ALLOWLIST:
        values = [r[f] for r in rows if r[f] is not None]
        stats[f] = dict(missing=len(rows) - len(values), min=min(values) if values else None,
                        median=statistics.median(values) if values else None, max=max(values) if values else None,
                        distinct_nonmissing=len(set(values)))
    return stats


def run(root=ROOT, execution_checks=None):
    root = Path(root)
    with coverage.offline_guard() as attempts:
        before = protected_hashes(root)
        frozen = audit.frozen_hashes(root)
        windows = audit.canonical_windows(root)
        labels = read_table(root / LABELS, ['appid', 'sale_year', 'sale_start_utc', 'discount_observed'])
        pairs = authorized_pairs(labels, windows)
        pilot = read_table(root / 'data/intermediate/pilot_games.csv', ['AppID', 'release_date', 'release_year'])
        games = {identifier(r['AppID']): {'AppID': r['AppID'], 'release_date': r['release_date']} for r in pilot}
        require(len(pilot) == len(games) == 100 and set(pairs) == {(a, y) for a in games for y in windows}, 'Expected original 100 games / 300 pairs')
        with (root / 'data/intermediate/games_master.csv').open(encoding='utf-8', newline='') as stream:
            reader = csv.DictReader(stream)
            require({'AppID', 'release_date', 'release_year'} <= set(reader.fieldnames or []), 'Invalid master schema')
            master_dates = {int(r['AppID']): (r['release_date'], r['release_year']) for r in reader if int(r['AppID']) in games}
        for r in pilot:
            require(master_dates[identifier(r['AppID'])] == (r['release_date'], r['release_year']) and
                    str(date.fromisoformat(r['release_date']).year) == r['release_year'], 'Master/pilot release-date mismatch')
        manifests = read_table(root / 'data/intermediate/itad_collection_manifest.csv', ['AppID', 'Name', 'itad_game_id'])
        manifest = {identifier(r['AppID']): r for r in manifests}
        require(len(manifest) == len(manifests) == 100 and set(manifest) == set(games), 'Manifest identities differ')
        histories = {}
        for appid, game in sorted(games.items()):
            records, info = audit.load_cache(root, game, manifest[appid])
            require(info['cache_status'] == 'ok', f'Malformed cache: {appid}: {info}')
            histories[appid] = records
        rows, provenance = build_features(pairs, games, histories, windows)
        model = modeling_table(rows, labels, windows)
        require(Counter(r['discount_observed'] for r in model) == {1: 175, 0: 125}, 'Approved target counts differ')
        statistics_by_feature = feature_statistics(rows)
        invalid = [dict(appid=r['appid'], sale_year=r['sale_year'], feature=f, value=r[f]) for r in rows for f in ALLOWLIST
                   if r[f] is not None and (not audit.number(r[f]) or r[f] < 0 or
                   (f in ('max_prior_discount_pct', 'mean_prior_discount_pct', 'last_observed_discount_pct') and r[f] > 100) or
                   (f in ('prior_discount_rate', 'has_prior_price_history', 'has_prior_discount_observation') and r[f] > 1))]
        stats = dict(total_rows=len(rows), unique_games=len(games), year_counts=dict(Counter(str(r['sale_year']) for r in rows)),
                     feature_list=list(ALLOWLIST), feature_statistics=statistics_by_feature,
                     feature_missingness={f: s['missing'] for f, s in statistics_by_feature.items()},
                     constant_features=[f for f, s in statistics_by_feature.items() if s['distinct_nonmissing'] <= 1],
                     invalid_values=invalid, duplicate_count=len(rows) - len(set(pairs)),
                     cutoff_violations=sum(p['cutoff_violations'] for p in provenance),
                     currency_conflict_pair_count=sum(len(p['prior_currencies']) > 1 for p in provenance),
                     monetary_withheld_pair_count=sum(bool(p['monetary_missing_reason']) and p['monetary_missing_reason'] != 'no_valid_prior_price' for p in provenance),
                     uncertain_release_hour_count=sum(r['audit_release_hour_uncertain'] for r in rows),
                     pairs_with_prior_timestamp_conflicts=sum(bool(p['pre_cutoff_conflicting_timestamp_groups']) for p in provenance),
                     latest_valid_timestamp_conflict_pairs=sum(p['latest_valid_timestamp_conflict'] for p in provenance))
        stats.update(pairs_with_observations_before_reported_release_date=sum(bool(p['valid_prior_observations_before_reported_release_date']) for p in provenance),
                     games_with_observations_before_reported_release_date=len({p['appid'] for p in provenance if p['valid_prior_observations_before_reported_release_date']}),
                     pairs_with_requested_since_observations=sum(bool(p['valid_prior_observations_at_requested_since']) for p in provenance),
                     games_with_requested_since_observations=len({p['appid'] for p in provenance if p['valid_prior_observations_at_requested_since']}),
                     requested_since_unique_record_count=sum(p['valid_prior_observations_at_requested_since'] for p in provenance if p['sale_year'] == min(windows)))
        require(not invalid and stats['cutoff_violations'] == 0 and stats['duplicate_count'] == 0, 'Feature validation failed')
        require(stats['uncertain_release_hour_count'] == 1, 'Expected preserved release-hour uncertainty')
        sources = source_hashes(root)
        if execution_checks is None:
            old = json.loads((root / RECEIPT).read_text()) if (root / RECEIPT).exists() else {}
            execution_checks = old.get('execution_checks', {})
            if execution_checks.get('source_sha256') != sources or execution_checks.get('protected_sha256') != before:
                execution_checks = dict(full_offline_test_suite='NOT RUN: use --verify', deterministic_full_runs='NOT RUN: use --verify',
                                        source_sha256=sources, protected_sha256=before)
        require(execution_checks['source_sha256'] == sources and execution_checks['protected_sha256'] == before, 'Verification fingerprint mismatch')
        for path, values, fields in ((FEATURES, rows, FIELDS), (MODELING, model, FIELDS + ('discount_observed',))):
            audit.write_csv(root / path, values, fields)
            expected = [{k: '' if v is None else str(v) for k, v in r.items()} for r in values]
            require(audit.read_csv(root / path) == expected, f'CSV round-trip mismatch: {path}')
        (root / MANIFEST).write_text(json.dumps(feature_manifest(), sort_keys=True, indent=2) + '\n', encoding='utf-8')
        (root / AVAILABILITY).write_text(availability_report(root, rows, stats), encoding='utf-8')
        receipt = dict(phase='6', feature_generation_version=VERSION, script_execution_status='PASS', **stats,
                       execution_checks=execution_checks, pair_pre_cutoff_provenance=provenance,
                       checks=dict(feature_only_contains_no_target=True, explicit_allowlist=True, target_independent_calculation=True,
                                   dates_cross_checked_with_master=True, no_2026_rows=True, no_interpolation_or_forward_fill=True,
                                   saved_csv_round_trip=True, network_attempts=len(attempts), api_requests=0, models_trained=0),
                       frozen_phase4_before_sha256=frozen, frozen_phase4_after_sha256=audit.frozen_hashes(root),
                       protected_before_sha256=before, protected_after_sha256=protected_hashes(root), source_sha256=sources,
                       output_sha256={p: audit.digest(root / p) for p in OUTPUTS if p != RECEIPT})
        (root / RECEIPT).write_text(json.dumps(receipt, sort_keys=True, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        require(before == protected_hashes(root) and frozen == audit.frozen_hashes(root), 'Protected inputs changed')
    return rows, model, receipt


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
        require(first == {p: (root / p).read_bytes() for p in OUTPUTS}, 'Repeated outputs differ')
        checks['deterministic_full_runs'] = 'PASS: all five outputs byte-identical in two full executions'
        run(root, checks)
        final = {p: (root / p).read_bytes() for p in OUTPUTS}
        output = run(root, checks)
        require(final == {p: (root / p).read_bytes() for p in OUTPUTS}, 'Verified reruns differ')
        require(before == protected_hashes(root), 'Protected inputs changed during tests/reruns')
    print(f'Phase 6 PASS: {len(output[0])} rows, {len(ALLOWLIST)} allowed features; stop before Phase 7.')
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true', help='Run offline tests and verify deterministic executions')
    args = parser.parse_args()
    verify_execution() if args.verify else run()
