# Dummy — frozen model card

Status: predefined comparison; not selected. Configuration and threshold were not revised using 2025 results.

## Objective and data

Predict observed ITAD Steam Autumn Sale discount evidence, positive class 1.
Operational policy: A→1, B→0, C→Unknown, D→0. **Operational zeros mean no discount
observed in available evidence; they do not establish verified nonparticipation.**
Frozen cohort: 2,000 games, 6,000 game-year rows, 3,030 positives, 2,970 zeros,
zero unknowns. US / Steam shop 61 historical evidence; 81 successfully empty
histories contribute 243 operational zeros. This is not a representative census
of Steam games. No target or feature was redesigned.

## Features and missing values

Approved runner predictors: `game_age_days`, `release_year`, `release_month`, `release_quarter`, `prior_price_record_count`, `prior_discount_count`, `prior_discount_rate`, `days_since_last_price_record`, `days_since_last_discount`, `max_prior_discount_pct`, `mean_prior_discount_pct`, `last_observed_price`, `last_observed_discount_pct`, `has_prior_price_history`, `has_prior_discount_observation`.
This Dummy ignores predictors and estimates only the training class prior.
No learned feature preprocessing.
No training feature was entirely missing, so the all-missing structural-zero
contingency was unused. Complete fitted preprocessing is retained in the saved pipeline.

## Temporal design and selection

Development: train 2023 (2,000 rows), validate 2024 (2,000).
Final: refit with fresh preprocessing on 2023–2024 (4,000), test 2025 (2,000).
All 2,000 games recur across years; evaluation measures later-sale performance
on previously represented games, **not unseen-game generalization**.
The observations are dependent within game. Previously audited 2025 outcomes
do not constitute a fresh confirmatory holdout.

One predefined configuration per model, seed 42, threshold .50. No tuning,
early stopping, probability calibration fitting or threshold optimization.
Selection used only 2024 average precision, then Brier score for ties; XGBoost
won before the single held-out probability pass. Other test comparisons did not
change selection. Parameters: `{"random_state": 42, "strategy": "prior"}`.

## Recorded performance

| Metric | Development 2024 | Held-out 2025 |
| --- | ---: | ---: |
| Accuracy | 0.466000 | 0.491500 |
| Balanced accuracy | 0.500000 | 0.500000 |
| Precision | undefined | 0.491500 |
| Recall | 0.000000 | 1.000000 |
| F1 | 0.000000 | 0.659068 |
| ROC-AUC | 0.500000 | 0.500000 |
| Average precision / PR-AUC | 0.534000 | 0.491500 |
| Brier score | 0.250824 | 0.250338 |

Confusion matrices (actual 0/1 rows, predicted 0/1 columns): development
`[[932, 0], [1068, 0]]`; held-out `[[0, 1017], [0, 983]]`.
Undefined metrics are saved as null with reasons. AP is the step-weighted
ranking measure, not trapezoidal PR interpolation.

## Coverage, calibration and limitations

Held-out score/observation-count Spearman correlation:
`None`.
Ten-bin held-out calibration error:
`0.020250`.
Calibration is descriptive and bin-dependent; no calibrator was fitted.
Returned observation density, recording gaps and historical discounts may
predict provider coverage as well as actual discount propensity. Correlation
and split gain do not establish causation. Sparse subgroups can have high
accuracy while missing rare positives. Single-class discrimination is undefined.

Retrospective record timestamps do not prove ITAD contemporaneous availability:
backfill/initialization remain unverified. Reported release dates and their
stability are assumed; release-hour ambiguity, raw timestamp/shop conflicts and
snapshot-based population selection remain documented limitations. No raw
history was repaired, deduplicated or treated as continuous daily price states.
No seed sensitivity, unseen-game test or prospective new-year evaluation ran.

## Appropriate and inappropriate uses

Appropriate: retrospective analysis of recorded discount evidence, comparison
of fixed models, exploratory probability/coverage diagnostics within the
documented source scope and calendar windows.
Inappropriate: certifying actual Steam sale participation/nonparticipation,
interpreting zero as proven absence, causal claims from importance/correlation,
guaranteeing future discounts or purchase savings, claiming unseen-game or
population-wide performance, or tuning models/thresholds using 2025 diagnostics.

Artifacts: `../cohort_2000_models/final_models/bernoulli_baseline.joblib`;
configuration, versions and checksums are in the preserved Phase 7A manifest.
This card and all figures use saved outputs only. No fitting or new probability
predictions were made in Phase 7B.
