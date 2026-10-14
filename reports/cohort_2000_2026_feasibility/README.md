# Phase 8A — 2026 retrospective pre-sale feasibility

**The fixed 2,000-game event-time prediction exercise is computationally
feasible. A genuinely prospective or verified point-in-time reconstruction is
not established by these caches.** No additional games, refit, probabilities,
2026 operational labels or predictions were generated.

## Verified sale window and cutoff

Verification date: **October 14, 2026**.

| Boundary | America/Los_Angeles | UTC | Manila |
| --- | --- | --- | --- |
| Sale start | October 1, 2026, 10:00 AM PDT | **2026-10-01T17:00:00Z** | October 2, 1:00 AM |
| Sale end | October 8, 2026, 10:00 AM PDT | **2026-10-08T17:00:00Z** | October 9, 1:00 AM |

The source is Valve's [2026 Steamworks sale documentation](https://partner.steamgames.com/doc/marketing/upcoming_events/2026_autumn_sale?l=english),
corroborated by its October 1 [Steam News announcement](https://steamcommunity.com/games/593110/announcements/detail/687517158280790640)
and the readable [official news archive](https://store.steampowered.com/oldnews/?headlines=0&l=english).
The source record and access limitations are frozen in
[verified_sale_dates.json](verified_sale_dates.json).

**Source access distinction:** the expired Steamworks event URL now redirects
to documentation home. Its recently indexed official text specifies October
1–8, 2026 at 10 AM Pacific; this was not treated as a freshly downloaded full
event page. The live official news archive identifies the October 1 launch and
confirms the October 8 end at 10 AM Pacific. The indexed Valve Steam Promotions
event listing also identifies October 1–8. No secondary site's dates or clock
time were used as the verification basis.

Both dates are PDT, UTC−7, computed with Python `zoneinfo` for
`America/Los_Angeles`, not a fixed PST offset or the 2025 dates. The event
window is start-inclusive, end-exclusive.

The prediction cutoff is the exact start boundary,
**2026-10-01T17:00:00Z**, with the unchanged feature condition
**record timestamp < cutoff**. This represents information immediately before
sale start without discarding fractional timestamps in the preceding second.
Exact-boundary, in-sale and later observations are excluded. At microsecond
resolution, 16:59:59.999999Z is eligible; 17:00:00Z is not.

The event had ended by October 14. Any later output must be named and described
as **retrospective pre-sale predictions of observed ITAD discount evidence**,
never a genuinely prospective forecast or certified actual Steam participation.

## Reconstructable feature vectors and missingness

The unchanged `pre_sale_observations_v1` feature core reconstructs an audit
vector for **all 2,000 games / 30,000 predictor cells**. Of these:

- **1,664 vectors** have all 15 values observed.
- **336 vectors** have expected nullable values, compatible with historical
  training-only median imputation in a later refit.
- **1,919 games** have qualifying pre-cutoff price observations.
- **1,664 games** have qualifying pre-cutoff discounted observations.
- **81 successfully empty histories** remain distinct from failed/missing
  caches; there are no missing or invalid collection caches.

“Reconstructable” means the existing calculation can be performed, including
its defined null results. It does not mean every cell is observed, every game
has complete price coverage, or every input was demonstrably available before
the cutoff. No 2026 target labels or probabilities accompany the audit vectors.

| Approved predictor | Missing games | Missing percent |
| --- | ---: | ---: |
| game_age_days | 0 | 0% |
| release_year | 0 | 0% |
| release_month | 0 | 0% |
| release_quarter | 0 | 0% |
| prior_price_record_count | 0 | 0% |
| prior_discount_count | 0 | 0% |
| prior_discount_rate | 81 | 4.05% |
| days_since_last_price_record | 81 | 4.05% |
| days_since_last_discount | 336 | 16.8% |
| max_prior_discount_pct | 336 | 16.8% |
| mean_prior_discount_pct | 336 | 16.8% |
| last_observed_price | 81 | 4.05% |
| last_observed_discount_pct | 81 | 4.05% |
| has_prior_price_history | 0 | 0% |
| has_prior_discount_observation | 0 | 0% |

The 336 incomplete vectors comprise 81 with no price history and 255 with
prices but no qualifying prior discounts. Counts/flags remain their defined
numeric zeros; unavailable ratios, recencies and prices remain null. No
preprocessing was fitted, no missing value was silently zero-filled and no
new feature was added.

[feature_missingness.csv](feature_missingness.csv) also records observed ranges
and historical training ranges. All nonmissing values have valid types/ranges:
finite numeric inputs, nonnegative age/counts/prices, valid date components,
binary flags, count-consistent ratios, 0–100 percentages and positive observed
recencies. [game_feature_availability.csv](game_feature_availability.csv)
audits every game/predictor cell, and [audit_feature_values.csv](audit_feature_values.csv)
contains the existing 19-column feature-only schema for audit—not predictions.

## Event timestamps versus provider availability

All 93,286 raw history records parsed without silent failures. The event-time
partition is:

| Record period | Records | Feature use |
| --- | ---: | --- |
| Before January 1, 2026 | 79,263 | Eligible if parser-valid |
| January 1 to immediately before October 1 cutoff | 12,026 | Eligible if parser-valid |
| 2026 sale window | 960 | Excluded |
| At/after sale end | 1,037 | Excluded |

Thus **91,289 pre-cutoff event records** are retained and **1,997 at/after-cutoff
records** are excluded. 1,006 games have records excluded by this boundary.
All 2,000 vectors remain identical after removing every at/after-cutoff record
and inserting a synthetic discount exactly at the boundary. Direct event-time
cutoff violations: **zero**.

**Provider point-in-time availability is unverified for every game.**
The earliest history receipt is October 5, 2026 at 16:21:27.543717Z; the latest
is October 13 at 19:10:04.132860Z. All receipts are after the October 1 cutoff:
100 during the sale, 1,900 after it ended. No pre-cutoff cache snapshot is
demonstrated. Raw records contain `timestamp`, `shop` and `deal`, without
provider first-seen or record-version availability timestamps.

A historical event timestamp establishes only the asserted time of the pricing
observation. A response received later cannot prove the observation/value was
in the provider's dataset earlier. Backfill, initialization, retroactive
corrections and records missing from the later snapshot remain unresolved.
**Zero demonstrated pre-cutoff snapshots does not establish that the records
were unavailable then; it establishes lack of evidence here.**

Four static release-derived predictors assume the reported historical release
date is accurate/stable; no independently dated metadata snapshot proves its
as-of version. Zero-observation flags/counts describe the returned records,
not independently proven absence at cutoff. Consequently **zero entire
15-feature vectors have fully proven point-in-time provenance**.

The data also retain 606 qualifying observations dated before reported release
and 1,128 at the exact 2021-01-01 requested-since boundary. These are recorded
anomalies/initialization cautions, not repaired or declared causal backfill.
No game has a conflicting latest prior price timestamp; historical conflicts
remain preserved elsewhere in raw history.

To resolve a stronger point-in-time claim, locate trustworthy archived
responses obtained before October 1, or provider record-version/first-availability
evidence matched to exact prices and record identities. Fetching a new live
response now cannot establish past availability. This phase made no ITAD calls.

## Model compatibility and necessary adapters

The saved selected XGBoost has exactly the same approved 15 feature names and
order. Audit vectors coerce to a compatible 2,000×15 numeric matrix with nulls
represented as missing. Saved imputation and classifier structure/parameters
were inspected read-only; no model transform, fit or prediction ran.

The frozen XGBoost configuration remains 100 trees, depth 3, learning rate
.05, row/column subsampling .8, binary logistic objective, seed 42 and one job.
The classification threshold remains .5. The same median-imputation pipeline
can be **refitted later on historical training data only**.

Two executable compatibility issues require a cohort-aware Phase 8B adapter:

1. `cohort_pipeline.evidence` uses only canonical 2023–2025 windows and truncates
   input history at 2026-01-01. Reusing that wrapper unchanged would drop 12,026
   valid 2026 pre-sale records and change **1,230 vectors**. Instead, pass the
   separately verified 2026 window and full parsed histories to the unchanged
   `07_build_autumn_features.py:build_features` core.
2. Existing `08:fit_models` and `09:fit_models` year guards do not accept the
   requested 2023–2025 refit. A new runner should validate those three training
   years and reuse `09:pipeline('xgboost')`; do not weaken old guards or overwrite
   the original training/evaluation pipeline.

These are adapter/configuration requirements, not reasons to alter features,
labels or hyperparameters. Original calendars and approved implementations
remain unchanged. Details are in [model_compatibility.json](model_compatibility.json).

There is temporal distribution shift: 306 price-recency values and 121
discount-recency values exceed the historical training maximum. One game each
exceeds the historical age, observation-count and discount-count maxima, and
one mean-cut value exceeds the historical maximum. These are valid values,
not range errors; they flag extrapolation/saturation risk. No feature clipping,
rescaling policy change or performance claim was introduced. Prior held-out
performance does not guarantee 2026 performance, especially given the strong
coverage dependence documented in Phase 7B.

## Prepared Phase 8B protocol — not executed

[final_refit_prediction_protocol.json](final_refit_prediction_protocol.json)
freezes the proposed steps, source/configuration hashes, dependencies, sample
size, cutoffs and output semantics:

1. Verify Phase 6C/7A/8A hashes and the original 2,000-game membership/order.
2. Freeze one 2026 feature row per game using the exact October 1 exclusive
   cutoff, full parsed histories, original 15 definitions and explicit nulls.
   Attach source/raw-index receipts and unverified point-in-time metadata.
3. Reuse all **6,000 frozen 2023–2025 training observations**, with 3,030
   positives, 2,970 zeros and zero unknowns. Do not regenerate labels or allow
   any 2026 target-window evidence into training.
4. Fit fresh median imputation and the unchanged selected XGBoost configuration
   on those historical rows only. No 2026 values fit preprocessing, selectors,
   calibration, thresholds or model selection. Stop if an all-missing training
   column unexpectedly appears rather than silently change the policy.
5. Save a separately named 2023–2025 refit pipeline and configuration receipt;
   verify reload using historical training probes.
6. Generate exactly **2,000 probabilities/classes**, one per frozen AppID,
   with the original .50 threshold and retrospective/event-time-only flags.
   Do not generate/use 2026 outcome labels in that prediction phase.
7. Preserve the original 2025 held-out evaluation and all Phase 7 artifacts.
   Because 2025 enters the new training set, do not evaluate the new refit on
   2025 as a held-out test or attribute old test metrics to the new refit.

No expansion to 2,500 is proposed. No new game/API collection is required for
the computational exercise. The execution blockers are the new year-aware
adapter and a fresh output namespace. The unresolved provenance limitation
blocks **verified point-in-time/prospective claims**, not explicitly qualified
retrospective event-time analysis. It must remain visible on every later output.

## Reproduction and integrity

Calendar verification used official public web research only. Cache inspection,
feature calculation and model compatibility checks were offline, with socket,
subprocess, fitting and model-prediction guards.

Reproduce from the frozen verified calendar into a fresh directory:

```sh
env -u ITAD_API_KEY PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp \
  /usr/bin/python3 -B src/audit_2026_feasibility.py \
  --sale-dates reports/cohort_2000_2026_feasibility/verified_sale_dates.json \
  --output-dir reports/cohort_2000_2026_feasibility_reproduction
```

The script refuses existing destinations, reuses feature definitions unchanged,
reads/validates all complete caches, verifies frozen model/dataset checksums,
and confines writes to the new reports directory/runtime cache. It copies the
saved calendar facts; reproducing the numerical audit requires no web or ITAD
requests. [feature_provenance.json](feature_provenance.json) retains selected
raw indices and cutoff checks. Per-game receipt evidence is in
[game_availability.csv](game_availability.csv). [checksums.json](checksums.json)
covers the new deliverables.

**9/9 guarded offline tests passed**, with no fitting or predictions. They
cover PDT conversion, exact-boundary exclusion, preservation of 2026 pre-sale
records, receipt-versus-event distinction, explicit nulls and feature schema/
range validation. General model-fitting tests were not run in this phase.

All **2,310 preexisting data/report/model and protected files** retain their
phase-start bytes, including raw caches, frozen cohorts, original operational
labels/features, all Phase 6/7 outputs and model artifacts, journal/checkpoints
and pilot artifacts. All **219 protected artifacts were preserved**. Historical
baseline agreement remains **218/219**, with the same unrepaired mismatch in
`autumn_sale_evidence_records.csv`. The collection journal remains at **3,816
attempts**. No refit or prediction was executed.
