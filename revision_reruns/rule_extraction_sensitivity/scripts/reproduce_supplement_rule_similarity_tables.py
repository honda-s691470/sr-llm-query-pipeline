from __future__ import annotations

from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[1]
REPORTS = BASE / "reports"
OUT = BASE / "reproduction_check" / "supplement_tables"

NAME_MAP = {
    "run1_rulebook": "Run1",
    "run2_rulebook": "Run2",
    "run3_rulebook": "Run3",
    "pooled_consensus_rulebook": "Pooled",
    "run1_original": "Run1",
    "run2_rerun": "Run2",
    "run3_rerun": "Run3",
    "pooled_run1_run2_run3": "Pooled",
}

COMPARISON_ORDER = [
    "Run1 vs Run2",
    "Run1 vs Run3",
    "Run2 vs Run3",
    "Run1 vs Pooled",
    "Run2 vs Pooled",
    "Run3 vs Pooled",
]

REFINED_ORDER = [
    "Run1 vs Run2",
    "Run1 vs Run3",
    "Run1 vs Pooled",
    "Run2 vs Run3",
    "Run2 vs Pooled",
    "Run3 vs Pooled",
]


def comp(a: str, b: str) -> str:
    return f"{NAME_MAP[a]} vs {NAME_MAP[b]}"


def write_refined_table() -> Path:
    df = pd.read_csv(REPORTS / "refined_rulebook_topn_similarity.csv")
    sub = df[(df["kind"] == "ALL") & (df["top_n"] == 24)].copy()
    sub["Comparison"] = [comp(a, b) for a, b in zip(sub["A"], sub["B"])]
    sub["Shared"] = sub.apply(lambda r: f"{int(r['shared_n'])}/{int(min(r['n_A'], r['n_B']))}", axis=1)
    sub["Shared / smaller set"] = sub["shared_over_smaller_set"].map(lambda x: f"{float(x):.3f}")
    out = sub[["Comparison", "Shared", "Shared / smaller set"]].set_index("Comparison").loc[REFINED_ORDER].reset_index()

    definitions = pd.DataFrame([
        {"Comparison": "Definitions", "Shared": "", "Shared / smaller set": ""},
        {
            "Comparison": "Shared",
            "Shared": "Number of laws with an identical strict normalized key (META_ACTION + META_CONCEPT + Action_Operator + Target_Block + Target_Slot + Field_Policy) present in BOTH final refined rulebooks being compared, out of the size of the smaller of the two rulebooks. E.g. Run1 vs Run2 = 13/19 means the smaller rulebook has 19 laws and 13 of them also appear in the other rulebook.",
            "Shared / smaller set": "",
        },
        {
            "Comparison": "Shared / smaller set",
            "Shared": "Overlap coefficient (Szymkiewicz-Simpson coefficient) = Shared / min(|rulebook A|, |rulebook B|). Unlike Jaccard (which divides by the union size and is penalized when the two rulebooks differ in total size), this measures what fraction of the SMALLER rulebook's laws are also found in the larger one -- i.e. how much of the smaller set is 'contained' in the larger set.",
            "Shared / smaller set": "",
        },
        {
            "Comparison": "Source",
            "Shared": "public_release/revision_reruns/rule_extraction_sensitivity/reports/refined_rulebook_topn_similarity.csv, ALL/top_n=24 section (final refined rulebooks, after refinement).",
            "Shared / smaller set": "",
        },
    ])
    path = OUT / "refined_rulebook_shared_by_run.csv"
    pd.concat([out, definitions], ignore_index=True).to_csv(path, index=False, encoding="utf-8-sig")
    return path


def write_candidate_table() -> Path:
    df = pd.read_csv(REPORTS / "pairwise_rule_similarity.csv")
    rows = []
    for _, r in df.iterrows():
        comparison = comp(r["A"], r["B"])
        rows.append({
            "Comparison": comparison,
            "Top DO overlap": f"{int(r['top12_do_overlap_n'])}/12",
            "Top DO overlap (%)": f"{float(r['top12_do_overlap_n'] / 12):.3f}",
            "Top AVOID overlap": f"{int(r['top12_avoid_overlap_n'])}/12",
            "Top AVOID overlap (%)": f"{float(r['top12_avoid_overlap_n'] / 12):.3f}",
            "Top DO+AVOID overlap": f"{int(r['top12_do_overlap_n'] + r['top12_avoid_overlap_n'])}/24",
            "Top DO+AVOID overlap (%)": f"{float((r['top12_do_overlap_n'] + r['top12_avoid_overlap_n']) / 24):.3f}",
            "All-candidates Shared (no cap)": f"{int(r['n_shared_strict'])}/{int(min(r['n_A'], r['n_B']))}",
            "All-candidates Overlap coefficient (no cap)": f"{float(r['n_shared_strict'] / min(r['n_A'], r['n_B'])):.3f}",
        })
    out = pd.DataFrame(rows).set_index("Comparison").loc[COMPARISON_ORDER].reset_index()
    definitions = pd.DataFrame([
        {"Comparison": "Definitions"},
        {"Comparison": "Top DO overlap", "Top DO overlap": "Number of candidate DO-laws (deployment/positive laws) shared between the two runs' independently selected top-12 DO lists, out of 12. A law counts as shared only if its normalized key (META_ACTION + META_CONCEPT + Action_Operator + Target_Block + Target_Slot + Field_Policy) matches exactly in both lists; score values and rank order are not part of the key."},
        {"Comparison": "Top AVOID overlap", "Top DO overlap": "Number of candidate AVOID-laws (recall-risk/negative laws) shared between the two runs' independently selected top-12 AVOID lists, out of 12, using the same strict normalized key as above."},
        {"Comparison": "Top DO+AVOID overlap", "Top DO overlap": "Sum of the DO overlap count and the AVOID overlap count, out of 24 (12 DO + 12 AVOID). Combines both law families into a single agreement measure across the two runs."},
        {"Comparison": "All-candidates Shared (no cap)", "Top DO overlap": "Number of laws with an identical strict normalized key present in BOTH runs' FULL candidate law sets (before the top-12 DO / top-12 AVOID selection cap is applied), out of the size of the smaller of the two candidate sets."},
        {"Comparison": "All-candidates Overlap coefficient (no cap)", "Top DO overlap": "Overlap coefficient (Szymkiewicz-Simpson) = Shared / min(|candidate set A|, |candidate set B|), computed on the full (uncapped) candidate law sets. Measures how much of the smaller run's candidate laws are also found in the other run's candidate laws, without truncating either list to the top 12."},
        {"Comparison": "Candidate rule totals (pre-refinement)", "Top DO overlap": "Run1=29, Run2=30, Run3=32, Pooled=37 total candidate laws (all types combined: CONDITIONAL, RECALL_PROTECTIVE, AVOID, NOISE_REDUCTION), before the top-12 DO / top-12 AVOID selection cap and before final refinement. Source: public_release/revision_reruns/rule_extraction_sensitivity/candidate_rules_pre_refinement/ and refined_rulebooks/refined_rulebook_manifest.csv (candidate_laws column)."},
        {"Comparison": "Note on Pooled comparisons", "Top DO overlap": "Run1/Run2/Run3 vs Pooled all show Overlap coefficient = 1.000 because the pooled candidate set was extracted from the union of all three runs' logs (33 logs total), so every candidate law found in any individual run is, by construction, also present in the pooled set. The more informative reproducibility comparisons are Run1 vs Run2, Run1 vs Run3, and Run2 vs Run3."},
        {"Comparison": "Source", "Top DO overlap": "public_release/revision_reruns/rule_extraction_sensitivity/reports/pairwise_rule_similarity.csv (candidate-extraction stage, before refinement)."},
    ])
    path = OUT / "rule_candidate_top_overlap_by_run.csv"
    pd.concat([out, definitions], ignore_index=True).to_csv(path, index=False, encoding="utf-8-sig")
    return path


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for path in [write_refined_table(), write_candidate_table()]:
        print(path.relative_to(BASE))


if __name__ == "__main__":
    main()

