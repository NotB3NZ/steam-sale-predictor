"""Phase 8C saved-output regressions; no fitting, inference, or model loading."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import visualize_cohort_2026 as v

ARTIFACTS = None


class FrozenVisualizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import pandas as pd
        cls.pd = pd
        cls.data = v.build()
        cls.features = pd.read_csv(v.SOURCE / 'features_2026.csv', float_precision='round_trip')
        cls.approved = v.read_json(v.SOURCE / 'feature_schema_manifest.json')['predictor_order']

    def test_exact_frozen_totals_scores_and_correlation(self):
        d = self.data
        self.assertEqual(d['overall']['games'], 2000)
        self.assertEqual(d['overall']['predicted_positives'], 1026)
        self.assertEqual(d['overall']['predicted_operational_zeros'], 974)
        self.assertAlmostEqual(d['overall']['probability_mean'], .49964911729330197, places=14)
        self.assertAlmostEqual(d['overall']['probability_median'], .7096369862556458, places=14)
        self.assertAlmostEqual(d['rho'], .892484082231661, places=14)

    def test_coverage_boundary_partition(self):
        series = self.pd.Series([0, 1, 9, 10, 29, 30, 100000])
        self.assertEqual(v.coverage_groups(series).tolist(), ['0', '1-9', '1-9', '10-29', '10-29', '30+', '30+'])
        for invalid in ([-1], [.5], [float('nan')], [float('inf')]):
            with self.assertRaises(ValueError): v.coverage_groups(self.pd.Series(invalid))

    def test_saved_coverage_counts_and_predicted_rates(self):
        c = self.data['coverage']
        self.assertEqual(c.games.tolist(), [81, 505, 295, 1119])
        self.assertEqual(c.predicted_positives.tolist(), [0, 6, 74, 946])
        self.assertEqual(c.predicted_operational_zeros.tolist(), [81, 499, 221, 173])
        self.assertEqual(c.games.sum(), 2000)
        self.assertEqual(c.predicted_positives.sum(), 1026)
        for row in c.itertuples():
            self.assertAlmostEqual(row.predicted_positive_rate, row.predicted_positives / row.games)

    def test_histogram_reconciles_and_preserves_end_bins(self):
        h = self.data['histogram']
        self.assertEqual(h.games.sum(), 2000)
        self.assertEqual(h.games.iloc[:10].sum(), 974)
        self.assertEqual(h.games.iloc[10:].sum(), 1026)
        self.assertEqual(h.games.iloc[:2].sum(), 754)
        self.assertEqual(h.games.iloc[-2:].sum(), 656)
        self.assertEqual(h.upper_inclusive.tolist(), [False] * 19 + [True])

    def test_historical_rates_are_observed_labels_and_same_cohort(self):
        rates = self.data['rates']
        self.assertEqual(rates.sale_year.tolist(), [2023, 2024, 2025, 2026])
        self.assertEqual(rates.operational_positive.tolist(), [979, 1068, 983, 1026])
        self.assertEqual(rates.games.tolist(), [2000] * 4)
        self.assertIn('no verified outcomes', rates.kind.iloc[-1])
        self.assertTrue(rates.kind.iloc[:3].str.contains('observed').all())

    def test_all_336_missing_vectors_are_predicted_zero(self):
        s = self.data['status'].iloc[1]
        self.assertEqual(s.games, 336)
        self.assertEqual(s.predicted_positives, 0)
        self.assertEqual(s.predicted_operational_zeros, 336)
        self.assertLess(s.probability_max, .5)
        complete = self.data['status'].iloc[0]
        self.assertEqual(complete.predicted_operational_zeros, 638)

    def test_exact_null_patterns_and_sparse_observation_relationship(self):
        patterns = self.data['patterns']
        self.assertEqual(patterns.missing_predictor_count.tolist(), [0, 3, 7])
        self.assertEqual(patterns.games.tolist(), [1664, 255, 81])
        pred = self.data['pred']
        no_price = pred[pred.missing_feature_count.eq(7)]
        no_discount = pred[pred.missing_feature_count.eq(3)]
        self.assertTrue(no_price.prior_price_record_count.eq(0).all())
        self.assertTrue(no_discount.prior_price_record_count.between(1, 9).all())
        self.assertTrue(pred.loc[pred.missing_feature_count.gt(0), 'prior_discount_count'].eq(0).all())
        self.assertEqual(len(json.loads(patterns.missing_feature_names.iloc[1])), 3)
        self.assertEqual(len(json.loads(patterns.missing_feature_names.iloc[2])), 7)

    def test_missingness_denominators_use_predicted_class(self):
        rows = self.data['missing_by_class']
        self.assertEqual(len(rows), 30)
        self.assertTrue(rows.loc[rows.predicted_operational_label.eq(1), 'missing'].eq(0).all())
        zeros = rows[rows.predicted_operational_label.eq(0)].set_index('feature')
        self.assertAlmostEqual(zeros.loc['mean_prior_discount_pct', 'missing_percent'], 336 / 974 * 100)
        self.assertEqual(zeros.loc['last_observed_price', 'missing'], 81)
        self.assertEqual(zeros.loc['game_age_days', 'missing'], 0)

    def test_ranking_uses_full_precision_and_ascending_appid_ties(self):
        frame = self.pd.DataFrame(dict(appid=[3, 1, 2], predicted_probability=[.9, .9, .1]))
        self.assertEqual(v.rank(frame, True).appid.tolist(), [1, 3, 2])
        self.assertEqual(v.rank(frame, False).appid.tolist(), [2, 1, 3])
        self.assertEqual(self.data['ranks']['top'].appid.iloc[:3].tolist(), [252310, 514990, 536220])
        self.assertEqual(self.data['ranks']['bottom'].appid.iloc[:3].tolist(), [1934650, 2133940, 2145480])

    def test_invalid_probability_class_cohort_cutoff_and_coverage_rejected(self):
        pred = self.data['pred']
        for column, value in [('predicted_probability', float('nan')), ('predicted_probability', 1.01),
                              ('predicted_operational_label', 7), ('prediction_cutoff_utc', '2026-10-02T17:00:00Z'),
                              ('coverage_group', '0'), ('missing_feature_count', 100)]:
            bad = pred.copy(); bad.loc[0, column] = value
            with self.assertRaises(ValueError): v.validate_rows(bad, self.features, self.approved)
        with self.assertRaises(ValueError): v.validate_rows(pred.iloc[:-1], self.features, self.approved)
        bad = pred.copy(); bad.loc[0, 'appid'] = pred.appid.iloc[1]
        with self.assertRaises(ValueError): v.validate_rows(bad, self.features, self.approved)

    def test_blank_feature_cells_remain_missing_and_observed_zero_stays_zero(self):
        f = self.features
        self.assertEqual(f.last_observed_price.isna().sum(), 81)
        self.assertEqual(f.mean_prior_discount_pct.isna().sum(), 336)
        self.assertTrue(f.loc[f.prior_price_record_count.eq(0), 'prior_discount_count'].eq(0).all())
        self.assertTrue(f.last_observed_discount_pct.eq(0).any())

    def test_source_digest_verification_rejects_tampering(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / 'input.csv').write_text('frozen\n')
            (directory / 'checksums.json').write_text(json.dumps({'input.csv': '0' * 64}))
            with self.assertRaisesRegex(ValueError, 'Frozen checksum mismatch'): v.verify_manifest(directory)

    def test_offline_guards_block_network_external_commands_models_and_writes(self):
        for event, args in [('socket.connect', (None, None)), ('subprocess.Popen', (None, None, None, None)),
                            ('import', ('xgboost', None, None, None, None)), ('pickle.find_class', ('model', 'Class'))]:
            with self.assertRaises((RuntimeError, AssertionError, OSError)): sys.audit(event, *args)
        with self.assertRaises((ValueError, RuntimeError)):
            sys.audit('open', str(v.ROOT / 'reports/forbidden-phase8c-write'), 'w', 577)

    def test_preexisting_serialization_discrepancy_is_proven_without_repair(self):
        audit = self.data['source_integrity_notes']
        self.assertTrue(audit['original_manifest_hash_reproduced'])
        self.assertTrue(audit['scores_classes_and_cohort_unchanged'])
        self.assertFalse(audit['source_repaired'])
        self.assertEqual([r['appid'] for r in audit['name_discrepancies']], [1518000, 2402900])
        self.assertEqual(v.digest(v.SOURCE / 'predictions_2026.csv'), audit['current_sha256'])


class DeliveredArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if ARTIFACTS is None: raise unittest.SkipTest('Delivered artifact checks require --artifacts')
        cls.path = ARTIFACTS
        cls.data = v.build()

    def test_complete_checksums_and_png_design_metadata(self):
        checks = v.read_json(self.path / 'checksums.json')
        self.assertEqual(set(checks), {p.name for p in self.path.iterdir() if p.is_file() and p.name != 'checksums.json'})
        for name, sha in checks.items(): self.assertEqual(v.digest(self.path / name), sha)
        manifest = v.figure_manifest(self.path)
        self.assertEqual(manifest, v.read_json(self.path / 'figure_manifest.json'))

    def test_saved_csv_values_match_frozen_predictions_and_patterns(self):
        import pandas as pd
        for name, source in [('coverage_summary.csv', 'coverage'), ('missingness_patterns.csv', 'patterns'),
                             ('missingness_by_predicted_class.csv', 'missing_by_class'), ('missingness_status_summary.csv', 'status')]:
            saved = pd.read_csv(self.path / name, float_precision='round_trip', dtype={'coverage_group': str}, keep_default_na=False)
            # CSV has no dtype schema: integral-valued count summaries may be
            # inferred as integer even when computed as float. Verify values.
            pd.testing.assert_frame_equal(saved, self.data[source], check_exact=False, check_dtype=False, rtol=1e-13, atol=1e-13)
        self.assertEqual(len(pd.read_csv(self.path / 'missing_predictor_games.csv')), 336)

    def test_method_warning_and_no_outcome_evaluation_prominent(self):
        for name in ('README.md', 'key_findings.md', 'figure_captions.md'):
            body = (self.path / name).read_text()
            self.assertIn(v.WARNING, body)
        body = (self.path / 'README.md').read_text()
        self.assertIn(v.CUTOFF, body)
        self.assertIn('No independent 2026 outcome evaluation has been conducted', body)
        self.assertIn('Operational zeros do not prove nonparticipation', body)
        self.assertEqual(len(list(self.path.glob('*.png'))), 8)

    def test_independent_byte_reproduction_and_phase_start_integrity(self):
        report = v.read_json(self.path / 'reproduction.json')
        self.assertTrue(report['byte_identical'])
        self.assertTrue(report['independent_frozen_csv_reload'])
        self.assertEqual(report['png_files'], 8)
        result = v.verify_preservation(v.read_json(self.path / 'phase_start_checksums.json'))
        self.assertEqual(result['historical_baseline_matches'], 218)
        self.assertEqual(result['protected_artifacts_preserved'], 219)


if __name__ == '__main__': unittest.main()
