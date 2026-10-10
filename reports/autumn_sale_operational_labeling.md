# Phase 5B.3 — Operational Label Construction

**Status:** operational labels constructed; human review required before Phase 6. No predictive features, models, accuracy estimates or PU algorithms were created.

## Research objective and decision

> Can historical Steam game metadata and pre-sale pricing behavior predict whether a Steam-store discount will be RECORDED during the Steam Autumn Sale?

The broader motivation remains actual Autumn Sale discount participation. Phase 5B.2 did not establish independently verified full-sale negatives using the accessible sources. The authorized operational target measures recorded discount occurrence so that a reproducible pipeline can proceed without asserting complete historical capture. No additional historical-source research was conducted.

## Formal target and evidence mapping

`discount_observed = 1` when at least one qualifying Steam-store discounted-price observation is timestamped inside the verified sale interval. `discount_observed = 0` when no qualifying discounted observation exists. Category C is withheld as a blank/null label with `ambiguity_flag=True` and `requires_review=True`. This ambiguity exception deliberately avoids silently converting unusable in-window evidence into zero.

The implementation reuses `observation()` and `category()` from the unchanged Phase 5A.1 script. Qualifying discount observations require valid consistent money/currency information, explicit cut > 0 and price < regular. No new discount detector or price persistence assumption is introduced.

| Evidence category | discount_observed | pu_status | Meaning |
| --- | --- | --- | --- |
| A | 1 | positive | At least one recorded in-window discount |
| B | 0 | unlabeled | Full-price-only in-window records; discount not observed |
| C | null | unlabeled | Ambiguous/null in-window evidence without a discount; review required |
| D | 0 | unlabeled | No directly timestamped in-window records; discount not observed |

Rule version: **operational_observed_v1**. Collection scope: **Steam shop 61, US**. `label_limitation_flag=True` for every row because complete historical event capture is unproven.

### Methodological disclosure

> Games with at least one qualifying Steam-store discount observation during the official Autumn Sale window were assigned a positive operational label. Games without such an observation were assigned a negative operational label, except that Category C remains null for review. Because historical price coverage is incomplete, negative operational labels do not establish that a game was never discounted. The resulting target measures recorded discount occurrence rather than independently verified sale participation.

**Operational negatives must not be interpreted as verified non-discounts, non-participation or uninterrupted full price. These labels are not ground truth for actual sale participation or formal Valve event enrollment.**

## Exact event windows

Intervals are half-open: **start <= timestamp < end**. Exact start is included; exact end is excluded. The unchanged centralized calendar and existing Valve verification supply both boundaries:

| Year | Start UTC (inclusive) | End UTC (exclusive) | Pacific | Existing verification |
| --- | --- | --- | --- | --- |
| 2023 | 2023-11-21T18:00:00Z | 2023-11-28T18:00:00Z | 10 AM PST | [Valve](https://steamcommunity.com/games/593110/announcements/detail/3823053915973575702) |
| 2024 | 2024-11-27T18:00:00Z | 2024-12-04T18:00:00Z | 10 AM PST | [Valve](https://steamcommunity.com/games/593110/announcements/detail/4464851103138185583) |
| 2025 | 2025-09-29T17:00:00Z | 2025-10-06T17:00:00Z | 10 AM PDT | [Valve](https://steamcommunity.com/games/593110/announcements/detail/507340830949770005) |

No approximate calendar-day boundaries or 2026 sale rows are used.

## Label distributions

| Year | Rows | 1: discount recorded | 0: discount not observed | Null | A / B / C / D |
| --- | --- | --- | --- | --- | --- |
| 2023 | 100 | 55 | 45 | 0 | 55 / 2 / 0 / 43 |
| 2024 | 100 | 60 | 40 | 0 | 60 / 0 / 0 / 40 |
| 2025 | 100 | 60 | 40 | 0 | 60 / 1 / 0 / 39 |
| All | 300 | 175 | 125 | 0 | 175 / 3 / 0 / 122 |

PU status totals: **175 positive / 125 unlabeled**. All 300 original game-year pairs remain, with unchanged categories. There are zero current C cases and zero null labels. Label counts are checked against the approved frozen pilot; an unexpected scope/count change stops execution for review rather than forcing results.

## Dataset provenance and eligibility

The label builder reads the existing audit, long evidence records, coverage diagnostics, pilot and collection manifest. Raw JSON embedded in each in-window record is reparsed with the shared parser, checked against the saved fields, and reconciled with the coverage JSON and counts. The preceding receipt chain protects the cached original histories and all earlier source/evidence/verification artifacts with SHA-256. No evidence input or previous receipt is regenerated.

`supporting_record_indices` contains only raw-array indices of qualifying in-window discounts; B/C/D have an empty array. `in_window_record_indices` retains all actual in-window indices. Shop and region come from the manifest, including for empty histories; they describe the collection request, not an invented observed price. `source_currencies` is blank if none is observed. Currency, counts and conflict indicators remain target provenance.

Eligibility uncertainty: **1 pair**. nekowater (AppID 2650840), 2023, retains its B category and operational zero, with `eligibility_status=uncertain_release_hour` and `requires_review=True`. The source release date matches the sale start date; the release hour remains unknown. The remaining 299 pairs are `eligible_by_release_date`, which certifies the existing date rule, not continuous purchase availability. No row was excluded.

Three empty-history games contribute nine D operational zeros. Their missing histories are visible via `empty_raw_history`; no price state or actual absence of discount is inferred. Known historical timestamp conflicts are not repaired. In-window conflicts, if present, remain explicit diagnostics; the current in-window conflict count is zero.

## Limitations and evaluation implications

- **False negatives relative to actual discounts:** a discount may have occurred without being recorded. A zero is correct for this observation-based target but can be incorrect if interpreted as actual non-discounting. No true false-negative rate was estimated.
- **Coverage:** change-oriented records, missing histories, irregular gaps and unproven complete capture remain. Before/after records do not fill the sale interval. No coverage threshold, interpolation or persistence is used.
- **Sampling:** the 100-game pilot was designed for diagnostic diversity, not representativeness. Its operational class balance and future performance cannot establish population rates or accuracy.
- **Evaluation:** future training uses 2023–2024 (115 operational ones / 85 zeros); 2025 is temporal validation (60 / 40). Evaluate agreement with recorded discounts, not ground-truth participation. Coverage differences across games/years can confound apparent performance. Repeated AppIDs across years and uncertain eligibility require transparent handling.
- **Probability interpretation:** any future probability concerns a discount being recorded under these data-source/scope conditions. It is not an independently calibrated probability of actual discount participation. Coverage and publisher/game characteristics may affect recording availability; associations are not causal effects.

## PU view and future feature safeguards

The separate PU CSV projects only identifiers, original evidence category, PU status and rule version. All non-A pairs are unlabeled; none is a verified negative. It supports an optional later sensitivity experiment. No PU algorithm, class-prior estimate or assumption that positives are selected completely at random is implemented.

The operational CSV is a **target/provenance table, not a predictor table**. Constructing retrospective targets from in-sale records is valid; feeding those observations into predictors would leak the target. Do not use evidence categories, PU status, supporting indices, in-window counts, ambiguity/coverage flags, future history emptiness/conflicts or collection metadata as predictors. They can reflect the sale or later collection, even where no post-sale prices are copied.

After human review, Phase 6 must construct predictors separately from information available strictly before each sale start. Current snapshot Price, Discount, reviews, playtime and Peak CCU are not automatically historically valid. Any pre-sale pricing behavior must use timestamp-filtered pre-event observations; no sale/post-sale observation or 2026 outcome may influence historical predictors. No feature selection, exclusion policy for uncertain eligibility, modeling or tuning was performed here.

## Reproducibility and validation

```bash
python3 -B src/06_build_operational_labels.py --verify
```

Standard-library-only execution reads local files under a socket/DNS prohibition. Outputs are sorted by numeric AppID then sale year. Null labels are blank CSV cells; booleans use the established `True`/`False` CSV convention. A normal run only reuses execution checks for matching source/protected fingerprints; `--verify` runs the whole offline suite and proves repeated byte-identical CSVs, report and receipt.

| Check | Result |
| --- | --- |
| Full offline tests | PASS; 102 tests |
| Repeated full execution | PASS: all four outputs byte-identical in two full executions |
| Protected preceding files / frozen Phase 4 inputs | 153 / 107; unchanged before/after |
| Unique pairs / duplicates / null labels | 300 / 0 / 0 |
| API/network attempts / new histories | 0 / 0 |
| Predictive features / trained models / 2026 target rows | None |

Artifacts: [operational labels](../data/intermediate/autumn_sale_operational_labels.csv), [PU view](../data/intermediate/autumn_sale_pu_labels.csv), [validation receipt](autumn_sale_operational_label_validation.json). Earlier context: [exact audit](autumn_sale_evidence_audit.md), [coverage investigation](autumn_sale_coverage_investigation.md), [ground-truth feasibility](autumn_sale_ground_truth_feasibility.md).

**Stop:** Phase 5B.3 is complete. Human review precedes Phase 6. There are no unresolved implementation failures; source completeness, true participation, release-hour precision and later predictor timing remain scientific limitations.
