# Project Status

## Current Phase

Phase 2 — Games Master Dataset ✅ (Phase 1 also complete)

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

Snapshot reference date remains unknown, so no future-release flag is created. Retained snapshot fields (including Price, Discount, DLC count, Tags, and Achievements) are not approved as historical predictors. Discount is never a sale label. No Phase 3+ work has been performed.

Execution: `python3 src/01_build_games_master.py` with requirements installed. The system Python currently supplies pandas 2.3.3; the existing `.venv` lacks pandas.

## Next Phase

**Phase 3 — Create Pilot Sample**
