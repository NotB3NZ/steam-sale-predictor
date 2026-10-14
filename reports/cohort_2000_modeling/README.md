# Phase 6C — frozen operational modeling data and temporal protocol

**Frozen dataset: 6,000 unique rows × 21 columns, 2,000 unique games,
exactly 2,000 rows in each of 2023, 2024 and 2025.**

[modeling.csv](modeling.csv) contains the unchanged 15 approved predictors,
`appid`, `sale_year`, `prediction_cutoff_utc`, `audit_release_hour_uncertain`,
`discount_observed`, and `evidence_category`. The six latter columns are
identity/cutoff/audit/target provenance, not predictors. [features.csv](features.csv)
contains the existing 19-column feature-only schema without labels/categories.
Both files are ordered deterministically by numeric AppID, then year.

The executable pilot label rule `operational_observed_v1` remains
**A→1, B→0, C→Unknown, D→0**. There are 3,030 positives, 2,970 zeros and no
unknowns. Operational zero means **no discount observed in available ITAD
evidence**, not verified nonparticipation. Empty successful histories remain
valid collection outcomes; their 243 D zeros retain this observational meaning.
Every target and every raw-index feature provenance record agrees with Phase 6B.

## Frozen chronological evaluation

| Role | Years | Rows | Games | Positive | Operational zero |
| --- | --- | ---: | ---: | ---: | ---: |
| Development training | 2023 | 2,000 | 2,000 | 979 | 1,021 |
| Development validation | 2024 | 2,000 | 2,000 | 1,068 | 932 |
| Final training | 2023–2024 | 4,000 | 2,000 | 2,047 | 1,953 |
| Held-out test | 2025 | 2,000 | 2,000 | 983 | 1,017 |

[split_membership.csv](split_membership.csv) assigns every AppID/year to its
final and development roles. [temporal_split_manifest.json](temporal_split_manifest.json)
records the complete protocol. The cohort's earlier `evaluation_group` values
are preserved in the source cohort but deliberately unused here: this task
explicitly requests all games in chronological splits, not the earlier
game-disjoint expanded protocol.

1. Use 2023 to fit development models and all learned preprocessing. Transform
   2024 using those fitted objects; do not fit on validation features or labels.
2. Any separately authorized model selection must use only this 2023→2024
   development comparison. Freeze model choice, feature allowlist, preprocessing,
   parameters and probability threshold before evaluating 2025.
3. Refit fresh preprocessing and the selected model on 2023+2024, then transform
   and evaluate 2025 without fitting. Do not reuse a 2023-only imputer/scaler as
   if it had been fitted to the final training portion.
4. All imputers, scalers, encoders, selectors, calibration or other learned
   transformations belong inside the appropriate training partition. No test
   driven tuning, threshold selection, early stopping or feature changes.

There are **2,000 overlapping games** between final train/test and between
development train/validation. This assesses temporal generalization to a later
sale for previously represented games, not unseen-game generalization. Three
rows per game are dependent; 6,000 rows are not 6,000 independent games. Any
future uncertainty analysis must account for game clusters.

2025 labels have already been inspected in audits. They are held out from model
fitting/selection under this frozen protocol, but are not an untouched
confirmatory holdout. No performance claims are made during preparation.

Frozen defaults: seed 42, class threshold 0.5, and reporting ROC-AUC, average
precision, log loss, Brier score, accuracy, precision, recall, F1 and confusion
matrix. Model probabilities concern recorded discount occurrence.

## Approved feature manifest and cutoffs

[feature_manifest.json](feature_manifest.json) lists definitions, data sources,
types, missing-value meanings, historical availability caveats and predictor
approval for the existing `pre_sale_observations_v1` implementation.

The 15 predictors are:

- `game_age_days`, `release_year`, `release_month`, `release_quarter`
- `prior_price_record_count`, `prior_discount_count`, `prior_discount_rate`
- `days_since_last_price_record`, `days_since_last_discount`
- `max_prior_discount_pct`, `mean_prior_discount_pct`
- `last_observed_price`, `last_observed_discount_pct`
- `has_prior_price_history`, `has_prior_discount_observation`

No new feature, contemporary master price/popularity indicator, or previous
Autumn Sale participation feature was introduced. Categories and targets are
never supplied to the feature core. Use the allowlist rather than selecting
every numeric column; AppID/year and audit flags remain excluded.

| Year | Predictor timestamp must be strictly before | Label window end, exclusive |
| --- | --- | --- |
| 2023 | 2023-11-21T18:00:00Z | 2023-11-28T18:00:00Z |
| 2024 | 2024-11-27T18:00:00Z | 2024-12-04T18:00:00Z |
| 2025 | 2025-09-29T17:00:00Z | 2025-10-06T17:00:00Z |

Label evidence starts inclusively at the corresponding predictor cutoff.
Direct future-timestamp violations: **zero**. All **171,868 pre-cutoff record
uses** were checked against raw indices; removing at/after-cutoff raw records
reproduced every feature vector for all 6,000 pairs. Phase 6B separately
verified that inserting an exact-cutoff discount cannot affect the features.

These checks establish timestamp causality in the existing implementation,
not contemporaneous access to retrospectively supplied ITAD records. Provider
initialization/backfill, reported release-date accuracy, release-hour uncertainty,
recording coverage, raw timestamp/shop conflicts and retrospective sampling
limitations remain as documented in the preserved Phase 6B report. No raw
records were repaired, deduplicated, forward-filled or interpreted as daily states.

## Missingness, types and ranges

Blank CSV cells represent missing values; JSON uses null. No preparation-time
imputation, scaling, encoding, feature selection or other transformation was
fitted. True observed numeric zeros remain zero and are distinguished from
missing cells. [missingness.csv](missingness.csv) records every feature/year,
overall counts, percentages, observed minima and maxima.

| Predictor | Missing 2023 | Missing 2024 | Missing 2025 | Total |
| --- | ---: | ---: | ---: | ---: |
| game_age_days | 0 | 0 | 0 | 0 |
| release_year | 0 | 0 | 0 | 0 |
| release_month | 0 | 0 | 0 | 0 |
| release_quarter | 0 | 0 | 0 | 0 |
| prior_price_record_count | 0 | 0 | 0 | 0 |
| prior_discount_count | 0 | 0 | 0 | 0 |
| prior_discount_rate | 89 | 82 | 82 | 253 |
| days_since_last_price_record | 89 | 82 | 82 | 253 |
| days_since_last_discount | 415 | 368 | 351 | 1,134 |
| max_prior_discount_pct | 415 | 368 | 351 | 1,134 |
| mean_prior_discount_pct | 415 | 368 | 351 | 1,134 |
| last_observed_price | 89 | 82 | 82 | 253 |
| last_observed_discount_pct | 89 | 82 | 82 | 253 |
| has_prior_price_history | 0 | 0 | 0 | 0 |
| has_prior_discount_observation | 0 | 0 | 0 | 0 |

All nonmissing predictors are finite numeric values. Date-derived components,
counts and flags are integers. Ages/counts/prices are nonnegative; discount
count cannot exceed valid price count; flags match observation counts;
ratio is in [0,1]; percentages are in [0,100]; observed recencies are strictly
positive. Month/quarter values are valid and consistent. No training feature is
entirely missing, including in the 2023-only development portion.

The existing baseline core can use training-only median imputation and
training-only scaling. Its training-only all-missing-column exclusion rule and
the tree core's documented structural-zero rule are distinct contingencies;
neither was applied here. Preserve the chosen future estimator's documented
policy rather than silently replacing nulls while preparing the dataset.

## Reusable model components and remaining adapters

| Component | Readiness |
| --- | --- |
| `07_build_autumn_features.py:build_features` | Directly reused without feature-definition changes |
| `08_train_baseline_models.py:select_predictors`, `predict`, `evaluate` | Reusable approved-column selection, predictions and metrics for arbitrary cohort row counts |
| `08_train_baseline_models.py:fit_models` | Reusable for final 2023+2024 training; accepts larger row count, requires both years, fits preprocessing only on supplied training data |
| `09_train_ensemble_models.py:pipeline` | Reusable fixed approved-feature logistic/RF/XGBoost pipeline construction for a later authorized development adapter |
| `09_train_ensemble_models.py:fit_models(..., cohort_mode=True)` | Supports 2023-only development or 2023+2024 final training without the 100-game count limit |
| Pilot `chronological_split`, `split_protocol`, `inspect_inputs`, standalone writers/reporting | Fixed pilot sizes/paths/receipts; need a cohort-aware loader/split/report adapter |
| `cohort_pipeline.py:model_frames` | Uses the earlier game-disjoint policy; must not be used as the splitter for this frozen chronological experiment |

Recommended initial comparison: training-prior Bernoulli baseline and the
existing L2 logistic regression, with the unchanged 15-feature allowlist,
training-only median imputation and logistic scaling. Candidate models are
the existing Random Forest and XGBoost with their predefined source parameters.
Select only through the 2023→2024 development protocol, then freeze before test
evaluation. Their implementation hashes and installed library versions are
recorded in [model_readiness.json](model_readiness.json). No estimator was fitted.

There is no dataset, label-count, type/range or direct timestamp-leakage blocker.
Before training, a runner must load these frozen manifests, implement the
requested temporal splits instead of the old game-disjoint/fixed-pilot helpers,
and save models/reports into a fresh namespace. For logistic development,
`08:fit_models` rejects 2023-only input: reuse the existing pipeline constructor
through a cohort-aware adapter rather than bypassing its guard. Historical
provider availability and verified sale nonparticipation remain unproven.

## Reproduction, checksums and integrity

The new offline adapter `src/freeze_cohort_modeling.py` reuses the existing
labeling/features, blocks network/subprocess operations and confines writes to
a new reports directory. It does not import or invoke training functions.
The only existing source changed in this phase is the guarded offline test
runner, to include `tests/test_frozen_modeling.py`; approved label/feature/model
implementations were unchanged.

From the repository root, reproduce into a fresh directory:

```sh
env -u ITAD_API_KEY /usr/bin/python3 -B src/freeze_cohort_modeling.py \
  --cohort data/cohorts/cohort_2000.csv \
  --cache-dir data/cohorts/itad/cache \
  --reuse-cache data/raw/itad \
  --output-dir reports/cohort_2000_modeling_reproduction
```

The script refuses existing destinations. [input_manifest.json](input_manifest.json)
pins the source implementations, calendar evidence, frozen cohort, metadata,
2,000 input caches and Phase 6B artifacts. [checksums.json](checksums.json) lists
SHA-256 for all delivered files except the checksum index itself. Verify each
file against that index and verify input hashes before any future training.

An independent second build reproduced **nine core payloads byte-for-byte**:
modeling/features CSVs, missingness, split membership, feature manifest,
feature provenance, target distribution, temporal protocol and input manifest.
[reproduction.json](reproduction.json) records this check. `validation.json`
is an execution receipt: its preservation inventory can differ on a later run
that has additional preexisting reports. Supporting preparation documentation,
test results and readiness notes are separately checksummed.

Modeling dataset SHA-256:
`e26d11ad8369b8110689092b2c21c8c61ae8805faa472af2cab24bbcdaf41523`.

Offline tests: **208 run, 207 passed, one known historical baseline hash
failure, zero errors/skips**. All 12 added dataset/split/serialization/range/
missingness regressions passed. The guarded runner intentionally excludes
historical full-regeneration and model-fitting tests.

All **2,219 preexisting data/report/model and protected files**, including all
100 pilot caches, all 2,000 complete caches, frozen cohorts, archived checkpoints,
the 3,816-attempt journal, nine Phase 6A files and eight Phase 6B files, retain
their phase-start bytes. All **219 protected artifacts were preserved**.
Historical baseline agreement remains **218/219**, with the same unrepaired
ordering-only mismatch in `autumn_sale_evidence_records.csv`. Preservation
during this phase and historical baseline agreement are distinct checks.

No HTTP requests, raw/cohort/journal modifications, pilot output changes,
model training, fitted preprocessing or prediction visuals were performed.
