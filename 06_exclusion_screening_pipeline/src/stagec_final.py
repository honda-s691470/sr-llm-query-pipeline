"""
Reference implementation for Stage C Final score.

Final formula:
  final = rank(s_q) + rank(s_pos_mean) - rank(s_neg_mean)

where
  s_q = 0.5 * dense_sim_medcpt + 0.5 * bm25_score
  pos anchors = top-2 by s_q
  neg anchors = bottom-2 by s_q

Rank definition (deterministic):
  descending percentile rank in [0,1], stable mergesort, ties keep input order.
"""
from __future__ import annotations

from typing import Any

import numpy as np


def rank_percentile_desc(values: np.ndarray) -> np.ndarray:
    n = len(values)
    if n <= 1:
        return np.ones(n, dtype=np.float32)
    order = np.argsort(-values, kind="mergesort")
    ranks = np.empty(n, dtype=np.float32)
    ranks[order] = np.arange(n, dtype=np.float32)
    return 1.0 - (ranks / float(n - 1))


def _select_anchor_idx(s_q: np.ndarray, pmids: list[str], top: bool) -> tuple[int, int]:
    n = len(pmids)
    if n == 0:
        return 0, 0
    if top:
        order = sorted(range(n), key=lambda i: (-float(s_q[i]), pmids[i]))
    else:
        order = sorted(range(n), key=lambda i: (float(s_q[i]), pmids[i]))
    a = order[0]
    b = order[1] if n > 1 else order[0]
    return a, b


def compute_stagec_final(
    pmids: list[str],
    dense_scores: list[float],
    bm25_scores: list[float],
    doc_embs: np.ndarray,
) -> dict[str, Any]:
    """
    Compute Stage C Final score components.

    Args:
      pmids: candidate PMIDs in deterministic order.
      dense_scores: dense_sim_medcpt list (aligned with pmids).
      bm25_scores: bm25_score list (aligned with pmids).
      doc_embs: normalized document embeddings, shape [n, d] aligned with pmids.
    """
    n = len(pmids)
    if n == 0:
        return {
            "pos_anchor_idx": [0, 0],
            "neg_anchor_idx": [0, 0],
            "s_q": [],
            "s_pos1": [],
            "s_pos2": [],
            "s_neg1": [],
            "s_neg2": [],
            "s_pos_mean": [],
            "s_neg_mean": [],
            "rank_s_q": [],
            "rank_s_pos_mean": [],
            "rank_s_neg_mean": [],
            "final": [],
        }

    s_dense = np.asarray(dense_scores, dtype=np.float32)
    s_bm25 = np.asarray(bm25_scores, dtype=np.float32)
    s_q = 0.5 * s_dense + 0.5 * s_bm25

    pos1, pos2 = _select_anchor_idx(s_q, pmids, top=True)
    neg1, neg2 = _select_anchor_idx(s_q, pmids, top=False)

    pos1_vec = doc_embs[pos1]
    pos2_vec = doc_embs[pos2]
    neg1_vec = doc_embs[neg1]
    neg2_vec = doc_embs[neg2]

    s_pos1 = (doc_embs @ pos1_vec).astype(np.float32)
    s_pos2 = (doc_embs @ pos2_vec).astype(np.float32)
    s_neg1 = (doc_embs @ neg1_vec).astype(np.float32)
    s_neg2 = (doc_embs @ neg2_vec).astype(np.float32)

    s_pos_mean = ((s_pos1 + s_pos2) / 2.0).astype(np.float32)
    s_neg_mean = ((s_neg1 + s_neg2) / 2.0).astype(np.float32)

    r_q = rank_percentile_desc(s_q)
    r_pos = rank_percentile_desc(s_pos_mean)
    r_neg = rank_percentile_desc(s_neg_mean)
    final = (r_q + r_pos - r_neg).astype(np.float32)

    return {
        "pos_anchor_idx": [int(pos1), int(pos2)],
        "neg_anchor_idx": [int(neg1), int(neg2)],
        "s_q": s_q.tolist(),
        "s_pos1": s_pos1.tolist(),
        "s_pos2": s_pos2.tolist(),
        "s_neg1": s_neg1.tolist(),
        "s_neg2": s_neg2.tolist(),
        "s_pos_mean": s_pos_mean.tolist(),
        "s_neg_mean": s_neg_mean.tolist(),
        "rank_s_q": r_q.tolist(),
        "rank_s_pos_mean": r_pos.tolist(),
        "rank_s_neg_mean": r_neg.tolist(),
        "final": final.tolist(),
    }

