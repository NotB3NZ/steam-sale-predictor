"""Phase 3: deterministic diagnostic diversity pilot; no API collection."""
from collections import Counter
import hashlib
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

# Reuse the existing schema/validation contract without running Phase 2.
_spec = importlib.util.spec_from_file_location('games_master', Path(__file__).with_name('01_build_games_master.py'))
_master = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_master)
MASTER_COLUMNS = _master.COLUMNS
ROOT = Path(__file__).resolve().parent.parent
MASTER_PATH = ROOT / 'data/intermediate/games_master.csv'
OUTPUT_PATH = ROOT / 'data/intermediate/pilot_games.csv'
REPORT_PATH = ROOT / 'reports/pilot_sample_report.md'
RANDOM_SEED = 42
TARGET_SIZE = 100
CORE_SIZE = 80
CUTOFF = '2023-11-21'
ERAS = ['Before 2015', '2015–2018', '2019–2020', '2021–2022', '2023 through 2023-11-21']
PRICE_BANDS = ['Low price', 'Lower-mid price', 'Upper-mid price', 'High price']
OWNER_GROUPS = ['Zero/unknown', 'Low (upper bound <= 20,000)',
                'Moderate (20,000 < upper bound <= 200,000)', 'Popular (upper bound > 200,000)']
PILOT_COLUMNS = ['pilot_release_era', 'pilot_price_band', 'pilot_owner_group',
                 'pilot_activity_group', 'pilot_publisher_portfolio_group',
                 'pilot_selection_reason']
GENRE_TARGETS = ['Adventure', 'RPG', 'Strategy', 'Simulation', 'Racing', 'Sports', 'Massively Multiplayer']


def sha256(path):
    return _master.digest(path)


def tokens(value):
    """Exact, case-sensitive comma tokens; never rewrite the original text."""
    if pd.isna(value):
        return frozenset()
    return frozenset(t.strip() for t in str(value).split(',') if t.strip())


def load_master():
    frame = pd.read_csv(MASTER_PATH, keep_default_na=False, na_values=[''], low_memory=False)
    _master.validate(frame)
    for column in ['Peak CCU', 'DLC count']:
        numeric = pd.to_numeric(frame[column], errors='coerce')
        if not (np.isfinite(numeric).all() and numeric.ge(0).all()):
            raise ValueError(f'Invalid sampling diagnostic {column}')
    return frame


def allocate(total, counts):
    """Largest-remainder quotas proportional to square-root stratum size."""
    weights = np.sqrt(np.asarray(counts, dtype=float))
    if weights.sum() == 0:
        raise ValueError('No available strata')
    exact = total * weights / weights.sum()
    quota = np.floor(exact).astype(int)
    order = sorted(range(len(quota)), key=lambda i: (-(exact[i] - quota[i]), i))
    for i in order[:total - int(quota.sum())]:
        quota[i] += 1
    return quota.tolist()


def prepare(master):
    candidate = master.loc[master.release_date.le(CUTOFF)].copy()
    if len(candidate) < TARGET_SIZE:
        raise ValueError('Fewer than 100 historically eligible games; review required')
    quartiles = candidate.Price.quantile([.25, .5, .75]).tolist()
    if not quartiles[0] < quartiles[1] < quartiles[2]:
        raise ValueError('Price quartiles are not distinct; review band strategy')
    candidate['pilot_release_era'] = pd.cut(candidate.release_year, [0, 2014, 2018, 2020, 2022, 2023], labels=ERAS).astype('object')
    candidate['pilot_price_band'] = pd.cut(candidate.Price, [-np.inf] + quartiles + [np.inf], labels=PRICE_BANDS).astype('object')
    bounds = candidate['Estimated owners'].str.extract(r'^\s*(\d+)\s*-\s*(\d+)\s*$')
    if bounds.isna().any().any():
        raise ValueError('Unexpected owner range; review group definitions')
    lower, upper = bounds[0].astype('int64'), bounds[1].astype('int64')
    if lower.gt(upper).any():
        raise ValueError('Owner range lower bound exceeds upper bound')
    candidate['_owner_upper'] = upper
    candidate['pilot_owner_group'] = np.select(
        [upper.eq(0), upper.le(20000), upper.le(200000)], OWNER_GROUPS[:3], default=OWNER_GROUPS[3])
    positive = candidate.loc[candidate['Peak CCU'].gt(0), 'Peak CCU']
    if positive.empty:
        raise ValueError('No nonzero activity games available')
    high_ccu = float(positive.quantile(.9))
    candidate['pilot_activity_group'] = np.select(
        [candidate['Peak CCU'].eq(0), candidate['Peak CCU'].lt(high_ccu)],
        ['Zero CCU', 'Nonzero below high threshold'], default='High activity')
    publisher_counts = Counter(entity for value in master.Publishers for entity in tokens(value))
    high_portfolio = float(pd.Series(list(publisher_counts.values())).quantile(.95))
    candidate['_publisher_tokens'] = candidate.Publishers.map(tokens)
    candidate['_genre_tokens'] = candidate.Genres.map(tokens)
    candidate['_portfolio'] = candidate['_publisher_tokens'].map(lambda entities: max((publisher_counts[e] for e in entities), default=0))
    candidate['pilot_publisher_portfolio_group'] = np.select(
        [candidate['_portfolio'].eq(0), candidate['_portfolio'].le(2), candidate['_portfolio'].lt(high_portfolio)],
        ['Missing', 'Small (1–2 titles)', 'Middle portfolio'], default='High portfolio')
    candidate['_self_published_proxy'] = [bool(tokens(dev) & pub) for dev, pub in zip(candidate.Developers, candidate['_publisher_tokens'])]
    # Stable pseudorandom priority based on identifier, not source row order.
    candidate['_rank'] = candidate.AppID.map(lambda appid: hashlib.sha256(f'{RANDOM_SEED}:{int(appid)}'.encode()).hexdigest())
    candidate = candidate.sort_values(['_rank', 'AppID']).set_index('AppID', drop=False)
    config = {'quartiles': quartiles, 'high_ccu': high_ccu, 'high_portfolio': high_portfolio,
              'publisher_counts': publisher_counts}
    return candidate, config


def select(candidate, config):
    reasons = {}
    publisher_used = Counter()
    era_quota = allocate(CORE_SIZE, [candidate.pilot_release_era.eq(era).sum() for era in ERAS])

    def choose(mask, reason, reuse=False):
        pool = candidate.loc[mask]
        if reuse:
            already = [appid for appid in pool.index if appid in reasons]
            if already:
                appid = already[0]
                if reason not in reasons[appid]:
                    reasons[appid].append(reason)
                return appid
        for appid, row in pool.iterrows():
            if appid not in reasons and all(publisher_used[e] < 2 for e in row['_publisher_tokens']):
                if len(reasons) >= TARGET_SIZE:
                    raise ValueError('Supplement budget exceeded; review sampling approach')
                reasons[appid] = [reason]
                publisher_used.update(row['_publisher_tokens'])
                return appid
        raise ValueError(f'No candidates within publisher cap for {reason}; review required')

    # Broad ordinary core: era/price strata with an activity cycle.
    activity_cycle = ['Zero CCU', 'Nonzero below high threshold', 'Zero CCU', 'High activity']
    core_allocations = []
    for era, era_total in zip(ERAS, era_quota):
        era_mask = candidate.pilot_release_era.eq(era)
        quotas = allocate(era_total, [(era_mask & candidate.pilot_price_band.eq(band)).sum() for band in PRICE_BANDS])
        slot = 0
        for band, quota in zip(PRICE_BANDS, quotas):
            mask = era_mask & candidate.pilot_price_band.eq(band)
            core_allocations.append((era, band, quota))
            for _ in range(quota):
                activity = activity_cycle[slot % len(activity_cycle)]
                slot += 1
                try:
                    choose(mask & candidate.pilot_activity_group.eq(activity), 'stratified_core')
                except ValueError:
                    # Sparse activity intersections may fall back to the era/price cell.
                    choose(mask, 'stratified_core')

    # Tag existing coverage when possible; otherwise add one diagnostic case.
    edges = [
        ('edge_high_price', candidate.Price.eq(candidate.Price.max()), 'Highest eligible source price; atypical price histories.'),
        ('edge_high_dlc', candidate['DLC count'].eq(candidate['DLC count'].max()), 'Highest eligible DLC count; complex product metadata.'),
        ('edge_zero_owners', candidate['Estimated owners'].eq('0 - 0'), 'Unknown/zero source owners; possible weak history coverage.'),
        ('edge_zero_ccu', candidate['Peak CCU'].eq(0), 'No measured snapshot activity; coverage comparison.'),
        ('edge_missing_tags', candidate.Tags.isna(), 'Sparse content metadata.'),
        ('edge_missing_genres', candidate.Genres.isna(), 'Missing genre diagnostic.'),
        ('edge_missing_publisher', candidate.Publishers.isna(), 'Missing publisher/matching diagnostic.'),
        ('edge_oldest', candidate.release_date.eq(candidate.release_date.min()), 'Longest possible release history.'),
        ('edge_near_cutoff', candidate.release_date.eq(candidate.release_date.max()), 'Shortest pre-2023-sale release history.'),
        ('edge_high_activity', candidate['Peak CCU'].eq(candidate['Peak CCU'].max()), 'Highest eligible measured activity; coverage sanity check.'),
        ('edge_low_price', candidate.Price.eq(candidate.Price.min()), 'Lowest paid source price; rounding/price-history diagnostic.'),
        ('edge_high_owners', candidate['_owner_upper'].eq(candidate['_owner_upper'].max()), 'Largest owner range; popularity coverage comparison.'),
    ]
    for reason, mask, _ in edges:
        if mask.any():
            choose(mask, reason, reuse=True)

    # Simple supplementation, not a balancing optimization.
    for genre in GENRE_TARGETS:
        mask = candidate['_genre_tokens'].map(lambda genres: genre in genres)
        while mask.reindex(list(reasons)).sum() < 3:
            choose(mask, 'genre_supplement')
    puzzle = candidate.Tags.map(lambda value: 'Puzzle' in tokens(value))
    while puzzle.reindex(list(reasons)).sum() < 2:
        choose(puzzle, 'genre_supplement_puzzle_tag')
    for mask, minimum, reason in [
        (candidate['_portfolio'].ge(config['high_portfolio']), 5, 'publisher_diversity_high_portfolio'),
        (candidate['_portfolio'].between(1, 2), 5, 'publisher_diversity_small_portfolio'),
        (candidate['_self_published_proxy'], 5, 'publisher_diversity_developer_overlap'),
        (candidate.pilot_owner_group.eq(OWNER_GROUPS[3]), 10, 'ownership_diversity'),
    ]:
        while mask.reindex(list(reasons)).sum() < minimum:
            choose(mask, reason)

    # Fill remaining slots from the least-covered era/price cell, by stable rank.
    while len(reasons) < TARGET_SIZE:
        current = candidate.loc[list(reasons)]
        cells = [(int((current.pilot_release_era.eq(era) & current.pilot_price_band.eq(band)).sum()), i, j, era, band)
                 for i, era in enumerate(ERAS) for j, band in enumerate(PRICE_BANDS)]
        for _, _, _, era, band in sorted(cells):
            try:
                choose(candidate.pilot_release_era.eq(era) & candidate.pilot_price_band.eq(band), 'diversity_fill')
                break
            except ValueError:
                continue
        else:
            raise ValueError('Unable to fill 100 games under publisher cap')
    pilot = candidate.loc[list(reasons), MASTER_COLUMNS + PILOT_COLUMNS[:-1]].copy()
    pilot['pilot_selection_reason'] = [';'.join(reasons[appid]) for appid in pilot.index]
    return pilot.sort_index().reset_index(drop=True), core_allocations, edges


def validate(pilot, master, candidate, config):
    if list(pilot.columns) != MASTER_COLUMNS + PILOT_COLUMNS or len(pilot) != TARGET_SIZE:
        raise ValueError('Unexpected pilot size/schema')
    _master.validate(pilot[MASTER_COLUMNS])
    if not pilot.AppID.isin(master.AppID).all() or not pilot.release_date.le(CUTOFF).all():
        raise ValueError('Invalid source membership or historical cutoff')
    original = master.set_index('AppID').loc[pilot.AppID].reset_index()[MASTER_COLUMNS]
    pd.testing.assert_frame_equal(pilot[MASTER_COLUMNS].reset_index(drop=True), original, check_dtype=False)
    diagnostics = candidate.loc[pilot.AppID, PILOT_COLUMNS[:-1]].reset_index(drop=True)
    pd.testing.assert_frame_equal(pilot[PILOT_COLUMNS[:-1]], diagnostics, check_dtype=False)
    if pilot.pilot_selection_reason.isna().any() or pilot.pilot_selection_reason.eq('').any():
        raise ValueError('Missing selection reason')
    for column, levels in [('pilot_release_era', ERAS), ('pilot_price_band', PRICE_BANDS),
                           ('pilot_owner_group', OWNER_GROUPS)]:
        if set(pilot[column]) != set(levels):
            raise ValueError(f'Missing diversity in {column}')
    if set(pilot.pilot_activity_group) != {'Zero CCU', 'Nonzero below high threshold', 'High activity'}:
        raise ValueError('Missing activity diversity')
    publisher_counts = Counter(e for value in pilot.Publishers for e in tokens(value))
    if max(publisher_counts.values(), default=0) > 2:
        raise ValueError('Publisher concentration cap exceeded')
    for genre in GENRE_TARGETS:
        if sum(genre in tokens(value) for value in pilot.Genres) < 3:
            raise ValueError(f'Missing target genre coverage: {genre}')
    if sum('Puzzle' in tokens(value) for value in pilot.Tags) < 2:
        raise ValueError('Missing Puzzle tag coverage')
    for c in ['Tags', 'Genres', 'Publishers']:
        if not pilot[c].isna().any():
            raise ValueError(f'Missing diagnostic case: {c}')
    for c in ['Price', 'DLC count', 'Peak CCU']:
        if pilot[c].max() != candidate[c].max():
            raise ValueError(f'Missing diagnostic maximum: {c}')
    edge_count = pilot.pilot_selection_reason.str.contains('edge_').sum()
    if not 10 <= edge_count <= 20:
        raise ValueError(f'Expected 10–20 diagnostic games, got {edge_count}')


def report(pilot, master, candidate, config, quotas, edges, master_hash, pilot_hash):
    table = _master.table
    counts = lambda col, levels: [(level, int(candidate[col].eq(level).sum()), int(pilot[col].eq(level).sum())) for level in levels]
    q1, q2, q3 = config['quartiles']
    lines = ['# Pilot Sample Report — Phase 3', '',
             '**Validation: PASS.** Pipeline-validation pilot / diagnostic diversity sample.', '',
             '## Purpose and candidate population', '',
             'The pilot stress-tests later historical Steam price collection across ordinary games, differing metadata/activity, and a small set of unusual cases. It is not a statistically representative survey, final modeling sample, training dataset, or sale-label dataset.', '',
             f'- Master catalog: {len(master):,} paid candidates, {len(MASTER_COLUMNS)} source columns.',
             f'- Historically eligible: {len(candidate):,} (`release_date <= {CUTOFF}`).',
             f'- Excluded from this pilot only: {len(master)-len(candidate):,} released later.',
             f'- Final pilot: {len(pilot)} unique games, all within the core historical cutoff; no post-cutoff exceptions.', '',
             'The 2023 cutoff applies only to this historical-data pilot. Later modeling populations can include newer releases for applicable sale events.', '',
             '## Reproducible sampling method', '',
             f'Run `python3 src/02_create_pilot.py`. Seed: **{RANDOM_SEED}**. Candidate priority is ascending SHA-256 of `42:AppID`, with AppID as a tie-breaker. This is a deterministic pseudorandom ranking independent of input row order. Output is sorted by AppID.', '',
             '1. Select 80 ordinary core games. Allocate release-era quotas proportional to the square root of eligible era counts, using largest remainders (ties follow listed era order). Allocate each era quota across its price bands the same way. This increases older-game coverage without allocating equal counts blindly.',
             '2. Within each era, cycle requested activity groups: zero CCU, nonzero below the high threshold, zero CCU, high activity. Choose the first available ranked candidate in the era/price/activity cell; if unavailable under the publisher cap, use the era/price cell.',
             '3. Cover 12 diagnostic criteria in the listed order. If an already selected game meets a criterion, append its reason; otherwise add the first qualifying ranked candidate. A game can satisfy multiple criteria without duplication.',
             '4. Supplement until each of Adventure, RPG, Strategy, Simulation, Racing, Sports, and Massively Multiplayer has at least 3 games, and the exact Puzzle tag has at least 2. Ensure at least 5 high-portfolio publishers’ games, 5 small-portfolio games, 5 developer/publisher-overlap games, and 10 games in the popular owner group.',
             '5. Fill to 100 from the least-covered era/price cell (ties follow listed era and band order), respecting the publisher cap. The script fails if the supplementation budget/candidate pool cannot support these rules.', '',
             'Every new selection is limited to two games per parsed publisher entity, including co-publishers. Missing publishers have no shared entity and remain eligible. No titles are selected by fame or external lookup.', '',
             '### Temporary diagnostic definitions', '',
             f'Eligible-population source-price quartiles: **{q1:g}, {q2:g}, {q3:g}**. Bands are `(0, {q1:g}]`, `({q1:g}, {q2:g}]`, `({q2:g}, {q3:g}]`, and `>{q3:g}`. Boundaries include the right endpoint; source Price is unchanged.',
             f'High activity starts at **{config["high_ccu"]:g} Peak CCU**, the 90th percentile among eligible nonzero CCU games. Zero CCU is a separate group.',
             'Owner ranges are grouped by the source upper bound: zero, up to 20,000, above 20,000 through 200,000, and above 200,000. This is a sampling-only grouping, not a midpoint estimate; source text is unchanged.',
             f'Publisher portfolios count each exact, trimmed comma-delimited entity at most once per master game. High portfolio starts at **{config["high_portfolio"]:g} titles**, the 95th percentile across distinct nonmissing publisher entities in the full master. Small portfolios contain 1–2 titles. Co-published games use the largest associated portfolio for grouping, while concentration counts each entity.',
             'Publisher/developer overlap means at least one exact parsed token is shared; it is only an independent/self-published-looking proxy, not verified corporate ownership. Portfolio size does not establish AAA status or name recognition. Commas embedded in organization names may cause false token splits; no subjective aliases or case-merging are applied.',
             'Genres and Tags use exact trimmed comma tokens only for diagnostics. Puzzle is present in Tags rather than the Genres taxonomy. No one-hot encoding, imputation, historical feature approval, or master modification occurs.', '',
             'Core allocation before supplementation:', '', table(['Era', 'Price band', 'Core quota'], quotas), '',
             '## Distribution diagnostics', '']
    for title, column, levels in [('Release era', 'pilot_release_era', ERAS), ('Price band', 'pilot_price_band', PRICE_BANDS),
                                  ('Owners group', 'pilot_owner_group', OWNER_GROUPS),
                                  ('Activity', 'pilot_activity_group', ['Zero CCU', 'Nonzero below high threshold', 'High activity']),
                                  ('Publisher portfolio', 'pilot_publisher_portfolio_group', ['Missing', 'Small (1–2 titles)', 'Middle portfolio', 'High portfolio'])]:
        lines += [f'### {title}', '', table(['Group', 'Eligible candidates', 'Pilot'], counts(column, levels)), '']
    genres = Counter(e for value in pilot.Genres for e in tokens(value))
    publishers = Counter(e for value in pilot.Publishers for e in tokens(value))
    lines += ['### Genres (multi-label counts, may exceed 100)', '', table(['Genre', 'Games'], sorted(genres.items(), key=lambda item: (-item[1], item[0]))), '',
              f'Exact Puzzle tag: {sum("Puzzle" in tokens(v) for v in pilot.Tags)} games.', '',
              '### Publisher concentration', '',
              f'Distinct parsed publisher entities: {len(publishers)}. Maximum games per entity: {max(publishers.values(), default=0)}. Developer/publisher overlap proxy: {int(candidate.loc[pilot.AppID, "_self_published_proxy"].sum())} games.', '',
              table(['Publisher entity', 'Pilot titles', 'Master portfolio'], [(e, n, config['publisher_counts'][e]) for e, n in sorted(publishers.items(), key=lambda item: (-item[1], item[0]))[:15]]), '',
              '### Missing metadata', '', table(['Field', 'Pilot missing', 'Percent'], [(c, int(pilot[c].isna().sum()), f'{pilot[c].isna().mean():.1%}') for c in ['Tags', 'Genres', 'Publishers']]), '',
              '### Selection reasons (overlap allowed)', '', table(['Reason', 'Games'], sorted(Counter(r for value in pilot.pilot_selection_reason for r in value.split(';')).items())), '',
              '## Intentionally retained diagnostic cases', '',
              f'{int(pilot.pilot_selection_reason.str.contains("edge_").sum())} distinct games carry edge-case reasons. Broad properties such as zero CCU may also occur in ordinary core games; they are not all counted as intentionally reserved edge cases.', '']
    edge_rows = []
    for reason, mask, rationale in edges:
        for _, row in pilot.loc[pilot.pilot_selection_reason.str.split(';').map(lambda values: reason in values)].iterrows():
            edge_rows.append((reason, row.AppID, row.Name, rationale))
    lines += [table(['Criterion', 'AppID', 'Name', 'Use'], edge_rows), '',
              '## Validation and reproducibility', '',
              'PASS: exactly 100 unique AppIDs; exact intended schema; source membership and all 30 source-column values preserved; positive numeric prices; valid names/dates; every game meets the historical cutoff; all eras, price bands, owner groups, and activity groups represented; target genres, missing metadata, diagnostic maxima, and publisher cap checked.', '',
              'Two selections produce identical CSV bytes. A selection after shuffling the master rows (seed 43) also produces identical bytes. The saved CSV is reloaded and validated. A second full script execution must produce the same pilot/report hashes; this is verified at Phase 3 completion.', '',
              f'Pilot CSV SHA-256: `{pilot_hash}`.', '', f'Master CSV SHA-256 (unchanged before/after run): `{master_hash}`.', '',
              '## Limitations', '',
              'This is not the final modeling sample. Current Price, CCU, owners, DLC count, portfolio size, Tags, and other metadata are snapshots of unknown timing. Sampling with these values does not approve them as historical predictors. The intentionally diversity-oriented sample has unequal inclusion probabilities and no survey weights; model performance must never be evaluated as though these 100 games were a random population sample.', '',
              'The paid master includes some software/non-game products; diagnostic extremes may expose these. They are retained consistently with the approved master population, with original Genres available for review. Missing metadata and publisher-token ambiguity are not grounds for silent exclusion. ITAD matching and historical coverage are still unknown.', '',
              'No ITAD/Steam/external API calls, scraping, labels, game × sale-year rows, or model work occurred. Stopped before Phase 4.', '',
              '## Human sanity view', '',
              'Approximately 20 records: all intentional edge cases plus pseudorandom ordinary core records. Together they cover old/new, cheap/expensive, and low/high activity.', '']
    edge_view = pilot.loc[pilot.pilot_selection_reason.str.contains('edge_')]
    ordinary = pilot.loc[~pilot.AppID.isin(edge_view.AppID) & pilot.pilot_selection_reason.str.contains('stratified_core')].copy()
    ordinary['_view_rank'] = ordinary.AppID.map(lambda appid: hashlib.sha256(f'{RANDOM_SEED}:view:{appid}'.encode()).hexdigest())
    view = pd.concat([edge_view, ordinary.sort_values('_view_rank').head(max(0, 20-len(edge_view)))])
    columns = ['AppID', 'Name', 'release_date', 'Price', 'Estimated owners', 'Peak CCU', 'Genres', 'Publishers', 'pilot_selection_reason']
    lines += [table(columns, [['(missing)' if pd.isna(row[c]) else row[c] for c in columns] for _, row in view.iterrows()]), '']
    REPORT_PATH.write_text('\n'.join(lines), encoding='utf-8')


def build(master):
    candidate, config = prepare(master)
    pilot, quotas, edges = select(candidate, config)
    validate(pilot, master, candidate, config)
    return pilot, candidate, config, quotas, edges


def main():
    before = sha256(MASTER_PATH)
    master = load_master()
    pilot, candidate, config, quotas, edges = build(master)
    csv_bytes = pilot.to_csv(index=False).encode('utf-8')
    repeated, _, _, _, _ = build(master)
    shuffled, _, _, _, _ = build(master.sample(frac=1, random_state=RANDOM_SEED + 1))
    if csv_bytes != repeated.to_csv(index=False).encode('utf-8') or csv_bytes != shuffled.to_csv(index=False).encode('utf-8'):
        raise ValueError('Selection is not deterministic / row-order independent')
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_bytes(csv_bytes)
    saved = pd.read_csv(OUTPUT_PATH, keep_default_na=False, na_values=[''], low_memory=False)
    validate(saved, master, candidate, config)
    pd.testing.assert_frame_equal(pilot, saved, check_dtype=False)
    if sha256(MASTER_PATH) != before:
        raise ValueError('Master CSV changed during sampling')
    report(saved, master, candidate, config, quotas, edges, before, sha256(OUTPUT_PATH))
    print(f'Master: {len(master):,}; historically eligible: {len(candidate):,}; pilot: {len(saved)}')
    for c in ['pilot_release_era', 'pilot_price_band', 'pilot_owner_group', 'pilot_activity_group']:
        print(f'{c}: {saved[c].value_counts().to_dict()}')
    print(f'Validation: PASS; master unchanged; repeated and shuffled selections identical.\nPilot SHA-256: {sha256(OUTPUT_PATH)}')
    print(f'Output: {OUTPUT_PATH}\nReport: {REPORT_PATH}\nStopped before Phase 4; no API calls.')


if __name__ == '__main__':
    main()
