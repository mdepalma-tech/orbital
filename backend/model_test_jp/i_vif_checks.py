"""
VIF (Variance Inflation Factor) Diagnostic
Run after the pipeline has built mmm_results, df_train, saturated_cols, seasonality_cols.

Add this to your pipeline_mmm.py after step 6:
    from model_test_jp.vif_check import compute_and_plot_vif
    compute_and_plot_vif(df_train, mmm_results['all_feature_cols'])
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression
from typing import List


def compute_vif(df: pd.DataFrame, feature_cols: List[str]) -> pd.DataFrame:
    """
    Compute VIF for each feature by regressing it on all other features
    and measuring how much of its variance is explained.

    VIF = 1 / (1 - R²)

    A feature with R²=0.9 when regressed on others has VIF=10 — meaning
    90% of its variance is shared with other features. The regression
    coefficient for that feature is 10x less stable than it would be
    if the feature were independent.

    Args:
        df           : Training DataFrame.
        feature_cols : All feature columns used in the model.

    Returns:
        DataFrame with feature name, VIF score, and interpretation.
    """
    X = df[feature_cols].values
    vif_data = []

    for i, col in enumerate(feature_cols):
        # Regress feature i on all other features
        X_others = np.delete(X, i, axis=1)
        y_target = X[:, i]

        model = LinearRegression()
        model.fit(X_others, y_target)
        r2 = model.score(X_others, y_target)

        # Clamp R² to avoid division by zero or negative VIF
        r2 = min(r2, 0.9999)
        vif = 1 / (1 - r2)

        if vif < 2:
            flag = "✓ fine"
            color = "#2ca02c"
        elif vif < 5:
            flag = "⚠ moderate"
            color = "#DD8452"
        elif vif < 10:
            flag = "⚠⚠ high"
            color = "#d62728"
        else:
            flag = "❌ severe"
            color = "#8B0000"

        vif_data.append({
            'feature'       : col,
            'VIF'           : round(vif, 2),
            'R²_with_others': round(r2, 4),
            'flag'          : flag,
            'color'         : color,
        })

    return pd.DataFrame(vif_data).sort_values('VIF', ascending=False).reset_index(drop=True)


def compute_and_plot_vif(
    df: pd.DataFrame,
    feature_cols: List[str],
    save_path: str = "model_test_jp/vif_check.png",
) -> pd.DataFrame:
    """
    Compute VIF for all model features and produce a diagnostic bar chart.

    Args:
        df           : Training DataFrame with all feature columns.
        feature_cols : All feature columns used in the model (saturated + seasonality).
        save_path    : Where to save the PNG.

    Returns:
        DataFrame with VIF scores — also printed to console.
    """
    vif_df = compute_vif(df, feature_cols)

    # ── Console output ────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("VIF DIAGNOSTIC  (Variance Inflation Factor)")
    print("=" * 60)
    print(f"  {'Feature':40} | {'VIF':>6} | Status")
    print("-" * 60)
    for _, row in vif_df.iterrows():
        print(f"  {row['feature']:40} | {row['VIF']:>6.2f} | {row['flag']}")
    print("-" * 60)
    print("  Thresholds: <2 fine  |  2-5 moderate  |  5-10 high  |  >10 severe")

    max_vif = vif_df['VIF'].max()
    if max_vif < 2:
        print("\n  ✅ No multicollinearity detected — coefficients are reliable.")
    elif max_vif < 5:
        print("\n  ⚠  Mild multicollinearity. Coefficients are slightly less stable.")
        print("     Consider checking correlated feature pairs.")
    elif max_vif < 10:
        print("\n  ⚠⚠ High multicollinearity detected.")
        print("     Some coefficients may be unreliable. Consider Ridge regression.")
    else:
        print("\n  ❌ Severe multicollinearity. Coefficients cannot be trusted.")
        print("     Use Ridge regression or drop correlated features.")

    # ── Plot ──────────────────────────────────────────────────────────────────
    fig, axes = plt.subplots(1, 2, figsize=(14, 5), facecolor='white')
    fig.suptitle("VIF Diagnostic — Multicollinearity Check", fontsize=13, fontweight='bold')

    SHADE = "#F5F7FF"

    # Left: VIF bar chart
    ax = axes[0]
    ax.set_facecolor(SHADE)

    features_plot = vif_df['feature'].tolist()[::-1]   # reverse for horizontal bar
    vif_vals      = vif_df['VIF'].tolist()[::-1]
    bar_colors    = vif_df['color'].tolist()[::-1]

    bars = ax.barh(features_plot, vif_vals, color=bar_colors, alpha=0.85, height=0.6)

    # threshold lines
    ax.axvline(2,  color='#DD8452', lw=1.5, ls='--', alpha=0.7, label='VIF=2 (moderate)')
    ax.axvline(5,  color='#d62728', lw=1.5, ls='--', alpha=0.7, label='VIF=5 (high)')
    ax.axvline(10, color='#8B0000', lw=1.5, ls='--', alpha=0.7, label='VIF=10 (severe)')

    # value labels on bars
    for bar, val in zip(bars, vif_vals):
        ax.text(bar.get_width() + 0.05, bar.get_y() + bar.get_height() / 2,
                f'{val:.2f}', va='center', fontsize=9)

    ax.set_xlabel("VIF score")
    ax.set_title("VIF per Feature", fontsize=11, fontweight='bold')
    ax.legend(fontsize=8, loc='lower right')
    ax.grid(axis='x', alpha=0.3)
    ax.set_xlim(0, max(vif_vals) * 1.2 + 1)

    # Right: correlation heatmap of features
    ax2 = axes[1]
    ax2.set_facecolor(SHADE)

    corr = df[feature_cols].corr()
    n    = len(feature_cols)
    im   = ax2.imshow(corr.values, cmap='RdBu_r', vmin=-1, vmax=1, aspect='auto')

    ax2.set_xticks(range(n))
    ax2.set_yticks(range(n))
    short_names = [c.replace('_spend_adstocked_saturated', '\n(sat)')
                    .replace('_spend_adstocked', '\n(ads)') for c in feature_cols]
    ax2.set_xticklabels(short_names, fontsize=7, rotation=45, ha='right')
    ax2.set_yticklabels(short_names, fontsize=7)

    # annotate cells
    for i in range(n):
        for j in range(n):
            val = corr.values[i, j]
            color = 'white' if abs(val) > 0.6 else 'black'
            ax2.text(j, i, f'{val:.2f}', ha='center', va='center',
                     fontsize=7, color=color)

    plt.colorbar(im, ax=ax2, shrink=0.8)
    ax2.set_title("Feature Correlation Matrix\n(high |r| = potential collinearity)", fontsize=11, fontweight='bold')

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    print(f"\n✅ VIF plot saved to: {save_path}")
    plt.close()

    return vif_df


if __name__ == "__main__":
    print("Import and call compute_and_plot_vif(df_train, mmm_results['all_feature_cols'])")
    print("from your pipeline after build_mmm_model.")