"""Read-only EDA regressions: cohort, recorded units, cutoffs and frozen labels."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import eda_cohort_2000 as e
ARTIFACTS = None


class EDADataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import numpy as np
        import pandas as pd
        cls.np, cls.pd = np, pd
        cls.data = e.build()
        cls.tables, cls.stats = cls.data['tables'], cls.data['stats']
        cls.cohort = pd.read_csv(e.COHORT, keep_default_na=False)
        cls.frame = pd.read_csv(e.MODEL / 'modeling.csv', float_precision='round_trip')
        cls.manifest = e.read_json(e.MODEL / 'feature_manifest.json')

    def test_exact_original_membership_and_three_historical_rows_per_game(self):
        e.validate_modeling(self.cohort, self.frame, self.manifest, self.data['windows'])
        self.assertEqual(len(self.cohort), 2000)
        self.assertEqual(self.frame.groupby('appid').size().unique().tolist(), [3])
        self.assertEqual(set(self.tables['prices_by_game'].appid), set(self.cohort.AppID))
        self.assertEqual(set(self.tables['recurrence_by_game'].appid), set(self.cohort.AppID))

    def test_duplicate_wrong_year_cutoff_and_label_are_rejected(self):
        for name, value in [('appid', self.frame.appid.iloc[1]), ('sale_year', 2026),
                            ('prediction_cutoff_utc', '2025-01-01T00:00:00Z'), ('discount_observed', 9)]:
            bad = self.frame.copy(); bad.loc[0, name] = value
            if name == 'appid': bad.loc[0, 'sale_year'] = self.frame.sale_year.iloc[1]
            with self.assertRaises(ValueError): e.validate_modeling(self.cohort, bad, self.manifest, self.data['windows'])
        with self.assertRaises(ValueError): e.validate_modeling(self.cohort.iloc[:-1], self.frame, self.manifest, self.data['windows'])

    def test_release_years_chronological_and_each_game_once(self):
        r = self.tables['release_years']
        self.assertEqual(r.games.sum(), 2000)
        self.assertEqual(r.release_year.tolist(), list(range(1997, 2024)))
        self.assertEqual(int(r.loc[r.release_year.eq(2022), 'games'].iloc[0]), 327)
        self.assertEqual(self.stats['release_2015_or_later'], 1883)

    def test_exact_historical_label_counts_and_roles(self):
        r = self.tables['historical_labels']
        self.assertEqual(r.discount_observed.tolist(), [979, 1068, 983])
        self.assertEqual(r.no_discount_observed.tolist(), [1021, 932, 1017])
        self.assertEqual(r.role.tolist(), ['Development', 'Development', 'Held-out evaluation'])
        self.assertEqual((r.discount_observed + r.no_discount_observed).tolist(), [2000] * 3)

    def test_recurrence_counts_games_once_and_matches_3030_labels(self):
        r = self.tables['evidence_recurrence']
        self.assertEqual(r.games.tolist(), [741, 201, 345, 713])
        self.assertEqual(r.games.sum(), 2000)
        self.assertEqual((r.games * r.years_with_discount_observed).sum(), 3030)

    def test_recurrence_rejects_duplicate_or_missing_years(self):
        for bad in (self.pd.concat([self.frame, self.frame.iloc[:1]]), self.frame.iloc[1:]):
            with self.assertRaises(ValueError): e.evidence_recurrence(bad, self.pd)

    def test_price_measure_preserves_missing_zeros_and_extremes(self):
        p = self.tables['prices_by_game'].last_recorded_price_usd
        self.assertEqual(p.notna().sum(), 1918)
        self.assertEqual(p.isna().sum(), 82)
        self.assertEqual(p.eq(0).sum(), 2)
        self.assertAlmostEqual(p.max(), 199.99)
        self.assertAlmostEqual(p.median(), 5.54)
        self.assertEqual(p.lt(10).sum(), 1456)
        self.assertTrue(self.tables['prices_by_game'].loc[p.isna(), 'missing_reason'].ne('').all())

    def test_observation_unit_includes_every_game_and_zero_history(self):
        c = self.tables['observation_counts_by_game']
        self.assertEqual(len(c), 2000)
        self.assertTrue(c.appid.is_unique)
        self.assertEqual(c.pre_2025_price_observations.eq(0).sum(), 82)
        self.assertEqual(c.pre_2025_price_observations.median(), 32)
        self.assertEqual(c.pre_2025_price_observations.max(), 256)
        self.assertEqual(self.tables['observation_histogram']['count'].sum(), 2000)

    def test_historical_coverage_uses_separate_year_cutoffs_and_denominators(self):
        c = self.tables['coverage']
        for year in e.YEARS:
            group = c[c.sale_year.eq(year)]
            self.assertEqual(group.game_year_rows.sum(), 2000)
            self.assertEqual(group.coverage_group.tolist(), e.GROUPS)
            self.assertEqual(group.observation_cutoff_utc.unique().tolist(), [self.data['windows'][str(year)]['start_inclusive']])
            self.np.testing.assert_allclose(group.discount_observed_rate + group.no_discount_observed_rate, 1)
        r = c[c.sale_year.eq(2025)]
        self.assertEqual(r.game_year_rows.tolist(), [82, 538, 336, 1044])
        self.assertEqual(r.discount_observed.tolist(), [0, 19, 118, 846])

    def test_all_15_feature_missing_counts_reconcile_to_6000_rows(self):
        m = self.tables['missingness'].set_index('feature')
        self.assertEqual(len(m), 15)
        self.assertTrue(m.historical_game_year_rows.eq(6000).all())
        self.assertEqual(m.missing_count.value_counts().to_dict(), {0: 8, 253: 4, 1134: 3})
        self.assertTrue((m.missing_2023 + m.missing_2024 + m.missing_2025).eq(m.missing_count).all())
        for feature in m.index: self.assertEqual(m.loc[feature, 'missing_count'], self.frame[feature].isna().sum())

    def test_discount_units_are_raw_records_inside_corresponding_sale_windows(self):
        d = self.tables['discount_records']
        self.assertEqual(len(d), 3035)
        self.assertFalse(d.duplicated(['appid', 'source_record_index']).any())
        self.assertTrue(d.discount_percent.between(10, 95).all())
        self.assertTrue(d.recorded_price_usd.lt(d.regular_price_usd).all())
        for year in e.YEARS:
            r = d[d.sale_year.eq(year)]
            timestamps = self.pd.to_datetime(r.timestamp_utc, utc=True)
            window = self.data['windows'][str(year)]
            self.assertTrue((timestamps >= self.pd.Timestamp(window['start_inclusive'])).all())
            self.assertTrue((timestamps < self.pd.Timestamp(window['end_exclusive'])).all())

    def test_discount_exclusions_are_chart_only_and_fully_counted(self):
        excluded = self.tables['discount_exclusions']
        self.assertEqual(excluded.reason.value_counts().to_dict(), {'not_a_discount_observation': 24, 'conflicting_same_time_records': 2})
        self.assertEqual(len(excluded) + len(self.tables['discount_records']), 3061)
        self.assertEqual(self.frame.discount_observed.sum(), 3030)
        self.assertEqual(self.stats['discount_median'], 55)

    def test_histograms_cover_endpoints_without_clipping_or_zero_filling(self):
        result = e.histogram(self.pd.Series([0, 10, 20]), [0, 10, 20], self.np, self.pd)
        self.assertEqual(result['count'].tolist(), [1, 2])
        self.assertEqual(result.upper_inclusive.tolist(), [False, True])
        with self.assertRaises(ValueError): e.histogram(self.pd.Series([float('nan')]), [0, 10], self.np, self.pd)
        with self.assertRaises(ValueError): e.histogram(self.pd.Series([11]), [0, 10], self.np, self.pd)
        for key, expected in [('price_histogram', 1918), ('observation_histogram', 2000), ('discount_histogram', 3035)]:
            self.assertEqual(self.tables[key]['count'].sum(), expected)

    def test_all_6000_saved_count_indices_have_raw_cutoff_support(self):
        r = self.data['raw_validation']
        self.assertEqual(r['cache_files'], 2000)
        self.assertEqual(r['prior_record_uses'], 171868)
        self.assertEqual(r['sale_records'], 3061)
        self.assertEqual(r['successful_empty_histories'], 81)
        self.assertEqual(r['parse_failures'], 0)

    def test_exact_cutoff_and_ambiguous_price_do_not_enter_prior_counts(self):
        from datetime import datetime, timezone, timedelta
        cutoff = datetime(2025, 9, 29, 17, tzinfo=timezone.utc)
        items = [(dict(source_record_index=0, observation_kind='full_price'), cutoff - timedelta(seconds=1)),
                 (dict(source_record_index=1, observation_kind='discount'), cutoff),
                 (dict(source_record_index=2, observation_kind='discount'), cutoff + timedelta(seconds=1)),
                 (dict(source_record_index=3, observation_kind='ambiguous'), cutoff - timedelta(seconds=1))]
        self.assertEqual([r['source_record_index'] for r in e.prior_valid_records(items, cutoff)], [0])

    def test_existing_source_discrepancy_is_metadata_only(self):
        note = self.data['source_integrity_notes']
        self.assertTrue(note['original_manifest_hash_reproduced'])
        self.assertFalse(note['source_repaired'])
        self.assertEqual(e.digest(e.ROOT / note['file']), note['current_sha256'])
        self.assertEqual(len(e.read_json(e.ROOT / 'tests/scalable_artifact_hashes.json')), 219)

    def test_offline_guards_block_requests_models_external_commands_and_writes(self):
        for event, args in [('socket.connect', (None, None)), ('subprocess.Popen', (None, None, None, None)),
                            ('import', ('xgboost', None, None, None, None)), ('pickle.find_class', ('model', 'Class'))]:
            with self.assertRaises((RuntimeError, AssertionError, OSError)): sys.audit(event, *args)
        with self.assertRaises((ValueError, RuntimeError)):
            sys.audit('open', str(e.ROOT / 'reports/forbidden-eda-write'), 'w', 577)


class DeliveredEDATests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if ARTIFACTS is None: raise unittest.SkipTest('Requires --artifacts')
        cls.path = ARTIFACTS

    def test_checksums_and_eight_300dpi_white_figures(self):
        checks = e.read_json(self.path / 'checksums.json')
        self.assertEqual(set(checks), {p.name for p in self.path.iterdir() if p.is_file() and p.name != 'checksums.json'})
        for name, sha in checks.items(): self.assertEqual(e.digest(self.path / name), sha)
        self.assertEqual(e.io.figure_manifest(self.path), e.read_json(self.path / 'figure_manifest.json'))

    def test_summary_csvs_and_observation_units_match_sources(self):
        import pandas as pd
        for name in ['release_years', 'historical_labels', 'evidence_recurrence', 'coverage', 'missingness',
                     'price_histogram', 'observation_histogram', 'discount_histogram']:
            saved = pd.read_csv(self.path / (name + '.csv'), dtype={'coverage_group': str}, float_precision='round_trip')
            pd.testing.assert_frame_equal(saved, EDADataTests.data['tables'][name], check_dtype=False, check_exact=False, rtol=1e-13, atol=1e-13)
        self.assertEqual(len(pd.read_csv(self.path / 'prices_by_game.csv')), 2000)
        self.assertEqual(len(pd.read_csv(self.path / 'discount_records.csv')), 3035)

    def test_every_figure_has_question_source_unit_takeaway_and_limitation(self):
        import pandas as pd
        d = pd.read_csv(self.path / 'figure_captions.csv')
        self.assertEqual(len(d), 8)
        for field in ['question', 'source', 'unit', 'takeaway', 'limitation']:
            self.assertTrue(d[field].notna().all())
        body = (self.path / 'README.md').read_text()
        self.assertIn(e.NOTICE, body)
        self.assertIn('not verified nonparticipation', body)
        self.assertIn('held-out 2025', body)
        self.assertEqual(len(pd.read_csv(self.path / 'predictor_dictionary.csv')), 15)

    def test_independent_reproduction_and_protected_artifacts_preserved(self):
        r = e.read_json(self.path / 'reproduction.json')
        self.assertTrue(r['byte_identical']); self.assertTrue(r['independent_source_reload'])
        self.assertEqual(r['png_files'], 8)
        integrity = e.io.verify_preservation(e.read_json(self.path / 'phase_start_checksums.json'))
        self.assertEqual(integrity['protected_artifacts_preserved'], 219)
        self.assertEqual(integrity['historical_baseline_matches'], 218)
        validation = e.read_json(self.path / 'validation.json')
        for name, sha in validation['source_sha256'].items(): self.assertEqual(e.digest(e.ROOT / name), sha)


if __name__ == '__main__': unittest.main()
