# Phase 6A: 2,000-game pipeline compatibility and labelability

The offline audit covers **2,000 games and 6,000 unique game-year pairs**.
Every game appears exactly once in 2023, 2024, and 2025. No collection, feature
engineering, model training, or prediction figures were performed.

## Compatibility and implementation

| Component | Finding |
| --- | --- |
| `04_audit_autumn_evidence.py`: calendar, UTC parser, observation/category rules, `audit_pair` | Directly reusable. Categories and precise discount detector are executable. |
| `05_investigate_sale_coverage.py`: `summarize_pair`, timestamp/state conflicts | Directly reusable; excludes observations at/after 2026 and does not interpolate prices. |
| `06_build_operational_labels.py`: `construct_labels`, `mapping` | Directly reusable with explicit cohort pair keys and cache paths, already supported. Reconciles raw indices, JSON, categories, counts, boundaries, and collection scope. |
| `incremental_itad.resolve_cache` | Directly reusable across the primary cache and read-only pilot namespace. Validates successful empty responses separately from missing/failed histories. |
| `cohort_pipeline.evidence` | Reusable with a small optional `include_features=False` argument. The default remains unchanged. |
| Existing cohort audit CLI | Not audit-only: all stages calculate/write features; repository output paths are restricted to `data/cohorts`. A dedicated adapter writes this new reports directory without changing path protections or historical writers. |
| Historical standalone pilot routines/receipt chains | Not plug-and-play: fixed paths, 100-game/300-pair checks, and protected historical fingerprints. The known mismatch fails historical hash validation. These routines were not executed. |
| Feature and fitting cores | Reusable for a later authorized phase through the configurable cohort adapter; pilot entry-point assumptions cannot simply be applied to 2,000 games. |

Minimal source changes: the optional evidence-only switch in
`src/cohort_pipeline.py`, the new `src/audit_cohort_labelability.py` adapter,
and two regressions in `tests/test_scalable_pipeline.py`. No category,
discount detector, eligibility rule, sale calendar, feature definition, model
parameter, or cohort membership was changed.

The adapter reuses the established expanded `model_eligible` mask:
**A/B and not `requires_review`**. `labelability.csv` leaves all other target
cells blank. It is an audit/eligibility view, not a final training dataset.
Legacy operational mapping is disclosed separately in the summary:
A -> 1, B/D -> 0, C -> null. In the pilot, D zero means "discount not recorded";
it is not sufficient evidence for an expanded modeling negative. All 243
game-year rows belonging to the 81 successful empty histories remain unknown
in the usable-label view. Missing/failed histories would also remain unknown.

## Unchanged methodology

| Year | UTC start, inclusive | UTC end, exclusive |
| --- | --- | --- |
| 2023 | 2023-11-21 18:00 | 2023-11-28 18:00 |
| 2024 | 2024-11-27 18:00 | 2024-12-04 18:00 |
| 2025 | 2025-09-29 17:00 | 2025-10-06 17:00 |

The central `src/autumn_sale_calendar.json`, project context, existing evidence
report, operational-labeling report, Pacific timezone conversions, and saved
source-image hashes agree. No new external calendar research was needed.

The unchanged categories are:

- **A:** at least one directly observed in-window discount, even when other
  in-window records show full price or ambiguity.
- **B:** in-window records exist and every record shows full price.
- **C:** in-window records exist, no discount, and some ambiguous/null information.
- **D:** no directly timestamped in-window records.

The existing detector requires finite consistent money/currency fields, explicit
cut > 0, and price < regular for a discount. Full price requires cut = 0 and
price = regular. Context before/after the event does not establish an in-sale
state. Release eligibility remains date <= sale-start date; same-day release
hours are uncertain and flagged. Empty histories do not prove no discounts.

## Coverage

All denominators are 2,000 observations per year. "Usable zero" means a
full-price-only **observed** operational zero, never verified nonparticipation
or continuous full price throughout the sale.

| Year | A | B | C | D | Usable 1 | Usable 0 | Unknown/excluded | Usable % |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2023 | 979 | 10 | 0 | 1,011 | 979 | 9 | 1,012 | 49.40 |
| 2024 | 1,068 | 5 | 0 | 927 | 1,068 | 5 | 927 | 53.65 |
| 2025 | 983 | 8 | 0 | 1,009 | 983 | 8 | 1,009 | 49.55 |
| Total | 3,030 | 23 | 0 | 2,947 | 3,030 | 22 | 2,948 | 50.87 |

All 6,000 pairs are release-date eligible. One B pair, nekowater
(AppID 2650840) in 2023, retains uncertain release-hour review and is excluded
from the usable view. Legacy operational zeros total 2,970; the usable view
does not treat those D zeros as reliable negative evidence. Verified full-sale
negative/official-participation labels: **zero**.

- Complete caches: **2,000**, including 1,919 nonempty and **81 successful empty** histories.
- Games with usable pre-2026 historical price evidence: **1,918**.
- Games with at least one usable game-year label: **1,268**.
- AppID 2270900 has five records, all from 2026; its nonempty successful cache
  supplies no usable evidence for these historical targets.

## Data quality and validation

There are **93,286 raw history records**, with 14,023 at/after 2026 excluded
from historical analysis without changing the caches. Parsing failures,
non-Steam records excluded, ambiguous parsed deals, and identical duplicate
raw records are all **zero**. No missing/invalid caches or duplicate/missing
game-year pairs were found. In-window raw JSON and indices were independently
reconciled back to the authoritative cache arrays. Repeated evidence-only
evaluation reproduces all six saved CSV tables exactly.

There are **51 price-state conflict groups at the same UTC timestamp/shop across
24 games**, listed in `timestamp_shop_conflicts.csv`. The original eleven
groups across nine games remain unchanged; these include pilot and early
expansion games. Raw ties are retained, not deduplicated or repaired.

One group falls inside a target sale: AppID **1817400**, 2023-11-21T21:23:32Z,
raw indices 136/137. Both records are discounts, at USD 0.90/1.98 (55%) and
USD 0.49/0.99 (51%). Price amounts disagree, but both support the same A/binary
recorded-discount classification. This does not require changing the A rule.

The guarded suite ran **189 tests: 188 passed, one failed, zero errors/skips**.
The sole failure is the pre-existing protected-file SHA-256 regression for the
known mismatch described below. Both new audit regressions passed: evidence-only
mode preserves evidence/labels without feature calls; empty/missing histories
remain blank in the labelability view. Network, repository writes, and fitting
are blocked by the existing safe runner. Historical full-regeneration tests
are excluded. The expected hash failure was not suppressed or repaired.

## Preservation versus historical baseline agreement

All **219 protected artifacts** and all **2,000 raw caches** were preserved
during this phase. All 100 original pilot caches, frozen cohorts, archived
checkpoints, and HTTP journal bytes remain unchanged. The journal still has
**3,816 attempts**. The independent validation compared **2,203 pre-existing
data/report/model and protected files** with the phase-start snapshot and found
no changes. Historical baseline matching remains **218/219**.

Read-only `git show HEAD:data/intermediate/autumn_sale_evidence_records.csv`
has SHA-256 `5d59669621686a81fb33c751ba7bebca6d148d2781da9f2db38aa4898cc11754`,
exactly matching the existing protected baseline. The current file has SHA-256
`69f4930f07a8a5f56c4434611dab81597c626d02411d286a7b542b9889213336`.
Both contain **178 rows and 68,596 bytes**. The complete row multisets are
identical: zero additions, removals, or changed row contents. The row for
AppID 2205710/year 2025/raw index 21 moved from position 152 to 176, and
AppID 2268470/year 2023/raw index 0 moved from 155 to 177, shifting intervening
rows. This is an ordering-only byte mismatch; who/what reordered it remains
unverified. It was not repaired, normalized, or overwritten. The cohort audit
reads authoritative raw caches rather than this mismatched pilot derivative.

## Readiness and next phase

The executable evidence/labeling cores scale to 2,000 games. The previous CLI
was not a strictly plug-and-play labelability-only command; the small adapter
resolves scope/output compatibility without redesigning the methodology.

There is enough usable evidence for a **separate, offline pre-sale feature
availability/leakage audit**. Reuse `07_build_autumn_features.py:build_features`
through configurable cohort processing, maintaining its 15-feature allowlist,
strict timestamp < sale-start cutoff, missing-value handling, and conflict
diagnostics. Keep labels/coverage flags and in-sale/post-sale observations out
of predictors. Do not run a fixed-path pilot writer.

Reliable binary evaluation is not ready. Under the existing game-disjoint
development/evaluation split, usable development labels for 2023–2024 are
**1,692 ones / 10 zeros** (1,702 rows, 993 games); held-out 2025 is
**176 ones / one zero** (177 games). This is insufficient negative-class
coverage for credible broad classifier/evaluation claims. Unknown D observations
must not be converted to negatives to improve balance. Source capture is not
known to be complete, so true sale participation remains unverified.

Future training can reuse `08_train_baseline_models.py` and
`09_train_ensemble_models.py` fitting functions through `cohort_pipeline`'s
game-disjoint adapter, with fixed parameters and training-only preprocessing.
The legacy pilot split/report functions expect 100 games and are incompatible
with direct enlarged-cohort execution. No training was attempted. The
class-coverage limitation and intended observation-based target require review
before modeling; historical receipt-based reproduction also retains its known
ordering mismatch blocker.

Reproduction into a **new** report directory:

```sh
env -u ITAD_API_KEY /usr/bin/python3 -B src/audit_cohort_labelability.py \
  --cohort data/cohorts/cohort_2000.csv \
  --cache-dir data/cohorts/itad/cache \
  --reuse-cache data/raw/itad \
  --output-dir reports/cohort_2000_labelability_rerun
```

Artifacts: `labelability_summary.json`, `validation.json`, `evidence_audit.csv`,
`evidence_records.csv`, `coverage_diagnostics.csv`, `labelability.csv`,
`game_cache_audit.csv`, and `timestamp_shop_conflicts.csv`. Stop after this audit;
feature generation and modeling require a later authorized phase.
