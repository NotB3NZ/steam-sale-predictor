"""Offline Phase 6 tests; adversarial fixtures never modify historical inputs."""
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
spec = importlib.util.spec_from_file_location('autumn_features', ROOT / 'src/07_build_autumn_features.py')
features = importlib.util.module_from_spec(spec)
spec.loader.exec_module(features)
WINDOWS = features.audit.canonical_windows(ROOT)
START = WINDOWS[2023][2]
GAME = {'AppID': '1', 'release_date': '2020-01-01'}


def parsed(history):
    records, issues, other = features.audit.parse_history(history)
    if issues:
        raise ValueError(issues)
    return records


def price(history, cutoff=START):
    return features.price_features(parsed(history), cutoff)


def label(year=2023, target='0'):
    return dict(appid='1', sale_year=str(year), sale_start_utc=features.audit.fmt(WINDOWS[year][2]),
                discount_observed=target, evidence_category='D', pu_status='unlabeled')


class TemporalFeatureTests(unittest.TestCase):
    def test_verified_exact_cutoffs(self):
        self.assertEqual([features.audit.fmt(WINDOWS[y][2]) for y in WINDOWS],
                         ['2023-11-21T18:00:00Z', '2024-11-27T18:00:00Z', '2025-09-29T17:00:00Z'])

    def test_immediately_before_cutoff_included(self):
        row, p = price([prior.raw(features.audit.fmt(START - timedelta(microseconds=1)))])
        self.assertEqual(row['prior_price_record_count'], 1)
        self.assertGreater(row['days_since_last_price_record'], 0)
        self.assertEqual(p['cutoff_violations'], 0)

    def test_exact_cutoff_excluded(self):
        row, _ = price([prior.raw(features.audit.fmt(START), 1, 10, 90)])
        self.assertEqual(row, price([])[0])

    def test_timezone_equivalent_cutoff_excluded(self):
        self.assertEqual(price([prior.raw('2023-11-21T10:00:00-08:00')])[0], price([])[0])

    def test_adversarial_current_sale_post_sale_and_future_records_invariant(self):
        base = [prior.raw('2023-11-20T18:00:00Z')]
        expected = price(base)[0]
        for timestamp in (features.audit.fmt(START), '2023-11-22T18:00:00Z', '2023-11-28T18:00:00Z',
                          '2024-11-27T18:00:00Z', '2025-10-01T17:00:00Z', '2026-11-01T00:00:00Z'):
            with self.subTest(timestamp=timestamp):
                self.assertEqual(price(base + [prior.raw(timestamp, 1, 10, 90)])[0], expected)

    def test_future_currency_and_ambiguity_do_not_influence_features(self):
        base = [prior.raw('2023-11-20T18:00:00Z')]
        euro = prior.raw('2025-10-01T17:00:00Z', 1, 10, 90)
        for money in ('price', 'regular'):
            euro['deal'][money]['currency'] = 'EUR'
        ambiguous = dict(prior.raw('2026-01-01T00:00:00Z'), deal=None)
        self.assertEqual(price(base + [euro, ambiguous])[0], price(base)[0])

    def test_all_earlier_feature_vectors_unchanged_by_future_year(self):
        pairs = [(1, y) for y in WINDOWS]
        base = parsed([prior.raw('2023-11-20T18:00:00Z')])
        original = features.build_features(pairs, {1: GAME}, {1: base}, WINDOWS)[0]
        future = parsed([prior.raw('2026-01-01T00:00:00Z', 1, 10, 90)])
        self.assertEqual(original, features.build_features(pairs, {1: GAME}, {1: base + future}, WINDOWS)[0])

    def test_prior_year_sale_observation_is_valid_past_information(self):
        row, _ = price([prior.raw('2023-11-22T18:00:00Z', 5, 10, 50)], WINDOWS[2024][2])
        self.assertEqual(row['prior_discount_count'], 1)

    def test_target_and_category_changes_cannot_change_predictors(self):
        rows = [label()]
        records = parsed([prior.raw('2023-11-20T18:00:00Z')])
        original = features.build_features(features.authorized_pairs(rows, WINDOWS), {1: GAME}, {1: records}, WINDOWS)[0]
        mutated = copy.deepcopy(rows)
        mutated[0].update(discount_observed='1', evidence_category='A', pu_status='positive',
                          supporting_record_indices='[999]', in_window_record_count='999', empty_raw_history='True',
                          eligibility_status='something_else', label_limitation_flag='False')
        changed = features.build_features(features.authorized_pairs(mutated, WINDOWS), {1: GAME}, {1: records}, WINDOWS)[0]
        self.assertEqual(original, changed)
        self.assertEqual(features.modeling_table(changed, mutated, WINDOWS)[0]['discount_observed'], 1)
        self.assertNotIn('discount_observed', original[0])


class PriceFeatureTests(unittest.TestCase):
    def test_valid_price_and_discount_observation_counts(self):
        row, _ = price([prior.raw('2023-11-18T18:00:00Z'), prior.raw('2023-11-19T18:00:00Z', 5, 10, 50),
                        prior.raw('2023-11-20T18:00:00Z', 2, 10, 80)])
        self.assertEqual(row['prior_price_record_count'], 3)
        self.assertEqual(row['prior_discount_count'], 2)
        self.assertEqual(row['prior_discount_rate'], 2 / 3)
        self.assertEqual(row['max_prior_discount_pct'], 80)
        self.assertEqual(row['mean_prior_discount_pct'], 65)
        self.assertEqual(row['days_since_last_discount'], 1)
        self.assertEqual(row['last_observed_price'], 2)
        self.assertEqual(row['last_observed_discount_pct'], 80)

    def test_no_valid_history_missingness(self):
        row, _ = price([])
        for field in features.PRICE:
            self.assertEqual(row[field], 0 if field in ('prior_price_record_count', 'prior_discount_count',
                                                       'has_prior_price_history', 'has_prior_discount_observation') else None)

    def test_no_prior_discount_missingness(self):
        row, _ = price([prior.raw('2023-11-20T18:00:00Z')])
        self.assertEqual(row['prior_discount_rate'], 0)
        self.assertEqual(row['has_prior_price_history'], 1)
        self.assertEqual(row['has_prior_discount_observation'], 0)
        for f in ('days_since_last_discount', 'max_prior_discount_pct', 'mean_prior_discount_pct'):
            self.assertIsNone(row[f])

    def test_null_ambiguous_and_invalid_price_do_not_enter_denominator(self):
        null = dict(prior.raw('2023-11-20T18:00:00Z'), deal=None)
        row, p = price([null, prior.raw('2023-11-19T18:00:00Z', 5, 10, 0),
                        prior.raw('2023-11-18T18:00:00Z', -1, 10, 50)])
        self.assertEqual(row, price([])[0])
        self.assertEqual(p['pre_cutoff_ambiguous_count'], 3)
        self.assertEqual(p['pre_cutoff_null_deal_count'], 1)
        self.assertEqual(p['ambiguous_prior_raw_indices'], [2, 1, 0])

    def test_steam_only(self):
        records = [features.audit.observation(prior.raw('2023-11-20T18:00:00Z', 1, 10, 90, shop=60), 0)]
        self.assertEqual(features.price_features(records, START)[0], price([])[0])

    def test_no_campaign_inference_or_deduplication(self):
        repeated = prior.raw('2023-11-20T18:00:00Z', 5, 10, 50)
        row, _ = price([repeated, copy.deepcopy(repeated), prior.raw('2023-11-19T18:00:00Z', 5, 10, 50)])
        self.assertEqual(row['prior_discount_count'], 3)
        self.assertEqual(row['prior_price_record_count'], 3)
        self.assertNotIn('campaign_count', row)

    def test_no_interpolation_or_forward_fill(self):
        old = prior.raw('2021-01-01T00:00:00Z', 5, 10, 50)
        row, _ = price([old])
        self.assertEqual(row['prior_price_record_count'], 1)
        self.assertEqual(row['last_observed_price'], 5)
        self.assertEqual(row['days_since_last_price_record'], (START - features.audit.utc_stamp(old['timestamp'])).total_seconds() / 86400)
        self.assertGreater(row['days_since_last_price_record'], 1000)

    def test_newer_ambiguous_record_is_not_a_valid_price(self):
        null = dict(prior.raw('2023-11-20T18:00:00Z'), deal=None)
        row, p = price([prior.raw('2023-11-19T18:00:00Z'), null])
        self.assertEqual(row['days_since_last_price_record'], 2)
        self.assertEqual(p['pre_cutoff_ambiguous_count'], 1)

    def test_mixed_currencies_withhold_money_not_valid_dimensionless_cuts(self):
        euro = prior.raw('2023-11-20T18:00:00Z', 2, 10, 80)
        for money in ('price', 'regular'):
            euro['deal'][money]['currency'] = 'EUR'
        row, p = price([prior.raw('2023-11-19T18:00:00Z', 5, 10, 50), euro])
        self.assertIsNone(row['last_observed_price'])
        self.assertEqual(row['mean_prior_discount_pct'], 65)
        self.assertEqual(row['last_observed_discount_pct'], 80)
        self.assertEqual(p['monetary_missing_reason'], 'mixed_prior_currencies')

    def test_non_USD_amount_is_not_compared_to_USD_game_amounts(self):
        euro = prior.raw('2023-11-20T18:00:00Z')
        for money in ('price', 'regular'):
            euro['deal'][money]['currency'] = 'EUR'
        row, p = price([euro])
        self.assertIsNone(row['last_observed_price'])
        self.assertEqual(p['monetary_missing_reason'], 'non_USD_prior_currency')

    def test_mismatched_currency_is_ambiguous(self):
        bad = prior.raw('2023-11-20T18:00:00Z', 5, 10, 50)
        bad['deal']['regular']['currency'] = 'EUR'
        self.assertEqual(price([bad])[0], price([])[0])

    def test_latest_timestamp_conflict_withholds_last_values(self):
        row, p = price([prior.raw('2023-11-20T18:00:00Z'), prior.raw('2023-11-20T18:00:00Z', 5, 10, 50)])
        self.assertEqual(row['prior_price_record_count'], 2)
        self.assertIsNone(row['last_observed_price'])
        self.assertIsNone(row['last_observed_discount_pct'])
        self.assertTrue(p['latest_valid_timestamp_conflict'])
        self.assertEqual(p['latest_valid_raw_indices'], [0, 1])

    def test_zero_price_preserved(self):
        self.assertEqual(price([prior.raw('2023-11-20T18:00:00Z', 0, 0, 0)])[0]['last_observed_price'], 0)


class StaticAndSchemaTests(unittest.TestCase):
    def test_date_resolution_age_and_release_components(self):
        row = features.static_features('2020-02-29', WINDOWS[2023])
        self.assertEqual(row['game_age_days'], (features.date.fromisoformat('2023-11-21') - features.date.fromisoformat('2020-02-29')).days)
        self.assertEqual([row[f] for f in features.STATIC[1:]], [2020, 2, 1])

    def test_same_day_release_hour_uncertainty(self):
        row = features.static_features('2023-11-21', WINDOWS[2023])
        self.assertEqual(row['game_age_days'], 0)
        self.assertEqual(row['audit_release_hour_uncertain'], 1)
        self.assertNotIn('release_timestamp', row)

    def test_negative_age_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Negative game age'):
            features.static_features('2023-11-22', WINDOWS[2023])

    def test_duplicate_pairs_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            features.authorized_pairs([label(), label()], WINDOWS)

    def test_2026_and_unsupported_years_excluded(self):
        for y in ('2026', '2022'):
            row = dict(label(), sale_year=y)
            with self.assertRaisesRegex(ValueError, 'Unsupported sale year'):
                features.authorized_pairs([row], WINDOWS)

    def test_approximate_cutoff_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Exact cutoff mismatch'):
            features.authorized_pairs([dict(label(), sale_start_utc='2023-11-21T00:00:00Z')], WINDOWS)

    def test_explicit_allowlist_and_no_label_fields(self):
        manifest = features.feature_manifest()
        self.assertEqual(manifest['baseline_feature_allowlist'], list(features.STATIC + features.PRICE))
        self.assertEqual(len(set(features.ALLOWLIST)), 15)
        prohibited = {'discount_observed', 'evidence_category', 'pu_status', 'in_window_record_count',
                      'supporting_record_indices', 'empty_raw_history', 'label_limitation_flag'}
        self.assertFalse(prohibited & set(features.FIELDS))
        self.assertFalse(set(features.IDENTIFIERS + features.AUDIT_FIELDS) & set(features.ALLOWLIST))

    def test_row_order_deterministic(self):
        pairs = [(1, 2025), (1, 2023), (1, 2024)]
        a = features.build_features(pairs, {1: GAME}, {1: []}, WINDOWS)[0]
        b = features.build_features(list(reversed(pairs)), {1: GAME}, {1: []}, WINDOWS)[0]
        self.assertEqual(a, b)
        self.assertEqual([r['sale_year'] for r in a], [2023, 2024, 2025])

    def test_malformed_csv_schema_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bad.csv'
            for text in ('appid,appid\n1,1\n', 'appid\n1,extra\n', 'other\n1\n'):
                path.write_text(text)
                with self.assertRaises(ValueError):
                    features.read_table(path, ['appid'])


class FeatureIntegrationTests(unittest.TestCase):
    def test_full_pipeline_offline_300_rows_integrity_and_determinism(self):
        protected = features.protected_hashes(ROOT)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = set(protected) | set(features.source_hashes(ROOT)) | {'PROJECT_CONTEXT.md'}
            for relative in sorted(paths):
                dest = root / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.symlink_to(ROOT / relative)
            with features.coverage.offline_guard():
                rows, model, receipt = features.run(root)
                first = {p: (root / p).read_bytes() for p in features.OUTPUTS}
                again = features.run(root)
                self.assertEqual(first, {p: (root / p).read_bytes() for p in features.OUTPUTS})
            self.assertEqual(len(rows), 300)
            self.assertEqual(len({(r['appid'], r['sale_year']) for r in rows}), 300)
            self.assertEqual(receipt['year_counts'], {'2023': 100, '2024': 100, '2025': 100})
            self.assertEqual(receipt['unique_games'], 100)
            self.assertEqual(sum(r['discount_observed'] for r in model), 175)
            self.assertTrue(all(set(r) == set(features.FIELDS) for r in rows))
            self.assertTrue(all(set(r) == set(features.FIELDS) | {'discount_observed'} for r in model))
            self.assertEqual(receipt['cutoff_violations'], 0)
            self.assertEqual(receipt['currency_conflict_pair_count'], 0)
            self.assertEqual(receipt['uncertain_release_hour_count'], 1)
            self.assertEqual(receipt['checks']['network_attempts'], 0)
            self.assertEqual(receipt['protected_before_sha256'], receipt['protected_after_sha256'])
            self.assertEqual(receipt['frozen_phase4_before_sha256'], receipt['frozen_phase4_after_sha256'])
            nekowater = next(r for r in rows if r['appid'] == 2650840 and r['sale_year'] == 2023)
            self.assertEqual(nekowater['audit_release_hour_uncertain'], 1)
            manifest = json.loads((root / features.MANIFEST).read_text())
            self.assertEqual(manifest['baseline_feature_allowlist'], list(features.ALLOWLIST))
            for p in receipt['pair_pre_cutoff_provenance']:
                cache = json.loads((ROOT / 'data/raw/itad' / f"{p['appid']}.json").read_text())
                raw_history = cache['history_response']
                expected = [i for i, raw_record in enumerate(raw_history)
                            if raw_record['shop']['id'] == 61 and features.audit.utc_stamp(raw_record['timestamp']) < WINDOWS[p['sale_year']][2]
                            and features.audit.observation(raw_record, i)['observation_kind'] in ('discount', 'full_price')]
                self.assertEqual(set(p['valid_prior_raw_indices']), set(expected))
                vector = next(r for r in rows if (r['appid'], r['sale_year']) == (p['appid'], p['sale_year']))
                self.assertEqual(vector['prior_price_record_count'], len(expected))
                self.assertEqual(vector['prior_discount_count'], len(p['discount_prior_raw_indices']))
                for field in ('latest_valid_prior_timestamp', 'latest_discount_prior_timestamp'):
                    if p[field]:
                        self.assertLess(features.audit.utc_stamp(p[field]), WINDOWS[p['sale_year']][2])
            self.assertEqual(rows, again[0])
        self.assertEqual(protected, features.protected_hashes(ROOT))

    def test_offline_guard_rejects_network(self):
        with self.assertRaisesRegex(AssertionError, 'Network forbidden'):
            with features.coverage.offline_guard():
                socket.create_connection(('example.invalid', 443))

    def test_protected_input_modification_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / features.PRIOR_RECEIPT
            path.parent.mkdir(parents=True)
            (root / 'input.csv').write_text('changed')
            path.write_text(json.dumps(dict(protected_after_sha256={'input.csv': '0' * 64}, source_sha256={}, output_sha256={})))
            with self.assertRaisesRegex(ValueError, 'Protected input changed'):
                features.protected_hashes(root)


if __name__ == '__main__':
    unittest.main()
