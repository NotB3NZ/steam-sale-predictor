"""Operational-target tests; all mutation fixtures are temporary or in memory."""
import copy
from datetime import timedelta
import importlib.util
import json
from pathlib import Path
import socket
import tempfile
import unittest

import test_autumn_evidence_audit as prior

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('operational_labels', ROOT / 'src/06_build_operational_labels.py')
labels = importlib.util.module_from_spec(spec)
spec.loader.exec_module(labels)
WINDOWS = labels.audit.canonical_windows(ROOT)


def strings(row):
    return {k: str(v) for k, v in row.items()}


def synthetic(history=(), release='2020-01-01'):
    game = {'AppID': '1', 'Name': 'Synthetic game', 'release_date': release}
    records, failures, other = labels.audit.parse_history(list(history))
    if failures or other:
        raise ValueError('Invalid synthetic input')
    info = dict(cache_status='ok', issue='', raw_history_record_count=len(history))
    inputs = dict(pairs=[], records=[], diagnostics=[], games=[game],
                  manifest=[dict(AppID='1', Name=game['Name'], country='US', steam_shop_id='61', cache_path='data/raw/itad/1.json')])
    for year, window in WINDOWS.items():
        pair, long = labels.audit.audit_pair(game, year, window, records, info)
        diagnostic = labels.coverage.summarize_pair(game, year, window, records, info)
        inputs['pairs'].append(strings(pair))
        inputs['records'].extend(strings(r) for r in long)
        inputs['diagnostics'].append(strings(diagnostic))
    return inputs


class MappingTests(unittest.TestCase):
    def test_categories_A_B_D_and_PU(self):
        for category, value, status in [('A', 1, 'positive'), ('B', 0, 'unlabeled'), ('D', 0, 'unlabeled')]:
            with self.subTest(category=category):
                self.assertEqual(labels.mapping(category), dict(discount_observed=value, pu_status=status,
                                                               ambiguity_flag=False, requires_review=False))

    def test_C_stays_null_and_flagged_in_constructed_rows(self):
        raw = prior.raw('2023-11-23T18:00:00Z')
        raw['deal'] = None
        result = labels.construct_labels(synthetic([raw]), WINDOWS)[0]
        self.assertEqual(result['evidence_category'], 'C')
        self.assertEqual(result['discount_observed'], '')
        self.assertEqual(result['pu_status'], 'unlabeled')
        self.assertTrue(result['ambiguity_flag'])
        self.assertTrue(result['requires_review'])
        self.assertEqual(result['null_deal_record_count'], 1)
        self.assertEqual(result['supporting_record_indices'], '[]')

    def test_unexpected_categories_rejected(self):
        for value in ('', 'X', 'AB', None):
            with self.assertRaisesRegex(ValueError, 'Invalid evidence category'):
                labels.mapping(value)

    def test_discount_support_indices_and_no_fabricated_prices(self):
        history = [prior.raw('2023-11-22T18:00:00Z', 5, 10, 50), prior.raw('2023-11-23T18:00:00Z')]
        row = labels.construct_labels(synthetic(history), WINDOWS)[0]
        self.assertEqual(row['discount_observed'], 1)
        self.assertEqual(row['discounted_record_count'], 1)
        self.assertEqual(row['supporting_record_indices'], '[0]')
        self.assertEqual(row['in_window_record_indices'], '[0,1]')
        self.assertEqual(row['source_shop_id'], 61)
        self.assertEqual(row['source_region'], 'US')
        self.assertEqual(row['source_currencies'], 'USD')
        self.assertNotIn('price', row)

    def test_full_price_and_no_observations_both_operational_zero(self):
        inputs = synthetic([prior.raw('2023-11-23T18:00:00Z')])
        rows = labels.construct_labels(inputs, WINDOWS)
        self.assertEqual([r['evidence_category'] for r in rows], ['B', 'D', 'D'])
        self.assertEqual([r['discount_observed'] for r in rows], [0, 0, 0])
        self.assertTrue(all(r['supporting_record_indices'] == '[]' for r in rows))
        self.assertTrue(all(r['label_limitation_flag'] for r in rows))

    def test_mixed_discounted_full_price_and_ambiguous_records_retain_A(self):
        ambiguous = prior.raw('2023-11-24T18:00:00Z')
        ambiguous['deal'] = None
        rows = labels.construct_labels(synthetic([prior.raw('2023-11-22T18:00:00Z', 5, 10, 50),
                                                  prior.raw('2023-11-23T18:00:00Z'), ambiguous]), WINDOWS)
        self.assertEqual(rows[0]['evidence_category'], 'A')
        self.assertEqual(rows[0]['discount_observed'], 1)
        self.assertEqual(rows[0]['ambiguous_record_count'], 1)

    def test_start_included_and_end_excluded_with_immediate_neighbors(self):
        start, end = WINDOWS[2023][2:]
        for timestamp, expected in [(start, 1), (start - timedelta(microseconds=1), 0),
                                    (end, 0), (end - timedelta(microseconds=1), 1)]:
            with self.subTest(timestamp=timestamp):
                row = labels.construct_labels(synthetic([prior.raw(labels.audit.fmt(timestamp), 5, 10, 50)]), WINDOWS)[0]
                self.assertEqual(row['discount_observed'], expected)
                self.assertEqual(row['sale_start_utc'], labels.audit.fmt(start))
                self.assertEqual(row['sale_end_utc'], labels.audit.fmt(end))

    def test_duplicate_game_year_rejected(self):
        inputs = synthetic()
        inputs['pairs'].append(copy.deepcopy(inputs['pairs'][0]))
        with self.assertRaisesRegex(ValueError, 'Duplicate game-year'):
            labels.construct_labels(inputs, WINDOWS)

    def test_unsupported_year_and_2026_rejected(self):
        for year in ('2022', '2026', 'invalid'):
            inputs = synthetic()
            inputs['pairs'][0]['sale_year'] = year
            with self.assertRaisesRegex(ValueError, 'sale year'):
                labels.construct_labels(inputs, WINDOWS)

    def test_missing_appid_and_missing_game_year_rejected(self):
        inputs = synthetic()
        inputs['pairs'][0]['AppID'] = ''
        with self.assertRaisesRegex(ValueError, 'AppID'):
            labels.construct_labels(inputs, WINDOWS)
        inputs = synthetic()
        inputs['pairs'].pop()
        with self.assertRaisesRegex(ValueError, 'pair keys'):
            labels.construct_labels(inputs, WINDOWS)

    def test_category_and_record_count_corruption_rejected(self):
        inputs = synthetic()
        inputs['pairs'][0]['evidence_category'] = 'B'
        with self.assertRaisesRegex(ValueError, 'category mismatch'):
            labels.construct_labels(inputs, WINDOWS)
        inputs = synthetic()
        inputs['pairs'][0]['in_window_record_count'] = '1'
        with self.assertRaisesRegex(ValueError, 'count mismatch'):
            labels.construct_labels(inputs, WINDOWS)

    def test_inexact_calendar_boundary_rejected(self):
        inputs = synthetic()
        inputs['pairs'][0]['window_start_utc'] = '2023-11-21T00:00:00Z'
        with self.assertRaisesRegex(ValueError, 'Exact UTC calendar mismatch'):
            labels.construct_labels(inputs, WINDOWS)

    def test_steam_only_and_raw_field_consistency(self):
        inputs = synthetic([prior.raw('2023-11-23T18:00:00Z', 5, 10, 50)])
        modified = copy.deepcopy(inputs)
        raw = json.loads(modified['records'][0]['raw_record_json'])
        raw['shop']['id'] = 1
        modified['records'][0]['raw_record_json'] = json.dumps(raw)
        with self.assertRaisesRegex(ValueError, 'Steam shop 61'):
            labels.construct_labels(modified, WINDOWS)
        inputs['records'][0]['cut'] = '75'
        with self.assertRaisesRegex(ValueError, 'Raw/parsed evidence disagrees'):
            labels.construct_labels(inputs, WINDOWS)

    def test_foreign_region_or_fabricated_raw_provenance_rejected(self):
        inputs = synthetic()
        inputs['manifest'][0]['country'] = 'DE'
        with self.assertRaisesRegex(ValueError, 'Collection scope'):
            labels.construct_labels(inputs, WINDOWS)
        inputs = synthetic([prior.raw('2023-11-23T18:00:00Z', 5, 10, 50)])
        inputs['diagnostics'][0]['in_window_raw_indices_json'] = '[99]'
        with self.assertRaisesRegex(ValueError, 'raw provenance'):
            labels.construct_labels(inputs, WINDOWS)

    def test_same_timestamp_conflicts_not_collapsed(self):
        inputs = synthetic([prior.raw('2023-11-23T18:00:00Z', 5, 10, 50), prior.raw('2023-11-23T18:00:00Z')])
        row = labels.construct_labels(inputs, WINDOWS)[0]
        self.assertEqual(row['in_window_record_count'], 2)
        self.assertEqual(row['in_window_conflicting_timestamp_groups'], 1)
        self.assertEqual(row['supporting_record_indices'], '[0]')

    def test_empty_history_has_no_fabricated_observed_currency_or_indices(self):
        rows = labels.construct_labels(synthetic(), WINDOWS)
        self.assertTrue(all(r['empty_raw_history'] and r['source_currencies'] == '' and
                            r['in_window_record_indices'] == '[]' for r in rows))

    def test_eligibility_hour_uncertainty_retained(self):
        row = labels.construct_labels(synthetic(release='2023-11-21'), WINDOWS)[0]
        self.assertEqual(row['eligibility_status'], 'uncertain_release_hour')
        self.assertTrue(row['requires_review'])
        self.assertEqual(row['discount_observed'], 0)

    def test_input_permutation_does_not_change_outputs(self):
        inputs = synthetic([prior.raw('2023-11-22T18:00:00Z', 5, 10, 50), prior.raw('2023-11-23T18:00:00Z')])
        original = labels.construct_labels(inputs, WINDOWS)
        for rows in inputs.values():
            rows.reverse()
        self.assertEqual(labels.construct_labels(inputs, WINDOWS), original)


class OfflineIntegrationTests(unittest.TestCase):
    def fixture(self, root):
        paths = list(labels.protected_hashes(ROOT)) + ['PROJECT_CONTEXT.md', 'src/06_build_operational_labels.py',
                                                     'tests/test_operational_labels.py']
        for name in paths:
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(ROOT / name)

    def test_real_pilot_counts_provenance_PU_and_deterministic_full_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            before = labels.protected_hashes(root)
            rows, pu, receipt = labels.run(root)
            first = {p: (root / p).read_bytes() for p in labels.OUTPUTS}
            labels.run(root)
            self.assertEqual(first, {p: (root / p).read_bytes() for p in labels.OUTPUTS})
            self.assertEqual(before, labels.protected_hashes(root))
            self.assertEqual(receipt['operational_label_counts'], {'1': 175, '0': 125, 'null': 0})
            self.assertEqual(receipt['category_counts'], dict(A=175, B=3, C=0, D=122))
            self.assertEqual(receipt['pu_status_counts'], dict(positive=175, unlabeled=125))
            self.assertEqual(receipt['eligibility_uncertainty_count'], 1)
            self.assertEqual(receipt['duplicate_count'], 0)
            for y, positives, zeros in [(2023, 55, 45), (2024, 60, 40), (2025, 60, 40)]:
                self.assertEqual(receipt['year_counts'][str(y)]['operational_label_counts'], {'1': positives, '0': zeros, 'null': 0})
            self.assertEqual(pu, [{f: r[f] for f in ('appid', 'sale_year', 'evidence_category', 'pu_status', 'label_rule_version')} for r in rows])
            self.assertEqual(sum(r['empty_raw_history'] for r in rows), 9)
            neko = next(r for r in rows if r['appid'] == '2650840' and r['sale_year'] == 2023)
            self.assertEqual(neko['eligibility_status'], 'uncertain_release_hour')
            self.assertEqual(receipt['checks']['diagnostic_network_attempts'], 0)

    def test_protected_evidence_change_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            path = root / labels.INPUTS['records'][0]
            path.unlink()  # Temporary symlink only; original file is unchanged.
            path.write_text('invalid')
            with self.assertRaisesRegex(ValueError, 'Protected input changed'):
                labels.run(root)

    def test_malformed_csv_schema_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            path = root / labels.INPUTS['pairs'][0]
            path.unlink()
            path.write_text('AppID,Name\n1,Synthetic\n')
            with self.assertRaisesRegex(ValueError, 'Missing required columns'):
                labels.read_inputs(root)

    def test_offline_guard_blocks_network(self):
        with self.assertRaises(AssertionError):
            with labels.coverage.offline_guard():
                socket.create_connection(('example.com', 443))


if __name__ == '__main__':
    unittest.main()
