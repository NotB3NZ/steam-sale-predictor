# Phase 8C completed verification

**Retrospective event-time-filtered predictions using post-cutoff-collected historical data.**

- Eight separate white-background PNGs have 300-DPI metadata and widths of 2,580–3,450 pixels and heights of 1,560–2,100 pixels. All eight were visually reviewed. The scatter legend occupies unused space; coverage labels explicitly name positive and zero counts.
- All 26 core output files (eight PNGs, thirteen CSVs, four Markdown files and the source-integrity JSON) reproduced byte-for-byte after an independent reload of the frozen inputs. `reproduction.json` lists the compared payloads. Final execution/test/integrity receipts are separate from those deterministic figure payloads.
- The delivered Phase 8C offline suite passed 18/18 tests. The existing Phase 7B visualization regressions passed 9/9 tests. There were no failures, errors or skips: 27 unique tests in the completed suites. Model-fitting and new-inference tests were excluded.
- Exactly 2,000 original games, 1,026 predicted positives, 974 predicted operational zeros, the fixed 0.50 threshold, all score quantiles, histogram bins, coverage counts/rates, ranks, and missingness diagnostics reconcile to saved inputs.
- Every one of the 2,388 recorded phase-start project files retained its SHA-256 bytes. All 219 protected artifacts were preserved. Historical-baseline agreement remains 218/219, with the known evidence-record ordering mismatch unchanged and unrepaired.
- The HTTP-attempt journal retains 3,816 attempts (maximum sequence 3,816; 7,647 total lines including results/control records). No journal entries were added or edited; no HTTP requests were made.
- A separate preexisting Phase 8B CSV discrepancy is proven to consist solely of row reordering and two name edits. Restoring only original order/names in memory exactly reproduces its original manifest hash, proving scores, classes, cohort membership and all other fields unchanged. The source CSV and stale manifest entry remain untouched. Details are in `source_integrity_notes.json`; neither affected row appears in the top/bottom ten.
- No models were loaded, trained, queried, tuned or modified. No new predictions, threshold changes, cohort expansion, historical-data changes or outcome evaluation occurred. Original Phase 6/7/8 reports and datasets were preserved.

Use figures 01, 02, 05, 06 and 08 as the core presentation; retain figure 07 and the top/bottom ranks as supplements. The artifacts are ready for descriptive final research synthesis with the coverage, missingness, source-provenance and retrospective limitations visible.

The cutoff is 2026-10-01T17:00:00Z. Provider availability before cutoff cannot be established. Predicted operational zeros and missing predictors do not prove nonparticipation. No independent 2026 outcome evaluation has been conducted. These prediction rates are not actual sale participation rates; coverage/score associations are not causal findings.
