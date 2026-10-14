"""Pure saved-output diagnostics and plot tests; no model fitting/prediction."""
import copy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import visualize_cohort_models as v


class VisualizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core=v.temporal.cores()
        cls.pred=cls.core.pd.DataFrame([dict(appid=i+1,sale_year=2025,model_name='xgboost',actual_label=y,
                       predicted_probability=p,predicted_class=int(p>=.5),decision_score=float('nan'),
                       prior_price_record_count=count) for i,(count,y,p) in enumerate(
                       [(0,0,.05),(2,0,.1),(3,1,.8),(10,1,.3),(20,0,.6),(30,1,.9),(40,0,.1)])])

    def test_coverage_bins_partition_and_show_sample_class_error_counts(self):
        with v.frozen_model_guard(self.core):rows=v.coverage_summary(self.pred,self.core)
        self.assertEqual([r['observations'] for r in rows],[1,2,2,2])
        self.assertEqual(sum(r['actual_positive'] for r in rows),3)
        self.assertEqual(sum(r['fp'] for r in rows),1)
        self.assertEqual(sum(r['fn'] for r in rows),1)

    def test_single_class_and_no_predicted_positive_are_not_zero_metrics(self):
        row=v.coverage_summary(self.pred,self.core)[0]
        self.assertIsNone(row['balanced_accuracy'])
        self.assertIsNone(row['precision'])
        self.assertIsNone(row['recall'])
        self.assertIsNone(row['average_precision'])
        self.assertEqual(row['accuracy'],1)

    def test_duplicate_or_negative_coverage_is_rejected(self):
        for bad in (self.core.pd.concat([self.pred,self.pred.head(1)]),self.pred.assign(prior_price_record_count=-1)):
            with self.assertRaises(ValueError):v.coverage_summary(bad,self.core)

    def test_saved_metric_verification_detects_mismatch(self):
        actual=v.temporal.evaluate(self.pred,self.core)
        expected=copy.deepcopy(actual)
        v.assert_metrics(actual,expected,self.core)
        expected['models']['xgboost']['accuracy']+=.01
        with self.assertRaises(AssertionError):v.assert_metrics(actual,expected,self.core)

    def test_gain_is_normalized_average_gain_with_unused_features_zero(self):
        values=self.core.np.zeros(15);values[:2]=[2/3,1/3]
        estimator=SimpleNamespace(get_booster=lambda:SimpleNamespace(get_score=lambda importance_type:{'f0':2.,'f1':1.}),feature_importances_=values)
        class Model:
            named_steps={'classifier':estimator}
            def __getitem__(self,key):return SimpleNamespace(get_feature_names_out=lambda:self.core.b.APPROVED)
        model=Model();model.core=self.core
        rows=v.native_importance(model,self.core)
        self.assertAlmostEqual(sum(r['normalized_average_split_gain'] for r in rows),1)
        self.assertEqual(rows[2]['normalized_average_split_gain'],0)

    def test_no_fit_and_no_new_predictions_guard(self):
        with v.frozen_model_guard(self.core):
            for cls,method in ((self.core.b.LogisticRegression,'fit'),(self.core.b.DummyClassifier,'predict_proba')):
                with self.assertRaisesRegex(AssertionError,'Frozen diagnostics'):
                    getattr(cls(),method)([[0],[1]],[0,1])

    def test_caption_labels_include_sample_and_both_classes(self):
        labels=v.coverage_labels(v.coverage_summary(self.pred,self.core))
        self.assertIn('n=1; 1:0 / 0:1',labels[0])

    def test_csv_null_is_blank_and_real_zero_stays_zero(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'table.csv';v.write_csv(path,[dict(undefined=None,observed_zero=0)])
            from cohort_io import read_csv
            self.assertEqual(read_csv(path),[{'undefined':'','observed_zero':'0'}])

    def test_already_annotated_predictions_reuse_helper_without_duplicate_coverage_columns(self):
        frame=self.pred[['appid','sale_year']].copy()
        for feature in self.core.b.APPROVED:frame[feature]=1.
        frame['prior_price_record_count']=self.pred.prior_price_record_count
        frame['has_prior_price_history']=frame.prior_price_record_count.gt(0).astype(int)
        frame['has_prior_discount_observation']=1
        with v.frozen_model_guard(self.core):
            result=v.saved_diagnostics(self.pred,frame,self.core)
        self.assertEqual(sum(r['observations'] for r in result['calibration_bins']),len(self.pred))


if __name__=='__main__':unittest.main()
