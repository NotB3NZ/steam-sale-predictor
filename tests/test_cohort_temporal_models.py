"""Offline cohort model regressions; fitting uses synthetic observations only."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import train_cohort_temporal as runner


class TemporalModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core=runner.cores()
        rows=[]
        for year in (2023,2024,2025):
            for appid in range(1,33):
                missing=appid%8==0
                row={f:float(appid) for f in cls.core.b.APPROVED}
                row.update(appid=appid,sale_year=year,discount_observed=appid%2,
                           prediction_cutoff_utc='audit only',evidence_category='A' if appid%2 else 'D',
                           audit_release_hour_uncertain=0,
                           prior_price_record_count=0 if missing else appid,
                           prior_discount_count=0 if missing else appid//2,
                           has_prior_price_history=int(not missing),has_prior_discount_observation=int(not missing))
                if missing:
                    for f in ('prior_discount_rate','days_since_last_price_record','days_since_last_discount',
                              'max_prior_discount_pct','mean_prior_discount_pct','last_observed_price','last_observed_discount_pct'):
                        row[f]=None
                rows.append(row)
        cls.frame=cls.core.pd.DataFrame(rows)
        cls.parts=runner.chronological_parts(cls.frame)
        with cls.core.b.offline_guard():
            cls.models,_=cls.core.fit_models(cls.parts['development_training'],training_years=[2023],include_baselines=True,cohort_mode=True)
            cls.predictions=cls.core.predict(cls.models,cls.parts['development_validation'])
        cls.metrics=runner.evaluate(cls.predictions,cls.core)

    def test_temporal_parts_keep_all_games_and_future_changes_do_not_affect_training(self):
        altered=self.frame.copy()
        altered.loc[altered.sale_year.eq(2025),'discount_observed']=1
        altered.loc[altered.sale_year.eq(2025),'last_observed_price']=999999
        parts=runner.chronological_parts(altered)
        for name in ('development_training','development_validation','final_training'):
            self.core.pd.testing.assert_frame_equal(parts[name],self.parts[name])
        self.assertEqual(len(parts['final_training']),64)
        self.assertEqual(len(parts['held_out_test']),32)
        self.assertEqual(set(parts['final_training'].appid),set(parts['held_out_test'].appid))

    def test_duplicate_keys_and_wrong_years_are_rejected(self):
        for bad in (self.core.pd.concat([self.frame,self.frame.head(1)]),self.frame.assign(sale_year=2026)):
            with self.assertRaises(ValueError): runner.chronological_parts(bad)

    def test_exact_allowlist_excludes_numeric_target_and_metadata(self):
        X=self.core.numeric_predictors(self.frame)
        self.assertEqual(list(X),self.core.b.APPROVED)
        self.assertEqual(len(X.columns),15)
        self.assertFalse(set(['appid','sale_year','discount_observed','audit_release_hour_uncertain'])&set(X))

    def test_preprocessing_matches_training_only_medians_and_scaler(self):
        profiles=runner.verify_preprocessing(self.models,self.parts['development_training'],self.core)
        self.assertEqual(profiles['logistic_regression']['training_rows'],32)
        altered=self.parts['development_validation'].copy()
        altered['last_observed_price']=999999
        for model in self.models.values():
            if hasattr(model,'named_steps'):
                before=model.named_steps['impute'].statistics_.copy()
                model.predict_proba(self.core.numeric_predictors(altered))
                self.core.np.testing.assert_array_equal(before,model.named_steps['impute'].statistics_)

    def test_all_missing_training_column_stops_instead_of_silent_zero_policy(self):
        bad=self.parts['development_training'].copy()
        bad['last_observed_price']=self.core.np.nan
        with self.assertRaisesRegex(ValueError,'All-missing'):
            runner.verify_preprocessing(self.models,bad,self.core)

    def test_selection_uses_development_ap_then_brier_then_fixed_order(self):
        values={'models':{name:dict(average_precision=.8,brier_score=.2) for name in runner.ORDER}}
        self.assertEqual(runner.choose_model(values)['selected_model'],'bernoulli_baseline')
        values['models']['random_forest']['brier_score']=.1
        self.assertEqual(runner.choose_model(values)['selected_model'],'random_forest')
        values['models']['logistic_regression']['average_precision']=.9
        self.assertEqual(runner.choose_model(values)['selected_model'],'logistic_regression')
        self.assertEqual(runner.choose_model(self.metrics),runner.choose_model(copy.deepcopy(self.metrics)))

    def test_requested_metrics_and_confusion_orientation(self):
        for name,row in self.metrics['models'].items():
            self.assertTrue(set(['accuracy','balanced_accuracy','precision','recall','f1','roc_auc','pr_auc','brier_score','confusion_matrix'])<=set(row))
            self.assertEqual(row['pr_auc'],row['average_precision'])
            self.assertEqual(sum(map(sum,row['confusion_matrix'])),32)
            tn,fp=row['confusion_matrix'][0];fn,tp=row['confusion_matrix'][1]
            self.assertAlmostEqual(row['balanced_accuracy'],((tp/(tp+fn))+(tn/(tn+fp)))/2)

    def test_dummy_has_training_prior_probabilities_and_defined_ranking_metrics(self):
        dummy=self.predictions[self.predictions.model_name.eq('bernoulli_baseline')]
        self.assertTrue(dummy.predicted_probability.eq(.5).all())
        self.assertEqual(self.metrics['models']['bernoulli_baseline']['roc_auc'],.5)
        self.assertEqual(self.metrics['models']['bernoulli_baseline']['average_precision'],.5)

    def test_single_class_diagnostics_have_explicit_undefined_discrimination(self):
        subset=self.predictions[self.predictions.actual_label.eq(0)]
        result=runner.evaluate(subset,self.core)
        self.assertTrue(all(r['roc_auc'] is None and r['balanced_accuracy'] is None and r['average_precision'] is None
                            for r in result['models'].values()))

    def test_saved_pipelines_roundtrip_without_refitting(self):
        with tempfile.TemporaryDirectory() as temp:
            result=runner.save_models(self.models,Path(temp)/'models',self.parts['development_training'].head(8),self.core)
            self.assertTrue(all(row['reload_probability_identity_verified'] for row in result.values()))
            self.assertEqual(set(result),set(self.models))

    def test_calibration_bins_and_coverage_metrics_account_for_every_prediction(self):
        report=runner.diagnostics(self.predictions,self.parts['development_validation'],self.core)
        for name in self.models:
            bins=[r for r in report['calibration_bins'] if r['model']==name]
            self.assertEqual(sum(r['observations'] for r in bins),32)
            density=[r for r in report['coverage_rows'] if r['model']==name and r['family']=='price_observation_density']
            self.assertEqual(sum(r['observations'] for r in density),32)
            self.assertFalse(report['summary'][name]['calibration_fitted'])
        self.assertEqual(report['missingness']['last_observed_price'],4)


if __name__=='__main__': unittest.main()
