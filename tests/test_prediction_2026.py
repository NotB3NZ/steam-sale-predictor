"""Offline Phase 8B regressions: immutable inputs, fixture-only fitting, final payloads."""
import copy
import csv
import os
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import predict_cohort_2026 as p


class PredictionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core=p.temporal.cores()
        cls.selection=p.read_json(p.ROOT/'reports/cohort_2000_models/selection.json')
        cls.protocol=p.read_json(p.ROOT/'reports/cohort_2000_2026_feasibility/final_refit_prediction_protocol.json')

    def fixture(self):
        rows=[]
        for year in (2023,2024,2025):
            for appid in range(1,13):
                row={f:float(appid) for f in p.FEATURES.ALLOWLIST}
                row.update(appid=appid,sale_year=year,discount_observed=appid%2,
                           prior_discount_rate=None if appid%3==0 else appid/12,
                           last_observed_price=appid+year-2023)
                rows.append(row)
        return self.core.pd.DataFrame(rows)

    def test_only_three_historical_training_years(self):
        frame=self.fixture();p.validate_training(frame,list(range(1,13)))
        for replacement in (2022,2026):
            bad=frame.copy();bad.loc[0,'sale_year']=replacement
            with self.assertRaisesRegex(ValueError,'2023'):p.validate_training(bad,list(range(1,13)))

    def test_training_requires_each_game_once_per_year(self):
        frame=self.fixture()
        for bad in (frame.iloc[1:],self.core.pd.concat([frame,frame.iloc[:1]])):
            with self.assertRaises(ValueError):p.validate_training(bad,list(range(1,13)))
        frame.loc[0,'appid']=99
        with self.assertRaisesRegex(ValueError,'membership'):p.validate_training(frame,list(range(1,13)))

    def test_unknown_targets_rejected(self):
        frame=self.fixture();frame.loc[0,'discount_observed']=float('nan')
        with self.assertRaisesRegex(ValueError,'targets'):p.validate_training(frame,list(range(1,13)))

    def test_frozen_hyperparameters_and_threshold(self):
        p.verify_configuration(self.core,self.selection,self.protocol)
        expected=dict(n_estimators=100,max_depth=3,learning_rate=.05,subsample=.8,colsample_bytree=.8,
                      objective='binary:logistic',eval_metric='logloss',random_state=42,n_jobs=1)
        self.assertEqual(self.selection['selected_configuration'],expected)
        for key in expected:
            altered=copy.deepcopy(self.selection);altered['selected_configuration'][key]='altered'
            with self.assertRaises(ValueError):p.verify_configuration(self.core,altered,self.protocol)
        altered=copy.deepcopy(self.selection);altered['threshold']=.4
        with self.assertRaises(ValueError):p.verify_configuration(self.core,altered,self.protocol)

    def test_feature_order_change_is_rejected(self):
        altered=copy.deepcopy(self.protocol);altered['training']['feature_allowlist'].reverse()
        with self.assertRaisesRegex(ValueError,'ordering'):p.verify_configuration(self.core,self.selection,altered)

    def test_exact_classification_boundary(self):
        self.assertEqual(p.classify([0,.499999999,.5,.500000001,1],self.core).tolist(),[0,0,1,1,1])

    def test_invalid_probabilities_rejected(self):
        for values in ([float('nan')],[float('inf')],[-.0001],[1.0001],[[.5]]):
            with self.assertRaisesRegex(ValueError,'probability'):p.classify(values,self.core)

    def test_training_only_imputation_and_predictor_selection(self):
        train=self.fixture();model,profile=p.fit_refit(train,list(range(1,13)),self.core)
        self.core.np.testing.assert_array_equal(model.named_steps['impute'].statistics_,self.core.numeric_predictors(train).median())
        self.assertEqual(profile['training_years'],[2023,2024,2025]);self.assertEqual(profile['training_rows'],36)
        self.assertEqual(list(model[:-1].get_feature_names_out()),list(p.FEATURES.ALLOWLIST))
        test=train.iloc[:3].copy();medians=model.named_steps['impute'].statistics_.copy()
        first=p.positive_probabilities(model,test,self.core)
        test['appid']=999;test['sale_year']=2026;test['discount_observed']=999
        test['evidence_category']='untrusted';test['prediction_cutoff_utc']='untrusted'
        self.core.np.testing.assert_array_equal(first,p.positive_probabilities(model,test,self.core))
        test['last_observed_price']=1000000;p.positive_probabilities(model,test,self.core)
        self.core.np.testing.assert_array_equal(medians,model.named_steps['impute'].statistics_)

    def test_all_missing_training_feature_stops_before_fit(self):
        frame=self.fixture();frame['prior_discount_rate']=float('nan')
        with self.assertRaisesRegex(ValueError,'All-missing'):p.fit_refit(frame,list(range(1,13)),self.core)

    def test_deterministic_fixture_refit_and_reload(self):
        train=self.fixture();a,pa=p.fit_refit(train,list(range(1,13)),self.core);b,pb=p.fit_refit(train,list(range(1,13)),self.core)
        self.assertEqual(pa,pb)
        self.core.np.testing.assert_array_equal(p.positive_probabilities(a,train,self.core),p.positive_probabilities(b,train,self.core))
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'model.joblib';self.core.joblib.dump(a,path)
            self.core.np.testing.assert_array_equal(p.positive_probabilities(a,train,self.core),p.positive_probabilities(self.core.joblib.load(path),train,self.core))

    def test_null_csv_roundtrip_and_exclusive_writer(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'features.csv';p.write_csv(path,[{'value':None,'count':0},{'value':.5,'count':1}],self.core)
            self.assertEqual(p.read_csv(path),[{'value':'','count':'0'},{'value':'0.5','count':'1'}])
            with self.assertRaises(FileExistsError):p.write_csv(path,[{'value':2}],self.core)

    def test_guard_resolves_temp_cleanup_and_rename_directory_descriptors(self):
        with tempfile.TemporaryDirectory() as folder:
            directory=Path(folder).resolve();fd=os.open(directory,os.O_RDONLY)
            try:
                self.assertEqual(p.mutation_paths('os.remove',('payload.csv',fd)),[directory/'payload.csv'])
                self.assertEqual(p.mutation_paths('os.rename',('old.csv','new.csv',fd,fd)),[directory/'old.csv',directory/'new.csv'])
                self.assertEqual(p.mutation_paths('os.symlink',('/unrelated/source','link',fd)),[directory/'link'])
                self.assertEqual(p.mutation_paths('os.remove',(str(p.ROOT/'data/raw/itad/7830.json'),fd)),[p.ROOT/'data/raw/itad/7830.json'])
            finally:os.close(fd)

    def test_coverage_boundaries(self):
        self.assertEqual([p.coverage_group(n) for n in (0,1,9,10,29,30,100)],['0','1-9','1-9','10-29','10-29','30+','30+'])

    def test_exact_two_thousand_cohort_and_frozen_training(self):
        p.verify_indexes()
        games=p.load_cohort(p.ROOT/'data/cohorts/cohort_2000.csv');ids=[int(g['AppID']) for g in games]
        self.assertEqual(len(ids),2000);self.assertEqual(len(set(ids)),2000)
        frame,_,_=p.temporal.load_frozen(p.ROOT/'reports/cohort_2000_modeling',self.core)
        p.validate_training(frame,ids)
        self.assertEqual(frame.groupby('sale_year').size().to_dict(),{2023:2000,2024:2000,2025:2000})
        self.assertEqual(frame.discount_observed.value_counts().to_dict(),{1:3030,0:2970})

    def test_phase8a_actual_schema_membership_and_missingness(self):
        saved=p.read_csv(p.ROOT/'reports/cohort_2000_2026_feasibility/audit_feature_values.csv')
        integer=set(p.FEATURES.STATIC)|{'appid','sale_year','audit_release_hour_uncertain','prior_price_record_count',
                                     'prior_discount_count','has_prior_price_history','has_prior_discount_observation'}
        vectors=[{k:None if v=='' else int(v) if k in integer else float(v) if k in p.FEATURES.ALLOWLIST else v for k,v in r.items()} for r in saved]
        ids=[int(g['AppID']) for g in p.load_cohort(p.ROOT/'data/cohorts/cohort_2000.csv')]
        self.assertEqual(p.validate_features(vectors,ids,datetime(2026,10,1,17,tzinfo=timezone.utc),p.EXPECTED_NULLS),p.EXPECTED_NULLS)
        for changed in (vectors[:-1],vectors[::-1],vectors+[vectors[0]]):
            with self.assertRaises(ValueError):p.validate_features(changed,ids,datetime(2026,10,1,17,tzinfo=timezone.utc))
        altered=copy.deepcopy(vectors[0]);altered=dict(reversed(list(altered.items())))
        with self.assertRaisesRegex(ValueError,'schema'):p.feasibility.validate_vector(altered,datetime(2026,10,1,17,tzinfo=timezone.utc))

    def test_protected_preservation_is_separate_from_known_baseline_mismatch(self):
        baseline=p.read_json(p.ROOT/'tests/scalable_artifact_hashes.json')
        prior=p.read_json(p.ROOT/'reports/cohort_2000_2026_feasibility/validation.json')['preservation_sha256']
        self.assertEqual(len(baseline),219)
        self.assertTrue(all(p.digest(p.ROOT/name)==prior[name] for name in baseline))
        mismatches=[name for name,v in baseline.items() if p.digest(p.ROOT/name)!=v['sha256']]
        self.assertEqual(mismatches,['data/intermediate/autumn_sale_evidence_records.csv'])


class PredictionArtifactTests(unittest.TestCase):
    destination=p.OUT

    def test_output_membership_schema_probabilities_threshold(self):
        core=p.temporal.cores();out=self.destination
        features=core.pd.read_csv(out/'features_2026.csv');pred=core.pd.read_csv(out/'predictions_2026.csv')
        cohort=[int(g['AppID']) for g in p.load_cohort(p.ROOT/'data/cohorts/cohort_2000.csv')]
        self.assertEqual(features.appid.tolist(),cohort);self.assertEqual(pred.appid.tolist(),cohort)
        self.assertEqual(pred.appid.nunique(),2000);self.assertEqual(features.shape,(2000,19))
        self.assertEqual(list(features.columns),list(p.FEATURES.FIELDS))
        self.assertEqual(features[list(p.FEATURES.ALLOWLIST)].isna().sum().to_dict(),p.EXPECTED_NULLS)
        self.assertEqual(set(pred.sale_year),{2026});self.assertEqual(set(pred.prediction_cutoff_utc),{p.CUTOFF})
        self.assertEqual(set(pred.prediction_description),{p.DESCRIPTION})
        core.np.testing.assert_array_equal(pred.predicted_operational_label,p.classify(pred.predicted_probability,core))
        self.assertFalse(pred.point_in_time_provider_availability_proven.any())
        self.assertNotIn('actual_label',pred.columns)

    def test_saved_model_exact_params_training_only_medians(self):
        core=p.temporal.cores();out=self.destination;model=core.joblib.load(out/'refit_2023_2025_pipeline.joblib')
        original=p.read_json(p.ROOT/'reports/cohort_2000_models/selection.json')['selected_configuration']
        self.assertTrue(all(model.named_steps['classifier'].get_params()[k]==v for k,v in original.items()))
        training,_,_=p.temporal.load_frozen(p.ROOT/'reports/cohort_2000_modeling',core)
        core.np.testing.assert_array_equal(model.named_steps['impute'].statistics_,core.numeric_predictors(training).median())
        self.assertEqual(list(model[:-1].get_feature_names_out()),list(p.FEATURES.ALLOWLIST))
        manifest=p.read_json(out/'configuration_manifest.json')
        self.assertEqual(manifest['training_rows'],6000);self.assertEqual(manifest['training_years'],[2023,2024,2025])

    def test_checksums_reproduction_and_preservation(self):
        out=self.destination
        self.assertTrue(all(p.digest(out/name)==sha for name,sha in p.read_json(out/'checksums.json').items()))
        p.assert_preserved(p.read_json(out/'input_checksums.json')['preservation_sha256'])
        p.verify_indexes()
        receipt=p.read_json(out/'reproduction.json')
        self.assertEqual(receipt['maximum_absolute_probability_difference'],0)
        self.assertTrue(receipt['complete_pipeline_and_separate_components_reload_identical'])
        validation=p.read_json(out/'validation.json')
        self.assertEqual(validation['protected_artifacts_preserved'],219)
        self.assertEqual(validation['historical_baseline_matches'],218)
        self.assertEqual(validation['journal']['total_http_attempts'],3816)
        self.assertEqual(validation['timestamp_violations'],0)

    def test_summary_and_subgroups_partition_predictions(self):
        out=self.destination;pred=p.read_csv(out/'predictions_2026.csv');summary=p.read_json(out/'prediction_summary.json')
        ones=sum(int(r['predicted_operational_label']) for r in pred)
        self.assertEqual(summary['games'],2000);self.assertEqual(summary['predicted_positive'],ones)
        self.assertEqual(summary['predicted_operational_zero'],2000-ones)
        for name in ('coverage.csv','missingness_patterns.csv','probability_histogram.csv'):
            self.assertEqual(sum(int(r['games']) for r in p.read_csv(out/name)),2000)
        for name,label in (('top_10_predicted_positive.csv',1),('bottom_10_predicted_zero.csv',0)):
            rows=p.read_csv(out/name);self.assertEqual(len(rows),10)
            self.assertEqual({int(r['predicted_operational_label']) for r in rows},{label})


if __name__=='__main__':unittest.main()
