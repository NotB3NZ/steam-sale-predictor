# Data sources and observation units

**Retrospective descriptive EDA conducted after model development.** All sources are local frozen artifacts. No provider requests were made.

| Chart | Source | Unit and time scope |
| --- | --- | --- |
| 01 | `data/cohorts/cohort_2000.csv` | Source-reported release year, one value per original game |
| 02 | `reports/cohort_2000_modeling/modeling.csv` | `last_observed_price`, 2025 rows; one recorded USD amount per game; timestamp strictly before 2025-09-29T17:00:00Z |
| 03 | Same frozen modeling CSV | `prior_price_record_count`, 2025 rows; one pre-cutoff count per game, including zero |
| 04 | Same frozen modeling CSV | Frozen `discount_observed` labels; one row per game/year, 2023–2025 |
| 05 | Same frozen modeling CSV | Sum of three frozen labels per AppID; each game counted once |
| 06 | `reports/cohort_2000_labelability/evidence_records.csv` | Explicit `cut` in valid discounted Steam/USD raw records inside the three sale windows; `timestamp_shop_conflicts.csv` flags excluded conflicting observations |
| 07 | Frozen modeling CSV and `feature_provenance.json` | Prior count and frozen label for the same year; each historical cutoff applied separately |
| 08 | Frozen modeling CSV and `feature_manifest.json` | Null cells per approved predictor in 6,000 historical game-year rows; checked against `missingness.csv` |

The original caches pinned by `input_manifest.json` provide read-only validation of all 2,000 histories, 6,000 saved count/provenance pairs, every saved sale record, and the 2025 last recorded prices. The existing Phase 5A.1 observation parser is reused unchanged; no labels, features or predictions are regenerated. Saved observations retain their original raw-index units. The sale-record CSV is not a complete history table; it contains only directly timestamped in-window observations.

Price histogram bins are $10 wide from $0 through $200, with the final upper boundary inclusive. Zero-dollar observed amounts and $199.99 remain included. Missing prices are omitted and counted separately, with their documented missing reasons in `prices_by_game.csv`. There is no top-coding, clipping, invented regular price or substitution of the master dataset's contemporary price. All values are nominal USD, without inflation adjustment.

Observation-count bins are ten records wide and include zero. No missing count is replaced by zero. Raw duplicate observations are retained by the existing definition; counts are not unique sales. The observation source collection begins at the requested boundary 2021-01-01T00:00:00Z, which does not establish complete coverage thereafter.

Discount histogram bins are ten percentage points wide from 0 to 100, left-inclusive/right-exclusive except the final bin includes 100. Only positive explicit discounts with valid USD money and price below regular price are included. Full-price records, ambiguous/null/malformed monetary fields, non-USD records and same-time conflicts are excluded if present. Exact data-specific exclusion counts and original raw indices are in `discount_exclusions.csv`. The source has no identical duplicate sale-record payloads; records remain discrete observations, without daily interpolation. Repeated games and multiple records per game are not independent units.

## Historical windows and development roles

| Year | Role | Predictor timestamps strictly before / label window start inclusive | Label window end exclusive |
| --- | --- | --- | --- |
| 2023 | Development | 2023-11-21T18:00:00Z | 2023-11-28T18:00:00Z |
| 2024 | Development | 2024-11-27T18:00:00Z | 2024-12-04T18:00:00Z |
| 2025 | Held-out evaluation | 2025-09-29T17:00:00Z | 2025-10-06T17:00:00Z |

A→“Discount observed”; B/D→“No discount observed”; C remains Unknown under the frozen rule, and there are no C rows in this dataset. The frozen binary modeling view is used, not Phase 6A's separate conservative labelability eligibility target. No discount observed means absent evidence in available observations, not proof of nonparticipation.

`predictor_dictionary.csv` preserves all 15 approved definitions and missing-value meanings. Source hashes and versions accompany the report. Existing Phase 7B/8C styling is reused through `src/plotting_style.py`, with larger text and simple audience-friendly titles/takeaways. None of their figures or source artifacts are changed.
