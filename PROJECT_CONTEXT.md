# Project Context — Steam Sale Prediction

## Research Question

> Given information available about a Steam game **before** a specific Steam Autumn Sale begins, what is the probability that the game will be discounted during that sale?

## Unit of Observation

```
one row = one game × one Autumn Sale year
```

Example:
```
appid | sale_year | age_at_sale | price | ... | discounted
12345 | 2023      | 850         | 29.99 | ... | 1
12345 | 2024      | 1216        | 29.99 | ... | 0
```

## Data Sources

| Source | Role | Status |
|--------|------|--------|
| `games.csv` | Game metadata & potential predictors | Available (125,855 games) |
| ITAD historical Steam price data | Ground-truth sale labels (`discounted`) | Phase 2+ |

## Known Data Issue

The raw `games.csv` header has a concatenated column `DiscountDLC count` that should be `Discount` + `DLC count` (header has 39 fields, data rows have 40). Both pipeline scripts use `src/source_schema.py` to correct this at load time. The original file is preserved.

## Methodological Rules

1. **Label integrity:** Insufficient historical price coverage → `UNKNOWN`, never `0`.
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
Autumn 2025: 2025-09-29 to 2025-10-06  (date may need verification)
```

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

## Phase 5A — Exploratory evidence audit (completed; pending human review)

`src/04_audit_autumn_evidence.py` reads frozen Phase 4 caches locally, without importing/executing the collector or making network requests. The audit covers all 100 pilot AppIDs for Autumn 2023 and 2024 (200 game-sale pairs); 238 records are directly timestamped inside the documented calendar-date windows. See `reports/autumn_sale_evidence_audit.md`, the two `autumn_sale_evidence_*.csv` intermediate files, and `reports/autumn_sale_evidence_validation.json` for provenance/hashes and validation.

Canonical dates above remain unchanged. The repository does not specify exact sale hours/timezone. For Phase 5A only, compare timezone-aware UTC timestamps against inclusive UTC calendar dates: start midnight through midnight after the end date, exclusive at the latter boundary. This is an explicit audit convention, not verification of official hour boundaries. End-date full-price observations may occur after live sale hours; no different dates/hours have been silently substituted.

Timestamp-usable Steam records include null/ambiguous deals when time/shop are valid. Reported discount observations have explicit cut > 0 and price < regular; reported full-price observations have cut = 0 and equal price/regular. Missing/contradictory information is ambiguous and raw fields are retained. Descriptive A/B/C/D categories summarize only in-window records. Before/after records and gaps are separate diagnostics and do not imply state persistence or coverage. Equal-time records are preserved with raw indices; all nearest-context ties remain inspectable.

Observed categories A/B/C/D: 2023 **55/8/0/37**, 2024 **60/4/0/36**. All B cases have one full-price observation; no multiple-full-price-only or null/ambiguous in-window cases occur. Cached histories appear change-oriented, but repeats, conflicting same-time prices, sparse gaps and exact requested-since timestamps prevent confident identification of the generating process from these data alone.

Phase 4 remains COMPLETE and frozen. Phase 5A is an audit, not a final labeling implementation. **Phase 5B is NOT YET IMPLEMENTED:** observation sufficiency, before/after coverage use, thresholds, state persistence and the final 1/0/UNKNOWN methodology remain undecided pending human review. No labels, model-ready data, feature engineering or modeling changes were created.
