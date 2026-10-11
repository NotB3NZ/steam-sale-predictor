"""Phase 7A offline tests, including synthetic leakage and plotting adversaries."""
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
from scipy.special import expit
from sklearn import metrics as skmetrics

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('baseline_models', ROOT / 'src/08_train_baseline_models.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


class BaselineModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with b.offline_guard():
            cls.frame, cls.manifest, cls.inspection = b.inspect_inputs()
            cls.train, cls.valid = b.chronological_split(cls.frame)
            cls.models, cls.preprocessing = b.fit_models(cls.train)
            cls.predictions = b.predict(cls.models,cls.valid)
            cls.metrics = b.evaluate(cls.predictions)
            cls.data = b.build_plot_data(cls.predictions,cls.models,cls.metrics)

    def test_chronological_split(self):
        self.assertEqual(set(self.train.sale_year),{2023,2024})
        self.assertEqual(set(self.valid.sale_year),{2025})
        self.assertLess(self.train.sale_year.max(),self.valid.sale_year.min())
        self.assertEqual(set(self.train.appid),set(self.valid.appid))

    def test_exact_row_counts(self):
        self.assertEqual(len(self.frame),300)
        self.assertEqual(len(self.train),200)
        self.assertEqual(len(self.valid),100)
        self.assertEqual(self.train.groupby('sale_year').size().to_dict(),{2023:100,2024:100})

    def test_target_counts(self):
        self.assertEqual(self.train[b.TARGET].value_counts().to_dict(),{1:115,0:85})
        self.assertEqual(self.valid[b.TARGET].value_counts().to_dict(),{1:60,0:40})

    def test_exact_allowlist_matches_phase6_builder_and_manifest(self):
        spec = importlib.util.spec_from_file_location('baseline_phase6',ROOT/'src/07_build_autumn_features.py')
        phase6 = importlib.util.module_from_spec(spec); spec.loader.exec_module(phase6)
        self.assertEqual(b.APPROVED,list(phase6.ALLOWLIST))
        self.assertEqual(b.APPROVED,self.manifest['baseline_feature_allowlist'])
        self.assertEqual(b.select_predictors(self.frame).columns.tolist(),b.APPROVED)
        self.assertEqual(self.models['logistic_regression'][:-1].get_feature_names_out().tolist(),b.APPROVED)

    def test_identifiers_target_audit_fields_excluded(self):
        self.assertFalse(b.PROHIBITED & set(b.select_predictors(self.frame).columns))
        self.assertFalse(b.PROHIBITED & set(self.preprocessing['transformed_feature_names']))

    def test_manifest_disagreement_stops(self):
        for key,value in [('baseline_feature_allowlist',b.APPROVED+['appid']),('target_column','pu_status')]:
            altered=copy.deepcopy(self.manifest); altered[key]=value
            with self.assertRaises(ValueError): b.validate_manifest(altered)
        altered=copy.deepcopy(self.manifest); altered['features'][0]['baseline_allowlist']=True
        with self.assertRaises(ValueError): b.validate_manifest(altered)

    def test_source_schema_disagreement_stops_without_repair(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for path in [b.FEATURE_MANIFEST,b.TABLE,b.FEATURES]:
                dest=root/path; dest.parent.mkdir(parents=True,exist_ok=True)
                dest.write_bytes((ROOT/path).read_bytes())
            frame=b.read_csv(root/b.TABLE).drop(columns='release_month')
            frame.to_csv(root/b.TABLE,index=False)
            snapshot=(root/b.TABLE).read_bytes()
            with self.assertRaisesRegex(ValueError,'schema disagreement'): b.inspect_inputs(root)
            self.assertEqual(snapshot,(root/b.TABLE).read_bytes())

    def test_validated_numeric_types_binary_and_training_missingness(self):
        X=b.select_predictors(self.frame)
        self.assertTrue(all(pd.api.types.is_numeric_dtype(X[f]) for f in b.APPROVED))
        for f in b.BINARY: self.assertEqual(set(X[f]),{0,1})
        bad=self.train.copy(); bad['game_age_days']=bad.game_age_days.astype(object); bad.loc[0,'game_age_days']='invalid'
        with self.assertRaises(ValueError): b.select_predictors(bad)
        bad=self.train.copy(); bad['game_age_days']=bad.game_age_days.astype(float); bad.loc[0,'game_age_days']=np.inf
        with self.assertRaises(ValueError): b.select_predictors(bad)
        self.assertEqual(self.inspection['training_all_missing_features'],[])
        self.assertEqual(self.inspection['training_constant_features'],[])

    def test_missingness_covered_by_existing_flags(self):
        for f in ['prior_discount_rate','days_since_last_price_record','last_observed_price','last_observed_discount_pct']:
            np.testing.assert_array_equal(self.frame[f].isna(),self.frame.has_prior_price_history.eq(0))
        for f in ['days_since_last_discount','max_prior_discount_pct','mean_prior_discount_pct']:
            np.testing.assert_array_equal(self.frame[f].isna(),self.frame.has_prior_discount_observation.eq(0))
        self.assertEqual(self.preprocessing['additional_missingness_indicators'],[])

    def test_all_missing_training_exclusion_rule(self):
        synthetic=self.train.copy(); synthetic['last_observed_price']=np.nan
        models,prep=b.fit_models(synthetic)
        self.assertEqual(prep['excluded_all_missing_training_features'],['last_observed_price'])
        self.assertNotIn('last_observed_price',prep['transformed_feature_names'])
        self.assertEqual(len(prep['transformed_feature_names']),14)
        b.predict(models,self.valid)

    def test_constant_training_column_retained(self):
        synthetic=self.train.copy(); synthetic['release_month']=3
        models,prep=b.fit_models(synthetic)
        self.assertIn('release_month',prep['retained_constant_training_features'])
        self.assertEqual(prep['scaler_scale'][b.APPROVED.index('release_month')],1)

    def test_fitting_rejects_validation_future_rows(self):
        for frame in [self.frame,self.valid,self.train.assign(sale_year=2026)]:
            with self.assertRaisesRegex(ValueError,'only 2023'): b.fit_models(frame)
        with self.assertRaises(ValueError): b.chronological_split(self.frame.assign(sale_year=2026))
        self.assertEqual(self.inspection['phase6_cutoff_violations'],0)

    def test_no_validation_leakage_in_imputation(self):
        p=self.models['logistic_regression']
        expected=b.select_predictors(self.train).median().to_numpy()
        np.testing.assert_array_equal(p.named_steps['impute'].statistics_,expected)
        combined=b.select_predictors(self.frame).median().to_numpy()
        self.assertFalse(np.array_equal(expected,combined))

    def test_no_validation_leakage_in_scaling(self):
        p=self.models['logistic_regression']
        X=b.select_predictors(self.train)
        imputed=X.fillna(X.median()).to_numpy()
        np.testing.assert_allclose(p.named_steps['scale'].mean_,imputed.mean(axis=0),rtol=1e-14)
        np.testing.assert_allclose(p.named_steps['scale'].var_,imputed.var(axis=0),rtol=1e-14)
        self.assertEqual(p.named_steps['scale'].n_samples_seen_,200)

    def test_adversarial_validation_label_changes_do_not_change_fit_or_probabilities(self):
        altered=self.frame.copy()
        altered.loc[altered.sale_year.eq(2025),b.TARGET]=1-altered.loc[altered.sale_year.eq(2025),b.TARGET]
        train,valid=b.chronological_split(altered); models,prep=b.fit_models(train)
        self.assertEqual(b.model_parameters(models),b.model_parameters(self.models))
        self.assertEqual(prep,self.preprocessing)
        predicted=b.predict(models,valid)
        np.testing.assert_array_equal(predicted.predicted_probability,self.predictions.predicted_probability)
        self.assertFalse(np.array_equal(predicted.actual_label,self.predictions.actual_label))

    def test_adversarial_validation_features_do_not_change_preprocessing(self):
        altered=self.frame.copy(); mask=altered.sale_year.eq(2025)
        for f in b.APPROVED: altered.loc[mask,f]=1e6
        train,valid=b.chronological_split(altered); models,prep=b.fit_models(train)
        self.assertEqual(prep,self.preprocessing)
        self.assertEqual(b.model_parameters(models),b.model_parameters(self.models))
        b.predict(models,valid)

    def test_adversarial_prohibited_columns_cannot_enter_predictors(self):
        altered=self.frame.copy()
        for column in ['evidence_category','pu_status','audit_release_hour_uncertain','future_price','current_sale_outcome','contemporary_reviews']:
            altered[column]=np.arange(len(altered))
        altered[b.TARGET]=1-altered[b.TARGET]
        pd.testing.assert_frame_equal(b.select_predictors(altered),b.select_predictors(self.frame))
        X=b.select_predictors(self.valid)
        p=self.models['logistic_regression']
        direct=self.valid.copy(); direct['evidence_category']=np.arange(100); direct[b.TARGET]=999
        np.testing.assert_array_equal(p.predict_proba(X),p.predict_proba(direct))
        with self.assertRaises(ValueError): b.select_predictors(altered,b.APPROVED+[b.TARGET])

    def test_row_order_preserves_game_year_prediction_associations(self):
        shuffled=self.frame.sample(frac=1,random_state=3)
        train,valid=b.chronological_split(shuffled); models,_=b.fit_models(train)
        result=b.predict(models,valid.sample(frac=1,random_state=9))
        pd.testing.assert_frame_equal(result,self.predictions,check_exact=True)

    def test_bernoulli_prior_constant_probability(self):
        prior=self.models['bernoulli_baseline']
        np.testing.assert_array_equal(prior.class_prior_,[0.425,0.575])
        p=self.predictions[self.predictions.model_name.eq('bernoulli_baseline')]
        np.testing.assert_array_equal(p.predicted_probability,np.full(100,0.575))
        self.assertTrue(p.decision_score.isna().all())
        self.assertEqual(prior.strategy,'prior')

    def test_logistic_configuration_and_complete_pipeline(self):
        p=self.models['logistic_regression']
        self.assertEqual(list(p.named_steps),['select','impute','scale','classifier'])
        for key,value in b.LOGISTIC_PARAMS.items(): self.assertEqual(p.named_steps['classifier'].get_params()[key],value)

    def test_logistic_probability_range_and_sigmoid(self):
        p=self.predictions[self.predictions.model_name.eq('logistic_regression')]
        self.assertTrue(np.isfinite(p.predicted_probability).all())
        self.assertTrue(p.predicted_probability.between(0,1).all())
        np.testing.assert_allclose(expit(p.decision_score),p.predicted_probability,atol=1e-14,rtol=1e-12)
        self.assertTrue(np.isfinite(expit([-10000,10000])).all())

    def test_fixed_threshold_inclusive_boundary(self):
        np.testing.assert_array_equal(b.classes([0,0.49999,0.5,0.50001,1]),[0,0,1,1,1])
        np.testing.assert_array_equal(self.predictions.predicted_class,b.classes(self.predictions.predicted_probability))

    def test_metrics_match_independent_sklearn_calculations(self):
        for name,f in self.predictions.groupby('model_name'):
            m=self.metrics['models'][name]; y=f.actual_label; p=f.predicted_probability; c=f.predicted_class
            expected={'roc_auc':skmetrics.roc_auc_score(y,p),'average_precision':skmetrics.average_precision_score(y,p),
                'brier_score':skmetrics.brier_score_loss(y,p),'log_loss':skmetrics.log_loss(y,p),
                'accuracy':skmetrics.accuracy_score(y,c),'precision':skmetrics.precision_score(y,c),
                'recall':skmetrics.recall_score(y,c),'f1':skmetrics.f1_score(y,c)}
            for key,value in expected.items(): self.assertAlmostEqual(m[key],value,places=14)
        prior=self.metrics['models']['bernoulli_baseline']
        self.assertEqual(prior['roc_auc'],0.5); self.assertEqual(prior['average_precision'],0.6)
        self.assertAlmostEqual(prior['brier_score'],0.6*0.425**2+0.4*0.575**2)

    def test_undefined_metrics_explicit_null_reasons(self):
        synthetic=self.predictions.copy(); synthetic['actual_label']=0; synthetic['predicted_class']=0
        m=b.evaluate(synthetic)
        for model in m['models'].values():
            self.assertIsNone(model['precision']); self.assertIsNone(model['recall'])
            self.assertIsNone(model['f1']); self.assertIsNone(model['roc_auc']); self.assertIsNone(model['average_precision'])
            self.assertIn('precision',model['undefined_metrics'])
            json.dumps(m,allow_nan=False)

    def test_confusion_orientation(self):
        for name,f in self.predictions.groupby('model_name'):
            counts=[[int(((f.actual_label==a)&(f.predicted_class==c)).sum()) for c in [0,1]] for a in [0,1]]
            self.assertEqual(counts,self.metrics['models'][name]['confusion_matrix'])
        self.assertEqual(self.metrics['models']['bernoulli_baseline']['confusion_matrix'],[[0,40],[0,60]])

    def test_prediction_uniqueness_and_counts(self):
        self.assertEqual(len(self.predictions),200)
        self.assertFalse(self.predictions.duplicated(b.KEYS+['model_name']).any())
        self.assertEqual(self.predictions.groupby('model_name').size().to_dict(),{name:100 for name in b.MODEL_PATHS})
        self.assertEqual(self.predictions.columns.tolist(),b.KEYS+['model_name','actual_label','predicted_probability','predicted_class','decision_score'])
        duplicated=pd.concat([self.frame,self.frame.iloc[:1]])
        with self.assertRaisesRegex(ValueError,'Duplicate'): b.chronological_split(duplicated)

    def test_model_serialization_identical_predictions(self):
        with tempfile.TemporaryDirectory() as temp:
            for name,model in self.models.items():
                path=Path(temp)/(name+'.joblib'); joblib.dump(model,path); loaded=joblib.load(path)
                X=np.zeros((100,1)) if name=='bernoulli_baseline' else b.select_predictors(self.valid)
                np.testing.assert_array_equal(model.predict_proba(X),loaded.predict_proba(X))
                if name=='logistic_regression':
                    np.testing.assert_array_equal(model.decision_function(X),loaded.decision_function(X))
                    self.assertEqual(list(loaded.named_steps),['select','impute','scale','classifier'])

    def test_deterministic_repeat_fitting_and_predictions(self):
        models,prep=b.fit_models(self.train)
        self.assertEqual(prep,self.preprocessing)
        self.assertEqual(b.model_parameters(models),b.model_parameters(self.models))
        pd.testing.assert_frame_equal(b.predict(models,self.valid),self.predictions,check_exact=True)
        self.assertEqual(b.evaluate(b.predict(models,self.valid)),self.metrics)

    def test_all_plot_data_use_actual_predictions_parameters_metrics(self):
        logistic=self.predictions[self.predictions.model_name.eq('logistic_regression')]
        np.testing.assert_array_equal(self.data['sigmoid']['scores'],logistic.decision_score)
        np.testing.assert_array_equal(self.data['sigmoid']['probabilities'],logistic.predicted_probability)
        np.testing.assert_array_equal(self.data['sigmoid']['appids'],logistic.appid)
        np.testing.assert_array_equal(self.data['coefficients']['values'],self.models['logistic_regression'].named_steps['classifier'].coef_[0])
        self.assertEqual(self.data['coefficients']['names'],self.preprocessing['transformed_feature_names'])
        self.assertEqual(self.data['confusion_matrix'],self.metrics['models']['logistic_regression']['confusion_matrix'])
        for name,f in self.predictions.groupby('model_name'):
            fpr,tpr,_=skmetrics.roc_curve(f.actual_label,f.predicted_probability,drop_intermediate=False)
            precision,recall,_=skmetrics.precision_recall_curve(f.actual_label,f.predicted_probability)
            curve=self.data['curves'][name]
            for key,value in [('fpr',fpr),('tpr',tpr),('precision',precision),('recall',recall)]:
                np.testing.assert_array_equal(curve[key],value)
            self.assertEqual(curve['auc'],self.metrics['models'][name]['roc_auc'])
            self.assertEqual(curve['ap'],self.metrics['models'][name]['average_precision'])
        np.testing.assert_array_equal(self.data['histogram']['positive'],logistic.loc[logistic.actual_label.eq(1),'predicted_probability'])
        np.testing.assert_array_equal(self.data['histogram']['negative'],logistic.loc[logistic.actual_label.eq(0),'predicted_probability'])

    def test_adversarial_plot_data_changes_with_actual_prediction_outputs(self):
        altered=self.predictions.copy(); mask=altered.model_name.eq('logistic_regression')
        altered.loc[mask,'predicted_probability']=np.linspace(0.01,0.99,100)
        altered.loc[mask,'decision_score']=np.log(altered.loc[mask,'predicted_probability']/(1-altered.loc[mask,'predicted_probability']))
        altered['predicted_class']=b.classes(altered.predicted_probability)
        altered.loc[mask,'actual_label']=1-altered.loc[mask,'actual_label']
        data=b.build_plot_data(altered,self.models,b.evaluate(altered))
        for key in ['sigmoid','confusion_matrix','curves','histogram','reliability']:
            self.assertNotEqual(data[key],self.data[key])
        self.assertEqual(data['coefficients'],self.data['coefficients'])
        # Figure renderer is driven solely by supplied data, with no hidden evaluation access.
        with tempfile.TemporaryDirectory() as temp, patch.object(b,'evaluate',side_effect=AssertionError('hidden metric evaluation')), \
             patch.object(b,'predict',side_effect=AssertionError('hidden predictions')):
            output=b.generate_figures(Path(temp),data)
            self.assertEqual(len(output),8)

    def test_reliability_counts_and_empty_bin_omission(self):
        self.assertEqual(sum(row['count'] for row in self.data['reliability']),100)
        logistic=self.predictions[self.predictions.model_name.eq('logistic_regression')]
        for row in self.data['reliability']:
            mask=(logistic.predicted_probability>=row['bin_left']) & ((logistic.predicted_probability<row['bin_right']) if row['bin_right']<1 else (logistic.predicted_probability<=1))
            f=logistic[mask]
            self.assertEqual(len(f),row['count']); self.assertGreater(len(f),0)
            self.assertAlmostEqual(f.actual_label.mean(),row['positive_fraction'])
            self.assertAlmostEqual(f.predicted_probability.mean(),row['mean_probability'])
        synthetic=self.predictions.copy(); synthetic['predicted_probability']=0.5
        data=b.build_plot_data(synthetic,self.models,b.evaluate(synthetic))
        self.assertEqual(len(data['reliability']),1); self.assertEqual(data['reliability'][0]['count'],100)

    def test_plot_light_mode_and_export_settings(self):
        with b.light_style():
            self.assertEqual(b.plt.rcParams['figure.facecolor'],'white')
            self.assertEqual(b.plt.rcParams['axes.facecolor'],'white')
            self.assertEqual(b.plt.rcParams['savefig.facecolor'],'white')
            self.assertEqual(b.plt.rcParams['savefig.dpi'],300)
            self.assertFalse(b.plt.rcParams['axes.spines.top']); self.assertFalse(b.plt.rcParams['axes.spines.right'])

    def test_offline_guard_blocks_network(self):
        for call in [lambda:socket.getaddrinfo('example.invalid',443),lambda:socket.create_connection(('example.invalid',443))]:
            with self.assertRaisesRegex(AssertionError,'Network forbidden'):
                with b.offline_guard(): call()

    def test_protected_input_mutation_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); (root/'reports').mkdir(); (root/'input.csv').write_text('changed')
            (root/b.PHASE6_RECEIPT).write_text(json.dumps(dict(protected_after_sha256={'input.csv':'0'*64},source_sha256={},output_sha256={})))
            with self.assertRaisesRegex(ValueError,'Protected input changed'): b.protected_hashes(root)

    def test_complete_run_offline_protected_integrity_and_deterministic_content(self):
        before=b.protected_hashes(ROOT)
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as c, b.offline_guard():
            first=b.run(ROOT,Path(a)); second=b.run(ROOT,Path(c))
            pd.testing.assert_frame_equal(first[0],second[0],check_exact=True)
            self.assertEqual(first[1:],second[1:])
            for path in b.OUTPUTS:
                self.assertEqual(b.digest(Path(a)/path),b.digest(Path(c)/path),path)
            receipt=first[3]
            self.assertEqual(receipt['protected_before_sha256'],receipt['protected_after_sha256'])
            self.assertEqual(receipt['network_attempts'],0)
            self.assertTrue(all(v['probabilities_identical'] for v in receipt['artifact_reload_checks'].values()))
            loaded=pd.read_csv(Path(a)/b.PREDICTIONS,float_precision='round_trip')
            np.testing.assert_array_equal(loaded.predicted_probability,first[0].predicted_probability)
        self.assertEqual(before,b.protected_hashes(ROOT))


if __name__=='__main__':
    unittest.main()
