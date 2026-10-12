# First live 10-game test: prepared, blocked before HTTP

Live collection did not start: `ITAD_API_KEY` is absent/nonempty=false in the
collector's process environment. Its value was never printed or read from a
credential file. No HTTP requests were attempted. The remaining 390 new games
were not collected.

The deterministic 500-game cohort was frozen at
`data/cohorts/cohort_500.csv`. Its membership, ordering and SHA-256 remain
unchanged after deriving `data/cohorts/first_live_10.csv`. The test contains
nonpilot sample ranks 1–10, in that order. Each is eligible for 2023–2025 with
no sale-start release-hour uncertainty in the existing candidate frame.

Selected AppIDs:
`1521870, 747130, 2494860, 1110980, 779950, 1777210, 556770, 1868280, 410910, 2358320`.

| Measure | Result |
|---|---:|
| Selected new games | 10 |
| Prior journal attempts | 0; no existing journal |
| Authorized cumulative cap, including retries | 30 |
| Estimated lookup + history requests without retries | 20 |
| Total HTTP attempts | 0 |
| Successful lookups / history retrievals | 0 / 0 |
| Failed HTTP requests | 0 |
| Games not attempted | 10 |
| Newly cached games | 0 |
| Unknown or insufficient game-year labels | 30 |
| API errors / rate-limit responses | None; API not contacted |
| Live collection duration | 0 seconds; not started |
| Offline subset checks, dry run and processing | 0.400 seconds |

Coverage is unobserved for all 10 games in each Autumn Sale year, 2023, 2024
and 2025. These are 10 unknown labels per year, not negative observations.
The downstream feature/evidence/label pipeline ran offline in
`data/cohorts/runs/first_live_10/processing`. It trained no models. The
common incremental cache namespace is `data/cohorts/itad/cache`; offline
preparation created no caches or request journal there.

The actual CLI accepts the 10-row cohort file and `--max-total-attempts 30`.
Its journal reserves and persists every attempt before HTTP, enforces the
cumulative cap before opening a request, and counts retries and interrupted
attempts. No collector code change is required for this scope. Existing
endpoint, shop 61, US, historical-start, pacing, retries and cooldown handling
were inspected and retained.

Before and after preparation, all 219 protected research artifacts matched
their prior SHA-256 hashes, including the original 100 AppID caches, datasets,
four models, reports and scaling preparation. No source code or original
research artifacts were modified in this task.

Parent cohort SHA-256:
`1765eb1cffc66cf3ea48536da0daeae6b5e1a54c095d72d89d942d4fad59e9d9`.

Test cohort SHA-256:
`67c69c5cba7f883e386691dafb37a0111e2408bd3e3e21c7c43f41e7d3da5fd4`.

To resume the already authorized bounded test, make `ITAD_API_KEY` available
privately to the collector's process environment. Do not paste its value into
chat. Reuse the frozen subset and retain the cumulative 30-attempt cap:

```sh
/usr/bin/python3 -B src/03_fetch_itad.py \
  --cohort data/cohorts/first_live_10.csv \
  --cache-dir data/cohorts/itad/cache \
  --output-dir data/cohorts/runs/first_live_10 \
  --max-total-attempts 30 --live
```

This command was not executed. The offline collection reports presently in
that directory describe preparation; live execution will replace those two
collection snapshots. `preparation_status.json` and this report preserve the
preparation record. After actual collection, rerun the following offline stage
and verify protected hashes before reporting live results:

```sh
env -u ITAD_API_KEY /usr/bin/python3 -B src/07_build_autumn_features.py \
  --cohort data/cohorts/first_live_10.csv \
  --cache-dir data/cohorts/itad/cache \
  --output-dir data/cohorts/runs/first_live_10/processing
```

Stop after this test. Do not pass the full 500-game cohort to the live collector.
