"""Phase 8C: offline figures from frozen CSVs, without loading any model."""
import argparse
import csv
import hashlib
import io
from importlib import metadata
import json
import os
from pathlib import Path
import sys
import tempfile
import textwrap

from cohort_io import ROOT, digest, read_json, require

SOURCE = ROOT / 'reports/cohort_2000_2026_predictions'
HISTORY = ROOT / 'reports/cohort_2000_modeling'
CUTOFF = '2026-10-01T17:00:00Z'
WARNING = 'Retrospective event-time-filtered predictions using post-cutoff-collected historical data.'
GROUPS = ['0', '1-9', '10-29', '30+']
DISPLAY = ['0', '1–9', '10–29', '30+']
GREEN, BLUE, ORANGE, GRAY = '#779584', '#527D9D', '#C58B57', '#88939D'
PALETTE = [GRAY, BLUE, ORANGE, GREEN]
MISMATCH = 'data/intermediate/autumn_sale_evidence_records.csv'
FEATURE_LABELS = {
    'days_since_last_discount': 'Days since last discount',
    'max_prior_discount_pct': 'Maximum prior discount',
    'mean_prior_discount_pct': 'Mean prior discount',
    'prior_discount_rate': 'Prior discount observation ratio',
    'days_since_last_price_record': 'Days since last price observation',
    'last_observed_price': 'Last observed price',
    'last_observed_discount_pct': 'Last observed discount',
}


def write_json(path, value):
    with path.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + '\n')


def write_csv(path, frame):
    frame.to_csv(path, index=False, mode='x', lineterminator='\n', float_format='%.17g')


def prediction_serialization_audit(directory, expected):
    """Prove the preexisting CSV discrepancy affects only order and two names.

    Reconstruct original serialization in memory for hashing only. Plot inputs
    always retain the current frozen CSV values; no source file is repaired.
    """
    availability_path = ROOT / 'reports/cohort_2000_2026_feasibility/game_availability.csv'
    input_sha = read_json(directory / 'input_checksums.json')['frozen_artifact_sha256']
    require(digest(availability_path) == input_sha[str(availability_path.relative_to(ROOT))],
            'Frozen availability checksum mismatch')
    with (directory / 'predictions_2026.csv').open(newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    with availability_path.open(newline='', encoding='utf-8') as f:
        availability = list(csv.DictReader(f))
    lookup = {r['appid']: dict(r) for r in rows}
    require(len(lookup) == len(rows) == 2000 and set(lookup) == {r['appid'] for r in availability},
            'Prediction serialization membership mismatch')
    name_changes = []
    for r in availability:
        if lookup[r['appid']]['game_name'] != r['game_name']:
            name_changes.append(dict(appid=int(r['appid']), current_prediction_csv_name=lookup[r['appid']]['game_name'],
                                     frozen_cohort_name=r['game_name']))
        lookup[r['appid']]['game_name'] = r['game_name']
    original = io.StringIO(newline='')
    writer = csv.DictWriter(original, fieldnames=list(rows[0]))
    writer.writeheader(); writer.writerows([lookup[r['appid']] for r in availability])
    reconstructed = hashlib.sha256(original.getvalue().encode('utf-8')).hexdigest()
    require(reconstructed == expected, 'Prediction discrepancy exceeds ordering/name-only changes')
    require([r['appid'] for r in name_changes] == [1518000, 2402900], 'Unexpected preexisting name discrepancy')
    return dict(file='reports/cohort_2000_2026_predictions/predictions_2026.csv',
                manifest_sha256=expected, current_sha256=digest(directory / 'predictions_2026.csv'),
                original_serialization_reconstructed_in_memory_sha256=reconstructed,
                original_manifest_hash_reproduced=True, preexisting_row_order_changed=True,
                name_discrepancies=name_changes, all_other_fields_unchanged=True,
                scores_classes_and_cohort_unchanged=True, source_repaired=False,
                frozen_availability_sha256=digest(availability_path))


def verify_manifest(directory, permit_proven_prediction_serialization=False):
    checks = read_json(directory / 'checksums.json')
    for name, sha in checks.items():
        require(Path(name).name == name, 'Unsafe input manifest path')
        actual = digest(directory / name)
        if actual != sha and permit_proven_prediction_serialization and name == 'predictions_2026.csv':
            prediction_serialization_audit(directory, sha)
        else:
            require(actual == sha, f'Frozen checksum mismatch: {directory.name}/{name}')
    return {str((directory / name).relative_to(ROOT)): digest(directory / name) for name in checks}


def coverage_groups(counts):
    import numpy as np
    import pandas as pd
    require(counts.notna().all() and np.isfinite(counts).all() and
            counts.ge(0).all() and counts.eq(counts.astype(int)).all(), 'Invalid observation counts')
    return pd.Series(np.select([counts.eq(0), counts.le(9), counts.le(29)],
                              GROUPS[:3], default=GROUPS[3]), index=counts.index)


def distribution(values, prefix='probability_'):
    require(len(values) > 0 and values.notna().all(), 'Invalid distribution sample')
    return {prefix + name: float(value) for name, value in {
        'min': values.min(), 'p05': values.quantile(.05), 'q25': values.quantile(.25),
        'median': values.median(), 'q75': values.quantile(.75), 'p95': values.quantile(.95),
        'max': values.max(), 'mean': values.mean(), 'std_population': values.std(ddof=0),
    }.items()}


def summarize(frame, **identity):
    positive = int(frame.predicted_operational_label.sum())
    return dict(**identity, games=len(frame), predicted_positives=positive,
                predicted_operational_zeros=len(frame) - positive,
                predicted_positive_rate=positive / len(frame),
                **distribution(frame.predicted_probability),
                **distribution(frame.prior_price_record_count, 'observation_count_'))


def rank(frame, highest):
    return frame.sort_values(['predicted_probability', 'appid'],
                             ascending=[not highest, True], kind='stable').head(10).reset_index(drop=True)


def validate_rows(pred, features, approved):
    import numpy as np
    require(len(pred) == len(features) == 2000 and pred.appid.is_unique and features.appid.is_unique,
            'Exactly 2,000 unique games required')
    require(set(pred.appid) == set(features.appid), 'Prediction/feature membership mismatch')
    for frame in (pred, features):
        require(frame.sale_year.eq(2026).all() and frame.prediction_cutoff_utc.eq(CUTOFF).all(),
                'Year/cutoff mismatch')
    require(np.isfinite(pred.predicted_probability).all() and pred.predicted_probability.between(0, 1).all(),
            'Invalid probability')
    require(pred.predicted_operational_label.isin([0, 1]).all() and
            pred.predicted_operational_label.eq(pred.predicted_probability.ge(.5).astype(int)).all(),
            'Frozen threshold/class mismatch')
    require(pred.prediction_description.eq(WARNING).all() and pred.retrospective_event_time_filtered.all() and
            not pred.point_in_time_provider_availability_proven.any(), 'Availability warning mismatch')
    require(coverage_groups(pred.prior_price_record_count).eq(pred.coverage_group).all(), 'Coverage group mismatch')
    features = features.set_index('appid').loc[pred.appid].reset_index()
    for name in ('prior_price_record_count', 'prior_discount_count', 'has_prior_price_history', 'has_prior_discount_observation'):
        require(pred[name].eq(features[name]).all(), 'Feature/prediction metadata mismatch: ' + name)
    missing = features[approved].isna()
    require(missing.sum(axis=1).eq(pred.missing_feature_count).all(), 'Missingness count mismatch')
    require((15 - missing.sum(axis=1)).eq(pred.observed_feature_count).all() and
            missing.sum(axis=1).eq(0).eq(pred.all_15_features_nonmissing).all(), 'Feature completeness mismatch')
    for i, value in enumerate(pred.missing_feature_names):
        require(json.loads(value) == [name for name in approved if missing.loc[i, name]], 'Missingness pattern mismatch')
    return features, missing


def build(source=SOURCE):
    import numpy as np
    import pandas as pd
    checks = verify_manifest(source, permit_proven_prediction_serialization=True)
    checks.update(verify_manifest(HISTORY))
    serialization_audit = prediction_serialization_audit(source, read_json(source / 'checksums.json')['predictions_2026.csv'])
    for path in [source / 'checksums.json', HISTORY / 'checksums.json',
                 ROOT / 'reports/cohort_2000_2026_feasibility/game_availability.csv']:
        checks[str(path.relative_to(ROOT))] = digest(path)
    config = read_json(source / 'configuration_manifest.json')
    schema = read_json(source / 'feature_schema_manifest.json')
    selection_path = ROOT / 'reports/cohort_2000_models/selection.json'
    selection = read_json(selection_path)
    require(digest(selection_path) == config['selection_receipt_sha256'] and
            selection['selected_model'] == 'xgboost' and selection['threshold'] == config['threshold'] == .5,
            'Selected model/threshold changed')
    checks[str(selection_path.relative_to(ROOT))] = digest(selection_path)
    approved = schema['predictor_order']
    require(len(approved) == 15 and approved == config['features'], 'Frozen feature schema mismatch')
    pred = pd.read_csv(source / 'predictions_2026.csv', float_precision='round_trip', keep_default_na=False)
    features = pd.read_csv(source / 'features_2026.csv', float_precision='round_trip')
    require(list(features.columns) == schema['csv_column_order'], 'Feature column order mismatch')
    features, missing = validate_rows(pred, features, approved)
    frozen = read_json(source / 'prediction_summary.json')
    overall = summarize(pred)
    require(overall['games'] == frozen['games'] == 2000 and
            overall['predicted_positives'] == frozen['predicted_positive'] == 1026 and
            overall['predicted_operational_zeros'] == frozen['predicted_operational_zero'] == 974,
            'Frozen totals mismatch')
    for key in ('mean', 'min', 'max'):
        np.testing.assert_allclose(overall['probability_' + key], frozen['probability_' + key], rtol=0, atol=1e-14)
    for q, expected in frozen['probability_quantiles'].items():
        np.testing.assert_allclose(pred.predicted_probability.quantile(float(q)), expected, rtol=0, atol=1e-14)
    # Pandas average ranks handle ties; Pearson of ranks is Spearman without scipy/model imports.
    rho = float(pred.predicted_probability.rank().corr(pred.prior_price_record_count.rank()))
    np.testing.assert_allclose(rho, frozen['probability_vs_observation_count_spearman'], rtol=0, atol=1e-14)
    coverage = pd.DataFrame([summarize(pred[pred.coverage_group.eq(g)], coverage_group=g,
                                     games_with_missing_predictors=int(pred.loc[pred.coverage_group.eq(g), 'missing_feature_count'].gt(0).sum()))
                             for g in GROUPS])
    saved_coverage = pd.read_csv(source / 'coverage.csv', dtype={'coverage_group': str})
    for i, row in coverage.iterrows():
        saved = saved_coverage.iloc[i]
        require(row.coverage_group == saved.coverage_group and row.games == saved.games and
                row.predicted_positives == saved.predicted_positive and
                row.predicted_operational_zeros == saved.predicted_operational_zero and
                row.games_with_missing_predictors == saved.games_with_missing_features, 'Saved coverage counts mismatch')
        np.testing.assert_allclose([row.predicted_positive_rate * 100, row.probability_mean, row.probability_median],
                                  [saved.predicted_positive_percent, saved.mean_probability, saved.median_probability], rtol=0, atol=1e-13)
    feature_rows = []
    for name in approved:
        for label in (0, 1):
            mask = pred.predicted_operational_label.eq(label)
            n = int(mask.sum()); count = int(missing.loc[mask, name].sum())
            feature_rows.append(dict(feature=name, predicted_operational_label=label,
                                     games=n, missing=count, missing_percent=100 * count / n))
    missing_by_class = pd.DataFrame(feature_rows)
    saved = pd.read_csv(source / 'missingness_by_class.csv', float_precision='round_trip')
    pd.testing.assert_frame_equal(missing_by_class, saved, check_exact=False, rtol=1e-13, atol=1e-13)
    saved_missing = pd.read_csv(source / 'feature_missingness.csv').set_index('feature')
    for name in approved:
        require(int(missing[name].sum()) == saved_missing.loc[name, 'missing'] == schema['missingness'][name],
                'Frozen feature missingness mismatch')
    patterns = []
    for n in sorted(pred.missing_feature_count.unique()):
        group = pred[pred.missing_feature_count.eq(n)]
        names = sorted(set(group.missing_feature_names))
        require(len(names) == 1, 'More than one pattern for a given missing count')
        patterns.append(summarize(group, missing_predictor_count=int(n), missing_feature_names=names[0]))
    patterns = pd.DataFrame(patterns)
    saved_patterns = pd.read_csv(source / 'missingness_patterns.csv')
    np.testing.assert_array_equal(patterns[['missing_predictor_count', 'games', 'predicted_positives']].to_numpy(),
                                  saved_patterns[['missing_features', 'games', 'predicted_positive']].to_numpy())
    status = pd.DataFrame([summarize(pred[pred.missing_feature_count.eq(0)], predictor_status='Complete'),
                           summarize(pred[pred.missing_feature_count.gt(0)], predictor_status='Any missing')])
    require(status.iloc[1].games == 336 and status.iloc[1].predicted_positives == 0, 'Missing-predictor result mismatch')
    missing_coverage = pd.DataFrame([summarize(group, coverage_group=g, predictor_status=s)
                                   for g in GROUPS for s, mask in [('Complete', pred.missing_feature_count.eq(0)),
                                                                  ('Any missing', pred.missing_feature_count.gt(0))]
                                   if len(group := pred[pred.coverage_group.eq(g) & mask])])
    history = pd.read_csv(HISTORY / 'modeling.csv', usecols=['appid', 'sale_year', 'discount_observed', 'evidence_category'])
    require(len(history) == 6000 and not history.duplicated(['appid', 'sale_year']).any() and
            set(history.sale_year) == {2023, 2024, 2025}, 'Historical cohort/year mismatch')
    require(history.discount_observed.isin([0, 1]).all() and
            history.discount_observed.eq(history.evidence_category.eq('A').astype(int)).all() and
            history.evidence_category.isin(['A', 'B', 'D']).all(), 'Historical operational labels mismatch')
    historical_labels = read_json(HISTORY / 'label_distribution.json')['by_year']
    rates = []
    for year, group in history.groupby('sale_year', sort=True):
        require(len(group) == 2000 and set(group.appid) == set(pred.appid), 'Historical membership mismatch')
        positive = int(group.discount_observed.sum())
        require(positive == historical_labels[str(year)]['positives'], 'Historical label totals mismatch')
        rates.append(dict(sale_year=int(year), kind='Historical observed operational labels', games=len(group),
                          operational_positive=positive, operational_zero=len(group) - positive, positive_rate=positive / len(group)))
    rates.append(dict(sale_year=2026, kind='Model predictions; no verified outcomes', games=len(pred),
                      operational_positive=1026, operational_zero=974, positive_rate=1026 / 2000))
    ranks = {}
    for highest, filename in [(True, 'top_10_predicted_positive.csv'), (False, 'bottom_10_predicted_zero.csv')]:
        ranked = rank(pred, highest)
        saved = pd.read_csv(source / filename, float_precision='round_trip', keep_default_na=False)
        require(ranked.appid.tolist() == saved.appid.tolist(), 'Rank/tie order mismatch')
        np.testing.assert_array_equal(ranked.predicted_probability, saved.predicted_probability)
        ranks['top' if highest else 'bottom'] = ranked
    counts, edges = np.histogram(pred.predicted_probability, bins=np.linspace(0, 1, 21))
    saved_hist = pd.read_csv(source / 'probability_histogram.csv', float_precision='round_trip')
    np.testing.assert_array_equal(counts, saved_hist.games)
    histogram = pd.DataFrame(dict(lower_inclusive=edges[:-1], upper=edges[1:],
                                  upper_inclusive=[False] * 19 + [True], games=counts))
    return dict(pred=pred, missing=missing, coverage=coverage, rates=pd.DataFrame(rates),
                patterns=patterns, status=status, missing_coverage=missing_coverage,
                missing_by_class=missing_by_class, ranks=ranks, histogram=histogram,
                overall=overall, rho=rho, input_checksums=checks, source_integrity_notes=serialization_audit)


def figures(destination, data):
    import numpy as np
    from plotting_style import light_style, plt
    from matplotlib.patches import Patch
    captions = []
    pred, coverage = data['pred'], data['coverage']

    def finish(fig, filename, title, caption, recommended=False):
        fig.text(.5, .056, WARNING, ha='center', fontsize=7.5, color='#616970')
        fig.text(.5, .018, '2026 model scores · Fixed threshold 0.50 · Sale outcomes independently unverified',
                 ha='center', fontsize=8, color='#616970')
        fig.tight_layout(rect=(0, .115, 1, 1))
        fig.savefig(destination / filename, dpi=300, facecolor='white', metadata={'Software': 'Steam cohort Phase 8C'})
        plt.close(fig)
        captions.append(dict(filename=filename, title=title, caption=caption, recommended_for_presentation=recommended, dpi=300))

    def grid(ax, axis='y'):
        ax.grid(axis=axis); ax.set_axisbelow(True)

    with light_style():
        fig, ax = plt.subplots(figsize=(8.6, 5.2))
        hist = data['histogram']
        ax.bar(hist.lower_inclusive, hist.games, width=.05, align='edge',
               color=[GRAY if x < .5 else GREEN for x in hist.lower_inclusive], edgecolor='white', linewidth=.6)
        ax.axvline(.5, color='#616970', ls='--', lw=1)
        ax.set(title='2026 · Predicted probability distribution', xlabel='Saved XGBoost probability', ylabel='Games', xlim=(0, 1))
        ax.legend(handles=[Patch(color=GRAY, label='Predicted operational zero · 974'),
                           Patch(color=GREEN, label='Predicted positive · 1,026')], loc='upper right')
        ax.text(.98, .73, 'n = 2,000\nMean 0.4996 · Median 0.7096', transform=ax.transAxes, ha='right', color='#34414B')
        grid(ax)
        finish(fig, '01_probability_histogram.png', 'Predicted probability histogram',
               'Twenty fixed 0.05-wide bins partition all 2,000 saved scores. The dashed line is the frozen 0.50 threshold. '
               'Scores cluster at the low and high ends; their distribution does not establish 2026 calibration.', True)

        fig, ax = plt.subplots(figsize=(8.6, 5.2))
        rates = data['rates']; bars = ax.bar(range(4), rates.positive_rate * 100, color=[BLUE] * 3 + [GREEN], width=.57)
        bars[-1].set_hatch('//')
        for i, row in rates.iterrows():
            ax.text(i, row.positive_rate * 100 + 1.4, f'{row.positive_rate:.2%}\n{row.operational_positive:,}/2,000', ha='center', fontsize=10)
        ax.set(xticks=range(4), xticklabels=['2023\nObserved label', '2024\nObserved label', '2025\nObserved label', '2026\nPredicted class'],
               ylabel='Operational positive rate (%)', ylim=(0, 72), title='Historical operational labels and 2026 predictions')
        ax.legend(handles=[Patch(color=BLUE, label='Historical observed ITAD discount evidence'),
                           Patch(facecolor=GREEN, hatch='//', label='2026 predicted operational positives')], loc='upper left', fontsize=8)
        grid(ax)
        finish(fig, '02_historical_and_predicted_rates.png', 'Historical operational rates versus 2026 predicted rate',
               'Observed operational positive rates are 48.95% (2023), 53.40% (2024) and 49.15% (2025); the 2026 predicted '
               'positive rate is 51.30%. Each denominator is the same 2,000 games. The 2026 bar is a model output, '
               'not an observed sale participation rate; this is not outcome evaluation.', True)

        for kind, filename in [('top', '03_top_10_games.png'), ('bottom', '04_bottom_10_games.png')]:
            ranked = data['ranks'][kind]; highest = kind == 'top'
            fig, ax = plt.subplots(figsize=(10.2, 7.0))
            names = [textwrap.fill(str(row.game_name), 38) + f'  [AppID {row.appid}]' for row in ranked.itertuples()]
            ax.barh(range(10), ranked.predicted_probability, color=GREEN if highest else GRAY, height=.58)
            for i, score in enumerate(ranked.predicted_probability):
                ax.text(score + (.012 if highest else .00012), i, f'{score:.6f}', va='center', fontsize=9)
            ax.set(yticks=range(10), yticklabels=names, xlim=(0, 1.08 if highest else .0105),
                   xlabel='Saved XGBoost probability' + ('' if highest else ' (detail: 0–0.0105)'),
                   title='2026 · ' + ('Ten highest-probability games' if highest else 'Ten lowest-probability games'))
            ax.invert_yaxis(); ax.tick_params(axis='y', labelsize=8.5); grid(ax, 'x')
            finish(fig, filename, 'Top ten games' if highest else 'Bottom ten games',
                   ('Highest' if highest else 'Lowest') + '-probability games, ranked by saved probability and then ascending AppID for ties. '
                   'Labels display six decimal places; ranking uses full precision. ' +
                   ('' if highest else 'The horizontal axis is zoomed to 0–0.0105. ') +
                   'These are model rankings, not verified sale outcomes.')

        fig, ax = plt.subplots(figsize=(8.6, 5.5))
        for g, label, color in zip(GROUPS, DISPLAY, PALETTE):
            group = pred[pred.coverage_group.eq(g)].sort_values('appid')
            ax.scatter(group.prior_price_record_count, group.predicted_probability, s=12, alpha=.4,
                       color=color, edgecolors='none', label=f'{label} observations · n={len(group):,}', rasterized=True)
        ax.set_xscale('symlog', linthresh=1)
        ax.set(title='2026 · Historical observation coverage and predicted probability',
               xlabel='Pre-cutoff price observations (symlog axis; duplicates retained)', ylabel='Saved XGBoost probability', ylim=(-.025, 1.03))
        ax.axhline(.5, color='#BCC3C9', ls='--', lw=.8)
        ax.legend(loc='upper left', bbox_to_anchor=(.01, .82), fontsize=8)
        ax.text(.02, .96, f'Spearman ρ = {data["rho"]:.4f}\nn = 2,000', transform=ax.transAxes, va='top', color='#34414B')
        grid(ax)
        finish(fig, '05_observation_count_vs_probability.png', 'Historical count versus predicted probability',
               'All saved scores are plotted against historical valid pre-cutoff price observation counts. '
               'The symlog axis includes zero. Spearman correlation is 0.8925; ties use average ranks. '
               'Observation density is associated with scores, without establishing causation or complete provider coverage.', True)

        labels = [f'{label} observations\nn={row.games:,}\nPos {row.predicted_positives:,} · Zero {row.predicted_operational_zeros:,}'
                  for label, row in zip(DISPLAY, coverage.itertuples())]
        fig, ax = plt.subplots(figsize=(8.6, 5.6))
        ax.bar(range(4), coverage.predicted_positive_rate * 100, color=PALETTE, width=.57)
        for i, row in coverage.iterrows():
            ax.text(i, row.predicted_positive_rate * 100 + 1.5, f'{row.predicted_positive_rate:.2%}', ha='center')
        ax.set(xticks=range(4), xticklabels=labels, ylabel='Predicted operational positive rate (%)', ylim=(0, 100),
               title='2026 · Predicted positive rate by historical coverage')
        grid(ax)
        finish(fig, '06_positive_rate_by_coverage.png', 'Predicted positive rate by observation coverage',
               'Groups partition the original cohort: 0, 1–9, 10–29 and 30+ observations. Tick labels give sample sizes '
               'and predicted positive (Pos) / operational-zero (Zero) counts. Rates are 0.00%, 1.19%, 25.08% and 84.54%; '
               'they are prediction rates, not actual sale participation rates.', True)

        fig, ax = plt.subplots(figsize=(8.6, 5.6))
        boxes = ax.boxplot([pred.loc[pred.coverage_group.eq(g), 'predicted_probability'] for g in GROUPS],
                           patch_artist=True, tick_labels=[f'{label} observations\nn={int(row.games):,}' for label, row in zip(DISPLAY, coverage.itertuples())],
                           whis=(0, 100), widths=.48, medianprops={'color': '#34414B', 'linewidth': 1.5},
                           whiskerprops={'color': GRAY}, capprops={'color': GRAY}, boxprops={'edgecolor': GRAY})
        for box, color in zip(boxes['boxes'], PALETTE): box.set_facecolor(color); box.set_alpha(.55)
        ax.scatter(range(1, 5), coverage.probability_mean, marker='D', s=30, color='#34414B', label='Mean', zorder=3)
        ax.axhline(.5, color='#BCC3C9', ls='--', lw=.8)
        ax.set(title='2026 · Score distributions by historical coverage', ylabel='Saved XGBoost probability', ylim=(-.025, 1.03))
        ax.legend(loc='upper left'); grid(ax)
        finish(fig, '07_probability_by_coverage.png', 'Probability distribution by observation coverage',
               'Boxes show the 25th–75th percentiles; horizontal lines show medians, diamonds show means, and whiskers '
               'show full minimum–maximum ranges. The dashed line is 0.50. Complete subgroup quantiles accompany the figure. '
               'Coverage groups describe available historical observations, not verified sale outcomes.')

        fig, axes = plt.subplots(1, 2, figsize=(11.5, 6.3), gridspec_kw={'width_ratios': [1.65, 1]})
        ax = axes[0]
        features = [f for f in data['missing'].columns if data['missing'][f].any()]
        y = np.arange(len(features))
        for label, offset, color, name in [(0, -.17, GRAY, 'Predicted zero · n=974'), (1, .17, GREEN, 'Predicted positive · n=1,026')]:
            rows = data['missing_by_class'].set_index(['feature', 'predicted_operational_label'])
            values = [rows.loc[(f, label), 'missing_percent'] for f in features]
            ax.barh(y + offset, values, height=.3, color=color, label=name)
            for i, value in enumerate(values): ax.text(value + .8, i + offset, f'{value:.1f}%', va='center', fontsize=8)
        ax.set(yticks=y, yticklabels=[FEATURE_LABELS[f] for f in features], xlim=(0, 44),
               xlabel='Missing within predicted class (%)', title='Feature missingness by predicted class')
        ax.invert_yaxis(); ax.legend(loc='lower right', fontsize=8); grid(ax, 'x')
        ax = axes[1]; status = data['status']
        ax.bar(range(2), status.predicted_operational_zeros, color=GRAY, label='Predicted operational zero')
        ax.bar(range(2), status.predicted_positives, bottom=status.predicted_operational_zeros, color=GREEN, label='Predicted positive')
        for i, row in status.iterrows():
            ax.text(i, row.predicted_operational_zeros / 2, f'{row.predicted_operational_zeros:,} zeros', ha='center', color='white', fontsize=9)
            if row.predicted_positives:
                ax.text(i, row.predicted_operational_zeros + row.predicted_positives / 2, f'{row.predicted_positives:,} positives', ha='center', color='white', fontsize=9)
        ax.set(xticks=range(2), xticklabels=['Complete\nn=1,664', 'Any missing\nn=336'], ylabel='Games', ylim=(0, 1900), title='Feature completeness and predictions')
        grid(ax)
        finish(fig, '08_missingness_vs_predicted_class.png', 'Missingness versus predicted class',
               'Left: missing percentages use predicted-class denominators (974 zeros, 1,026 positives); eight remaining '
               'predictors have no missing values in either class. Right: all 336 games with missing predictors are predicted '
               'operational zero, alongside 638 complete-vector zeros. Missingness is associated with sparse coverage and '
               'predicted class; it is not evidence of verified nonparticipation.', True)
    return captions


def narrative(data, captions):
    s = data['status'].iloc[1]; p = data['overall']
    index = '| Figure | File | Recommended |\n| --- | --- | --- |\n' + '\n'.join(
        f'| {r["title"]} | [{r["filename"]}]({r["filename"]}) | {"Yes" if r["recommended_for_presentation"] else "Supplement"} |' for r in captions)
    findings = f'''# Phase 8C key findings

**{WARNING}**

- Frozen XGBoost predictions cover exactly 2,000 games: 1,026 positives (51.3%) and 974 operational zeros (48.7%), at the unchanged 0.50 threshold.
- Mean probability is {p['probability_mean']:.6f}; median is {p['probability_median']:.6f}; range is {p['probability_min']:.6f}–{p['probability_max']:.6f}. The interquartile range is {p['probability_q25']:.6f}–{p['probability_q75']:.6f}. There are 754 scores below 0.10 and 656 at or above 0.90. These distributions do not establish calibration.
- Historical observed operational positive rates are 48.95% in 2023, 53.40% in 2024 and 49.15% in 2025. The 51.30% 2026 figure is a predicted class rate. Historical observed labels and 2026 predictions describe different quantities.
- Observation-count/score Spearman is {data['rho']:.4f}. The 0, 1–9, 10–29 and 30+ groups have 81, 505, 295 and 1,119 games; predicted positive rates are 0.00%, 1.19%, 25.08% and 84.54%. The 30+ group supplies 946/1,026 predicted positives (92.2%). This is a descriptive association, not a causal attribution or an actual participation estimate.
- All 336 games with missing predictors receive predicted operational zero. Their mean score is {s.probability_mean:.6f}, median {s.probability_median:.6f}, and range {s.probability_min:.6f}–{s.probability_max:.6f}. Their observation counts range from {s.observation_count_min:.0f} to {s.observation_count_max:.0f}, with median {s.observation_count_median:.0f}.
- Missingness has two exact patterns: 255 games have three discount-derived nulls and 1–4 price observations (within the 1–9 group); 81 games have seven nulls and zero price observations. The missing-vector score 95th percentile is {s.probability_p95:.6f}; even the maximum {s.probability_max:.6f} is below 0.50. All missing-vector games have zero qualifying prior discount observations. This describes available evidence; missing data does not verify absence of real discounts.
- All 1,026 predicted positives have complete vectors. Among the 974 predicted zeros, 638 have complete vectors (65.5%), 255 have three nulls and 81 have seven nulls. A complete vector therefore does not imply a predicted positive. No new imputation, missingness model, threshold change or model inference is used here.
- Highest and lowest score rankings have ties; the frozen ascending-AppID tie break is retained. Displayed precision is not a claim of outcome certainty.

Recommended core presentation: figures 01, 02, 05, 06 and 08. Figures 03–04 are ranking supplements; 07 supplies subgroup distribution detail. Keep coverage and missingness beside any aggregate prediction result.

## Limits on interpretation

The cutoff is **2026-10-01T17:00:00Z**. All history receipts were collected after cutoff (October 5–13); event-time filtering cannot establish provider availability before cutoff. No vector is independently proven available at that time. These are retrospective scores, not validated prospective forecasts.

Historical A→1 and B/D→0 labels describe observed ITAD Autumn Sale discount evidence. Operational zeros do not prove nonparticipation. Missing histories or predictors do not establish verified nonparticipation. Observation counts retain duplicates and measure returned observation density, not distinct sales, campaigns, or discounted days.

**No independent 2026 outcome evaluation has been conducted.** No verified 2026 sale outcome is inferred; no accuracy, confusion, ROC, calibration, or participation-rate evaluation is computed. The 2026 probability distribution is not evidence that probabilities are calibrated for actual sale outcomes.

Repeated games across historical years, retrospective cohort selection, provider backfill, source release-date uncertainty, historical timestamp/shop ambiguities, and feature values outside historical training ranges remain limitations. The strong coverage/score association does not disentangle provider recording density from pricing behavior. Historical performance belongs to the earlier evaluated fit, not an independently evaluated 2026 refit.

The figures and summaries are ready for a descriptive final research synthesis with these limitations and the source serialization caveat prominent. They do not establish verified 2026 participation or independently evaluated predictive performance.

## Preexisting Phase 8B CSV provenance caveat

The prediction CSV differs from its original manifest hash. An in-memory reconstruction using the frozen availability-table row order and original game names exactly reproduces the original SHA-256. All probabilities, classes, cohort IDs and other fields are unchanged. Two names differ: AppID 1518000 is currently “CooKing: Around the C” versus frozen “CooKing: Around the World”; AppID 2402900 is currently “Hollow Knight” versus frozen “Hoboman”. This does not add either named title to the cohort or validate its identity. The source CSV, manifests and journal are preserved without repair. Figures and tables read the current source; neither renamed row appears in the top/bottom ten. See `source_integrity_notes.json` for exact hashes. This discrepancy is separate from the known 218/219 historical protected-baseline agreement.
'''
    readme = f'''# Phase 8C — 2026 prediction visualizations

**{WARNING}**

Eight separate 300-DPI PNGs use only the existing frozen Phase 8B XGBoost prediction CSV and feature/missingness/coverage diagnostics, plus frozen historical operational labels. Exactly 2,000 games are retained. No model is loaded, trained, queried, tuned, or changed; no new predictions or outcome labels are generated. The threshold remains 0.50.

**Cutoff: {CUTOFF}. Provider availability before cutoff cannot be established. Operational zeros do not prove nonparticipation. No independent 2026 outcome evaluation has been conducted.**

## Figure index

{index}

See [figure_captions.md](figure_captions.md), [figure_captions.csv](figure_captions.csv), [figure_index.csv](figure_index.csv), and [key_findings.md](key_findings.md). Every figure embeds the retrospective warning. White backgrounds, DejaVu Sans, minimal gridlines/borders, and restrained colors reuse `src/plotting_style.py` from Phase 7B. Predicted positives use Phase 7B XGBoost green; operational zeros use gray; historical observed rates use blue. Coverage groups have consistent gray/blue/orange/green colors.

## Supporting data

- `prediction_distribution.csv`: totals and full score/observation distribution summaries (population SD; pandas linear-interpolated quantiles).
- `probability_histogram.csv`: twenty fixed bins, left-inclusive/right-exclusive except the last bin includes 1.00.
- `historical_and_predicted_rates.csv`: 2023–2025 observed operational labels and separate 2026 predicted classes.
- `coverage_summary.csv`: 0, 1–9, 10–29, 30+ groups; sample sizes, predicted counts, rates, missing-vector counts, score/count summaries.
- `top_10_games.csv`, `bottom_10_games.csv`: saved-score ranks, ascending AppID ties; no outcome verification.
- `missingness_by_predicted_class.csv`: all 15 predictors, class denominators, missing counts and percentages.
- `missingness_patterns.csv`, `missingness_status_summary.csv`, `missingness_coverage_summary.csv`: exact null patterns, counts, class and score/count distributions.
- `missing_predictor_games.csv`: all 336 affected games, including observation counts, scores, classes and null names; sourced from saved prediction diagnostics.
- `input_checksums.json`: actual frozen-input hashes. `source_integrity_notes.json`: the proven preexisting prediction-CSV order/two-name serialization discrepancy, with original/current hashes. `figure_manifest.json`: PNG dimensions, DPI, background checks and hashes. `checksums.json`: all delivered files except itself.
- `reproduction.json`: independent render and byte comparisons. `validation.json`: guards, frozen-data reconciliation, dependency versions, code hashes and integrity. `phase_start_checksums.json`: phase-start snapshot. `offline_test_results.json`: test receipt.

Rate fields named `predicted_positive_rate` and `positive_rate` are proportions from 0 to 1; plot annotations use percentages. Predicted rates are not actual sale participation rates. Missing CSV cells remain null; none are converted to zeros. Count fields describe historical observations, not sale outcomes. Mean/median probabilities are descriptive saved model scores.

## Reproduce offline

From the repository root, use a **fresh destination**; existing directories are refused:

```sh
env -u ITAD_API_KEY PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp \\
  /usr/bin/python3 -B src/visualize_cohort_2026.py \\
  --output-dir reports/cohort_2000_2026_visualizations_reproduction

env -u ITAD_API_KEY PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp \\
  /usr/bin/python3 -B tests/run_visualization_2026_offline.py \\
  --artifacts reports/cohort_2000_2026_visualizations \\
  --results /private/tmp/steam-phase8c-tests.json
```

The generator checks frozen Phase 8B and historical input manifests, proves the prediction CSV's preexisting order/two-name serialization discrepancy by reproducing its original hash in memory, reconciles every figure source against saved summaries, and independently renders all figure/summary payloads again in temporary runtime storage. Every PNG and supporting CSV/Markdown must reproduce byte-for-byte in the recorded environment. Cross-version font/rendering changes can change PNG bytes; dependency versions are recorded.

Network, external commands, machine-learning/prediction modules and model-deserialization imports are blocked. Writes are restricted to the fresh output directory and a temporary plotting cache; bytecode writes are disabled. Test runners exclude all model-fitting tests, including synthetic refit tests from Phase 8B. The existing Phase 7B pure visualization tests may be run separately using `tests/run_visualization_offline.py`.

## Interpretation and integrity

Historical observed operational labels, 2026 predictions, historical observation coverage and verified outcomes are distinct. No verified 2026 outcomes are supplied or evaluated. See the complete [key findings, methodological limitations and source provenance caveat](key_findings.md). Two game-name edits and row reordering predate this phase; original scores/classes/membership are proven unchanged. The current prediction CSV and its stale manifest entry are preserved without repair.

All preexisting project files in the recorded phase-start snapshot must retain their bytes, including Phase 6/7/8 artifacts, models, caches, cohort files, journal entries, and protected files. The 219-file protected historical baseline remains 218/219, with the known ordering-only mismatch in `data/intermediate/autumn_sale_evidence_records.csv` preserved without repair. Phase-start preservation and historical-baseline agreement are checked separately. No HTTP requests, training, inference, tuning, threshold changes, cohort expansion, historical-data repair, or journal changes are performed.
'''
    return readme, findings, '# Figure index\n\n' + index + '\n'


def render(destination, data):
    import pandas as pd
    destination.mkdir()
    write_json(destination / 'source_integrity_notes.json', data['source_integrity_notes'])
    captions = figures(destination, data)
    for filename, frame in {
        'prediction_distribution.csv': pd.DataFrame([dict(**data['overall'], spearman_score_vs_observation_count=data['rho'])]),
        'probability_histogram.csv': data['histogram'], 'historical_and_predicted_rates.csv': data['rates'],
        'coverage_summary.csv': data['coverage'], 'missingness_by_predicted_class.csv': data['missing_by_class'],
        'missingness_patterns.csv': data['patterns'], 'missingness_status_summary.csv': data['status'],
        'missingness_coverage_summary.csv': data['missing_coverage'],
        'missing_predictor_games.csv': data['pred'].loc[data['pred'].missing_feature_count.gt(0),
            ['appid', 'game_name', 'prior_price_record_count', 'prior_discount_count', 'coverage_group',
             'predicted_probability', 'predicted_operational_label', 'missing_feature_count', 'missing_feature_names']],
        'top_10_games.csv': data['ranks']['top'], 'bottom_10_games.csv': data['ranks']['bottom'],
        'figure_captions.csv': pd.DataFrame(captions),
        'figure_index.csv': pd.DataFrame(captions)[['filename', 'title', 'recommended_for_presentation', 'dpi']],
    }.items(): write_csv(destination / filename, frame)
    readme, findings, index = narrative(data, captions)
    for filename, body in [('README.md', readme), ('key_findings.md', findings), ('figure_index.md', index),
                            ('figure_captions.md', '# Figure captions\n\n**' + WARNING + '**\n\n' + '\n\n'.join(
                                f'**{r["filename"]} — {r["title"]}.** {r["caption"]}' for r in captions) + '\n')]:
        (destination / filename).write_text(body, encoding='utf-8')
    return captions


def install_guard(destination, runtime):
    forbidden_modules = {'sklearn', 'xgboost', 'joblib', 'pickle', 'predict_cohort_2026', 'train_cohort_temporal', 'requests', 'httpx'}

    def allowed(value, dir_fd=None):
        if not isinstance(value, (str, bytes, os.PathLike)): return True
        p = Path(os.fsdecode(value))
        if not p.is_absolute() and isinstance(dir_fd, int) and dir_fd >= 0:
            if sys.platform == 'darwin':
                import fcntl
                parent = fcntl.fcntl(dir_fd, 50, b'\0' * 1024).split(b'\0', 1)[0]
                p = Path(os.fsdecode(parent)) / p
            else: p = Path(os.readlink(f'/proc/self/fd/{dir_fd}')) / p
        p = p.resolve()
        return p.is_relative_to(destination) or p.is_relative_to(runtime)

    def guard(event, args):
        if event in {'socket.connect', 'socket.getaddrinfo', 'socket.bind', 'urllib.Request'}:
            raise RuntimeError('Offline visualization forbids network')
        if event in {'subprocess.Popen', 'os.system', 'os.posix_spawn'}:
            raise OSError('Offline visualization forbids external commands')
        if event == 'import' and args[0].split('.')[0] in forbidden_modules:
            raise RuntimeError('Offline visualization forbids model/prediction imports')
        if event == 'pickle.find_class': raise RuntimeError('Model deserialization forbidden')
        if event == 'open':
            writing = (isinstance(args[1], str) and any(c in args[1] for c in 'wax+')) or (
                isinstance(args[2], int) and args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            if writing: require(allowed(args[0]), 'Writes confined to fresh output/runtime')
        if event in {'os.remove', 'os.rmdir', 'os.mkdir', 'os.chmod', 'os.utime', 'os.rename', 'os.link', 'os.symlink'}:
            if event in {'os.rename', 'os.link'}: targets = [(args[0], args[2]), (args[1], args[3])]
            elif event == 'os.symlink': targets = [(args[1], args[2])]
            elif event in {'os.remove', 'os.rmdir'}: targets = [(args[0], args[1])]
            elif event in {'os.mkdir', 'os.chmod'}: targets = [(args[0], args[2])]
            else: targets = [(args[0], None)]
            require(all(allowed(p, fd) for p, fd in targets), 'Mutations confined to fresh output/runtime')
    sys.addaudithook(guard)


def inventory():
    return {str(p.relative_to(ROOT)): digest(p) for p in sorted(ROOT.rglob('*')) if p.is_file() and
            not any(part in {'.git', '.venv', '__pycache__'} for part in p.relative_to(ROOT).parts)}


def verify_preservation(before):
    require(all((ROOT / name).is_file() and digest(ROOT / name) == sha for name, sha in before.items()),
            'Preexisting project artifact changed')
    baseline = read_json(ROOT / 'tests/scalable_artifact_hashes.json')
    mismatches = [name for name, row in baseline.items() if digest(ROOT / name) != row['sha256']]
    require(len(baseline) == 219 and mismatches == [MISMATCH], 'Historical baseline mismatch changed')
    require(digest(ROOT / MISMATCH) == read_json(SOURCE / 'validation.json')['existing_baseline_mismatch_preserved_sha256'],
            'Known historical mismatch was modified')
    require(all(name in before for name in baseline), 'Incomplete protected snapshot')
    return dict(preexisting_files_preserved=len(before), protected_artifacts_preserved=219,
                historical_baseline_matches=218, historical_baseline_total=219,
                existing_baseline_mismatch=MISMATCH, existing_baseline_mismatch_sha256=digest(ROOT / MISMATCH),
                historical_baseline_mismatch_preserved_without_repair=True)


def figure_manifest(destination):
    from PIL import Image
    rows = []
    for path in sorted(destination.glob('*.png')):
        with Image.open(path) as im:
            dpi = im.info.get('dpi', (0, 0))
            require(all(abs(v - 300) < .01 for v in dpi), 'PNG is not 300 DPI')
            require(im.width >= 1920 and im.height >= 1400, 'Figure dimensions too small')
            rgb = im.convert('RGB')
            require(all(rgb.getpixel(c) == (255, 255, 255) for c in
                        [(0, 0), (im.width - 1, 0), (0, im.height - 1), (im.width - 1, im.height - 1)]), 'Figure background not white')
            rows.append(dict(filename=path.name, width_pixels=im.width, height_pixels=im.height,
                             dpi=list(dpi), white_background_corners=True, sha256=digest(path)))
    require(len(rows) == 8, 'Eight individual figures required')
    return rows


def main():
    sys.dont_write_bytecode = True
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--phase-start-checksums', type=Path, help='Optional earlier phase-start SHA-256 snapshot')
    parser.add_argument('--test-results', type=Path, help='Optional preflight offline test receipt')
    args = parser.parse_args()
    destination = args.output_dir.absolute()
    require(not any(p.is_symlink() for p in [destination, *destination.parents]), 'Symlink output refused')
    destination = destination.resolve()
    require(not destination.exists() and destination.parent.is_dir(), 'Use a fresh output directory with an existing parent')
    require(not destination.is_relative_to(ROOT) or destination.parent == ROOT / 'reports', 'Repository output must be a new reports directory')
    require('ITAD_API_KEY' not in os.environ, 'Run with env -u ITAD_API_KEY')
    runtime = Path(tempfile.mkdtemp(prefix='steam-phase8c-', dir='/private/tmp'))
    os.environ['MPLCONFIGDIR'] = str(runtime / 'mpl'); tempfile.tempdir = str(runtime)
    # Pandas internally imports pickle for unrelated IO support. Import it before
    # the guard; no deserializer or model artifacts are used. Model-class lookup remains blocked.
    import numpy
    import pandas
    install_guard(destination, runtime)
    before = read_json(args.phase_start_checksums) if args.phase_start_checksums else inventory()
    preflight = read_json(args.test_results) if args.test_results else None
    if preflight: require(preflight['passed'] and preflight['no_models_trained'] and preflight['no_model_predictions'], 'Invalid test receipt')
    verify_preservation(before)
    data = build()
    captions = render(destination, data)
    second = runtime / 'independent-render'
    # Reload every frozen table rather than sharing calculated plot data.
    render(second, build())
    payload = sorted(p.name for p in destination.iterdir())
    require(all(digest(destination / name) == digest(second / name) for name in payload), 'Independent render differs')
    write_json(destination / 'reproduction.json', dict(independent_frozen_csv_reload=True, byte_identical=True,
        compared_files=payload, png_files=8, csv_files=sum(n.endswith('.csv') for n in payload), no_models_loaded=True))
    write_json(destination / 'input_checksums.json', data['input_checksums'])
    write_json(destination / 'figure_manifest.json', figure_manifest(destination))
    write_json(destination / 'phase_start_checksums.json', before)
    if preflight: write_json(destination / 'offline_test_results.json', preflight)
    integrity = verify_preservation(before)
    write_json(destination / 'validation.json', dict(**integrity, games=2000, figures=len(captions), threshold=.5,
        selected_model='xgboost', no_network=True, api_calls=0, no_models_loaded=True, no_models_trained=True,
        no_model_predictions=True, historical_dataset_modified=False, cohort_expanded=False,
        frozen_counts_and_scores_reconciled=True, coverage_and_missingness_reconciled=True,
        phase8b_prediction_csv_manifest_byte_match=False, phase8b_prediction_csv_original_serialization_reconciled=True,
        phase8b_prediction_csv_order_and_two_name_discrepancy_preserved=True,
        independent_2026_outcome_evaluation=False, retrospective_description=WARNING, cutoff_utc=CUTOFF,
        point_in_time_provider_availability_proven=False, independent_payload_reproduction=True,
        versions={name: metadata.version(name) for name in ('numpy', 'pandas', 'matplotlib', 'Pillow')},
        python_version=sys.version, source_sha256={name: digest(ROOT / name) for name in
            ['src/visualize_cohort_2026.py', 'src/plotting_style.py', 'tests/test_visualization_2026.py', 'tests/run_visualization_2026_offline.py']}))
    write_json(destination / 'checksums.json', {p.name: digest(p) for p in sorted(destination.iterdir()) if p.is_file()})
    print(json.dumps(dict(figures=8, payload_files_reproduced=len(payload), **integrity)))


if __name__ == '__main__': main()
