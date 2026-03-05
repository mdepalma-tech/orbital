"""
Hill Saturation Visual Explainer
Run: python -m model_test_jp.saturation_explainer
"""

import numpy as np
import matplotlib.pyplot as plt


def hill(x_norm, alpha, gamma):
    return x_norm ** alpha / (x_norm ** alpha + gamma ** alpha)


def plot_saturation_explainer(save_path="model_test_jp/saturation_explainer.png"):

    x = np.linspace(0, 1, 300)   # normalised spend 0→1
    SHADE = "#F5F7FF"

    fig, axes = plt.subplots(1, 3, figsize=(15, 5), facecolor='white')
    fig.suptitle("Hill Saturation — Diminishing Returns on Ad Spend",
                 fontsize=13, fontweight='bold')

    # ── Panel 1: the core concept ─────────────────────────────────────────────
    ax = axes[0]
    ax.set_facecolor(SHADE)

    y = hill(x, alpha=2.0, gamma=0.5)
    ax.plot(x, y, color='#4C72B0', lw=2.5)

    # annotate the three zones
    ax.axvspan(0,    0.30, alpha=0.12, color='#2ca02c')
    ax.axvspan(0.30, 0.65, alpha=0.12, color='#DD8452')
    ax.axvspan(0.65, 1.00, alpha=0.12, color='#d62728')

    ax.text(0.03, 0.85, "High ROI zone\neach £ works hard",   fontsize=8, color='#2ca02c')
    ax.text(0.31, 0.55, "Inflection point\nbest bang-per-£\nstarts declining", fontsize=8, color='#DD8452')
    ax.text(0.66, 0.25, "Saturated zone\neach extra £\nbarely moves sales", fontsize=8, color='#d62728')

    # mark gamma
    ax.axvline(0.5, color='#888', lw=1, ls='--')
    ax.plot(0.5, hill(0.5, 2.0, 0.5), 'o', color='#888', ms=7)
    ax.text(0.52, 0.42, "γ = 0.5\nhalf-saturation\npoint", fontsize=8, color='#555')

    ax.set_title("Core concept\n(alpha=2.0, gamma=0.5)", fontsize=10, fontweight='bold')
    ax.set_xlabel("Normalised spend  (0 = none, 1 = max ever spent)")
    ax.set_ylabel("Saturated response  (0 → 1)")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.grid(alpha=0.25)

    # ── Panel 2: effect of alpha ──────────────────────────────────────────────
    ax = axes[1]
    ax.set_facecolor(SHADE)

    alphas  = [0.5, 1.0, 2.0, 4.0]
    palette = ['#1f77b4', '#2ca02c', '#DD8452', '#d62728']
    for a, c in zip(alphas, palette):
        ax.plot(x, hill(x, alpha=a, gamma=0.5), color=c, lw=2, label=f"alpha={a}")

    ax.axvline(0.5, color='#888', lw=1, ls='--', alpha=0.5)
    ax.set_title("Effect of alpha\n(gamma fixed at 0.5)", fontsize=10, fontweight='bold')
    ax.set_xlabel("Normalised spend")
    ax.set_ylabel("Saturated response")
    ax.legend(fontsize=9)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.grid(alpha=0.25)
    ax.text(0.02, 0.6,
            "Low alpha → gentle curve\n(gradual diminishing returns)\n\nHigh alpha → sharp S-curve\n(returns collapse quickly)",
            fontsize=8, color='#444',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    # ── Panel 3: effect of gamma ──────────────────────────────────────────────
    ax = axes[2]
    ax.set_facecolor(SHADE)

    gammas  = [0.2, 0.4, 0.6, 0.8]
    palette = ['#1f77b4', '#2ca02c', '#DD8452', '#d62728']
    for g, c in zip(gammas, palette):
        ax.plot(x, hill(x, alpha=2.0, gamma=g), color=c, lw=2, label=f"gamma={g}")
        # mark inflection point
        ax.plot(g, 0.5, 'o', color=c, ms=5, alpha=0.7)

    ax.axhline(0.5, color='#888', lw=1, ls='--', alpha=0.5)
    ax.text(0.01, 0.52, "response = 0.5", fontsize=8, color='#888')
    ax.set_title("Effect of gamma\n(alpha fixed at 2.0)", fontsize=10, fontweight='bold')
    ax.set_xlabel("Normalised spend")
    ax.set_ylabel("Saturated response")
    ax.legend(fontsize=9)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.grid(alpha=0.25)
    ax.text(0.45, 0.1,
            "gamma = the spend level where\nyou hit 50% of max response\n\nLow gamma → saturates early\nHigh gamma → saturates late",
            fontsize=8, color='#444',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    print(f"✅ Saved to: {save_path}")
    plt.close()


if __name__ == "__main__":
    plot_saturation_explainer()