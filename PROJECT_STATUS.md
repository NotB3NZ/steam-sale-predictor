# Project Status

## Current Phase

Phase 5B.3 — Operational label construction completed; pending human review before Phase 6. Recorded-discount labels exist; true sale participation remains unverified. Phase 4 COMPLETE and frozen; no predictive features or models.

## Completed

- [x] Directory setup (`data/raw/`, `data/intermediate/`, `data/processed/`, `src/`, `reports/`, `notebooks/`)
- [x] Source CSV inspection (`src/00_inspect_source.py`)
- [x] CSV structural validation — confirmed `DiscountDLC count` header concatenation bug
- [x] Missingness analysis — 8 columns >50% missing; Movies 100% null; Tags 34% missing
- [x] Numeric distribution analysis — no invalid values; flagged extreme prices and zero-heavy columns
- [x] Date parsing — 100% success; range 1997–2026
- [x] Column classification for modeling
- [x] Leakage risk assessment — 12 columns flagged
- [x] Data quality report (`reports/source_data_report.md`)
- [x] Project context documentation (`PROJECT_CONTEXT.md`)

## Key Findings

1. **125,855 games**, unique by AppID, zero duplicates.
2. **Header bug confirmed:** `DiscountDLC count` is two columns concatenated. Raw header has 39 fields; data rows have 40. Corrected at load time; original file preserved.
3. **Movies column is 100% null** after header correction.
4. **21.2% have source Price == 0** — excluded operationally in Phase 2; permanent F2P status is not established.
5. **84.4% have Peak CCU == 0** — extremely sparse engagement data.
6. **12 columns** have temporal leakage risk for historical prediction.
7. **All 125,855 release dates parse successfully** (earliest: 1997, latest: 2026).
8. **Tags** are 33.8% missing — the most valuable content feature has significant gaps.

## Generated Files

| File | Purpose |
|------|---------|
| `src/00_inspect_source.py` | Reproducible inspection script |
| `reports/source_data_report.md` | Data quality findings |
| `PROJECT_CONTEXT.md` | Persistent project decisions |
| `PROJECT_STATUS.md` | This file |
| `requirements.txt` | Python dependencies |

## Existing Files Preserved

| File | Notes |
|------|-------|
| `games.csv` | Primary dataset (401 MB) — NOT modified |
| `games.json` | Companion JSON (962 MB) — NOT inspected, not needed yet |
| `test.py` | ITAD API exploration script — preserved for Phase 2+ reference |
| `apikey` | ITAD API key file — preserved |

## Phase 2 completed

- [x] Shared corrected schema (`src/source_schema.py`) used by both pipeline scripts.
- [x] Paid-game catalog built by `src/01_build_games_master.py`.
- [x] Output: `data/intermediate/games_master.csv` — **99,194 rows, 30 columns**.
- [x] Audit and temporal classification: `reports/games_master_report.md`.
- [x] In-memory and saved-CSV integrity validation passed; round-trip values verified.
- [x] Raw `games.csv` SHA-256 unchanged before/after processing.
- [x] Synthetic checks cover invalid inputs, overlapping rules, optional missingness, retained zero-owner/CCU records, and duplicate-ID rejection.

Original rows: 125,855. Sequential removals: invalid AppID 0; missing/invalid name 1; invalid release date 0; invalid price 0; Price <= 0 26,660. Overall 26,661 titles fail Price <= 0 (all zero, none negative); the missing-name title overlaps that group. This is an operational paid-candidate filter, not proof that all excluded games are permanently free.

Names are trimmed; dates are standardized as `release_date` with `release_year`. Eleven unnecessary columns are dropped. Optional missing metadata, original owner ranges, and multi-value fields are preserved. No historical-sale cutoff is applied. There remain 7,872 zero-owner games and 81,702 zero-Peak-CCU games.

Snapshot reference date remains unknown, so no future-release flag is created. Retained snapshot fields (including Price, Discount, DLC count, Tags, and Achievements) are not approved as historical predictors. Discount is never a sale label. Phase 2 stopped before pilot sampling; Phase 3 is documented below.

Execution: `python3 src/01_build_games_master.py` with requirements installed. The system Python currently supplies pandas 2.3.3; the existing `.venv` lacks pandas.

## Phase 3 completed

- [x] Script: `src/02_create_pilot.py`.
- [x] Master candidates: **99,194**; eligible at `release_date <= 2023-11-21`: **61,681**; later releases excluded from this pilot only: **37,513**.
- [x] Pilot: **100 unique games**, all within the historical cutoff; **36 columns** (30 unchanged master columns plus 6 pilot diagnostics).
- [x] Output: `data/intermediate/pilot_games.csv`.
- [x] Report: `reports/pilot_sample_report.md`, including distributions, 12 edge criteria across 11 distinct games, and a 20-record sanity view.
- [x] Seed **42**, stable SHA-256 priority by AppID, independent of source row order.
- [x] 80-game core uses square-root-weighted release-era/price quotas and activity cycling; diagnostics/supplements plus diversity fill complete the sample. No manual fame-based selection.
- [x] All eras, price bands, owner groups, and activity groups represented. Target genres meet minimum coverage; no parsed publisher exceeds two pilot games.
- [x] Saved-CSV validation passes, all 30 source-column values match the master, and invalid schema/duplicate/source-value/cutoff/price cases are rejected.
- [x] Two full script runs produce identical pilot and report bytes. Repeated selection and shuffled-master selection are identical.
- [x] Master hash unchanged: `e4fa1eb1a7d5154831badc8b82cd5e1d34409948b0559b18dee81d9192b97852`.
- [x] Pilot SHA-256: `458ddc9042beb8f978e1607cac6eeace88bd3b9a73537bc2dae82b75c419d14e`.

Release-era counts: before 2015 **20**; 2015–2018 **24**; 2019–2020 **18**; 2021–2022 **21**; 2023 through cutoff **17**.

Source-price quartiles: **1.19 / 2.99 / 5.99**. Pilot price-band counts, low to high: **25 / 25 / 23 / 27**. Zero/nonzero Peak CCU: **53 / 47**, including **24** high-activity games (eligible nonzero CCU 90th-percentile threshold **89.4**).

Genres include Adventure 38, Strategy 22, RPG 19, Simulation 19, Massively Multiplayer 4, Racing 4, and Sports 3; 19 games have the exact Puzzle tag. Publisher tokens: 103 distinct, maximum concentration 2; 62 games share at least one developer/publisher token. Missing metadata: Tags 10, Genres 1, Publishers 2.

This diagnostic diversity pilot is not statistically representative or suitable for population model-performance claims. Snapshot diagnostics are not approved historical predictors. Publisher comma parsing may split organization names; exact developer overlap is only a self-publishing proxy. The approved paid catalog contains some software/non-game products, including the high-DLC diagnostic. These remain unchanged for downstream review. ITAD matching/history coverage remains unknown.

Execution: `python3 src/02_create_pilot.py`. No ITAD/Steam/external API calls, scraping, labels, sale-year expansion, or model work occurred. Phase 3 stopped before Phase 4.

## Phase 4 completed

- Validation PASS at 2026-10-05T17:06:32.189335Z; pilot: 100; matched: 100; history success: 100; empty: 3; unmatched: 0; request failures: 0.
- AppID lookup /games/lookup/v1; history /games/history/v2; US; shops=61; since=2021-01-01T00:00:00Z.
- Cache: data/raw/itad/; manifest: data/intermediate/itad_collection_manifest.csv; report: reports/itad_collection_report.md.
- Smoke receipt and raw cache provenance validated; Phase 2/3 datasets unchanged.
- Unresolved collection issues: 0 unmatched AppIDs (see report). Event-specific historical coverage remains unassessed.
- Phase 4 created no sale labels or event-specific coverage decisions. Collection is COMPLETE; its inputs remain frozen.

## Phase 5A completed — preserved historical baseline

- Original implementation, report, validation receipt, context and both CSV outputs are preserved under `reports/baselines/phase_5a_calendar_window/`; SHA-256 manifest references commit `509377ca2a217b1d908add07814a49928a55fe08`.
- Baseline outputs: **200 unique AppID × sale_year rows** and **238 actual in-window records**. Current output paths now hold the Phase 5A.1 refinement below.
- All **100 pilot games** considered for **2023 and 2024**. No missing/unreadable/invalid caches, record parsing failures, or non-Steam records.
- Canonical dates are unchanged: November 21–28, 2023; November 27–December 4, 2024. Exact sale hours/timezone are not documented; audit includes both calendar dates in UTC, with the midnight after the end date exclusive. This convention is explicit and does not verify live sale hours.
- Descriptive categories A/B/C/D: **2023: 55/8/0/37**; **2024: 60/4/0/36**. These are evidence descriptions, not final target labels.
- Observation counts 0/1/2/3: **2023: 37/9/53/1**; **2024: 36/8/56/0**. Every B case has one full-price observation; no sufficiency decision has been made.
- Before/after evidence is reported separately without price carry-forward. All original in-window records and timestamps are retained with raw array indices.
- Empirical histories suggest change-oriented records, but periodic polling/change retention/corrections cannot be distinguished confidently. Two repeated state patterns, six conflicting same-timestamp groups, and 65 exact requested-since timestamps are documented; no observed null deals.
- **30 offline tests PASS**, including boundary inclusion, timezone normalization, zero evidence, discount/full-price/null/ambiguous handling, nearest context/ties, missing caches, reproducibility, and Phase 4 regression tests. Saved CSVs are independently reconciled to raw history.
- SHA-256 and inventories unchanged for **107 frozen input files**, including every raw ITAD JSON, the pilot/master/collection manifest, and Phase 4 script/report. Original receipt is preserved inside the baseline directory. Initial pre-work hashes were also verified after completion.
- **Zero API/network requests.** No raw cache refreshes, final labels, coverage thresholds, state-persistence rules, training data, or modeling changes.

## Phase 5A.1 completed — pending review

- Reused and verified the baseline left by the interrupted IDE session; the six preserved files match the committed revision. The baseline manifest and all baseline files remain unchanged. An offline test reproduces all four original output artifacts byte-for-byte in isolation.
- Official Valve event hours verified: 2023 November 21–28 and 2024 November 27–December 4 at **10 AM PST**, 2025 September 29–October 6 at **10 AM PDT**. Exact UTC half-open windows are centralized in `src/autumn_sale_calendar.json`; official source references and preserved artwork are included in the audit report.
- **300 unique pairs**, all 100 pilot AppIDs for 2023/2024/2025; **300 date-eligible**, **0 ineligible**. Same-start-date release nekowater has an explicitly unresolved release-hour limitation. Ineligible cases are supported as explicit rows, never silently discarded or categorized D.
- Updated audit and record CSVs contain **178 in-window records**: 2023 **57**, 2024 **60**, 2025 **61**. No missing/unreadable caches, parsing failures, non-Steam, null or ambiguous in-window records.
- Descriptive A/B/C/D: **2023: 55/2/0/43**, **2024: 60/0/0/40**, **2025: 60/1/0/39**. Record densities 0/1: **43/57**, **40/60**, **39/61** respectively; no pair has multiple in-window observations.
- Original-to-exact comparison: 2023 **61 removed** (1 before start, 60 at/after end), 2024 **60 removed** (all at/after end); **0 added**. **6 + 4 category changes**, all original B → D. **10 of 12 original B cases affected**; A counts unchanged. Dedicated report: `reports/autumn_sale_boundary_comparison.md`.
- **42 offline tests PASS**, including all original tests, exact start/end inclusion, PST/PDT conversion, three calendars, eligibility, null/ambiguous/mixed handling, Steam-only selection, 300 unique pairs, corruption gates, baseline reproduction and comparison reconciliation.
- Saved CSVs independently reconciled to local raw records. Repeated full audits produce identical bytes. Execution checks: `reports/phase_5a1_execution_checks.json`; detailed before/after hashes: `reports/autumn_sale_evidence_validation.json`.
- **107 frozen Phase 4 input hashes unchanged**, including all raw histories, smoke/archive JSONs and frozen CSVs; preserved baseline inventory/hashes also unchanged.
- **Zero ITAD/pricing requests; zero audit network requests.** Authorized external research was confined to official Valve event-calendar verification; web-tool HTTP totals are unavailable. No raw refresh, target labels, coverage rules, state persistence, features or modeling.
- Training/validation intent remains 2023–2024 / 2025; **2026 excluded** from this audit. Sparse histories and timestamp conflicts remain evidence limitations for human methodological review.

## Next Phase

**Phase 6 — NOT STARTED. Leakage-safe feature engineering requires human review.**

STOP after Phase 5B.3. Operational labeling is complete; it does not verify actual sale participation.

## Phase 5B.1 completed — pending review

- New offline script: `src/05_investigate_sale_coverage.py`; reuses the unchanged Phase 5A.1 parser and exact event calendar.
- **300 unique game-sale pairs**, all date-eligible; unchanged A/B/C/D totals **175/3/0/122**, with **178** directly observed in-window records. No 2026 sale rows.
- Strict investigation cutoff: timestamps **before 2026-01-01T00:00:00Z** only. Of 5,568 cached records, 852 are excluded by timestamp and 4,716 analyzed. This censors post-sale context without modifying any cached history or earlier artifact.
- Category B latest pre-state: **0 full price / 2 discounted / 0 ambiguous / 1 missing**. Category D: **93 full price / 20 discounted / 0 ambiguous / 9 missing**. D post-state before cutoff: **18 full price / 25 discounted / 0 ambiguous / 79 missing**.
- Non-A pre-recency scenarios, 7/14/30/60/90 days/unrestricted: full-price counts **1/2/7/10/13/93**, discounted counts **7/14/15/15/15/22**. Unrestricted also reports 10 missing-pre pairs separately. These measure evidence availability, never inferred negative labels; no threshold chosen.
- D pre-gap median **808.986539 days** (113 available, 9 missing); post-gap median **17.013194 days** (43 available, 79 missing). Surrounding interval median **118.708287 days**, maximum **1,243.698218 days** where both sides exist.
- Official ITAD documentation supports historical and change-oriented records. Complete Steam-change capture and safe persistence are unestablished. Pre-2026 observations contain 6 conflicting timestamp groups, 2 repeated-state patterns, 53 consecutive cut=0 pairs and 65 requested-since timestamps; no null/ambiguous individual deals.
- Main report: `reports/autumn_sale_coverage_investigation.md`. Pair chronology and raw indices: `data/intermediate/autumn_sale_coverage_diagnostics.csv`. Hypothetical scenarios: `data/intermediate/autumn_sale_coverage_sensitivity.csv` (384 overlapping aggregate cells). Receipt: `reports/autumn_sale_coverage_validation.json`. Documentation review note: `reports/sources/itad_history_semantics.json`.
- **62 offline tests PASS**, including all 42 previous tests. Full diagnostic executions produce identical bytes for all four outputs. Independent partition/provenance, gap, category and scenario reconciliation passes; saved CSVs round-trip exactly.
- **133 protected prior-phase file hashes unchanged**, including **107 frozen Phase 4 inputs** and the original Phase 5A baseline. Initial tracked-file hashes also checked after work.
- **Zero diagnostic network attempts/requests; zero ITAD/pricing API calls; zero new histories.** External research was confined to official ITAD documentation; web-tool underlying HTTP totals are unavailable.
- No persistent price inference, final target labels, modeling features or models. Release-hour precision for nekowater (2023), coverage sufficiency, conflict handling and later UNKNOWN methodology remain human-review questions.

## Phase 5B.2 completed — source feasibility; pending review

- Formalized the any-point discount event and distinct minimum evidence requirements for occurrence, full-sale absence, partial/missing/conflicting evidence and unknown eligibility. No final labeling policy selected or implemented.
- Investigated **11 source candidates** across all five requested families, with primary URLs/access dates and explicit restrictions in `reports/sources/historical_price_source_inventory.json`.
- Deterministic diagnostic subset: **18 pairs / 17 games**, **4 A / 3 B / 0 C / 11 D**, including all B cases, old/recent D, empty history, positive controls and conflict-bearing games. Original 100-game pilot and 300 pair categories remain unchanged.
- Recorded **21 pair-source attempt rows**. Seven of 17 distinct public Steam news feeds accessible, covering eight pairs; no relevant historical price observations. Wayback CDX probe failed; external archive component stopped. SteamDB automation and authenticated publisher access were not attempted without permission/credentials. No access restrictions bypassed.
- Independent outcomes verified: **0 positive / 0 full-sale absence / 0 partial-only pricing / 0 conflicting observations / 18 NOT_VERIFIABLE**. Inaccessibility or absent target evidence never became a negative outcome. Known ITAD conflicts and nekowater release-hour uncertainty remain unresolved.
- Main report: `reports/autumn_sale_ground_truth_feasibility.md`; pilot/evidence CSVs under `data/intermediate/`; reviewed research ledger and pre-work manifest under `reports/sources/`; new offline script `src/06_verify_historical_ground_truth.py` and focused tests `tests/test_historical_ground_truth.py`.
- **80 offline tests PASS**, including 18 new focused tests. Reproduction: `python3 -B src/06_verify_historical_ground_truth.py --verify`. Validation receipt records identical repeated outputs, **144 unchanged protected preceding files**, including all **107 frozen Phase 4 inputs**, and zero diagnostic network attempts.
- No ITAD pricing/history requests, new histories, final labels, state persistence, features or models. Authorized external research was limited to source documentation and legitimate public verification; underlying web-tool HTTP totals unavailable. Only 2023–2025 outcomes considered.
- At Phase 5B.2 completion, Strategy A was the most defensible evidence-retention approach; no binary dataset for verified participation was established. The subsequent human-authorized operational target is documented below; prior analytical artifacts remain frozen.

## Phase 5B.3 completed — operational labels; pending review

- Human-approved target: whether a qualifying Steam-store discount is **recorded** during the exact event, not actual/formal sale participation. Rule: `operational_observed_v1`; A → 1, B/D → 0, C → null with ambiguity/review flags. All limitation flags true.
- **300 unique rows**, unchanged categories **175/3/0/122**. Operational labels **175 ones / 125 zeros / 0 nulls**. Yearly ones/zeros: **2023 55/45; 2024 60/40; 2025 60/40**. PU view: **175 positive / 125 unlabeled**.
- **One eligibility-uncertain pair**: nekowater (2650840), 2023, retains zero and explicit review/release-hour flags. All rows retained. Three empty histories remain nine D operational zeros; no actual non-discounting inferred.
- Created `src/06_build_operational_labels.py`, `tests/test_operational_labels.py`, two label CSVs, `reports/autumn_sale_operational_labeling.md` and `reports/autumn_sale_operational_label_validation.json`. Shared parser/calendar reused; actual in-sale records and raw indices reconciled to saved evidence.
- **102 offline tests PASS**, including 22 new focused tests. Verification: `python3 -B src/06_build_operational_labels.py --verify`. Receipt records byte-identical repeated outputs and **153 unchanged protected preceding files**, including **107 frozen Phase 4 inputs**, with prior audits/investigations/verification receipts preserved.
- No further source research, network/API calls, raw refreshes, new games/years, predictive features, PU algorithms, models or accuracy estimates. **STOP before Phase 6.** Future evaluation/probabilities must refer to recorded discounts; the operational label CSV is not a feature table.
