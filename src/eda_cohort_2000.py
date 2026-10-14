"""Phase 8D: accessible retrospective EDA of frozen historical data, offline."""
import argparse
from collections import Counter
import csv
from importlib import metadata
import json
import os
from pathlib import Path
import sys
import tempfile

from cohort_io import ROOT, digest, module, read_json, require
import visualize_cohort_2026 as io

MODEL = ROOT / 'reports/cohort_2000_modeling'
EVIDENCE = ROOT / 'reports/cohort_2000_labelability'
COHORT = ROOT / 'data/cohorts/cohort_2000.csv'
YEARS = [2023, 2024, 2025]
GROUPS = ['0', '1-9', '10-29', '30+']
DISPLAY = ['0', '1–9', '10–29', '30+']
BLUE, GRAY = '#527D9D', '#88939D'
FEATURE_NAMES = {
    'game_age_days': 'Game age (days)', 'release_year': 'Release year',
    'release_month': 'Release month', 'release_quarter': 'Release quarter',
    'prior_price_record_count': 'Earlier price observation count',
    'prior_discount_count': 'Earlier discount observation count',
    'prior_discount_rate': 'Earlier discount observation share',
    'days_since_last_price_record': 'Days since last price observation',
    'days_since_last_discount': 'Days since last discount',
    'max_prior_discount_pct': 'Largest earlier discount (%)',
    'mean_prior_discount_pct': 'Average earlier discount (%)',
    'last_observed_price': 'Last recorded price (USD)',
    'last_observed_discount_pct': 'Last recorded discount (%)',
    'has_prior_price_history': 'Any earlier price history',
    'has_prior_discount_observation': 'Any earlier discount observation',
}
NOTICE = 'Retrospective descriptive EDA conducted after model development.'


def histogram(values, edges, np, pd):
    require(len(values) > 0 and np.isfinite(values).all(), 'Invalid histogram values')
    counts, edges = np.histogram(values, bins=edges)
    require(int(counts.sum()) == len(values), 'Histogram loses observations')
    return pd.DataFrame(dict(lower_inclusive=edges[:-1], upper=edges[1:],
                             upper_inclusive=[False] * (len(counts) - 1) + [True], count=counts))


def validate_modeling(cohort, frame, manifest, windows):
    require(len(cohort) == 2000 and cohort.AppID.is_unique, 'Exactly 2,000 unique cohort games required')
    ids = set(cohort.AppID)
    require(len(frame) == 6000 and not frame.duplicated(['appid', 'sale_year']).any(), 'Invalid game-year keys')
    require(set(frame.sale_year) == set(YEARS), 'Historical year assignment mismatch')
    require(list(frame.columns) == manifest['dataset_fields'], 'Frozen modeling schema mismatch')
    require(frame.discount_observed.isin([0, 1]).all() and frame.evidence_category.isin(['A', 'B', 'D']).all(), 'Invalid operational label')
    require(frame.discount_observed.eq(frame.evidence_category.eq('A').astype(int)).all(), 'Frozen label/category mismatch')
    release = cohort.set_index('AppID').release_year
    for year in YEARS:
        group = frame[frame.sale_year.eq(year)]
        require(len(group) == 2000 and set(group.appid) == ids, 'Historical cohort membership mismatch')
        require(group.prediction_cutoff_utc.eq(windows[str(year)]['start_inclusive']).all(), 'Historical cutoff mismatch')
        require(group.release_year.eq(group.appid.map(release)).all(), 'Release year disagreement')
    io.coverage_groups(frame.prior_price_record_count)


def evidence_recurrence(frame, pd):
    require(not frame.duplicated(['appid', 'sale_year']).any() and set(frame.sale_year) == set(YEARS), 'Recurrence requires distinct historical pairs')
    require(frame.groupby('appid').sale_year.nunique().eq(3).all(), 'Each game must have three years')
    per_game = frame.groupby('appid', sort=True).discount_observed.sum().rename('years_with_discount_observed').reset_index()
    counts = per_game.years_with_discount_observed.value_counts().reindex(range(4), fill_value=0)
    summary = pd.DataFrame(dict(years_with_discount_observed=range(4), games=counts.to_numpy(), game_share=counts.to_numpy() / len(per_game)))
    require(summary.games.sum() == len(per_game), 'Recurrence double counts games')
    require((summary.years_with_discount_observed * summary.games).sum() == frame.discount_observed.sum(), 'Recurrence/label totals disagree')
    return per_game, summary


def prior_valid_records(timed, cutoff):
    return [r for r, stamp in timed if stamp < cutoff and r['observation_kind'] in ('discount', 'full_price')]


def raw_support(frame, inputs, windows, record_rows):
    """Validate saved observation units against original raw-index provenance.

    Only parser-valid counts and recorded values are checked. No model feature
    matrix, outcome label, or prediction is regenerated or written.
    """
    import pandas as pd
    audit = module('eda_record_parser', '04_audit_autumn_evidence.py')
    cache_paths = {int(Path(n).stem): ROOT / n for n in inputs
                   if (n.startswith('data/raw/itad/') or n.startswith('data/cohorts/itad/cache/'))
                   and Path(n).suffix == '.json' and Path(n).stem.isdecimal()}
    require(len(cache_paths) == 2000 and set(cache_paths) == set(frame.appid), 'Cache membership mismatch')
    provenance = {(int(r['appid']), int(r['sale_year'])): r for r in read_json(MODEL / 'feature_provenance.json')}
    require(set(provenance) == set(zip(frame.appid, frame.sale_year)), 'Feature provenance keys mismatch')
    record_keys = Counter((int(r['AppID']), int(r['source_record_index'])) for r in record_rows)
    require(all(n == 1 for n in record_keys.values()), 'Saved sale records duplicate a raw-index unit')
    saved_by_game = {}
    for r in record_rows: saved_by_game.setdefault(int(r['AppID']), []).append(r)
    model_by_key = frame.set_index(['appid', 'sale_year'])
    ends = {year: (audit.utc_stamp(windows[str(year)]['start_inclusive']),
                   audit.utc_stamp(windows[str(year)]['end_exclusive'])) for year in YEARS}
    checks = dict(cache_files=2000, prior_record_uses=0, sale_records=0, successful_empty_histories=0,
                  raw_records=0, parse_failures=0, non_steam_records=0, post_2025_records_not_used=0)
    latest_rows = []
    for appid, path in sorted(cache_paths.items()):
        obj = read_json(path)
        require(obj['steam_appid'] == appid and obj['request_configuration']['country'] == 'US' and
                obj['request_configuration']['steam_shop_id'] == 61, 'Cache shop/country mismatch')
        history = obj['history_response']
        checks['raw_records'] += len(history); checks['successful_empty_histories'] += int(not history)
        parsed, issues, other = audit.parse_history(history)
        require(not issues and other == 0, 'Unexpected cache parsing/shop exclusions')
        timed = [(r, audit.utc_stamp(r['timestamp_utc'])) for r in parsed]
        checks['post_2025_records_not_used'] += sum(t >= audit.utc_stamp('2026-01-01T00:00:00Z') for _, t in timed)
        # Prove the saved sale-record file contains exactly every in-window raw index.
        for year, (start, end) in ends.items():
            expected = {r['source_record_index'] for r, t in timed if start <= t < end}
            saved = {int(r['source_record_index']) for r in saved_by_game.get(appid, []) if int(r['sale_year']) == year}
            require(expected == saved, 'Saved evidence-record unit/window mismatch')
            prior = prior_valid_records(timed, start)
            frozen = model_by_key.loc[(appid, year)]; trace = provenance[(appid, year)]
            require(len(prior) == frozen.prior_price_record_count and
                    [r['source_record_index'] for r in prior] == trace['valid_prior_raw_indices'], 'Pre-cutoff count/index mismatch')
            require(sum(r['observation_kind'] == 'discount' for r in prior) == frozen.prior_discount_count, 'Discount count mismatch')
            require(trace['cutoff_violations'] == 0, 'Frozen cutoff violation')
            checks['prior_record_uses'] += len(prior)
            if year == 2025:
                latest = [r for r in prior if r['timestamp_utc'] == trace['latest_valid_prior_timestamp']] if prior else []
                if pd.notna(frozen.last_observed_price):
                    require(trace['prior_currencies'] == ['USD'] and not trace['latest_valid_timestamp_conflict'] and latest,
                            'Last-price currency/conflict provenance mismatch')
                    require(all(r['price'] == frozen.last_observed_price for r in latest), 'Saved last price differs from raw record')
                else:
                    require(bool(trace['monetary_missing_reason']), 'Missing price without a documented reason')
                latest_rows.append(dict(appid=appid, last_recorded_price_usd=None if pd.isna(frozen.last_observed_price) else float(frozen.last_observed_price),
                    last_recorded_timestamp_utc=trace['latest_valid_prior_timestamp'], source_raw_indices=json.dumps(trace['latest_valid_raw_indices']),
                    prior_price_observations=int(frozen.prior_price_record_count), missing_reason=trace['monetary_missing_reason']))
        for row in saved_by_game.get(appid, []):
            index = int(row['source_record_index']); raw = history[index]
            require(json.loads(row['raw_record_json']) == raw, 'Sale record does not match original cached JSON')
            observed = audit.observation(raw, index)
            require(all(str(observed[k]) == row[k] for k in audit.OBS_FIELDS), 'Sale record field/parser mismatch')
            checks['sale_records'] += 1
    return checks, latest_rows


def build():
    import numpy as np
    import pandas as pd
    inputs = io.verify_manifest(MODEL)
    frozen_inputs = read_json(MODEL / 'input_manifest.json')
    for name, sha in frozen_inputs['input_sha256'].items():
        require(digest(ROOT / name) == sha, 'Frozen modeling input checksum mismatch: ' + name)
    inputs.update(frozen_inputs['input_sha256'])
    evidence_validation = read_json(EVIDENCE / 'validation.json')
    for name, sha in evidence_validation['output_sha256'].items():
        require(digest(ROOT / name) == sha, 'Frozen evidence checksum mismatch: ' + name)
        inputs[name] = sha
    for path in [MODEL / 'checksums.json', EVIDENCE / 'validation.json',
                 ROOT / 'src/plotting_style.py', ROOT / 'reports/cohort_2000_visualizations/README.md',
                 ROOT / 'reports/cohort_2000_2026_visualizations/README.md',
                 ROOT / 'reports/cohort_2000_2026_visualizations/source_integrity_notes.json']:
        inputs[str(path.relative_to(ROOT))] = digest(path)
    manifest = read_json(MODEL / 'feature_manifest.json'); windows = frozen_inputs['sale_windows']
    cohort = pd.read_csv(COHORT, keep_default_na=False)
    frame = pd.read_csv(MODEL / 'modeling.csv', float_precision='round_trip')
    validate_modeling(cohort, frame, manifest, windows)
    approved = manifest['baseline_feature_allowlist']
    require(len(approved) == 15 and set(approved) == set(FEATURE_NAMES), 'Approved feature list changed')
    # Date parsing is validation only: the existing source-reported year remains authoritative.
    require(pd.to_datetime(cohort.release_date).dt.year.eq(cohort.release_year).all(), 'Cohort release date/year mismatch')
    release_counts = cohort.release_year.value_counts().reindex(range(int(cohort.release_year.min()), int(cohort.release_year.max()) + 1), fill_value=0).sort_index()
    releases = pd.DataFrame(dict(release_year=release_counts.index, games=release_counts.to_numpy()))
    require(releases.games.sum() == 2000, 'Release counts do not cover cohort')
    label_summary = read_json(MODEL / 'label_distribution.json')['by_year']
    labels = pd.DataFrame([dict(sale_year=year, role='Development' if year < 2025 else 'Held-out evaluation', games=2000,
        discount_observed=int(frame.loc[frame.sale_year.eq(year), 'discount_observed'].sum()),
        no_discount_observed=int(2000 - frame.loc[frame.sale_year.eq(year), 'discount_observed'].sum())) for year in YEARS])
    for row in labels.itertuples():
        require(row.discount_observed == label_summary[str(row.sale_year)]['positives'] and
                row.no_discount_observed == label_summary[str(row.sale_year)]['operational_zeros'], 'Historical label counts disagree')
    recurrence_games, recurrence = evidence_recurrence(frame, pd)
    frozen_missing = pd.read_csv(MODEL / 'missingness.csv')
    missing_rows = []
    for feature in approved:
        row = dict(feature=feature, display_name=FEATURE_NAMES[feature], historical_game_year_rows=6000,
                   missing_count=int(frame[feature].isna().sum()), missing_percent=100 * float(frame[feature].isna().mean()))
        for year in YEARS: row['missing_' + str(year)] = int(frame.loc[frame.sale_year.eq(year), feature].isna().sum())
        missing_rows.append(row)
        for year in [*YEARS, 'all']:
            saved = frozen_missing[(frozen_missing.feature == feature) & (frozen_missing.sale_year.astype(str) == str(year))]
            require(len(saved) == 1 and int(saved.iloc[0].missing) == (row['missing_count'] if year == 'all' else row['missing_' + str(year)]), 'Frozen missingness mismatch')
    missingness = pd.DataFrame(missing_rows)
    grouped = frame.assign(coverage_group=io.coverage_groups(frame.prior_price_record_count))
    coverage = []
    for year in YEARS:
        for group in GROUPS:
            part = grouped[(grouped.sale_year == year) & (grouped.coverage_group == group)]
            count = int(part.discount_observed.sum()); n = len(part)
            coverage.append(dict(sale_year=year, role='Development' if year < 2025 else 'Held-out evaluation',
                coverage_group=group, game_year_rows=n, discount_observed=count, no_discount_observed=n - count,
                discount_observed_rate=count / n, no_discount_observed_rate=(n - count) / n,
                observation_cutoff_utc=windows[str(year)]['start_inclusive']))
    coverage = pd.DataFrame(coverage)
    with (EVIDENCE / 'evidence_records.csv').open(newline='', encoding='utf-8') as stream:
        records = list(csv.DictReader(stream))
    require({int(r['AppID']) for r in records} <= set(cohort.AppID), 'Sale record outside cohort')
    support, price_rows = raw_support(frame, inputs, windows, records)
    prices_by_game = pd.DataFrame(price_rows)
    prices = prices_by_game.last_recorded_price_usd.dropna()
    require(len(prices) == 1918 and prices.ge(0).all() and np.isfinite(prices).all(), 'Historical price sample mismatch')
    count_values = frame.loc[frame.sale_year.eq(2025), 'prior_price_record_count']
    conflicts = pd.read_csv(EVIDENCE / 'timestamp_shop_conflicts.csv', keep_default_na=False)
    conflict_keys = {(int(r.AppID), r.timestamp_utc) for r in conflicts.itertuples()}
    discount_rows, excluded_rows = [], []
    for r in records:
        reason = ''
        if (int(r['AppID']), r['timestamp_utc']) in conflict_keys: reason = 'conflicting_same_time_records'
        elif r['observation_kind'] != 'discount': reason = 'not_a_discount_observation'
        elif r['price_currency'] != 'USD' or r['regular_currency'] != 'USD': reason = 'not_comparable_USD'
        if reason:
            excluded_rows.append(dict(appid=int(r['AppID']), sale_year=int(r['sale_year']),
                                      source_record_index=int(r['source_record_index']), reason=reason))
        else:
            discount_rows.append(dict(appid=int(r['AppID']), sale_year=int(r['sale_year']),
                timestamp_utc=r['timestamp_utc'], source_record_index=int(r['source_record_index']),
                discount_percent=float(r['cut']), recorded_price_usd=float(r['price']), regular_price_usd=float(r['regular_price'])))
    discounts = pd.DataFrame(discount_rows).sort_values(['appid', 'sale_year', 'timestamp_utc', 'source_record_index']).reset_index(drop=True)
    require(discounts.discount_percent.gt(0).all() and discounts.discount_percent.le(100).all() and
            discounts.recorded_price_usd.lt(discounts.regular_price_usd).all(), 'Invalid discount histogram unit')
    cut_values = discounts.discount_percent
    price_bins = np.arange(0, np.ceil(prices.max() / 10) * 10 + 10, 10)
    count_bins = np.arange(0, np.ceil((count_values.max() + 1) / 10) * 10 + 10, 10)
    tables = dict(release_years=releases, historical_labels=labels, evidence_recurrence=recurrence,
        recurrence_by_game=recurrence_games, missingness=missingness, coverage=coverage,
        prices_by_game=prices_by_game, observation_counts_by_game=frame.loc[frame.sale_year.eq(2025), ['appid', 'prior_price_record_count']].rename(columns={'prior_price_record_count': 'pre_2025_price_observations'}),
        discount_records=discounts, discount_exclusions=pd.DataFrame(excluded_rows),
        price_histogram=histogram(prices, price_bins, np, pd),
        observation_histogram=histogram(count_values, count_bins, np, pd),
        discount_histogram=histogram(cut_values, np.arange(0, 101, 10), np, pd))
    stats = dict(games=2000, historical_game_year_rows=6000, release_2015_or_later=int(cohort.release_year.ge(2015).sum()),
        release_year_min=int(cohort.release_year.min()), release_year_max=int(cohort.release_year.max()),
        price_games=len(prices), price_missing_games=int(prices_by_game.last_recorded_price_usd.isna().sum()),
        price_median=float(prices.median()), price_min=float(prices.min()), price_max=float(prices.max()),
        price_zero_games=int(prices.eq(0).sum()), price_below_10_games=int(prices.lt(10).sum()),
        observation_median=float(count_values.median()), observation_min=int(count_values.min()), observation_max=int(count_values.max()),
        zero_observation_games=int(count_values.eq(0).sum()), recorded_sale_rows=len(records),
        valid_discount_records=len(discounts), discounted_record_games=int(discounts.appid.nunique()),
        discount_median=float(cut_values.median()), discount_min=float(cut_values.min()), discount_max=float(cut_values.max()),
        discount_at_least_50_records=int(cut_values.ge(50).sum()),
        discount_conflicting_records_excluded=sum(r['reason'] == 'conflicting_same_time_records' for r in excluded_rows),
        discount_full_price_records_excluded=sum(r['reason'] == 'not_a_discount_observation' for r in excluded_rows),
        source_same_time_conflict_groups=len(conflict_keys), feature_rows_with_any_missing=int(frame[approved].isna().any(axis=1).sum()))
    # Carry the already-proven Phase 8B caveat as integrity metadata only; no predictions enter EDA.
    caveat = read_json(ROOT / 'reports/cohort_2000_2026_visualizations/source_integrity_notes.json')
    require(digest(ROOT / caveat['file']) == caveat['current_sha256'], 'Preexisting prediction CSV discrepancy changed')
    return dict(tables=tables, stats=stats, raw_validation=support, input_checksums=inputs,
                windows=windows, source_integrity_notes=caveat)


def chart_descriptions(data):
    s = data['stats']
    return [
        dict(filename='01_games_by_release_year.png', title='Games by release year',
             question='When were the games in this cohort released?', source='data/cohorts/cohort_2000.csv: release_year, checked against release_date.',
             unit='One game; all 2,000 games.', takeaway=f"{s['release_2015_or_later'] / 2000:.1%} were released in 2015 or later.",
             limitation='Source-reported release dates may be revised. This selected cohort does not represent every Steam game.'),
        dict(filename='02_historical_price_distribution.png', title='Prices recorded before the 2025 sale',
             question='How much did games cost at their last usable recorded observation before the 2025 sale?', source='Frozen modeling.csv: last_observed_price for sale_year=2025; raw-index provenance and original USD caches cross-checked.',
             unit=f"One last valid recorded USD price per game; {s['price_games']:,} games. Event timestamp strictly before 2025-09-29T17:00:00Z.",
             takeaway=f"{s['price_below_10_games'] / s['price_games']:.1%} of recorded prices were below $10.",
             limitation=f"{s['price_missing_games']} missing prices omitted, not zero-filled. Both observed zero prices and the $199.99 maximum are retained. Records can be stale; this is neither current price nor price verified at the cutoff. No currency conversion or inflation adjustment."),
        dict(filename='03_historical_observations_per_game.png', title='How much price history is available?',
             question='How many valid historical price observations were available before the 2025 sale?', source='Frozen modeling.csv: prior_price_record_count for sale_year=2025; saved raw indices checked against each historical cutoff.',
             unit='One count per game; all 2,000 games, including zero. Cutoff 2025-09-29T17:00:00Z; ten-observation bins.',
             takeaway=f"Half the games have {s['observation_median']:.0f} or fewer recorded price observations.",
             limitation=f"{s['zero_observation_games']} games have zero observations. Counts retain duplicates and are not distinct sales, discounted days, or proof of complete history. Provider availability at the historical cutoff is unproven."),
        dict(filename='04_autumn_sale_evidence_by_year.png', title='Autumn Sale discount evidence by year',
             question='How many games had discount evidence in each Autumn Sale?', source='Frozen modeling.csv: discount_observed and evidence_category; reconciled to Phase 6C label_distribution.json.',
             unit='One game-year label; 2,000 games per year, 6,000 rows total.', takeaway='About half the games have discount evidence in each year.',
             limitation='No discount observed means no evidence in the available records, not verified nonparticipation. 2023–2024 are development years; 2025 is the held-out evaluation year. This chart is descriptive, not a new evaluation.'),
        dict(filename='05_discount_evidence_across_three_years.png', title='How often was a discount observed?',
             question='In how many of the three Autumn Sales did each game have positive evidence?', source='Frozen modeling.csv: sum of discount_observed across 2023, 2024 and 2025 for each AppID.',
             unit='One game counted exactly once in 0, 1, 2 or 3 positive-label years.', takeaway='713 games have discount evidence in all three years.',
             limitation='Zero positive years does not prove a game never participated. Repeated observations of the same games are dependent; these are descriptive counts.'),
        dict(filename='06_observed_discount_percentages.png', title='Sizes of recorded Autumn Sale discounts',
             question='How large were the directly recorded discounts during the three Autumn Sales?', source='Phase 6A evidence_records.csv: explicit cut, shop 61, USD price and regular price; verified against original cached JSON. timestamp_shop_conflicts.csv flags exclusions.',
             unit=f"One unambiguous discounted raw record inside a 2023–2025 Autumn Sale window; {s['valid_discount_records']:,} records from {s['discounted_record_games']:,} games.",
             takeaway=f"The middle recorded discount was {s['discount_median']:.0f}%.",
             limitation=f"{s['discount_conflicting_records_excluded']} same-time conflicting records and {s['discount_full_price_records_excluded']} full-price records are excluded only from this descriptive chart. Explicit cut is retained, not recomputed from rounded money fields. Games with more records receive more weight; records are not independent sales or distinct discounted days."),
        dict(filename='07_coverage_vs_discount_evidence.png', title='More history goes with more discount evidence',
             question='How does recorded sale evidence vary with the amount of prior price history?', source='Frozen modeling.csv: each game-year prior_price_record_count and unchanged discount_observed label. Saved pre-cutoff indices are independently checked.',
             unit='Game-year rows grouped separately for each year into 0, 1–9, 10–29 and 30+ prior valid observations. Each panel sums to 2,000 games.',
             takeaway='The 30+ observation group has the highest discount-evidence rate in every year.',
             limitation='Each year uses its own strictly pre-sale cutoff. Sample sizes differ. This is an association between coverage and available evidence, not a causal claim or verified participation rate. Development (2023–2024) and held-out (2025) panels stay separate.'),
        dict(filename='08_missing_values_by_feature.png', title='Which features have missing values?',
             question='Which of the 15 approved predictors contain blank values?', source='Frozen modeling.csv: is-missing counts for the 15 approved predictors, reconciled to frozen missingness.csv and feature_manifest.json.',
             unit='Missing cells within 6,000 historical game-year rows (2023–2025); one bar per approved predictor.',
             takeaway='Seven predictors have missing values; eight are complete.',
             limitation='A game can have multiple missing predictors in multiple years. Counts are missing cells per feature, not unique games. Nulls mean unavailable information, not zero or verified nonparticipation. No imputation or feature selection is performed.'),
    ]


def figures(destination, data, descriptions):
    import numpy as np
    from plotting_style import light_style, plt
    from matplotlib.patches import Patch
    t = data['tables']

    def grid(ax, axis='y'):
        ax.grid(axis=axis); ax.set_axisbelow(True)

    def finish(fig, number, footer):
        desc = descriptions[number - 1]
        fig.suptitle(desc['title'], fontsize=18, y=.98)
        fig.text(.5, .919, desc['takeaway'], ha='center', fontsize=13, color=BLUE)
        fig.text(.5, .031, footer, ha='center', fontsize=9, color='#616970')
        fig.tight_layout(rect=(0, .08, 1, .95))
        fig.savefig(destination / desc['filename'], dpi=300, facecolor='white', metadata={'Software': 'Steam cohort Phase 8D'})
        plt.close(fig)

    def hist(ax, table):
        ax.bar(table.lower_inclusive, table['count'], width=table.upper - table.lower_inclusive,
               align='edge', color=BLUE, edgecolor='white', linewidth=.7)
        ax.set_ylabel('Games'); grid(ax)

    with light_style(), plt.rc_context({'font.size': 12, 'axes.labelsize': 12, 'xtick.labelsize': 11, 'ytick.labelsize': 11, 'legend.fontsize': 11}):
        fig, ax = plt.subplots(figsize=(10.5, 5.6))
        r = t['release_years']; ax.bar(r.release_year, r.games, color=BLUE, width=.78)
        ax.set(xlabel='Release year', ylabel='Games', xticks=list(range(int(r.release_year.min()), int(r.release_year.max()) + 1, 2)))
        ax.tick_params(axis='x', rotation=45); grid(ax)
        finish(fig, 1, 'Original 2,000-game cohort · Source-reported release dates')

        fig, ax = plt.subplots(figsize=(9.3, 5.6)); hist(ax, t['price_histogram'])
        ax.set(xlabel='Last recorded Steam price (USD)', xlim=(0, 200), xticks=[0, 50, 100, 150, 200])
        finish(fig, 2, '1,918 games with a usable price · Before the 2025 sale · 82 missing prices omitted; all extremes retained')

        fig, ax = plt.subplots(figsize=(9.3, 5.6)); hist(ax, t['observation_histogram'])
        ax.set(xlabel='Historical price observations before the 2025 sale', xlim=(0, t['observation_histogram'].upper.max()), xticks=[0, 50, 100, 150, 200, 250])
        finish(fig, 3, 'All 2,000 games included · 82 have zero observations · Records are not distinct sales')

        fig, ax = plt.subplots(figsize=(9.3, 5.8)); r = t['historical_labels']; x = np.arange(3)
        for field, offset, color, label in [('discount_observed', -.19, BLUE, 'Discount observed'), ('no_discount_observed', .19, GRAY, 'No discount observed')]:
            ax.bar(x + offset, r[field], width=.36, color=color, label=label)
            for i, count in enumerate(r[field]): ax.text(i + offset, count + 25, f'{count:,}', ha='center', fontsize=12)
        ax.set(xticks=x, xticklabels=['2023\nDevelopment', '2024\nDevelopment', '2025\nHeld-out evaluation'], ylabel='Games', ylim=(0, 1350))
        ax.legend(loc='upper center', ncol=2); grid(ax)
        finish(fig, 4, '2,000 games per year · “No discount observed” does not prove nonparticipation')

        fig, ax = plt.subplots(figsize=(9.3, 5.6)); r = t['evidence_recurrence']
        ax.bar(r.years_with_discount_observed, r.games, color=BLUE, width=.6)
        for row in r.itertuples(): ax.text(row.years_with_discount_observed, row.games + 12, f'{row.games:,}', ha='center')
        ax.set(xlabel='Years with discount evidence (2023–2025)', ylabel='Games', xticks=range(4), xticklabels=['0 years', '1 year', '2 years', '3 years'], ylim=(0, 880)); grid(ax)
        finish(fig, 5, 'Each of the 2,000 games counted once · Zero evidence years does not prove nonparticipation')

        fig, ax = plt.subplots(figsize=(9.3, 5.6)); hist(ax, t['discount_histogram'])
        ax.set(xlabel='Recorded discount (%)', ylabel='Discount observations', xlim=(0, 100), xticks=[0, 20, 40, 60, 80, 100])
        finish(fig, 6, '3,035 valid Steam USD discount records · 2023–2025 sale windows · Two conflicting records excluded')

        fig, axes = plt.subplots(1, 3, figsize=(12.0, 6.3), sharey=True)
        for ax, year in zip(axes, YEARS):
            r = t['coverage'][t['coverage'].sale_year.eq(year)].reset_index(drop=True); x = np.arange(4)
            ax.bar(x - .18, r.discount_observed_rate * 100, width=.34, color=BLUE)
            ax.bar(x + .18, r.no_discount_observed_rate * 100, width=.34, color=GRAY)
            ax.set(xticks=x, xticklabels=[f'{label}\nn={n:,}' for label, n in zip(DISPLAY, r.game_year_rows)], ylim=(0, 105), yticks=[0, 50, 100],
                   title=str(year) + (' · Development' if year < 2025 else ' · Held-out evaluation'), xlabel='Prior observations')
            ax.title.set_fontsize(12); grid(ax)
        axes[0].set_ylabel('Share of games in the group (%)')
        fig.legend(handles=[Patch(color=BLUE, label='Discount observed'), Patch(color=GRAY, label='No discount observed')],
                   loc='upper center', bbox_to_anchor=(.5, .868), ncol=2, fontsize=11)
        # Headroom separates the legend from the three panel titles.
        desc = descriptions[6]
        fig.suptitle(desc['title'], fontsize=18, y=.98)
        fig.text(.5, .927, desc['takeaway'], ha='center', fontsize=12.5, color=BLUE)
        fig.text(.5, .026, 'Each year uses its own pre-sale cutoff · Association, not causation or verified participation', ha='center', fontsize=9, color='#616970')
        fig.tight_layout(rect=(0, .08, 1, .9))
        fig.savefig(destination / desc['filename'], dpi=300, facecolor='white', metadata={'Software': 'Steam cohort Phase 8D'}); plt.close(fig)

        fig, ax = plt.subplots(figsize=(10.8, 8.4)); r = t['missingness'].sort_values(['missing_count', 'feature'], ascending=[False, True]).reset_index(drop=True)
        ax.barh(range(15), r.missing_count, color=BLUE, height=.61)
        for i, count in enumerate(r.missing_count): ax.text(count + 17, i, f'{count:,}', va='center', fontsize=11)
        ax.set(yticks=range(15), yticklabels=r.display_name, xlabel='Missing values out of 6,000 historical game-year rows', xlim=(0, 1320))
        ax.invert_yaxis(); grid(ax, 'x')
        finish(fig, 8, 'All 15 approved predictors · Blank cells remain missing; observed zeros remain zero')


def document(destination, data, descriptions):
    import pandas as pd
    s, t = data['stats'], data['tables']
    docs = pd.DataFrame(descriptions)
    io.write_csv(destination / 'figure_captions.csv', docs)
    io.write_csv(destination / 'figure_index.csv', docs[['filename', 'title']])
    index = '| Figure | PNG |\n| --- | --- |\n' + '\n'.join(f'| {d["title"]} | [{d["filename"]}]({d["filename"]}) |' for d in descriptions)
    caption_body = '# Figure captions and interpretation\n\n**' + NOTICE + '**\n\n' + '\n\n'.join(
        f'## {i:02d} — {d["title"]}\n\n**Question:** {d["question"]}\n\n**Data source:** {d["source"]}\n\n**Unit:** {d["unit"]}\n\n**Takeaway:** {d["takeaway"]}\n\n**Limitation:** {d["limitation"]}' for i, d in enumerate(descriptions, 1)) + '\n'
    (destination / 'figure_captions.md').write_text(caption_body, encoding='utf-8')
    (destination / 'figure_index.md').write_text('# Figure index\n\n' + index + '\n', encoding='utf-8')
    recurrence = t['evidence_recurrence'].games.tolist()
    (destination / 'key_findings.md').write_text(f'''# Key EDA findings

**{NOTICE}** Findings are descriptive and must not alter frozen model development, labels, cohort membership, thresholds or predictions.

- The 2,000 cohort games have source-reported release years {s['release_year_min']}–{s['release_year_max']}; {s['release_2015_or_later']:,} ({s['release_2015_or_later'] / 2000:.1%}) were released in 2015 or later. The largest release-year group is 2022 (327 games).
- Among {s['price_games']:,} games with a usable last recorded pre-2025-sale USD price, {s['price_below_10_games']:,} ({s['price_below_10_games'] / s['price_games']:.1%}) have prices below $10. Median is ${s['price_median']:.2f}; range is ${s['price_min']:.2f}–${s['price_max']:.2f}. All values, including two observed zero prices and the maximum, remain in the histogram; {s['price_missing_games']} missing prices are omitted and separately counted.
- The median historical observation count before the 2025 cutoff is {s['observation_median']:.0f}, with range {s['observation_min']}–{s['observation_max']}. All 2,000 games contribute once, including {s['zero_observation_games']} with zero observations. Counts measure returned records, not distinct sales or discounted days.
- Discount-observed labels number 979 (48.95%) in 2023, 1,068 (53.40%) in 2024 and 983 (49.15%) in 2025. Corresponding “No discount observed” counts are 1,021, 932 and 1,017. These are frozen operational labels, not verified sale participation outcomes.
- Across all three years, {recurrence[0]} games have positive evidence in zero years, {recurrence[1]} in one, {recurrence[2]} in two, and {recurrence[3]} in three. Each game is counted exactly once. Zero evidence years does not prove no actual participation.
- The discount histogram uses {s['valid_discount_records']:,} valid Steam USD discount records from {s['discounted_record_games']:,} games inside the 2023–2025 Autumn Sale windows. Median explicit discount is {s['discount_median']:.0f}%, with range {s['discount_min']:.0f}–{s['discount_max']:.0f}%. {s['discount_at_least_50_records']:,} ({s['discount_at_least_50_records'] / s['valid_discount_records']:.1%}) show discounts of at least 50%. Two conflicting same-time records and 24 full-price observations are excluded from this chart only; no historical labels or source records are changed.
- More historical observations go with more recorded sale evidence in every year. In the held-out 2025 year, observed positive-label rates are 0%, 3.53%, 35.12% and 81.03% for 0, 1–9, 10–29 and 30+ prior observations. This is an association, not proof that coverage causes discounts or a measure of true participation. The year-specific sample sizes and both label rates are in `coverage.csv`.
- Seven of 15 approved predictors contain missing cells. Days since last discount, largest earlier discount and average earlier discount each have 1,134 missing values (18.9% of 6,000 rows). Four price-history predictors each have 253 (4.22%). Eight predictors have none. Missingness describes unavailable historical evidence, not verified nonparticipation.

## Data quality and interpretation

Recorded prices are USD amounts for Steam shop 61 / US, one latest usable price per game strictly before the 2025 cutoff. They can be stale; no price is claimed to be current or verified at the cutoff. No currency conversion, clipping, imputation, inflation adjustment or forward filling is used.

The discount chart represents discrete observed sale-window records, not game averages, purchases, unique campaigns or daily price states. Games with more observations carry more weight. Explicit percentage fields follow the existing parser; rounded money fields are not used to invent new percentages. One conflicting timestamp group contributes two excluded observations. Original evidence and labels remain frozen.

Historical 2023–2024 development and held-out 2025 evaluation data are shown separately for coverage and annual labels. This EDA was conducted after model development, including inspection of the held-out year; it must not be used for feature selection, model tuning, threshold changes, label revisions or re-evaluation claims. No model is loaded or queried here.

All historical cutoffs exclude at/after-cutoff events. This demonstrates event-time filtering, not provider availability at those historical times. ITAD snapshots were collected retrospectively. Source-release-date uncertainty, incomplete/uneven history, provider backfill, timestamp conflicts and retrospective cohort selection remain limitations. Repeated game-year rows are dependent; 6,000 rows are not 6,000 independent games. The cohort is not a representative estimate of the full Steam catalog. “No discount observed” is not verified nonparticipation.

## Supported charts and presentation

All eight requested charts are supported; no alternate variable or infeasible-chart replacement is needed. The historical price measure is explicitly the last valid recorded pre-2025-sale USD price, and the discount measure is an explicit percentage inside historical sale windows. Their units differ and must stay labeled.

Recommended core presentation: 01 (release years), 04 (annual evidence), 05 (three-year evidence) and 07 (coverage association). Include 02 and 06 when discussing prices/discount sizes; retain 03 and 08 for a data-quality explanation. Read the limitation alongside every takeaway.

## Preexisting integrity caveats

The protected historical baseline remains 218/219: `data/intermediate/autumn_sale_evidence_records.csv` has the previously documented ordering-only mismatch. It is preserved without repair and is not an EDA chart source.

The Phase 8B prediction CSV also has the already documented row-order/two-name discrepancy (AppIDs 1518000 and 2402900). Its Phase 8C integrity note is retained; current bytes are checked against that note. Predictions and prediction names are not EDA chart inputs. No source file, manifest or journal is repaired.

The charts and documented sources are ready for Phase 9A descriptive research synthesis with these limits visible. No frozen modeling or prediction result is revised by this EDA.
''', encoding='utf-8')
    definitions = read_json(MODEL / 'feature_manifest.json')['features']
    io.write_csv(destination / 'predictor_dictionary.csv', pd.DataFrame([
        dict(feature=d['feature_name'], display_name=FEATURE_NAMES[d['feature_name']], definition=d['definition'],
             source=d['source'], missing_value_meaning=d['missing_value_meaning']) for d in definitions if d['baseline_allowlist']]))
    (destination / 'data_sources.md').write_text(f'''# Data sources and observation units

**{NOTICE}** All sources are local frozen artifacts. No provider requests were made.

| Chart | Source | Unit and time scope |
| --- | --- | --- |
| 01 | `data/cohorts/cohort_2000.csv` | Source-reported release year, one value per original game |
| 02 | `reports/cohort_2000_modeling/modeling.csv` | `last_observed_price`, 2025 rows; one recorded USD amount per game; timestamp strictly before 2025-09-29T17:00:00Z |
| 03 | Same frozen modeling CSV | `prior_price_record_count`, 2025 rows; one pre-cutoff count per game, including zero |
| 04 | Same frozen modeling CSV | Frozen `discount_observed` labels; one row per game/year, 2023–2025 |
| 05 | Same frozen modeling CSV | Sum of three frozen labels per AppID; each game counted once |
| 06 | `reports/cohort_2000_labelability/evidence_records.csv` | Explicit `cut` in valid discounted Steam/USD raw records inside the three sale windows; `timestamp_shop_conflicts.csv` flags excluded conflicting observations |
| 07 | Frozen modeling CSV and `feature_provenance.json` | Prior count and frozen label for the same year; each historical cutoff applied separately |
| 08 | Frozen modeling CSV and `feature_manifest.json` | Null cells per approved predictor in 6,000 historical game-year rows; checked against `missingness.csv` |

The original caches pinned by `input_manifest.json` provide read-only validation of all 2,000 histories, 6,000 saved count/provenance pairs, every saved sale record, and the 2025 last recorded prices. The existing Phase 5A.1 observation parser is reused unchanged; no labels, features or predictions are regenerated. Saved observations retain their original raw-index units. The sale-record CSV is not a complete history table; it contains only directly timestamped in-window observations.

Price histogram bins are $10 wide from $0 through $200, with the final upper boundary inclusive. Zero-dollar observed amounts and $199.99 remain included. Missing prices are omitted and counted separately, with their documented missing reasons in `prices_by_game.csv`. There is no top-coding, clipping, invented regular price or substitution of the master dataset's contemporary price. All values are nominal USD, without inflation adjustment.

Observation-count bins are ten records wide and include zero. No missing count is replaced by zero. Raw duplicate observations are retained by the existing definition; counts are not unique sales. The observation source collection begins at the requested boundary 2021-01-01T00:00:00Z, which does not establish complete coverage thereafter.

Discount histogram bins are ten percentage points wide from 0 to 100, left-inclusive/right-exclusive except the final bin includes 100. Only positive explicit discounts with valid USD money and price below regular price are included. Full-price records, ambiguous/null/malformed monetary fields, non-USD records and same-time conflicts are excluded if present. Exact data-specific exclusion counts and original raw indices are in `discount_exclusions.csv`. The source has no identical duplicate sale-record payloads; records remain discrete observations, without daily interpolation. Repeated games and multiple records per game are not independent units.

## Historical windows and development roles

| Year | Role | Predictor timestamps strictly before / label window start inclusive | Label window end exclusive |
| --- | --- | --- | --- |
''' + '\n'.join(f'| {year} | {"Development" if year < 2025 else "Held-out evaluation"} | {data["windows"][str(year)]["start_inclusive"]} | {data["windows"][str(year)]["end_exclusive"]} |' for year in YEARS) + '''

A→“Discount observed”; B/D→“No discount observed”; C remains Unknown under the frozen rule, and there are no C rows in this dataset. The frozen binary modeling view is used, not Phase 6A's separate conservative labelability eligibility target. No discount observed means absent evidence in available observations, not proof of nonparticipation.

`predictor_dictionary.csv` preserves all 15 approved definitions and missing-value meanings. Source hashes and versions accompany the report. Existing Phase 7B/8C styling is reused through `src/plotting_style.py`, with larger text and simple audience-friendly titles/takeaways. None of their figures or source artifacts are changed.
''', encoding='utf-8')
    (destination / 'README.md').write_text(f'''# Phase 8D — fundamental exploratory data analysis

**{NOTICE}** This accessible EDA covers the original **2,000-game cohort** and frozen **6,000 historical game-year rows (2023–2025)**. It is descriptive and cannot be used to change frozen features, models, parameters, selection, thresholds, labels, cohort membership or predictions.

**“No discount observed” means no evidence in the available records, not verified nonparticipation.** Provider availability at historical cutoffs is unproven. Development years 2023–2024 and the held-out 2025 evaluation year retain their frozen roles; inspecting them here does not authorize new tuning or evaluation.

## Eight core figures

{index}

Every figure has a simple question, data source, unit, factual takeaway and limitation in [figure_captions.md](figure_captions.md) and `figure_captions.csv`. All eight requested charts are supported with explicitly defined measures. PNGs are separate 300-DPI files, with white backgrounds, larger DejaVu Sans text, minimal gridlines/borders, and consistent blue/gray colors. Each chart presents one plain factual takeaway beneath its title.

See [key_findings.md](key_findings.md), [data_sources.md](data_sources.md) and [figure_index.md](figure_index.md). Each CSV named for a table supplies its chart data; `recurrence_by_game.csv`, `prices_by_game.csv`, `observation_counts_by_game.csv`, and `discount_records.csv` document the individual contributing units. `discount_exclusions.csv` records chart-only exclusions. `predictor_dictionary.csv` preserves the existing 15 definitions. Nulls remain blank, with true observed zeros retained.

The price histogram uses **one last recorded USD price per game before the 2025 sale**, not current prices or a mixture of currencies. It includes 1,918 games, omits 82 missing prices, and retains all observed extremes. The discount histogram uses **3,035 directly recorded Steam/USD discount observations inside the 2023–2025 sale windows**, excluding two conflicting same-time records and 24 full-price records from this chart only. These units differ; neither chart describes purchases, complete daily price states or guaranteed sale outcomes.

## Reproduce and test offline

From the repository root, use a **fresh destination** (existing output directories are refused):

```sh
env -u ITAD_API_KEY PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp \\
  /usr/bin/python3 -B tests/run_eda_offline.py \\
  --results /private/tmp/steam-eda-preflight.json

env -u ITAD_API_KEY PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp \\
  /usr/bin/python3 -B src/eda_cohort_2000.py \\
  --output-dir reports/cohort_2000_eda_reproduction \\
  --test-results /private/tmp/steam-eda-preflight.json

env -u ITAD_API_KEY PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp \\
  /usr/bin/python3 -B tests/run_eda_offline.py \\
  --artifacts reports/cohort_2000_eda \\
  --results /private/tmp/steam-eda-final-tests.json
```

The generator verifies the frozen modeling manifest, all pinned inputs, and saved evidence hashes, then cross-checks raw observation membership, timestamps, USD values and existing feature provenance. It reloads all source files independently for a second render: all core figures, summary CSVs and explanatory documents must reproduce byte-for-byte. Versions, input/code hashes, image metadata and preservation receipts are saved. PNG byte identity is established in the recorded dependency/font environment; other versions can change rendering bytes.

Network requests, subprocesses, model imports/deserialization and writes outside the fresh report/runtime directories are guarded. No model-fitting or inference tests run. Existing artifacts are read-only. `reproduction.json`, `validation.json`, `input_checksums.json`, `figure_manifest.json`, `phase_start_checksums.json`, and `checksums.json` record verification; test receipts accompany the report when supplied.

## Integrity and readiness

All phase-start project files, protected artifacts, historical data, Phase 6/7/8 reports/models and journal entries must retain their original bytes. The historical protected baseline's known ordering mismatch (218/219 agreement) and Phase 8B's already documented prediction CSV row-order/two-name discrepancy are recorded without repair. Predictions are not chart inputs; release metadata and AppIDs come from the original frozen cohort.

All eight charts and their supporting sources are ready for Phase 9A descriptive synthesis with their stated limitations. No EDA finding revises any frozen model or prediction result.
''', encoding='utf-8')


def render(destination, data):
    destination.mkdir()
    descriptions = chart_descriptions(data)
    figures(destination, data, descriptions)
    for name, frame in data['tables'].items(): io.write_csv(destination / (name + '.csv'), frame)
    io.write_json(destination / 'descriptive_statistics.json', data['stats'])
    io.write_json(destination / 'source_integrity_notes.json', data['source_integrity_notes'])
    document(destination, data, descriptions)


def main():
    sys.dont_write_bytecode = True
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--phase-start-checksums', type=Path)
    parser.add_argument('--test-results', type=Path)
    args = parser.parse_args()
    destination = args.output_dir.absolute()
    require(not any(p.is_symlink() for p in [destination, *destination.parents]), 'Symlink output refused')
    destination = destination.resolve()
    require(not destination.exists() and destination.parent.is_dir(), 'Use a fresh output directory')
    require(not destination.is_relative_to(ROOT) or destination.parent == ROOT / 'reports', 'Repository outputs must be new reports directories')
    require('ITAD_API_KEY' not in os.environ, 'Run with env -u ITAD_API_KEY')
    runtime = Path(tempfile.mkdtemp(prefix='steam-phase8d-', dir='/private/tmp'))
    os.environ['MPLCONFIGDIR'] = str(runtime / 'mpl'); tempfile.tempdir = str(runtime)
    import numpy
    import pandas
    io.install_guard(destination, runtime)
    before = read_json(args.phase_start_checksums) if args.phase_start_checksums else io.inventory()
    integrity = io.verify_preservation(before)
    receipt = read_json(args.test_results) if args.test_results else None
    if receipt: require(receipt['passed'] and receipt['no_models_trained'] and receipt['no_model_predictions'], 'Invalid offline test receipt')
    data = build(); render(destination, data)
    second = runtime / 'independent-render'; render(second, build())
    names = sorted(p.name for p in destination.iterdir())
    require(all(digest(destination / n) == digest(second / n) for n in names), 'Independent EDA reproduction differs')
    io.write_json(destination / 'reproduction.json', dict(independent_source_reload=True, byte_identical=True, compared_files=names,
        png_files=8, csv_files=sum(n.endswith('.csv') for n in names), no_models_loaded=True))
    io.write_json(destination / 'input_checksums.json', data['input_checksums'])
    io.write_json(destination / 'figure_manifest.json', io.figure_manifest(destination))
    io.write_json(destination / 'phase_start_checksums.json', before)
    if receipt: io.write_json(destination / 'offline_test_results.json', receipt)
    integrity = io.verify_preservation(before)
    io.write_json(destination / 'validation.json', dict(**integrity, games=2000, historical_game_year_rows=6000,
        historical_years=YEARS, figures=8, raw_validation=data['raw_validation'],
        no_network=True, api_calls=0, no_models_loaded=True, no_models_trained=True, no_model_predictions=True,
        no_feature_selection=True, no_parameter_or_threshold_changes=True, no_operational_label_changes=True,
        no_cohort_expansion=True, no_frozen_modeling_or_prediction_changes=True, charts_supported=8,
        direct_raw_record_provenance_verified=True, each_year_own_pre_cutoff_counts_verified=True,
        missingness_reconciled=True, historical_labels_reconciled=True, independent_byte_reproduction=True,
        retrospective_post_modeling_description=NOTICE, versions={name: metadata.version(name) for name in ('numpy', 'pandas', 'matplotlib', 'Pillow')},
        source_sha256={name: digest(ROOT / name) for name in ['src/eda_cohort_2000.py', 'src/visualize_cohort_2026.py',
            'src/plotting_style.py', 'src/04_audit_autumn_evidence.py', 'tests/test_cohort_eda.py', 'tests/run_eda_offline.py']}))
    io.write_json(destination / 'checksums.json', {p.name: digest(p) for p in sorted(destination.iterdir()) if p.is_file()})
    print(json.dumps(dict(figures=8, byte_identical_core_files=len(names), **integrity)))


if __name__ == '__main__': main()
