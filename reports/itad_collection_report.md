# ITAD Collection Report — Phase 4

**Validation: PASS.** All 100 pilot games accounted for; received histories structurally validated. Unmatched AppIDs remain explicit.

## Configuration and verified API contract

Official [documentation](https://docs.isthereanydeal.com/) and [OpenAPI schema](https://github.com/IsThereAnyDeal/API/blob/master/dist/openapi.json) verified 2026-10-05; API 2.11.0.
Header authentication: `ITAD-API-Key`, supplied only from environment variable `ITAD_API_KEY`.
Lookup: `GET /games/lookup/v1?appid=<Steam AppID>`. History: `GET /games/history/v2`.
`id=<ITAD UUID>`, `country=US`, `shops=61`, `since=2021-01-01T00:00:00Z`.
The official default without since is three months. Shops use comma-separated integer IDs; Steam is 61.
Lookup returns boolean found and, when matched, game.id. History is an array of timestamp/shop/deal records.
The schema permits deal=null; non-null deals contain price, regular, and cut. All extra fields and original response text are retained.
Documented responses: 200, 400 and generic errors. Handle 401/403 by stopping, and transient 408/5xx with at most three attempts.
Verified-email default limit: 1,000 requests per five minutes; actual account limits may differ. HTTP 429 supplies Retry-After.
One second minimum between requests. Respect Retry-After; stop rather than shorten waits longer than 60 seconds. Never follow redirects.
No material API differences from the requested methodology. Nullable deals are explicitly preserved.

Run time (UTC): 2026-10-05T17:06:32.189335Z. Authenticated requests this run: 2.
Cache reuse this run: 99. Smoke test: previous smoke PASS; receipt and artifacts verified.
Valid same-configuration caches are reused. Corrupt or incompatible caches require --force; prior artifacts are archived.
Incomplete matched caches retain lookup evidence; --retry-failed deliberately retries history. --force refreshes lookup and history.
Full collection requires a three-game smoke receipt bound to the pilot hash, request configuration and cache hashes.

## Lookup and history results

| Metric | Count |
| --- | --- |
| Pilot games | 100 |
| Matched | 100 |
| Not found | 0 |
| Lookup errors | 0 |
| Not collected | 0 |
| Successful histories (including empty) | 100 |
| Nonempty histories | 97 |
| Empty histories | 3 |
| History request failures | 0 |
| Failed/unmatched/invalid games (unique) | 0 |
| Total history records | 5568 |
| Steam records | 5568 |
| Unexpected shop records | 0 |

Uncollected games are not request failures or empty histories. A blocked authentication run makes zero authenticated calls.

## Temporal diagnostics (Steam records only)

Global earliest/latest: 2021-01-01T00:00:00Z / 2026-10-01T20:20:04Z.
Earliest-timestamp range: 2021-01-01T00:00:00Z to 2023-11-21T22:39:17Z.
Latest-timestamp range: 2021-01-01T00:00:00Z to 2026-10-01T20:20:04Z.
Records per successful game min/median/max: 0 / 55.0 / 136.

| Descriptive calendar-date comparison | Games |
| --- | --- |
| Before Autumn 2023 start | 96 |
| After Autumn 2023 end date | 77 |
| Before Autumn 2024 start | 97 |
| After Autumn 2024 end date | 76 |

Boundaries come from PROJECT_CONTEXT.md. Strict calendar-date comparisons exclude the boundary date; these counts do not establish sale coverage.

## Shop validation

Expected shop.id=61. Unexpected records are preserved and flagged; anomalies stop further requests.
No returned records means shop validation is untested, rather than evidence of Steam-only collection.

Offline safety checks: `python3 -m unittest discover -s tests -v`. Tests use synthetic responses in temporary directories and do not establish live API success.

## Failures and blockers

No observed API failures/unmatched games.

All 100 pilot games accounted for; received histories structurally validated. Unmatched AppIDs remain explicit.

## Human sanity view

| AppID | Name | ITAD ID | Records | Earliest UTC | Latest UTC |
| --- | --- | --- | --- | --- | --- |
| 252490 | Rust | 018d937f-060f-705e-b364-8c5bba4d62f6 | 89 | 2021-01-01T00:00:00Z | 2026-10-01T20:06:14Z |
| 1544810 | HANDMADE CARPROGRAM | 018d937f-4cbb-70e0-b510-6653c4eb7dab | 2 | 2021-03-15T21:21:12Z | 2021-03-16T18:49:07Z |
| 282010 | Carmageddon Max Pack | 018d937f-1339-70a2-83f3-bddda2cf238f | 8 | 2021-01-01T00:00:00Z | 2021-03-05T18:21:14Z |
| 2650840 | nekowater | 018d937f-7820-71b5-a562-a229ba3c4d89 | 55 | 2023-11-21T22:39:17Z | 2026-10-01T20:06:19Z |
| 2504210 | The Leverage Game Business Edition | 018d937f-7456-7396-b192-9e185b79ca1a | unavailable | unavailable | unavailable |

## Validation and limitations

Manifest: 100 unique AppIDs matching the pilot. Every accepted cache is checked for AppID, ITAD ID, raw-body agreement, request configuration, shop IDs and record structure.
pilot_games.csv and games_master.csv SHA-256 unchanged:

- `data/intermediate/pilot_games.csv`: `458ddc9042beb8f978e1607cac6eeace88bd3b9a73537bc2dae82b75c419d14e`
- `data/intermediate/games_master.csv`: `e4fa1eb1a7d5154831badc8b82cd5e1d34409948b0559b18dee81d9192b97852`

Presence of ITAD history does not by itself establish sufficient coverage for an Autumn Sale.

Absence of a price-change record during a sale does not imply that the game was not discounted.

Phase 5 will implement event-specific coverage and labeling rules. No discount labels or event-specific coverage decisions were created.

## Execution

Set ITAD_API_KEY securely in your process environment; the collector does not read apikey or automatically load .env.
Never put credentials in command-line arguments or paste them into reports.

```bash
python3 src/03_fetch_itad.py --limit 3
python3 src/03_fetch_itad.py --limit 3  # confirm cache reuse
python3 src/03_fetch_itad.py            # only after smoke PASS
python3 src/03_fetch_itad.py --validate-cache  # offline audit
```
