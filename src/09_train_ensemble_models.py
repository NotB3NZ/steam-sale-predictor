"""Phase 7B: predefined nonlinear comparisons and exploratory diagnostics, offline.

python3 -B src/09_train_ensemble_models.py --verify
Never regenerate Phase 7A artifacts; stop before Phase 8.
"""
import argparse
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import platform
import sys
import tempfile
import unittest

# Reuse the frozen baseline's input, split, threshold and metric utilities.
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('phase7a_baselines', ROOT / 'src/08_train_baseline_models.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_recall_curve, roc_curve
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits
from plotting_style import BLUE, ORANGE, GRAY, light_style, save_figure, plt

try:
    import xgboost
    from xgboost import XGBClassifier
    XGBOOST_VERSION = xgboost.__version__
    XGBOOST_UNAVAILABLE = None
except Exception as error:  # Optional import/runtime availability failures are reported, never substituted.
    XGBClassifier = None
    XGBOOST_VERSION = None
    XGBOOST_UNAVAILABLE = f'{type(error).__name__}: {error}. No network installation attempted.'

# Fixed before prediction/evaluation; neither diagnostic changes primary settings.
RF_PARAMS = dict(n_estimators=200, max_depth=4, min_samples_leaf=5,
                 max_features='sqrt', random_state=42, n_jobs=1)
XGB_PARAMS = dict(n_estimators=100, max_depth=3, learning_rate=0.05, subsample=0.8,
                  colsample_bytree=0.8, objective='binary:logistic', eval_metric='logloss',
                  random_state=42, n_jobs=1)
COVERAGE_FEATURES = ['prior_price_record_count', 'days_since_last_price_record', 'has_prior_price_history']
PERMUTATION_REPEATS = 20
PERMUTATION_SCORING = 'roc_auc'
ORDER = ['bernoulli_baseline', 'logistic_regression', 'random_forest', 'xgboost']
LABELS = dict(bernoulli_baseline='Bernoulli', logistic_regression='Logistic regression',
              random_forest='Random Forest', xgboost='XGBoost', coverage_only_logistic='Coverage-only logistic')
COLORS = dict(bernoulli_baseline=GRAY, logistic_regression=BLUE, random_forest=ORANGE, xgboost='#779584')
METRIC_LABELS = dict(roc_auc='ROC-AUC', average_precision='Average precision', brier_score='Brier score', log_loss='Log loss', accuracy='Accuracy', precision='Precision', recall='Recall', f1='F1')
METRIC_DIRECTIONS = {k:('lower' if k in ('brier_score','log_loss') else 'higher') for k in
                      ['roc_auc','average_precision','brier_score','log_loss','accuracy','precision','recall','f1']}
PREDICTIONS = 'data/processed/autumn_sale_2025_ensemble_predictions.csv'
COMBINED = 'data/processed/autumn_sale_2025_model_comparison_predictions.csv'
METRICS = 'reports/autumn_sale_model_comparison_metrics.json'
REPORT = 'reports/autumn_sale_model_comparison.md'
TEMPORAL = 'reports/autumn_sale_temporal_robustness.json'
COVERAGE = 'reports/autumn_sale_coverage_sensitivity_modeling.json'
IMPORTANCE = 'reports/autumn_sale_ensemble_feature_importance.json'
MANIFEST = 'reports/autumn_sale_ensemble_model_manifest.json'
VALIDATION = 'reports/autumn_sale_ensemble_validation.json'
PLOT_DATA = 'reports/autumn_sale_ensemble_plot_data.json'
INTEGRITY = 'reports/autumn_sale_phase7a_integrity.json'
MODEL_PATHS = dict(random_forest='models/random_forest.joblib', xgboost='models/xgboost_model.joblib')
FIGURES = ['model_roc_auc_comparison','model_average_precision_comparison','model_brier_comparison',
           'model_roc_curves','model_pr_curves','model_confusion_matrices','random_forest_feature_importance',
           'xgboost_feature_importance','model_probability_distributions','model_temporal_robustness',
           'coverage_sensitivity_comparison']
STRUCTURED = [PREDICTIONS,COMBINED,METRICS,REPORT,TEMPORAL,COVERAGE,IMPORTANCE,MANIFEST,VALIDATION,PLOT_DATA,INTEGRITY]
require = b.require


def clean(value):
    if isinstance(value, dict): return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value, (list,tuple)): return [clean(v) for v in value]
    if isinstance(value, np.ndarray): return clean(value.tolist())
    if isinstance(value, np.generic): return clean(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return "NaN" if np.isnan(value) else ("Infinity" if value > 0 else "-Infinity")
    return value


def hash_structured(value):
    return hashlib.sha256(json.dumps(clean(value),sort_keys=True,allow_nan=False,separators=(',',':')).encode()).hexdigest()


def write_json(path,value):
    b.write_json(path,clean(value))


def unavailable_models():
    return {'xgboost':XGBOOST_UNAVAILABLE} if XGBOOST_UNAVAILABLE else {}


def protected_hashes(root=ROOT):
    """Chain Phase 7A's historical hashes, then freeze every baseline output/source."""
    root=Path(root)
    r=json.loads((root/b.VALIDATION).read_text())
    baseline_expected={**r['protected_after_sha256'],**r['source_sha256']}
    baseline_expected.update({v['path']:v['sha256'] for v in r['figure_generation'].values()})
    manifest=json.loads((root/b.MANIFEST).read_text())
    baseline_expected.update({v['path']:v['sha256'] for v in manifest['artifacts'].values()})
    for p,h in baseline_expected.items():
        require((root/p).is_file() and b.digest(root/p)==h,f'Protected Phase 7A/earlier input changed: {p}')
    # Inputs without hashes in the Phase 7A receipt are also frozen for this phase.
    current={p:b.digest(root/p) for p in sorted(set(baseline_expected)|set(b.OUTPUTS))}
    snapshot=root/INTEGRITY
    if snapshot.exists():
        saved=json.loads(snapshot.read_text())['protected_sha256']
        require(saved==current,'Phase 7B protected-input snapshot disagrees; do not repair/retrain baselines')
    return current


def source_hashes(root):
    return {p:b.digest(root/p) for p in ['src/09_train_ensemble_models.py','tests/test_ensemble_models.py','requirements-ensemble.txt']}


def numeric_predictors(frame, features=b.APPROVED, diagnostic=False):
    allowed=COVERAGE_FEATURES if diagnostic else b.APPROVED
    require(list(features)==allowed,'Unapproved feature set')
    # Explicit selection/conversion in the baseline utility, never numeric auto-selection.
    X=b.select_predictors(frame)
    return X.loc[:,features]


def split_protocol(frame,training_years,evaluation_year):
    require((list(training_years),evaluation_year) in [(b.TRAIN_YEARS,2025),([2023],2024)],'Unsupported temporal protocol')
    require(not frame.duplicated(b.KEYS).any(),'Duplicate game-year observations')
    train=frame[frame.sale_year.isin(training_years)].sort_values(['sale_year','appid']).reset_index(drop=True)
    valid=frame[frame.sale_year.eq(evaluation_year)].sort_values(b.KEYS).reset_index(drop=True)
    require(len(train)==100*len(training_years) and len(valid)==100,'Temporal row count mismatch')
    require(set(train.appid)==set(valid.appid) and valid.appid.nunique()==100,'Temporal identity mismatch')
    require(train.sale_year.max()<valid.sale_year.min(),'Chronology violated')
    return train,valid


def validate_predictions(predictions,valid,names):
    required=b.KEYS+['model_name','actual_label','predicted_probability','predicted_class','decision_score']
    require(list(predictions.columns)==required,'Prediction schema mismatch')
    require(len(predictions)==len(valid)*len(names) and set(predictions.model_name)==set(names),'Prediction model/row count mismatch')
    require(not predictions.duplicated(b.KEYS+['model_name']).any(),'Duplicate prediction identity')
    require(predictions[b.KEYS+['model_name','actual_label','predicted_probability','predicted_class']].notna().all().all(),'Missing prediction fields')
    for f in b.KEYS+['actual_label','predicted_class']:
        values=pd.to_numeric(predictions[f],errors='raise')
        require(np.isfinite(values).all() and (values==np.floor(values)).all(),f'Invalid integer prediction field: {f}')
    p=predictions.predicted_probability.to_numpy()
    require(np.isfinite(p).all() and ((p>=0)&(p<=1)).all(),'Invalid predicted probabilities')
    require(np.array_equal(predictions.predicted_class,b.classes(p)),'Fixed 0.50 threshold disagreement')
    expected=valid[b.KEYS+[b.TARGET]].sort_values(b.KEYS).reset_index(drop=True)
    for name in names:
        rows=predictions[predictions.model_name.eq(name)].sort_values(b.KEYS).reset_index(drop=True)
        actual=rows[b.KEYS+['actual_label']].rename(columns={'actual_label':b.TARGET})
        require(actual.equals(expected),'Prediction identities/labels disagree with evaluation rows')
    return True


def load_baselines(root,valid):
    """Validate saved predictions/metrics and trusted artifacts; never fit primary baselines."""
    predictions=pd.read_csv(root/b.PREDICTIONS,float_precision='round_trip')
    b.read_csv(root/b.PREDICTIONS)  # Also reject malformed/duplicate CSV headers.
    validate_predictions(predictions,valid,ORDER[:2])
    saved=json.loads((root/b.METRICS).read_text())
    calculated=b.evaluate(predictions)
    require(calculated['models']==saved['models'],'Saved Phase 7A metrics disagree with predictions')
    require(saved['target_definition']==b.TARGET_DEFINITION and saved['training_positive_prevalence']==0.575 and
            saved['validation_positive_prevalence']==float(valid[b.TARGET].mean()),'Baseline target/prevalence disagreement')
    manifest=json.loads((root/b.MANIFEST).read_text())
    receipt=json.loads((root/b.VALIDATION).read_text())
    require(manifest['feature_allowlist']==b.APPROVED and manifest['training_years']==b.TRAIN_YEARS and
            manifest['validation_year']==2025 and manifest['threshold']==b.THRESHOLD,'Baseline manifest protocol mismatch')
    require(receipt['evaluation_metrics']==saved,'Baseline validation receipt metrics disagree')
    require(manifest['source_sha256']==b.source_hashes(root),'Baseline sources changed')
    for name,path in b.MODEL_PATHS.items():
        require(b.digest(root/path)==manifest['artifacts'][name]['sha256'],'Baseline artifact checksum disagreement')
        # Trusted prior local artifacts, verified against the original manifest before loading.
        model=joblib.load(root/path)
        X=np.zeros((100,1)) if name=='bernoulli_baseline' else b.select_predictors(valid)
        f=predictions[predictions.model_name.eq(name)].sort_values(b.KEYS)
        require(np.array_equal(model.predict_proba(X)[:,1],f.predicted_probability),'Baseline artifact/prediction disagreement')
        if name=='logistic_regression':
            require(np.array_equal(model.decision_function(X),f.decision_score),'Baseline artifact/decision score disagreement')
            require(model[:-1].get_feature_names_out().tolist()==b.APPROVED,'Baseline transformed feature disagreement')
            require(model.named_steps['classifier'].get_params()==manifest['estimator_parameters'][name],'Baseline estimator settings disagreement')
        else:
            require(model.class_prior_[1]==0.575 and f.predicted_probability.nunique()==1,'Bernoulli prior disagreement')
    return predictions,saved


def pipeline(kind,features=b.APPROVED):
    selector=ColumnTransformer([('approved','passthrough',list(features))],remainder='drop',verbose_feature_names_out=False)
    steps=[('select',selector),('impute',SimpleImputer(strategy='median',add_indicator=False,keep_empty_features=True))]
    if kind=='random_forest': estimator=RandomForestClassifier(**RF_PARAMS)
    elif kind=='xgboost':
        require(XGBClassifier is not None,'XGBoost unavailable; never substitute another estimator')
        estimator=XGBClassifier(**XGB_PARAMS)
    elif kind in ('logistic_regression','coverage_only_logistic'):
        steps.append(('scale',StandardScaler()))
        estimator=LogisticRegression(**b.LOGISTIC_PARAMS)
    else: raise ValueError('Unsupported model kind')
    return Pipeline(steps+[('classifier',estimator)])


def preprocessing_profile(model,train,features):
    profile=dict(features=list(features),transformed_features=model[:-1].get_feature_names_out().tolist(),
        imputation_statistics=model.named_steps['impute'].statistics_.tolist(),training_rows=len(train),
        training_years=sorted(int(y) for y in train.sale_year.unique()),
        training_missingness={f:int(train[f].isna().sum()) for f in features},
        all_missing_training_features=[f for f in features if train[f].isna().all()],
        all_missing_rule='Preserve schema; SimpleImputer keep_empty_features=True uses structural zero for an entirely missing training column.',
        added_missingness_indicators=[],scaling='StandardScaler' if 'scale' in model.named_steps else 'none')
    if 'scale' in model.named_steps:
        scaler=model.named_steps['scale']
        profile.update(scaler_mean=scaler.mean_.tolist(),scaler_variance=scaler.var_.tolist(),scaler_scale=scaler.scale_.tolist(),
                       scaler_samples=int(scaler.n_samples_seen_))
    require(profile['transformed_features']==list(features),'Preprocessing changed predictor schema')
    return profile


def fit_models(train,training_years=b.TRAIN_YEARS,include_baselines=False,cohort_mode=False):
    require(list(training_years) in [b.TRAIN_YEARS,[2023]],'Unsupported fitting years')
    require(set(train.sale_year.unique())==set(training_years) and (cohort_mode or len(train)==100*len(training_years)),'Fitting received nontraining rows')
    train=train.sort_values(['sale_year','appid']).reset_index(drop=True)
    X,y=numeric_predictors(train),train[b.TARGET].to_numpy()
    models={}; profiles={}
    kinds=(['logistic_regression'] if include_baselines else [])+['random_forest']+(['xgboost'] if XGBClassifier is not None else [])
    if include_baselines:
        require(training_years==[2023],'Baseline refitting permitted only for the secondary 2023 experiment')
        models['bernoulli_baseline']=DummyClassifier(strategy='prior',random_state=42).fit(np.zeros((len(train),1)),y)
    with threadpool_limits(limits=1):
        for name in kinds:
            model=pipeline(name)
            model.fit(X,y)  # No eval_set, early stopping, calibration fitting, or validation arguments.
            models[name]=model; profiles[name]=preprocessing_profile(model,train,b.APPROVED)
            if name=='logistic_regression':
                require(model.named_steps['classifier'].n_iter_[0]<b.LOGISTIC_PARAMS['max_iter'],'Secondary logistic convergence failed')
    return models,profiles


def predict(models,valid):
    valid=valid.sort_values(b.KEYS).reset_index(drop=True)
    frames=[]
    for name,model in models.items():
        X=np.zeros((len(valid),1)) if name=='bernoulli_baseline' else numeric_predictors(valid,diagnostic=name=='coverage_only_logistic',features=COVERAGE_FEATURES if name=='coverage_only_logistic' else b.APPROVED)
        p=np.asarray(model.predict_proba(X)[:,list(model.classes_).index(1)],dtype=float)
        f=valid[b.KEYS].copy(); f['model_name']=name;f['actual_label']=valid[b.TARGET].to_numpy()
        f['predicted_probability']=p;f['predicted_class']=b.classes(p)
        f['decision_score']=model.decision_function(X) if name in ('logistic_regression','coverage_only_logistic') else np.nan
        frames.append(f)
    predictions=pd.concat(frames,ignore_index=True)
    validate_predictions(predictions,valid,list(models))
    return predictions


def fitted_parameters(models):
    result={}
    for name,model in models.items():
        if name=='bernoulli_baseline':
            result[name]=dict(class_prior=model.class_prior_.tolist());continue
        estimator=model.named_steps['classifier']
        value=dict(imputation_statistics=model.named_steps['impute'].statistics_.tolist())
        if name=='random_forest':
            trees=[]
            for tree in estimator.estimators_:
                t=tree.tree_
                trees.append(dict(children_left=t.children_left,children_right=t.children_right,feature=t.feature,
                                  threshold=t.threshold,value=t.value,impurity=t.impurity,n_node_samples=t.n_node_samples))
            value.update(tree_state_sha256=hash_structured(trees),feature_importances=estimator.feature_importances_.tolist(),trees=len(trees))
        elif name=='xgboost':
            value.update(booster_json_sha256=hashlib.sha256(estimator.get_booster().save_raw(raw_format='json')).hexdigest(),
                         feature_importances=estimator.feature_importances_.tolist())
        else:
            value.update(coefficients=estimator.coef_.tolist(),intercept=estimator.intercept_.tolist(),iterations=estimator.n_iter_.tolist(),
                         scaler_mean=model.named_steps['scale'].mean_.tolist(),scaler_variance=model.named_steps['scale'].var_.tolist())
        result[name]=value
    return result


def coverage_diagnostic(train,valid,baseline_predictions):
    require(set(train.sale_year.unique())==set(b.TRAIN_YEARS) and len(train)==200,'Coverage diagnostic requires primary training only')
    train=train.sort_values(['sale_year','appid']).reset_index(drop=True)
    model=pipeline('coverage_only_logistic',COVERAGE_FEATURES)
    model.fit(numeric_predictors(train,COVERAGE_FEATURES,diagnostic=True),train[b.TARGET])
    predictions=predict({'coverage_only_logistic':model},valid)
    require(model.named_steps['classifier'].n_iter_[0]<b.LOGISTIC_PARAMS['max_iter'],'Coverage logistic did not converge')
    full=baseline_predictions[baseline_predictions.model_name.eq('logistic_regression')]
    metrics=b.evaluate(pd.concat([full,predictions],ignore_index=True))
    return dict(analysis='Post-hoc exploratory coverage sensitivity motivated by Phase 7A; not a primary/production model.',
        feature_subset=COVERAGE_FEATURES,
        feature_classification={f:'historical price-observation availability' for f in COVERAGE_FEATURES},
        excluded_discount_behavior_features=['prior_discount_count','days_since_last_discount','has_prior_discount_observation'],
        distinction='No discount-specific counts, recencies or indicators enter this diagnostic; they mix discount behavior and observation availability.',
        interpretation='Strong coverage-only results would suggest the operational target partly reflects provider observation patterns; they cannot establish the precise source of the signal.',
        training_years=b.TRAIN_YEARS,validation_year=2025,training_rows=200,validation_rows=100,
        estimator_parameters=model.named_steps['classifier'].get_params(),preprocessing=preprocessing_profile(model,train,COVERAGE_FEATURES),
        fitted_parameters=fitted_parameters({'coverage_only_logistic':model}),metrics=metrics,
        predictions=predictions.replace({np.nan:None}).to_dict('records'),
        diagnostic_isolated_from_primary=True,threshold=b.THRESHOLD)


def feature_importances(models,valid):
    result={}
    X=numeric_predictors(valid);y=valid[b.TARGET].to_numpy()
    for name,model in models.items():
        names=model[:-1].get_feature_names_out().tolist()
        estimator=model.named_steps['classifier']
        perm=permutation_importance(model,X,y,scoring=PERMUTATION_SCORING,n_repeats=PERMUTATION_REPEATS,random_state=42,n_jobs=1)
        result[name]=dict(features=names,native_importance=estimator.feature_importances_.tolist(),
            native_definition='Normalized mean decrease in impurity (MDI)' if name=='random_forest' else 'Normalized average split gain (XGBClassifier default gain importance)',
            native_dataset='2023–2024 training fit',permutation_mean=perm.importances_mean.tolist(),
            permutation_std=perm.importances_std.tolist(),permutation_repeats=perm.importances.tolist(),
            scoring=PERMUTATION_SCORING,n_repeats=PERMUTATION_REPEATS,random_seed=42,
            permutation_dataset='2025 previously examined validation holdout',
            limitations='Exploratory diagnostic only; correlated features can share/mask importance, small holdout and random permutations add variability; negative drops are possible. Not causal; no feature selection or retuning.')
    return dict(models=result,unavailable_models=unavailable_models())


def secondary_experiment(frame,primary_metrics):
    train,valid=split_protocol(frame,[2023],2024)
    require(train[b.TARGET].value_counts().to_dict()=={1:55,0:45},'Secondary training counts mismatch')
    require(valid[b.TARGET].value_counts().to_dict()=={1:60,0:40},'Secondary evaluation counts mismatch')
    models,profiles=fit_models(train,[2023],include_baselines=True)
    predictions=predict(models,valid)
    metrics=b.evaluate(predictions)
    require(models['bernoulli_baseline'].class_prior_[1]==float(train[b.TARGET].mean())==0.55,'Secondary Bernoulli prior incorrect')
    return dict(protocol='2023 -> 2024',training_years=[2023],evaluation_year=2024,training_rows=100,evaluation_rows=100,
        training_target_counts={'0':45,'1':55},evaluation_target_counts={'0':40,'1':60},
        bernoulli_training_prior=float(train[b.TARGET].mean()),metrics=metrics,
        primary_protocol='2023–2024 -> 2025',primary_metrics=primary_metrics,preprocessing=profiles,
        fitted_parameters=fitted_parameters(models),unavailable_models=unavailable_models(),
        predictions=predictions.replace({np.nan:None}).to_dict('records'),
        limitations='Different training sizes and evaluation years; not a controlled temporal-drift estimate. Games recur in training. 2024 outcomes contribute to primary training, so this check is not an independent confirmatory test.')


def plot_data(combined,metrics,temporal,coverage,importance):
    require(b.evaluate(combined)['models']==metrics['models'],'Plot metrics disagree with saved predictions')
    curves={};histograms={};matrices={}
    for name,f in combined.groupby('model_name'):
        fpr,tpr,_=roc_curve(f.actual_label,f.predicted_probability,drop_intermediate=False)
        precision,recall,_=precision_recall_curve(f.actual_label,f.predicted_probability)
        curves[name]=dict(fpr=fpr.tolist(),tpr=tpr.tolist(),precision=precision.tolist(),recall=recall.tolist())
        histograms[name]=dict(positive=f.loc[f.actual_label.eq(1),'predicted_probability'].tolist(),negative=f.loc[f.actual_label.eq(0),'predicted_probability'].tolist())
        matrices[name]=metrics['models'][name]['confusion_matrix']
    return dict(model_order=[n for n in ORDER if n in metrics['models']],labels=LABELS,colors=COLORS,
        metric_values={name:{key:value for key,value in values.items() if key in METRIC_DIRECTIONS} for name,values in metrics['models'].items()},
        directions=METRIC_DIRECTIONS,curves=curves,confusion_matrices=matrices,histograms=histograms,
        histogram_bins=np.linspace(0,1,11).tolist(),validation_prevalence=float(combined.drop_duplicates(b.KEYS).actual_label.mean()),
        temporal_protocols=['2023 -> 2024','2023–2024 -> 2025'],
        temporal_values={name:[temporal['metrics']['models'][name]['roc_auc'],metrics['models'][name]['roc_auc']] for name in metrics['models']},
        coverage_metrics=coverage['metrics']['models'],importance=importance['models'],unavailable_models=unavailable_models())


def generate_figures(output_root,data):
    destination=output_root/'reports/figures';destination.mkdir(parents=True,exist_ok=True)
    status={}
    names=data['model_order']
    def save(fig,name,caption=None):
        save_figure(fig,destination/(name+'.png'),caption)
        status[name]=dict(status='generated',path=f'reports/figures/{name}.png',dpi=300,mode='light',sha256=b.digest(destination/(name+'.png')))
    def grid(ax,axis='x'):
        ax.grid(axis=axis);ax.set_axisbelow(True)
    with light_style():
        for metric,name,title in [('roc_auc','model_roc_auc_comparison','Recorded Discounts: ROC-AUC'),
                ('average_precision','model_average_precision_comparison','Recorded Discounts: Average Precision'),
                ('brier_score','model_brier_comparison','Recorded Discounts: Brier Score')]:
            fig,ax=plt.subplots();values=[data['metric_values'][n][metric] for n in names]
            ax.barh([LABELS[n] for n in names],values,color=[COLORS[n] for n in names],height=0.6,zorder=3)
            ax.invert_yaxis();ax.set(xlim=(0,1),xlabel=f"{METRIC_LABELS[metric]} ({data['directions'][metric]} is better)",title=title)
            for i,v in enumerate(values):ax.text(min(v+0.015,0.98),i,f'{v:.3f}',va='center',ha='left' if v<0.95 else 'right',fontsize=9)
            grid(ax)
            caption='2025 previously examined holdout; fixed configurations.'
            if data['unavailable_models']:caption+=' XGBoost unavailable; omitted.'
            save(fig,name,caption)

        fig,ax=plt.subplots()
        for name in names:
            c=data['curves'][name];auc=data['metric_values'][name]['roc_auc']
            ax.plot(c['fpr'],c['tpr'],color=COLORS[name],label=f'{LABELS[name]} (AUC {auc:.3f})')
        ax.plot([0,1],[0,1],color=GRAY,linestyle='--',linewidth=0.8,label='Chance reference')
        ax.set(xlim=(0,1),ylim=(0,1.03),xlabel='False positive rate',ylabel='True positive rate',title='Recorded Discounts: 2025 ROC Curves')
        ax.legend(loc='lower right');grid(ax,'both');save(fig,'model_roc_curves')

        fig,ax=plt.subplots()
        for name in names:
            c=data['curves'][name];ap=data['metric_values'][name]['average_precision']
            ax.step(c['recall'],c['precision'],where='post',color=COLORS[name],label=f'{LABELS[name]} (AP {ap:.3f})')
        ax.axhline(data['validation_prevalence'],color=GRAY,linestyle='--',linewidth=0.8,label='Validation prevalence')
        ax.set(xlim=(0,1),ylim=(0,1.03),xlabel='Recall',ylabel='Precision',title='Recorded Discounts: 2025 Precision–Recall')
        ax.legend(loc='lower left');grid(ax,'both');save(fig,'model_pr_curves','Prevalence is an evaluation reference, not the fitted Bernoulli probability.')

        from matplotlib.colors import ListedColormap
        cmap=ListedColormap(['#FFFFFF','#E8EEF2','#CAD9E4','#A6BFCE','#7F9FB5',BLUE])
        fig,axes=plt.subplots(1,len(names),figsize=(3.5*len(names),4.0),squeeze=False)
        vmax=max(np.asarray(data['confusion_matrices'][n]).max() for n in names)
        for ax,name in zip(axes[0],names):
            cm=np.asarray(data['confusion_matrices'][name]);ax.imshow(cm,cmap=cmap,vmin=0,vmax=vmax)
            for i in [0,1]:
                for j in [0,1]:ax.text(j,i,str(cm[i,j]),ha='center',va='center',fontsize=12,color='white' if cm[i,j]>vmax*0.75 else '#34414B')
            ax.set(xticks=[0,1],yticks=[0,1],xticklabels=['0: No discount\nrecorded','1: Discount\nrecorded'],yticklabels=['0: No discount\nrecorded','1: Discount\nrecorded'],
                   xlabel='Predicted operational label',ylabel='Actual operational label',title=LABELS[name])
            for spine in ax.spines.values():spine.set_visible(False)
        save(fig,'model_confusion_matrices','2025 recorded-discount labels; rows actual, columns predicted; threshold 0.50; shared color scale.')

        for name in ['random_forest','xgboost']:
            filename=name+'_feature_importance'
            if name not in data['importance']:
                status[filename]=dict(status='unavailable',reason=data['unavailable_models'].get(name,'model unavailable'));continue
            info=data['importance'][name]
            fig,axes=plt.subplots(1,2,figsize=(11.4,6.4))
            order=np.argsort(info['native_importance'])
            axes[0].barh(np.asarray(info['features'])[order],np.asarray(info['native_importance'])[order],height=0.65,color=COLORS[name],zorder=3)
            axes[0].set(xlabel='Normalized importance',xlim=(0,1),title='Training impurity importance' if name=='random_forest' else 'Training split-gain importance')
            order=np.argsort(info['permutation_mean'])
            axes[1].barh(np.asarray(info['features'])[order],np.asarray(info['permutation_mean'])[order],xerr=np.asarray(info['permutation_std'])[order],
                         color=COLORS[name],height=0.65,error_kw={'elinewidth':0.7,'ecolor':GRAY},zorder=3)
            axes[1].axvline(0,color=GRAY,linewidth=0.8)
            axes[1].set(xlabel='Decrease in validation ROC-AUC',title='Exploratory 2025 permutation importance')
            for ax in axes:grid(ax)
            fig.suptitle(LABELS[name]+': Feature Importance',fontsize=12)
            save(fig,filename,'20 permutations per feature; seed 42; error bars: repeat SD. Correlated predictors; no causal interpretation.')

        fig,axes=plt.subplots(2,2,figsize=(9.2,7.2));bins=data['histogram_bins']
        for ax,name in zip(axes.flat,names):
            h=data['histograms'][name]
            ax.hist(h['negative'],bins=bins,color='#B5BDC4',alpha=0.5,label='Operational negative',edgecolor='white',linewidth=0.4)
            ax.hist(h['positive'],bins=bins,color=COLORS[name],alpha=0.6,label='Operational positive',edgecolor='white',linewidth=0.4)
            ax.set(xlim=(0,1),ylim=(0,65),title=LABELS[name],xlabel='Recorded-discount probability',ylabel='Validation observations');grid(ax,'y')
            ax.legend(fontsize=7,loc='upper right')
        if len(names)<4:
            ax=axes.flat[-1];ax.axis('off');ax.text(0.5,0.5,'XGBoost unavailable\nNo predictions generated',ha='center',va='center',color=GRAY,transform=ax.transAxes)
        save(fig,'model_probability_distributions','2025 operational classes; common ten bins and count scale across models.')

        fig,ax=plt.subplots();x=np.arange(len(names));width=0.34
        for index,label in enumerate(data['temporal_protocols']):
            ax.bar(x+(index-0.5)*width,[data['temporal_values'][n][index] for n in names],width,
                   color=[COLORS[n] for n in names],alpha=0.45 if index==0 else 1,label=label,zorder=3)
        ax.set(xticks=x,xticklabels=[LABELS[n] for n in names],ylim=(0,1),ylabel='ROC-AUC (higher is better)',title='Temporal Checks: Recorded-Discount Discrimination')
        ax.legend();grid(ax,'y')
        save(fig,'model_temporal_robustness','Different training sizes and evaluation years; not an independent test or controlled drift estimate.')

        fig,axes=plt.subplots(1,3,figsize=(10.8,4.3))
        keys=['roc_auc','average_precision','brier_score'];cov_names=['logistic_regression','coverage_only_logistic']
        for ax,key in zip(axes,keys):
            ax.bar([0,1],[data['coverage_metrics'][n][key] for n in cov_names],color=[BLUE,ORANGE],width=0.6,zorder=3)
            ax.set(xticks=[0,1],xticklabels=['Full-feature\nlogistic','Coverage-only\nlogistic'],ylim=(0,1),
                   title=METRIC_LABELS[key],ylabel=f"{data['directions'][key].title()} is better")
            grid(ax,'y')
        save(fig,'coverage_sensitivity_comparison','Post-hoc exploratory diagnostic; three price-observation coverage features; no primary-model changes.')
    return status


def metric_table(metrics):
    keys=list(METRIC_DIRECTIONS)
    lines=['| Model | ROC-AUC ↑ | AP ↑ | Brier ↓ | Log loss ↓ | Accuracy ↑ | Precision ↑ | Recall ↑ | F1 ↑ |',
           '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for name in ORDER:
        if name not in metrics['models']:
            lines.append('| '+LABELS[name]+' | '+' | '.join(['Unavailable']*len(keys))+' |');continue
        values=metrics['models'][name]
        lines.append('| '+LABELS[name]+' | '+' | '.join('Undefined' if values[k] is None else f'{values[k]:.6f}' for k in keys)+' |')
    return '\n'.join(lines)


def comparison_report(metrics,temporal,coverage,importance,manifest,receipt):
    full=metrics['models']['logistic_regression'];rf=metrics['models']['random_forest'];cov=coverage['metrics']['models']['coverage_only_logistic']
    delta={k:rf[k]-full[k] for k in METRIC_DIRECTIONS}
    figures='\n'.join(f"- `{name}.png`: {info['status']}" for name,info in receipt['figures'].items())
    return f'''# Nonlinear comparisons for recorded Autumn Sale discounts

## Objective and evidence

Do predefined nonlinear ensembles improve prediction of recorded Steam Autumn Sale discount occurrence relative to logistic regression and a constant-probability prior? {b.TARGET_DEFINITION}

The existing 100-game pilot provides 300 game-year rows. Training: 2023–2024, 200 rows (115 positive / 85 negative); evaluation: 2025, 100 rows (60 positive / 40 negative). All primary models use exactly the same game-year identities. The same games recur across years: this measures temporal generalization for previously represented games, not unseen-game or full-catalog generalization. The 2025 holdout was already examined in Phase 7A. This comparison is exploratory on a previously examined holdout, **not a fresh confirmatory test**. Configurations were prescribed before this phase's evaluation; no tuning, feature selection, early stopping or calibration fitting uses 2025 labels. Threshold remains 0.50.

## Inputs, features and preprocessing

Approved predictors: {', '.join('`'+f+'`' for f in b.APPROVED)}. Explicit ColumnTransformer selection drops all identifiers, cutoff, targets, categories, PU and audit fields. Input types, exact Phase 6 manifest approval, frozen targets and pre-cutoff provenance are validated using the unchanged baseline utilities. Median imputers fit training predictors only. Existing coverage indicators are retained; no redundant indicators or unnecessary tree scaling are added. The complete saved pipelines include feature selection, imputation and classifiers. Entirely missing training columns would be preserved as structural zeros using keep_empty_features=True; actual primary training has none. Constants would remain in schema. Transformed names and imputer statistics are in the manifest.

Primary Phase 7A predictions and metrics are loaded unchanged, validated against the 2025 identities/labels, recomputed metrics and trusted checksum-verified model artifacts. The primary Bernoulli/logistic models are never retrained. Historical data, labels, feature values, baseline models/reports/predictions and all eight existing figures remain protected. `autumn_sale_phase7a_integrity.json` freezes the protected inventory for future checks.

## Fixed model configurations

Random Forest: `{RF_PARAMS}`. XGBoost: `{XGB_PARAMS}`. No configuration changes are based on observed scores. Native defaults not explicitly overridden are recorded with the resolved estimator parameters in the manifest. Seeds are 42 and estimator jobs are one; numerical math thread pools are also limited to one.

XGBoost availability: `{receipt['unavailable_models'] or 'available'}`. The implemented conditional XGBClassifier path uses the same training-only median pipeline and no eval_set or early stopping. `requirements-ensemble.txt` declares xgboost==2.1.4 without changing the protected baseline dependencies. No network install is attempted. When unavailable, XGBoost has no predictions, trained artifact, importance values or evaluated metrics; its dependent figure is omitted, and comparison tables explicitly mark it unavailable. There is no substitute estimator. The XGBoost training path has not been executed or runtime-validated in this environment when its dependency is unavailable.

## Primary model comparison

{metric_table(metrics)}

↑ Higher is better for ROC-AUC, AP, accuracy, precision, recall and F1. ↓ Lower is better for Brier and log loss. Undefined metrics are null with explicit reasons. Confusion matrices use actual rows and predicted columns in [0,1] order:

{json.dumps({n:v['confusion_matrix'] for n,v in metrics['models'].items()},sort_keys=True)}

Random Forest minus full logistic: ROC-AUC {delta['roc_auc']:+.6f}, AP {delta['average_precision']:+.6f}, Brier {delta['brier_score']:+.6f}, log loss {delta['log_loss']:+.6f}, accuracy {delta['accuracy']:+.6f}. Discrimination and probability error are separate criteria; accuracy at one threshold does not establish a universal best model. Brier/log loss assess probability quality against operational labels and do not alone establish calibration. No significance, population-wide, causal or verified-participation claim follows these point estimates. Additional nonlinear complexity is not assumed beneficial. {'Unavailable XGBoost prevents a complete four-model empirical assessment in this environment.' if XGBOOST_UNAVAILABLE else 'All four predefined model types are evaluated; the inspected-holdout limitation still applies.'}

## Secondary temporal check

Fit all available model types anew on 2023 only (100 rows, 55 positive / 45 negative), then evaluate 2024 (100 rows, 60 positive / 40 negative). The Bernoulli prior is **0.55**, estimated solely from 2023 labels. Logistic uses the Phase 7A configuration with a separate training-only imputer/scaler; ensembles retain the predefined configurations. These temporary fits never overwrite primary artifacts.

{metric_table(temporal['metrics'])}

This check and the primary experiment use different training sizes and evaluation years; differences are not clean estimates of temporal drift. Games have already appeared in training. Since 2024 outcomes contribute to primary training, the secondary analysis is not an independent confirmatory test. `autumn_sale_temporal_robustness.json` includes all metrics, preprocessing, fitted fingerprints and actual secondary predictions.

## Coverage sensitivity: post-hoc exploratory diagnostic

The fixed subset is `{COVERAGE_FEATURES}`: prior price-record count, price-record recency and presence of prior price history. These describe historical price-observation availability, regardless of whether observations show discounts. Discount count, discount recency and prior-discount indicator are deliberately excluded from this narrow diagnostic because they combine historical discount behavior with availability. The subset is declared before diagnostic fitting; it is not selected from its evaluation results.

A separate coverage-only logistic pipeline uses the same logistic configuration, median imputation and StandardScaler, trained only on 2023–2024. At evaluation it has ROC-AUC **{cov['roc_auc']:.6f}**, AP **{cov['average_precision']:.6f}**, Brier **{cov['brier_score']:.6f}** and accuracy **{cov['accuracy']:.6f}**. Full-feature logistic has ROC-AUC **{full['roc_auc']:.6f}**, AP **{full['average_precision']:.6f}**, Brier **{full['brier_score']:.6f}** and accuracy **{full['accuracy']:.6f}**.

Strong performance from coverage features would suggest that the operational target partly reflects data-provider observation patterns; it would not prove the precise source of the predictive signal or isolate coverage from underlying commercial behavior. This diagnostic is post-hoc, motivated by Phase 7A findings on an already examined holdout. It does not replace a primary model or influence any hyperparameter, feature or threshold choice. Complete metrics, diagnostic predictions, preprocessing and coefficients are in `autumn_sale_coverage_sensitivity_modeling.json`.

## Feature importance

Random Forest native importance is normalized mean decrease in impurity across fitted training trees. XGBoost's conditional implementation reports normalized average split gain. Feature names come from the fitted transformed schema. Permutation importance uses the fitted complete pipeline on 2025, scoring ROC-AUC with **20 repeats per feature**, seed **42**, n_jobs=1; it reports mean score decrease, repeat SD and every repeat. This is an exploratory diagnostic on the previously examined holdout, never used to select predictors or retune models. Correlated age/release, count/recency and discount-summary features can share, mask or distort rankings. Native importance can favor variables with more possible splits; negative permutation values are possible. Repeat SD is not a confidence interval. Importance does not establish causality or explain why a publisher discounts a game. Data is saved in `autumn_sale_ensemble_feature_importance.json`.

## Visualizations

All figures reuse the protected `src/plotting_style.py`: white backgrounds, muted consistent model colors, subtle grids, sans-serif text and PNG at 300 DPI. Metric bars start at zero and use [0,1]; confusion matrices share a scale and label operational rows/columns; probability histograms use common bins and small multiples. The ROC/AP/Brier charts separate evaluation dimensions. Temporal and coverage captions explicitly state their limitations. Native and permutation importance are separate panels, with transformed names and no causal claims. No HTML report or dashboard is generated. `autumn_sale_ensemble_plot_data.json` stores the actual underlying values, rebuilt from saved predictions rather than hard-coded results.

{figures}

## Reproduction, artifacts and verification

Use the local dependencies already installed; `requirements-ensemble.txt` declares the optional XGBoost dependency. Phase 7B itself is offline:

```bash
python3 -B src/09_train_ensemble_models.py --verify
python3 -B -m unittest discover -s tests -p 'test_ensemble_models.py'
```

`--verify` runs the full offline suite, compares two complete isolated runs including diagnostics, predicts after reloading this run's trusted local artifacts, checks actual output hashes, then saves verified results. A normal run explicitly records tests and repeated-run verification as not run. Model artifacts are complete joblib pipelines; only trusted local outputs are loaded. Versions: `{manifest['versions']}`. Reproduction across package/platform versions is not guaranteed.

Execution results: `{receipt['execution_checks']}`. Artifact reload checks: `{receipt['artifact_reload']}`. Protected before/after inventories agree for **{len(receipt['protected_before_sha256'])}** earlier files. Zero network/API requests. PNG and model bytes are compared before any identity claim; underlying plotted data is compared separately.

## Methodological assessment and scope

The small, nonrepresentative pilot, repeated-game dependence, one previously inspected primary holdout, incomplete recording coverage, source snapshot selection bias, release-date/eligibility uncertainty and unverified retrospective provider availability limit conclusions. Historical observation counts are not complete campaigns or price-state trajectories. Secondary performance and feature importance remain exploratory. No fresh confirmatory experiment or verified true-negative dataset is established.

This is Phase 7B only. Raw histories, operational labels and Phase 6/7A outputs are unchanged. No new games or data, PU learning, large searches, 2026 predictions, genre analytics, rankings, calibration fitting or dashboard. Stop before Phase 8 and Phase 9. Future work needs explicit approval and a separately designed untouched evaluation set.
'''


def run(root=ROOT,output_root=None,execution_checks=None):
    root=Path(root);out=Path(output_root or root)
    with b.offline_guard() as attempts,threadpool_limits(limits=1):
        before=protected_hashes(root)
        frame,fm,inspection=b.inspect_inputs(root)
        train,valid=split_protocol(frame,b.TRAIN_YEARS,2025)
        baseline_predictions,baseline_metrics=load_baselines(root,valid)  # Gate before any fitting/output writes.
        models,profiles=fit_models(train)
        predictions=predict(models,valid)
        combined=pd.concat([baseline_predictions,predictions],ignore_index=True)
        validate_predictions(combined,valid,ORDER[:2]+list(models))
        for p in STRUCTURED+list(MODEL_PATHS.values()): (out/p).parent.mkdir(parents=True,exist_ok=True)
        predictions.to_csv(out/PREDICTIONS,index=False,float_format='%.17g')
        combined.to_csv(out/COMBINED,index=False,float_format='%.17g')
        # All comparison metrics/figures use exact round-trip saved predictions.
        saved=pd.read_csv(out/COMBINED,float_precision='round_trip')
        pd.testing.assert_frame_equal(saved,combined,check_exact=True)
        metrics=b.evaluate(saved)
        metrics.update(metric_directions=METRIC_DIRECTIONS,protocol='2023–2024 -> 2025; previously examined holdout',
                       training_positive_prevalence=float(train[b.TARGET].mean()),unavailable_models=unavailable_models())
        require(all(metrics['models'][n]==baseline_metrics['models'][n] for n in ORDER[:2]),'Comparison altered baseline metrics')
        temporal=secondary_experiment(frame,metrics)
        coverage=coverage_diagnostic(train,valid,baseline_predictions)
        importance=feature_importances(models,valid)
        reload={}
        for name,model in models.items():
            path=out/MODEL_PATHS[name];joblib.dump(model,path);loaded=joblib.load(path)
            identical=np.array_equal(model.predict_proba(numeric_predictors(valid)),loaded.predict_proba(numeric_predictors(valid)))
            parameter_identical=fitted_parameters({name:model})==fitted_parameters({name:loaded})
            require(identical and parameter_identical,'Ensemble artifact reload mismatch')
            reload[name]=dict(probabilities_identical=identical,fitted_parameters_identical=parameter_identical)
        data=plot_data(saved,metrics,temporal,coverage,importance)
        figures=generate_figures(out,data)
        import matplotlib
        manifest=dict(phase='7B',target_definition=b.TARGET_DEFINITION,target_column=b.TARGET,approved_features=b.APPROVED,
            training_years=b.TRAIN_YEARS,validation_year=2025,random_seed=42,threshold=b.THRESHOLD,
            predefined_parameters=dict(random_forest=RF_PARAMS,xgboost=XGB_PARAMS,logistic_regression=b.LOGISTIC_PARAMS),
            resolved_ensemble_parameters={n:m.named_steps['classifier'].get_params() for n,m in models.items()},
            preprocessing=profiles,fitted_parameters=fitted_parameters(models),unavailable_models=unavailable_models(),
            versions=dict(python=platform.python_version(),sklearn=sklearn.__version__,xgboost=XGBOOST_VERSION,
                          numpy=np.__version__,pandas=pd.__version__,matplotlib=matplotlib.__version__,joblib=joblib.__version__),
            artifact_format='Complete fitted sklearn Pipeline, joblib pickle; trusted local artifacts only.',
            parameter_serialization_note='Nonfinite estimator parameter sentinels (for example XGBoost missing=NaN) are recorded as strings; prediction probabilities must remain finite.',
            artifacts={n:dict(path=MODEL_PATHS[n],sha256=b.digest(out/MODEL_PATHS[n])) for n in models},
            decision_score_convention='Blank for tree models; probabilities and fixed-threshold classes are primary outputs.',
            permutation=dict(scoring=PERMUTATION_SCORING,repeats=PERMUTATION_REPEATS,random_seed=42,dataset='2025 previously examined holdout'),
            coverage_subset=COVERAGE_FEATURES,source_sha256=source_hashes(root))
        checks=execution_checks or dict(full_offline_test_suite='NOT RUN: use --verify',determinism='NOT RUN: use --verify')
        receipt=dict(phase='7B',status='PASS_WITH_XGBOOST_UNAVAILABLE' if XGBOOST_UNAVAILABLE else 'PASS',
            input_inspection=inspection,approved_features=b.APPROVED,baseline_schema_alignment='PASS: saved predictions, targets, metrics and trusted models agree',
            model_configurations=manifest['predefined_parameters'],prediction_checks=dict(ensemble_rows=len(predictions),
                comparison_rows=len(saved),per_model_counts=saved.groupby('model_name').size().to_dict(),unique_rows=True,
                same_100_validation_identities=True,finite_probabilities=True,unit_interval=True,fixed_threshold=0.5),
            comparison_metrics=metrics,secondary_temporal_results=temporal,coverage_diagnostic=coverage,
            feature_importance_status={n:'native and permutation executed' for n in models},figures=figures,artifact_reload=reload,
            execution_checks=checks,unavailable_models=unavailable_models(),
            unresolved_issues=[XGBOOST_UNAVAILABLE] if XGBOOST_UNAVAILABLE else [],
            protected_before_sha256=before,protected_after_sha256=protected_hashes(root),source_sha256=source_hashes(root),
            network_attempts=len(attempts),api_requests=0,scope='Phase 7B only; no Phase 8/9, population expansion or 2026 predictions.')
        for p,v in [(METRICS,metrics),(TEMPORAL,temporal),(COVERAGE,coverage),(IMPORTANCE,importance),
                    (MANIFEST,manifest),(PLOT_DATA,data),(INTEGRITY,dict(phase='7A preserved for 7B',protected_sha256=before))]:write_json(out/p,v)
        (out/REPORT).write_text(comparison_report(metrics,temporal,coverage,importance,manifest,receipt),encoding='utf-8')
        artifacts=STRUCTURED.copy();artifacts.remove(VALIDATION)
        artifacts+=list(manifest['artifacts'][n]['path'] for n in models)
        artifacts+=[v['path'] for v in figures.values() if v['status']=='generated']
        receipt['output_sha256']={p:b.digest(out/p) for p in artifacts}
        write_json(out/VALIDATION,receipt)
        require(before==protected_hashes(root),'Protected earlier artifacts changed')
        return saved,metrics,manifest,receipt


def verify_execution(root=ROOT):
    before=protected_hashes(root)
    with b.offline_guard():
        stream=io.StringIO()
        result=unittest.TextTestRunner(stream=stream).run(unittest.defaultTestLoader.discover(str(root/'tests')))
        print(stream.getvalue(),end='');require(result.wasSuccessful(),'Offline tests failed')
        checks=dict(full_offline_test_suite='PASS',tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),
                    skipped=len(result.skipped),skip_reasons=[reason for _,reason in result.skipped])
        with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as c:
            first=run(root,Path(a),checks);second=run(root,Path(c),checks)
            pd.testing.assert_frame_equal(first[0],second[0],check_exact=True)
            require(first[1]==second[1] and first[2]==second[2],'Repeated metrics/model parameters differ')
            for p in [METRICS,TEMPORAL,COVERAGE,IMPORTANCE,PLOT_DATA,INTEGRITY]:
                require(json.loads((Path(a)/p).read_text())==json.loads((Path(c)/p).read_text()),f'Repeated structured data differ: {p}')
            pngs=[v['path'] for v in first[3]['figures'].values() if v['status']=='generated']
            model_paths=[v['path'] for v in first[2]['artifacts'].values()]
            png_equal=all(b.digest(Path(a)/p)==b.digest(Path(c)/p) for p in pngs)
            model_equal=all(b.digest(Path(a)/p)==b.digest(Path(c)/p) for p in model_paths)
            checks.update(determinism='PASS: two complete isolated Phase 7B runs',predictions_identical=True,metrics_identical=True,
                fitted_parameters_identical=True,secondary_results_identical=True,coverage_results_identical=True,
                importance_values_identical=True,plotted_data_identical=True,png_bytes_identical=png_equal,joblib_bytes_identical=model_equal,
                structured_outputs_byte_identical=all(b.digest(Path(a)/p)==b.digest(Path(c)/p) for p in STRUCTURED),
                determinism_note='PNG/model bytes compared in this environment; cross-platform identity is not guaranteed.')
        final=run(root,execution_checks=checks)
        require(before==protected_hashes(root),'Tests/reruns changed protected inputs')
        require(all(b.digest(root/p)==h for p,h in final[3]['output_sha256'].items()),'Final output integrity mismatch')
    print(f'Phase 7B verified: {result.testsRun} tests, {len(final[0])} primary prediction rows; XGBoost {"unavailable" if XGBOOST_UNAVAILABLE else "evaluated"}. STOP before Phase 8.')
    print('reports/figures/')
    print('open reports/figures')
    return final


if __name__ == '__main__':
    # Active CLI requires isolated configurable outputs. Historical pure routines
    # remain available for regression, without regenerating protected artifacts.
    from cohort_pipeline import cli
    cli('ensemble')
