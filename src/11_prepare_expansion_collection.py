"""Offline Phase 8B.1 preparation; a separately authorized 20-game collector.

Default and --verify never instantiate an HTTP client. No labels or models.
"""
import argparse
import base64
from collections import Counter, defaultdict
from contextlib import contextmanager
import csv
from datetime import date, datetime, timezone
import fcntl
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener
from email.utils import parsedate_to_datetime
from http.client import HTTPException, IncompleteRead

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'expansion-smoke-v1'
TRIAL = 'autumn-sale-expansion-smoke-20-v1'
CANDIDATES = 'data/intermediate/autumn_sale_scaling_candidates.csv'
PRIOR_RECEIPT = 'reports/autumn_sale_scaling_validation.json'
REPORT_DIR = 'reports/expansion'
INVENTORY = REPORT_DIR + '/autumn_sale_smoke_protected_inventory.json'
MEMBERSHIP = 'data/intermediate/expansion/autumn_sale_evaluation_membership.csv'
SMOKE = 'data/intermediate/expansion/autumn_sale_smoke_candidates.csv'
APPROVAL = REPORT_DIR + '/autumn_sale_smoke_approval_manifest.json'
PREFLIGHT = REPORT_DIR + '/autumn_sale_smoke_preflight.json'
REPORT = REPORT_DIR + '/autumn_sale_smoke_preflight.md'
VALIDATION = REPORT_DIR + '/autumn_sale_smoke_validation.json'
OUTPUTS = [INVENTORY, MEMBERSHIP, SMOKE, APPROVAL, PREFLIGHT, REPORT, VALIDATION]
DOCS = ['README.md', 'PROJECT_CONTEXT.md', 'PROJECT_STATUS.md']
STRATA = ['before_2015', '2015_2019', '2020_2022', '2023_before_sale']
MEMBERSHIP_SALT = 'steam-autumn-unseen-v1|314159'
FIELDS = ['appid', 'pilot_membership', 'release_date', 'release_year'] + \
    [f'eligibility_{y}' for y in (2023, 2024, 2025)] + \
    [f'release_hour_uncertain_{y}' for y in (2023, 2024, 2025)] + \
    ['sampling_stratum', 'sampling_priority', 'probability_sample_rank', 'selection_status'] + \
    [f'included_in_{n}' for n in (500, 1000, 2000, 5000)]
MEMBER_FIELDS = ['appid', 'release_date', 'sampling_stratum', 'phase8a_candidate_rank',
                 'evaluation_group', 'assignment_priority']
SMOKE_FIELDS = MEMBER_FIELDS + ['planned_request_eligibility', 'expected_output_namespace']
RAW_ROOT = f'data/raw/itad_expansion/{TRIAL}'
CONFIG = dict(api_base='https://api.isthereanydeal.com', lookup_endpoint='/games/lookup/v1',
              history_endpoint='/games/history/v2', country='US', steam_shop_id=61,
              requested_since='2021-01-01T00:00:00Z', request_start_spacing_seconds=1.0,
              timeout_seconds=30, attempts_per_endpoint=3, retry_backoff_seconds=[2, 4],
              maximum_retry_after_seconds=60, maximum_response_bytes=8*1024*1024,
              maximum_total_requests=60, maximum_games=20)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+'\n').encode()


def read_json(path):
    return json.loads(Path(path).read_text(), parse_constant=lambda _: require(False, 'Nonfinite JSON'))


def atomic_write(path, body, immutable=False):
    path = Path(path)
    require(not path.is_symlink(), 'Output symlink forbidden')
    if immutable and path.exists():
        require(path.read_bytes() == body, f'Frozen artifact differs; stop for review: {path.name}')
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.pending-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(body); f.flush(); os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name): os.unlink(name)


def csv_bytes(rows, fields):
    s = io.StringIO(newline='')
    w = csv.DictWriter(s, fieldnames=fields, lineterminator='\n')
    w.writeheader(); w.writerows(rows)
    return s.getvalue().encode()


def secure_path(root, relative):
    root = Path(root).resolve()
    path = root/relative
    require(path.resolve().is_relative_to(root), 'Output collision/path escape')
    inside = [path]+[p for p in path.parents if p.is_relative_to(root)]
    require(not any(p.is_symlink() for p in inside), 'Output symlink forbidden')
    return path


def import_local(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT/relative)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


itad = import_local('expansion_contract', 'src/03_fetch_itad.py')
audit = import_local('expansion_calendar', 'src/04_audit_autumn_evidence.py')


@contextmanager
def offline_guard():
    def forbidden(*args, **kwargs):
        raise AssertionError('Network forbidden in preparation and offline tests')
    with patch('socket.getaddrinfo', forbidden), patch('socket.create_connection', forbidden), \
         patch('socket.socket.connect', forbidden), patch('socket.socket.connect_ex', forbidden):
        yield


def protected_inventory(root=ROOT):
    """Validate the entire approved 8A receipt chain, including its own bytes."""
    root = Path(root)
    prior = read_json(root/PRIOR_RECEIPT)
    require(prior['status'] == 'PASS', 'Phase 8A is not verified')
    expected = {}
    for group in ['protected_after_sha256', 'source_sha256', 'output_sha256']:
        for p, h in prior[group].items():
            require(p not in expected or expected[p] == h, 'Conflicting prior inventory')
            expected[p] = h
    expected[PRIOR_RECEIPT] = digest(root/PRIOR_RECEIPT)
    rows = []
    for p, h in sorted(expected.items()):
        require((root/p).is_file(), f'Missing protected artifact: {p}')
        require(digest(root/p) == h, f'Protected artifact changed: {p}')
        rows.append(dict(path=p, size_bytes=(root/p).stat().st_size, sha256=h))
    result = dict(schema_version=1, phase='8B.1', authorized_documentation_changes=DOCS, files=rows)
    if (root/INVENTORY).exists():
        require(read_json(root/INVENTORY) == result, 'Pre-work inventory mismatch')
    return result


def read_candidates(path):
    with Path(path).open(newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        require(reader.fieldnames == FIELDS, 'Candidate manifest schema mismatch')
        rows = list(reader)
    require(all(None not in r and all(v is not None for v in r.values()) for r in rows), 'Malformed candidate row')
    ids = [r['appid'] for r in rows]
    require(len(ids) == len(set(ids)), 'Duplicate candidate AppIDs')
    for r in rows:
        require(re.fullmatch(r'[1-9][0-9]*', r['appid']) and int(r['appid']) <= 2**32-1, 'Invalid candidate AppID')
        require(r['pilot_membership'] in {'0', '1'}, 'Invalid pilot membership')
        if r['probability_sample_rank']:
            d = date.fromisoformat(r['release_date'])
            require(r['pilot_membership'] == '0' and r['sampling_stratum'] in STRATA and
                    d.isoformat() == r['release_date'] and d < date(2023, 11, 21) and
                    r['release_year'] == str(d.year) and
                    all(r[f'eligibility_{y}'] == '1' and r[f'release_hour_uncertain_{y}'] == '0' for y in (2023, 2024, 2025)),
                    'Ineligible nonpilot sampling-frame member')
            require(r['sampling_priority'] == hashlib.sha256(f"42|{r['appid']}".encode()).hexdigest(), 'Phase 8A sampling priority mismatch')
            require(r['selection_status'] in {'selected_expansion_candidate', 'eligible_reserve'}, 'Invalid frame status')
    frame = [r for r in rows if r['probability_sample_rank']]
    require(sorted(int(r['probability_sample_rank']) for r in frame) == list(range(1, len(frame)+1)), 'Candidate rank gap/duplicate')
    return rows


def allocate_membership(rows):
    """Outcomes and retrieval variables are deliberately not inputs to this rule."""
    by_stratum = defaultdict(list)
    for r in rows:
        if r['probability_sample_rank']:
            require(r['pilot_membership'] == '0', 'Pilot cannot enter probability frame')
            by_stratum[r['sampling_stratum']].append(r)
    members = []
    for stratum in STRATA:
        group = sorted(by_stratum[stratum], key=lambda r: (hashlib.sha256(
            f"{MEMBERSHIP_SALT}|{r['appid']}".encode()).hexdigest(), int(r['appid'])))
        n_eval = (len(group)+2)//5  # nearest 20%, integer rule; never revised after retrieval
        for i, r in enumerate(group):
            members.append(dict(appid=r['appid'], release_date=r['release_date'], sampling_stratum=stratum,
                phase8a_candidate_rank=int(r['probability_sample_rank']),
                evaluation_group='sealed_evaluation' if i < n_eval else 'development',
                assignment_priority=hashlib.sha256(f"{MEMBERSHIP_SALT}|{r['appid']}".encode()).hexdigest()))
    return sorted(members, key=lambda r: int(r['appid']))


def select_smoke(members):
    selected = sorted(members, key=lambda r: r['phase8a_candidate_rank'])[:20]
    require(len(selected) == 20, 'Exactly 20 new games required')
    return [dict(r, planned_request_eligibility='pending_explicit_approval',
                 expected_output_namespace=f"{RAW_ROOT}/{r['evaluation_group']}") for r in selected]


def validate_membership(members, expected):
    require(members == expected, 'Frozen membership mismatch')
    require(len({r['appid'] for r in members}) == len(members), 'Membership overlap')
    require(all(r['evaluation_group'] in {'development', 'sealed_evaluation'} for r in members), 'Unknown evaluation group')


def development_inputs(rows, members):
    """Fail closed on unknown, pilot or held-out games, in EVERY sale year.

    This is the required adapter for future development code, not a model fitter.
    It checks identity before touching any target/feature values.
    """
    groups = {int(r['appid']): r['evaluation_group'] for r in members}
    require(len(groups) == len(members), 'Membership overlap')
    for r in rows:
        require(groups.get(int(r['appid'])) == 'development', 'Sealed/unknown/pilot AppID cannot enter development inputs')
        require(int(r['sale_year']) in {2023, 2024, 2025}, 'Unsupported historical year')
    return rows


def implementation_hashes(root=ROOT):
    return {p: digest(Path(root)/p) for p in ['src/11_prepare_expansion_collection.py',
        'src/03_fetch_itad.py', 'src/04_audit_autumn_evidence.py', 'src/autumn_sale_calendar.json']}


def approval_manifest(root, members, smoke, inventory):
    require([r['phase8a_candidate_rank'] for r in smoke] == list(range(1, 21)), 'Trial must preserve the approved prefix')
    return dict(schema_version=1, trial_identity=TRIAL, collector_version=VERSION, approval_status='PENDING',
        network_requests_performed=0, exact_appids=[int(r['appid']) for r in smoke],
        sampling_manifest_sha256=digest(Path(root)/CANDIDATES),
        evaluation_membership_manifest_sha256=hashlib.sha256(csv_bytes(members, MEMBER_FIELDS)).hexdigest(),
        smoke_manifest_sha256=hashlib.sha256(csv_bytes(smoke, SMOKE_FIELDS)).hexdigest(),
        protected_inventory_sha256=hashlib.sha256(json_bytes(inventory)).hexdigest(),
        collector_implementation_sha256=implementation_hashes(root), configuration=CONFIG,
        planned_endpoints=[CONFIG['lookup_endpoint'], CONFIG['history_endpoint']],
        historical_scope_note='Retain the complete returned array after requested since; no undocumented end-date parameter. Later approved features must filter strictly before each 2023–2025 cutoff; no labels are generated by collection.',
        output_paths=dict(raw_root=RAW_ROOT, request_journal=f'{RAW_ROOT}/request_journal.json',
                          development=f'{RAW_ROOT}/development', sealed_evaluation=f'{RAW_ROOT}/sealed_evaluation'),
        expected_cache_schema='expansion_cache_v1: provenance + per-endpoint response; sealed CMS ciphertext for every evaluation response; no labels',
        sealing=dict(method='OpenSSL CMS EnvelopedData, AES-256-CBC, RSA recipient >=2048 bits',
            certificate='External public certificate required and bound by approval receipt SHA-256',
            custody='Private key must be retained by independent custodian outside developer access; explicit attestation required',
            trust_boundary='Trusted collector operator sees response memory. Encryption and the development adapter do not prevent deliberate bypass by an operator or repository owner. No filesystem-only blindness claim.'),
        approval_receipt_contract=dict(approval_status='APPROVED', trial_identity=TRIAL,
            pending_manifest_sha256='SHA-256 of this immutable pending manifest', maximum_total_requests=60,
            custodian_certificate_sha256='SHA-256 of externally supplied public certificate',
            private_key_external_to_development=True, custodian='Named independent custodian', authorized_by='Explicit human authorizer'),
        abort_conditions=['401/403', 'any redirect', 'invalid/excessive/missing Retry-After on 429',
            'credential reflection', 'unexpected response schema/shop', 'response-size or truncation suspicion',
            'request budget/endpoint attempt exhaustion', 'approval/input/implementation/certificate mismatch',
            'pilot or unapproved candidate/output collision', 'concurrent collector', 'missing sealing controls'])


def api_contract():
    return {
        'credential_presence': dict(status='VERIFIED LOCALLY', available=bool(os.environ.get('ITAD_API_KEY', '').strip())),
        'lookup_response_structure': dict(status='VERIFIED LOCALLY', detail='Saved pilot objects: found boolean, matched game.id UUID; provider current behavior not live-verified.'),
        'matching_rules': dict(status='VERIFIED LOCALLY', detail='Lookup by Steam AppID; no title fallback; preserve found=false separately. Provider mapping accuracy is UNKNOWN.'),
        'history_response_structure': dict(status='VERIFIED LOCALLY', detail='Local arrays: aware timestamp, shop.id/name, deal or null; preserve raw order, duplicate timestamps and ambiguity.'),
        'historical_timestamp_semantics': dict(status='DOCUMENTED BUT NOT LIVE-VERIFIED', detail='Change-oriented observations after requested since; initialized boundary records/backfill do not prove contemporary availability, continuity or duration.'),
        'pagination_support': dict(status='UNKNOWN', detail='Existing implementation has no pagination. Unexpected Link/cursor/object wrapper stops; one array request is an assumption.'),
        'response_size_limits': dict(status='UNKNOWN', detail='Provider limit unknown; collector safety cap 8 MiB is local policy, not a provider quota or complete truncation detector.'),
        'historical_backfill_completeness': dict(status='UNKNOWN', detail='No reliable provider completion indicator; every successful history remains completion UNVERIFIED, including empty arrays.'),
        'account_specific_request_quota': dict(status='UNKNOWN', detail='Historical documentation recorded 1000 requests/5 minutes; current account quota not verified.'),
        'rate_limit_headers': dict(status='DOCUMENTED BUT NOT LIVE-VERIFIED', detail='Retry-After/Date handled; reliable remaining/reset headers unknown.'),
        'retry_behavior': dict(status='VERIFIED LOCALLY', detail='Mock tests: <=3 attempts total per game/endpoint across restart; 408/transient 5xx/timeouts; bounded Retry-After; global 60-request cap.'),
        'timeout_behavior': dict(status='VERIFIED LOCALLY', detail='30-second urllib socket timeout, not a guaranteed whole-response wall-clock deadline.'),
        'cache_provenance': dict(status='VERIFIED LOCALLY', detail='Approval, membership, implementation and endpoint configuration bound; response hashes, atomic cache and durable journal. Live provider content remains unverified.')}


def preflight_report(info, approval_sha):
    lines = ['# Expansion collection preflight', '',
        'Preparation only. No network requests, new histories, labels, features or model fits. The 20-game trial remains pending explicit human approval and an external evaluation-data custodian.', '',
        '## Frozen sampling and evaluation design', '',
        f"The approved Phase 8A frame contains {info['frame_games']:,} nonpilot AppIDs. Within each existing release-period stratum, sort SHA-256(`{MEMBERSHIP_SALT}|appid`) and assign the first `floor((n+2)/5)` to sealed evaluation (nearest 20%). Remaining games form development. This salt is independent of seed-42 candidate sampling. Membership excludes every held-out AppID from development in all three years. The original 100 pilot games remain a separate diagnostic sample.", '',
        f"Groups: {info['membership_counts']['development']:,} development; {info['membership_counts']['sealed_evaluation']:,} sealed evaluation. The manifest is immutable by convention and hashed. Regeneration is permitted only from identical approved candidates, salt and allocation rule; a changed file stops, rather than rebalancing after collection.", '',
        'The trial is the existing rank-1–20 prefix, without replacements for nonresponse. Its 1/8/8/3 release allocation reasonably follows the frame; one older game limits diagnostics. It is not a representative discount-rate estimate. No outcomes, matches or coverage variables enter selection.', '',
        '| Rank | AppID | Reported release | Release stratum | Assignment |',
        '|---:|---:|---|---|---|']
    for r in info['smoke_candidates']:
        lines.append(f"| {r['phase8a_candidate_rank']} | {r['appid']} | {r['release_date']} | {r['sampling_stratum']} | {r['evaluation_group']} |")
    lines += ['', '## Access controls and evaluation protocol', '',
        'Evaluation lookup, error and history payloads must be encrypted in memory to an externally supplied RSA custodian certificate before any disk write, including quarantine. The repository stores no production private key or decryption entry point. Cache restart uses public transport/provenance metadata and skips sealed cached responses without decrypting. The development-input adapter rejects held-out, unknown and pilot IDs before reading targets, in every year. Existing pilot-only scripts remain unchanged and cannot consume expansion namespaces.', '',
        'The trusted collector operator can see responses in memory; repository owners can deliberately bypass Python guards. Encryption, restricted paths and filesystem permissions alone do not guarantee blindness. Separate custody, controlled collection execution, no developer access to the private key, and a logged custodian-authorized future unsealing decision are necessary. No evaluation-outcome access is authorized here. If custody cannot be established, live collection must not run. The public request journal exposes transport status and linkage, without outcomes or record counts. Ciphertext lengths and matching/transport statuses can still reveal coarse availability; these must not guide model selection or sample replacement.', '',
        'Later evaluation should distinguish development-game temporal testing (2023–2024 → 2025) from unseen-game 2025 testing (held-out games excluded in EVERY training year). Select models/preprocessing on development training only. The inspected pilot 2025 holdout cannot serve as fresh confirmation, and new games do not make 2025 an untouched event. Coverage and pilot-versus-expansion comparisons require separately approved analysis; no model is trained now.', '',
        '## Request scope and approval gate', '',
        'US, Steam shop 61, since 2021-01-01T00:00:00Z. Up to 20 AppID lookups and 20 histories if all match: at most 40 initial requests. Proposed hard cumulative budget: **60 HTTP attempts**, including retries and all restarts. At most three attempts per game/endpoint; unused budget is not permission for other games. Serial request starts are spaced at least one second, including restarts. Timeout is 30 seconds; exponential retry delays 2/4 seconds. 429 requires valid Retry-After at most 60 seconds. Authentication errors and redirects abort immediately.', '',
        'Journal reservations are atomically persisted before each attempt; a crash consumes the reservation conservatively. A nonblocking exclusive lock forbids concurrent collectors. Compatible cached successes, unmatched responses and empty arrays are reused. Failed attempts require explicit `--retry-failed` for reconsideration, within the original per-endpoint and global caps. No force refresh, replacement, pagination or larger-cohort mode exists.', '',
        'Missing retrieval, unmatched lookup, request failure, malformed JSON, empty history, ambiguous/null deals and unexpected schema remain separate states. Failures never become negative labels. Unexpected responses are quarantined and stop collection; truncation suspicion stops, and complete historical capture is never assumed. Duplicate timestamps and raw record order remain intact under existing audit rules. The endpoint has no locally supported end-date parameter; retain returned records intact, including observations after 2025, and apply exact historical cutoffs only in later separately approved feature construction.', '',
        '## API contract evidence', '', '| Item | Status | Evidence / limitation |', '|---|---|---|']
    for key, value in info['api_contract'].items():
        detail = str(value.get('available')) if key == 'credential_presence' else value['detail']
        lines.append(f"| {key.replace('_', ' ')} | {value['status']} | {detail} |")
    lines += ['', 'The encryption primitive is CMS AES-256-CBC; ciphertext/cache SHA-256 checks detect accidental modification, not malicious authenticity attacks by a repository owner. Provider schema compatibility, account quota, response truncation, backfill and actual matching remain unverified live. OpenSSL availability and mock encryption round-trip are checked offline; no dependencies are installed.', '',
        '## Reproduction and proposed future command', '', '```bash',
        'python3 -B src/11_prepare_expansion_collection.py --verify', '```', '',
        f'Pending approval-manifest SHA-256: `{approval_sha}`. Preserve this file; a human-authored approval receipt must bind this digest, the exact trial, budget, named authorizer/custodian and the external certificate digest. The code has no self-approval flag. Changing a digest, candidate set, implementation, budget or namespace rejects the receipt.', '',
        'The following command is a proposal only and MUST NOT run until explicit authorization and external key custody are established. The public certificate and approved receipt must be supplied by the responsible humans:', '', '```bash',
        'python3 -B src/11_prepare_expansion_collection.py --live \\',
        f'  --manifest-sha256 {approval_sha} \\',
        '  --approval-receipt /absolute/path/to/human-approved-trial-receipt.json \\',
        '  --custodian-cert /absolute/path/to/external-custodian-public-certificate.pem \\',
        '  --request-budget 60', '```', '',
        'No figure is needed: the cohort table and group counts directly describe the preflight. No histories or raw-output placeholder directories are created during preparation. Later collection, labels, feature scaling, model retraining and 500-game expansion require separate authorization.', '']
    return '\n'.join(lines).encode()


def prepare(root=ROOT, output_root=None):
    root = Path(root); out = Path(output_root or root)
    before = protected_inventory(root)
    rows = read_candidates(root/CANDIDATES)
    require(len(rows) == 99194 and sum(r['pilot_membership'] == '1' for r in rows) == 100, 'Approved catalog/pilot counts differ')
    members = allocate_membership(rows)
    require(len(members) == 61559, 'Approved frame differs')
    smoke = select_smoke(members)
    require(not {r['appid'] for r in smoke} & {r['appid'] for r in rows if r['pilot_membership'] == '1'}, 'Pilot overlap')
    require(Counter(r['sampling_stratum'] for r in members) == read_json(root/'reports/autumn_sale_scaling_feasibility.json')['sampling']['frame_by_stratum'], 'Approved strata differ')
    audit.canonical_windows(root)
    manifest = approval_manifest(root, members, smoke, before)
    sha = hashlib.sha256(json_bytes(manifest)).hexdigest()
    info = dict(phase='8B.1', status='PREPARATION_ONLY_PENDING_APPROVAL', frame_games=len(members), pilot_games=100,
        membership_counts=dict(Counter(r['evaluation_group'] for r in members)),
        membership_by_stratum={s: dict(Counter(r['evaluation_group'] for r in members if r['sampling_stratum'] == s)) for s in STRATA},
        membership_rule=dict(salt=MEMBERSHIP_SALT, evaluation_count_per_stratum='floor((n+2)/5)', seed=314159,
            target_fraction=0.2, scope='entire eligible nonpilot probability frame; pilot excluded'),
        smoke_candidates=smoke, smoke_strata=dict(Counter(r['sampling_stratum'] for r in smoke)),
        smoke_membership=dict(Counter(r['evaluation_group'] for r in smoke)),
        expected_requests=dict(max_lookup=20, max_history=20, max_initial=40, hard_cumulative_budget=60),
        api_contract=api_contract(), network_requests_performed=0, new_histories=0, new_labels=0, model_fits=0,
        approval_manifest_sha256=sha, figures='Omitted: cohort table suffices; no analytical figure needed.',
        live_blockers=['Explicit human approval receipt absent', 'External custodian certificate/custody not configured',
                       'ITAD_API_KEY absent' if not api_contract()['credential_presence']['available'] else 'Credential available; authorization still required'])
    for p, b in [(INVENTORY, json_bytes(before)), (MEMBERSHIP, csv_bytes(members, MEMBER_FIELDS)),
                 (SMOKE, csv_bytes(smoke, SMOKE_FIELDS)), (APPROVAL, json_bytes(manifest)),
                 (PREFLIGHT, json_bytes(info)), (REPORT, preflight_report(info, sha))]:
        atomic_write(secure_path(out, p), b, immutable=p in {INVENTORY, MEMBERSHIP, SMOKE})
    after = protected_inventory(root)
    require(before == after, 'Protected integrity failure')
    receipt = dict(phase='8B.1', status='PASS_PREPARATION_ONLY', network_requests_performed=0,
        new_histories=0, new_operational_labels=0, models_fitted=0, protected_files=len(before['files']),
        protected_inventory_sha256=hashlib.sha256(json_bytes(before)).hexdigest(), protected_artifacts_byte_identical=True,
        membership_counts=info['membership_counts'], smoke_membership=info['smoke_membership'],
        smoke_strata=info['smoke_strata'], approved_candidate_prefix=list(range(1, 21)),
        exact_smoke_games=20, pilot_overlap=0, approval_status='PENDING', maximum_total_requests=60,
        api_contract=info['api_contract'], source_sha256=implementation_hashes(root),
        output_sha256={p: digest(out/p) for p in OUTPUTS if p != VALIDATION},
        tests=dict(status='NOT_RUN'), determinism=dict(status='NOT_RUN'),
        unverified=['Live endpoint compatibility/quota/coverage/truncation', 'Actual independent custodian custody',
                    'End-to-end wall-clock timeout', 'Adversarial operator blindness; procedural trust required'])
    atomic_write(out/VALIDATION, json_bytes(receipt))
    return info, receipt


def validate_certificate(path):
    """Only a public RSA certificate, never a local private key, is accepted."""
    path = Path(path).resolve()
    require(path.is_file() and ROOT not in path.parents, 'Custodian certificate must be outside repository')
    require('PRIVATE KEY' not in path.read_text(), 'Private key forbidden')
    require(shutil.which('openssl'), 'OpenSSL unavailable; sealing blocked')
    env = dict(os.environ); env.pop('ITAD_API_KEY', None)
    pub = subprocess.run(['openssl', 'x509', '-in', str(path), '-noout', '-pubkey'],
                         capture_output=True, check=True, env=env).stdout
    text = subprocess.run(['openssl', 'rsa', '-pubin', '-text', '-noout'], input=pub,
                          capture_output=True, check=True, env=env).stdout.decode()
    match = re.search(r'(?:Public-Key|Public Key):\s*\((\d+) bit\)', text)
    require(match and int(match[1]) >= 2048, 'RSA >=2048 bits required')
    valid = subprocess.run(['openssl', 'x509', '-in', str(path), '-checkend', '0', '-noout'],
                           capture_output=True, env=env)
    require(valid.returncode == 0, 'Expired/invalid custodian certificate')
    return digest(path)


def seal_payload(value, cert):
    env = dict(os.environ); env.pop('ITAD_API_KEY', None)
    proc = subprocess.run(['openssl', 'cms', '-encrypt', '-binary', '-aes256', '-outform', 'DER', str(cert)],
                          input=json_bytes(value), capture_output=True, check=True, env=env)
    return base64.b64encode(proc.stdout).decode()


def gate(manifest, expected, manifest_sha, receipt, budget, cert_sha):
    require(manifest == expected and manifest['approval_status'] == 'PENDING', 'Manifest/candidate/configuration mismatch')
    require(manifest_sha == hashlib.sha256(json_bytes(manifest)).hexdigest(), 'Manifest digest mismatch')
    require(len(manifest['exact_appids']) == len(set(manifest['exact_appids'])) == 20, '20-game cap violated')
    require(budget == manifest['configuration']['maximum_total_requests'] == 60, 'Request-budget mismatch')
    require(isinstance(receipt, dict) and receipt.get('approval_status') == 'APPROVED', 'Explicit human approval missing')
    for key, value in dict(trial_identity=TRIAL, pending_manifest_sha256=manifest_sha,
                          maximum_total_requests=budget, custodian_certificate_sha256=cert_sha,
                          private_key_external_to_development=True).items():
        require(receipt.get(key) == value and type(receipt.get(key)) is type(value), f'Approval receipt mismatch: {key}')
    require(all(isinstance(receipt.get(k), str) and receipt[k].strip() for k in ['custodian', 'authorized_by']), 'Named approval and custody required')


class StopCollection(RuntimeError):
    pass


class Journal:
    """Cumulative attempt reservation, including crashes and resumed failures."""
    def __init__(self, path, binding, maximum=60):
        self.path = Path(path); self.maximum = maximum
        self.data = read_json(path) if self.path.exists() else dict(binding=binding, attempts=[])
        require(self.data['binding'] == binding, 'Journal approval mismatch')
        require(len(self.data['attempts']) <= maximum, 'Journal exceeds budget')
        self.lock = self.path.with_suffix('.lock')
        self.lock.parent.mkdir(parents=True, exist_ok=True)
        require(not self.lock.is_symlink(), 'Journal lock symlink forbidden')
        self.handle = self.lock.open('a+b')
        try: fcntl.flock(self.handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.handle.close(); raise StopCollection('Concurrent collector forbidden')
        # Read after acquiring lock to avoid a stale pre-lock snapshot.
        if self.path.exists():
            self.data = read_json(self.path)
            require(self.data['binding'] == binding and len(self.data['attempts']) <= maximum, 'Journal changed')

    def close(self):
        self.handle.close()

    def reserve(self, appid, endpoint):
        if len(self.data['attempts']) >= self.maximum:
            raise StopCollection('Total request budget exhausted')
        prior = [a for a in self.data['attempts'] if a['appid'] == appid and a['endpoint'] == endpoint]
        if len(prior) >= CONFIG['attempts_per_endpoint']:
            raise StopCollection('Per-endpoint attempt cap exhausted')
        # Pace across restarts, not only within a single process.
        if self.data['attempts']:
            last = self.data['attempts'][-1]
            delta = time.time()-last.get('completed_unix_time', last['reserved_unix_time'])
            if delta < CONFIG['request_start_spacing_seconds']:
                time.sleep(CONFIG['request_start_spacing_seconds']-delta)
        record = dict(appid=appid, endpoint=endpoint, reserved_unix_time=time.time(), status='reserved')
        self.data['attempts'].append(record)
        atomic_write(self.path, json_bytes(self.data))
        return record

    def finish(self, record, status):
        record['status'] = status  # transport only; no response bodies/history counts/labels
        record['completed_unix_time'] = time.time()
        atomic_write(self.path, json_bytes(self.data))


class Transport:
    def __init__(self, key):
        self.key = key
        self.opener = build_opener(itad.NoRedirect())

    def get(self, endpoint, params):
        req = Request(CONFIG['api_base']+endpoint+'?'+urlencode(params),
                      headers={'ITAD-API-Key': self.key, 'Accept': 'application/json'})
        try:
            response = self.opener.open(req, timeout=CONFIG['timeout_seconds'])
        except HTTPError as e:
            response = e
        with response:
            raw = response.read(CONFIG['maximum_response_bytes']+1)
            return response.code, dict(response.headers), raw


def request_response(transport, journal, appid, endpoint, params, key):
    for attempt in range(CONFIG['attempts_per_endpoint']):
        reservation = journal.reserve(appid, endpoint)
        incomplete = False
        try:
            code, headers, raw = transport.get(endpoint, params)
        except IncompleteRead as error:
            code, headers, raw, incomplete = 200, {}, error.partial, True
        except (URLError, TimeoutError, socket.timeout, ConnectionError, OSError, HTTPException):
            code, headers, raw = None, {}, b''
        header_text = json.dumps(dict(headers))
        if key.encode() in raw or json.dumps(key)[1:-1].encode() in raw or key in header_text or json.dumps(key)[1:-1] in header_text:
            journal.finish(reservation, 'credential_reflection_withheld')
            return dict(status='credential_reflection_withheld', stop=True)
        headers = {k.lower(): v for k, v in headers.items()}
        evidence = dict(http_status=code, request=dict(endpoint=endpoint, params=params), headers={k: headers[k] for k in
            ['retry-after', 'date', 'content-type', 'content-length', 'link'] if k in headers})
        if code in {401, 403} or (code is not None and 300 <= code < 400):
            journal.finish(reservation, f'http_{code}_abort')
            return dict(status='authentication_abort' if code in {401, 403} else 'redirect_abort', stop=True, **evidence)
        retryable = code is None or code in {408, 429, 500, 502, 503, 504}
        if retryable:
            pause = CONFIG['retry_backoff_seconds'][min(attempt, 1)]
            if code == 429:
                try:
                    value = headers['retry-after']
                    pause = float(value) if re.fullmatch(r'\d+', value) else max(0, parsedate_to_datetime(value).timestamp()-time.time())
                    require(0 <= pause <= CONFIG['maximum_retry_after_seconds'], 'Unbounded Retry-After')
                except (KeyError, ValueError, TypeError, OverflowError):
                    journal.finish(reservation, 'rate_limit_stop')
                    return dict(status='rate_limit_stop', stop=True, **evidence)
            journal.finish(reservation, 'transient_failure')
            if attempt == CONFIG['attempts_per_endpoint']-1:
                return dict(status='request_failed', stop=code == 429, **evidence)
            time.sleep(pause); continue
        journal.finish(reservation, 'response_received' if code == 200 else 'request_failed')
        if code != 200:
            return dict(status='request_failed', stop=False, **evidence)
        if incomplete or len(raw) > CONFIG['maximum_response_bytes'] or 'link' in headers or \
           ('content-length' in headers and (not headers['content-length'].isdigit() or int(headers['content-length']) != len(raw))):
            return dict(status='truncation_suspected', stop=True, raw_body_b64=base64.b64encode(raw).decode(), **evidence)
        try:
            payload = json.loads(raw.decode('utf-8'), parse_constant=lambda _: require(False, 'Nonfinite JSON'))
        except (ValueError, UnicodeDecodeError):
            return dict(status='malformed_json', stop=False, raw_body_b64=base64.b64encode(raw).decode(), **evidence)
        if key in json.dumps(payload, ensure_ascii=False):
            journal.finish(reservation, 'credential_reflection_withheld')
            return dict(status='credential_reflection_withheld', stop=True)
        return dict(status='retrieved', stop=False, payload=payload, raw_body_b64=base64.b64encode(raw).decode(),
                    response_sha256=hashlib.sha256(raw).hexdigest(), **evidence)
    raise AssertionError('Unreachable')


def cache_path(root, candidate):
    require(candidate['evaluation_group'] in {'development', 'sealed_evaluation'}, 'Invalid output group')
    require(re.fullmatch(r'[1-9][0-9]*', str(candidate['appid'])), 'Invalid output AppID')
    relative = f"{RAW_ROOT}/{candidate['evaluation_group']}/{candidate['appid']}.json"
    require(candidate['expected_output_namespace'] == f"{RAW_ROOT}/{candidate['evaluation_group']}", 'Output namespace mismatch')
    path = secure_path(root, relative)
    require(path.resolve().is_relative_to(Path(root).resolve()/RAW_ROOT), 'Output collision/path escape')
    return path


def store_response(cache, endpoint, response, group, cert):
    if group == 'sealed_evaluation':
        cache['responses'][endpoint] = dict(sealed_cms_der_b64=seal_payload(response, cert))
    else:
        cache['responses'][endpoint] = response


def collect(root, smoke, manifest, manifest_sha, receipt, receipt_sha, expected_manifest, cert, key, transport, retry_failed=False):
    """Internal runner; only main's independently checked approval path calls it.

    Binding plus exact prefix is rechecked here so injected candidates cannot
    exceed the approved set. Offline tests provide mock transports exclusively.
    """
    require(len(smoke) == 20 and [int(r['appid']) for r in smoke] == manifest['exact_appids'], 'Candidate-set/20-game cap mismatch')
    require(manifest_sha == hashlib.sha256(json_bytes(manifest)).hexdigest(), 'Manifest digest mismatch')
    gate(manifest, expected_manifest, manifest_sha, receipt, CONFIG['maximum_total_requests'], validate_certificate(cert))
    binding = dict(manifest_sha256=manifest_sha, receipt_sha256=receipt_sha, certificate_sha256=digest(cert))
    require(manifest['output_paths']['request_journal'] == f'{RAW_ROOT}/request_journal.json', 'Journal output collision')
    journal_path = secure_path(root, manifest['output_paths']['request_journal'])
    if not journal_path.exists():
        require(not any(journal_path.parent.rglob('*.json')), 'Missing request journal with existing caches; stop for review')
    journal = Journal(journal_path, binding, CONFIG['maximum_total_requests'])
    stopped = False
    try:
        for candidate in smoke:
            path = cache_path(root, candidate); appid = int(candidate['appid']); group = candidate['evaluation_group']
            cache = read_json(path) if path.exists() else dict(schema='expansion_cache_v1', appid=appid,
                trial_identity=TRIAL, evaluation_group=group, binding=binding, responses={},
                progress=dict(lookup='not_collected', history='not_collected'), history_completion='UNVERIFIED')
            require(cache['appid'] == appid and cache['binding'] == binding and cache['evaluation_group'] == group and
                    cache['trial_identity'] == TRIAL and cache['schema'] == 'expansion_cache_v1', 'Cache provenance mismatch')
            # Payload hashes bind safe reuse; never decrypt sealed responses.
            if path.exists():
                require(cache.get('responses_sha256') == hashlib.sha256(json_bytes(cache['responses'])).hexdigest(), 'Cache payload integrity failure')
                unsigned = {k: v for k, v in cache.items() if k != 'cache_sha256'}
                require(cache.get('cache_sha256') == hashlib.sha256(json_bytes(unsigned)).hexdigest(), 'Cache metadata integrity failure')
            if cache['progress']['lookup'] == 'unmatched' or cache['progress']['history'] in {'retrieved', 'sealed_stored'}:
                continue
            if not retry_failed and any(v == 'failed' for v in cache['progress'].values()):
                continue
            for endpoint in ['lookup', 'history']:
                if endpoint == 'lookup' and cache['progress']['lookup'] == 'matched': continue
                if endpoint == 'history' and cache['progress']['lookup'] != 'matched': break
                url = CONFIG[f'{endpoint}_endpoint']
                params = {'appid': appid} if endpoint == 'lookup' else dict(id=cache['provider_game_id'],
                    country=CONFIG['country'], shops=str(CONFIG['steam_shop_id']), since=CONFIG['requested_since'])
                response = request_response(transport, journal, appid, url, params, key)
                if response['status'] == 'retrieved':
                    try:
                        if endpoint == 'lookup':
                            gid = itad.lookup_id(response['payload'])
                            cache['progress']['lookup'] = 'matched' if gid else 'unmatched'
                            if gid: cache['provider_game_id'] = gid  # linkage only; no discount outcome
                        else:
                            diagnostics = itad.history_diagnostics(response['payload'])
                            require(not diagnostics['unexpected_shop_record_count'], 'Unexpected shop')
                            response['history_state'] = 'empty_history' if not response['payload'] else 'nonempty_history'
                            response['history_completion'] = 'UNVERIFIED'
                            response['duplicate_timestamp_excess'] = sum(n-1 for n in Counter(itad.stamp(r['timestamp']) for r in response['payload']).values())
                            cache['progress']['history'] = 'sealed_stored' if group == 'sealed_evaluation' else 'retrieved'
                    except (ValueError, KeyError, TypeError):
                        response['status'] = 'unexpected_schema'; response['stop'] = True
                        cache['progress'][endpoint] = 'failed'
                else:
                    cache['progress'][endpoint] = 'failed'
                require(digest(cert) == binding['certificate_sha256'], 'Custodian certificate changed during collection')
                store_response(cache, endpoint, response, group, cert)
                cache['responses_sha256'] = hashlib.sha256(json_bytes(cache['responses'])).hexdigest()
                cache['cache_sha256'] = hashlib.sha256(json_bytes({k: v for k, v in cache.items() if k != 'cache_sha256'})).hexdigest()
                atomic_write(path, json_bytes(cache))
                if response['status'] in {'unexpected_schema', 'truncation_suspected'}:
                    quarantine = path.parent/'quarantine'/f'{appid}-{endpoint}.json'
                    atomic_write(quarantine, json_bytes(dict(appid=appid, binding=binding, response=cache['responses'][endpoint])))
                if response.get('stop'):
                    stopped = True; break
                if cache['progress'][endpoint] in {'failed', 'unmatched'}: break
            if stopped: break
    finally:
        journal.close()
    return dict(status='STOPPED' if stopped else 'TRAVERSAL_FINISHED', requests_reserved=len(journal.data['attempts']),
                histories_complete='UNVERIFIED', operational_labels_generated=0)


def verify(root=ROOT, output_root=None):
    root = Path(root); out = Path(output_root or root)
    before = protected_inventory(root)
    with offline_guard():
        suite = unittest.defaultTestLoader.discover(str(root/'tests'), pattern='test_expansion_collection.py')
        result = unittest.TextTestRunner(verbosity=1).run(suite)
        require(result.wasSuccessful(), 'Focused offline tests failed')
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            prepare(root, a); prepare(root, b)
            equal = {p: (Path(a)/p).read_bytes() == (Path(b)/p).read_bytes() for p in OUTPUTS}
            require(all(equal.values()), 'Deterministic preparation output mismatch')
        _, receipt = prepare(root, out)
    require(protected_inventory(root) == before, 'Protected integrity failure')
    receipt['tests'] = dict(status='PASS', passed=result.testsRun-len(result.skipped), failed=len(result.failures),
                           errors=len(result.errors), skipped=len(result.skipped), suite='test_expansion_collection.py')
    receipt['determinism'] = dict(status='PASS', isolated_complete_runs=2, byte_identical=equal,
        environment_note='Credential presence is environment-specific; identical in both runs. Live ciphertext intentionally uses fresh randomness; no live cache is generated in preparation.')
    receipt['test_source_sha256'] = digest(root/'tests/test_expansion_collection.py')
    atomic_write(out/VALIDATION, json_bytes(receipt))
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    parser.add_argument('--dry-run', action='store_true', help='Explicit offline default')
    parser.add_argument('--output-root', type=Path)
    parser.add_argument('--live', action='store_true', help='Separately authorized exact-20 trial only')
    parser.add_argument('--manifest-sha256')
    parser.add_argument('--approval-receipt', type=Path)
    parser.add_argument('--custodian-cert', type=Path)
    parser.add_argument('--request-budget', type=int)
    parser.add_argument('--retry-failed', action='store_true')
    args = parser.parse_args(argv)
    try:
        if not args.live:
            require(not any([args.approval_receipt, args.manifest_sha256, args.custodian_cert,
                             args.request_budget, args.retry_failed]), 'Live-only arguments require explicit --live')
            with offline_guard():
                receipt = verify(output_root=args.output_root) if args.verify else prepare(output_root=args.output_root)[1]
            print(f"{receipt['status']}; network requests=0; approval=PENDING")
            return 0
        require(not args.verify and not args.dry_run and not args.output_root, 'Live/default mode conflict; output override forbidden')
        require(args.approval_receipt and args.manifest_sha256 and args.custodian_cert and args.request_budget,
                'Live collection requires explicit approval, digest, custodian certificate and request budget')
        inventory = protected_inventory()
        rows = read_candidates(ROOT/CANDIDATES); members = allocate_membership(rows); smoke = select_smoke(members)
        require((ROOT/MEMBERSHIP).read_bytes() == csv_bytes(members, MEMBER_FIELDS) and
                (ROOT/SMOKE).read_bytes() == csv_bytes(smoke, SMOKE_FIELDS), 'Frozen memberships/candidate-set mismatch')
        manifest = read_json(ROOT/APPROVAL)
        expected = approval_manifest(ROOT, members, smoke, inventory)
        require(digest(ROOT/APPROVAL) == args.manifest_sha256, 'Approval-manifest file digest mismatch')
        cert_sha = validate_certificate(args.custodian_cert)
        receipt = read_json(args.approval_receipt)
        gate(manifest, expected, args.manifest_sha256, receipt, args.request_budget, cert_sha)
        key = os.environ.get('ITAD_API_KEY', '').strip()
        require(bool(key), 'ITAD_API_KEY unavailable; no request performed')
        result = collect(ROOT, smoke, manifest, args.manifest_sha256, receipt, digest(args.approval_receipt),
                         expected, args.custodian_cert, key, Transport(key), args.retry_failed)
        require(protected_inventory() == inventory, 'Protected integrity failure')
        print(json.dumps(result, sort_keys=True))
        return 1 if result['status'] == 'STOPPED' else 0
    except (ValueError, StopCollection, OSError, subprocess.SubprocessError):
        # Do not print provider responses, exception text, credentials or URLs.
        print('STOP: preflight/approval/collection safeguard rejected execution; no further requests.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
