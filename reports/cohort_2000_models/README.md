# Phase 7A — frozen-feature temporal models

All four requested models trained successfully: training-prior Dummy,
Logistic Regression, Random Forest and XGBoost. **XGBoost was selected using
2024 development average precision, before 2025 probability predictions.**
The selected configuration and selection receipt were not revised after testing.

The target remains observed Autumn Sale discount evidence:
**A→1, B/D→0, C→Unknown**. Operational zero does not establish actual Steam
sale nonparticipation. No label or feature definition was changed.

## Inputs, split and selection

Input: `reports/cohort_2000_modeling/modeling.csv`, SHA-256
`e26d11ad8369b8110689092b2c21c8c61ae8805faa472af2cab24bbcdaf41523`.
All Phase 6C artifact checksums, referenced inputs, approved model-core hashes,
dependency versions, 6,000 unique keys, 15-feature allowlist and temporal split
membership were verified before fitting.

| Stage | Training | Evaluation | Training positives / zeros | Evaluation positives / zeros |
| --- | --- | --- | --- | --- |
| Development | 2023: 2,000 rows | 2024: 2,000 rows | 979 / 1,021 | 1,068 / 932 |
| Final | 2023–2024: 4,000 rows | 2025: 2,000 rows | 2,047 / 1,953 | 983 / 1,017 |

All 2,000 games recur across years. This evaluates later-sale generalization
for previously represented games, not unseen-game generalization. Rows within
a game are dependent. No random or game-disjoint split helper was used.
2025 outcomes were already summarized in earlier audits, so this is not an
untouched confirmatory dataset; 2025 model results were nevertheless held out
from model choice, tuning, preprocessing and threshold decisions.

The protocol was committed in [precommitted_protocol.json](precommitted_protocol.json)
before development fitting. One existing predefined configuration per model
was used; no grid/random search, early stopping, probability calibration fitting,
or threshold optimization occurred. Selection maximizes 2024 average precision,
then minimizes Brier score for an exact tie, then uses the fixed candidate order.
Seed is 42; classifier jobs and numerical thread pools are limited to one.

The [selection receipt](selection.json) records XGBoost's development AP
0.944549, ahead of logistic 0.938271 and RF 0.935825. Logistic had better
development accuracy and Brier score; XGBoost was selected by the predefined
ranking metric rather than claimed to dominate every measure.

XGBoost parameters are the unchanged core configuration: 100 estimators,
depth 3, learning rate 0.05, row/column subsampling 0.8, binary logistic objective,
seed 42, one job. Logistic uses L2, C=1, lbfgs, 2,000 maximum iterations;
RF uses 200 trees, depth 4, minimum leaf size 5 and sqrt feature sampling.
The Dummy uses only training class prevalence.

## Development evaluation — 2024

Positive class is 1 (recorded qualifying discount), threshold **0.5** for all
four probability models. PR-AUC in the tables denotes **average precision**,
the step-weighted ranking measure; linear-interpolated trapezoidal PR area is
also saved separately. These two definitions must not be interchanged.

| Model | Accuracy | Balanced accuracy | Precision | Recall | F1 | ROC-AUC | AP / PR-AUC | Brier |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Dummy | .4660 | .5000 | — | .0000 | .0000 | .5000 | .5340 | .2508 |
| Logistic Regression | .8945 | .8926 | .8864 | .9204 | .9031 | .9426 | .9383 | .0851 |
| Random Forest | .8560 | .8577 | .8900 | .8333 | .8607 | .9421 | .9358 | .0971 |
| **XGBoost** | **.8835** | **.8849** | **.9130** | **.8642** | **.8879** | **.9480** | **.9445** | **.0896** |

The Dummy training prior is .4895, so it predicts zero for all 2,000 rows at
threshold .5. Its precision is undefined because it predicts no positives;
JSON reports null with the reason, not an invented zero precision.
Its constant probabilities still support ROC-AUC, AP and Brier comparisons.

## Held-out evaluation — 2025

After selection was locked, fresh preprocessing and all four predefined models
were fitted on 2023+2024. Each model made **one probability prediction pass**
over 2025. Other models are predefined comparisons; their test scores did not
change the selection. Diagnostic metrics reuse those saved predictions.

| Model | Accuracy | Balanced accuracy | Precision | Recall | F1 | ROC-AUC | AP / PR-AUC | Brier |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Dummy | .4915 | .5000 | .4915 | 1.0000 | .6591 | .5000 | .4915 | .2503 |
| Logistic Regression | .8775 | .8790 | .8165 | .9685 | .8860 | .9524 | .9293 | .0889 |
| Random Forest | .8985 | .8992 | .8645 | .9410 | .9011 | .9573 | .9440 | .0798 |
| **XGBoost** | **.9140** | **.9143** | **.8972** | **.9318** | **.9142** | **.9603** | **.9479** | **.0703** |

The final Dummy prior is .51175 and therefore predicts positive for all 2,000
test rows. XGBoost improves accuracy by **42.25 percentage points**, AP by
**.45644**, and reduces Brier score from .25034 to .07035. These are descriptive
comparisons, not significance claims.

Confusion matrices use actual [0,1] rows and predicted [0,1] columns:

| Stage / model | TN | FP | FN | TP |
| --- | ---: | ---: | ---: | ---: |
| Development Dummy | 932 | 0 | 1,068 | 0 |
| Development Logistic | 806 | 126 | 85 | 983 |
| Development RF | 822 | 110 | 178 | 890 |
| Development XGBoost | 844 | 88 | 145 | 923 |
| Held-out Dummy | 0 | 1,017 | 0 | 983 |
| Held-out Logistic | 803 | 214 | 31 | 952 |
| Held-out RF | 872 | 145 | 58 | 925 |
| Held-out XGBoost | 912 | 105 | 67 | 916 |

Full unrounded metrics, including log loss and trapezoidal PR area, are in
[model_comparison.csv](model_comparison.csv), [development_metrics.json](development_metrics.json)
and [held_out_metrics.json](held_out_metrics.json). Predictions include AppID,
year, actual target, probability, thresholded class and diagnostic context.

## Preprocessing and missingness

Only the approved 15 predictors enter models. AppID/year, target, category,
cutoff and audit fields are explicitly excluded by the reused ColumnTransformer
allowlist. The Dummy consumes a structural constant input and estimates the
training label prior; no historical feature is replaced by that constant.

All learned median imputers were fitted on training predictors only. Logistic
scalers were likewise fitted on training-imputed data only. Development fits
use 2023; final fits use fresh 2023+2024 data. Statistics were independently
checked against training medians, means, variances and row counts. No predictor
is entirely missing in either training portion, so the core's all-missing
structural-zero contingency was never used. No missing value was silently
defaulted to zero. Tree models are not scaled. No encoder or feature selector
was learned from validation/test data.

[preprocessing.json](preprocessing.json) records every fitted statistic and
missingness count. Complete fitted pipelines are saved alongside models.
Pipeline reloads reproduced probabilities exactly on training-only probes.

| Pattern | Development 2024 | Held-out 2025 |
| --- | ---: | ---: |
| All 15 predictors observed | 1,632 | 1,649 |
| Seven price-derived predictors missing: no prior valid prices | 82 | 82 |
| Three discount-derived predictors missing: prices but no prior discount | 286 | 269 |

The eight date/count/flag predictors are complete. Missingness remains explicit
in the frozen input; future consumers should load the saved fitted pipeline,
not invent new fill values or refit preprocessing at inference time.

## Calibration, prediction distribution and coverage limitations

Selected XGBoost predicts 1,011 positives in development and 1,021 positives
in testing; actual counts are 1,068 and 983. On the test, mean probability is
.49708 versus observed prevalence .49150. Its fixed ten equal-width-bin
calibration error is **.02115**, versus .06598 in development. This bin-dependent
descriptive diagnostic is not a guarantee of future probability calibration;
no calibrator was fitted. Reliability-bin counts/probabilities/fractions are
saved for all models. Logistic overestimates test prevalence on average
(.54776); its test ECE is .06298. RF test ECE is .06906.

**A material limitation is dependence on observation coverage.** XGBoost's
test probabilities correlate strongly with pre-cutoff price-record count
(Spearman **.8972**, descriptive and noncausal). Its leading gain importances
include price-record recency (.31688), prior discounted observation count
(.21927), last observed cut (.10134), history availability (.08107), and record
count (.06641). Importances are associations, not causal effects, and cannot
show whether coverage or actual discount propensity drives the relationship.

| XGBoost test subgroup | Rows | Positives | Accuracy | Balanced accuracy | AP |
| --- | ---: | ---: | ---: | ---: | ---: |
| No prior price observations | 82 | 0 | 1.0000 | — | — |
| 1–9 prior price observations | 538 | 19 | .9721 | .6813 | .4802 |
| 10–29 prior price observations | 336 | 118 | .8185 | .8212 | .7475 |
| 30+ prior price observations | 1,044 | 846 | .9080 | .8253 | .9606 |

All 82 games without prior prices have operational-zero labels and receive
negative predictions. That is consistent with this observational target,
not independent confirmation that the real games did not discount. Among
351 test games without prior discounted observations there is one positive,
and XGBoost predicts zero for all: accuracy .99715 but positive recall zero
and balanced accuracy .5. High sparse-coverage accuracy can therefore conceal
poor detection of rare observed positives. Single-class ROC-AUC/AP/balanced
accuracy are explicitly null with reasons.

The full family-specific subgroup metrics are in the coverage CSV/JSON files.
Different diagnostic families overlap and must not be summed together. No
coverage finding triggered new model selection, threshold changes or label edits.

## Overfitting and stability

Selected XGBoost AP is .94804 on development training versus .94455 on 2024,
and .95145 on final training versus .94794 on 2025: resubstitution gaps of
about .00349 and .00351. There is no large observed temporal performance
collapse in this experiment. Small gaps do not prove absence of overfitting,
particularly with repeated games and coverage-related labels.

RF and logistic likewise show no large AP collapse across these reported
splits. Seed sensitivity, new-game generalization, confidence intervals and
prospective live-year performance were **not** evaluated. The 2024/2025
differences include prevalence, calendar-window and feature-coverage shifts,
not controlled evidence about a single cause. All raw timestamp and release
availability caveats from Phase 6B remain applicable.

## Outputs, reproduction and preservation

[selected_model.joblib](selected_model.joblib) is the final selected complete
XGBoost preprocessing/classifier pipeline. Development and final pipelines for
all candidates are stored in their respective subdirectories. Joblib artifacts
are trusted local files and require the recorded Python/library versions.

[model_configuration_manifest.json](model_configuration_manifest.json) records
model configuration, seed, dependencies, source/input hashes, selection lock
and artifacts. The machine-readable predictions, calibration bins, confusion
matrices, importances and metrics are ready for later visualization. No
presentation charts were generated.

Reproduce the predefined experiment into a **new** directory:

```sh
env -u ITAD_API_KEY PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp \
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  /usr/bin/python3 -B src/train_cohort_temporal.py \
  --input-dir reports/cohort_2000_modeling \
  --output-dir reports/cohort_2000_models_reproduction
```

The runner refuses existing output directories, verifies frozen inputs, blocks
network and external subprocesses, confines writes to its new reports/runtime
cache, and preserves selection before the single 2025 pass. A later exact
reproduction repeats the finalized evaluation without new tuning; timestamps
and per-run preservation receipts differ. This phase did not rerun the 2025
prediction pass to verify saved models: reload probes used training rows only.

Reusable cores were unchanged. New files are `src/train_cohort_temporal.py` and
`tests/test_cohort_temporal_models.py`; the offline runner was updated to include
the new tests. No pilot-size or earlier game-disjoint helper is invoked.

Offline tests: **219 run, 218 passed, one known historical baseline hash
failure, zero errors/skips**. All 11 new regressions passed, including synthetic
training-only preprocessing, temporal exclusion, metric handling, selection,
coverage/calibration accounting and pipeline serialization. Tests fit synthetic
fixtures, not original pilot models. Full historical regeneration tests remain
excluded.

All **2,234 preexisting data/report/model and protected files** retained their
phase-start bytes: raw caches, all frozen cohorts, the 3,816-attempt journal,
archived checkpoints, 100 pilot caches, nine Phase 6A files, eight Phase 6B files,
15 Phase 6C files and original pilot model/report outputs. All **219 protected
artifacts were preserved during this phase**. Historical baseline agreement is
still **218/219** with the same unrepaired ordering-only mismatch in
`autumn_sale_evidence_records.csv`.

Next, review the saved coverage/calibration diagnostics and prepare exploratory
model cards and visualizations from these fixed outputs. Do not claim verified
sale participation, unseen-game performance or prospective reliability. Any
new model choice or calibration experiment should use development data under a
separately frozen protocol and should not tune against these 2025 results.
