"""Pure offline dataset/split regressions; no fitted transformations or models."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
import freeze_cohort_modeling as freeze
from cohort_io import digest, read_csv


class FrozenModelingTests(unittest.TestCase):
    def setUp(self):
        self.windows = freeze.pipeline.audit.canonical_windows(freeze.ROOT)
        games = {1: dict(release_date='2020-01-01'), 2: dict(release_date='2020-01-01')}
        raw = dict(timestamp='2023-11-20T18:00:00Z', shop={'id': 61},
                   deal=dict(price=dict(amount=5, amountInt=500, currency='USD'),
                             regular=dict(amount=10, amountInt=1000, currency='USD'), cut=50))
        parsed, _, _ = freeze.pipeline.audit.parse_history([raw])
        pairs = [(appid, year) for appid in games for year in self.windows]
        features, provenance = freeze.FEATURES.build_features(pairs, games, {1: parsed, 2: []}, self.windows)
        labels = [dict(appid=str(appid), sale_year=year, discount_observed=int(appid == 1),
                       evidence_category='A' if appid == 1 else 'D',
                       sale_start_utc=freeze.pipeline.audit.fmt(self.windows[year][2])) for appid,year in pairs]
        self.result = dict(labels=labels, features=features, provenance=provenance)
        self.rows = freeze.assemble_dataset(self.result)

    def test_schema_preserves_original_features_and_target_provenance(self):
        result = freeze.validate_rows(self.rows, self.windows, {1, 2})
        self.assertEqual(result['dataset_columns'], 21)
        self.assertEqual(result['approved_feature_count'], 15)
        self.assertTrue(all(r['discount_observed'] == 0 for r in self.rows if r['evidence_category'] == 'D'))
        self.assertTrue(all(tuple(r) == freeze.DATASET_FIELDS for r in self.rows))

    def test_unknown_operational_target_is_not_forced_to_zero(self):
        self.result['labels'][0].update(discount_observed='', evidence_category='C')
        with self.assertRaisesRegex(ValueError, 'Unknown targets'):
            freeze.assemble_dataset(self.result)

    def test_duplicate_labels_or_unmatched_feature_keys_are_rejected(self):
        duplicate = copy.deepcopy(self.result)
        duplicate['labels'].append(duplicate['labels'][0])
        with self.assertRaisesRegex(ValueError, 'Duplicate labels'):
            freeze.assemble_dataset(duplicate)
        self.result['features'].pop()
        with self.assertRaisesRegex(ValueError, 'join mismatch'):
            freeze.assemble_dataset(self.result)

    def test_split_uses_every_game_chronologically_without_old_group_filter(self):
        membership, protocol = freeze.temporal_protocol(self.rows)
        self.assertEqual(protocol['splits']['final_training']['rows'], 4)
        self.assertEqual(protocol['splits']['held_out_test']['rows'], 2)
        self.assertEqual(protocol['splits']['development_training']['rows'], 2)
        self.assertEqual(protocol['splits']['development_validation']['rows'], 2)
        self.assertEqual(protocol['final_train_test_game_overlap'], 2)
        self.assertTrue(all(r['development_role'] == 'excluded' and r['final_role'] == 'held_out_test'
                            for r in membership if r['sale_year'] == 2025))
        self.assertFalse(protocol['preprocessing']['fitted_during_preparation'])

    def test_test_outcomes_do_not_change_training_membership_or_counts(self):
        roles, protocol = freeze.temporal_protocol(self.rows)
        changed = copy.deepcopy(self.rows)
        for row in changed:
            if row['sale_year'] == 2025:
                row.update(discount_observed=1, evidence_category='A')
        other_roles, other = freeze.temporal_protocol(changed)
        self.assertEqual(roles, other_roles)
        for name in ('final_training', 'development_training', 'development_validation'):
            self.assertEqual(protocol['splits'][name], other['splits'][name])

    def test_missing_and_duplicate_game_years_are_rejected(self):
        for rows in (self.rows[:-1], self.rows[:-1]+[self.rows[0]]):
            with self.assertRaisesRegex(ValueError, 'Missing or duplicate'):
                freeze.validate_rows(rows, self.windows, {1, 2})

    def test_unapproved_snapshot_column_is_rejected(self):
        self.rows[0]['current_price'] = 999
        with self.assertRaisesRegex(ValueError, 'columns'):
            freeze.validate_rows(self.rows, self.windows, {1, 2})

    def test_invalid_feature_values_and_types_are_rejected(self):
        for name, value in [('game_age_days', -1), ('release_month', 13),
                            ('last_observed_discount_pct', 101), ('last_observed_price', float('inf')),
                            ('prior_price_record_count', 1.5), ('prior_discount_rate', 0.1)]:
            with self.subTest(feature=name):
                rows = copy.deepcopy(self.rows)
                rows[0][name] = value
                with self.assertRaises(ValueError):
                    freeze.validate_rows(rows, self.windows, {1, 2})

    def test_missing_history_values_cannot_be_silently_zero_filled(self):
        rows = copy.deepcopy(self.rows)
        row = next(r for r in rows if r['appid'] == 2)
        self.assertIsNone(row['last_observed_price'])
        row['last_observed_price'] = 0
        with self.assertRaisesRegex(ValueError, 'filled'):
            freeze.validate_rows(rows, self.windows, {1, 2})

    def test_wrong_cutoff_and_target_mapping_are_rejected(self):
        for name, value in [('prediction_cutoff_utc', '2023-11-21T00:00:00Z'), ('discount_observed', 0)]:
            rows = copy.deepcopy(self.rows)
            rows[0][name] = value
            with self.assertRaises(ValueError):
                freeze.validate_rows(rows, self.windows, {1, 2})

    def test_serialized_nulls_checksums_and_reproduction(self):
        roles, protocol = freeze.temporal_protocol(self.rows)
        payload = dict(rows=self.rows, features=self.result['features'], provenance=self.result['provenance'],
                       membership=roles, protocol=protocol, missingness=freeze.missingness(self.rows),
                       manifest=freeze.FEATURES.feature_manifest(), labels=freeze.distribution(self.rows),
                       validation={}, input_manifest={})
        with tempfile.TemporaryDirectory() as temp:
            first, second = Path(temp)/'first', Path(temp)/'second'
            freeze.write_outputs(first, payload)
            freeze.write_outputs(second, payload)
            checks = json.loads((first/'checksums.json').read_text())
            self.assertEqual(checks, json.loads((second/'checksums.json').read_text()))
            self.assertTrue(all(digest(first/name) == value for name,value in checks.items()))
            empty = next(r for r in read_csv(first/'modeling.csv') if r['appid'] == '2')
            self.assertEqual(empty['last_observed_price'], '')
            self.assertEqual(empty['prior_price_record_count'], '0')

    def test_missingness_is_reported_by_year_for_every_predictor(self):
        report = freeze.missingness(self.rows)
        self.assertEqual(len(report), 60)
        self.assertTrue(all(r['missing'] == 1 and r['missing_percent'] == 50
                            for r in report if r['feature'] == 'last_observed_price' and r['sale_year'] != 'all'))


if __name__ == '__main__':
    unittest.main()
