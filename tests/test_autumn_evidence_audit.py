"""Offline Phase 5A/5A.1 tests. No fixtures write into Phase 4 inputs."""
import contextlib
import copy
import csv
import importlib.util
import io
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import shutil
import socket
import tempfile
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

spec = importlib.util.spec_from_file_location(
    'audit', Path(__file__).resolve().parents[1] / 'src/04_audit_autumn_evidence.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def raw(ts, price=10, regular=10, cut=0, shop=61):
    return {'timestamp': ts, 'shop': {'id': shop, 'name': 'Steam' if shop == 61 else 'Other'},
            'deal': {'price': {'amount': price, 'amountInt': int(price * 100), 'currency': 'USD'},
                     'regular': {'amount': regular, 'amountInt': int(regular * 100), 'currency': 'USD'},
                     'cut': cut}}


WINDOW = ('2023-11-21', '2023-11-28', audit.utc_stamp('2023-11-21T00:00:00Z'),
          audit.utc_stamp('2023-11-29T00:00:00Z'))
GAME = {'AppID': '1', 'Name': 'Synthetic game', 'release_date': '2020-01-01'}
OK = {'cache_status': 'ok', 'issue': ''}


class EvidenceTests(unittest.TestCase):
    def pair(self, history):
        records, issues, other = audit.parse_history(history)
        self.assertEqual(issues, [])
        self.assertEqual(other, 0)
        return audit.audit_pair(GAME, 2023, WINDOW, records, OK)

    def test_inclusive_dates_and_timezone_equivalence(self):
        history = [raw('2023-11-20T23:59:59.999999Z'),
                   raw('2023-11-21T01:00:00+01:00'),
                   raw('2023-11-28T23:59:59.999999Z'),
                   raw('2023-11-29T01:00:00+01:00')]
        summary, long = self.pair(history)
        self.assertEqual(summary['in_window_record_count'], 2)
        self.assertEqual(long[0]['timestamp_utc'], '2023-11-21T00:00:00Z')
        self.assertEqual(summary['before_source_record_index'], 0)
        self.assertEqual(summary['after_source_record_index'], 3)
        self.assertEqual(summary['after_gap_days'], 0)
        self.assertEqual(long[0]['timestamp_raw'], '2023-11-21T01:00:00+01:00')

    def test_zero_evidence_does_not_carry_prices(self):
        summary, long = self.pair([raw('2023-11-15T00:00:00Z'), raw('2023-12-03T00:00:00Z')])
        self.assertEqual(summary['evidence_category'], 'D')
        self.assertEqual(summary['in_window_record_count'], 0)
        self.assertEqual(summary['in_window_full_price_count'], 0)
        self.assertFalse(summary['has_in_window_records'])
        self.assertEqual(summary['min_observed_in_window_price'], '')
        self.assertEqual(summary['before_gap_days'], 6)
        self.assertEqual(summary['after_gap_days'], 4)
        self.assertEqual(long, [])

    def test_discount_and_mixed_direct_evidence(self):
        summary, long = self.pair([raw('2023-11-21T18:00:00Z', 5, 10, 50),
                                  raw('2023-11-28T18:00:00Z')])
        self.assertEqual(summary['evidence_category'], 'A')
        self.assertEqual(summary['in_window_discount_count'], 1)
        self.assertEqual(summary['in_window_full_price_count'], 1)
        self.assertTrue(summary['in_window_mixed_discount_full_price'])
        self.assertEqual(summary['min_observed_in_window_price'], 5)
        self.assertEqual(summary['max_observed_in_window_regular_price'], 10)
        self.assertEqual(summary['max_observed_in_window_cut'], 50)
        self.assertEqual(json.loads(long[0]['raw_record_json'])['deal']['cut'], 50)

    def test_full_price_and_zero_preservation(self):
        summary, long = self.pair([raw('2023-11-22T00:00:00Z', 0, 0, 0), raw('2023-11-23T00:00:00Z')])
        self.assertEqual(summary['evidence_category'], 'B')
        self.assertEqual(summary['in_window_full_price_count'], 2)
        self.assertEqual(summary['min_observed_in_window_price'], 0)
        self.assertEqual(long[0]['price_amountInt'], 0)

    def test_null_deal_is_temporal_evidence_never_full_price(self):
        null = dict(raw('2023-11-22T00:00:00Z'), deal=None)
        summary, long = self.pair([null])
        self.assertEqual(summary['in_window_record_count'], 1)
        self.assertEqual(summary['in_window_price_usable_count'], 0)
        self.assertEqual(summary['in_window_null_deal_count'], 1)
        self.assertEqual(summary['in_window_ambiguous_count'], 1)
        self.assertEqual(summary['in_window_full_price_count'], 0)
        self.assertEqual(summary['evidence_category'], 'C')
        self.assertEqual(json.loads(long[0]['raw_record_json'])['deal'], None)
        self.assertEqual(self.pair([null, raw('2023-11-23T00:00:00Z')])[0]['evidence_category'], 'C')
        self.assertEqual(self.pair([null, raw('2023-11-23T00:00:00Z', 5, 10, 50)])[0]['evidence_category'], 'A')

    def test_missing_and_contradictory_information_not_invented(self):
        missing = raw('2023-11-22T00:00:00Z')
        del missing['deal']['cut']
        for r in [missing, raw('2023-11-22T00:00:00Z', 10, 10, 50),
                  raw('2023-11-22T00:00:00Z', 5, 10, 0),
                  dict(raw('2023-11-22T00:00:00Z'), deal={})]:
            with self.subTest(record=r):
                summary, long = self.pair([r])
                self.assertEqual(summary['evidence_category'], 'C')
                self.assertEqual(summary['in_window_price_usable_count'], 0)
                self.assertEqual(json.loads(long[0]['raw_record_json']), r)
        self.assertEqual(self.pair([missing])[1][0]['cut'], '')

    def test_invalid_amounts_cuts_and_currencies_remain_ambiguous(self):
        wrong_currency = raw('2023-11-22T00:00:00Z')
        wrong_currency['deal']['regular']['currency'] = 'EUR'
        for record in [wrong_currency, raw('2023-11-22T00:00:00Z', -1, 10, 50),
                       raw('2023-11-22T00:00:00Z', 5, -10, 50),
                       raw('2023-11-22T00:00:00Z', 5, 10, 101),
                       raw('2023-11-22T00:00:00Z', 5, 10, -1)]:
            with self.subTest(record=record):
                row, observations = self.pair([record])
                self.assertEqual(row['evidence_category'], 'C')
                self.assertEqual(row['in_window_ambiguous_count'], 1)
                self.assertEqual(json.loads(observations[0]['raw_record_json']), record)

    def test_nearest_context_selection_unsorted_input_and_ties(self):
        history = [raw('2023-12-20T00:00:00Z'), raw('2023-11-20T00:00:00Z', 5, 10, 50),
                   raw('2023-11-15T00:00:00Z'), raw('2023-11-29T12:00:00Z'),
                   raw('2023-11-20T00:00:00Z')]
        summary, _ = self.pair(history)
        self.assertEqual(summary['before_source_record_index'], 1)
        self.assertEqual(summary['before_nearest_timestamp_tie_count'], 2)
        self.assertEqual(len(json.loads(summary['before_tied_records_json'])), 2)
        self.assertEqual(summary['before_gap_days'], 1)
        self.assertEqual(summary['after_source_record_index'], 3)
        self.assertEqual(summary['after_gap_days'], 0.5)

    def test_null_context_is_preserved(self):
        summary, _ = self.pair([dict(raw('2023-11-20T00:00:00Z'), deal=None)])
        self.assertEqual(summary['before_deal_status'], 'null')
        self.assertEqual(summary['before_price'], '')
        self.assertEqual(summary['before_gap_days'], 1)

    def test_only_steam_shop_and_explicit_timezone(self):
        records, issues, other = audit.parse_history([
            raw('2023-11-22T00:00:00Z', shop=35), raw('2023-11-22T00:00:00Z', shop='61'),
            raw('2023-11-22T00:00:00'), raw('2023-11-22'), raw('2023-11-22T00:00:00Z')])
        self.assertEqual(len(records), 1)
        self.assertEqual(other, 1)
        self.assertEqual(len(issues), 3)
        self.assertEqual(records[0]['source_record_index'], 4)

    def test_no_deduplication_or_input_mutation(self):
        history = [raw('2023-11-22T00:00:00Z'), raw('2023-11-22T00:00:00Z', 5, 10, 50)]
        original = copy.deepcopy(history)
        summary, long = self.pair(history)
        self.assertEqual(summary['in_window_record_count'], 2)
        self.assertEqual(len(long), 2)
        self.assertEqual(history, original)

    def test_failed_cache_not_reported_as_zero_evidence(self):
        row, _ = audit.audit_pair(GAME, 2023, WINDOW, [], {'cache_status': 'missing', 'issue': 'missing'})
        self.assertEqual(row['evidence_category'], '')
        self.assertEqual(row['in_window_record_count'], '')


class IntegrationTests(unittest.TestCase):
    def make_fixture(self, root, missing_cache=False):
        for directory in ('data/raw/itad', 'data/intermediate', 'reports', 'src'):
            (root / directory).mkdir(parents=True)
        (root / 'PROJECT_CONTEXT.md').write_text('\n'.join(
            f"Autumn {e['sale_year']}: {e['sale_start_pacific'][:10]} to {e['sale_end_pacific'][:10]}"
            for e in audit.calendar_data(audit.ROOT)['events']))
        shutil.copyfile(audit.ROOT / 'src/autumn_sale_calendar.json', root / 'src/autumn_sale_calendar.json')
        shutil.copyfile(audit.ROOT / 'src/04_audit_autumn_evidence.py', root / 'src/04_audit_autumn_evidence.py')
        for e in audit.calendar_data(audit.ROOT)['events']:
            if e.get('source_image_path'):
                dest = root / e['source_image_path']
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(audit.ROOT / e['source_image_path'], dest)
        (root / 'src/03_fetch_itad.py').write_text('frozen Phase 4 sentinel\n')
        (root / 'reports/itad_collection_report.md').write_text('frozen report\n')
        (root / 'data/intermediate/games_master.csv').write_text('frozen master\n')
        games, manifests = [], []
        for i in range(1, 101):
            appid = str(i)
            games.append(dict(GAME, AppID=appid))
            h = [raw('2023-11-22T00:00:00Z', 5, 10, 50), raw('2024-11-27T18:00:00Z'),
                 raw('2025-09-29T17:00:00Z', 5, 10, 50)] if i == 1 else []
            status = 'history_received' if h else 'empty_history'
            manifest = dict(AppID=appid, itad_game_id='synthetic-id', country='US', steam_shop_id='61',
                            requested_since='2021-01-01T00:00:00Z', history_record_count=str(len(h)), history_status=status)
            manifests.append(manifest)
            obj = {'steam_appid': i, 'itad_game_id': 'synthetic-id',
                   'lookup_response': {'found': True, 'game': {'id': 'synthetic-id'}},
                   'request_configuration': {'country': 'US', 'steam_shop_id': 61,
                                             'requested_since': manifest['requested_since'],
                                             'history_endpoint': '/games/history/v2', 'lookup_endpoint': '/games/lookup/v1'},
                   'history_response': h, 'collection_metadata': {'history_status': status},
                   'history_evidence': {'http_status': 200, 'body': json.dumps(h),
                                        'params': {'id': 'synthetic-id', 'country': 'US', 'shops': '61',
                                                   'since': manifest['requested_since']}}}
            (root / f'data/raw/itad/{i}.json').write_text(json.dumps(obj))
        audit.write_csv(root / 'data/intermediate/pilot_games.csv', games, list(games[0]))
        audit.write_csv(root / 'data/intermediate/itad_collection_manifest.csv', manifests, list(manifests[0]))
        if missing_cache:
            (root / 'data/raw/itad/1.json').unlink()
        # Execute the preserved original implementation to construct a real fixture baseline.
        base = root / audit.BASELINE_DIRECTORY
        original_source = audit.ROOT / audit.BASELINE_DIRECTORY / 'src/04_audit_autumn_evidence.py'
        original_spec = importlib.util.spec_from_file_location('original_audit', original_source)
        original = importlib.util.module_from_spec(original_spec)
        original_spec.loader.exec_module(original)
        with patch.object(socket.socket, 'connect', side_effect=AssertionError('Network forbidden')), contextlib.redirect_stdout(io.StringIO()):
            old_rows, old_long, _ = original.run(root)
        paths = ['data/intermediate/autumn_sale_evidence_audit.csv',
                 'data/intermediate/autumn_sale_evidence_records.csv',
                 'reports/autumn_sale_evidence_audit.md', 'reports/autumn_sale_evidence_validation.json',
                 'PROJECT_CONTEXT.md', 'src/04_audit_autumn_evidence.py']
        for path in paths:
            dest = base / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original_source if path == 'src/04_audit_autumn_evidence.py' else root / path, dest)
        manifest = dict(git_revision='synthetic baseline', game_sale_pairs=len(old_rows),
                        in_window_records=len(old_long), files_sha256={p: audit.digest(base / p) for p in paths},
                        frozen_phase4_sha256=audit.frozen_hashes(root),
                        categories={str(y): {c: sum(r['sale_year'] == y and r['evidence_category'] == c for r in old_rows)
                                             for c in audit.CATEGORIES} for y in (2023, 2024)})
        (base / 'baseline_manifest.json').write_text(json.dumps(manifest))

    def test_complete_offline_run_hash_preservation_and_reproducibility(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_fixture(root)
            before = audit.frozen_hashes(root)
            baseline_before = audit.baseline_hashes(root)
            with patch.object(socket.socket, 'connect', side_effect=AssertionError('Network forbidden')), contextlib.redirect_stdout(io.StringIO()):
                rows, long, receipt = audit.run(root)
                outputs = list((root / 'data/intermediate').glob('autumn*')) + list((root / 'reports').glob('autumn*'))
                first = {p: p.read_bytes() for p in outputs}
                audit.run(root)
            self.assertEqual(before, audit.frozen_hashes(root))
            self.assertEqual(baseline_before, audit.baseline_hashes(root))
            self.assertEqual(first, {p: p.read_bytes() for p in outputs})
            self.assertEqual(len(rows), 300)
            self.assertEqual(len({(r['AppID'], r['sale_year']) for r in rows}), 300)
            self.assertTrue(all(r['eligible_for_sale'] for r in rows))
            self.assertEqual(len(long), 3)
            self.assertEqual(rows[0]['evidence_category'], 'A')
            self.assertEqual(rows[1]['evidence_category'], 'B')
            self.assertEqual(rows[2]['evidence_category'], 'A')
            self.assertTrue(all(r['evidence_category'] == 'D' for r in rows[3:]))
            for s in receipt['boundary_comparison']['summary'].values():
                self.assertEqual(s['original_records'] - s['removed_records'] + s['added_records'], s['corrected_records'])
            self.assertEqual(receipt['api_calls'], 0)
            self.assertEqual(receipt['network_requests'], 0)
            saved = audit.read_csv(root / 'data/intermediate/autumn_sale_evidence_audit.csv')
            self.assertEqual(len(saved), 300)
            self.assertEqual({r['AppID'] for r in saved}, {str(i) for i in range(1, 101)})
            self.assertFalse(any(k in saved[0] for k in ('target', 'discounted', 'label')))

    def test_missing_cache_accounted_for_without_category_d(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_fixture(root, missing_cache=True)
            with contextlib.redirect_stdout(io.StringIO()):
                rows, _, receipt = audit.run(root)
            self.assertEqual(len(rows), 300)
            self.assertEqual(rows[0]['cache_status'], 'missing')
            self.assertEqual(rows[0]['evidence_category'], '')
            self.assertEqual(rows[1]['evidence_category'], '')
            self.assertIn('ISSUES', receipt['checks']['Cache provenance and record parsing'])

    def test_canonical_dates_cannot_silently_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'src').mkdir()
            shutil.copyfile(audit.ROOT / 'src/autumn_sale_calendar.json', root / 'src/autumn_sale_calendar.json')
            for e in audit.calendar_data(audit.ROOT)['events']:
                if e.get('source_image_path'):
                    dest = root / e['source_image_path']
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(audit.ROOT / e['source_image_path'], dest)
            (root / 'PROJECT_CONTEXT.md').write_text('Autumn 2023: 2023-11-22 to 2023-11-28\n')
            with self.assertRaises(ValueError):
                audit.canonical_windows(root)

    def test_corrupted_baseline_stops_before_overwriting_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_fixture(root)
            output = root / 'data/intermediate/autumn_sale_evidence_audit.csv'
            before = output.read_bytes()
            (root / audit.BASELINE_DIRECTORY / 'reports/autumn_sale_evidence_audit.md').write_text('changed')
            with self.assertRaisesRegex(ValueError, 'baseline changed'):
                audit.run(root)
            self.assertEqual(output.read_bytes(), before)

    def test_frozen_input_change_stops_before_overwriting_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_fixture(root)
            output = root / 'data/intermediate/autumn_sale_evidence_audit.csv'
            before = output.read_bytes()
            (root / 'data/raw/itad/1.json').write_text('changed')
            with self.assertRaisesRegex(ValueError, 'Frozen Phase 4 inputs differ'):
                audit.run(root)
            self.assertEqual(output.read_bytes(), before)


class ExactBoundaryTests(unittest.TestCase):
    def test_original_baseline_reproduces_all_four_artifacts(self):
        base = audit.ROOT / audit.BASELINE_DIRECTORY
        manifest, _, _ = audit.verify_baseline(audit.ROOT)
        original_spec = importlib.util.spec_from_file_location('baseline_reproduction', base / 'src/04_audit_autumn_evidence.py')
        original = importlib.util.module_from_spec(original_spec)
        original_spec.loader.exec_module(original)
        before = audit.baseline_hashes(audit.ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Only isolated output directories are writable. Frozen inputs are linked for reading.
            for path in manifest['frozen_phase4_sha256']:
                dest = root / path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.symlink_to(audit.ROOT / path)
            shutil.copyfile(base / 'PROJECT_CONTEXT.md', root / 'PROJECT_CONTEXT.md')
            with patch.object(socket.socket, 'connect', side_effect=AssertionError('Network forbidden')), contextlib.redirect_stdout(io.StringIO()):
                original.run(root)
            for path in manifest['files_sha256']:
                if path.startswith(('data/intermediate/autumn_', 'reports/autumn_')):
                    self.assertEqual((root / path).read_bytes(), (base / path).read_bytes(), path)
        self.assertEqual(audit.baseline_hashes(audit.ROOT), before)

    def test_all_three_verified_boundaries(self):
        windows = audit.canonical_windows(audit.ROOT)
        expected = {2023: ('2023-11-21T18:00:00Z', '2023-11-28T18:00:00Z'),
                    2024: ('2024-11-27T18:00:00Z', '2024-12-04T18:00:00Z'),
                    2025: ('2025-09-29T17:00:00Z', '2025-10-06T17:00:00Z')}
        self.assertEqual(set(windows), set(expected))
        for year, (start, end) in expected.items():
            with self.subTest(year=year):
                self.assertEqual((audit.fmt(windows[year][2]), audit.fmt(windows[year][3])), (start, end))

    def test_half_open_boundaries_every_year(self):
        for year, window in audit.canonical_windows(audit.ROOT).items():
            start, end = window[2:]
            for delta, boundary, included in [(-1, start, False), (0, start, True), (-1, end, True), (0, end, False)]:
                ts = audit.fmt(boundary + timedelta(microseconds=delta))
                with self.subTest(year=year, timestamp=ts):
                    records, _, _ = audit.parse_history([raw(ts)])
                    row, long = audit.audit_pair(GAME, year, window, records, OK)
                    self.assertEqual(len(long), int(included))
                    if boundary == end and delta == 0:
                        self.assertEqual(row['after_gap_days'], 0)

    def test_pacific_standard_time(self):
        local = datetime(2023, 11, 21, 10, tzinfo=ZoneInfo('America/Los_Angeles'))
        self.assertEqual(local.utcoffset(), timedelta(hours=-8))
        self.assertEqual(audit.fmt(local.astimezone(timezone.utc)), '2023-11-21T18:00:00Z')

    def test_pacific_daylight_time(self):
        local = datetime(2025, 9, 29, 10, tzinfo=ZoneInfo('America/Los_Angeles'))
        self.assertEqual(local.utcoffset(), timedelta(hours=-7))
        self.assertEqual(audit.fmt(local.astimezone(timezone.utc)), '2025-09-29T17:00:00Z')

    def test_unverified_calendar_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'src').mkdir()
            calendar = audit.calendar_data(audit.ROOT)
            calendar['events'][0]['verification_status'] = 'unresolved'
            (root / 'src/autumn_sale_calendar.json').write_text(json.dumps(calendar))
            with self.assertRaisesRegex(ValueError, 'Unverified event boundary'):
                audit.canonical_windows(root)

    def test_after_start_release_explicitly_ineligible(self):
        game = dict(GAME, release_date='2024-11-28')
        window = audit.canonical_windows(audit.ROOT)[2024]
        records, _, _ = audit.parse_history([raw('2024-11-29T00:00:00Z', 5, 10, 50)])
        row, long = audit.audit_pair(game, 2024, window, records, OK)
        self.assertFalse(row['eligible_for_sale'])
        self.assertEqual(row['eligibility_reason'], 'release_date_after_sale_start_date')
        self.assertEqual(row['evidence_category'], '')
        self.assertEqual(row['in_window_record_count'], '')
        self.assertEqual(long, [])

    def test_same_start_date_release_hour_limitation_is_explicit(self):
        window = audit.canonical_windows(audit.ROOT)[2023]
        row, _ = audit.audit_pair(dict(GAME, release_date='2023-11-21'), 2023, window, [], OK)
        self.assertTrue(row['eligible_for_sale'])
        self.assertIn('exact release hour unavailable', row['eligibility_reason'])

    def test_boundary_comparison_explains_b_to_d_and_start_effect(self):
        windows = audit.canonical_windows(audit.ROOT)
        old_rows, old_records, rows, records = [], [], [], []
        for year, exact in windows.items():
            if year == 2025:
                continue
            # Full price before event start and exactly at event end; neither is inside.
            history = [raw(audit.fmt(exact[2] - timedelta(hours=1))), raw(audit.fmt(exact[3]))]
            parsed, _, _ = audit.parse_history(history)
            calendar = (*exact[:2], audit.utc_stamp(exact[0] + 'T00:00:00Z'),
                        audit.utc_stamp(exact[1] + 'T00:00:00Z') + timedelta(days=1))
            old, old_long = audit.audit_pair(GAME, year, calendar, parsed, OK)
            new, new_long = audit.audit_pair(GAME, year, exact, parsed, OK)
            old_rows.append(old)
            old_records.extend(old_long)
            rows.append(new)
            records.extend(new_long)
        comparison = audit.compare_boundaries(old_rows, old_records, rows, records, windows)
        self.assertEqual(len(comparison['category_changes']), 2)
        for s in comparison['summary'].values():
            self.assertEqual(s['original_categories']['B'], 1)
            self.assertEqual(s['corrected_categories']['D'], 1)
            self.assertEqual(s['removed_before_start'], 1)
            self.assertEqual(s['removed_at_or_after_end'], 1)
            self.assertEqual(s['original_records'] - s['removed_records'] + s['added_records'], s['corrected_records'])


if __name__ == '__main__':
    unittest.main()
