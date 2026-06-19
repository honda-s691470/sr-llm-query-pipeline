"""
Phase 5: LLM-based full query rewrite (last-resort hit reduction).

Called when Stage A' Phases 1-4 have been exhausted and hits remain > 9,999.

Architecture (v2.0):
  Phase 5 LLM calls are NOT made from Python scripts.
  Instead, the main Claude Code conversation orchestrates Phase 5 via Agent tool
  subagents, which generate one raw PubMed query line directly.
  The main conversation verifies hits via PubMed and loops until hits < 9,999.

This module provides prompt-building and response-parsing utilities only.
"""
from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

# ── Prompt templates ──────────────────────────────────────────────────────────
_PHASE5_CONTEXT_TEMPLATE = """\

---

## ⚠ PHASE 5 CONTEXT — FULL QUERY REWRITE REQUIRED

The query below was generated and optimized through Stage A' Phases 1–4,
but still returns {current_hits} hits, exceeding the 9,999-hit target.

### Previous Query (after Stage A' Phases 1–4)
{current_query}

### Current Total Hits: {current_hits}  |  Target: < {target_hits}
{training_recall_block}
### Task
Generate ONE NEW PubMed Boolean query that:
1. Returns < {target_hits} total hits in PubMed.
2. Preserves maximum recall — do NOT sacrifice recall for hit reduction.
3. Follows all rules in query_laws.txt and the base prompt above.

### Suggested Hit-Reduction Strategies (in order of recall safety)
Apply these where the previous query is over-broad:
1. Replace [Mesh] with [Mesh:NoExp] for terms with large MeSH subtrees and tiab backup.
2. Replace [Mesh:NoExp] with [majr] to restrict to primary-topic papers where tiab backup exists.
3. Replace broad [tiab] with [ti] where [Mesh] or [majr] backup covers the concept.
4. Remove genuinely redundant OR terms (non-wildcard term already covered by a wildcard in same block).
5. Remove very broad generic tiab when a more-specific tiab covers the concept in the same block.
6. Apply NOT publication-type filters not already present if justified by exclusion criteria.
   Safe: NOT "Comment"[pt], NOT "Letter"[pt], NOT "Editorial"[pt], NOT "Case Reports"[pt].

### Hard Constraints — Never Violate
- Do NOT remove the last tiab/MeSH coverage of a core concept (condition, intervention).
- Do NOT add new mandatory AND blocks not justified by core inclusion criteria.
- Do NOT convert OR to AND inside a primary concept block.
- Do NOT apply NOT "Review"[pt] / NOT "Meta-Analysis"[pt] if inclusion criteria
  allow systematic reviews or meta-analyses as eligible study types (SR-of-SRs rule).

Output exactly ONE line containing only the complete PubMed query.
"""

_PHASE5_TRAINING_RECALL_BLOCK = """\

### Recall Information (Training Mode)
- Gold standard papers: {gold_n}
- Current recall after Phase 1–4: {current_recall:.4f}  (TP = {tp} / {gold_n})
- Required minimum recall for acceptance: >= {min_recall:.4f}  (ΔR tolerance = 0.02)
A proposed query is accepted only if hits < {target_hits} AND recall >= {min_recall:.4f}.
"""


def parse_full_query(text: str) -> str | None:
    """Extract a query from LLM/subagent response.

    Accepts either the new raw-query one-line format or legacy
    `FULL_QUERY: <query>` responses.
    """
    stripped = text.strip()
    if not stripped:
        return None
    for line in text.strip().splitlines():
        line = line.strip()
        if line.upper().startswith("FULL_QUERY:"):
            q = line[len("FULL_QUERY:"):].strip()
            if q:
                return q
    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    if len(lines) == 1:
        return lines[0]
    return stripped if "\n" not in stripped else None


def build_prompt(
    base_prompt_text: str,
    query_laws_text: str,
    input_config: dict,
    current_query: str,
    current_hits: int,
    target_hits: int,
    sr_of_srs: bool = False,
    training_recall_block: str = "",
) -> str:
    """Assemble the full Phase 5 prompt for subagent use."""
    config_json = json.dumps(input_config, ensure_ascii=False, indent=2)
    assembled = (
        f"input_config.json:\n```json\n{config_json}\n```\n\n"
        f"query_laws.txt:\n```\n{query_laws_text}\n```\n\n"
        f"{base_prompt_text}"
    )
    context = _PHASE5_CONTEXT_TEMPLATE.format(
        current_query=current_query,
        current_hits=current_hits,
        target_hits=target_hits,
        training_recall_block=training_recall_block,
    )
    if sr_of_srs:
        context += (
            "\n> SR-of-SRs ACTIVE: Do NOT apply NOT \"Review\"[pt], NOT \"Meta-Analysis\"[pt], "
            "or NOT \"Systematic Review\"[pt] — inclusion criteria allow review-type studies.\n"
        )
    return assembled + context


def build_training_recall_block(
    gold_n: int,
    current_recall: float,
    target_hits: int,
) -> str:
    """Build the training-mode recall information block."""
    min_recall = current_recall - 0.02
    tp = round(current_recall * gold_n)
    return _PHASE5_TRAINING_RECALL_BLOCK.format(
        gold_n=gold_n,
        current_recall=current_recall,
        tp=tp,
        min_recall=min_recall,
        target_hits=target_hits,
    )
