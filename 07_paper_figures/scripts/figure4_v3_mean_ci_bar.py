"""Figure 4 v3: Stage 2 — both panels as mean±95%CI bar with individual SR dots.

Panel A  : Recall — mean ± 95% CI bar (linear scale, 0–1) + individual SR dots
Panel B  : NNR    — mean ± 95% CI bar (log scale)          + individual SR dots

Output: figures/figure4_v3_mean_ci_bar.png
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = _SCRIPT_DIR.parent / "data" / "test24_eval"
OUT_DIR  = _SCRIPT_DIR.parent / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CSV = DATA_DIR / "elicit24_points_gate1000_floor1000_20260511.csv"
df = pd.read_csv(CSV)

METHODS = [
    ("Human query",             "#5B7FA6"),
    ("Elicit Keyword all",      "#C9B8D8"),
    ("Elicit Question all",     "#9B72B0"),
    ("Elicit Question include", "#6A3D9A"),
    ("OpenScholar normal",      "#FBCBA0"),
    ("OpenScholar deep",        "#E07B2A"),
    ("Claude cut70",            "#2E6FA3"),
    ("Codex cut70",             "#D97B2B"),
    ("Gemini cut70",            "#3A9E52"),
]

SIG_NNR = {
    "Claude cut70":  "* p=0.042",
    "Codex cut70":   "* p=0.023",
    "Gemini cut70":  "* p=0.024",
}

RNG    = np.random.default_rng(42)
N_BOOT = 10_000
JIT    = 0.12
BAR    = 0.55

def get_col(method: str, col: str) -> np.ndarray:
    return (df[df["method"] == method]
            .drop_duplicates("paper_id")[col]
            .replace([np.inf, -np.inf], np.nan)
            .dropna()
            .values)

def bootstrap_ci(vals: np.ndarray) -> tuple[float, float, float]:
    v = vals[np.isfinite(vals)]
    if len(v) == 0:
        return np.nan, np.nan, np.nan
    boots = RNG.choice(v, size=(N_BOOT, len(v)), replace=True).mean(axis=1)
    return v.mean(), np.percentile(boots, 2.5), np.percentile(boots, 97.5)

# Precompute
X      = np.arange(len(METHODS))
colors = [c for _, c in METHODS]
labels = [lb for lb, _ in METHODS]

recall_vals = [get_col(lb, "recall") for lb, _ in METHODS]
nnr_vals    = [get_col(lb, "nnr")    for lb, _ in METHODS]

recall_stats = [bootstrap_ci(v) for v in recall_vals]
nnr_stats    = [bootstrap_ci(v) for v in nnr_vals]

r_mean = np.array([s[0] for s in recall_stats])
r_lo   = np.array([s[1] for s in recall_stats])
r_hi   = np.array([s[2] for s in recall_stats])

n_mean = np.array([s[0] for s in nnr_stats])
n_lo   = np.array([s[1] for s in nnr_stats])
n_hi   = np.array([s[2] for s in nnr_stats])

# ── Style ──────────────────────────────────────────────────────────────────────
plt.rcParams.update({
    "font.family": "Arial",
    "font.size":   10,
    "axes.labelsize": 11,
})

fig, (ax_r, ax_n) = plt.subplots(1, 2, figsize=(15, 6))
fig.subplots_adjust(left=0.06, right=0.98, top=0.93, bottom=0.24, wspace=0.28)

# ── Panel A: Recall mean±CI bar (linear) ──────────────────────────────────────
ax_r.bar(X, r_mean, width=BAR, color=colors, alpha=0.75,
         edgecolor="white", linewidth=0.8, zorder=3)
ax_r.errorbar(X, r_mean,
              yerr=[r_mean - r_lo, r_hi - r_mean],
              fmt="none", color="#222222", capsize=5, capthick=1.4,
              linewidth=1.4, zorder=4)

for xi, (vals, color) in enumerate(zip(recall_vals, colors)):
    jitter = RNG.uniform(-JIT, JIT, size=len(vals))
    ax_r.scatter(xi + jitter, vals, s=30, color=color,
                 edgecolors="black", linewidths=0.8, zorder=5, alpha=0.9)

ax_r.axhline(r_mean[0], color=colors[0], linestyle="--", linewidth=1.2, alpha=0.6)

ax_r.set_xticks(X)
ax_r.set_xticklabels(labels, fontsize=9.5, rotation=15, ha="right")
ax_r.set_ylabel("Recall"); ax_r.set_ylim(0, 1.05)
ax_r.set_title("A  Stage 2 Recall", loc="left", fontweight="bold", fontsize=12)
ax_r.yaxis.grid(True, linestyle="--", alpha=0.35, zorder=0)
ax_r.spines["top"].set_visible(False); ax_r.spines["right"].set_visible(False)

# ── Panel B: NNR mean±CI bar (log scale) ──────────────────────────────────────
ax_n.bar(X, n_mean, width=BAR, color=colors, alpha=0.75,
         edgecolor="white", linewidth=0.8, zorder=3)
ax_n.errorbar(X, n_mean,
              yerr=[n_mean - n_lo, n_hi - n_mean],
              fmt="none", color="#222222", capsize=5, capthick=1.4,
              linewidth=1.4, zorder=4)

for xi, (vals, color) in enumerate(zip(nnr_vals, colors)):
    jitter = RNG.uniform(-JIT, JIT, size=len(vals))
    ax_n.scatter(xi + jitter, vals, s=26, color=color,
                 edgecolors="black", linewidths=0.8, zorder=5, alpha=0.9)

ax_n.axhline(n_mean[0], color=colors[0], linestyle="--", linewidth=1.2, alpha=0.6)

ax_n.set_yscale("log")

# Significance brackets: Human (x=0) vs each LLM cut70 — drawn after set_yscale
# Bracket heights spaced in log space above Human CI upper
SIG_BRACKET_NNR = [
    (6, "* p=0.042"),   # Claude cut70
    (7, "* p=0.023"),   # Codex cut70
    (8, "* p=0.024"),   # Gemini cut70
]
log_factors  = [2.2, 3.8, 6.5]   # multiplied by n_hi[0] (Human CI upper ~746)
stub_divisor = 1.55               # tick stub = bracket_y / stub_divisor  (floats above CI)
for i, (xi, plabel) in enumerate(SIG_BRACKET_NNR):
    y      = n_hi[0] * log_factors[i]   # bracket height in NNR units
    y_stub = y / stub_divisor            # short tick bottom — detached from CI lines
    ax_n.plot([0, 0, xi, xi], [y_stub, y, y, y_stub],
              color="#333333", linewidth=1.0, clip_on=False, zorder=6)
    ax_n.text(xi / 2, y * 1.08, plabel, ha="center", va="bottom",
              fontsize=8.5, fontweight="bold", color="#333333")

# Set y upper limit to give bracket + label room (above highest bracket)
ax_n.set_ylim(top=n_hi[0] * log_factors[-1] * 3.5)

ax_n.set_xticks(X)
ax_n.set_xticklabels(labels, fontsize=9.5, rotation=15, ha="right")
ax_n.set_ylabel("NNR — Mean ± 95% CI (log scale)")
ax_n.set_title("B  Stage 2 NNR", loc="left", fontweight="bold", fontsize=12)
ax_n.yaxis.grid(True, linestyle="--", alpha=0.35, zorder=0)
ax_n.spines["top"].set_visible(False); ax_n.spines["right"].set_visible(False)

# ── Legend ────────────────────────────────────────────────────────────────────
legend_items = [mpatches.Patch(color=c, label=lb, alpha=0.75)
                for lb, c in METHODS]
fig.legend(handles=legend_items, loc="lower center", ncol=5,
           bbox_to_anchor=(0.5, 0.01), frameon=False, fontsize=9.5,
           handlelength=1.3, handletextpad=0.5, columnspacing=1.1)

out = OUT_DIR / "figure4_v3_mean_ci_bar.png"
fig.savefig(out, dpi=300, bbox_inches="tight")
print(f"Saved: {out}")

print("\nRecall mean / 95% CI per method:")
for (label, _), m, lo, hi in zip(METHODS, r_mean, r_lo, r_hi):
    print(f"  {label:<30}  mean={m:.3f}  [{lo:.3f}-{hi:.3f}]")
print("\nNNR mean / 95% CI per method:")
for (label, _), m, lo, hi in zip(METHODS, n_mean, n_lo, n_hi):
    print(f"  {label:<30}  mean={m:7.1f}  [{lo:7.1f}-{hi:7.1f}]")
