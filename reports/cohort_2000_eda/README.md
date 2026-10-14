# Phase 8D — fundamental exploratory data analysis

**Retrospective descriptive EDA conducted after model development.** This accessible EDA covers the original **2,000-game cohort** and frozen **6,000 historical game-year rows (2023–2025)**. It is descriptive and cannot be used to change frozen features, models, parameters, selection, thresholds, labels, cohort membership or predictions.

**“No discount observed” means no evidence in the available records, not verified nonparticipation.** Provider availability at historical cutoffs is unproven. Development years 2023–2024 and the held-out 2025 evaluation year retain their frozen roles; inspecting them here does not authorize new tuning or evaluation.

## Eight core figures

| Figure | PNG |
| --- | --- |
| Games by release year | [01_games_by_release_year.png](01_games_by_release_year.png) |
| Prices recorded before the 2025 sale | [02_historical_price_distribution.png](02_historical_price_distribution.png) |
| How much price history is available? | [03_historical_observations_per_game.png](03_historical_observations_per_game.png) |
| Autumn Sale discount evidence by year | [04_autumn_sale_evidence_by_year.png](04_autumn_sale_evidence_by_year.png) |
| How often was a discount observed? | [05_discount_evidence_across_three_years.png](05_discount_evidence_across_three_years.png) |
| Sizes of recorded Autumn Sale discounts | [06_observed_discount_percentages.png](06_observed_discount_percentages.png) |
| More history goes with more discount evidence | [07_coverage_vs_discount_evidence.png](07_coverage_vs_discount_evidence.png) |
| Which features have missing values? | [08_missing_values_by_feature.png](08_missing_values_by_feature.png) |

Every figure has a simple question, data source, unit, factual takeaway and limitation in [figure_captions.md](figure_captions.md) and `figure_captions.csv`. All eight requested charts are supported with explicitly defined measures. PNGs are separate 300-DPI files, with white backgrounds, larger DejaVu Sans text, minimal gridlines/borders, and consistent blue/gray colors. Each chart presents one plain factual takeaway beneath its title.

See [key_findings.md](key_findings.md), [data_sources.md](data_sources.md) and [figure_index.md](figure_index.md). Each CSV named for a table supplies its chart data; `recurrence_by_game.csv`, `prices_by_game.csv`, `observation_counts_by_game.csv`, and `discount_records.csv` document the individual contributing units. `discount_exclusions.csv` records chart-only exclusions. `predictor_dictionary.csv` preserves the existing 15 definitions. Nulls remain blank, with true observed zeros retained.

The price histogram uses **one last recorded USD price per game before the 2025 sale**, not current prices or a mixture of currencies. It includes 1,918 games, omits 82 missing prices, and retains all observed extremes. The discount histogram uses **3,035 directly recorded Steam/USD discount observations inside the 2023–2025 sale windows**, excluding two conflicting same-time records and 24 full-price records from this chart only. These units differ; neither chart describes purchases, complete daily price states or guaranteed sale outcomes.

## Reproduce and test offline

From the repository root, use a **fresh destination** (existing output directories are refused):

```sh
env -u ITAD_API_KEY PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp \
  /usr/bin/python3 -B tests/run_eda_offline.py \
  --results /private/tmp/steam-eda-preflight.json

env -u ITAD_API_KEY PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp \
  /usr/bin/python3 -B src/eda_cohort_2000.py \
  --output-dir reports/cohort_2000_eda_reproduction \
  --test-results /private/tmp/steam-eda-preflight.json

env -u ITAD_API_KEY PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp \
  /usr/bin/python3 -B tests/run_eda_offline.py \
  --artifacts reports/cohort_2000_eda \
  --results /private/tmp/steam-eda-final-tests.json
```

The generator verifies the frozen modeling manifest, all pinned inputs, and saved evidence hashes, then cross-checks raw observation membership, timestamps, USD values and existing feature provenance. It reloads all source files independently for a second render: all core figures, summary CSVs and explanatory documents must reproduce byte-for-byte. Versions, input/code hashes, image metadata and preservation receipts are saved. PNG byte identity is established in the recorded dependency/font environment; other versions can change rendering bytes.

Network requests, subprocesses, model imports/deserialization and writes outside the fresh report/runtime directories are guarded. No model-fitting or inference tests run. Existing artifacts are read-only. `reproduction.json`, `validation.json`, `input_checksums.json`, `figure_manifest.json`, `phase_start_checksums.json`, and `checksums.json` record verification; test receipts accompany the report when supplied.

## Integrity and readiness

All phase-start project files, protected artifacts, historical data, Phase 6/7/8 reports/models and journal entries must retain their original bytes. The historical protected baseline's known ordering mismatch (218/219 agreement) and Phase 8B's already documented prediction CSV row-order/two-name discrepancy are recorded without repair. Predictions are not chart inputs; release metadata and AppIDs come from the original frozen cohort.

All eight charts and their supporting sources are ready for Phase 9A descriptive synthesis with their stated limitations. No EDA finding revises any frozen model or prediction result.
