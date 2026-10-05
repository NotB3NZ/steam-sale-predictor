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
