"""Offline checks for diagnostic selection, provenance and missing-evidence safeguards."""
import copy
import importlib.util
import json
from pathlib import Path
import socket
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ground_truth', ROOT / 'src/06_verify_historical_ground_truth.py')
ground = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ground)


class SourceFeasibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = ground.audit.read_csv(ROOT / ground.coverage.DIAGNOSTICS)
        cls.pilot = ground.select_pilot(cls.rows)
        cls.inventory = json.loads((ROOT / ground.INVENTORY).read_text())
        cls.ledger = json.loads((ROOT / ground.LEDGER).read_text())
        cls.windows = ground.audit.canonical_windows(ROOT)

    def validate(self, records):
        return ground.validate_evidence(records, self.pilot, self.inventory, self.windows)

    def observation(self, timestamp='2023-11-21T18:00:00Z', price=5, regular=10, cut=50):
        records = copy.deepcopy(self.ledger['records'])
        records[0].update(source_page_accessible=True, historical_price_observation_available=True,
                          observation_timestamp_utc=timestamp, observed_price=price, regular_price=regular,
                          discount_percent=cut, currency='USD', region='US', steam_store_explicit=True,
                          purchase_scope='standalone base game', coverage_kind='point',
                          independently_verifiable_observation=True, supports_discount_occurrence=False)
        return records

    def test_selection_is_deterministic_under_input_permutation(self):
        self.assertEqual(self.pilot, ground.select_pilot(list(reversed(self.rows))))

    def test_selection_strata_and_scope(self):
        self.assertEqual(len(self.pilot), 18)
        keys = {(r['appid'], r['sale_year']) for r in self.pilot}
        self.assertEqual(len(keys), 18)
        self.assertEqual({r['sale_year'] for r in self.pilot}, {'2023', '2024', '2025'})
        self.assertEqual(sum(r['evidence_category'] == 'B' for r in self.pilot), 3)
        self.assertEqual(sum('positive_control_A' in r['selection_rationale'] for r in self.pilot), 2)
        self.assertEqual(sum('historical_timestamp_conflict' in r['selection_rationale'] for r in self.pilot), 2)
        self.assertEqual(sum(r['empty_raw_history'] == 'True' for r in self.pilot), 1)
        self.assertEqual(sum(r['evidence_category'] == 'D' and r['pre_observed_state'] == 'discount' for r in self.pilot), 3)
        self.assertTrue(all(r['selection_rationale'] for r in self.pilot))

    def test_original_categories_retained(self):
        original = {(r['appid'], r['sale_year']): r for r in self.rows}
        for r in self.pilot:
            self.assertEqual(r['evidence_category'], original[r['appid'], r['sale_year']]['evidence_category'])

    def test_real_ledger_counts_reconcile(self):
        evidence = self.validate(self.ledger['records'])
        counts = ground.summarize(self.pilot, evidence)
        self.assertEqual(counts['discoverable_source_page_pairs'], 8)
        self.assertEqual(counts['not_verifiable_pairs'], 18)
        self.assertEqual(counts['unknown_release_hour_pairs'], 1)
        for key in ('historical_price_observation_pairs', 'independent_positive_evidence_pairs',
                    'full_sale_absence_evidence_pairs', 'partial_only_pricing_evidence_pairs', 'conflicting_source_pairs'):
            self.assertEqual(counts[key], 0)

    def test_missing_price_information_stays_empty(self):
        evidence = self.validate(self.ledger['records'])
        self.assertTrue(all(r['observed_price'] == r['observation_timestamp_utc'] == r['evidence_inside_sale'] == '' for r in evidence))
        self.assertTrue(all(r['verification_result'] == 'NOT_VERIFIABLE' for r in evidence))

    def test_single_full_price_point_is_partial_never_full_sale_absence(self):
        records = self.observation(price=10, cut=0)
        counts = ground.summarize(self.pilot, self.validate(records))
        self.assertEqual(counts['partial_only_pricing_evidence_pairs'], 1)
        self.assertEqual(counts['full_sale_absence_evidence_pairs'], 0)
        records[0]['supports_full_sale_absence'] = True
        with self.assertRaisesRegex(ValueError, 'point observation'):
            self.validate(records)

    def test_exact_start_is_inside_and_exact_end_is_outside(self):
        records = self.observation()
        records[0]['supports_discount_occurrence'] = True
        self.assertTrue(self.validate(records)[0]['evidence_inside_sale'])
        records[0]['observation_timestamp_utc'] = '2023-11-28T18:00:00Z'
        with self.assertRaisesRegex(ValueError, 'Positive assertion'):
            self.validate(records)
        records[0]['supports_discount_occurrence'] = False
        self.assertFalse(self.validate(records)[0]['evidence_inside_sale'])

    def test_2026_observations_and_sale_rows_rejected(self):
        records = self.observation('2026-01-01T00:00:00Z')
        with self.assertRaisesRegex(ValueError, '2026 observations'):
            self.validate(records)
        records = copy.deepcopy(self.ledger['records'])
        records[0]['sale_year'] = 2026
        with self.assertRaisesRegex(ValueError, 'outside selected scope'):
            self.validate(records)

    def test_naive_timestamps_and_noncanonical_offsets_rejected(self):
        for timestamp in ('2023-11-21T18:00:00', '2023-11-21T10:00:00-08:00'):
            with self.assertRaises(ValueError):
                self.validate(self.observation(timestamp))

    def test_missing_or_inaccessible_evidence_cannot_be_positive(self):
        records = copy.deepcopy(self.ledger['records'])
        records[0]['supports_discount_occurrence'] = True
        with self.assertRaisesRegex(ValueError, 'Missing evidence'):
            self.validate(records)
        records = self.observation()
        records[0]['source_page_accessible'] = False
        with self.assertRaisesRegex(ValueError, 'inaccessible'):
            self.validate(records)

    def test_store_and_scope_provenance_required_for_discount_assertion(self):
        for field, value in [('steam_store_explicit', False), ('region', ''), ('currency', ''), ('purchase_scope', '')]:
            records = self.observation()
            records[0].update(supports_discount_occurrence=True)
            records[0][field] = value
            with self.assertRaisesRegex(ValueError, 'provenance'):
                self.validate(records)

    def test_conflicting_source_observations_preserved(self):
        records = self.observation()
        records[0]['contradicts_itad'] = 'YES'
        evidence = self.validate(records)
        self.assertEqual(evidence[0]['contradicts_itad'], 'YES')
        self.assertEqual(ground.summarize(self.pilot, evidence)['conflicting_source_pairs'], 1)

    def test_ambiguous_point_does_not_gain_a_price_or_outcome(self):
        records = self.observation()
        records[0].update(observed_price='', regular_price='', discount_percent='',
                          independently_verifiable_observation=False)
        evidence = self.validate(records)
        self.assertEqual(evidence[0]['observed_price'], '')
        self.assertFalse(evidence[0]['supports_discount_occurrence'])

    def test_missing_provenance_and_invalid_access_reuse_rejected(self):
        records = copy.deepcopy(self.ledger['records'])
        records[0]['source_url'] = ''
        with self.assertRaisesRegex(ValueError, 'provenance'):
            self.validate(records)
        records = copy.deepcopy(self.ledger['records'])
        records[0]['reuse_of_attempt_id'] = 'R99'
        with self.assertRaisesRegex(ValueError, 'reused access'):
            self.validate(records)

    def test_complete_interval_claim_requires_documented_proof(self):
        records = self.observation(price=10, cut=0)
        records[0].update(supports_full_sale_absence=True, coverage_kind='continuous_documented_complete',
                          coverage_start_utc='2023-11-21T18:00:00Z', coverage_end_utc='2023-11-28T18:00:00Z')
        with self.assertRaisesRegex(ValueError, 'point observation'):
            self.validate(records)

    def test_network_guard_blocks_connections(self):
        with self.assertRaises(AssertionError):
            with ground.coverage.offline_guard():
                socket.create_connection(('example.com', 443))


class OfflineIntegrationTests(unittest.TestCase):
    def fixture(self, root):
        manifest = json.loads((ROOT / ground.MANIFEST).read_text())
        paths = list(manifest['protected_sha256']) + [ground.MANIFEST, ground.INVENTORY, ground.LEDGER,
                                                     'PROJECT_CONTEXT.md', 'src/06_verify_historical_ground_truth.py',
                                                     'tests/test_historical_ground_truth.py']
        for name in paths:
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(ROOT / name)

    def test_full_pipeline_deterministic_and_prior_inputs_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            before = ground.protected_hashes(root)
            pilot, evidence, receipt = ground.run(root)
            first = {p: (root / p).read_bytes() for p in ground.OUTPUTS}
            ground.run(root)
            self.assertEqual(first, {p: (root / p).read_bytes() for p in ground.OUTPUTS})
            self.assertEqual(before, ground.protected_hashes(root))
            self.assertEqual(receipt['all_existing_pairs'], 300)
            self.assertEqual(len(pilot), 18)
            self.assertEqual(len(evidence), 21)
            self.assertEqual(receipt['checks']['diagnostic_network_attempts'], 0)
            self.assertFalse({'label', 'target', 'discounted', 'final_label'} & set(evidence[0]))

    def test_protected_input_change_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            path = root / 'data/raw/itad/7830.json'
            path.unlink()  # Only the temporary fixture symlink; the original is untouched.
            path.write_text('{}')
            with self.assertRaisesRegex(ValueError, 'protected input'):
                ground.run(root)


if __name__ == '__main__':
    unittest.main()
