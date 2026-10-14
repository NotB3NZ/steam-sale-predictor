# Technical appendix — what the story's numbers mean

This is a reference for the [narrative](narrative_research_report.md), not a new experiment. All performance, EDA and prediction quantities are taken from saved project artifacts. No model is loaded or queried for this synthesis.

## A. Datasets and observation units

| Dataset | Size / unit | Important distinction |
| --- | --- | --- |
| Original metadata snapshot | 125,855 entries | Snapshot attributes do not establish historical availability |
| Cleaned sampling catalog | 99,194 paid-game candidates | Source-price eligibility, not proof of permanent paid/free status |
| Diagnostic pilot | 100 games; 300 game-year rows | Earlier pilot experiments, separate from the cohort results |
| Original frozen cohort | 2,000 unique AppIDs | Includes the original 100 pilot games and 1,900 selected additions |
| Historical modeling table | 6,000 rows: 2,000 each in 2023, 2024 and 2025 | Same games repeat; rows within a game are dependent |
| Historical operational targets | 3,030 positive; 2,970 zero; no Unknown labels | Observed evidence, not independently verified participation |
| Frozen 2026 output | 2,000 saved scores/classes | Retrospective predictions without an independent outcome evaluation |

The cohort is a mixture of diagnostic pilot selection and the existing stratified nonpilot sampling procedure. It is not a representative sample of all Steam games. New nonpilot selection used the historical eligibility frame; source-date assumptions and the original pilot's release-hour uncertainty remain documented limitations.

The expansion journal records 3,816 attempts: 3,801 HTTP-200 results, five HTTP-429 responses, one HTTP-403 response and nine timeout/connection-failure results without an HTTP status. This is not a total for every original pilot or historical research request. Final complete caches include 81 successful empty histories; cache completeness does not imply complete pricing coverage. See the [final batch receipt](../../data/cohorts/runs/2000_batch_004/collection_quality.json), [journal](../../data/cohorts/itad/cache/http_attempts.jsonl) and [cohort audit](../cohort_2000_labelability/README.md).

## B. Label rules and historical windows

The unchanged policy is `operational_observed_v1`: A→1, B→0, D→0, C→Unknown. A requires a directly observed qualifying discount inside the window. B has only valid full-price in-window observations. D has no directly timestamped in-window observations. C has ambiguous in-window information without a qualifying discount. No C rows occur in the frozen historical table.

“No discount observed” does not verify nonparticipation. Even valid full-price observations describe only their timestamps; the project does not infer continuous prices between records. Formal Valve seasonal-event enrollment is also distinct from a qualifying Steam-store offer.

| Sale year | Predictor timestamps strictly before / label start inclusive | Label end exclusive | Discount observed | No discount observed |
| --- | --- | --- | ---: | ---: |
| 2023 | 2023-11-21T18:00:00Z | 2023-11-28T18:00:00Z | 979 | 1,021 |
| 2024 | 2024-11-27T18:00:00Z | 2024-12-04T18:00:00Z | 1,068 | 932 |
| 2025 | 2025-09-29T17:00:00Z | 2025-10-06T17:00:00Z | 983 | 1,017 |

Sources: [frozen label distribution](../cohort_2000_modeling/label_distribution.json), [input calendar/windows](../cohort_2000_modeling/input_manifest.json), [operational policy](../cohort_2000_operational/README.md). The 2023–2024 boundaries are in Pacific standard time, while the 2025 boundary is in Pacific daylight time; using the exact UTC boundaries avoids treating the offset as fixed.

## C. The approved predictors

All historical price inputs must precede the corresponding year's cutoff. Source scope is cached ITAD Steam shop 61 / US. Observations remain discrete records; duplicates are retained. The timestamp check does not prove that the provider made the record available at that historical moment.

| Predictor | Plain-English definition |
| --- | --- |
| `game_age_days` | Days from the reported release date to the sale-start Pacific calendar date |
| `release_year` | Reported release year |
| `release_month` | Reported release month |
| `release_quarter` | Quarter of the reported release date |
| `prior_price_record_count` | Valid earlier price observations, not distinct sales |
| `prior_discount_count` | Qualifying discounted observations within that earlier history |
| `prior_discount_rate` | Discounted observations divided by valid price observations |
| `days_since_last_price_record` | Elapsed days since the latest valid earlier price observation |
| `days_since_last_discount` | Elapsed days since the latest qualifying earlier discount |
| `max_prior_discount_pct` | Largest explicit earlier discount percentage |
| `mean_prior_discount_pct` | Average explicit percentage across earlier discounted observations |
| `last_observed_price` | Latest valid earlier price, withheld for currency/latest-timestamp issues under the frozen rules |
| `last_observed_discount_pct` | Explicit percentage at the latest valid earlier price observation, withheld for a latest-timestamp conflict |
| `has_prior_price_history` | Whether any valid earlier price observation exists |
| `has_prior_discount_observation` | Whether any qualifying earlier discount observation exists |

There are 15 approved predictors. AppID, sale year, cutoff, target, evidence category and the same-day release audit flag are excluded from model inputs. Contemporary master prices, popularity/review totals and previous Autumn Sale participation labels are not added predictors.

Missing source values remain blank. Counts and flags can legitimately be zero; recencies, ratios or values requiring an unavailable observation can be null. In the historical 6,000-row table, three discount-derived predictors each have 1,134 missing cells; four price-history predictors each have 253; eight predictors have none. Definitions and exact missing meanings are preserved in the [feature manifest](../cohort_2000_modeling/feature_manifest.json) and [EDA dictionary](../cohort_2000_eda/predictor_dictionary.csv).

## D. Time splits, preprocessing and fixed models

Development fits on 2023 (2,000 rows; 979 positive / 1,021 zero) and assesses 2024 (2,000; 1,068 / 932). After selection, fresh pipelines fit on 2023–2024 (4,000; 2,047 / 1,953) and assess 2025 (2,000; 983 / 1,017).

The selected model is XGBoost, chosen by highest **2024 average precision**, then lower Brier score for an exact tie, then the predefined candidate order. Selection was locked before the held-out probability pass. One fixed configuration per model was used; no hyperparameter search, early stopping, fitted calibration or threshold optimization occurred. Classification uses probability **≥0.50** for positive.

| Model | Frozen configuration |
| --- | --- |
| Training-prior Dummy | `strategy="prior"`, `random_state=42`; ignores game-specific predictors |
| Logistic Regression | L2 penalty; `C=1.0`, `solver="lbfgs"`, `max_iter=2000`, `tol=0.0001`, `class_weight=None`, `random_state=42` |
| Random Forest | `n_estimators=200`, `max_depth=4`, `min_samples_leaf=5`, `max_features="sqrt"`, `n_jobs=1`, `random_state=42` |
| XGBoost | `n_estimators=100`, `max_depth=3`, `learning_rate=0.05`, `subsample=0.8`, `colsample_bytree=0.8`, `objective="binary:logistic"`, `eval_metric="logloss"`, `n_jobs=1`, `random_state=42` |

Median imputers learn only from the corresponding training partition. Logistic scaling learns only from training-imputed values; tree inputs are not scaled. No training predictor is entirely missing, so an all-missing-column fallback was not used. No extra missingness indicators or feature selector were added. The final Dummy prior is 0.51175, producing all-positive classes at the frozen threshold.

Sources: [precommitted protocol](../cohort_2000_models/precommitted_protocol.json), [selection](../cohort_2000_models/selection.json), [configuration manifest](../cohort_2000_models/model_configuration_manifest.json), [preprocessing receipt](../cohort_2000_models/preprocessing.json), [model cards](../cohort_2000_visualizations/README.md).

The same games appear in all years; this is temporal evaluation for represented games, not unseen-game testing. Earlier audits had inspected 2025 labels, so “held-out” describes exclusion from this model-development procedure, not a claim that the event was previously untouched.

## E. Frozen evaluation numbers and metric meanings

| Model | 2024 average precision | 2025 accuracy | 2025 balanced accuracy | 2025 precision | 2025 recall | 2025 F1 | 2025 ROC-AUC | 2025 average precision | 2025 Brier |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Training-prior baseline | 0.5340 | 0.4915 | 0.5000 | 0.4915 | 1.0000 | 0.6591 | 0.5000 | 0.4915 | 0.2503 |
| Logistic Regression | 0.9383 | 0.8775 | 0.8790 | 0.8165 | 0.9685 | 0.8860 | 0.9524 | 0.9293 | 0.0889 |
| Random Forest | 0.9358 | 0.8985 | 0.8992 | 0.8645 | 0.9410 | 0.9011 | 0.9573 | 0.9440 | 0.0798 |
| XGBoost | 0.9445 | 0.9140 | 0.9143 | 0.8972 | 0.9318 | 0.9142 | 0.9603 | 0.9479 | 0.0703 |

Values are rounded from the [saved development](../cohort_2000_models/development_metrics.json) and [held-out metrics](../cohort_2000_models/held_out_metrics.json). XGBoost's held-out confusion counts are TN 912, FP 105, FN 67, TP 916, with 1,828 agreements among 2,000 rows.

Accuracy is agreement with the recorded labels. Balanced accuracy averages recognition of positives and zeros. Precision is the positive-label share among positive predictions; recall is the share of positive labels found. F1 is their harmonic mean. ROC-AUC measures positive-versus-zero score ordering across thresholds, counting ties neutrally. Average precision summarizes precision at successive recall increases; it is the saved step-weighted measure, not trapezoidal interpolation of a precision–recall curve. Brier is average squared probability error against the recorded binary labels; lower is better.

None is a metric against independently verified sale participation. Probability error on historical operational labels does not establish calibrated probabilities for actual 2026 outcomes. No confidence intervals, seed-robustness claims, new calibration fits or new subgroup experiments are introduced here.

The historical score/count Spearman value is 0.8972 for XGBoost's saved 2025 scores. In the 1–9-observation test group, sample size is 538, with 19 positive labels; the model detects seven and misses twelve despite 97.2% subgroup accuracy. Sources: [saved diagnostics](../cohort_2000_models/held_out_diagnostics.json), [Phase 7B subgroup summary](../cohort_2000_visualizations/coverage_summary.csv).

## F. EDA measurement choices

Phase 8D was descriptive work conducted after model development and prediction freezing. It supplies reader context, not development evidence for new features or thresholds.

Release years come from the original cohort. Prices are **one last valid recorded nominal USD amount per game before the 2025 cutoff**, not every raw price record and not the metadata snapshot's contemporary price. The supported sample is 1,918 values; 82 missing values are omitted, not imputed. Two observed zeros and the $199.99 maximum remain included; no inflation adjustment or clipping is applied.

Observation counts likewise use one frozen pre-2025 count per game, including zero. Recurrence counts sum the three existing operational labels per AppID, assigning each game once to 0, 1, 2 or 3 positive years: 741, 201, 345 and 713 games.

Discount percentages use a different unit: valid, directly timestamped Steam/USD discounted records inside the three sale windows. The supported chart sample has 3,035 records from 1,259 games; two conflicting same-time records and 24 full-price records are chart-only exclusions. The explicit provider percentage is retained, not recomputed from rounded currency fields. Records are not independent campaigns or daily states, and denser games contribute more observations.

Sources: [EDA source documentation](../cohort_2000_eda/data_sources.md), [descriptive statistics](../cohort_2000_eda/descriptive_statistics.json), [recurrence counts](../cohort_2000_eda/evidence_recurrence.csv), [chart-only exclusions](../cohort_2000_eda/discount_exclusions.csv).

## G. The separate 2026 retrospective run

The prediction cutoff is **2026-10-01T17:00:00Z**; the frozen event window ends at **2026-10-08T17:00:00Z**, exclusive. Qualifying predictors use only events strictly before the cutoff. The old wrapper's January-2026 truncation was bypassed through a separate adapter, without changing the feature definitions or historical artifacts.

The existing Phase 8B pipeline fitted fresh median preprocessing and the same selected XGBoost configuration on **2023–2025: 6,000 rows, 3,030 positive / 2,970 zero**. It is stored separately from the evaluated 2023–2024 fit. The earlier 2025 performance numbers do not independently evaluate this refit.

The frozen summary is 2,000 games, 1,026 predicted positives, 974 predicted operational zeros, mean probability 0.4996 and median 0.7096. Coverage/score Spearman is 0.8925.

| Prior price observations | Games | Predicted positives | Predicted operational zeros | Positive prediction rate |
| --- | ---: | ---: | ---: | ---: |
| 0 | 81 | 0 | 81 | 0.00% |
| 1–9 | 505 | 6 | 499 | 1.19% |
| 10–29 | 295 | 74 | 221 | 25.08% |
| 30+ | 1,119 | 946 | 173 | 84.54% |

All 336 incomplete vectors receive predicted operational zero: 255 lack three discount-derived predictors, and 81 lack seven predictors associated with absent valid price history. Their available observation counts range from zero to four. Another 638 predicted zeros have complete vectors. Missingness is not proof of nonparticipation.

**Retrospective event-time-filtered predictions using post-cutoff-collected historical data.** The history receipts span October 5–13, 2026 UTC, all after cutoff. Pre-cutoff provider availability cannot be established, and no complete feature vector is proven available then. That does not prove the records were unavailable; it means the necessary availability evidence is absent. No independently verified 2026 outcome evaluation has been conducted. Some valid 2026 features also exceed historical training ranges; no clipping or redesign was applied.

Sources: [feasibility audit](../cohort_2000_2026_feasibility/README.md), [prediction protocol](../cohort_2000_2026_feasibility/final_refit_prediction_protocol.json), [prediction summary](../cohort_2000_2026_predictions/prediction_summary.json), [coverage CSV](../cohort_2000_2026_predictions/coverage.csv), [missingness patterns](../cohort_2000_2026_predictions/missingness_patterns.csv), [Phase 8C interpretation](../cohort_2000_2026_visualizations/key_findings.md).

## H. Reproducibility, integrity and the limits of this synthesis

The source phases retain frozen dataset/prediction checksums, configurations, raw-index provenance, dependency versions and isolated reproduction receipts. This synthesis reads saved outputs only. Its [offline verifier](verify_report.py) checks report tables and quantitative statements against those artifacts, resolves relative links and image paths, checks relevant source manifests and compares preexisting bytes to the phase-start inventory. It does not execute model-regeneration commands or import model libraries. See [README.md](README.md) for the safe verification command and word-count convention.

Two existing discrepancies remain separate from preservation during this phase:

- The protected historical baseline agrees on 218/219 artifacts. The ordering-only mismatch is `data/intermediate/autumn_sale_evidence_records.csv`; its current bytes are preserved, not repaired.
- The Phase 8B `predictions_2026.csv` has a stale original manifest entry after row ordering and two game-name edits. AppID 1518000 currently says “CooKing: Around the C” instead of frozen “CooKing: Around the World”; AppID 2402900 says “Hollow Knight” instead of frozen “Hoboman”. Phase 8C restored only names/order **in memory** and obtained the original hash, proving all other fields, including scores, classes and membership, unchanged. These edited names do not establish the presence of different games. See the [provenance note](../cohort_2000_2026_visualizations/source_integrity_notes.json). Neither discrepancy is repaired here.

The investigation cannot establish representative Steam-population performance, unseen-game generalization, complete historical coverage, causal effects of observation density, or genuine prospective 2026 accuracy. Reported release dates, provider backfill and timestamp/shop ambiguities remain limitations. The post-modeling EDA is explicitly retrospective; it supplies no authorization to revise the frozen experiment.
