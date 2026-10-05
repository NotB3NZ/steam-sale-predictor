"""Phase 2: build and validate the paid-game catalog (no historical features)."""
import csv
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from source_schema import CORRECTED_COLUMNS

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'games.csv'
OUTPUT = ROOT / 'data/intermediate/games_master.csv'
REPORT = ROOT / 'reports/games_master_report.md'
DROP = ['About the game', 'Reviews', 'Header image', 'Website', 'Support url',
        'Support email', 'Metacritic url', 'Score rank', 'Notes', 'Screenshots', 'Movies']
COLUMNS = [c if c != 'Release date' else 'release_date'
           for c in CORRECTED_COLUMNS if c not in DROP]
COLUMNS.insert(COLUMNS.index('release_date') + 1, 'release_year')


def digest(path):
    with path.open('rb') as stream:
        result = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
        return result.hexdigest()


def load_source(path):
    # Reuse Phase 1's schema, but reject unexpected headers/row widths explicitly.
    with path.open(encoding='utf-8', newline='') as stream:
        reader = csv.reader(stream)
        header = next(reader)
        expected = CORRECTED_COLUMNS.copy()
        expected[7:9] = ['DiscountDLC count']
        if header not in (expected, CORRECTED_COLUMNS):
            raise ValueError('Unexpected source header; review schema before continuing.')
        for line, row in enumerate(reader, 2):
            if len(row) != len(CORRECTED_COLUMNS):
                raise ValueError(f'Unexpected field count at record {line}: {len(row)}')
    # Preserve literal strings such as "NA" in titles and optional metadata.
    return pd.read_csv(path, header=0, names=CORRECTED_COLUMNS,
                       keep_default_na=False, na_values=[''], low_memory=False)


def clean(df):
    df = df.copy()
    appid = pd.to_numeric(df['AppID'], errors='coerce')
    name = df['Name'].astype('string').str.strip()
    dates = pd.to_datetime(df['Release date'], format='mixed', errors='coerce')
    price = pd.to_numeric(df['Price'], errors='coerce')
    valid_id = (appid.notna() & np.isfinite(appid) & appid.gt(0)
                & appid.le(np.iinfo(np.uint32).max) & appid.mod(1).eq(0))
    rules = [
        ('Invalid AppID', ~valid_id),
        ('Missing/invalid name', name.isna() | name.eq('')),
        ('Invalid release date', dates.isna()),
        ('Invalid price', price.isna() | ~np.isfinite(price)),
        ('Price <= 0', price.le(0)),
    ]
    keep = pd.Series(True, index=df.index)
    audit = []
    for label, failed in rules:
        failed = failed.fillna(True)
        removed = int((keep & failed).sum())
        audit.append((label, int(failed.sum()), removed))
        keep &= ~failed
    df['AppID'] = appid
    df['Name'] = name
    df['release_date'] = dates
    df['release_year'] = dates.dt.year
    df['Price'] = price
    master = df.loc[keep, COLUMNS].copy()
    master['AppID'] = master['AppID'].astype('int64')
    master['release_year'] = master['release_year'].astype('int64')
    numeric = ['Discount', 'DLC count', 'Peak CCU', 'Required age',
               'Metacritic score', 'User score', 'Positive', 'Negative',
               'Achievements', 'Recommendations', 'Average playtime forever',
               'Average playtime two weeks', 'Median playtime forever',
               'Median playtime two weeks']
    for column in numeric:
        # Raise rather than silently replacing unexpected optional numeric values.
        master[column] = pd.to_numeric(master[column], errors='raise')
    return master, audit, int(price.lt(0).sum()), int(price.eq(0).sum())


def validate(df):
    if list(df.columns) != COLUMNS or df.empty:
        raise ValueError('Empty output or unexpected columns')
    ids = pd.to_numeric(df['AppID'], errors='coerce')
    if not (ids.notna().all() and ids.gt(0).all() and ids.mod(1).eq(0).all()
            and ids.le(np.iinfo(np.uint32).max).all() and ids.is_unique):
        raise ValueError('Invalid or duplicate AppID; review before proceeding')
    names = df['Name'].astype('string').str.strip()
    if names.isna().any() or names.eq('').any():
        raise ValueError('Missing/blank name')
    dates = pd.to_datetime(df['release_date'], format='%Y-%m-%d', errors='coerce')
    if dates.isna().any() or not dates.dt.year.eq(df['release_year']).all():
        raise ValueError('Invalid release date/year')
    prices = pd.to_numeric(df['Price'], errors='coerce')
    if not (np.isfinite(prices).all() and prices.gt(0).all()):
        raise ValueError('Invalid/non-positive price')


def table(headers, rows):
    def cell(value):
        return str(value).replace('|', '\\|').replace('\n', ' ').replace('\r', ' ')
    return '\n'.join(['| ' + ' | '.join(headers) + ' |',
                      '| ' + ' | '.join(['---'] * len(headers)) + ' |'] +
                     ['| ' + ' | '.join(cell(v) for v in row) + ' |' for row in rows])


def write_report(df, original, audit, negative, zero, source_hash):
    dates = pd.to_datetime(df['release_date'])
    lines = ['# Games Master Report — Phase 2', '',
             'Validation: **PASS** (in-memory and saved CSV). One row = one Steam game.', '',
             'This is a cleaned catalog for Phase 3 sampling, not a model dataset. Retention does not approve any variable as a historical predictor.', '',
             '## Cleaning audit', '',
             f'Original rows: **{original:,}**. Final rows: **{len(df):,}**. Columns: **{len(df.columns)}**.', '',
             'Failures count each rule on the original data; sequential removals apply rules in the order shown, avoiding double-counting.', '',
             table(['Rule', 'Failing rule', 'Sequentially removed'], audit), '',
             f'Zero source prices: {zero:,}; negative source prices: {negative:,}.', '',
             '## Decisions and provenance', '',
             '- Titles with source `Price <= 0` are excluded from the paid-game candidate population. This does not establish that all excluded titles are permanently free/free-to-play.',
             '- AppIDs must be positive whole numbers within the Steam unsigned 32-bit identifier range; duplicate retained IDs cause validation failure rather than silent deduplication.',
             '- Names are trimmed; release dates use YYYY-MM-DD and release_year is derived. Source order is preserved.',
             '- Optional missing metadata remains missing. Literal text such as NA is preserved; empty CSV fields are missing.',
             '- Estimated owners remains source text; zero-owner and zero-CCU games remain eligible. Multi-value fields are not encoded.',
             '- No historical-event release cutoff is applied. Snapshot date is unknown in existing documentation; no future-release flag is created.',
             '- Discount is a scrape-time snapshot, NOT approved as a historical feature or sale label. No age_at_sale, labels, or sale-year rows are created.',
             '- Shared source_schema.py supplies the same corrected 40-column schema to Phases 1 and 2. Header and record widths are checked before loading.', '',
             f'Source SHA-256 (verified unchanged after processing): `{source_hash}`.', '',
             '## Temporal classification of retained variables', '',
             table(['Category', 'Variables', 'Interpretation'], [
                 ('A. Structural / identifier', 'AppID; Name', 'Identity/provenance, not predictors.'),
                 ('B. Historically derivable', 'release_date; release_year', 'Age can later be calculated relative to sale_start_date; source release-date accuracy remains an assumption.'),
                 ('C. Relatively stable metadata', 'Developers; Publishers; Genres; Required age; Windows; Mac; Linux', 'May change; not guaranteed historically unchanged or approved for modeling.'),
                 ('D. Snapshot / temporally contaminated', 'Price; Discount; DLC count; Estimated owners; Peak CCU; Metacritic score; User score; Positive; Negative; Achievements; Recommendations; all four playtime statistics; Tags; Categories; Supported languages; Full audio languages', 'Unknown observation time; may reflect changes or activity after historical events. Requires later temporal assessment/reconstruction.')]), '',
             '## E. Removed / unusable source columns', '',
             table(['Column', 'Reason'], [(c, 'Free text outside tabular scope' if c in ['About the game', 'Reviews', 'Notes'] else 'Nearly all missing / unclear provenance' if c == 'Score rank' else 'Entirely empty' if c == 'Movies' else 'Media/contact/URL metadata outside tabular scope') for c in DROP]), '',
             '## Plausibility diagnostics', '',
             f'- Release date range: {dates.min():%Y-%m-%d} to {dates.max():%Y-%m-%d}.',
             f'- Price min/median/max: {df.Price.min():g} / {df.Price.median():g} / {df.Price.max():g}.',
             f'- DLC count min/median/max: {df["DLC count"].min():g} / {df["DLC count"].median():g} / {df["DLC count"].max():g}.']
    for c in ['Genres', 'Tags', 'Publishers']:
        lines.append(f'- Missing {c}: {df[c].isna().sum():,} ({df[c].isna().mean():.2%}).')
    lines += [f'- Zero Peak CCU retained: {df["Peak CCU"].eq(0).sum():,}.',
              f'- "0 - 0" Estimated owners retained: {df["Estimated owners"].eq("0 - 0").sum():,}.', '',
              'Release-year distribution:', '',
              table(['Year', 'Games'], sorted(df['release_year'].value_counts().items())), '',
              '## Record alignment sanity checks', '',
              'Deterministic random records (seed 42) plus diagnostic extremes. Unusual values are retained.', '']
    samples = [(f'Random {i+1}', row) for i, (_, row) in enumerate(df.sample(min(4, len(df)), random_state=42).iterrows())]
    samples += [('High price', df.loc[df.Price.idxmax()]), ('High DLC', df.loc[df['DLC count'].idxmax()])]
    for label, mask in [('Zero owners', df['Estimated owners'].eq('0 - 0')), ('Missing Tags', df.Tags.isna())]:
        if mask.any():
            samples.append((label, df.loc[mask].iloc[0]))
    cols = ['AppID', 'Name', 'release_date', 'Price', 'Discount', 'DLC count', 'Estimated owners', 'Peak CCU', 'Genres', 'Tags']
    rows = [[label] + ['(missing)' if pd.isna(row[c]) else row[c] for c in cols] for label, row in samples]
    lines += [table(['Selection'] + cols, rows), '', '## Validation and remaining limitations', '',
              'PASS: nonempty table; exact intended columns; valid, nonnull, unique AppIDs; nonblank names; valid standardized dates and matching years; finite numeric strictly positive prices. Saved CSV was reloaded and compared against the cleaned table.', '',
              'Snapshot reference date and historical validity of retained metadata remain unresolved. Extreme prices/DLC counts, missing optional fields, and sparse engagement are preserved rather than used as exclusion rules.', '',
              'Stopped before Phase 3. No external API requests, sampling dataset, feature encoding, labels, or modeling were performed.']
    REPORT.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(table(['Selection'] + cols, rows))


def main():
    before = digest(SOURCE)
    source = load_source(SOURCE)
    master, audit, negative, zero = clean(source)
    validate(master)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    master.to_csv(OUTPUT, index=False, date_format='%Y-%m-%d')
    saved = pd.read_csv(OUTPUT, keep_default_na=False, na_values=[''], low_memory=False)
    validate(saved)
    expected = master.reset_index(drop=True).copy()
    expected['release_date'] = expected['release_date'].dt.strftime('%Y-%m-%d')
    pd.testing.assert_frame_equal(expected, saved, check_dtype=False)
    if digest(SOURCE) != before:
        raise ValueError('Source file changed during processing')
    write_report(saved, len(source), audit, negative, zero, before)
    print(f'Original: {len(source):,}; final: {len(master):,}; columns: {len(COLUMNS)}')
    for rule, failures, removed in audit:
        print(f'{rule}: {failures:,} failures; {removed:,} sequential removals')
    print(f'Validation: PASS\nOutput: {OUTPUT}\nReport: {REPORT}')


if __name__ == '__main__':
    main()
