"""Figure 5: Relative screening workload forest plot —human query = 1.00 baseline."""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
OUT_DIR = _SCRIPT_DIR.parent / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Original R_search values (proportion of human workload ELIMINATED)
# Transformed to relative workload = 1 - R_search (human = 1.00)
# (label, r_search_mean, r_search_ci_lo, r_search_ci_hi, recall, color, low_recall_flag)
_RAW = [
    # High-recall group (top)
    ("Claude cut70",             0.685, 0.094, 0.872, 0.718, "#2E6FA3", False),
    ("Gemini cut70",             0.732, 0.275, 0.878, 0.713, "#3A9E52", False),
    ("Human query",              0.000, 0.000, 0.000, 0.699, "#5B7FA6", False),
    ("Codex cut70",              0.707, 0.265, 0.866, 0.674, "#D97B2B", False),
    # Low-recall group (bottom)
    ("Elicit Question all",      0.742, 0.283, 0.863, 0.591, "#9B72B0", True),
    ("Elicit Question\ninclude", 0.932, 0.833, 0.958, 0.527, "#6A3D9A", True),
    ("OpenScholar deep",         0.921, 0.739, 0.965, 0.512, "#E07B2A", True),
    ("OpenScholar normal",       0.969, 0.904, 0.984, 0.301, "#FBCBA0", True),
    ("Elicit Keyword all",       0.745, 0.296, 0.891, 0.209, "#C9B8D8", True),
]

# Replace manuscript display values with values recomputed from the public Test24 CSV.
# Run reproduce_stage2_statistics.py first.
_stats_path = _SCRIPT_DIR.parent / "data" / "test24_eval" / "reproduced_stage2_statistics.csv"
if not _stats_path.exists():
    raise FileNotFoundError("Run reproduce_stage2_statistics.py before generating Figure 5")
_stats = {row["method"]: row for row in __import__("csv").DictReader(_stats_path.open(encoding="utf-8-sig"))}
_recomputed = []
for label, _, _, _, recall, color, low_recall in _RAW:
    key = label.replace("\n", " ")
    if key == "Human query":
        values = (0.0, 0.0, 0.0)
    else:
        row = _stats[key]
        values = tuple(float(row[col]) for col in ("r_search", "r_search_ci_low", "r_search_ci_high"))
    _recomputed.append((label, *values, recall, color, low_recall))
_RAW = _recomputed
# Transform: workload = 1 - R_search; CI reverses (lo →hi)
METHODS = [
    (label, 1 - mean, 1 - ci_hi, 1 - ci_lo, recall, color, low_recall)
    for label, mean, ci_lo, ci_hi, recall, color, low_recall in _RAW
]

Y_HIGH = [8.0, 7.0, 6.0, 5.0]
Y_LOW  = [3.5, 2.5, 1.5, 0.5, -0.5]
y_pos  = Y_HIGH + Y_LOW

plt.rcParams.update({
    "font.family": "Arial",
    "font.size": 10,
    "axes.labelsize": 11,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.spines.left": False,
})

fig, ax = plt.subplots(figsize=(11, 7))
fig.subplots_adjust(left=0.30, right=0.78, top=0.93, bottom=0.18)

# Separator between groups
ax.axhline(4.25, color="#aaaaaa", linewidth=0.9, linestyle="--", alpha=0.7)
# Human baseline at 1.0
ax.axvline(1.0, color="#5B7FA6", linewidth=1.3, linestyle="--", alpha=0.65)

for i, (label, wl_mean, wl_lo, wl_hi, recall, color, low_recall) in enumerate(METHODS):
    y = y_pos[i]
    dagger = " ‡" if low_recall else ""

    # Left label: method name (recall)
    ax.text(-0.04, y, f"{label}{dagger}\n(recall = {recall:.2f})",
            ha="right", va="center", fontsize=9.5, color="#222222",
            transform=ax.get_yaxis_transform(), linespacing=1.3)

    if label == "Human query":
        ax.scatter(1.0, y, s=80, marker="D", color=color,
                   edgecolors="black", linewidths=1.2, zorder=5)
        ax.text(1.03, y, "1.00 (baseline)", ha="left", va="center",
                fontsize=9, color="#555555", style="italic",
                transform=ax.get_yaxis_transform())
    else:
        # CI bar
        ax.plot([wl_lo, wl_hi], [y, y], color=color, linewidth=2.5,
                solid_capstyle="round", zorder=3, alpha=0.80)
        for xc in [wl_lo, wl_hi]:
            ax.plot([xc, xc], [y - 0.14, y + 0.14], color=color,
                    linewidth=1.8, zorder=4)
        # Mean point
        marker = "s" if low_recall else "o"
        ax.scatter(wl_mean, y, s=60, marker=marker, color=color,
                   edgecolors="white", linewidths=0.9, zorder=5)
        # Right: numeric value (workload proportion)
        r_str = f"{wl_mean:.3f} [{wl_lo:.3f}, {wl_hi:.3f}]"
        ax.text(1.03, y, r_str, ha="left", va="center",
                fontsize=8.5, color="#333333",
                transform=ax.get_yaxis_transform())

ax.set_xlim(-0.05, 1.15)
ax.set_ylim(-1.3, 9.5)
ax.set_yticks([])
ax.set_xlabel("Relative screening workload  (human query = 1.00)", fontsize=11)
ax.set_xticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
ax.set_xticklabels(["0", "0.2", "0.4", "0.6", "0.8", "1.0\n(human)"], fontsize=9.5)
ax.xaxis.grid(True, linestyle="--", alpha=0.35, zorder=0)
ax.set_title("Figure 5  Screening Workload Relative to Human Query", loc="left",
             fontweight="bold", fontsize=12)

# Legend
legend_items = [
    mpatches.Patch(color="#5B7FA6", label="Human query (baseline)"),
    mpatches.Patch(color="#2E6FA3", label="Claude cut70"),
    mpatches.Patch(color="#D97B2B", label="Codex cut70"),
    mpatches.Patch(color="#3A9E52", label="Gemini cut70"),
    mpatches.Patch(color="#9B72B0", label="Elicit Question all ‡"),
    mpatches.Patch(color="#6A3D9A", label="Elicit Question include ‡"),
    mpatches.Patch(color="#E07B2A", label="OpenScholar deep ‡"),
    mpatches.Patch(color="#FBCBA0", label="OpenScholar normal ‡"),
    mpatches.Patch(color="#C9B8D8", label="Elicit Keyword all ‡"),
]
fig.legend(handles=legend_items, loc="lower center", ncol=3,
           bbox_to_anchor=(0.54, 0.00), frameon=False, fontsize=9,
           handlelength=1.2, handletextpad=0.5, columnspacing=1.0)

fig.text(0.54, -0.02,
         "‡ Recall substantially below human query; low workload reflects incomplete retrieval.",
         ha="center", va="bottom", fontsize=8, color="#666666", style="italic")

out = OUT_DIR / "figure5_workload_reduction_forest.png"
fig.savefig(out, dpi=300, bbox_inches="tight")
print(f"Saved: {out}")


