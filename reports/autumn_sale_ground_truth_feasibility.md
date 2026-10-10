# Phase 5B.2 — Historical Ground-Truth Verification and Label Feasibility

Research/access date: **2026-10-11**. Investigation complete; external verification limited by access and evidence availability. **Final labels have not been generated. Stop for human review before Phase 5B.3.**

## Research objective and required evidence standard

> Given information available about a Steam game before a specific Steam Autumn Sale begins, what is the probability that the game will be discounted at any point during that sale?

The event is a valid Steam-store discount at **any instant** inside `[start_utc, end_utc)`. Start is included; end is excluded. A positive occurrence is existential; an absence claim is universal across the entire event. Formal Valve event enrollment is a different question.

These are minimum requirements for evaluating candidate evidence, **not an approved evidence-to-label policy**:

| Evidence type | Minimum requirement / unresolved decision |
| --- | --- |
| Positive discount evidence | Identifiable AppID/purchase option, explicit Steam storefront, historical event timestamp, currency/region and an authentic discounted offer. One valid point can demonstrate occurrence; source authenticity, eligibility and conflicts still need review. |
| Negative full-sale coverage evidence | A reproducible record covering every instant of the event, with documented capture completeness or an authoritative complete offer schedule, matching storefront/region/purchase scope. No unobserved gap or competing qualifying discount may remain. No investigated source established this. |
| Partial-sale evidence | One or several authentic historical observations with known times. Full price at those points establishes only those points; finite samples cannot rule out a temporary discount between them. |
| Missing evidence | No retrieved relevant observation, empty history, inaccessible page or missing archive entry. Preserve missing fields; none implies absence of a discount. |
| Conflicting evidence | Retain incompatible observations with both provenance chains. First resolve timestamps, regions, editions and purchase options; an apparent mismatch is not automatically a source error. |
| Unknown eligibility | A release date without sufficient event-time precision, delisting or purchase availability ambiguity requires separate review. nekowater 2023 remains unresolved. |

The frozen ITAD collection uses US / USD / Steam shop 61. Whether the eventual outcome is US-specific or across regions, which purchase options qualify, and how free promotions, bundles and rounding are treated remain human decisions. A publisher promotion announcement can corroborate a store offer only when its game, storefront and time scope are explicit; a publication date alone is not a price timestamp. No state is carried forward here.

## Inputs, provenance and unchanged scope

The existing 100-game pilot and 300 game-sale diagnostics are unchanged. Original A/B/C/D totals remain **175/3/0/122**; the 178 directly timestamped in-sale records remain prior-phase evidence, not independent verification. Frozen histories contain 5,568 records; the existing 5B.1 pre-2026 scope contains 4,716. This phase reads the saved diagnostics; it does not recollect prices or rewrite them.

Exact events reuse the verified centralized calendar and its original Valve references:

| Year | UTC start (inclusive) | UTC end (exclusive) | Pacific | Existing source |
| --- | --- | --- | --- | --- |
| 2023 | 2023-11-21T18:00:00Z | 2023-11-28T18:00:00Z | 10 AM PST | [Valve](https://steamcommunity.com/games/593110/announcements/detail/3823053915973575702) |
| 2024 | 2024-11-27T18:00:00Z | 2024-12-04T18:00:00Z | 10 AM PST | [Valve](https://steamcommunity.com/games/593110/announcements/detail/4464851103138185583) |
| 2025 | 2025-09-29T17:00:00Z | 2025-10-06T17:00:00Z | 10 AM PDT | [Valve](https://steamcommunity.com/games/593110/announcements/detail/507340830949770005) |

All 300 pairs are eligible under the original release-date rule, but nekowater’s unknown release hour is not resolved. Only 2023–2025 events are investigated. Current-year outcomes seen incidentally in live pages/search results are excluded, along with current prices and wrong-year promotions.

Inputs and pre-work hashes: [Phase 5B.2 input manifest](sources/phase_5b2_input_manifest.json). Existing reports: [coverage investigation](autumn_sale_coverage_investigation.md), [exact-window audit](autumn_sale_evidence_audit.md), and [boundary comparison](autumn_sale_boundary_comparison.md).

## Sources investigated and access constraints

The [source inventory](sources/historical_price_source_inventory.json) records eleven candidates across all five requested families, field-level availability, access dates, verified facts and unresolved questions. “Not established” means a guarantee or capability was not verified; it does not mean the source has no data. Documentation can describe a source without establishing any selected game’s outcome.

| Candidate / family | Observed access or suitability | Primary reference |
| --- | --- | --- |
| SteamDB historical prices / A | STOPPED_PERMISSION_REQUIRED | [Reference](https://steamdb.info/faq/) |
| SteamDB sales/event history / B | CALENDAR_ONLY | [Reference](https://steamdb.info/sales/history/) |
| Steam store / IStoreService / C | DOCUMENTATION_REVIEW | [Reference](https://partner.steamgames.com/doc/webapi/IStoreService) |
| Steam publisher news / ISteamNews / C | DOCUMENTATION_REVIEW | [Reference](https://partner.steamgames.com/doc/webapi/ISteamNews) |
| Valve publisher financial reports / C | STOPPED_CREDENTIALS_REQUIRED | [Reference](https://partner.steamgames.com/doc/webapi/IPartnerFinancialsService) |
| Internet Archive / Wayback Machine / D | ACCESS_LIMITATION | [Reference](https://help.archive.org/help/using-the-wayback-machine/) |
| Common Crawl / E | DOCUMENTATION_ONLY_NO_CAPTURE_RETRIEVAL | [Reference](https://commoncrawl.org/overview) |
| Steambase / E | DISCOVERY_ONLY_PERMISSION_UNRESOLVED | [Reference](https://steambase.io/games/have-a-nice-death/price) |
| CheapShark / E | DOCUMENTATION_RENDER_LIMITATION | [Reference](https://apidocs.cheapshark.com/) |
| GG.deals / E | ACCESS_LIMITATION | [Reference](https://gg.deals/faq/) |
| Public Steam metadata dataset (May 2024) / E | REJECTED_FOR_EVENT_GROUND_TRUTH | [Reference](https://github.com/RitikSarang/steam-games-dataset-may2024) |

SteamDB automation was stopped because permission is required; no app price pages were scraped. Its event calendar alone supplies no full-sale absence proof. See the [FAQ](https://steamdb.info/faq/).

Steam’s [news method](https://partner.steamgames.com/doc/webapi/ISteamNews) can locate publisher posts; posts are not complete price monitoring. [Publisher financial access](https://partner.steamgames.com/doc/webapi/IPartnerFinancialsService) requires authorized credentials. No credentials were supplied or bypassed. Transactions also do not describe offers when nobody purchased.

Wayback’s [documented lookup](https://archive.org/help/wayback_api.php) and [CDX documentation](https://github.com/internetarchive/wayback/tree/master/wayback-cdx-server) identify captures. The Droid Assault lookup failed through the research tool; no index result or snapshot was obtained. Its HTTP cause is unknown. Archive verification stopped at that limitation; other pilot pairs were not individually queried. A failed request is not an empty archive. [Replay limitations](https://help.archive.org/help/using-the-wayback-machine/) also require checking missing assets and live substitutions before trusting a captured price.

Common Crawl provides a documented archive route, but no selected AppID capture or WARC was retrieved in this phase. Future lookup must follow its [rate guidance](https://blog.commoncrawl.org/faq) and [terms](https://commoncrawl.org/terms-of-use); underlying content rights still apply. Crawl samples cannot by themselves establish uninterrupted offer coverage.

One [Steambase tracker](https://steambase.io/games/have-a-nice-death/price) was inspected for source discovery. The rendered monthly table did not expose the selected 2023 event. No chart export or price data was collected. [Reuse terms](https://steambase.io/legal/terms/) and its [completeness disclaimer](https://steambase.io/legal/fair-use/) prevent assuming an unrestricted complete source. Bulk collection/republication was not undertaken.

CheapShark documentation could not be read sufficiently to verify a suitable endpoint; GG.deals documentation retrieval failed. No undocumented endpoints were guessed. The reviewed public metadata dataset is a snapshot rather than an event-resolution price log. These candidates remain unsuitable or unresolved for the present verification, not proven globally unavailable.

## Diagnostic verification pilot

**Selection is diagnostic, not representative:** 18 pairs / 17 distinct games; A=4, B=3, C=0, D=11. Years contain 9 / 3 / 6 pairs. All three B pairs are mandatory. Remaining strata deliberately cover recent full-price D, very old D, recent discounted D, positive controls, historical timestamp conflicts and an empty history.

Selection has no randomness: numeric AppID/year tie-breaking; recent full-price D chooses the closest per year plus another closest; old D chooses the longest per year with distinct games; recent discounted D chooses the three smallest pre-gaps; A controls use the smallest eligible AppID without conflicts in 2023/2025; two additional conflict-bearing games are ranked by conflict count; an empty history uses the smallest AppID/year. The 30-day stratum is only for sampling. No threshold is approved as a coverage rule.

[Pilot CSV](../data/intermediate/autumn_sale_verification_pilot.csv) preserves original categories and a rationale for every pair. [Evidence CSV](../data/intermediate/autumn_sale_verification_evidence.csv) preserves exact source URLs, access status and separate observed-fact/interpretation fields. Empty historical time/price/currency fields mean no observation was retrieved; they are never zeros.

| AppID | Game | Year | Category | Pre / post observed state | Pre / post gap (days) | Independent result |
| --- | --- | --- | --- | --- | --- | --- |
| 8930 | Sid Meier's Civilization® V | 2023 | D | full_price / discount | 1054.750000 / 166.969248 | NOT_VERIFIABLE |
| 9730 | Tycoon City: New York | 2023 | A | discount / full_price | 78.039479 / 0.008576 | NOT_VERIFIABLE |
| 115320 | Prototype 2 | 2023 | A | full_price / full_price | 0.981424 / 0.008924 | NOT_VERIFIABLE |
| 234490 | Rush Bros. | 2023 | A | full_price / full_price | 131.034641 / 0.009178 | NOT_VERIFIABLE |
| 1740720 | Have a Nice Death | 2023 | D | full_price / discount | 19.022002 / 23.178160 | NOT_VERIFIABLE |
| 1894600 | Monster | 2023 | D | missing / missing | missing / missing | NOT_VERIFIABLE |
| 2268470 | HOPE LEFT ME | 2023 | B | discount / missing | 2.997419 / missing | NOT_VERIFIABLE |
| 2621900 | Railway Islands 2 - Puzzle | 2023 | D | discount / full_price | 1.206030 / 0.158102 | NOT_VERIFIABLE |
| 2650840 | nekowater | 2023 | B | missing / full_price | missing / 7.606794 | NOT_VERIFIABLE |
| 7830 | Men of War™ | 2024 | D | discount / full_price | 0.987106 / 0.012407 | NOT_VERIFIABLE |
| 202410 | Scoregasm | 2024 | D | full_price / missing | 1426.750000 / missing | NOT_VERIFIABLE |
| 303680 | FATE: The Traitor Soul | 2024 | D | full_price / discount | 15.985150 / 173.055949 | NOT_VERIFIABLE |
| 7830 | Men of War™ | 2025 | A | full_price / full_price | 80.987998 / 0.012546 | NOT_VERIFIABLE |
| 219200 | Droid Assault | 2025 | D | full_price / discount | 3.291505 / 73.054757 | NOT_VERIFIABLE |
| 314300 | CubeZ | 2025 | D | full_price / missing | 1732.708333 / missing | NOT_VERIFIABLE |
| 1158850 | The Great Ace Attorney Chronicles | 2025 | D | discount / full_price | 5.986840 / 1.013472 | NOT_VERIFIABLE |
| 1836120 | QUICKERFLAK | 2025 | D | full_price / discount | 8.008137 / 17.013194 | NOT_VERIFIABLE |
| 2205710 | Hentai Beauty | 2025 | B | discount / discount | 12.988738 / 25.013137 | NOT_VERIFIABLE |

## Verification findings: discoverability is not ground truth

| Level / result (pair-level) | Count |
| --- | --- |
| discoverable_source_page_pairs | 8 |
| historical_price_observation_pairs | 0 |
| independent_positive_evidence_pairs | 0 |
| full_sale_absence_evidence_pairs | 0 |
| partial_only_pricing_evidence_pairs | 0 |
| conflicting_source_pairs | 0 |
| not_verifiable_pairs | 18 |
| unknown_release_hour_pairs | 1 |

**Observed facts:** Seven of 17 distinct Steam app-news feeds were accessible in the returned extracts, covering eight selected pairs because Men of War appears twice. Ten pairs’ feed requests failed. The additional Steambase page concerns a pair already discoverable. None yielded a relevant historical price observation, continuous price interval or source contradiction. A 2023 Steam Awards post for Have a Nice Death is non-pricing evidence and is not counted as partial price coverage.

**Verification outcome:** independently positive **0**, full-sale absence **0**, partial-only historical pricing **0**, conflicting independent observations **0**, unverifiable **18**. Conflict counts may overlap other evidence counts when observations exist; unknown release-hour count is a separate eligibility flag. Zero independent conflicts does not clear the known ITAD conflicts: no independent observation was available to compare.

A positive control is an ITAD-positive pair selected to test an independent source, not an independently verified positive. FATE posts for a later sale year and unrelated-year Have a Nice Death promotions were excluded from the selected pairs. Finding a discount for a different year would not verify these pairs; the selection was not changed to favor accessible promotions.

The reviewed ledger contains 21 pair-source attempt rows: 18 app-feed rows (17 distinct URLs, one reused), one public news API probe, one archive-index probe and one Steambase inspection. Searches and documentation access are additional. Underlying web-tool HTTP totals are unavailable. Generic access errors are not described as CAPTCHAs, bans, empty histories or paywalls without supporting evidence. No bypasses or alternative restricted routes were used.

## Special cases and existing conflicting evidence

The following tables reproduce **existing ITAD observations only**, with raw-array provenance. They are not independent confirmations or reconstructed prices. All original B cases and both ordinary A controls are shown:

### Tycoon City: New York (9730), 2023 — A

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency |
| --- | --- | --- | --- | --- | --- | --- |
| pre | 55 | 2023-09-04T17:03:09Z | 3.99 | 9.99 | 60 | USD |
| in | 54 | 2023-11-21T18:30:17Z | 4.99 | 9.99 | 50 | USD |
| post | 53 | 2023-11-28T18:12:21Z | 9.99 | 9.99 | 0 | USD |

Independent historical price verification: NOT_VERIFIABLE. The observed sequence does not establish persistence or full-sale absence.

### HOPE LEFT ME (2268470), 2023 — B

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency |
| --- | --- | --- | --- | --- | --- | --- |
| pre | 1 | 2023-11-18T18:03:43Z | 1.59 | 1.99 | 20 | USD |
| in | 0 | 2023-11-25T18:24:20Z | 1.99 | 1.99 | 0 | USD |

Independent historical price verification: NOT_VERIFIABLE. The observed sequence does not establish persistence or full-sale absence.

### nekowater (2650840), 2023 — B

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency |
| --- | --- | --- | --- | --- | --- | --- |
| in | 54 | 2023-11-21T22:39:17Z | 2.99 | 2.99 | 0 | USD |
| post | 53 | 2023-12-06T08:33:47Z | 1.99 | 1.99 | 0 | USD |

Independent historical price verification: NOT_VERIFIABLE. The observed sequence does not establish persistence or full-sale absence.

### Men of War™ (7830), 2025 — A

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency |
| --- | --- | --- | --- | --- | --- | --- |
| pre | 14 | 2025-07-10T17:17:17Z | 4.99 | 4.99 | 0 | USD |
| in | 13 | 2025-09-29T17:36:25Z | 0.74 | 4.99 | 85 | USD |
| post | 12 | 2025-10-06T17:18:04Z | 4.99 | 4.99 | 0 | USD |

Independent historical price verification: NOT_VERIFIABLE. The observed sequence does not establish persistence or full-sale absence.

### Hentai Beauty (2205710), 2025 — B

| Relation | Raw index | UTC timestamp | Price | Regular | Cut | Currency |
| --- | --- | --- | --- | --- | --- | --- |
| pre | 22 | 2025-09-16T17:16:13Z | 0.49 | 0.99 | 51 | USD |
| in | 21 | 2025-09-30T17:15:31Z | 0.99 | 0.99 | 0 | USD |
| post | 20 | 2025-10-31T17:18:55Z | 0.49 | 0.99 | 51 | USD |

Independent historical price verification: NOT_VERIFIABLE. The observed sequence does not establish persistence or full-sale absence.

nekowater (2650840), 2023, was released on the event start date. The observed full-price record at 22:39:17 UTC does not determine its release hour or whether it was purchasable throughout the event. HOPE LEFT ME has no post-sale record within the permitted observation scope; this does not establish a permanently unchanged offer.

Men of War (7830), 2024 D, has a pre-sale discount at `2024-11-26T18:18:34Z` (USD 0.74 / 4.99, cut 85; raw index 25), and a post-sale full price at `2024-12-04T18:17:52Z` (USD 4.99 / 4.99, cut 0; index 24). The latter is only 17 minutes 52 seconds after event end. This resembles a discount-end pattern but neither observation proves the price inside the event. The public feed supplied no corroborating historical offer.

Railway Islands 2 (2621900), 2023, and The Great Ace Attorney Chronicles (1158850), 2025, likewise have recent pre-sale discounts and no in-window records. Droid Assault (219200), 2025, has recent pre-sale full price but a 73-day post gap; its failed Wayback lookup does not resolve that interval. QUICKERFLAK (1836120), 2025, and the two other recent-full-price D cases remain unverified.

The old-observation stratum includes Civilization V (8930), 2023; Scoregasm (202410), 2024; and CubeZ (314300), 2025, with pre-gaps shown above reaching 1,732.708333 days. Monster (1894600), 2023, has an empty ITAD history and no pre/post state. None has independent retrieved target-price evidence.

Prototype 2 (115320) has three conflicting historical timestamp groups and Rush Bros. (234490) has one. These are pre-event ITAD conflicts, not new source disagreements. Their exact raw-index sequences remain in the unchanged [coverage diagnostics](../data/intermediate/autumn_sale_coverage_diagnostics.csv) and [prior report](autumn_sale_coverage_investigation.md). Neither public feed resolved them; no record was deleted or overwritten.

## Strategy comparison and label feasibility

**Diagnostic interpretation:** the current retrieved evidence does not support a defensible binary outcome dataset. No independent full-sale negative was established. This does not prove that reliable negatives cannot ever be obtained; permissioned complete histories or authoritative publisher schedules remain untested possibilities.

| Strategy | Validity / coverage / false-negative risk | Bias, reproducibility, access and scale |
| --- | --- | --- |
| A — retain direct ITAD discounts as positive evidence; others unresolved | 175 positive-evidence candidates across 300 pairs; 125 others remain unresolved. Requires eligibility/conflict review. No inferred negatives. Cannot support ordinary binary logistic-regression training/evaluation by itself. | Offline and reproducible; access already available. Observation availability can bias which positives are visible. Retain evidence without creating labels. |
| B — ITAD positives plus independently verified full-sale negatives | Conceptually defensible if entire-event absence is genuinely established. Present independent negative coverage is zero; combining single full-price snapshots is insufficient. | Permission/access and completeness proof unresolved. Easily verified or well-known games may be overselected; scale cannot be estimated from this blocked pilot. |
| C — reconstruct from a demonstrably complete change log | Could cover intervening instants only with justified completeness, initial-state validity, purchase scope and timestamp accuracy. No investigated source meets this standard yet. | Requires documented guarantees, permissioned export and source/version capture. Monitoring outages and corrections can create false negatives; no reconstruction implemented. |
| D — independent archived Steam snapshots | Authentic in-event discounted points can support occurrence. Full-price points give partial coverage; a finite set cannot rule out an unobserved temporary discount. | Documented archive access exists, but the probe failed. Sampled capture availability, geolocation, age gates, JavaScript and replay assets introduce bias. No interval completeness established. |
| E — permissioned publisher historical offer/discount schedules | A complete authoritative offer schedule could resolve a limited cooperating cohort; transaction reports alone are insufficient. No schedules obtained or guarantees verified. | Requires publisher/source cooperation and lawful reproducible access. Cohort would likely be selected; any reduced population/research question needs explicit approval. |

**Most defensible next step:** use Strategy A as an evidence-retention approach while leaving unresolved pairs unresolved, not as a finalized label-generation decision. Seek authorized source exports or publisher schedules with explicit completeness before considering Strategy B/C/E. A binary label dataset and logistic regression remain blocked by negative ground truth; label count or class balance is not a reason to weaken the evidence standard.

For the 300 pairs, practical verification requires game/purchase-option/region identity, timestamp alignment, preservation of source payloads, and coverage review over each full event—not merely 300 successful page loads. The 18-pair pilot did not measure a successful verification rate or review throughput. Approximately 99,194 master games imply at most **297,582 game-year reviews** before eligibility filtering. No time/cost estimate or automated scaling claim is supported. Permissioned batch exports would need separate feasibility testing; sampled archives might add positive points without resolving the negative bottleneck.

Source discoverability and source coverage can favor popular titles, long-lived store pages, active publishers and regions frequently crawled. The deliberately difficult pilot cannot estimate population source availability. Source availability may correlate with the intended outcome and predictors, so complete-case training could be biased. Independent vendor branding also does not establish independent collection; shared upstream Steam or ITAD data must be checked.

## Unresolved human decisions

- Define geographic and purchase-option scope, qualifying discounts/free promotions and release eligibility at event-hour precision.
- Decide what authenticated completeness evidence would justify absence or interval reconstruction, and how outages, conflicts and rounding are adjudicated.
- Decide whether to obtain authorized exports/publisher cooperation, attempt permitted archive retrieval in an environment where it works, or revise the study cohort/question.
- Determine how unresolved outcomes and source-selection bias will be handled; no 1/0/UNKNOWN mapping is approved or implemented.
- Keep 2026 outcomes reserved for the planned retrospective verification; no current-year outcomes inform these decisions.

## Validation and reproducibility

Run only the new offline investigation to preserve prior analytical artifacts:

```bash
python3 -B src/06_verify_historical_ground_truth.py --verify
```

The script consumes the reviewed local source inventory/ledger and pre-work manifest, reuses the exact calendar and existing CSV parser, and never collects external observations. A normal run checks the previous execution fingerprint; `--verify` runs the complete offline suite and two repeated executions, then repeats with the verified receipt. It protects all preceding files listed in the manifest, including uncommitted Phase 5B.1 work. Documentation changes are intentionally recorded separately from frozen inputs.

| Check | Result |
| --- | --- |
| Full offline test suite | PASS; 80 tests |
| Deterministic full outputs | PASS: all four outputs identical in two complete runs |
| Protected pre-work files / frozen Phase 4 inputs | 144 / 107; before/after SHA-256 unchanged |
| Previous 300 pair keys and evidence categories | Unchanged; exact event timestamps reconciled |
| Research provenance / missing fields | All 21 attempts have source URL/access date; no invented historical observations |
| Diagnostic network attempts / ITAD pricing requests / new histories | 0 / 0 / 0 |
| 2026 outcome records / final target columns / models | None |

Detailed hashes and execution results: [validation receipt](autumn_sale_ground_truth_validation.json). The [research ledger](sources/historical_price_verification_ledger.json) preserves concise manually reviewed access notes; raw HTML responses were not archived, so live-source replay may change. Offline determinism is not a claim that external sites are immutable. No prior analytical report, raw cache, test or source implementation was modified. README/context/status updates only record this phase.

**Stop gate:** Phase 5B.2 source-feasibility investigation is complete with external verification limitations explicitly recorded. No final labels, features, models or Phase 5B.3 work were created. Human review is required.
