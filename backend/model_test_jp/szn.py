"""
Seasonality Features — Visual Explainer
Run standalone to see what each feature looks like over time.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec


def plot_seasonality_features(n_weeks: int = 104, save_path: str = "seasonality_explainer.png"):
    """
    Visualise the trend + Fourier seasonality features used in the MMM.

    Args:
        n_weeks   : Number of weeks to plot (default 104 = 2 years).
        save_path : Where to save the PNG.
    """
    t      = np.arange(n_weeks)
    sin_1  = np.sin(2 * np.pi * 1 * t / 52)
    cos_1  = np.cos(2 * np.pi * 1 * t / 52)
    sin_2  = np.sin(2 * np.pi * 2 * t / 52)
    cos_2  = np.cos(2 * np.pi * 2 * t / 52)

    # Simulate what the combined seasonality looks like with example coefficients
    # (similar to what a fitted MMM might learn)
    example_season = 0.4 * sin_1 + 0.15 * cos_1 + 0.2 * sin_2 - 0.1 * cos_2

    fig = plt.figure(figsize=(14, 12), facecolor="white")
    fig.suptitle("Seasonality Features in the MMM — How They Work",
                 fontsize=15, fontweight='bold', y=0.98)

    gs = gridspec.GridSpec(3, 2, figure=fig, hspace=0.55, wspace=0.35)

    C1, C2, C3 = "#4C72B0", "#DD8452", "#55A868"
    SHADE = "#F5F7FF"

    week_ticks       = np.arange(0, n_weeks + 1, 13)
    week_tick_labels = [f"W{w}" for w in week_ticks]

    # ── Panel 1: Trend ────────────────────────────────────────────────────────
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.set_facecolor(SHADE)
    ax1.plot(t, t, color=C1, lw=2)
    ax1.set_title("Trend  (t)", fontsize=11, fontweight='bold')
    ax1.set_xlabel("Week")
    ax1.set_ylabel("Value")
    ax1.set_xticks(week_ticks)
    ax1.set_xticklabels(week_tick_labels, fontsize=7)
    ax1.grid(alpha=0.3)
    ax1.text(5, n_weeks * 0.75,
             "Tells the model:\n'time is passing'\nCaptures slow drift\nin baseline sales",
             fontsize=9, color="#444", bbox=dict(boxstyle='round', facecolor='white', alpha=0.7))

    # ── Panel 2: k=1 Fourier pair ─────────────────────────────────────────────
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.set_facecolor(SHADE)
    ax2.plot(t, sin_1, color=C1,     lw=2, label="sin_1")
    ax2.plot(t, cos_1, color=C2,     lw=2, label="cos_1", ls="--")
    ax2.axhline(0, color="#aaa", lw=0.8, ls=":")
    ax2.set_title("Harmonic k=1  (1 wave/year)", fontsize=11, fontweight='bold')
    ax2.set_xlabel("Week")
    ax2.set_ylabel("Value")
    ax2.set_xticks(week_ticks)
    ax2.set_xticklabels(week_tick_labels, fontsize=7)
    ax2.legend(fontsize=9)
    ax2.grid(alpha=0.3)
    ax2.text(5, 0.65,
             "One full peak + trough\nper year — captures\nthe main annual season",
             fontsize=9, color="#444", bbox=dict(boxstyle='round', facecolor='white', alpha=0.7))

    # ── Panel 3: k=2 Fourier pair ─────────────────────────────────────────────
    ax3 = fig.add_subplot(gs[1, 0])
    ax3.set_facecolor(SHADE)
    ax3.plot(t, sin_2, color=C1, lw=2, label="sin_2")
    ax3.plot(t, cos_2, color=C2, lw=2, label="cos_2", ls="--")
    ax3.axhline(0, color="#aaa", lw=0.8, ls=":")
    ax3.set_title("Harmonic k=2  (2 waves/year)", fontsize=11, fontweight='bold')
    ax3.set_xlabel("Week")
    ax3.set_ylabel("Value")
    ax3.set_xticks(week_ticks)
    ax3.set_xticklabels(week_tick_labels, fontsize=7)
    ax3.legend(fontsize=9)
    ax3.grid(alpha=0.3)
    ax3.text(5, 0.65,
             "Two peaks + troughs\nper year — captures\nsecondary patterns\n(e.g. summer + Christmas)",
             fontsize=9, color="#444", bbox=dict(boxstyle='round', facecolor='white', alpha=0.7))

    # ── Panel 4: Combined seasonal signal ─────────────────────────────────────
    ax4 = fig.add_subplot(gs[1, 1])
    ax4.set_facecolor(SHADE)
    ax4.plot(t, example_season, color=C3, lw=2.5, label="Combined seasonality")
    ax4.fill_between(t, 0, example_season, alpha=0.15, color=C3)
    ax4.axhline(0, color="#aaa", lw=0.8, ls=":")
    ax4.set_title("Combined Seasonal Signal\n(example coefficients)", fontsize=11, fontweight='bold')
    ax4.set_xlabel("Week")
    ax4.set_ylabel("Value")
    ax4.set_xticks(week_ticks)
    ax4.set_xticklabels(week_tick_labels, fontsize=7)
    ax4.legend(fontsize=9)
    ax4.grid(alpha=0.3)
    ax4.text(5, example_season.min() + 0.05,
             "Model combines all 4\ncurves with learned\ncoefficients to fit\nyour actual sales pattern",
             fontsize=9, color="#444", bbox=dict(boxstyle='round', facecolor='white', alpha=0.7))

    # ── Panel 5: Why not month dummies? ───────────────────────────────────────
    ax5 = fig.add_subplot(gs[2, :])
    ax5.set_facecolor(SHADE)
    ax5.axis('off')

    comparison = [
        ["Approach",          "Features used",  "Parameters",  "Good for"],
        ["Month dummies",     "12 binary cols", "11",          "500+ rows"],
        ["2 Fourier harmonics\n(this model)", "sin/cos × 2", "4", "100–300 rows ✓"],
        ["3 Fourier harmonics","sin/cos × 3",   "6",           "300+ rows"],
    ]

    table = ax5.table(
        cellText  = comparison[1:],
        colLabels = comparison[0],
        cellLoc   = 'center',
        loc       = 'center',
        bbox      = [0.05, 0.0, 0.90, 1.0],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)

    # Highlight the current model row
    for col in range(4):
        table[2, col].set_facecolor("#D4EDDA")
        table[2, col].set_text_props(fontweight='bold')
    for col in range(4):
        table[0, col].set_facecolor("#4C72B0")
        table[0, col].set_text_props(color='white', fontweight='bold')

    ax5.set_title("Why Fourier terms instead of month dummies?", fontsize=11, fontweight='bold', pad=10)

    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    print(f"✅ Saved to: {save_path}")
    plt.close()


if __name__ == "__main__":
    plot_seasonality_features(save_path="model_test_jp/seasonality_explainer.png")