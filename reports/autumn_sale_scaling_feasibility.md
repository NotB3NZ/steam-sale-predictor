# Historical data scaling feasibility

## Executive summary

The local catalog supports a deterministic candidate plan for totals of 500, 1,000, 2,000 and 5,000 games, with the original pilot reported separately. This establishes sampling feasibility, not historical coverage or a completed expanded dataset. Responsible collection feasibility is conditional on account quota, matching success, response completeness, timing provenance and changes to pilot-specific pipeline guards. No collection, new labels, feature generation or model fitting occurs in this audit.

## Master catalog audit

Authoritative catalog: `data/intermediate/games_master.csv`, 99,194 rows and 99,194 unique valid AppIDs. Missing IDs: 0; invalid IDs: 0; duplicate excess rows: 0. Missing release dates: 0; invalid dates: 0; inconsistent release years: 0.

The catalog is the cleaned positive-source-price population from the local metadata snapshot, not the complete Steam population. Unknown snapshot time, excluded zero-price products, delisted/missing titles, software/non-game products and corrected/early-access release interpretation limit representativeness. No contemporary metadata is approved as a historical predictor. The source-stage report describes 125,855 raw entries; this audit counts the authoritative cleaned master directly rather than treating that report as a new raw-source audit.

## Sale-year eligibility

Release dates are date-only. Use the existing official Pacific calendar dates and exact UTC observation boundaries from `src/autumn_sale_calendar.json`. No midnight release timestamp is invented. Existing eligibility includes a start-day release with uncertainty. End-day releases may be inside or after the 10 AM boundary; report them separately. Interior-date counts describe releases strictly between the boundary dates, not confirmed purchase availability.

| Year | Before start date | Start day uncertain | Date-rule eligible | Interior sale dates | End day uncertain | After end date |
| --- | --- | --- | --- | --- | --- | --- |
| 2023 | 61658 | 23 | 61681 | 124 | 25 | 37364 |
| 2024 | 76209 | 47 | 76256 | 223 | 67 | 22648 |
| 2025 | 90839 | 54 | 90893 | 246 | 50 | 8005 |

Eligible for all three by the existing date rule: 61,681. Strictly before all three starts: 61,658. New sampling excludes start-day uncertainty; the separately retained pilot is unchanged. Date eligibility is not independent evidence of actual Steam sale participation or continuous availability.

## Existing historical evidence

All 100 cached pilot games reconcile with the collection manifest and original response bodies. Local temporal records: 5,568; valid price records: 5,568; discounted observations: 2,783. Games with any temporal records: 97; any valid price records: 97; any qualifying discount observations: 88; empty histories: 3.

| Year | Any before | Any inside | Any after | Valid prices before | Discount inside |
| --- | --- | --- | --- | --- | --- |
| 2023 | 96 | 57 | 77 | 96 | 55 |
| 2024 | 97 | 60 | 76 | 97 | 60 |
| 2025 | 97 | 61 | 74 | 97 | 60 |

Every row above has denominator 100 cached games. At catalog level only 100 / 99,194 have local caches; 99,094 have no local cached evidence and unknown provider-side availability. Cached empty responses are distinct from uncollected games. Complete continuous capture remains unestablished for all 100 cached games. No interpolation, price continuity or discount campaign duration is inferred. Existing A/B/C/D categories reconcile with local observations, but no new operational labels are emitted. Recorded absence does not establish actual non-discounting.

Potential external evidence is limited to the existing provider lookup/history contract. Matching and historical availability for new games cannot be determined without separately authorized requests. No estimate transfers the pilot's 97% nonempty-history rate to the wider population.

## Collection feasibility

Provider: IsThereAnyDeal. Endpoints: `/games/lookup/v1` and `/games/history/v2`; header authentication comes from `ITAD_API_KEY`. Scope remains US / Steam shop 61 / since 2021-01-01. Current code sends one array-returning history request per matched game; no cursor, offset, page or pagination loop. Provider limits/truncation remain unestablished offline.

Existing Phase 4 report records a verified-email default of 1,000 requests per five minutes, reviewed 2026-10-05. Account-specific/current quota is NOT verified by this audit. Default serial request-start spacing at least one second. Latency, throttles, retries and checkpoints add time; floors are not completion-time forecasts. At most three attempts. Exponential waits 2s/4s for transient connection/408/5xx failures; 429 honors Retry-After. Missing/invalid Retry-After or waits >60s stop; 401/403 and redirects abort. Per-request timeout 30s.

| Planned total | New uncached | Requests, all matched | Cold start requests | Pacing floor, minutes |
| --- | --- | --- | --- | --- |
| 500 | 400 | 800 | 1000 | 13.3 |
| 1000 | 900 | 1800 | 2000 | 30.0 |
| 2000 | 1900 | 3800 | 4000 | 63.3 |
| 5000 | 4900 | 9800 | 10000 | 163.3 |

The totals include 100 reusable pilot caches. New-game request formula: `U + q*U*H`, plus retries; mapping fractions 0.5, 0.8 and 1.0 and a hypothetical stricter quota scenario are saved in JSON. Current code assumes H=1, but provider-side limits or a future revised pagination contract could change that. At most three attempts per endpoint gives 6U requests in the all-matched worst-attempt scenario; authentication/rate-limit aborts can stop earlier. Pacing figures are request-start lower bounds, not wall-clock completion forecasts. Latency, 30-second timeouts, retries, quota and manual resume can dominate.

Atomic JSON replacement, configuration/provenance checks, compatible cache reuse, deliberate retry of incomplete matched histories, forced refresh archives old files. Each completed game is cached; restart reuses valid cache. Manifest/report written after traversal; no durable per-attempt scheduler or bulk progress checkpoint. Existing smoke gate is pilot-hash-bound. No documented response-size cap or truncation detector in current code; entire response/body and decoded history retained in memory and duplicated in cache wrappers. Provider cap unknown.

Pilot cache wrappers total 3,896,051 bytes. They duplicate parsed history and original body. Storage scenarios in JSON use the observed nonrepresentative mean and are sensitivity calculations only; they are not a coverage or response-size forecast. The history request date boundary does not establish earlier history or contemporaneous availability; initialized boundary timestamps and backfills remain unresolved.

## Sampling strategy

61,559 nonpilot games enter the restricted balanced historical frame. Use release-period strata, seed 42, within-stratum SHA-256 priorities and exact rational proportional interleaving to form nested cohorts. Totals include the separately identified 100-game pilot. Selection ignores discount outcomes, evidence abundance, matching success and contemporary snapshots. The [sampling plan](autumn_sale_sampling_plan.md) documents fields, allocations and inclusion fractions. The [candidate manifest](../data/intermediate/autumn_sale_scaling_candidates.csv) is planning only.

## Labeling pipeline readiness

The operational definition is reusable: A -> recorded discount (1); B/D -> no qualifying recorded discount (0); C -> null/review. None provides verified sale participation. Current labeling assumes the pilot input paths, 100 games, 300 rows and exact pilot category/target counts. Upstream auditing and collection likewise use pilot paths and a pilot-bound smoke gate. Parameterize cohort identity and output namespace, separate legacy regression checks, and validate historically eligible pairs before producing new labels. Keep failed/unmatched/missing collection statuses separate from operational negatives; do not fabricate negative labels for absent retrievals.

## Feature pipeline readiness

The unchanged 15-feature allowlist is verified against the Phase 6 manifest and source. The current feature builder requires 100 pilot/manifests, a complete 300-pair panel and exactly 175 positive / 125 negative labels; static features reject negative age. A later-entry panel needs eligibility-aware construction instead of every game in every year. Existing model wrappers reject null targets, while evidence category C correctly remains nullable. Future analysis needs an explicit missing-target/failed-retrieval accounting policy; do not recode ambiguity as zero or silently discard it to pass legacy guards. Date uncertainty, null history summaries, mixed currencies and latest-timestamp conflicts must retain existing semantics. Pricing inputs must remain strictly before exact UTC cutoffs; no snapshot price, reviews or activity enters historical predictors. Feature functions can be reused once paths/count checks are parameterized; feature definitions must not change.

At 5,000 games, a balanced three-year panel has at most 15,000 rows, but response/provenance size is unknown. Current all-history loading and repeated filter/sort operations can amplify memory; measure records and stream/chunk by game in Phase 8B. Do not extrapolate a latency or memory benchmark from uncollected games. Training-only missing-value handling belongs to later authorized modeling.

Concrete source barriers (line references to unchanged files):

- `src/06_build_operational_labels.py:43`: `'games': ('data/intermediate/pilot_games.csv', ['AppID', 'Name', 'release_date']),`
- `src/06_build_operational_labels.py:125`: `require(set(pairs) == expected and set(games) == set(manifests), 'Expected every pilot AppID for every sale year')`
- `src/06_build_operational_labels.py:163`: `require(r['cache_path'] == manifest['cache_path'] == f'data/raw/itad/{appid}.json', f'Cache path mismatch: {key}')`
- `src/06_build_operational_labels.py:212`: `require(stats['total_rows'] == 300 and stats['duplicate_count'] == 0, 'Expected 300 unique operational rows')`
- `src/06_build_operational_labels.py:213`: `require(stats['category_counts'] == dict(A=175, B=3, C=0, D=122), 'Current pilot categories differ; review required')`
- `src/06_build_operational_labels.py:214`: `require(stats['operational_label_counts'] == {'1': 175, '0': 125, 'null': 0}, 'Unexpected operational label counts')`
- `src/06_build_operational_labels.py:215`: `require(stats['pu_status_counts'] == {'positive': 175, 'unlabeled': 125}, 'Unexpected PU counts')`
- `src/06_build_operational_labels.py:228`: `require(len(inputs['games']) == 100, 'Expected unchanged 100-game pilot')`
- `src/06_build_operational_labels.py:317`: `'PU status totals: **175 positive / 125 unlabeled**. All 300 original game-year pairs remain, with unchanged categories. There are zero current C cases and zero null labels. Label counts are checked against the approved frozen pilot; an unexpected scope/count change stops execution for review rather than forcing results.', '',`
- `src/07_build_autumn_features.py:235`: `header = read_table(root / 'data/intermediate/pilot_games.csv', ['AppID'])[0].keys()`
- `src/07_build_autumn_features.py:284`: `f"Rows: **{len(rows)}**; year counts: **100 / 100 / 100**. Currency conflicts: **{stats['currency_conflict_pair_count']}**; uncertain release-hour pairs: **{stats['uncertain_release_hour_count']}**. Constant baseline features: **{', '.join(stats['constant_features']) or 'none'}**. Unusual values are retained; no target-based feature selection is performed.", '',`
- `src/07_build_autumn_features.py:314`: `pilot = read_table(root / 'data/intermediate/pilot_games.csv', ['AppID', 'release_date', 'release_year'])`
- `src/07_build_autumn_features.py:316`: `require(len(pilot) == len(games) == 100 and set(pairs) == {(a, y) for a in games for y in windows}, 'Expected original 100 games / 300 pairs')`
- `src/07_build_autumn_features.py:326`: `require(len(manifest) == len(manifests) == 100 and set(manifest) == set(games), 'Manifest identities differ')`
- `src/07_build_autumn_features.py:334`: `require(Counter(r['discount_observed'] for r in model) == {1: 175, 0: 125}, 'Approved target counts differ')`
- `src/08_train_baseline_models.py:175`: `require(len(train) == 200 and len(valid) == 100, 'Expected 200 training / 100 validation rows')`
- `src/08_train_baseline_models.py:176`: `require(set(train.appid) == set(valid.appid) and train.appid.nunique() == 100, 'Repeated pilot game identities mismatch')`
- `src/08_train_baseline_models.py:177`: `require(all(train.groupby('sale_year').size() == 100), 'Expected 100 rows per training year')`
- `src/08_train_baseline_models.py:187`: `require(len(frame) == len(features) == 300, 'Expected 300 game-year observations')`
- `src/08_train_baseline_models.py:190`: `require(frame[TARGET].notna().all() and set(frame[TARGET]) == {0, 1}, 'Invalid operational labels')`
- `src/08_train_baseline_models.py:200`: `require(train[TARGET].value_counts().to_dict() == {1: 115, 0: 85}, 'Training target count mismatch')`
- `src/08_train_baseline_models.py:201`: `require(valid[TARGET].value_counts().to_dict() == {1: 60, 0: 40}, 'Validation target count mismatch')`
- `src/08_train_baseline_models.py:215`: `require(len(merged) == 300 and (merged[TARGET] == merged[TARGET + '_source']).all(), 'Frozen operational label disagreement')`
- `src/08_train_baseline_models.py:276`: `require(len(out) == 200 and not out.duplicated(KEYS + ['model_name']).any(), 'Prediction row count/uniqueness failure')`
- `src/09_train_ensemble_models.py:143`: `require(len(train)==100*len(training_years) and len(valid)==100,'Temporal row count mismatch')`
- `src/09_train_ensemble_models.py:144`: `require(set(train.appid)==set(valid.appid) and valid.appid.nunique()==100,'Temporal identity mismatch')`
- `src/09_train_ensemble_models.py:152`: `require(len(predictions)==100*len(names) and set(predictions.model_name)==set(names),'Prediction model/row count mismatch')`
- `src/09_train_ensemble_models.py:233`: `require(set(train.sale_year.unique())==set(training_years) and len(train)==100*len(training_years),'Fitting received nontraining rows')`

Additional collector/upstream audit references are saved in JSON. No source barrier is repaired in Phase 8A.

## Generalization evaluation plan

Preassign new AppIDs to development and sealed game-level evaluation groups within release strata using an independent deterministic priority. For represented-game evaluation, train development games on eligible 2023–2024 rows and report their 2025 rows. For unseen-game evaluation, remove every held-out AppID from all training years, and evaluate only eligible 2025 rows for those games. Fit all preprocessing on development training only; choose configurations by training-only temporal/grouped resampling, never the examined pilot 2025 holdout.

Report pilot versus probability sample separately, and evaluate pre-cutoff coverage sensitivity using bins defined in development data. Account for retrieval failure, ambiguous labels and date uncertainty. Do not choose replacements or favorable targets after collection. Sampling weights apply only to the new restricted frame; repeated-game uncertainty should be clustered by AppID.

New held-out game outcomes could remain untouched if allocation and access controls are preregistered before collection. However, the 2025 event and model choices have already been inspected through the pilot. This can provide an untouched game-level evaluation, not a fully fresh event-level confirmatory test. Stronger confirmation requires a separately authorized unexamined event and verified dates/data. No 2026 dates, predictions or collection are created here.

## Risks and limitations

Provider matching/coverage, actual account quota, truncation limits, historical backfill, requested-since initialization, changing product availability, date revisions and early-access interpretation remain unresolved. Observation coverage may predict the operational labels. The catalog itself is snapshot-selected and includes some non-game products; the balanced frame excludes later releases. Increasing sample size alone does not fix these limitations or produce verified non-discounting labels.

## Recommended Phase 8B scope

Parameterize separate cohort-aware collection/evidence/label/feature namespaces and preserve the original pilot artifacts. Obtain explicit collection approval and confirm the account quota and current endpoint limits. Conduct a bounded smoke/coverage trial across release strata, retaining failures and empty histories. Assess retrieval sizes, timestamp provenance, ambiguity and nonresponse before approving 2,000–5,000 games. Freeze candidate and sealed evaluation memberships before outcomes are accessed. Bulk collection, model retraining, Phase 8B/8C and Phase 9 remain unstarted.

## Reproduction and visualizations

```bash
python3 -B src/10_audit_scaling_feasibility.py --verify
```

This command reads local files, executes only the Phase 8A offline tests (older model tests would retrain models), compares two complete audit executions and preserves all earlier artifacts. Four light-mode 300-DPI PNGs under `reports/figures/` show catalog release years, observed local evidence, planned sampling composition and the restricted population funnel. Every plotted value is stored in the feasibility JSON. Catalog and local-cache denominators are distinct; no chart portrays unknown external availability as observed absence.
