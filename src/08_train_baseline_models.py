"""Phase 7A only: offline, chronological baseline experiments for recorded discounts.

Reproduce and verify: python3 -B src/08_train_baseline_models.py --verify
No prior-phase artifacts are regenerated. No tuning or threshold optimization.
"""
import argparse
import csv
from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch

# A writable local cache, outside protected historical inputs. Agg requires no GUI.
os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir()) / 'steam_phase7a_mpl'))
os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('MKL_NUM_THREADS', '1')
import joblib
import numpy as np
import pandas as pd
import scipy
from scipy.special import expit
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, average_precision_score, brier_score_loss,
                            confusion_matrix, log_loss, precision_recall_curve, roc_auc_score, roc_curve)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plotting_style import BLUE, ORANGE, GRAY, light_style, save_figure, plt

ROOT = Path(__file__).resolve().parents[1]
FEATURE_MANIFEST = 'reports/autumn_sale_feature_manifest.json'
PHASE6_RECEIPT = 'reports/autumn_sale_feature_validation.json'
FEATURES = 'data/intermediate/autumn_sale_features.csv'
TABLE = 'data/intermediate/autumn_sale_modeling_table.csv'
TARGET = 'discount_observed'
KEYS = ['appid', 'sale_year']
TRAIN_YEARS = [2023, 2024]
VALIDATION_YEAR = 2025
SEED = 42
THRESHOLD = 0.50
# Frozen experiment configuration, declared before any validation evaluation.
LOGISTIC_PARAMS = dict(penalty='l2', C=1.0, solver='lbfgs', max_iter=2000,
                       random_state=SEED, class_weight=None, tol=1e-4)
APPROVED = ['game_age_days', 'release_year', 'release_month', 'release_quarter',
            'prior_price_record_count', 'prior_discount_count', 'prior_discount_rate',
            'days_since_last_price_record', 'days_since_last_discount', 'max_prior_discount_pct',
            'mean_prior_discount_pct', 'last_observed_price', 'last_observed_discount_pct',
            'has_prior_price_history', 'has_prior_discount_observation']
BINARY = ['has_prior_price_history', 'has_prior_discount_observation']
PROHIBITED = {'appid', 'sale_year', 'prediction_cutoff_utc', TARGET, 'evidence_category',
              'pu_status', 'audit_release_hour_uncertain'}
TARGET_DEFINITION = ('1: a qualifying Steam-store discount was recorded during the official Autumn Sale '
                     'window; 0: no qualifying discount was recorded. Zero does not establish absence '
                     'of an actual discount. Probabilities concern recorded occurrence, not verified participation.')
PREDICTIONS = 'data/processed/autumn_sale_2025_baseline_predictions.csv'
METRICS = 'reports/autumn_sale_baseline_metrics.json'
MANIFEST = 'reports/autumn_sale_baseline_model_manifest.json'
VALIDATION = 'reports/autumn_sale_baseline_validation.json'
EVALUATION = 'reports/autumn_sale_baseline_evaluation.md'
PLOT_DATA = 'reports/autumn_sale_baseline_plot_data.json'
MODEL_PATHS = {'bernoulli_baseline': 'models/bernoulli_baseline.joblib',
               'logistic_regression': 'models/logistic_regression.joblib'}
FIGURES = ['bernoulli_distribution', 'logistic_sigmoid', 'logistic_coefficients',
           'logistic_confusion_matrix', 'baseline_roc_curves', 'baseline_pr_curves',
           'logistic_probability_distribution', 'logistic_reliability']
OUTPUTS = [PREDICTIONS, METRICS, MANIFEST, VALIDATION, EVALUATION, PLOT_DATA] + list(MODEL_PATHS.values()) + [f'reports/figures/{n}.png' for n in FIGURES]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest() if hasattr(hashlib, 'file_digest') else _digest_stream(f)


def _digest_stream(f):
    h = hashlib.sha256()
    for chunk in iter(lambda: f.read(1024 * 1024), b''):
        h.update(chunk)
    return h.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n', encoding='utf-8')


@contextmanager
def offline_guard():
    attempts = []
    def forbidden(*args, **kwargs):
        attempts.append('network_attempt')
        raise AssertionError('Network forbidden during Phase 7A execution')
    with patch.object(socket, 'getaddrinfo', forbidden), patch.object(socket, 'create_connection', forbidden), \
         patch.object(socket.socket, 'connect', forbidden), patch.object(socket.socket, 'connect_ex', forbidden):
        yield attempts
    require(not attempts, 'A network request was attempted')


def protected_hashes(root=ROOT):
    """Verify the Phase 6 receipt chain; freeze its outputs, source, tests, and receipt."""
    r = json.loads((root / PHASE6_RECEIPT).read_text())
    expected = {}
    for group in ['protected_after_sha256', 'source_sha256', 'output_sha256']:
        for p, h in r[group].items():
            require(p not in expected or expected[p] == h, f'Conflicting protected hash: {p}')
            expected[p] = h
    actual = {}
    for p, h in sorted(expected.items()):
        require((root / p).is_file(), f'Missing protected input: {p}')
        actual[p] = digest(root / p)
        require(actual[p] == h, f'Protected input changed: {p}')
    actual[PHASE6_RECEIPT] = digest(root / PHASE6_RECEIPT)
    return actual


def source_hashes(root):
    paths = ['src/08_train_baseline_models.py', 'src/plotting_style.py', 'tests/test_baseline_models.py', 'requirements-baseline.txt']
    return {p: digest(root / p) for p in paths}


def read_csv(path):
    with Path(path).open(newline='', encoding='utf-8') as f:
        r = csv.reader(f)
        header = next(r)
        require(len(header) == len(set(header)), f'Duplicate CSV columns: {path}')
        require(all(len(row) == len(header) for row in r), f'Malformed CSV rows: {path}')
    return pd.read_csv(path)


def validate_manifest(m):
    allow = m['baseline_feature_allowlist']
    require(allow == APPROVED, 'Phase 6 manifest allowlist disagrees with approved experiment schema')
    require(not PROHIBITED.intersection(allow), 'Prohibited predictor in manifest')
    require(m['target_column'] == TARGET, 'Operational target mismatch')
    declared = [f['feature_name'] for f in m['features'] if f['baseline_allowlist']]
    require(declared == allow, 'Manifest per-feature approval disagrees with allowlist')
    require(m['identifier_columns'] == ['appid', 'sale_year', 'prediction_cutoff_utc'] and
            m['audit_only_columns'] == ['audit_release_hour_uncertain'], 'Manifest linkage/audit mismatch')
    return allow


def select_predictors(frame, allow=APPROVED):
    require(list(allow) == APPROVED, 'Unapproved predictor selection')
    require(set(allow) <= set(frame.columns), 'Missing approved predictor')
    result = frame.loc[:, allow].copy()
    for f in allow:
        result[f] = pd.to_numeric(result[f], errors='raise').astype(float)
    require(not np.isinf(result.to_numpy()).any(), 'Infinite predictor values')
    return result


def chronological_split(frame):
    require(set(frame.sale_year.unique()) == {2023, 2024, 2025}, 'Unsupported sale years')
    require(not frame.duplicated(KEYS).any(), 'Duplicate game-year records')
    train = frame[frame.sale_year.isin(TRAIN_YEARS)].sort_values(['sale_year', 'appid']).reset_index(drop=True)
    valid = frame[frame.sale_year.eq(VALIDATION_YEAR)].sort_values(KEYS).reset_index(drop=True)
    require(len(train) == 200 and len(valid) == 100, 'Expected 200 training / 100 validation rows')
    require(set(train.appid) == set(valid.appid) and train.appid.nunique() == 100, 'Repeated pilot game identities mismatch')
    require(all(train.groupby('sale_year').size() == 100), 'Expected 100 rows per training year')
    return train, valid


def inspect_inputs(root=ROOT):
    m = json.loads((root / FEATURE_MANIFEST).read_text())
    allow = validate_manifest(m)
    frame, features = read_csv(root / TABLE), read_csv(root / FEATURES)
    schema = m['identifier_columns'] + allow + m['audit_only_columns']
    require(list(features.columns) == schema and list(frame.columns) == schema + [TARGET], 'Manifest / table schema disagreement')
    require(len(frame) == len(features) == 300, 'Expected 300 game-year observations')
    pd.testing.assert_frame_equal(frame[schema].sort_values(KEYS).reset_index(drop=True),
                                  features.sort_values(KEYS).reset_index(drop=True))
    require(frame[TARGET].notna().all() and set(frame[TARGET]) == {0, 1}, 'Invalid operational labels')
    metadata = {f['feature_name']: f for f in m['features']}
    X = select_predictors(frame, allow)
    for f in allow:
        require(pd.api.types.is_numeric_dtype(frame[f]), f'Non-numeric source feature: {f}')
        if metadata[f]['type'] == 'integer':
            require(X[f].notna().all() and (X[f] == np.floor(X[f])).all(), f'Invalid integer feature: {f}')
    for f in BINARY:
        require(set(X[f]) <= {0, 1}, f'Invalid binary indicator: {f}')
    train, valid = chronological_split(frame)
    require(train[TARGET].value_counts().to_dict() == {1: 115, 0: 85}, 'Training target count mismatch')
    require(valid[TARGET].value_counts().to_dict() == {1: 60, 0: 40}, 'Validation target count mismatch')
    r = json.loads((root / PHASE6_RECEIPT).read_text())
    require(r['cutoff_violations'] == 0 and r['feature_list'] == allow, 'Phase 6 provenance disagreement')
    provenance = {(p['appid'], p['sale_year']): p for p in r['pair_pre_cutoff_provenance']}
    require(set(provenance) == set(map(tuple, frame[KEYS].to_numpy())), 'Provenance identity disagreement')
    # Verified Phase 6 cutoffs are cross-checked against each row's recorded provenance.
    for row in frame.to_dict('records'):
        p = provenance[(row['appid'], row['sale_year'])]
        for key in ['latest_valid_prior_timestamp', 'latest_discount_prior_timestamp']:
            if p[key]:
                require(pd.Timestamp(p[key]) < pd.Timestamp(row['prediction_cutoff_utc']), 'Future price provenance')
        require(p['cutoff_violations'] == 0, 'Future observations in Phase 6 provenance')
    labels = read_csv(root / 'data/intermediate/autumn_sale_operational_labels.csv')
    merged = frame.merge(labels[KEYS + [TARGET, 'sale_start_utc']], on=KEYS, validate='one_to_one', suffixes=('', '_source'))
    require(len(merged) == 300 and (merged[TARGET] == merged[TARGET + '_source']).all(), 'Frozen operational label disagreement')
    require((merged.prediction_cutoff_utc == merged.sale_start_utc).all(), 'Prediction cutoff disagreement')
    return frame, m, dict(input_rows=300, feature_only_rows=300, unique_games=100,
        training_rows=len(train), validation_rows=len(valid), training_target_counts={'0':85,'1':115},
        validation_target_counts={'0':40,'1':60}, approved_features=allow,
        numeric_source_types={f:str(frame[f].dtype) for f in allow}, binary_indicators=BINARY,
        training_missingness={f:int(train[f].isna().sum()) for f in allow},
        validation_missingness={f:int(valid[f].isna().sum()) for f in allow},
        training_constant_features=[f for f in allow if train[f].nunique(dropna=True) == 1],
        training_all_missing_features=[f for f in allow if train[f].isna().all()],
        phase6_cutoff_violations=0, target_column=TARGET)


def fit_models(train, allow=APPROVED):
    require(set(train.sale_year.unique()) == set(TRAIN_YEARS), 'Fitting requires only 2023–2024')
    train = train.sort_values(['sale_year', 'appid']).reset_index(drop=True)
    X, y = select_predictors(train, allow), train[TARGET].to_numpy()
    excluded = [f for f in allow if X[f].isna().all()]
    used = [f for f in allow if f not in excluded]
    require(bool(used), 'No observed training predictors')
    pipeline = Pipeline([
        ('select', ColumnTransformer([('approved', 'passthrough', used)], remainder='drop', verbose_feature_names_out=False)),
        ('impute', SimpleImputer(strategy='median', add_indicator=False, keep_empty_features=True)),
        ('scale', StandardScaler()), ('classifier', LogisticRegression(**LOGISTIC_PARAMS))])
    prior = DummyClassifier(strategy='prior', random_state=SEED)
    with threadpool_limits(limits=1):
        prior.fit(np.zeros((len(y), 1)), y)
        pipeline.fit(X, y)
    require(pipeline.named_steps['classifier'].n_iter_[0] < LOGISTIC_PARAMS['max_iter'], 'Logistic regression did not converge')
    return {'bernoulli_baseline': prior, 'logistic_regression': pipeline}, dict(
        strategy='training-only median imputation, then StandardScaler; existing coverage flags retained',
        additional_missingness_indicators=[], excluded_all_missing_training_features=excluded,
        all_missing_rule='Exclude entirely missing training features using training predictors only; never use validation values.',
        transformed_feature_names=pipeline[:-1].get_feature_names_out().tolist(),
        retained_constant_training_features=[f for f in used if X[f].nunique(dropna=True) == 1],
        imputation_statistics=pipeline.named_steps['impute'].statistics_.tolist(),
        scaler_mean=pipeline.named_steps['scale'].mean_.tolist(),
        scaler_variance=pipeline.named_steps['scale'].var_.tolist(),
        scaler_scale=pipeline.named_steps['scale'].scale_.tolist(), scaler_samples=int(pipeline.named_steps['scale'].n_samples_seen_))


def classes(probabilities):
    return (np.asarray(probabilities) >= THRESHOLD).astype(int)


def predict(models, valid):
    valid = valid.sort_values(KEYS).reset_index(drop=True)
    X = select_predictors(valid)
    frames = []
    for name, model in models.items():
        model_X = np.zeros((len(valid), 1)) if name == 'bernoulli_baseline' else X
        p = model.predict_proba(model_X)[:, list(model.classes_).index(1)]
        require(np.isfinite(p).all() and ((p >= 0) & (p <= 1)).all(), 'Invalid prediction probabilities')
        score = model.decision_function(model_X) if name == 'logistic_regression' else np.full(len(valid), np.nan)
        if name == 'logistic_regression':
            require(np.allclose(expit(score), p, rtol=1e-12, atol=1e-14), 'Sigmoid inconsistency')
        f = valid[KEYS].copy()
        f['model_name'], f['actual_label'] = name, valid[TARGET].to_numpy()
        f['predicted_probability'], f['predicted_class'], f['decision_score'] = p, classes(p), score
        frames.append(f)
    out = pd.concat(frames, ignore_index=True)
    require(len(out) == 200 and not out.duplicated(KEYS + ['model_name']).any(), 'Prediction row count/uniqueness failure')
    return out


def evaluate(predictions):
    results = {}
    for name, f in predictions.groupby('model_name', sort=True):
        y, p, c = f.actual_label.to_numpy(), f.predicted_probability.to_numpy(), f.predicted_class.to_numpy()
        tn, fp, fn, tp = confusion_matrix(y, c, labels=[0, 1]).ravel().tolist()
        undefined = {}
        def ratio(num, den, metric):
            if not den:
                undefined[metric] = 'Undefined: zero denominator; reported as JSON null.'
                return None
            return num / den
        both = len(np.unique(y)) == 2
        if not both:
            undefined['roc_auc'] = 'Undefined: validation has only one operational class.'
        if not y.sum():
            undefined['average_precision'] = 'Undefined: no operational positives.'
        results[name] = dict(roc_auc=float(roc_auc_score(y,p)) if both else None,
            average_precision=float(average_precision_score(y,p)) if y.sum() else None,
            brier_score=float(brier_score_loss(y,p)), log_loss=float(log_loss(y,p,labels=[0,1])),
            accuracy=float(accuracy_score(y,c)), precision=ratio(tp,tp+fp,'precision'),
            recall=ratio(tp,tp+fn,'recall'), f1=ratio(2*tp,2*tp+fp+fn,'f1'),
            confusion_matrix=[[tn,fp],[fn,tp]], confusion_matrix_orientation='rows actual [0,1]; columns predicted [0,1]',
            threshold=THRESHOLD, observations=len(f), undefined_metrics=undefined)
    return dict(target_definition=TARGET_DEFINITION,
                validation_positive_prevalence=float(predictions.drop_duplicates(KEYS).actual_label.mean()), models=results)


def model_parameters(models):
    p = models['logistic_regression']
    return dict(bernoulli_class_prior=models['bernoulli_baseline'].class_prior_.tolist(),
                logistic_coefficients=p.named_steps['classifier'].coef_.tolist(),
                logistic_intercept=p.named_steps['classifier'].intercept_.tolist(),
                logistic_iterations=p.named_steps['classifier'].n_iter_.tolist(),
                imputation_statistics=p.named_steps['impute'].statistics_.tolist(),
                scaler_mean=p.named_steps['scale'].mean_.tolist(), scaler_variance=p.named_steps['scale'].var_.tolist())


def build_plot_data(predictions, models, metrics):
    """Every evaluation graphic consumes this receipt of actual fitted-model outputs."""
    logistic = predictions[predictions.model_name.eq('logistic_regression')]
    bins = np.linspace(0, 1, 6)
    index = np.minimum(np.searchsorted(bins, logistic.predicted_probability, side='right') - 1, 4)
    reliability = []
    for i in range(5):
        f = logistic[index == i]
        if len(f):
            reliability.append(dict(bin_left=float(bins[i]), bin_right=float(bins[i+1]), count=len(f),
                mean_probability=float(f.predicted_probability.mean()), positive_fraction=float(f.actual_label.mean())))
    curves = {}
    for name, f in predictions.groupby('model_name'):
        fpr, tpr, _ = roc_curve(f.actual_label, f.predicted_probability, drop_intermediate=False)
        precision, recall, _ = precision_recall_curve(f.actual_label, f.predicted_probability)
        curves[name] = dict(fpr=fpr.tolist(), tpr=tpr.tolist(), precision=precision.tolist(), recall=recall.tolist(),
                           auc=metrics['models'][name]['roc_auc'], ap=metrics['models'][name]['average_precision'])
    names = models['logistic_regression'][:-1].get_feature_names_out().tolist()
    score = logistic.decision_score.to_numpy()
    grid = np.linspace(min(-6, score.min()-0.5), max(6, score.max()+0.5), 400)
    return dict(target_definition=TARGET_DEFINITION,
        bernoulli_probabilities=models['bernoulli_baseline'].class_prior_.tolist(),
        training_years=TRAIN_YEARS, validation_year=VALIDATION_YEAR,
        sigmoid=dict(scores=score.tolist(), probabilities=logistic.predicted_probability.tolist(),
                     appids=logistic.appid.tolist(), curve_scores=grid.tolist(), curve_probabilities=expit(grid).tolist()),
        coefficients=dict(names=names, values=models['logistic_regression'].named_steps['classifier'].coef_[0].tolist()),
        confusion_matrix=metrics['models']['logistic_regression']['confusion_matrix'], curves=curves,
        validation_prevalence=metrics['validation_positive_prevalence'],
        histogram=dict(bins=np.linspace(0,1,11).tolist(), positive=logistic.loc[logistic.actual_label.eq(1),'predicted_probability'].tolist(),
                       negative=logistic.loc[logistic.actual_label.eq(0),'predicted_probability'].tolist()),
        reliability=reliability, reliability_bin_edges=bins.tolist())


def generate_figures(root, data):
    destination = root / 'reports/figures'
    destination.mkdir(parents=True, exist_ok=True)
    def save(fig, name, caption=None):
        save_figure(fig, destination / (name + '.png'), caption)
    with light_style():
        fig, ax = plt.subplots()
        p = data['bernoulli_probabilities']
        ax.bar([0,1],p,color=[ORANGE,BLUE],width=0.55,zorder=3)
        ax.set(xticks=[0,1],xticklabels=['0 = No discount recorded','1 = Discount recorded'], ylim=(0,1),
               ylabel='Probability',title='Bernoulli Baseline: Recorded Discount Probability')
        for x, v in enumerate(p): ax.text(x,v+0.025,f'{v:.3f}',ha='center',fontsize=10)
        ax.grid(axis='y'); ax.set_axisbelow(True)
        save(fig,'bernoulli_distribution','Probabilities estimated from 2023–2024 training labels.')

        fig, ax = plt.subplots()
        s = data['sigmoid']
        ax.plot(s['curve_scores'],s['curve_probabilities'],color=BLUE,label='Sigmoid transformation')
        ax.scatter(s['scores'],s['probabilities'],s=14,alpha=0.45,color=ORANGE,label='2025 predictions',zorder=3)
        ax.axhline(0.5,color=GRAY,linestyle='--',linewidth=0.9)
        ax.axvline(0,color=GRAY,linestyle=':',linewidth=0.9)
        ax.set(xlabel='Logistic regression decision score (log-odds)',
               ylabel='Predicted probability of a recorded discount',ylim=(-0.02,1.02),title='Logistic Regression: Score to Probability')
        ax.legend(); ax.grid(axis='y'); ax.set_axisbelow(True)
        save(fig,'logistic_sigmoid','Actual validation predictions; explanatory transformation, not evidence of accuracy.')

        fig, ax = plt.subplots(figsize=(7.2,5.8))
        coef = data['coefficients']; order = np.argsort(coef['values'])
        values = np.asarray(coef['values'])[order]
        ax.barh(np.asarray(coef['names'])[order],values,color=[BLUE if v>=0 else ORANGE for v in values],height=0.65,zorder=3)
        ax.axvline(0,color=GRAY,linewidth=0.9)
        ax.set(xlabel='Fitted coefficient on standardized feature scale',title='Logistic Regression Coefficients')
        ax.grid(axis='x'); ax.set_axisbelow(True)
        save(fig,'logistic_coefficients','Blue: positive; orange: negative. Associations with recorded labels; no causal interpretation.')

        from matplotlib.colors import LinearSegmentedColormap
        fig, ax = plt.subplots()
        cm = np.asarray(data['confusion_matrix'])
        cmap = LinearSegmentedColormap.from_list('restrained_blue',['#FFFFFF','#D8E4ED',BLUE])
        ax.imshow(cm,cmap=cmap,vmin=0,vmax=max(1,cm.max()))
        for i in range(2):
            for j in range(2): ax.text(j,i,str(cm[i,j]),ha='center',va='center',fontsize=15,color='white' if cm[i,j]>cm.max()*0.7 else '#34414B')
        labels=['No discount\nrecorded (0)','Discount\nrecorded (1)']
        ax.set(xticks=[0,1],yticks=[0,1],xticklabels=labels,yticklabels=labels,
               xlabel='Predicted operational label',ylabel='Actual operational label',title='Logistic Regression: 2025 Confusion Matrix')
        for spine in ax.spines.values(): spine.set_visible(False)
        save(fig,'logistic_confusion_matrix','Fixed probability threshold: 0.50. Operational zeros do not verify absence of discounts.')

        fig, ax = plt.subplots()
        for name,color,label in [('bernoulli_baseline',ORANGE,'Bernoulli'),('logistic_regression',BLUE,'Logistic regression')]:
            c = data['curves'][name]
            ax.plot(c['fpr'],c['tpr'],color=color,label=f"{label} (AUC = {c['auc']:.3f})")
        ax.plot([0,1],[0,1],color=GRAY,linestyle='--',linewidth=0.9,label='Chance reference')
        ax.set(xlim=(0,1),ylim=(0,1.03),xlabel='False positive rate',ylabel='True positive rate',title='2025 Recorded Discounts: ROC Curves')
        ax.legend(loc='lower right'); ax.grid(); ax.set_axisbelow(True)
        save(fig,'baseline_roc_curves')

        fig, ax = plt.subplots()
        for name,color,label in [('bernoulli_baseline',ORANGE,'Bernoulli'),('logistic_regression',BLUE,'Logistic regression')]:
            c=data['curves'][name]
            ax.step(c['recall'],c['precision'],where='post',color=color,label=f"{label} (AP = {c['ap']:.3f})")
        ax.axhline(data['validation_prevalence'],color=GRAY,linestyle='--',linewidth=0.9,label=f"Validation prevalence = {data['validation_prevalence']:.2f}")
        ax.set(xlim=(0,1),ylim=(0,1.03),xlabel='Recall',ylabel='Precision',title='2025 Recorded Discounts: Precision–Recall Curves')
        ax.legend(loc='lower left'); ax.grid(); ax.set_axisbelow(True)
        save(fig,'baseline_pr_curves','Validation prevalence is an evaluation reference; Bernoulli probability comes from training.')

        fig, ax = plt.subplots(); h=data['histogram']
        ax.hist(h['negative'],bins=h['bins'],color=ORANGE,alpha=0.55,label='Operational negative',edgecolor='white',linewidth=0.4)
        ax.hist(h['positive'],bins=h['bins'],color=BLUE,alpha=0.55,label='Operational positive',edgecolor='white',linewidth=0.4)
        ax.set(xlim=(0,1),xlabel='Predicted probability of a recorded discount',ylabel='Validation observations',title='Logistic Regression: 2025 Probability Distribution')
        ax.legend(); ax.grid(axis='y'); ax.set_axisbelow(True)
        save(fig,'logistic_probability_distribution','Identical bins for both operational classes; 100 validation observations.')

        fig, ax = plt.subplots(); bins=data['reliability']
        ax.plot([0,1],[0,1],color=GRAY,linestyle='--',linewidth=0.9,label='Perfect calibration reference')
        ax.plot([b['mean_probability'] for b in bins],[b['positive_fraction'] for b in bins],marker='o',markersize=4,color=BLUE,label='Nonempty validation bins')
        for b in bins:
            ax.annotate(f"n={b['count']}",(b['mean_probability'],b['positive_fraction']),xytext=(0,7),textcoords='offset points',ha='center',fontsize=8)
        ax.set(xlim=(0,1),ylim=(-0.03,1.08),xlabel='Mean predicted probability',ylabel='Observed recorded-discount fraction',title='Logistic Regression: 2025 Reliability')
        ax.legend(loc='lower right'); ax.grid(); ax.set_axisbelow(True)
        save(fig,'logistic_reliability','Five fixed uniform bins; empty bins omitted. Only 100 observations: limited calibration evidence.')
    return {n:dict(path=f'reports/figures/{n}.png',status='generated',dpi=300,mode='light',sha256=digest(destination/(n+'.png'))) for n in FIGURES}


def comparison_table(metrics):
    lines=['| Metric | Bernoulli | Logistic regression |','| --- | ---: | ---: |']
    for key,label in [('roc_auc','ROC-AUC'),('average_precision','Average precision'),('brier_score','Brier score'),
                      ('log_loss','Log loss'),('accuracy','Accuracy'),('precision','Precision'),('recall','Recall'),('f1','F1')]:
        values=[metrics['models'][name][key] for name in MODEL_PATHS]
        lines.append('| '+label+' | '+' | '.join('undefined' if v is None else f'{v:.6f}' for v in values)+' |')
    for name in MODEL_PATHS:
        lines.append(f"\n{name} confusion matrix (rows actual 0/1, columns predicted 0/1): `{metrics['models'][name]['confusion_matrix']}`.")
    return '\n'.join(lines)


def evaluation_report(metrics, manifest, receipt):
    p=manifest['fitted_parameters']; checks=receipt['execution_checks']
    return f'''# Phase 7A — Baseline modeling evaluation

## Research objective and operational target

Can historical Steam game metadata and pre-sale pricing behavior predict whether a Steam-store discount will be **recorded** during the official Autumn Sale? {TARGET_DEFINITION}

## Dataset and chronological protocol

The pilot has 100 games and 300 game-year observations (2023–2025), with 175 operational positives and 125 negatives. Train on 2023–2024: 200 observations, 115 positives, 85 negatives. Validate on 2025: 100 observations, 60 positives, 40 negatives. Training prevalence is 0.575; validation prevalence is 0.600, reported only for evaluation. No random split, cross-year shuffling, hyperparameter search, threshold optimization, or validation-driven model changes occur. Configurations were fixed before evaluation; fitting receives training rows only.

The same 100 games recur across years. This measures temporal generalization to a later sale for previously represented games. It does **not** establish generalization to entirely unseen games or the full Steam catalog. Repeated observations are dependent; no independence-based confidence intervals are claimed.

## Feature selection and preprocessing

Only the exact Phase 6 manifest allowlist enters the logistic predictor matrix:

{', '.join('`'+f+'`' for f in manifest['feature_allowlist'])}.

AppID, sale year, cutoff, target, audit flag, evidence and PU fields are excluded. The complete fitted Pipeline contains explicit allowlist selection (all other columns dropped), median imputation, StandardScaler, and LogisticRegression. Numeric types are validated without silently repairing source values. All medians, means and variances come only from training observations. Two existing binary coverage flags are retained and standardized alongside the other predictors. No redundant missingness indicators are added: in the current data, price-derived missingness aligns with no prior price history, and discount-summary missingness aligns with no prior discount observation. Future currency/conflict missingness may differ and requires a new documented review.

Training missing counts: `{receipt['input_inspection']['training_missingness']}`. Training constant columns: `{receipt['input_inspection']['training_constant_features']}`. Entirely missing training columns: `{receipt['input_inspection']['training_all_missing_features']}`. The documented fallback excludes entirely missing columns using training predictors only; no exclusions occur in this experiment. Constant observed columns would be retained and handled by StandardScaler. Imputer/scaler statistics and transformed names are saved in the manifest.

## Baseline definitions and fixed configuration

Bernoulli uses sklearn DummyClassifier(strategy="prior"). Its fitted class prior is `{p['bernoulli_class_prior']}`: P(recorded discount)=0.575 and P(no recorded discount)=0.425. It needs no feature preprocessing; a zero-valued placeholder matrix supplies row count to the sklearn API. Every validation game receives probability 0.575. This is deterministic probability estimation, without random Bernoulli draws. Blank decision_score in the CSV means not applicable for this baseline.

LogisticRegression parameters: `{LOGISTIC_PARAMS}`. These are unoptimized initial defaults. Seed: {SEED}. Iterations used: `{p['logistic_iterations']}`. No class weights. Both models use predicted_class = 1 when probability >= 0.50, otherwise 0. Validation data is consulted only after fitting for prediction and evaluation.

## Metrics and model comparison

Probability metrics are ROC-AUC, average precision (sklearn definition), Brier score and log loss. Fixed-threshold metrics are accuracy, precision, recall and F1. Confusion matrices use rows for actual operational labels and columns for predicted labels, both ordered [0,1]. Undefined metrics are JSON null with a reason, never silently zero-filled; no metric is undefined in this experiment. Lower Brier/log loss is better; larger other reported metrics is better.

{comparison_table(metrics)}

The constant baseline has ROC-AUC 0.5 and AP equal to validation prevalence (0.600); its **prediction** is still the training prior (0.575). Logistic regression has ROC-AUC {metrics['models']['logistic_regression']['roc_auc']:.5f}, AP {metrics['models']['logistic_regression']['average_precision']:.5f} and accuracy {metrics['models']['logistic_regression']['accuracy']:.2f}; it improves all eight reported metrics over the constant baseline on this holdout. The fitted logistic results provide a pilot comparison, not evidence of verified participation, causal behavior, or population-wide performance. Differences on 100 holdout observations should be interpreted conservatively; no significance claim or configuration change follows this evaluation.

## Figures

All eight PNGs use white backgrounds, muted blue/orange/gray, restrained grids, consistent fonts, and 300 DPI. Dimensions are 7.2 × 4.8 inches except the coefficient figure (7.2 × 5.8 inches) to fit all transformed names. `src/plotting_style.py` provides reusable styling. `autumn_sale_baseline_plot_data.json` records every underlying plotted value.

- `bernoulli_distribution.png`: two training-prior probability masses, 0.425 and 0.575.
- `logistic_sigmoid.png`: stable scipy.special.expit curve and the actual 100 validation decision scores/probabilities. Maximum consistency error: {receipt['sigmoid_consistency']['max_absolute_error']:.3g}. The combined multivariable score, not any individual feature, is on the x-axis. Points lie on the sigmoid by construction. This explanatory plot is **not evidence of predictive accuracy**.
- `logistic_coefficients.png`: actual transformed feature names and all fitted coefficients, sorted by value. Positive blue and negative orange bars are conditional associations on the imputed, standardized feature scale, including standardized binary flags. No causal interpretation is justified. Correlated age/release and price-summary predictors can make individual coefficients unstable or hard to interpret.
- `logistic_confusion_matrix.png`: operational label counts at fixed 0.50 threshold, rows actual / columns predicted.
- `baseline_roc_curves.png`: observed threshold points from both models, with AUC and a chance diagonal; no invented performance points.
- `baseline_pr_curves.png`: actual precision/recall threshold points and AP; 2025 prevalence is only an evaluation reference, distinct from the fitted Bernoulli prior.
- `logistic_probability_distribution.png`: identical ten uniform histogram bins for both operational classes.
- `logistic_reliability.png`: five fixed uniform calibration bins, sample counts shown, empty bins omitted. Calibration is measured against recorded-discount labels. With just 100 observations, this gives limited evidence and no strong calibration conclusion.

## Artifacts and verification

Complete preprocessing and classifier are saved in `models/logistic_regression.joblib`; the fitted prior estimator is `models/bernoulli_baseline.joblib`. Format: joblib pickle, for trusted local artifacts only. Versions: Python {manifest['versions']['python']}, sklearn {manifest['versions']['sklearn']}, NumPy {manifest['versions']['numpy']}, pandas {manifest['versions']['pandas']}, SciPy {manifest['versions']['scipy']}, matplotlib {manifest['versions']['matplotlib']}, joblib {manifest['versions']['joblib']}. Loading across package versions is not guaranteed. Saved artifacts are reloaded immediately and predictions compared exactly. Reload results: `{receipt['artifact_reload_checks']}`.

Execution checks: `{checks}`. Protected input SHA-256 inventories match for {len(receipt['protected_before_sha256'])} prior files, including Phase 6 features/labels, prior source/tests/reports and all frozen histories. Socket/DNS access is blocked. No API requests or new data. Structured predictions, metrics, fitted parameters and plot data are compared across complete runs; PNG bytes are compared separately before any claim of identity. Verification is specific to this recorded environment; different math libraries/fonts may yield platform differences.

## Limitations

Operational zeros establish no recorded qualifying observation, not confirmed non-discounting. Sparse and incomplete histories and provider recording coverage can influence features and labels. Retrospective timestamps do not prove point-in-time ITAD availability; backfill and requested-since initialization remain unresolved. Release-date accuracy, early-access/full-release interpretation, same-day release-hour eligibility and pre-release price observations remain unresolved. Counts describe observations, not campaigns or discount durations; last prices are observations, not reconstructed cutoff states. Pilot sampling used undated snapshots, introducing selection bias despite their exclusion from predictors. Linear default models, correlated predictors, repeated games, one validation year and only 100 holdout observations limit interpretation.

## Reproduction

Use an environment with the recorded dependencies in `requirements-baseline.txt` already installed; execution is offline. Original `requirements.txt` is protected and unchanged:

```bash
python3 -B src/08_train_baseline_models.py --verify
python3 -B -m unittest discover -s tests -p 'test_baseline_models.py'
```

`--verify` runs the complete offline suite, then two complete experiments with isolated output directories and read-only source inputs, checks structured equality/model parameters/PNG bytes, and writes the final verified artifacts. A normal run without `--verify` generates artifacts but explicitly records tests/determinism as not run. Earlier pipelines are never rerun against the project inputs.

## Phase 7B handoff — not implemented

Require explicit human approval before Phase 7B. Preserve this frozen baseline, allowlist and operational target semantics. Any future model/configuration selection should use training-only temporal resampling; 2025 has now been inspected and must not become a tuning set. Consider a new untouched holdout for confirmatory evaluation. Review recording coverage and repeated-game dependence, and agree on the permitted Phase 7B scope before selecting additional methods. No Phase 7B, 8 or 9 work, PU learning, rankings, dashboard or 2026 prediction is performed.
'''


def run(root=ROOT, output_root=None, execution_checks=None):
    root = Path(root); output_root = Path(output_root or root)
    with offline_guard() as attempts, threadpool_limits(limits=1):
        before = protected_hashes(root)
        frame, fm, inspection = inspect_inputs(root)
        train, valid = chronological_split(frame)
        # Configurations and feature handling finalized from training before prediction/evaluation.
        models, preprocessing = fit_models(train, fm['baseline_feature_allowlist'])
        predictions = predict(models, valid)
        metrics = evaluate(predictions)
        metrics['training_positive_prevalence'] = float(train[TARGET].mean())
        require(models['bernoulli_baseline'].class_prior_[1] == train[TARGET].mean() == 0.575, 'Training prior mismatch')
        plot_data = build_plot_data(predictions, models, metrics)
        for p in OUTPUTS: (output_root / p).parent.mkdir(parents=True, exist_ok=True)
        predictions.to_csv(output_root / PREDICTIONS, index=False, float_format='%.17g')
        write_json(output_root / METRICS, metrics); write_json(output_root / PLOT_DATA, plot_data)
        reload_checks = {}
        for name, path in MODEL_PATHS.items():
            joblib.dump(models[name], output_root / path)
            # Only reload this run's trusted, locally created artifacts.
            reloaded = joblib.load(output_root / path)
            X = np.zeros((len(valid),1)) if name == 'bernoulli_baseline' else select_predictors(valid)
            same = np.array_equal(models[name].predict_proba(X), reloaded.predict_proba(X))
            score_same = name != 'logistic_regression' or np.array_equal(models[name].decision_function(X),reloaded.decision_function(X))
            require(same and score_same, 'Reload prediction mismatch')
            reload_checks[name] = dict(probabilities_identical=same, decision_scores_identical=score_same)
        figures = generate_figures(output_root, plot_data)
        import matplotlib
        manifest = dict(phase='7A', target_column=TARGET, target_definition=TARGET_DEFINITION,
            feature_allowlist=APPROVED, training_years=TRAIN_YEARS, validation_year=VALIDATION_YEAR,
            protocol='Chronological temporal holdout for previously represented games; no tuning.',
            random_seed=SEED, threshold=THRESHOLD, preprocessing=preprocessing,
            estimator_parameters={'bernoulli_baseline':models['bernoulli_baseline'].get_params(),
                                  'logistic_regression':models['logistic_regression'].named_steps['classifier'].get_params()},
            fitted_parameters=model_parameters(models), artifact_format='joblib pickle; trusted local artifacts only',
            artifacts={n:dict(path=p,sha256=digest(output_root/p)) for n,p in MODEL_PATHS.items()},
            versions=dict(python=platform.python_version(),sklearn=sklearn.__version__,numpy=np.__version__,
                          pandas=pd.__version__,scipy=scipy.__version__,matplotlib=matplotlib.__version__,joblib=joblib.__version__),
            decision_score_convention='Bernoulli: blank CSV / not applicable; logistic: decision_function log-odds.',
            source_sha256=source_hashes(root))
        write_json(output_root / MANIFEST, manifest)
        checks = execution_checks or dict(full_offline_test_suite='NOT RUN: use --verify',determinism='NOT RUN: use --verify')
        logistic = predictions[predictions.model_name.eq('logistic_regression')]
        receipt = dict(phase='7A',status='PASS',input_inspection=inspection,feature_allowlist=APPROVED,
            missingness_handling=preprocessing,model_parameters=manifest['estimator_parameters'],
            fitted_parameters=manifest['fitted_parameters'],training_positive_prevalence=float(train[TARGET].mean()),
            validation_positive_prevalence=float(valid[TARGET].mean()),evaluation_metrics=metrics,
            prediction_checks=dict(rows=len(predictions),rows_per_model=predictions.groupby('model_name').size().to_dict(),
                unique_game_year_model_rows=True,finite_probabilities=True,probabilities_in_unit_interval=True,
                fixed_threshold=THRESHOLD,bernoulli_constant_probability=float(models['bernoulli_baseline'].class_prior_[1])),
            sigmoid_consistency=dict(passed=True,rtol=1e-12,atol=1e-14,
                max_absolute_error=float(np.max(np.abs(expit(logistic.decision_score)-logistic.predicted_probability)))),
            artifact_reload_checks=reload_checks,figure_generation=figures,execution_checks=checks,
            protected_before_sha256=before,protected_after_sha256=protected_hashes(root),
            protected_integrity_passed=before==protected_hashes(root),source_sha256=source_hashes(root),
            network_attempts=len(attempts),api_requests=0,scope='Phase 7A only; stop before Phase 7B.')
        write_json(output_root / VALIDATION, receipt)
        (output_root / EVALUATION).write_text(evaluation_report(metrics,manifest,receipt),encoding='utf-8')
        require(before == protected_hashes(root), 'Protected inputs changed during Phase 7A')
    return predictions, metrics, manifest, receipt


def verify_execution(root=ROOT):
    before = protected_hashes(root)
    with offline_guard():
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream).run(unittest.defaultTestLoader.discover(str(root / 'tests')))
        print(stream.getvalue(),end='')
        require(result.wasSuccessful(), 'Offline tests failed')
        checks = dict(full_offline_test_suite='PASS',tests_run=result.testsRun,failures=len(result.failures),
                      errors=len(result.errors),skipped=len(result.skipped))
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            first = run(root,Path(a),checks); second = run(root,Path(b),checks)
            pd.testing.assert_frame_equal(first[0],second[0],check_exact=True)
            require(first[1] == second[1], 'Non-deterministic metrics')
            require(first[2] == second[2], 'Non-deterministic model manifest/parameters')
            require(first[3] == second[3], 'Non-deterministic validation receipt')
            structured = [PREDICTIONS,METRICS,MANIFEST,PLOT_DATA,EVALUATION,VALIDATION]
            require(all(digest(Path(a)/p)==digest(Path(b)/p) for p in structured), 'Non-deterministic structured outputs')
            png_equal = all(digest(Path(a)/f'reports/figures/{n}.png')==digest(Path(b)/f'reports/figures/{n}.png') for n in FIGURES)
            model_equal = all(digest(Path(a)/p)==digest(Path(b)/p) for p in MODEL_PATHS.values())
            checks.update(determinism='PASS: two complete isolated experiments',predictions_identical=True,
                metrics_identical=True,fitted_parameters_identical=True,plotted_data_identical=True,
                structured_outputs_byte_identical=True,png_bytes_identical=png_equal,joblib_bytes_identical=model_equal,
                png_determinism_note='PNG bytes compared in this environment; no cross-platform byte identity guarantee.')
        final = run(root,execution_checks=checks)
        require(before == protected_hashes(root), 'Tests/reruns changed protected inputs')
    print(f'Phase 7A PASS: {result.testsRun} tests; 200 training / 100 validation; STOP before Phase 7B.')
    return final


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify',action='store_true',help='Run full offline suite and compare two complete experiments')
    args = parser.parse_args()
    verify_execution() if args.verify else run()
