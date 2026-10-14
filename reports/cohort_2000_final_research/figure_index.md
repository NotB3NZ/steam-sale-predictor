# Figures selected for the narrative

Ten existing PNGs are embedded in the report using relative Markdown links. No figure is regenerated, copied or edited. Narrative figure numbers differ from the original phase numbers; the source number/location is retained below.

| Narrative figure | Chapter | Existing figure / relative source | What the reader should notice |
| --- | --- | --- | --- |
| 1 | 4 | [Phase 8D, 01 — release years](../cohort_2000_eda/01_games_by_release_year.png) | The selected cohort is concentrated in later release years; it is not a Steam census |
| 2 | 4 | [Phase 8D, 04 — annual operational evidence](../cohort_2000_eda/04_autumn_sale_evidence_by_year.png) | Positive/zero evidence counts are close, and development/held-out roles stay explicit |
| 3 | 4 | [Phase 8D, 05 — evidence across three years](../cohort_2000_eda/05_discount_evidence_across_three_years.png) | Each game contributes once; repeated evidence is distinct from verified participation |
| 4 | 6 | [Phase 7B — held-out model comparison](../cohort_2000_visualizations/held_out_model_comparison.png) | Learned models improve over the constant baseline on recorded labels; lower Brier is better |
| 5 | 6 | [Phase 7B — held-out XGBoost confusion](../cohort_2000_visualizations/held_out_xgboost_confusion.png) | Agreements and errors refer to operational labels, not verified real-world outcomes |
| 6 | 7 | [Phase 8D, 07 — historical coverage/evidence](../cohort_2000_eda/07_coverage_vs_discount_evidence.png) | More prior observations go with more positive evidence in each year; sample sizes differ |
| 7 | 7 | [Phase 7B — held-out coverage/probability](../cohort_2000_visualizations/held_out_coverage_probability.png) | Saved model scores strongly track record counts, without identifying a causal explanation |
| 8 | 8 | [Phase 8C, 01 — 2026 score histogram](../cohort_2000_2026_visualizations/01_probability_histogram.png) | A mean near one-half masks many low/high scores; calibration is not established |
| 9 | 8 | [Phase 8C, 06 — 2026 predicted rate by coverage](../cohort_2000_2026_visualizations/06_positive_rate_by_coverage.png) | These are group prediction rates, not observed participation rates |
| 10 | 8 | [Phase 8C, 08 — missingness/predicted class](../cohort_2000_2026_visualizations/08_missingness_vs_predicted_class.png) | All incomplete vectors are predicted zero, but many complete vectors are too |

## Why the other figures stay outside the main story

The report uses the four prioritized EDA figures and a small set of model/prediction diagnostics. The remaining price, observation-count, discount-size and missing-feature EDA summaries are explained with explicit units in the text and appendix, with their original plots available through the [Phase 8D index](../cohort_2000_eda/figure_index.md).

The Phase 8C historical-versus-predicted rate plot (02) would repeat the historical comparison while adding an observed/predicted distinction already explained in the final chapter. Its 2026 coverage scatter (05) would closely repeat the 2025 scatter; the later association is instead stated with its saved coefficient and the subgroup rate chart. Rankings do not advance the central methodological question, so the top/bottom games are not embedded. ROC, precision–recall and calibration curves remain available in [Phase 7B](../cohort_2000_visualizations/README.md) without adding another set of technical charts for general readers.

Original captions, numeric plot data and image manifests remain at their source locations. The report's short captions explain what to notice and the relevant limitation; they do not replace the original provenance. Image hashes are checked during [offline verification](README.md).
