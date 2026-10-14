# Phase 6B — original operational labels and historical feature audit

The frozen 2,000-game cohort produces **6,000 unique game-year pairs** under
the unchanged pilot rule `operational_observed_v1`: **3,030 positives,
2,970 operational zeros, zero unknowns**. Every game has exactly the three
target years. There are no missing or duplicate pairs or cache parsing failures.

**An operational zero means no discount was observed in the available ITAD
evidence. It does not establish actual Steam Autumn Sale nonparticipation.**
The 100% operational label coverage is not a claim of complete observation of
every sale. The separate Phase 6A conservative diagnostic and all nine of its
files remain byte-for-byte unchanged. Its restricted modeling coverage is not
the target policy used here.

## Original rules and distributions

| Category | Unchanged evidence definition | Operational target |
| --- | --- | --- |
| A | At least one directly timestamped in-window qualifying discount | 1 |
| B | In-window records exist and all are valid full-price observations | 0 |
| C | In-window records exist, none qualifies as a discount, and some evidence is ambiguous | Unknown |
| D | No directly timestamped in-window record | 0 |

| Year | A | B | C | D | Positive | Operational zero | Unknown |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2023 | 979 | 10 | 0 | 1,011 | 979 | 1,021 | 0 |
| 2024 | 1,068 | 5 | 0 | 927 | 1,068 | 932 | 0 |
| 2025 | 983 | 8 | 0 | 1,009 | 983 | 1,017 | 0 |
| Total | 3,030 | 23 | 0 | 2,947 | 3,030 | 2,970 | 0 |

These are final **operational target values**, not verified participation
labels or a final model input dataset. Category C would remain blank if
encountered. Missing/failed caches and release-ineligible pairs remain unknown;
they are never converted to Category D. No such pairs exist in this cohort.
The original same-day release-hour review flag for AppID 2650840 / 2023 is
retained along with its B→0 target and operational eligibility.

The existing verified calendar and `PROJECT_CONTEXT.md` agree on these UTC
intervals. Label evidence uses start-inclusive, end-exclusive bounds; features
use timestamps strictly **before the start**:

| Year | Start, inclusive | End, exclusive |
| --- | --- | --- |
| 2023 | 2023-11-21T18:00:00Z | 2023-11-28T18:00:00Z |
| 2024 | 2024-11-27T18:00:00Z | 2024-12-04T18:00:00Z |
| 2025 | 2025-09-29T17:00:00Z | 2025-10-06T17:00:00Z |

All 2,000 caches are complete and readable. Of these, 1,919 contain nonempty
successful histories and 81 contain successful empty histories. Under the
original operational rule, the latter contribute **243 Category D zeros**;
this is explicitly missing observational evidence, not proof of no discounts.
1,918 games have usable pre-2026 price evidence. AppID 2270900 has only 2026
observations; these cannot enter any of the three historical feature sets.

## Reused implementation and small compatibility changes

| Component | Reuse and compatibility |
| --- | --- |
| `04_audit_autumn_evidence.py` | Existing parser, categories, window partitioning and raw-index provenance reused unchanged |
| `05_investigate_sale_coverage.py` | Existing coverage/conflict diagnostics reused unchanged |
| `06_build_operational_labels.py:construct_labels` | Existing executable A=1, B/D=0, C=Unknown mapping reused unchanged |
| `cohort_pipeline.py` | Added explicit `label_policy='operational'` / `--label-policy operational`; propagates original nonmissing targets into the modeling eligibility mask, retaining review flags. The separate conservative mode/default remains available for diagnostics and existing collection summaries |
| `07_build_autumn_features.py:build_features` | Existing 15-feature core, missingness, tie/currency handling and strict cutoffs reused unchanged; values calculated in memory for audit only |
| `08_train_baseline_models.py:fit_models` | Reusable training-only imputation/scaling and fixed baseline models; not executed |
| `09_train_ensemble_models.py:fit_models(..., cohort_mode=True)` | Reusable configurable training core; not executed |
| Legacy standalone pilot writers/split/report functions | Fixed 100-game paths/counts and historical receipts; use configurable cohort adapter instead |

`audit_cohort_operational.py` confines writes to a new reports directory,
blocks socket operations, reuses the evidence/label/feature cores, and verifies
all existing data/report/model inputs before writing. It creates target and
audit tables, not final feature/model datasets. Existing general output-path
protections remain intact.

The baseline comparison helper now searches Git history for bytes that actually
match the saved baseline hash when HEAD has advanced. This read-only comparison
fix does not alter the artifact or Phase 6A outputs.

Reproduce this audit with a **fresh**, separate reports directory:

```sh
env -u ITAD_API_KEY /usr/bin/python3 -B src/audit_cohort_operational.py \
  --cohort data/cohorts/cohort_2000.csv \
  --cache-dir data/cohorts/itad/cache \
  --reuse-cache data/raw/itad \
  --output-dir reports/cohort_2000_operational_recheck
```

For any future authorized configurable feature/model stage, explicitly supply
`--label-policy operational`; the default diagnostic policy would otherwise
exclude D from model eligibility despite retaining its target value.

## Feature-by-feature temporal availability

The complete machine-readable audit, including source, definition, historical
availability, cutoff, risk, missingness and required changes for **every
predictor, administrative column and requested absent feature**, is
[feature_leakage_audit.csv](feature_leakage_audit.csv).

Release-derived features below use the frozen cohort's reported release date,
cross-checked during the existing deterministic master/pilot selection. Their
historical validity assumes that reported date accurately describes release;
metadata revisions and early-access/full-release interpretation are unverified.
Game age is a Pacific calendar-date difference, not exact elapsed release time.

All price-derived features use parser-valid Steam shop 61 / US observations
whose UTC timestamp is strictly before the corresponding sale start above.
This prevents direct sale-time/future-timestamp leakage. It does **not** prove
that retrospective provider records were accessible at that historical instant.
None of these calculations needs a definition change for the existing target.

| Predictor | Existing definition | Availability / leakage constraint |
| --- | --- | --- |
| `game_age_days` | Sale-start Pacific date minus reported release date | Reported historical date; unknown release hour retained in audit |
| `release_year` | Year of reported release | Same reported-date assumption |
| `release_month` | Month of reported release | Same reported-date assumption |
| `release_quarter` | Quarter of reported release | Same reported-date assumption |
| `prior_price_record_count` | Number of valid earlier price observations | Pre-cutoff records only; not complete price history |
| `prior_discount_count` | Number of earlier discounted observations | Not distinct campaigns or sale count |
| `prior_discount_rate` | Discount observations / valid price observations | Observation ratio, not discounted-day frequency; null without prior prices |
| `days_since_last_price_record` | UTC days since latest valid earlier price record | Null without prior price; does not reconstruct price state |
| `days_since_last_discount` | UTC days since latest qualifying earlier discount | Null without prior discount |
| `max_prior_discount_pct` | Maximum explicit earlier qualifying cut | Earlier observations only; null without discounts |
| `mean_prior_discount_pct` | Mean explicit earlier qualifying cut | Observation-weighted, not time-weighted; conflicts remain distinct observations |
| `last_observed_price` | Latest valid earlier USD price | Null for latest-time conflicts/mixed or non-USD currencies; not current price |
| `last_observed_discount_pct` | Explicit cut at latest valid earlier record | Null for latest-time conflicts or absent prices |
| `has_prior_price_history` | Any valid earlier price record | Zero describes returned evidence only |
| `has_prior_discount_observation` | Any qualifying earlier discount | Zero does not establish absence of earlier discounts |

AppID, sale year, cutoff and `audit_release_hour_uncertain` are excluded from
predictors. Categories, targets, PU status, in-window counts/indices, future
coverage/empty-history flags, collection metadata and label-review flags must
also remain excluded. The approved allowlist enforces this separation.

**Previous Autumn Sale participation is not an implemented predictor.** No
addition is required to reuse the established baseline. If separately requested
later, earlier operational outcomes would describe observed evidence only and
must come from completed earlier-year windows; target-year/later labels cannot
be predictors. Earlier sale observations already enter later-year price
summaries legitimately as past information.

**Popularity indicators are excluded.** Estimated owners, lifetime Peak CCU,
reviews, scores and recommendations are undated snapshots. Current master
Price/Discount are also excluded. Adding these requires independently
timestamped historical snapshots; current values cannot substitute for them.

## Feature availability and data quality findings

All **6,000** feature sets passed removal of every at/after-cutoff observation
plus insertion of a synthetic discounted record exactly at the cutoff:
feature values remained identical. All **171,868 pre-cutoff record uses** were
verified against raw-index timestamps; cutoff violations: **zero**. The offline
tests also check independence from targets/categories and future history.

| Year | Pairs without prior price evidence | Pairs without prior discounts |
| --- | ---: | ---: |
| 2023 | 89 | 415 |
| 2024 | 82 | 368 |
| 2025 | 82 | 351 |
| Total | 253 | 1,134 |

82 games lack valid pre-cutoff prices in every target year. Counts and flags
remain zero while unavailable ratios, recencies and values remain null; they
are not automatically zero-filled. Existing training-only imputation can
handle these nulls. See [feature_availability.csv](feature_availability.csv)
and the raw-index [feature_provenance.json](feature_provenance.json).

- 51 raw timestamp/shop price-state conflict groups across 24 games; the
  original 11 groups across nine games remain unchanged. They affect 71
  pre-cutoff feature pairs, with **zero conflicting latest-price pairs**.
  Independent earlier conflicting observations retain their existing count/
  aggregation treatment. AppID 1817400's 2023 in-sale conflicting prices are
  both discounts; its Category A label is unchanged.
- 273 pairs across 91 games contain pre-cutoff observations earlier than their
  reported release date (1,818 repeated record uses). Early access, preorders,
  retrospective backfill or metadata error are hypotheses, not established
  explanations. No raw records or reported dates were repaired.
- 3,342 pairs across 1,114 games include observations at the exact requested
  `since` boundary, 2021-01-01T00:00:00Z (3,384 repeated record uses). Provider
  initialization/backfill is possible; contemporaneous availability is unknown.
- Successful empty histories and missing historical coverage can make the
  operational model predict recording coverage as well as discount behavior.
  They retain the user's original labels and are visible as separate diagnostics.
- Repeated yearly observations are dependent. Frozen selection and undated
  snapshot-based sampling do not establish representativeness of all Steam.

## Preservation and historical baseline

All **219 protected artifacts** and all 100 pilot caches retain their
phase-start bytes. All 2,000 complete caches, frozen cohorts, 3,816-attempt
journal, archived checkpoints, existing model artifacts and Phase 6A reports
remain unchanged. Full inventory checks are in [validation.json](validation.json).

Historical agreement remains **218/219**, distinct from preservation during
this phase. `data/intermediate/autumn_sale_evidence_records.csv` still has
SHA-256 `69f4930f07a8a5f56c4434611dab81597c626d02411d286a7b542b9889213336`,
versus saved baseline
`5d59669621686a81fb33c751ba7bebca6d148d2781da9f2db38aa4898cc11754`.
Git revision `70f1ddc6d857433c74e9615ff3dabe310f331919` supplies verified
baseline bytes. Both versions have 178 rows and identical row multisets;
two relocated records account for the ordering change. No repair was made.

Offline validation: **196 tests run, 195 passed, one known historical hash
regression failure, zero errors/skips**. All seven new policy/compatibility/
baseline-comparison regressions pass. Full historical regeneration/model-fitting
tests are deliberately excluded by the guarded runner. No HTTP requests,
credential inspection, final model dataset generation or model training ran.

## Modeling readiness and recommended next phase

**The 2,000-game cohort is sufficient for an initial retrospective operational
baseline.** It has balanced aggregate target coverage, three years per game,
and substantially more independent games than the pilot. This does not guarantee
performance, verified participation labels, or population representativeness.

The existing fixed game-level split permits 2023–2024 development training:
**3,280 rows / 1,640 games, 1,692 positives and 1,588 zeros**. Evaluation uses
2025 on 360 different games: **176 positives and 184 zeros**. There is no
game overlap. Other rows remain available for diagnostics; 6,000 labeled rows
do not imply training and evaluating on all of them simultaneously. Previously
inspected pilot games stay in development. 2025 labels have been audited, so
evaluation is retrospective and must not be used for tuning or called a fresh
confirmatory holdout.

Next, generate isolated feature-only outputs with the existing core and
`--label-policy operational`, reconcile them to this target table, and freeze
the feature/split/provenance receipt before separately authorized model fitting.
Use the approved 15 predictors and training-only preprocessing; retain missing
values and all observational caveats. Do not invoke legacy fixed-path writers.

There is no unresolved label-count or direct timestamp-leakage blocker. The
historical baseline mismatch remains a blocker for claiming full pilot receipt
reproduction; it does not require altering preserved raw inputs to use the
configurable path. Actual historical provider availability and undated
popularity snapshots remain unverified, so claims requiring those guarantees
cannot be made from this dataset. No methodology redesign is proposed.
