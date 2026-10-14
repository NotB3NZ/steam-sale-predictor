"""Offline all-game temporal runner using frozen operational features and model cores."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from importlib import metadata
import json
import os
from pathlib import Path
import sys

from cohort_io import ROOT, digest, module, read_csv, read_json, require
import freeze_cohort_modeling as frozen

ORDER = ['bernoulli_baseline', 'logistic_regression', 'random_forest', 'xgboost']


def cores():
    return module('cohort_temporal_ensemble', '09_train_ensemble_models.py')


def load_frozen(directory, core):
    checksums = read_json(directory/'checksums.json')
    require(all(digest(directory/name) == sha for name,sha in checksums.items()), 'Frozen Phase 6C file checksum mismatch')
    inputs = read_json(directory/'input_manifest.json')['input_sha256']
    require(all(digest(ROOT/name) == sha for name,sha in inputs.items()), 'Frozen input/source checksum mismatch')
    readiness = read_json(directory/'model_readiness.json')
    require(all(metadata.version(name) == version for name,version in readiness['library_versions'].items()), 'Dependency versions differ from frozen environment')
    require(all(digest(ROOT/name) == sha for name,sha in readiness['source_sha256'].items()), 'Frozen model core changed')
    manifest = read_json(directory/'feature_manifest.json')
    require(core.b.validate_manifest(manifest) == list(frozen.FEATURES.ALLOWLIST), 'Unapproved feature manifest')
    raw = read_csv(directory/'modeling.csv')
    integer = set(frozen.FEATURES.STATIC) | {'appid', 'sale_year', 'audit_release_hour_uncertain', 'discount_observed',
               'prior_price_record_count', 'prior_discount_count', 'has_prior_price_history', 'has_prior_discount_observation'}
    rows = [{name: int(value) if name in integer else float(value) if name in frozen.FEATURES.ALLOWLIST and value else
                  None if name in frozen.FEATURES.ALLOWLIST else value for name,value in row.items()} for row in raw]
    windows = frozen.pipeline.audit.canonical_windows(ROOT)
    validation = frozen.validate_rows(rows, windows, {r['appid'] for r in rows})
    require(validation['game_year_rows'] == 6000 and validation['unique_games'] == 2000, 'Expected frozen cohort size')
    membership, protocol = frozen.temporal_protocol(rows)
    require(protocol == read_json(directory/'temporal_split_manifest.json'), 'Temporal protocol differs')
    require([{k: str(v) for k,v in r.items()} for r in membership] == read_csv(directory/'split_membership.csv'), 'Split membership differs')
    frame = core.pd.DataFrame(rows).sort_values(['sale_year', 'appid']).reset_index(drop=True)
    require(frame.discount_observed.value_counts().to_dict() == {1: 3030, 0: 2970}, 'Operational targets differ')
    return frame, protocol, dict(dataset_sha256=digest(directory/'modeling.csv'),
                               phase6c_file_sha256={name: digest(directory/name) for name in checksums},
                               checksum_index_sha256=digest(directory/'checksums.json'))


def chronological_parts(frame):
    require(not frame.duplicated(['appid', 'sale_year']).any(), 'Duplicate game-year observations')
    require(set(frame.sale_year) == {2023, 2024, 2025}, 'Unexpected temporal years')
    parts = {name: frame[frame.sale_year.isin(years)].sort_values(['sale_year', 'appid']).reset_index(drop=True)
             for name,years in {'development_training': [2023], 'development_validation': [2024],
                               'final_training': [2023, 2024], 'held_out_test': [2025]}.items()}
    require(set(parts['development_training'].appid) == set(parts['development_validation'].appid) ==
            set(parts['held_out_test'].appid), 'Temporal game identities differ')
    return parts


def evaluate(predictions, core):
    from sklearn.metrics import auc, balanced_accuracy_score, precision_recall_curve
    result = core.b.evaluate(predictions)
    result.update(positive_class=1, classification_threshold=0.5,
                  pr_auc_definition='Primary PR-AUC is average precision (step-weighted). Trapezoidal PR area is reported separately.',
                  operational_zero='No discount observed in available evidence, not verified nonparticipation')
    for name, row in result['models'].items():
        group = predictions[predictions.model_name.eq(name)]
        y, p, c = group.actual_label.to_numpy(), group.predicted_probability.to_numpy(), group.predicted_class.to_numpy()
        precision, recall, _ = precision_recall_curve(y, p) if y.sum() else (None, None, None)
        row.update(balanced_accuracy=float(balanced_accuracy_score(y,c)) if len(set(y)) == 2 else None,
                   pr_auc=row['average_precision'], pr_auc_trapezoidal=float(auc(recall,precision)) if y.sum() else None,
                   predicted_positive=int(c.sum()), predicted_negative=int(len(c)-c.sum()),
                   mean_probability=float(p.mean()), actual_positive=int(y.sum()), actual_negative=int(len(y)-y.sum()))
        if len(set(y)) != 2:
            row['undefined_metrics']['balanced_accuracy'] = 'Single-class subgroup; balanced accuracy omitted.'
    return result


def choose_model(development_metrics):
    """Selection receives development metrics only; held-out inputs are absent."""
    candidates = development_metrics['models']
    require(bool(candidates) and set(candidates) <= set(ORDER), 'Unexpected candidates')
    require(all(v['average_precision'] is not None for v in candidates.values()), 'Selection needs development positives')
    ranking = sorted(candidates, key=lambda name: (-candidates[name]['average_precision'],
                                                 candidates[name]['brier_score'], ORDER.index(name)))
    return dict(selected_model=ranking[0], ranking=ranking,
                selection_data='2023 training -> 2024 development validation only',
                primary_metric='average_precision', tie_breakers=['lower Brier score', 'predefined model order'],
                threshold=0.5, hyperparameter_search=False,
                rationale='Highest development average precision among the predefined configurations; no 2025 scores used')


def verify_preprocessing(models, train, core):
    X = core.numeric_predictors(train)
    expected = X.median().to_numpy()
    require(not X.isna().all().any(), 'All-missing training column: stop rather than silently use structural zeros')
    profiles = {}
    for name,model in models.items():
        if name == 'bernoulli_baseline':
            core.np.testing.assert_allclose(model.class_prior_[list(model.classes_).index(1)], train.discount_observed.mean(), rtol=0, atol=0)
            profiles[name] = dict(strategy='training class prior; no predictor preprocessing', training_rows=len(train))
            continue
        require(list(model[:-1].get_feature_names_out()) == core.b.APPROVED, 'Predictor schema changed')
        core.np.testing.assert_allclose(model.named_steps['impute'].statistics_, expected, rtol=0, atol=0)
        if 'scale' in model.named_steps:
            imputed = X.fillna(X.median()).to_numpy()
            core.np.testing.assert_allclose(model.named_steps['scale'].mean_, imputed.mean(axis=0), rtol=1e-12, atol=1e-12)
            core.np.testing.assert_allclose(model.named_steps['scale'].var_, imputed.var(axis=0), rtol=1e-12, atol=1e-12)
            require(int(model.named_steps['scale'].n_samples_seen_) == len(train), 'Scaler fitted on nontraining rows')
        profiles[name] = core.preprocessing_profile(model, train, core.b.APPROVED)
    return profiles


def flat_metrics(result, stage):
    return [dict(stage=stage, model=name, **{k: v for k,v in row.items() if not isinstance(v, (dict,list))},
                 tn=row['confusion_matrix'][0][0], fp=row['confusion_matrix'][0][1],
                 fn=row['confusion_matrix'][1][0], tp=row['confusion_matrix'][1][1])
            for name,row in result['models'].items()]


def diagnostics(predictions, frame, core):
    rows, bins, summary = [], [], {}
    context = frame[['appid', 'sale_year', *core.b.APPROVED]].copy()
    context['missing_features'] = context[core.b.APPROVED].isna().sum(axis=1)
    merged = predictions.merge(context, on=['appid', 'sale_year'], validate='many_to_one')
    for name,group in merged.groupby('model_name', sort=True):
        groups = [('prior_price_history', 'none', group.has_prior_price_history.eq(0)),
                  ('prior_price_history', 'present', group.has_prior_price_history.eq(1)),
                  ('prior_discount_history', 'none', group.has_prior_discount_observation.eq(0)),
                  ('prior_discount_history', 'present', group.has_prior_discount_observation.eq(1)),
                  ('feature_missingness', 'any_missing', group.missing_features.gt(0)),
                  ('feature_missingness', 'complete', group.missing_features.eq(0))]
        for label,low,high in [('0', 0, 0), ('1-9', 1, 9), ('10-29', 10, 29), ('30+', 30, None)]:
            mask = group.prior_price_record_count.ge(low)
            if high is not None:
                mask &= group.prior_price_record_count.le(high)
            groups.append(('price_observation_density', label, mask))
        for family,segment,mask in groups:
            selected = group[mask]
            if not selected.empty:
                result = evaluate(selected,core)
                rows.append(dict(family=family,segment=segment,**flat_metrics(result,'diagnostic')[0]))
        p, y = group.predicted_probability.to_numpy(), group.actual_label.to_numpy()
        ece = 0.0
        for index in range(10):
            low, high = index/10, (index+1)/10
            mask = (p >= low)&((p < high) if index < 9 else (p <= high))
            count = int(mask.sum())
            avg_p = float(p[mask].mean()) if count else None
            fraction = float(y[mask].mean()) if count else None
            if count:
                ece += count/len(p)*abs(avg_p-fraction)
            bins.append(dict(model=name, bin=index, lower_inclusive=low, upper=high,
                             upper_inclusive=index==9, observations=count,
                             mean_probability=avg_p, observed_positive_fraction=fraction))
        correlation = group.predicted_probability.corr(group.prior_price_record_count, method='spearman') if group.predicted_probability.nunique()>1 and group.prior_price_record_count.nunique()>1 else None
        summary[name] = dict(equal_width_10_bin_ece=ece, mean_probability=float(p.mean()),
                             observed_prevalence=float(y.mean()),
                             probability_vs_record_count_spearman=float(correlation) if correlation is not None and core.np.isfinite(correlation) else None,
                             calibration_fitted=False, correlation_is_not_causal=True)
    patterns = Counter(tuple(f for f in core.b.APPROVED if row[f] != row[f]) for row in frame.to_dict('records'))
    return dict(coverage_rows=rows, calibration_bins=bins, summary=summary,
                missingness={f: int(frame[f].isna().sum()) for f in core.b.APPROVED},
                missing_patterns=[dict(features=list(features),observations=n) for features,n in patterns.items()])


def importance(models, stage, core):
    rows = []
    for name,model in models.items():
        if name == 'bernoulli_baseline':
            continue
        estimator = model.named_steps['classifier']
        values = estimator.coef_[0] if name == 'logistic_regression' else estimator.feature_importances_
        kind = 'standardized log-odds coefficient' if name == 'logistic_regression' else 'impurity importance' if name == 'random_forest' else 'normalized gain importance'
        rows.extend(dict(stage=stage,model=name,feature=f,value=float(value),definition=kind)
                    for f,value in zip(core.b.APPROVED,values))
    return rows


def save_models(models, destination, probe, core):
    destination.mkdir()
    result = {}
    for name,model in models.items():
        path = destination/(name+'.joblib')
        core.joblib.dump(model,path)
        saved = core.joblib.load(path)
        X = core.np.zeros((len(probe),1)) if name == 'bernoulli_baseline' else core.numeric_predictors(probe)
        core.np.testing.assert_array_equal(model.predict_proba(X), saved.predict_proba(X))
        result[name] = dict(path=str(path.relative_to(destination.parent)), sha256=digest(path),
                            reload_probability_identity_verified=True,
                            estimator_parameters=core.clean(model.get_params() if name == 'bernoulli_baseline' else model.named_steps['classifier'].get_params()))
    return result


def write_json(path, value, core):
    with path.open('x',encoding='utf-8') as stream:
        stream.write(json.dumps(core.clean(value),indent=2,sort_keys=True,allow_nan=False)+'\n')


def write_csv(path, rows, core):
    import csv
    if hasattr(rows,'to_dict'):
        rows = rows.to_dict('records')
    clean = [{k: None if isinstance(v,float) and not core.np.isfinite(v) else v for k,v in r.items()} for r in rows]
    fields = list(dict.fromkeys(k for r in clean for k in r))
    with path.open('x',encoding='utf-8',newline='') as stream:
        writer = csv.DictWriter(stream,fieldnames=fields)
        writer.writeheader()
        writer.writerows(clean)


def run(directory, destination, before):
    core = cores()
    frame, protocol, frozen_inputs = load_frozen(directory,core)
    parts = chronological_parts(frame)
    require([len(parts[name]) for name in ('development_training','development_validation','final_training','held_out_test')] == [2000,2000,4000,2000], 'Wrong temporal split sizes')
    for name in ('development_training','final_training'):
        require(not core.numeric_predictors(parts[name]).isna().all().any(), 'All-missing training feature')
    destination.mkdir()
    precommit = dict(protocol=protocol, candidate_order=ORDER, feature_allowlist=core.b.APPROVED,
                     configurations=dict(logistic_regression=core.b.LOGISTIC_PARAMS,random_forest=core.RF_PARAMS,xgboost=core.XGB_PARAMS,
                                         bernoulli_baseline={'strategy':'prior','random_state':42}),
                     selection=dict(primary_metric='average_precision',tie_breakers=['lower Brier score','predefined model order'],
                                    data='2023->2024 only',hyperparameter_trials_per_model=1,threshold=0.5),
                     dependency_versions={name: metadata.version(name) for name in ('numpy','pandas','scipy','scikit-learn','xgboost','joblib','threadpoolctl') if name != 'xgboost' or core.XGBClassifier is not None},
                     unavailable_models=core.unavailable_models(),input_verification=frozen_inputs,
                     source_sha256={name:digest(ROOT/name) for name in ('src/train_cohort_temporal.py','src/08_train_baseline_models.py','src/09_train_ensemble_models.py')})
    write_json(destination/'precommitted_protocol.json',precommit,core)
    with core.b.offline_guard():
        development, _ = core.fit_models(parts['development_training'],training_years=[2023],include_baselines=True,cohort_mode=True)
        dev_profiles = verify_preprocessing(development,parts['development_training'],core)
        dev_pred = core.predict(development,parts['development_validation'])
        dev_metrics = evaluate(dev_pred,core)
        train_dev_metrics = evaluate(core.predict(development,parts['development_training']),core)
        selected = choose_model(dev_metrics)
        selected.update(selection_locked_at_utc=datetime.now(timezone.utc).isoformat(),
                        selected_configuration=precommit['configurations'][selected['selected_model']],
                        development_scores={name:dict(average_precision=row['average_precision'],brier_score=row['brier_score'])
                                            for name,row in dev_metrics['models'].items()})
        write_json(destination/'selection.json',selected,core)
        selection_sha = digest(destination/'selection.json')
        # No test probabilities/metrics have been computed before this lock.
        final, _ = core.b.fit_models(parts['final_training'])
        trees, _ = core.fit_models(parts['final_training'],cohort_mode=True)
        final.update(trees)
        final_profiles = verify_preprocessing(final,parts['final_training'],core)
        artifacts = {'development':save_models(development,destination/'development_models',parts['development_training'].head(32),core),
                     'final':save_models(final,destination/'final_models',parts['final_training'].head(32),core)}
        core.joblib.dump(final[selected['selected_model']],destination/'selected_model.joblib')
        final_train_metrics = evaluate(core.predict(final,parts['final_training']),core)
        test_started = datetime.now(timezone.utc).isoformat()
        test_pred = core.predict(final,parts['held_out_test'])  # Exactly one probability call per predefined model on 2025.
        # Persist the single held-out probability pass before diagnostic work so
        # any later reporting failure can be recovered without predicting again.
        write_csv(destination/'held_out_probability_pass.csv',test_pred,core)
        test_metrics = evaluate(test_pred,core)
        require(digest(destination/'selection.json') == selection_sha, 'Selection changed after held-out evaluation')
        dev_diagnostics = diagnostics(dev_pred,parts['development_validation'],core)
        test_diagnostics = diagnostics(test_pred,parts['held_out_test'],core)
    comparisons = flat_metrics(dev_metrics,'development_2024')+flat_metrics(test_metrics,'held_out_2025')
    write_csv(destination/'model_comparison.csv',comparisons,core)
    for prefix,predictions,metrics,diagnostic in [('development',dev_pred,dev_metrics,dev_diagnostics),('held_out',test_pred,test_metrics,test_diagnostics)]:
        write_json(destination/(prefix+'_metrics.json'),metrics,core)
        write_csv(destination/(prefix+'_metrics.csv'),flat_metrics(metrics,prefix),core)
        annotated = predictions.merge(parts['development_validation' if prefix=='development' else 'held_out_test'][
               ['appid','sale_year','evidence_category','has_prior_price_history','prior_price_record_count','has_prior_discount_observation']],on=['appid','sale_year'],validate='many_to_one')
        write_csv(destination/(prefix+'_predictions.csv'),annotated,core)
        write_json(destination/(prefix+'_diagnostics.json'),diagnostic,core)
        write_csv(destination/(prefix+'_coverage_metrics.csv'),diagnostic['coverage_rows'],core)
        write_csv(destination/(prefix+'_calibration_bins.csv'),diagnostic['calibration_bins'],core)
    write_json(destination/'training_metrics.json',dict(development_2023=train_dev_metrics,final_2023_2024=final_train_metrics),core)
    write_json(destination/'preprocessing.json',dict(development=dev_profiles,final=final_profiles),core)
    write_json(destination/'model_artifacts.json',dict(**artifacts,selected=dict(name=selected['selected_model'],path='selected_model.joblib',sha256=digest(destination/'selected_model.joblib'))),core)
    write_csv(destination/'feature_importance.csv',importance(development,'development',core)+importance(final,'final',core),core)
    matrices = [dict(stage=r['stage'],model=r['model'],tn=r['tn'],fp=r['fp'],fn=r['fn'],tp=r['tp'],orientation='rows actual [0,1]; columns predicted [0,1]') for r in comparisons]
    write_csv(destination/'confusion_matrices.csv',matrices,core)
    stability = {name:dict(development_training_ap=train_dev_metrics['models'][name]['average_precision'],
                           development_validation_ap=dev_metrics['models'][name]['average_precision'],
                           final_training_ap=final_train_metrics['models'][name]['average_precision'],
                           held_out_ap=test_metrics['models'][name]['average_precision'],
                           seed_stability_evaluated=False) for name in final}
    write_json(destination/'temporal_stability.json',stability,core)
    require(all(digest(ROOT/name)==sha for name,sha in before.items()),'Preexisting artifact changed during training')
    baseline = read_json(ROOT/'tests/scalable_artifact_hashes.json')
    validation = dict(no_network=True,protected_artifacts_preserved_this_phase=len(baseline),
                      historical_baseline_matches=sum(before[name]==v['sha256'] for name,v in baseline.items()),
                      preserved_input_files=len(before),preservation_sha256=before,
                      phase6a_files_preserved=sum(n.startswith('reports/cohort_2000_labelability/') for n in before),
                      phase6b_files_preserved=sum(n.startswith('reports/cohort_2000_operational/') for n in before),
                      phase6c_files_preserved=sum(n.startswith('reports/cohort_2000_modeling/') for n in before),
                      selection_sha256=selection_sha,test_started_at_utc=test_started,
                      held_out_probability_passes_per_model=1,selection_unchanged_after_test=True,
                      training_only_preprocessing_statistics_verified=True,serialized_pipeline_reload_verified=True,
                      game_overlap=2000,held_out_rows=2000,preservation_mismatches=[],pilot_models_refitted=False)
    write_json(destination/'validation.json',validation,core)
    write_json(destination/'checksums.json',{str(p.relative_to(destination)):digest(p) for p in sorted(destination.rglob('*')) if p.is_file()},core)
    print(json.dumps(core.clean(dict(selected_model=selected['selected_model'],development=dev_metrics['models'],held_out=test_metrics['models'],integrity={k:v for k,v in validation.items() if k!='preservation_sha256'}))))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir',type=Path,default=ROOT/'reports/cohort_2000_modeling')
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    destination=args.output_dir.resolve()
    require(destination.is_relative_to(ROOT/'reports') and not destination.exists(),'Choose a new reports directory')
    require(not any(p.is_symlink() for p in [args.output_dir.absolute(),*args.output_dir.absolute().parents]),'Symlink output forbidden')
    runtime=Path('/private/tmp/steam-cohort-models-runtime')
    os.environ['MPLCONFIGDIR']=str(runtime)
    def permitted(path):
        p=Path(os.fsdecode(path)).resolve()
        return p.is_relative_to(destination) or p.is_relative_to(runtime)
    def guard(event,values):
        if event in {'socket.connect','socket.getaddrinfo'}:
            raise RuntimeError('Network forbidden in temporal model runner')
        if event=='subprocess.Popen':
            # Optional NumPy/font hardware probes handle OSError as unavailable.
            raise OSError('External subprocesses forbidden in temporal model runner')
        if event=='open' and (values[2] or 0)&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):
            if isinstance(values[0],(str,bytes,os.PathLike)):
                require(permitted(values[0]),'Writes confined to new model reports/runtime cache')
        if event in {'os.remove','os.rename','os.mkdir','os.rmdir','os.symlink','os.link','os.chmod','os.utime'}:
            for path in values[:2] if event in {'os.rename','os.link'} else values[:1]:
                if isinstance(path,(str,bytes,os.PathLike)):
                    require(permitted(path),'Mutations confined to new model reports/runtime cache')
    sys.addaudithook(guard)
    runtime.mkdir(parents=True,exist_ok=True)
    # Legacy imports query gettempdir even when MPLCONFIGDIR is set. Keep its
    # writable probes and all library caches within the authorized runtime path.
    import tempfile
    tempfile.tempdir=str(runtime)
    baseline=read_json(ROOT/'tests/scalable_artifact_hashes.json')
    paths={p for folder in ('data','reports','models') for p in (ROOT/folder).rglob('*') if p.is_file()}
    paths.update(ROOT/name for name in baseline)
    before={str(p.relative_to(ROOT)):digest(p) for p in paths}
    run(args.input_dir.resolve(),destination,before)


if __name__=='__main__':
    main()
