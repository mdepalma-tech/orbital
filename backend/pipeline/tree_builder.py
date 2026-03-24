"""Builds and caches the pipeline tree with AST-enriched metadata."""

from __future__ import annotations

import ast
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from pipeline.tree_schema import PipelineNode, PipelineTree

PIPELINE_DIR = Path(__file__).parent
CACHE_PATH = PIPELINE_DIR / ".tree_cache.json"


# ── Source hashing ───────────────────────────────────────────────────────────


def compute_source_hash(pipeline_dir: Optional[Path] = None) -> str:
    d = pipeline_dir or PIPELINE_DIR
    hasher = hashlib.sha256()
    for f in sorted(d.glob("*.py")):
        hasher.update(f.read_bytes())
    return hasher.hexdigest()


# ── AST enrichment ───────────────────────────────────────────────────────────


def _extract_function_info(source_path: Path, function_name: str) -> dict:
    if not source_path.exists():
        return {}
    source = source_path.read_text()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == function_name:
                lines = source.splitlines()
                sig_start = node.lineno - 1
                sig_end = sig_start
                paren_depth = 0
                for i in range(sig_start, min(sig_start + 20, len(lines))):
                    paren_depth += lines[i].count("(") - lines[i].count(")")
                    if paren_depth <= 0 and ":" in lines[i]:
                        sig_end = i
                        break
                full_sig = "\n".join(lines[sig_start : sig_end + 1]).strip()
                docstring = ast.get_docstring(node)
                return {
                    "function_signature": full_sig,
                    "line_number": node.lineno,
                    "docstring": (
                        docstring.split("\n")[0].strip() if docstring else None
                    ),
                }
    return {}


def _enrich_node(node: PipelineNode, pipeline_dir: Path) -> None:
    if node.function_name.startswith("("):
        return
    source_path = pipeline_dir / node.module_path.replace("pipeline/", "")
    info = _extract_function_info(source_path, node.function_name)
    if info:
        node.function_signature = info.get("function_signature")
        node.line_number = info.get("line_number")
        node.docstring = info.get("docstring")
    for child in node.children:
        _enrich_node(child, pipeline_dir)


# ── Pipeline definition ─────────────────────────────────────────────────────


def _define_modeling_steps() -> List[PipelineNode]:
    return [
        PipelineNode(
            step_id="fetch",
            step_number="1",
            name="Fetch Project Data",
            description="Queries Supabase for project timeseries, spend, and events data",
            module_path="pipeline/fetch.py",
            function_name="fetch_project_data",
            inputs=["project_id (str UUID)"],
            outputs=["timeseries_df (ts, revenue, orders)", "spend_df (ts, meta_spend, google_spend, tiktok_spend)", "events_df (event_name, event_type, start_ts, end_ts)"],
            parameters={"tables": ["projects", "project_timeseries", "project_spend", "project_events"]},
        ),
        PipelineNode(
            step_id="validate",
            step_number="2",
            name="Validate & Prepare",
            description="Normalizes timestamps, fills missing dates with 0, checks data integrity, removes zero-variance spend columns",
            module_path="pipeline/validate.py",
            function_name="validate_and_prepare",
            inputs=["timeseries_df", "spend_df", "events_df"],
            outputs=["daily_df (continuous date index)", "events_clean", "spend_cols (list[str])"],
            parameters={"min_observations": 60, "EPSILON": 1e-6, "SPEND_COLUMNS": ["meta_spend", "google_spend", "tiktok_spend"]},
        ),
        PipelineNode(
            step_id="aggregate",
            step_number="3",
            name="Apply Events & Aggregate to Weekly",
            description="Creates binary event dummy columns at daily level, then aggregates to weekly (W-MON) frequency",
            module_path="pipeline/aggregate.py",
            function_name="apply_event_dummies",
            inputs=["daily_df", "events_clean", "spend_cols"],
            outputs=["df_weekly (week_start, revenue, orders, spend, event flags, week_index)"],
            parameters={"freq": "W-MON", "partial_week": "dropped if < 7 days"},
            children=[
                PipelineNode(
                    step_id="event_dummies",
                    step_number="3a",
                    name="Apply Event Dummies",
                    description="For each event: 'step' type = 1 from start_ts onward, 'pulse' type = 1 between start_ts and end_ts",
                    module_path="pipeline/aggregate.py",
                    function_name="apply_event_dummies",
                    inputs=["daily_df", "events"],
                    outputs=["daily_df with event_* columns"],
                ),
                PipelineNode(
                    step_id="weekly_agg",
                    step_number="3b",
                    name="Aggregate to Weekly",
                    description="Revenue/orders/spend: SUM. Event flags: MAX. Adds week_index column",
                    module_path="pipeline/aggregate.py",
                    function_name="aggregate_to_weekly",
                    inputs=["daily_df", "spend_cols"],
                    outputs=["df_weekly"],
                ),
            ],
        ),
        PipelineNode(
            step_id="backtest",
            step_number="4",
            name="Out-of-Sample Backtest",
            description="80/20 time-based split; trains model on first 80%, evaluates on held-out 20%",
            module_path="pipeline/stream.py",
            function_name="(inline: backtest block)",
            inputs=["df_weekly", "spend_cols"],
            outputs=["oos_metrics (oos_r2, oos_rmse, oos_mae, oos_n_obs)"],
            parameters={"split_ratio": 0.8, "min_oos_for_metrics": 8},
            children=[
                PipelineNode(
                    step_id="backtest_diag",
                    step_number="4a",
                    name="Run Diagnostics on Training Fold",
                    description="Scores data quality on 80% training set to select model_mode",
                    module_path="pipeline/diagnostics.py",
                    function_name="run_diagnostics",
                    inputs=["train_weekly", "spend_cols"],
                    outputs=["train_diagnostics"],
                ),
                PipelineNode(
                    step_id="backtest_matrix",
                    step_number="4b",
                    name="Build Training Design Matrix",
                    description="Builds X, y with adstock/log/trend transforms on training fold",
                    module_path="pipeline/matrix.py",
                    function_name="build_design_matrix",
                    inputs=["train_weekly", "spend_cols", "train_model_mode"],
                    outputs=["X_train", "y_train", "feature_state"],
                ),
                PipelineNode(
                    step_id="backtest_model",
                    step_number="4c",
                    name="Run Model on Training Fold",
                    description="Fits OLS + diagnostic checks (VIF, autocorrelation, etc.) on training data",
                    module_path="pipeline/modeling.py",
                    function_name="run_model",
                    inputs=["X_train", "y_train", "spend_cols"],
                    outputs=["train_result (ModelResult)"],
                ),
                PipelineNode(
                    step_id="backtest_test_matrix",
                    step_number="4d",
                    name="Build Test Design Matrix",
                    description="Builds X_test using training feature_state for consistent transforms",
                    module_path="pipeline/matrix.py",
                    function_name="build_design_matrix",
                    inputs=["test_weekly", "spend_cols", "feature_state"],
                    outputs=["X_test", "y_test"],
                ),
                PipelineNode(
                    step_id="backtest_eval",
                    step_number="4e",
                    name="Compute OOS Metrics",
                    description="Predicts on test set, computes R2, RMSE, MAE (if n_oos >= 8)",
                    module_path="pipeline/stream.py",
                    function_name="(inline: OOS metrics)",
                    inputs=["train_result", "X_test", "y_test"],
                    outputs=["oos_r2", "oos_rmse", "oos_mae"],
                    branch_condition="n_oos >= 8 for metric computation, else oos_metrics = {}",
                ),
            ],
        ),
        PipelineNode(
            step_id="diagnostics",
            step_number="5",
            name="Data Diagnostics",
            description="Scores data quality (0-100) to select modeling mode: causal_full, causal_cautious, or diagnostic_stabilized",
            module_path="pipeline/diagnostics.py",
            function_name="run_diagnostics",
            inputs=["df_weekly", "spend_cols", "dropped_weekly_constant"],
            outputs=["score (0-100)", "model_mode", "data_confidence_band", "gating_reasons", "diagnostics_snapshot"],
            parameters={
                "scoring_weights": "depth(25) + coverage(20) + inactivity(10) + cv(20) + snr(25)",
                "mode_gates": "score>=70 -> causal_full, score>=55 -> causal_cautious, else -> diagnostic_stabilized",
                "hard_gate": "cv_active < 0.12 always forces diagnostic_stabilized",
            },
        ),
        PipelineNode(
            step_id="matrix",
            step_number="6",
            name="Build Design Matrix",
            description="Constructs X (const, centered trend, event dummies, transformed spend) and y (revenue)",
            module_path="pipeline/matrix.py",
            function_name="build_design_matrix",
            inputs=["df_weekly", "spend_cols", "model_mode", "diagnostics", "feature_state (None)"],
            outputs=["X (DataFrame)", "y (Series)", "feature_state (dict)"],
            parameters={
                "causal_full": "adstock(alpha=0.5) + log1p(spend) + log1p(revenue)",
                "causal_cautious": "adstock(alpha=0.4) + log1p(spend) + log1p(revenue)",
                "diagnostic_stabilized": "raw spend, raw revenue",
            },
        ),
        PipelineNode(
            step_id="ols",
            step_number="7",
            name="Fit Base OLS",
            description="Ordinary Least Squares regression via statsmodels",
            module_path="pipeline/modeling.py",
            function_name="fit_ols",
            inputs=["X", "y"],
            outputs=["ModelResult (model_type, coefficients, residuals, predicted, r2, adj_r2, residual_std)"],
        ),
        PipelineNode(
            step_id="vif",
            step_number="8",
            name="VIF Check (Multicollinearity)",
            description="Computes Variance Inflation Factor for each feature; switches to Ridge if VIF too high",
            module_path="pipeline/modeling.py",
            function_name="check_vif",
            inputs=["result (ModelResult)", "spend_cols"],
            outputs=["result (possibly Ridge)"],
            parameters={"VIF_threshold": 10},
            branch_condition="max(VIF) > 10 -> switch to Ridge(alpha via RidgeCV)",
        ),
        PipelineNode(
            step_id="autocorrelation",
            step_number="9",
            name="Autocorrelation Check",
            description="Durbin-Watson + Ljung-Box test; adds lagged y terms and/or HAC standard errors if residuals are autocorrelated",
            module_path="pipeline/modeling.py",
            function_name="check_autocorrelation",
            inputs=["result", "spend_cols"],
            outputs=["result (possibly with lags and/or HAC)"],
            parameters={"ljung_box_lags": 5, "p_threshold": 0.05, "max_lags_added": 2, "hac_maxlags": 1},
            branch_condition="LB p < 0.05 -> add lag_1 -> refit -> still < 0.05 -> add lag_2 -> refit -> still < 0.05 -> apply HAC (OLS only)",
        ),
        PipelineNode(
            step_id="heteroskedasticity",
            step_number="10",
            name="Heteroskedasticity Check",
            description="Breusch-Pagan test for non-constant variance in residuals; applies HAC if significant",
            module_path="pipeline/modeling.py",
            function_name="check_heteroskedasticity",
            inputs=["result"],
            outputs=["result (possibly with HAC)"],
            parameters={"bp_p_threshold": 0.05, "hac_maxlags": 1},
            branch_condition="BP p < 0.05 and not ridge_applied and not hac_applied -> apply HAC",
        ),
        PipelineNode(
            step_id="nonlinearity",
            step_number="11",
            name="Nonlinearity Check",
            description="Tests whether log-transforming spend improves R2; adopts log if improvement > threshold",
            module_path="pipeline/modeling.py",
            function_name="check_nonlinearity",
            inputs=["result", "spend_cols"],
            outputs=["result (possibly with log-transformed spend)"],
            parameters={"r2_improvement_threshold": 0.01},
            branch_condition="log(spend) R2 > current R2 + 0.01 -> adopt log transform",
        ),
        PipelineNode(
            step_id="counterfactual",
            step_number="12",
            name="Counterfactual Impact",
            description="Zeros out each spend channel individually; measures incremental revenue and marginal ROI",
            module_path="pipeline/counterfactual.py",
            function_name="compute_counterfactual",
            inputs=["result", "spend_cols", "use_log_target", "smearing_factor", "df_weekly"],
            outputs=["incremental (Dict[channel, $])", "marginal_roi (Dict[channel, $/$ spent])"],
        ),
        PipelineNode(
            step_id="anomalies",
            step_number="13",
            name="Anomaly Detection",
            description="Flags weekly observations where the residual z-score exceeds threshold",
            module_path="pipeline/anomalies.py",
            function_name="detect_anomalies",
            inputs=["result", "dates (week_start Series)"],
            outputs=["anomalies (List[Dict] with ts, actual, predicted, residual, z_score, direction)"],
            parameters={"Z_THRESHOLD": 2.5},
        ),
        PipelineNode(
            step_id="confidence",
            step_number="14",
            name="Confidence Score",
            description="Rule-based confidence scoring; OOS metrics can only downgrade, never upgrade",
            module_path="pipeline/confidence.py",
            function_name="compute_confidence",
            inputs=["result", "n_obs", "oos_metrics", "n_obs_effective (optional)"],
            outputs=["confidence_level ('high' | 'medium' | 'low')"],
            parameters={
                "r2_thresholds": "< 0.15 -> low, < 0.3 -> medium",
                "obs_thresholds": "60-90 -> medium, < 90 and r2 < 0.3 -> low (uses n_obs_effective when provided)",
                "vif_gate": "min_vif < 1.01 -> low",
                "oos_gates": "r2 < -0.5 (16+ obs) -> low, r2 < 0 (16+ obs) -> downgrade one level",
            },
        ),
        PipelineNode(
            step_id="persist",
            step_number="15",
            name="Persist Results",
            description="Saves model version, coefficients, diagnostics, and anomalies to Supabase",
            module_path="pipeline/persist.py",
            function_name="persist_results",
            inputs=[
                "project_id", "result", "spend_cols", "incremental", "marginal_roi",
                "anomalies", "confidence_level", "n_obs", "diagnostics",
                "model_config", "config_hash", "oos_metrics", "feature_state",
            ],
            outputs=["version_id (UUID)"],
            parameters={"tables_written": ["models", "model_versions", "model_coefficients", "model_diagnostics", "model_anomalies"]},
        ),
    ]


def _define_forecast_steps() -> List[PipelineNode]:
    return [
        PipelineNode(
            step_id="load_model",
            step_number="F1",
            name="Load Model Version",
            description="Version-driven load from Supabase; no in-memory state. Retrieves coefficients, feature_state, model_config",
            module_path="pipeline/forecast.py",
            function_name="load_latest_model_version",
            inputs=["project_id", "version_id (optional)"],
            outputs=["LoadedModelVersion (coefficients, feature_state, model_config, spend_cols)"],
        ),
        PipelineNode(
            step_id="latest_weekly",
            step_number="F2",
            name="Get Latest Weekly Row",
            description="Fetches latest weekly actual data to establish baseline spend and week_index",
            module_path="pipeline/forecast.py",
            function_name="get_latest_weekly_row",
            inputs=["project_id", "spend_cols"],
            outputs=["last_week_index (int)", "baseline_spend (Dict[str, float])"],
        ),
        PipelineNode(
            step_id="build_prediction_x",
            step_number="F3",
            name="Build Prediction Matrix",
            description="Builds X using stored feature_state for consistency (trend centering, adstock carryover values)",
            module_path="pipeline/forecast.py",
            function_name="build_X_for_prediction",
            inputs=["df_weekly", "spend_cols", "model_config", "feature_state"],
            outputs=["X (DataFrame)"],
        ),
        PipelineNode(
            step_id="predict",
            step_number="F4",
            name="Predict Revenue",
            description="X @ beta with lag recursion, inverse log-target transform, smearing factor correction",
            module_path="pipeline/forecast.py",
            function_name="predict_revenue",
            inputs=["loaded (LoadedModelVersion)", "X"],
            outputs=["predictions (ndarray, revenue space)"],
        ),
    ]


# ── Builder ──────────────────────────────────────────────────────────────────


def build_pipeline_tree(
    pipeline_dir: Optional[Path] = None,
    force_rebuild: bool = False,
) -> PipelineTree:
    d = pipeline_dir or PIPELINE_DIR
    current_hash = compute_source_hash(d)

    if not force_rebuild and CACHE_PATH.exists():
        try:
            cached = json.loads(CACHE_PATH.read_text())
            if cached.get("source_hash") == current_hash:
                tree_data = cached["tree"]
                return PipelineTree(
                    version=tree_data["version"],
                    source_hash=tree_data["source_hash"],
                    pipeline_name=tree_data["pipeline_name"],
                    entry_point=tree_data["entry_point"],
                    steps=[_node_from_dict(s) for s in tree_data["steps"]],
                    forecast_steps=[_node_from_dict(s) for s in tree_data.get("forecast_steps", [])],
                )
        except (json.JSONDecodeError, KeyError):
            pass

    modeling_steps = _define_modeling_steps()
    forecast_steps = _define_forecast_steps()

    for node in modeling_steps:
        _enrich_node(node, d)
    for node in forecast_steps:
        _enrich_node(node, d)

    tree = PipelineTree(
        version=datetime.now(timezone.utc).isoformat(),
        source_hash=current_hash,
        pipeline_name="Orbital Modeling Pipeline",
        entry_point="pipeline/stream.py :: stream_pipeline()",
        steps=modeling_steps,
        forecast_steps=forecast_steps,
    )

    try:
        CACHE_PATH.write_text(
            json.dumps({"source_hash": current_hash, "tree": tree.to_dict()}, indent=2)
        )
    except OSError:
        pass

    return tree


def has_changed(pipeline_dir: Optional[Path] = None) -> bool:
    d = pipeline_dir or PIPELINE_DIR
    current_hash = compute_source_hash(d)
    if not CACHE_PATH.exists():
        return True
    try:
        cached = json.loads(CACHE_PATH.read_text())
        return cached.get("source_hash") != current_hash
    except (json.JSONDecodeError, KeyError):
        return True


def _node_from_dict(d: dict) -> PipelineNode:
    children = [_node_from_dict(c) for c in d.get("children", [])]
    return PipelineNode(
        step_id=d["step_id"],
        step_number=d["step_number"],
        name=d["name"],
        description=d["description"],
        module_path=d["module_path"],
        function_name=d["function_name"],
        inputs=d["inputs"],
        outputs=d["outputs"],
        parameters=d.get("parameters", {}),
        children=children,
        branch_condition=d.get("branch_condition"),
        function_signature=d.get("function_signature"),
        line_number=d.get("line_number"),
        docstring=d.get("docstring"),
    )
