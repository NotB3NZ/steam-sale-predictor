# Phase 9B.2 change control — 2026-10-15

This phase finalizes documentation, navigation, and safe verification. It conducts no new research, collection, model fitting, inference, or figure generation.

## Starting point and explicit allowlist

The working tree was clean on `main` at commit `dbcfd72` (Final research reports). A SHA-256 baseline of all **2,476 tracked files** was recorded outside the repository before editing. The Phase 9B.1 audit is recorded in the project conversation; no repository audit file was created in that read-only phase.

Only these existing files may change:

- `README.md`: replace the pilot-era landing page with the completed investigation.
- `.gitignore`: add narrowly scoped local environment and credential exclusions.

Only these files may be added:

- `docs/repository_guide.md`
- `docs/reproduction.md`
- `docs/integrity_addendum_2026-10-15.md`
- `docs/phase_9b2_change_control.md`
- `scripts/verify_public.py`
- `scripts/public_artifact_baseline.json`
- `tests/test_public_verification.py`

## Immutable research and historical material

All other **2,474 previously tracked files** retain their start-of-phase bytes: cohorts, catalogs, cached histories, journals, checkpoints, operational labels, feature/modeling tables, configurations, model fits, evaluation results, saved predictions, existing figures, code, tests, narratives, and historical manifests/receipts. The allowlist deliberately leaves earlier documentation unchanged.

The public baseline pins those existing tracked files against the pre-edit inventory. It also pins the final presentation files separately, excluding its own self-referential hash. It is a **new current-state baseline**, not a replacement for, or proof of agreement with, original historical hashes. It contains no dependency on ignored local credentials or source files. The [integrity addendum](integrity_addendum_2026-10-15.md) identifies all accepted historical differences and expected older-check failures.

## Validation boundary

Validation uses standard-library artifact checks and new verification tests only. The verifier forbids network activity, external processes, model imports/deserialization, and filesystem writes. Tests exercise rejected mutations and invalid inputs without changing research artifacts. A separate temporary fresh-clone simulation contains public files only; no `.git`, API key, original raw metadata, virtual environment, or local `test.py` is required.

After finalization, compare every preexisting tracked file against the external baseline, allowing only the two declared edits. Check Git status for unexpected paths. No staging, commits, pushes, dependency installation, broad historical test discovery, training commands, prediction commands, or figure generators are part of this phase.

Historical whole-workspace checks will observe the authorized README/ignore edits. The older 219-file inventory also pins `.gitignore`; its new mismatch is an **authorized presentation change**, separate from the two scientific integrity discrepancies. Preserve the original manifests rather than changing their expected hashes.

## Final verification results

The public verifier passes with documented exceptions, checking **2,474 immutable files**, eight presentation files, **392 local Markdown links across 58 documents**, and the four required existing 300-DPI figures. Its installed guard rejects seven synthetic audit events without performing those actions. All **17 new verification tests** pass; they do not install persistent hooks in the broader unittest process or alter older tests.

A temporary public-files-only export contains **2,483 files** and no Git metadata, API key, ignored metadata snapshots, local `test.py`, or virtual environment. Both the verifier and all 17 tests pass there; every exported file retains its bytes and no extra file is produced. This tests the public verification path, not full legacy pipeline reproduction or a fresh network clone.

Only `README.md` and `.gitignore` differ among the 2,476 original tracked files. The seven added paths match the explicit allowlist. Existing scientific artifacts and historical receipts are unchanged. The Phase 9A failure and Phase 8C adapter limitation remain documented; original manifests are not rewritten. No network requests, model fitting, inference, new figures, automatic staging, commits, or pushes occur.
