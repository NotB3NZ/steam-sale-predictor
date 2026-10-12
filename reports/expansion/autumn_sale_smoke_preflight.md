# Expansion collection preflight

Preparation only. No network requests, new histories, labels, features or model fits. The 20-game trial remains pending explicit human approval and an external evaluation-data custodian.

## Frozen sampling and evaluation design

The approved Phase 8A frame contains 61,559 nonpilot AppIDs. Within each existing release-period stratum, sort SHA-256(`steam-autumn-unseen-v1|314159|appid`) and assign the first `floor((n+2)/5)` to sealed evaluation (nearest 20%). Remaining games form development. This salt is independent of seed-42 candidate sampling. Membership excludes every held-out AppID from development in all three years. The original 100 pilot games remain a separate diagnostic sample.

Groups: 49,247 development; 12,312 sealed evaluation. The manifest is immutable by convention and hashed. Regeneration is permitted only from identical approved candidates, salt and allocation rule; a changed file stops, rather than rebalancing after collection.

The trial is the existing rank-1–20 prefix, without replacements for nonresponse. Its 1/8/8/3 release allocation reasonably follows the frame; one older game limits diagnostics. It is not a representative discount-rate estimate. No outcomes, matches or coverage variables enter selection.

| Rank | AppID | Reported release | Release stratum | Assignment |
|---:|---:|---|---|---|
| 1 | 1521870 | 2021-02-01 | 2020_2022 | development |
| 2 | 747130 | 2017-11-27 | 2015_2019 | sealed_evaluation |
| 3 | 2494860 | 2023-11-09 | 2023_before_sale | development |
| 4 | 1110980 | 2020-02-14 | 2020_2022 | development |
| 5 | 779950 | 2019-12-13 | 2015_2019 | development |
| 6 | 1777210 | 2021-10-17 | 2020_2022 | development |
| 7 | 556770 | 2016-11-24 | 2015_2019 | development |
| 8 | 1868280 | 2022-02-04 | 2020_2022 | development |
| 9 | 410910 | 2015-10-23 | 2015_2019 | development |
| 10 | 2358320 | 2023-07-06 | 2023_before_sale | sealed_evaluation |
| 11 | 274560 | 2014-03-19 | before_2015 | sealed_evaluation |
| 12 | 2009840 | 2022-06-28 | 2020_2022 | development |
| 13 | 674230 | 2018-02-01 | 2015_2019 | development |
| 14 | 2143160 | 2022-10-03 | 2020_2022 | sealed_evaluation |
| 15 | 857420 | 2018-08-30 | 2015_2019 | development |
| 16 | 2259360 | 2023-09-08 | 2023_before_sale | development |
| 17 | 1345940 | 2020-12-31 | 2020_2022 | development |
| 18 | 947250 | 2018-11-12 | 2015_2019 | development |
| 19 | 1917600 | 2022-03-21 | 2020_2022 | development |
| 20 | 594000 | 2019-06-19 | 2015_2019 | development |

## Access controls and evaluation protocol

Evaluation lookup, error and history payloads must be encrypted in memory to an externally supplied RSA custodian certificate before any disk write, including quarantine. The repository stores no production private key or decryption entry point. Cache restart uses public transport/provenance metadata and skips sealed cached responses without decrypting. The development-input adapter rejects held-out, unknown and pilot IDs before reading targets, in every year. Existing pilot-only scripts remain unchanged and cannot consume expansion namespaces.

The trusted collector operator can see responses in memory; repository owners can deliberately bypass Python guards. Encryption, restricted paths and filesystem permissions alone do not guarantee blindness. Separate custody, controlled collection execution, no developer access to the private key, and a logged custodian-authorized future unsealing decision are necessary. No evaluation-outcome access is authorized here. If custody cannot be established, live collection must not run. The public request journal exposes transport status and linkage, without outcomes or record counts. Ciphertext lengths and matching/transport statuses can still reveal coarse availability; these must not guide model selection or sample replacement.

Later evaluation should distinguish development-game temporal testing (2023–2024 → 2025) from unseen-game 2025 testing (held-out games excluded in EVERY training year). Select models/preprocessing on development training only. The inspected pilot 2025 holdout cannot serve as fresh confirmation, and new games do not make 2025 an untouched event. Coverage and pilot-versus-expansion comparisons require separately approved analysis; no model is trained now.

## Request scope and approval gate

US, Steam shop 61, since 2021-01-01T00:00:00Z. Up to 20 AppID lookups and 20 histories if all match: at most 40 initial requests. Proposed hard cumulative budget: **60 HTTP attempts**, including retries and all restarts. At most three attempts per game/endpoint; unused budget is not permission for other games. Serial request starts are spaced at least one second, including restarts. Timeout is 30 seconds; exponential retry delays 2/4 seconds. 429 requires valid Retry-After at most 60 seconds. Authentication errors and redirects abort immediately.

Journal reservations are atomically persisted before each attempt; a crash consumes the reservation conservatively. A nonblocking exclusive lock forbids concurrent collectors. Compatible cached successes, unmatched responses and empty arrays are reused. Failed attempts require explicit `--retry-failed` for reconsideration, within the original per-endpoint and global caps. No force refresh, replacement, pagination or larger-cohort mode exists.

Missing retrieval, unmatched lookup, request failure, malformed JSON, empty history, ambiguous/null deals and unexpected schema remain separate states. Failures never become negative labels. Unexpected responses are quarantined and stop collection; truncation suspicion stops, and complete historical capture is never assumed. Duplicate timestamps and raw record order remain intact under existing audit rules. The endpoint has no locally supported end-date parameter; retain returned records intact, including observations after 2025, and apply exact historical cutoffs only in later separately approved feature construction.

## API contract evidence

| Item | Status | Evidence / limitation |
|---|---|---|
| credential presence | VERIFIED LOCALLY | False |
| lookup response structure | VERIFIED LOCALLY | Saved pilot objects: found boolean, matched game.id UUID; provider current behavior not live-verified. |
| matching rules | VERIFIED LOCALLY | Lookup by Steam AppID; no title fallback; preserve found=false separately. Provider mapping accuracy is UNKNOWN. |
| history response structure | VERIFIED LOCALLY | Local arrays: aware timestamp, shop.id/name, deal or null; preserve raw order, duplicate timestamps and ambiguity. |
| historical timestamp semantics | DOCUMENTED BUT NOT LIVE-VERIFIED | Change-oriented observations after requested since; initialized boundary records/backfill do not prove contemporary availability, continuity or duration. |
| pagination support | UNKNOWN | Existing implementation has no pagination. Unexpected Link/cursor/object wrapper stops; one array request is an assumption. |
| response size limits | UNKNOWN | Provider limit unknown; collector safety cap 8 MiB is local policy, not a provider quota or complete truncation detector. |
| historical backfill completeness | UNKNOWN | No reliable provider completion indicator; every successful history remains completion UNVERIFIED, including empty arrays. |
| account specific request quota | UNKNOWN | Historical documentation recorded 1000 requests/5 minutes; current account quota not verified. |
| rate limit headers | DOCUMENTED BUT NOT LIVE-VERIFIED | Retry-After/Date handled; reliable remaining/reset headers unknown. |
| retry behavior | VERIFIED LOCALLY | Mock tests: <=3 attempts total per game/endpoint across restart; 408/transient 5xx/timeouts; bounded Retry-After; global 60-request cap. |
| timeout behavior | VERIFIED LOCALLY | 30-second urllib socket timeout, not a guaranteed whole-response wall-clock deadline. |
| cache provenance | VERIFIED LOCALLY | Approval, membership, implementation and endpoint configuration bound; response hashes, atomic cache and durable journal. Live provider content remains unverified. |

The encryption primitive is CMS AES-256-CBC; ciphertext/cache SHA-256 checks detect accidental modification, not malicious authenticity attacks by a repository owner. Provider schema compatibility, account quota, response truncation, backfill and actual matching remain unverified live. OpenSSL availability and mock encryption round-trip are checked offline; no dependencies are installed.

## Reproduction and proposed future command

```bash
python3 -B src/11_prepare_expansion_collection.py --verify
```

Pending approval-manifest SHA-256: `19f09098f2dc4f5ddfd929af2b12e9cb890bdc1bf42ae49f2855e9d7287c5336`. Preserve this file; a human-authored approval receipt must bind this digest, the exact trial, budget, named authorizer/custodian and the external certificate digest. The code has no self-approval flag. Changing a digest, candidate set, implementation, budget or namespace rejects the receipt.

The following command is a proposal only and MUST NOT run until explicit authorization and external key custody are established. The public certificate and approved receipt must be supplied by the responsible humans:

```bash
python3 -B src/11_prepare_expansion_collection.py --live \
  --manifest-sha256 19f09098f2dc4f5ddfd929af2b12e9cb890bdc1bf42ae49f2855e9d7287c5336 \
  --approval-receipt /absolute/path/to/human-approved-trial-receipt.json \
  --custodian-cert /absolute/path/to/external-custodian-public-certificate.pem \
  --request-budget 60
```

No figure is needed: the cohort table and group counts directly describe the preflight. No histories or raw-output placeholder directories are created during preparation. Later collection, labels, feature scaling, model retraining and 500-game expansion require separate authorization.
