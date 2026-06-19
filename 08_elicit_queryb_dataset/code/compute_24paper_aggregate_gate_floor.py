"""
Compute 24-paper aggregate (Recall, NNR, F1) for Elicit and LLM cut0/30/50/70/unified.
Applies gate=1000, floor=1000 logic consistently:
  - stage_b_hits <= 1000: passthrough (no cut)
  - stage_b_hits > 1000: kept_n = max(1000, round(hits * keep_frac))

Data sources:
  - Original 12 papers: allpapers_recall/nnr_points_..._20260505.csv (pre-computed correctly)
  - Missing 9 + new 3 papers: posthoc CSV + stage C JSONL files
  - Elicit: elicit_queryB_list_papers.csv (DOI-based recall, no gate/floor, 24 test papers)
"""
import json
import glob
import csv as csv_mod
import os
import pandas as pd
import numpy as np

# ── Paths ───────────────────────────────────────────────────────────────────
from pathlib import Path
_ROOT = Path(__file__).resolve().parents[2]  # public_release/
ELICIT_DIR  = str(_ROOT / "08_elicit_queryb_dataset")
TEST_DIR    = str(_ROOT / "05_test_data")
DATA_DIR    = str(_ROOT / "04_data")
CACHE_BASE  = str(_ROOT / "06_exclusion_screening_pipeline" / "pubmed_cache")
RESULTS_DIR = str(_ROOT / "06_exclusion_screening_pipeline" / "results")

GATE = 1000
FLOOR = 1000

# ── 24-paper elicit set ──────────────────────────────────────────────────────
ELICIT_24 = sorted([
    d for d in os.listdir(ELICIT_DIR)
    if os.path.isdir(f"{ELICIT_DIR}/{d}") and d[0].isdigit()
])

# Original 12 papers (already computed with correct gate+floor by pipeline)
ORIG_12_CSV = (
    f"{ELICIT_DIR}/allpapers_recall_points_elicit_all_include_llm"
    "_cut0_30_50_70_gate1000_floor1000_20260505.csv"
)
ORIG_12_NNR_CSV = (
    f"{ELICIT_DIR}/allpapers_nnr_points_elicit_all_include_llm"
    "_cut0_30_50_70_gate1000_floor1000_20260505.csv"
)
# Note: unified also available in the _unified_ variant
ORIG_12_UNIFIED_CSV = (
    f"{ELICIT_DIR}/allpapers_recall_points_elicit_all_include_llm"
    "_cut0_30_50_70_unified_gate1000_floor1000_20260505.csv"
)
ORIG_12_UNIFIED_NNR_CSV = (
    f"{ELICIT_DIR}/allpapers_nnr_points_elicit_all_include_llm"
    "_cut0_30_50_70_unified_gate1000_floor1000_20260505.csv"
)


# ── Helpers ──────────────────────────────────────────────────────────────────
def gate_floor(stage_b_hits: int, cut_percent: float) -> int:
    if stage_b_hits <= GATE:
        return stage_b_hits
    keep_frac = max(0.0, 1.0 - cut_percent / 100.0)
    kept = max(FLOOR, int(round(stage_b_hits * keep_frac)))
    return min(stage_b_hits, kept)


def load_gold_n(paper_id: str) -> int | None:
    for domain in os.listdir(TEST_DIR):
        if not os.path.isdir(f"{TEST_DIR}/{domain}"):
            continue
        for fname in ["gold_pmids.json", "input_config.json"]:
            p = f"{TEST_DIR}/{domain}/{paper_id}/{fname}"
            if os.path.exists(p):
                obj = json.loads(open(p, encoding="utf-8-sig").read())
                g = obj.get("gold_pmids", [])
                if g:
                    return len(g)
        p = f"{DATA_DIR}/{domain}/{paper_id}/input_config.json"
        if os.path.exists(p):
            obj = json.loads(open(p, encoding="utf-8-sig").read())
            g = obj.get("gold_pmids", [])
            if g:
                return len(g)
    return None


def load_gold_set(paper_id: str) -> set[str]:
    for domain in os.listdir(TEST_DIR):
        if not os.path.isdir(f"{TEST_DIR}/{domain}"):
            continue
        for fname in ["gold_pmids.json", "input_config.json"]:
            p = f"{TEST_DIR}/{domain}/{paper_id}/{fname}"
            if os.path.exists(p):
                obj = json.loads(open(p, encoding="utf-8-sig").read())
                g = obj.get("gold_pmids", [])
                if g:
                    return {str(x) for x in g}
        p = f"{DATA_DIR}/{domain}/{paper_id}/input_config.json"
        if os.path.exists(p):
            obj = json.loads(open(p, encoding="utf-8-sig").read())
            g = obj.get("gold_pmids", [])
            if g:
                return {str(x) for x in g}
    return set()


def get_domain(paper_id: str) -> str | None:
    for base in [TEST_DIR, DATA_DIR]:
        for d in os.listdir(base):
            if os.path.isdir(f"{base}/{d}/{paper_id}"):
                return d
    return None


def get_posthoc(paper_id: str, provider: str) -> dict:
    csvs = sorted(glob.glob(
        f"{RESULTS_DIR}/test_prime_A_B_C_posthoc_recall_{provider}_*.csv"
    ))
    for c in reversed(csvs):
        with open(c, encoding="utf-8-sig") as f:
            for row in csv_mod.DictReader(f):
                if row.get("paper_id") == paper_id:
                    return row
    return {}


def load_jsonl(paper_id: str, domain: str, provider: str, qhash: str) -> list[dict] | None:
    pdir = f"{CACHE_BASE}/{domain}/{paper_id}/{provider}"
    files = sorted(glob.glob(f"{pdir}/stagec_scored_records_medcpt_{qhash}*.jsonl"))
    if not files:
        return None
    with open(files[-1], encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def top_recall(records: list[dict], gold_set: set[str], keep_n: int, score_key: str) -> tuple[int, int, float]:
    actual_keep = min(keep_n, len(records))
    ordered = sorted(
        records,
        key=lambda r: (-float(r.get(score_key, 0.0)), str(r.get("pmid", "")))
    )
    kept = {str(r.get("pmid", "")).strip() for r in ordered[:actual_keep]}
    tp = len(kept & gold_set)
    recall = tp / len(gold_set) if gold_set else 0.0
    return tp, actual_keep, recall


# ── 1. Elicit data from 27papers CSV ─────────────────────────────────────────
df27 = pd.read_csv(f"{ELICIT_DIR}/elicit_queryB_list_papers.csv")
df27_24 = df27[df27["paper_id"].isin(ELICIT_24)].copy()

# ── 2. Original 12 papers from 20260505 (already gate+floor correct) ──────────
df_r_orig = pd.read_csv(ORIG_12_CSV).rename(columns={"value": "recall"})
df_n_orig = pd.read_csv(ORIG_12_NNR_CSV).rename(columns={"value": "nnr"})
df_ru_orig = pd.read_csv(ORIG_12_UNIFIED_CSV).rename(columns={"value": "recall"})
df_nu_orig = pd.read_csv(ORIG_12_UNIFIED_NNR_CSV).rename(columns={"value": "nnr"})

# Combine cut0-70 and unified
df_all_r = pd.concat([df_r_orig, df_ru_orig[df_ru_orig["method"].str.contains("Unified")]], ignore_index=True)
df_all_n = pd.concat([df_n_orig, df_nu_orig[df_nu_orig["method"].str.contains("Unified")]], ignore_index=True)

orig_12 = set(df_all_r["paper_id"].unique()) & set(ELICIT_24)
df_orig = (
    df_all_r[df_all_r["paper_id"].isin(orig_12)]
    .merge(df_all_n[df_all_n["paper_id"].isin(orig_12)], on=["method", "paper_id"])
)

METHOD_MAP_ORIG = {
    "Claude cut0": ("claude", "cut0"),   "Claude cut30": ("claude", "cut30"),
    "Claude cut50": ("claude", "cut50"), "Claude cut70": ("claude", "cut70"),
    "Claude Unified": ("claude", "unified"),
    "Codex cut0": ("codex", "cut0"),     "Codex cut30": ("codex", "cut30"),
    "Codex cut50": ("codex", "cut50"),   "Codex cut70": ("codex", "cut70"),
    "Codex Unified": ("codex", "unified"),
    "Gemini cut0": ("gemini", "cut0"),   "Gemini cut30": ("gemini", "cut30"),
    "Gemini cut50": ("gemini", "cut50"), "Gemini cut70": ("gemini", "cut70"),
    "Gemini Unified": ("gemini", "unified"),
}

# ── 3. Remaining 12 papers (missing9 + new3) from posthoc + JSONL ─────────────
remaining_12 = [p for p in ELICIT_24 if p not in orig_12]
print(f"Orig 12: {sorted(orig_12)}")
print(f"Remaining {len(remaining_12)}: {sorted(remaining_12)}")

# ── Build records ──────────────────────────────────────────────────────────────
records = []

for paper_id in ELICIT_24:
    gold_n = load_gold_n(paper_id)
    gold_set = load_gold_set(paper_id)

    # --- Elicit ---
    row27 = df27_24[df27_24["paper_id"] == paper_id]
    if not row27.empty:
        r27 = row27.iloc[0]
        for method, rcol, hcol in [
            ("Elicit Keyword all", "elicit_keyword_recall", "elicit_keyword_hits"),
            ("Elicit Question all", "elicit_question_all_recall", "elicit_question_all_hits"),
            ("Elicit Question include", "elicit_question_exclude_recall", "elicit_question_exclude_hits"),
            ("OpenScholar normal", "openscholar_normal_recall", "openscholar_normal_hits"),
            ("OpenScholar deep", "openscholar_deep_recall", "openscholar_deep_hits"),
            ("Human query", "human_recall", "human_hits"),
        ]:
            recall = float(r27.get(rcol, np.nan))
            hits = float(r27.get(hcol, np.nan))
            # Elicit Keyword: NaN means no keyword search done → treat as hits=0, recall=0
            if method == "Elicit Keyword all" and pd.isna(recall):
                recall, hits = 0.0, 0.0
            if pd.notna(recall) and pd.notna(hits):
                tp = recall * gold_n if gold_n else np.nan
                nnr = hits / tp if (pd.notna(tp) and tp > 0) else np.nan
                records.append({
                    "paper_id": paper_id, "method": method,
                    "recall": recall, "hits": hits, "tp": tp, "gold_n": gold_n, "nnr": nnr,
                })

    # --- LLM original 12 ---
    if paper_id in orig_12:
        for _, pr in df_orig[df_orig["paper_id"] == paper_id].iterrows():
            m = pr["method"]
            if m not in METHOD_MAP_ORIG:
                continue
            prov, cut = METHOD_MAP_ORIG[m]
            recall = pr["recall"]
            nnr = pr["nnr"]
            tp = recall * gold_n if (gold_n and pd.notna(recall)) else np.nan
            hits_raw = nnr * tp if (pd.notna(nnr) and pd.notna(tp) and tp > 0) else (0.0 if recall == 0 else np.nan)
            hits = round(hits_raw) if pd.notna(hits_raw) else np.nan
            records.append({
                "paper_id": paper_id,
                "method": f"{prov.capitalize()} {cut}",
                "recall": recall, "hits": hits, "tp": tp, "gold_n": gold_n, "nnr": nnr,
            })

    # --- LLM remaining 12 (gate+floor applied correctly) ---
    if paper_id in remaining_12:
        domain = get_domain(paper_id)
        if not domain:
            print(f"  WARNING: domain not found for {paper_id}")
            continue

        for provider in ["claude", "codex", "gemini"]:
            ph = get_posthoc(paper_id, provider)
            if not ph:
                continue
            qhash = ph.get("stage_c_query_hash", "")
            b_hits = int(float(ph.get("stage_b_total_hits", 0) or 0))
            b_tp = int(float(ph.get("stage_b_tp", 0) or 0))
            gold_n_ph = int(float(ph.get("gold_n", gold_n or 0) or 0))
            b_recall = b_tp / gold_n_ph if gold_n_ph else 0.0

            # cut0 = stage B passthrough
            prov_cap = provider.capitalize()
            nnr_c0 = b_hits / b_tp if b_tp > 0 else np.nan
            records.append({
                "paper_id": paper_id, "method": f"{prov_cap} cut0",
                "recall": b_recall, "hits": float(b_hits), "tp": float(b_tp),
                "gold_n": gold_n_ph, "nnr": nnr_c0,
            })

            if not qhash:
                # No stage C available → passthrough for all cuts
                for cut, cp in [("cut30", 30), ("cut50", 50), ("cut70", 70), ("unified", None)]:
                    records.append({
                        "paper_id": paper_id, "method": f"{prov_cap} {cut}",
                        "recall": b_recall, "hits": float(b_hits), "tp": float(b_tp),
                        "gold_n": gold_n_ph, "nnr": nnr_c0,
                    })
                continue

            recs = load_jsonl(paper_id, domain, provider, qhash)
            if not recs:
                print(f"  WARNING: no JSONL for {paper_id}/{provider}/{qhash}")
                continue

            sample = recs[0]
            score_key = "final" if "final" in sample else "dense_sim_medcpt"

            for cut, cp in [("cut30", 30), ("cut50", 50), ("cut70", 70)]:
                kept_n = gate_floor(b_hits, cp)
                tp_cut, actual_kept, recall_cut = top_recall(recs, gold_set, kept_n, score_key)
                nnr_cut = actual_kept / tp_cut if tp_cut > 0 else np.nan
                records.append({
                    "paper_id": paper_id, "method": f"{prov_cap} {cut}",
                    "recall": recall_cut, "hits": float(actual_kept), "tp": float(tp_cut),
                    "gold_n": gold_n_ph, "nnr": nnr_cut,
                })

            # unified = top 1000 by "final" if b_hits > 1000, else passthrough
            if b_hits > 1000:
                ukey = "final" if "final" in sample else score_key
                tp_u, h_u, rec_u = top_recall(recs, gold_set, min(1000, len(recs)), ukey)
                nnr_u = h_u / tp_u if tp_u > 0 else np.nan
            else:
                rec_u, h_u, tp_u, nnr_u = b_recall, float(b_hits), float(b_tp), nnr_c0
            records.append({
                "paper_id": paper_id, "method": f"{prov_cap} unified",
                "recall": rec_u, "hits": float(h_u), "tp": float(tp_u),
                "gold_n": gold_n_ph, "nnr": nnr_u,
            })

df_all = pd.DataFrame(records)
print(f"\nTotal records: {len(df_all)}")

# ── N per method ──────────────────────────────────────────────────────────────
n_per_method = (
    df_all[df_all["recall"].notna()]
    .groupby("method")["paper_id"]
    .nunique()
    .reset_index()
    .rename(columns={"paper_id": "n_papers"})
)
print("\nN per method:")
print(n_per_method.to_string(index=False))

# ── Aggregate ─────────────────────────────────────────────────────────────────
TARGET_METHODS = [
    "Elicit Keyword all",
    "Elicit Question all",
    "Elicit Question include",
    "OpenScholar normal",
    "OpenScholar deep",
    "Human query",
    "Claude cut0", "Claude cut30", "Claude cut50", "Claude cut70", "Claude unified",
    "Codex cut0",  "Codex cut30",  "Codex cut50",  "Codex cut70",  "Codex unified",
    "Gemini cut0", "Gemini cut30", "Gemini cut50", "Gemini cut70", "Gemini unified",
]

agg_rows = []
for method in TARGET_METHODS:
    sub = df_all[(df_all["method"] == method) & df_all["recall"].notna()]
    n = len(sub)
    if n == 0:
        agg_rows.append({"method": method, "n_papers": 0,
                         "mean_recall": np.nan, "mean_nnr": np.nan, "mean_f1": np.nan})
        continue

    mean_recall = sub["recall"].mean()

    # NNR: use precomputed nnr column
    nnr_vals = sub["nnr"].dropna()
    mean_nnr = nnr_vals.mean() if len(nnr_vals) else np.nan

    # F1 = 2*P*R/(P+R), P=1/NNR
    f1_vals = []
    for _, r in sub.iterrows():
        rec = r["recall"]
        nnr_v = r.get("nnr", np.nan)
        if pd.notna(nnr_v) and nnr_v > 0:
            prec = 1.0 / nnr_v
            denom = rec + prec
            f1_vals.append(2 * rec * prec / denom if denom > 0 else 0.0)
    mean_f1 = float(np.mean(f1_vals)) if f1_vals else np.nan

    agg_rows.append({
        "method": method, "n_papers": n,
        "mean_recall": round(mean_recall, 4),
        "mean_nnr": round(mean_nnr, 1) if not np.isnan(mean_nnr) else np.nan,
        "mean_f1": round(mean_f1, 4) if not np.isnan(mean_f1) else np.nan,
    })

df_agg = pd.DataFrame(agg_rows)
print("\n=== 24-paper aggregate (gate=1000, floor=1000) ===")
print(df_agg.to_string(index=False))

# ── Save ──────────────────────────────────────────────────────────────────────
df_agg.to_csv(f"{ELICIT_DIR}/elicit24_aggregate_gate1000_floor1000_20260511.csv", index=False)
print("\nSaved elicit24_aggregate_gate1000_floor1000_20260511.csv")

# Also save per-paper points data for charting
df_all.to_csv(f"{ELICIT_DIR}/elicit24_points_gate1000_floor1000_20260511.csv", index=False)
print("Saved elicit24_points_gate1000_floor1000_20260511.csv")
