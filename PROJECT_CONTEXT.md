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

## Phase 5B.3 — Operational label construction (completed; pending human review)

Rule **operational_observed_v1** uses the unchanged exact calendar and observation/category parser: A → `discount_observed=1`; B/D → `0`; C → null with ambiguity/review flags. PU status is A → positive, B/C/D → unlabeled. All labels carry `label_limitation_flag=True`. A zero measures non-observation, not verified absence or formal Valve sale enrollment. No price persistence or coverage threshold is assumed.

`src/06_build_operational_labels.py` reads only local evidence artifacts and reconciles embedded raw records, categories, counts, exact timestamps, raw-array indices and collection scope. The operational CSV preserves all **300 pairs** and **175 A / 3 B / 0 C / 122 D** categories. Labels: **175 ones / 125 zeros / 0 nulls**; yearly ones/zeros **2023: 55/45; 2024: 60/40; 2025: 60/40**. PU: **175 positive / 125 unlabeled**.

nekowater (2650840), 2023, retains operational zero with `eligibility_status=uncertain_release_hour` and `requires_review=True`; the remaining 299 rows are eligible under the existing date rule. No row is excluded. Shop 61 / US are manifest provenance; missing observed currencies and supporting records remain missing/empty, never invented.

Outputs: `data/intermediate/autumn_sale_operational_labels.csv`, `data/intermediate/autumn_sale_pu_labels.csv`, `reports/autumn_sale_operational_labeling.md`, and `reports/autumn_sale_operational_label_validation.json`. Run `python3 -B src/06_build_operational_labels.py --verify` for offline tests, deterministic reruns and before/after SHA-256 verification of **153 protected preceding files**, including all **107 frozen Phase 4 inputs**. No preceding artifact/receipt is regenerated; no network/API calls or new histories occur.

These are **target/provenance tables, not predictor tables**. In-sale observations can construct retrospective targets but cannot be predictors. In-window counts, supporting indices, categories, PU status, history-coverage flags and collection metadata must not become features. Any later model estimates recorded-discount probability under the source's observation conditions, not independently verified participation probability. Pilot sampling and recording coverage can bias evaluation; no PU algorithms or class priors are implemented.

**STOP before Phase 6.** Feature engineering requires human review, a separate pre-sale-only feature table, historical validity checks and preservation of the 2023–2024 / 2025 temporal split. No predictive features, model training, tuning, accuracy calculations or 2026 outcomes were introduced.
