"""Freeze original operational targets, existing features and chronological splits offline."""
import argparse
from collections import Counter
import csv
import json
import math
import os
from pathlib import Path
import sys

from cohort_io import ROOT, digest, load_cohort, read_csv, read_json, require
import cohort_pipeline as pipeline
from incremental_itad import Journal, resolve_cache

FEATURES = pipeline.features_core
DATASET_FIELDS = (*FEATURES.FIELDS, 'discount_observed', 'evidence_category')
POLICY = 'operational_observed_v1'


def assemble_dataset(result):
    """Join already calculated features to targets; no category/target predictors."""
    labels = {(int(r['appid']), r['sale_year']): r for r in result['labels']}
    require(len(labels) == len(result['labels']), 'Duplicate labels')
    feature_keys = {(r['appid'], r['sale_year']) for r in result['features']}
    require(len(feature_keys) == len(result['features']) and feature_keys == set(labels), 'Feature/label join mismatch')
    rows = []
    for feature in sorted(result['features'], key=lambda r: (r['appid'], r['sale_year'])):
        label = labels[(feature['appid'], feature['sale_year'])]
        require(label['discount_observed'] in {0, 1}, 'Unknown targets cannot enter this complete operational dataset')
        require(label['sale_start_utc'] == feature['prediction_cutoff_utc'], 'Target/feature cutoff mismatch')
        row = {name: feature[name] for name in FEATURES.FIELDS}
        row.update(discount_observed=label['discount_observed'], evidence_category=label['evidence_category'])
        rows.append(row)
    return rows


def validate_rows(rows, windows, appids):
    expected = {(int(appid), year) for appid in appids for year in windows}
    require(len(rows) == len(expected) and {(r['appid'], r['sale_year']) for r in rows} == expected,
            'Missing or duplicate game-year rows')
    require(set(windows) == {2023, 2024, 2025}, 'Unexpected target years')
    integer = set(FEATURES.STATIC) | {'prior_price_record_count', 'prior_discount_count',
                                   'has_prior_price_history', 'has_prior_discount_observation'}
    null_allowed = set(FEATURES.PRICE) - integer
    for r in rows:
        require(tuple(r) == DATASET_FIELDS, 'Unexpected dataset columns or order')
        require(type(r['appid']) is int and r['appid'] > 0 and type(r['sale_year']) is int, 'Invalid identity types')
        require(r['prediction_cutoff_utc'] == pipeline.audit.fmt(windows[r['sale_year']][2]), 'Incorrect UTC cutoff')
        require(r['evidence_category'] in {'A', 'B', 'D'} and type(r['discount_observed']) is int and
                r['discount_observed'] == (1 if r['evidence_category'] == 'A' else 0), 'Operational mapping mismatch')
        require(type(r['audit_release_hour_uncertain']) is int and r['audit_release_hour_uncertain'] in {0, 1}, 'Invalid audit flag')
        for name in FEATURES.ALLOWLIST:
            value = r[name]
            if value is None:
                require(name in null_allowed, 'Required feature is null: '+name)
                continue
            require(type(value) in {int, float} and math.isfinite(value), 'Nonfinite/nonnumeric feature: '+name)
            require(name not in integer or type(value) is int, 'Noninteger feature: '+name)
            require(value >= 0, 'Negative feature: '+name)
        require(1 <= r['release_year'] <= r['sale_year'] and 1 <= r['release_month'] <= 12 and
                1 <= r['release_quarter'] <= 4 and r['release_quarter'] == (r['release_month']-1)//3+1,
                'Invalid release components')
        count, discounts = r['prior_price_record_count'], r['prior_discount_count']
        require(0 <= discounts <= count, 'Discount count exceeds price count')
        require(r['has_prior_price_history'] == int(count > 0) and
                r['has_prior_discount_observation'] == int(discounts > 0), 'History flags/counts disagree')
        require(r['prior_discount_rate'] is None if not count else
                r['prior_discount_rate'] is not None and math.isclose(r['prior_discount_rate'], discounts/count), 'Invalid discount ratio')
        for name in ('days_since_last_price_record', 'days_since_last_discount'):
            if r[name] is not None:
                require(r[name] > 0, 'Recency is not strictly pre-cutoff')
        for name in ('max_prior_discount_pct', 'mean_prior_discount_pct', 'last_observed_discount_pct'):
            require(r[name] is None or 0 <= r[name] <= 100, 'Discount percentage out of range')
        if not count:
            require(all(r[name] is None for name in null_allowed), 'No-history missing values were filled')
        if not discounts:
            require(all(r[name] is None for name in ('days_since_last_discount', 'max_prior_discount_pct', 'mean_prior_discount_pct')),
                    'No-discount missing values were filled')
    return dict(game_year_rows=len(rows), unique_games=len(appids), duplicate_or_missing_pairs=0,
                approved_feature_count=len(FEATURES.ALLOWLIST), dataset_columns=len(DATASET_FIELDS),
                numeric_types_and_ranges_valid=True, explicit_nulls_preserved=True, cutoffs_and_labels_valid=True)


def distribution(rows):
    cats = Counter(r['evidence_category'] for r in rows)
    return dict(rows=len(rows), unique_games=len({r['appid'] for r in rows}),
                positives=sum(r['discount_observed'] == 1 for r in rows),
                operational_zeros=sum(r['discount_observed'] == 0 for r in rows), unknowns=0,
                evidence_categories={c: cats[c] for c in 'ABCD'})


def temporal_protocol(rows):
    require(set(r['sale_year'] for r in rows) == {2023, 2024, 2025}, 'Expected three chronological years')
    require(len({(r['appid'], r['sale_year']) for r in rows}) == len(rows), 'Duplicate split keys')
    selections = {'final_training': [r for r in rows if r['sale_year'] in {2023, 2024}],
                  'held_out_test': [r for r in rows if r['sale_year'] == 2025],
                  'development_training': [r for r in rows if r['sale_year'] == 2023],
                  'development_validation': [r for r in rows if r['sale_year'] == 2024]}
    repeated = lambda left, right: len({r['appid'] for r in selections[left]} & {r['appid'] for r in selections[right]})
    membership = [dict(appid=r['appid'], sale_year=r['sale_year'],
                       final_role='held_out_test' if r['sale_year'] == 2025 else 'training',
                       development_role={2023: 'training', 2024: 'validation', 2025: 'excluded'}[r['sale_year']]) for r in rows]
    protocol = dict(protocol_version='cohort_2000_chronological_v1', label_policy=POLICY,
                    final_training_years=[2023, 2024], held_out_test_year=2025,
                    development_training_years=[2023], development_validation_year=2024,
                    splits={key: distribution(values) for key,values in selections.items()},
                    final_train_test_game_overlap=repeated('final_training', 'held_out_test'),
                    development_train_validation_game_overlap=repeated('development_training', 'development_validation'),
                    split_unit='game-year; deterministic chronological membership, not random or game-disjoint',
                    previous_cohort_evaluation_groups='Preserved in frozen cohort; not used by this explicitly requested temporal protocol',
                    evaluation_scope='Later-sale generalization for previously represented games, not unseen-game generalization',
                    test_inspection='2025 labels have already been audited. Freeze this test for model selection purposes; it is not an untouched confirmatory holdout.',
                    preprocessing=dict(development_fit_on='2023 training rows only; transform 2024 without fitting',
                                       final_fit_on='Fresh preprocessing fitted on 2023+2024 training rows only; transform 2025 without fitting',
                                       learned_steps=['imputation', 'scaling', 'encoding if applicable', 'feature selection if applicable'],
                                       missing_values='No preparation-time imputation or zero filling',
                                       all_missing_training_columns='Existing logistic core excludes all-missing training columns using training data only. Tree core retains them with documented structural-zero imputation. Record the chosen policy before fitting.',
                                       fitted_during_preparation=False),
                    selection_rules='Use only 2023->2024 development scores for any authorized model/parameter selection; freeze candidates before consulting 2025 metrics. No test-driven preprocessing, tuning, threshold optimization, calibration, early stopping, or feature changes.',
                    metrics=['ROC-AUC', 'average precision', 'log loss', 'Brier score', 'accuracy', 'precision', 'recall', 'F1', 'confusion matrix'],
                    probability_threshold=0.5, random_seed=42,
                    dependence='Three observations per game are dependent; do not claim 6000 independent samples. Any future uncertainty analysis must account for game clusters.',
                    no_models_trained=True)
    return membership, protocol


def missingness(rows):
    report = []
    for year in (2023, 2024, 2025, 'all'):
        selected = rows if year == 'all' else [r for r in rows if r['sale_year'] == year]
        for name in FEATURES.ALLOWLIST:
            values = [r[name] for r in selected if r[name] is not None]
            missing = len(selected)-len(values)
            report.append(dict(sale_year=year, feature=name, rows=len(selected), missing=missing,
                               missing_percent=100*missing/len(selected), observed=len(values),
                               observed_min=min(values) if values else None, observed_max=max(values) if values else None))
    return report


def build(cohort, cache_dir, reuse_dirs):
    games = load_cohort(cohort)
    require(len(games) == 2000, 'Expected frozen 2000-game cohort')
    caches = {g['AppID']: resolve_cache(g['AppID'], cache_dir, reuse_dirs) for g in games}
    require(all(status == 'valid' for _,status,_,_ in caches.values()), 'Incomplete/invalid cache')
    result = pipeline.evidence(games, caches, label_policy='operational')
    saved = read_csv(ROOT/'reports/cohort_2000_operational/operational_labels.csv')
    require(pipeline.strings(result['labels']) == saved, 'Labels differ from Phase 6B')
    prior = read_json(ROOT/'reports/cohort_2000_operational/operational_summary.json')
    prior_provenance = read_json(ROOT/'reports/cohort_2000_operational/feature_provenance.json')
    index = lambda rows: {(r['appid'], r['sale_year']): r for r in rows}
    require(len(prior_provenance) == len(result['provenance']) and
            index(result['provenance']) == index(prior_provenance), 'Feature provenance differs from Phase 6B')
    rows = assemble_dataset(result)
    validation = validate_rows(rows, result['windows'], {g['AppID'] for g in games})
    require(distribution(rows)['positives'] == 3030 and distribution(rows)['operational_zeros'] == 2970, 'Unexpected target totals')
    for name in ('src/06_build_operational_labels.py', 'src/07_build_autumn_features.py', 'src/autumn_sale_calendar.json'):
        require(digest(ROOT/name) == prior['source_sha256'][name], 'Approved implementation changed since Phase 6B')
    uses = violations = 0
    by_key = {(r['appid'], r['sale_year']): r for r in rows}
    by_game = {int(g['AppID']): g for g in games}
    for trace in result['provenance']:
        raw = caches[str(trace['appid'])][0]['history_response']
        cutoff = result['windows'][trace['sale_year']][2]
        require(trace['cutoff_violations'] == 0, 'Recorded feature cutoff violation')
        for index in trace['valid_prior_raw_indices']:
            require(raw[index]['shop']['id'] == 61, 'Non-Steam predictor')
            violations += int(pipeline.audit.utc_stamp(raw[index]['timestamp']) >= cutoff)
            uses += 1
        # Independent recomputation with only earlier raw observations.
        earlier = [record for record in raw if pipeline.audit.utc_stamp(record['timestamp']) < cutoff]
        parsed, issues, other = pipeline.audit.parse_history(earlier)
        require(not issues and not other, 'Silent feature parsing failures')
        selected, _ = FEATURES.build_features([(trace['appid'], trace['sale_year'])],
                   {trace['appid']: by_game[trace['appid']]},
                   {trace['appid']: parsed}, result['windows'])
        require(all(selected[0][name] == by_key[(trace['appid'], trace['sale_year'])][name] for name in FEATURES.FIELDS),
                'Feature values depend on at/after-cutoff observations')
    require(violations == 0, 'Direct future leakage')
    require(not any(pair['cache_status'] != 'ok' for pair in result['pairs']), 'Silent cache parsing failure')
    validation.update(cutoff_violations=0, pre_cutoff_record_uses_verified=uses,
                      future_record_removal_invariant_pairs=len(rows), phase6b_labels_and_provenance_identical=True,
                      approved_implementation_hashes_match_phase6b=True, record_parsing_failures=0,
                      no_preprocessing_fitted=True, no_models_trained=True, no_network=True,
                      operational_zero_semantics='No discount observed in available evidence; not verified nonparticipation',
                      historical_availability='Retrospective timestamps do not prove contemporaneous provider availability; reported release date accuracy/stability assumed')
    membership, protocol = temporal_protocol(rows)
    manifest = FEATURES.feature_manifest()
    for entry in manifest['features']:
        if entry['feature_name'] in FEATURES.STATIC or entry['feature_name'] in FEATURES.AUDIT_FIELDS:
            entry['source'] = 'frozen cohort release_date; existing deterministic master/pilot selection metadata'
    manifest.update(dataset_fields=list(DATASET_FIELDS), feature_only_fields=list(FEATURES.FIELDS),
                    label_policy=POLICY, evidence_category_role='Target provenance only; prohibited predictor',
                    predictor_count=15, excluded_dataset_columns=[name for name in DATASET_FIELDS if name not in FEATURES.ALLOWLIST],
                    label_semantics=validation['operational_zero_semantics'],
                    explicit_missing_representation='Blank CSV cell / JSON null; never preparation-time zero filling')
    dependencies = {ROOT/name for name in ('data/cohorts/cohort_2000.csv', 'data/intermediate/pilot_games.csv',
                    'tests/scalable_artifact_hashes.json', 'src/cohort_io.py', 'src/cohort_pipeline.py',
                    'src/04_audit_autumn_evidence.py', 'src/05_investigate_sale_coverage.py', 'src/06_build_operational_labels.py',
                    'src/07_build_autumn_features.py', 'src/autumn_sale_calendar.json', 'src/incremental_itad.py', 'src/03_fetch_itad.py',
                    'src/08_train_baseline_models.py', 'src/09_train_ensemble_models.py',
                    'src/freeze_cohort_modeling.py', 'PROJECT_CONTEXT.md') if (ROOT/name).is_file()}
    dependencies.update(path for _,_,_,path in caches.values())
    dependencies.update(ROOT/event['source_image_path'] for event in pipeline.audit.calendar_data(ROOT)['events']
                        if event.get('source_image_path'))
    dependencies.update(p for p in (ROOT/'reports/cohort_2000_operational').iterdir() if p.is_file())
    input_manifest = dict(input_sha256={str(p.relative_to(ROOT)): digest(p) for p in sorted(dependencies)},
                          original_rule=POLICY, feature_version=FEATURES.VERSION,
                          sale_windows=prior['sale_windows'], input_cache_files=len(caches),
                          successful_empty_histories=prior['successful_empty_histories'])
    return dict(rows=rows, features=result['features'], provenance=result['provenance'],
                missingness=missingness(rows), membership=membership, protocol=protocol, manifest=manifest,
                validation=validation, input_manifest=input_manifest,
                labels=dict(overall=distribution(rows), by_year={str(y): distribution([r for r in rows if r['sale_year'] == y])
                                                             for y in result['windows']}, by_split=protocol['splits']))


def write_outputs(destination, result):
    destination.mkdir()
    tables = {'modeling.csv': (result['rows'], DATASET_FIELDS), 'features.csv': (result['features'], FEATURES.FIELDS),
              'missingness.csv': (result['missingness'], list(result['missingness'][0])),
              'split_membership.csv': (result['membership'], list(result['membership'][0]))}
    for name,(rows, fields) in tables.items():
        with (destination/name).open('x', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    for filename,key in {'feature_manifest.json': 'manifest', 'feature_provenance.json': 'provenance',
                         'label_distribution.json': 'labels', 'temporal_split_manifest.json': 'protocol',
                         'input_manifest.json': 'input_manifest', 'validation.json': 'validation'}.items():
        with (destination/filename).open('x', encoding='utf-8') as stream:
            stream.write(json.dumps(result[key], indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)+'\n')
    checksums = {p.name: digest(p) for p in sorted(destination.iterdir()) if p.is_file()}
    with (destination/'checksums.json').open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(checksums, indent=2, sort_keys=True)+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohort', required=True, type=Path)
    parser.add_argument('--cache-dir', required=True, type=Path)
    parser.add_argument('--reuse-cache', action='append', default=[], type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    destination = args.output_dir.resolve()
    require(destination.is_relative_to(ROOT/'reports') and not destination.exists(), 'Choose a new reports directory')
    require(not any(p.is_symlink() for p in [args.output_dir.absolute(), *args.output_dir.absolute().parents]), 'Symlink output forbidden')
    def guard(event, values):
        if event.startswith('socket.') or event == 'subprocess.Popen':
            raise RuntimeError('Network and subprocesses forbidden during modeling freeze')
        if event == 'open' and (values[2] or 0)&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):
            if isinstance(values[0], (str, bytes, os.PathLike)):
                require(Path(os.fsdecode(values[0])).resolve().is_relative_to(destination), 'Writes restricted to new reports directory')
        if event in {'os.remove', 'os.rename', 'os.mkdir', 'os.rmdir', 'os.symlink', 'os.link', 'os.chmod', 'os.utime'}:
            for value in values[:2] if event in {'os.rename', 'os.link'} else values[:1]:
                if isinstance(value, (str, bytes, os.PathLike)):
                    require(Path(os.fsdecode(value)).resolve().is_relative_to(destination), 'Mutations restricted to new reports directory')
    sys.addaudithook(guard)
    baseline = read_json(ROOT/'tests/scalable_artifact_hashes.json')
    inputs = {p for folder in ('data', 'reports', 'models') for p in (ROOT/folder).rglob('*') if p.is_file()}
    inputs.update(ROOT/name for name in baseline)
    before = {str(p.relative_to(ROOT)): digest(p) for p in inputs}
    result = build(args.cohort, args.cache_dir.resolve(), [p.resolve() for p in args.reuse_cache])
    require(all(digest(ROOT/name) == sha for name,sha in before.items()), 'Existing artifact changed')
    journal = Journal(args.cache_dir.resolve(), 3816, readonly=True).counts()
    require(journal['total_http_attempts'] == 3816, 'Unexpected journal count')
    result['validation'].update(preexisting_input_files_preserved=len(before), preservation_mismatches=[],
                                phase6a_files_preserved=sum(p.startswith('reports/cohort_2000_labelability/') for p in before),
                                phase6b_files_preserved=sum(p.startswith('reports/cohort_2000_operational/') for p in before),
                                protected_artifacts_preserved_this_phase=len(baseline),
                                historical_baseline_matches=sum(before[n] == v['sha256'] for n,v in baseline.items()),
                                historical_mismatch_sha256=before['data/intermediate/autumn_sale_evidence_records.csv'],
                                journal=journal, preservation_sha256=before)
    write_outputs(destination, result)
    require(all(digest(ROOT/name) == sha for name,sha in before.items()), 'Existing artifact changed after writing')
    print(json.dumps(dict(dataset_rows=len(result['rows']), dataset_columns=len(DATASET_FIELDS), predictors=15,
                         distribution=result['labels'], cutoff_violations=0,
                         protected_artifacts_preserved=len(baseline), historical_baseline_matches=result['validation']['historical_baseline_matches'])))


if __name__ == '__main__':
    main()
