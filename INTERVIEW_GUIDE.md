# Orbital — Technical Interview & Demo Guide

## 1. Elevator Pitch

Orbital is a **causal intelligence platform for e-commerce revenue attribution**. It uses econometric modeling — OLS/Ridge regression with automated diagnostics — to answer: **"Which ad channels actually drive incremental revenue, and by how much?"**

Unlike black-box ML or last-click attribution, Orbital produces interpretable coefficients with direct economic meaning: "Every $1 spent on Meta generates $2.30 of incremental revenue." This enables data-driven budget allocation across Meta, Google, and TikTok.

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     NEXT.JS 16 FRONTEND                      │
│               (React 19, TypeScript, Tailwind)               │
│                                                              │
│  Landing (Three.js 3D)  │  Build Wizard  │  Dashboard        │
│  CSV Upload Parsers     │  SSE Stream UI │  Forecast UI       │
│  AI Chat Assistant      │  Scenario Builder                   │
└──────────────┬──────────────────────────┬────────────────────┘
               │ REST / SSE               │ Direct DB (uploads)
               ▼                          ▼
┌──────────────────────────┐    ┌──────────────────────────────┐
│    FASTAPI BACKEND       │    │     SUPABASE (PostgreSQL)    │
│    (Python 3.11)         │    │                              │
│                          │    │  project_timeseries          │
│  /v1/projects/{id}/      │    │  project_spend               │
│    run/stream (SSE)      │◄──►│  project_events              │
│    forecast              │    │  models                      │
│    scenarios CRUD        │    │  model_versions              │
│                          │    │  model_coefficients          │
│  14-step pipeline in     │    │  model_diagnostics           │
│  backend/pipeline/       │    │  model_anomalies             │
│                          │    │  forecast_scenarios          │
└──────────────────────────┘    │                              │
                                │  Row-Level Security (RLS)    │
                                │  Auth via Supabase Auth      │
                                └──────────────────────────────┘
```

### Component Breakdown

| Component | Tech | Role |
|-----------|------|------|
| **Frontend** | Next.js 16, React 19, TypeScript, Tailwind, Three.js, Recharts | Auth, CSV upload/parsing, pipeline streaming UI, forecast scenarios, AI chat |
| **Backend** | FastAPI, Python 3.11, Pandas, Statsmodels, Scikit-learn | 14-step modeling pipeline, forecasting engine, SSE streaming |
| **Database** | Supabase (PostgreSQL) | Raw data storage, model artifact registry, multi-tenant isolation via RLS |

---

## 3. The ML Pipeline — 14 Steps, 5 Phases

### Phase 1: Data Ingestion & Validation

| Step | Module | What It Does |
|------|--------|-------------|
| 1 | `pipeline/fetch.py` | Loads timeseries (revenue/orders), spend (by channel/date), and events from Supabase |
| 2 | `pipeline/validate.py` | Hard gates: minimum 60 days, continuous date index, revenue variance, drops zero-variance spend channels |
| 2.75 | `pipeline/aggregate.py` | Daily to weekly aggregation (Monday-start), applies event dummies (step = permanent shift, pulse = one-time) |

**Why weekly?** Daily e-commerce data is too noisy for regression. Weekly aggregation smooths noise while preserving enough observations for statistical power.

### Phase 2: Diagnosis & Feature Engineering

| Step | Module | What It Does |
|------|--------|-------------|
| 2.5 | `pipeline/diagnostics.py` | Seasonality detection (periodogram, ACF, AIC sweep), data quality scoring, model mode selection |
| — | `pipeline/adstock.py` | Per-channel adstock alpha selection (0.0–0.9) via TimeSeriesSplit cross-validation |
| 3 | `pipeline/matrix.py` | Builds design matrix X: constant, centered trend, Fourier seasonal terms, adstocked spend, event dummies |

**Model Modes** (data-adaptive complexity):
- `causal_full` — enough data for full causal attribution with adstock
- `causal_cautious` — limited data, conservative feature engineering with adstock
- `diagnostic_stabilized` — weak data, no adstock, stability over accuracy

### Phase 3: Model Fitting & Diagnostics

All in `pipeline/modeling.py` (655 lines):

| Step | Function | What It Does |
|------|----------|-------------|
| 4 | `fit_ols()` | Base OLS regression |
| 5 | `check_vif()` | If max VIF > 10 (collinearity), switch to Ridge with stability-based alpha |
| 6 | `check_autocorrelation()` | Ljung-Box test; if significant, add lag_1/lag_2; apply HAC if still significant |
| 7 | `check_nonlinearity()` | 3-way race: Base vs Linear-Log vs Log-Log, evaluated in dollar space via Duan's smearing |
| 8 | `check_heteroskedasticity()` | Breusch-Pagan test; if p < 0.05, apply HAC covariance |
| 9 | `run_model()` | Orchestrates steps 4–8 sequentially |

### Phase 4: Post-Fit Analysis

| Step | Module | What It Does |
|------|--------|-------------|
| 10 | `pipeline/counterfactual.py` | Zeros each channel, re-predicts. Incremental = actual minus counterfactual. Computes marginal ROI per channel |
| 11 | `pipeline/anomalies.py` | Residual z-score detection (threshold 2.5 sigma). Flags dates with unusual patterns |
| 12 | `pipeline/confidence.py` | Rule-based scoring across 7 dimensions. Output: high / medium / low |
| 13 | `pipeline/persist.py` | Saves model version, coefficients, diagnostics, OOS metrics to Supabase (immutable) |

### Phase 5: Forecasting

| Module | What It Does |
|--------|-------------|
| `pipeline/forecast.py` | Version-driven (loads persisted model from DB, no in-memory state). Scenario simulation with per-channel spend multipliers. Handles lag recursion for multi-week horizons |

---

## 4. Key Algorithms — What They Are and Why

### Geometric Adstock
```
A_t = Spend_t + alpha * A_{t-1}
```
- **What:** Captures media carryover — ad effects don't stop when spending stops
- **Why:** A Meta campaign seen today still influences purchases next week
- **How alpha is selected:** Per-channel via TimeSeriesSplit cross-validation (respects temporal order, not random split)
- **Range:** 0.0 (no carryover) to 0.9 (strong persistence)
- **Code:** `pipeline/adstock.py`

### OLS to Ridge Fallback
- **What:** Starts with OLS. If VIF > 10 (multicollinearity between channels), switches to Ridge (L2 regularization)
- **Why:** When Meta and Google spend are correlated, OLS coefficients become unstable. Ridge stabilizes them
- **Alpha selection:** Stability-based — finds lowest alpha that keeps spend coefficients positive and minimizes coefficient volatility
- **Code:** `pipeline/modeling.py:check_vif()`

### Fourier Seasonality
- **What:** Models seasonal patterns as smooth continuous waves using sin/cos pairs
- **Why:** Month dummies (12 binary columns) assume sharp jumps between months. Fourier terms are smoother, more realistic, and use fewer degrees of freedom
- **Selection process:** Periodogram detects dominant period, ACF confirms statistical significance, AIC sweep selects k harmonics (0, 1, or 2)
- **Code:** `pipeline/diagnostics.py` (detection), `pipeline/matrix.py:build_fourier_features()` (generation)

### Counterfactual Attribution
- **What:** For each channel, zero out its contribution and re-predict. Incremental = actual minus counterfactual
- **Why:** This is the core causal claim — isolates each channel's true incremental impact
- **Output:** Incremental revenue per channel, marginal ROI (incremental / total spend)
- **Code:** `pipeline/counterfactual.py`

### Nonlinearity Race
- **What:** 3-way comparison: Base (linear-linear) vs Linear-Log (log spend) vs Log-Log (log both)
- **Why:** Media spend often has diminishing returns — the first $1000 on Meta drives more revenue than the next $1000. Log transforms capture this curvature
- **Evaluation:** All candidates compared in dollar space (not log space) using Duan's smearing estimator for fair comparison
- **Code:** `pipeline/modeling.py:check_nonlinearity()`

### Out-of-Sample Backtesting
- **What:** 80/20 time-based split. Train on first 80%, evaluate R-squared, RMSE, MAE on held-out 20%
- **Why:** In-sample R-squared can be misleading (overfitting). OOS metrics show true generalization ability
- **Code:** `pipeline/stream.py` (lines 230–300)

### Confidence Scoring
- **What:** Deterministic, rule-based scoring that starts at "high" and downgrades based on 7 checks
- **Checks:** adjusted R-squared, data volume, VIF, Durbin-Watson, Ljung-Box/Breusch-Pagan p-values, negative spend coefficients, OOS R-squared
- **Why:** Users need to know how much to trust the results — no silent failures
- **Code:** `pipeline/confidence.py`

---

## 5. MLOps Best Practices

### Immutable Model Versioning
Every pipeline run creates a new `model_version` row with a UUID. Versions are never overwritten. Each stores: model type, Ridge/lag/log flags, R-squared, adjusted R-squared, confidence level, full model config (JSON), feature state (JSONB), config hash, and OOS metrics.

**Why it matters:** Full model lineage. Any historical model can be audited, compared, or rolled back.

### Feature State Serialization (Reproducibility)
`feature_state` captures everything needed to reproduce predictions: `trend_mean` (normalization constant), `adstock_last` (per-channel carryover state), `lag_history` (for lag recursion), `channel_alphas` (decay rates), `seasonality_k` and `seasonality_period`.

**Why it matters:** Forecasting is version-driven — loads from DB, not in-memory state. Survives restarts, multi-worker setups, and deploys.

### Separation of Training and Serving
- **Training path:** `stream.py` calls `run_model()` then `persist_results()` (writes to DB)
- **Serving path:** `forecast.py` calls `load_latest_model_version()` then `predict_revenue()` (reads from DB)
- No shared in-memory state between the two paths

### Self-Correcting Pipeline
The pipeline doesn't just fit a model — it diagnoses and adapts:
- VIF > 10 triggers automatic switch from OLS to Ridge
- Significant autocorrelation triggers lag features then HAC covariance
- Significant heteroskedasticity triggers HAC standard errors
- Data quality score selects model complexity mode
- Every decision is logged and persisted in `diagnostics_snapshot` and `gating_reasons`

### Data Validation Gate
Hard gates before modeling: minimum 60 days, continuous date index, revenue must have variance, zero-variance spend channels are dropped, spend coverage gaps are warned.

### Config Hashing
Pipeline hashes the full model config (`config_hash`) for deduplication — detects whether a re-run would produce a materially different model.

### Real-Time Observability (SSE Streaming)
`stream.py` yields structured SSE events at every step with `reasoning` (explains what's happening and why), `status` (pass/warn/fail), and `metrics`. Full transparency into model decisions.

### Anomaly Detection on Residuals
Post-fit residual monitoring — flags dates where z-score exceeds 2.5 sigma. Persisted per model version. Signals external events the model didn't capture.

### Coefficient Persistence with Statistical Metadata
Every coefficient is stored with: feature name, coefficient value, p-value, standard error. Plus correlation matrix, VIF, Ljung-Box p, Breusch-Pagan p, Durbin-Watson statistic, residual std.

---

## 6. Data Flow: End to End

```
User uploads CSV files (Shopify orders, Meta/Google/TikTok spend, events)
    |
    v
Next.js API parses, validates, aggregates by date, upserts to Supabase
    |
    v
User clicks "Run Model" -> Next.js calls FastAPI /v1/projects/{id}/run/stream
    |
    v
[FETCH] Load from Supabase tables
    |
    v
[VALIDATE] Check data integrity (60+ days, continuous dates, variance)
    |
    v
[AGGREGATE] Daily -> Weekly (Monday-based), apply event dummies
    |
    v
[DIAGNOSTICS] Detect seasonality, score data quality, select model mode
    |
    v
[ADSTOCK] Optimize per-channel alpha via TimeSeriesSplit CV
    |
    v
[MATRIX] Build X: const + trend + Fourier + adstocked spend + events
    |
    v
[MODEL] OLS -> Ridge(if VIF>10) -> Lags(if autocorr) -> Log race -> HAC(if hetero)
    |
    v
[BACKTEST] 80/20 time split, evaluate OOS R-squared, RMSE, MAE
    |
    v
[COUNTERFACTUAL] Zero each channel, compute incremental revenue and ROI
    |
    v
[ANOMALIES] Flag residual outliers (z > 2.5 sigma)
    |
    v
[CONFIDENCE] Score model reliability: high / medium / low
    |
    v
[PERSIST] Save model version, coefficients, diagnostics to Supabase
    |
    v
User sees: model quality, channel impact, ROI, anomalies, confidence level
    |
    v
User builds forecast scenarios with spend multipliers per channel
```

---

## 7. Database Schema

| Table | Purpose |
|-------|---------|
| `projects` | Project metadata (user_id, name, Shopify domain) |
| `project_timeseries` | Daily revenue and orders (upserted on upload) |
| `project_spend` | Daily ad spend by channel (Meta, Google, TikTok) |
| `project_events` | Promotions, launches, algorithm changes (step or pulse type) |
| `models` | Model metadata (one per project) |
| `model_versions` | Immutable model snapshots (config, feature state, metrics, OOS) |
| `model_coefficients` | Per-feature coefficients with p-values and std errors |
| `model_diagnostics` | VIF, Ljung-Box, Breusch-Pagan, DW, correlation matrix |
| `model_anomalies` | Residual outliers per model version |
| `forecast_scenarios` | Saved forecast scenarios (spend multipliers, weeks) |

Row-Level Security (RLS) enforces multi-tenant isolation — users only see their own projects.

---

## 8. Test Suite

**118 tests across 14 test files** in `backend/tests/`:

| File | What It Tests |
|------|--------------|
| `test_modeling.py` | OLS, Ridge, VIF switching, autocorrelation handling, nonlinearity race, heteroskedasticity |
| `test_diagnostics.py` | Seasonality detection, data quality scoring, model mode selection |
| `test_adstock.py` | Alpha selection, TimeSeriesSplit CV, sweep logic, determinism |
| `test_forecast.py` | Version loading, X matrix building, prediction, lag recursion, log target inverse |
| `test_matrix.py` | Design matrix construction, Fourier features, adstock/log transforms, feature state reuse |
| `test_counterfactual.py` | Incremental revenue, marginal ROI, log target handling |
| `test_confidence.py` | Scoring rules, downgrade logic, OOS integration |
| `test_anomalies.py` | Z-score detection, direction, edge cases |
| `test_validate.py` | Data integrity, continuous index, variance checks, edge cases |
| `test_aggregate.py` | Weekly aggregation, event dummies, partial week removal |
| `test_persist.py` | Model persistence, numpy type coercion, serialization |
| `test_fetch.py` | Supabase data loading, error handling |
| `test_autocorrelation_sanity.py` | Lag logic, index preservation, HAC flag propagation |

### Commands
```bash
cd backend

# All tests
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=pipeline --cov-report=term-missing

# Single file
pytest tests/test_modeling.py -v

# Single test
pytest tests/test_modeling.py::test_fit_ols_returns_model_result -v

# Only pure unit tests (no DB)
pytest tests/ -v -m pure
```

---

## 9. Key Files Quick Reference

| File | Lines | Role |
|------|-------|------|
| `backend/pipeline/modeling.py` | 655 | Core regression logic (OLS, Ridge, VIF, autocorr, nonlinearity, hetero) |
| `backend/pipeline/stream.py` | 900+ | SSE streaming orchestrator — runs full pipeline with real-time events |
| `backend/pipeline/diagnostics.py` | 300+ | Data quality scoring, seasonality detection, model mode selection |
| `backend/pipeline/forecast.py` | 459 | Version-driven forecasting, scenario simulation, lag recursion |
| `backend/pipeline/matrix.py` | 240 | Design matrix construction, adstock, Fourier features |
| `backend/pipeline/adstock.py` | 149 | Per-channel adstock alpha optimization via TimeSeriesSplit CV |
| `backend/pipeline/counterfactual.py` | 80 | Channel-by-channel incremental revenue estimation |
| `backend/pipeline/confidence.py` | 81 | Rule-based confidence scoring (7 dimensions) |
| `backend/pipeline/persist.py` | 189 | Model artifact persistence to Supabase |
| `backend/pipeline/validate.py` | 112 | Data integrity gates |
| `backend/pipeline/aggregate.py` | 96 | Daily-to-weekly aggregation with event handling |
| `backend/routers/models.py` | 672 | FastAPI endpoint handlers |
| `backend/main.py` | 22 | FastAPI app with CORS |
| `app/dashboard/build/run/page.tsx` | 300+ | Pipeline runner UI with SSE streaming |
| `supabase_schema.sql` | 140 | Database migrations |

---

## 10. Interview Q&A

### "Why econometric ML instead of deep learning / XGBoost?"
The goal is **causal attribution**, not prediction. A Ridge coefficient of 2.3 on `meta_spend` means "$2.30 of incremental revenue per dollar spent." You can't get that from XGBoost feature importance — those measure predictive contribution, not causal effect. The counterfactual analysis (zeroing out a channel and re-predicting) only works when coefficients have causal meaning.

### "Why not just use last-click or multi-touch attribution?"
Last-click gives 100% credit to the final touchpoint. Multi-touch distributes credit by arbitrary rules (linear, time-decay). Neither measures **incrementality** — what would have happened if you didn't spend at all? Orbital's counterfactual approach answers that directly.

### "How do you handle multicollinearity?"
VIF check (step 5). If any channel's VIF exceeds 10, the pipeline automatically switches from OLS to Ridge regression. Ridge alpha is selected via a stability-based search that enforces positive spend coefficients and minimizes coefficient volatility. The comparison table (`compare_alpha_objectives`) shows the trade-off between prediction accuracy and attribution stability.

### "How do you prevent overfitting?"
Four mechanisms: (1) Model mode selection reduces complexity for small datasets, (2) Ridge regularization when triggered, (3) Out-of-sample backtesting with 80/20 time split catches overfit models, (4) Confidence scoring downgrades models with poor OOS R-squared.

### "How do you handle seasonality?"
Three-step gating process: (1) Periodogram finds the candidate period, (2) ACF confirms it's statistically significant, (3) AIC sweep selects how many Fourier harmonics (0, 1, or 2) to include. This prevents adding seasonal features when the data doesn't justify them.

### "What happens when data quality is poor?"
The diagnostics module scores data quality and selects one of three model modes. With weak data, it uses `diagnostic_stabilized` mode — no adstock, no log transforms, minimal features. The confidence scoring system then honestly reports "low" confidence so users know not to make major budget decisions based on the results.

### "How does forecasting work?"
Forecasting is completely decoupled from training. `load_latest_model_version()` reads the persisted model from Supabase — coefficients, feature state, config. `build_X_for_prediction()` constructs the design matrix for future weeks using the same transforms (adstock carryover, Fourier terms, trend normalization). `predict_revenue()` computes `y = X @ beta` with lag recursion if needed. This is version-driven and stateless — survives restarts and multi-worker deployments.

### "What's your testing strategy?"
118 tests covering every pipeline module. Tests use synthetic data with known effects so we can verify exact outputs. Pure unit tests (marked `@pytest.mark.pure`) run without any DB calls. Integration tests verify the full pipeline flow. Coverage is tracked per module.

### "What would you improve next?"
- Bayesian regression for uncertainty quantification on coefficients
- Geo-based experiments for ground-truth calibration of model estimates
- Background job queue (Celery/Redis) for large pipelines
- API authentication middleware on FastAPI routes
- Budget optimizer that uses marginal ROI curves to recommend optimal allocation

---

## 11. Demo Flow (Suggested Order)

1. **Landing page** — Show the 3D orbital visualization, explain the product positioning
2. **Create a project** — Walk through auth and project setup
3. **Upload data** — Show CSV upload for orders (Shopify export), ad spend (Meta/Google), and events
4. **Run the pipeline** — Click "Run Model" and narrate the SSE stream as each step appears:
   - "It's validating data integrity..."
   - "Aggregating to weekly frequency..."
   - "Detecting seasonality — it found a 52-week cycle with 1 harmonic..."
   - "Selecting adstock decay per channel — Meta has 0.6 alpha (strong carryover)..."
   - "Fitting OLS, checking VIF — no collinearity issues..."
   - "Running the nonlinearity race — base model won..."
   - "Backtesting: OOS R-squared is 0.72..."
   - "Confidence: high"
5. **Show results** — Channel impact (incremental revenue), marginal ROI, anomalies flagged
6. **Forecast scenarios** — "What if we increase Meta spend by 20% and cut Google by 10%?"
7. **Technical deep-dive** — Open the codebase, walk through `modeling.py`, explain the self-correcting pipeline
