# Phase 9A — narrative research synthesis

**Can Machine Learning Predict a Steam Sale? Here's What Happened When I Tried.**

*An investigation into historical game prices, discount patterns, and the challenges of predicting Steam sales.*

This report tells the completed investigation for gamers, data enthusiasts and readers new to machine learning. It is a synthesis of frozen local evidence, not a new experiment. It preserves the distinction between historical observations, operational labels, held-out evaluation, retrospective 2026 model outputs and independently verified outcomes.

## Read the report

| File | Purpose |
| --- | --- |
| [narrative_research_report.md](narrative_research_report.md) | The continuous eight-chapter story, with ten selected existing figures |
| [executive_summary.md](executive_summary.md) | A short shareable account of the result and its limits |
| [research_timeline.md](research_timeline.md) | Documented milestones, decisions, recoveries and chronology caveats |
| [technical_appendix.md](technical_appendix.md) | Dataset units, labels, features, fixed configurations, metrics and provenance |
| [figure_index.md](figure_index.md) | Every embedded figure and its original phase/location, with selection rationale |
| [README.md](README.md) | Scope, source hierarchy and offline reproduction/verification instructions |

The only additional files are [verify_report.py](verify_report.py), the standard-library offline checker, and `verification.json`, its machine-readable receipt with source/output hashes, numerical checks, link checks, word counts and preservation inventory. Figures and historical result tables are not copied into this folder as duplicate artifacts.

## Source hierarchy and chronology

Initial objectives, metadata preparation and pilot work are reconstructed from the root documentation and [source](../source_data_report.md), [catalog](../games_master_report.md), [pilot](../pilot_sample_report.md), [collection](../itad_collection_report.md), [ground-truth](../autumn_sale_ground_truth_feasibility.md) and [operational-label](../autumn_sale_operational_labeling.md) reports. [Batch receipts](../../data/cohorts/runs/2000_batch_004/collection_quality.json) and cohort-specific reports establish the completed expansion where earlier root documents still describe preparation or unstarted live work.

The quantitative cohort sources are [frozen data/protocol](../cohort_2000_modeling/README.md), [models and selection](../cohort_2000_models/README.md), [Phase 7B model cards/figures](../cohort_2000_visualizations/README.md), [2026 feasibility](../cohort_2000_2026_feasibility/README.md), [Phase 8B predictions](../cohort_2000_2026_predictions/README.md), [Phase 8C diagnostics](../cohort_2000_2026_visualizations/README.md), and [Phase 8D EDA](../cohort_2000_eda/README.md). Chapter-level research trails and the appendix link directly to the supporting artifacts.

The same phase numbers were used for some pilot and cohort activities; the timeline distinguishes them. Phase 8D EDA occurred after model development and 2026 prediction freezing. Chapter 4 introduces it earlier for reader comprehension, without implying that it selected features or tuned models. The canceled handpicked-game expansion is not included.

## Reproduce the checks without reproducing the experiments

From the repository root:

```sh
env -u ITAD_API_KEY PYTHONDONTWRITEBYTECODE=1 \\
  /usr/bin/python3 -B reports/cohort_2000_final_research/verify_report.py
```

The default is read-only: it verifies the six Markdown files and checker against the delivered receipt, source manifests and phase-start hashes. It resolves all local Markdown links and anchors, checks ten original image paths/hashes, validates reported numerical tables/statements against saved results and records no new predictions. It blocks network/subprocess activity and model imports/deserialization. It does not run earlier training, prediction, feature-generation or plot-regeneration commands. External source URLs inside older research artifacts are historical citations; they are not fetched.

To save a separate verification result outside the repository, add:

```sh
--results /private/tmp/steam-phase9a-verification.json
```

The one-time authoring command used `--phase-start-checksums /private/tmp/steam-phase9a-start-sha256.json --record` to create `verification.json` after the prose review. The delivered default does not overwrite that receipt. A different report edition would need its own authorized output namespace and preservation snapshot, not edits to earlier phase artifacts.

The report is authored prose, not a model-generated payload reconstructed by a training command. Reproducibility here means that its data-backed statements can be checked against the frozen sources, its exact text/figure bytes can be identified, and the original artifacts remain intact. Word counts in `verification.json` count whitespace-delimited visible Markdown text after removing markup, image syntax and link destinations; headings, captions and table text are included. Main-report and six-document totals are reported separately; the checker/receipt are excluded.

## Quality and methodological review

The completed review checks the eight-chapter sequence, transitions, nontechnical explanations, appropriate first-person voice, exact statistics, local figure links, source traceability, chronology and repeated limitations. The main narrative does not attribute the 2025 performance to independently verified participation or to the later 2026 refit. XGBoost selection is explicitly tied to 2024 average precision before the held-out pass.

The frozen conclusion is qualified: the project predicted later **recorded discount evidence** for represented games; verified prospective participation prediction remains unestablished. Coverage dependence is an association, not proof that coverage causes discounts or that the model learned only availability. Missing data is not a verified negative outcome. No post-modeling EDA finding revises the experiment.

**Retrospective event-time-filtered predictions using post-cutoff-collected historical data.** The 2026 cutoff is **2026-10-01T17:00:00Z**. Provider availability before cutoff cannot be established. **No independently verified 2026 outcome evaluation has been conducted.**

Historical incomplete coverage, operational label assumptions, empty histories, record density, provider backfill, source-date/timestamp ambiguities, repeated-game evaluation and retrospective cohort selection remain limits. The report makes no claim of Steam-population representativeness, unseen-game performance, causal identification or prospective accuracy.

## Artifact integrity and Phase 9B readiness

All preexisting project files in the phase-start inventory are preserved. Protected historical baseline agreement remains **218/219**, with the known ordering-only evidence-record mismatch unchanged. The separate Phase 8B prediction CSV row-order/two-name discrepancy is documented in the [appendix](technical_appendix.md) and [original Phase 8C note](../cohort_2000_2026_visualizations/source_integrity_notes.json); no repair is attempted. Current prediction bytes and the previous proof note remain pinned.

No HTTP requests, model training, tuning, new inference, label revisions, cohort expansion, new experiments, plot generation, historical artifact edits or journal changes occur in this synthesis. The narrative, supporting references and verification record are ready for Phase 9B editorial/presentation work with the scientific qualifications retained. Phase 9B work is not performed here.
