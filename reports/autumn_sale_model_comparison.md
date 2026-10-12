# Nonlinear comparisons for recorded Autumn Sale discounts

## Objective and evidence

Do predefined nonlinear ensembles improve prediction of recorded Steam Autumn Sale discount occurrence relative to logistic regression and a constant-probability prior? 1: a qualifying Steam-store discount was recorded during the official Autumn Sale window; 0: no qualifying discount was recorded. Zero does not establish absence of an actual discount. Probabilities concern recorded occurrence, not verified participation.

The existing 100-game pilot provides 300 game-year rows. Training: 2023–2024, 200 rows (115 positive / 85 negative); evaluation: 2025, 100 rows (60 positive / 40 negative). All primary models use exactly the same game-year identities. The same games recur across years: this measures temporal generalization for previously represented games, not unseen-game or full-catalog generalization. The 2025 holdout was already examined in Phase 7A. This comparison is exploratory on a previously examined holdout, **not a fresh confirmatory test**. Configurations were prescribed before this phase's evaluation; no tuning, feature selection, early stopping or calibration fitting uses 2025 labels. Threshold remains 0.50.

## Inputs, features and preprocessing

Approved predictors: `game_age_days`, `release_year`, `release_month`, `release_quarter`, `prior_price_record_count`, `prior_discount_count`, `prior_discount_rate`, `days_since_last_price_record`, `days_since_last_discount`, `max_prior_discount_pct`, `mean_prior_discount_pct`, `last_observed_price`, `last_observed_discount_pct`, `has_prior_price_history`, `has_prior_discount_observation`. Explicit ColumnTransformer selection drops all identifiers, cutoff, targets, categories, PU and audit fields. Input types, exact Phase 6 manifest approval, frozen targets and pre-cutoff provenance are validated using the unchanged baseline utilities. Median imputers fit training predictors only. Existing coverage indicators are retained; no redundant indicators or unnecessary tree scaling are added. The complete saved pipelines include feature selection, imputation and classifiers. Entirely missing training columns would be preserved as structural zeros using keep_empty_features=True; actual primary training has none. Constants would remain in schema. Transformed names and imputer statistics are in the manifest.

Primary Phase 7A predictions and metrics are loaded unchanged, validated against the 2025 identities/labels, recomputed metrics and trusted checksum-verified model artifacts. The primary Bernoulli/logistic models are never retrained. Historical data, labels, feature values, baseline models/reports/predictions and all eight existing figures remain protected. `autumn_sale_phase7a_integrity.json` freezes the protected inventory for future checks.

## Fixed model configurations

Random Forest: `{'n_estimators': 200, 'max_depth': 4, 'min_samples_leaf': 5, 'max_features': 'sqrt', 'random_state': 42, 'n_jobs': 1}`. XGBoost: `{'n_estimators': 100, 'max_depth': 3, 'learning_rate': 0.05, 'subsample': 0.8, 'colsample_bytree': 0.8, 'objective': 'binary:logistic', 'eval_metric': 'logloss', 'random_state': 42, 'n_jobs': 1}`. No configuration changes are based on observed scores. Native defaults not explicitly overridden are recorded with the resolved estimator parameters in the manifest. Seeds are 42 and estimator jobs are one; numerical math thread pools are also limited to one.

XGBoost availability: `available`. The implemented conditional XGBClassifier path uses the same training-only median pipeline and no eval_set or early stopping. `requirements-ensemble.txt` declares xgboost==2.1.4 without changing the protected baseline dependencies. No network install is attempted. When unavailable, XGBoost has no predictions, trained artifact, importance values or evaluated metrics; its dependent figure is omitted, and comparison tables explicitly mark it unavailable. There is no substitute estimator. The XGBoost training path has not been executed or runtime-validated in this environment when its dependency is unavailable.

## Primary model comparison

| Model | ROC-AUC ↑ | AP ↑ | Brier ↓ | Log loss ↓ | Accuracy ↑ | Precision ↑ | Recall ↑ | F1 ↑ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Bernoulli | 0.500000 | 0.600000 | 0.240625 | 0.674298 | 0.600000 | 0.600000 | 1.000000 | 0.750000 |
| Logistic regression | 0.933750 | 0.937660 | 0.075389 | 0.268593 | 0.910000 | 0.880597 | 0.983333 | 0.929134 |
| Random Forest | 0.927083 | 0.918201 | 0.081897 | 0.288333 | 0.880000 | 0.842857 | 0.983333 | 0.907692 |
| XGBoost | 0.929583 | 0.926240 | 0.067501 | 0.252518 | 0.930000 | 0.907692 | 0.983333 | 0.944000 |

↑ Higher is better for ROC-AUC, AP, accuracy, precision, recall and F1. ↓ Lower is better for Brier and log loss. Undefined metrics are null with explicit reasons. Confusion matrices use actual rows and predicted columns in [0,1] order:

{"bernoulli_baseline": [[0, 40], [0, 60]], "logistic_regression": [[32, 8], [1, 59]], "random_forest": [[29, 11], [1, 59]], "xgboost": [[34, 6], [1, 59]]}

Random Forest minus full logistic: ROC-AUC -0.006667, AP -0.019459, Brier +0.006508, log loss +0.019739, accuracy -0.030000. Discrimination and probability error are separate criteria; accuracy at one threshold does not establish a universal best model. Brier/log loss assess probability quality against operational labels and do not alone establish calibration. No significance, population-wide, causal or verified-participation claim follows these point estimates. Additional nonlinear complexity is not assumed beneficial. All four predefined model types are evaluated; the inspected-holdout limitation still applies.

## Secondary temporal check

Fit all available model types anew on 2023 only (100 rows, 55 positive / 45 negative), then evaluate 2024 (100 rows, 60 positive / 40 negative). The Bernoulli prior is **0.55**, estimated solely from 2023 labels. Logistic uses the Phase 7A configuration with a separate training-only imputer/scaler; ensembles retain the predefined configurations. These temporary fits never overwrite primary artifacts.

| Model | ROC-AUC ↑ | AP ↑ | Brier ↓ | Log loss ↓ | Accuracy ↑ | Precision ↑ | Recall ↑ | F1 ↑ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Bernoulli | 0.500000 | 0.600000 | 0.242500 | 0.678105 | 0.600000 | 0.600000 | 1.000000 | 0.750000 |
| Logistic regression | 0.910833 | 0.901928 | 0.090222 | 0.336933 | 0.900000 | 0.878788 | 0.966667 | 0.920635 |
| Random Forest | 0.892917 | 0.867763 | 0.111685 | 0.378861 | 0.860000 | 0.838235 | 0.950000 | 0.890625 |
| XGBoost | 0.910417 | 0.901769 | 0.104885 | 0.356591 | 0.870000 | 0.898305 | 0.883333 | 0.890756 |

This check and the primary experiment use different training sizes and evaluation years; differences are not clean estimates of temporal drift. Games have already appeared in training. Since 2024 outcomes contribute to primary training, the secondary analysis is not an independent confirmatory test. `autumn_sale_temporal_robustness.json` includes all metrics, preprocessing, fitted fingerprints and actual secondary predictions.

## Coverage sensitivity: post-hoc exploratory diagnostic

The fixed subset is `['prior_price_record_count', 'days_since_last_price_record', 'has_prior_price_history']`: prior price-record count, price-record recency and presence of prior price history. These describe historical price-observation availability, regardless of whether observations show discounts. Discount count, discount recency and prior-discount indicator are deliberately excluded from this narrow diagnostic because they combine historical discount behavior with availability. The subset is declared before diagnostic fitting; it is not selected from its evaluation results.

A separate coverage-only logistic pipeline uses the same logistic configuration, median imputation and StandardScaler, trained only on 2023–2024. At evaluation it has ROC-AUC **0.865833**, AP **0.874952**, Brier **0.108245** and accuracy **0.870000**. Full-feature logistic has ROC-AUC **0.933750**, AP **0.937660**, Brier **0.075389** and accuracy **0.910000**.

Strong performance from coverage features would suggest that the operational target partly reflects data-provider observation patterns; it would not prove the precise source of the predictive signal or isolate coverage from underlying commercial behavior. This diagnostic is post-hoc, motivated by Phase 7A findings on an already examined holdout. It does not replace a primary model or influence any hyperparameter, feature or threshold choice. Complete metrics, diagnostic predictions, preprocessing and coefficients are in `autumn_sale_coverage_sensitivity_modeling.json`.

## Feature importance

Random Forest native importance is normalized mean decrease in impurity across fitted training trees. XGBoost's conditional implementation reports normalized average split gain. Feature names come from the fitted transformed schema. Permutation importance uses the fitted complete pipeline on 2025, scoring ROC-AUC with **20 repeats per feature**, seed **42**, n_jobs=1; it reports mean score decrease, repeat SD and every repeat. This is an exploratory diagnostic on the previously examined holdout, never used to select predictors or retune models. Correlated age/release, count/recency and discount-summary features can share, mask or distort rankings. Native importance can favor variables with more possible splits; negative permutation values are possible. Repeat SD is not a confidence interval. Importance does not establish causality or explain why a publisher discounts a game. Data is saved in `autumn_sale_ensemble_feature_importance.json`.

## Visualizations

All figures reuse the protected `src/plotting_style.py`: white backgrounds, muted consistent model colors, subtle grids, sans-serif text and PNG at 300 DPI. Metric bars start at zero and use [0,1]; confusion matrices share a scale and label operational rows/columns; probability histograms use common bins and small multiples. The ROC/AP/Brier charts separate evaluation dimensions. Temporal and coverage captions explicitly state their limitations. Native and permutation importance are separate panels, with transformed names and no causal claims. No HTML report or dashboard is generated. `autumn_sale_ensemble_plot_data.json` stores the actual underlying values, rebuilt from saved predictions rather than hard-coded results.

- `model_roc_auc_comparison.png`: generated
- `model_average_precision_comparison.png`: generated
- `model_brier_comparison.png`: generated
- `model_roc_curves.png`: generated
- `model_pr_curves.png`: generated
- `model_confusion_matrices.png`: generated
- `random_forest_feature_importance.png`: generated
- `xgboost_feature_importance.png`: generated
- `model_probability_distributions.png`: generated
- `model_temporal_robustness.png`: generated
- `coverage_sensitivity_comparison.png`: generated

## Reproduction, artifacts and verification

Use the local dependencies already installed; `requirements-ensemble.txt` declares the optional XGBoost dependency. Phase 7B itself is offline:

```bash
python3 -B src/09_train_ensemble_models.py --verify
python3 -B -m unittest discover -s tests -p 'test_ensemble_models.py'
```

`--verify` runs the full offline suite, compares two complete isolated runs including diagnostics, predicts after reloading this run's trusted local artifacts, checks actual output hashes, then saves verified results. A normal run explicitly records tests and repeated-run verification as not run. Model artifacts are complete joblib pipelines; only trusted local outputs are loaded. Versions: `{'python': '3.9.6', 'sklearn': '1.6.1', 'xgboost': '2.1.4', 'numpy': '2.0.2', 'pandas': '2.3.3', 'matplotlib': '3.9.4', 'joblib': '1.5.3'}`. Reproduction across package/platform versions is not guaranteed.

Execution results: `{'full_offline_test_suite': 'PASS', 'tests_run': 201, 'failures': 0, 'errors': 0, 'skipped': 0, 'skip_reasons': [], 'determinism': 'PASS: two complete isolated Phase 7B runs', 'predictions_identical': True, 'metrics_identical': True, 'fitted_parameters_identical': True, 'secondary_results_identical': True, 'coverage_results_identical': True, 'importance_values_identical': True, 'plotted_data_identical': True, 'png_bytes_identical': True, 'joblib_bytes_identical': True, 'structured_outputs_byte_identical': True, 'determinism_note': 'PNG/model bytes compared in this environment; cross-platform identity is not guaranteed.'}`. Artifact reload checks: `{'random_forest': {'probabilities_identical': True, 'fitted_parameters_identical': True}, 'xgboost': {'probabilities_identical': True, 'fitted_parameters_identical': True}}`. Protected before/after inventories agree for **186** earlier files. Zero network/API requests. PNG and model bytes are compared before any identity claim; underlying plotted data is compared separately.

## Methodological assessment and scope

The small, nonrepresentative pilot, repeated-game dependence, one previously inspected primary holdout, incomplete recording coverage, source snapshot selection bias, release-date/eligibility uncertainty and unverified retrospective provider availability limit conclusions. Historical observation counts are not complete campaigns or price-state trajectories. Secondary performance and feature importance remain exploratory. No fresh confirmatory experiment or verified true-negative dataset is established.

This is Phase 7B only. Raw histories, operational labels and Phase 6/7A outputs are unchanged. No new games or data, PU learning, large searches, 2026 predictions, genre analytics, rankings, calibration fitting or dashboard. Stop before Phase 8 and Phase 9. Future work needs explicit approval and a separately designed untouched evaluation set.
