# Project Context — Steam Sale Prediction

## Research Question

> Can historical Steam game metadata and pre-sale pricing behavior predict whether a Steam-store discount will be RECORDED during the Steam Autumn Sale?

The broader motivation is actual Autumn Sale discount participation. Phase 5B.3 adopts recorded discount occurrence as the operational target because historical observation coverage is incomplete; operational zero does not establish actual non-participation.

## Unit of Observation

```
one row = one game × one Autumn Sale year
```

Example:
```
appid | sale_year | discount_observed
7830  | 2024      | 0
7830  | 2025      | 1
```

## Data Sources

| Source | Role | Status |
|--------|------|--------|
| `games.csv` | Game metadata & potential predictors | Available (125,855 games) |
| ITAD historical Steam price data | Recorded-discount operational labels, not verified participation | Phase 4 frozen; Phase 5B.3 labels constructed |

## Known Data Issue

The raw `games.csv` header has a concatenated column `DiscountDLC count` that should be `Discount` + `DLC count` (header has 39 fields, data rows have 40). Both pipeline scripts use `src/source_schema.py` to correct this at load time. The original file is preserved.

## Methodological Rules

1. **Target interpretation:** `discount_observed=0` means no qualifying in-sale discount observation; never infer actual non-discounting from missing evidence. Category C remains null and flagged. True-participation negatives remain unverified; the earlier `UNKNOWN` requirement applies to that broader target, not the authorized operational definition.
2. **Raw data preservation:** Never overwrite `games.csv` or `games.json`.
3. **API caching:** Raw ITAD API responses must be cached locally.
4. **Temporal validity:** Predictors must represent information available **before** the sale being predicted.
5. **No temporal leakage:** Lifetime stats (Peak CCU, review counts, playtime, current Discount) are post-hoc snapshots — unsafe as historical predictors without reconstruction.
6. **Primary key:** Steam AppID is the identifier across all tables.
7. **Dataset before modeling:** Complete the analytical dataset before fitting any model.
8. **Pilot first:** Test the full pipeline on a small sample before scaling.
9. **Expansion evaluation:** Frozen nonpilot held-out AppIDs are excluded from development in every year. Collection approval does not authorize outcome access, labeling or model fitting; evaluation evidence requires independent private-key custody.

## Target Sale Windows

```
Autumn 2023: 2023-11-21 to 2023-11-28
Autumn 2024: 2024-11-27 to 2024-12-04
Autumn 2025: 2025-09-29 to 2025-10-06
```

Phase 5A.1 verified both event endpoints from official Valve announcements and, for 2024/2025, their official artwork. Central configuration: `src/autumn_sale_calendar.json`; source links, archived artwork hashes and verification details are in `reports/autumn_sale_evidence_audit.md`.

| Year | UTC start, inclusive | UTC end, exclusive | Pacific start/end time |
|------|----------------------|--------------------|------------------------|
| 2023 | 2023-11-21T18:00:00Z | 2023-11-28T18:00:00Z | 10 AM PST (UTC −8) |
| 2024 | 2024-11-27T18:00:00Z | 2024-12-04T18:00:00Z | 10 AM PST (UTC −8) |
| 2025 | 2025-09-29T17:00:00Z | 2025-10-06T17:00:00Z | 10 AM PDT (UTC −7) |

The experimental design is 2023–2024 historical training, 2025 temporal validation, and 2026 final retrospective prediction/manual verification. Phase 5A.1 excludes 2026 and implements only evidence diagnostics.

## Master Catalog Population

`data/intermediate/games_master.csv` is one row per Steam game, not the final game × sale-year modeling dataset. Require valid positive integer AppID, nonblank name, valid release date, and finite numeric Price > 0. Titles with source Price <= 0 are excluded from the paid-game candidate population; this does not prove permanent free-to-play status.

Optional missing metadata, zero-owner ranges, and zero Peak CCU do not disqualify games. Owner ranges remain source text. No historical-sale release cutoff is applied until event-specific construction (`release_date <= sale_start_date`). The dataset snapshot reference date is unknown; do not infer it from file timestamps or the current date.

Retention in the master catalog does not approve historical feature use. Price, Discount, DLC count, Achievements, Tags, Categories, language support, and engagement statistics are snapshots requiring later temporal assessment. Discount must never become the target. Relatively stable metadata is not guaranteed historically unchanged.

## Historical-data Pilot

Phase 3 uses a deterministic diagnostic diversity sample of 100 paid catalog entries, with `release_date <= 2023-11-21` for the whole pilot. This cutoff is pilot-specific and does not constrain later modeling populations. The pilot is not statistically representative, and its model performance must not be treated as population performance.

`pilot_*` columns describe sampling only. Snapshot price, owners, activity, and publisher portfolio diagnostics do not authorize historical feature use. Source columns and the master catalog remain unchanged. Publisher tokens and developer/publisher overlap are approximate metadata proxies, not verified publisher identity or corporate ownership.

## ITAD Collection Contract

Official ITAD API 2.11.0 documentation and OpenAPI specification verified for Phase 4. Resolve identifiers only with `GET /games/lookup/v1?appid=<Steam AppID>`; fetch raw history with `GET /games/history/v2` using the resolved UUID, `country=US`, `shops=61`, and explicit `since=2021-01-01T00:00:00Z`. Omitting since restricts history to the latest three months. Authenticate via the `ITAD-API-Key` header from process environment variable `ITAD_API_KEY`; the collector does not read the local `apikey` file or automatically load `.env`.

History records have timestamp, shop, and deal; the official schema permits `deal=null`. Preserve these records and all returned fields, including original response text, without interpreting their sale meaning. Cache wrappers live in `data/raw/itad/<AppID>.json`; configuration-compatible validated evidence is reused, and intentional refreshes archive prior artifacts. A three-game smoke receipt is required before full collection. Collection diagnostics describe observations only; event-specific coverage and sale labels remain Phase 5 work.

## Phase 5A — Preserved calendar-date evidence baseline

The original Phase 5A audit covered all 100 pilot AppIDs for Autumn 2023 and 2024 (200 game-sale pairs); 238 records were directly timestamped inside the documented calendar-date windows. Its original CSVs, report, validation receipt, implementation and context are preserved at `reports/baselines/phase_5a_calendar_window/`, with original hashes and Git revision in `baseline_manifest.json`. The original implementation reproduces all four artifacts byte-for-byte using frozen inputs in an isolated temporary directory.

Phase 5A used inclusive UTC calendar dates: start midnight through midnight after the end date, exclusive at the latter boundary. At that time exact event hours were unverified. Phase 5A.1 supersedes this convention with the verified half-open event intervals above; the baseline remains unchanged.

Timestamp-usable Steam records include null/ambiguous deals when time/shop are valid. Reported discount observations have explicit cut > 0 and price < regular; reported full-price observations have cut = 0 and equal price/regular. Missing/contradictory information is ambiguous and raw fields are retained. Descriptive A/B/C/D categories summarize only in-window records. Before/after records and gaps are separate diagnostics and do not imply state persistence or coverage. Equal-time records are preserved with raw indices; all nearest-context ties remain inspectable.

Observed categories A/B/C/D: 2023 **55/8/0/37**, 2024 **60/4/0/36**. All B cases have one full-price observation; no multiple-full-price-only or null/ambiguous in-window cases occur. Cached histories appear change-oriented, but repeats, conflicting same-time prices, sparse gaps and exact requested-since timestamps prevent confident identification of the generating process from these data alone.

## Phase 5A.1 — Exact boundaries and 2025 expansion (completed; pending human review)

`src/04_audit_autumn_evidence.py` continues reading only frozen Phase 4 caches, without importing/executing the collector or making network requests. Current outputs cover **300 unique game-sale pairs** and **178 directly timestamped in-window Steam records**. All pairs qualify under the existing date-level release rule, checked separately for each event; release dates after the start date would produce explicit ineligible rows with blank evidence category/counts. nekowater (AppID 2650840) was released on the 2023 start date; its exact release hour is unavailable and this precision limitation is explicitly reported rather than assumed resolved.

Corrected A/B/C/D counts: **2023: 55/2/0/43**, **2024: 60/0/0/40**, **2025: 60/1/0/39**. Each observed pair has one in-window record. No ambiguous/null or mixed in-window records occur. For 2023/2024, **121 records** were removed (one before exact start, 120 at/after exact end), with no additions. **Ten original B cases become D** (six in 2023, four in 2024); discount-evidence categories are unchanged. `reports/autumn_sale_boundary_comparison.md` lists every affected pair, original B case and removed record.

Current artifacts: `data/intermediate/autumn_sale_evidence_audit.csv`, `data/intermediate/autumn_sale_evidence_records.csv`, `reports/autumn_sale_evidence_audit.md`, and `reports/autumn_sale_evidence_validation.json`. **42 offline tests PASS**; isolated baseline reproduction, deterministic reruns, saved-CSV reconciliation and **107 unchanged frozen-input hashes** are recorded in `reports/phase_5a1_execution_checks.json`. Network research was confined to the official event calendar; no ITAD/pricing requests or new histories were fetched. Audit execution makes zero network requests.

Phase 4 remains COMPLETE and frozen. Phase 5A.1 created no final labels, model-ready data, feature engineering or models. Its original artifacts remain unchanged; the subsequent diagnostic investigation is documented below.

## Phase 5B.1 — Historical price-state and coverage investigation (completed; pending human review)

`src/05_investigate_sale_coverage.py` reads the same frozen histories and Phase 5A.1 calendar/parser offline. It investigates all **300 pairs**, preserving the **175 A / 3 B / 0 C / 122 D** evidence categories and all **178 in-window observations**. Full observed chronologies, pre/in/post raw indices, nearest tied records, observed states, counts, elapsed-day gaps and conflict indicators are diagnostics only. A valid temporal record can have ambiguous/null price information; such information is never replaced by an older known price. Conflicting nearest same-time records have an ambiguous aggregate state and retain all raw fields.

**2026 exclusion is strict for this investigation:** only observations timestamped before `2026-01-01T00:00:00Z` enter any context, chronology, semantics or sensitivity calculation. **852** of 5,568 cached observations are outside scope; **4,716** are analyzed. The raw files remain intact. Post-sale context is therefore censored and can differ from Phase 5A.1; missing post evidence means none was returned within the permitted observation scope, not that no later price exists.

Category B pre-state is **2 discounted / 1 missing**; Category D pre-state is **93 full price / 20 discounted / 9 missing**. No nearest ambiguous state occurs in these actual pairs. Recency scenarios at 7/14/30/60/90 days/unrestricted find **1/2/7/10/13/93** non-A pairs with pre-sale full-price evidence and **7/14/15/15/15/22** with discounted pre-evidence. Missing-pre pairs remain a separate bucket. These hypothetical scenarios quantify availability; none establishes a negative label or selects a coverage threshold. No price is carried forward, and equal observed surrounding prices do not establish what happened between them.

Official ITAD documentation reviewed for Phase 5B.1 explicitly describes price changes in the history endpoint's `since` parameter. Historical records and change-oriented behavior are supported; complete capture of every Steam change and safe state persistence are not established by the reviewed documentation. Six same-timestamp conflict groups, repeated states, changed full-price values and requested-since timestamps remain empirical caveats. Documentation-only research is separate from the network-blocked diagnostic pipeline.

Artifacts: `data/intermediate/autumn_sale_coverage_diagnostics.csv`, `data/intermediate/autumn_sale_coverage_sensitivity.csv`, `reports/autumn_sale_coverage_investigation.md`, `reports/autumn_sale_coverage_validation.json`, and `reports/sources/itad_history_semantics.json`. Run `python3 src/05_investigate_sale_coverage.py --verify` for **62 passing offline tests**, repeated deterministic executions, saved-CSV reconciliation and preservation checks for **133 prior-phase files**, including **107 frozen Phase 4 inputs**. No pricing API requests or new collection occurred.

Phase 5B.1 ended without implementing coverage or 1/0/UNKNOWN labeling methodology. The subsequent source-feasibility investigation is documented below; its original artifacts remain frozen.

## Phase 5B.2 — Historical ground-truth verification and label feasibility (completed; pending human review)

The target event is a valid Steam-store discount at **any point** within the verified half-open Autumn Sale interval. Positive occurrence evidence and complete-event absence evidence require different standards. Single full-price observations, sampled snapshots, missing records and inaccessible pages cannot establish full-sale absence. Geographic/purchase-option scope and evidence-to-label policy remain unresolved.

`src/06_verify_historical_ground_truth.py` deterministically selects **18 pairs / 17 games** from the unchanged 300 diagnostics: **4 A / 3 B / 0 C / 11 D**, including all B cases, recent/stale D, empty history, positive controls and historical conflicts. Original categories and individual selection rationales are preserved. The reviewed local source inventory and research ledger regenerate all new outputs offline; they are not an external price collector.

Eleven source candidates cover SteamDB price/event information, official Steam store/news/publisher records, Wayback, Common Crawl, Steambase, CheapShark, GG.deals and a metadata snapshot dataset. SteamDB scraping was not undertaken; publisher credentials were not bypassed. The Wayback lookup failed, and that component stopped without interpreting failure as archive absence. Seven of 17 distinct public Steam news feeds were accessible, covering eight selected pairs, but none supplied target-event price evidence. Wrong-year announcements and current prices/outcomes were excluded.

Independent verification: **0 positive / 0 full-sale absence / 0 partial-only pricing / 0 source conflicts / 18 NOT_VERIFIABLE**. These are verification results, not labels. Zero independent conflicts does not resolve known ITAD conflicts; nekowater's release hour remains unknown. No investigated source established a complete historical offer log. At Phase 5B.2 completion, Strategy A—retain directly observed ITAD discounts as evidence and leave other pairs unresolved—was the most defensible evidence-retention approach; it could not support ordinary binary model training on its own. No labeling strategy was implemented in that phase.

Artifacts: `data/intermediate/autumn_sale_verification_pilot.csv`, `data/intermediate/autumn_sale_verification_evidence.csv`, `reports/autumn_sale_ground_truth_feasibility.md`, `reports/autumn_sale_ground_truth_validation.json`, and reviewed JSONs under `reports/sources/`. Before/after SHA-256 verification protects **144 preceding files**, including all **107 frozen Phase 4 inputs** and prior Phase 5A/5B.1 artifacts. Run `python3 -B src/06_verify_historical_ground_truth.py --verify` for full offline tests and deterministic reruns. Authorized documentation/public-page research is separate from network-blocked execution; no ITAD pricing/history requests or new histories occurred.

Phase 5B.2 ended without labels, features or models. Its reports remain frozen; the subsequent human-authorized operational target changes the modeling outcome as documented below. Only 2023–2025 outcomes were investigated; 2026 remains reserved.

## Phase 5B.3 — Operational label construction (completed; approved for Phase 6)

Rule **operational_observed_v1** uses the unchanged exact calendar and observation/category parser: A → `discount_observed=1`; B/D → `0`; C → null with ambiguity/review flags. PU status is A → positive, B/C/D → unlabeled. All labels carry `label_limitation_flag=True`. A zero measures non-observation, not verified absence or formal Valve sale enrollment. No price persistence or coverage threshold is assumed.

`src/06_build_operational_labels.py` reads only local evidence artifacts and reconciles embedded raw records, categories, counts, exact timestamps, raw-array indices and collection scope. The operational CSV preserves all **300 pairs** and **175 A / 3 B / 0 C / 122 D** categories. Labels: **175 ones / 125 zeros / 0 nulls**; yearly ones/zeros **2023: 55/45; 2024: 60/40; 2025: 60/40**. PU: **175 positive / 125 unlabeled**.

nekowater (2650840), 2023, retains operational zero with `eligibility_status=uncertain_release_hour` and `requires_review=True`; the remaining 299 rows are eligible under the existing date rule. No row is excluded. Shop 61 / US are manifest provenance; missing observed currencies and supporting records remain missing/empty, never invented.

Outputs: `data/intermediate/autumn_sale_operational_labels.csv`, `data/intermediate/autumn_sale_pu_labels.csv`, `reports/autumn_sale_operational_labeling.md`, and `reports/autumn_sale_operational_label_validation.json`. Run `python3 -B src/06_build_operational_labels.py --verify` for offline tests, deterministic reruns and before/after SHA-256 verification of **153 protected preceding files**, including all **107 frozen Phase 4 inputs**. No preceding artifact/receipt is regenerated; no network/API calls or new histories occur.

These are **target/provenance tables, not predictor tables**. In-sale observations can construct retrospective targets but cannot be predictors. In-window counts, supporting indices, categories, PU status, history-coverage flags and collection metadata must not become features. Any later model estimates recorded-discount probability under the source's observation conditions, not independently verified participation probability. Pilot sampling and recording coverage can bias evaluation; no PU algorithms or class priors are implemented.

Phase 5B.3 was approved for Phase 6. That phase introduced no predictors or models; its label artifacts remain frozen.


## Phase 6 — Leakage-safe feature engineering (completed; approved for Phase 7A)

`src/07_build_autumn_features.py` generates **300 unique rows / 100 games**, **100 per year**, from the frozen pilot/master release dates and cached Steam history using the existing parser. Prediction cutoff is the exact verified sale start: **2023-11-21T18:00:00Z**, **2024-11-27T18:00:00Z**, **2025-09-29T17:00:00Z**. Price records must satisfy **timestamp < cutoff**; exact cutoff, current-sale, post-sale and future-year observations cannot enter predictors. Prior-year sale observations may enter later-year predictors as past evidence.

The explicit **15-feature allowlist** contains `game_age_days`, `release_year`, `release_month`, `release_quarter`, `prior_price_record_count`, `prior_discount_count`, `prior_discount_rate`, `days_since_last_price_record`, `days_since_last_discount`, `max_prior_discount_pct`, `mean_prior_discount_pct`, `last_observed_price`, `last_observed_discount_pct`, `has_prior_price_history`, and `has_prior_discount_observation`. No numeric auto-selection is permitted. AppID, year, cutoff and `audit_release_hour_uncertain` are linkage/audit fields, excluded from the allowlist. The audit flag is derived from the reported release date, not copied from target-derived review flags; nekowater 2023 remains uncertain and retained.

Release dates follow Phase 2's historically derivable classification, conditional on reported date accuracy/stability. Age subtracts the Pacific sale-start date from the normalized release date, with no invented release hour. Other metadata snapshots, including current prices/discounts, reviews/scores, player counts/CCU, ownership, languages, platforms, genres/tags and publisher/developer fields, are excluded without timestamped historical snapshots. Sampling diagnostics and target/evidence/PU/post-sale fields are prohibited predictors.

A price-usable observation must be classified `discount` or `full_price` by the unchanged parser. Ambiguous/null temporal records do not enter price statistics. Counts retain independently valid duplicate/conflicting observations and do not represent campaigns or discounted duration. Latest valid price refers to a timestamped observation, never the inferred state at cutoff. Latest-timestamp conflicts make last price/cut missing. USD-only compatible prior prices are required for the monetary feature; mixed/non-USD monetary values are missing with an audit reason. Valid dimensionless cuts are comparable within each record's matching currency pair; no conversion or interpolation is applied. Actual data has zero currency conflicts and zero latest-valid timestamp conflict pairs; 12 pairs contain older timestamp conflicts.

Missing pre-price history yields zero counts/flags and null rate, gaps and values. With valid prices but no observed prior discount, rate is zero and discount recency/max/mean remain null. **10 pairs** lack valid prior prices; **46** lack qualifying prior discounts. No missing gap is replaced with zero. All 15 baseline features vary; extreme gaps up to 1,732.71 days and observed 100% cuts are retained without target-based selection.

Outputs: `data/intermediate/autumn_sale_features.csv` contains no target, category or PU status. `data/intermediate/autumn_sale_modeling_table.csv` adds only `discount_observed` after independent feature calculation. Definitions/availability: `reports/autumn_sale_feature_availability.md`; explicit allowlist and version **pre_sale_observations_v1**: `reports/autumn_sale_feature_manifest.json`; validation, missingness/distributions and strictly pre-cutoff raw-index provenance: `reports/autumn_sale_feature_validation.json`.

Timestamp filtering establishes direct temporal separation, not proven point-in-time provider availability. Six games / 18 pairs have observations dated before the source-reported release date; earlier access/preorders, source errors or date interpretation remain hypotheses. Sixty-five cached records across 64 games occur exactly at the requested 2021-01-01 boundary, potentially reflecting initialization. They satisfy the existing parser and remain visible, without silent historical correction. Backfill and source release-date stability remain unresolved.

Run `python3 -B src/07_build_autumn_features.py --verify`: **136 offline tests PASS**, including 34 new feature tests and adversarial future/target invariance tests. All five generated outputs are byte-identical across repeated executions; **159 protected preceding files** and **107 frozen Phase 4 inputs** retain their hashes. No previous evidence/labels/receipts are regenerated; zero network/API requests. No models, imputation, scaling, tuning, feature selection against targets or performance estimates.

Phase 6 was approved for Phase 7A. Its feature values, allowlist, provenance and operational labels remain frozen. The completed Phase 7A below preserves training-only preprocessing, the temporal split and recorded-discount semantics; 2026 outcomes remain excluded.

## Phase 7A completed — baseline modeling, evaluation and visualization

Phase 7A is approved and its artifacts remain frozen. The authorized Phase 7B comparison reuses those outputs; its verified four-model results are documented below. The research target is recorded Steam-store discount occurrence. Operational zero means no qualifying discount was recorded, not verified absence of a discount.

- Chronological training: 2023–2024, **200 rows (115 positive / 85 negative)**. Validation: 2025, **100 rows (60 positive / 40 negative)**, the same 100 games represented previously. This evaluates later-sale temporal generalization, not unseen-game or catalog generalization.
- Bernoulli: deterministic `DummyClassifier(strategy="prior")`, **P(recorded discount)=0.575** from training labels only. Logistic regression: explicit allowlist selection → training-only median imputation → StandardScaler → `LogisticRegression(penalty="l2", C=1.0, solver="lbfgs", max_iter=2000, random_state=42)`. Existing historical coverage flags retained; no added indicators or feature exclusions. Exactly the 15 approved Phase 6 predictors; identifiers/target/audit fields excluded. No tuning; threshold fixed at 0.50.
- Validation: Bernoulli ROC-AUC **0.50000**, AP **0.60000**, Brier **0.240625**, accuracy **0.60**. Logistic ROC-AUC **0.93375**, AP **0.93766**, Brier **0.075389**, accuracy **0.91**. Full metrics, confusion matrices and methodological limitations: [baseline evaluation](reports/autumn_sale_baseline_evaluation.md).
- Artifacts: `models/bernoulli_baseline.joblib`, `models/logistic_regression.joblib` (complete fitted pipeline); `data/processed/autumn_sale_2025_baseline_predictions.csv` (200 long-format rows); `reports/autumn_sale_baseline_metrics.json`; `reports/autumn_sale_baseline_model_manifest.json`; `reports/autumn_sale_baseline_validation.json`; `reports/autumn_sale_baseline_plot_data.json`. Load only trusted local joblib artifacts.
- **171 offline tests pass**, including **35 new baseline tests** and adversarial validation-label/feature changes, prohibited columns, row ordering, preprocessing isolation, threshold boundaries, metrics, sigmoid, serialization and plotting provenance. Two complete reruns have identical structured results, predictions, metrics, model parameters, plotted data, PNG bytes and joblib bytes in this environment. All **166 protected earlier files**, including Phase 6 and **107 frozen Phase 4 inputs**, remain unchanged. Zero network/API requests; earlier artifacts are never regenerated.
- Eight minimalist light-mode PNGs at 300 DPI use `src/plotting_style.py`; the sigmoid overlays actual 100 validation scores/probabilities (maximum sigmoid error **0.0**):

- `reports/figures/baseline_pr_curves.png`
- `reports/figures/baseline_roc_curves.png`
- `reports/figures/bernoulli_distribution.png`
- `reports/figures/logistic_coefficients.png`
- `reports/figures/logistic_confusion_matrix.png`
- `reports/figures/logistic_probability_distribution.png`
- `reports/figures/logistic_reliability.png`
- `reports/figures/logistic_sigmoid.png`

Reproduce using Python 3.9.6 and the recorded dependency versions, already available in the execution environment (`requirements-baseline.txt` preserves the original protected `requirements.txt`):

```bash
python3 -B src/08_train_baseline_models.py --verify
python3 -B -m unittest discover -s tests -p 'test_baseline_models.py'
```

A normal run without `--verify` generates artifacts and explicitly records tests/determinism as not run. Verification blocks network access, runs the full offline suite, compares two complete isolated experiments and saves the verified artifacts. Cross-platform floating-point/font/PNG identity and cross-version joblib compatibility are not guaranteed.

Limitations: only 100 validation rows from one later sale, repeated games, sparse recording coverage, retrospective provider availability/backfill, source release-date/eligibility ambiguity and pilot selection bias. Metrics and calibration concern recorded labels; coefficients are standardized associations, without causal interpretation. The sigmoid is explanatory, not accuracy evidence. Strong calibration claims and unseen-game/catalog extrapolation are unsupported.

The predefined Phase 7B comparison was authorized subsequently. Its use of the previously examined 2025 holdout remains exploratory. The approved Phase 7A artifacts and target semantics are preserved; later scaling or confirmatory work remains outside the implemented scope.

## Ensemble comparison and exploratory diagnostics

Phase 7B implements the predefined Random Forest and conditional XGBoost pipelines on the unchanged 15-feature allowlist. Random Forest uses `n_estimators=200`, `max_depth=4`, `min_samples_leaf=5`, `max_features="sqrt"`, seed 42 and one job. XGBoost is configured with 100 trees, depth 3, learning rate 0.05, subsample/colsample 0.8, binary logistic objective, log-loss evaluation, seed 42 and one job. XGBoost 2.1.4 is installed and the fitted pipeline, predictions, metrics and importance figure are verified. `requirements-ensemble.txt` declares xgboost==2.1.4 without altering baseline dependencies. No network installation or substitute model occurs.

Primary training remains 2023–2024: 200 rows, 115 positive / 85 negative. Evaluation remains 2025: the same 100 game-year rows, 60 positive / 40 negative. Tree pipelines select approved columns and fit median imputers only on training; no scaling, tuning, feature selection, early stopping or calibration fitting uses validation outcomes. Threshold is fixed at 0.50. Approved Phase 7A predictions and metrics are loaded unchanged and cross-checked against identities, labels, recomputed metrics and trusted checksum-verified artifacts. The 2025 holdout is previously examined; this is comparative evaluation, not a fresh confirmatory test. Games recur across years, so unseen-game/catalog generalization is not established.

Random Forest validation: ROC-AUC 0.927083, AP 0.918201, Brier 0.081897, log loss 0.288333, accuracy 0.880000, precision 0.842857, recall 0.983333, F1 0.907692. Logistic regression scores slightly better on discrimination and probability error in this pilot; accuracy alone is not a universal selection criterion. Both refer to operational recorded-discount labels, not verified actual participation. Complete tables and assessment: [model comparison](reports/autumn_sale_model_comparison.md).

The secondary 2023 → 2024 check trains on 100 rows (55 positive / 45 negative) and evaluates 100 rows (60 positive / 40 negative). Its Bernoulli prior is 0.55. ROC-AUC: Bernoulli 0.500000, logistic 0.910833, Random Forest 0.892917; XGBoost 0.910417. Training size and evaluation year differ from the primary protocol; this is not a controlled drift experiment. 2024 outcomes contribute to primary fitting, so the secondary result is not independent confirmation. Temporary secondary fits do not overwrite primary artifacts.

The post-hoc coverage-only logistic diagnostic uses exactly `prior_price_record_count`, `days_since_last_price_record` and `has_prior_price_history`, without discount-specific behavior features. Training-only median imputation/scaling and the unchanged logistic settings give ROC-AUC 0.865833, AP 0.874952, Brier 0.108245, accuracy 0.870000. Observation availability may contribute to recorded-label prediction, but this does not identify the precise source of signal. No diagnostic changes any primary predictor, parameter or threshold. Native Random Forest impurity importance and 2025 permutation importance (ROC-AUC, 20 repeats, seed 42) are exploratory; correlated predictors and the small holdout limit interpretation, and importance is not causal.

Artifacts: `models/random_forest.joblib` and `models/xgboost_model.joblib` (complete fitted pipelines); `data/processed/autumn_sale_2025_ensemble_predictions.csv` (200 rows); `data/processed/autumn_sale_2025_model_comparison_predictions.csv` (400 rows); comparison metrics/report; secondary temporal results; coverage diagnostic; ensemble feature importance; model manifest; plotted data; ensemble validation receipt; and the Phase 7A integrity snapshot. Eleven minimalist light-mode PNGs are in `reports/figures/`, including `xgboost_feature_importance.png`. All previous model artifacts, figures, labels and feature values remain intact.

```bash
python3 -B src/09_train_ensemble_models.py --verify
```

Verification records **201 passing tests, with no skips**, with zero failures/errors. Two complete runs have identical predictions, metrics, fitted fingerprints, secondary results, coverage/importance values, plotted data, PNG bytes and both ensemble joblib bytes in this environment. All **186 protected earlier hashes** remain unchanged, including all Phase 7A outputs and **107 frozen Phase 4 inputs**. Zero network/API requests. Source/platform/version-specific determinism and trusted artifact loading remain documented constraints.

The XGBoost 2.1.4 compatibility fix and complete Phase 7B verification passed without parameter or split changes. XGBoost validation ROC-AUC is 0.929583, AP 0.926240, Brier 0.067501, log loss 0.252518, accuracy 0.930000, precision 0.907692, recall 0.983333 and F1 0.944000. No new histories, games, PU learning, large searches, future predictions, genre analytics, rankings, HTML report or dashboard were produced. The authorized feasibility audit is documented below; later collection and modeling remain unstarted. Research limitations concerning recorded negatives, incomplete provider coverage, retrospective availability, source-date ambiguity, sampling bias and repeated-game dependence remain unresolved.

## Historical scaling feasibility audit

Phase 8A audits the authoritative `data/intermediate/games_master.csv`: **99,194 records / unique AppIDs**, no duplicate, missing or invalid identifiers, and no missing/invalid release dates or release-year inconsistencies. Existing date-rule eligibility is **61,681 / 76,256 / 90,893** for 2023/2024/2025; start-day release uncertainty affects **23 / 47 / 54** catalog games. Release dates remain date-only and all official boundaries are preserved.

The original 100 games remain a separately identified diagnostic cohort. The restricted balanced-frame probability sample has **61,559 eligible nonpilot games**, using release-period strata, SHA-256 priorities with seed 42 and exact rational proportional interleaving. Nested totals **500 / 1,000 / 2,000 / 5,000** include the pilot and **400 / 900 / 1,900 / 4,900** new candidates. Start-day releases are excluded from the new frame; the original uncertain pilot case remains unchanged. The candidate CSV has all 99,194 catalog IDs with eligibility, status and cohort flags, but no new labels or inferred histories.

Existing local evidence remains **100 caches / 5,568 Steam observations**: **97 games with price observations, 88 with qualifying discounts, three empty histories**. No local caches exist for the other **99,094** catalog games; provider availability and complete historical capture remain unknown. Missing records do not establish actual non-discounting. No new data were fetched.

If all new games match and need one history request, existing-cache reuse gives **800 / 1,800 / 3,800 / 9,800** requests for the planned totals, before retries. Recorded quota documentation is historical, not verification of the current account limit. Matching fractions, request formulas, pacing floors, storage scenarios, retry/caching/resume behavior and unknown response limits are documented in the feasibility reports. Wall-clock completion time is not established.

Collection, labeling, features and existing modeling wrappers contain pilot-specific paths, count guards and fixed-panel assumptions. The Phase 6 wrapper also locks the original 175 positive / 125 negative counts; existing model wrappers reject null targets. Expanded ambiguity and failed retrievals require explicit accounting rather than recoding or silent exclusion. A future Phase 8B must parameterize separate cohort namespaces, retain failures/ambiguity, enforce release eligibility and exact pre-cutoff rules, and preserve the 15 approved features and operational target semantics. No such source changes were made here. New cohort/model-ready data do not yet exist.

Proposed evaluation separates represented-game temporal evaluation from a sealed unseen-game cohort whose AppIDs are excluded from every training year. Report pilot and probability sample separately, and use development-defined pre-cutoff coverage sensitivity. New game outcomes can be kept untouched, but 2025 as an event and the model methodology have already been examined; it is not a fresh event-level confirmatory test.

Artifacts: `src/10_audit_scaling_feasibility.py`, `tests/test_scaling_feasibility.py`, `data/intermediate/autumn_sale_scaling_candidates.csv`, `reports/autumn_sale_scaling_feasibility.md`, `reports/autumn_sale_scaling_feasibility.json`, `reports/autumn_sale_sampling_plan.md` and `reports/autumn_sale_scaling_validation.json`. Four white-background 300-DPI figures: `scaling_catalog_release_years.png`, `scaling_historical_coverage.png`, `scaling_sampling_composition.png` and `scaling_population_funnel.png` under `reports/figures/`.

```bash
python3 -B src/10_audit_scaling_feasibility.py --verify
```

**22 focused offline tests pass**. Two complete isolated audit executions produce byte-identical candidate CSV, JSON/Markdown reports, plotted data and PNGs in this environment. All **214 completed source/data/report/model/dependency artifacts**, including raw source snapshots, all prior figures and Phase 7 outputs, retain their hashes. The three project documentation files are updated as authorized. The audit does not execute earlier model-fitting test suites; prior verified results remain hash-protected. Zero network/API requests, zero new histories and zero model fits.

Recommended next step, requiring separate approval: a cohort-aware collection implementation and bounded release-stratified smoke/coverage trial with account quota and response-limit confirmation. Assess matching/nonresponse, response sizes and historical timing provenance before approving bulk collection. Phase 8B, Phase 8C and Phase 9 remain unstarted.

## Bounded expansion collection and sealed evaluation design

Phase 8B.1 prepares infrastructure only. It does not authorize live collection. `src/11_prepare_expansion_collection.py` defaults to offline preparation; the approval manifest under `reports/expansion/` remains PENDING. The exact trial is the Phase 8A rank-1–20 prefix: 20 nonpilot AppIDs, with release-stratum allocation 1 / 8 / 8 / 3. No replacements depend on matching, history completeness or outcomes.

All 61,559 eligible nonpilot AppIDs are assigned once at game level. Within each existing release-period stratum, SHA-256 of `steam-autumn-unseen-v1|314159|appid` determines the order. The first `floor((n+2)/5)` form sealed evaluation, a nearest-20% allocation; the remainder form development. Totals are 49,247 development / 12,312 evaluation. The trial contains 16 / 4. The independent salt differs from Phase 8A sampling; the pilot stays a separate diagnostic sample. The membership CSV and its digest are frozen before retrieval, with no post-retrieval rebalancing. Held-out IDs are rejected by the development adapter in every year.

Future collection requires a human-authored approval receipt binding the pending-manifest SHA-256, exact cohort, implementation, 60-attempt cumulative budget and external custodian certificate. Serial spacing is at least one second; timeout is 30 seconds; each game/endpoint has at most three attempts across restarts. The journal reserves attempts before requests, counts crash reservations conservatively, blocks concurrent collectors and refuses restart if caches exist without the journal. No 500-game mode exists.

Evaluation payloads, including errors and quarantine, are encrypted before disk storage using system OpenSSL CMS with AES-256-CBC and an external RSA certificate. Private keys are never accepted or generated for production. Independent custody and a trusted collection operator are essential: the operator sees plaintext in memory, ciphertext length reveals coarse size, and repository owners can bypass software guards deliberately. Filesystem permissions alone do not guarantee blindness. Custody remains unverified and must be established before live approval; evaluation-outcome inspection and unsealing are not authorized.

Missing retrievals, unmatched lookup, request failures, malformed responses, empty arrays, ambiguous deals and schema anomalies remain distinct. Collection generates no operational labels. Successful responses retain UNVERIFIED historical completion, with duplicate timestamps and raw order preserved. The provider's current quota, pagination, truncation and backfill guarantees remain unknown. The requested-since history can include post-2025 records; later separately approved features must apply the unchanged exact historical cutoffs and 15-feature allowlist.

```bash
python3 -B src/11_prepare_expansion_collection.py --verify
```

The focused offline suite mocks all HTTP behavior, uses temporary test-only encryption keys, and verifies protected artifacts and deterministic preparation outputs. Planning CSVs are under `data/intermediate/expansion/`; the preflight, pending approval, SHA-256 inventory and validation receipt are under `reports/expansion/`. No raw expansion histories, new labels, models or figures are created. The separately approved 20-game trial is the next decision; Phase 8B.2, larger collection and later modeling remain outside this execution.
