"""Step 4: compare reproduced tables with the reported values in expected/.

Integers, booleans and hashes must match exactly; floating-point values within 1e-12 (relative to max(1, |x|)).
Exit status 0 only if every table matches.
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path
import numpy as np
import pandas as pd

PKG = Path(__file__).resolve().parent.parent
SCEN = {"primary": "per_sr_metrics_all.csv", "sens_codex_41641734_4b8f": "per_sr_metrics_codex_4b8f.csv",
        "sens_gemini_41770755_inferred714": "per_sr_metrics_gemini_inferred714.csv"}
KEYS = {"all_condition_summary.csv": ["scenario", "model", "arm", "alpha", "cut", "metric"],
        "primary_tests_vs_human.csv": ["model", "metric"], "primary_reduction_search.csv": ["model"],
        "paired_arm_contrasts_alpha05_cut70.csv": ["model", "population", "contrast", "metric"],
        "c6_retention_categories_per_sr.csv": ["model", "paper_id"], "c6_retention_category_counts.csv": ["model", "category"],
        "c1_nnr_reanalysis_unified.csv": ["source", "model"]}
PER_SR_KEYS = ["model", "paper_id", "arm", "alpha", "cut"]


def same(got, exp, keys, label):
    got, exp = got.copy(), exp.copy()
    for d in (got, exp):
        for k in keys:
            d[k] = d[k].astype(float).round(6) if k in ("alpha", "cut") else d[k].astype(str)
    m = exp.merge(got, on=keys, how="left", suffixes=("_e", "_g"), indicator=True)
    bad = []
    if (m._merge != "both").any():
        bad.append(f"{int((m._merge != 'both').sum())} expected rows missing")
    cols = [c for c in exp.columns if c not in keys and c in got.columns]
    for c in cols:
        e, g = m[c + "_e"], m[c + "_g"]
        if pd.api.types.is_float_dtype(e) or pd.api.types.is_float_dtype(g):
            e, g = e.astype(float).to_numpy(), g.astype(float).to_numpy()
            ok = (np.isnan(e) & np.isnan(g)) | (np.abs(e - g) <= 1e-12 * np.maximum(1, np.abs(e)))
        else:
            ok = (e.astype(str) == g.astype(str)).to_numpy()
        if not ok.all():
            bad.append(f"{c}: {int((~ok).sum())} rows differ")
    print(f"{'OK ' if not bad else 'NG '} {label}: {len(exp)} expected rows, {len(cols)} columns" + ("" if not bad else " | " + "; ".join(bad)))
    return not bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--metrics", required=True, help="output folder of replay_metrics.py")
    ap.add_argument("--stats", required=True, help="output folder of statistics.py")
    a = ap.parse_args()
    M, S, E = Path(a.metrics), Path(a.stats), PKG / "expected"
    rd = lambda p: pd.read_csv(p, dtype={"paper_id": str})
    ok = True
    ind = rd(E / "per_sr_metrics_7cuts_independent.csv").rename(columns={"n": "n_scored"})
    for s, f in SCEN.items():
        got = rd(M / f"per_sr_metrics_{s}.csv")
        ok &= same(got, rd(E / f), PER_SR_KEYS, f"per_sr_metrics_{s} vs {f} (cuts 0/30/50/70)")
        ok &= same(got, ind[ind.scenario == s].drop(columns="scenario"), PER_SR_KEYS,
                   f"per_sr_metrics_{s} vs per_sr_metrics_7cuts_independent (all cuts)")
    for f, keys in KEYS.items():
        ok &= same(rd(S / f), rd(E / f), keys, f)
    print("ALL MATCH" if ok else "MISMATCH")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
