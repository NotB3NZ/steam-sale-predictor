# Autumn Sale Historical Price-State and Coverage Investigation — Phase 5B.1

## A. Research objective

> Given information available about a Steam game before a specific Steam Autumn Sale begins, what is the probability that the game will be discounted during that sale?

This investigation measures observed surrounding prices and missing evidence before designing final labels. **OBSERVED FACTS** are timestamps and returned fields. **DIAGNOSTIC INTERPRETATIONS** flag uncertainty. **HYPOTHETICAL ASSUMPTIONS** appear only in sensitivity scenarios. No persistent price states, daily histories, final 1/0/UNKNOWN labels, modeling features or models are produced.

## B. Input datasets and provenance

Inputs are the frozen 100-game pilot, Phase 4 collection manifest and cached `data/raw/itad/<AppID>.json` wrappers, plus the unchanged Phase 5A.1 audit/record CSVs and verified centralized event calendar. The Phase 5A calendar-date baseline is verified against its preserved manifest before execution. The existing Phase 5A.1 parser is reused without changing its price, cut, currency, null-deal or provenance rules.

The cache contains **5568 records**. To exclude 2026 from this investigation, **852 observations at or after 2026-01-01T00:00:00Z are excluded**, leaving **4716 timestamp-usable Steam records**. Exclusion is by timestamp, without analyzing their prices. Thus post-sale context can differ from the previous audit, which searched the whole cache. A missing post-sale observation means none was returned before this cutoff; it does not establish absence after it. The cutoff is an experimental scope restriction, not a coverage threshold.

A valid temporal observation has a parsed timezone-aware timestamp and integer Steam shop ID 61. Ambiguous/null deals remain temporal observations; `price_usable_count` separately counts discount/full-price records. Cached HTTP response text, wrapper configuration and manifest counts are verified. Invalid caches/parsing failures stop this investigation rather than becoming D.

## C. Event windows and eligibility

The unchanged Phase 5A.1 calendar uses **start <= timestamp < end**. A record exactly at end is post-sale. No new event-time verification or calendar changes are made here.

| Year | UTC start | UTC end | Pacific start | Pacific end | Official source |
| --- | --- | --- | --- | --- | --- |
| 2023 | 2023-11-21T18:00:00Z | 2023-11-28T18:00:00Z | 2023-11-21T10:00:00-08:00 | 2023-11-28T10:00:00-08:00 | [Valve announcement](https://steamcommunity.com/games/593110/announcements/detail/3823053915973575702) |
| 2024 | 2024-11-27T18:00:00Z | 2024-12-04T18:00:00Z | 2024-11-27T10:00:00-08:00 | 2024-12-04T10:00:00-08:00 | [Valve announcement](https://steamcommunity.com/games/593110/announcements/detail/4464851103138185583) |
| 2025 | 2025-09-29T17:00:00Z | 2025-10-06T17:00:00Z | 2025-09-29T10:00:00-07:00 | 2025-10-06T10:00:00-07:00 | [Valve announcement](https://steamcommunity.com/games/593110/announcements/detail/507340830949770005) |

**300 unique pairs** (100 games × 2023/2024/2025); all 300 meet the existing date-level eligibility rule; zero ineligible pairs. nekowater’s 2023 same-day release has unresolved hour precision. Only pre-2026 historical observations are examined. Intended experiments remain 2023–2024 training, 2025 validation, 2026 retrospective evaluation; no 2026 outcomes enter development.

## D. Coverage summary for all 300 pairs

| Year | A | B | C | D | In-window records | Pre exists | Post exists | Both exist |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2023 | 55 | 2 | 0 | 43 | 57 | 96 | 76 | 75 |
| 2024 | 60 | 0 | 0 | 40 | 60 | 97 | 74 | 74 |
| 2025 | 60 | 1 | 0 | 39 | 61 | 97 | 70 | 70 |

Categories remain A=direct discount; B=only full-price in-window observations; C=ambiguous in-window evidence without a discount; D=no in-window observations. **175 A, 3 B, 0 C, 122 D; 178 in-window records**, each observed pair has one record. These are unchanged descriptive categories, not target labels. No null/ambiguous or mixed in-window records occur.

Empty raw histories: 3 games; 9 pairs have no analyzed observations. Missing pre: 10 pairs; missing post before cutoff: 80 pairs.

| Overlapping diagnostic pattern | Pairs |
| --- | --- |
| pattern_direct_in_window_discount | 175 |
| pattern_pre_discount_no_direct_discount | 22 |
| pattern_pre_full_price_no_direct_discount | 93 |
| pattern_no_unambiguous_latest_pre_state | 10 |
| pattern_surrounding_evidence_requires_review | 139 |

Patterns overlap. The review cue covers missing/ambiguous surrounding observations, differing observed surrounding values, history conflicts or unknown release hour. A value change is not a proven contradiction and missing evidence is not a discount-state finding.

## E. Pre-sale observed-state distributions

| Year | Pairs | Full price | Discounted | Ambiguous | Missing |
| --- | --- | --- | --- | --- | --- |
| all | 300 | 265 | 25 | 0 | 10 |
| 2023 | 100 | 85 | 11 | 0 | 4 |
| 2024 | 100 | 91 | 6 | 0 | 3 |
| 2025 | 100 | 89 | 8 | 0 | 3 |

| Category | Pairs | Full price | Discounted | Ambiguous | Missing |
| --- | --- | --- | --- | --- | --- |
| A | 175 | 172 | 3 | 0 | 0 |
| B | 3 | 0 | 2 | 0 | 1 |
| C | 0 | 0 | 0 | 0 | 0 |
| D | 122 | 93 | 20 | 0 | 9 |

“Latest observed state” refers only to the last pre-sale timestamp, not the state at sale start. The pipeline never skips a latest null/ambiguous record to select an older known price. Divergent nearest same-time records make the aggregated state ambiguous even if both have cut=0. The lowest raw index supplies explicitly representative fields; all ties remain serialized. A conflict is more than one signature at the same timestamp: price amount/amountInt/currency, regular amount/amountInt/currency, cut and deal status define that signature. Different raw metadata outside these fields alone does not constitute a price-state conflict.

## F. Post-sale observed-state distributions

| Year | Pairs | Full price | Discounted | Ambiguous | Missing |
| --- | --- | --- | --- | --- | --- |
| all | 300 | 193 | 27 | 0 | 80 |
| 2023 | 100 | 65 | 11 | 0 | 24 |
| 2024 | 100 | 65 | 9 | 0 | 26 |
| 2025 | 100 | 63 | 7 | 0 | 30 |

| Category | Pairs | Full price | Discounted | Ambiguous | Missing |
| --- | --- | --- | --- | --- | --- |
| A | 175 | 174 | 1 | 0 | 0 |
| B | 3 | 1 | 1 | 0 | 1 |
| C | 0 | 0 | 0 | 0 | 0 |
| D | 122 | 18 | 25 | 0 | 79 |

Earliest post evidence is at or after exact end and strictly before 2026. It describes that timestamp only. No post-sale observation retroactively establishes an in-sale state.

## G. Observation-gap statistics

Gaps use exact elapsed seconds / 86,400, not rounded calendar days. Missing gaps remain empty CSV cells and count as missing, never zero. Surrounding interval = post timestamp − pre timestamp, when both exist; for A/B this interval may contain observations and must not be mistaken for an observation-free gap. For D it spans the whole event without a returned observation. Percentiles use linear interpolation at (n−1) × percentile. All statistics below are days.

| Group | Metric | N | Missing | Min | P10 | P25 | Median | Mean | P75 | P90 | P95 | Max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| sale_year=2023 | pre_gap_days | 96 | 4 | 0.091285 | 6.507622 | 19.77831 | 85.025666 | 270.561439 | 242.896484 | 1054.75 | 1054.75 | 1054.75 |
| sale_year=2023 | post_gap_days | 76 | 24 | 0.005162 | 0.010301 | 0.027216 | 0.103582 | 27.397092 | 0.164818 | 23.189456 | 216.813261 | 469.229502 |
| sale_year=2023 | surrounding_interval_days | 75 | 25 | 7.248368 | 13.018088 | 26.052072 | 49.200162 | 134.770373 | 138.040162 | 203.471463 | 669.275769 | 1243.698218 |
| sale_year=2024 | pre_gap_days | 97 | 3 | 0.987106 | 8.98385 | 22.028681 | 64.028634 | 337.097452 | 351.969271 | 1383.784574 | 1426.75 | 1426.75 |
| sale_year=2024 | post_gap_days | 74 | 26 | 0.012407 | 0.012557 | 0.020576 | 0.033704 | 11.065231 | 0.061137 | 15.215377 | 97.850197 | 173.055949 |
| sale_year=2024 | surrounding_interval_days | 74 | 26 | 7.999514 | 14.015183 | 25.463151 | 41.048709 | 100.128636 | 146.040506 | 200.942663 | 348.847788 | 796.124907 |
| sale_year=2025 | pre_gap_days | 97 | 3 | 0.989016 | 6.988565 | 16.989282 | 53.289398 | 383.205852 | 201.728831 | 1689.742907 | 1732.708333 | 1732.708333 |
| sale_year=2025 | post_gap_days | 70 | 30 | 0.012546 | 0.012854 | 0.016464 | 0.031105 | 3.875042 | 0.057891 | 7.511794 | 21.413163 | 76.095938 |
| sale_year=2025 | surrounding_interval_days | 70 | 30 | 8.001597 | 14.005043 | 21.532584 | 35.019473 | 53.01128 | 87.998588 | 88.00242 | 88.029361 | 353.023345 |
| evidence_category=A | pre_gap_days | 175 | 0 | 0.091285 | 6.411204 | 17.488339 | 27.026424 | 54.674558 | 80.957506 | 134.032815 | 139.028081 | 614.862384 |
| evidence_category=A | post_gap_days | 175 | 0 | 0.005162 | 0.0126 | 0.016574 | 0.03338 | 0.412635 | 0.062274 | 0.122655 | 0.185781 | 14.015822 |
| evidence_category=A | surrounding_interval_days | 175 | 0 | 7.248368 | 13.424303 | 25.022714 | 35.029549 | 62.087193 | 88.00022 | 141.162375 | 146.04103 | 621.920741 |
| evidence_category=B | pre_gap_days | 2 | 1 | 2.997419 | 3.996551 | 5.495249 | 7.993079 | 7.993079 | 10.490909 | 11.989606 | 12.489172 | 12.988738 |
| evidence_category=B | post_gap_days | 2 | 1 | 7.606794 | 9.347428 | 11.95838 | 16.309965 | 16.309965 | 20.661551 | 23.272502 | 24.142819 | 25.013137 |
| evidence_category=B | surrounding_interval_days | 1 | 2 | 45.001875 | 45.001875 | 45.001875 | 45.001875 | 45.001875 | 45.001875 | 45.001875 | 45.001875 | 45.001875 |
| evidence_category=C | pre_gap_days | 0 | 0 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| evidence_category=C | post_gap_days | 0 | 0 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| evidence_category=C | surrounding_interval_days | 0 | 0 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| evidence_category=D | pre_gap_days | 113 | 9 | 0.987106 | 11.388606 | 123.612419 | 808.986539 | 763.356503 | 1362.985255 | 1668.343546 | 1732.708333 | 1732.708333 |
| evidence_category=D | post_gap_days | 43 | 79 | 0.009711 | 0.03334 | 0.142431 | 17.013194 | 71.335533 | 86.66272 | 180.169764 | 360.68536 | 469.229502 |
| evidence_category=D | surrounding_interval_days | 43 | 79 | 7.999514 | 14.003012 | 20.60184 | 118.708287 | 239.949439 | 269.045191 | 759.882296 | 908.904907 | 1243.698218 |
| pre_observed_state=full_price | pre_gap_days | 265 | 0 | 0.091285 | 7.996741 | 21.027743 | 76.028611 | 329.756823 | 251.015197 | 1362.955671 | 1657.962792 | 1732.708333 |
| pre_observed_state=full_price | post_gap_days | 201 | 64 | 0.005486 | 0.012731 | 0.018032 | 0.045336 | 15.610291 | 0.109826 | 23.019086 | 97.229502 | 469.229502 |
| pre_observed_state=full_price | surrounding_interval_days | 201 | 64 | 7.248368 | 14.009063 | 27.049468 | 45.047778 | 102.607507 | 118.708287 | 161.546343 | 353.023345 | 1243.698218 |
| pre_observed_state=discount | pre_gap_days | 25 | 0 | 0.987106 | 4.193188 | 6.986539 | 12.988738 | 338.31042 | 144.896678 | 1356.777336 | 1598.336373 | 1665.943299 |
| pre_observed_state=discount | post_gap_days | 18 | 7 | 0.005162 | 0.00937 | 0.015668 | 0.046505 | 1.499099 | 0.131453 | 0.414713 | 4.613422 | 25.013137 |
| pre_observed_state=discount | surrounding_interval_days | 18 | 7 | 7.999514 | 11.624755 | 14.003686 | 16.534369 | 33.554312 | 27.130064 | 89.238743 | 106.968788 | 152.028843 |
| pre_observed_state=ambiguous | pre_gap_days | 0 | 0 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| pre_observed_state=ambiguous | post_gap_days | 0 | 0 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| pre_observed_state=ambiguous | surrounding_interval_days | 0 | 0 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| pre_observed_state=missing | pre_gap_days | 0 | 10 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| pre_observed_state=missing | post_gap_days | 1 | 9 | 7.606794 | 7.606794 | 7.606794 | 7.606794 | 7.606794 | 7.606794 | 7.606794 | 7.606794 | 7.606794 |
| pre_observed_state=missing | surrounding_interval_days | 0 | 10 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| post_observed_state=full_price | pre_gap_days | 192 | 1 | 0.091285 | 5.988904 | 14.162245 | 25.503883 | 64.924979 | 80.961693 | 138.99723 | 141.669209 | 1054.75 |
| post_observed_state=full_price | post_gap_days | 193 | 0 | 0.005162 | 0.012581 | 0.016748 | 0.034005 | 5.966394 | 0.070556 | 0.152808 | 7.249856 | 469.229502 |
| post_observed_state=full_price | surrounding_interval_days | 192 | 1 | 7.248368 | 13.024119 | 21.842601 | 34.071296 | 77.882829 | 88.000584 | 146.039843 | 148.765363 | 1243.698218 |
| post_observed_state=discount | pre_gap_days | 27 | 0 | 3.291505 | 14.786586 | 21.004693 | 96.153958 | 150.549569 | 150.507975 | 302.744153 | 452.519475 | 1054.75 |
| post_observed_state=discount | post_gap_days | 27 | 0 | 0.016481 | 15.104398 | 15.553472 | 23.17816 | 74.842405 | 87.549427 | 173.055949 | 307.451412 | 387.26294 |
| post_observed_state=discount | surrounding_interval_days | 27 | 0 | 30.004977 | 37.63909 | 71.695683 | 161.054352 | 232.391974 | 269.045191 | 517.875359 | 585.800904 | 1228.719248 |
| post_observed_state=ambiguous | pre_gap_days | 0 | 0 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| post_observed_state=ambiguous | post_gap_days | 0 | 0 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| post_observed_state=ambiguous | surrounding_interval_days | 0 | 0 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| post_observed_state=missing | pre_gap_days | 71 | 9 | 2.997419 | 201.728831 | 936.523166 | 1056.952963 | 1117.082877 | 1426.75 | 1732.708333 | 1732.708333 | 1732.708333 |
| post_observed_state=missing | post_gap_days | 0 | 80 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| post_observed_state=missing | surrounding_interval_days | 0 | 80 | missing | missing | missing | missing | missing | missing | missing | missing | missing |

<details>
<summary>Year × evidence category / pre-state / post-state gap distributions</summary>

| Group | Metric | N | Missing | Min | P10 | P25 | Median | Mean | P75 | P90 | P95 | Max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2023:evidence_category=A | pre_gap_days | 55 | 0 | 0.091285 | 4.863109 | 18.523258 | 27.026343 | 56.373501 | 111.446655 | 131.002954 | 131.035799 | 242.998785 |
| 2023:evidence_category=A | post_gap_days | 55 | 0 | 0.005162 | 0.009586 | 0.017789 | 0.073553 | 0.080304 | 0.112037 | 0.15412 | 0.185781 | 0.461366 |
| 2023:evidence_category=A | surrounding_interval_days | 55 | 0 | 7.248368 | 11.887012 | 25.543773 | 34.05184 | 63.453805 | 118.523368 | 138.052808 | 138.200946 | 250.016817 |
| 2023:evidence_category=B | pre_gap_days | 1 | 1 | 2.997419 | 2.997419 | 2.997419 | 2.997419 | 2.997419 | 2.997419 | 2.997419 | 2.997419 | 2.997419 |
| 2023:evidence_category=B | post_gap_days | 1 | 1 | 7.606794 | 7.606794 | 7.606794 | 7.606794 | 7.606794 | 7.606794 | 7.606794 | 7.606794 | 7.606794 |
| 2023:evidence_category=B | surrounding_interval_days | 0 | 2 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| 2023:evidence_category=C | pre_gap_days | 0 | 0 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| 2023:evidence_category=C | post_gap_days | 0 | 0 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| 2023:evidence_category=C | surrounding_interval_days | 0 | 0 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| 2023:evidence_category=D | pre_gap_days | 40 | 3 | 1.20603 | 18.518343 | 129.125848 | 638.990295 | 571.758953 | 1054.75 | 1054.75 | 1054.75 | 1054.75 |
| 2023:evidence_category=D | post_gap_days | 20 | 23 | 0.009711 | 0.125575 | 0.156751 | 23.085961 | 103.507775 | 170.71399 | 367.270815 | 391.361268 | 469.229502 |
| 2023:evidence_category=D | surrounding_interval_days | 20 | 23 | 8.364132 | 19.513365 | 44.187034 | 156.536001 | 330.890934 | 542.134482 | 952.164341 | 1229.468196 | 1243.698218 |
| 2023:pre_observed_state=full_price | pre_gap_days | 85 | 0 | 0.091285 | 7.981308 | 21.027743 | 99.032523 | 278.009786 | 242.998785 | 1054.75 | 1054.75 | 1054.75 |
| 2023:pre_observed_state=full_price | post_gap_days | 67 | 18 | 0.005486 | 0.013037 | 0.028872 | 0.102454 | 30.953501 | 0.186325 | 23.284493 | 279.570339 | 469.229502 |
| 2023:pre_observed_state=full_price | surrounding_interval_days | 67 | 18 | 7.248368 | 13.025095 | 26.115405 | 50.177303 | 144.462274 | 138.045793 | 226.633005 | 741.760991 | 1243.698218 |
| 2023:pre_observed_state=discount | pre_gap_days | 11 | 0 | 1.20603 | 2.997419 | 9.9918 | 21.994954 | 213.006025 | 118.454265 | 979.965891 | 983.975428 | 987.984965 |
| 2023:pre_observed_state=discount | post_gap_days | 8 | 3 | 0.005162 | 0.007552 | 0.009427 | 0.110608 | 0.085953 | 0.137297 | 0.154318 | 0.15621 | 0.158102 |
| 2023:pre_observed_state=discount | surrounding_interval_days | 8 | 3 | 8.364132 | 12.306615 | 18.593845 | 25.112477 | 53.600703 | 88.540295 | 114.920562 | 133.474703 | 152.028843 |
| 2023:pre_observed_state=ambiguous | pre_gap_days | 0 | 0 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| 2023:pre_observed_state=ambiguous | post_gap_days | 0 | 0 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| 2023:pre_observed_state=ambiguous | surrounding_interval_days | 0 | 0 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| 2023:pre_observed_state=missing | pre_gap_days | 0 | 4 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| 2023:pre_observed_state=missing | post_gap_days | 1 | 3 | 7.606794 | 7.606794 | 7.606794 | 7.606794 | 7.606794 | 7.606794 | 7.606794 | 7.606794 | 7.606794 |
| 2023:pre_observed_state=missing | surrounding_interval_days | 0 | 4 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| 2023:post_observed_state=full_price | pre_gap_days | 64 | 1 | 0.091285 | 4.675419 | 14.791846 | 26.022766 | 82.34816 | 130.889708 | 131.036863 | 237.154243 | 1054.75 |
| 2023:post_observed_state=full_price | post_gap_days | 65 | 0 | 0.005162 | 0.009905 | 0.018032 | 0.087998 | 15.158208 | 0.137454 | 0.186597 | 6.177708 | 469.229502 |
| 2023:post_observed_state=full_price | surrounding_interval_days | 64 | 1 | 7.248368 | 11.700834 | 21.875188 | 33.038258 | 104.624359 | 138.030373 | 138.282052 | 244.170864 | 1243.698218 |
| 2023:post_observed_state=discount | pre_gap_days | 11 | 0 | 19.022002 | 47.494606 | 97.593241 | 130.963657 | 203.447588 | 146.528744 | 242.862384 | 648.806192 | 1054.75 |
| 2023:post_observed_state=discount | post_gap_days | 11 | 0 | 15.554329 | 23.019086 | 23.080341 | 23.17816 | 99.717774 | 95.189676 | 365.049468 | 376.156204 | 387.26294 |
| 2023:post_observed_state=discount | surrounding_interval_days | 11 | 0 | 49.200162 | 77.695359 | 123.910995 | 161.054352 | 310.165362 | 354.994161 | 614.911852 | 921.81555 | 1228.719248 |
| 2023:post_observed_state=ambiguous | pre_gap_days | 0 | 0 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| 2023:post_observed_state=ambiguous | post_gap_days | 0 | 0 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| 2023:post_observed_state=ambiguous | surrounding_interval_days | 0 | 0 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| 2023:post_observed_state=missing | pre_gap_days | 21 | 3 | 2.997419 | 243.006863 | 979.965891 | 1008.984167 | 879.318685 | 1054.75 | 1054.75 | 1054.75 | 1054.75 |
| 2023:post_observed_state=missing | post_gap_days | 0 | 24 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| 2023:post_observed_state=missing | surrounding_interval_days | 0 | 24 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| 2024:evidence_category=A | pre_gap_days | 60 | 0 | 1.984711 | 8.784345 | 19.247711 | 26.989398 | 65.291535 | 93.277934 | 139.028049 | 139.028432 | 614.862384 |
| 2024:evidence_category=A | post_gap_days | 60 | 0 | 0.012419 | 0.012545 | 0.016904 | 0.027407 | 0.748365 | 0.058119 | 0.062775 | 8.013473 | 14.011215 |
| 2024:evidence_category=A | surrounding_interval_days | 60 | 0 | 9.006586 | 15.839839 | 26.298643 | 38.051887 | 73.0399 | 100.306377 | 146.04103 | 146.044367 | 621.920741 |
| 2024:evidence_category=B | pre_gap_days | 0 | 0 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| 2024:evidence_category=B | post_gap_days | 0 | 0 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| 2024:evidence_category=B | surrounding_interval_days | 0 | 0 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| 2024:evidence_category=C | pre_gap_days | 0 | 0 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| 2024:evidence_category=C | post_gap_days | 0 | 0 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| 2024:evidence_category=C | surrounding_interval_days | 0 | 0 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| 2024:evidence_category=D | pre_gap_days | 37 | 3 | 0.987106 | 13.586752 | 138.993727 | 691.895405 | 777.863803 | 1387.985185 | 1426.75 | 1426.75 | 1426.75 |
| 2024:evidence_category=D | post_gap_days | 14 | 26 | 0.012407 | 0.027462 | 3.801126 | 15.371308 | 55.280374 | 98.559563 | 167.631008 | 173.055949 | 173.055949 |
| 2024:evidence_category=D | surrounding_interval_days | 14 | 26 | 7.999514 | 13.319657 | 22.436247 | 178.793721 | 216.223218 | 279.566843 | 499.904407 | 615.262701 | 796.124907 |
| 2024:pre_observed_state=full_price | pre_gap_days | 91 | 0 | 1.984711 | 14.030891 | 22.983403 | 72.737419 | 329.25877 | 309.976684 | 1387.985185 | 1426.75 | 1426.75 |
| 2024:pre_observed_state=full_price | post_gap_days | 70 | 21 | 0.012419 | 0.012578 | 0.020576 | 0.039861 | 11.696043 | 0.062173 | 15.284613 | 98.20488 | 173.055949 |
| 2024:pre_observed_state=full_price | surrounding_interval_days | 70 | 21 | 9.006586 | 16.045681 | 27.56318 | 44.523021 | 105.106586 | 146.040749 | 207.539189 | 382.424526 | 796.124907 |
| 2024:pre_observed_state=discount | pre_gap_days | 6 | 0 | 0.987106 | 3.487951 | 6.238817 | 8.489016 | 455.984132 | 1016.471707 | 1355.975428 | 1357.980197 | 1359.984965 |
| 2024:pre_observed_state=discount | post_gap_days | 4 | 2 | 0.012407 | 0.016164 | 0.0218 | 0.029149 | 0.026019 | 0.033368 | 0.033368 | 0.033368 | 0.033368 |
| 2024:pre_observed_state=discount | surrounding_interval_days | 4 | 2 | 7.999514 | 9.506309 | 11.766502 | 13.517986 | 13.014502 | 14.765987 | 16.119909 | 16.571216 | 17.022523 |
| 2024:pre_observed_state=ambiguous | pre_gap_days | 0 | 0 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| 2024:pre_observed_state=ambiguous | post_gap_days | 0 | 0 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| 2024:pre_observed_state=ambiguous | surrounding_interval_days | 0 | 0 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| 2024:pre_observed_state=missing | pre_gap_days | 0 | 3 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| 2024:pre_observed_state=missing | post_gap_days | 0 | 3 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| 2024:pre_observed_state=missing | surrounding_interval_days | 0 | 3 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| 2024:post_observed_state=full_price | pre_gap_days | 65 | 0 | 0.987106 | 6.388866 | 16.028854 | 24.030822 | 71.282176 | 79.027384 | 139.02813 | 139.028528 | 691.895405 |
| 2024:post_observed_state=full_price | post_gap_days | 65 | 0 | 0.012407 | 0.012539 | 0.016956 | 0.02934 | 2.188238 | 0.058113 | 0.065021 | 8.013481 | 97.229502 |
| 2024:post_observed_state=full_price | surrounding_interval_days | 65 | 0 | 7.999514 | 13.418995 | 23.083079 | 37.017384 | 80.470414 | 86.061157 | 146.04103 | 146.084532 | 796.124907 |
| 2024:post_observed_state=discount | pre_gap_days | 9 | 0 | 15.98515 | 16.155225 | 22.987384 | 86.029074 | 159.927831 | 267.984097 | 380.6979 | 438.15516 | 495.612419 |
| 2024:post_observed_state=discount | post_gap_days | 9 | 0 | 15.104398 | 15.104398 | 15.26294 | 15.552616 | 75.176851 | 154.972813 | 173.055949 | 173.055949 | 173.055949 |
| 2024:post_observed_state=discount | surrounding_interval_days | 9 | 0 | 38.677419 | 60.292289 | 161.546343 | 203.043333 | 242.104681 | 290.088495 | 469.952822 | 493.91409 | 517.875359 |
| 2024:post_observed_state=ambiguous | pre_gap_days | 0 | 0 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| 2024:post_observed_state=ambiguous | post_gap_days | 0 | 0 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| 2024:post_observed_state=ambiguous | surrounding_interval_days | 0 | 0 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| 2024:post_observed_state=missing | pre_gap_days | 23 | 3 | 172.031053 | 394.992123 | 1190.517049 | 1362.985255 | 1157.641778 | 1426.75 | 1426.75 | 1426.75 | 1426.75 |
| 2024:post_observed_state=missing | post_gap_days | 0 | 26 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| 2024:post_observed_state=missing | surrounding_interval_days | 0 | 26 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| 2025:evidence_category=A | pre_gap_days | 60 | 0 | 0.989016 | 6.98535 | 15.487312 | 27.98213 | 42.500216 | 80.954948 | 80.987528 | 80.987921 | 192.962662 |
| 2025:evidence_category=A | post_gap_days | 60 | 0 | 0.012546 | 0.012854 | 0.013579 | 0.025162 | 0.381543 | 0.051826 | 0.060966 | 0.070556 | 14.015822 |
| 2025:evidence_category=A | surrounding_interval_days | 60 | 0 | 8.001597 | 14.005043 | 23.01899 | 35.019473 | 49.881759 | 87.999097 | 88.002086 | 88.008172 | 200.003877 |
| 2025:evidence_category=B | pre_gap_days | 1 | 0 | 12.988738 | 12.988738 | 12.988738 | 12.988738 | 12.988738 | 12.988738 | 12.988738 | 12.988738 | 12.988738 |
| 2025:evidence_category=B | post_gap_days | 1 | 0 | 25.013137 | 25.013137 | 25.013137 | 25.013137 | 25.013137 | 25.013137 | 25.013137 | 25.013137 | 25.013137 |
| 2025:evidence_category=B | surrounding_interval_days | 1 | 0 | 45.001875 | 45.001875 | 45.001875 | 45.001875 | 45.001875 | 45.001875 | 45.001875 | 45.001875 | 45.001875 |
| 2025:evidence_category=C | pre_gap_days | 0 | 0 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| 2025:evidence_category=C | post_gap_days | 0 | 0 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| 2025:evidence_category=C | surrounding_interval_days | 0 | 0 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| 2025:evidence_category=D | pre_gap_days | 36 | 3 | 3.291505 | 8.987222 | 82.482645 | 1141.938247 | 961.332388 | 1703.634722 | 1732.708333 | 1732.708333 | 1732.708333 |
| 2025:evidence_category=D | post_gap_days | 9 | 30 | 0.012581 | 0.029183 | 0.059641 | 12.010856 | 24.816354 | 44.053414 | 73.662993 | 74.879465 | 76.095938 |
| 2025:evidence_category=D | surrounding_interval_days | 9 | 30 | 14.000312 | 15.617025 | 16.046215 | 32.021331 | 74.764684 | 83.346262 | 154.078919 | 253.551132 | 353.023345 |
| 2025:pre_observed_state=full_price | pre_gap_days | 89 | 0 | 0.989016 | 6.988606 | 20.98412 | 62.947697 | 379.687396 | 201.728831 | 1701.696481 | 1732.708333 | 1732.708333 |
| 2025:pre_observed_state=full_price | post_gap_days | 64 | 25 | 0.012546 | 0.012894 | 0.015747 | 0.025301 | 3.829076 | 0.057755 | 4.929495 | 16.563589 | 76.095938 |
| 2025:pre_observed_state=full_price | surrounding_interval_days | 64 | 25 | 8.001597 | 14.006478 | 27.003365 | 39.040932 | 56.057431 | 88.000058 | 88.003677 | 88.040906 | 353.023345 |
| 2025:pre_observed_state=discount | pre_gap_days | 8 | 0 | 5.98684 | 6.685828 | 8.486279 | 9.987182 | 422.348679 | 424.22261 | 1660.329947 | 1663.136623 | 1665.943299 |
| 2025:pre_observed_state=discount | post_gap_days | 6 | 2 | 0.012581 | 0.022957 | 0.03991 | 0.059774 | 4.365345 | 0.775081 | 13.013304 | 19.01322 | 25.013137 |
| 2025:pre_observed_state=discount | surrounding_interval_days | 6 | 2 | 14.000312 | 14.022807 | 14.539277 | 16.033709 | 20.518997 | 17.510859 | 31.500475 | 38.251175 | 45.001875 |
| 2025:pre_observed_state=ambiguous | pre_gap_days | 0 | 0 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| 2025:pre_observed_state=ambiguous | post_gap_days | 0 | 0 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| 2025:pre_observed_state=ambiguous | surrounding_interval_days | 0 | 0 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| 2025:pre_observed_state=missing | pre_gap_days | 0 | 3 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| 2025:pre_observed_state=missing | post_gap_days | 0 | 3 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| 2025:pre_observed_state=missing | surrounding_interval_days | 0 | 3 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| 2025:post_observed_state=full_price | pre_gap_days | 63 | 0 | 0.989016 | 6.985042 | 13.525694 | 25.988576 | 40.666226 | 80.952471 | 80.9875 | 80.987906 | 192.962662 |
| 2025:post_observed_state=full_price | post_gap_days | 63 | 0 | 0.012546 | 0.012822 | 0.013547 | 0.025185 | 0.380875 | 0.057691 | 0.06838 | 0.070556 | 14.015822 |
| 2025:post_observed_state=full_price | surrounding_interval_days | 63 | 0 | 8.001597 | 14.00275 | 21.0211 | 34.086366 | 48.047101 | 87.998345 | 88.001861 | 88.007785 | 200.003877 |
| 2025:post_observed_state=discount | pre_gap_days | 7 | 0 | 3.291505 | 6.121484 | 10.498437 | 17.070741 | 55.366346 | 38.138947 | 139.944602 | 204.936005 | 269.927407 |
| 2025:post_observed_state=discount | post_gap_days | 7 | 0 | 0.016481 | 7.213106 | 14.512025 | 25.013137 | 35.32254 | 58.554086 | 74.271229 | 75.183583 | 76.095938 |
| 2025:post_observed_state=discount | surrounding_interval_days | 7 | 0 | 30.004977 | 31.214789 | 34.051464 | 45.001875 | 97.688886 | 93.844537 | 203.815025 | 278.419185 | 353.023345 |
| 2025:post_observed_state=ambiguous | pre_gap_days | 0 | 0 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| 2025:post_observed_state=ambiguous | post_gap_days | 0 | 0 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| 2025:post_observed_state=ambiguous | surrounding_interval_days | 0 | 0 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| 2025:post_observed_state=missing | pre_gap_days | 27 | 3 | 80.963183 | 198.216211 | 741.463987 | 1665.943299 | 1267.460407 | 1732.708333 | 1732.708333 | 1732.708333 | 1732.708333 |
| 2025:post_observed_state=missing | post_gap_days | 0 | 30 | missing | missing | missing | missing | missing | missing | missing | missing | missing |
| 2025:post_observed_state=missing | surrounding_interval_days | 0 | 30 | missing | missing | missing | missing | missing | missing | missing | missing | missing |

</details>

Counts of historical observations before and after each sale, full observed chronology, raw indices, nearest raw fields, price summaries and conflicting groups are in [the pair-level diagnostics](../data/intermediate/autumn_sale_coverage_diagnostics.csv). Long gaps leave broad intervals without direct observations. Neither large nor small gaps alone demonstrate completeness; no gap cutoff is adopted.

## H. Detailed Category B and D analysis

All three B pairs follow. One full-price record proves only that observed timestamp, not that the whole event was undiscounted. Two B pairs have a pre-sale discount; one has no pre-sale observation.

### Every Category B case: Hentai Beauty (2205710), 2025 — B

Pre/post observed states: discount / discount. Pre/post gaps: 12.988738 / 25.013137 days. Surrounding interval: 45.001875 days. Observed counts pre/in/post: 53/1/3.

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| pre | 22 | 2025-09-16T17:16:13Z | 0.49 | 0.99 | 51 | USD | discount |
| in_window | 21 | 2025-09-30T17:15:31Z | 0.99 | 0.99 | 0 | USD | full_price |
| post | 20 | 2025-10-31T17:18:55Z | 0.49 | 0.99 | 51 | USD | discount |

Only the listed timestamps establish observed prices. Missing intervals and an absent side remain unresolved.

### Every Category B case: HOPE LEFT ME (2268470), 2023 — B

Pre/post observed states: discount / missing. Pre/post gaps: 2.997419 / missing days. Surrounding interval: missing days. Observed counts pre/in/post: 4/1/0.

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| pre | 1 | 2023-11-18T18:03:43Z | 1.59 | 1.99 | 20 | USD | discount |
| in_window | 0 | 2023-11-25T18:24:20Z | 1.99 | 1.99 | 0 | USD | full_price |

Only the listed timestamps establish observed prices. Missing intervals and an absent side remain unresolved.

### Every Category B case: nekowater (2650840), 2023 — B

Pre/post observed states: missing / full_price. Pre/post gaps: missing / 7.606794 days. Surrounding interval: missing days. Observed counts pre/in/post: 0/1/40.

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| in_window | 54 | 2023-11-21T22:39:17Z | 2.99 | 2.99 | 0 | USD | full_price |
| post | 53 | 2023-12-06T08:33:47Z | 1.99 | 1.99 | 0 | USD | full_price |

Only the listed timestamps establish observed prices. Missing intervals and an absent side remain unresolved.

HOPE LEFT ME: the cache stops at the in-window full-price observation; no post-sale price is available. Hentai Beauty: a pre-sale discount precedes the one in-window full-price record and a later discount. nekowater: release date equals sale-start date; the observed full price at 22:39:17Z is after sale start, but release availability at 18:00:00Z is unverified. A later full-price record has a lower regular price, showing that cut=0 alone does not mean an unchanged base price.

D pairs by year and latest pre-sale state:

| Year | Full price | Discounted | Ambiguous | Missing |
| --- | --- | --- | --- | --- |
| 2023 | 32 | 8 | 0 | 3 |
| 2024 | 31 | 6 | 0 | 3 |
| 2025 | 30 | 6 | 0 | 3 |

The sensitivity section quantifies recency for every D pair. There is no direct in-window observation to resolve any D pair regardless of whether surrounding values agree.

## I. ITAD history-semantics assessment

Official [History endpoint documentation](https://docs.isthereanydeal.com/#tag/History/operation/games-history-v2) and [official OpenAPI schema](https://github.com/IsThereAnyDeal/API/blob/master/dist/openapi.json) were reviewed on 2026-10-11 (documented API 2.11.0). The endpoint returns a historical price log; its `since` parameter says “Load only price changes after this date.” The schema allows null deals. A local [documentation evidence note](sources/itad_history_semantics.json) records review scope. The diagnostic pipeline reads it offline.

| Claim | Supporting evidence | Counterevidence / limitation | Assessment |
| --- | --- | --- | --- |
| 1. Returns historical records | Official endpoint and schema; timestamped cached response arrays | A history array does not define coverage quality | Supported |
| 2. Change-oriented | Official since description explicitly refers to price changes; observed transitions dominate | Repeated states, tied conflicts and requested-since observations do occur | Supported orientation; not a strict unique-change log |
| 3. Captures every Steam change | No completeness guarantee found in reviewed materials | Gaps cannot establish completeness or prove that specific changes were omitted | Unresolved; not established |
| 4. Safe persistence until next record | Would require additional capture/timestamp/state assumptions | No such guarantee found; ambiguous/conflicting and potentially initialized records complicate reconstruction | Unresolved; never applied here |

**Observed facts (pre-2026 records only):**

| Measure | Count |
| --- | --- |
| adjacent_groups_excluded_from_directional_counts | 10 |
| ambiguous | 0 |
| conflicting_timestamp_groups | 6 |
| consecutive_cut_zero | 53 |
| consecutive_groups_sharing_state | 2 |
| discount | 2361 |
| duplicate_timestamp_groups | 6 |
| full_price | 2355 |
| nonempty_games | 97 |
| null_deals | 0 |
| records | 4716 |
| requested_since_timestamp | 65 |
| reverse_chronological_games | 97 |
| same_price_adjacent_pairs | 3 |
| singleton_adjacent_pairs | 4603 |
| zero_price_regular | 9 |

| From observed state | To observed state | Singleton consecutive pairs |
| --- | --- | --- |
| discount | discount | 24 |
| discount | full_price | 2263 |
| full_price | discount | 2263 |
| full_price | full_price | 53 |

| Consecutive distinct timestamp gap (days) | n | missing | min | p10 | p25 | median | mean | p75 | p90 | p95 | max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| All analyzed histories | 4613 | 0 | 0.002211 | 6.045458 | 7.002176 | 13.997431 | 25.975798 | 29.966505 | 52.993255 | 84.060678 | 1243.698218 |

Of 4603 adjacent singleton timestamp pairs, 4526 alternate between discounted and full-price observations. There are 53 consecutive cut=0 pairs, with 0 identical full-price signatures. These analyzed observations do not show regular unchanged full-price polling. Directional counts exclude tied groups rather than arbitrarily ordering conflicting states. Consecutive identical states contradict a strict “every record is a unique changed price” interpretation, but do not disprove change-oriented collection. Consecutive cut=0 records can reflect changed regular prices. Requested-since timestamps could be initialized snapshots; their origin is an interpretation, not established fact. No polling schedule, perfect coverage, price-duration guarantee or null-deal sale meaning is inferred.

## J. Hypothetical coverage sensitivity scenarios

**HYPOTHETICAL ASSUMPTION:** a pre-sale observation within each listed elapsed-day limit is available for possible later methodological review. This is a recency test, not a negative-label rule. Only 125 non-A pairs enter these scenarios. States remain separate; discounted pre-state counts are not combined with full-price counts as potential negatives. Missing and ambiguous states remain separate.

Unrestricted imposes no recency filter, so missing-pre pairs appear as a separate availability bucket; finite limits cannot be satisfied without a pre timestamp. Optional two-sided counts require a post timestamp within the same limit as well (unrestricted requires both timestamps). Neither condition establishes coverage. CSV aggregate rows overlap across year/category slices; do not sum “all” rows with their component rows.

| Scenario | Year | Pre full price | Pre discounted | Pre ambiguous | Pre missing |
| --- | --- | --- | --- | --- | --- |
| pre_within_7_days | all | 1 | 7 | 0 | 0 |
| pre_within_7_days | 2023 | 0 | 3 | 0 | 0 |
| pre_within_7_days | 2024 | 0 | 3 | 0 | 0 |
| pre_within_7_days | 2025 | 1 | 1 | 0 | 0 |
| pre_within_14_days | all | 2 | 14 | 0 | 0 |
| pre_within_14_days | 2023 | 0 | 5 | 0 | 0 |
| pre_within_14_days | 2024 | 0 | 4 | 0 | 0 |
| pre_within_14_days | 2025 | 2 | 5 | 0 | 0 |
| pre_within_30_days | all | 7 | 15 | 0 | 0 |
| pre_within_30_days | 2023 | 1 | 6 | 0 | 0 |
| pre_within_30_days | 2024 | 3 | 4 | 0 | 0 |
| pre_within_30_days | 2025 | 3 | 5 | 0 | 0 |
| pre_within_60_days | all | 10 | 15 | 0 | 0 |
| pre_within_60_days | 2023 | 2 | 6 | 0 | 0 |
| pre_within_60_days | 2024 | 4 | 4 | 0 | 0 |
| pre_within_60_days | 2025 | 4 | 5 | 0 | 0 |
| pre_within_90_days | all | 13 | 15 | 0 | 0 |
| pre_within_90_days | 2023 | 2 | 6 | 0 | 0 |
| pre_within_90_days | 2024 | 5 | 4 | 0 | 0 |
| pre_within_90_days | 2025 | 6 | 5 | 0 | 0 |
| unrestricted | all | 93 | 22 | 0 | 10 |
| unrestricted | 2023 | 32 | 9 | 0 | 4 |
| unrestricted | 2024 | 31 | 6 | 0 | 3 |
| unrestricted | 2025 | 30 | 7 | 0 | 3 |

Post evidence and its gap distributions, keeping pre states separate:

| Scenario | Pre state | Meets recency | Post exists | Post missing | Both within limit | Post gap min | Median | Mean | P90 | Max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pre_within_7_days | full_price | 1 | 1 | 0 | 0 | 73.054757 | 73.054757 | 73.054757 | 73.054757 | 73.054757 |
| pre_within_7_days | discount | 7 | 6 | 1 | 6 | 0.009711 | 0.029149 | 0.208665 | 0.585787 | 1.013472 |
| pre_within_7_days | ambiguous | 0 | 0 | 0 | 0 | missing | missing | missing | missing | missing |
| pre_within_7_days | missing | 0 | 0 | 0 | 0 | missing | missing | missing | missing | missing |
| pre_within_14_days | full_price | 2 | 2 | 0 | 0 | 17.013194 | 45.033976 | 45.033976 | 67.450601 | 73.054757 |
| pre_within_14_days | discount | 14 | 13 | 1 | 12 | 0.009711 | 0.033368 | 2.048097 | 0.842398 | 25.013137 |
| pre_within_14_days | ambiguous | 0 | 0 | 0 | 0 | missing | missing | missing | missing | missing |
| pre_within_14_days | missing | 0 | 0 | 0 | 0 | missing | missing | missing | missing | missing |
| pre_within_30_days | full_price | 7 | 7 | 0 | 4 | 12.010856 | 23.17816 | 69.549792 | 173.055949 | 173.055949 |
| pre_within_30_days | discount | 15 | 14 | 1 | 14 | 0.009711 | 0.046505 | 1.912712 | 0.756861 | 25.013137 |
| pre_within_30_days | ambiguous | 0 | 0 | 0 | 0 | missing | missing | missing | missing | missing |
| pre_within_30_days | missing | 0 | 0 | 0 | 0 | missing | missing | missing | missing | missing |
| pre_within_60_days | full_price | 10 | 10 | 0 | 7 | 12.010856 | 23.189456 | 56.920711 | 173.055949 | 173.055949 |
| pre_within_60_days | discount | 15 | 14 | 1 | 14 | 0.009711 | 0.046505 | 1.912712 | 0.756861 | 25.013137 |
| pre_within_60_days | ambiguous | 0 | 0 | 0 | 0 | missing | missing | missing | missing | missing |
| pre_within_60_days | missing | 0 | 0 | 0 | 0 | missing | missing | missing | missing | missing |
| pre_within_90_days | full_price | 13 | 11 | 2 | 8 | 12.010856 | 23.200752 | 65.834538 | 173.055949 | 173.055949 |
| pre_within_90_days | discount | 15 | 14 | 1 | 14 | 0.009711 | 0.046505 | 1.912712 | 0.756861 | 25.013137 |
| pre_within_90_days | ambiguous | 0 | 0 | 0 | 0 | missing | missing | missing | missing | missing |
| pre_within_90_days | missing | 0 | 0 | 0 | 0 | missing | missing | missing | missing | missing |
| unrestricted | full_price | 93 | 29 | 64 | 29 | 12.010856 | 23.410104 | 105.707963 | 330.136606 | 469.229502 |
| unrestricted | discount | 22 | 15 | 7 | 15 | 0.009711 | 0.059641 | 1.794008 | 0.671324 | 25.013137 |
| unrestricted | ambiguous | 0 | 0 | 0 | 0 | missing | missing | missing | missing | missing |
| unrestricted | missing | 10 | 1 | 9 | 0 | 7.606794 | 7.606794 | 7.606794 | 7.606794 | 7.606794 |

<details>
<summary>B/C/D scenario breakdown by pre state</summary>

| Scenario | Category | Pre state | Stratum pairs | Meets recency | Post exists | Post missing |
| --- | --- | --- | --- | --- | --- | --- |
| pre_within_7_days | B | full_price | 0 | 0 | 0 | 0 |
| pre_within_7_days | B | discount | 2 | 1 | 0 | 1 |
| pre_within_7_days | B | ambiguous | 0 | 0 | 0 | 0 |
| pre_within_7_days | B | missing | 1 | 0 | 0 | 0 |
| pre_within_7_days | C | full_price | 0 | 0 | 0 | 0 |
| pre_within_7_days | C | discount | 0 | 0 | 0 | 0 |
| pre_within_7_days | C | ambiguous | 0 | 0 | 0 | 0 |
| pre_within_7_days | C | missing | 0 | 0 | 0 | 0 |
| pre_within_7_days | D | full_price | 93 | 1 | 1 | 0 |
| pre_within_7_days | D | discount | 20 | 6 | 6 | 0 |
| pre_within_7_days | D | ambiguous | 0 | 0 | 0 | 0 |
| pre_within_7_days | D | missing | 9 | 0 | 0 | 0 |
| pre_within_14_days | B | full_price | 0 | 0 | 0 | 0 |
| pre_within_14_days | B | discount | 2 | 2 | 1 | 1 |
| pre_within_14_days | B | ambiguous | 0 | 0 | 0 | 0 |
| pre_within_14_days | B | missing | 1 | 0 | 0 | 0 |
| pre_within_14_days | C | full_price | 0 | 0 | 0 | 0 |
| pre_within_14_days | C | discount | 0 | 0 | 0 | 0 |
| pre_within_14_days | C | ambiguous | 0 | 0 | 0 | 0 |
| pre_within_14_days | C | missing | 0 | 0 | 0 | 0 |
| pre_within_14_days | D | full_price | 93 | 2 | 2 | 0 |
| pre_within_14_days | D | discount | 20 | 12 | 12 | 0 |
| pre_within_14_days | D | ambiguous | 0 | 0 | 0 | 0 |
| pre_within_14_days | D | missing | 9 | 0 | 0 | 0 |
| pre_within_30_days | B | full_price | 0 | 0 | 0 | 0 |
| pre_within_30_days | B | discount | 2 | 2 | 1 | 1 |
| pre_within_30_days | B | ambiguous | 0 | 0 | 0 | 0 |
| pre_within_30_days | B | missing | 1 | 0 | 0 | 0 |
| pre_within_30_days | C | full_price | 0 | 0 | 0 | 0 |
| pre_within_30_days | C | discount | 0 | 0 | 0 | 0 |
| pre_within_30_days | C | ambiguous | 0 | 0 | 0 | 0 |
| pre_within_30_days | C | missing | 0 | 0 | 0 | 0 |
| pre_within_30_days | D | full_price | 93 | 7 | 7 | 0 |
| pre_within_30_days | D | discount | 20 | 13 | 13 | 0 |
| pre_within_30_days | D | ambiguous | 0 | 0 | 0 | 0 |
| pre_within_30_days | D | missing | 9 | 0 | 0 | 0 |
| pre_within_60_days | B | full_price | 0 | 0 | 0 | 0 |
| pre_within_60_days | B | discount | 2 | 2 | 1 | 1 |
| pre_within_60_days | B | ambiguous | 0 | 0 | 0 | 0 |
| pre_within_60_days | B | missing | 1 | 0 | 0 | 0 |
| pre_within_60_days | C | full_price | 0 | 0 | 0 | 0 |
| pre_within_60_days | C | discount | 0 | 0 | 0 | 0 |
| pre_within_60_days | C | ambiguous | 0 | 0 | 0 | 0 |
| pre_within_60_days | C | missing | 0 | 0 | 0 | 0 |
| pre_within_60_days | D | full_price | 93 | 10 | 10 | 0 |
| pre_within_60_days | D | discount | 20 | 13 | 13 | 0 |
| pre_within_60_days | D | ambiguous | 0 | 0 | 0 | 0 |
| pre_within_60_days | D | missing | 9 | 0 | 0 | 0 |
| pre_within_90_days | B | full_price | 0 | 0 | 0 | 0 |
| pre_within_90_days | B | discount | 2 | 2 | 1 | 1 |
| pre_within_90_days | B | ambiguous | 0 | 0 | 0 | 0 |
| pre_within_90_days | B | missing | 1 | 0 | 0 | 0 |
| pre_within_90_days | C | full_price | 0 | 0 | 0 | 0 |
| pre_within_90_days | C | discount | 0 | 0 | 0 | 0 |
| pre_within_90_days | C | ambiguous | 0 | 0 | 0 | 0 |
| pre_within_90_days | C | missing | 0 | 0 | 0 | 0 |
| pre_within_90_days | D | full_price | 93 | 13 | 11 | 2 |
| pre_within_90_days | D | discount | 20 | 13 | 13 | 0 |
| pre_within_90_days | D | ambiguous | 0 | 0 | 0 | 0 |
| pre_within_90_days | D | missing | 9 | 0 | 0 | 0 |
| unrestricted | B | full_price | 0 | 0 | 0 | 0 |
| unrestricted | B | discount | 2 | 2 | 1 | 1 |
| unrestricted | B | ambiguous | 0 | 0 | 0 | 0 |
| unrestricted | B | missing | 1 | 1 | 1 | 0 |
| unrestricted | C | full_price | 0 | 0 | 0 | 0 |
| unrestricted | C | discount | 0 | 0 | 0 | 0 |
| unrestricted | C | ambiguous | 0 | 0 | 0 | 0 |
| unrestricted | C | missing | 0 | 0 | 0 | 0 |
| unrestricted | D | full_price | 93 | 93 | 29 | 64 |
| unrestricted | D | discount | 20 | 20 | 14 | 6 |
| unrestricted | D | ambiguous | 0 | 0 | 0 | 0 |
| unrestricted | D | missing | 9 | 9 | 0 | 9 |

</details>

The [sensitivity CSV](../data/intermediate/autumn_sale_coverage_sensitivity.csv) includes all 384 scenario/year/category/pre-state cells, zero-count strata, post-state counts, missing counts, full post-gap percentiles and matching pair keys. No optimum threshold is selected.

## K. Special-case investigations

All D pairs without pre-sale observations:

| AppID | Name | Year | Analyzed records | Post state |
| --- | --- | --- | --- | --- |
| 1894600 | Monster | 2023 | 0 | missing |
| 1894600 | Monster | 2024 | 0 | missing |
| 1894600 | Monster | 2025 | 0 | missing |
| 2062610 | Phantom Club (CPC/Spectrum) | 2023 | 0 | missing |
| 2062610 | Phantom Club (CPC/Spectrum) | 2024 | 0 | missing |
| 2062610 | Phantom Club (CPC/Spectrum) | 2025 | 0 | missing |
| 2504210 | The Leverage Game Business Edition | 2023 | 0 | missing |
| 2504210 | The Leverage Game Business Edition | 2024 | 0 | missing |
| 2504210 | The Leverage Game Business Edition | 2025 | 0 | missing |

### D with recent pre-sale discount evidence: Men of War™ (7830), 2024 — D

Pre/post observed states: discount / full_price. Pre/post gaps: 0.987106 / 0.012407 days. Surrounding interval: 7.999514 days. Observed counts pre/in/post: 41/0/16.

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| pre | 25 | 2024-11-26T18:18:34Z | 0.74 | 4.99 | 85 | USD | discount |
| post | 24 | 2024-12-04T18:17:52Z | 4.99 | 4.99 | 0 | USD | full_price |

Only the listed timestamps establish observed prices. Missing intervals and an absent side remain unresolved.

### D with recent pre-sale full_price evidence: Droid Assault (219200), 2025 — D

Pre/post observed states: full_price / discount. Pre/post gaps: 3.291505 / 73.054757 days. Surrounding interval: 83.346262 days. Observed counts pre/in/post: 59/0/1.

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| pre | 13 | 2025-09-26T10:00:14Z | 9.99 | 9.99 | 0 | USD | full_price |
| post | 12 | 2025-12-18T18:18:51Z | 4.29 | 9.99 | 57 | USD | discount |

Only the listed timestamps establish observed prices. Missing intervals and an absent side remain unresolved.

### D without pre-sale evidence: Monster (1894600), 2023 — D

Pre/post observed states: missing / missing. Pre/post gaps: missing / missing days. Surrounding interval: missing days. Observed counts pre/in/post: 0/0/0.

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |

Only the listed timestamps establish observed prices. Missing intervals and an absent side remain unresolved.

### D with the longest pre-sale gap (ranking, no cutoff): Scoregasm (202410), 2025 — D

Pre/post observed states: full_price / missing. Pre/post gaps: 1732.708333 / missing days. Surrounding interval: missing days. Observed counts pre/in/post: 1/0/0.

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| pre | 2 | 2021-01-01T00:00:00Z | 4.99 | 4.99 | 0 | USD | full_price |

Only the listed timestamps establish observed prices. Missing intervals and an absent side remain unresolved.

### D with one of the longest observed surrounding intervals: Spunk and Moxie (449310), 2023 — D

Pre/post observed states: full_price / full_price. Pre/post gaps: 1054.75 / 181.948218 days. Surrounding interval: 1243.698218 days. Observed counts pre/in/post: 1/0/1.

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| pre | 1 | 2021-01-01T00:00:00Z | 3.99 | 3.99 | 0 | USD | full_price |
| post | 0 | 2024-05-28T16:45:26Z | 0.99 | 0.99 | 0 | USD | full_price |

Only the listed timestamps establish observed prices. Missing intervals and an absent side remain unresolved.

### D with one of the longest observed surrounding intervals: Sid Meier's Civilization® V (8930), 2023 — D

Pre/post observed states: full_price / discount. Pre/post gaps: 1054.75 / 166.969248 days. Surrounding interval: 1228.719248 days. Observed counts pre/in/post: 1/0/15.

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| pre | 29 | 2021-01-01T00:00:00Z | 29.99 | 29.99 | 0 | USD | full_price |
| post | 28 | 2024-05-13T17:15:43Z | 7.49 | 29.99 | 75 | USD | discount |

Only the listed timestamps establish observed prices. Missing intervals and an absent side remain unresolved.

### D with one of the longest observed surrounding intervals: New World: Aeternum (1063730), 2023 — D

Pre/post observed states: full_price / full_price. Pre/post gaps: 593.027627 / 321.408391 days. Surrounding interval: 921.436019 days. Observed counts pre/in/post: 2/0/9.

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| pre | 9 | 2022-04-07T17:20:13Z | 0 | 0 | 0 | USD | full_price |
| post | 8 | 2024-10-15T03:48:05Z | 59.99 | 59.99 | 0 | USD | full_price |

Only the listed timestamps establish observed prices. Missing intervals and an absent side remain unresolved.

### Possible discount end near boundary (unproven in-window persistence): FATE: The Traitor Soul (303680), 2023 — D

Pre/post observed states: discount / full_price. Pre/post gaps: 6.986539 / 0.009711 days. Surrounding interval: 13.99625 days. Observed counts pre/in/post: 26/0/14.

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| pre | 22 | 2023-11-14T18:19:23Z | 4.79 | 7.99 | 40 | USD | discount |
| post | 21 | 2023-11-28T18:13:59Z | 7.99 | 7.99 | 0 | USD | full_price |

Only the listed timestamps establish observed prices. Missing intervals and an absent side remain unresolved.

### A with an already-discounted pre-sale observation: Tycoon City: New York (9730), 2023 — A

Pre/post observed states: discount / full_price. Pre/post gaps: 78.039479 / 0.008576 days. Surrounding interval: 85.048056 days. Observed counts pre/in/post: 27/1/38.

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| pre | 55 | 2023-09-04T17:03:09Z | 3.99 | 9.99 | 60 | USD | discount |
| in_window | 54 | 2023-11-21T18:30:17Z | 4.99 | 9.99 | 50 | USD | discount |
| post | 53 | 2023-11-28T18:12:21Z | 9.99 | 9.99 | 0 | USD | full_price |

Only the listed timestamps establish observed prices. Missing intervals and an absent side remain unresolved.

### A with an already-discounted pre-sale observation: Grass Simulator (331200), 2023 — A

Pre/post observed states: discount / full_price. Pre/post gaps: 92.011852 / 0.005162 days. Surrounding interval: 99.017014 days. Observed counts pre/in/post: 25/1/20.

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| pre | 35 | 2023-08-21T17:42:56Z | 3.24 | 4.99 | 35 | USD | discount |
| in_window | 34 | 2023-11-21T18:17:49Z | 2.49 | 4.99 | 50 | USD | discount |
| post | 33 | 2023-11-28T18:07:26Z | 4.99 | 4.99 | 0 | USD | full_price |

Only the listed timestamps establish observed prices. Missing intervals and an absent side remain unresolved.

### A with an already-discounted pre-sale observation: Railway Islands 2 - Puzzle (2621900), 2025 — A

Pre/post observed states: discount / full_price. Pre/post gaps: 6.985394 / 0.059907 days. Surrounding interval: 14.045301 days. Observed counts pre/in/post: 42/1/4.

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| pre | 21 | 2025-09-22T17:21:02Z | 2.24 | 4.99 | 55 | USD | discount |
| in_window | 20 | 2025-09-29T21:02:25Z | 0.69 | 4.99 | 86 | USD | discount |
| post | 19 | 2025-10-06T18:26:16Z | 4.99 | 4.99 | 0 | USD | full_price |

Only the listed timestamps establish observed prices. Missing intervals and an absent side remain unresolved.

An early post-sale full price following a pre-sale discount is consistent with a discount ending near the boundary, but cannot establish when it began/ended or its persistence inside the event. A pairs directly establish an observed discount; an already-discounted pre-state does not establish a sale-triggered change or formal Valve event enrollment.

### Every conflicting same-timestamp group

| AppID | Name | Raw index | UTC timestamp | Price | Regular | Cut | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 115320 | Prototype 2 | 100 | 2021-02-01T18:27:46Z | 39.99 | 39.99 | 0 | full_price |
| 115320 | Prototype 2 | 101 | 2021-02-01T18:27:46Z | 19.99 | 19.99 | 0 | full_price |
| 115320 | Prototype 2 | 97 | 2021-02-11T20:54:12Z | 13.19 | 39.99 | 67 | discount |
| 115320 | Prototype 2 | 98 | 2021-02-11T20:54:12Z | 6.59 | 19.99 | 67 | discount |
| 115320 | Prototype 2 | 95 | 2021-02-15T18:32:13Z | 39.99 | 39.99 | 0 | full_price |
| 115320 | Prototype 2 | 96 | 2021-02-15T18:32:13Z | 19.99 | 19.99 | 0 | full_price |
| 234490 | Rush Bros. | 49 | 2021-01-01T00:00:00Z | 9.99 | 9.99 | 0 | full_price |
| 234490 | Rush Bros. | 50 | 2021-01-01T00:00:00Z | 0.99 | 9.99 | 90 | discount |
| 363890 | RPG Maker MV | 63 | 2023-09-28T17:19:58Z | 7.99 | 79.99 | 90 | discount |
| 363890 | RPG Maker MV | 64 | 2023-09-28T17:19:58Z | 0 | 0 | 0 | full_price |
| 1785150 | Friends vs Friends | 72 | 2023-09-14T17:05:26Z | 4.99 | 9.99 | 50 | discount |
| 1785150 | Friends vs Friends | 73 | 2023-09-14T17:05:26Z | 0 | 0 | 0 | full_price |

Tied conflicts are retained, not deduplicated or ordered as simultaneous start/end transitions. Zero price with zero regular and cut=0 remains the existing parser’s full-price observation; this arithmetic classification does not establish free-game status or what Steam offered throughout an interval.

### Repeated consecutive states and full-price changes

| Pattern | AppID | Raw index | UTC timestamp | Price | Regular | Cut |
| --- | --- | --- | --- | --- | --- | --- |
| Identical state across adjacent timestamp groups | 115320 | 99 | 2021-02-11T18:56:54Z | 13.19 | 39.99 | 67 |
| Identical state across adjacent timestamp groups | 115320 | 97 | 2021-02-11T20:54:12Z | 13.19 | 39.99 | 67 |
| Identical state across adjacent timestamp groups | 234490 | 50 | 2021-01-01T00:00:00Z | 0.99 | 9.99 | 90 |
| Identical state across adjacent timestamp groups | 234490 | 48 | 2021-02-11T18:34:11Z | 0.99 | 9.99 | 90 |
| Full price with changed values | 38210 | 77 | 2021-01-05T18:51:19Z | 0.99 | 0.99 | 0 |
| Full price with changed values | 38210 | 76 | 2021-01-14T20:07:11Z | 2.99 | 2.99 | 0 |
| Full price with changed values | 38210 | 48 | 2022-08-29T17:54:08Z | 2.99 | 2.99 | 0 |
| Full price with changed values | 38210 | 47 | 2023-03-31T15:10:14Z | 3.99 | 3.99 | 0 |
| Full price with changed values | 218740 | 47 | 2021-11-01T18:00:30Z | 9.99 | 9.99 | 0 |
| Full price with changed values | 218740 | 46 | 2021-11-08T15:33:11Z | 19.99 | 19.99 | 0 |

No observed null/ambiguous deal records occur in this pilot’s analyzed histories. Synthetic tests retain such records without assigning full price. Same-timestamp price conflicts are distinct from a malformed/null individual deal.

## L. Implications for negative-label feasibility

**DIAGNOSTIC INTERPRETATION:** direct discounted observations exist for 175 pairs. The other 125 pairs have varying surrounding evidence, including pre-sale discounts and completely absent histories. Recent full-price evidence only establishes an earlier observation. Even equal full prices on both sides do not exclude an unobserved intervening discount. B’s one in-window full-price timestamp also does not prove absence of a discount elsewhere in the event. Coverage and state persistence require independent justification before any final negative label. Convenient class balance supplies none.

## M. Unresolved methodological questions

- What capture/completeness evidence would justify any price-state reconstruction?
- How should polling latency, corrections, same-time variants and initialized records be treated?
- What event-wide evidence can support absence of a discount, beyond a single full-price timestamp?
- Can surrounding observations contribute to coverage, and under which independently justified assumptions?
- How should missing/ambiguous records, long gaps, censoring and unknown release hours affect later UNKNOWN decisions?
- Which metadata can be verified as available before each event, without leakage?

No threshold, persistence policy or labeling rule is finalized. Formal Valve enrollment remains outside the observed-discount target. The diversity pilot is diagnostic, not a population-representative sample.

## N. Validation and reproducibility results

Run `python3 src/05_investigate_sale_coverage.py --verify` to execute the full offline test suite and repeated complete diagnostics under a socket/DNS prohibition. A normal run reads only local files and reuses execution checks only if source and protected-input fingerprints match. No credentials or extra dependencies beyond the standard library are needed.

| Check | Result |
| --- | --- |
| unique_pairs | True |
| all_expected_years | True |
| exact_boundaries | True |
| temporal_partitions | True |
| nearest_observations | True |
| missing_and_ambiguous_preserved | True |
| conflicts_detected | True |
| gap_calculations | True |
| diagnostic_patterns | True |
| chronological_raw_provenance | True |
| categories_and_in_window_raw_records_unchanged | True |
| sensitivity_reconciled | True |
| no_final_label_columns | True |
| no_2026_observations | True |
| saved_csv_round_trip | True |
| prior_artifacts_hashes_unchanged | True |
| phase4_hashes_unchanged | True |
| preserved_baseline_verified | True |
| diagnostic_network_attempts | 0 |
| itad_pricing_api_requests | 0 |
| new_histories | 0 |

| Execution check | Result |
| --- | --- |
| deterministic_full_runs | PASS: all four outputs identical in two complete runs |
| errors | 0 |
| failures | 0 |
| full_offline_test_suite | PASS |
| network_requests | 0 |
| skipped | 0 |
| tests_run | 62 |

Before/after SHA-256 inventories match for **133 protected prior-phase files**, including **107 frozen Phase 4 inputs**. Both inventories and output hashes are in [the validation receipt](autumn_sale_coverage_validation.json). Phase 5A/5A.1 outputs, original baseline and all raw caches remain unchanged. Saved CSVs are parsed back and reconciled to generated diagnostics; sensitivity subsets reconcile to pair-level raw indices. Missing values use empty CSV cells, not zero; JSON arrays use `[]`.

**Zero diagnostic network attempts or requests; zero ITAD/pricing API calls; zero new histories.** Documentation-only research was separate from diagnostic execution; web-tool underlying HTTP totals are unavailable. No claims of a total external HTTP request count are made.

**STOP: Phase 5B.1 completed pending human review. Phase 5B.2 has not started. No final labels, features or trained models exist.**
