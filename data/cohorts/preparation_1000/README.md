# Preparation for raw ITAD collection: 1,000 games

Prepared offline on 2026-10-13. No live HTTP requests, existing raw-cache
changes, journal changes, research artifact regeneration, or model training
were performed.

## Frozen selection and provenance

[`../cohort_1000.csv`](../cohort_1000.csv) was created by the unchanged
`src/cohort_io.py:select_cohort` procedure: existing `included_in_1000` flags,
pilot-first order, probability sample ranks, and AppID tie-breaking. Seed 42,
release strata, and evaluation groups remain unchanged. The existing 500 rows
are the exact first 500 rows, including their order and all metadata. The next
500 games extend the existing nested selection without substitutions based on
cache outcomes.

Independent selector runs reproduced byte-identical CSV files. The
[provenance receipt](../cohort_1000.provenance.json) records cohort and input
hashes, selector identity, seed, nesting, and the reproduction command. The
selector refuses to overwrite a frozen cohort.

## Collection readiness

The [offline validation receipt](validation.json) records:

- 1,000 unique AppIDs; 500 reusable complete caches and 500 absent caches.
- Reuse of 100 original pilot caches and 400 expansion caches, in their existing
  namespaces. Complete caches are skipped without refresh flags.
- An unchanged journal containing 815 attempts and no active saved cooldown.
- Preservation of all 219 protected artifacts, every existing raw cache, all
  eight archived checkpoints, and `cohort_500.csv`.
- Preservation of 11 timestamp ambiguity groups across nine games (22 entries).
  These provider-response entries remain raw evidence; no deduplication occurs.
- 187 passing tests in the existing guarded offline suite, including eight new
  pacing tests and one new exact-prefix/reproducibility regression. The runner
  forbids network access and repository writes; historical artifact-regeneration
  and model-fitting tests are not run.

An actual raw-only CLI dry run, with repository writes and network access
blocked and reports directed to `/private/tmp`, selected exactly rows 501–525
of the frozen cohort: 25 new games and 50 expected requests. It made zero HTTP
requests and did not create or replace cache files.

## Configurable pacing

`src/03_fetch_itad.py` already delegates its CLI to `src/incremental_itad.py`.
The new `--request-interval-seconds` option defaults to 1.0 seconds. Finite,
nonnegative intervals are accepted; negative, nonnumeric, NaN, and infinite
values are rejected before collection. Zero is an explicit opt-out from pacing.

The interval applies to serial lookup and history request starts, transient
retries, and the first reservation after a restart. The client measures starts
using monotonic time; the journal enforces spacing from the latest persisted
reservation across invocations. The client start timestamp is updated after
journal persistence so persistence delay cannot shorten the next interval.
Slow responses count toward the interval; a full interval is not added after
each response. Provider cooldowns can impose longer waits and are never replaced
by the pacing option. Reports record the configured interval; historical journal
entries and bindings are unchanged.

Immediate 401/403/429 stopping, persistent cooldowns, checkpoint reuse,
explicit failed-checkpoint recovery, append-only reservations, cumulative
budgets, and the exclusive collector lock remain in place.

## First live batch — prepared, not executed

The initial cumulative cap is **875**: 815 historical attempts, 50 expected
requests, and 10 retry-reserve attempts. This permits at most 60 additional
attempts. It is a batch budget, not the budget for all 500 new games. Collection
may stop before all 25 games complete; preserve checkpoints and reassess before
an explicitly budgeted resume. No failed checkpoints currently require
`--retry-failed`.

Run only one collector at a time, from the repository root, in a separately
authorized live session:

```sh
/usr/bin/python3 -B src/03_fetch_itad.py \
  --cohort data/cohorts/cohort_1000.csv \
  --cache-dir data/cohorts/itad/cache \
  --reuse-cache data/raw/itad \
  --output-dir data/cohorts/runs/1000_batch_001 \
  --raw-only \
  --max-new-games 25 \
  --request-interval-seconds 3 \
  --max-total-attempts 875 \
  --live
```

Wait at least **five minutes after the last request** before starting another
batch, and longer if a saved provider cooldown requires it. The collector does
not automatically schedule inter-batch breaks. Keep the same cache namespace
and journal; use distinct run directories and explicit cumulative budgets for
later batches. Do not use refresh flags on completed caches.

The next 500 games are expected to need 500 lookups and 500 histories, or 1,000
requests without retries if all lookups match. That would bring the cumulative
count to 1,815. Unmatched lookups omit history; retries add attempts. The proposed
pacing and breaks are conservative trial settings, not a verified ITAD policy
or a guarantee against 429s. Empty successful histories are valid cache completion
and do not prove an absence of historical discounts.

There are no offline preparation blockers. Authentication and provider behavior
were not tested live during this preparation. Stop before collection or any
downstream labels, features, datasets, or models.
