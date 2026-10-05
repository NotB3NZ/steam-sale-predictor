# Project Status

## Current Phase

Phase 4 — ITAD Historical Price Collection ✅ (Phases 1–3 complete)

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
- No sale labels or event-specific coverage decisions; Phase 5 has not begun.

## Next Phase

**Phase 5 — Historical Coverage Assessment and Autumn Sale Labels**
