# Integrity addendum — 2026-10-15

This dated note clarifies the current committed state audited in Phase 9B.1 and preserved in Phase 9B.2. It does **not** repair data, replace labels, normalize CSVs, overwrite old receipts, or change historical expected hashes. The [public verifier](../scripts/verify_public.py) identifies current tracked bytes separately from historical agreement.

## 1. Historical evidence-file mismatch

Affected file: [data/intermediate/autumn_sale_evidence_records.csv](../data/intermediate/autumn_sale_evidence_records.csv).

The original [219-file inventory](../tests/scalable_artifact_hashes.json) records SHA-256:

`5d59669621686a81fb33c751ba7bebca6d148d2781da9f2db38aa4898cc11754`

The preserved current file has SHA-256:

`69f4930f07a8a5f56c4434611dab81597c626d02411d286a7b542b9889213336`

Existing cohort reports describe this as an ordering-only historical mismatch. This addendum does not newly reconstruct the unavailable original file or claim a new equivalence proof for it. It checks the current bytes against prior receipts. Before finalization, original historical agreement was **218/219** in the full local workspace. The file is unchanged during finalization.

## 2. Phase 8B prediction CSV and subsequent committed drift

Affected file: [predictions_2026.csv](../reports/cohort_2000_2026_predictions/predictions_2026.csv).

| Reference | SHA-256 |
| --- | --- |
| Original [Phase 8B manifest](../reports/cohort_2000_2026_predictions/checksums.json) | `0826d3ebf256ed973a045004146b7a162a04e1e54416f14116cf3b996722b5dd` |
| Current CSV recorded in the preserved [Phase 8C note](../reports/cohort_2000_2026_visualizations/source_integrity_notes.json) | `b896b153e4e7e0054aa2e66b17aad430f53811387c745b4a69bff97736e73746` |
| Current committed CSV at `dbcfd72`, preserved here | `4256315d2caf8bfddab7c95b416ccf3775329174756dcffb40504d047256cddf` |

The Phase 8C note describes reordered rows and two edited names. Commit `dbcfd72` (Final research reports) subsequently changes row order and restores one name. A comparison by AppID with the parent commit found exactly one changed cell: AppID 1518000's `game_name`. Current versus original cohort names are:

| AppID | Earlier Phase 8C CSV name | Current committed name | Original cohort name |
| --- | --- | --- | --- |
| 1518000 | CooKing: Around the C | CooKing: Around the World | CooKing: Around the World |
| 2402900 | Hollow Knight | Hollow Knight | Hoboman |

These edits do not add new games or validate different game identities. Use AppIDs and the original frozen cohort for membership. The remaining name discrepancy is preserved, not corrected.

### What the current in-memory proof establishes

The verifier reads the current CSV and frozen [availability table](../reports/cohort_2000_2026_feasibility/game_availability.csv). It restores **only row order and game names in memory**, serializes with the original CSV field order and line endings, and hashes that temporary string. The result exactly matches the **original Phase 8B manifest hash**.

Exact byte agreement after only those substitutions proves all other fields unchanged: AppIDs, years, cutoffs, probabilities, classes, counts, coverage groups, missingness diagnostics, receipt timestamps, availability flags, and descriptions. It is stronger than merely matching aggregate counts. No file is written and no prediction is recomputed.

The current table still contains the original 2,000 games, 1,026 predicted positives, 974 predicted operational zeros, mean probability 0.4996, median 0.7096, and 336 incomplete vectors all predicted zero. This is numerical continuity, **not exact current-byte agreement with the original CSV manifest**.

### Why historical verification fails

The preserved [Phase 9A checker](../reports/cohort_2000_final_research/verify_report.py) requires the current CSV hash to equal the Phase 8C note's recorded current hash. It fails with `Known Phase 8B discrepancy changed`. The old Phase 8C adapter requires both name discrepancies and fails with `Unexpected preexisting name discrepancy` on the current one-name state.

The Phase 9A phase-start snapshot also records ignored local files, an earlier `.DS_Store`, and the previous root README. Frozen prose describing “current” two-name discrepancies describes its creation-time version; this addendum supersedes that current-state wording without editing the report.

## Authorized presentation changes are separate

Phase 9B.2 changes only the root README and `.gitignore` among existing files. Historical whole-workspace inventories therefore observe intended documentation/ignore differences. The 219-file baseline also pins `.gitignore`; its additional mismatch is authorized presentation work, **not a third scientific discrepancy**. Original snapshots, manifests, verifiers, and test expectations remain unchanged.

Three files in the old 219-file inventory (`games.csv`, `games.json`, and `test.py`) are ignored and unavailable in a typical clone. Other snapshots additionally fingerprint a local credential file. The public verifier neither reads these files nor requires them. It reports the omitted legacy scope explicitly, checks every publicly scoped legacy entry, and accepts the `.gitignore` difference only when it matches the new presentation pin.

The [new public baseline](../scripts/public_artifact_baseline.json) pins the **current start-of-finalization tracked research state**, including both scientific discrepancies. All unrecognized differences fail. Its passing result means current artifact identity and documented checks hold; it does not mean historical manifests were repaired or that the original 219-file workspace can be recreated from a clone.

No independently verified 2026 outcome evaluation exists. None of these integrity checks establish genuine prospective forecasts, provider availability before cutoff, or actual sale participation.
