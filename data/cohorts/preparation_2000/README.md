# Preparation for raw ITAD collection: 2,000 games

Prepared offline on 2026-10-14. No live HTTP requests or collection were
performed. Existing caches, journal entries, frozen cohorts, archived
checkpoints, collector source, and original research artifacts were preserved.

## Frozen selection

[`../cohort_2000.csv`](../cohort_2000.csv) contains exactly 2,000 unique AppIDs.
The unchanged `src/cohort_io.py:select_cohort` procedure uses existing
`included_in_2000` flags, pilot-first ordering, probability sample ranks,
and AppID tie-breaking. Seed 42, release strata, and evaluation assignments
remain unchanged. The first 1,000 rows match `cohort_1000.csv` exactly in every
column and order; the first 500 also match `cohort_500.csv`.

Two independent temporary selector runs and the final frozen file have
identical bytes. The [provenance receipt](../cohort_2000.provenance.json)
records source/input hashes, selection rules, nesting, and reproduction.
The selector refuses to overwrite an existing frozen cohort.

## Offline validation

The [validation receipt](validation.json) records:

- 1,000 complete, readable, reusable caches: 100 original pilot caches and
  900 expansion caches. Exactly 1,000 new games have absent caches; there
  are no invalid or incomplete active checkpoints.
- 957 nonempty successful histories and 43 empty successful histories.
  Successful empty histories count as complete retrievals and do not prove
  that games never received discounts. Raw histories were not changed.
- An unchanged, validated journal containing 1,816 attempts, with no
  interrupted/unknown attempts or active provider cooldown at validation.
- Byte preservation of all 1,000 existing caches, all 219 protected artifacts,
  both prior frozen cohorts, and all nine archived failure checkpoints.
- 187 passing guarded offline tests, with zero failures, errors, or skips.
  Coverage includes three-second pacing, immediate 401/403/429 stops,
  persistent cooldowns, interrupted-history and explicit failed-checkpoint
  recovery, append-only journaling, cumulative budgets, and the exclusive
  collector lock. Network and repository writes are blocked by the test
  runner; historical regeneration and model-fitting tests are excluded.

A guarded raw-only CLI dry run, writing only temporary reports outside the
repository, selected exactly cohort rows 1001–1250: 250 absent-cache games,
250 expected lookups and 250 expected histories. It made zero HTTP requests.
The collector skips complete caches and rechecks their validity under its
exclusive lock before collection. No refresh or retry flags are needed now.

## First batch — prepared, not executed

From the repository root, in a separately authorized live session:

```sh
/usr/bin/python3 -B src/03_fetch_itad.py \
  --cohort data/cohorts/cohort_2000.csv \
  --cache-dir data/cohorts/itad/cache \
  --reuse-cache data/raw/itad \
  --output-dir data/cohorts/runs/2000_batch_001 \
  --raw-only \
  --max-new-games 250 \
  --request-interval-seconds 3 \
  --max-total-attempts 2366 \
  --live
```

The cumulative cap is **2,366**: 1,816 historical attempts + 500 expected
requests + 50 retry-reserve attempts. It permits at most 550 additional
attempts, including failures. It covers this batch, not all 1,000 new games.
The remaining expansion is expected to require 2,000 requests without retries
if all 1,000 new lookups match; unmatched lookups omit history requests.

Before the live command, verify the journal is still at 1,816, the cohort and
existing caches still match the preparation receipts, no collector holds the
cache lock, and authentication is available without displaying credentials.
Require at least **five minutes after the last HTTP response**, and honor any
longer provider cooldown. This break and cooldown check passed at preparation
time, but must be checked again immediately before starting collection.
The collector enforces saved cooldowns and the three-second request spacing;
it does not automatically schedule the five-minute inter-batch break.

Keep collection serial. Immediate 401/403/429 stopping and the cumulative
budget may leave a partial batch. Preserve its journal and checkpoints and
inspect the recorded failure/cooldown before a separately authorized resume;
use `--retry-failed` only when a failed checkpoint actually requires it.
Successful lookup responses in partial checkpoints can be reused on recovery.
Do not use refresh flags on completed caches. Use a separate output directory
and an explicit cumulative budget for each later invocation.

No offline preparation blockers remain. Three-second pacing is supported and
tested but does not guarantee freedom from provider rate limits; earlier
collection encountered a 429 at that pacing. Live authentication and provider
availability were not tested during this preparation. No labels, features,
model datasets, or model training were produced.
