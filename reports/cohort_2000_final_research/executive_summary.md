# Can Machine Learning Predict a Steam Sale?

*Here's what happened when I tried.*

The idea was appealing: use earlier game prices and discount patterns to predict what happens during a Steam Autumn Sale. The investigation produced a useful model—and a harder question about what the data actually measured.

It began with a 100-game diagnostic pilot, then expanded through frozen nested selections to 2,000 games. Historical Steam records came from IsThereAnyDeal, with raw responses and collection receipts preserved. Failed requests, rate limits and successful empty histories were kept distinct. Getting a response was not the same as getting a complete pricing history.

The central decision was to predict **recorded discount evidence**, rather than claim independently verified sale participation. A qualifying in-window discount became label 1. Full-price-only evidence or no in-window observations became an operational zero. That zero means “no discount observed,” not “this game definitely did not go on sale.”

The same games contributed 6,000 historical rows across 2023–2025. Development trained on 2023 and compared four predefined models on 2024. XGBoost was selected by 2024 average precision, before the held-out 2025 prediction pass. A fresh 2023–2024 fit then achieved **91.4% accuracy against the 2025 operational labels**, with average precision **0.9479** and Brier score **0.0703**. The evaluation covered a later event for previously represented games, not completely unseen titles.

Then the diagnostics complicated the headline. Historical observation count and XGBoost score were strongly associated: Spearman correlation **0.8972 in 2025** and **0.8925 in the later 2026 scores**. Dense histories went with more positive evidence labels and higher predictions. This does not prove coverage causes discounts, or that the model learned only data availability. It does show why good aggregate accuracy cannot settle the underlying participation question.

The saved 2026 output contains **1,026 predicted positives and 974 predicted operational zeros** among the original 2,000 games. Mean probability is **0.4996**; median is **0.7096**. All **336 games with missing predictors** received predicted operational zero, while another **638** zero predictions had complete inputs.

Those outputs are **retrospective event-time-filtered predictions using post-cutoff-collected historical data**. The feature cutoff was **2026-10-01T17:00:00Z**, but all history receipts were collected afterward. Provider availability before that cutoff cannot be established. **No independently verified 2026 outcome evaluation has been conducted.** These are neither prospective forecasts nor confirmed results.

The most defensible conclusion is that historical pricing observations helped predict later **recorded evidence** for this cohort. Reliable prospective prediction of independently verified Steam sale participation remains unestablished. The final EDA was conducted after modeling and cannot be used to revise the frozen results.

Read the [complete story](narrative_research_report.md), the [technical appendix](technical_appendix.md), or the [documented chronology](research_timeline.md). All findings reuse frozen artifacts; this synthesis conducts no new collection, training, inference or experiments. Known artifact discrepancies remain documented and unrepaired.
