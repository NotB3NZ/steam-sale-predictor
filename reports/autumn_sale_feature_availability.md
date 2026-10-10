# Phase 6 — Historical Feature Availability

**Completed feature engineering; human review required before Phase 7. No model or predictive performance was produced.**

## Availability audit

A denotes static/historical information; B requires strict timestamp filtering; C is unavailable or potentially contaminated; D is target-derived or prohibited. Source-snapshot time is unknown. The Phase 2 report classifies release dates as historically derivable while explicitly retaining a source-accuracy assumption. Only date-derived metadata is admitted; other relatively stable metadata is excluded. Earlier Phase 1 suggestions that snapshot prices/DLC/tags are safe are superseded by this audit.

| Candidate | Meaning | Source | Availability / risk | Decision | Reason |
| --- | --- | --- | --- | --- | --- |
| AppID | Steam application identity | master / pilot metadata | A: identity | exclude from predictors | Row linkage only; titles/IDs do not establish historical characteristics. |
| Name | Human-readable product title | master / pilot metadata | A: identity | exclude from predictors | Row linkage only; titles/IDs do not establish historical characteristics. |
| release_date | Reported release calendar date | master / pilot metadata | A: historical date fact (conditional) | include derived date features | Phase 2 historically derivable classification; source accuracy/stability assumed, hours absent. Master/pilot date equality checked. |
| release_year | Derived reported release year | master / pilot metadata | A: historical date fact (conditional) | include derived date features | Phase 2 historically derivable classification; source accuracy/stability assumed, hours absent. Master/pilot date equality checked. |
| Estimated owners | Snapshot estimated ownership range | master / pilot metadata | C: undated snapshot | exclude | No timestamped historical snapshot; metadata may change after prediction. Pilot sampling diagnostics additionally reflect selection using snapshots. |
| Peak CCU | Snapshot lifetime peak concurrent players | master / pilot metadata | C: undated snapshot | exclude | No timestamped historical snapshot; metadata may change after prediction. Pilot sampling diagnostics additionally reflect selection using snapshots. |
| Required age | Snapshot age restriction | master / pilot metadata | C: undated snapshot | exclude | No timestamped historical snapshot; metadata may change after prediction. Pilot sampling diagnostics additionally reflect selection using snapshots. |
| Price | Contemporary store price; not historical base price | master / pilot metadata | C: undated snapshot | exclude | No timestamped historical snapshot; metadata may change after prediction. Pilot sampling diagnostics additionally reflect selection using snapshots. |
| Discount | Contemporary discount; not historical target | master / pilot metadata | C: undated snapshot | exclude | No timestamped historical snapshot; metadata may change after prediction. Pilot sampling diagnostics additionally reflect selection using snapshots. |
| DLC count | Snapshot DLC catalog size | master / pilot metadata | C: undated snapshot | exclude | No timestamped historical snapshot; metadata may change after prediction. Pilot sampling diagnostics additionally reflect selection using snapshots. |
| Supported languages | Snapshot supported languages | master / pilot metadata | C: undated snapshot | exclude | No timestamped historical snapshot; metadata may change after prediction. Pilot sampling diagnostics additionally reflect selection using snapshots. |
| Full audio languages | Snapshot audio languages | master / pilot metadata | C: undated snapshot | exclude | No timestamped historical snapshot; metadata may change after prediction. Pilot sampling diagnostics additionally reflect selection using snapshots. |
| Windows | Snapshot platform support | master / pilot metadata | C: undated snapshot | exclude | No timestamped historical snapshot; metadata may change after prediction. Pilot sampling diagnostics additionally reflect selection using snapshots. |
| Mac | Snapshot platform support | master / pilot metadata | C: undated snapshot | exclude | No timestamped historical snapshot; metadata may change after prediction. Pilot sampling diagnostics additionally reflect selection using snapshots. |
| Linux | Snapshot platform support | master / pilot metadata | C: undated snapshot | exclude | No timestamped historical snapshot; metadata may change after prediction. Pilot sampling diagnostics additionally reflect selection using snapshots. |
| Metacritic score | Snapshot critic score | master / pilot metadata | C: undated snapshot | exclude | No timestamped historical snapshot; metadata may change after prediction. Pilot sampling diagnostics additionally reflect selection using snapshots. |
| User score | Snapshot user score | master / pilot metadata | C: undated snapshot | exclude | No timestamped historical snapshot; metadata may change after prediction. Pilot sampling diagnostics additionally reflect selection using snapshots. |
| Positive | Accumulated positive reviews | master / pilot metadata | C: undated snapshot | exclude | No timestamped historical snapshot; metadata may change after prediction. Pilot sampling diagnostics additionally reflect selection using snapshots. |
| Negative | Accumulated negative reviews | master / pilot metadata | C: undated snapshot | exclude | No timestamped historical snapshot; metadata may change after prediction. Pilot sampling diagnostics additionally reflect selection using snapshots. |
| Achievements | Snapshot achievement count | master / pilot metadata | C: undated snapshot | exclude | No timestamped historical snapshot; metadata may change after prediction. Pilot sampling diagnostics additionally reflect selection using snapshots. |
| Recommendations | Accumulated recommendations | master / pilot metadata | C: undated snapshot | exclude | No timestamped historical snapshot; metadata may change after prediction. Pilot sampling diagnostics additionally reflect selection using snapshots. |
| Average playtime forever | Snapshot playtime statistic in minutes | master / pilot metadata | C: undated snapshot | exclude | No timestamped historical snapshot; metadata may change after prediction. Pilot sampling diagnostics additionally reflect selection using snapshots. |
| Average playtime two weeks | Snapshot playtime statistic in minutes | master / pilot metadata | C: undated snapshot | exclude | No timestamped historical snapshot; metadata may change after prediction. Pilot sampling diagnostics additionally reflect selection using snapshots. |
| Median playtime forever | Snapshot playtime statistic in minutes | master / pilot metadata | C: undated snapshot | exclude | No timestamped historical snapshot; metadata may change after prediction. Pilot sampling diagnostics additionally reflect selection using snapshots. |
| Median playtime two weeks | Snapshot playtime statistic in minutes | master / pilot metadata | C: undated snapshot | exclude | No timestamped historical snapshot; metadata may change after prediction. Pilot sampling diagnostics additionally reflect selection using snapshots. |
| Developers | Current developer attribution | master / pilot metadata | C: undated snapshot | exclude | No timestamped historical snapshot; metadata may change after prediction. Pilot sampling diagnostics additionally reflect selection using snapshots. |
| Publishers | Current publisher attribution | master / pilot metadata | C: undated snapshot | exclude | No timestamped historical snapshot; metadata may change after prediction. Pilot sampling diagnostics additionally reflect selection using snapshots. |
| Categories | Current store categories | master / pilot metadata | C: undated snapshot | exclude | No timestamped historical snapshot; metadata may change after prediction. Pilot sampling diagnostics additionally reflect selection using snapshots. |
| Genres | Current genre attribution | master / pilot metadata | C: undated snapshot | exclude | No timestamped historical snapshot; metadata may change after prediction. Pilot sampling diagnostics additionally reflect selection using snapshots. |
| Tags | Current user/store tags | master / pilot metadata | C: undated snapshot | exclude | No timestamped historical snapshot; metadata may change after prediction. Pilot sampling diagnostics additionally reflect selection using snapshots. |
| pilot_release_era | Sampling diagnostic; not a predictor | master / pilot metadata | C: undated snapshot | exclude | No timestamped historical snapshot; metadata may change after prediction. Pilot sampling diagnostics additionally reflect selection using snapshots. |
| pilot_price_band | Sampling diagnostic; not a predictor | master / pilot metadata | C: undated snapshot | exclude | No timestamped historical snapshot; metadata may change after prediction. Pilot sampling diagnostics additionally reflect selection using snapshots. |
| pilot_owner_group | Sampling diagnostic; not a predictor | master / pilot metadata | C: undated snapshot | exclude | No timestamped historical snapshot; metadata may change after prediction. Pilot sampling diagnostics additionally reflect selection using snapshots. |
| pilot_activity_group | Sampling diagnostic; not a predictor | master / pilot metadata | C: undated snapshot | exclude | No timestamped historical snapshot; metadata may change after prediction. Pilot sampling diagnostics additionally reflect selection using snapshots. |
| pilot_publisher_portfolio_group | Sampling diagnostic; not a predictor | master / pilot metadata | C: undated snapshot | exclude | No timestamped historical snapshot; metadata may change after prediction. Pilot sampling diagnostics additionally reflect selection using snapshots. |
| pilot_selection_reason | Sampling diagnostic; not a predictor | master / pilot metadata | C: undated snapshot | exclude | No timestamped historical snapshot; metadata may change after prediction. Pilot sampling diagnostics additionally reflect selection using snapshots. |
| timestamp | Observed historical time, storefront or price/deal field | cached ITAD history | B: timestamp filtering | conditional | UTC timestamp strictly before cutoff; shop 61; shared parser price/regular/cut/currency validity. Null/ambiguous deals excluded from price statistics and retained in validation. |
| shop.id | Observed historical time, storefront or price/deal field | cached ITAD history | B: timestamp filtering | conditional | UTC timestamp strictly before cutoff; shop 61; shared parser price/regular/cut/currency validity. Null/ambiguous deals excluded from price statistics and retained in validation. |
| deal.price.amount / currency | Observed historical time, storefront or price/deal field | cached ITAD history | B: timestamp filtering | conditional | UTC timestamp strictly before cutoff; shop 61; shared parser price/regular/cut/currency validity. Null/ambiguous deals excluded from price statistics and retained in validation. |
| deal.regular.amount / currency | Observed historical time, storefront or price/deal field | cached ITAD history | B: timestamp filtering | conditional | UTC timestamp strictly before cutoff; shop 61; shared parser price/regular/cut/currency validity. Null/ambiguous deals excluded from price statistics and retained in validation. |
| deal.cut | Observed historical time, storefront or price/deal field | cached ITAD history | B: timestamp filtering | conditional | UTC timestamp strictly before cutoff; shop 61; shared parser price/regular/cut/currency validity. Null/ambiguous deals excluded from price statistics and retained in validation. |
| deal=null / ambiguous | Observed historical time, storefront or price/deal field | cached ITAD history | B: timestamp filtering | conditional | UTC timestamp strictly before cutoff; shop 61; shared parser price/regular/cut/currency validity. Null/ambiguous deals excluded from price statistics and retained in validation. |
| discount_observed | Outcome or retrospective diagnostic | labels / previous evidence artifacts | D: prohibited predictor | exclude | Outcome/future/collection-derived information; labels supply pair identities and a separate target join only. |
| evidence_category | Outcome or retrospective diagnostic | labels / previous evidence artifacts | D: prohibited predictor | exclude | Outcome/future/collection-derived information; labels supply pair identities and a separate target join only. |
| pu_status | Outcome or retrospective diagnostic | labels / previous evidence artifacts | D: prohibited predictor | exclude | Outcome/future/collection-derived information; labels supply pair identities and a separate target join only. |
| in-window counts / supporting indices | Outcome or retrospective diagnostic | labels / previous evidence artifacts | D: prohibited predictor | exclude | Outcome/future/collection-derived information; labels supply pair identities and a separate target join only. |
| post-sale records / coverage diagnostics | Outcome or retrospective diagnostic | labels / previous evidence artifacts | D: prohibited predictor | exclude | Outcome/future/collection-derived information; labels supply pair identities and a separate target join only. |
| future verification / full-history empty flags | Outcome or retrospective diagnostic | labels / previous evidence artifacts | D: prohibited predictor | exclude | Outcome/future/collection-derived information; labels supply pair identities and a separate target join only. |
| label limitation / review flags | Outcome or retrospective diagnostic | labels / previous evidence artifacts | D: prohibited predictor | exclude | Outcome/future/collection-derived information; labels supply pair identities and a separate target join only. |
| 2026 outcomes | Outcome or retrospective diagnostic | labels / previous evidence artifacts | D: prohibited predictor | exclude | Outcome/future/collection-derived information; labels supply pair identities and a separate target join only. |
| current concurrent player count | Current activity; distinct from lifetime Peak CCU | not present as a separate source field | C: unavailable historical snapshot | exclude | No historical snapshot is available; never substitute current or peak activity. |

## Prediction cutoffs

| Year | Strict upper bound UTC |
| --- | --- |
| 2023 | 2023-11-21T18:00:00Z |
| 2024 | 2024-11-27T18:00:00Z |
| 2025 | 2025-09-29T17:00:00Z |

Only `observation_timestamp < prediction_cutoff_utc` enters any pricing calculation. Exact cutoff, current-sale, post-sale and future-year observations are excluded. Prior years' sale observations are legitimate past observations. No 2026 outcome information is used.

## Included definitions and allowlist

| Feature | Definition |
| --- | --- |
| game_age_days | Sale-start Pacific calendar date minus source-reported release date; date-resolution days. |
| release_year | Year of the normalized source-reported release date. |
| release_month | Month (1–12) of the normalized source-reported release date. |
| release_quarter | Quarter (1–4) of the normalized source-reported release date. |
| prior_price_record_count | Count of independently parser-valid pre-cutoff Steam price observations; duplicates retained. |
| prior_discount_count | Count of qualifying discounted observations among prior_price_record_count; not campaigns. |
| prior_discount_rate | prior_discount_count / prior_price_record_count; observation-level ratio, not discounted-day share. |
| days_since_last_price_record | Elapsed UTC days since latest valid pre-cutoff price observation. |
| days_since_last_discount | Elapsed UTC days since latest qualifying pre-cutoff discount observation. |
| max_prior_discount_pct | Maximum explicit cut percentage among qualifying pre-cutoff discounts. |
| mean_prior_discount_pct | Arithmetic mean explicit cut percentage among qualifying pre-cutoff discounts. |
| last_observed_price | Amount at latest valid pre-cutoff observation, only with exclusively USD prior valid prices and no latest-timestamp conflict. |
| last_observed_discount_pct | Explicit cut at latest valid pre-cutoff observation; null for conflicting latest timestamp. |
| has_prior_price_history | 1 if at least one valid pre-cutoff price observation exists, otherwise 0. |
| has_prior_discount_observation | 1 if at least one qualifying pre-cutoff discount observation exists, otherwise 0. |

The explicit 15-feature baseline allowlist is stored in [the manifest](autumn_sale_feature_manifest.json). AppID, sale year, cutoff and `audit_release_hour_uncertain` are excluded. The audit flag preserves same-day uncertainty without copying target-derived review/eligibility flags. All 300 rows remain. nekowater (2650840), 2023, has date-resolution age zero and unknown release hour; no midnight release time is invented.

Release date is used as a reported historical fact, conditional on the existing source being accurate and stable. Age subtracts dates in the event calendar's Pacific timezone and is not an exact elapsed release-time duration. Release-date corrections, early-access/full-release interpretation and continuous purchase availability remain unverified.

## Observation validity, currency and conflicts

A valid price observation has the unchanged parser's `discount` or `full_price` kind. This requires finite nonnegative price/regular amounts, valid matching three-letter currencies, finite cut in [0,100], and consistent price/regular/cut direction. Discount means cut > 0 and price < regular. Ambiguous/null deals are temporal evidence but do not enter the price denominator. Their pre-cutoff indices/conflict diagnostics remain in the validation receipt.

All current cached price/regular currencies are USD. `last_observed_price` is emitted only when all valid prior currencies are USD and latest-timestamp values do not conflict. Mixed/non-USD monetary values are withheld, with reasons in validation; no conversion is performed. Cut is dimensionless and validated within each record's matching currency pair, so cut statistics may combine valid percentages across currencies without comparing money amounts.

Duplicates and independently valid conflicting records are counted separately as observations. They are not unique discount campaigns. Max/mean cut describe the returned observation multiset, not verified states or campaign prevalence. A conflict at the latest valid timestamp makes last price/cut null; all tied raw indices remain inspectable. A newer ambiguous temporal observation does not erase an older valid observation: recency refers explicitly to the latest valid price, not a carried-forward price at cutoff.

## Missingness and distribution audit

No valid prior prices gives zero counts/flags, with ratio, recencies and values missing. Valid prices without a qualifying discount give ratio zero, missing discount recency/max/mean, and discount flag zero. Missing recency is never zero-filled. CSV nulls are blank; JSON uses null.

| Feature | Missing | Min | Median | Max |
| --- | --- | --- | --- | --- |
| game_age_days | 0 | 0 | 1887.5 | 10318 |
| release_year | 0 | 1997 | 2019.5 | 2023 |
| release_month | 0 | 1 | 6.5 | 12 |
| release_quarter | 0 | 1 | 2.5 | 4 |
| prior_price_record_count | 0 | 0 | 30.0 | 111 |
| prior_discount_count | 0 | 0 | 15.0 | 55 |
| prior_discount_rate | 10 | 0.0 | 0.5 | 1.0 |
| days_since_last_price_record | 10 | 0.09128472222222223 | 64.03055555555557 | 1732.7083333333333 |
| days_since_last_discount | 46 | 0.9871064814814815 | 55.257471064814816 | 1732.7083333333333 |
| max_prior_discount_pct | 46 | 15 | 75.0 | 100 |
| mean_prior_discount_pct | 46 | 12.142857142857142 | 53.625 | 90.91666666666667 |
| last_observed_price | 10 | 0 | 9.99 | 99.99 |
| last_observed_discount_pct | 10 | 0 | 0.0 | 90 |
| has_prior_price_history | 0 | 0 | 1.0 | 1 |
| has_prior_discount_observation | 0 | 0 | 1.0 | 1 |

Rows: **300**; year counts: **100 / 100 / 100**. Currency conflicts: **0**; uncertain release-hour pairs: **1**. Constant baseline features: **none**. Unusual values are retained; no target-based feature selection is performed.

## Historical availability limitations

Filtering retrospective observation timestamps prevents direct temporal leakage but does not prove records were available from ITAD at that historical instant. Backfill and initial requested-since records remain unresolved. Observation counts, recency and flags describe the returned pre-cutoff evidence, not complete history, uninterrupted price states or true discount frequency. They may predict recording coverage as well as discount behavior. Sampling used undated snapshot information, so population selection bias persists even though those fields are excluded from predictors.

**Observed alignment caveats:** 18 pairs across 6 games contain valid pre-cutoff observations whose UTC calendar date precedes the source-reported release date. The six games are Evil Genius 2 (700600), CryoFall (829590), New World: Aeternum (1063730), The Great Ace Attorney Chronicles (1158850), Have a Nice Death (1740720), and Workplace Fantasy (2544720). Earlier access, preorders, release-date interpretation, backfill or source errors are possible explanations, not established facts. These records satisfy the existing parser and are retained with explicit diagnostics; neither source is silently corrected. Separately, 192 pairs contain observations at the exact 2021-01-01 request boundary (65 records across 64 cached games, repeated across sale-year feature sets). An initialized timestamp is possible; true contemporaneous availability remains unverified.

Extremes in the distribution table are retained, including very old price/discount gaps, zero observed prices and 100% cuts. These are returned-record summaries, not imputed daily states. No unusual value is removed.

The operational target remains recorded discount occurrence, not independently verified participation. Pre-cutoff histories and static dates calculate features independently of the target; targets are joined only afterward. [Features](../data/intermediate/autumn_sale_features.csv) omit targets, categories and PU status. [Modeling table](../data/intermediate/autumn_sale_modeling_table.csv) adds only `discount_observed`. Future modeling must use the manifest allowlist, handle missing values with training-only preprocessing, train on 2023–2024 and reserve 2025 for temporal validation; repeated games across years and uncertain eligibility need transparent treatment.

## Reproduction and stop gate

```bash
python3 -B src/07_build_autumn_features.py --verify
```

Standard library only, local cached inputs, no credentials. Socket/DNS access is blocked. Verification runs the full offline test suite, adversarial future/target invariance tests, protected-input hashes and repeated byte-identical outputs. [Validation receipt](autumn_sale_feature_validation.json) records actual execution results and pre-cutoff raw-index provenance. Earlier artifacts are never regenerated. Stop before Phase 7; no imputation, scaling, encoding, training or evaluation is implemented.
