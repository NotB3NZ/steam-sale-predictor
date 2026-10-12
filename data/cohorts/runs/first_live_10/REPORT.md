# First live 10-game test results

The bounded test stopped when the network-enabled lookup returned HTTP 403. The key was present in the collector environment and was never displayed. HTTP 403 establishes a forbidden response; the specific reason is not established.

The first sandboxed execution recorded nine timeout/connection failures, affecting three games. It was interrupted to preserve the budget. The resumed network-enabled command reused the frozen subset, cache namespace and append-only journal and recorded one HTTP 403 for the fourth game. The provider safeguard then stopped collection. No further requests were made.

| Measure | Result |
|---|---:|
| Selected games | 10 |
| Cumulative HTTP attempts including retries | 10/30 |
| Successful lookups | 0 |
| Successful history retrievals | 0 |
| Newly cached successful histories | 0 |
| Saved failure checkpoint files | 4 |
| Failed game retrievals | 4 |
| Not attempted after safeguard stop | 6 |
| Unavailable or incomplete histories | 10 |
| Usable / unknown game-year labels | 0 / 30 |
| Timeout/connection failure attempts | 9 |
| HTTP 403 responses | 1 |
| HTTP 429 / rate-limit responses | 0 |
| Collection wall span including resumption | 31.489 seconds |
| Total execution time | 137.401 seconds |

Timing runs from verified prechecks through offline processing, final integrity verification and report assembly. It includes interruption and resumption. The collector JSON run duration describes only the last invocation; this consolidated report accounts for both invocations.

| Autumn Sale | Histories providing usable evidence | Usable labels | Unknown labels |
|---|---:|---:|---:|
| 2023 | 0/10 | 0 | 10 |
| 2024 | 0/10 | 0 | 10 |
| 2025 | 0/10 | 0 | 10 |

Historical coverage is unobserved for all selected games in all three sale years. Unknown labels were retained and were not converted to negatives. No games were replaced.

## Game outcomes

| AppID | Outcome |
|---|---|
| 1521870 | timeout_or_connection_failure |
| 747130 | timeout_or_connection_failure |
| 2494860 | timeout_or_connection_failure |
| 1110980 | HTTP_403 |
| 779950 | Not attempted after provider safeguard stop |
| 1777210 | Not attempted after provider safeguard stop |
| 556770 | Not attempted after provider safeguard stop |
| 1868280 | Not attempted after provider safeguard stop |
| 410910 | Not attempted after provider safeguard stop |
| 2358320 | Not attempted after provider safeguard stop |

## Processing and preservation

The existing offline feature entry point regenerated evidence, coverage, operational/PU labels, features, modeling tables, provenance and data-quality reports for only the frozen 10-game cohort. It produced 30 label rows and 30 feature rows. No model training was invoked.

All 219 original protected artifacts match their prior SHA-256 hashes and sizes, including all 100 original AppID caches. Both frozen cohort hashes remain unchanged. Collector paths enforce read-only reuse of original caches and isolate writes under `data/cohorts`.

Serial pacing, three-attempt endpoint limits, 30-second timeouts, retry backoff, durable cumulative reservations and provider cooldown safeguards were retained. No journal entries were deleted or reset.

Outputs: `collection_manifest.csv`, `collection_quality.json`, `live_prechecks.json`, `live_results.json`, and `processing/data_quality.json` with downstream CSVs and provenance. `preparation_status.json` preserves the earlier offline preparation record.

**Stopped after this test. The remaining 390 games were not collected.**
