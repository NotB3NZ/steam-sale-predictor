# Games Master Report — Phase 2

Validation: **PASS** (in-memory and saved CSV). One row = one Steam game.

This is a cleaned catalog for Phase 3 sampling, not a model dataset. Retention does not approve any variable as a historical predictor.

## Cleaning audit

Original rows: **125,855**. Final rows: **99,194**. Columns: **30**.

Failures count each rule on the original data; sequential removals apply rules in the order shown, avoiding double-counting.

| Rule | Failing rule | Sequentially removed |
| --- | --- | --- |
| Invalid AppID | 0 | 0 |
| Missing/invalid name | 1 | 1 |
| Invalid release date | 0 | 0 |
| Invalid price | 0 | 0 |
| Price <= 0 | 26661 | 26660 |

Zero source prices: 26,661; negative source prices: 0.

## Decisions and provenance

- Titles with source `Price <= 0` are excluded from the paid-game candidate population. This does not establish that all excluded titles are permanently free/free-to-play.
- AppIDs must be positive whole numbers within the Steam unsigned 32-bit identifier range; duplicate retained IDs cause validation failure rather than silent deduplication.
- Names are trimmed; release dates use YYYY-MM-DD and release_year is derived. Source order is preserved.
- Optional missing metadata remains missing. Literal text such as NA is preserved; empty CSV fields are missing.
- Estimated owners remains source text; zero-owner and zero-CCU games remain eligible. Multi-value fields are not encoded.
- No historical-event release cutoff is applied. Snapshot date is unknown in existing documentation; no future-release flag is created.
- Discount is a scrape-time snapshot, NOT approved as a historical feature or sale label. No age_at_sale, labels, or sale-year rows are created.
- Shared source_schema.py supplies the same corrected 40-column schema to Phases 1 and 2. Header and record widths are checked before loading.

Source SHA-256 (verified unchanged after processing): `1b48008b01a799d82385d6e66ba0cb65dd477b6aa4b6c2ec8c443025ab6880ad`.

## Temporal classification of retained variables

| Category | Variables | Interpretation |
| --- | --- | --- |
| A. Structural / identifier | AppID; Name | Identity/provenance, not predictors. |
| B. Historically derivable | release_date; release_year | Age can later be calculated relative to sale_start_date; source release-date accuracy remains an assumption. |
| C. Relatively stable metadata | Developers; Publishers; Genres; Required age; Windows; Mac; Linux | May change; not guaranteed historically unchanged or approved for modeling. |
| D. Snapshot / temporally contaminated | Price; Discount; DLC count; Estimated owners; Peak CCU; Metacritic score; User score; Positive; Negative; Achievements; Recommendations; all four playtime statistics; Tags; Categories; Supported languages; Full audio languages | Unknown observation time; may reflect changes or activity after historical events. Requires later temporal assessment/reconstruction. |

## E. Removed / unusable source columns

| Column | Reason |
| --- | --- |
| About the game | Free text outside tabular scope |
| Reviews | Free text outside tabular scope |
| Header image | Media/contact/URL metadata outside tabular scope |
| Website | Media/contact/URL metadata outside tabular scope |
| Support url | Media/contact/URL metadata outside tabular scope |
| Support email | Media/contact/URL metadata outside tabular scope |
| Metacritic url | Media/contact/URL metadata outside tabular scope |
| Score rank | Nearly all missing / unclear provenance |
| Notes | Free text outside tabular scope |
| Screenshots | Media/contact/URL metadata outside tabular scope |
| Movies | Entirely empty |

## Plausibility diagnostics

- Release date range: 1997-06-30 to 2026-03-02.
- Price min/median/max: 0.49 / 3.59 / 999.98.
- DLC count min/median/max: 0 / 0 / 1066.
- Missing Genres: 109 (0.11%).
- Missing Tags: 24,478 (24.68%).
- Missing Publishers: 442 (0.45%).
- Zero Peak CCU retained: 81,702.
- "0 - 0" Estimated owners retained: 7,872.

Release-year distribution:

| Year | Games |
| --- | --- |
| 1997 | 1 |
| 1998 | 1 |
| 1999 | 2 |
| 2000 | 2 |
| 2001 | 4 |
| 2002 | 1 |
| 2003 | 3 |
| 2004 | 5 |
| 2005 | 6 |
| 2006 | 63 |
| 2007 | 80 |
| 2008 | 145 |
| 2009 | 300 |
| 2010 | 229 |
| 2011 | 232 |
| 2012 | 285 |
| 2013 | 420 |
| 2014 | 1395 |
| 2015 | 2231 |
| 2016 | 3546 |
| 2017 | 5018 |
| 2018 | 6266 |
| 2019 | 6102 |
| 2020 | 7312 |
| 2021 | 8783 |
| 2022 | 9400 |
| 2023 | 11072 |
| 2024 | 14860 |
| 2025 | 18577 |
| 2026 | 2853 |

## Record alignment sanity checks

Deterministic random records (seed 42) plus diagnostic extremes. Unusual values are retained.

| Selection | AppID | Name | release_date | Price | Discount | DLC count | Estimated owners | Peak CCU | Genres | Tags |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Random 1 | 1521820 | LightWave | 2021-02-24 | 14.99 | 0 | 0 | 0 - 20000 | 0 | Action,Indie,Racing,Early Access | Racing,2D Platformer,Action,PvP,Platformer,2D,Early Access,Indie,Cyberpunk,Pixel Graphics,Stylized,Sci-fi,Futuristic,Retro,4 Player Local,Multiplayer,Singleplayer |
| Random 2 | 2511650 | Burden of the Blue | 2025-05-16 | 6.49 | 35 | 0 | 0 - 20000 | 0 | Action,Adventure,Indie | Exploration,Action-Adventure,Dungeon Crawler,2D,Top-Down,Nonlinear,Action,Pixel Graphics,Atmospheric,Adventure,Singleplayer,Indie |
| Random 3 | 1316720 | THE 8IGHT | 2025-01-24 | 1.59 | 80 | 0 | 0 - 20000 | 2 | Adventure,Indie | Adventure,Indie,Horror,Psychological Horror,Puzzle,Immersive Sim,3D,Story Rich,Singleplayer |
| Random 4 | 4240280 | My Wifey | 2026-01-05 | 0.89 | 0 | 5 | 0 - 0 | 0 | Simulation,Early Access | (missing) |
| High price | 2504210 | The Leverage Game Business Edition | 2023-08-26 | 999.98 | 0 | 0 | 0 - 20000 | 0 | Indie,Simulation | (missing) |
| High DLC | 363890 | RPG Maker MV | 2015-10-23 | 11.99 | 85 | 1066 | 200000 - 500000 | 657 | RPG,Design & Illustration,Education,Web Publishing,Game Development | RPG,RPGMaker,Game Development,Anime,GameMaker,Design & Illustration,Web Publishing,JRPG,Software,2D,Singleplayer,Pixel Graphics,Action RPG,Education,Multiplayer,MMORPG,Sandbox |
| Zero owners | 3854040 | BRUTALISMUS: Dystopia | 2025-07-31 | 1.39 | 0 | 1 | 0 - 0 | 0 | Adventure,Casual,Indie,Simulation | (missing) |
| Missing Tags | 3292190 | 버튜버 파라노이아 - Vtuber Paranoia | 2024-10-31 | 8.99 | 0 | 1 | 0 - 20000 | 1 | Casual,Indie,Simulation | (missing) |

## Validation and remaining limitations

PASS: nonempty table; exact intended columns; valid, nonnull, unique AppIDs; nonblank names; valid standardized dates and matching years; finite numeric strictly positive prices. Saved CSV was reloaded and compared against the cleaned table.

Snapshot reference date and historical validity of retained metadata remain unresolved. Extreme prices/DLC counts, missing optional fields, and sparse engagement are preserved rather than used as exclusion rules.

Stopped before Phase 3. No external API requests, sampling dataset, feature encoding, labels, or modeling were performed.
