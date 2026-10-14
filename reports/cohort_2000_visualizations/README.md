# Phase 7B — frozen model diagnostics and exploratory figures

**23 individual 300-DPI light-theme PNGs and four model cards** were created
from the frozen Phase 7A predictions, metrics, fitted-pipeline metadata and
XGBoost split gains. No models were fitted or queried for new predictions;
model selection, configurations and the threshold remain unchanged.

The objective is **observed ITAD Autumn Sale discount evidence**, not verified
Steam Autumn Sale participation. A→1, B/D→0, C→Unknown. Operational zero means
no discount observed in available evidence; it does not establish verified
nonparticipation. All figures and findings are exploratory, not presentation
claims of prospective performance.

## Figure index

Development means 2023 training → 2024 validation. Held-out means 2023–2024
training → 2025 testing. Both use all 2,000 games and the fixed .50 threshold.

| Diagnostic | Development 2024 | Held-out 2025 |
| --- | --- | --- |
| Model comparison | [PNG](development_model_comparison.png) | [PNG](held_out_model_comparison.png) |
| ROC curves | [PNG](development_roc_curves.png) | [PNG](held_out_roc_curves.png) |
| Precision–recall curves | [PNG](development_pr_curves.png) | [PNG](held_out_pr_curves.png) |
| Selected XGBoost confusion | [PNG](development_xgboost_confusion.png) | [PNG](held_out_xgboost_confusion.png) |
| Probability calibration | [PNG](development_calibration.png) | [PNG](held_out_calibration.png) |
| Selected probability distribution | [PNG](development_probability_distribution.png) | [PNG](held_out_probability_distribution.png) |
| Observation count distribution | [PNG](development_observation_count_distribution.png) | [PNG](held_out_observation_count_distribution.png) |
| Observation count vs probability | [PNG](development_coverage_probability.png) | [PNG](held_out_coverage_probability.png) |
| Operational labels by coverage | [PNG](development_labels_by_coverage.png) | [PNG](held_out_labels_by_coverage.png) |
| Performance by coverage | [PNG](development_performance_by_coverage.png) | [PNG](held_out_performance_by_coverage.png) |
| False positives/negatives by coverage | [PNG](development_errors_by_coverage.png) | [PNG](held_out_errors_by_coverage.png) |

The 23rd figure is [final fitted XGBoost gain importance](xgboost_gain_importance.png).
All figures have white backgrounds, consistent DejaVu Sans typography,
restrained gridlines/borders and consistent model colors. Dimensions range
from 1,920–2,700 pixels wide, with 300-DPI metadata. Individual explanatory
captions are in [figure_captions.md](figure_captions.md) and
[figure_captions.csv](figure_captions.csv).

## Model comparison and calibration findings

All reported metrics and confusion counts were reconciled to saved probabilities
and targets; coverage fields were cross-checked against the frozen feature
table. Average precision is the reported PR-AUC measure. The PR curve is drawn
from observed precision/recall thresholds; trapezoidal interpolation is not
substituted for average precision.

| Model | Development AP | Held-out AP | Held-out accuracy | Held-out balanced accuracy | Held-out Brier |
| --- | ---: | ---: | ---: | ---: | ---: |
| Dummy | .5340 | .4915 | .4915 | .5000 | .2503 |
| Logistic Regression | .9383 | .9293 | .8775 | .8790 | .0889 |
| Random Forest | .9358 | .9440 | .8985 | .8992 | .0798 |
| XGBoost | .9445 | .9479 | .9140 | .9143 | .0703 |

XGBoost remains the selection made from 2024 AP before the held-out pass. No
2025 diagnostic changed that decision. Logistic had better development accuracy
and Brier score; selection was deliberately based on the previously frozen
ranking criterion. Full metrics, including precision, recall, F1, log loss and
explicit undefined values, are in [model_comparison.csv](model_comparison.csv).

The 2025 selected confusion counts remain **TN 912, FP 105, FN 67, TP 916**.
Its mean probability is .49708 versus observed prevalence .49150. Ten-bin
calibration error is .02115, compared with .06598 in development. These are
fixed equal-width bins, with counts in [calibration_bins.csv](calibration_bins.csv);
small/empty bins limit interpretation. Lines connecting nonempty reliability
bins are visual guides, not fitted calibration curves. No calibrator was fitted.

The Dummy has no ranking discrimination (ROC-AUC .5). Its training prior
crosses the .5 threshold between stages, so it predicts all zeros in development
and all positives in the test. Development precision is undefined because no
positives were predicted; it is not silently set to zero.

## Fitted feature importance

Method: inspect the existing final XGBoost booster with
`get_score(importance_type='gain')`, map fitted feature positions to the approved
15-feature order, and normalize each feature's **average split gain** by the
sum of average gains. Unused features receive zero. Values were checked against
the saved Phase 7A native importances and `XGBClassifier.feature_importances_`.
No refitting, permutation prediction passes or feature selection occurred.

| Leading feature | Normalized average split gain |
| --- | ---: |
| days_since_last_price_record | .31688 |
| prior_discount_count | .21927 |
| last_observed_discount_pct | .10134 |
| has_prior_price_history | .08107 |
| prior_price_record_count | .06641 |
| days_since_last_discount | .06333 |

These gains describe split associations in the fitted model, not causal effects,
unique contributions or guaranteed out-of-sample usefulness. Correlated
recency/count/availability predictors can share or mask importance. Low gain
does not prove a feature is irrelevant. Raw and normalized gains for all 15
features are in [xgboost_gain_importance.csv](xgboost_gain_importance.csv).

## Coverage findings and subgroup limitations

Prior observation count is the number of valid returned price observations
strictly before the historical cutoff, not number of distinct sales, discounted
days or proof of complete history. Scatter plots use a symlog count axis,
including zero, and every saved XGBoost probability. Histogram bins are ten
records wide; the zero-observation sample size is annotated separately.

Score/count Spearman correlation is **.89710 in development** and **.89720 in
the held-out test**. This strong association does not establish that recording
density causes scores, nor disentangle provider coverage from actual pricing
behavior.

| Test coverage | n | Positive / zero | Accuracy | Precision | Recall | Balanced accuracy | FP / FN |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 records | 82 | 0 / 82 | 1.0000 | Undefined | Undefined | Undefined | 0 / 0 |
| 1–9 records | 538 | 19 / 519 | .9721 | .7000 | .3684 | .6813 | 3 / 12 |
| 10–29 records | 336 | 118 / 218 | .8185 | .7050 | .8305 | .8212 | 41 / 20 |
| 30+ records | 1,044 | 846 / 198 | .9080 | .9300 | .9586 | .8253 | 61 / 35 |

The sparse 1–9 group has 97.2% accuracy but detects only **7 of 19** positives,
missing 12. All 82 zero-history games have operational-zero labels and negative
predictions; that does not independently verify absence of real discounts.
The 30+ group accounts for 61 false positives because it is larger and has
different class proportions; error counts should not be read as comparable rates.

Positive operational-label prevalence rises from 3.5% in the 1–9 group to 81.0%
in the 30+ group. The plots therefore show both recording/behavior association
and a major subgroup class imbalance. Aggregate accuracy alone hides important
limitations. Sample sizes and both class counts accompany each subgroup figure.
Precision with no predicted positives, recall with no actual positives, and
single-class balanced accuracy/AP are explicitly undefined, represented as
blank CSV cells/nulls and gaps/annotations rather than plotted zeros.

[coverage_summary.csv](coverage_summary.csv) includes both stages, all subgroup
sizes/classes, metrics, confusion counts and undefined reasons. Bins are
mutually exclusive and sum to 2,000 per year. The figures do not authorize new
threshold choices, model tuning or reclassification of operational zeros.

## Model cards and permissible interpretation

- [Dummy](model_card_bernoulli_baseline.md)
- [Logistic Regression](model_card_logistic_regression.md)
- [Random Forest](model_card_random_forest.md)
- [XGBoost](model_card_xgboost.md)

Each card covers objective/data, original label semantics, the 15-feature
allowlist, missing-data treatment, split/selection, performance, calibration,
coverage dependence, source availability and appropriate/inappropriate uses.

All 2,000 games recur between earlier training and later evaluation; three
observations per game are dependent. Results do not establish unseen-game or
Steam-population generalization. Retrospective ITAD timestamps cannot establish
when provider records first became available: backfill/initialization remain
unverified. Reported release-date stability, missing release hours, existing
timestamp/shop conflicts and retrospective cohort-selection bias remain.
Successful empty histories provide valid collection completion, not proof that
a game never discounted. No new confidence intervals, seed robustness or
prospective calendar-year performance claims were introduced.

## Reproduction and verification

From the repository root, regenerate into a **new** directory:

```sh
env -u ITAD_API_KEY PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp \
  /usr/bin/python3 -B src/visualize_cohort_models.py \
  --input-dir reports/cohort_2000_models \
  --output-dir reports/cohort_2000_visualizations_reproduction
```

The adapter refuses existing output directories, verifies Phase 7A/6C input
checksums, blocks network and subprocesses, and guards model `fit`, `predict`
and `predict_proba` methods. It only reads fitted parameters/split gains and
computes metrics/curves from saved predictions. Writes are confined to its new
report directory and an external plotting cache. Existing plotting-style
definitions were reused without altering their source or historical outputs.

All **23 PNGs reproduced byte-for-byte** in an independent temporary render.
All plots were visually reviewed, and readable undefined-metric placement was
corrected before the final freeze. Figure dimensions, white backgrounds and
300-DPI metadata were checked. [plot_data.json](plot_data.json) and
[curve_points.csv](curve_points.csv) record supporting numeric data.
[figure_manifest.json](figure_manifest.json) lists individual dimensions/hashes;
[checksums.json](checksums.json) covers all delivered artifacts except itself.

The visualization-only offline suite has **9 passing tests, zero failures or
errors**, covering coverage bins, explicit undefined metrics, saved metric
reconciliation, native-gain normalization, no-fit/no-prediction guards,
already-annotated CSV compatibility and missing-value serialization. Existing
model-fitting/full-regeneration tests were deliberately not run during this
no-retraining phase.

All **2,270 preexisting data/report/model and protected files** retained their
phase-start bytes. This includes all raw caches, frozen cohorts, the
3,816-attempt journal, archived checkpoints, Phase 6A/B/C outputs, all 36
Phase 7A files and original pilot artifacts/models. All **219 protected
artifacts were preserved**. Historical baseline agreement remains **218/219**,
with the existing ordering-only mismatch unchanged and unrepaired.

Next, use these fixed results for a coverage-aware model review and exploratory
presentation. Any new calibration, model-selection or feature experiment needs
a separately frozen development protocol and suitable evaluation data;
these 2025 diagnostics must not become a tuning set. Do not turn probabilities
into guarantees of actual Steam sale participation or purchase savings.
