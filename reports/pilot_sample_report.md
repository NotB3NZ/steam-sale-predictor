# Pilot Sample Report — Phase 3

**Validation: PASS.** Pipeline-validation pilot / diagnostic diversity sample.

## Purpose and candidate population

The pilot stress-tests later historical Steam price collection across ordinary games, differing metadata/activity, and a small set of unusual cases. It is not a statistically representative survey, final modeling sample, training dataset, or sale-label dataset.

- Master catalog: 99,194 paid candidates, 30 source columns.
- Historically eligible: 61,681 (`release_date <= 2023-11-21`).
- Excluded from this pilot only: 37,513 released later.
- Final pilot: 100 unique games, all within the core historical cutoff; no post-cutoff exceptions.

The 2023 cutoff applies only to this historical-data pilot. Later modeling populations can include newer releases for applicable sale events.

## Reproducible sampling method

Run `python3 src/02_create_pilot.py`. Seed: **42**. Candidate priority is ascending SHA-256 of `42:AppID`, with AppID as a tie-breaker. This is a deterministic pseudorandom ranking independent of input row order. Output is sorted by AppID.

1. Select 80 ordinary core games. Allocate release-era quotas proportional to the square root of eligible era counts, using largest remainders (ties follow listed era order). Allocate each era quota across its price bands the same way. This increases older-game coverage without allocating equal counts blindly.
2. Within each era, cycle requested activity groups: zero CCU, nonzero below the high threshold, zero CCU, high activity. Choose the first available ranked candidate in the era/price/activity cell; if unavailable under the publisher cap, use the era/price cell.
3. Cover 12 diagnostic criteria in the listed order. If an already selected game meets a criterion, append its reason; otherwise add the first qualifying ranked candidate. A game can satisfy multiple criteria without duplication.
4. Supplement until each of Adventure, RPG, Strategy, Simulation, Racing, Sports, and Massively Multiplayer has at least 3 games, and the exact Puzzle tag has at least 2. Ensure at least 5 high-portfolio publishers’ games, 5 small-portfolio games, 5 developer/publisher-overlap games, and 10 games in the popular owner group.
5. Fill to 100 from the least-covered era/price cell (ties follow listed era and band order), respecting the publisher cap. The script fails if the supplementation budget/candidate pool cannot support these rules.

Every new selection is limited to two games per parsed publisher entity, including co-publishers. Missing publishers have no shared entity and remain eligible. No titles are selected by fame or external lookup.

### Temporary diagnostic definitions

Eligible-population source-price quartiles: **1.19, 2.99, 5.99**. Bands are `(0, 1.19]`, `(1.19, 2.99]`, `(2.99, 5.99]`, and `>5.99`. Boundaries include the right endpoint; source Price is unchanged.
High activity starts at **89.4 Peak CCU**, the 90th percentile among eligible nonzero CCU games. Zero CCU is a separate group.
Owner ranges are grouped by the source upper bound: zero, up to 20,000, above 20,000 through 200,000, and above 200,000. This is a sampling-only grouping, not a midpoint estimate; source text is unchanged.
Publisher portfolios count each exact, trimmed comma-delimited entity at most once per master game. High portfolio starts at **4 titles**, the 95th percentile across distinct nonmissing publisher entities in the full master. Small portfolios contain 1–2 titles. Co-published games use the largest associated portfolio for grouping, while concentration counts each entity.
Publisher/developer overlap means at least one exact parsed token is shared; it is only an independent/self-published-looking proxy, not verified corporate ownership. Portfolio size does not establish AAA status or name recognition. Commas embedded in organization names may cause false token splits; no subjective aliases or case-merging are applied.
Genres and Tags use exact trimmed comma tokens only for diagnostics. Puzzle is present in Tags rather than the Genres taxonomy. No one-hot encoding, imputation, historical feature approval, or master modification occurs.

Core allocation before supplementation:

| Era | Price band | Core quota |
| --- | --- | --- |
| Before 2015 | Low price | 2 |
| Before 2015 | Lower-mid price | 2 |
| Before 2015 | Upper-mid price | 2 |
| Before 2015 | High price | 2 |
| 2015–2018 | Low price | 5 |
| 2015–2018 | Lower-mid price | 5 |
| 2015–2018 | Upper-mid price | 5 |
| 2015–2018 | High price | 5 |
| 2019–2020 | Low price | 5 |
| 2019–2020 | Lower-mid price | 4 |
| 2019–2020 | Upper-mid price | 4 |
| 2019–2020 | High price | 4 |
| 2021–2022 | Low price | 5 |
| 2021–2022 | Lower-mid price | 5 |
| 2021–2022 | Upper-mid price | 5 |
| 2021–2022 | High price | 5 |
| 2023 through 2023-11-21 | Low price | 3 |
| 2023 through 2023-11-21 | Lower-mid price | 4 |
| 2023 through 2023-11-21 | Upper-mid price | 4 |
| 2023 through 2023-11-21 | High price | 4 |

## Distribution diagnostics

### Release era

| Group | Eligible candidates | Pilot |
| --- | --- | --- |
| Before 2015 | 3174 | 20 |
| 2015–2018 | 17061 | 24 |
| 2019–2020 | 13414 | 18 |
| 2021–2022 | 18183 | 21 |
| 2023 through 2023-11-21 | 9849 | 17 |

### Price band

| Group | Eligible candidates | Pilot |
| --- | --- | --- |
| Low price | 15821 | 25 |
| Lower-mid price | 15903 | 25 |
| Upper-mid price | 14552 | 23 |
| High price | 15405 | 27 |

### Owners group

| Group | Eligible candidates | Pilot |
| --- | --- | --- |
| Zero/unknown | 459 | 1 |
| Low (upper bound <= 20,000) | 42713 | 47 |
| Moderate (20,000 < upper bound <= 200,000) | 14565 | 27 |
| Popular (upper bound > 200,000) | 3944 | 25 |

### Activity

| Group | Eligible candidates | Pilot |
| --- | --- | --- |
| Zero CCU | 49434 | 53 |
| Nonzero below high threshold | 11022 | 23 |
| High activity | 1225 | 24 |

### Publisher portfolio

| Group | Eligible candidates | Pilot |
| --- | --- | --- |
| Missing | 405 | 2 |
| Small (1–2 titles) | 28372 | 31 |
| Middle portfolio | 4242 | 4 |
| High portfolio | 28662 | 63 |

### Genres (multi-label counts, may exceed 100)

| Genre | Games |
| --- | --- |
| Indie | 69 |
| Action | 45 |
| Adventure | 38 |
| Casual | 37 |
| Strategy | 22 |
| RPG | 19 |
| Simulation | 19 |
| Early Access | 8 |
| Massively Multiplayer | 4 |
| Racing | 4 |
| Sports | 3 |
| Design & Illustration | 1 |
| Education | 1 |
| Game Development | 1 |
| Gore | 1 |
| Violent | 1 |
| Web Publishing | 1 |

Exact Puzzle tag: 19 games.

### Publisher concentration

Distinct parsed publisher entities: 103. Maximum games per entity: 2. Developer/publisher overlap proxy: 62 games.

| Publisher entity | Pilot titles | Master portfolio |
| --- | --- | --- |
| 2K | 2 | 81 |
| Aspyr (Mac) | 2 | 14 |
| BFG Entertainment | 2 | 535 |
| Ltd. | 2 | 434 |
| Raw Fury | 2 | 50 |
| Ubisoft | 2 | 131 |
| .orphans | 1 | 1 |
| 2x2 Games | 1 | 2 |
| 90% Studios | 1 | 3 |
| A&S Inc. | 1 | 2 |
| ASOBI | 1 | 10 |
| Activision | 1 | 74 |
| Akupara Games | 1 | 42 |
| Amazon Games | 1 | 1 |
| Anamik Majumdar | 1 | 65 |

### Missing metadata

| Field | Pilot missing | Percent |
| --- | --- | --- |
| Tags | 10 | 10.0% |
| Genres | 1 | 1.0% |
| Publishers | 2 | 2.0% |

### Selection reasons (overlap allowed)

| Reason | Games |
| --- | --- |
| diversity_fill | 11 |
| edge_high_activity | 1 |
| edge_high_dlc | 1 |
| edge_high_owners | 1 |
| edge_high_price | 1 |
| edge_low_price | 1 |
| edge_missing_genres | 1 |
| edge_missing_publisher | 1 |
| edge_missing_tags | 1 |
| edge_near_cutoff | 1 |
| edge_oldest | 1 |
| edge_zero_ccu | 1 |
| edge_zero_owners | 1 |
| stratified_core | 80 |

## Intentionally retained diagnostic cases

11 distinct games carry edge-case reasons. Broad properties such as zero CCU may also occur in ordinary core games; they are not all counted as intentionally reserved edge cases.

| Criterion | AppID | Name | Use |
| --- | --- | --- | --- |
| edge_high_price | 2504210 | The Leverage Game Business Edition | Highest eligible source price; atypical price histories. |
| edge_high_dlc | 363890 | RPG Maker MV | Highest eligible DLC count; complex product metadata. |
| edge_zero_owners | 242960 | Blood Omen 2: Legacy of Kain | Unknown/zero source owners; possible weak history coverage. |
| edge_zero_ccu | 1544810 | HANDMADE CARPROGRAM | No measured snapshot activity; coverage comparison. |
| edge_missing_tags | 2205710 | Hentai Beauty | Sparse content metadata. |
| edge_missing_genres | 603210 | Valkyries | Missing genre diagnostic. |
| edge_missing_publisher | 449310 | Spunk and Moxie | Missing publisher/matching diagnostic. |
| edge_oldest | 282010 | Carmageddon Max Pack | Longest possible release history. |
| edge_near_cutoff | 2650840 | nekowater | Shortest pre-2023-sale release history. |
| edge_high_activity | 252490 | Rust | Highest eligible measured activity; coverage sanity check. |
| edge_low_price | 2205710 | Hentai Beauty | Lowest paid source price; rounding/price-history diagnostic. |
| edge_high_owners | 1063730 | New World: Aeternum | Largest owner range; popularity coverage comparison. |

## Validation and reproducibility

PASS: exactly 100 unique AppIDs; exact intended schema; source membership and all 30 source-column values preserved; positive numeric prices; valid names/dates; every game meets the historical cutoff; all eras, price bands, owner groups, and activity groups represented; target genres, missing metadata, diagnostic maxima, and publisher cap checked.

Two selections produce identical CSV bytes. A selection after shuffling the master rows (seed 43) also produces identical bytes. The saved CSV is reloaded and validated. A second full script execution must produce the same pilot/report hashes; this is verified at Phase 3 completion.

Pilot CSV SHA-256: `458ddc9042beb8f978e1607cac6eeace88bd3b9a73537bc2dae82b75c419d14e`.

Master CSV SHA-256 (unchanged before/after run): `e4fa1eb1a7d5154831badc8b82cd5e1d34409948b0559b18dee81d9192b97852`.

## Limitations

This is not the final modeling sample. Current Price, CCU, owners, DLC count, portfolio size, Tags, and other metadata are snapshots of unknown timing. Sampling with these values does not approve them as historical predictors. The intentionally diversity-oriented sample has unequal inclusion probabilities and no survey weights; model performance must never be evaluated as though these 100 games were a random population sample.

The paid master includes some software/non-game products; diagnostic extremes may expose these. They are retained consistently with the approved master population, with original Genres available for review. Missing metadata and publisher-token ambiguity are not grounds for silent exclusion. ITAD matching and historical coverage are still unknown.

No ITAD/Steam/external API calls, scraping, labels, game × sale-year rows, or model work occurred. Stopped before Phase 4.

## Human sanity view

Approximately 20 records: all intentional edge cases plus pseudorandom ordinary core records. Together they cover old/new, cheap/expensive, and low/high activity.

| AppID | Name | release_date | Price | Estimated owners | Peak CCU | Genres | Publishers | pilot_selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 242960 | Blood Omen 2: Legacy of Kain | 2013-09-24 | 0.97 | 0 - 0 | 0 | Action | Crystal Dynamics | edge_zero_owners |
| 252490 | Rust | 2018-02-08 | 19.99 | 20000000 - 50000000 | 143870 | Action,Adventure,Indie,Massively Multiplayer,RPG | Facepunch Studios | edge_high_activity |
| 282010 | Carmageddon Max Pack | 1997-06-30 | 2.49 | 100000 - 200000 | 1 | Action,Indie,Racing | THQ Nordic | edge_oldest |
| 363890 | RPG Maker MV | 2015-10-23 | 11.99 | 200000 - 500000 | 657 | RPG,Design & Illustration,Education,Web Publishing,Game Development | Gotcha Gotcha Games | edge_high_dlc |
| 449310 | Spunk and Moxie | 2016-05-06 | 0.99 | 0 - 20000 | 0 | Action,Indie | (missing) | edge_missing_publisher |
| 603210 | Valkyries | 2018-09-17 | 1.99 | 0 - 20000 | 0 | (missing) | Heartomics | edge_missing_genres |
| 1063730 | New World: Aeternum | 2021-09-28 | 59.99 | 50000000 - 100000000 | 5583 | Action,Adventure,Massively Multiplayer,RPG | Amazon Games | edge_high_owners |
| 1544810 | HANDMADE CARPROGRAM | 2021-03-15 | 1.79 | 0 - 20000 | 0 | Simulation | ストロングツリー(HusHucHuライス),Strong Tree (HusHucHu Rice) | stratified_core;edge_zero_ccu |
| 2205710 | Hentai Beauty | 2022-11-22 | 0.49 | 0 - 20000 | 0 | Casual,Indie | Reddiamondgames | stratified_core;edge_missing_tags;edge_low_price |
| 2504210 | The Leverage Game Business Edition | 2023-08-26 | 999.98 | 0 - 20000 | 0 | Indie,Simulation | A&S Inc. | edge_high_price |
| 2650840 | nekowater | 2023-11-21 | 0.99 | 0 - 20000 | 0 | Adventure,Casual,Indie | LuuuLuuuL | edge_near_cutoff |
| 666120 | Dawn of the killer zombies | 2017-07-08 | 4.99 | 0 - 20000 | 0 | Violent,Gore,Action,Adventure | Theodor Niklas | stratified_core |
| 1005530 | Club Soccer Director PRO 2020 | 2019-09-26 | 24.99 | 0 - 20000 | 1 | Indie,Simulation,Sports,Strategy | Go Play Games Ltd | stratified_core |
| 1413660 | Elderand | 2023-02-16 | 6.79 | 0 - 20000 | 9 | Action,Adventure,Indie,RPG | Graffiti Games | stratified_core |
| 1373180 | The Sea Hotel☆Umineko Tei | 2020-09-30 | 3.63 | 20000 - 50000 | 0 | Adventure,Casual,Indie,RPG,Simulation,Strategy | Starship Studio | stratified_core |
| 1418360 | Lonesome Village | 2022-11-01 | 8.99 | 0 - 20000 | 1 | Adventure,Indie | Ogre Pixel | stratified_core |
| 2009420 | Zaxterion: Space Frenzy! | 2022-09-09 | 7.99 | 0 - 20000 | 0 | Action,Indie | ZaxtorGameS | stratified_core |
| 1141280 | Super Space Slayer 2 | 2019-09-22 | 2.99 | 0 - 20000 | 0 | Action,Indie,RPG | Plasma Beam Games | stratified_core |
| 445220 | Avorion | 2020-03-09 | 9.99 | 500000 - 1000000 | 618 | Action,Indie,Simulation | Boxelware | stratified_core |
| 2387820 | Beach Gas Gas | 2023-05-03 | 4.99 | 0 - 20000 | 0 | Casual,Indie,Racing,Simulation,Sports | Gamesforgames | stratified_core |
