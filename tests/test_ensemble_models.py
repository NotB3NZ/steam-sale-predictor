"""Offline Phase 7B tests with isolated fixtures and protected Phase 7A artifacts."""
import ast
import copy
import importlib.util
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

import joblib
import numpy as np
import pandas as pd
from sklearn import metrics as skmetrics

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('ensemble_models',ROOT/'src/09_train_ensemble_models.py')
e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)
b=e.b


class EnsembleModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with b.offline_guard():
            cls.frame,cls.manifest,cls.inspection=b.inspect_inputs(ROOT)
            cls.train,cls.valid=e.split_protocol(cls.frame,[2023,2024],2025)
            cls.baselines,cls.baseline_metrics=e.load_baselines(ROOT,cls.valid)
            cls.models,cls.profiles=e.fit_models(cls.train)
            cls.predictions=e.predict(cls.models,cls.valid)
            cls.combined=pd.concat([cls.baselines,cls.predictions],ignore_index=True)
            cls.metrics=b.evaluate(cls.combined)
            cls.temporal=e.secondary_experiment(cls.frame,cls.metrics)
            cls.coverage=e.coverage_diagnostic(cls.train,cls.valid,cls.baselines)
            cls.importance=e.feature_importances(cls.models,cls.valid)
            cls.data=e.plot_data(cls.combined,cls.metrics,cls.temporal,cls.coverage,cls.importance)

    def test_chronological_split_counts_and_classes(self):
        self.assertEqual(len(self.train),200);self.assertEqual(len(self.valid),100)
        self.assertEqual(set(self.train.sale_year),{2023,2024});self.assertEqual(set(self.valid.sale_year),{2025})
        self.assertEqual(self.train[b.TARGET].value_counts().to_dict(),{1:115,0:85})
        self.assertEqual(self.valid[b.TARGET].value_counts().to_dict(),{1:60,0:40})
        self.assertEqual(set(self.train.appid),set(self.valid.appid))

    def test_exact_manifest_allowlist_and_transformed_schema(self):
        self.assertEqual(b.APPROVED,self.manifest['baseline_feature_allowlist'])
        self.assertEqual(len(b.APPROVED),15)
        for name,model in self.models.items():
            self.assertEqual(model[:-1].get_feature_names_out().tolist(),b.APPROVED)
            self.assertEqual(self.profiles[name]['transformed_features'],b.APPROVED)
            self.assertNotIn('scale',model.named_steps)

    def test_no_identifier_target_audit_predictors_and_adversarial_injection(self):
        altered=self.frame.copy()
        for name in ['evidence_category','pu_status','current_sale_prices','future_price','contemporary_reviews']:
            altered[name]=np.arange(300)
        altered[b.TARGET]=1-altered[b.TARGET];altered['audit_release_hour_uncertain']=999
        pd.testing.assert_frame_equal(e.numeric_predictors(altered),e.numeric_predictors(self.frame))
        self.assertFalse(set(b.PROHIBITED)&set(e.numeric_predictors(altered).columns))
        with self.assertRaises(ValueError):e.numeric_predictors(altered,b.APPROVED+[b.TARGET])
        for name,model in self.models.items():
            direct=self.valid.copy();direct['evidence_category']=999;direct[b.TARGET]=999
            np.testing.assert_array_equal(model.predict_proba(direct),model.predict_proba(e.numeric_predictors(self.valid)))

    def test_training_only_imputation_no_scaling(self):
        expected=e.numeric_predictors(self.train).median().to_numpy()
        for name,model in self.models.items():
            np.testing.assert_array_equal(model.named_steps['impute'].statistics_,expected)
            self.assertEqual(self.profiles[name]['training_rows'],200)
            self.assertEqual(self.profiles[name]['training_years'],[2023,2024])
            self.assertEqual(self.profiles[name]['scaling'],'none')

    def test_all_missing_column_preserves_schema(self):
        train=self.train.copy();train['last_observed_price']=np.nan
        models,profiles=e.fit_models(train)
        for name,model in models.items():
            self.assertEqual(profiles[name]['all_missing_training_features'],['last_observed_price'])
            self.assertEqual(profiles[name]['transformed_features'],b.APPROVED)
            self.assertEqual(model.named_steps['impute'].statistics_[b.APPROVED.index('last_observed_price')],0)
        e.predict(models,self.valid)

    def test_no_validation_or_future_fitting(self):
        for frame in [self.frame,self.valid,self.train.assign(sale_year=2026)]:
            with self.assertRaisesRegex(ValueError,'nontraining'):e.fit_models(frame)
        with self.assertRaisesRegex(ValueError,'Unsupported'):e.split_protocol(self.frame,[2024],2025)
        with self.assertRaisesRegex(ValueError,'secondary'):e.fit_models(self.train,include_baselines=True)

    def test_predefined_hyperparameters_fixed(self):
        for name,model in self.models.items():
            expected=e.RF_PARAMS if name=='random_forest' else e.XGB_PARAMS
            for key,value in expected.items():self.assertEqual(model.named_steps['classifier'].get_params()[key],value)
        self.assertEqual(e.RF_PARAMS,dict(n_estimators=200,max_depth=4,min_samples_leaf=5,max_features='sqrt',random_state=42,n_jobs=1))
        self.assertEqual(e.XGB_PARAMS,dict(n_estimators=100,max_depth=3,learning_rate=0.05,subsample=0.8,colsample_bytree=0.8,objective='binary:logistic',eval_metric='logloss',random_state=42,n_jobs=1))

    @unittest.skipIf(e.XGBClassifier is None,'XGBoost unavailable locally; no network installation authorized')
    def test_xgboost_fitting_no_early_stopping_validation_or_substitution(self):
        classifier=self.models['xgboost'].named_steps['classifier']
        self.assertIsInstance(classifier,e.XGBClassifier)
        self.assertEqual(classifier.get_booster().num_boosted_rounds(),100)
        self.assertIsNone(classifier.get_params().get('early_stopping_rounds'))
        self.assertIsNone(classifier.get_params().get('callbacks'))
        with self.assertRaisesRegex(e.xgboost.core.XGBoostError,
                r"No evaluation result, `eval_set` is not used during training\."):
            classifier.evals_result()
        # Independently inspect the actual sklearn-pipeline fit call: only the
        # training predictor matrix and labels reach XGBoost, with no fit options.
        with patch.object(e.XGBClassifier,'fit',autospec=True,
                side_effect=e.XGBClassifier.fit) as fit:
            models,_=e.fit_models(self.train)
        self.assertEqual(fit.call_count,1)
        self.assertEqual(fit.call_args.kwargs,{})
        self.assertEqual(len(fit.call_args.args),3)
        np.testing.assert_array_equal(fit.call_args.args[1],
            models['xgboost'][:-1].transform(e.numeric_predictors(self.train)))
        np.testing.assert_array_equal(fit.call_args.args[2],self.train[b.TARGET].to_numpy())

    def test_xgboost_availability_reported_honestly(self):
        self.assertEqual(e.clean({"missing":np.float32(np.nan)}),{"missing":"NaN"})
        json.dumps(e.clean({"missing":float("nan")}),allow_nan=False)
        if e.XGBClassifier is None:
            self.assertNotIn('xgboost',self.models);self.assertIn('xgboost',e.unavailable_models())
            with self.assertRaisesRegex(ValueError,'unavailable'):e.pipeline('xgboost')
        else:self.assertIn('xgboost',self.models);self.assertEqual(e.unavailable_models(),{})

    def test_fixed_inclusive_threshold_and_valid_probabilities(self):
        np.testing.assert_array_equal(b.classes([0,0.4999,0.5,1]),[0,0,1,1])
        p=self.predictions.predicted_probability
        self.assertTrue(np.isfinite(p).all());self.assertTrue(p.between(0,1).all())
        np.testing.assert_array_equal(self.predictions.predicted_class,b.classes(p))
        self.assertTrue(self.predictions.decision_score.isna().all())

    def test_prediction_schema_counts_identity_and_labels(self):
        self.assertTrue(e.validate_predictions(self.combined,self.valid,list(e.ORDER[:2])+list(self.models)))
        self.assertEqual(len(self.predictions),100*len(self.models))
        self.assertFalse(self.combined.duplicated(b.KEYS+['model_name']).any())
        for _,f in self.combined.groupby('model_name'):
            pd.testing.assert_frame_equal(f[b.KEYS].reset_index(drop=True),self.valid[b.KEYS])
            np.testing.assert_array_equal(f.actual_label,self.valid[b.TARGET])

    def test_invalid_prediction_alignment_and_probability_rejected(self):
        for column,value in [('appid',1),('actual_label',99),('sale_year',2024),('predicted_probability',np.inf),('predicted_class',99)]:
            altered=self.combined.copy();altered.loc[0,column]=value
            with self.assertRaises(ValueError):e.validate_predictions(altered,self.valid,e.ORDER[:2]+list(self.models))
        duplicated=pd.concat([self.combined,self.combined.iloc[:1]])
        with self.assertRaises(ValueError):e.validate_predictions(duplicated,self.valid,e.ORDER[:2]+list(self.models))

    def test_adversarial_validation_targets_do_not_change_fitted_parameters_or_probabilities(self):
        altered=self.frame.copy();mask=altered.sale_year.eq(2025);altered.loc[mask,b.TARGET]=1-altered.loc[mask,b.TARGET]
        train,valid=e.split_protocol(altered,[2023,2024],2025);models,profiles=e.fit_models(train)
        self.assertEqual(e.fitted_parameters(models),e.fitted_parameters(self.models));self.assertEqual(profiles,self.profiles)
        predictions=e.predict(models,valid)
        np.testing.assert_array_equal(predictions.predicted_probability,self.predictions.predicted_probability)
        self.assertFalse(np.array_equal(predictions.actual_label,self.predictions.actual_label))

    def test_adversarial_validation_features_do_not_change_preprocessing(self):
        altered=self.frame.copy();mask=altered.sale_year.eq(2025)
        for f in b.APPROVED:altered.loc[mask,f]=1e6
        train,valid=e.split_protocol(altered,[2023,2024],2025);models,profiles=e.fit_models(train)
        self.assertEqual(profiles,self.profiles);self.assertEqual(e.fitted_parameters(models),e.fitted_parameters(self.models))
        e.predict(models,valid)

    def test_adversarial_shuffling_preserves_appid_year_association(self):
        train,valid=e.split_protocol(self.frame.sample(frac=1,random_state=9),[2023,2024],2025)
        models,_=e.fit_models(train)
        pd.testing.assert_frame_equal(e.predict(models,valid.sample(frac=1,random_state=4)),self.predictions,check_exact=True)

    def test_metrics_match_independent_sklearn_calculations(self):
        for name,f in self.combined.groupby('model_name'):
            y,p,c=f.actual_label,f.predicted_probability,f.predicted_class
            expected=dict(roc_auc=skmetrics.roc_auc_score(y,p),average_precision=skmetrics.average_precision_score(y,p),
                brier_score=skmetrics.brier_score_loss(y,p),log_loss=skmetrics.log_loss(y,p),accuracy=skmetrics.accuracy_score(y,c),
                precision=skmetrics.precision_score(y,c),recall=skmetrics.recall_score(y,c),f1=skmetrics.f1_score(y,c))
            for key,value in expected.items():self.assertAlmostEqual(self.metrics['models'][name][key],value,places=14)
        for name in e.ORDER[:2]:self.assertEqual(self.metrics['models'][name],self.baseline_metrics['models'][name])
        self.assertEqual(e.METRIC_DIRECTIONS['brier_score'],'lower');self.assertEqual(e.METRIC_DIRECTIONS['roc_auc'],'higher')

    def test_confusion_matrix_actual_rows_predicted_columns(self):
        for name,f in self.combined.groupby('model_name'):
            expected=[[int(((f.actual_label==actual)&(f.predicted_class==predicted)).sum()) for predicted in [0,1]] for actual in [0,1]]
            self.assertEqual(self.metrics['models'][name]['confusion_matrix'],expected)

    def test_serialization_complete_pipeline_identical_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            for name,model in self.models.items():
                path=Path(directory)/(name+'.joblib');joblib.dump(model,path);loaded=joblib.load(path)
                self.assertEqual(list(loaded.named_steps),['select','impute','classifier'])
                np.testing.assert_array_equal(model.predict_proba(e.numeric_predictors(self.valid)),loaded.predict_proba(e.numeric_predictors(self.valid)))
                self.assertEqual(e.fitted_parameters({name:model}),e.fitted_parameters({name:loaded}))

    def test_repeated_predictions_metrics_parameters_deterministic(self):
        models,profiles=e.fit_models(self.train);predictions=e.predict(models,self.valid)
        pd.testing.assert_frame_equal(predictions,self.predictions,check_exact=True)
        self.assertEqual(profiles,self.profiles);self.assertEqual(e.fitted_parameters(models),e.fitted_parameters(self.models))
        self.assertEqual(b.evaluate(predictions),b.evaluate(self.predictions))

    def test_secondary_split_counts_prior_preprocessing_and_configurations(self):
        train,valid=e.split_protocol(self.frame,[2023],2024)
        self.assertEqual(len(train),100);self.assertEqual(len(valid),100)
        self.assertEqual(set(train.sale_year),{2023});self.assertEqual(set(valid.sale_year),{2024})
        self.assertEqual(self.temporal['bernoulli_training_prior'],0.55)
        records=pd.DataFrame(self.temporal['predictions'])
        e.validate_predictions(records,valid,e.ORDER[:2]+list(self.models))
        np.testing.assert_array_equal(records[records.model_name.eq('bernoulli_baseline')].predicted_probability,np.full(100,0.55))
        for name,profile in self.temporal['preprocessing'].items():
            np.testing.assert_array_equal(profile['imputation_statistics'],e.numeric_predictors(train).median().to_numpy())
            self.assertEqual(profile['training_rows'],100);self.assertEqual(profile['training_years'],[2023])
            if name=='logistic_regression':
                imputed=e.numeric_predictors(train).fillna(e.numeric_predictors(train).median()).to_numpy()
                np.testing.assert_allclose(profile['scaler_mean'],imputed.mean(axis=0),rtol=1e-14)
                self.assertEqual(profile['scaler_samples'],100)

    def test_coverage_isolation_feature_classification_and_training_only_statistics(self):
        before=e.fitted_parameters(self.models)
        coverage=e.coverage_diagnostic(self.train,self.valid,self.baselines)
        self.assertEqual(e.fitted_parameters(self.models),before)
        self.assertEqual(coverage,self.coverage)
        self.assertEqual(coverage['feature_subset'],['prior_price_record_count','days_since_last_price_record','has_prior_price_history'])
        self.assertFalse(set(coverage['excluded_discount_behavior_features'])&set(coverage['feature_subset']))
        self.assertTrue(coverage['diagnostic_isolated_from_primary'])
        self.assertEqual(coverage['metrics']['models']['logistic_regression'],self.baseline_metrics['models']['logistic_regression'])
        X=e.numeric_predictors(self.train,e.COVERAGE_FEATURES,diagnostic=True)
        np.testing.assert_array_equal(coverage['preprocessing']['imputation_statistics'],X.median().to_numpy())
        np.testing.assert_allclose(coverage['preprocessing']['scaler_mean'],X.fillna(X.median()).to_numpy().mean(axis=0),rtol=1e-14)
        self.assertEqual(coverage['preprocessing']['scaler_samples'],200)
        altered=self.valid.copy();altered[b.TARGET]=1-altered[b.TARGET]
        changed=e.coverage_diagnostic(self.train,altered,self.baselines.assign(actual_label=1-self.baselines.actual_label))
        self.assertEqual(coverage['fitted_parameters'],changed['fitted_parameters'])
        self.assertEqual(coverage['preprocessing'],changed['preprocessing'])

    def test_native_and_permutation_importance_names_definitions_and_data(self):
        for name,info in self.importance['models'].items():
            self.assertEqual(info['features'],b.APPROVED)
            self.assertEqual(info['scoring'],'roc_auc');self.assertEqual(info['n_repeats'],20);self.assertEqual(info['random_seed'],42)
            values=np.asarray(info['permutation_repeats'])
            self.assertEqual(values.shape,(15,20))
            np.testing.assert_array_equal(values.mean(axis=1),info['permutation_mean'])
            np.testing.assert_array_equal(values.std(axis=1),info['permutation_std'])
            np.testing.assert_array_equal(info['native_importance'],self.models[name].named_steps['classifier'].feature_importances_)

    def test_figures_use_actual_prediction_metrics_curves_histograms_and_confusions(self):
        for name,f in self.combined.groupby('model_name'):
            c=self.data['curves'][name];fpr,tpr,_=skmetrics.roc_curve(f.actual_label,f.predicted_probability,drop_intermediate=False)
            precision,recall,_=skmetrics.precision_recall_curve(f.actual_label,f.predicted_probability)
            for key,value in [('fpr',fpr),('tpr',tpr),('precision',precision),('recall',recall)]:np.testing.assert_array_equal(c[key],value)
            for key in e.METRIC_DIRECTIONS:self.assertEqual(self.data['metric_values'][name][key],self.metrics['models'][name][key])
            self.assertEqual(self.data['confusion_matrices'][name],self.metrics['models'][name]['confusion_matrix'])
            np.testing.assert_array_equal(self.data['histograms'][name]['positive'],f.loc[f.actual_label.eq(1),'predicted_probability'])
            np.testing.assert_array_equal(self.data['histograms'][name]['negative'],f.loc[f.actual_label.eq(0),'predicted_probability'])
        self.assertEqual(self.data['temporal_values']['random_forest'],[self.temporal['metrics']['models']['random_forest']['roc_auc'],self.metrics['models']['random_forest']['roc_auc']])
        self.assertEqual(self.data['coverage_metrics'],self.coverage['metrics']['models'])

    def test_adversarial_plot_receipt_tracks_changed_saved_predictions(self):
        changed=self.combined.copy();mask=changed.model_name.eq('random_forest')
        changed.loc[mask,'predicted_probability']=np.linspace(0.01,0.99,100)
        changed.loc[mask,'predicted_class']=b.classes(changed.loc[mask,'predicted_probability'])
        changed.loc[mask,'actual_label']=1-changed.loc[mask,'actual_label']
        metrics=b.evaluate(changed)
        data=e.plot_data(changed,metrics,self.temporal,self.coverage,self.importance)
        for key in ['curves','metric_values','histograms','confusion_matrices']:
            self.assertNotEqual(data[key]['random_forest'],self.data[key]['random_forest'])
        with self.assertRaisesRegex(ValueError,'Plot metrics'):e.plot_data(changed,self.metrics,self.temporal,self.coverage,self.importance)
        with tempfile.TemporaryDirectory() as directory,patch.object(b,'evaluate',side_effect=AssertionError('renderer recomputes metrics')):
            status=e.generate_figures(Path(directory),data)
            self.assertEqual(sum(v['status']=='generated' for v in status.values()),10 if e.XGBClassifier is None else 11)
            if e.XGBClassifier is None:self.assertEqual(status['xgboost_feature_importance']['status'],'unavailable')

    def test_light_style_300dpi_white_backgrounds(self):
        with e.light_style():
            for setting in ['figure.facecolor','axes.facecolor','savefig.facecolor']:self.assertEqual(e.plt.rcParams[setting],'white')
            self.assertEqual(e.plt.rcParams['savefig.dpi'],300)
            self.assertFalse(e.plt.rcParams['axes.spines.top']);self.assertFalse(e.plt.rcParams['axes.spines.right'])

    def test_offline_guard_blocks_network(self):
        with self.assertRaisesRegex(AssertionError,'Network forbidden'):
            with b.offline_guard():socket.create_connection(('example.invalid',443))

    def test_inconsistent_baseline_predictions_metrics_or_artifact_stop(self):
        inventory=e.protected_hashes(ROOT)
        for changed_file in [b.PREDICTIONS,b.METRICS,b.MODEL_PATHS['logistic_regression']]:
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory)
                for relative in inventory:
                    dest=root/relative;dest.parent.mkdir(parents=True,exist_ok=True)
                    if relative==changed_file:dest.write_bytes((ROOT/relative).read_bytes())
                    else:dest.symlink_to(ROOT/relative)
                if changed_file==b.PREDICTIONS:
                    frame=pd.read_csv(root/changed_file,float_precision='round_trip');frame.loc[0,'appid']=1;frame.to_csv(root/changed_file,index=False)
                elif changed_file==b.METRICS:
                    metrics=json.loads((root/changed_file).read_text());metrics['models']['logistic_regression']['roc_auc']=0.123
                    (root/changed_file).write_text(json.dumps(metrics))
                else:(root/changed_file).write_bytes(b'not a trusted model')
                with self.assertRaises(ValueError):e.load_baselines(root,self.valid)

    def test_protected_snapshot_detects_any_baseline_artifact_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for relative in e.protected_hashes(ROOT):
                dest=root/relative;dest.parent.mkdir(parents=True,exist_ok=True);dest.symlink_to(ROOT/relative)
            (root/e.INTEGRITY).write_text(json.dumps(dict(protected_sha256={'bad':'0'*64})))
            with self.assertRaisesRegex(ValueError,'snapshot'):e.protected_hashes(root)

    def test_no_phase8_population_expansion_or_future_predictions(self):
        self.assertEqual(set(self.predictions.sale_year),{2025})
        self.assertEqual(set(pd.DataFrame(self.temporal['predictions']).sale_year),{2024})
        self.assertEqual(set(pd.DataFrame(self.coverage['predictions']).sale_year),{2025})
        self.assertEqual(self.valid.appid.nunique(),100)
        self.assertTrue(all('2026' not in p and 'phase8' not in p.lower() for p in e.STRUCTURED))
        tree=ast.parse((ROOT/'src/09_train_ensemble_models.py').read_text())
        fit_calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='fit']
        self.assertTrue(all(not n.keywords for n in fit_calls))
        self.assertNotIn('train_test_split',(ROOT/'src/09_train_ensemble_models.py').read_text())

    def test_full_pipeline_twice_integrity_reload_saved_plot_data_and_determinism(self):
        before=e.protected_hashes(ROOT)
        with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as c,b.offline_guard():
            first=e.run(ROOT,Path(a));second=e.run(ROOT,Path(c))
            pd.testing.assert_frame_equal(first[0],second[0],check_exact=True);self.assertEqual(first[1:],second[1:])
            for path in first[3]['output_sha256']:
                self.assertEqual(b.digest(Path(a)/path),b.digest(Path(c)/path),path)
                self.assertEqual(b.digest(Path(a)/path),first[3]['output_sha256'][path])
            self.assertEqual(b.digest(Path(a)/e.VALIDATION),b.digest(Path(c)/e.VALIDATION))
            predictions=pd.read_csv(Path(a)/e.COMBINED,float_precision='round_trip')
            pd.testing.assert_frame_equal(predictions,first[0],check_exact=True)
            data=json.loads((Path(a)/e.PLOT_DATA).read_text())
            self.assertEqual(data['metric_values']['random_forest']['roc_auc'],skmetrics.roc_auc_score(predictions[predictions.model_name.eq('random_forest')].actual_label,predictions[predictions.model_name.eq('random_forest')].predicted_probability))
            self.assertEqual(first[3]['protected_before_sha256'],before);self.assertEqual(first[3]['protected_after_sha256'],before)
            self.assertEqual(first[3]['network_attempts'],0)
            self.assertTrue(all(v['probabilities_identical'] for v in first[3]['artifact_reload'].values()))
            if e.XGBClassifier is None:
                self.assertFalse((Path(a)/e.MODEL_PATHS['xgboost']).exists())
                self.assertFalse((Path(a)/'reports/figures/xgboost_feature_importance.png').exists())
                self.assertEqual(len(predictions),300)
        self.assertEqual(before,e.protected_hashes(ROOT))


if __name__=='__main__':unittest.main()
