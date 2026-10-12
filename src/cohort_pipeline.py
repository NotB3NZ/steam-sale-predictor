"""Configurable offline processing using the original evidence and feature rules."""
import argparse
from collections import Counter
from datetime import date
import json
from pathlib import Path

from cohort_io import (ROOT, checked_path, digest, load_cohort, module, require,
                       select_cohort, write_csv, write_json)

audit = module('cohort_audit', '04_audit_autumn_evidence.py')
coverage = module('cohort_coverage', '05_investigate_sale_coverage.py')
labels_core = module('cohort_labels', '06_build_operational_labels.py')
features_core = module('cohort_features', '07_build_autumn_features.py')


def strings(rows):
    return [{k: '' if v is None else str(v) for k, v in r.items()} for r in rows]


def provenance_path(path):
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def evidence(games, caches):
    """Missing/unmatched/failed histories never become audited category D."""
    windows = audit.canonical_windows(ROOT)
    pairs, records, diagnostics, manifests, cache_paths = [], [], [], [], {}
    features, provenance = [], []
    usable_histories = set()
    successful = set()
    for game in games:
        appid = game['AppID']
        obj, status, reason, path = caches(appid) if callable(caches) else caches[appid]
        cache_paths[appid] = provenance_path(path)
        info = dict(cache_status=status, issue=reason, raw_history_record_count=0)
        parsed = []
        if status == 'valid' and obj['collection_metadata']['history_status'] in {'history_received', 'empty_history'}:
            parsed, issues, other = audit.parse_history(obj['history_response'])
            info.update(cache_status='partial' if issues or other else 'ok',
                        raw_history_record_count=len(obj['history_response']),
                        record_parsing_failures=issues, non_steam_records_excluded=other)
        analyzed = [r for r in parsed if audit.utc_stamp(r['timestamp_utc']) < coverage.CUTOFF]
        if info['cache_status'] == 'ok' and any(r['observation_kind'] in {'discount', 'full_price'} for r in analyzed):
            usable_histories.add(appid)
        manifests.append(dict(AppID=appid, Name=game['Name'], country='US', steam_shop_id=61,
                              cache_path=cache_paths[appid]))
        for year, window in windows.items():
            pair, raw = audit.audit_pair(game, year, window, analyzed, info)
            pair['cache_path'] = cache_paths[appid]
            pairs.append(pair)
            if info['cache_status'] == 'ok' and pair['eligible_for_sale']:
                diagnostic = coverage.summarize_pair(game, year, window, analyzed, info, len(parsed)-len(analyzed),
                                                     include_sequence=False)
                diagnostic['cache_path'] = cache_paths[appid]
                diagnostics.append(diagnostic)
                records.extend(raw)
                successful.add((appid, year))
        eligible = [(int(appid), y) for y, window in windows.items()
                    if date.fromisoformat(game['release_date']) <= date.fromisoformat(window[0])]
        game_features, game_provenance = features_core.build_features(eligible, {int(appid): game},
                                                     {int(appid): analyzed}, windows)
        features.extend(game_features)
        provenance.extend(game_provenance)
    inputs = dict(pairs=strings([p for p in pairs if (p['AppID'], p['sale_year']) in successful]),
                  records=strings(records), diagnostics=strings(diagnostics), games=strings(games),
                  manifest=strings(manifests))
    modeled_labels = labels_core.construct_labels(inputs, windows, expected_pairs=successful, cache_paths=cache_paths)
    indexed = {(r['appid'], r['sale_year']): r for r in modeled_labels}
    labels = []
    by_game = {g['AppID']: g for g in games}
    for pair in pairs:
        appid, year = pair['AppID'], pair['sale_year']
        game = by_game[appid]
        row = indexed.get((appid, year))
        if row is None:
            row = dict(appid=appid, game_name=game['Name'], sale_year=year,
                       sale_start_utc=audit.fmt(windows[year][2]), sale_end_utc=audit.fmt(windows[year][3]),
                       evidence_category='', discount_observed='', pu_status='unknown',
                       ambiguity_flag=True, requires_review=True, label_rule_version=labels_core.RULE,
                       label_source='No valid eligible ITAD history', label_limitation_flag=True,
                       eligibility_status='ineligible_by_release_date' if not pair['eligible_for_sale'] else 'unknown_history',
                       eligibility_reason=pair['eligibility_reason'], release_date=game['release_date'],
                       cache_path=cache_paths[appid], source_shop_id=61, source_region='US')
        # Original D means no *recorded* in-window discount, never a confirmed
        # negative Steam participation label. Exclude it from expanded fitting.
        sufficient = row['evidence_category'] in {'A', 'B'} and not row['requires_review']
        row.update(evaluation_group=game['evaluation_group'], model_eligible=bool(sufficient),
                   evidence_sufficiency='observed_in_window_price' if sufficient else 'missing_or_uncertain_in_window_evidence',
                   steam_sale_participation='UNKNOWN', confirmed_negative=False)
        labels.append(row)
    features.sort(key=lambda r: (r['appid'], r['sale_year']))
    provenance.sort(key=lambda r: (r['appid'], r['sale_year']))
    targets = {(int(r['appid']), r['sale_year']): r for r in labels}
    modeling = []
    for feature in features:
        label = targets[(feature['appid'], feature['sale_year'])]
        modeling.append(dict(feature, discount_observed=label['discount_observed'],
                             evaluation_group=label['evaluation_group'], model_eligible=label['model_eligible'],
                             evidence_sufficiency=label['evidence_sufficiency']))
    return dict(games=games, windows=windows, pairs=pairs, records=records, diagnostics=diagnostics,
                labels=labels, features=features, provenance=provenance, modeling=modeling,
                usable_history_ids=usable_histories)


def quality(result):
    years = {}
    for year in result['windows']:
        rr = [r for r in result['labels'] if r['sale_year'] == year]
        years[str(year)] = dict(target_games=len(rr), categories=dict(Counter(r['evidence_category'] or 'unknown' for r in rr)),
                               observed_discount_games=sum(r['evidence_category'] == 'A' for r in rr),
                               usable_model_labels=sum(r['model_eligible'] for r in rr),
                               missing_or_uncertain_labels=sum(not r['model_eligible'] for r in rr),
                               release_ineligible_games=sum(r['eligibility_status'] == 'ineligible_by_release_date' for r in rr))
    usable_ids = {r['appid'] for r in result['labels'] if r['model_eligible']}
    historical_ids = result['usable_history_ids']
    return dict(games_with_usable_historical_records=len(historical_ids),
                games_with_incomplete_historical_records=len(result['games'])-len(historical_ids),
                games_with_usable_model_labels=len(usable_ids),
                missing_or_uncertain_labels=sum(not r['model_eligible'] for r in result['labels']),
                coverage_by_sale_year=years,
                label_semantics='Recorded discounts only; D retains the historical operational target but is excluded from expanded fitting. Steam participation remains unknown.')


def write_table(path, rows, fields=None):
    if fields is None:
        fields = list(dict.fromkeys(k for row in rows for k in row))
    write_csv(path, rows, fields or ['appid', 'sale_year'])


def model_frames(result):
    import pandas as pd
    rows = [r for r in result['modeling'] if r['model_eligible']]
    frame = pd.DataFrame(rows, columns=list(features_core.FIELDS)+
                         ['discount_observed', 'evaluation_group', 'model_eligible', 'evidence_sufficiency'])
    frame['discount_observed'] = pd.to_numeric(frame.discount_observed, errors='raise')
    train = frame[frame.evaluation_group.eq('development') & frame.sale_year.isin([2023, 2024])].copy()
    evaluation = frame[frame.evaluation_group.eq('evaluation') & frame.sale_year.eq(2025)].copy()
    require(not set(train.appid) & set(evaluation.appid), 'Game-level train/evaluation overlap')
    require(not frame.duplicated(['appid', 'sale_year']).any(), 'Duplicate modeling keys')
    require(train.empty or set(train.sale_year) <= {2023, 2024}, 'Future training rows')
    return train, evaluation


def modeling(result, output_dir, stage, fit=False):
    train, evaluation = model_frames(result)
    report = dict(mode='fit' if fit else 'prepare_only', training_years=[2023, 2024], evaluation_year=2025,
                  training_rows=len(train), evaluation_rows=len(evaluation), training_games=train.appid.nunique(),
                  evaluation_games=evaluation.appid.nunique(), game_overlap=0,
                  training_class_counts={str(k): int(v) for k, v in train.discount_observed.value_counts().items()},
                  evaluation_class_counts={str(k): int(v) for k, v in evaluation.discount_observed.value_counts().items()},
                  predictors=list(features_core.ALLOWLIST), threshold=0.5, seed=42,
                  original_pilot='Diagnostic development only; previously inspected games are excluded from new held-out claims',
                  excluded_rows=len(result['modeling'])-sum(r['model_eligible'] for r in result['modeling']),
                  selection='Fixed model parameters; no evaluation outcomes used for preprocessing or model selection')
    write_table(output_dir/f'{stage}_training.csv', train.to_dict('records'), list(train.columns))
    write_table(output_dir/f'{stage}_evaluation.csv', evaluation.to_dict('records'), list(evaluation.columns))
    if fit:
        require(set(train.sale_year) == {2023, 2024} and set(train.discount_observed) == {0, 1},
                'Fitting requires both historical training years and both observed target classes')
        require(not evaluation.empty, 'No independent usable evaluation rows')
        destination = checked_path(output_dir/f'{stage}_models', write=True)
        require(not destination.exists(), 'Model directory already exists; choose a new output namespace')
        # Import fitting libraries only when requested. Never load or overwrite pilot models.
        b = module('scalable_baselines', '08_train_baseline_models.py')
        with b.offline_guard():
            if stage == 'baseline':
                models, profile = b.fit_models(train)
                predictions = b.predict(models, evaluation)
            else:
                e = module('scalable_ensembles', '09_train_ensemble_models.py')
                require(e.XGBClassifier is not None, 'Install the documented environment before ensemble fitting')
                models, profile = e.fit_models(train, cohort_mode=True)
                predictions = e.predict(models, evaluation)
            metrics = b.evaluate(predictions)
            destination.mkdir(parents=True)
            for name, model in models.items():
                b.joblib.dump(model, destination/f'{name}.joblib')
            write_table(output_dir/f'{stage}_predictions.csv', predictions.to_dict('records'), list(predictions.columns))
            write_json(output_dir/f'{stage}_metrics.json', metrics)
            write_json(output_dir/f'{stage}_preprocessing.json', profile)
            report['models_written'] = list(models)
    write_json(output_dir/f'{stage}_protocol.json', report)
    return report


def run(cohort, cache_dir, output_dir, reuse_dirs=None, stage='features', fit=False):
    from incremental_itad import paths, resolve_cache, ORIGINAL_CACHE
    cohort, cache_dir, reuse_dirs, output_dir = paths(cohort, cache_dir,
                    reuse_dirs if reuse_dirs is not None else (ORIGINAL_CACHE,), output_dir)
    games = load_cohort(cohort)
    result = evidence(games, lambda appid: resolve_cache(appid, cache_dir, reuse_dirs))
    output_dir.mkdir(parents=True, exist_ok=True)
    # All stages produce reconciled evidence; none invokes historical fixed-path writers.
    write_table(output_dir/'evidence_audit.csv', result['pairs'])
    write_table(output_dir/'evidence_records.csv', result['records'], ['AppID', 'Name', 'sale_year', *audit.OBS_FIELDS])
    write_table(output_dir/'coverage_diagnostics.csv', result['diagnostics'])
    write_table(output_dir/'operational_labels.csv', result['labels'])
    write_table(output_dir/'pu_labels.csv', result['labels'], ['appid', 'sale_year', 'evidence_category', 'pu_status', 'label_rule_version'])
    write_table(output_dir/'features.csv', result['features'], features_core.FIELDS)
    write_table(output_dir/'modeling.csv', result['modeling'])
    write_json(output_dir/'feature_manifest.json', features_core.feature_manifest())
    write_json(output_dir/'feature_provenance.json', result['provenance'])
    write_json(output_dir/'data_quality.json', dict(cohort_sha256=digest(cohort), **quality(result)))
    if stage == 'ground_truth':
        write_json(output_dir/'ground_truth.json', dict(status='UNKNOWN', confirmed_negative_games=0,
                   explanation='ITAD observations do not confirm official Steam sale participation. No new independent evidence was accessed.'))
    if stage in {'baseline', 'ensemble'}:
        modeling(result, output_dir, stage, fit)
    return result


def cli(stage=None, argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    if stage is None:
        p.add_argument('stage', choices=['select', 'audit', 'coverage', 'ground_truth', 'labels', 'features', 'baseline', 'ensemble'])
    p.add_argument('--cohort', type=Path)
    p.add_argument('--cache-dir', type=Path)
    p.add_argument('--output-dir', type=Path)
    p.add_argument('--reuse-cache', type=Path, action='append')
    p.add_argument('--cohort-size', type=int, choices=[500, 1000, 2000, 5000])
    p.add_argument('--cohort-output', type=Path)
    p.add_argument('--fit', action='store_true', help='Explicitly fit into a fresh isolated model directory; default prepares only')
    args = p.parse_args(argv)
    stage = stage or args.stage
    if stage == 'select':
        require(args.cohort_size and args.cohort_output, 'Selection requires --cohort-size and --cohort-output')
        print(json.dumps(select_cohort(args.cohort_size, args.cohort_output)))
    else:
        require(args.cohort and args.cache_dir and args.output_dir, 'Supply --cohort, --cache-dir and --output-dir')
        require(not args.fit or stage in {'baseline', 'ensemble'}, '--fit is only for model stages')
        result = run(args.cohort, args.cache_dir, args.output_dir, args.reuse_cache, stage, args.fit)
        print(json.dumps(dict(stage=stage, target_games=len(result['games']), **quality(result))))


if __name__ == '__main__':
    cli()
