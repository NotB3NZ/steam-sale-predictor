"""Offline feasibility checks; no historic output regeneration or model fitting."""
import ast
import copy
import csv
from datetime import date
import importlib.util
import json
from pathlib import Path
import random
import socket
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('scaling_audit',ROOT/'src/10_audit_scaling_feasibility.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
WINDOWS=a.audit.canonical_windows(ROOT)


def fixture():
    rows=[dict(AppID='1',release_date='2000-01-01',release_year='2000'),
          dict(AppID='2',release_date=WINDOWS[2023][0],release_year='2023')]
    for i in range(40):
        year=[2010,2017,2021,2023][i%4]
        rows.append(dict(AppID=str(10+i),release_date=f'{year}-01-01',release_year=str(year)))
    rows.append(dict(AppID='99',release_date='2025-01-01',release_year='2025'))
    return rows


class ScalingFeasibilityTests(unittest.TestCase):
    def test_streaming_catalog_parsing_deterministic_and_explicit_schema(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'master.csv'
            with p.open('w',newline='') as stream:
                w=csv.DictWriter(stream,fieldnames=['AppID','release_date','release_year','discount_observed'])
                w.writeheader();w.writerows([dict(r,discount_observed=1) for r in fixture()])
            self.assertEqual(a.read_catalog(p),fixture())
            self.assertEqual(a.read_catalog(p),a.read_catalog(p))
            self.assertNotIn('discount_observed',a.read_catalog(p)[0])
            p.write_text('AppID,release_date,release_date\n1,2020-01-01,2020\n')
            with self.assertRaisesRegex(ValueError,'schema'):a.read_catalog(p)

    def test_identifier_domain_and_invalid_handling(self):
        for value in ['1',str(2**32-1)]:self.assertTrue(a.valid_appid(value))
        for value in ['', '0', '-1','1.0','01',' 1','abc',str(2**32),'１２',None]:self.assertFalse(a.valid_appid(value))
        rows=fixture()+[dict(AppID=v,release_date='2020-01-01',release_year='2020') for v in ['', '0','bad']]
        stats=a.audit_catalog(rows,WINDOWS)
        self.assertEqual(stats['missing_appids'],1);self.assertEqual(stats['invalid_identifiers'],2)
        candidates,_=a.sample_candidates(rows,{1,2},WINDOWS,[4,8,12])
        self.assertEqual(len(candidates),len(fixture()))

    def test_duplicate_identifiers_reported_and_all_copies_excluded(self):
        rows=fixture()+[dict(fixture()[2],release_date='2012-01-01',release_year='2012')]
        stats=a.audit_catalog(rows,WINDOWS)
        self.assertEqual(stats['duplicate_appid_values'],1);self.assertEqual(stats['duplicate_excess_rows'],1)
        candidates,_=a.sample_candidates(rows,{1,2},WINDOWS,[4,8,12])
        self.assertNotIn(10,{r['appid'] for r in candidates})
        with self.assertRaisesRegex(ValueError,'Pilot'):a.sample_candidates(rows,{1,2,10},WINDOWS,[4,8,12])

    def test_release_date_validation_and_year_consistency(self):
        self.assertEqual(a.release_date('2020-02-29'),date(2020,2,29))
        for value in ['', '2021-02-29','2020-1-01','2020-01-01T00:00:00Z',None]:self.assertIsNone(a.release_date(value))
        rows=fixture()+[dict(AppID='100',release_date='',release_year=''),
            dict(AppID='101',release_date='bad',release_year=''),dict(AppID='102',release_date='2020-01-01',release_year='2021')]
        stats=a.audit_catalog(rows,WINDOWS)
        self.assertEqual(stats['missing_release_dates'],1);self.assertEqual(stats['invalid_release_dates'],1)
        self.assertEqual(stats['release_year_mismatches'],1)
        candidates,_=a.sample_candidates(rows,{1,2},WINDOWS,[4,8,12])
        for r in candidates:
            if r['appid']>=100:self.assertEqual(r['selection_status'],'excluded_invalid_release')

    def test_date_only_eligibility_boundaries_and_release_hour_uncertainty(self):
        window=WINDOWS[2023]
        for d,eligible,uncertain,timing in [('2023-11-20',1,0,'before_start_date'),
            ('2023-11-21',1,1,'on_start_date'),('2023-11-22',0,0,'interior_sale_dates'),
            ('2023-11-28',0,0,'on_end_date'),('2023-11-29',0,0,'after_end_date')]:
            self.assertEqual(a.eligibility(date.fromisoformat(d),window),dict(eligible=eligible,uncertain=uncertain,timing=timing))
        self.assertEqual(a.eligibility(None,window)['eligible'],None)

    def test_catalog_denominators_and_exhaustive_release_timing_partition(self):
        rows=fixture()+[dict(AppID='100',release_date='',release_year='')]
        stats=a.audit_catalog(rows,WINDOWS)
        for year,s in stats['eligibility_by_year'].items():
            self.assertEqual(s['denominator_catalog_records'],len(rows))
            self.assertEqual(sum(s[k] for k in ['before_start_date','on_start_date','interior_sale_dates','on_end_date','after_end_date','unknown_release_date']),len(rows))
            self.assertEqual(s['eligible_by_existing_date_rule'],s['before_start_date']+s['on_start_date'])
        self.assertEqual(sum(stats['release_year_distribution'].values()),len(rows)-1)

    def test_nested_selection_order_invariance_and_seed(self):
        rows=fixture();original=a.sample_candidates(rows,{1,2},WINDOWS,[4,8,12])
        shuffled=copy.deepcopy(rows);random.Random(7).shuffle(shuffled)
        self.assertEqual(a.sample_candidates(shuffled,{2,1},WINDOWS,[4,8,12]),original)
        self.assertEqual(a.sample_candidates(rows,{1,2},WINDOWS,[4,8,12]),original)
        self.assertEqual(original[1]['seed'],42)
        sets=[{r['appid'] for r in original[0] if r[f'included_in_{n}']} for n in [4,8,12]]
        self.assertEqual([len(s) for s in sets],[4,8,12]);self.assertTrue(sets[0]<sets[1]<sets[2])

    def test_pilot_is_separate_and_start_day_uncertainty_preserved(self):
        candidates,plan=a.sample_candidates(fixture(),{1,2},WINDOWS,[4,8,12])
        for r in candidates:
            if r['appid'] in {1,2}:
                self.assertEqual(r['pilot_membership'],1);self.assertEqual(r['selection_status'],'pilot_cohort')
                self.assertEqual(r['sampling_priority'],'');self.assertEqual(r['probability_sample_rank'],'')
                for n in [4,8,12]:self.assertEqual(r[f'included_in_{n}'],1)
        same_day=next(r for r in candidates if r['appid']==2)
        self.assertEqual(same_day['eligibility_2023'],1);self.assertEqual(same_day['release_hour_uncertain_2023'],1)
        self.assertEqual(plan['pilot_games'],2)

    def test_new_uncertain_start_day_game_excluded_without_changing_eligibility(self):
        rows=fixture()+[dict(AppID='100',release_date='2023-11-21',release_year='2023')]
        candidates,_=a.sample_candidates(rows,{1,2},WINDOWS,[4,8,12])
        r=next(r for r in candidates if r['appid']==100)
        self.assertEqual(r['selection_status'],'excluded_uncertain_release_hour')
        self.assertEqual(r['eligibility_2023'],1);self.assertEqual(r['sampling_priority'],'')
        self.assertEqual(r['included_in_12'],0)

    def test_future_targets_snapshots_and_historical_coverage_cannot_change_selection(self):
        rows=fixture();expected=a.sample_candidates(rows,{1,2},WINDOWS,[4,8,12])
        altered=copy.deepcopy(rows)
        for i,r in enumerate(altered):r.update(discount_observed=i%2,evidence_category='A',prior_price_record_count=999,
            Price='999',Positive='999',future_discount_2025=1,historical_availability='abundant')
        self.assertEqual(a.sample_candidates(altered,{1,2},WINDOWS,[4,8,12]),expected)

    def test_candidates_have_no_labels_histories_or_future_event_dates(self):
        candidates,_=a.sample_candidates(fixture(),{1,2},WINDOWS,[4,8,12])
        for r in candidates:
            for field in ['discount_observed','actual_label','evidence_category','pu_status','prior_discount_count','prediction_cutoff_utc','eligibility_2026']:
                self.assertNotIn(field,r)
        self.assertEqual(set(WINDOWS),{2023,2024,2025})

    def test_sampling_strata_counts_allocations_and_inclusion_fractions(self):
        candidates,plan=a.sample_candidates(fixture(),{1,2},WINDOWS,[4,8,12])
        self.assertEqual(plan['frame_by_stratum'],{s:10 for s in a.STRATA})
        for n,c in plan['cohorts'].items():
            self.assertEqual(sum(c['new_sample_by_stratum'].values()),int(n)-2)
            for s,count in c['new_sample_by_stratum'].items():
                self.assertEqual(c['within_stratum_inclusion_probability'][s],count/10)
                for r in candidates:
                    if r[f'included_in_{n}'] and not r['pilot_membership']:self.assertIn(r['sampling_stratum'],a.STRATA)

    def test_insufficient_or_invalid_cohort_request_fails(self):
        for sizes in [[12,4],[2,4],[4,4],[4,100]]:
            with self.assertRaises(ValueError):a.sample_candidates(fixture(),{1,2},WINDOWS,sizes)

    def test_local_evidence_partition_exact_utc_boundaries_no_continuity_inference(self):
        def observation(t,kind):return dict(timestamp_utc=t,observation_kind=kind)
        s=a.audit.fmt(WINDOWS[2023][2]);end=a.audit.fmt(WINDOWS[2023][3])
        histories={1:[observation('2023-11-20T18:00:00Z','discount'),observation(s,'ambiguous'),observation(end,'full_price')],2:[]}
        stats=a.summarize_histories(histories,WINDOWS)
        self.assertEqual(stats['local_cohort_denominator'],2);self.assertEqual(stats['games_with_no_temporal_observations'],1)
        y=stats['by_year']['2023']
        self.assertEqual(y['before']['games_with_valid_price_records'],1)
        self.assertEqual(y['inside']['games_with_temporal_records'],1)
        self.assertEqual(y['inside']['games_with_valid_price_records'],0)
        self.assertEqual(y['after']['games_with_temporal_records'],1)
        self.assertEqual(y['games_without_in_window_record'],1)

    def test_request_estimates_reuse_pilot_and_do_not_establish_quota(self):
        q=a.collection_feasibility(dict(local_cohort_denominator=100,cache_wrapper_bytes={'mean':1000}))
        self.assertEqual(q['workload']['2000']['all_matched_no_retry_requests'],3800)
        self.assertEqual(q['workload']['5000']['cold_start_all_matched_requests'],10000)
        self.assertEqual(q['workload']['5000']['at_most_three_attempts_per_endpoint_all_matched_bound'],29400)
        self.assertEqual(q['workload']['500']['mapping_fraction_scenarios']['0.5'],600)
        self.assertIn('NOT verified',q['recorded_quota']);self.assertIn('unestablished',q['pagination'])

    def test_unseen_game_design_and_coverage_diagnostic_are_separate(self):
        design=a.evaluation_design()
        self.assertIn('EVERY holdout AppID',design['unseen_games'])
        self.assertIn('training-only',design['tuning'])
        self.assertIn('not an entirely fresh',design['confirmatory_feasibility'])
        self.assertIn('never to the diagnostic pilot',a.sample_candidates(fixture(),{1,2},WINDOWS,[4,8,12])[1]['inclusion_probability_note'])

    def test_approved_feature_schema_unchanged(self):
        manifest=a.read_json(ROOT/'reports/autumn_sale_feature_manifest.json')
        self.assertEqual(a.APPROVED,manifest['baseline_feature_allowlist']);self.assertEqual(a.APPROVED,list(a.features.ALLOWLIST))
        self.assertEqual(len(a.APPROVED),15)

    def test_pipeline_barriers_and_missingness_are_audited_not_repaired(self):
        result=a.readiness(ROOT)
        self.assertTrue(result['labeling']['barriers']);self.assertTrue(result['features']['barriers'])
        self.assertEqual(result['existing_feature_missingness']['days_since_last_price_record'],10)
        self.assertEqual(result['existing_feature_missingness']['days_since_last_discount'],46)
        for group in ['labeling','features','modeling_handoff']:
            for ref in result[group]['barriers']:
                self.assertEqual((ROOT/ref['path']).read_text().splitlines()[ref['line']-1].strip(),ref['text'])

    def test_offline_guard_blocks_socket_and_dns(self):
        for call in [lambda:socket.create_connection(('example.invalid',443)),lambda:socket.getaddrinfo('example.invalid',443)]:
            with self.assertRaisesRegex(AssertionError,'Network forbidden'):
                with a.coverage.offline_guard():call()

    def test_no_model_collection_execution_or_earlier_output_writes(self):
        tree=ast.parse((ROOT/a.SOURCE_FILES[0]).read_text())
        calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call)]
        forbidden={'fit','predict','predict_proba','urlopen','collect','Client','load_baselines'}
        for n in calls:
            name=n.func.attr if isinstance(n.func,ast.Attribute) else n.func.id if isinstance(n.func,ast.Name) else ''
            self.assertNotIn(name,forbidden)
        for p in a.OUTPUTS:
            self.assertNotIn(p,a.read_json(ROOT/'reports/autumn_sale_ensemble_validation.json')['output_sha256'])
            self.assertFalse(p.startswith('models/'))

    def test_missing_or_mutated_completed_artifact_stops_before_writes(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'Missing'):a.validate_prior(Path(d))
        with patch.object(a.audit,'digest',return_value='invalid'):
            with self.assertRaisesRegex(ValueError,'changed'):a.validate_prior(ROOT)

    def test_complete_audit_manifest_plot_data_integrity_and_light_figures(self):
        before=a.protected_hashes(ROOT)
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);result,receipt=a.run(ROOT,out)
            saved=a.features.read_table(out/a.CANDIDATES,a.FIELDS)
            self.assertEqual(len(saved),result['catalog']['total_records'])
            self.assertEqual(len({r['appid'] for r in saved}),len(saved))
            self.assertEqual(sum(int(r['pilot_membership']) for r in saved),100)
            for n in a.SIZES:self.assertEqual(sum(int(r[f'included_in_{n}']) for r in saved),n)
            self.assertEqual(a.validate_candidates(saved,result['sampling'],
                {int(r['appid']) for r in saved if r['pilot_membership']=='1'},WINDOWS),receipt['candidate_checks'])
            for altered in [saved+[saved[0]], [dict(saved[0],discount_observed='1')]+saved[1:],
                    [dict(saved[0],included_in_500='2')]+saved[1:]]:
                with self.assertRaises(ValueError):a.validate_candidates(altered,result['sampling'],
                    {int(r['appid']) for r in saved if r['pilot_membership']=='1'},WINDOWS)
            self.assertEqual(receipt['protected_before_sha256'],before);self.assertEqual(receipt['protected_after_sha256'],before)
            self.assertEqual(receipt['api_requests'],0);self.assertEqual(receipt['network_attempts'],0);self.assertEqual(receipt['models_fitted'],0)
            self.assertEqual(receipt['plotted_data'],result['plot_data'])
            self.assertEqual(result['plot_data'],a.plotted_data(result['catalog'],result['local_evidence'],result['sampling']))
            for n,c in result['sampling']['cohorts'].items():
                self.assertEqual(c['new_probability_sample_games'],int(n)-100)
                for s,count in c['new_sample_by_stratum'].items():
                    self.assertEqual(sum(r['sampling_stratum']==s and r['pilot_membership']=='0' and r[f'included_in_{n}']=='1' for r in saved),count)
            for p,h in receipt['output_sha256'].items():self.assertEqual(a.audit.digest(out/p),h)
            for f in receipt['figures'].values():
                with Image.open(out/f['path']) as im:
                    self.assertTrue(all(abs(x-300)<1 for x in im.info['dpi']))
                    self.assertEqual(im.convert('RGB').getpixel((0,0)),(255,255,255))
            with a.light_style():
                for k in ['figure.facecolor','axes.facecolor','savefig.facecolor']:self.assertEqual(a.plt.rcParams[k],'white')
            self.assertEqual(a.protected_hashes(ROOT),before)


if __name__=='__main__':unittest.main()
