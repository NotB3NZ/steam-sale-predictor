"""Offline Phase 5B.1 regression and synthetic methodology checks."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import shutil
import socket
import tempfile
import unittest
from unittest.mock import patch

import test_autumn_evidence_audit as prior_tests
raw = prior_tests.raw

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('coverage_diagnostics', ROOT / 'src/05_investigate_sale_coverage.py')
coverage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(coverage)
audit = coverage.audit
WINDOW = audit.canonical_windows(ROOT)[2023]
GAME = {'AppID': '1', 'Name': 'Synthetic', 'release_date': '2020-01-01'}


def pair(history):
    records, issues, other = audit.parse_history(history)
    if issues:
        raise AssertionError(issues)
    scoped = [r for r in records if audit.utc_stamp(r['timestamp_utc']) < coverage.CUTOFF]
    return coverage.summarize_pair(GAME, 2023, WINDOW, scoped,
                                  {'cache_status': 'ok', 'issue': '', 'raw_history_record_count': len(history)},
                                  len(records) - len(scoped))


class DiagnosticTests(unittest.TestCase):
    def test_exact_pre_in_post_partition_and_nearest(self):
        row = pair([raw('2023-11-28T18:00:00Z'), raw('2023-11-19T18:00:00Z'),
                    raw('2023-11-21T17:59:59.999999Z'), raw('2023-11-21T18:00:00Z', 5, 10, 50),
                    raw('2023-11-28T17:59:59.999999Z'), raw('2023-12-01T18:00:00Z')])
        self.assertEqual((row['pre_record_count'], row['in_window_record_count'], row['post_record_count']), (2, 2, 2))
        self.assertEqual(row['pre_source_record_index'], 2)
        self.assertEqual(row['post_source_record_index'], 0)
        self.assertEqual(row['post_gap_days'], 0)
        self.assertAlmostEqual(row['pre_gap_days'], 1e-6 / 86400)
        self.assertEqual(row['evidence_category'], 'A')
        self.assertTrue(row['in_window_mixed_discount_full_price'])
        self.assertEqual(row['in_window_discount_count'], 1)
        events = json.loads(row['observed_sequence_json'])
        self.assertEqual(len(events), 8)
        self.assertEqual([e['timestamp_utc'] for e in events], sorted((e['timestamp_utc'] for e in events),
                         key=audit.utc_stamp))

    def test_missing_records_are_null_not_zero(self):
        row = pair([])
        self.assertEqual(row['evidence_category'], 'D')
        for side in ('pre', 'post'):
            self.assertEqual(row[f'{side}_observed_state'], 'missing')
            self.assertEqual(row[f'{side}_gap_days'], '')
            self.assertEqual(row[f'{side}_price'], '')
            self.assertEqual(json.loads(row[f'{side}_nearest_records_json']), [])
        self.assertEqual(row['surrounding_interval_days'], '')
        self.assertTrue(row['empty_raw_history'])
        self.assertTrue(row['pattern_no_unambiguous_latest_pre_state'])

    def test_latest_null_is_not_skipped_and_no_carry_forward(self):
        row = pair([raw('2023-11-19T18:00:00Z'), dict(raw('2023-11-20T18:00:00Z'), deal=None)])
        self.assertEqual(row['pre_observed_state'], 'ambiguous')
        self.assertEqual(row['pre_price'], '')
        self.assertEqual(row['pre_source_record_index'], 1)
        self.assertEqual(row['pre_price_usable_count'], 1)
        self.assertEqual(row['pre_null_deal_count'], 1)
        self.assertEqual(row['in_window_full_price_count'], 0)
        self.assertEqual(row['evidence_category'], 'D')

    def test_null_and_contradictory_inside_remain_category_c(self):
        row = pair([dict(raw('2023-11-22T18:00:00Z'), deal=None), raw('2023-11-23T18:00:00Z', 10, 10, 50)])
        self.assertEqual(row['evidence_category'], 'C')
        self.assertEqual(row['in_window_ambiguous_count'], 2)
        self.assertEqual(row['in_window_null_deal_count'], 1)
        self.assertEqual(row['in_window_full_price_count'], 0)

    def test_nearest_conflicts_even_same_kind_are_ambiguous(self):
        row = pair([raw('2023-11-20T18:00:00Z', 10, 10, 0), raw('2023-11-20T18:00:00Z', 20, 20, 0),
                    raw('2023-11-28T18:00:00Z', 5, 10, 50), raw('2023-11-28T18:00:00Z')])
        self.assertEqual(row['pre_observed_state'], 'ambiguous')
        self.assertEqual(row['post_observed_state'], 'ambiguous')
        self.assertTrue(row['pre_nearest_conflict'])
        self.assertTrue(row['post_nearest_conflict'])
        self.assertEqual(row['history_conflicting_timestamp_groups'], 2)
        self.assertEqual(row['pre_source_record_index'], 0)
        self.assertEqual(json.loads(row['pre_nearest_raw_indices_json']), [0, 1])
        self.assertEqual(row['evidence_category'], 'D')

    def test_identical_ties_preserved_without_conflict(self):
        item = raw('2023-11-20T18:00:00Z')
        row = pair([item, copy.deepcopy(item)])
        self.assertEqual(row['pre_record_count'], 2)
        self.assertEqual(row['pre_observed_state'], 'full_price')
        self.assertFalse(row['pre_nearest_conflict'])
        self.assertEqual(json.loads(row['pre_nearest_raw_indices_json']), [0, 1])

    def test_gaps_elapsed_days_and_no_inferred_states(self):
        row = pair([raw('2023-11-15T06:00:00Z'), raw('2023-12-03T06:00:00Z')])
        self.assertEqual(row['pre_gap_days'], 6.5)
        self.assertEqual(row['post_gap_days'], 4.5)
        self.assertEqual(row['surrounding_interval_days'], 18)
        self.assertTrue(row['pattern_pre_full_price_no_direct_discount'])
        self.assertEqual(row['in_window_records_json'], '[]')
        self.assertEqual(row['evidence_category'], 'D')

    def test_discount_patterns_overlap_and_category_a_not_contradiction(self):
        row = pair([raw('2023-11-20T18:00:00Z', 5, 10, 50), raw('2023-11-22T18:00:00Z', 5, 10, 50)])
        self.assertTrue(row['pattern_direct_in_window_discount'])
        self.assertFalse(row['pattern_pre_discount_no_direct_discount'])
        self.assertTrue(row['pattern_surrounding_evidence_requires_review'])
        row2 = pair([raw('2023-11-20T18:00:00Z', 5, 10, 50)])
        self.assertTrue(row2['pattern_pre_discount_no_direct_discount'])
        self.assertEqual(row2['evidence_category'], 'D')

    def test_2026_exclusion_and_cutoff_exact(self):
        row = pair([raw('2025-12-31T23:59:59.999999Z'), raw('2026-01-01T00:00:00Z'),
                    raw('2026-10-01T00:00:00Z')])
        self.assertEqual(row['analyzed_history_record_count'], 1)
        self.assertEqual(row['records_excluded_at_or_after_2026'], 2)
        self.assertEqual(row['post_source_record_index'], 0)
        self.assertNotIn('2026-10-01', row['observed_sequence_json'])
        self.assertEqual(pair([raw('2026-01-01T00:00:00Z')])['post_observed_state'], 'missing')

    def test_real_calendar_matches_three_exact_events(self):
        windows = audit.canonical_windows(ROOT)
        self.assertEqual(set(windows), {2023, 2024, 2025})
        self.assertEqual(audit.fmt(windows[2023][2]), '2023-11-21T18:00:00Z')
        self.assertEqual(audit.fmt(windows[2024][3]), '2024-12-04T18:00:00Z')
        self.assertEqual(audit.fmt(windows[2025][2]), '2025-09-29T17:00:00Z')

    def test_parser_steam_only_and_timestamp_validation(self):
        records, issues, other = audit.parse_history([raw('2023-11-20T18:00:00Z', shop=35),
                                                      raw('2023-11-20T18:00:00Z'),
                                                      raw('2023-11-20T18:00:00')])
        self.assertEqual(other, 1)
        self.assertEqual(len(issues), 1)
        self.assertEqual([r['shop_id'] for r in records], [61])

    def test_statistics_missing_and_linear_percentiles(self):
        stats = coverage.gap_stats([None, '', 0, 10])
        self.assertEqual(stats['n'], 2)
        self.assertEqual(stats['missing'], 2)
        self.assertEqual(stats['median'], 5)
        self.assertEqual(stats['p90'], 9)
        self.assertEqual(coverage.gap_stats([''])['mean'], '')
        groups = coverage.grouped_gap_statistics([])
        self.assertEqual(len(groups), 153)
        self.assertTrue(all(r['n'] == r['missing'] == 0 and r['median'] == '' for r in groups))

    def test_sensitivity_separates_states_and_threshold_edges(self):
        base = {'appid': '1', 'sale_year': 2023, 'evidence_category': 'D', 'pre_observed_state': 'full_price',
                'post_observed_state': 'full_price', 'pre_gap_days': 7, 'post_gap_days': 7}
        rows = [base, dict(base, appid='2', pre_gap_days=7.000001, post_gap_days='', post_observed_state='missing'),
                dict(base, appid='3', pre_observed_state='discount'),
                dict(base, appid='4', pre_observed_state='missing', pre_gap_days=''),
                dict(base, appid='5', pre_observed_state='ambiguous'),
                dict(base, appid='6', evidence_category='A')]
        results = coverage.sensitivity_rows(rows)
        self.assertEqual(len(results), 384)
        get = lambda scenario, state: next(r for r in results if r['scenario'] == scenario
                                          and r['sale_year'] == 'all' and r['evidence_category'] == 'all_non_A'
                                          and r['pre_observed_state'] == state)
        full = get('pre_within_7_days', 'full_price')
        self.assertEqual(full['stratum_pair_count'], 2)
        self.assertEqual(full['satisfying_recency_count'], 1)
        self.assertEqual(full['both_sides_within_limit_count'], 1)
        self.assertEqual(get('pre_within_7_days', 'discount')['satisfying_recency_count'], 1)
        self.assertEqual(get('pre_within_7_days', 'ambiguous')['satisfying_recency_count'], 1)
        self.assertEqual(get('pre_within_7_days', 'missing')['satisfying_recency_count'], 0)
        self.assertEqual(get('unrestricted', 'missing')['satisfying_recency_count'], 1)
        self.assertEqual(get('unrestricted', 'full_price')['post_gap_days_missing'], 1)
        self.assertEqual(get('unrestricted', 'full_price')['post_gap_days_mean'], 7)

    def test_same_day_release_hour_remains_unresolved(self):
        row = coverage.summarize_pair(dict(GAME, release_date='2023-11-21'), 2023, WINDOW, [],
                                     {'cache_status': 'ok', 'issue': '', 'raw_history_record_count': 0})
        self.assertTrue(row['eligible_for_sale'])
        self.assertIn('exact release hour unavailable', row['eligibility_reason'])
        self.assertIn('release_hour_unknown', row['interpretation_cues'])
        self.assertEqual(row['evidence_category'], 'D')

    def test_network_guard_blocks_attempts(self):
        with self.assertRaises(AssertionError):
            with coverage.offline_guard():
                socket.getaddrinfo('example.com', 443)

    def test_no_final_label_columns_or_daily_states(self):
        row = pair([raw('2023-11-20T18:00:00Z')])
        self.assertFalse({'label', 'target', 'discounted'} & set(row))
        self.assertEqual(len(json.loads(row['observed_sequence_json'])), 3)


class PipelineTests(unittest.TestCase):
    def fixture(self, root):
        prior_tests.IntegrationTests().make_fixture(root)
        with contextlib.redirect_stdout(io.StringIO()):
            audit.run(root)
        for path in (coverage.DOC_NOTE, 'src/05_investigate_sale_coverage.py', 'tests/test_autumn_sale_coverage.py'):
            dest = root / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / path, dest)

    def test_complete_offline_pipeline_reconciles_and_preserves_all_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            before = coverage.protected_hashes(root)
            with patch.object(socket.socket, 'connect', side_effect=AssertionError('Forbidden')):
                rows, scenarios, receipt = coverage.run(root)
                first = {p: (root / p).read_bytes() for p in coverage.OUTPUTS}
                coverage.run(root)
            self.assertEqual(first, {p: (root / p).read_bytes() for p in coverage.OUTPUTS})
            self.assertEqual(before, coverage.protected_hashes(root))
            self.assertEqual(len(rows), 300)
            self.assertEqual(len({(r['appid'], r['sale_year']) for r in rows}), 300)
            self.assertEqual({r['sale_year'] for r in rows}, {2023, 2024, 2025})
            self.assertEqual(len(scenarios), 384)
            self.assertEqual(receipt['checks']['diagnostic_network_attempts'], 0)
            old = {(r['AppID'], int(r['sale_year'])): r['evidence_category'] for r in
                   audit.read_csv(root / 'data/intermediate/autumn_sale_evidence_audit.csv')}
            self.assertTrue(all(r['evidence_category'] == old[(r['appid'], r['sale_year'])] for r in rows))
            self.assertTrue(all(r['in_window_record_count'] == r['in_window_discount_count'] +
                                r['in_window_full_price_count'] + r['in_window_ambiguous_count'] for r in rows))

    def test_changed_prior_category_fails_reconciliation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            path = root / 'data/intermediate/autumn_sale_evidence_audit.csv'
            old = audit.read_csv(path)
            old[0]['evidence_category'] = 'D' if old[0]['evidence_category'] == 'A' else 'A'
            audit.write_csv(path, old, list(old[0]))
            with self.assertRaisesRegex(ValueError, 'category changed'):
                coverage.run(root)

    def test_validation_rejects_gap_pattern_and_scenario_corruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            rows, scenarios, _ = coverage.run(root)
            games = audit.read_csv(root / 'data/intermediate/pilot_games.csv')
            manifest = {r['AppID']: r for r in audit.read_csv(root / 'data/intermediate/itad_collection_manifest.csv')}
            histories = {g['AppID']: audit.load_cache(root, g, manifest[g['AppID']])[0] for g in games}
            old_rows = audit.read_csv(root / 'data/intermediate/autumn_sale_evidence_audit.csv')
            old_records = audit.read_csv(root / 'data/intermediate/autumn_sale_evidence_records.csv')
            validate = lambda r, s: coverage.validate(r, s, histories, old_rows, old_records, audit.canonical_windows(root))
            corrupted = copy.deepcopy(rows)
            corrupted[0]['post_gap_days'] = 99
            with self.assertRaisesRegex(ValueError, 'Gap calculation'):
                validate(corrupted, scenarios)
            corrupted = copy.deepcopy(rows)
            corrupted[0]['pattern_direct_in_window_discount'] = False
            with self.assertRaisesRegex(ValueError, 'Diagnostic pattern'):
                validate(corrupted, scenarios)
            scenarios[0]['satisfying_recency_count'] += 1
            with self.assertRaisesRegex(ValueError, 'Sensitivity membership'):
                validate(rows, scenarios)

    def test_modified_frozen_input_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            (root / 'data/raw/itad/1.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'Frozen Phase 4'):
                coverage.run(root)


if __name__ == '__main__':
    unittest.main()
