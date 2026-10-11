# Phase 7A — Baseline modeling evaluation

## Research objective and operational target

Can historical Steam game metadata and pre-sale pricing behavior predict whether a Steam-store discount will be **recorded** during the official Autumn Sale? 1: a qualifying Steam-store discount was recorded during the official Autumn Sale window; 0: no qualifying discount was recorded. Zero does not establish absence of an actual discount. Probabilities concern recorded occurrence, not verified participation.

## Dataset and chronological protocol

The pilot has 100 games and 300 game-year observations (2023–2025), with 175 operational positives and 125 negatives. Train on 2023–2024: 200 observations, 115 positives, 85 negatives. Validate on 2025: 100 observations, 60 positives, 40 negatives. Training prevalence is 0.575; validation prevalence is 0.600, reported only for evaluation. No random split, cross-year shuffling, hyperparameter search, threshold optimization, or validation-driven model changes occur. Configurations were fixed before evaluation; fitting receives training rows only.

The same 100 games recur across years. This measures temporal generalization to a later sale for previously represented games. It does **not** establish generalization to entirely unseen games or the full Steam catalog. Repeated observations are dependent; no independence-based confidence intervals are claimed.

## Feature selection and preprocessing

Only the exact Phase 6 manifest allowlist enters the logistic predictor matrix:

`game_age_days`, `release_year`, `release_month`, `release_quarter`, `prior_price_record_count`, `prior_discount_count`, `prior_discount_rate`, `days_since_last_price_record`, `days_since_last_discount`, `max_prior_discount_pct`, `mean_prior_discount_pct`, `last_observed_price`, `last_observed_discount_pct`, `has_prior_price_history`, `has_prior_discount_observation`.

AppID, sale year, cutoff, target, audit flag, evidence and PU fields are excluded. The complete fitted Pipeline contains explicit allowlist selection (all other columns dropped), median imputation, StandardScaler, and LogisticRegression. Numeric types are validated without silently repairing source values. All medians, means and variances come only from training observations. Two existing binary coverage flags are retained and standardized alongside the other predictors. No redundant missingness indicators are added: in the current data, price-derived missingness aligns with no prior price history, and discount-summary missingness aligns with no prior discount observation. Future currency/conflict missingness may differ and requires a new documented review.

Training missing counts: `{'game_age_days': 0, 'release_year': 0, 'release_month': 0, 'release_quarter': 0, 'prior_price_record_count': 0, 'prior_discount_count': 0, 'prior_discount_rate': 7, 'days_since_last_price_record': 7, 'days_since_last_discount': 33, 'max_prior_discount_pct': 33, 'mean_prior_discount_pct': 33, 'last_observed_price': 7, 'last_observed_discount_pct': 7, 'has_prior_price_history': 0, 'has_prior_discount_observation': 0}`. Training constant columns: `[]`. Entirely missing training columns: `[]`. The documented fallback excludes entirely missing columns using training predictors only; no exclusions occur in this experiment. Constant observed columns would be retained and handled by StandardScaler. Imputer/scaler statistics and transformed names are saved in the manifest.

## Baseline definitions and fixed configuration

Bernoulli uses sklearn DummyClassifier(strategy="prior"). Its fitted class prior is `[0.425, 0.575]`: P(recorded discount)=0.575 and P(no recorded discount)=0.425. It needs no feature preprocessing; a zero-valued placeholder matrix supplies row count to the sklearn API. Every validation game receives probability 0.575. This is deterministic probability estimation, without random Bernoulli draws. Blank decision_score in the CSV means not applicable for this baseline.

LogisticRegression parameters: `{'penalty': 'l2', 'C': 1.0, 'solver': 'lbfgs', 'max_iter': 2000, 'random_state': 42, 'class_weight': None, 'tol': 0.0001}`. These are unoptimized initial defaults. Seed: 42. Iterations used: `[18]`. No class weights. Both models use predicted_class = 1 when probability >= 0.50, otherwise 0. Validation data is consulted only after fitting for prediction and evaluation.

## Metrics and model comparison

Probability metrics are ROC-AUC, average precision (sklearn definition), Brier score and log loss. Fixed-threshold metrics are accuracy, precision, recall and F1. Confusion matrices use rows for actual operational labels and columns for predicted labels, both ordered [0,1]. Undefined metrics are JSON null with a reason, never silently zero-filled; no metric is undefined in this experiment. Lower Brier/log loss is better; larger other reported metrics is better.

| Metric | Bernoulli | Logistic regression |
| --- | ---: | ---: |
| ROC-AUC | 0.500000 | 0.933750 |
| Average precision | 0.600000 | 0.937660 |
| Brier score | 0.240625 | 0.075389 |
| Log loss | 0.674298 | 0.268593 |
| Accuracy | 0.600000 | 0.910000 |
| Precision | 0.600000 | 0.880597 |
| Recall | 1.000000 | 0.983333 |
| F1 | 0.750000 | 0.929134 |

bernoulli_baseline confusion matrix (rows actual 0/1, columns predicted 0/1): `[[0, 40], [0, 60]]`.

logistic_regression confusion matrix (rows actual 0/1, columns predicted 0/1): `[[32, 8], [1, 59]]`.

The constant baseline has ROC-AUC 0.5 and AP equal to validation prevalence (0.600); its **prediction** is still the training prior (0.575). Logistic regression has ROC-AUC 0.93375, AP 0.93766 and accuracy 0.91; it improves all eight reported metrics over the constant baseline on this holdout. The fitted logistic results provide a pilot comparison, not evidence of verified participation, causal behavior, or population-wide performance. Differences on 100 holdout observations should be interpreted conservatively; no significance claim or configuration change follows this evaluation.

## Figures

All eight PNGs use white backgrounds, muted blue/orange/gray, restrained grids, consistent fonts, and 300 DPI. Dimensions are 7.2 × 4.8 inches except the coefficient figure (7.2 × 5.8 inches) to fit all transformed names. `src/plotting_style.py` provides reusable styling. `autumn_sale_baseline_plot_data.json` records every underlying plotted value.

- `bernoulli_distribution.png`: two training-prior probability masses, 0.425 and 0.575.
- `logistic_sigmoid.png`: stable scipy.special.expit curve and the actual 100 validation decision scores/probabilities. Maximum consistency error: 0. The combined multivariable score, not any individual feature, is on the x-axis. Points lie on the sigmoid by construction. This explanatory plot is **not evidence of predictive accuracy**.
- `logistic_coefficients.png`: actual transformed feature names and all fitted coefficients, sorted by value. Positive blue and negative orange bars are conditional associations on the imputed, standardized feature scale, including standardized binary flags. No causal interpretation is justified. Correlated age/release and price-summary predictors can make individual coefficients unstable or hard to interpret.
- `logistic_confusion_matrix.png`: operational label counts at fixed 0.50 threshold, rows actual / columns predicted.
- `baseline_roc_curves.png`: observed threshold points from both models, with AUC and a chance diagonal; no invented performance points.
- `baseline_pr_curves.png`: actual precision/recall threshold points and AP; 2025 prevalence is only an evaluation reference, distinct from the fitted Bernoulli prior.
- `logistic_probability_distribution.png`: identical ten uniform histogram bins for both operational classes.
- `logistic_reliability.png`: five fixed uniform calibration bins, sample counts shown, empty bins omitted. Calibration is measured against recorded-discount labels. With just 100 observations, this gives limited evidence and no strong calibration conclusion.

## Artifacts and verification

Complete preprocessing and classifier are saved in `models/logistic_regression.joblib`; the fitted prior estimator is `models/bernoulli_baseline.joblib`. Format: joblib pickle, for trusted local artifacts only. Versions: Python 3.9.6, sklearn 1.6.1, NumPy 2.0.2, pandas 2.3.3, SciPy 1.13.1, matplotlib 3.9.4, joblib 1.5.3. Loading across package versions is not guaranteed. Saved artifacts are reloaded immediately and predictions compared exactly. Reload results: `{'bernoulli_baseline': {'probabilities_identical': True, 'decision_scores_identical': True}, 'logistic_regression': {'probabilities_identical': True, 'decision_scores_identical': True}}`.

Execution checks: `{'full_offline_test_suite': 'PASS', 'tests_run': 171, 'failures': 0, 'errors': 0, 'skipped': 0, 'determinism': 'PASS: two complete isolated experiments', 'predictions_identical': True, 'metrics_identical': True, 'fitted_parameters_identical': True, 'plotted_data_identical': True, 'structured_outputs_byte_identical': True, 'png_bytes_identical': True, 'joblib_bytes_identical': True, 'png_determinism_note': 'PNG bytes compared in this environment; no cross-platform byte identity guarantee.'}`. Protected input SHA-256 inventories match for 166 prior files, including Phase 6 features/labels, prior source/tests/reports and all frozen histories. Socket/DNS access is blocked. No API requests or new data. Structured predictions, metrics, fitted parameters and plot data are compared across complete runs; PNG bytes are compared separately before any claim of identity. Verification is specific to this recorded environment; different math libraries/fonts may yield platform differences.

## Limitations

Operational zeros establish no recorded qualifying observation, not confirmed non-discounting. Sparse and incomplete histories and provider recording coverage can influence features and labels. Retrospective timestamps do not prove point-in-time ITAD availability; backfill and requested-since initialization remain unresolved. Release-date accuracy, early-access/full-release interpretation, same-day release-hour eligibility and pre-release price observations remain unresolved. Counts describe observations, not campaigns or discount durations; last prices are observations, not reconstructed cutoff states. Pilot sampling used undated snapshots, introducing selection bias despite their exclusion from predictors. Linear default models, correlated predictors, repeated games, one validation year and only 100 holdout observations limit interpretation.

## Reproduction

Use an environment with the recorded dependencies in `requirements-baseline.txt` already installed; execution is offline. Original `requirements.txt` is protected and unchanged:

```bash
python3 -B src/08_train_baseline_models.py --verify
python3 -B -m unittest discover -s tests -p 'test_baseline_models.py'
```

`--verify` runs the complete offline suite, then two complete experiments with isolated output directories and read-only source inputs, checks structured equality/model parameters/PNG bytes, and writes the final verified artifacts. A normal run without `--verify` generates artifacts but explicitly records tests/determinism as not run. Earlier pipelines are never rerun against the project inputs.

## Phase 7B handoff — not implemented

Require explicit human approval before Phase 7B. Preserve this frozen baseline, allowlist and operational target semantics. Any future model/configuration selection should use training-only temporal resampling; 2025 has now been inspected and must not become a tuning set. Consider a new untouched holdout for confirmatory evaluation. Review recording coverage and repeated-game dependence, and agree on the permitted Phase 7B scope before selecting additional methods. No Phase 7B, 8 or 9 work, PU learning, rankings, dashboard or 2026 prediction is performed.
