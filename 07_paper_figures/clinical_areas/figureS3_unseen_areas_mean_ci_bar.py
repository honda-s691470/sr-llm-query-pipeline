"""Figure S3: Stage 1 Recall and NNR — Rheumatology + Oncology only.

Both panels: mean ± 95% CI bootstrap bars with individual SR dots (black outline).

Inputs are release CSVs and the accompanying clinical-area classification CSV.
Use --release-root when running outside the public repository.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path
import argparse

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--release-root", type=Path, help="Public repository root")
parser.add_argument("--output-dir", type=Path, default=Path.cwd() / "figureS3_output")
args = parser.parse_args()
release_root = args.release_root
if release_root is None:
    release_root = next((p for p in Path(__file__).resolve().parents
                         if (p / "07_paper_figures/data/test24_eval").is_dir()), None)
if release_root is None:
    parser.error("Cannot locate the public repository; supply --release-root.")
DATA_DIR = release_root / "07_paper_figures/data/test24_eval"
OUT_DIR = args.output_dir
OUT_DIR.mkdir(parents=True, exist_ok=True)

df_all = pd.read_csv(DATA_DIR / "all_test_metrics.csv")
df_wo  = pd.read_csv(DATA_DIR / "test24_without_laws_all_providers.csv")

TEST24 = set(df_wo[df_wo["provider"] == "claude"]["paper_folder"].unique())

# Clinical areas from the rule-based reclassification
_rc = pd.read_csv(Path(__file__).resolve().with_name("clinical_areas_35reviews.csv"), dtype=str)
_new = dict(zip(_rc.paper_id, _rc.new_domain))
novel_papers = {p for p in TEST24 if _new.get(p[:8]) in {"Rheumatology", "Oncology"}}

print(f"Novel domain papers: {len(novel_papers)}")

def get_series(provider, condition, source_df):
    sub = source_df[(source_df["provider"] == provider) &
                    (source_df["condition"] == condition) &
                    (source_df["paper_folder"].isin(novel_papers))].copy()
    sub = sub.drop_duplicates(subset="paper_folder", keep="last")
    sub["nnr"] = sub.apply(
        lambda r: r["total_hits"] / r["hit_gold_count"]
        if r["hit_gold_count"] > 0 else np.nan, axis=1)
    return sub[["paper_folder", "recall", "nnr"]].set_index("paper_folder")

human = get_series("human",  "human_reference",    df_all)
cl_wo = get_series("claude", "without_laws",        df_wo)
co_wo = get_series("codex",  "without_laws",        df_wo)
ge_wo = get_series("gemini", "without_laws",        df_wo)
cl_wi = get_series("claude", "with_laws_test_eval", df_all)
co_wi = get_series("codex",  "with_laws_test_eval", df_all)
ge_wi = get_series("gemini", "with_laws_test_eval", df_all)

GROUPS = [
    ("Human",          human,  "#5B7FA6"),
    ("Claude\nw/o RB", cl_wo,  "#A8C5DA"),
    ("Claude\nw/ RB",  cl_wi,  "#2E6FA3"),
    ("Codex\nw/o RB",  co_wo,  "#F2C18D"),
    ("Codex\nw/ RB",   co_wi,  "#D97B2B"),
    ("Gemini\nw/o RB", ge_wo,  "#A8D5A2"),
    ("Gemini\nw/ RB",  ge_wi,  "#3A9E52"),
]

RNG    = np.random.default_rng(42)
N_BOOT = 10_000
JIT    = 0.12
BAR    = 0.55

def bootstrap_ci(vals: np.ndarray) -> tuple[float, float, float]:
    v = vals[np.isfinite(vals)]
    if len(v) == 0:
        return np.nan, np.nan, np.nan
    boots = RNG.choice(v, size=(N_BOOT, len(v)), replace=True).mean(axis=1)
    return v.mean(), np.percentile(boots, 2.5), np.percentile(boots, 97.5)

plt.rcParams.update({
    "font.family": "Arial",
    "font.size":   10,
    "axes.labelsize": 11,
    "axes.spines.top": False,
    "axes.spines.right": False,
})

fig, (ax_r, ax_n) = plt.subplots(1, 2, figsize=(15, 6))
fig.subplots_adjust(left=0.06, right=0.98, top=0.93, bottom=0.24, wspace=0.28)

X      = np.arange(len(GROUPS))
colors = [c for _, _, c in GROUPS]
labels = [lb for lb, _, _ in GROUPS]

recall_vals = [grp["recall"].dropna().values for _, grp, _ in GROUPS]
nnr_vals    = [grp["nnr"].replace([np.inf, -np.inf], np.nan).dropna().values
               for _, grp, _ in GROUPS]

recall_stats = [bootstrap_ci(v) for v in recall_vals]
nnr_stats    = [bootstrap_ci(v) for v in nnr_vals]

r_mean = np.array([s[0] for s in recall_stats])
r_lo   = np.array([s[1] for s in recall_stats])
r_hi   = np.array([s[2] for s in recall_stats])

n_mean = np.array([s[0] for s in nnr_stats])
n_lo   = np.array([s[1] for s in nnr_stats])
n_hi   = np.array([s[2] for s in nnr_stats])

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
ax_r.set_xticks(X); ax_r.set_xticklabels(labels, fontsize=9.5)
ax_r.set_ylabel("Recall"); ax_r.set_ylim(0, 1.05)
ax_r.set_title("A  Stage 1 Recall — Areas Without Training Reviews (Rheumatology + Oncology)",
               loc="left", fontweight="bold", fontsize=12)
ax_r.yaxis.grid(True, linestyle="--", alpha=0.35, zorder=0)

# ── Panel B: NNR mean±CI bar (log scale) ──────────────────────────────────────
ax_n.bar(X, n_mean, width=BAR, color=colors, alpha=0.75,
         edgecolor="white", linewidth=0.8, zorder=3)
ax_n.errorbar(X, n_mean,
              yerr=[n_mean - n_lo, n_hi - n_mean],
              fmt="none", color="#222222", capsize=5, capthick=1.4,
              linewidth=1.4, zorder=4)

for xi, (vals, color) in enumerate(zip(nnr_vals, colors)):
    jitter = RNG.uniform(-JIT, JIT, size=len(vals))
    ax_n.scatter(xi + jitter, vals, s=30, color=color,
                 edgecolors="black", linewidths=0.8, zorder=5, alpha=0.9)

ax_n.axhline(n_mean[0], color=colors[0], linestyle="--", linewidth=1.2, alpha=0.6)
ax_n.set_yscale("log")
ax_n.set_xticks(X); ax_n.set_xticklabels(labels, fontsize=9.5)
ax_n.set_ylabel("NNR — Mean ± 95% CI (log scale)")
ax_n.set_title("B  Stage 1 NNR — Areas Without Training Reviews (Rheumatology + Oncology)",
               loc="left", fontweight="bold", fontsize=12)
ax_n.yaxis.grid(True, linestyle="--", alpha=0.35, zorder=0)

# ── Legend ────────────────────────────────────────────────────────────────────
legend_items = [
    mpatches.Patch(color="#5B7FA6", label="Human query"),
    mpatches.Patch(color="#A8C5DA", label="Claude  w/o Rulebook"),
    mpatches.Patch(color="#2E6FA3", label="Claude  w/ Rulebook"),
    mpatches.Patch(color="#F2C18D", label="Codex  w/o Rulebook"),
    mpatches.Patch(color="#D97B2B", label="Codex  w/ Rulebook"),
    mpatches.Patch(color="#A8D5A2", label="Gemini  w/o Rulebook"),
    mpatches.Patch(color="#3A9E52", label="Gemini  w/ Rulebook"),
]
fig.legend(handles=legend_items, loc="lower center", ncol=4,
           bbox_to_anchor=(0.5, 0.01), frameon=False, fontsize=10,
           handlelength=1.4, handletextpad=0.5, columnspacing=1.4)

out = OUT_DIR / "figureS3_unseen_areas_mean_ci_bar.png"
fig.savefig(out, dpi=300, bbox_inches="tight")
print(f"Saved: {out}")

print("\nRecall mean / 95% CI per group:")
for (label, _, _), m, lo, hi in zip(GROUPS, r_mean, r_lo, r_hi):
    print(f"  {label.replace(chr(10), ' '):<22} mean={m:.3f}  [{lo:.3f}-{hi:.3f}]")
print("\nNNR mean / 95% CI per group:")
for (label, _, _), m, lo, hi in zip(GROUPS, n_mean, n_lo, n_hi):
    print(f"  {label.replace(chr(10), ' '):<22} mean={m:8.1f}  [{lo:8.1f}-{hi:8.1f}]")
