# Figure captions and interpretation

**Retrospective descriptive EDA conducted after model development.**

## 01 — Games by release year

**Question:** When were the games in this cohort released?

**Data source:** data/cohorts/cohort_2000.csv: release_year, checked against release_date.

**Unit:** One game; all 2,000 games.

**Takeaway:** 94.2% were released in 2015 or later.

**Limitation:** Source-reported release dates may be revised. This selected cohort does not represent every Steam game.

## 02 — Prices recorded before the 2025 sale

**Question:** How much did games cost at their last usable recorded observation before the 2025 sale?

**Data source:** Frozen modeling.csv: last_observed_price for sale_year=2025; raw-index provenance and original USD caches cross-checked.

**Unit:** One last valid recorded USD price per game; 1,918 games. Event timestamp strictly before 2025-09-29T17:00:00Z.

**Takeaway:** 75.9% of recorded prices were below $10.

**Limitation:** 82 missing prices omitted, not zero-filled. Both observed zero prices and the $199.99 maximum are retained. Records can be stale; this is neither current price nor price verified at the cutoff. No currency conversion or inflation adjustment.

## 03 — How much price history is available?

**Question:** How many valid historical price observations were available before the 2025 sale?

**Data source:** Frozen modeling.csv: prior_price_record_count for sale_year=2025; saved raw indices checked against each historical cutoff.

**Unit:** One count per game; all 2,000 games, including zero. Cutoff 2025-09-29T17:00:00Z; ten-observation bins.

**Takeaway:** Half the games have 32 or fewer recorded price observations.

**Limitation:** 82 games have zero observations. Counts retain duplicates and are not distinct sales, discounted days, or proof of complete history. Provider availability at the historical cutoff is unproven.

## 04 — Autumn Sale discount evidence by year

**Question:** How many games had discount evidence in each Autumn Sale?

**Data source:** Frozen modeling.csv: discount_observed and evidence_category; reconciled to Phase 6C label_distribution.json.

**Unit:** One game-year label; 2,000 games per year, 6,000 rows total.

**Takeaway:** About half the games have discount evidence in each year.

**Limitation:** No discount observed means no evidence in the available records, not verified nonparticipation. 2023–2024 are development years; 2025 is the held-out evaluation year. This chart is descriptive, not a new evaluation.

## 05 — How often was a discount observed?

**Question:** In how many of the three Autumn Sales did each game have positive evidence?

**Data source:** Frozen modeling.csv: sum of discount_observed across 2023, 2024 and 2025 for each AppID.

**Unit:** One game counted exactly once in 0, 1, 2 or 3 positive-label years.

**Takeaway:** 713 games have discount evidence in all three years.

**Limitation:** Zero positive years does not prove a game never participated. Repeated observations of the same games are dependent; these are descriptive counts.

## 06 — Sizes of recorded Autumn Sale discounts

**Question:** How large were the directly recorded discounts during the three Autumn Sales?

**Data source:** Phase 6A evidence_records.csv: explicit cut, shop 61, USD price and regular price; verified against original cached JSON. timestamp_shop_conflicts.csv flags exclusions.

**Unit:** One unambiguous discounted raw record inside a 2023–2025 Autumn Sale window; 3,035 records from 1,259 games.

**Takeaway:** The middle recorded discount was 55%.

**Limitation:** 2 same-time conflicting records and 24 full-price records are excluded only from this descriptive chart. Explicit cut is retained, not recomputed from rounded money fields. Games with more records receive more weight; records are not independent sales or distinct discounted days.

## 07 — More history goes with more discount evidence

**Question:** How does recorded sale evidence vary with the amount of prior price history?

**Data source:** Frozen modeling.csv: each game-year prior_price_record_count and unchanged discount_observed label. Saved pre-cutoff indices are independently checked.

**Unit:** Game-year rows grouped separately for each year into 0, 1–9, 10–29 and 30+ prior valid observations. Each panel sums to 2,000 games.

**Takeaway:** The 30+ observation group has the highest discount-evidence rate in every year.

**Limitation:** Each year uses its own strictly pre-sale cutoff. Sample sizes differ. This is an association between coverage and available evidence, not a causal claim or verified participation rate. Development (2023–2024) and held-out (2025) panels stay separate.

## 08 — Which features have missing values?

**Question:** Which of the 15 approved predictors contain blank values?

**Data source:** Frozen modeling.csv: is-missing counts for the 15 approved predictors, reconciled to frozen missingness.csv and feature_manifest.json.

**Unit:** Missing cells within 6,000 historical game-year rows (2023–2025); one bar per approved predictor.

**Takeaway:** Seven predictors have missing values; eight are complete.

**Limitation:** A game can have multiple missing predictors in multiple years. Counts are missing cells per feature, not unique games. Nulls mean unavailable information, not zero or verified nonparticipation. No imputation or feature selection is performed.
