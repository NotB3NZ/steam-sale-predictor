# Historical expansion sampling plan

This is a deterministic planning manifest, not a collected or labeled expanded dataset. Cohort sizes are totals including the original 100-game diagnostic pilot. The pilot is identified separately and has no probability-sample inclusion weight.

## Sampling frame and selection

Use the authoritative `data/intermediate/games_master.csv`. Exclude invalid/duplicate identifiers and inconsistent or missing release dates from planning eligibility. For the new balanced historical cohort, require reported release date strictly before every official 2023–2025 sale start date. The existing date-level eligibility rule remains release date <= start date; the stricter sampling rule avoids new release-on-start-day ambiguity without rewriting pilot rules. The pilot retains its one uncertain 2023 pair.

There are 61,559 eligible nonpilot games. Stratify by reported release period: before 2015, 2015–2019, 2020–2022 and 2023 before sale. Game age is derivable from the same date and would be redundant as a second sampling dimension. Snapshot genre/publisher/OS fields exist but are mutable and are not used; snapshot price/owners/activity are excluded. The master itself was already selected by positive snapshot price, so selection bias persists.

Within each stratum sort SHA-256 priorities from UTF-8 `42|appid`, then integer AppID. Interleave strata by exact rational `(within_stratum_rank - 0.5) / stratum_population`, with deterministic ties by stratum, priority and AppID. Take prefixes of 400, 900, 1,900 and 4,900 new games. This gives approximately proportional release-stratum allocations and nested cohorts without future-label or coverage selection. For each size, the design inclusion fraction is `selected_in_stratum / frame_in_stratum`; those fractions are saved in JSON. They describe the pseudorandom design, not uncertainty about the fixed realized manifest.

| Total | Pilot | New | before_2015 | 2015_2019 | 2020_2022 | 2023_before_sale |
| --- | --- | --- | --- | --- | --- | --- |
| 500 | 100 | 400 | 21 | 150 | 165 | 64 |
| 1000 | 100 | 900 | 46 | 338 | 372 | 144 |
| 2000 | 100 | 1900 | 97 | 714 | 786 | 303 |
| 5000 | 100 | 4900 | 251 | 1841 | 2027 | 781 |

## Manifest fields

`appid` is the normalized linkage identifier. `pilot_membership` is 0/1. `release_date` and `release_year` reproduce reported historical release information. `eligibility_2023/2024/2025` apply the existing date-only rule (blank if unknown); `release_hour_uncertain_*` flags equality with the start date. `sampling_stratum` identifies a release-period stratum or the outside/unknown frame. `sampling_priority` is the within-stratum SHA-256 priority for eligible nonpilot games; `probability_sample_rank` is the interleaved rank. Both are blank outside that frame and for pilot games. `selection_status` distinguishes pilot, selected expansion candidate, eligible reserve, uncertain start-day exclusion, later-release exclusion and invalid-release exclusion. `included_in_500/1000/2000/5000` are 0/1 planned cohort flags, including pilot membership.

The manifest contains all unique valid catalog AppIDs, with later releases explicitly outside the sampling frame. The pilot's same-start-day case uses the separate `pilot_start_day_uncertain` stratum. It contains no operational targets, inferred evidence categories, histories, matching-success claims or new feature vectors. Adding unavailable histories or changing future labels cannot change selection. No candidate is guaranteed to be labelable or modelable.

## Collection and nonresponse

Pre-collection variables are AppID, pilot membership and reported release dates/years. Coverage, matching success, empty histories, ambiguity and discount observations become known only after an approved collection. Keep failures and sparse/empty evidence in a collection-accounting ledger; do not replace them with high-coverage games. A failed/missing retrieval cannot be silently converted into an operational zero. Assess inclusion/nonresponse by release stratum before any population claim.

New post-2023-release titles require a separately defined later-entry cohort and eligible game-year panel in a future phase. This plan represents only the restricted balanced historical sampling frame, not all 99,194 catalog entries or the full Steam store.
