"""Frozen Phase 7A diagnostics and light figures; no fitting or new predictions."""
import argparse
from contextlib import contextmanager, ExitStack
import csv
from importlib import metadata
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

from cohort_io import ROOT, digest, read_json, require
import train_cohort_temporal as temporal

STAGES = {'development': ('Development validation · 2024', 2024),
          'held_out': ('Held-out test · 2025', 2025)}
LABELS = {'bernoulli_baseline': 'Dummy', 'logistic_regression': 'Logistic Regression',
          'random_forest': 'Random Forest', 'xgboost': 'XGBoost'}
COLORS = {'bernoulli_baseline': '#88939D', 'logistic_regression': '#527D9D',
          'random_forest': '#C58B57', 'xgboost': '#779584'}
SEGMENTS = [('0', 0, 0), ('1-9', 1, 9), ('10-29', 10, 29), ('30+', 30, None)]


@contextmanager
def frozen_model_guard(core):
    def forbidden(*args, **kwargs):
        raise AssertionError('Frozen diagnostics forbid fitting and new model predictions')
    classes = [core.b.Pipeline, core.b.DummyClassifier, core.b.LogisticRegression, core.RandomForestClassifier]
    if core.XGBClassifier is not None:
        classes.append(core.XGBClassifier)
    with ExitStack() as stack:
        for cls in classes:
            for method in ('fit', 'predict', 'predict_proba'):
                stack.enter_context(patch.object(cls, method, forbidden))
        yield


def coverage_summary(predictions, core):
    selected = predictions[predictions.model_name.eq('xgboost')]
    require(not selected.empty and not selected.duplicated(['appid','sale_year']).any(), 'Invalid selected-model keys')
    require(selected.prior_price_record_count.ge(0).all(), 'Negative observation counts')
    rows = []
    for label, low, high in SEGMENTS:
        mask = selected.prior_price_record_count.ge(low)
        if high is not None:
            mask &= selected.prior_price_record_count.le(high)
        group = selected[mask]
        if group.empty:
            rows.append(dict(segment=label, observations=0, actual_positive=0, actual_negative=0,
                             tn=0,fp=0,fn=0,tp=0, accuracy=None,precision=None,recall=None,balanced_accuracy=None,
                             average_precision=None,undefined_metrics='Empty subgroup'))
            continue
        value = temporal.evaluate(group,core)['models']['xgboost']
        rows.append(dict(segment=label, **{k:value[k] for k in ('observations','actual_positive','actual_negative',
                         'accuracy','precision','recall','balanced_accuracy','average_precision')},
                         tn=value['confusion_matrix'][0][0],fp=value['confusion_matrix'][0][1],
                         fn=value['confusion_matrix'][1][0],tp=value['confusion_matrix'][1][1],
                         undefined_metrics=json.dumps(value['undefined_metrics'],sort_keys=True)))
    require(sum(r['observations'] for r in rows)==len(selected), 'Coverage bins do not partition the sample')
    return rows


def assert_metrics(actual, expected, core):
    for name,value in actual['models'].items():
        require(value['confusion_matrix']==expected['models'][name]['confusion_matrix'], 'Confusion mismatch')
        for key in ('accuracy','balanced_accuracy','precision','recall','f1','roc_auc','average_precision','brier_score','log_loss'):
            left,right=value[key],expected['models'][name][key]
            if right is None:
                require(left is None, 'Undefined metric changed')
            else:
                core.np.testing.assert_allclose(left,right,rtol=1e-12,atol=1e-12)


def saved_diagnostics(predictions, context, core):
    # The frozen CSV is already annotated; the existing helper adds its own
    # feature context. Project base prediction fields to avoid duplicate joins.
    columns=['appid','sale_year','model_name','actual_label','predicted_probability','predicted_class','decision_score']
    return temporal.diagnostics(predictions[columns],context,core)


def native_importance(model, core):
    names=list(model[:-1].get_feature_names_out())
    require(names==core.b.APPROVED, 'Fitted feature order mismatch')
    gain=model.named_steps['classifier'].get_booster().get_score(importance_type='gain')
    values=core.np.zeros(len(names),dtype=float)
    for name,value in gain.items():
        index=names.index(name) if name in names else int(name[1:]) if name.startswith('f') and name[1:].isdigit() else -1
        require(0<=index<len(names), 'Unknown booster feature')
        values[index]=value
    require(values.sum()>0, 'No split gain in fitted model')
    normalized=values/values.sum()
    core.np.testing.assert_allclose(normalized,model.named_steps['classifier'].feature_importances_,rtol=1e-6,atol=1e-8)
    return [dict(feature=name,raw_average_split_gain=float(value),normalized_average_split_gain=float(weight))
            for name,value,weight in zip(names,values,normalized)]


def build(source, core):
    checks=read_json(source/'checksums.json')
    require(all(digest(source/name)==sha for name,sha in checks.items()), 'Frozen Phase 7A checksum mismatch')
    frame,protocol,_=temporal.load_frozen(ROOT/'reports/cohort_2000_modeling',core)
    selection=read_json(source/'selection.json')
    validation=read_json(source/'validation.json')
    require(selection['selected_model']=='xgboost' and selection['threshold']==.5, 'Selection/threshold changed')
    require(digest(source/'selection.json')==validation['selection_sha256'], 'Selection lock changed')
    manifest=read_json(source/'model_configuration_manifest.json')
    require(manifest['feature_allowlist']==core.b.APPROVED and manifest['classification_threshold']==.5, 'Model manifest changed')
    stages={}
    from sklearn.metrics import roc_curve, precision_recall_curve
    for stage,(label,year) in STAGES.items():
        pred=core.pd.read_csv(source/(stage+'_predictions.csv'))
        require(len(pred)==8000 and set(pred.sale_year)=={year} and set(pred.model_name)==set(temporal.ORDER), 'Wrong stage predictions')
        require(not pred.duplicated(['appid','sale_year','model_name']).any(), 'Duplicate predictions')
        context=frame[frame.sale_year.eq(year)]
        joined=pred.merge(context[['appid','sale_year','discount_observed','prior_price_record_count',
                                  'has_prior_price_history','has_prior_discount_observation']],on=['appid','sale_year'],validate='many_to_one',suffixes=('_saved','_frozen'))
        require(joined.actual_label.eq(joined.discount_observed).all(), 'Target/prediction mismatch')
        for name in ('prior_price_record_count','has_prior_price_history','has_prior_discount_observation'):
            require(joined[name+'_saved'].eq(joined[name+'_frozen']).all(), 'Coverage metadata mismatch')
        require(pred.predicted_probability.between(0,1).all() and
                pred.predicted_class.eq(pred.predicted_probability.ge(.5).astype(int)).all(), 'Probability/threshold mismatch')
        metrics=temporal.evaluate(pred,core)
        assert_metrics(metrics,read_json(source/(stage+'_metrics.json')),core)
        coverage=coverage_summary(pred,core)
        old_coverage=core.pd.read_csv(source/(stage+'_coverage_metrics.csv'))
        for row in coverage:
            old=old_coverage[old_coverage.model.eq('xgboost') & old_coverage.family.eq('price_observation_density') & old_coverage.segment.eq(row['segment'])].iloc[0]
            for key in ('observations','actual_positive','actual_negative','tn','fp','fn','tp'):
                require(row[key]==int(old[key]), 'Frozen coverage counts changed')
            for key in ('accuracy','precision','recall','balanced_accuracy','average_precision'):
                if row[key] is None:
                    require(core.pd.isna(old[key]), 'Undefined subgroup metric changed')
                else:
                    core.np.testing.assert_allclose(row[key],old[key],rtol=1e-12,atol=1e-12)
        diagnostic=saved_diagnostics(pred,context,core)
        saved_diag=read_json(source/(stage+'_diagnostics.json'))
        for name, values in diagnostic['summary'].items():
            for key in ('equal_width_10_bin_ece','mean_probability','observed_prevalence','probability_vs_record_count_spearman'):
                expected=saved_diag['summary'][name][key]
                require(values[key] is None, 'Correlation undefinedness changed') if expected is None else core.np.testing.assert_allclose(values[key],expected,rtol=1e-12,atol=1e-12)
        curves={}
        for name,group in pred.groupby('model_name',sort=True):
            fpr,tpr,_=roc_curve(group.actual_label,group.predicted_probability,drop_intermediate=False)
            precision,recall,_=precision_recall_curve(group.actual_label,group.predicted_probability)
            curves[name]=dict(fpr=fpr.tolist(),tpr=tpr.tolist(),precision=precision.tolist(),recall=recall.tolist())
        stages[stage]=dict(label=label,year=year,predictions=pred,metrics=metrics,coverage=coverage,diagnostics=diagnostic,curves=curves)
    pipelines={name:core.joblib.load(source/'final_models'/(name+'.joblib')) for name in temporal.ORDER}
    for name,model in pipelines.items():
        estimator=model if name=='bernoulli_baseline' else model.named_steps['classifier']
        for key,value in manifest['fixed_configurations'][name].items():
            require(estimator.get_params()[key]==value, 'Saved estimator configuration changed')
        if name!='bernoulli_baseline':
            require(list(model[:-1].get_feature_names_out())==core.b.APPROVED, 'Pipeline predictors changed')
    require(digest(source/'selected_model.joblib')==digest(source/'final_models/xgboost.joblib'), 'Selected artifact differs')
    importance=native_importance(pipelines['xgboost'],core)
    old_importance=core.pd.read_csv(source/'feature_importance.csv')
    saved=old_importance[old_importance.stage.eq('final') & old_importance.model.eq('xgboost')].set_index('feature')
    for row in importance:
        core.np.testing.assert_allclose(row['normalized_average_split_gain'],saved.loc[row['feature'],'value'],rtol=1e-6,atol=1e-8)
    return dict(stages=stages,importance=importance,manifest=manifest,selection=selection,protocol=protocol,
                input_sha256={str((source/name).relative_to(ROOT)):digest(source/name) for name in checks},
                pipeline_inspection='Read-only parameter/schema/gain inspection; no fit, predict or predict_proba calls')


def write_json(path,value,core):
    with path.open('x',encoding='utf-8') as stream:
        stream.write(json.dumps(core.clean(value),indent=2,sort_keys=True,allow_nan=False)+'\n')


def write_csv(path,rows):
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with path.open('x',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields)
        writer.writeheader();writer.writerows(rows)


def coverage_labels(rows):
    return [r['segment']+' records\n'+f"n={r['observations']}; 1:{r['actual_positive']} / 0:{r['actual_negative']}" for r in rows]


def generate_figures(destination,data,core):
    from plotting_style import light_style,plt
    from matplotlib.colors import LinearSegmentedColormap
    captions=[]
    def finish(fig,name,title,caption):
        fig.text(.5,.015,caption,ha='center',va='bottom',fontsize=8,color='#616970')
        fig.tight_layout(rect=(0,.075,1,1))
        fig.savefig(destination/(name+'.png'),dpi=300,facecolor='white',metadata={'Software':'Steam cohort Phase 7B'})
        plt.close(fig)
        captions.append(dict(filename=name+'.png',title=title,caption=caption,dpi=300))
    def grid(ax,axis='y'):
        ax.grid(axis=axis,color='#E9ECEF',linewidth=.5);ax.set_axisbelow(True)
    with light_style():
        for stage,item in data['stages'].items():
            label=item['label'];metrics=item['metrics']['models'];pred=item['predictions'];rows=item['coverage']
            selected=pred[pred.model_name.eq('xgboost')];year=item['year']
            footer=f'{year}: '+('development validation' if stage=='development' else 'held-out testing')+' · Observed ITAD evidence, not verified participation'
            fig,axes=plt.subplots(2,2,figsize=(9.0,6.5))
            for ax,(key,title) in zip(axes.flat,[('average_precision','Average precision ↑'),('roc_auc','ROC-AUC ↑'),('balanced_accuracy','Balanced accuracy ↑'),('brier_score','Brier score ↓')]):
                values=[metrics[name][key] for name in temporal.ORDER]
                ax.barh([LABELS[n] for n in temporal.ORDER],values,color=[COLORS[n] for n in temporal.ORDER],height=.58)
                ax.invert_yaxis();ax.set(title=title,xlim=(0,1 if key!='brier_score' else .3))
                for i,value in enumerate(values):
                    ax.text(value+.012 if key!='brier_score' else value+.003,i,f'{value:.3f}',va='center',ha='left',fontsize=9)
                grid(ax,'x')
            fig.suptitle(label+' · Model comparison',fontsize=14)
            finish(fig,stage+'_model_comparison',label+' model comparison',footer)
            for kind in ('roc','pr'):
                fig,ax=plt.subplots(figsize=(7.2,4.9))
                for name in temporal.ORDER:
                    curve=item['curves'][name]
                    if kind=='roc':
                        ax.plot(curve['fpr'],curve['tpr'],color=COLORS[name],label=f"{LABELS[name]} · AUC {metrics[name]['roc_auc']:.3f}")
                    else:
                        ax.step(curve['recall'],curve['precision'],where='post',color=COLORS[name],label=f"{LABELS[name]} · AP {metrics[name]['average_precision']:.3f}")
                if kind=='roc':
                    ax.plot([0,1],[0,1],color='#BCC3C9',ls='--',lw=.9);ax.set(xlabel='False positive rate',ylabel='True positive rate')
                else:
                    prevalence=item['metrics']['validation_positive_prevalence']
                    ax.axhline(prevalence,color='#BCC3C9',ls='--',lw=.9,label=f'Observed prevalence {prevalence:.3f}')
                    ax.set(xlabel='Recall',ylabel='Precision')
                ax.set(title=label+' · '+('ROC curves' if kind=='roc' else 'Precision–recall curves'),xlim=(0,1),ylim=(0,1.025))
                ax.legend(loc='lower right' if kind=='roc' else 'lower left',fontsize=8);grid(ax)
                finish(fig,stage+'_'+kind+'_curves',label+' '+kind.upper()+' curves',footer)
            fig,ax=plt.subplots(figsize=(6.4,4.9))
            matrix=core.np.array(metrics['xgboost']['confusion_matrix'])
            ax.imshow(matrix,cmap=LinearSegmentedColormap.from_list('gain_light',['#FFFFFF','#DCE8E2',COLORS['xgboost']]),vmin=0,vmax=matrix.max())
            for i in range(2):
                for j in range(2):
                    ax.text(j,i,f'{matrix[i,j]:,}',ha='center',va='center',fontsize=17,color='white' if matrix[i,j]>.7*matrix.max() else '#34414B')
            ax.set(xticks=[0,1],yticks=[0,1],xticklabels=['No discount\nobserved (0)','Discount\nobserved (1)'],yticklabels=['No discount\nobserved (0)','Discount\nobserved (1)'],
                   xlabel='Predicted operational label',ylabel='Actual operational label',title=label+' · XGBoost confusion')
            for spine in ax.spines.values():spine.set_visible(False)
            finish(fig,stage+'_xgboost_confusion',label+' selected-model confusion',f'{year} · Fixed threshold 0.50 · Rows actual; columns predicted')
            fig,ax=plt.subplots(figsize=(7.2,4.9))
            for name in temporal.ORDER:
                bins=[r for r in item['diagnostics']['calibration_bins'] if r['model']==name and r['observations']]
                ax.plot([r['mean_probability'] for r in bins],[r['observed_positive_fraction'] for r in bins],'-o',ms=4,color=COLORS[name],label=LABELS[name])
            ax.plot([0,1],[0,1],ls='--',lw=.9,color='#BCC3C9',label='Perfect-calibration reference')
            ax.set(title=label+' · Probability calibration',xlabel='Mean predicted probability within bin',ylabel='Observed positive fraction within bin',xlim=(0,1),ylim=(0,1.025));ax.legend(fontsize=8);grid(ax)
            finish(fig,stage+'_calibration',label+' calibration',f'{year} · Ten fixed equal-width bins; empty bins omitted · No calibrator fitted')
            fig,ax=plt.subplots(figsize=(7.2,4.9))
            for target,color,text in [(0,COLORS['bernoulli_baseline'],'Operational zero'),(1,COLORS['xgboost'],'Observed positive')]:
                ax.hist(selected.loc[selected.actual_label.eq(target),'predicted_probability'],bins=core.np.linspace(0,1,21),color=color,alpha=.75,label=text)
            ax.axvline(.5,color='#527D9D',ls='--',lw=1,label='Fixed threshold 0.50')
            ax.set(title=label+' · XGBoost probabilities',xlabel='Predicted probability of observed discount evidence',ylabel='Games',xlim=(0,1));ax.legend(fontsize=8);grid(ax)
            finish(fig,stage+'_probability_distribution',label+' selected probability distribution',footer)
            fig,ax=plt.subplots(figsize=(7.2,4.9))
            counts=selected.prior_price_record_count.to_numpy()
            ax.hist(counts,bins=core.np.arange(0,int(counts.max())+11,10),color=COLORS['xgboost'],alpha=.9)
            ax.set(title=label+' · Historical observation counts',xlabel='Valid price observations strictly before prediction cutoff',ylabel='Games')
            ax.text(.98,.92,f'n = {len(selected):,}\nZero observations = {int((counts==0).sum())}',transform=ax.transAxes,ha='right',va='top',fontsize=9);grid(ax)
            finish(fig,stage+'_observation_count_distribution',label+' observation count distribution',f'{year} · 10-record histogram bins; zero counts remain explicit in annotation')
            fig,ax=plt.subplots(figsize=(7.2,4.9))
            ax.scatter(counts,selected.predicted_probability,s=9,alpha=.22,color=COLORS['xgboost'],edgecolors='none')
            ax.set_xscale('symlog',linthresh=1);ax.set_xticks([0,1,10,30,100,300]);ax.set_xticklabels(['0','1','10','30','100','300'])
            rho=item['diagnostics']['summary']['xgboost']['probability_vs_record_count_spearman']
            ax.set(title=label+' · Coverage and XGBoost score',xlabel='Prior price observation count (symlog scale)',ylabel='Saved predicted probability',ylim=(-.025,1.025),xlim=(-.1,300))
            ax.text(.98,.05,f'Spearman ρ = {rho:.4f}',transform=ax.transAxes,ha='right',fontsize=10);grid(ax)
            finish(fig,stage+'_coverage_probability',label+' observation count versus probability',f'{year} · All 2,000 saved probabilities · Correlation is descriptive, not causal')
            x=core.np.arange(4);ticks=coverage_labels(rows)
            fig,ax=plt.subplots(figsize=(8.5,5.3))
            zeros=[r['actual_negative']/r['observations'] for r in rows];ones=[r['actual_positive']/r['observations'] for r in rows]
            ax.bar(x,zeros,width=.6,color=COLORS['bernoulli_baseline'],label='Operational zero (0)')
            ax.bar(x,ones,bottom=zeros,width=.6,color=COLORS['xgboost'],label='Observed positive (1)')
            for i,row in enumerate(rows):ax.text(i,1.015,f"{100*ones[i]:.1f}% positive",ha='center',fontsize=9)
            ax.set(title=label+' · Labels by coverage',xticks=x,xticklabels=ticks,ylabel='Share of games',ylim=(0,1.13))
            ax.legend(loc='upper center',bbox_to_anchor=(.5,-.16),ncol=2,fontsize=9);grid(ax)
            finish(fig,stage+'_labels_by_coverage',label+' operational labels by coverage',f'{year} · Tick labels include subgroup n and operational class counts · Zeros do not verify nonparticipation')
            fig,ax=plt.subplots(figsize=(8.5,5.3))
            for key,color,marker,text in [('accuracy','#527D9D','o','Accuracy'),('precision','#C58B57','s','Precision'),('recall','#779584','^','Recall'),('balanced_accuracy','#7F7896','D','Balanced accuracy')]:
                values=[core.np.nan if r[key] is None else r[key] for r in rows]
                ax.plot(x,values,marker=marker,color=color,label=text,lw=1.4,ms=5)
            ax.text(.04,.14,'0-record group:\nPrecision, recall and balanced accuracy: N/A',
                    transform=ax.transAxes,ha='left',fontsize=8,color='#616970')
            ax.set(title=label+' · XGBoost performance by coverage',xticks=x,xticklabels=ticks,ylabel='Metric value',ylim=(0,1.04))
            ax.legend(loc='upper center',bbox_to_anchor=(.5,-.16),ncol=4,fontsize=8);grid(ax)
            finish(fig,stage+'_performance_by_coverage',label+' selected performance by coverage',f'{year} · Missing metrics are undefined, not zero · Fixed threshold 0.50')
            fig,ax=plt.subplots(figsize=(8.5,5.3))
            for offset,key,color,text in [(-.17,'fp',COLORS['random_forest'],'False positives'),(.17,'fn',COLORS['logistic_regression'],'False negatives')]:
                values=[r[key] for r in rows]
                ax.bar(x+offset,values,width=.3,color=color,label=text)
                for i,value in enumerate(values):ax.text(i+offset,value+1,str(value),ha='center',va='bottom',fontsize=9)
            ax.set(title=label+' · XGBoost errors by coverage',xticks=x,xticklabels=ticks,ylabel='Games',ylim=(0,max(max(r['fp'],r['fn']) for r in rows)*1.22+5))
            ax.legend(fontsize=9);grid(ax)
            finish(fig,stage+'_errors_by_coverage',label+' selected errors by coverage',f'{year} · Counts, not rates; subgroup sample and class sizes differ · Threshold 0.50')
        importance=sorted(data['importance'],key=lambda r:r['normalized_average_split_gain'])
        fig,ax=plt.subplots(figsize=(8.0,6.0))
        ax.barh([r['feature'] for r in importance],[r['normalized_average_split_gain'] for r in importance],color=COLORS['xgboost'],height=.62)
        ax.set(title='Final XGBoost · Feature importance',xlabel='Normalized average split gain (sums to 1)')
        grid(ax,'x')
        finish(fig,'xgboost_gain_importance','Fitted XGBoost native importance','2023–2024 fitted model · Existing booster inspected only · Correlated predictors share importance; no causal interpretation')
    return captions


def model_card(name,data):
    m=data['manifest'];dev=data['stages']['development']['metrics']['models'][name];test=data['stages']['held_out']['metrics']['models'][name]
    selected=name=='xgboost'
    features=', '.join('`'+f+'`' for f in m['feature_allowlist'])
    return f'''# {LABELS[name]} — frozen model card

Status: {'selected using 2024 average precision' if selected else 'predefined comparison; not selected'}. Configuration and threshold were not revised using 2025 results.

## Objective and data

Predict observed ITAD Steam Autumn Sale discount evidence, positive class 1.
Operational policy: A→1, B→0, C→Unknown, D→0. **Operational zeros mean no discount
observed in available evidence; they do not establish verified nonparticipation.**
Frozen cohort: 2,000 games, 6,000 game-year rows, 3,030 positives, 2,970 zeros,
zero unknowns. US / Steam shop 61 historical evidence; 81 successfully empty
histories contribute 243 operational zeros. This is not a representative census
of Steam games. No target or feature was redesigned.

## Features and missing values

Approved runner predictors: {features}.
{'This Dummy ignores predictors and estimates only the training class prior.' if name=='bernoulli_baseline' else 'The fitted pipeline uses only these 15 features; identifiers, year, target, category and cutoff/audit fields are excluded.'}
{'No learned feature preprocessing.' if name=='bernoulli_baseline' else 'Median imputation is fitted on training predictors only; no preparation-time zero filling. '+('Logistic scaling is fitted on training-imputed values only.' if name=='logistic_regression' else 'Tree predictors are not scaled.')}
No training feature was entirely missing, so the all-missing structural-zero
contingency was unused. Complete fitted preprocessing is retained in the saved pipeline.

## Temporal design and selection

Development: train 2023 (2,000 rows), validate 2024 (2,000).
Final: refit with fresh preprocessing on 2023–2024 (4,000), test 2025 (2,000).
All 2,000 games recur across years; evaluation measures later-sale performance
on previously represented games, **not unseen-game generalization**.
The observations are dependent within game. Previously audited 2025 outcomes
do not constitute a fresh confirmatory holdout.

One predefined configuration per model, seed 42, threshold .50. No tuning,
early stopping, probability calibration fitting or threshold optimization.
Selection used only 2024 average precision, then Brier score for ties; XGBoost
won before the single held-out probability pass. Other test comparisons did not
change selection. Parameters: `{json.dumps(m['fixed_configurations'][name],sort_keys=True)}`.

## Recorded performance

| Metric | Development 2024 | Held-out 2025 |
| --- | ---: | ---: |
'''+ '\n'.join(f"| {label} | {'undefined' if dev[key] is None else format(dev[key],'.6f')} | {'undefined' if test[key] is None else format(test[key],'.6f')} |" for key,label in [('accuracy','Accuracy'),('balanced_accuracy','Balanced accuracy'),('precision','Precision'),('recall','Recall'),('f1','F1'),('roc_auc','ROC-AUC'),('average_precision','Average precision / PR-AUC'),('brier_score','Brier score')])+f'''

Confusion matrices (actual 0/1 rows, predicted 0/1 columns): development
`{dev['confusion_matrix']}`; held-out `{test['confusion_matrix']}`.
Undefined metrics are saved as null with reasons. AP is the step-weighted
ranking measure, not trapezoidal PR interpolation.

## Coverage, calibration and limitations

Held-out score/observation-count Spearman correlation:
`{data['stages']['held_out']['diagnostics']['summary'][name]['probability_vs_record_count_spearman']}`.
Ten-bin held-out calibration error:
`{data['stages']['held_out']['diagnostics']['summary'][name]['equal_width_10_bin_ece']:.6f}`.
Calibration is descriptive and bin-dependent; no calibrator was fitted.
Returned observation density, recording gaps and historical discounts may
predict provider coverage as well as actual discount propensity. Correlation
and split gain do not establish causation. Sparse subgroups can have high
accuracy while missing rare positives. Single-class discrimination is undefined.

Retrospective record timestamps do not prove ITAD contemporaneous availability:
backfill/initialization remain unverified. Reported release dates and their
stability are assumed; release-hour ambiguity, raw timestamp/shop conflicts and
snapshot-based population selection remain documented limitations. No raw
history was repaired, deduplicated or treated as continuous daily price states.
No seed sensitivity, unseen-game test or prospective new-year evaluation ran.

## Appropriate and inappropriate uses

Appropriate: retrospective analysis of recorded discount evidence, comparison
of fixed models, exploratory probability/coverage diagnostics within the
documented source scope and calendar windows.
Inappropriate: certifying actual Steam sale participation/nonparticipation,
interpreting zero as proven absence, causal claims from importance/correlation,
guaranteeing future discounts or purchase savings, claiming unseen-game or
population-wide performance, or tuning models/thresholds using 2025 diagnostics.

Artifacts: `../cohort_2000_models/final_models/{name}.joblib`;
configuration, versions and checksums are in the preserved Phase 7A manifest.
This card and all figures use saved outputs only. No fitting or new probability
predictions were made in Phase 7B.
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir',type=Path,default=ROOT/'reports/cohort_2000_models')
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args();destination=args.output_dir.resolve()
    require(destination.is_relative_to(ROOT/'reports') and not destination.exists(),'Choose a new reports directory')
    require(not any(p.is_symlink() for p in [args.output_dir.absolute(),*args.output_dir.absolute().parents]),'Symlink output forbidden')
    runtime=Path('/private/tmp/steam-cohort-visualizations-runtime');runtime.mkdir(exist_ok=True)
    os.environ['MPLCONFIGDIR']=str(runtime)
    import tempfile
    tempfile.tempdir=str(runtime)
    def guard(event,values):
        if event in ('socket.connect','socket.getaddrinfo'):raise RuntimeError('Offline diagnostics forbid network')
        if event=='subprocess.Popen':raise OSError('External commands forbidden')
        if event=='open' and (values[2] or 0)&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):
            if isinstance(values[0],(str,bytes,os.PathLike)):
                p=Path(os.fsdecode(values[0])).resolve();require(p.is_relative_to(destination) or p.is_relative_to(runtime),'Writes confined to new reports/runtime')
        if event in ('os.remove','os.rename','os.mkdir','os.rmdir','os.symlink','os.link','os.chmod','os.utime'):
            for value in values[:2] if event in ('os.rename','os.link') else values[:1]:
                if isinstance(value,(str,bytes,os.PathLike)):
                    p=Path(os.fsdecode(value)).resolve();require(p.is_relative_to(destination) or p.is_relative_to(runtime),'Mutations confined to new reports/runtime')
    sys.addaudithook(guard)
    baseline=read_json(ROOT/'tests/scalable_artifact_hashes.json')
    files={p for folder in ('data','reports','models') for p in (ROOT/folder).rglob('*') if p.is_file()};files.update(ROOT/name for name in baseline)
    before={str(p.relative_to(ROOT)):digest(p) for p in files}
    core=temporal.cores()
    with frozen_model_guard(core):
        data=build(args.input_dir.resolve(),core)
        destination.mkdir()
        captions=generate_figures(destination,data,core)
        comparisons=[];coverage=[];curves=[];calibration=[]
        for stage,item in data['stages'].items():
            comparisons.extend(temporal.flat_metrics(item['metrics'],stage))
            coverage.extend(dict(stage=stage,**row) for row in item['coverage'])
            calibration.extend(dict(stage=stage,**row) for row in item['diagnostics']['calibration_bins'])
            for name,curve in item['curves'].items():
                curves.extend(dict(stage=stage,model=name,kind='roc',x=x,y=y) for x,y in zip(curve['fpr'],curve['tpr']))
                curves.extend(dict(stage=stage,model=name,kind='precision_recall',x=x,y=y) for x,y in zip(curve['recall'],curve['precision']))
        write_csv(destination/'model_comparison.csv',comparisons)
        write_csv(destination/'coverage_summary.csv',coverage)
        write_csv(destination/'curve_points.csv',curves)
        write_csv(destination/'calibration_bins.csv',calibration)
        write_csv(destination/'xgboost_gain_importance.csv',data['importance'])
        write_csv(destination/'figure_captions.csv',captions)
        (destination/'figure_captions.md').write_text('# Figure captions\n\n'+'\n\n'.join(f"**{r['filename']}** — {r['title']}. {r['caption']}." for r in captions)+'\n')
        for name in temporal.ORDER:(destination/('model_card_'+name+'.md')).write_text(model_card(name,data))
        write_json(destination/'plot_data.json',dict(stages={stage:{key:value for key,value in item.items() if key!='predictions'} for stage,item in data['stages'].items()},
                                                   importance=data['importance'],model_colors=COLORS,captions=captions),core)
    require(all(digest(ROOT/name)==sha for name,sha in before.items()),'Preexisting artifact changed')
    validation=dict(figures=len(captions),model_cards=4,dpi=300,white_background=True,
                     saved_metrics_verified=True,saved_coverage_counts_metrics_verified=True,
                     native_gain_verified_against_saved_importance=True,
                     no_network=True,no_model_fitting=True,no_new_model_predictions=True,
                     threshold=.5,selection_unchanged=True,input_sha256=data['input_sha256'],
                     source_sha256={name:digest(ROOT/name) for name in ('src/visualize_cohort_models.py','src/plotting_style.py','src/train_cohort_temporal.py')},
                     versions={name:metadata.version(name) for name in ('numpy','pandas','scikit-learn','xgboost','matplotlib','Pillow')},
                     preserved_input_files=len(before),preservation_sha256=before,
                     protected_artifacts_preserved_this_phase=len(baseline),
                     historical_baseline_matches=sum(before[name]==value['sha256'] for name,value in baseline.items()))
    write_json(destination/'validation.json',validation,core)
    write_json(destination/'checksums.json',{p.name:digest(p) for p in sorted(destination.iterdir()) if p.is_file()},core)
    print(json.dumps(dict(figures=len(captions),model_cards=4,preserved_input_files=len(before),protected_preserved=len(baseline),historical_baseline_matches=validation['historical_baseline_matches'])))


if __name__=='__main__':main()
