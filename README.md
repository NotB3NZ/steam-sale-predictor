# Steam Seasonal Sale Prediction

An ongoing data science project investigating whether historical game metadata and pre-sale pricing behavior can predict a **recorded Steam-store discount** during an Autumn Sale.

The intended primary model is **interpretable logistic regression**, with attention to historical validity, reproducible evidence and associations between game characteristics and recorded discounting behavior. The broader motivation is actual discount participation, but incomplete historical coverage requires an explicitly observation-based target.

**Current milestone: Phase 6 leakage-safe feature engineering completed, pending human review before Phase 7. Operational labels and separate feature/modeling tables exist; no models have been trained.**

## Research Question

> Can historical Steam game metadata and pre-sale pricing behavior predict whether a Steam-store discount will be RECORDED during the Steam Autumn Sale?

The target concerns a particular historical event. Whether a game has ever been discounted does not establish whether it was discounted during the Autumn Sale being predicted.

The operational outcome is at least one qualifying recorded Steam-store discount inside the exact event window. A zero means **discount not observed**, not verified full price or non-participation. Recorded discounts also do **not** verify formal enrollment in Valve's seasonal sale program.

## Research Design

**One observation = one Steam game × one Autumn Sale year.** The same AppID can therefore appear in several years, with any eventual predictors evaluated as of each sale's start.

| Period | Planned role |
|---|---|
| 2023–2024 | Historical training |
| 2025 | Temporal validation |
| 2026 | Final retrospective prediction and manual verification |

The 2026 experiment will be retrospective, rather than a live forecast. **2026 sale outcomes must remain excluded from model development and training.** The current event-specific audit covers only 2023–2025. Cached histories extend into 2026, but their presence does not authorize using 2026 outcomes in model development.

Predictors must represent information available **before the relevant sale begins**. Current metadata is not automatically valid for historical prediction. Logistic regression is planned because it can estimate probabilities and provide interpretable coefficients; any estimated relationships will be associations, not established causal effects.

## Data Sources

| Source | Role | Current state |
|---|---|---|
| `games.csv` | Steam metadata and potential predictor candidates | Original local source; 125,855 rows |
| ITAD historical Steam prices | Evidence for event-specific outcomes | 100 cached pilot histories; 5,568 Steam records |

The metadata contains release information, prices, developers, publishers, genres, tags and engagement snapshots. Its snapshot reference date is unknown. `games.json` is a companion source file and is not used by the completed pipeline. Both source files are preserved and excluded from Git by the existing ignore rules. Source-stage reproduction requires a local `games.csv`; `games.json` is not required.

Phase 4 matched Steam AppIDs to IsThereAnyDeal identifiers and requested histories for `country=US`, Steam shop ID `61`, and `since=2021-01-01T00:00:00Z`. Cached JSON wrappers preserve response bodies, request configuration, lookup evidence and collection metadata. History observations contain timestamps, shop identifiers and deal information with price, regular price, cut percentage and currency where available.

The evidence audit and label builder read local artifacts without additional pricing API requests. Successful collection establishes availability and provenance, not complete historical coverage or actual sale participation.

## Project Progress

| Phase | Description | Status |
|---|---|---|
| 1 | Source Data Inspection | Complete |
| 2 | Game Master Dataset | Complete |
| 3 | Pilot Dataset | Complete |
| 4 | Historical Price Collection | Complete |
| 5A | Autumn Sale In-Window Evidence Audit | Complete; preserved baseline |
| 5A.1 | Exact Sale Boundaries and 2025 Expansion | Complete; Need some more review on my end |
| 5B.1 | Historical Price-State and Coverage Investigation | Complete; pending human review |
| 5B.2 | Historical Ground-Truth Verification and Label Feasibility | Complete; pending human review |
| 5B.3 | Operational Label Construction | Complete; approved |
| 6 | Leakage-Safe Feature Engineering and Modeling Dataset | Complete; pending human review |
| 7 | Logistic Regression Modeling and Evaluation | Not started |
| 8 | Scaling and Final Validation | Not started |

The detailed implementation history is maintained in [PROJECT_STATUS.md](PROJECT_STATUS.md), with current methodological constraints in [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md).

## Phase-by-Phase Research Reports

Reports describe the project at the time each phase completed. Later phases refine earlier assumptions; the current temporal-validity policy follows Phase 2 and the project context, rather than treating early candidate-variable suggestions as feature approval.

### Phase 1 — Source Data Inspection

**Objective:** Establish the structure and quality of the original Steam metadata before processing it.

**Methodology:** Inspect CSV field widths, missingness, numeric distributions, duplicate identifiers and release-date parsing. Supply a corrected schema at load time while preserving the source file.

**Results:** The source has **125,855 rows**, unique AppIDs and no duplicate rows. Its header has **39 fields**, while every data row has **40**: `DiscountDLC count` concatenates two column names. Release dates parse successfully for every row; one name is missing. `Movies` is entirely null, `Tags` is **33.77%** missing, and **84.4%** of rows have zero Peak CCU.

**Key takeaway:** Schema repair is required before analysis. Missing fields, sparse engagement and unknown snapshot timing limit what the metadata can support.

**Detailed report:** [Source Data Report](reports/source_data_report.md).

### Phase 2 — Game Master Dataset

**Objective:** Construct a validated catalog of paid-game candidates for subsequent sampling.

**Methodology:** Use the shared corrected schema; validate AppIDs, names, release dates and prices; trim names; normalize dates to `YYYY-MM-DD`; derive release year; remove unusable columns. Retain optional missing metadata and zero-owner/zero-CCU entries. Source `Price > 0` is an operational eligibility filter, not proof of permanent paid/free status.

**Results:** The master contains **99,194 candidates and 30 columns**. Sequential removals are one missing-name row and **26,660** nonpositive-price rows. In total, **26,661** source rows have zero price, including the missing-name row. No historical sale cutoff is applied at this stage. In-memory and saved-CSV validation passed.

**Key takeaway:** The master is a cleaned catalog, not a modeling dataset. Retaining a snapshot field does not approve it as a historical predictor.

**Detailed report:** [Games Master Report](reports/games_master_report.md).

### Phase 3 — Pilot Dataset

**Objective:** Test the historical-data pipeline on a manageable sample spanning ordinary and unusual catalog entries.

**Methodology:** Start with **61,681** candidates released on or before `2023-11-21`. Use seed **42**, deterministic SHA-256 ranking, an 80-game core allocated across release eras and source-price bands, activity cycling, diagnostic cases and diversity supplementation. Limit selection to two titles per parsed publisher entity.

**Results:** The pilot contains **100 unique games**, with all 30 master columns preserved and six sampling diagnostics. Release-era counts are **20 / 24 / 18 / 21 / 17** for before 2015, 2015–2018, 2019–2020, 2021–2022 and 2023 through the cutoff. Selection and shuffled-input checks produce identical results.

**Key takeaway:** This is a diagnostic diversity sample with unequal inclusion probabilities, not a representative population sample or final training dataset. Sampling diagnostics are not approved modeling features.

**Detailed report:** [Pilot Sample Report](reports/pilot_sample_report.md).

### Phase 4 — Historical Price Collection

**Objective:** Match the pilot to ITAD and preserve historical Steam pricing evidence locally.

**Methodology:** Resolve AppIDs through ITAD lookup, retrieve Steam-specific histories with explicit country/shop/since settings, validate response structure and provenance, and cache original responses. A three-game smoke gate precedes full collection; compatible caches are reused.

**Results:**

| Collection metric | Count |
|---|---:|
| Pilot games processed | 100 |
| Successfully matched | 100 |
| Successful histories, including empty responses | 100 |
| Nonempty histories | 97 |
| Empty histories | 3 |
| Historical Steam records | 5,568 |
| Unexpected shop records | 0 |
| History request failures | 0 |

**Key takeaway:** Matching and structural validation succeeded. A received history—even a nonempty one—does not establish sufficient observation coverage for a specific sale.

**Detailed report:** [ITAD Collection Report](reports/itad_collection_report.md).

### Phase 5A — Historical Evidence Audit

**Objective:** Inspect directly timestamped evidence inside the 2023 and 2024 Autumn Sale windows before choosing labeling rules.

**Methodology:** Read frozen caches offline, separate in-window records from nearest before/after context, and preserve raw observation provenance. The original convention included both UTC calendar dates: midnight on the start date through midnight after the end date, exclusive at that latter boundary.

The audit introduced descriptive categories that remain in use:

| Category | Direct in-window evidence |
|---|---|
| A | At least one observed discount |
| B | One or more records, all showing full price |
| C | Records exist, no discount is observed, and some deal/price information is ambiguous or null |
| D | No directly timestamped observations |

**Results:** The original audit covered **200 pairs and 238 in-window records**.

| Year | A | B | C | D | Records | Games with 0 / 1 / 2 / 3 observations |
|---|---:|---:|---:|---:|---:|---|
| 2023 | 55 | 8 | 0 | 37 | 118 | 37 / 9 / 53 / 1 |
| 2024 | 60 | 4 | 0 | 36 | 120 | 36 / 8 / 56 / 0 |

**Key takeaway:** Missing observations cannot establish that a game was not discounted. All original B cases had one full-price record; several occurred after the actual event ended. Phase 5A was exploratory, and its calendar boundaries were subsequently corrected.

**Detailed report:** [Preserved Phase 5A Report](reports/baselines/phase_5a_calendar_window/reports/autumn_sale_evidence_audit.md), with original CSVs, implementation, context and hashes in the [baseline directory](reports/baselines/phase_5a_calendar_window/) and [baseline manifest](reports/baselines/phase_5a_calendar_window/baseline_manifest.json).

### Phase 5A.1 — Exact Sale Boundaries and 2025 Expansion

**Objective:** Correct event-hour inclusion and extend the evidence audit to 2025 without developing labels.

**Methodology:** Verify both endpoints against official Valve announcements and their artwork, centralize the calendar, account for PST/PDT, and apply the half-open interval `sale_start_utc <= timestamp_utc < sale_end_utc`. Preserve and hash-verify the original Phase 5A baseline before regenerating outputs.

| Year | UTC start, inclusive | UTC end, exclusive | Pacific time at both endpoints |
|---|---|---|---|
| 2023 | 2023-11-21T18:00:00Z | 2023-11-28T18:00:00Z | 10 AM PST, UTC −8 |
| 2024 | 2024-11-27T18:00:00Z | 2024-12-04T18:00:00Z | 10 AM PST, UTC −8 |
| 2025 | 2025-09-29T17:00:00Z | 2025-10-06T17:00:00Z | 10 AM PDT, UTC −7 |

Authoritative source references and archived artwork are documented in the [updated evidence report](reports/autumn_sale_evidence_audit.md); exact boundaries are stored in [the event calendar](src/autumn_sale_calendar.json).

**Results:** **300 unique game-sale pairs and 178 directly timestamped in-window records**, all from Steam shop ID 61.

| Year | A | B | C | D | In-window records | Games with 0 / 1 observations |
|---|---:|---:|---:|---:|---:|---|
| 2023 | 55 | 2 | 0 | 43 | 57 | 43 / 57 |
| 2024 | 60 | 0 | 0 | 40 | 60 | 40 / 60 |
| 2025 | 60 | 1 | 0 | 39 | 61 | 39 / 61 |

Every observed pair has exactly one in-window record. No null, ambiguous or mixed discounted/full-price in-window records occur in this pilot. All pairs meet the existing date-level release eligibility rule; nekowater's release hour on the 2023 sale-start date remains unknown.

For 2023–2024, exact boundaries exclude **121 original records**: one before event start and 120 at/after event end. No records are newly included. **Ten of the twelve original Category B cases become D**—six in 2023 and four in 2024—while A counts remain unchanged.

The recorded validation includes **42 passing offline tests**, independent saved-CSV reconciliation, deterministic reruns, byte-for-byte reproduction of the original baseline artifacts and **107 unchanged frozen-input hashes**. Audit execution made zero network requests; external research was confined to official event-calendar verification, with no new ITAD pricing requests.

**Key takeaway:** Exact event timestamps materially change the evidence classification. **A/B/C/D are descriptive categories, not final binary labels; no final target labels were created.**

**Detailed reports:** [Exact-Window Evidence Audit](reports/autumn_sale_evidence_audit.md) and [Boundary Comparison](reports/autumn_sale_boundary_comparison.md). Validation: [audit receipt](reports/autumn_sale_evidence_validation.json) and [execution checks](reports/phase_5a1_execution_checks.json).

### Phase 5B.1 — Historical Price-State and Coverage Investigation

**Objective:** Investigate surrounding price observations and hypothetical coverage standards before developing target labels.

**Methodology:** Reuse the exact calendar and frozen parser; order observations without carrying prices forward; retain tied conflicts and missing values; compare pre-sale recency scenarios at 7, 14, 30, 60 and 90 days plus unrestricted. All observations dated in 2026 are excluded: **4,716 records** are analyzed and **852** remain outside scope, without changing the caches.

**Results:** All **300 pairs** retain their Phase 5A.1 evidence categories. The three B pairs have latest pre-sale states of two discounted and one missing. The 122 D pairs have 93 full-price, 20 discounted and nine missing pre-states. Among non-A pairs, full-price pre-evidence within 7/14/30/60/90 days occurs in **1/2/7/10/13** pairs; discounted pre-evidence occurs in **7/14/15/15/15**. These counts remain separate and are not inferred negatives. **62 offline tests pass**, repeated full executions are deterministic, and **133 prior-phase file hashes** remain unchanged, including all 107 frozen Phase 4 inputs.

**Key takeaway:** Recency measures availability, not event-wide coverage. Official documentation supports change-oriented history, while complete capture and safe price persistence remain unresolved. No final labels or coverage rule were created.

**Detailed report:** [Coverage Investigation](reports/autumn_sale_coverage_investigation.md), [validation receipt](reports/autumn_sale_coverage_validation.json), [pair diagnostics](data/intermediate/autumn_sale_coverage_diagnostics.csv) and [hypothetical sensitivity scenarios](data/intermediate/autumn_sale_coverage_sensitivity.csv).

### Phase 5B.2 — Historical Ground-Truth Verification and Label Feasibility

**Objective:** Investigate whether independent historical sources can establish discount occurrence or absence throughout an entire Autumn Sale.

**Methodology:** Review eleven source candidates and select 18 diagnostic pairs deterministically, including all three B cases, recent/stale D cases, positive controls, an empty history and timestamp conflicts. Preserve source URLs and access outcomes in a reviewed research ledger; regenerate artifacts offline.

**Results:** Eight selected pairs had a discoverable source page, but none yielded relevant historical price evidence. Independent verification found **0 positive, 0 full-sale absence, 0 partial-only pricing and 0 conflicting observations; all 18 remain NOT_VERIFIABLE**. SteamDB automation required permission; publisher access required credentials; the archive lookup failed. None of these limitations implies no discount. Prior 300 pairs and evidence categories remain unchanged.

**Key takeaway:** A binary dataset for verified actual participation was not established. Direct ITAD discounts remained positive evidence candidates; other outcomes were unresolved. Complete authorized histories or publisher schedules would need verification before any interval reconstruction or true-negative inference. No labels were generated in Phase 5B.2; Phase 5B.3 subsequently adopted the operational recorded-discount target.

**Detailed report:** [Ground-Truth Feasibility](reports/autumn_sale_ground_truth_feasibility.md), [validation receipt](reports/autumn_sale_ground_truth_validation.json), [source inventory](reports/sources/historical_price_source_inventory.json), [verification pilot](data/intermediate/autumn_sale_verification_pilot.csv) and [source evidence](data/intermediate/autumn_sale_verification_evidence.csv).

### Phase 5B.3 — Operational Label Construction

**Objective:** Construct reproducible labels for recorded discounts after independent full-sale negative verification proved unavailable in Phase 5B.2.

**Methodology:** Reuse the existing exact calendar and observation parser, reconcile saved evidence/provenance, and apply `operational_observed_v1`: A → 1; B/D → 0; C → null with ambiguity/review flags. PU status is A → positive; all others → unlabeled. Every label carries a historical-coverage limitation flag.

**Results:** All **300 pairs** retained: **175 recorded-discount ones / 125 non-observation zeros / 0 nulls**. Yearly ones/zeros: **2023 55/45; 2024 60/40; 2025 60/40**. PU: **175 positive / 125 unlabeled**. nekowater's 2023 release-hour uncertainty remains flagged; no row was removed. Prior categories and frozen artifacts remain unchanged.

**Key takeaway:** Operational labels support a recorded-discount modeling task. Zero does not establish that a game was never discounted. Future evaluation and probabilities must be interpreted against recorded occurrence, not independently verified participation. No features, PU algorithms or models were built.

**Detailed report:** [Operational Labeling](reports/autumn_sale_operational_labeling.md), [validation receipt](reports/autumn_sale_operational_label_validation.json), [operational labels](data/intermediate/autumn_sale_operational_labels.csv) and [PU view](data/intermediate/autumn_sale_pu_labels.csv).

### Phase 6 — Leakage-Safe Feature Engineering

**Objective:** Create a compact predictor table for the 300 authorized game-year pairs, independently of the operational target.

**Methodology:** Reuse the verified calendar and price parser; require every price observation to precede its sale-start UTC cutoff. Admit date-derived metadata under the existing release-date accuracy assumption; exclude mutable undated snapshots. Keep an explicit 15-feature allowlist and separate the target join from feature calculation.

**Results:** **300 unique rows / 100 games**, with **100 rows per year**. Features comprise age and release year/month/quarter; prior price/discount observation counts and ratio; price/discount recency; max/mean prior discount; latest observed price/cut; and two pre-history flags. Ten rows lack valid prior price evidence; 46 lack prior discount evidence. Missing values remain blank, counts/flags remain explicit, and one same-day release-hour audit flag is preserved outside the predictor allowlist. All observed currencies are USD; mixed/non-USD monetary values or conflicting latest prices would be withheld.

**Key takeaway:** Direct future and target leakage is tested: injecting cutoff/current-sale/future observations or changing targets leaves predictors unchanged. Retrospective provider availability, initialized timestamps and release-date interpretation remain limitations. Counts are observations, not campaigns or durations; latest prices are observations, not carried-forward sale-start states. **136 offline tests pass**, five outputs are byte-identical across repeated executions, and **159 protected prior files**, including **107 frozen Phase 4 inputs**, remain unchanged. No model, imputation, feature selection against targets or performance estimate was created.

**Detailed report:** [Feature availability and definitions](reports/autumn_sale_feature_availability.md), [machine-readable allowlist](reports/autumn_sale_feature_manifest.json), [validation receipt](reports/autumn_sale_feature_validation.json), [features](data/intermediate/autumn_sale_features.csv) and [modeling table](data/intermediate/autumn_sale_modeling_table.csv).

## Key Findings So Far

- **The history endpoint is change-oriented, but completeness and persistence remain unestablished.** Official ITAD documentation describes price changes; empirical repeats and six conflicting timestamp groups prevent treating records as a strict, complete change log. See the [coverage investigation](reports/autumn_sale_coverage_investigation.md#i-itad-history-semantics-assessment).
- **Event hours matter.** Calendar end dates admitted post-sale full-price observations, changing ten full-price-only cases once exact boundaries were applied. See the [boundary comparison](reports/autumn_sale_boundary_comparison.md).
- **Absence of a record is not proof of no discount.** Operational zero represents non-observation; surrounding evidence does not establish prices throughout the sale.
- **Coverage limits the outcome interpretation.** The approved target now measures recorded occurrence. Sparse histories can still bias future modeling and cannot establish actual participation probabilities.

## Methodological Considerations

| Concept | Current treatment |
|---|---|
| Observed evidence | Timestamped Steam records, with raw fields and provenance retained |
| Inferred price states | Not implemented; no interpolation, missing-observation filling or price carry-forward |
| Operational labels | Implemented: A → 1, B/D → 0, C → null; zero means discount not observed |
| Actual participation | Unverified; operational zeros are not true negatives |

`discount_observed` is `1` for a recorded qualifying discount and `0` for no qualifying observation; Category C remains null for review. The separate PU view preserves positive/unlabeled status without treating unlabeled pairs as verified negatives. The earlier proposed `1/0/UNKNOWN` true-participation target remains unverified and is distinct from the approved operational target. No coverage threshold, daily-price reconstruction or persistence rule is assumed.

The audit describes a discount when explicit cut > 0 and price < regular; full price requires cut = 0 and equal price/regular amounts. These checks describe an observation, not an event-level target label. Missing or contradictory information remains ambiguous.

Price-state persistence between timestamps remains unresolved. Before/after observations are contextual diagnostics only. Null deals retain their raw meaning and are treated as ambiguous evidence rather than automatically full price. Conflicting equal-time records remain separate, with original array indices and inspectable context ties.

Temporal leakage must be addressed independently of outcome labeling. Current Price, Discount, review totals, Peak CCU, playtime and other snapshot fields can contain post-event information. The source Discount column is not a target label. Even relatively stable metadata requires historical assessment; interpretable coefficients would not establish causation.

The pilot supports pipeline diagnostics, not population-level discount rates or model-performance claims. Publisher token parsing is approximate, and the approved catalog includes some software/non-game products. Date-level release eligibility cannot resolve whether a same-day release preceded the exact sale start. Observed discounts also cannot establish formal Valve event enrollment.

## Project Structure

Important existing files and directories:

```text
.
├── README.md
├── PROJECT_CONTEXT.md
├── PROJECT_STATUS.md
├── requirements.txt
├── games.csv                         # Original local metadata; Git-ignored
├── games.json                        # Local companion source; not used
├── data/
│   ├── raw/itad/                      # Per-AppID JSON, smoke receipt, archive/
│   ├── intermediate/
│   │   ├── games_master.csv
│   │   ├── pilot_games.csv
│   │   ├── itad_collection_manifest.csv
│   │   ├── autumn_sale_evidence_audit.csv
│   │   ├── autumn_sale_evidence_records.csv
│   │   ├── autumn_sale_coverage_diagnostics.csv
│   │   ├── autumn_sale_coverage_sensitivity.csv
│   │   ├── autumn_sale_verification_pilot.csv
│   │   ├── autumn_sale_verification_evidence.csv
│   │   ├── autumn_sale_operational_labels.csv
│   │   ├── autumn_sale_pu_labels.csv
│   │   ├── autumn_sale_features.csv
│   │   └── autumn_sale_modeling_table.csv
│   └── processed/                    # Currently empty; no fitted-model outputs
├── src/
│   ├── source_schema.py
│   ├── 00_inspect_source.py
│   ├── 01_build_games_master.py
│   ├── 02_create_pilot.py
│   ├── 03_fetch_itad.py
│   ├── 04_audit_autumn_evidence.py
│   ├── 05_investigate_sale_coverage.py
│   ├── 06_verify_historical_ground_truth.py
│   ├── 06_build_operational_labels.py
│   ├── 07_build_autumn_features.py
│   └── autumn_sale_calendar.json
├── tests/
│   ├── test_itad_collection.py
│   ├── test_autumn_evidence_audit.py
│   ├── test_autumn_sale_coverage.py
│   ├── test_historical_ground_truth.py
│   ├── test_operational_labels.py
│   └── test_autumn_features.py
├── reports/                          # Phase reports and validation receipts
│   ├── baselines/phase_5a_calendar_window/
│   │                                 # Original CSVs/report/receipt/code/context + manifest
│   └── sources/                       # Reviewed research JSONs and calendar artwork
└── notebooks/                        # Currently empty
```

The audit CSV has one row per game/year. The evidence-record CSV has one row per actual in-window observation. Neither is a model-ready labeled dataset.

The operational label CSV is a **target/provenance table, not a predictor table**. Categories, PU status, supporting indices, in-sale counts and coverage/collection diagnostics must not become predictors. The PU CSV is only a lightweight optional sensitivity view; no PU-learning method is implemented.

## Reproducibility

Run commands from the repository root. The current offline audit uses Python's standard library, including `zoneinfo` (Python 3.9+) and the system's IANA timezone database. Source processing additionally requires the pandas and NumPy minimum versions listed in [requirements.txt](requirements.txt); dependency versions are not pinned to a reproducible lockfile.

### Source Inspection, Master and Pilot

With the original `games.csv` available locally and the requirements installed, the implemented entry points are:

```bash
python3 src/00_inspect_source.py
python3 src/01_build_games_master.py
python3 src/02_create_pilot.py
```

The inspection prints diagnostics without modifying the source; its detailed Markdown report is maintained separately. Master and pilot scripts regenerate their intermediate CSVs and reports, with validation and input-hash checks. Reproduce these earlier stages in a separate working copy when preserving the current frozen audit inputs.

### Historical Price Collection

Collection requires an ITAD API credential supplied securely through the process environment as `ITAD_API_KEY`. The collector does not read a local key file or automatically load `.env`. For a separately authorized collection in an isolated working copy with the pilot and master available, the existing smoke/full entry points are:

```bash
python3 src/03_fetch_itad.py --limit 3
python3 src/03_fetch_itad.py
```

The full run requires a valid three-game smoke receipt. These commands can make pricing API requests and are **not needed to reproduce the cached evidence audit**. Phase 4 inputs are frozen for the current research stage.

The collector's `--validate-cache` mode makes no API calls but still rewrites the Phase 4 manifest/report and, on success, project status. It is not a read-only verification command for the current frozen repository; use the evidence-audit workflow below.

### Offline Evidence Audit and Tests

The audit needs the frozen pilot/master/manifest, cached ITAD JSONs, preserved Phase 5A baseline, Phase 4 script/report, current project context, event calendar and archived official artwork. No API key or new pricing requests are required.

```bash
python3 src/04_audit_autumn_evidence.py
python3 -m unittest discover -s tests -v
```

The audit regenerates the two evidence CSVs, updated audit report, validation receipt and boundary comparison. It verifies baseline and frozen-input hashes before analysis and checks preservation afterward. The tests use temporary fixtures, mocked collection responses and isolated baseline reproduction. They do not train a model or refresh the production caches.

The existing [execution receipt](reports/phase_5a1_execution_checks.json) records 42 passing tests, independent CSV validation and identical outputs across repeated full audits. The audit reuses that receipt only when the tested source hashes match; it does not run or certify new tests automatically.

### Offline Coverage Investigation

To reproduce Phase 5B.1 without regenerating previous-phase artifacts:

```bash
python3 src/05_investigate_sale_coverage.py --verify
```

This standard-library workflow reads the frozen inputs and local documentation note, runs the full offline test suite under a socket/DNS prohibition, generates the two coverage CSVs and report/receipt, and verifies identical repeated executions. It makes no pricing API requests and requires no credentials. Its 2026 cutoff also censors post-sale context; missing post observations remain missing. Prior Phase 5A/5A.1 outputs and the baseline are preserved.

To reproduce Phase 5B.2 from the reviewed local source inventory and research ledger:

```bash
python3 -B src/06_verify_historical_ground_truth.py --verify
```

This offline workflow runs the full test suite, verifies repeated identical outputs and checks 144 protected preceding files. It does not repeat external research, request pricing data or regenerate prior-phase artifacts. Source-access failures and missing observations remain explicit; no final target columns are created.

### Offline Operational Labels

```bash
python3 -B src/06_build_operational_labels.py --verify
```

The builder validates local schemas, exact UTC windows, categories, raw-record provenance and counts; produces the operational/PU CSVs and report/receipt; runs the complete offline suite; and checks repeated byte-identical outputs. It verifies **153 protected prior files**, including all frozen Phase 4 inputs, without regenerating prior analytical artifacts. It makes no API calls and performs no source research.

### Offline Feature Engineering

```bash
python3 -B src/07_build_autumn_features.py --verify
```

Uses only local pilot/master metadata, cached Steam histories, authorized pair identities and the verified calendar. No API credential or new dependency is needed. This command generates only Phase 6 artifacts and preserves previous phase outputs. The full offline suite and repeated executions verify cutoff/target invariance, deterministic bytes and protected input hashes.

Pricing cutoffs are **2023-11-21T18:00:00Z**, **2024-11-27T18:00:00Z**, and **2025-09-29T17:00:00Z**; an observation exactly at a cutoff is excluded. The feature-only CSV contains no target. The modeling CSV adds only `discount_observed`. Future modeling must use `baseline_feature_allowlist` from the manifest rather than selecting all numeric columns: identifiers, cutoff and `audit_release_hour_uncertain` are audit/linkage fields.

## Current Status and Next Steps

**Phase 6 is complete and awaits human review. Phase 7 has not started.**

Next, build a logistic-regression baseline with training-only missing-value handling, scaling and encoding after approval. Use 2023–2024 for training and reserve 2025 for temporal validation; exclude 2026 outcomes from development. Do not interpret operational zeros as verified non-discounts or eventual model probabilities as verified participation probabilities.

The release-date assumption, same-day eligibility, provider backfill/initialization and incomplete histories remain limitations. Six games have pre-cutoff observations preceding their reported release date; early access/preorders and source interpretation are possible explanations, not verified conclusions. Pre-cutoff evidence availability is necessary but does not establish what ITAD knew at that instant. No price interpolation or persistence is assumed, and undated snapshot prices, discounts, reviews, ownership, activity and mutable metadata are excluded. The project stops before Phase 7.

## Technologies

| Implementation state | Technologies |
|---|---|
| Used in completed phases | Python; pandas; NumPy; standard-library CSV/JSON, SHA-256 hashing, timezone handling, HTTP collection and `unittest`; Git; ITAD API with local caching |
| Planned for modeling | Logistic regression; scikit-learn is not currently listed in requirements or used by the completed pipeline |

No trained-model performance, coefficients or causal conclusions are available at this stage.
