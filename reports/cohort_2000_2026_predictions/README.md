# Phase 8B — retrospective 2026 predictions

**Retrospective event-time-filtered predictions using post-cutoff-collected historical data.** These are model scores for observed ITAD Autumn Sale discount evidence, not independently verified Steam sale participation. Predicted operational zero means the model predicts no discount observed in available evidence; it does not establish verified nonparticipation.

## Results

Exactly 2,000 cohort games receive one probability and class: **1,026 positives (51.30%)** and **974 operational zeros (48.70%)**. Threshold is unchanged: probability ≥0.5 yields 1. Mean probability 0.499649, median 0.709637, range 0.008056–0.959107. Full quantiles, histogram, ranks, coverage and missingness tables accompany this report. Rankings use probability then ascending AppID for ties; they are predictions, not observed outcomes.

### Ten highest-probability predicted positives

| AppID | Game | Probability |
| --- | --- | ---: |
| 252310 | Syder Arcade | 0.959107 |
| 514990 | Outbreak | 0.959107 |
| 536220 | The Walking Dead: A New Frontier | 0.959107 |
| 261720 | Holy Avatar vs. Maidens of the Dead | 0.958935 |
| 284100 | Unclaimed World | 0.958935 |
| 319450 | Chariot | 0.958935 |
| 331190 | Master Spy | 0.958935 |
| 421810 | OH! RPG! | 0.958935 |
| 663250 | Professional Farmer: American Dream | 0.958935 |
| 674210 | Rush to Adventure | 0.958935 |

### Ten lowest-probability predicted operational zeros

| AppID | Game | Probability |
| --- | --- | ---: |
| 1934650 | Girbal | 0.008056 |
| 2133940 | Precision Break | 0.008056 |
| 2145480 | Inversion Institute | 0.008056 |
| 1787050 | Voxel Farm Island | 0.008128 |
| 943900 | Tombeaux | 0.008260 |
| 963670 | Project Flesh | 0.008260 |
| 1123400 | The Land of Exile | 0.008260 |
| 1125340 | Tales of Lazo | 0.008260 |
| 1148200 | Fadó: Chapter One | 0.008260 |
| 1339030 | Final Hope: The Plot | 0.008260 |

## Frozen inputs and adapters

Only `predict_cohort_2026.py` and new offline tests/runner are introduced. The unchanged feature core receives full parsed histories and an explicit verified 2026 window, bypassing the old wrapper's January-2026 truncation. Event timestamps must be **strictly before 2026-10-01T17:00:00Z**; records at the boundary, within the sale, or later are excluded. Sale end is 2026-10-08T17:00:00Z. No 2026 outcomes are generated or inspected for training, tuning, thresholding, selection or evaluation. Audit metadata counts excluded records but their prices/discounts never enter predictors.

The 2,000×15 predictor matrix plus four identity/audit columns matches Phase 8A values exactly. All 2,000 vectors pass cutoff-removal/exact-boundary invariance checks. Four price-related predictors each retain 81 nulls; three discount-related predictors each retain 336. There are 1,664 complete vectors, 255 with only three discount-derived nulls, and 81 with seven price-derived nulls. Blank CSV cells mean missing, not zero. Definitions, ordering, type/range checks and historical labels are unchanged. No current price/popularity or previous sale participation predictor is introduced.

The fresh model uses the unchanged selected configuration: 100 trees, depth 3, learning rate .05, subsample/column sample .8, binary:logistic objective, logloss metric, seed 42, n_jobs=1. ColumnTransformer selects the 15 approved columns, followed by training-median imputation without indicators/scaling. All 6,000 frozen 2023–2025 rows (3,030 positive, 2,970 zero) fit the new imputer and classifier; 2026 rows never fit preprocessing. No feature is entirely missing in training. No hyperparameter search, feature selection, calibration fitting, early stopping or model/threshold selection occurs.

`refit_2023_2025_pipeline.joblib` is the new complete inference pipeline. Separate `preprocessing_2023_2025.joblib` and `xgboost_2023_2025.joblib` are saved components of that same fit. The original Phase 7A selected model and 2025 evaluation remain immutable; their performance estimates belong to that older 2023–2024 fit, not this new refit. Versions and exact preprocessing medians are in configuration/preprocessing manifests.

## Coverage and methodological limitations

Score-versus-observation-count Spearman is **0.8925**, compared with **0.8972** for saved 2025 scores. Coverage groups are unchanged (0, 1–9, 10–29, 30+ price observations). Tables include subgroup sample sizes, predicted class counts and score summaries; no 2026 accuracy/calibration or actual-class counts are inferred. Coverage correlation is descriptive, not causal. Counts retain duplicate observations and represent observation density, not distinct campaigns or discounted-day frequency.

All history receipts are October 5–13, after cutoff. Event time does **not** demonstrate provider availability before cutoff: zero vectors are fully point-in-time proven. Backfill, source release-date accuracy, pre-release/request-boundary observations and past timestamp/shop ambiguities remain limitations. Missing histories are not evidence of no actual discounts. Phase 8A range diagnostics are retained: several valid recency/count/age/discount values exceed historical training ranges; no clipping or feature redesign is applied. Repeated games across years and observational labels limit claims about unseen-game performance or genuine prospective forecasts. No independent 2026 outcome validation is performed here.

## Reproduction and integrity

Run from repository root into a fresh destination (the runner refuses existing directories):

```sh
env -u ITAD_API_KEY PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp \
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  /usr/bin/python3 -B tests/run_prediction_2026_offline.py \
  --results /private/tmp/steam-2026-prediction-tests.json

env -u ITAD_API_KEY PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp \
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  /usr/bin/python3 -B src/predict_cohort_2026.py \
  --output-dir reports/cohort_2000_2026_predictions_reproduction \
  --test-results /private/tmp/steam-2026-prediction-tests.json
```

Offline guards block network/subprocesses and confine writes to the fresh output/runtime namespace. Frozen input hashes, dependency versions, exact cohort/feature/target membership, training medians, parameters, probability ranges and threshold are checked before delivery. An independent same-configuration verification refit in runtime storage must reproduce predictor/prediction CSVs and booster JSON byte-for-byte. This verification is not model selection; no old model is fitted and no 2025 evaluation is repeated. Serialized pipeline/component reloads must yield identical probabilities. `reproduction.json`, `offline_test_results.json`, `validation.json`, `input_checksums.json` and `checksums.json` record the results. Execution receipts can differ with additional preexisting files; core prediction payloads are deterministic in the recorded environment.

All existing data/report/model files and 219 protected artifacts must retain phase-start bytes. Historical baseline agreement remains 218/219: the known ordering-only mismatch in `autumn_sale_evidence_records.csv` is preserved without repair. All 2,000 caches, cohorts, labels, Phase 6/7/8A outputs, archived checkpoints and the 3,816-entry journal remain unchanged. Preservation and historical baseline agreement are separate checks.

## Recommended Phase 8C

Build separate minimalist light-theme figures from these saved outputs: score histogram/quantiles; positive-versus-operational-zero counts; observation-count versus score with coverage groups; subgroup prediction rates and sample sizes; feature missingness by predicted class; top/bottom-ranked game tables; descriptive 2025-versus-2026 coverage/score comparison. Keep the retrospective/backfill warning visible. Do not present score distributions as calibrated 2026 outcome probabilities or generate accuracy/ROC/confusion/calibration plots without independently authorized outcome analysis.

## Completed offline verification

**29/29 offline tests passed**, with zero failures, errors or skips: 16 new adapter/input regressions, nine existing feasibility regressions, and four new delivered-artifact regressions. The final suite receipt is `post_artifact_test_results.json`; the pre-execution receipt is separate. All 2,323 phase-start files retain their SHA-256 bytes, including all 219 protected artifacts. Historical baseline agreement is still 218/219.

All 336 games with missing predictors receive predicted operational zero; all 1,026 predicted positives have complete feature vectors. Of the 974 predicted zeros, 638 have complete vectors, 255 lack the three discount-derived values, and 81 lack seven price-derived values. These are prediction diagnostics, not observed 2026 outcomes.

| Prior price observations | Games | Predicted positives | Positive prediction rate | Mean score |
| --- | ---: | ---: | ---: | ---: |
| 0 | 81 | 0 | 0.00% | 0.0174 |
| 1–9 | 505 | 6 | 1.19% | 0.0357 |
| 10–29 | 295 | 74 | 25.08% | 0.2730 |
| 30+ | 1,119 | 946 | 84.54% | 0.8037 |

The saved 2025 predictions have subgroup positive prediction rates 0%, 1.86%, 41.37% and 83.52%, respectively. Group sizes and training periods differ. `coverage_score_comparison.csv` supports a descriptive comparison; this is not a controlled attribution or a new 2026 performance evaluation.

An initial execution passed score reproduction but stopped during temporary cleanup. The new guard's directory-descriptor handling was corrected and tested before the fresh successful execution. `execution_notes.json` documents the partial run; no frozen configuration or historical input changed.

Verify the delivered artifacts offline without refitting the final model:

```sh
env -u ITAD_API_KEY PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp \
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  /usr/bin/python3 -B tests/run_prediction_2026_offline.py \
  --artifacts reports/cohort_2000_2026_predictions \
  --results /private/tmp/steam-2026-prediction-final-tests.json
```

The suite fits only synthetic test models. Delivered-model tests inspect its statistics and saved outputs without modifying the fitted artifact. No additional execution blocker remains for this retrospective exercise; the provider-availability and operational-label limitations remain unresolved.
