# Autumn Sale In-Window Evidence Audit — Phase 5A

**Exploratory audit completed; pending human review. No final labels or coverage rules.**

## Scope and overall results

Pilot games: **100**. Expected pairs: **200**. Actual rows considered: **200**. Successfully analyzed pairs: **200**. Actual in-window records: **238**.

| Cache/parse diagnostic | Games/records |
| --- | --- |
| Missing cache files (games) | 0 |
| Unreadable cache files (games) | 0 |
| Invalid JSON/wrapper/provenance (games) | 0 |
| Games with record parsing failures | 0 |
| Record parsing failures | 0 |
| Non-Steam records excluded | 0 |
| Empty successful histories | 3 |

All pilot games satisfy the existing release-date cutoff for both years. No games were silently dropped. The 100-game pilot is a diagnostic diversity sample; these results do not estimate population participation.

## Canonical dates and boundary convention

Dates are read from `PROJECT_CONTEXT.md`, not from external sources. The repository supplies calendar dates, without exact sale hours or a sale timezone. This audit uses both endpoint dates inclusively in UTC: start midnight <= timestamp < midnight after the end date. This is a documented calendar-date convention, not verification of exact live sale hours. Original offsets are preserved; comparisons use timezone-aware UTC instants.

| Year | Canonical start | Canonical end (inclusive) | UTC start | UTC end (exclusive) |
| --- | --- | --- | --- | --- |
| 2023 | 2023-11-21 | 2023-11-28 | 2023-11-21T00:00:00Z | 2023-11-29T00:00:00Z |
| 2024 | 2024-11-27 | 2024-12-04 | 2024-11-27T00:00:00Z | 2024-12-05T00:00:00Z |

Before means strictly earlier than start midnight. After means at or later than end-exclusive midnight. Gap days are elapsed seconds / 86,400 relative to those boundaries, not rounded calendar-day distances. An observation at end-exclusive midnight has an after-gap of zero. Full-price records on the documented sale end date may be post-sale-hour observations. No hour boundary is silently substituted and no boundary sensitivity establishes coverage.

## Actual cached schema and extraction semantics

Phase 4 wrapper fields are `steam_appid`, `itad_game_id`, `request_configuration`, `lookup_response`, `history_response`, `collection_metadata`, `lookup_evidence`, and `history_evidence`. `history_response` is an array, and `history_evidence.body` contains its original JSON response text; agreement is verified before analysis. The manifest mapping, record count, collection status and request configuration are checked.

Every observed record has exactly `timestamp`, `shop`, and `deal`. `shop` is `{id: 61, name: "Steam"}`. Every observed deal has exactly `price`, `regular`, and `cut`; each price object contains `amount`, `amountInt`, and `currency`. All currencies are USD. There is no separate deal-active/status flag. Full price is represented by a non-null deal with cut zero and equal price/regular amounts. The existing Phase 4 contract permits null deals but assigns them no sale meaning. There are no null/missing deal records in this pilot, so their empirical semantics cannot be investigated here.

A timestamp-usable observation has an explicitly parsed timezone and integer Steam shop ID 61. Such observations count as records even when deal information is null or ambiguous. Price-usable observations require finite nonnegative price/regular amounts, matching currency, and explicit cut in [0,100]. A descriptive discount requires cut > 0 and price < regular; full price requires cut = 0 and price = regular. Any missing or contradictory information is ambiguous. This validates what a record says; it does not select a sufficient number of observations or infer state between timestamps. Zero-price/equal-zero-regular records are retained as reported cut-zero observations, with no claim about permanent free-to-play status.

## Descriptive evidence categories

| Category | Description |
| --- | --- |
| A | At least one directly observed in-window discount |
| B | In-window records exist and every record shows full price |
| C | In-window records exist; no discount and some ambiguous/null information |
| D | No directly timestamped in-window records |

Category A takes precedence if any directly discounted observation exists, even alongside full-price or ambiguous records. B requires all timestamp-usable in-window records to show full price; full-price plus ambiguous records without a discount are C. These letters are evidence descriptions, not 1/0/UNKNOWN labels. Unreadable/invalid/partial inputs have a blank category, rather than being presented as an audited D.

| Year | Games analyzed | Any records | Zero records | A | B | C | D | Pairs with any ambiguous record | Pairs with null deal | Mixed discount/full |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2023 | 100 | 63 | 37 | 55 | 8 | 0 | 37 | 0 | 0 | 54 |
| 2024 | 100 | 64 | 36 | 60 | 4 | 0 | 36 | 0 | 0 | 56 |

| Year | In-window records | Discount records | Full-price records | Ambiguous | Null deals |
| --- | --- | --- | --- | --- | --- |
| 2023 | 118 | 55 | 63 | 0 | 0 |
| 2024 | 120 | 60 | 60 | 0 | 0 |

## In-window record density

Statistics include zero-observation games. Quartiles use inclusive interpolation. No density cutoff is adopted.

| Year | N | Min | Q1 | Median | Mean | Q3 | Max |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2023 | 100 | 0 | 0.0 | 2.0 | 1.18 | 2.0 | 3 |
| 2024 | 100 | 0 | 0.0 | 2.0 | 1.2 | 2.0 | 2 |

| Observation count | 2023 | 2024 |
| --- | --- | --- |
| 0 | 37 | 36 |
| 1 | 9 | 8 |
| 2 | 53 | 56 |
| 3 | 1 | 0 |

### Endpoint-date observations

| Year | Records on start date | Records on end date | B cases only on end date |
| --- | --- | --- | --- |
| 2023 | 53 | 61 | 6 |
| 2024 | 59 | 60 | 4 |

## Before/after gaps — contextual diagnostics only

Nearest usable here means nearest timestamp-usable Steam observation; it does not require an interpretable deal. The deal status/kind and raw JSON remain explicit, so null contextual evidence would never imply full price. All ties at the nearest timestamp are retained in contextual JSON; the scalar representative uses the lowest raw array index, without choosing a preferred price. No preceding observation is carried into the window. Missing surrounding observations stay blank and are excluded from gap statistics, never treated as zero.

| Year | Subset | Side | Missing | N | Min days | Q1 | Median | Mean | Q3 | Max days |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2023 | all analyzed pairs | before | 4 | 96 | 0.231424 | 19.02831 | 84.275666 | 269.863633 | 242.146484 | 1054.0 |
| 2023 | all analyzed pairs | after | 23 | 77 | 0.211366 | 14.763773 | 22.805428 | 53.100637 | 22.950752 | 954.21897 |
| 2023 | zero in-window pairs | before | 3 | 34 | 18.272002 | 138.032005 | 982.72559 | 665.964455 | 1054.0 | 1054.0 |
| 2023 | zero in-window pairs | after | 22 | 15 | 15.304329 | 22.835961 | 23.160104 | 201.346706 | 342.978929 | 954.21897 |
| 2024 | all analyzed pairs | before | 3 | 97 | 0.237106 | 21.278681 | 63.278634 | 336.347452 | 351.219271 | 1426.0 |
| 2024 | all analyzed pairs | after | 24 | 76 | 0.761701 | 14.854398 | 14.913814 | 36.280797 | 15.096207 | 623.073634 |
| 2024 | zero in-window pairs | before | 3 | 33 | 15.23515 | 267.234097 | 1323.331134 | 870.674448 | 1426.0 | 1426.0 |
| 2024 | zero in-window pairs | after | 24 | 12 | 14.854398 | 15.175492 | 97.866209 | 164.717813 | 172.805949 | 623.073634 |

## All full-price-only cases (category B)

Each has exactly one directly timestamped full-price observation. This list describes observed records only; none is a negative label. Endpoint dates have no verified hour boundary in the repository.

| Year | AppID | Name | UTC timestamp | Price | Regular | Cut |
| --- | --- | --- | --- | --- | --- | --- |
| 2024 | 7830 | Men of War™ | 2024-12-04T18:17:52Z | 4.99 | 4.99 | 0 |
| 2023 | 303680 | FATE: The Traitor Soul | 2023-11-28T18:13:59Z | 7.99 | 7.99 | 0 |
| 2023 | 1158850 | The Great Ace Attorney Chronicles | 2023-11-28T20:12:20Z | 39.99 | 39.99 | 0 |
| 2024 | 1239260 | Barro F | 2024-12-04T18:48:03Z | 4.99 | 4.99 | 0 |
| 2024 | 1257270 | The Valley of Super Flowers | 2024-12-04T18:48:03Z | 4.99 | 4.99 | 0 |
| 2023 | 1836120 | QUICKERFLAK | 2023-11-28T21:06:13Z | 0.99 | 0.99 | 0 |
| 2023 | 1882420 | Learn Programming: Python - Remake | 2023-11-28T21:10:19Z | 2.99 | 2.99 | 0 |
| 2023 | 2268470 | HOPE LEFT ME | 2023-11-25T18:24:20Z | 1.99 | 1.99 | 0 |
| 2023 | 2383710 | Caveman Ransom | 2023-11-28T21:39:53Z | 4.99 | 4.99 | 0 |
| 2023 | 2621900 | Railway Islands 2 - Puzzle | 2023-11-28T21:47:40Z | 3.99 | 3.99 | 0 |
| 2023 | 2650840 | nekowater | 2023-11-21T22:39:17Z | 2.99 | 2.99 | 0 |
| 2024 | 2650840 | nekowater | 2024-12-04T18:35:54Z | 1.99 | 1.99 | 0 |

## Representative game-sale cases

Examples use only actual pilot records. “Closest”/“most distant” below rank the sum of available before and after gaps among zero-record pairs having both sides; these are relative descriptions, not coverage thresholds.

**Multiple full-price observations with no discounted evidence:** no example exists in this pilot.

**Null or ambiguous in-window deal:** no example exists in this pilot.

### Clear in-window discount: American Truck Simulator — AppID 270880, 2024

Category A; 1 directly timestamped records. Before gap: 23.280822 days; after gap: 7.763484 days.

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| in-window | 40 | 2024-11-27T20:40:30Z | 4.99 | 19.99 | 75 | USD | discount |

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| before context | 41 | 2024-11-03T17:15:37Z | 19.99 | 19.99 | 0 | USD | full_price |

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| after context | 39 | 2024-12-12T18:19:25Z | 19.99 | 19.99 | 0 | USD | full_price |

### One full-price observation: Men of War™ — AppID 7830, 2024

Category B; 1 directly timestamped records. Before gap: 0.237106 days; after gap: 14.953681 days.

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| in-window | 24 | 2024-12-04T18:17:52Z | 4.99 | 4.99 | 0 | USD | full_price |

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| before context | 25 | 2024-11-26T18:18:34Z | 0.74 | 4.99 | 85 | USD | discount |

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| after context | 23 | 2024-12-19T22:53:18Z | 0.74 | 4.99 | 85 | USD | discount |

### Mixed discounted and full-price observations: Tycoon City: New York — AppID 9730, 2023

Category A; 2 directly timestamped records. Before gap: 77.289479 days; after gap: 23.002384 days.

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| in-window | 54 | 2023-11-21T18:30:17Z | 4.99 | 9.99 | 50 | USD | discount |
| in-window | 53 | 2023-11-28T18:12:21Z | 9.99 | 9.99 | 0 | USD | full_price |

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| before context | 55 | 2023-09-04T17:03:09Z | 3.99 | 9.99 | 60 | USD | discount |

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| after context | 52 | 2023-12-22T00:03:26Z | 4.99 | 9.99 | 50 | USD | discount |

### 2023: zero records, closest two-sided context: Have a Nice Death — AppID 1740720, 2023

Category D; 0 directly timestamped records. Before gap: 18.272002 days; after gap: 22.92816 days.

No in-window observations. Surrounding prices do not establish in-window behavior.

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| before context | 47 | 2023-11-02T17:28:19Z | 24.99 | 24.99 | 0 | USD | full_price |

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| after context | 46 | 2023-12-21T22:16:33Z | 16.74 | 24.99 | 33 | USD | discount |

### 2023: zero records, most distant two-sided context: Scoregasm — AppID 202410, 2023

Category D; 0 directly timestamped records. Before gap: 1054.0 days; after gap: 954.21897 days.

No in-window observations. Surrounding prices do not establish in-window behavior.

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| before context | 2 | 2021-01-01T00:00:00Z | 4.99 | 4.99 | 0 | USD | full_price |

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| after context | 1 | 2026-07-10T05:15:19Z | 5.99 | 5.99 | 0 | USD | full_price |

### 2024: zero records, closest two-sided context: Cyberpunk SFX — AppID 1465260, 2024

Category D; 0 directly timestamped records. Before gap: 15.447743 days; after gap: 15.229676 days.

No in-window observations. Surrounding prices do not establish in-window behavior.

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| before context | 37 | 2024-11-11T13:15:15Z | 19.99 | 19.99 | 0 | USD | full_price |

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| after context | 36 | 2024-12-20T05:30:44Z | 0.99 | 19.99 | 95 | USD | discount |

### 2024: zero records, most distant two-sided context: Scoregasm — AppID 202410, 2024

Category D; 0 directly timestamped records. Before gap: 1426.0 days; after gap: 582.21897 days.

No in-window observations. Surrounding prices do not establish in-window behavior.

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| before context | 2 | 2021-01-01T00:00:00Z | 4.99 | 4.99 | 0 | USD | full_price |

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| after context | 1 | 2026-07-10T05:15:19Z | 5.99 | 5.99 | 0 | USD | full_price |

### No in-window records and absent subsequent history: A Valley Without Wind 2 — AppID 228320, 2023

Category D; 0 directly timestamped records. Before gap: 987.234965 days; after gap: unavailable days.

No in-window observations. Surrounding prices do not establish in-window behavior.

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| before context | 0 | 2021-03-08T18:21:39Z | 3.74 | 14.99 | 75 | USD | discount |

### Completely empty cached history: Monster — AppID 1894600, 2023

Category D; 0 directly timestamped records. Before gap: unavailable days; after gap: unavailable days.

No in-window observations. Surrounding prices do not establish in-window behavior.

### Three in-window observations: Workplace Fantasy — AppID 2544720, 2023

Category A; 3 directly timestamped records. Before gap: 4.35191 days; after gap: 23.016852 days.

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| in-window | 69 | 2023-11-21T15:48:33Z | 14.99 | 14.99 | 0 | USD | full_price |
| in-window | 68 | 2023-11-21T18:03:25Z | 11.99 | 14.99 | 20 | USD | discount |
| in-window | 67 | 2023-11-28T21:46:12Z | 14.99 | 14.99 | 0 | USD | full_price |

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| before context | 70 | 2023-11-16T15:33:15Z | 11.99 | 14.99 | 20 | USD | discount |

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| after context | 66 | 2023-12-22T00:24:16Z | 9.74 | 14.99 | 35 | USD | discount |

### Pilot game released on 2023 sale start date: nekowater — AppID 2650840, 2023

Category B; 1 directly timestamped records. Before gap: unavailable days; after gap: 7.356794 days.

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| in-window | 54 | 2023-11-21T22:39:17Z | 2.99 | 2.99 | 0 | USD | full_price |

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| after context | 53 | 2023-12-06T08:33:47Z | 1.99 | 1.99 | 0 | USD | full_price |

### Full-price-only evidence on 2024 end date: Men of War™ — AppID 7830, 2024

Category B; 1 directly timestamped records. Before gap: 0.237106 days; after gap: 14.953681 days.

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| in-window | 24 | 2024-12-04T18:17:52Z | 4.99 | 4.99 | 0 | USD | full_price |

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| before context | 25 | 2024-11-26T18:18:34Z | 0.74 | 4.99 | 85 | USD | discount |

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| after context | 23 | 2024-12-19T22:53:18Z | 0.74 | 4.99 | 85 | USD | discount |

## Empirical ITAD history semantics

### Observed facts

These diagnostics use all cached Steam history, not just the two sale windows. Records are sorted by UTC timestamp. Equal-time records are preserved; transitions are counted only between adjacent timestamp groups containing exactly one record each, so conflicting equal-time states have no invented order.

| Diagnostic | Count |
| --- | --- |
| All Steam records | 5568 |
| Discount records | 2783 |
| Full-price records | 2785 |
| Ambiguous records | 0 |
| Null deals | 0 |
| Equal-zero price/regular records | 9 |
| Records exactly at requested since boundary | 65 |
| Nonempty histories | 97 |
| Nonempty histories in reverse chronological array order | 97 |
| Timestamp groups containing multiple records | 6 |
| Those groups with different price states | 6 |
| Adjacent timestamp groups sharing an identical price/regular/cut state | 2 |
| Adjacent singleton-timestamp pairs | 5455 |
| Adjacent groups excluded from directional counts because of timestamp ties | 10 |
| Singleton pairs with identical price/currency (regular/cut may differ) | 3 |
| Singleton pairs with consecutive cut=0 | 59 |
| Singleton pairs with identical full-price state | 0 |

| Earlier kind | Later kind | Adjacent singleton pairs |
| --- | --- | --- |
| discount | discount | 25 |
| discount | full_price | 2687 |
| full_price | discount | 2684 |
| full_price | full_price | 59 |

Elapsed gaps between distinct adjacent timestamp groups (zero-time ties are reported separately):

| N | Min days | Q1 | Median | Mean | Q3 | Max days |
| --- | --- | --- | --- | --- | --- | --- |
| 5465 | 0.002211 | 7.004387 | 13.999745 | 26.154704 | 29.996412 | 2016.21897 |

Repeated cut-zero records occur, but unchanged normal-price states are not common in these adjacent observations. Repeated price states do occur, so a strict “every record is a price change” claim would be too strong. No empirical null/deal transitions can be examined because the caches have no null deals.

### Repeated identical price-state timestamps

**Prototype 2 — AppID 115320**

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all-history diagnostic | 99 | 2021-02-11T18:56:54Z | 13.19 | 39.99 | 67 | USD | discount |
| all-history diagnostic | 97 | 2021-02-11T20:54:12Z | 13.19 | 39.99 | 67 | USD | discount |

**Rush Bros. — AppID 234490**

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all-history diagnostic | 50 | 2021-01-01T00:00:00Z | 0.99 | 9.99 | 90 | USD | discount |
| all-history diagnostic | 48 | 2021-02-11T18:34:11Z | 0.99 | 9.99 | 90 | USD | discount |

### Consecutive full-price records with changed amounts

**Roogoo — AppID 38210**

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all-history diagnostic | 77 | 2021-01-05T18:51:19Z | 0.99 | 0.99 | 0 | USD | full_price |
| all-history diagnostic | 76 | 2021-01-14T20:07:11Z | 2.99 | 2.99 | 0 | USD | full_price |

### Conflicting records at the same timestamp

**Prototype 2 — AppID 115320**

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all-history diagnostic | 100 | 2021-02-01T18:27:46Z | 39.99 | 39.99 | 0 | USD | full_price |
| all-history diagnostic | 101 | 2021-02-01T18:27:46Z | 19.99 | 19.99 | 0 | USD | full_price |

**Prototype 2 — AppID 115320**

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all-history diagnostic | 97 | 2021-02-11T20:54:12Z | 13.19 | 39.99 | 67 | USD | discount |
| all-history diagnostic | 98 | 2021-02-11T20:54:12Z | 6.59 | 19.99 | 67 | USD | discount |

**Prototype 2 — AppID 115320**

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all-history diagnostic | 95 | 2021-02-15T18:32:13Z | 39.99 | 39.99 | 0 | USD | full_price |
| all-history diagnostic | 96 | 2021-02-15T18:32:13Z | 19.99 | 19.99 | 0 | USD | full_price |

**Rush Bros. — AppID 234490**

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all-history diagnostic | 49 | 2021-01-01T00:00:00Z | 9.99 | 9.99 | 0 | USD | full_price |
| all-history diagnostic | 50 | 2021-01-01T00:00:00Z | 0.99 | 9.99 | 90 | USD | discount |

**RPG Maker MV — AppID 363890**

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all-history diagnostic | 63 | 2023-09-28T17:19:58Z | 7.99 | 79.99 | 90 | USD | discount |
| all-history diagnostic | 64 | 2023-09-28T17:19:58Z | 0 | 0 | 0 | USD | full_price |

**Friends vs Friends — AppID 1785150**

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all-history diagnostic | 72 | 2023-09-14T17:05:26Z | 4.99 | 9.99 | 50 | USD | discount |
| all-history diagnostic | 73 | 2023-09-14T17:05:26Z | 0 | 0 | 0 | USD | full_price |

### Interpretation / hypotheses

The frequent discount-to-full-price and full-price-to-discount transitions, sparse irregular gaps, and lack of repeated unchanged normal-price records are consistent with a change-oriented history rather than a regular observation log. Some identical-state repeats and same-timestamp conflicting states show that a simple one-record-per-price-change model is incomplete. Records at the exact requested-since instant could be boundary snapshots or truncated earlier states; their original observation times cannot be inferred. These are hypotheses, not established API semantics.

The cached data alone cannot confidently distinguish event notifications, periodic polling with change retention, synthetic boundary records, corrections, or a combination. Same-timestamp conflicts could reflect correction or product/price variants, but the returned record fields do not identify the cause. The absence of a timestamp inside a window proves only that this cache has no such timestamp. It does not prove stable price, nonparticipation, complete observation, or lack of a sale.

## Audit artifacts and column definitions

- `data/intermediate/autumn_sale_evidence_audit.csv`: one row per AppID/year with explicit cache status, UTC boundaries, record/deal diagnostics, amounts, category and separate nearest before/after context.
- `data/intermediate/autumn_sale_evidence_records.csv`: one row per actual timestamp-usable in-window Steam record; raw index, original timestamp/offset, normalized UTC timestamp, shop, deal status, amounts/amountInt/currencies/cut, observation kind, issue and complete serialized raw record.
- `reports/autumn_sale_evidence_validation.json`: individual frozen-input SHA-256 before/after values, validation checks and per-game parsing/provenance diagnostics.

`in_window_record_count` includes null/ambiguous timestamp-usable records; `in_window_price_usable_count` excludes them. `in_window_ambiguous_count` includes null/missing/contradictory deals; null count is a subset. Extrema use explicitly available finite amounts/cut, never filled values; amount extrema are blank if currencies cannot be pooled. Zero is preserved. Empty evidence has blank timestamps/extrema. Context columns never contribute to the category. Raw indices are zero-based offsets into `history_response`. Duplicate timestamp records are never deduplicated. Before/after ties include all raw records in `*_tied_records_json`.

## Validation and preservation

| Validation | Result |
| --- | --- |
| All 100 pilot AppIDs, both eligible years | PASS |
| 200 unique AppID × sale_year rows | PASS |
| Timezone-aware UTC parsing and inclusive calendar-date boundaries | PASS |
| Long-file counts reconcile to audit rows | PASS |
| Discount/full/ambiguous counts reconcile | PASS |
| Only integer Steam shop ID 61 included | PASS |
| Frozen input hashes and inventory unchanged | PASS |
| Cache provenance and record parsing | PASS |
| Network/API requests | 0 |
| Final labeling/coverage decisions | NOT IMPLEMENTED |

Frozen input files checked: **107** (all raw ITAD JSON including smoke receipt/archive, three frozen intermediate CSVs, Phase 4 script/report). Every file has identical SHA-256 before/after; the file inventory is unchanged. Individual digests are in the validation receipt. No API, web, or network requests were made. The standalone audit has no network client and does not execute/import the Phase 4 collector.

Reproduce: `python3 src/04_audit_autumn_evidence.py`. Tests: `python3 -m unittest discover -s tests -v` (offline synthetic fixtures; includes Phase 4 regression tests). The report/datasets are deterministic for identical frozen inputs and canonical dates; the audit does not modify project status/context itself.

## Remaining ambiguities and stop gate

Exact sale-hour boundaries are unspecified in the repository. End-date full-price observations and mixed records must be reviewed with that limitation in mind. All B cases have only one full-price observation; whether any such case provides sufficient negative coverage remains undecided. There are no multiple-full-price-only, null, or ambiguous in-window examples in this pilot. Several histories are empty, stop long before the window, or have very distant surrounding observations. Same-timestamp conflicting records and possible requested-since boundary artifacts need later semantic review.

**Stopped after Phase 5A. Phase 4 remains COMPLETE. Phase 5A is completed/pending review. Phase 5B coverage and final labeling methodology are NOT YET IMPLEMENTED.** No labels, UNKNOWN mapping, observation sufficiency threshold, state persistence, feature engineering, or modeling changes were created.
