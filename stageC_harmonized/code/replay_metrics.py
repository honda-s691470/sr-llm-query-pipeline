"""Step 2 (CPU): score components -> Final -> order -> retained sets -> per-review Recall/NNR.

--scores is either the deposited data/scores/ folder or the output of score_stagec.py.
Final, anchors and order are recomputed from dense, BM25 and anchor-similarity components and must equal
the stored Final exactly. Kept sets are fixed before gold is read (gold: public 05_test_data/*/gold_pmids.json).
"""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
sys.path.insert(0, str(HERE))
import numpy as np
import pandas as pd
import stagec_core as core

ARMS = ["T1", "T2", "LLM"]
ALPHAS = [0, 0.25, 0.5, 0.75, 1]
CUTS = [0, 30, 50, 60, 70, 80, 90]
SCENARIOS = ["primary", "sens_codex_41641734_4b8f", "sens_gemini_41770755_inferred714"]


def orders_for(c, scores):
    """{(arm, alpha): order} for a ranked condition, verifying Final from components."""
    with np.load(scores / f"{c.condition_id}.npz", allow_pickle=False) as z:
        pmids = z["pmids"].astype(str).tolist()
        out = {}
        for arm in ARMS:
            dense, bm25 = z[f"{arm}_dense"], z[f"{arm}_bm25"]
            for a in ALPHAS:
                k = f"{arm}_a{a}"
                sq = np.float32(a) * dense.astype(np.float32) + np.float32(1 - a) * bm25.astype(np.float32)
                pos = core._select_anchor_idx(sq, pmids, top=True)
                neg = core._select_anchor_idx(sq, pmids, top=False)
                assert list(pos) == z[f"{k}_pos_anchor"].tolist() and list(neg) == z[f"{k}_neg_anchor"].tolist(), (c.condition_id, k)
                final = (core.rank_percentile_desc(sq) + core.rank_percentile_desc(z[f"{k}_s_pos_mean"])
                         - core.rank_percentile_desc(z[f"{k}_s_neg_mean"])).astype(np.float32)
                assert np.array_equal(final, z[f"{k}_final"]), (c.condition_id, k)
                out[(arm, a)] = np.argsort(-final, kind="mergesort")
    return pmids, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scores", default=str(PKG / "data/scores"))
    ap.add_argument("--public-root", required=True, help="repository root containing 05_test_data/")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    scores, root, out = Path(a.scores), Path(a.public_root), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    man = pd.read_csv(PKG / "data/candidate_manifest.csv", dtype={"paper_id": str})
    # phase 1: kept sets (no gold)
    kept = {}
    for _, c in man.iterrows():
        pmids = json.loads((PKG / f"data/candidates/{c.condition_id}.json").read_text(encoding="utf-8"))["pmids"]
        n = len(pmids)
        orders = None if c.gate else orders_for(c, scores)
        if orders:
            assert orders[0] == pmids
        for arm in ARMS:
            for alpha in ALPHAS:
                for cut in CUTS:
                    k = core.keep_count(n, cut, bool(c.gate))
                    ks = pmids if c.gate else [pmids[i] for i in orders[1][(arm, alpha)][:k]]
                    kept[(c.condition_id, arm, alpha, cut)] = (n, k, ks)
    digest = hashlib.sha256(json.dumps({"|".join(map(str, key)): v[2] for key, v in sorted(kept.items())},
                                       separators=(",", ":")).encode()).hexdigest()
    (out / "kept_sets_before_gold.json").write_text(json.dumps({"kept_sets_sha256": digest, "units": len(kept)}) + "\n", encoding="utf-8")
    # phase 2: gold
    gold = {}
    for pid, dom in man[["paper_id", "domain"]].drop_duplicates().itertuples(index=False):
        g = json.loads((root / "05_test_data" / dom / pid / "gold_pmids.json").read_text(encoding="utf-8"))["gold_pmids"]
        gold[pid] = {str(x).strip() for x in g}
    for s in SCENARIOS:
        rows = []
        for _, c in man[man.scenarios.str.split(";").apply(lambda x: s in x)].iterrows():
            for arm in ARMS:
                for alpha in ALPHAS:
                    for cut in CUTS:
                        n, k, ks = kept[(c.condition_id, arm, alpha, cut)]
                        tp = len(gold[c.paper_id].intersection(ks))
                        rows.append(dict(model=c.model, paper_id=c.paper_id, arm=arm, alpha=float(alpha), cut=cut, gate=bool(c.gate),
                                         stageB_n=int(c.gate_count), n_scored=n, keep=k, tp=tp, gold_n=len(gold[c.paper_id]),
                                         recall=tp / len(gold[c.paper_id]), nnr=(k / tp if tp else np.nan),
                                         candidate_hash=c.candidate_sha256, condition_id=c.condition_id))
        d = pd.DataFrame(rows).sort_values(["model", "paper_id", "arm", "alpha", "cut"])
        assert len(d) == 3 * 24 * 3 * 5 * 7, (s, len(d))
        d.to_csv(out / f"per_sr_metrics_{s}.csv", index=False, float_format="%.16g", lineterminator="\n")
    print("kept sets", len(kept), digest)


if __name__ == "__main__":
    main()
