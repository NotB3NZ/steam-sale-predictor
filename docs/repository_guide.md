# Repository guide

Start with the [landing page](../README.md), the [executive summary](../reports/cohort_2000_final_research/executive_summary.md), or the [eight-chapter narrative](../reports/cohort_2000_final_research/narrative_research_report.md). The narrative is the authoritative account of the completed investigation; the [timeline](../reports/cohort_2000_final_research/research_timeline.md) records its chronology.

## Where things live

| Location | Purpose |
| --- | --- |
| [src/](../src/) | Numbered scripts for the original pilot; named adapters for the later cohort, temporal modeling, and figures; shared parsers and plotting style. Numbers alone are not a complete execution order. |
| [data/](../data/) | Metadata-derived catalogs, original pilot inputs, frozen nested cohorts, cached ITAD evidence, collection journals, batch receipts, and archived checkpoints. |
| [models/](../models/) | Original **100-game pilot** fits. These are not the selected 2,000-game classifier. |
| [reports/](../reports/) | Pilot reports at the top level; cohort-specific folders contain final datasets, model fits, evaluations, predictions, figures, and research synthesis. |
| [tests/](../tests/) | Historical regression suites and separate offline runners. Some fit synthetic models or regenerate outputs; use the new public check for verification only. |
| [scripts/](../scripts/) | The independent public verifier and its explicitly scoped current-state baseline. No collection, training, or plotting entry point is imported. |
| [docs/](./) | Current navigation, reproduction instructions, change control, and dated integrity clarification. |

## Authoritative final artifacts

| Research object | Source |
| --- | --- |
| Original 2,000 AppIDs | [cohort_2000.csv](../data/cohorts/cohort_2000.csv) and its [selection provenance](../data/cohorts/cohort_2000.provenance.json) |
| Historical evidence policy and labels | [Operational-label audit](../reports/cohort_2000_operational/README.md) |
| 6,000-row modeling table, 15 predictors, temporal protocol | [Frozen modeling data](../reports/cohort_2000_modeling/README.md) |
| Selection and 2025 held-out results | [Model report](../reports/cohort_2000_models/README.md), [selection receipt](../reports/cohort_2000_models/selection.json), and [held-out metrics](../reports/cohort_2000_models/held_out_metrics.json) |
| Evaluated selected pipeline | [selected_model.joblib](../reports/cohort_2000_models/selected_model.joblib): fitted on 2023–2024, evaluated on 2025 |
| Model cards and diagnostic figures | [Phase 7B](../reports/cohort_2000_visualizations/README.md) |
| 2026 cutoff and provider-availability audit | [Phase 8A](../reports/cohort_2000_2026_feasibility/README.md) |
| Separate 2023–2025 refit and saved 2026 scores | [Phase 8B](../reports/cohort_2000_2026_predictions/README.md), including `refit_2023_2025_pipeline.joblib` and `predictions_2026.csv` |
| Prediction figures | [Phase 8C](../reports/cohort_2000_2026_visualizations/README.md) |
| Post-modeling descriptive EDA | [Phase 8D](../reports/cohort_2000_eda/README.md) |
| Final research story and technical details | [Phase 9A](../reports/cohort_2000_final_research/README.md) |

Complete pipelines and separately saved components represent specific fits. Do not mix the pilot, 2023-only development fit, 2023–2024 evaluation fit, and 2023–2025 refit. The 91.4% result belongs to the evaluation fit and operational labels; it is not an outcome score for the 2026 refit.

## Historical workflows and documentation

The original pilot contains 100 games and 300 historical rows. It remains valuable research history, but its results differ from the final 2,000-game experiment. [Pilot selection](../reports/pilot_sample_report.md) and [pilot comparison](../reports/autumn_sale_model_comparison.md) retain that context.

[PROJECT_CONTEXT.md](../PROJECT_CONTEXT.md), [PROJECT_STATUS.md](../PROJECT_STATUS.md), and [SCALABLE_PIPELINE_REPORT.md](../SCALABLE_PIPELINE_REPORT.md) describe earlier checkpoints and plans. Statements about unstarted expansion, game-disjoint evaluation, evidence exclusions, or future collection are **historical**, not instructions defining the final experiment. The final cohort protocol uses the same 2,000 games in chronological years. Phase numbers were reused for pilot and cohort work.

The root README was replaced during finalization. Frozen Phase 9A passages referring to its earlier status describe the version at commit `dbcfd72`; they do not describe today's landing page. Retired authorization workflows, failed checkpoints, journals, and archived baselines remain preserved. The empty local `notebooks/` directory is not a tracked research component.

## Configuration and preservation

- [requirements-scalable.txt](../requirements-scalable.txt) includes the pinned direct research dependencies through the baseline/ensemble requirement files. The minimal `requirements.txt` alone does not install the complete research stack.
- [.env.example](../.env.example) names `ITAD_API_KEY`; only optional live collection needs it. The collector reads the process environment, not this file automatically.
- [Sale calendar](../src/autumn_sale_calendar.json), cohort manifests, model configurations, and integrity receipts are frozen research inputs.
- [.gitignore](../.gitignore) excludes local environments, metadata snapshots, and credential variants. It does not untrack existing research files.

Use the [reproduction guide](reproduction.md) for execution effects, and the [integrity addendum](integrity_addendum_2026-10-15.md) for known discrepancies. No directory moves or scientific refactors were performed.
