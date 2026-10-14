# Phase 8C key findings

**Retrospective event-time-filtered predictions using post-cutoff-collected historical data.**

- Frozen XGBoost predictions cover exactly 2,000 games: 1,026 positives (51.3%) and 974 operational zeros (48.7%), at the unchanged 0.50 threshold.
- Mean probability is 0.499649; median is 0.709637; range is 0.008056–0.959107. The interquartile range is 0.031252–0.937633. There are 754 scores below 0.10 and 656 at or above 0.90. These distributions do not establish calibration.
- Historical observed operational positive rates are 48.95% in 2023, 53.40% in 2024 and 49.15% in 2025. The 51.30% 2026 figure is a predicted class rate. Historical observed labels and 2026 predictions describe different quantities.
- Observation-count/score Spearman is 0.8925. The 0, 1–9, 10–29 and 30+ groups have 81, 505, 295 and 1,119 games; predicted positive rates are 0.00%, 1.19%, 25.08% and 84.54%. The 30+ group supplies 946/1,026 predicted positives (92.2%). This is a descriptive association, not a causal attribution or an actual participation estimate.
- All 336 games with missing predictors receive predicted operational zero. Their mean score is 0.013826, median 0.009634, and range 0.008056–0.262135. Their observation counts range from 0 to 4, with median 1.
- Missingness has two exact patterns: 255 games have three discount-derived nulls and 1–4 price observations (within the 1–9 group); 81 games have seven nulls and zero price observations. The missing-vector score 95th percentile is 0.021260; even the maximum 0.262135 is below 0.50. All missing-vector games have zero qualifying prior discount observations. This describes available evidence; missing data does not verify absence of real discounts.
- All 1,026 predicted positives have complete vectors. Among the 974 predicted zeros, 638 have complete vectors (65.5%), 255 have three nulls and 81 have seven nulls. A complete vector therefore does not imply a predicted positive. No new imputation, missingness model, threshold change or model inference is used here.
- Highest and lowest score rankings have ties; the frozen ascending-AppID tie break is retained. Displayed precision is not a claim of outcome certainty.

Recommended core presentation: figures 01, 02, 05, 06 and 08. Figures 03–04 are ranking supplements; 07 supplies subgroup distribution detail. Keep coverage and missingness beside any aggregate prediction result.

## Limits on interpretation

The cutoff is **2026-10-01T17:00:00Z**. All history receipts were collected after cutoff (October 5–13); event-time filtering cannot establish provider availability before cutoff. No vector is independently proven available at that time. These are retrospective scores, not validated prospective forecasts.

Historical A→1 and B/D→0 labels describe observed ITAD Autumn Sale discount evidence. Operational zeros do not prove nonparticipation. Missing histories or predictors do not establish verified nonparticipation. Observation counts retain duplicates and measure returned observation density, not distinct sales, campaigns, or discounted days.

**No independent 2026 outcome evaluation has been conducted.** No verified 2026 sale outcome is inferred; no accuracy, confusion, ROC, calibration, or participation-rate evaluation is computed. The 2026 probability distribution is not evidence that probabilities are calibrated for actual sale outcomes.

Repeated games across historical years, retrospective cohort selection, provider backfill, source release-date uncertainty, historical timestamp/shop ambiguities, and feature values outside historical training ranges remain limitations. The strong coverage/score association does not disentangle provider recording density from pricing behavior. Historical performance belongs to the earlier evaluated fit, not an independently evaluated 2026 refit.

The figures and summaries are ready for a descriptive final research synthesis with these limitations and the source serialization caveat prominent. They do not establish verified 2026 participation or independently evaluated predictive performance.

## Preexisting Phase 8B CSV provenance caveat

The prediction CSV differs from its original manifest hash. An in-memory reconstruction using the frozen availability-table row order and original game names exactly reproduces the original SHA-256. All probabilities, classes, cohort IDs and other fields are unchanged. Two names differ: AppID 1518000 is currently “CooKing: Around the C” versus frozen “CooKing: Around the World”; AppID 2402900 is currently “Hollow Knight” versus frozen “Hoboman”. This does not add either named title to the cohort or validate its identity. The source CSV, manifests and journal are preserved without repair. Figures and tables read the current source; neither renamed row appears in the top/bottom ten. See `source_integrity_notes.json` for exact hashes. This discrepancy is separate from the known 218/219 historical protected-baseline agreement.
