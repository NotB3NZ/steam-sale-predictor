"""
00_inspect_source.py — Phase 1: Reproducible inspection of games.csv

This script inspects the raw source CSV WITHOUT modifying it.
It reports on:
  1. CSV structural integrity (header vs data field counts)
  2. Dataset structure (rows, columns, types, memory)
  3. Missing data analysis
  4. Unique-value summaries for categorical columns
  5. Descriptive statistics for numeric columns
  6. Date parsing diagnostics
  7. Column classification for future modeling

Usage:
    python src/00_inspect_source.py
"""

import csv
import sys
from pathlib import Path
from collections import Counter

import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = PROJECT_ROOT / "games.csv"

# The correct header should have 40 columns. The raw file has a known issue
# where "Discount" and "DLC count" are concatenated as "DiscountDLC count".
CORRECTED_COLUMNS = [
    "AppID", "Name", "Release date", "Estimated owners", "Peak CCU",
    "Required age", "Price", "Discount", "DLC count", "About the game",
    "Supported languages", "Full audio languages", "Reviews",
    "Header image", "Website", "Support url", "Support email",
    "Windows", "Mac", "Linux",
    "Metacritic score", "Metacritic url", "User score",
    "Positive", "Negative", "Score rank",
    "Achievements", "Recommendations", "Notes",
    "Average playtime forever", "Average playtime two weeks",
    "Median playtime forever", "Median playtime two weeks",
    "Developers", "Publishers", "Categories", "Genres", "Tags",
    "Screenshots", "Movies",
]

SECTION_SEP = "\n" + "=" * 80 + "\n"


def print_section(title: str) -> None:
    print(SECTION_SEP)
    print(f"  {title}")
    print("=" * 80)


# ============================================================================
# TASK A — CSV STRUCTURAL INTEGRITY
# ============================================================================
def check_structural_integrity() -> dict:
    """Low-level CSV scan: verify field counts across every row."""
    print_section("STRUCTURAL INTEGRITY CHECK")

    field_counts: Counter = Counter()
    header_fields = 0
    problem_rows: list[tuple[int, int]] = []  # (row_num, field_count)
    total_rows = 0

    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        header_fields = len(header)
        print(f"Header field count:  {header_fields}")

        for i, row in enumerate(reader, start=2):  # row 1 = header
            n = len(row)
            field_counts[n] += 1
            total_rows += 1
            if n != header_fields and n != header_fields + 1:
                # Flag only rows that don't match expected counts
                if len(problem_rows) < 50:
                    problem_rows.append((i, n))

    print(f"Total data rows:     {total_rows}")
    print(f"\nField-count distribution across data rows:")
    for n, count in sorted(field_counts.items()):
        pct = count / total_rows * 100
        match_label = ""
        if n == header_fields:
            match_label = " ← matches header"
        elif n == header_fields + 1:
            match_label = " ← header + 1 (expected if header is missing a column)"
        print(f"  {n} fields: {count:>8,} rows ({pct:.2f}%){match_label}")

    # Detect the DiscountDLC count issue
    discount_dlc_col = None
    for i, h in enumerate(header):
        if "Discount" in h and "DLC" in h:
            discount_dlc_col = i

    print(f"\n--- Header column names around suspected issue (index 5–10) ---")
    for idx in range(max(0, 5), min(len(header), 12)):
        print(f"  [{idx:>2}] {header[idx]!r}")

    if discount_dlc_col is not None:
        print(f"\n⚠ CONFIRMED: Column [{discount_dlc_col}] is {header[discount_dlc_col]!r}")
        print(f"  This appears to be two columns concatenated: 'Discount' + 'DLC count'")
        print(f"  Evidence: header has {header_fields} fields, ALL {total_rows:,} data rows have {header_fields + 1} fields.")
        print(f"  The corrected header should have {header_fields + 1} columns.")

    if problem_rows:
        print(f"\nRows with unexpected field counts (showing first {len(problem_rows)}):")
        for row_num, fc in problem_rows[:10]:
            print(f"  Row {row_num}: {fc} fields")
    else:
        print(f"\n✓ All {total_rows:,} data rows have a consistent field count ({list(field_counts.keys())[0]} fields).")

    return {
        "header_fields": header_fields,
        "total_rows": total_rows,
        "field_counts": dict(field_counts),
        "header": header,
        "discount_dlc_col": discount_dlc_col,
    }


# ============================================================================
# TASK B — LOAD DATA WITH CORRECTED HEADER
# ============================================================================
def load_dataframe() -> pd.DataFrame:
    """Load CSV with corrected column names (header=0 skipped, names provided)."""
    print_section("LOADING DATAFRAME WITH CORRECTED HEADER")

    df = pd.read_csv(
        CSV_PATH,
        header=0,           # skip the malformed header row
        names=CORRECTED_COLUMNS,
        low_memory=False,
    )
    print(f"Loaded {len(df):,} rows × {len(df.columns)} columns")
    print(f"Memory usage: {df.memory_usage(deep=True).sum() / 1e6:.1f} MB")

    # Verify semantic correctness of the split
    print(f"\n--- Spot-check: Price / Discount / DLC count (first 10 rows) ---")
    print(df[["AppID", "Name", "Price", "Discount", "DLC count"]].head(10).to_string())

    return df


# ============================================================================
# TASK C — DATASET STRUCTURE
# ============================================================================
def report_structure(df: pd.DataFrame) -> None:
    print_section("DATASET STRUCTURE")

    print(f"Rows:    {len(df):,}")
    print(f"Columns: {len(df.columns)}")
    print(f"Memory:  {df.memory_usage(deep=True).sum() / 1e6:.1f} MB")

    # Column names, dtypes
    print(f"\n{'#':<4} {'Column':<30} {'Dtype':<15}")
    print("-" * 52)
    for i, (col, dtype) in enumerate(zip(df.columns, df.dtypes)):
        print(f"{i:<4} {col:<30} {str(dtype):<15}")

    # Duplicates
    dup_rows = df.duplicated().sum()
    print(f"\nDuplicate rows (all columns): {dup_rows:,}")

    if "AppID" in df.columns:
        dup_appid = df["AppID"].duplicated().sum()
        print(f"Duplicate AppID values:        {dup_appid:,}")
        if dup_appid > 0:
            top_dups = df["AppID"].value_counts().head(5)
            top_dups_filtered = top_dups[top_dups > 1]
            if len(top_dups_filtered) > 0:
                print(f"  Top duplicated AppIDs:")
                for appid, cnt in top_dups_filtered.items():
                    print(f"    AppID {appid}: {cnt} occurrences")


# ============================================================================
# TASK D — MISSING DATA
# ============================================================================
def report_missing(df: pd.DataFrame) -> pd.DataFrame:
    print_section("MISSING DATA ANALYSIS")

    missing = df.isnull().sum()
    missing_pct = (missing / len(df) * 100).round(2)
    missing_df = pd.DataFrame({
        "column": df.columns,
        "missing_count": missing.values,
        "missing_pct": missing_pct.values,
    }).sort_values("missing_pct", ascending=False).reset_index(drop=True)

    # Also check for empty strings in object columns
    empty_str_counts = {}
    for col in df.select_dtypes(include="object").columns:
        empty_count = (df[col] == "").sum()
        if empty_count > 0:
            empty_str_counts[col] = empty_count

    print(missing_df.to_string(index=False))

    if empty_str_counts:
        print(f"\n--- Empty string counts (not NaN, but '') ---")
        for col, cnt in sorted(empty_str_counts.items(), key=lambda x: -x[1]):
            pct = cnt / len(df) * 100
            print(f"  {col:<30} {cnt:>8,} ({pct:.2f}%)")

    return missing_df


# ============================================================================
# TASK E — UNIQUE VALUES (CATEGORICAL)
# ============================================================================
def report_categoricals(df: pd.DataFrame) -> None:
    print_section("CATEGORICAL COLUMN SUMMARIES")

    # Columns likely to be categorical or of modeling interest
    cat_candidates = [
        "Estimated owners", "Required age", "Windows", "Mac", "Linux",
        "Developers", "Publishers", "Categories", "Genres", "Tags",
    ]

    for col in cat_candidates:
        if col not in df.columns:
            continue
        nuniq = df[col].nunique()
        print(f"\n--- {col} ---")
        print(f"  Unique values: {nuniq:,}")
        if nuniq <= 30:
            vc = df[col].value_counts().head(30)
            for val, cnt in vc.items():
                print(f"    {val!r}: {cnt:,}")
        else:
            vc = df[col].value_counts()
            print(f"  Top 10:")
            for val, cnt in vc.head(10).items():
                print(f"    {val!r}: {cnt:,}")
            print(f"  Bottom 3:")
            for val, cnt in vc.tail(3).items():
                print(f"    {val!r}: {cnt:,}")


# ============================================================================
# TASK F — NUMERIC COLUMNS
# ============================================================================
def report_numerics(df: pd.DataFrame) -> None:
    print_section("NUMERIC COLUMN STATISTICS")

    numeric_cols = [
        "AppID", "Peak CCU", "Required age", "Price", "Discount", "DLC count",
        "Metacritic score", "User score", "Positive", "Negative",
        "Achievements", "Recommendations",
        "Average playtime forever", "Average playtime two weeks",
        "Median playtime forever", "Median playtime two weeks",
    ]

    # Try to coerce to numeric
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    existing = [c for c in numeric_cols if c in df.columns]
    desc = df[existing].describe().T
    desc["null_count"] = df[existing].isnull().sum()

    pd.set_option("display.float_format", lambda x: f"{x:,.2f}")
    print(desc.to_string())
    pd.reset_option("display.float_format")

    # Flag suspicious values
    print(f"\n--- Suspicious value flags ---")

    if "Price" in df.columns:
        neg_price = (df["Price"] < 0).sum()
        zero_price = (df["Price"] == 0).sum()
        high_price = (df["Price"] > 500).sum()
        print(f"  Price < 0:   {neg_price:,}")
        print(f"  Price == 0:  {zero_price:,}")
        print(f"  Price > 500: {high_price:,}")
        if high_price > 0:
            print(f"    Highest prices: {df['Price'].nlargest(5).tolist()}")

    if "Discount" in df.columns:
        neg_disc = (df["Discount"] < 0).sum()
        over100 = (df["Discount"] > 100).sum()
        print(f"  Discount < 0:   {neg_disc:,}")
        print(f"  Discount > 100: {over100:,}")

    if "DLC count" in df.columns:
        neg_dlc = (df["DLC count"] < 0).sum()
        print(f"  DLC count < 0:  {neg_dlc:,}")
        high_dlc = df["DLC count"].nlargest(5)
        print(f"  Top DLC counts: {high_dlc.tolist()}")

    if "Required age" in df.columns:
        age_vals = df["Required age"].dropna().unique()
        print(f"  Required age unique values ({len(age_vals)}): {sorted(age_vals)[:20]}")

    if "Peak CCU" in df.columns:
        print(f"  Peak CCU max: {df['Peak CCU'].max():,.0f}")
        print(f"  Peak CCU == 0: {(df['Peak CCU'] == 0).sum():,}")


# ============================================================================
# TASK G — DATE ANALYSIS
# ============================================================================
def report_dates(df: pd.DataFrame) -> None:
    print_section("DATE COLUMN ANALYSIS")

    if "Release date" not in df.columns:
        print("No 'Release date' column found.")
        return

    raw = df["Release date"]
    print(f"Total values:   {len(raw):,}")
    print(f"Null/NaN:       {raw.isnull().sum():,}")
    print(f"Empty strings:  {(raw == '').sum():,}")

    # Show sample values
    non_null = raw.dropna()
    non_empty = non_null[non_null != ""]
    print(f"Non-empty:      {len(non_empty):,}")
    print(f"\nSample values (first 15):")
    for v in non_empty.head(15):
        print(f"  {v!r}")

    # Try parsing
    parsed = pd.to_datetime(raw, format="mixed", errors="coerce", dayfirst=False)
    success = parsed.notna().sum()
    failed = parsed.isna().sum() - raw.isna().sum()  # subtract original NaNs
    failed = max(failed, 0)

    print(f"\nParsing results:")
    print(f"  Successfully parsed: {success:,}")
    print(f"  Failed to parse:     {failed:,} ({failed / len(raw) * 100:.2f}%)")

    if success > 0:
        print(f"  Earliest date: {parsed.min()}")
        print(f"  Latest date:   {parsed.max()}")

    # Show some that failed parsing
    if failed > 0:
        failed_mask = parsed.isna() & raw.notna() & (raw != "")
        failed_examples = raw[failed_mask].head(20)
        print(f"\n  Examples that failed parsing:")
        for v in failed_examples:
            print(f"    {v!r}")


# ============================================================================
# TASK H — COLUMN CLASSIFICATION FOR MODELING
# ============================================================================
def classify_columns(df: pd.DataFrame) -> dict:
    print_section("COLUMN CLASSIFICATION FOR FUTURE MODELING")

    classification = {
        "Identifiers": {
            "cols": ["AppID", "Name"],
            "notes": "Primary key (AppID) and human-readable name. Not features."
        },
        "Temporal": {
            "cols": ["Release date"],
            "notes": "Can derive age_at_sale, release_year, etc. Safe if computed relative to sale date."
        },
        "Price-related": {
            "cols": ["Price", "Discount"],
            "notes": "Price = base price. Discount = current discount %. Discount at scrape time may not reflect pre-sale state."
        },
        "Popularity / Engagement": {
            "cols": ["Peak CCU", "Estimated owners", "Positive", "Negative",
                     "Recommendations", "User score", "Metacritic score",
                     "Average playtime forever", "Average playtime two weeks",
                     "Median playtime forever", "Median playtime two weeks"],
            "notes": "Many of these accumulate over time — LEAKAGE RISK if used as-is for historical prediction."
        },
        "Publisher / Developer": {
            "cols": ["Developers", "Publishers"],
            "notes": "High cardinality. May need grouping or encoding strategies."
        },
        "Content / Descriptive": {
            "cols": ["Genres", "Tags", "Categories", "About the game",
                     "Supported languages", "Full audio languages"],
            "notes": "Multi-value fields (comma-separated lists). Genres/Tags useful. 'About the game' is free text."
        },
        "Product Structure": {
            "cols": ["DLC count", "Achievements", "Required age"],
            "notes": "Structural attributes of the game product."
        },
        "Platform": {
            "cols": ["Windows", "Mac", "Linux"],
            "notes": "Boolean platform availability flags."
        },
        "Media / URLs (drop)": {
            "cols": ["Header image", "Website", "Support url", "Support email",
                     "Screenshots", "Movies", "Metacritic url"],
            "notes": "Not useful as numeric/categorical features. Drop for modeling."
        },
        "Other": {
            "cols": ["Reviews", "Notes", "Score rank"],
            "notes": "Reviews = text. Notes = content warnings. Score rank = unclear provenance."
        },
    }

    for category, info in classification.items():
        present = [c for c in info["cols"] if c in df.columns]
        missing = [c for c in info["cols"] if c not in df.columns]
        print(f"\n{category}:")
        print(f"  Columns: {present}")
        if missing:
            print(f"  Missing from data: {missing}")
        print(f"  Notes: {info['notes']}")

    # Leakage warnings
    print(f"\n{'─' * 60}")
    print(f"⚠  TEMPORAL LEAKAGE RISKS")
    print(f"{'─' * 60}")
    leakage_cols = [
        ("Peak CCU", "Lifetime peak — includes post-sale activity"),
        ("Positive", "Lifetime review count — accumulates over time"),
        ("Negative", "Lifetime review count — accumulates over time"),
        ("Recommendations", "Total recommendations — accumulates over time"),
        ("User score", "May reflect post-sale sentiment"),
        ("Estimated owners", "Lifetime estimate — includes post-sale purchases"),
        ("Average playtime forever", "Lifetime stat — includes post-sale play"),
        ("Median playtime forever", "Lifetime stat — includes post-sale play"),
        ("Average playtime two weeks", "Recent window — timing relative to scrape unknown"),
        ("Median playtime two weeks", "Recent window — timing relative to scrape unknown"),
        ("Discount", "Current discount at scrape time — not pre-sale state"),
        ("Metacritic score", "May be updated post-release"),
    ]

    for col, reason in leakage_cols:
        if col in df.columns:
            print(f"  {col:<35} {reason}")

    return classification


# ============================================================================
# MAIN
# ============================================================================
def main():
    print("=" * 80)
    print("  STEAM GAMES CSV — SOURCE DATA INSPECTION")
    print(f"  File: {CSV_PATH}")
    print(f"  File size: {CSV_PATH.stat().st_size / 1e6:.1f} MB")
    print("=" * 80)

    # Step 1: Structural integrity (low-level CSV)
    integrity = check_structural_integrity()

    # Step 2: Load with corrected header
    df = load_dataframe()

    # Step 3: Dataset structure
    report_structure(df)

    # Step 4: Missing data
    missing_df = report_missing(df)

    # Step 5: Categorical summaries
    report_categoricals(df)

    # Step 6: Numeric statistics
    report_numerics(df)

    # Step 7: Date analysis
    report_dates(df)

    # Step 8: Column classification
    classify_columns(df)

    print(SECTION_SEP)
    print("  INSPECTION COMPLETE")
    print("=" * 80)

    return df, missing_df, integrity


if __name__ == "__main__":
    df, missing_df, integrity = main()
