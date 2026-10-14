# Phase 8C — 2026 prediction visualizations

**Retrospective event-time-filtered predictions using post-cutoff-collected historical data.**

Eight separate 300-DPI PNGs use only the existing frozen Phase 8B XGBoost prediction CSV and feature/missingness/coverage diagnostics, plus frozen historical operational labels. Exactly 2,000 games are retained. No model is loaded, trained, queried, tuned, or changed; no new predictions or outcome labels are generated. The threshold remains 0.50.

**Cutoff: 2026-10-01T17:00:00Z. Provider availability before cutoff cannot be established. Operational zeros do not prove nonparticipation. No independent 2026 outcome evaluation has been conducted.**

## Figure index

| Figure | File | Recommended |
| --- | --- | --- |
| Predicted probability histogram | [01_probability_histogram.png](01_probability_histogram.png) | Yes |
| Historical operational rates versus 2026 predicted rate | [02_historical_and_predicted_rates.png](02_historical_and_predicted_rates.png) | Yes |
| Top ten games | [03_top_10_games.png](03_top_10_games.png) | Supplement |
| Bottom ten games | [04_bottom_10_games.png](04_bottom_10_games.png) | Supplement |
| Historical count versus predicted probability | [05_observation_count_vs_probability.png](05_observation_count_vs_probability.png) | Yes |
| Predicted positive rate by observation coverage | [06_positive_rate_by_coverage.png](06_positive_rate_by_coverage.png) | Yes |
| Probability distribution by observation coverage | [07_probability_by_coverage.png](07_probability_by_coverage.png) | Supplement |
| Missingness versus predicted class | [08_missingness_vs_predicted_class.png](08_missingness_vs_predicted_class.png) | Yes |

See [figure_captions.md](figure_captions.md), [figure_captions.csv](figure_captions.csv), [figure_index.csv](figure_index.csv), and [key_findings.md](key_findings.md). Every figure embeds the retrospective warning. White backgrounds, DejaVu Sans, minimal gridlines/borders, and restrained colors reuse `src/plotting_style.py` from Phase 7B. Predicted positives use Phase 7B XGBoost green; operational zeros use gray; historical observed rates use blue. Coverage groups have consistent gray/blue/orange/green colors.

## Supporting data

- `prediction_distribution.csv`: totals and full score/observation distribution summaries (population SD; pandas linear-interpolated quantiles).
- `probability_histogram.csv`: twenty fixed bins, left-inclusive/right-exclusive except the last bin includes 1.00.
- `historical_and_predicted_rates.csv`: 2023–2025 observed operational labels and separate 2026 predicted classes.
- `coverage_summary.csv`: 0, 1–9, 10–29, 30+ groups; sample sizes, predicted counts, rates, missing-vector counts, score/count summaries.
- `top_10_games.csv`, `bottom_10_games.csv`: saved-score ranks, ascending AppID ties; no outcome verification.
- `missingness_by_predicted_class.csv`: all 15 predictors, class denominators, missing counts and percentages.
- `missingness_patterns.csv`, `missingness_status_summary.csv`, `missingness_coverage_summary.csv`: exact null patterns, counts, class and score/count distributions.
- `missing_predictor_games.csv`: all 336 affected games, including observation counts, scores, classes and null names; sourced from saved prediction diagnostics.
- `input_checksums.json`: actual frozen-input hashes. `source_integrity_notes.json`: the proven preexisting prediction-CSV order/two-name serialization discrepancy, with original/current hashes. `figure_manifest.json`: PNG dimensions, DPI, background checks and hashes. `checksums.json`: all delivered files except itself.
- `reproduction.json`: independent render and byte comparisons. `validation.json`: guards, frozen-data reconciliation, dependency versions, code hashes and integrity. `phase_start_checksums.json`: phase-start snapshot. `offline_test_results.json`: test receipt.

Rate fields named `predicted_positive_rate` and `positive_rate` are proportions from 0 to 1; plot annotations use percentages. Predicted rates are not actual sale participation rates. Missing CSV cells remain null; none are converted to zeros. Count fields describe historical observations, not sale outcomes. Mean/median probabilities are descriptive saved model scores.

## Reproduce offline

From the repository root, use a **fresh destination**; existing directories are refused:

```sh
env -u ITAD_API_KEY PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp \
  /usr/bin/python3 -B src/visualize_cohort_2026.py \
  --output-dir reports/cohort_2000_2026_visualizations_reproduction

env -u ITAD_API_KEY PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp \
  /usr/bin/python3 -B tests/run_visualization_2026_offline.py \
  --artifacts reports/cohort_2000_2026_visualizations \
  --results /private/tmp/steam-phase8c-tests.json
```

The generator checks frozen Phase 8B and historical input manifests, proves the prediction CSV's preexisting order/two-name serialization discrepancy by reproducing its original hash in memory, reconciles every figure source against saved summaries, and independently renders all figure/summary payloads again in temporary runtime storage. Every PNG and supporting CSV/Markdown must reproduce byte-for-byte in the recorded environment. Cross-version font/rendering changes can change PNG bytes; dependency versions are recorded.

Network, external commands, machine-learning/prediction modules and model-deserialization imports are blocked. Writes are restricted to the fresh output directory and a temporary plotting cache; bytecode writes are disabled. Test runners exclude all model-fitting tests, including synthetic refit tests from Phase 8B. The existing Phase 7B pure visualization tests may be run separately using `tests/run_visualization_offline.py`.

## Interpretation and integrity

Historical observed operational labels, 2026 predictions, historical observation coverage and verified outcomes are distinct. No verified 2026 outcomes are supplied or evaluated. See the complete [key findings, methodological limitations and source provenance caveat](key_findings.md). Two game-name edits and row reordering predate this phase; original scores/classes/membership are proven unchanged. The current prediction CSV and its stale manifest entry are preserved without repair.

All preexisting project files in the recorded phase-start snapshot must retain their bytes, including Phase 6/7/8 artifacts, models, caches, cohort files, journal entries, and protected files. The 219-file protected historical baseline remains 218/219, with the known ordering-only mismatch in `data/intermediate/autumn_sale_evidence_records.csv` preserved without repair. Phase-start preservation and historical-baseline agreement are checked separately. No HTTP requests, training, inference, tuning, threshold changes, cohort expansion, historical-data repair, or journal changes are performed.
