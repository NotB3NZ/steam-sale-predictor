# Authorized rollback report — Steam Sale Prediction

Date: 2026-10-13 (Asia/Manila). Status: **COMPLETE / VERIFIED**.

The unfinished Phase 8 authorization, encryption-custody and 20-game collection-trial workflow is RETIRED. No 20-game live collection occurred. The original 100-game pipeline remains the active baseline; useful scaling preparation is preserved. The next objective is incremental ITAD caching and configurable processing for larger cohorts. This rollback did not implement it.

## Archive and provenance

Archive: `/Users/benzdecastro/Documents/Steam_Sale_Rollback_Archive/2026-10-13_012206_PHT`

- **45 original files archived**: 42 retired files plus the three pre-edit documentation files.
- Seven supporting archive files: `MANIFEST.json`, `MANIFEST.sha256`, `git-before-status.txt`, `documentation-before.patch`, `checkpoint.json`, `RESTORE.md`, and `restore.py`.
- All archived source bytes, sizes, modes and modification times were verified. The manifest records original paths, SHA-256 hashes, dispositions, Git tracking status and checkpoint blob IDs where applicable.
- Manifest SHA-256: `4f2dfdeb00e6d0199222c0a71d8e128f9b32cddf3ad735047047767b0b66c6f6`.
- External authorization records, private keys, API credentials and Python environments were excluded from the archive and untouched.

## Recoverable Git checkpoint

- Original branch: `main`.
- Preservation branch: `preserve/phase8-retirement-20261013-012206`.
- Current rollback branch: `rollback/phase8-retirement-20261013-012206`.
- Both branches point to original HEAD `366c16e75e0c36b7938e98c6f6606f58b3dce97e`.
- The branch plus verified archive preserve tracked, modified and untracked pre-rollback files. The branch alone does not contain the former untracked files or pre-edit working-tree documents.
- No files were staged or committed. The rollback remains reviewable in the working tree.

## Removed active files

- `PHASE8B1E_REPORT.md`
- `data/intermediate/expansion/autumn_sale_evaluation_membership.csv`
- `data/intermediate/expansion/autumn_sale_smoke_candidates.csv`
- `reports/expansion/autumn_sale_self_managed_v1_access_policy.json`
- `reports/expansion/autumn_sale_self_managed_v1_approval_manifest.json`
- `reports/expansion/autumn_sale_self_managed_v1_approval_receipt_contract.json`
- `reports/expansion/autumn_sale_self_managed_v1_final_evaluation_plan_proposed.md`
- `reports/expansion/autumn_sale_self_managed_v1_human_approval_receipt_UNAPPROVED_TEMPLATE.json`
- `reports/expansion/autumn_sale_self_managed_v1_phase8b1d_next_steps.md`
- `reports/expansion/autumn_sale_self_managed_v1_phase8b1d_preexecution_inventory.json`
- `reports/expansion/autumn_sale_self_managed_v1_phase8b1d_validation.json`
- `reports/expansion/autumn_sale_self_managed_v1_preexecution_inventory.json`
- `reports/expansion/autumn_sale_self_managed_v1_protocol.md`
- `reports/expansion/autumn_sale_self_managed_v1_review_integrity.json`
- `reports/expansion/autumn_sale_self_managed_v1_validation.json`
- `reports/expansion/autumn_sale_self_managed_v2_approval_manifest.json`
- `reports/expansion/autumn_sale_self_managed_v2_approval_receipt_contract.json`
- `reports/expansion/autumn_sale_self_managed_v2_evaluation_plan_operational_addendum_PROPOSED.md`
- `reports/expansion/autumn_sale_self_managed_v2_human_approval_receipt_UNAPPROVED_TEMPLATE.json`
- `reports/expansion/autumn_sale_self_managed_v2_next_steps.md`
- `reports/expansion/autumn_sale_self_managed_v2_phase8b1e_validation.json`
- `reports/expansion/autumn_sale_self_managed_v2_preexecution_inventory.json`
- `reports/expansion/autumn_sale_self_managed_v2_protocol.md`
- `reports/expansion/autumn_sale_smoke_approval_manifest.json`
- `reports/expansion/autumn_sale_smoke_preflight.json`
- `reports/expansion/autumn_sale_smoke_preflight.md`
- `reports/expansion/autumn_sale_smoke_protected_inventory.json`
- `reports/expansion/autumn_sale_smoke_validation.json`
- `reports/expansion/autumn_sale_trial_authorization_integrity.json`
- `reports/expansion/autumn_sale_trial_authorization_preexecution_inventory.json`
- `reports/expansion/autumn_sale_trial_authorization_readiness.json`
- `reports/expansion/autumn_sale_trial_authorization_readiness.md`
- `src/11_prepare_expansion_collection.py`
- `src/12_prepare_self_managed_collection.py`
- `src/13_prepare_solo_self_managed_collection.py`
- `src/self_managed_sealed_protocol_v1.md`
- `src/self_managed_sealed_protocol_v2.md`
- `tests/fixtures/self_managed_v2_public_certificate.pem`
- `tests/test_expansion_collection.py`
- `tests/test_self_managed_authorization_preparation.py`
- `tests/test_self_managed_collection.py`
- `tests/test_solo_self_managed_collection.py`

The empty `reports/expansion/`, `data/intermediate/expansion/` and `tests/fixtures/` directories contain no remaining files. No retired compiled Python artifacts remain in the source/test trees.

## Updated documentation

`README.md`, `PROJECT_CONTEXT.md` and `PROJECT_STATUS.md` identify retirement, absence of live trial collection, the active 100-game baseline, retained scaling preparation and the next objective. Obsolete authorization commands and links were removed; historical documents remain archived. The stale status entry claiming XGBoost was still unavailable was replaced by the current next objective.

## Integrity and read-only verification

| Check | Result |
|---|---|
| Prior inventory before changes | All 259 files matched recorded SHA-256 and size |
| Retained protected research after rollback/tests | All 227 files match prior SHA-256 and size |
| Pilot caches | All 100 original numeric AppID caches match pilot IDs and prior hashes |
| Original smoke receipt | `data/raw/itad/smoke_test.json` unchanged |
| Models and evaluation artifacts | Four trained models, predictions, metrics, reports and figures unchanged |
| Original inputs and pipeline | Source catalogs, scripts 00–10, labels and feature tables unchanged |
| Scaling preparation | All 11 source/test/data/report/figure artifacts unchanged |
| Archive | All 45 original payload files complete, SHA-256 and metadata verified |
| Trial namespaces | All three absent; no live trial caches/journals created |
| Git diff | Only three edited documents and nine intended tracked deletions; no staged changes |
| Whitespace | `git diff --check` passes |

## Tests and issues

**37 tests passed**, with zero failures, errors or skips: 16 original ITAD collection tests and 21 scaling tests. Real API credentials were removed from the test process environment. HTTP behavior was mocked; socket/DNS calls and repository writes were blocked. Synthetic fixture writes were confined to temporary directories. No original model, dataset or research report was regenerated.

The scaling test `test_complete_audit_manifest_plot_data_integrity_and_light_figures` was deliberately excluded because it regenerates audit datasets/reports/figures. Model-training test suites and artifact-generating verification commands were not run.

The existing `.venv` uses Python 3.14.7 and lacks PIL, matplotlib, pandas, NumPy and scikit-learn. Its initial test import could not load scaling dependencies. Tests passed using the already-installed `/usr/bin/python3` research environment (Python 3.9.6); no dependencies or environments were changed. A temporary test-guard path-resolution error initially blocked fixture cleanup; it was corrected in the temporary harness, with protected hashes verified before and after. No rollback integrity errors or unresolved cleanup issues remain.

## Exact restoration procedure

Save any subsequent work first. To restore the immediate pre-rollback working-tree files (including the three documents), run:

```sh
/usr/bin/python3 -B /Users/benzdecastro/Documents/Steam_Sale_Rollback_Archive/2026-10-13_012206_PHT/restore.py --repo /Users/benzdecastro/Documents/Projects/Steam_Logistics_model --restore-pre-rollback-documentation
```

This verifies the archive and retained protected artifacts before copying, restores all 45 original files with their metadata, rejects conflicting existing retired files, and deliberately replaces the three documents with their archived versions. It does not reset Git, switch branches, change the index or alter protected research. Omit `--restore-pre-rollback-documentation` to restore only the 42 retired files.

If the rollback is committed later and you want the original Git baseline too, save subsequent work and create a recovery branch from the preservation checkpoint:

```sh
git switch -c recover/phase8-pre-rollback preserve/phase8-retirement-20261013-012206
/usr/bin/python3 -B /Users/benzdecastro/Documents/Steam_Sale_Rollback_Archive/2026-10-13_012206_PHT/restore.py --repo /Users/benzdecastro/Documents/Projects/Steam_Logistics_model --restore-pre-rollback-documentation
```

The preservation checkpoint and restoration copies reconstruct the pre-rollback tracked and untracked state. `git reset --hard` and `git clean` are unnecessary.
