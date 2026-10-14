"""Offline fixed-configuration 2023–2025 refit and retrospective 2026 inference."""
import argparse
from collections import Counter
import csv
import fcntl
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import sys
import tempfile

from cohort_io import ROOT, digest, load_cohort, read_csv, read_json, require
import audit_2026_feasibility as feasibility
import train_cohort_temporal as temporal
from incremental_itad import Journal
from visualize_cohort_models import frozen_model_guard

DESCRIPTION = 'Retrospective event-time-filtered predictions using post-cutoff-collected historical data.'
CUTOFF = '2026-10-01T17:00:00Z'
FEATURES = feasibility.FEATURES
OUT = ROOT/'reports/cohort_2000_2026_predictions'
FROZEN = ('cohort_2000_modeling', 'cohort_2000_models', 'cohort_2000_2026_feasibility')
EXPECTED_NULLS = dict.fromkeys(FEATURES.ALLOWLIST, 0)
EXPECTED_NULLS.update(dict.fromkeys(('prior_discount_rate', 'days_since_last_price_record',
                                    'last_observed_price', 'last_observed_discount_pct'), 81))
EXPECTED_NULLS.update(dict.fromkeys(('days_since_last_discount', 'max_prior_discount_pct',
                                    'mean_prior_discount_pct'), 336))


def snapshot():
    protected = read_json(ROOT/'tests/scalable_artifact_hashes.json')
    files = {p for folder in ('data', 'reports', 'models') for p in (ROOT/folder).rglob('*') if p.is_file()}
    files.update(ROOT/name for name in protected)
    return {str(p.relative_to(ROOT)): digest(p) for p in sorted(files)}


def assert_preserved(before):
    changed = [name for name,sha in before.items() if not (ROOT/name).is_file() or digest(ROOT/name) != sha]
    require(not changed, 'Preexisting artifacts changed: '+', '.join(changed))


def mutation_paths(event, values):
    """Resolve audit-event paths relative to their actual directory descriptors."""
    if event in ('os.rename','os.link'):
        targets = ((values[0],values[2]),(values[1],values[3]))
    elif event == 'os.symlink':
        targets = ((values[1],values[2]),)
    elif event in ('os.remove','os.rmdir'):
        targets = ((values[0],values[1]),)
    elif event in ('os.mkdir','os.chmod'):
        targets = ((values[0],values[2]),)
    else:
        targets = ((values[0],None),)
    result = []
    for value,dir_fd in targets:
        if not isinstance(value,(str,bytes,os.PathLike)):
            continue
        path = Path(os.fsdecode(value))
        if not path.is_absolute() and isinstance(dir_fd,int) and dir_fd >= 0:
            parent = fcntl.fcntl(dir_fd,50,b'\0'*1024).split(b'\0',1)[0] if sys.platform=='darwin' else os.readlink('/proc/self/fd/'+str(dir_fd))
            path = Path(os.fsdecode(parent))/path
        result.append(path.resolve())
    return result


def verify_indexes():
    hashes = {}
    for directory in FROZEN:
        root = ROOT/'reports'/directory
        index = read_json(root/'checksums.json')
        require(all(digest(root/name) == sha for name,sha in index.items()), 'Frozen artifact mismatch: '+directory)
        hashes.update({str((root/name).relative_to(ROOT)):sha for name,sha in index.items()})
        hashes[str((root/'checksums.json').relative_to(ROOT))] = digest(root/'checksums.json')
    return hashes


def validate_training(frame, cohort_ids):
    require(set(frame.sale_year) == {2023,2024,2025}, 'Training must contain only 2023–2025')
    require(len(frame) == 3*len(cohort_ids) and not frame.duplicated(['appid','sale_year']).any(), 'Invalid training keys/count')
    require(all(set(part.appid) == set(cohort_ids) for _,part in frame.groupby('sale_year')), 'Training cohort membership differs')
    require(set(frame.discount_observed) == {0,1}, 'Training targets must be observed operational 0/1 labels')
    require(all(name in frame for name in FEATURES.ALLOWLIST), 'Training feature missing')


def validate_features(vectors, cohort_ids, cutoff, expected_nulls=None):
    require(len(vectors) == len(cohort_ids) and [r['appid'] for r in vectors] == list(cohort_ids), 'Prediction cohort membership/order differs')
    require(len({r['appid'] for r in vectors}) == len(vectors), 'Duplicate prediction AppIDs')
    for row in vectors:
        feasibility.validate_vector(row, cutoff)
    missing = {f:sum(r[f] is None for r in vectors) for f in FEATURES.ALLOWLIST}
    if expected_nulls is not None:
        require(missing == expected_nulls, 'Missingness differs from frozen Phase 8A; investigate before fitting')
    return missing


def verify_configuration(core, selection, protocol):
    require(core.XGBClassifier is not None, 'XGBoost unavailable; no substitution permitted')
    require(selection['selected_model'] == 'xgboost' and selection['threshold'] == .5, 'Frozen selection/threshold differs')
    require(selection['selected_configuration'] == protocol['estimator']['configuration'] == core.XGB_PARAMS, 'Frozen XGBoost parameters differ')
    require(protocol['training']['feature_allowlist'] == list(FEATURES.ALLOWLIST) == core.b.APPROVED, 'Approved feature ordering differs')
    require(protocol['training']['years'] == [2023,2024,2025] and protocol['training']['rows'] == 6000, 'Refit protocol differs')
    require(protocol['predictions']['threshold'] == .5 and protocol['calendar']['prediction_cutoff_utc'] == CUTOFF, 'Prediction protocol differs')


def fit_refit(frame, cohort_ids, core):
    """New adapter: unchanged constructor, fresh training-only imputer, no eval_set."""
    validate_training(frame, cohort_ids)
    training = frame.sort_values(['sale_year','appid']).reset_index(drop=True)
    X = core.numeric_predictors(training)
    require(not X.isna().all().any(), 'All-missing training feature; structural-zero contingency forbidden')
    model = core.pipeline('xgboost')
    with core.threadpool_limits(limits=1):
        model.fit(X, training.discount_observed.to_numpy())
    profile = temporal.verify_preprocessing({'xgboost':model}, training, core)['xgboost']
    profile['all_missing_rule'] = 'Stop before fitting if any training predictor is entirely missing; no structural-zero filling.'
    require(profile['training_years'] == [2023,2024,2025], 'Wrong refit years')
    return model, profile


def classify(probabilities, core):
    p = core.np.asarray(probabilities)
    require(p.ndim == 1 and core.np.isfinite(p).all() and ((p >= 0)&(p <= 1)).all(), 'Invalid predicted probability')
    return (p >= .5).astype(int)


def positive_probabilities(model, frame, core):
    X = core.numeric_predictors(frame)
    with core.threadpool_limits(limits=1):
        probabilities = model.predict_proba(X)[:,list(model.classes_).index(1)]
    classify(probabilities,core)
    return probabilities


def coverage_group(count):
    return '0' if count == 0 else '1-9' if count < 10 else '10-29' if count < 30 else '30+'


def prediction_rows(vectors, availability, probabilities, core):
    require(len(vectors) == len(availability) == len(probabilities), 'Prediction/identity lengths differ')
    classes = classify(probabilities,core)
    rows = []
    for vector,available,p,label in zip(vectors,availability,probabilities,classes):
        require(vector['appid'] == int(available['appid']), 'Availability join mismatch')
        missing = [f for f in FEATURES.ALLOWLIST if vector[f] is None]
        rows.append(dict(appid=vector['appid'],game_name=available['game_name'],sale_year=2026,
            prediction_cutoff_utc=CUTOFF,predicted_probability=float(p),predicted_operational_label=int(label),
            prior_price_record_count=vector['prior_price_record_count'],prior_discount_count=vector['prior_discount_count'],
            coverage_group=coverage_group(vector['prior_price_record_count']),
            has_prior_price_history=vector['has_prior_price_history'],has_prior_discount_observation=vector['has_prior_discount_observation'],
            missing_feature_count=len(missing),observed_feature_count=15-len(missing),all_15_features_nonmissing=not missing,
            missing_feature_names=json.dumps(missing),successful_empty_history=available['successful_empty_history'],
            history_received_at_utc=available['history_received_at_utc'],
            excluded_at_or_after_cutoff=available['excluded_at_or_after_cutoff'],
            latest_qualifying_prior_timestamp=available['latest_qualifying_prior_timestamp'],
            retrospective_event_time_filtered=True,point_in_time_provider_availability_proven=False,
            prediction_description=DESCRIPTION))
    return rows


def summaries(rows, vectors, core):
    frame = core.pd.DataFrame(rows)
    p = frame.predicted_probability
    count = int(frame.predicted_operational_label.sum())
    corr = p.corr(frame.prior_price_record_count, method='spearman') if p.nunique()>1 and frame.prior_price_record_count.nunique()>1 else None
    summary = dict(description=DESCRIPTION,games=len(rows),predicted_positive=count,predicted_operational_zero=len(rows)-count,
        predicted_positive_percent=100*count/len(rows),predicted_zero_percent=100*(len(rows)-count)/len(rows),
        probability_min=float(p.min()),probability_max=float(p.max()),probability_mean=float(p.mean()),
        probability_std_population=float(p.std(ddof=0)),
        probability_quantiles={str(q):float(p.quantile(q)) for q in (0,.01,.05,.25,.5,.75,.95,.99,1)},
        probability_vs_observation_count_spearman=float(corr) if corr is not None and core.np.isfinite(corr) else None,
        threshold=.5,observed_2026_outcomes_used=False,calibration_or_performance_estimated=False)
    coverage = []
    for name in ('0','1-9','10-29','30+'):
        part = frame[frame.coverage_group.eq(name)];n = len(part);ones = int(part.predicted_operational_label.sum())
        coverage.append(dict(coverage_group=name,games=n,predicted_positive=ones,predicted_operational_zero=n-ones,
            predicted_positive_percent=100*ones/n if n else None,mean_probability=float(part.predicted_probability.mean()) if n else None,
            median_probability=float(part.predicted_probability.median()) if n else None,
            games_with_missing_features=int(part.missing_feature_count.gt(0).sum())))
    missing = []
    for feature in FEATURES.ALLOWLIST:
        for label in (0,1):
            selected = [v for v,r in zip(vectors,rows) if r['predicted_operational_label'] == label]
            n = len(selected);nulls = sum(v[feature] is None for v in selected)
            missing.append(dict(feature=feature,predicted_operational_label=label,games=n,missing=nulls,
                                missing_percent=100*nulls/n if n else None))
    patterns = [dict(missing_features=n,games=count,predicted_positive=sum(r['predicted_operational_label'] for r in rows if r['missing_feature_count']==n))
                for n,count in sorted(Counter(r['missing_feature_count'] for r in rows).items())]
    top = sorted([r for r in rows if r['predicted_operational_label']==1], key=lambda r:(-r['predicted_probability'],r['appid']))[:10]
    bottom = sorted([r for r in rows if r['predicted_operational_label']==0], key=lambda r:(r['predicted_probability'],r['appid']))[:10]
    counts,edges = core.np.histogram(p.to_numpy(), bins=core.np.linspace(0,1,21))
    histogram = [dict(lower_inclusive=float(edges[i]),upper=float(edges[i+1]),upper_inclusive=i==19,games=int(n)) for i,n in enumerate(counts)]
    return dict(summary=summary,coverage=coverage,missingness_by_class=missing,missingness_patterns=patterns,
                top_10_predicted_positive=top,bottom_10_predicted_zero=bottom,probability_histogram=histogram)


def write_json(path, value, core):
    temporal.write_json(path,value,core)


def write_csv(path, rows, core):
    temporal.write_csv(path,rows,core)


def reconcile_phase8a(audit, core):
    saved = read_csv(ROOT/'reports/cohort_2000_2026_feasibility/audit_feature_values.csv')
    current = [{k:'' if v is None else str(v) for k,v in row.items()} for row in audit['vectors']]
    require(saved == current, 'Reconstructed features differ from frozen Phase 8A')
    require(audit['provenance'] == read_json(ROOT/'reports/cohort_2000_2026_feasibility/feature_provenance.json'), 'Feature provenance differs')
    require(audit['summary'] == read_json(ROOT/'reports/cohort_2000_2026_feasibility/feasibility_summary.json'), 'Availability audit differs')


def historical_comparison(core):
    # Read saved 2025 scores only; never predict with, refit, or modify the evaluated model.
    old = core.pd.read_csv(ROOT/'reports/cohort_2000_models/held_out_predictions.csv')
    old = old[old.model_name.eq('xgboost')].copy()
    require(len(old)==2000 and old.appid.nunique()==2000 and set(old.sale_year)=={2025}, 'Invalid frozen 2025 predictions')
    old['coverage_group'] = old.prior_price_record_count.map(coverage_group)
    return dict(context='Frozen 2025 evaluated model trained on 2023–2024; 2026 refit trained on 2023–2025. Descriptive score/coverage comparison only.',
                games=2000,predicted_positive=int(old.predicted_class.sum()),
                mean_probability=float(old.predicted_probability.mean()),
                probability_vs_observation_count_spearman=float(old.predicted_probability.corr(old.prior_price_record_count,method='spearman')),
                coverage=[dict(coverage_group=k,games=len(g),predicted_positive=int(g.predicted_class.sum()),
                               predicted_positive_percent=100*float(g.predicted_class.mean()),mean_probability=float(g.predicted_probability.mean()))
                          for k,g in old.groupby('coverage_group',sort=True)])


def readme(result, comparison, profile):
    s = result['summary']
    ranking = '\n'.join('| '+str(r['appid'])+' | '+r['game_name'].replace('|','\\|')+' | '+f"{r['predicted_probability']:.6f}"+' |'
                         for r in result['top_10_predicted_positive'])
    lowest = '\n'.join('| '+str(r['appid'])+' | '+r['game_name'].replace('|','\\|')+' | '+f"{r['predicted_probability']:.6f}"+' |'
                        for r in result['bottom_10_predicted_zero'])
    return f'''# Phase 8B — retrospective 2026 predictions

**{DESCRIPTION}** These are model scores for observed ITAD Autumn Sale discount evidence, not independently verified Steam sale participation. Predicted operational zero means the model predicts no discount observed in available evidence; it does not establish verified nonparticipation.

## Results

Exactly {s['games']:,} cohort games receive one probability and class: **{s['predicted_positive']:,} positives ({s['predicted_positive_percent']:.2f}%)** and **{s['predicted_operational_zero']:,} operational zeros ({s['predicted_zero_percent']:.2f}%)**. Threshold is unchanged: probability ≥0.5 yields 1. Mean probability {s['probability_mean']:.6f}, median {s['probability_quantiles']['0.5']:.6f}, range {s['probability_min']:.6f}–{s['probability_max']:.6f}. Full quantiles, histogram, ranks, coverage and missingness tables accompany this report. Rankings use probability then ascending AppID for ties; they are predictions, not observed outcomes.

### Ten highest-probability predicted positives

| AppID | Game | Probability |
| --- | --- | ---: |
{ranking}

### Ten lowest-probability predicted operational zeros

| AppID | Game | Probability |
| --- | --- | ---: |
{lowest}

## Frozen inputs and adapters

Only `predict_cohort_2026.py` and new offline tests/runner are introduced. The unchanged feature core receives full parsed histories and an explicit verified 2026 window, bypassing the old wrapper's January-2026 truncation. Event timestamps must be **strictly before {CUTOFF}**; records at the boundary, within the sale, or later are excluded. Sale end is 2026-10-08T17:00:00Z. No 2026 outcomes are generated or inspected for training, tuning, thresholding, selection or evaluation. Audit metadata counts excluded records but their prices/discounts never enter predictors.

The 2,000×15 predictor matrix plus four identity/audit columns matches Phase 8A values exactly. All 2,000 vectors pass cutoff-removal/exact-boundary invariance checks. Four price-related predictors each retain 81 nulls; three discount-related predictors each retain 336. There are 1,664 complete vectors, 255 with only three discount-derived nulls, and 81 with seven price-derived nulls. Blank CSV cells mean missing, not zero. Definitions, ordering, type/range checks and historical labels are unchanged. No current price/popularity or previous sale participation predictor is introduced.

The fresh model uses the unchanged selected configuration: 100 trees, depth 3, learning rate .05, subsample/column sample .8, binary:logistic objective, logloss metric, seed 42, n_jobs=1. ColumnTransformer selects the 15 approved columns, followed by training-median imputation without indicators/scaling. All 6,000 frozen 2023–2025 rows (3,030 positive, 2,970 zero) fit the new imputer and classifier; 2026 rows never fit preprocessing. No feature is entirely missing in training. No hyperparameter search, feature selection, calibration fitting, early stopping or model/threshold selection occurs.

`refit_2023_2025_pipeline.joblib` is the new complete inference pipeline. Separate `preprocessing_2023_2025.joblib` and `xgboost_2023_2025.joblib` are saved components of that same fit. The original Phase 7A selected model and 2025 evaluation remain immutable; their performance estimates belong to that older 2023–2024 fit, not this new refit. Versions and exact preprocessing medians are in configuration/preprocessing manifests.

## Coverage and methodological limitations

Score-versus-observation-count Spearman is **{s['probability_vs_observation_count_spearman']:.4f}**, compared with **{comparison['probability_vs_observation_count_spearman']:.4f}** for saved 2025 scores. Coverage groups are unchanged (0, 1–9, 10–29, 30+ price observations). Tables include subgroup sample sizes, predicted class counts and score summaries; no 2026 accuracy/calibration or actual-class counts are inferred. Coverage correlation is descriptive, not causal. Counts retain duplicate observations and represent observation density, not distinct campaigns or discounted-day frequency.

All history receipts are October 5–13, after cutoff. Event time does **not** demonstrate provider availability before cutoff: zero vectors are fully point-in-time proven. Backfill, source release-date accuracy, pre-release/request-boundary observations and past timestamp/shop ambiguities remain limitations. Missing histories are not evidence of no actual discounts. Phase 8A range diagnostics are retained: several valid recency/count/age/discount values exceed historical training ranges; no clipping or feature redesign is applied. Repeated games across years and observational labels limit claims about unseen-game performance or genuine prospective forecasts. No independent 2026 outcome validation is performed here.

## Reproduction and integrity

Run from repository root into a fresh destination (the runner refuses existing directories):

```sh
env -u ITAD_API_KEY PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp \\
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \\
  /usr/bin/python3 -B tests/run_prediction_2026_offline.py \\
  --results /private/tmp/steam-2026-prediction-tests.json

env -u ITAD_API_KEY PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp \\
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \\
  /usr/bin/python3 -B src/predict_cohort_2026.py \\
  --output-dir reports/cohort_2000_2026_predictions_reproduction \\
  --test-results /private/tmp/steam-2026-prediction-tests.json
```

Offline guards block network/subprocesses and confine writes to the fresh output/runtime namespace. Frozen input hashes, dependency versions, exact cohort/feature/target membership, training medians, parameters, probability ranges and threshold are checked before delivery. An independent same-configuration verification refit in runtime storage must reproduce predictor/prediction CSVs and booster JSON byte-for-byte. This verification is not model selection; no old model is fitted and no 2025 evaluation is repeated. Serialized pipeline/component reloads must yield identical probabilities. `reproduction.json`, `offline_test_results.json`, `validation.json`, `input_checksums.json` and `checksums.json` record the results. Execution receipts can differ with additional preexisting files; core prediction payloads are deterministic in the recorded environment.

All existing data/report/model files and 219 protected artifacts must retain phase-start bytes. Historical baseline agreement remains 218/219: the known ordering-only mismatch in `autumn_sale_evidence_records.csv` is preserved without repair. All 2,000 caches, cohorts, labels, Phase 6/7/8A outputs, archived checkpoints and the 3,816-entry journal remain unchanged. Preservation and historical baseline agreement are separate checks.

## Recommended Phase 8C

Build separate minimalist light-theme figures from these saved outputs: score histogram/quantiles; positive-versus-operational-zero counts; observation-count versus score with coverage groups; subgroup prediction rates and sample sizes; feature missingness by predicted class; top/bottom-ranked game tables; descriptive 2025-versus-2026 coverage/score comparison. Keep the retrospective/backfill warning visible. Do not present score distributions as calibrated 2026 outcome probabilities or generate accuracy/ROC/confusion/calibration plots without independently authorized outcome analysis.
'''


def run(destination, test_results):
    before = snapshot()
    frozen_hashes = verify_indexes()
    require(Journal(ROOT/'data/cohorts/itad/cache',3816,readonly=True).counts()['total_http_attempts']==3816, 'Journal differs before execution')
    tests = read_json(test_results)
    require(tests['passed'] and tests['failures']==0 and tests['errors']==0 and tests['network_guard'] and tests['repository_write_guard'], 'Offline regressions did not pass')
    require(all(digest(ROOT/name)==sha for name,sha in tests['test_source_sha256'].items()), 'Tests changed since execution')
    core = temporal.cores()
    protocol = read_json(ROOT/'reports/cohort_2000_2026_feasibility/final_refit_prediction_protocol.json')
    selection = read_json(ROOT/'reports/cohort_2000_models/selection.json')
    verify_configuration(core,selection,protocol)
    games = load_cohort(ROOT/'data/cohorts/cohort_2000.csv');ids = [int(g['AppID']) for g in games]
    require(len(ids)==2000 and len(set(ids))==2000 and digest(ROOT/protocol['cohort']['path'])==protocol['cohort']['sha256'], 'Frozen cohort differs')
    train,_,inputs = temporal.load_frozen(ROOT/'reports/cohort_2000_modeling',core)
    validate_training(train,ids)
    calendar = read_json(ROOT/'reports/cohort_2000_2026_feasibility/verified_sale_dates.json')
    with frozen_model_guard(core):
        audit = feasibility.build(calendar,core)
    missingness = validate_features(audit['vectors'],ids,feasibility.verified_window(calendar)[2],EXPECTED_NULLS)
    reconcile_phase8a(audit,core)
    assert_preserved(before)
    destination.mkdir()
    write_json(destination/'input_checksums.json',dict(frozen_artifact_sha256=frozen_hashes,preservation_sha256=before,
        frozen_training=inputs,source_sha256={str(p.relative_to(ROOT)):digest(p) for p in (ROOT/'src/predict_cohort_2026.py',ROOT/'tests/test_prediction_2026.py',ROOT/'tests/run_prediction_2026_offline.py')}),core)
    write_csv(destination/'features_2026.csv',audit['vectors'],core)
    write_csv(destination/'feature_missingness.csv',audit['missingness'],core)
    write_json(destination/'feature_provenance.json',audit['provenance'],core)
    write_json(destination/'feature_schema_manifest.json',dict(predictor_order=list(FEATURES.ALLOWLIST),
        csv_column_order=list(FEATURES.FIELDS),predictor_count=15,definitions=FEATURES.DEFINITIONS,
        numeric_types={f:'integer' if f in set(FEATURES.STATIC)|{'prior_price_record_count','prior_discount_count','has_prior_price_history','has_prior_discount_observation'} else 'numeric, nullable' for f in FEATURES.ALLOWLIST},
        missingness=missingness,cutoff_utc=CUTOFF,timestamp_rule='event_timestamp < cutoff',
        label_or_outcome_columns=[],feature_definition_version=FEATURES.VERSION),core)
    write_json(destination/'configuration_manifest.json',dict(description=DESCRIPTION,selected_configuration=selection['selected_configuration'],
        selection_receipt_sha256=digest(ROOT/'reports/cohort_2000_models/selection.json'),training_years=[2023,2024,2025],training_rows=6000,
        positive_labels=3030,operational_zero_labels=2970,threshold=.5,random_seed=42,
        dependency_versions={name:metadata.version(name) for name in protocol['dependency_versions']},python_version=platform.python_version(),
        original_evaluated_model='reports/cohort_2000_models/selected_model.joblib',
        new_refit_pipeline='refit_2023_2025_pipeline.joblib',hyperparameter_search=False,model_selection=False,threshold_tuning=False,
        features=list(FEATURES.ALLOWLIST),no_2026_outcomes_used=True,provider_point_in_time_availability_proven=False),core)
    model,profile = fit_refit(train,ids,core)
    frame = core.pd.DataFrame(audit['vectors'])
    probabilities = positive_probabilities(model,frame,core)
    rows = prediction_rows(audit['vectors'],audit['availability'],probabilities,core)
    require(len(rows)==2000 and {r['appid'] for r in rows}==set(ids), 'Incomplete predictions')
    write_csv(destination/'predictions_2026.csv',rows,core)
    write_json(destination/'preprocessing.json',profile,core)
    for name,component in [('refit_2023_2025_pipeline.joblib',model),('preprocessing_2023_2025.joblib',model[:-1]),('xgboost_2023_2025.joblib',model.named_steps['classifier'])]:
        core.joblib.dump(component,destination/name)
    model.named_steps['classifier'].save_model(str(destination/'xgboost_2023_2025.json'))
    restored = core.joblib.load(destination/'refit_2023_2025_pipeline.joblib')
    core.np.testing.assert_array_equal(probabilities,positive_probabilities(restored,frame,core))
    preprocessing = core.joblib.load(destination/'preprocessing_2023_2025.joblib')
    estimator = core.joblib.load(destination/'xgboost_2023_2025.joblib')
    core.np.testing.assert_array_equal(probabilities,estimator.predict_proba(preprocessing.transform(core.numeric_predictors(frame)))[:,1])
    # Independent frozen-configuration refit solely for the requested deterministic verification.
    with tempfile.TemporaryDirectory(prefix='reproduction-') as temporary:
        temp = Path(temporary)
        with frozen_model_guard(core):
            repeated = feasibility.build(calendar,core)
        require(repeated['vectors']==audit['vectors'], 'Independent feature build differs')
        second,second_profile = fit_refit(train,ids,core)
        require(second_profile==profile, 'Independent training-only preprocessing differs')
        p2 = positive_probabilities(second,core.pd.DataFrame(repeated['vectors']),core)
        core.np.testing.assert_array_equal(probabilities,p2)
        second_rows = prediction_rows(repeated['vectors'],repeated['availability'],p2,core)
        write_csv(temp/'features_2026.csv',repeated['vectors'],core)
        write_csv(temp/'predictions_2026.csv',second_rows,core)
        second.named_steps['classifier'].save_model(str(temp/'xgboost_2023_2025.json'))
        payloads = ('features_2026.csv','predictions_2026.csv','xgboost_2023_2025.json')
        require(all(digest(temp/name)==digest(destination/name) for name in payloads), 'Deterministic reproduction failed')
    write_json(destination/'reproduction.json',dict(independent_refit_verification=True,primary_fits=1,verification_fits=1,
        original_models_refitted=False,maximum_absolute_probability_difference=0,
        byte_identical_payloads={name:digest(destination/name) for name in payloads},
        complete_pipeline_and_separate_components_reload_identical=True,phase8a_feature_values_identical=True,
        independent_full_feature_build_identical=True,training_medians_independently_verified=True),core)
    result = summaries(rows,audit['vectors'],core)
    comparison = historical_comparison(core)
    write_json(destination/'prediction_summary.json',result['summary'],core)
    write_json(destination/'frozen_2025_score_comparison.json',comparison,core)
    for name in ('coverage','missingness_by_class','missingness_patterns','top_10_predicted_positive','bottom_10_predicted_zero','probability_histogram'):
        write_csv(destination/(name+'.csv'),result[name],core)
    write_json(destination/'offline_test_results.json',tests,core)
    (destination/'README.md').write_text(readme(result,comparison,profile),encoding='utf-8')
    protected = read_json(ROOT/'tests/scalable_artifact_hashes.json')
    journal = Journal(ROOT/'data/cohorts/itad/cache',3816,readonly=True).counts()
    require(journal['total_http_attempts']==3816, 'Journal changed')
    assert_preserved(before)
    write_json(destination/'validation.json',dict(preserved_input_files=len(before),protected_artifacts_preserved=219,
        historical_baseline_matches=sum(digest(ROOT/name)==v['sha256'] for name,v in protected.items()),
        existing_baseline_mismatch='data/intermediate/autumn_sale_evidence_records.csv',
        existing_baseline_mismatch_preserved_sha256=digest(ROOT/'data/intermediate/autumn_sale_evidence_records.csv'),
        frozen_input_checksums_verified=True,frozen_configuration_verified=True,cohort_games=2000,training_rows=6000,
        target_year=2026,feature_shape=[2000,15],unique_predictions=2000,missingness_matches_phase8a=True,
        timestamp_violations=0,boundary_invariant_vectors=2000,excluded_postcutoff_records=audit['summary']['excluded_at_or_after_cutoff_records'],
        fully_point_in_time_proven_vectors=0,old_january_filter_bypassed=True,api_calls=0,journal=journal,
        no_2026_outcomes_used=True,no_original_models_refitted=True,no_frozen_inputs_modified=True),core)
    write_json(destination/'checksums.json',{str(p.relative_to(destination)):digest(p) for p in sorted(destination.rglob('*')) if p.is_file()},core)
    assert_preserved(before)
    print(json.dumps(result['summary'],sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--test-results',type=Path,required=True)
    args = parser.parse_args();destination = args.output_dir.resolve()
    require(destination.is_relative_to(ROOT/'reports') and not destination.exists(), 'Choose a new reports directory')
    require(not any(p.is_symlink() for p in [args.output_dir.absolute(),*args.output_dir.absolute().parents]), 'Symlink destination forbidden')
    runtime = Path('/private/tmp/steam-2026-prediction-runtime');runtime.mkdir(exist_ok=True)
    os.environ['MPLCONFIGDIR'] = str(runtime);tempfile.tempdir = str(runtime)
    def guard(event,values):
        if event in ('socket.connect','socket.getaddrinfo'):raise RuntimeError('Offline predictions; no HTTP')
        if event=='subprocess.Popen':raise OSError('External commands forbidden')
        if event=='open' and (values[2] or 0)&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):
            if isinstance(values[0],(str,bytes,os.PathLike)):
                path=Path(os.fsdecode(values[0])).resolve()
                require(path.is_relative_to(destination) or path.is_relative_to(runtime),'Writes confined to new outputs/runtime')
        if event in ('os.remove','os.rename','os.mkdir','os.rmdir','os.symlink','os.link','os.chmod','os.utime'):
            for path in mutation_paths(event,values):
                require(path.is_relative_to(destination) or path.is_relative_to(runtime),'Mutations confined to new outputs/runtime')
    sys.addaudithook(guard)
    run(destination,args.test_results)


if __name__=='__main__':main()
