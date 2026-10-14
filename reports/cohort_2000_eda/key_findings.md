# Key EDA findings

**Retrospective descriptive EDA conducted after model development.** Findings are descriptive and must not alter frozen model development, labels, cohort membership, thresholds or predictions.

- The 2,000 cohort games have source-reported release years 1997–2023; 1,883 (94.2%) were released in 2015 or later. The largest release-year group is 2022 (327 games).
- Among 1,918 games with a usable last recorded pre-2025-sale USD price, 1,456 (75.9%) have prices below $10. Median is $5.54; range is $0.00–$199.99. All values, including two observed zero prices and the maximum, remain in the histogram; 82 missing prices are omitted and separately counted.
- The median historical observation count before the 2025 cutoff is 32, with range 0–256. All 2,000 games contribute once, including 82 with zero observations. Counts measure returned records, not distinct sales or discounted days.
- Discount-observed labels number 979 (48.95%) in 2023, 1,068 (53.40%) in 2024 and 983 (49.15%) in 2025. Corresponding “No discount observed” counts are 1,021, 932 and 1,017. These are frozen operational labels, not verified sale participation outcomes.
- Across all three years, 741 games have positive evidence in zero years, 201 in one, 345 in two, and 713 in three. Each game is counted exactly once. Zero evidence years does not prove no actual participation.
- The discount histogram uses 3,035 valid Steam USD discount records from 1,259 games inside the 2023–2025 Autumn Sale windows. Median explicit discount is 55%, with range 10–95%. 2,260 (74.5%) show discounts of at least 50%. Two conflicting same-time records and 24 full-price observations are excluded from this chart only; no historical labels or source records are changed.
- More historical observations go with more recorded sale evidence in every year. In the held-out 2025 year, observed positive-label rates are 0%, 3.53%, 35.12% and 81.03% for 0, 1–9, 10–29 and 30+ prior observations. This is an association, not proof that coverage causes discounts or a measure of true participation. The year-specific sample sizes and both label rates are in `coverage.csv`.
- Seven of 15 approved predictors contain missing cells. Days since last discount, largest earlier discount and average earlier discount each have 1,134 missing values (18.9% of 6,000 rows). Four price-history predictors each have 253 (4.22%). Eight predictors have none. Missingness describes unavailable historical evidence, not verified nonparticipation.

## Data quality and interpretation

Recorded prices are USD amounts for Steam shop 61 / US, one latest usable price per game strictly before the 2025 cutoff. They can be stale; no price is claimed to be current or verified at the cutoff. No currency conversion, clipping, imputation, inflation adjustment or forward filling is used.

The discount chart represents discrete observed sale-window records, not game averages, purchases, unique campaigns or daily price states. Games with more observations carry more weight. Explicit percentage fields follow the existing parser; rounded money fields are not used to invent new percentages. One conflicting timestamp group contributes two excluded observations. Original evidence and labels remain frozen.

Historical 2023–2024 development and held-out 2025 evaluation data are shown separately for coverage and annual labels. This EDA was conducted after model development, including inspection of the held-out year; it must not be used for feature selection, model tuning, threshold changes, label revisions or re-evaluation claims. No model is loaded or queried here.

All historical cutoffs exclude at/after-cutoff events. This demonstrates event-time filtering, not provider availability at those historical times. ITAD snapshots were collected retrospectively. Source-release-date uncertainty, incomplete/uneven history, provider backfill, timestamp conflicts and retrospective cohort selection remain limitations. Repeated game-year rows are dependent; 6,000 rows are not 6,000 independent games. The cohort is not a representative estimate of the full Steam catalog. “No discount observed” is not verified nonparticipation.

## Supported charts and presentation

All eight requested charts are supported; no alternate variable or infeasible-chart replacement is needed. The historical price measure is explicitly the last valid recorded pre-2025-sale USD price, and the discount measure is an explicit percentage inside historical sale windows. Their units differ and must stay labeled.

Recommended core presentation: 01 (release years), 04 (annual evidence), 05 (three-year evidence) and 07 (coverage association). Include 02 and 06 when discussing prices/discount sizes; retain 03 and 08 for a data-quality explanation. Read the limitation alongside every takeaway.

## Preexisting integrity caveats

The protected historical baseline remains 218/219: `data/intermediate/autumn_sale_evidence_records.csv` has the previously documented ordering-only mismatch. It is preserved without repair and is not an EDA chart source.

The Phase 8B prediction CSV also has the already documented row-order/two-name discrepancy (AppIDs 1518000 and 2402900). Its Phase 8C integrity note is retained; current bytes are checked against that note. Predictions and prediction names are not EDA chart inputs. No source file, manifest or journal is repaired.

The charts and documented sources are ready for Phase 9A descriptive research synthesis with these limits visible. No frozen modeling or prediction result is revised by this EDA.
