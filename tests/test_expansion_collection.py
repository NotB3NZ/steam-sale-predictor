"""Focused mock-only collection safeguards; no previous workflows are executed."""
import ast
import base64
from collections import Counter
import copy
import csv
import importlib.util
import io
import json
import os
from pathlib import Path
import random
import socket
import subprocess
import tempfile
import unittest
from http.client import HTTPException, IncompleteRead
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('expansion', ROOT/'src/11_prepare_expansion_collection.py')
e = importlib.util.module_from_spec(spec); spec.loader.exec_module(e)
FAKE_KEY = 'offline-fixture-not-a-credential'
GID = '12345678-1234-1234-1234-123456789012'
RECORD = dict(timestamp='2025-09-30T18:00:00Z', shop=dict(id=61, name='Steam'),
              deal=dict(price=dict(amount=5, amountInt=500, currency='USD'),
                        regular=dict(amount=10, amountInt=1000, currency='USD'), cut=50))


def wire(value, code=200, headers=None):
    return code, headers or {}, json.dumps(value).encode()


def approved(manifest, cert):
    return dict(approval_status='APPROVED', trial_identity=e.TRIAL,
        pending_manifest_sha256=e.hashlib.sha256(e.json_bytes(manifest)).hexdigest(),
        maximum_total_requests=60, custodian_certificate_sha256=e.digest(cert),
        private_key_external_to_development=True, custodian='Offline test custodian', authorized_by='Offline fixture only')


class FixtureTransport:
    def __init__(self, lookup=None, history=None):
        self.calls = []
        self.lookup = dict(found=True, game=dict(id=GID)) if lookup is None else lookup
        self.history = [RECORD] if history is None else history

    def get(self, endpoint, params):
        self.calls.append((endpoint, params))
        return wire(self.lookup if endpoint == e.CONFIG['lookup_endpoint'] else self.history)


class ExpansionCollectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = e.read_candidates(ROOT/e.CANDIDATES)
        cls.members = e.allocate_membership(cls.rows)
        cls.smoke = e.select_smoke(cls.members)
        cls.inventory = e.protected_inventory()
        cls.manifest = e.approval_manifest(ROOT, cls.members, cls.smoke, cls.inventory)
        cls.sha = e.hashlib.sha256(e.json_bytes(cls.manifest)).hexdigest()
        cls.temp = tempfile.TemporaryDirectory()
        cls.cert = Path(cls.temp.name)/'custodian.pem'
        cls.key = Path(cls.temp.name)/'private-test-only.pem'
        # Ephemeral fixture key, outside repository. No production key is created.
        env = dict(os.environ); env.pop('ITAD_API_KEY', None)
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '2',
            '-subj', '/CN=offline-fixture', '-keyout', str(cls.key), '-out', str(cls.cert)],
            capture_output=True, check=True, env=env)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def response(self, outcomes, appid=1, endpoint=None):
        with tempfile.TemporaryDirectory() as d, patch.object(e.time, 'sleep'):
            journal = e.Journal(Path(d)/'journal.json', {'fixture': True})
            client = Mock(); client.get.side_effect = outcomes
            try:
                response = e.request_response(client, journal, appid, endpoint or e.CONFIG['lookup_endpoint'], {}, FAKE_KEY)
                return response, copy.deepcopy(journal.data), client.get.call_count
            finally:
                journal.close()

    def run_collection(self, root, transport, retry_failed=False):
        receipt = approved(self.manifest, self.cert)
        e.gate(self.manifest, self.manifest, self.sha, receipt, 60, e.validate_certificate(self.cert))
        with patch.object(e.time, 'sleep'):
            return e.collect(root, self.smoke, self.manifest, self.sha, receipt,
                e.hashlib.sha256(e.json_bytes(receipt)).hexdigest(), self.manifest, self.cert, FAKE_KEY, transport, retry_failed)

    def test_candidate_prefix_reproducible_and_input_order_independent(self):
        shuffled = list(self.rows); random.Random(72).shuffle(shuffled)
        self.assertEqual(e.allocate_membership(shuffled), self.members)
        self.assertEqual(e.select_smoke(e.allocate_membership(shuffled)), self.smoke)
        self.assertEqual([r['phase8a_candidate_rank'] for r in self.smoke], list(range(1, 21)))

    def test_exactly_twenty_new_games_without_pilot_overlap(self):
        pilot = {r['appid'] for r in self.rows if r['pilot_membership'] == '1'}
        self.assertEqual(len({r['appid'] for r in self.smoke}), 20)
        self.assertFalse(pilot & {r['appid'] for r in self.smoke})
        for r in self.smoke: self.assertEqual(r['planned_request_eligibility'], 'pending_explicit_approval')

    def test_release_strata_and_group_denominators(self):
        self.assertEqual(Counter(r['sampling_stratum'] for r in self.smoke),
            dict(before_2015=1, **{'2015_2019': 8, '2020_2022': 8, '2023_before_sale': 3}))
        self.assertEqual(Counter(r['evaluation_group'] for r in self.members),
                         dict(development=49247, sealed_evaluation=12312))
        self.assertEqual(Counter(r['evaluation_group'] for r in self.smoke), dict(development=16, sealed_evaluation=4))
        for s in e.STRATA:
            group = [r for r in self.members if r['sampling_stratum'] == s]
            self.assertEqual(sum(r['evaluation_group'] == 'sealed_evaluation' for r in group), (len(group)+2)//5)

    def test_entire_frame_disjoint_and_independent_of_outcomes_or_coverage(self):
        ids = {r['appid'] for r in self.members}
        self.assertEqual(len(ids), 61559)
        groups = [{r['appid'] for r in self.members if r['evaluation_group'] == g} for g in ['development', 'sealed_evaluation']]
        self.assertFalse(groups[0] & groups[1]); self.assertEqual(groups[0] | groups[1], ids)
        changed = [dict(r, discount_observed=random.Random(int(r['appid'])).randint(0, 1),
                        evidence_category='D', history_status='empty') for r in self.rows]
        self.assertEqual(e.allocate_membership(changed), self.members)
        self.assertNotEqual(e.MEMBERSHIP_SALT, '42')

    def test_candidate_schema_rejects_injected_outcomes_and_invalid_ranks(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'candidates.csv'
            path.write_bytes(e.csv_bytes([dict(self.rows[0], discount_observed=1)], e.FIELDS+['discount_observed']))
            with self.assertRaisesRegex(ValueError, 'schema'): e.read_candidates(path)
            frame = [r for r in self.rows if r['probability_sample_rank']][:2]
            path.write_bytes(e.csv_bytes([dict(r, probability_sample_rank='1') for r in frame], e.FIELDS))
            with self.assertRaisesRegex(ValueError, 'rank'): e.read_candidates(path)

    def test_default_and_dry_run_perform_zero_network_calls(self):
        with tempfile.TemporaryDirectory() as d, patch.object(e, 'Transport') as transport, \
             patch.object(e, 'collect') as collector, e.offline_guard(), patch('sys.stdout', io.StringIO()):
            self.assertEqual(e.main(['--output-root', d]), 0)
            self.assertEqual(e.main(['--dry-run', '--output-root', d]), 0)
            transport.assert_not_called(); collector.assert_not_called()
            self.assertFalse((Path(d)/e.RAW_ROOT).exists())

    def test_offline_guard_blocks_dns_and_sockets(self):
        for operation in [lambda: socket.getaddrinfo('example.invalid', 443),
                          lambda: socket.create_connection(('example.invalid', 443))]:
            with self.assertRaisesRegex(AssertionError, 'Network forbidden'):
                with e.offline_guard(): operation()

    def test_missing_live_approval_blocks_before_transport(self):
        with patch.object(e, 'Transport') as transport, patch('sys.stderr', io.StringIO()):
            self.assertEqual(e.main(['--live']), 1)
            self.assertEqual(e.main(['--live', '--request-budget', '60']), 1)
            self.assertEqual(e.main(['--request-budget', '60']), 1)
            transport.assert_not_called()

    def test_explicit_human_receipt_required_no_self_approval(self):
        for receipt in [None, {}, dict(approved(self.manifest, self.cert), approval_status='PENDING'),
                        dict(approved(self.manifest, self.cert), authorized_by=''),
                        dict(approved(self.manifest, self.cert), private_key_external_to_development=False)]:
            with self.assertRaises(ValueError): e.gate(self.manifest, self.manifest, self.sha, receipt, 60, e.digest(self.cert))

    def test_changed_manifest_membership_implementation_and_receipt_digest_blocked(self):
        receipt = approved(self.manifest, self.cert)
        e.gate(self.manifest, self.manifest, self.sha, receipt, 60, e.digest(self.cert))
        with self.assertRaisesRegex(ValueError, 'digest'): e.gate(self.manifest, self.manifest, '0'*64, receipt, 60, e.digest(self.cert))
        for field in ['sampling_manifest_sha256', 'evaluation_membership_manifest_sha256',
                      'collector_implementation_sha256', 'smoke_manifest_sha256']:
            changed = copy.deepcopy(self.manifest); changed[field] = 'changed'
            with self.assertRaisesRegex(ValueError, 'mismatch'): e.gate(changed, self.manifest, self.sha, receipt, 60, e.digest(self.cert))
        for field in ['pending_manifest_sha256', 'custodian_certificate_sha256', 'trial_identity']:
            changed = dict(receipt); changed[field] = 'changed'
            with self.assertRaisesRegex(ValueError, 'mismatch'): e.gate(self.manifest, self.manifest, self.sha, changed, 60, e.digest(self.cert))

    def test_twenty_game_cap_candidate_set_and_budget_mismatch(self):
        receipt = approved(self.manifest, self.cert)
        for budget in [0, 40, 59, 61, 500]:
            with self.assertRaisesRegex(ValueError, 'budget'): e.gate(self.manifest, self.manifest, self.sha, receipt, budget, e.digest(self.cert))
        with tempfile.TemporaryDirectory() as d:
            for smoke in [self.smoke[:19], self.smoke+self.smoke, list(reversed(self.smoke))]:
                with self.assertRaisesRegex(ValueError, 'cap'):
                    e.collect(Path(d), smoke, self.manifest, self.sha, receipt, 'fixture', self.manifest, self.cert, FAKE_KEY, Mock())

    def test_internal_collector_also_rejects_missing_approval_before_requests(self):
        with tempfile.TemporaryDirectory() as d:
            transport = Mock()
            with self.assertRaisesRegex(ValueError, 'approval missing'):
                e.collect(Path(d), self.smoke, self.manifest, self.sha, None, 'fixture', self.manifest, self.cert, FAKE_KEY, transport)
            transport.get.assert_not_called()
            self.assertFalse((Path(d)/e.RAW_ROOT).exists())

    def test_live_cli_approval_checks_before_http_client_creation(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for p, b in [(e.MEMBERSHIP, e.csv_bytes(self.members, e.MEMBER_FIELDS)),
                         (e.SMOKE, e.csv_bytes(self.smoke, e.SMOKE_FIELDS)), (e.APPROVAL, e.json_bytes(self.manifest))]:
                e.atomic_write(root/p, b)
            approval_path = root/'human-receipt.json'
            argv = ['--live', '--manifest-sha256', self.sha, '--approval-receipt', str(approval_path),
                    '--custodian-cert', str(self.cert), '--request-budget', '60']
            with patch.object(e, 'ROOT', root), patch.object(e, 'protected_inventory', return_value=self.inventory), \
                 patch.object(e, 'read_candidates', return_value=self.rows), \
                 patch.object(e, 'approval_manifest', return_value=self.manifest), \
                 patch.object(e, 'Transport') as transport, patch('sys.stderr', io.StringIO()), \
                 patch.dict(os.environ, {'ITAD_API_KEY': ''}), e.offline_guard():
                for receipt in [{}, dict(approved(self.manifest, self.cert), approval_status='PENDING'),
                                dict(approved(self.manifest, self.cert), pending_manifest_sha256='changed'),
                                approved(self.manifest, self.cert)]:
                    approval_path.write_bytes(e.json_bytes(receipt))
                    self.assertEqual(e.main(argv), 1)
                transport.assert_not_called()
                self.assertFalse((root/e.RAW_ROOT).exists())

    def test_hard_total_budget_and_endpoint_cap_survive_restart(self):
        with tempfile.TemporaryDirectory() as d, patch.object(e.time, 'sleep'):
            p = Path(d)/'journal.json'
            journal = e.Journal(p, {'fixture': True}, maximum=2)
            journal.reserve(1, 'lookup'); journal.close()
            journal = e.Journal(p, {'fixture': True}, maximum=2)
            journal.reserve(2, 'lookup')
            with self.assertRaisesRegex(e.StopCollection, 'budget'): journal.reserve(3, 'lookup')
            journal.close()
            journal = e.Journal(Path(d)/'endpoint.json', {'fixture': True})
            for _ in range(3): journal.reserve(1, 'lookup')
            with self.assertRaisesRegex(e.StopCollection, 'endpoint'): journal.reserve(1, 'lookup')
            journal.close()

    def test_serial_lock_and_default_pacing_timeout(self):
        self.assertGreaterEqual(e.CONFIG['request_start_spacing_seconds'], 1)
        self.assertEqual(e.CONFIG['timeout_seconds'], 30)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'journal.json'; journal = e.Journal(p, {'fixture': True})
            with self.assertRaisesRegex(e.StopCollection, 'Concurrent'): e.Journal(p, {'fixture': True})
            journal.close()
        with patch.object(e, 'build_opener') as opener:
            response = Mock(); response.__enter__ = Mock(return_value=response); response.__exit__ = Mock(return_value=False)
            response.code = 200; response.headers = {}; response.read.return_value = b'{}'
            opener.return_value.open.return_value = response
            e.Transport(FAKE_KEY).get(e.CONFIG['lookup_endpoint'], {'appid': 1})
            self.assertEqual(opener.return_value.open.call_args.kwargs['timeout'], 30)
            self.assertEqual(response.read.call_args.args, (e.CONFIG['maximum_response_bytes']+1,))

    def test_request_spacing_uses_completion_time_across_restart(self):
        with tempfile.TemporaryDirectory() as d, patch.object(e.time, 'time', side_effect=[10, 12, 12.25, 13]), \
             patch.object(e.time, 'sleep') as sleep:
            p = Path(d)/'journal.json'; journal = e.Journal(p, {'fixture': True})
            first = journal.reserve(1, 'lookup'); journal.finish(first, 'response_received'); journal.close()
            journal = e.Journal(p, {'fixture': True})
            second = journal.reserve(2, 'lookup'); journal.close()
            sleep.assert_called_once_with(0.75)
            self.assertEqual(second['reserved_unix_time']-first['completed_unix_time'], 1)

    def test_pilot_namespace_collision_and_symlink_forbidden(self):
        with tempfile.TemporaryDirectory() as d:
            candidate = dict(self.smoke[0], expected_output_namespace='data/raw/itad')
            with self.assertRaisesRegex(ValueError, 'namespace'): e.cache_path(Path(d), candidate)
            raw = Path(d)/e.RAW_ROOT; raw.parent.mkdir(parents=True); raw.symlink_to(Path(d)/'pilot')
            with self.assertRaises(ValueError): e.cache_path(Path(d), self.smoke[0])

    def test_unmatched_lookups_distinct_no_history_calls_and_cached(self):
        with tempfile.TemporaryDirectory() as d:
            client = FixtureTransport(lookup=dict(found=False)); self.run_collection(Path(d), client)
            self.assertEqual(len(client.calls), 20)
            self.assertTrue(all(c[0] == e.CONFIG['lookup_endpoint'] for c in client.calls))
            obj = e.read_json(e.cache_path(Path(d), self.smoke[0]))
            self.assertEqual(obj['progress'], dict(lookup='unmatched', history='not_collected'))
            self.run_collection(Path(d), client); self.assertEqual(len(client.calls), 20)

    def test_empty_history_distinct_and_never_claims_complete_or_negative(self):
        with tempfile.TemporaryDirectory() as d:
            client = FixtureTransport(history=[]); self.run_collection(Path(d), client)
            obj = e.read_json(e.cache_path(Path(d), self.smoke[0]))
            self.assertEqual(obj['responses']['history']['history_state'], 'empty_history')
            self.assertEqual(obj['history_completion'], 'UNVERIFIED')
            self.assertNotIn('discount_observed', json.dumps(obj)); self.assertNotIn('actual_label', json.dumps(obj))

    def test_authentication_401_403_and_redirect_immediate_abort(self):
        for code in [401, 403, 301, 302, 307, 308]:
            response, journal, calls = self.response([wire({}, code)])
            self.assertTrue(response['stop']); self.assertEqual(calls, 1)
            self.assertEqual(len(journal['attempts']), 1)

    def test_rate_limit_bounded_retry_after_and_stop(self):
        response, _, calls = self.response([wire({}, 429, {'Retry-After': '2'}), wire({'found': False})])
        self.assertEqual(response['status'], 'retrieved'); self.assertEqual(calls, 2)
        for value in [None, 'bad', '61', '-1']:
            response, _, calls = self.response([wire({}, 429, {} if value is None else {'Retry-After': value})])
            self.assertEqual(response['status'], 'rate_limit_stop'); self.assertTrue(response['stop']); self.assertEqual(calls, 1)

    def test_transient_retry_limit_timeout_and_408_5xx(self):
        for failure in [TimeoutError(), socket.timeout(), OSError(), wire({}, 408), wire({}, 500), wire({}, 503)]:
            response, journal, calls = self.response([failure]*3)
            self.assertEqual(response['status'], 'request_failed'); self.assertEqual(calls, 3)
            self.assertEqual(len(journal['attempts']), 3)

    def test_malformed_json_and_credentials_withheld(self):
        for raw in [b'not JSON', b'{"x": NaN}', b'\xff']:
            response, _, calls = self.response([(200, {}, raw)])
            self.assertEqual(response['status'], 'malformed_json'); self.assertEqual(calls, 1)
            self.assertEqual(base64.b64decode(response['raw_body_b64']), raw)
        response, _, _ = self.response([(200, {}, FAKE_KEY.encode())])
        self.assertEqual(response['status'], 'credential_reflection_withheld'); self.assertTrue(response['stop'])
        self.assertNotIn(FAKE_KEY, json.dumps(response))
        escaped = ''.join('\\u%04x' % ord(c) for c in FAKE_KEY)
        response, _, _ = self.response([(200, {}, ('{"reflected":"'+escaped+'"}').encode())])
        self.assertEqual(response['status'], 'credential_reflection_withheld')

    def test_partial_http_response_stops_and_other_http_failures_bounded(self):
        response, _, calls = self.response([IncompleteRead(b'[', 100)])
        self.assertEqual(response['status'], 'truncation_suspected'); self.assertTrue(response['stop'])
        self.assertEqual(calls, 1)
        response, _, calls = self.response([HTTPException('offline fixture')]*3)
        self.assertEqual(response['status'], 'request_failed'); self.assertEqual(calls, 3)

    def test_truncation_suspicion_bounded_response_and_unknown_completion(self):
        for headers in [{'Content-Length': '100'}, {'Content-Length': 'bad'}, {'Link': 'next-page'}]:
            response, _, _ = self.response([(200, headers, b'[]')])
            self.assertEqual(response['status'], 'truncation_suspected'); self.assertTrue(response['stop'])
        with patch.dict(e.CONFIG, maximum_response_bytes=2):
            response, _, _ = self.response([(200, {}, b'123')])
            self.assertEqual(response['status'], 'truncation_suspected')

    def test_unexpected_schema_quarantined_and_stops(self):
        for history in [{'next': 'unknown'}, [dict(RECORD, shop=dict(id=99, name='Other'))], [dict(RECORD, timestamp='bad')]]:
            with tempfile.TemporaryDirectory() as d:
                client = FixtureTransport(history=history); result = self.run_collection(Path(d), client)
                self.assertEqual(result['status'], 'STOPPED'); self.assertEqual(len(client.calls), 2)
                p = e.cache_path(Path(d), self.smoke[0])
                obj = e.read_json(p); self.assertEqual(obj['responses']['history']['status'], 'unexpected_schema')
                self.assertTrue((p.parent/'quarantine'/f"{self.smoke[0]['appid']}-history.json").exists())

    def test_schema_quarantine_for_evaluation_is_encrypted_only(self):
        with tempfile.TemporaryDirectory() as d:
            client = FixtureTransport()
            original = client.get
            heldout_id = int(next(r for r in self.smoke if r['evaluation_group'] == 'sealed_evaluation')['appid'])
            def get(endpoint, params):
                if endpoint == e.CONFIG['lookup_endpoint'] and params['appid'] == heldout_id:
                    return wire({'unrecognized_schema': 'secret-evaluation-content'})
                return original(endpoint, params)
            client.get = get
            self.assertEqual(self.run_collection(Path(d), client)['status'], 'STOPPED')
            for p in (Path(d)/e.RAW_ROOT/'sealed_evaluation').rglob('*.json'):
                self.assertNotIn('secret-evaluation-content', p.read_text())
                self.assertIn('sealed_cms_der_b64', p.read_text())

    def test_restart_cache_reuse_identical_bytes_and_corruption_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            client = FixtureTransport(); result = self.run_collection(Path(d), client)
            self.assertEqual(len(client.calls), 40); self.assertEqual(result['requests_reserved'], 40)
            paths = [e.cache_path(Path(d), r) for r in self.smoke]
            before = {p: p.read_bytes() for p in paths}
            self.run_collection(Path(d), client)
            self.assertEqual(len(client.calls), 40); self.assertEqual(before, {p: p.read_bytes() for p in paths})
            obj = e.read_json(paths[0]); obj['responses']['history']['payload'] = []
            paths[0].write_bytes(e.json_bytes(obj))
            with self.assertRaisesRegex(ValueError, 'integrity'): self.run_collection(Path(d), client)

    def test_missing_restart_journal_cannot_reset_budget(self):
        with tempfile.TemporaryDirectory() as d:
            client = FixtureTransport(); self.run_collection(Path(d), client)
            (Path(d)/e.RAW_ROOT/'request_journal.json').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing request journal'): self.run_collection(Path(d), client)
            self.assertEqual(len(client.calls), 40)

    def test_retry_failed_explicit_no_negative_labels(self):
        with tempfile.TemporaryDirectory() as d:
            client = FixtureTransport(); client.get = Mock(return_value=wire({}, 400))
            self.run_collection(Path(d), client); self.assertEqual(client.get.call_count, 20)
            self.run_collection(Path(d), client); self.assertEqual(client.get.call_count, 20)
            self.run_collection(Path(d), client, retry_failed=True); self.assertEqual(client.get.call_count, 40)
            for p in (Path(d)/e.RAW_ROOT).rglob('*.json'):
                self.assertNotIn('discount_observed', p.read_text()); self.assertNotIn('actual_label', p.read_text())

    def test_duplicate_timestamps_and_null_ambiguity_preserved(self):
        history = [RECORD, dict(RECORD, deal=None), dict(RECORD, timestamp='2025-09-30T11:00:00-07:00')]
        with tempfile.TemporaryDirectory() as d:
            self.run_collection(Path(d), FixtureTransport(history=history))
            obj = e.read_json(e.cache_path(Path(d), self.smoke[0]))
            self.assertEqual(obj['responses']['history']['payload'], history)
            self.assertEqual(obj['responses']['history']['duplicate_timestamp_excess'], 2)
            self.assertIsNone(obj['responses']['history']['payload'][1]['deal'])

    def test_custodian_sealing_roundtrip_public_cache_has_no_outcomes(self):
        self.assertEqual(e.validate_certificate(self.cert), e.digest(self.cert))
        sealed = e.seal_payload({'operational_outcome_fixture': 1}, self.cert)
        env = dict(os.environ); env.pop('ITAD_API_KEY', None)
        plain = subprocess.run(['openssl', 'cms', '-decrypt', '-binary', '-inform', 'DER',
            '-recip', str(self.cert), '-inkey', str(self.key)], input=base64.b64decode(sealed),
            capture_output=True, check=True, env=env).stdout
        self.assertEqual(json.loads(plain), {'operational_outcome_fixture': 1})
        with self.assertRaisesRegex(ValueError, 'Private key'): e.validate_certificate(self.key)
        with tempfile.TemporaryDirectory() as d:
            self.run_collection(Path(d), FixtureTransport())
            for r in self.smoke:
                if r['evaluation_group'] == 'sealed_evaluation':
                    obj = e.read_json(e.cache_path(Path(d), r)); text = json.dumps(obj)
                    for prohibited in ['cut', 'regular', 'empty_history', RECORD['timestamp'], 'nonempty_history']:
                        self.assertNotIn('"'+prohibited+'"', text)
                    self.assertEqual(obj['progress']['history'], 'sealed_stored')

    def test_sealed_appids_rejected_from_all_development_training_years(self):
        heldout = next(r['appid'] for r in self.members if r['evaluation_group'] == 'sealed_evaluation')
        dev = next(r['appid'] for r in self.members if r['evaluation_group'] == 'development')
        for year in [2023, 2024, 2025]:
            self.assertEqual(e.development_inputs([dict(appid=dev, sale_year=year)], self.members), [dict(appid=dev, sale_year=year)])
            for appid in [heldout, '0', next(r['appid'] for r in self.rows if r['pilot_membership'] == '1')]:
                with self.assertRaisesRegex(ValueError, 'development inputs'):
                    e.development_inputs([dict(appid=appid, sale_year=year, discount_observed='do-not-read')], self.members)

    def test_frozen_membership_and_serialization_determinism(self):
        self.assertEqual(e.csv_bytes(self.members, e.MEMBER_FIELDS), e.csv_bytes(e.allocate_membership(self.rows), e.MEMBER_FIELDS))
        self.assertEqual(e.json_bytes(self.manifest), e.json_bytes(e.approval_manifest(ROOT, self.members, self.smoke, self.inventory)))
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'frozen.csv'; e.atomic_write(p, b'original', immutable=True)
            with self.assertRaisesRegex(ValueError, 'Frozen'): e.atomic_write(p, b'changed', immutable=True)
            self.assertEqual(p.read_bytes(), b'original')

    def test_no_model_fit_labels_or_previous_output_writes(self):
        tree = ast.parse((ROOT/'src/11_prepare_expansion_collection.py').read_text())
        for call in (n for n in ast.walk(tree) if isinstance(n, ast.Call)):
            name = call.func.attr if isinstance(call.func, ast.Attribute) else call.func.id if isinstance(call.func, ast.Name) else ''
            self.assertNotIn(name, {'fit', 'predict', 'predict_proba', 'build_labels', 'build_features'})
        previous = {r['path'] for r in self.inventory['files']}
        self.assertFalse(previous & set(e.OUTPUTS))
        self.assertFalse(any(p.startswith('models/') or p.startswith('data/raw/') for p in e.OUTPUTS))

    def test_protected_inventory_checks_bytes_sizes_and_chain(self):
        self.assertEqual(len(self.inventory['files']), 225)
        self.assertEqual(e.protected_inventory(), self.inventory)
        for row in self.inventory['files']:
            self.assertEqual((ROOT/row['path']).stat().st_size, row['size_bytes'])
        with patch.object(e, 'digest', return_value='changed'):
            with self.assertRaisesRegex(ValueError, 'changed'): e.protected_inventory()


if __name__ == '__main__':
    unittest.main()
