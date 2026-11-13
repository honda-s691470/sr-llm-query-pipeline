"""Step 3 (CPU): summary statistics reported for the harmonized Stage C analysis.

Inputs: per_sr_metrics_<scenario>.csv from replay_metrics.py and the public per-review comparator file
07_paper_figures/data/test24_eval/elicit24_points_gate1000_floor1000_20260511.csv (human-query Recall/NNR).
Main condition: T2, alpha 0.5, cut70. Tests: paired sign-flip permutation (100,000; seed 42), two-sided primary,
one-sided for reference; Holm over the six model-by-outcome tests. Bootstrap CIs: 10,000 review resamples, seed 42.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

SCEN = ["primary", "sens_codex_41641734_4b8f", "sens_gemini_41770755_inferred714"]


def boot(x, ratio=False):
    x = np.asarray(x, float)
    x = x[np.isfinite(x).all(axis=1)] if ratio else x[np.isfinite(x)]
    if len(x) == 0:
        return (np.nan, np.nan)
    rng = np.random.default_rng(42)
    sample = x[rng.integers(0, len(x), (10000, len(x)))].mean(axis=1)
    vals = 1 - sample[:, 0] / sample[:, 1] if ratio else sample
    return np.quantile(vals, [.025, .975])


def tests(d):
    d = np.asarray(d, float); d = d[np.isfinite(d)]
    observed = d.mean(); rng = np.random.default_rng(42)
    null = (rng.choice([-1, 1], size=(100000, len(d))) * d).mean(axis=1)
    return ((int((null >= observed).sum()) + 1) / 100001, (int((np.abs(null) >= abs(observed)).sum()) + 1) / 100001)


def holm(p):
    p = np.asarray(p); ix = np.argsort(p); v = np.maximum.accumulate(p[ix] * (len(p) - np.arange(len(p))))
    out = np.empty(len(p)); out[ix] = np.minimum(v, 1); return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--metrics", required=True, help="folder with per_sr_metrics_<scenario>.csv")
    ap.add_argument("--public-root", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    M, out = Path(a.metrics), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    pts = pd.read_csv(Path(a.public_root) / "07_paper_figures/data/test24_eval/elicit24_points_gate1000_floor1000_20260511.csv")
    human = pts[pts.method == "Human query"].drop_duplicates("paper_id").set_index("paper_id")
    sc = {s: pd.read_csv(M / f"per_sr_metrics_{s}.csv", dtype={"paper_id": str}) for s in SCEN}
    sc = {"primary": sc["primary"], "codex_4b8f": sc["sens_codex_41641734_4b8f"], "gemini_inferred714": sc["sens_gemini_41770755_inferred714"]}
    ids = sorted(sc["primary"].paper_id.unique()); assert len(ids) == 24
    # both alternatives together: Codex 41641734 4b8f and Gemini 41770755 inferred714
    sc["both_alternatives"] = pd.concat([sc["primary"][sc["primary"].model == "Claude"],
                                         sc["codex_4b8f"][lambda d: d.model == "Codex"],
                                         sc["gemini_inferred714"][lambda d: d.model == "Gemini"]], ignore_index=True)
    # all-condition means / medians / bootstrap CIs
    summ = []
    for s, d in sc.items():
        for (model, arm, alpha, cut), g in d.groupby(["model", "arm", "alpha", "cut"]):
            for metric in ["recall", "nnr"]:
                x = g[metric].dropna().to_numpy(); lo, hi = boot(x)
                summ.append(dict(scenario=s, model=model, arm=arm, alpha=alpha, cut=cut, metric=metric, n=len(x),
                                 mean=x.mean(), median=np.median(x), ci_low=lo, ci_high=hi))
    pd.DataFrame(summ).to_csv(out / "all_condition_summary.csv", index=False, float_format="%.16g", lineterminator="\n")
    primary = sc["primary"]
    main_ = primary[(primary.arm == "T2") & (primary.alpha == .5) & (primary.cut == 70)].copy()
    big = human[human.hits >= 14865].index; assert len(big) == 4
    stats, red = [], []
    for model, g in main_.groupby("model"):
        g = g.set_index("paper_id").reindex(ids); h = human.reindex(ids)
        for metric in ["recall", "nnr"]:
            pair = pd.DataFrame({"new": g[metric], "human": h[metric]}).dropna()
            diff = (pair.new - pair.human) if metric == "recall" else (pair.human - pair.new)
            p1, p2 = tests(diff); lo, hi = boot(diff)
            stats.append(dict(model=model, metric=metric, n=len(pair), mean_improvement=diff.mean(), improvement_ci_low=lo,
                              improvement_ci_high=hi, p_one_sided=p1, p_two_sided=p2))
        pair = pd.DataFrame({"new": g.nnr, "human": h.nnr}).dropna()
        lo, hi = boot(pair[["new", "human"]].to_numpy(), ratio=True)
        ratio = pair.new / pair.human
        red.append(dict(model=model, n=len(pair), reduction_search=1 - pair.new.mean() / pair.human.mean(), ci_low=lo, ci_high=hi,
                        median_individual_reduction=float((1 - ratio).median()),
                        geometric_nnr_ratio=float(np.exp(np.log(ratio[ratio > 0]).mean())),
                        wins=int((pair.new < pair.human).sum()), ties=int((pair.new == pair.human).sum()),
                        losses=int((pair.new > pair.human).sum())))
    stats = pd.DataFrame(stats)
    stats["p_two_sided_holm_six"] = holm(stats.p_two_sided); stats["p_one_sided_holm_six"] = holm(stats.p_one_sided)
    stats.to_csv(out / "primary_tests_vs_human.csv", index=False, float_format="%.16g", lineterminator="\n")
    pd.DataFrame(red).to_csv(out / "primary_reduction_search.csv", index=False, float_format="%.16g", lineterminator="\n")
    # Supplementary NNR summaries: legacy Run1 (public points file, "<Model> cut70") and new main (T2, alpha .5, cut70)
    c1 = []
    for src in ["legacy_run1", "new_main_T2"]:
        for model in ["Claude", "Codex", "Gemini"]:
            m = (pts[pts.method == f"{model} cut70"].drop_duplicates("paper_id").set_index("paper_id") if src == "legacy_run1"
                 else main_[main_.model == model].set_index("paper_id"))
            x = human[["nnr", "recall"]].join(m[["nnr", "recall"]], lsuffix="_h", rsuffix="_m").dropna()
            diff, ld = (x.nnr_h - x.nnr_m).to_numpy(), np.log(x.nnr_h / x.nnr_m).to_numpy()
            rng = np.random.default_rng(42)
            null = (rng.choice([-1.0, 1.0], size=(100000, len(diff))) * diff).mean(1)
            rng = np.random.default_rng(42)
            idx = rng.integers(0, len(ld), size=(10000, len(ld)))
            gci = 1 - np.exp(-np.percentile(ld[idx].mean(1), [2.5, 97.5]))
            xs = x.drop(big)
            c1.append({"source": src, "model": model, "n": len(x), "median_nnr_human": x.nnr_h.median(), "median_nnr_model": x.nnr_m.median(),
                       "mean_nnr_human": x.nnr_h.mean(), "mean_nnr_model": x.nnr_m.mean(),
                       "reviews_model_lower_nnr": int((diff > 0).sum()), "rsearch_ratio_of_means": 1 - x.nnr_m.mean() / x.nnr_h.mean(),
                       "rsearch_ratio_of_means_excl4": 1 - xs.nnr_m.mean() / xs.nnr_h.mean(),
                       "rsearch_geometric": 1 - np.exp(-ld.mean()), "rsearch_geometric_ci_lo": gci[0], "rsearch_geometric_ci_hi": gci[1],
                       "perm_p_one_sided": ((null >= diff.mean()).sum() + 1) / 100001,
                       "perm_p_two_sided": ((np.abs(null) >= abs(diff.mean())).sum() + 1) / 100001,
                       "wilcoxon_log_nnr_p_two_sided": wilcoxon(ld).pvalue,
                       "wilcoxon_recall_p_two_sided": wilcoxon(x.recall_m - x.recall_h).pvalue,
                       "mean_recall_human": x.recall_h.mean(), "mean_recall_model": x.recall_m.mean()})
    pd.DataFrame(c1).to_csv(out / "c1_nnr_reanalysis_unified.csv", index=False, float_format="%.16g", lineterminator="\n")
    # paired arm contrasts at alpha .5, cut70
    con = []
    p = primary[(primary.alpha == .5) & (primary.cut == 70)]
    for model, g in p.groupby("model"):
        for population in ["all24", "ranking_only"]:
            q = g if population == "all24" else g[~g.gate]
            for x1, x2 in [("T1", "T2"), ("T2", "LLM"), ("T1", "LLM")]:
                for metric in ["recall", "nnr"]:
                    x = q.pivot(index="paper_id", columns="arm", values=metric)[[x1, x2]].dropna(); delta = x[x1] - x[x2]; lo, hi = boot(delta)
                    con.append(dict(model=model, population=population, contrast=f"{x1}-{x2}", metric=metric, n=len(delta),
                                    mean_difference=delta.mean(), ci_low=lo, ci_high=hi, positive=int((delta > 0).sum()),
                                    zero=int((delta == 0).sum()), negative=int((delta < 0).sum())))
    pd.DataFrame(con).to_csv(out / "paired_arm_contrasts_alpha05_cut70.csv", index=False, float_format="%.16g", lineterminator="\n")
    # Retention categories
    cat = main_.copy()
    cat["category"] = np.where(cat.gate, "pass_through", np.where(np.rint(cat.n_scored * .30) >= 1000, "full70", "floor1000"))
    cat[["model", "paper_id", "stageB_n", "n_scored", "keep", "category"]].to_csv(out / "c6_retention_categories_per_sr.csv", index=False, lineterminator="\n")
    cat.groupby(["model", "category"]).size().rename("n").reset_index().to_csv(out / "c6_retention_category_counts.csv", index=False, lineterminator="\n")
    pd.set_option("display.width", 200)
    print(stats.round(4).to_string(index=False)); print(pd.DataFrame(red).round(4).to_string(index=False))


if __name__ == "__main__":
    main()
