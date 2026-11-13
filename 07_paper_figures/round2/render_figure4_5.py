"""Second-revision Figure 4 (Stage 2 recall/NNR at cut70) and Figure 5 (relative screening workload).

Main analysis: harmonized Stage C, T2 pseudo-abstract, dense weight (alpha) 0.5, cut70, primary candidate sets.
Inputs (read only, all in this release):
  ../data/test24_eval/elicit24_points_gate1000_floor1000_20260511.csv   human query, Elicit, OpenScholar rows
  ../../stageC_harmonized/expected/per_sr_metrics_all.csv                LLM rows (arm T2, alpha 0.5, cut 70)
  ../../stageC_harmonized/expected/primary_tests_vs_human.csv            p values shown in Figure 4B
  ../../stageC_harmonized/expected/primary_reduction_search.csv          check of the Figure 5 LLM values
Outputs: output/Figure4_*.png|pdf, output/Figure5_*.png|pdf, output/Figure4_5_points_data.csv,
         output/Figure4_5_plotted_values.csv
CPU only; no network or model calls.
Display labels: the comparator stored as "OpenScholar" in the input CSV is labelled "Asta" (its current name).

Bootstrap procedures:
  comparator CIs (human query, Elicit, OpenScholar): one shared default_rng(42) stream in method order, as in
    ../scripts/figure4_v3_mean_ci_bar.py, so these CIs equal the historical figure;
  LLM CIs: a fresh default_rng(42) per series with integer resampling (10,000 resamples);
  Figure 5: paired bootstrap of (mean human NNR - mean method NNR) / mean human NNR with a fresh default_rng(42),
    as in ../scripts/reproduce_stage2_statistics.py.
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
REL = HERE.parents[1]
EXP = REL / "stageC_harmonized" / "expected"
OUT = HERE / "output"
OUT.mkdir(exist_ok=True)

P = pd.read_csv(REL / "07_paper_figures/data/test24_eval/elicit24_points_gate1000_floor1000_20260511.csv")
M = pd.read_csv(EXP / "per_sr_metrics_all.csv")
prim = M[(M.arm == "T2") & (M.alpha == 0.5) & (M.cut == 70)]
assert len(prim) == 72
TESTS = pd.read_csv(EXP / "primary_tests_vs_human.csv")
RED = pd.read_csv(EXP / "primary_reduction_search.csv").set_index("model")
plt.rcParams.update({"font.family": "Arial", "font.size": 10, "axes.labelsize": 11})

# comparator and human rows from the Test24 CSV; LLM rows from the harmonized analysis
llm = prim.assign(method=prim.model + " cut70")[["paper_id", "method", "recall", "keep", "tp", "gold_n", "nnr"]].rename(columns={"keep": "hits"})
FD = pd.concat([P[~P.method.str.contains("cut|unified")], llm], ignore_index=True)
FD.to_csv(OUT / "Figure4_5_points_data.csv", index=False)

# ---------------------------------------------------------------- Figure 4
METHODS = [("Human query", "#5B7FA6"), ("Elicit Keyword all", "#C9B8D8"), ("Elicit Question all", "#9B72B0"),
           ("Elicit Question include", "#6A3D9A"), ("OpenScholar normal", "#FBCBA0"), ("OpenScholar deep", "#E07B2A"),
           ("Claude cut70", "#2E6FA3"), ("Codex cut70", "#D97B2B"), ("Gemini cut70", "#3A9E52")]
RNG = np.random.default_rng(42)
N_BOOT = 10_000
JIT = 0.12
BAR = 0.55


def get_col(method, col):
    return FD[FD.method == method].drop_duplicates("paper_id")[col].replace([np.inf, -np.inf], np.nan).dropna().values


def bootstrap_ci(v):  # shared RNG stream, same call order as figure4_v3_mean_ci_bar.py
    v = v[np.isfinite(v)]
    b = RNG.choice(v, size=(N_BOOT, len(v)), replace=True).mean(axis=1)
    return v.mean(), np.percentile(b, 2.5), np.percentile(b, 97.5)


def boot_fresh(x):  # LLM series: fresh default_rng(42), integer resampling
    s = x[np.random.default_rng(42).integers(0, len(x), (N_BOOT, len(x)))].mean(axis=1)
    return x.mean(), *np.percentile(s, [2.5, 97.5])


X = np.arange(len(METHODS))
colors = [c for _, c in METHODS]
labels = [m for m, _ in METHODS]
rv = [get_col(m, "recall") for m in labels]
nv = [get_col(m, "nnr") for m in labels]
rs = np.array([bootstrap_ci(v) for v in rv])
ns = np.array([bootstrap_ci(v) for v in nv])
for i, m in enumerate(labels):
    if m.endswith("cut70"):
        rs[i], ns[i] = boot_fresh(rv[i]), boot_fresh(nv[i])
vals = []
for i, m in enumerate(labels):
    for metric, s in [("recall", rs[i]), ("nnr", ns[i])]:
        vals.append(dict(figure="4", method=m, metric=metric, n=len(rv[i] if metric == "recall" else nv[i]),
                         mean=s[0], ci_low=s[1], ci_high=s[2]))

fig, (ax_r, ax_n) = plt.subplots(1, 2, figsize=(15, 6))
fig.subplots_adjust(left=0.06, right=0.98, top=0.93, bottom=0.24, wspace=0.28)
for ax, v_all, st, ttl in [(ax_r, rv, rs, "A  Stage 2 Recall"), (ax_n, nv, ns, "B  Stage 2 NNR")]:
    ax.bar(X, st[:, 0], width=BAR, color=colors, alpha=0.75, edgecolor="white", linewidth=0.8, zorder=3)
    ax.errorbar(X, st[:, 0], yerr=[st[:, 0] - st[:, 1], st[:, 2] - st[:, 0]], fmt="none", color="#222222",
                capsize=5, capthick=1.4, linewidth=1.4, zorder=4)
    for xi, (v, col) in enumerate(zip(v_all, colors)):
        ax.scatter(xi + RNG.uniform(-JIT, JIT, size=len(v)), v, s=28, color=col, edgecolors="black", linewidths=0.8, zorder=5, alpha=0.9)
        ax.plot([xi - BAR * 0.42, xi + BAR * 0.42], [np.median(v)] * 2, color="black", linewidth=2.2, zorder=6, solid_capstyle="butt")
    ax.axhline(st[0, 0], color=colors[0], linestyle="--", linewidth=1.2, alpha=0.6)
    ax.set_xticks(X)
    ax.set_xticklabels([lab.replace("OpenScholar", "Asta") for lab in labels], fontsize=9.5, rotation=15, ha="right")
    ax.set_title(ttl, loc="left", fontweight="bold", fontsize=12)
    ax.yaxis.grid(True, linestyle="--", alpha=0.35, zorder=0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
ax_r.set_ylabel("Recall")
ax_r.set_ylim(0, 1.05)
ax_n.set_yscale("log")
ax_n.set_ylabel("NNR — Mean ± 95% CI (log scale)")
T = TESTS[TESTS.metric == "nnr"].set_index("model")
for i, (xi, mdl) in enumerate([(6, "Claude"), (7, "Codex"), (8, "Gemini")]):
    y = ns[0, 2] * [2.2, 3.8, 6.5][i]
    ax_n.plot([0, 0, xi, xi], [y / 1.55, y, y, y / 1.55], color="#333333", linewidth=1.0, clip_on=False, zorder=6)
    ax_n.text(xi / 2, y * 1.08, f"p = {T.loc[mdl, 'p_two_sided']:.3f} (Holm {T.loc[mdl, 'p_two_sided_holm_six']:.2f})",
              ha="center", va="bottom", fontsize=8.5, color="#333333")
ax_n.set_ylim(top=ns[0, 2] * 6.5 * 3.5)
items = [mpatches.Patch(color=c, label=m.replace("OpenScholar", "Asta"), alpha=0.75) for m, c in METHODS] + [plt.Line2D([], [], color="black", linewidth=2.2, label="Median")]
fig.legend(handles=items, loc="lower center", ncol=5, bbox_to_anchor=(0.5, 0.01), frameon=False, fontsize=9.5,
           handlelength=1.3, handletextpad=0.5, columnspacing=1.1)
for ext in ["png", "pdf"]:
    fig.savefig(OUT / f"Figure4_stage2_mean_ci_bar_T2main.{ext}", dpi=300, bbox_inches="tight")
plt.close(fig)


# ---------------------------------------------------------------- Figure 5
def bootstrap_rsearch(h, m):  # as in reproduce_stage2_statistics.py
    r = np.random.default_rng(42)
    idx = r.integers(0, len(h), size=(10_000, len(h)))
    hm, mm = h[idx].mean(1), m[idx].mean(1)
    return np.percentile((hm - mm) / hm, [2.5, 97.5])


hum = FD[FD.method == "Human query"].drop_duplicates("paper_id").set_index("paper_id")
f5 = {}
for m in labels[1:]:
    j = hum[["nnr"]].join(FD[FD.method == m].drop_duplicates("paper_id").set_index("paper_id")[["nnr"]], lsuffix="_h", rsuffix="_m").dropna()
    h, mm = j.nnr_h.to_numpy(float), j.nnr_m.to_numpy(float)
    lo, hi = bootstrap_rsearch(h, mm)
    r = (h.mean() - mm.mean()) / h.mean()
    f5[m] = (r, lo, hi, get_col(m, "recall").mean())
    vals.append(dict(figure="5", method=m, metric="reduction_search", n=len(h), mean=r, ci_low=lo, ci_high=hi))
    if m.endswith("cut70"):  # must equal the harmonized statistics (stageC_harmonized/code/statistics.py)
        e = RED.loc[m.split()[0]]
        assert max(abs(r - e.reduction_search), abs(lo - e.ci_low), abs(hi - e.ci_high)) < 1e-9, (m, r, lo, hi, e.to_dict())
V = pd.DataFrame(vals)
V["relative_workload"] = np.where(V.figure == "5", 1 - V["mean"], np.nan)
V.to_csv(OUT / "Figure4_5_plotted_values.csv", index=False)

col = dict(METHODS)
high = sorted(["Claude cut70", "Codex cut70", "Gemini cut70", "Human query"], key=lambda m: -(f5[m][3] if m in f5 else hum.recall.mean()))
low = ["Elicit Question all", "Elicit Question include", "OpenScholar deep", "OpenScholar normal", "Elicit Keyword all"]
rows5 = []
for m in high + low:
    lab = m.replace("Question include", "Question\ninclude").replace("OpenScholar", "Asta")
    if m == "Human query":
        rows5.append((lab, 1, 1, 1, hum.recall.mean(), col[m], False))
    else:
        r, lo, hi, rec = f5[m]
        rows5.append((lab, 1 - r, 1 - hi, 1 - lo, rec, col[m], m in low))
y_pos = [8.0, 7.0, 6.0, 5.0, 3.5, 2.5, 1.5, 0.5, -0.5]
plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False})
fig, ax = plt.subplots(figsize=(11, 7))
fig.subplots_adjust(left=0.30, right=0.78, top=0.93, bottom=0.18)
ax.axhline(4.25, color="#aaaaaa", linewidth=0.9, linestyle="--", alpha=0.7)
ax.axvline(1.0, color="#5B7FA6", linewidth=1.3, linestyle="--", alpha=0.65)
for (lab, wm, wl, wh, rec, c, lowr), y in zip(rows5, y_pos):
    ax.text(-0.04, y, f"{lab}{' ‡' if lowr else ''}\n(recall = {rec:.2f})", ha="right", va="center", fontsize=9.5,
            color="#222222", transform=ax.get_yaxis_transform(), linespacing=1.3)
    if lab == "Human query":
        ax.scatter(1.0, y, s=80, marker="D", color=c, edgecolors="black", linewidths=1.2, zorder=5)
        ax.text(1.03, y, "1.00 (baseline)", ha="left", va="center", fontsize=9, color="#555555", style="italic", transform=ax.get_yaxis_transform())
        continue
    ax.plot([wl, wh], [y, y], color=c, linewidth=2.5, solid_capstyle="round", zorder=3, alpha=0.8)
    for xc in [wl, wh]:
        ax.plot([xc, xc], [y - 0.14, y + 0.14], color=c, linewidth=1.8, zorder=4)
    ax.scatter(wm, y, s=60, marker="s" if lowr else "o", color=c, edgecolors="white", linewidths=0.9, zorder=5)
    ax.text(1.03, y, f"{wm:.3f} [{wl:.3f}, {wh:.3f}]", ha="left", va="center", fontsize=8.5, color="#333333", transform=ax.get_yaxis_transform())
ax.set_xlim(-0.05, 1.15)
ax.set_ylim(-1.3, 9.5)
ax.set_yticks([])
ax.set_xlabel("Relative screening workload  (human query = 1.00)", fontsize=11)
ax.set_xticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
ax.set_xticklabels(["0", "0.2", "0.4", "0.6", "0.8", "1.0\n(human)"], fontsize=9.5)
ax.xaxis.grid(True, linestyle="--", alpha=0.35, zorder=0)
ax.set_title("Screening Workload Relative to Human Query", loc="left", fontweight="bold", fontsize=12)
leg = [mpatches.Patch(color=col["Human query"], label="Human query (baseline)")] + \
      [mpatches.Patch(color=col[m], label=m) for m in high if m != "Human query"] + [mpatches.Patch(color=col[m], label=m.replace("OpenScholar", "Asta") + " ‡") for m in low]
fig.legend(handles=leg, loc="lower center", ncol=3, bbox_to_anchor=(0.54, 0.0), frameon=False, fontsize=9, handlelength=1.2, handletextpad=0.5, columnspacing=1.0)
fig.text(0.54, -0.02, "‡ Recall substantially below human query; low workload reflects incomplete retrieval.", ha="center", va="bottom", fontsize=8, color="#666666", style="italic")
for ext in ["png", "pdf"]:
    fig.savefig(OUT / f"Figure5_relative_workload_T2main.{ext}", dpi=300, bbox_inches="tight")
plt.close(fig)
print(V.round(4).to_string(index=False))
