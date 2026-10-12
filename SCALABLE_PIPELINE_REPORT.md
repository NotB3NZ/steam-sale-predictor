# Scalable pipeline implementation — 2026-10-13

The original pipeline now accepts frozen cohorts and isolated cache/output paths.
The upgrade was implemented and tested offline. No live ITAD requests,
dependency installation, private-key access, original model fitting, or retired
authorization workflow occurred. The Git changes remain uncommitted for review.

## Changes

- `src/03_fetch_itad.py` uses the new incremental runner for its CLI. Collection
  defaults to offline; `--live` is explicit. Cohorts are not limited to the pilot.
- `src/incremental_itad.py` validates and reuses caches, resumes saved lookups,
  records failures, and maintains an append-only HTTP attempt journal. Every
  actual attempt, including retries, has a durable reservation before HTTP.
  Retries are bounded to three attempts per endpoint/retry round; the cumulative
  budget spans restarts and cohort growth. Concurrent collectors are rejected.
- `src/cohort_io.py` selects the existing `included_in_N` flags and sample ranks,
  validates cohort schemas, and enforces isolated outputs. Cohorts are nested,
  deterministic and frozen without outcome-based substitutions.
- Scripts 04–09 accept `--cohort`, `--cache-dir`, `--output-dir` and repeated
  `--reuse-cache`. They use `src/cohort_pipeline.py` and the existing parsers,
  evidence rules and feature functions. Histories are processed one game at a
  time. Repeated full-history display sequences are omitted from expanded
  coverage tables; raw caches and exact in-window provenance remain available.
- Model entry points prepare inputs by default. Optional future `--fit` uses
  existing model parameters/preprocessing in a fresh output model directory.
  Development games in 2023–2024 and evaluation games in 2025 are disjoint.
  Pilot games remain diagnostic development games. New groups use a stable
  SHA-256 split with seed 42, independent of outcomes and retrieval success.
- Added a guarded offline runner, scalable tests, a prior-hash inventory,
  `requirements-scalable.txt` and [environment instructions](ENVIRONMENT_SETUP.md).
  README, project context and status now distinguish current commands from
  historical artifact-generating commands.

The endpoint semantics remain lookup v1 plus history v2, Steam shop `61`, country
`US`, and requested history since `2021-01-01T00:00:00Z`. Collection remains
serial with at least one second between attempts, 30-second request timeouts,
bounded backoff and `Retry-After` handling. Provider cooldowns persist across
restarts. Authentication still uses `ITAD_API_KEY` in the live process
environment; no key file is read and credentials are never printed.

Sale windows, half-open observation intervals, strict pre-sale feature cutoffs,
all 15 predictors, missing-value calculations and existing model parameters
remain unchanged. The original historical fixed-count routines remain available
to regression tests; active CLI paths require configurable isolated outputs.
Historical `--verify` commands are no longer active CLI instructions for 03–09.

## Evidence and reports

Missing, corrupt, unmatched or failed histories yield unknown/null labels.
Successful empty histories retain the original category D operational zero,
which means no *recorded* discount. D, ambiguity and uncertain release-hour
rows are excluded from expanded fitting. This preserves the historical label
definition without claiming unavailable observations are modeling negatives.
Neither an ITAD discount nor an operational zero establishes confirmed Steam
sale participation. Expanded ground-truth reporting remains `UNKNOWN`.

`collection_quality.json` reports target, already cached and newly retrieved
games; planned games/requests; successful HTTP-200 requests, failed requests,
total attempts and interrupted/unknown attempts for the run and cumulatively;
usable/incomplete historical records; insufficient or uncertain labels; coverage
and evidence categories by sale year; duration; configuration and cohort hash.
HTTP-200 status is distinct from valid history retrieval and usable label evidence.
Previously reused caches have no newly attributed HTTP attempts. All target
members remain in the manifest, including failures.

`data_quality.json`, evidence/coverage CSVs, operational/PU labels, features,
modeling tables and feature provenance provide downstream reconciliation.
No current-sale outcomes enter predictors or train-only preprocessing. Evaluation
outcomes are used only for eventual evaluation, with fixed models/thresholds.

## Verification

**158 offline tests passed**, with zero failures, errors or skips. The runner
blocked network/DNS, repository writes and subprocesses; real credentials were
absent. Tests cover incremental skips, failures, empty histories, retries,
bounded budgets, restart checkpoints, persistent cooldowns, corrupted cache and
journal bindings, concurrency, credential reflection, sampling and leakage.

All **219 protected artifacts** match their prior sizes and SHA-256 hashes,
including all **100 original AppID caches**, smoke evidence, source catalogs,
pilot datasets/labels/features, four models, predictions/metrics/figures/reports
and scaling preparation. All **300 original label rows** and **300 feature rows**
match exactly, retaining **175 positives / 125 operational zeros**. Predictions
from all four saved models match stored predictions to tight numerical tolerance
without fitting. Full historical tests that regenerate protected artifacts were
excluded.

Command-line dry runs succeeded for **500 / 1,000 / 2,000 / 5,000 games**. All
seven downstream entry points succeeded with the 5,000-game cohort and existing
caches only, including model preparation. These runs created only temporary
outputs, zero caches and zero HTTP attempts. `git diff --check` passed.
Verification outputs are under `/private/tmp/steam-sale-upgrade-20261013/`.

## From 100 to 500 and beyond

Freeze the existing 500-game selection: 100 preserved pilot games plus 400 new
sampled games. Reuse original caches directly; write new caches to the common
`data/cohorts/itad/cache` namespace. Subsequent larger frozen cohorts reuse both
the originals and every valid new cache. Failed games stay in the selected sample.

| Total cohort | New games from original 100 | Lookup + history, all matched, no retries | Maximum at 3 attempts per endpoint |
|---:|---:|---:|---:|
| 500 | 400 | 800 | 2,400 |
| 1,000 | 900 | 1,800 | 5,400 |
| 2,000 | 1,900 | 3,800 | 11,400 |
| 5,000 | 4,900 | 9,800 | 29,400 |

These are cumulative estimates from the original cache. Expansion from a fully
cached 500 to 1,000 games adds at most 1,000 requests before retries. Unmatched
lookups need one request; partial checkpoints can reuse their lookup. Explicit
refresh/retry rounds consume additional attempts within the cumulative cap.
The 800-request initial estimate has roughly 13 minutes of pacing alone, plus
response times, backoff and provider cooldowns. Account quota and provider
response/coverage behavior were not checked through live requests.

## Exact offline commands

Run from the repository root using the verified interpreter. Reuse an existing
frozen cohort on reruns; selection refuses to overwrite it.

```sh
env -u ITAD_API_KEY PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp \
  MPLCONFIGDIR=/private/tmp/steam-scalable-mpl \
  /usr/bin/python3 -B tests/run_scalable_offline.py \
  --results /private/tmp/steam-scalable-test-results.json

/usr/bin/python3 -B src/cohort_pipeline.py select --cohort-size 500 \
  --cohort-output /private/tmp/steam-scalable-offline/cohort_500.csv

env -u ITAD_API_KEY /usr/bin/python3 -B src/03_fetch_itad.py \
  --cohort /private/tmp/steam-scalable-offline/cohort_500.csv \
  --cache-dir /private/tmp/steam-scalable-offline/cache \
  --output-dir /private/tmp/steam-scalable-offline/collection \
  --dry-run --max-total-attempts 2400

env -u ITAD_API_KEY /usr/bin/python3 -B src/07_build_autumn_features.py \
  --cohort /private/tmp/steam-scalable-offline/cohort_500.csv \
  --cache-dir /private/tmp/steam-scalable-offline/cache \
  --output-dir /private/tmp/steam-scalable-offline/processing

env -u ITAD_API_KEY /usr/bin/python3 -B src/08_train_baseline_models.py \
  --cohort /private/tmp/steam-scalable-offline/cohort_500.csv \
  --cache-dir /private/tmp/steam-scalable-offline/cache \
  --output-dir /private/tmp/steam-scalable-offline/model_preparation
```

The feature command produces reconciled labels and quality reports as well as
features. The baseline command prepares only; no `--fit` is supplied. With only
the original cache, all 400 new games have unknown histories and the held-out
evaluation table is empty. This is expected and is not a performance estimate.
Repeat the selector with 1,000, 2,000 or 5,000 and distinct cohort/output names.

## Future live commands — not executed

Only use these in a separately authorized live session with the documented
environment and a privately supplied `ITAD_API_KEY` already in its environment.
No key value is included in commands. Check current account quota before starting.

```sh
/usr/bin/python3 -B src/cohort_pipeline.py select --cohort-size 500 \
  --cohort-output data/cohorts/cohort_500.csv

/usr/bin/python3 -B src/03_fetch_itad.py \
  --cohort data/cohorts/cohort_500.csv \
  --cache-dir data/cohorts/itad/cache \
  --output-dir data/cohorts/runs/500_first \
  --max-total-attempts 2400 --live
```

Resume with the same cohort/cache and cumulative cap, choosing a new report
directory. Valid caches are skipped; interrupted lookup checkpoints resume
automatically. Add `--retry-failed` only to explicitly retry recorded failures.
Budget, interruption or provider safeguard stops return a nonzero CLI status;
the report and checkpoints remain available for inspection and resumption.
Use `--stale-appid APPID` only for deliberate refresh of a writable cache;
the prior bytes are copied and SHA-256 verified before replacement. Reused
original caches cannot be refreshed in place. Resume a refresh checkpoint
without repeating `--stale-appid` to avoid deliberately requesting another refresh.

For larger cohorts, freeze the corresponding existing selection and retain the
same common cache path. Raise the cumulative cap deliberately; do not discard
or edit the journal. Continue downstream processing with the same configurable
commands and isolated output directories. Model fitting is a separate explicit
future action using `--fit`; it has not been performed here.

## Limits

Retrospective provider history is not proof that a record was available at the
historical cutoff. Sparse/change-oriented history does not establish full-sale
absence. Excluding insufficient labels can introduce coverage selection bias;
report denominators and class balance, and avoid claims of representative
participation prediction. Fitting refuses absent independent evaluation rows or
missing training classes/years. The single 2025 evaluation is not for tuning.

A crash after HTTP finishes but before the cache checkpoint commits can require
a repeated request. Its reserved attempt remains counted as unknown; exactly-once
delivery cannot be guaranteed by a read-only provider endpoint. Truncated, empty
or inconsistent journals stop collection for manual recovery. Reports are run
snapshots; choose distinct output directories to retain each snapshot.

The locally tested stack is Python 3.9.6. The existing Python 3.14 `.venv` is
incomplete and remains untouched. Live provider behavior and enlarged-cohort
fitting were not exercised. Historical receipts retain pinned historical source
hashes; reproduce full historical artifact generation in a separate historical
checkout. The preserved retired authorization archive and external custody
directories were not touched. **Stop before live collection.**
