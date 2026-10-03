# Steam Seasonal Sale Prediction

A data science project investigating whether characteristics of a Steam game can help predict its participation in a major Steam seasonal sale.

The project focuses on building an interpretable **logistic regression model** that estimates the probability that a game will be discounted during a specific **Steam Autumn Sale**.

## Research Question

> Given information available about a Steam game before a Steam Autumn Sale begins, what is the probability that the game will be discounted during that sale?

Rather than attempting to predict whether a game will "ever go on sale," the project focuses on specific historical sale events. This allows sale participation to be defined using real historical price observations.

## Project Approach

The project combines two types of data.

**Steam game metadata** provides information about each game that may help explain discounting behavior. The primary source is `games.csv`, which contains attributes such as release information, pricing, publishers, genres, engagement indicators, and other game characteristics.

**Historical price data** will be collected separately using the IsThereAnyDeal (ITAD) API. Steam-specific price histories will be used to determine whether each game actually participated in historical Autumn Sale events.

These sources are eventually combined into a modeling dataset where:

> **One observation = one Steam game × one Autumn Sale year**

For example:

| Game | Sale Year | Age at Sale | Price | DLC Count | Publisher Size | Discounted |
|---|---:|---:|---:|---:|---:|---:|
| Game A | 2023 | 820 days | $29.99 | 2 | 6 | 1 |
| Game A | 2024 | 1,186 days | $29.99 | 2 | 6 | 0 |
| Game B | 2023 | 310 days | $59.99 | 0 | 24 | 1 |

This structure allows the same game to appear in multiple historical sale events while accounting for characteristics that change over time, such as the game's age.

## Why Logistic Regression?

The primary outcome is binary:

- `1` — the game was discounted during the specified Autumn Sale
- `0` — the game was not discounted

Logistic regression is therefore a natural starting point.

It also provides interpretable coefficients, making it possible to investigate how characteristics such as game age, price, popularity, publisher portfolio size, DLC count, and genre are associated with the probability of participating in a seasonal sale.

The objective is not only predictive performance, but also understanding which observable characteristics are associated with Steam discounting behavior.

## Data Quality and Historical Coverage

Historical price data requires careful treatment.

Price-history services may not observe every Steam price change consistently. Therefore, the absence of a recorded discount cannot automatically be interpreted as evidence that no discount occurred.

The project distinguishes between:

- **Discounted**
- **Not discounted**
- **Unknown due to insufficient historical coverage**

Observations with insufficient evidence will not be silently classified as non-discounted.

This coverage validation is an important part of constructing the final ground-truth dataset.

## Data Leakage

Because the project predicts historical sale participation, predictors should represent information that was available **before the sale being predicted**.

Variables that may contain information accumulated after a historical sale — such as current lifetime review counts or other present-day engagement statistics — must therefore be evaluated carefully before being included in the final model.

Preventing temporal data leakage is a core methodological requirement of the project.

## Project Pipeline

The project is being developed incrementally:

```text
Steam metadata
      │
      ▼
1. Inspect & validate source data
      │
      ▼
2. Build clean games master table
      │
      ▼
3. Create small pilot sample
      │
      ▼
4. Collect historical ITAD price data
      │
      ▼
5. Validate coverage & generate sale labels
      │
      ▼
6. Engineer features & build modeling dataset
      │
      ▼
7. Train & evaluate logistic regression
      │
      ▼
8. Scale dataset & perform final validation
```

A small pilot dataset will be used to validate the complete pipeline before historical price collection is scaled to thousands of games.

## Planned Project Structure

```text
steam-games/
│
├── data/
│   ├── raw/             # Raw collected data
│   ├── intermediate/    # Cleaned/intermediate datasets
│   └── processed/       # Final modeling datasets
│
├── src/                 # Reproducible Python pipeline
├── reports/             # Data-quality and analysis reports
├── notebooks/           # Exploratory analysis
│
├── games.csv            # Original Steam metadata
├── games.json           # Additional source data
├── PROJECT_CONTEXT.md   # Persistent methodological decisions
├── PROJECT_STATUS.md    # Current development progress
├── requirements.txt
└── README.md
```

The original source datasets are preserved and are not modified directly by the processing pipeline.

## Development Phases

### Phase 1 — Source Data Inspection
Validate the structure and quality of `games.csv`, investigate missing values and malformed fields, and document the available variables.

### Phase 2 — Game Master Dataset
Clean the source metadata and establish the population of eligible Steam games.

### Phase 3 — Pilot Dataset
Select a small and diverse sample of games for end-to-end pipeline testing.

### Phase 4 — Historical Price Collection
Retrieve and cache Steam-specific historical price information using ITAD.

### Phase 5 — Ground-Truth Labels
Determine historical Autumn Sale participation while enforcing explicit price-history coverage requirements.

### Phase 6 — Feature Engineering
Construct one observation per game and sale year while preventing temporal leakage.

### Phase 7 — Modeling
Train logistic regression models and compare their performance against simple baseline strategies.

### Phase 8 — Scaling & Validation
Run the validated pipeline on a larger game population and perform final model evaluation and sanity checks.

## Current Status

🚧 **In development**

The project is currently focused on validating and understanding the source Steam metadata before constructing the modeling dataset.

See `PROJECT_STATUS.md` for the current implementation status and `PROJECT_CONTEXT.md` for persistent methodological decisions.

## Technologies

- Python
- pandas
- NumPy
- scikit-learn
- IsThereAnyDeal API
- Jupyter
- Git

Additional dependencies will be introduced only when required by later stages of the project.

## Goal

The final result will be a reproducible data pipeline and interpretable statistical model for studying the relationship between Steam game characteristics and participation in seasonal discount events.

Particular emphasis is placed on **data quality, historical validity, reproducibility, and interpretability**, rather than treating model accuracy as the sole measure of success.