"""
Evaluator for exclusion screening pipeline.
Computes: Sensitivity, Candidate-Universe Specificity, Precision, F1, F2, NNR, WSS@95.

NOTE on specificity: reports "candidate-universe specificity" only.
Do NOT label this as general "specificity" — see v2 plan Section 6.
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Optional


@dataclass
class ScreeningMetrics:
    paper_id: str
    total_hits_before: int      # Stage A input (hits_A)
    total_hits_after_a: int     # after Stage A NOT expansion
    total_hits_after_b: int     # after Stage B deterministic filter
    total_candidates_c: int     # after Stage C ranking (LLM input size)
    total_retained_d: int       # after Stage D LLM screening
    total_final: int            # after Stage E rescue (= final set)

    gold_total: int             # total gold PMIDs
    tp: int                     # gold PMIDs in final set
    fp: int                     # non-gold PMIDs in final set
    fn: int                     # gold PMIDs NOT in final set
    tn_pooled: int              # non-gold in candidate universe NOT in final set

    sensitivity: float          # TP / (TP + FN) = recall
    precision: float            # TP / (TP + FP)
    f1: float
    f2: float
    nnr: float                  # total_final / TP (number needed to read)
    hit_reduction_ratio: float  # 1 - (total_final / total_hits_before)
    cu_specificity: float       # candidate-universe specificity: TN / (TN + FP)
    wss_at_95: Optional[float]  # work saved over sampling at 95% sensitivity

    notes: str = ""


def compute_metrics(
    paper_id: str,
    gold_pmids: set[str],
    stage_hits: dict[str, list[str]],
    pooled_universe: Optional[set[str]] = None,
) -> ScreeningMetrics:
    """
    Compute all metrics for one paper.

    Args:
        paper_id: identifier string
        gold_pmids: set of known-positive PMIDs
        stage_hits: dict with keys:
            'hits_a'  → PMIDs after Stage A (or pre-filter baseline)
            'hits_b'  → PMIDs after Stage B
            'candidates_c' → PMIDs after Stage C ranking
            'retained_d'   → PMIDs after Stage D LLM
            'final'        → PMIDs after Stage E rescue
        pooled_universe: U = union of all method PMIDs (for CU-specificity).
                         If None, uses hits_a as universe.
    """
    hits_a     = set(stage_hits.get("hits_a", []))
    hits_b     = set(stage_hits.get("hits_b", []))
    cands_c    = set(stage_hits.get("candidates_c", stage_hits.get("hits_b", [])))
    retained_d = set(stage_hits.get("retained_d", stage_hits.get("candidates_c", [])))
    final      = set(stage_hits.get("final", stage_hits.get("retained_d", [])))

    if pooled_universe is None:
        pooled_universe = hits_a

    tp = len(gold_pmids & final)
    fn = len(gold_pmids) - tp
    fp = len(final - gold_pmids)

    # Candidate-universe TN: in universe, not gold, not in final
    non_gold_universe = pooled_universe - gold_pmids
    tn_pooled = len(non_gold_universe - final)

    sensitivity = tp / max(tp + fn, 1)
    precision   = tp / max(tp + fp, 1)

    beta2 = 1.0
    f1 = (2 * precision * sensitivity / (precision + sensitivity)
          if (precision + sensitivity) > 0 else 0.0)
    beta = 2.0
    f2 = ((1 + beta**2) * precision * sensitivity
          / (beta**2 * precision + sensitivity)
          if (beta**2 * precision + sensitivity) > 0 else 0.0)

    nnr = len(final) / max(tp, 1)
    hit_reduction = 1.0 - len(final) / max(len(hits_a), 1)

    cu_spec = tn_pooled / max(tn_pooled + fp, 1)

    # WSS@95: requires screening in ranked order (not available here → None unless provided)
    wss = None

    return ScreeningMetrics(
        paper_id=paper_id,
        total_hits_before=len(hits_a),
        total_hits_after_a=len(hits_a),
        total_hits_after_b=len(hits_b),
        total_candidates_c=len(cands_c),
        total_retained_d=len(retained_d),
        total_final=len(final),
        gold_total=len(gold_pmids),
        tp=tp, fp=fp, fn=fn, tn_pooled=tn_pooled,
        sensitivity=round(sensitivity, 4),
        precision=round(precision, 4),
        f1=round(f1, 4),
        f2=round(f2, 4),
        nnr=round(nnr, 2),
        hit_reduction_ratio=round(hit_reduction, 4),
        cu_specificity=round(cu_spec, 4),
        wss_at_95=wss,
    )


def metrics_to_dict(m: ScreeningMetrics) -> dict:
    return {
        "paper_id": m.paper_id,
        "gold_total": m.gold_total,
        "total_hits_before": m.total_hits_before,
        "total_hits_after_b": m.total_hits_after_b,
        "total_candidates_c": m.total_candidates_c,
        "total_retained_d": m.total_retained_d,
        "total_final": m.total_final,
        "tp": m.tp, "fp": m.fp, "fn": m.fn, "tn_pooled": m.tn_pooled,
        "sensitivity": m.sensitivity,
        "precision": m.precision,
        "f1": m.f1,
        "f2": m.f2,
        "nnr": m.nnr,
        "hit_reduction_ratio": m.hit_reduction_ratio,
        "cu_specificity_note": "candidate-universe specificity (not global PubMed specificity)",
        "cu_specificity": m.cu_specificity,
        "wss_at_95": m.wss_at_95,
        "notes": m.notes,
    }


def aggregate_metrics(metrics_list: list[ScreeningMetrics]) -> dict:
    """Compute mean metrics across papers."""
    n = len(metrics_list)
    if n == 0:
        return {}

    def mean(attr: str) -> float:
        vals = [getattr(m, attr) for m in metrics_list if getattr(m, attr) is not None]
        return round(sum(vals) / max(len(vals), 1), 4)

    return {
        "n_papers": n,
        "mean_sensitivity": mean("sensitivity"),
        "mean_precision": mean("precision"),
        "mean_f1": mean("f1"),
        "mean_f2": mean("f2"),
        "mean_nnr": mean("nnr"),
        "mean_hit_reduction_ratio": mean("hit_reduction_ratio"),
        "mean_cu_specificity": mean("cu_specificity"),
        "cu_specificity_note": "candidate-universe specificity (not global PubMed specificity)",
    }
