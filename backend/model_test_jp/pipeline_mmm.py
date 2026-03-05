import pandas as pd
import numpy as np
import os
from typing import Dict, List, Tuple
import warnings
warnings.filterwarnings('ignore')

import sklearn
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_percentage_error, mean_squared_error
from scipy.optimize import minimize


from model_test_jp.a_data_prep import _load_local_series, _clean_data, _merge_data
from model_test_jp.b_feature_engineering import add_seasonality_features, apply_adstock, apply_saturation, hill_saturation  
from model_test_jp.c_train_test_split import time_based_split
from model_test_jp.d_model import build_mmm_model
from model_test_jp.e_optimize import tune_decay_rates
from model_test_jp.f_metrics import evaluate_holdout
from model_test_jp.g_overfitting_checks import plot_overfitting_diagnostics, plot_learning_curve
from model_test_jp.g_overfitting_checks import plot_overfitting_diagnostics, plot_learning_curve
from model_test_jp.h_mmm_analysis import compute_raw_elasticities
from model_test_jp.i_vif_checks import compute_and_plot_vif


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("MARKETING MIX MODEL (MMM) ANALYSIS")
    print("=" * 80)

    # 1. Load, clean, merge
    df_sales, df_google, df_meta, df_tiktok = _load_local_series()
    df_sales, df_google, df_meta, df_tiktok = _clean_data(df_sales, df_google, df_meta, df_tiktok)
    df_final = _merge_data(df_sales, df_google, df_meta, df_tiktok)
    df_final['sales'] = df_final['sales'] * 100

    df_final, seasonality_cols = add_seasonality_features(df_final)

    df_train_raw, df_test_raw = time_based_split(df_final, train_ratio=0.8)

    spend_cols     = ['google_spend', 'meta_spend', 'tiktok_spend']
    adstocked_cols = [f"{col}_adstocked" for col in spend_cols]

    # 4. Tune decay rates — optimises holdout MAPE across all channels jointly
    print("\n" + "=" * 80)
    print("TUNING ADSTOCK DECAY RATES  (minimising holdout MAPE)")
    print("=" * 80)

    tuning_results = tune_decay_rates(
        df_train_raw,
        df_test_raw,
        spend_cols,
        seasonality_cols,
        n_restarts=5,
    )

    best_decay_params = tuning_results['best_decay_params']

    # 5. Re-run full pipeline with tuned decay rates
    df_train = apply_adstock(df_train_raw, spend_cols, best_decay_params)
    df_test  = apply_adstock(df_test_raw,  spend_cols, best_decay_params)

    df_train, saturated_cols, sat_ref_maxes = apply_saturation(df_train, adstocked_cols)
    df_test,  _,              _             = apply_saturation(df_test,  adstocked_cols, ref_maxes=sat_ref_maxes)

    # 6. Fit final model on training data only
    print("\n" + "=" * 80)
    print("BUILDING FINAL MODEL  (tuned decay rates, training set only)")
    print("=" * 80)

    mmm_results = build_mmm_model(
        df_train,
        response_col     = 'sales',
        spend_cols       = spend_cols,
        saturated_cols   = saturated_cols,
        seasonality_cols = seasonality_cols,
    )

    # 7. Holdout evaluation
    print("\n" + "=" * 80)
    print("HOLDOUT VALIDATION")
    print("=" * 80)

    holdout_metrics = evaluate_holdout(
        mmm_results,
        df_test,
        saturated_cols   = saturated_cols,
        seasonality_cols = seasonality_cols,
    )

    # 8. Results summary
    print("\n" + "=" * 80)
    print("MODEL RESULTS & ELASTICITIES")
    print("=" * 80)

    print(f"\nTrain R²     : {mmm_results['r2_score']:.4f}  ({mmm_results['r2_score']*100:.1f}% of training variance explained)")
    print(f"Holdout R²   : {holdout_metrics['r2']:.4f}  ({holdout_metrics['r2']*100:.1f}% of holdout variance explained)")
    gap = mmm_results['r2_score'] - holdout_metrics['r2']
    print(f"R² gap       : {gap:.4f}  {'⚠ possible overfit' if gap > 0.15 else '✓ generalising well'}")
    print(f"Holdout MAPE : {holdout_metrics['mape']:.2%}")
    print(f"Holdout RMSE : {holdout_metrics['rmse']:,.0f}")

    print("\n⚙️  TUNED DECAY RATES:")
    print("-" * 60)
    for ch, v in best_decay_params.items():
        interpretation = "short memory" if v < 0.3 else ("long memory" if v > 0.7 else "medium memory")
        print(f"  {ch:15} : {v:.4f}  ({interpretation})")

    # 9. Elasticities in adstocked spend space
    raw_elasticities = compute_raw_elasticities(
        mmm_results,
        df_train,
        spend_cols,
        sat_ref_maxes=sat_ref_maxes,
    )

    print("\n📊 ELASTICITY ANALYSIS (adstocked spend space):")
    print("-" * 80)
    print("Elasticity = % change in sales for 1% change in adstocked spend")
    print("-" * 80)
    for channel, elasticity in raw_elasticities.items():
        symbol = "✓" if elasticity > 0 else "⚠"
        print(f"  {channel.upper():15} | Elasticity: {elasticity:7.4f}  {symbol}")

    print("\n📈 CHANNEL CONTRIBUTION TO SALES:")
    print("-" * 80)
    for channel, contribution in mmm_results['contributions'].items():
        pct = contribution * 100
        bar = "█" * int(abs(pct) / 5)
        print(f"  {channel.upper():15} | {pct:6.2f}% | {bar}")

    print("\n🔍 RAW COEFFICIENTS (standardised):")
    print("-" * 60)
    for col, coef in zip(mmm_results['all_feature_cols'], mmm_results['model'].coef_):
        print(f"  {col:40} | {coef:8.4f}")

    print("\n" + "=" * 80)
    print("GENERATING DIAGNOSTIC PLOTS")
    print("=" * 80)

    compute_and_plot_vif(df_train, mmm_results['all_feature_cols'])

    plot_overfitting_diagnostics(
        mmm_results,
        holdout_metrics,
        df_train,
        df_test,
        save_path="model_test_jp/mmm_diagnostics.png",)

    plot_learning_curve(
        df_train_raw,
        df_test_raw,
        spend_cols,
        seasonality_cols,
        best_decay_params,
            save_path="model_test_jp/mmm_learning_curve.png",
    )