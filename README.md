# Can Machine Learning Predict a Steam Sale?

*A data science investigation into historical Steam prices, machine learning, and the limitations of incomplete pricing records.*

How much can a game's price history tell us about its next Steam sale? This investigation began with a 100-game pilot, expanded to **2,000 games**, and produced a promising model alongside an important question: how much of the signal comes from what gets recorded?

**Research question:** Can pre-sale information predict whether qualifying Steam-store discount evidence will be recorded during an Autumn Sale?

[Read the complete story](reports/cohort_2000_final_research/narrative_research_report.md) · [Executive summary](reports/cohort_2000_final_research/executive_summary.md) · [Technical appendix](reports/cohort_2000_final_research/technical_appendix.md)

## What we found

- **6,000 game-year records** cover the original cohort in 2023–2025.
- XGBoost, selected using **2024 average precision**, achieved **91.4% agreement with held-out 2025 operational labels**.
- Scores were strongly associated with historical observation coverage: Spearman **0.8972 in 2025** and **0.8925 in 2026**. This is an association, not a causal finding.
- The separate retrospective 2026 run produced **1,026 predicted positives** and **974 predicted operational zeros**. These are model outputs, not verified outcomes.

## Meet the cohort

![Release-year distribution of the original 2,000-game cohort](reports/cohort_2000_eda/01_games_by_release_year.png)

*94.2% of the selected games were released in 2015 or later. This cohort does not represent the entire Steam catalog.* [Full EDA](reports/cohort_2000_eda/README.md)

## How the models were evaluated

Fifteen approved release and historical-price predictors used observations strictly before each sale cutoff. Learned preprocessing stayed inside training data. The four predefined models used a fixed 0.50 classification threshold.

**2023 training → 2024 development/selection → fresh 2023–2024 fit → held-out 2025 evaluation.** The same games recur across years; this tests later events for represented games, not unseen-game performance. Earlier audits had inspected 2025 labels, although they were excluded from model selection.

| Model | 2025 accuracy | Average precision | Brier score ↓ |
| --- | ---: | ---: | ---: |
| Training-prior baseline | 49.15% | 0.4915 | 0.2503 |
| Logistic Regression | 87.75% | 0.9293 | 0.0889 |
| Random Forest | 89.85% | 0.9440 | 0.0798 |
| **XGBoost** | **91.40%** | **0.9479** | **0.0703** |

These metrics measure recorded discount evidence, not independently verified Steam sale participation. [Frozen evaluation](reports/cohort_2000_models/README.md)

![Held-out 2025 XGBoost confusion matrix against operational evidence labels](reports/cohort_2000_visualizations/held_out_xgboost_confusion.png)

*XGBoost agreed with 1,828 of 2,000 labels; 105 false positives and 67 false negatives account for the remaining cases.* [Model diagnostics](reports/cohort_2000_visualizations/README.md)

## The retrospective 2026 exercise

**Retrospective event-time-filtered predictions using post-cutoff-collected historical data.**

The feature cutoff was **2026-10-01T17:00:00Z**, but historical records were collected afterward. Provider availability before cutoff cannot be established. A separate refit used the frozen 2023–2025 data and selected configuration; its outcomes have not been independently evaluated.

![2026 predicted positive rates by historical observation coverage](reports/cohort_2000_2026_visualizations/06_positive_rate_by_coverage.png)

*Positive prediction rates range from 0% with no prior observations to 84.54% with 30+. Coverage does not establish actual discount participation.*

![Distribution of saved retrospective 2026 XGBoost probabilities](reports/cohort_2000_2026_visualizations/01_probability_histogram.png)

*The saved scores split into 1,026 positives and 974 operational zeros. Their distribution does not establish calibrated outcome probabilities.* [Prediction visualizations](reports/cohort_2000_2026_visualizations/README.md) · [Frozen prediction report](reports/cohort_2000_2026_predictions/README.md)

## Important limitations

Historical ITAD coverage is incomplete. **“No discount observed” does not prove a game never received a discount.** Missing predictors likewise do not verify nonparticipation. Repeated games, retrospective sampling, and unproven provider availability limit generalization. The EDA followed modeling and did not revise frozen results. **No independently verified 2026 outcome evaluation exists; these were not genuine prospective forecasts.**

## Repository and getting started

`src/` contains workflows; `data/` contains cohorts and evidence; `models/` contains pilot fits; `reports/` contains final cohort datasets, fits, findings, and figures; `tests/` contains regression suites. [Repository guide](docs/repository_guide.md)

Inspect the reports directly, or run the standard-library public check with **Python 3.9+**:

```sh
python3 -B scripts/verify_public.py
```

It requires no API key or research dependencies and writes no files. It checks tracked artifacts, headline statistics, links, and explicit integrity exceptions. [Current integrity addendum](docs/integrity_addendum_2026-10-15.md)

For installation, offline tests, training, figure reproduction, and optional ITAD recollection, follow the [reproduction guide](docs/reproduction.md). The research stack was verified on Python **3.9.6** with `requirements-scalable.txt`; Python 3.11 was not verified. Some historical workflows require ignored local inputs and cannot run from a fresh clone.

## Sources and acknowledgments

Historical pricing comes from **IsThereAnyDeal**, scoped to Steam shop 61 / US. Sale-calendar evidence is attributed to **Valve** in the frozen reports. Metadata comes from a local Steam snapshot whose acquisition details and reference date are incomplete. [Source documentation](reports/source_data_report.md)

No code license has been selected. Third-party data reuse rights are separate from code licensing; see the [licensing and source notes](docs/reproduction.md#licensing-and-source-provenance).
