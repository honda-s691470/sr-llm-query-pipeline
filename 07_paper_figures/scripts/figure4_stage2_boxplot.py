"""Figure 4: Stage 2 Recall (4A top) and NNR (4B bottom) — all methods vs LLM cut70."""

import pandas as pd
import numpy as np
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
    ("Human query",           "#5B7FA6"),
    ("Elicit Keyword all",    "#C9B8D8"),
    ("Elicit Question all",   "#9B72B0"),
    ("Elicit Question include","#6A3D9A"),
    ("OpenScholar normal",    "#FBCBA0"),
    ("OpenScholar deep",      "#E07B2A"),
    ("Claude cut70",          "#2E6FA3"),
    ("Codex cut70",           "#D97B2B"),
    ("Gemini cut70",          "#3A9E52"),
]

# Significance vs Human NNR (cut70; from table1)
SIG_NNR = {
    "Claude cut70":  "* p=0.042",
    "Codex cut70":   "* p=0.023",
    "Gemini cut70":  "* p=0.024",
}

def get_data(method):
    sub = df[df["method"] == method][["paper_id", "recall", "nnr"]].copy()
    sub = sub.drop_duplicates(subset="paper_id")
    return sub

groups = [(label, get_data(label), color) for label, color in METHODS]

plt.rcParams.update({
    "font.family": "Arial",
    "font.size":   10,
    "axes.labelsize": 11,
    "axes.spines.top": False,
    "axes.spines.right": False,
})

fig, (ax_r, ax_n) = plt.subplots(2, 1, figsize=(14, 10))
fig.subplots_adjust(left=0.07, right=0.98, top=0.96, bottom=0.22, hspace=0.38)

X   = np.arange(len(groups))
JIT = 0.13

def draw_panel(ax, metric, ylabel, title_letter, title_text, ylim=None, logy=False, sig=None):
    data_list  = [grp[metric].replace([np.inf, -np.inf], np.nan).dropna().values
                  for _, grp, _ in groups]
    colors     = [c for _, _, c in groups]
    labels_x   = [lb for lb, _, _ in groups]

    bp = ax.boxplot(data_list, positions=X, widths=0.6, patch_artist=True,
                    medianprops=dict(color="black", linewidth=2),
                    whiskerprops=dict(linewidth=1.2),
                    capprops=dict(linewidth=1.2),
                    showfliers=False)
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.65)
        patch.set_edgecolor("white")

    for xi, (data, color) in enumerate(zip(data_list, colors)):
        jitter = np.random.default_rng(42).uniform(-JIT, JIT, size=len(data))
        ax.scatter(xi + jitter, data, s=28, color=color, edgecolors="white",
                   linewidths=0.5, zorder=4, alpha=0.9)

    for xi, data in enumerate(data_list):
        if len(data) > 0:
            ax.scatter(xi, np.nanmean(data), marker="D", s=60,
                       color="white", edgecolors="black", linewidths=1.2, zorder=5)

    # Human baseline
    human_mean = np.nanmean(data_list[0])
    ax.axhline(human_mean, color=colors[0], linestyle="--", linewidth=1.2, alpha=0.6)

    # Significance markers
    if sig:
        for xi, (label, _, _) in enumerate(groups):
            if label in sig:
                data = data_list[xi]
                if len(data) == 0:
                    continue
                top = np.nanmax(data)
                offset = top * 1.15 if logy else top + (ylim[1] - ylim[0]) * 0.03 if ylim else top * 1.05
                ax.text(xi, offset, sig[label], ha="center", va="bottom",
                        fontsize=8, fontweight="bold", color="#222222")

    ax.set_xticks(X)
    ax.set_xticklabels(labels_x, fontsize=9.5, rotation=15, ha="right")
    ax.set_ylabel(ylabel)
    ax.set_title(f"{title_letter}  {title_text}", loc="left",
                 fontweight="bold", fontsize=12)
    ax.yaxis.grid(True, linestyle="--", alpha=0.35, zorder=0)
    if ylim:
        ax.set_ylim(*ylim)
    if logy:
        ax.set_yscale("log")

draw_panel(ax_r, "recall", "Recall", "A",
           "Stage 2 Recall", ylim=(0, 1.15))
draw_panel(ax_n, "nnr", "NNR (log scale)", "B",
           "Stage 2 NNR", logy=True, sig=SIG_NNR)

# Legend
legend_items = [
    mpatches.Patch(color="#5B7FA6", label="Human query"),
    mpatches.Patch(color="#C9B8D8", label="Elicit Keyword all"),
    mpatches.Patch(color="#9B72B0", label="Elicit Question all"),
    mpatches.Patch(color="#6A3D9A", label="Elicit Question include"),
    mpatches.Patch(color="#FBCBA0", label="OpenScholar normal"),
    mpatches.Patch(color="#E07B2A", label="OpenScholar deep"),
    mpatches.Patch(color="#2E6FA3", label="Claude cut70"),
    mpatches.Patch(color="#D97B2B", label="Codex cut70"),
    mpatches.Patch(color="#3A9E52", label="Gemini cut70"),
]
fig.legend(handles=legend_items, loc="lower center", ncol=5,
           bbox_to_anchor=(0.5, 0.01), frameon=False, fontsize=10,
           handlelength=1.4, handletextpad=0.5, columnspacing=1.2)

# Print summary stats
print("Mean recall / NNR per method:")
for label, grp, _ in groups:
    r = grp["recall"].mean()
    n = grp["nnr"].replace([np.inf], np.nan).mean()
    print(f"  {label:<30} recall={r:.3f}  NNR={n:.1f}")

out = OUT_DIR / "figure4_stage2_boxplot.png"
fig.savefig(out, dpi=300, bbox_inches="tight")
print(f"\nSaved: {out}")
