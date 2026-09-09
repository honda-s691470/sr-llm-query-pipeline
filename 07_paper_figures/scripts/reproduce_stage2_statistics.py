"""Reproduce Test24 Stage 2 NNR tests, R_search, and projected savings."""
from pathlib import Path
import numpy as np
import pandas as pd

SEED = 42
N_BOOT = 10_000
N_PERM = 100_000
WEEKS_BASE = 67.3 * 0.20
COST_BASE_USD = 141_194.80 * 0.20
METHODS = ["Claude cut70", "Gemini cut70", "Codex cut70", "Elicit Question all", "Elicit Question include", "OpenScholar deep", "OpenScholar normal", "Elicit Keyword all"]
HERE = Path(__file__).resolve().parent
INPUT = HERE.parent / "data" / "test24_eval" / "elicit24_points_gate1000_floor1000_20260511.csv"
OUTPUT = HERE.parent / "data" / "test24_eval" / "reproduced_stage2_statistics.csv"

def sign_flip_pvalue(difference):
    rng = np.random.default_rng(SEED)
    signs = rng.choice(np.array([-1.0, 1.0]), size=(N_PERM, len(difference)))
    null = (signs * difference).mean(axis=1)
    return ((null >= difference.mean()).sum() + 1) / (N_PERM + 1)

def bootstrap_rsearch(human, method):
    rng = np.random.default_rng(SEED)
    index = rng.integers(0, len(human), size=(N_BOOT, len(human)))
    h_mean = human[index].mean(axis=1)
    m_mean = method[index].mean(axis=1)
    return np.percentile((h_mean - m_mean) / h_mean, [2.5, 97.5])

def main():
    data = pd.read_csv(INPUT)
    human = data[data.method.eq("Human query")].drop_duplicates("paper_id").set_index("paper_id")
    rows = []
    for name in METHODS:
        method = data[data.method.eq(name)].drop_duplicates("paper_id").set_index("paper_id")
        paired = human[["nnr"]].join(method[["nnr"]], lsuffix="_human", rsuffix="_method").dropna()
        h = paired.nnr_human.to_numpy(float)
        m = paired.nnr_method.to_numpy(float)
        r_search = (h.mean() - m.mean()) / h.mean()
        ci_low, ci_high = bootstrap_rsearch(h, m)
        rows.append({
            "method": name,
            "n_paired": len(paired),
            "mean_nnr_human": h.mean(),
            "mean_nnr_method": m.mean(),
            "nnr_sign_flip_p_one_sided": sign_flip_pvalue(h - m),
            "r_search": r_search,
            "r_search_ci_low": ci_low,
            "r_search_ci_high": ci_high,
            "weeks_saved": WEEKS_BASE * r_search,
            "weeks_saved_ci_low": WEEKS_BASE * ci_low,
            "weeks_saved_ci_high": WEEKS_BASE * ci_high,
            "cost_saved_usd": COST_BASE_USD * r_search,
            "cost_saved_ci_low_usd": COST_BASE_USD * ci_low,
            "cost_saved_ci_high_usd": COST_BASE_USD * ci_high,
        })
    result = pd.DataFrame(rows)
    result.to_csv(OUTPUT, index=False)
    print(result.to_string(index=False))
    print(f"Saved: {OUTPUT}")

if __name__ == "__main__":
    main()

