# Steam Autumn Sale Discount Prediction

An independent data science research project investigating whether historical Steam game metadata and pre-sale pricing behavior can predict a recorded Steam-store discount during the Autumn Sale.

The completed initial experiments compare a constant-probability Bernoulli baseline with logistic regression on a 100-game historical pilot. Training uses 2023–2024 observations; validation uses 2025 observations. The target is **recorded discount occurrence**, not independently verified sale participation.

## Research question

Can information about a game before an Autumn Sale begins predict whether a qualifying Steam-store discount will be recorded during that sale?

Each observation represents one game in one sale year. The operational target, `discount_observed`, is `1` when at least one qualifying discount is recorded inside the official sale window and `0` when none is recorded. A zero does not establish that the game remained at full price throughout the event. A recorded discount also does not establish formal enrollment in Valve's seasonal sale program.

## Data and scope

The broader metadata source, `games.csv`, contains **125,855 Steam entries**. Cleaning produces a catalog of **99,194 paid-game candidates**, using valid identifiers, names, release dates and positive source prices. This catalog is distinct from the modeling dataset; the source-price filter does not establish permanent paid or free-to-play status.

The historical pilot contains **100 games** selected for diagnostic diversity across release eras, source-price bands and other sampling characteristics. It is not a representative sample of the Steam catalog. Observing those games in the 2023, 2024 and 2025 Autumn Sales produces **300 game-year observations**, with **175 operational positives and 125 operational negatives**.

### Sources

Game metadata comes from the local `games.csv` snapshot. Its reference date is unknown, so contemporary prices, reviews, ownership and player activity are not used as historical predictors. A known concatenated CSV header is corrected at load time through `src/source_schema.py`; the original source remains unchanged. The companion `games.json` is not used by the completed pipeline. Both source files are Git-ignored, and source-stage reproduction requires a local copy of `games.csv`.

Historical prices come from [IsThereAnyDeal](https://isthereanydeal.com/), collected for Steam shop ID `61`, country `US`, with a requested history start of `2021-01-01T00:00:00Z`. The 100 cached histories contain **5,568 Steam records**; 97 histories are nonempty and three are empty. Original responses and collection provenance are retained under `data/raw/itad/`. Baseline reproduction uses these local artifacts without new pricing requests.

Sale boundaries were verified against official Valve announcements and artwork. The [event calendar](src/autumn_sale_calendar.json) and [evidence audit](reports/autumn_sale_evidence_audit.md) retain the source references.

| Sale year | UTC start, inclusive | UTC end, exclusive |
|---|---|---|
| 2023 | 2023-11-21T18:00:00Z | 2023-11-28T18:00:00Z |
| 2024 | 2024-11-27T18:00:00Z | 2024-12-04T18:00:00Z |
| 2025 | 2025-09-29T17:00:00Z | 2025-10-06T17:00:00Z |

## Methodology

### Labels and historical features

Labels use directly timestamped Steam observations within each half-open sale window. A qualifying discount requires an explicit positive cut percentage and a price below the regular price, with valid amounts and matching currencies. Missing or contradictory deal information remains ambiguous. The labeling rule supports null labels for ambiguous cases; none occur in the current 300-row dataset. Surrounding prices are contextual evidence, without interpolation or carry-forward assumptions.

Predictors are calculated independently of the target using observations strictly before the relevant sale start. Date-derived metadata is included under the assumption that the reported release date is accurate and stable. Modeling uses only the 15 predictors approved in the [feature manifest](reports/autumn_sale_feature_manifest.json):

| Feature group | Predictors |
|---|---|
| Release information | `game_age_days`, `release_year`, `release_month`, `release_quarter` |
| Historical observations | `prior_price_record_count`, `prior_discount_count`, `prior_discount_rate` |
| Recency | `days_since_last_price_record`, `days_since_last_discount` |
| Historical prices and cuts | `max_prior_discount_pct`, `mean_prior_discount_pct`, `last_observed_price`, `last_observed_discount_pct` |
| Coverage indicators | `has_prior_price_history`, `has_prior_discount_observation` |

AppID, sale year and prediction cutoff are linkage or split fields. The target, release-hour audit flag, evidence categories, PU status and current-sale outcomes are excluded from predictors. Counts describe recorded observations, not distinct discount campaigns or discounted durations. The latest observed price is not treated as the price at sale start.

### Evaluation protocol

| Split | Sale years | Observations | Positive | Negative |
|---|---|---:|---:|---:|
| Training | 2023–2024 | 200 | 115 | 85 |
| Validation | 2025 | 100 | 60 | 40 |

The split is chronological, without random mixing across years. Preprocessing and model fitting use training data only. Hyperparameters are fixed initial defaults, with no search or validation-based threshold selection. Both models classify a probability of at least **0.50** as an operational positive.

The same 100 games appear across years. This tests temporal generalization to a later sale for previously represented games, not generalization to entirely unseen games or the full catalog.

### Baseline models

The Bernoulli baseline uses `DummyClassifier(strategy="prior")` to assign every validation observation the training positive rate: **115 / 200 = 0.575**. It uses no game-specific predictors or preprocessing. The validation prevalence of 0.600 is an evaluation reference, not its fitted probability.

Logistic regression uses an explicit sklearn pipeline: approved feature selection, training-only median imputation, StandardScaler and `LogisticRegression(penalty="l2", C=1.0, solver="lbfgs", max_iter=2000, random_state=42)`. Existing historical coverage indicators are retained without additional missingness indicators. No training feature is constant or entirely missing, so all 15 approved predictors are retained. Coefficients describe associations on the transformed feature scale, without causal interpretation.

## Results

The completed Phase 7A experiments give the following results on the 100 observations from 2025:

| Model | ROC-AUC | Average precision | Brier score | Accuracy |
|---|---:|---:|---:|---:|
| Bernoulli baseline | 0.500000 | 0.600000 | 0.240625 | 0.600000 |
| Logistic regression | 0.933750 | 0.937660 | 0.075389 | 0.910000 |

Logistic regression improves ranking, probability error and fixed-threshold accuracy over the constant baseline on this holdout. These are pilot results against recorded-discount labels; they do not establish actual participation probabilities or catalog-wide performance. [The evaluation report](reports/autumn_sale_baseline_evaluation.md) includes log loss, precision, recall, F1, coefficient interpretation and calibration diagnostics. Exact metrics are saved in [JSON](reports/autumn_sale_baseline_metrics.json).

![ROC curves for both baselines on the 2025 validation observations](reports/figures/baseline_roc_curves.png)

The ROC curves compare the models using their actual validation probabilities.

![Sigmoid transformation with actual logistic regression validation predictions](reports/figures/logistic_sigmoid.png)

The sigmoid transforms the combined multivariable decision score into a probability. All 100 overlaid points are fitted-model validation predictions. They lie on the curve by construction; this is an explanatory figure, not evidence of predictive accuracy.

![Logistic regression confusion matrix at the fixed 0.50 threshold](reports/figures/logistic_confusion_matrix.png)

Rows are actual operational labels and columns are predicted labels. At the fixed threshold, logistic regression produces 32 true negatives, eight false positives, one false negative and 59 true positives **against the operational labels**.

Additional coefficient, precision–recall, probability-distribution, reliability and Bernoulli-distribution figures are available in [reports/figures/](reports/figures/). All figures use a consistent light-mode style and are exported at 300 DPI.

## Limitations

Historical coverage is incomplete. An absent discount record cannot establish absence of a discount, and models may learn recording coverage as well as discount behavior. The history endpoint is change-oriented; complete capture and price persistence between records have not been established. Independent research did not establish verified full-sale negatives for the diagnostic verification sample.

Filtering timestamps prevents direct use of future observations, but retrospective provider records do not prove that the information was available at the historical prediction time. Backfill, requested-since initialization, release-date corrections and early-access interpretation remain unresolved. Date-level eligibility also leaves a same-day release-hour ambiguity.

The pilot was selected using snapshot information and unequal inclusion probabilities, introducing selection bias. Some catalog entries may be software or other non-game products. Repeated games create dependence across observations, and correlated predictors complicate individual coefficient interpretation. One validation year with only 100 observations provides limited evidence about calibration or performance beyond this sample.

## Reproducibility

Run commands from the repository root. Baseline experiments were verified with Python **3.9.6**, NumPy **2.0.2**, pandas **2.3.3**, scikit-learn **1.6.1**, SciPy **1.13.1**, matplotlib **3.9.4** and joblib **1.5.3**. [requirements-baseline.txt](requirements-baseline.txt) specifies the tested modeling and plotting versions and includes the source-processing requirements from [requirements.txt](requirements.txt). The historical scripts also use Python's standard library and the system IANA timezone database.

### Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements-baseline.txt
```

Dependency installation requires package access. Once dependencies and the existing local inputs are available, baseline execution is offline and requires no API credential.

### Reproduce the baseline experiments

```bash
python3 -B src/08_train_baseline_models.py --verify
```

This command runs the full offline test suite, compares two complete experiments in isolated output directories, checks protected-input hashes and saves the verified baseline outputs. It does not regenerate earlier datasets or refresh price histories. Verification blocks socket and DNS access.

For the baseline tests alone:

```bash
python3 -B -m unittest discover -s tests -p 'test_baseline_models.py'
```

The saved [validation receipt](reports/autumn_sale_baseline_validation.json) records **171 passing offline tests**, including 35 baseline tests. It verifies identical predictions, metrics, fitted parameters, plotted data, PNG bytes and model bytes across repeated runs in the recorded environment, plus unchanged hashes for **166 protected earlier files**. Cross-platform numerical or image-byte identity and cross-version joblib compatibility are not guaranteed. Load only trusted local joblib artifacts.

<details>
<summary>Earlier data preparation and evidence workflows</summary>

With the original `games.csv` available, the supported source-processing entry points are:

```bash
python3 src/00_inspect_source.py
python3 src/01_build_games_master.py
python3 src/02_create_pilot.py
```

The inspection prints diagnostics; master and pilot scripts regenerate intermediate datasets and reports. Use a separate working copy when rebuilding stages whose outputs are protected by later experiments.

Historical collection requires `ITAD_API_KEY` in the process environment. The collector does not read the local `apikey` file or automatically load `.env`. Its smoke and full collection commands are:

```bash
python3 src/03_fetch_itad.py --limit 3
python3 src/03_fetch_itad.py
```

The full run requires a valid three-game smoke receipt. These commands can make pricing API requests and are unnecessary for reproducing the cached experiments. The collector's `--validate-cache` mode makes no API calls but rewrites collection artifacts; it is not a read-only check of the frozen inputs.

The cached evidence, coverage, reviewed verification ledger, labels and features have these supported offline entry points:

```bash
python3 src/04_audit_autumn_evidence.py
python3 src/05_investigate_sale_coverage.py --verify
python3 -B src/06_verify_historical_ground_truth.py --verify
python3 -B src/06_build_operational_labels.py --verify
python3 -B src/07_build_autumn_features.py --verify
```

These workflows regenerate their own outputs. The ground-truth verification script uses the reviewed local research ledger rather than repeating external research. Detailed input requirements and validation records are retained in their corresponding reports.

The complete test suite can also be run independently:

```bash
python3 -m unittest discover -s tests -v
```

</details>

## Repository structure

```text
.
├── data/raw/itad/          # Cached historical price responses and provenance
├── data/intermediate/     # Catalog, pilot, evidence, labels and historical features
├── data/processed/        # 2025 baseline validation predictions
├── models/                # Fitted Bernoulli estimator and logistic pipeline
├── reports/               # Research reports, manifests and validation receipts
│   ├── figures/           # Static model and evaluation figures
│   ├── sources/           # Reviewed source notes and official calendar artwork
│   └── baselines/         # Preserved earlier evidence-audit convention
├── src/                   # Data workflows, modeling and reusable plotting style
├── tests/                 # Offline unit, integration and adversarial tests
├── requirements.txt
├── requirements-baseline.txt
├── PROJECT_CONTEXT.md
└── PROJECT_STATUS.md
```

The main modeling artifacts are:

| Artifact | Path |
|---|---|
| Operational targets and provenance | `data/intermediate/autumn_sale_operational_labels.csv` |
| Predictor-only table | `data/intermediate/autumn_sale_features.csv` |
| Modeling table | `data/intermediate/autumn_sale_modeling_table.csv` |
| Approved feature definitions | `reports/autumn_sale_feature_manifest.json` |
| Validation predictions: 100 games × two models | `data/processed/autumn_sale_2025_baseline_predictions.csv` |
| Fitted constant-prior estimator | `models/bernoulli_baseline.joblib` |
| Complete fitted logistic pipeline | `models/logistic_regression.joblib` |
| Model configuration, preprocessing and versions | `reports/autumn_sale_baseline_model_manifest.json` |
| Underlying plotted values | `reports/autumn_sale_baseline_plot_data.json` |

Operational labels and the separate positive/unlabeled view are target/provenance artifacts, not predictor tables. No PU-learning algorithm is implemented. [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) records methodological decisions; [PROJECT_STATUS.md](PROJECT_STATUS.md) retains the implementation history.

## Planned work

The Bernoulli and logistic regression baselines are completed initial experiments. Random forest and XGBoost comparisons, dataset scaling and broader validation are planned work; **Phase 7B has not started**. Future model selection should use training-only temporal resampling because the 2025 holdout has already been inspected. The longer-term design includes a separate retrospective 2026 evaluation; no 2026 predictions or outcomes are used in the current experiments.

## Sources and licensing

Historical pricing is attributed to IsThereAnyDeal; official sale-calendar references are attributed to Valve in the evidence report. Further source and access details are documented in the [collection report](reports/itad_collection_report.md), [coverage investigation](reports/autumn_sale_coverage_investigation.md), [ground-truth feasibility report](reports/autumn_sale_ground_truth_feasibility.md) and [feature availability report](reports/autumn_sale_feature_availability.md). The repository does not currently include a license file; external data remains subject to its source terms.
