# Reproduction guide

Start with the [repository guide](repository_guide.md). This page separates reading saved results from commands that write outputs, fit models, or access APIs. **Only the new public verification commands were executed during finalization.** Commands below for research reproduction are documented options, not new experiments conducted in Phase 9B.2.

## Environment and inputs

The research stack was verified on **CPython 3.9.6 on macOS**, using NumPy 2.0.2, pandas 2.3.3, scikit-learn 1.6.1, SciPy 1.13.1, matplotlib 3.9.4, joblib 1.5.3, threadpoolctl 3.6.0, XGBoost 2.1.4, and Pillow 11.3.0. [requirements-scalable.txt](../requirements-scalable.txt) pins the direct research packages through the baseline/ensemble files. It is not a hash-locked archive of every transitive dependency, font, or operating-system library.

The separate public verifier uses only the Python standard library, requires **Python 3.9+**, and does not load serialized models. Its runtime was tested on 3.9.6. **Python 3.11 was not verified for the research pipeline.** The existing local `.venv` uses 3.14.7 and lacks research dependencies. Old `/usr/bin/python3`, `/private/tmp`, `fcntl`, and font assumptions are machine/platform specific; the legacy pipeline is not verified on Windows.

Optional installation, **not performed in this phase**:

```sh
python3.9 -m venv .venv-research
.venv-research/bin/python -m pip install -r requirements-scalable.txt
```

This writes a local environment and normally downloads packages. `python3.9` must already be available; a different patch/platform is not guaranteed to reproduce exact original bytes. If compatible wheels are already supplied, installation can remain offline:

```sh
.venv-research/bin/python -m pip install --no-index --find-links /path/to/wheelhouse -r requirements-scalable.txt
```

| Input | Availability and role |
| --- | --- |
| Frozen cohort, historical tables, metrics, predictions, images, and ITAD caches | Tracked; sufficient for public artifact verification and reading results. |
| Root `games.csv` | Ignored original 125,855-entry metadata input, about 401 MB. Needed to rebuild source/catalog stages; exact acquisition details and snapshot date are incomplete. |
| Root `games.json` | Ignored companion, about 962 MB; not used by the completed source pipeline, but referenced by some historical inventories. |
| Root `test.py`, `.DS_Store`, and `apikey` | Ignored workspace files present in some old preservation inventories. Never requirements of the public verifier; do not supply credentials to make old snapshots pass. |
| `ITAD_API_KEY` | Required only for explicitly enabled live ITAD collection. No key is needed for public verification or frozen-result inspection. |

## A. Inspect existing research results

No Python environment, API key, or regeneration is required to read the [narrative](../reports/cohort_2000_final_research/narrative_research_report.md), [technical appendix](../reports/cohort_2000_final_research/technical_appendix.md), [model results](../reports/cohort_2000_models/README.md), [EDA](../reports/cohort_2000_eda/README.md), or [2026 prediction figures](../reports/cohort_2000_2026_visualizations/README.md). The repository guide links exact datasets and fitted-model locations.

Operational targets are **A→1, B/D→0, C→Unknown**; no C rows occur in the 6,000-row modeling table. Zeros mean no observed qualifying discount evidence. They are not independently verified nonparticipation. The 2025 result and retrospective 2026 predictions are different research objects.

## B. Safe public offline verification

Run from the repository root:

```sh
python3 -B scripts/verify_public.py
python3 -B scripts/verify_public.py --json
python3 -B -m unittest discover -s tests -p 'test_public_verification.py' -v
```

These commands make no network requests, write no files, fit no models, and produce no new predictions. `-B` suppresses bytecode. The verifier does not consult an API credential, invoke Git, read ignored inputs, or deserialize models. Hashing model bytes is not model loading.

Expected result: exit code 0, explicit **PASS WITH DOCUMENTED EXCEPTIONS**, artifact/link counts, reconciled cohort/label/evaluation/prediction statistics, and the known integrity issues. Any unrecognized missing file, changed hash, incorrect statistic, broken local link, or changed equivalence proof fails with nonzero exit status. JSON goes to stdout; there is no output-file option.

[public_artifact_baseline.json](../scripts/public_artifact_baseline.json) pins 2,474 previously tracked immutable files and separately pins final presentation files. This new baseline identifies the delivered current state; it does not assert that original historical manifests all agree. A fresh clone needs these new files committed along with the existing tracked research. No `.git` directory is needed to run the verifier itself.

### Older checks and expected failures

The original [Phase 9A checker](../reports/cohort_2000_final_research/verify_report.py) is preserved. Its current failure is `Known Phase 8B discrepancy changed`; it also pins ignored files and the old README/ignore bytes. The corrected invocation below fixes only the old README's doubled line-continuation backslash, **not those integrity failures**:

```sh
env -u ITAD_API_KEY PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -B reports/cohort_2000_final_research/verify_report.py
```

The historical scalable runner is not a public all-green smoke test. It depends on local inventory files, includes synthetic fitting tests, and reports the historical evidence mismatch plus the newly authorized `.gitignore` hash difference. Broad `unittest` discovery includes other fitting/regeneration tests. Do not use it as a verification-only command.

Old test/validation receipts describe their creation-time workspace. They are not recomputed or overwritten. Read the [dated integrity addendum](integrity_addendum_2026-10-15.md) before interpreting failures.

## C. Reproduce model evaluation — training and output writes

**This fits models and generates evaluation predictions. It was not run during finalization.** Use a separate working copy with the verified research stack, frozen inputs, and the local files required by legacy preservation checks. A fresh clone alone is not sufficient for all legacy runners: their inventories include ignored metadata and `test.py` even where those files are not predictors.

The finalized execution order is frozen modeling inputs → 2023 training/2024 comparison → lock selection → fresh 2023–2024 fits → 2025 evaluation. Use the cohort temporal adapter, not the earlier pilot or game-disjoint helper:

```sh
env -u ITAD_API_KEY PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 /usr/bin/python3 -B src/train_cohort_temporal.py --input-dir reports/cohort_2000_modeling --output-dir reports/cohort_2000_models_reproduction
```

The destination must be a **new directory under `reports/`**. Expected outputs include separate development/final pipelines, selection receipt, saved predictions, metrics, preprocessing summaries, and checksums. Timestamps and preservation inventories differ between runs. Missing legacy inputs, changed pinned sources, dependency differences, or unsuitable runtime paths can stop execution; no success on a fresh clone is claimed here. Do not change original labels, features, parameters, selection rule, or threshold to resolve a failure.

The 2026 refit runner performs training and inference; public verification does not invoke it. This guide does not instruct recalculation of the frozen 2026 predictions.

## D. Reproduce visualizations — output writes, no original fitting

First inspect the existing PNGs; they are already delivered at 300 DPI. Original same-environment receipts record byte-identical reproduction. Cross-platform fonts or dependency changes can alter image bytes. The following commands were **not run in Phase 9B.2** and use fresh report destinations.

**Phase 7B:** reads saved historical predictions and fitted split gains; guards fitting and prediction methods. Its legacy preservation scan also requires ignored local inventory files.

```sh
env -u ITAD_API_KEY PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp /usr/bin/python3 -B src/visualize_cohort_models.py --input-dir reports/cohort_2000_models --output-dir reports/cohort_2000_visualizations_reproduction
```

**Phase 8D:** reads the frozen modeling table, original cohort, historical evidence, and cached raw records; no models are loaded.

```sh
env -u ITAD_API_KEY PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp /usr/bin/python3 -B src/eda_cohort_2000.py --output-dir reports/cohort_2000_eda_reproduction
```

Expected outputs are eight EDA figures, supporting CSVs, source/caption documentation, and integrity/reproduction receipts. The source-specific and workspace checks remain strict; this phase does not certify that every generator can complete from a fresh clone.

**Phase 8C is currently blocked by committed name drift.** Its preserved adapter requires the earlier two-name discrepancy, but the current CSV has one. This historical command is shown for identification, not as a passing recommendation:

```sh
env -u ITAD_API_KEY PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp /usr/bin/python3 -B src/visualize_cohort_2026.py --output-dir reports/cohort_2000_2026_visualizations_reproduction
```

It rejects the unexpected discrepancy state; do not repair the CSV or weaken its historical checks. The new verifier independently proves current numerical equivalence. Existing eight Phase 8C PNGs and summaries remain pinned and readable.

## E. Recollect ITAD data — optional network work

Recollection is distinct from reproducing saved research. It requires provider access, privately configured `ITAD_API_KEY` in the **process environment**, current account quota, and a separately authorized live session. `.env.example` is a placeholder and is not automatically loaded; the current collector does not read the root `apikey` file. No acquisition details or quota entitlement are invented here.

Use the unchanged original cohort and a new namespace. This bounded example first previews ten games; **the preview writes collection/quality outputs but makes no HTTP requests**:

```sh
/usr/bin/python3 -B src/03_fetch_itad.py --cohort data/cohorts/cohort_2000.csv --cache-dir data/cohorts/recollection_example/cache --output-dir data/cohorts/recollection_example/preview --max-new-games 10 --max-total-attempts 60 --request-interval-seconds 3 --raw-only --dry-run
```

Only an explicitly authorized live session may enable network access:

```sh
/usr/bin/python3 -B src/03_fetch_itad.py --cohort data/cohorts/cohort_2000.csv --cache-dir data/cohorts/recollection_example/cache --output-dir data/cohorts/recollection_example/run_001 --max-new-games 10 --max-total-attempts 60 --request-interval-seconds 3 --raw-only --live
```

Expected outputs are new raw caches, collection receipts, and an attempt journal. This example recollects at most ten original cohort games; it does not expand or replace cohort membership. Respect retries, cooldowns, quotas, and failures. New responses may differ because provider history can change. **Fetching now cannot establish provider availability before a past sale cutoff.** Never merge these outputs into frozen evidence or recalculate the research predictions as part of presentation work.

## Licensing and source provenance

**The owner has not selected a code license.** No license is assigned automatically. Before presenting the repository as reusable licensed software, the owner must choose and add an appropriate license. Public visibility alone is not a license decision.

Code licensing and third-party dataset rights are separate. Historical records are attributed to **IsThereAnyDeal**, Steam shop 61 / US, with request/receipt provenance preserved in [collection documentation](../reports/itad_collection_report.md) and batch receipts. Official sale-calendar sources are attributed to **Valve** in the [evidence audit](../reports/autumn_sale_evidence_audit.md).

The local Steam metadata snapshot is documented in the [source report](../reports/source_data_report.md), but its exact acquisition URL/version, reference date, and reuse permissions are not established here. Its raw files are ignored. Verify redistribution/reuse permissions for metadata, ITAD responses, and third-party artwork independently before distributing them under any new code license; this phase makes no rights determination. No new source downloads or permissions research occurred.
