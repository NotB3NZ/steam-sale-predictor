"""Public verification regressions; no fitting, inference, network, or writes."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('steam_public_verification', ROOT / 'scripts/verify_public.py')
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


class PublicVerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cohort = v.rows(ROOT, 'data/cohorts/cohort_2000.csv')
        cls.modeling = v.rows(ROOT, v.MODELING + '/modeling.csv')
        cls.predictions = v.rows(ROOT, v.PRED_CSV)
        cls.features = v.rows(ROOT, v.PRED + '/features_2026.csv')
        cls.availability = v.rows(ROOT, 'reports/cohort_2000_2026_feasibility/game_availability.csv')
        cls.baseline = v.load_json(ROOT, v.BASELINE)
        cls.original_hash = cls.baseline['historical_exceptions']['prediction_csv']['original_sha256']
        cls.metrics = v.load_json(ROOT, v.MODELS + '/held_out_metrics.json')['models']

    def check_tables(self, **changes):
        args = dict(cohort=self.cohort, modeling=self.modeling,
                    predictions=self.predictions, features=self.features)
        args.update(changes)
        return v.check_tables(**args)

    def test_delivered_public_verification_passes_with_explicit_scope(self):
        opened = []
        original = v.sha
        def audited_sha(path):
            opened.append(path.relative_to(ROOT).as_posix())
            return original(path)
        with patch.object(v, 'sha', side_effect=audited_sha):
            result = v.verify(ROOT)
        self.assertEqual(result['immutable_files_verified'], 2474)
        self.assertEqual(result['status'], 'PASS WITH DOCUMENTED EXCEPTIONS')
        self.assertEqual(result['historical_integrity']['legacy_entries_omitted'], ['games.csv', 'games.json', 'test.py'])
        self.assertFalse(set(opened) & (v.LEGACY_LOCAL | {'apikey', '.DS_Store'}))
        self.assertEqual(result['facts']['predicted_positive'], 1026)

    def test_unexpected_hash_fails_without_altering_file(self):
        with patch.object(v, 'sha', return_value='0' * 64):
            with self.assertRaisesRegex(v.VerificationError, 'Unexpected current-state hash'):
                v.check_hashes(ROOT, {'data/cohorts/cohort_2000.csv': self.baseline['immutable_sha256']['data/cohorts/cohort_2000.csv']})

    def test_missing_artifact_and_escape_paths_fail(self):
        with self.assertRaisesRegex(v.VerificationError, 'Missing public artifact'):
            v.check_hashes(ROOT, {'reports/nonexistent-public-artifact.csv': '0' * 64})
        for path in ['../apikey', '/tmp/outside.csv', 'data/../../apikey']:
            with self.assertRaises(v.VerificationError):
                v.safe_path(ROOT, path)

    def test_cohort_loss_or_duplicate_fails(self):
        for bad in [self.cohort[:-1], self.cohort[:-1] + [self.cohort[0]]]:
            with self.assertRaises(v.VerificationError):
                self.check_tables(cohort=bad)

    def test_wrong_year_duplicate_and_cutoff_fail(self):
        for field, value in [('sale_year', '2026'), ('prediction_cutoff_utc', '2025-01-01T00:00:00Z')]:
            bad = deepcopy(self.modeling)
            bad[0][field] = value
            with self.assertRaises(v.VerificationError):
                self.check_tables(modeling=bad)
        with self.assertRaises(v.VerificationError):
            self.check_tables(modeling=self.modeling[:-1] + [self.modeling[0]])

    def test_evidence_category_mismatch_fails_without_relabeling(self):
        bad = deepcopy(self.modeling)
        bad[0]['evidence_category'] = 'A' if bad[0]['discount_observed'] == '0' else 'D'
        with self.assertRaisesRegex(v.VerificationError, 'evidence policy'):
            self.check_tables(modeling=bad)

    def test_feature_missingness_is_checked_by_feature(self):
        bad = deepcopy(self.modeling)
        bad[0]['game_age_days'] = ''
        with self.assertRaisesRegex(v.VerificationError, 'predictor missingness'):
            self.check_tables(modeling=bad)

    def test_prediction_membership_year_and_threshold_fail(self):
        with self.assertRaises(v.VerificationError):
            self.check_tables(predictions=self.predictions[:-1])
        for field, value in [('sale_year', '2025'), ('predicted_operational_label',
                             '0' if self.predictions[0]['predicted_operational_label'] == '1' else '1')]:
            bad = deepcopy(self.predictions)
            bad[0][field] = value
            with self.assertRaises(v.VerificationError):
                self.check_tables(predictions=bad)

    def test_nonfinite_probability_fails(self):
        bad = deepcopy(self.predictions)
        bad[0]['predicted_probability'] = 'nan'
        with self.assertRaisesRegex(v.VerificationError, 'probability/class'):
            self.check_tables(predictions=bad)

    def test_missingness_count_or_feature_inconsistency_fails(self):
        bad = deepcopy(self.predictions)
        bad[0]['missing_feature_count'] = '15'
        with self.assertRaisesRegex(v.VerificationError, '2026 missingness'):
            self.check_tables(predictions=bad)
        bad_features = deepcopy(self.features)
        bad_features[0]['prior_price_record_count'] = '999'
        with self.assertRaises(v.VerificationError):
            self.check_tables(features=bad_features)

    def test_equivalence_is_order_independent_and_does_not_mutate_inputs(self):
        original = deepcopy(self.predictions)
        proof = v.prediction_equivalence(list(reversed(self.predictions)), self.availability, self.original_hash)
        self.assertTrue(proof['original_hash_reproduced'])
        self.assertEqual(proof['current_name_discrepancy_appids'], ['2402900'])
        self.assertEqual(self.predictions, original)

    def test_equivalence_rejects_changed_numeric_field(self):
        bad = deepcopy(self.predictions)
        bad[0]['predicted_probability'] = str(float(bad[0]['predicted_probability']) + .000001)
        with self.assertRaisesRegex(v.VerificationError, 'original row-order/name equivalence'):
            v.prediction_equivalence(bad, self.availability, self.original_hash)

    def test_readme_wrong_metric_and_missing_warning_fail(self):
        body = (ROOT / 'README.md').read_text()
        for bad in [body.replace('**91.40%**', '**99.00%**'), body.replace(v.NOTICE, '')]:
            with self.assertRaises(v.VerificationError):
                v.check_readme(bad, self.metrics)

    def test_broken_link_and_anchor_fail(self):
        for body in ['[missing](missing-file-public.md)', '[bad anchor](README.md#missing-public-anchor)']:
            with patch.object(Path, 'read_text', return_value=body):
                with self.assertRaises(v.VerificationError):
                    v.markdown_links(ROOT, ['README.md'])

    def test_png_dpi_and_saved_evaluation_are_checked(self):
        for name in v.FIGURES:
            self.assertAlmostEqual(v.png_metadata(ROOT / name), 300, places=2)
        self.assertEqual(v.check_saved_evaluation(ROOT)['accuracy_2025'], .914)

    def test_spearman_handles_tied_ranks(self):
        self.assertEqual(v.spearman([1, 1, 3], [4, 4, 9]), 1)
        self.assertEqual(v.spearman([1, 1, 3], [9, 9, 4]), -1)


class VerificationGuardTests(unittest.TestCase):
    def test_registered_guard_rejects_events_without_process_global_pollution(self):
        # Inspect the registered handler without installing a permanent hook in
        # unittest's process. The CLI separately exercises its actual hook.
        with patch.object(sys, 'addaudithook') as register:
            v.install_guard(ROOT)
        register.assert_called_once()
        guard = register.call_args[0][0]
        probes = [
            ('socket.connect', (None, None)),
            ('socket.getaddrinfo', (None, None, None, None, None)),
            ('subprocess.Popen', (None, None, None, None)),
            ('import', ('xgboost', None, None, None, None)),
            ('pickle.find_class', ('model', 'Class')),
            ('open', (str(ROOT / 'README.md'), 'w', 577)),
            ('open', (str(ROOT / 'apikey'), 'r', 0)),
            ('open', (str(ROOT / 'games.csv'), 'r', 0)),
            ('os.remove', (str(ROOT / 'README.md'), -1)),
        ]
        for event, args in probes:
            with self.subTest(event=event):
                with self.assertRaises(v.VerificationError):
                    guard(event, args)


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    unittest.main()
