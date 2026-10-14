"""Pure 2026 cutoff/receipt/schema checks; no HTTP, fitting or predictions."""
import copy
from datetime import datetime,timezone
import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import audit_2026_feasibility as a


class FeasibilityTests(unittest.TestCase):
    def setUp(self):
        self.calendar=dict(sale_year=2026,verified_on='2026-10-14',sources=[{'url':'official-calendar-fixture'}],
             sale_start_pacific='2026-10-01T10:00:00-07:00',sale_end_pacific='2026-10-08T10:00:00-07:00',
             sale_start_utc='2026-10-01T17:00:00Z',sale_end_utc='2026-10-08T17:00:00Z',prediction_cutoff_utc='2026-10-01T17:00:00Z')
        self.window=a.verified_window(self.calendar)
        self.game={'release_date':'2020-01-01'}

    def raw(self,at):
        return dict(timestamp=at,shop={'id':61},deal=dict(price=dict(amount=5,amountInt=500,currency='USD'),
                    regular=dict(amount=10,amountInt=1000,currency='USD'),cut=50))

    def features(self,raw):
        parsed,issues,other=a.pipeline.audit.parse_history(raw)
        self.assertFalse(issues or other)
        return a.FEATURES.build_features([(1,2026)],{1:self.game},{1:parsed},{2026:self.window})[0][0]

    def test_pdt_conversion_is_17_utc_not_pst_18(self):
        self.assertEqual(self.window[2],datetime(2026,10,1,17,tzinfo=timezone.utc))
        self.assertEqual(self.window[3],datetime(2026,10,8,17,tzinfo=timezone.utc))

    def test_wrong_offset_or_cutoff_is_rejected(self):
        for name,value in [('sale_start_pacific','2026-10-01T10:00:00-08:00'),('prediction_cutoff_utc','2026-10-01T16:59:59Z')]:
            bad=dict(self.calendar);bad[name]=value
            with self.assertRaises(ValueError):a.verified_window(bad)

    def test_exact_boundary_and_sale_later_records_do_not_change_vector(self):
        before=[self.raw('2026-10-01T16:59:59Z')]
        row=self.features(before)
        self.assertEqual(row,self.features(before+[self.raw('2026-10-01T17:00:00Z'),self.raw('2026-10-04T12:00:00Z'),self.raw('2026-10-12T12:00:00Z')]))
        a.validate_vector(row,self.window[2])

    def test_2026_presale_record_is_not_discarded_by_2025_analysis_filter(self):
        row=self.features([self.raw('2026-06-01T00:00:00Z')])
        self.assertEqual(row['prior_price_record_count'],1)
        self.assertEqual(self.features([])['prior_price_record_count'],0)

    def test_postcutoff_receipt_does_not_prove_precutoff_provider_availability(self):
        obj={'history_evidence':dict(received_at='2026-10-13T00:00:00Z',response_headers={'Date':'Tue, 13 Oct 2026 00:00:00 GMT'})}
        evidence=a.receipt_evidence(obj,self.window[2])
        self.assertFalse(evidence['provider_available_before_cutoff_demonstrated'])
        self.assertIn('does not prove',evidence['availability_interpretation'])

    def test_earlier_receipt_is_upper_bound_evidence_without_inventing_first_seen(self):
        obj={'history_evidence':dict(received_at='2026-09-30T00:00:00Z',response_headers={})}
        self.assertTrue(a.receipt_evidence(obj,self.window[2])['cache_snapshot_received_before_cutoff'])
        self.assertNotIn('provider_first_seen',a.receipt_evidence(obj,self.window[2]))

    def test_empty_history_preserves_explicit_nullable_values_and_zero_flags(self):
        row=self.features([]);a.validate_vector(row,self.window[2])
        self.assertIsNone(row['last_observed_price']);self.assertEqual(row['has_prior_price_history'],0)
        row['last_observed_price']=0
        with self.assertRaisesRegex(ValueError,'zero-filled'):a.validate_vector(row,self.window[2])

    def test_bad_schema_range_or_type_is_rejected(self):
        for name,value in [('max_prior_discount_pct',101),('prior_price_record_count',1.5),('game_age_days',-1),('last_observed_price',float('inf'))]:
            row=self.features([self.raw('2026-06-01T00:00:00Z')]);row[name]=value
            with self.assertRaises(ValueError):a.validate_vector(row,self.window[2])

    def test_fifteen_predictors_and_no_target_probability_or_year_predictor(self):
        row=self.features([])
        self.assertEqual(len(a.FEATURES.ALLOWLIST),15)
        self.assertFalse(set(['appid','sale_year','discount_observed','evidence_category','predicted_probability'])&set(a.FEATURES.ALLOWLIST))
        self.assertNotIn('predicted_probability',row);self.assertNotIn('discount_observed',row)


if __name__=='__main__':unittest.main()
