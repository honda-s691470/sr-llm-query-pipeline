"""
Unified exclusion screening pipeline: Stage A' -> A -> B -> C
  --mode test      : papers from manifest, no recall during pipeline, post-hoc recall
  --mode training  : papers from dir scan, live recall at each stage, Phase5 prompt on gate failure

Key behavioural differences by mode
  test     : Stage A' uses run_prime_no_recall (no recall guard); dataset_split="test"
  training : Stage A' uses phase1+phase3 with Δrecall<=0.02 guard; live recall at A/B/C;
             Phase5 manual-rewrite prompt written when prime_hits>=9999; dataset_split="training_eval_non27"

HyDE cache filenames differ by mode (hyde_query_test.txt / hyde_query_training.txt)
  to prevent cross-contamination between test and training runs.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "04_data"
TEST_DIR = ROOT / "05_test_data"
RESULTS_DIR = ROOT / "06_exclusion_screening_pipeline" / "results"
LOG_DIR = ROOT / "06_exclusion_screening_pipeline" / "logs"
CACHE_ROOT = ROOT / "06_exclusion_screening_pipeline" / "pubmed_cache"
BASE_TEST_PROMPT_PATH = ROOT / "03_hypothesis_accumlation_test" / "test_prompt_with.md"
def _latest_query_laws_path() -> Path:
    candidates = sorted(
        (ROOT / "02_query_laws_refinement").glob("query_laws_ver*.txt"),
        key=lambda p: int(re.search(r"ver(\d+)", p.stem).group(1)),
    )
    if not candidates:
        raise FileNotFoundError("No query_laws_ver*.txt found in 02_query_laws_refinement/")
    return candidates[-1]

QUERY_LAWS_PATH = _latest_query_laws_path()

sys.path.insert(0, str((ROOT / "06_exclusion_screening_pipeline" / "src").resolve()))
sys.path.insert(0, str((ROOT / "06_exclusion_screening_pipeline").resolve()))

from exclusion_parser import parse_and_log, stage_b_filter
from pubmed_fetcher import fetch_all_abstracts, fetch_all_metadata, search_pubmed
from ranker import HybridRanker, build_hyde_query
from stage_a_prime import run_prime_no_recall
from stagec_final import compute_stagec_final
from stage_query_storage import save_stage_query_snapshot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Shared utilities
# ══════════════════════════════════════════════════════════════════════════════

def _compute_kept_n_with_gate_floor(
    stage_b_hits: int, gate_hits: int, floor_hits: int, cut_percent: float
) -> int:
    """Gate/Floor passthrough/cut logic (shared between test and training)."""
    if stage_b_hits <= gate_hits:
        return stage_b_hits
    keep_frac = max(0.0, 1.0 - (cut_percent / 100.0))
    kept_n = max(int(floor_hits), int(round(stage_b_hits * keep_frac)))
    return min(stage_b_hits, kept_n)


def _freeze_hyde(
    *,
    cache_dir: Path,
    objectives: str,
    inclusion: str,
    exclusion: str,
    hyde_provider: str,
    hyde_model: str,
    mode: str,
    use_hyde: bool = True,
) -> tuple[str, bool]:
    """
    Load or generate a HyDE pseudo-abstract query.
    Cache filename differs by mode to prevent cross-contamination.
    Returns (hyde_text, newly_generated).
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    fname = "hyde_query_test.txt" if mode == "test" else "hyde_query_training.txt"
    hyde_path = cache_dir / fname
    if hyde_path.exists():
        text = hyde_path.read_text(encoding="utf-8").strip()
        logger.info("  HyDE loaded from cache (%d chars)", len(text))
        return text, False
    if use_hyde:
        text = build_hyde_query(
            objectives=objectives,
            inclusion_criteria=inclusion,
            exclusion_criteria=exclusion,
            provider=hyde_provider,
            model=hyde_model,
        )
    else:
        text = f"{objectives} {inclusion}".strip()
    hyde_path.write_text(text, encoding="utf-8")
    logger.info("  HyDE generated and saved (%d chars)", len(text))
    return text, True


def _run_stage_c(
    *,
    pmids_b: list[str],
    domain: str,
    paper_id: str,
    provider: str,
    hyde_provider: str,
    hyde_model: str,
    objectives: str,
    inclusion: str,
    exclusion: str,
    k: int,
    medcpt_ranker: HybridRanker,
    mode: str,
    use_hyde: bool = True,
) -> tuple[list[str], str, str, int, bool]:
    """
    Run Stage C: HyDE freeze -> abstract fetch -> MedCPT+BM25+Final scoring -> top-K.

    Cache key: query_hash + pmid_set_hash (robust against Stage B set changes).
    Legacy cache (query_hash only, from pre-unified test runner) is promoted on first use.

    Returns (pmids_c, hyde_text, query_hash, abstract_fetch_n, hyde_newly_generated).
    """
    cache_dir = CACHE_ROOT / domain / paper_id / provider
    cache_file = cache_dir / "pubmed_records.json"
    cache_dir.mkdir(parents=True, exist_ok=True)

    n_b = len(pmids_b)
    logger.info("  Stage C: n_stage_b=%d", n_b)

    hyde_text, hyde_newly_generated = _freeze_hyde(
        cache_dir=cache_dir,
        objectives=objectives,
        inclusion=inclusion,
        exclusion=exclusion,
        hyde_provider=hyde_provider,
        hyde_model=hyde_model,
        mode=mode,
        use_hyde=use_hyde,
    )
    query_hash = hashlib.sha1(hyde_text.encode("utf-8")).hexdigest()[:10]
    pmid_hash_src = "\n".join(sorted(str(p).strip() for p in pmids_b if str(p).strip()))
    pmid_hash = hashlib.sha1(pmid_hash_src.encode("utf-8")).hexdigest()[:10]

    score_jsonl = cache_dir / f"stagec_scored_records_medcpt_{query_hash}_{pmid_hash}.jsonl"
    score_meta_file = cache_dir / f"stagec_scored_records_medcpt_{query_hash}_{pmid_hash}.meta.json"
    # Legacy: test runner wrote query_hash-only filenames with full final scores
    legacy_score_jsonl = cache_dir / f"stagec_scored_records_medcpt_{query_hash}.jsonl"

    scored: list[dict] | None = None
    abstract_fetch_n = 0

    # ── Try primary cache ────────────────────────────────────────────────────
    if score_jsonl.exists() and score_meta_file.exists():
        try:
            meta_obj = json.loads(score_meta_file.read_text(encoding="utf-8"))
            n_ok = int(meta_obj.get("n_stage_b_input", -1)) == n_b
            hash_ok = str(meta_obj.get("pmid_set_hash", "")) == pmid_hash
            if n_ok and hash_ok:
                rows_tmp: list[dict] = []
                with score_jsonl.open("r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            rows_tmp.append(json.loads(line))
                if len(rows_tmp) == n_b and rows_tmp and "final" in rows_tmp[0]:
                    scored = rows_tmp
                    logger.info("  Scores loaded from cache: %d records", len(scored))
        except Exception:
            scored = None

    # ── Try legacy cache (query_hash only, pre-unification test runner) ──────
    if scored is None and legacy_score_jsonl.exists():
        try:
            rows_tmp = []
            with legacy_score_jsonl.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        rows_tmp.append(json.loads(line))
            legacy_pmids = {str(r.get("pmid", "")).strip() for r in rows_tmp}
            if (len(rows_tmp) == n_b
                    and legacy_pmids == set(pmids_b)
                    and rows_tmp
                    and "final" in rows_tmp[0]):
                scored = rows_tmp
                logger.info("  Legacy cache promoted: %s", legacy_score_jsonl.name)
                with score_jsonl.open("w", encoding="utf-8") as f:
                    for row in scored:
                        f.write(json.dumps(row, ensure_ascii=False) + "\n")
                score_meta_file.write_text(json.dumps({
                    "domain": domain, "paper_id": paper_id, "provider": provider,
                    "query_hash": query_hash, "pmid_set_hash": pmid_hash,
                    "n_stage_b_input": n_b, "records_scored_n": len(scored),
                    "dense_backend": "medcpt",
                    "promoted_from_legacy": legacy_score_jsonl.name,
                }, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            scored = None

    # ── Compute fresh scores ─────────────────────────────────────────────────
    if scored is None:
        records = fetch_all_abstracts(pmids_b, batch_size=100, cache_file=str(cache_file))
        n_with_abstract = sum(1 for r in records if r.get("abstract", ""))
        abstract_fetch_n = len(records) - n_with_abstract
        logger.info("  abstracts: %d present / %d total", n_with_abstract, len(records))

        rec_by_pmid = {str(r.get("pmid", "")).strip(): r for r in records}
        pmids_canonical = sorted(p for p in pmids_b if p in rec_by_pmid)
        recs_canonical = [rec_by_pmid[p] for p in pmids_canonical]

        scored_ranked = medcpt_ranker.rank(hyde_text, recs_canonical, top_k=len(recs_canonical))
        score_map = {
            str(r.get("pmid", "")).strip(): (
                float(r.get("_dense_score", 0.0)),
                float(r.get("_bm25_score", 0.0)),
            )
            for r in scored_ranked
        }
        corpus = [
            f"{rec_by_pmid[p].get('title', '')} {rec_by_pmid[p].get('abstract', '')[:500]}"
            for p in pmids_canonical
        ]
        doc_embs = np.asarray(medcpt_ranker.dense.encode_docs(corpus), dtype=np.float32)
        dense_vals = [score_map[p][0] for p in pmids_canonical]
        bm25_vals = [score_map[p][1] for p in pmids_canonical]
        comp = compute_stagec_final(
            pmids=pmids_canonical,
            dense_scores=dense_vals,
            bm25_scores=bm25_vals,
            doc_embs=doc_embs,
        )
        scored = [
            {
                "pmid": pmid,
                "dense_sim_medcpt": dense_vals[i],
                "bm25_score": bm25_vals[i],
                "s_q": comp["s_q"][i],
                "s_pos_mean": comp["s_pos_mean"][i],
                "s_neg_mean": comp["s_neg_mean"][i],
                "rank_s_q": comp["rank_s_q"][i],
                "rank_s_pos_mean": comp["rank_s_pos_mean"][i],
                "rank_s_neg_mean": comp["rank_s_neg_mean"][i],
                "final": comp["final"][i],
                "title": rec_by_pmid[pmid].get("title", ""),
            }
            for i, pmid in enumerate(pmids_canonical)
        ]
        with score_jsonl.open("w", encoding="utf-8") as f:
            for row in scored:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        score_meta_file.write_text(json.dumps({
            "domain": domain, "paper_id": paper_id, "provider": provider,
            "query_hash": query_hash, "pmid_set_hash": pmid_hash,
            "n_stage_b_input": n_b, "records_scored_n": len(scored),
            "dense_backend": "medcpt",
            "stagec_formula": "final=rank(s_q)+rank(s_pos_mean)-rank(s_neg_mean)",
            "pos_anchor_idx": comp.get("pos_anchor_idx"),
            "neg_anchor_idx": comp.get("neg_anchor_idx"),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("  MedCPT+BM25+Final scored %d records, saved", len(scored))

    actual_k = min(k, len(scored))
    ranked = sorted(scored, key=lambda r: (-float(r.get("final", -1e9)), str(r.get("pmid", ""))))
    pmids_c = [r["pmid"] for r in ranked[:actual_k]]
    logger.info("  Stage C top-K=%d (Final score)", actual_k)

    return pmids_c, hyde_text, query_hash, abstract_fetch_n, hyde_newly_generated


# ══════════════════════════════════════════════════════════════════════════════
# Training-mode helpers
# ══════════════════════════════════════════════════════════════════════════════

def _is_sr_of_srs(inclusion_text: str, objectives_text: str = "") -> bool:
    text = f"{inclusion_text}\n{objectives_text}".lower()
    markers = (
        "systematic review", "meta-analysis", "umbrella review",
        "review of reviews", "overview of reviews",
    )
    return any(m in text for m in markers)


def _true_recall_uid(query: str, gold_pmids: set[str]) -> tuple[int, float]:
    if not gold_pmids:
        return 0, 0.0
    gold_filter = "(" + " OR ".join(f"{p}[uid]" for p in sorted(gold_pmids)) + ")"
    combined = f"({query}) AND {gold_filter}"
    tp, _ = search_pubmed(combined, retmax=len(gold_pmids) + 10)
    return tp, tp / len(gold_pmids)


def _write_phase5_manual_prompt(
    *,
    paper_dir: Path,
    domain: str,
    paper_id: str,
    provider: str,
    objectives_text: str,
    inclusion_text: str,
    exclusion_text: str,
    current_query: str,
    current_hits: int,
    target_hits: int = 9999,
    current_recall: float = 0.0,
    gold_n: int = 0,
) -> Path:
    """
    Generate Phase5 manual-rewrite prompt.
    current_recall / gold_n are optional: in test mode recall is not computed during pipeline,
    so they default to 0 and the recall block is omitted from the prompt.
    """
    from phase5_rewriter import build_prompt as build_phase5_prompt, build_training_recall_block

    base_prompt_text = BASE_TEST_PROMPT_PATH.read_text(encoding="utf-8")
    query_laws_text = QUERY_LAWS_PATH.read_text(encoding="utf-8")
    recall_block = (
        build_training_recall_block(
            gold_n=gold_n,
            current_recall=current_recall,
            target_hits=target_hits,
        )
        if gold_n > 0 else ""
    )
    prompt_text = build_phase5_prompt(
        base_prompt_text=base_prompt_text,
        query_laws_text=query_laws_text,
        input_config={
            "objectives": objectives_text,
            "inclusion_criteria": inclusion_text,
            "exclusion_criteria": exclusion_text,
        },
        current_query=current_query,
        current_hits=current_hits,
        target_hits=target_hits,
        sr_of_srs=_is_sr_of_srs(inclusion_text, objectives_text),
        training_recall_block=recall_block,
    )
    out_dir = paper_dir / "model_outputs" / provider / "with_laws_stageA_prime_phase5_pending"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "phase5_manual_prompt.md"
    out_path.write_text(prompt_text, encoding="utf-8")
    meta_path = out_dir / "phase5_manual_prompt.meta.json"
    meta_path.write_text(json.dumps({
        "domain": domain, "paper_id": paper_id, "provider": provider,
        "current_hits": current_hits, "current_recall": round(current_recall, 4),
        "gold_n": gold_n, "target_hits": target_hits,
        "instruction": (
            "Send the contents of phase5_manual_prompt.md to chat, obtain one raw query line only, "
            "save the accepted query to with_laws_stageA_prime/normalized_query.txt, then rerun."
        ),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def _write_aprime_decisions_log(
    log_dir: Path,
    paper_id: str,
    domain: str,
    ts: str,
    records: list[dict],
) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{paper_id}_aprime_decisions_{ts}.jsonl"
    with log_path.open("a", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _run_stage_a_prime_with_recall_guard(
    *,
    paper_id: str,
    domain: str = "",
    base_query: str,
    gold_pmids: set[str],
    objectives_text: str,
    inclusion_text: str,
    hit_target: int = 9999,
    log_ts: str = "",
    recall_threshold: float = 0.02,
) -> tuple[str, int, float, str]:
    """Stage A' with Δrecall guard (training mode). Uses eval_stages tier narrowing."""
    import run_eval_training11_stages as eval_stages

    base_hits, _ = search_pubmed(base_query, retmax=1)
    if base_hits <= hit_target:
        _, r0 = _true_recall_uid(base_query, gold_pmids)
        return base_query, base_hits, r0, "skip_base_le_target"

    ap = eval_stages.run_stage_a_prime_phase1(
        base_query=base_query,
        gold_pmids=gold_pmids,
        initial_hits=base_hits,
        paper_id=paper_id,
        hit_target=hit_target,
        objectives_text=objectives_text,
        inclusion_text=inclusion_text,
        recall_threshold=recall_threshold,
    )
    query = ap["optimized_query"]
    hits = int(ap["final_hits"])
    recall = float(ap["final_recall"])
    note = "phase1"

    if log_ts:
        phase1_records: list[dict] = []
        for blk in ap.get("blocks_added", []):
            phase1_records.append({
                "phase": "phase1", "paper_id": paper_id, "domain": domain,
                "name": blk.get("name", ""), "syntax": blk.get("syntax", ""),
                "action": "ACCEPTED",
                "hits_before": blk.get("hits_before", 0),
                "hits_after": blk.get("hits_after", 0),
                "delta_hits": blk.get("hits_before", 0) - blk.get("hits_after", 0),
                "delta_recall": blk.get("delta_recall", 0.0),
                "recall_before": blk.get("recall_before", 0.0),
                "recall_after": blk.get("recall_after", 0.0),
            })
        for blk in ap.get("blocks_rejected", []):
            phase1_records.append({
                "phase": "phase1", "paper_id": paper_id, "domain": domain,
                "name": blk.get("name", ""), "syntax": blk.get("syntax", ""),
                "action": "REJECTED",
                "hits_before": blk.get("hits_before", 0),
                "hits_after": blk.get("hits_after", 0),
                "delta_hits": blk.get("hits_before", 0) - blk.get("hits_after", 0),
                "delta_recall": blk.get("delta_recall", 0.0),
                "recall_before": blk.get("recall_before", 0.0),
                "recall_after": blk.get("recall_after", 0.0),
            })
        if phase1_records:
            _write_aprime_decisions_log(LOG_DIR, paper_id, domain, log_ts, phase1_records)

    if hits >= hit_target:
        current_hits = hits
        current_recall = recall
        phase4_applied = 0
        phase4_rounds = 0

        # TIER_ORDER_REWRITE_BEGIN
        tier_fns = [
            eval_stages._tier1_candidates_from_raw,
            eval_stages._tier9_candidates_from_raw,
            eval_stages._tier6_candidates_from_raw,
            eval_stages._tier5_candidates_from_raw,
            eval_stages._tier7_candidates_from_raw,
            eval_stages._tier3_candidates_from_raw,
            eval_stages._tier2_candidates_from_raw,
            eval_stages._tier4_candidates_from_raw,
            eval_stages._tier8_candidates_from_raw,
            eval_stages._tier10_candidates_from_raw,
            eval_stages._tierF_candidates_from_raw,
        ]
        # TIER_ORDER_REWRITE_END

        while current_hits >= hit_target:
            phase4_rounds += 1
            raw_part, suffix_part = eval_stages._split_raw_and_suffix(query)
            tier_candidates: list[tuple[str, str]] = []
            for fn in tier_fns:
                prefix = fn.__name__.split("_")[1]  # "tier1" .. "tier10"
                for desc, new_raw in fn(raw_part):
                    tier_candidates.append((f"{prefix}_{desc}", new_raw + suffix_part))
            for desc, cand_q in eval_stages._tierF_candidates_from_raw(raw_part, query):
                tier_candidates.append((desc, cand_q))

            if not tier_candidates:
                note = f"phase3_stopped_no_candidates_round{phase4_rounds}"
                break

            phase3_log_records: list[dict] = []
            improved_valid: list[tuple[str, str, int, float]] = []
            for desc, cand_q in tier_candidates:
                tier_label = desc.split("_")[0] if "_" in desc else "tierF"
                hits_cand, _ = search_pubmed(cand_q, retmax=1)
                if hits_cand >= current_hits:
                    if log_ts:
                        phase3_log_records.append({
                            "phase": "phase3", "paper_id": paper_id, "domain": domain,
                            "tier": tier_label, "desc": desc, "action": "NO_REDUCTION",
                            "hits_before": current_hits, "hits_after": hits_cand,
                            "delta_hits": current_hits - hits_cand,
                            "delta_recall": 0.0, "round_number": phase4_rounds,
                        })
                    continue
                _, recall_cand = _true_recall_uid(cand_q, gold_pmids)
                delta_recall = round(current_recall - recall_cand, 4)
                if delta_recall > recall_threshold:
                    if log_ts:
                        phase3_log_records.append({
                            "phase": "phase3", "paper_id": paper_id, "domain": domain,
                            "tier": tier_label, "desc": desc, "action": "REJECTED",
                            "hits_before": current_hits, "hits_after": hits_cand,
                            "delta_hits": current_hits - hits_cand,
                            "delta_recall": delta_recall, "round_number": phase4_rounds,
                        })
                    continue
                if log_ts:
                    phase3_log_records.append({
                        "phase": "phase3", "paper_id": paper_id, "domain": domain,
                        "tier": tier_label, "desc": desc, "action": "ACCEPTED",
                        "hits_before": current_hits, "hits_after": hits_cand,
                        "delta_hits": current_hits - hits_cand,
                        "delta_recall": delta_recall, "round_number": phase4_rounds,
                    })
                improved_valid.append((desc, cand_q, hits_cand, recall_cand))

            if log_ts and phase3_log_records:
                _write_aprime_decisions_log(LOG_DIR, paper_id, domain, log_ts, phase3_log_records)

            if not improved_valid:
                note = f"phase3_stopped_no_improvement_round{phase4_rounds}"
                break

            desc, next_query, next_hits, next_recall = min(
                improved_valid, key=lambda x: abs(x[2] - hit_target)
            )
            query = next_query
            current_hits = next_hits
            current_recall = next_recall
            phase4_applied += 1
            note = f"phase3_applied_{phase4_applied}_last_{desc}"
            if current_hits < hit_target:
                break

        hits = current_hits
        recall = current_recall

    return query, hits, recall, note


def _load_papers_training(
    provider: str,
    condition: str,
    query_provider: str | None = None,
    query_condition: str | None = None,
) -> list[dict]:
    papers: list[dict] = []
    qp = query_provider or provider
    qc = query_condition or condition
    for domain_dir in sorted(DATA_DIR.iterdir()):
        if not domain_dir.is_dir() or domain_dir.name.startswith("_"):
            continue
        for paper_dir in sorted(domain_dir.iterdir()):
            if not paper_dir.is_dir():
                continue
            paper_id = paper_dir.name
            q_path = paper_dir / "model_outputs" / qp / qc / "normalized_query.txt"
            if not q_path.exists():
                continue
            cfg = json.loads((paper_dir / "input_config.json").read_text(encoding="utf-8"))
            det = json.loads((paper_dir / "input_config_detailed.json").read_text(encoding="utf-8"))
            papers.append({
                "domain": domain_dir.name,
                "paper_id": paper_id,
                "base_query": q_path.read_text(encoding="utf-8").strip(),
                "query_provider": qp,
                "query_condition": qc,
                "gold_pmids": {str(x).strip() for x in cfg.get("gold_pmids", []) if str(x).strip()},
                "objectives": det.get("objectives", ""),
                "inclusion_criteria": det.get("inclusion_criteria", ""),
                "exclusion_criteria": det.get("exclusion_criteria", ""),
                "human_query": det.get("pmid_query", ""),
            })
    return papers


def _a_prime_output_condition(source_condition: str) -> str:
    """
    Avoid overwriting a manual Phase 5 query when it is used as the input source.
    """
    if source_condition == "with_laws_stageA_prime":
        return "with_laws_stageA_prime_rerun"
    return "with_laws_stageA_prime"


def _run_one_paper_training(
    *,
    paper: dict,
    provider: str,
    condition: str,
    hyde_provider: str,
    medcpt_ranker: HybridRanker,
    k_fixed: int,
    stagec_gate_hits: int,
    stagec_floor_hits: int,
    stagec_cut_percent: float,
    use_fixed_k: bool,
    hyde_model: str,
    use_hyde: bool,
    stagec_min_hits: int,
    ts: str,
    recall_threshold: float = 0.02,
) -> tuple[list[dict], dict]:
    domain = paper["domain"]
    paper_id = paper["paper_id"]
    cache_dir = CACHE_ROOT / domain / paper_id / provider
    cache_file = cache_dir / "pubmed_records.json"
    cache_dir.mkdir(parents=True, exist_ok=True)

    gold = paper["gold_pmids"]
    gold_n = len(gold)
    paper_dir = DATA_DIR / domain / paper_id
    a_prime_condition = _a_prime_output_condition(condition)

    # Base (raw query) — recall is safe to compute in training mode
    base_query = paper["base_query"]
    base_hits, _ = search_pubmed(base_query, retmax=1)
    base_tp, base_recall = _true_recall_uid(base_query, gold)

    # Stage A' with recall guard
    prime_query, prime_hits, prime_recall, prime_note = _run_stage_a_prime_with_recall_guard(
        paper_id=paper_id,
        domain=domain,
        base_query=base_query,
        gold_pmids=gold,
        objectives_text=paper["objectives"],
        inclusion_text=paper["inclusion_criteria"],
        hit_target=9999,
        log_ts=ts,
        recall_threshold=recall_threshold,
    )
    prime_tp = int(round(prime_recall * gold_n))
    phase5_required = prime_hits >= 9999
    phase5_pending = phase5_required
    phase5_prompt_path = ""

    save_stage_query_snapshot(
        paper_dir=paper_dir,
        results_dir=RESULTS_DIR,
        dataset_split="training_eval_non27",
        domain=domain,
        paper_id=paper_id,
        provider=provider,
        stage="A_prime",
        condition=a_prime_condition,
        source_condition=condition,
        query_text=prime_query,
        query_type="pubmed_boolean",
        extra={
            "prime_total_hits": prime_hits,
            "target": 9999,
            "prime_gate_ok_for_stage_a": prime_hits < 9999,
            "prime_impl": f"phase1+phase3 recall_guard<={recall_threshold}",
            "prime_note": prime_note,
        },
    )

    if phase5_required:
        phase5_prompt_file = _write_phase5_manual_prompt(
            paper_dir=paper_dir,
            domain=domain,
            paper_id=paper_id,
            provider=provider,
            objectives_text=paper["objectives"],
            inclusion_text=paper["inclusion_criteria"],
            exclusion_text=paper["exclusion_criteria"],
            current_query=prime_query,
            current_hits=prime_hits,
            current_recall=prime_recall,
            gold_n=gold_n,
            target_hits=9999,
        )
        phase5_prompt_path = str(phase5_prompt_file)
        logger.warning(
            "[%s] Phase5 required: prime_hits=%d >= 9999. Prompt saved: %s",
            paper_id, prime_hits, phase5_prompt_file,
        )
        return [], {
            "domain": domain, "paper_id": paper_id, "gold_n": gold_n,
            "base_hits": base_hits, "base_tp": base_tp, "base_recall": round(base_recall, 4),
            "a_prime_hits": prime_hits, "a_prime_tp": prime_tp, "a_prime_recall": round(prime_recall, 4),
            "phase5_required": True, "phase5_pending": True, "phase5_prompt_path": phase5_prompt_path,
            "prime_gate_failed": True,
            "stagec_gate_hits": stagec_gate_hits, "stagec_floor_hits": stagec_floor_hits,
            "stagec_cut_percent": stagec_cut_percent, "use_fixed_k": use_fixed_k,
            "status": "phase5_pending_manual_rewrite",
        }

    # Stage A
    parse_log = LOG_DIR / f"{paper_id}_training_stageA_parse_{ts}.jsonl"
    parsed, q_a = parse_and_log(
        paper_id=paper_id,
        exclusion_text=paper["exclusion_criteria"],
        base_query=prime_query,
        log_path=parse_log,
    )
    stage_a_total_hits, pmids_a = search_pubmed(q_a, retmax=100000)
    stage_a_hits = int(stage_a_total_hits)
    stage_a_retrieved_n = len(pmids_a)
    stage_a_retrieval_capped = stage_a_total_hits > stage_a_retrieved_n
    stage_a_tp, stage_a_recall = _true_recall_uid(q_a, gold)
    save_stage_query_snapshot(
        paper_dir=paper_dir,
        results_dir=RESULTS_DIR,
        dataset_split="training_eval_non27",
        domain=domain,
        paper_id=paper_id,
        provider=provider,
        stage="A",
        condition="with_laws_stageA",
        source_condition=a_prime_condition,
        query_text=q_a,
        query_type="pubmed_boolean",
        extra={
            "stage_a_total_hits": stage_a_hits,
            "stage_a_retrieved_n": stage_a_retrieved_n,
            "stage_a_retrieval_capped": stage_a_retrieval_capped,
        },
    )

    # Stage B
    meta_b = fetch_all_metadata(pmids_a, batch_size=200, cache_file=str(cache_file))
    kept_b, _ = stage_b_filter(meta_b, parsed)
    pmids_b = [r["pmid"] for r in kept_b]
    stage_b_hits = len(pmids_b)
    stage_b_recall = (len(gold & set(pmids_b)) / gold_n) if gold_n else 0.0
    save_stage_query_snapshot(
        paper_dir=paper_dir,
        results_dir=RESULTS_DIR,
        dataset_split="training_eval_non27",
        domain=domain,
        paper_id=paper_id,
        provider=provider,
        stage="B",
        condition="with_laws_stageB",
        source_condition="with_laws_stageA",
        query_text=q_a,
        query_type="pubmed_boolean",
        extra={
            "stage_b_total_hits": stage_b_hits,
            "stage_b_input_n": stage_a_retrieved_n,
            "stage_b_input_capped": stage_a_retrieval_capped,
        },
    )

    # Stage C
    if use_fixed_k:
        k = min(k_fixed, stage_b_hits)
    else:
        k = _compute_kept_n_with_gate_floor(
            stage_b_hits=stage_b_hits,
            gate_hits=stagec_gate_hits,
            floor_hits=stagec_floor_hits,
            cut_percent=stagec_cut_percent,
        )

    if stage_b_hits < stagec_min_hits or k >= stage_b_hits:
        # Passthrough: stage_b too small or gate/floor already covers all records
        stage_c_mode = "passthrough_stageb"
        stage_c_k = stage_b_hits
        rec_c = stage_b_recall
        query_hash = ""
        hyde_text = ""
        abstract_fetch_n = 0
        hyde_newly_generated = False
        save_stage_query_snapshot(
            paper_dir=paper_dir,
            results_dir=RESULTS_DIR,
            dataset_split="training_eval_non27",
            domain=domain,
            paper_id=paper_id,
            provider=provider,
            stage="C",
            condition="with_laws_stageC_passthrough_le1000",
            source_condition="with_laws_stageB",
            query_text=q_a,
            query_type="pubmed_boolean",
            extra={
                "stage_c_mode": stage_c_mode,
                "stagec_min_hits": stagec_min_hits,
                "k_used": stage_c_k,
                "passthrough_reason": "stage_b_hits_below_threshold",
            },
        )
    else:
        stage_c_mode = "ranked"
        pmids_c, hyde_text, query_hash, abstract_fetch_n, hyde_newly_generated = _run_stage_c(
            pmids_b=pmids_b,
            domain=domain,
            paper_id=paper_id,
            provider=provider,
            hyde_provider=hyde_provider,
            hyde_model=hyde_model,
            objectives=paper["objectives"],
            inclusion=paper["inclusion_criteria"],
            exclusion=paper["exclusion_criteria"],
            k=k,
            medcpt_ranker=medcpt_ranker,
            mode="training",
            use_hyde=use_hyde,
        )
        stage_c_k = len(pmids_c)
        rec_c = (len(gold & set(pmids_c)) / gold_n) if gold_n else 0.0
        save_stage_query_snapshot(
            paper_dir=paper_dir,
            results_dir=RESULTS_DIR,
            dataset_split="training_eval_non27",
            domain=domain,
            paper_id=paper_id,
            provider=provider,
            stage="C",
            condition="with_laws_stageC_k500",
            source_condition="with_laws_stageB",
            query_text=hyde_text,
            query_type="hyde_pseudo_abstract",
            extra={
                "stage_c_mode": stage_c_mode,
                "k_used": stage_c_k,
                "query_hash": query_hash,
                "stagec_formula": "final=rank(s_q)+rank(s_pos_mean)-rank(s_neg_mean)",
                "stagec_gate_hits": stagec_gate_hits,
                "stagec_floor_hits": stagec_floor_hits,
                "stagec_cut_percent": stagec_cut_percent,
                "use_fixed_k": use_fixed_k,
            },
        )

    row: dict = {
        "domain": domain,
        "paper_id": paper_id,
        "method": "final_reference_v1",
        "gold_n": gold_n,
        "base_hits": base_hits,
        "base_tp": base_tp,
        "base_recall": round(base_recall, 4),
        "a_prime_hits": prime_hits,
        "a_prime_tp": prime_tp,
        "a_prime_recall": round(prime_recall, 4),
        "stage_a_hits": stage_a_hits,
        "stage_a_retrieved_n": stage_a_retrieved_n,
        "stage_a_retrieval_capped": stage_a_retrieval_capped,
        "stage_a_tp": stage_a_tp,
        "stage_a_recall": round(stage_a_recall, 4),
        "stage_b_input_n": stage_a_retrieved_n,
        "stage_b_input_capped": stage_a_retrieval_capped,
        "stage_b_hits": stage_b_hits,
        "stage_b_recall": round(stage_b_recall, 4),
        "stage_c_mode": stage_c_mode,
        "stage_c_hits": stage_c_k,
        "stage_c_recall": round(rec_c, 4),
        "delta_recall_c_minus_b": round(rec_c - stage_b_recall, 4),
        "phase5_required": phase5_required,
        "phase5_pending": phase5_pending,
        "phase5_prompt_path": phase5_prompt_path,
        "prime_gate_failed": bool(prime_hits >= 9999),
        "stagec_gate_hits": stagec_gate_hits,
        "stagec_floor_hits": stagec_floor_hits,
        "stagec_cut_percent": stagec_cut_percent,
        "use_fixed_k": use_fixed_k,
        "query_hash": query_hash,
    }
    status: dict = {
        "domain": domain, "paper_id": paper_id, "gold_n": gold_n,
        "base_hits": base_hits, "base_tp": base_tp, "base_recall": round(base_recall, 4),
        "a_prime_hits": prime_hits, "a_prime_tp": prime_tp, "a_prime_recall": round(prime_recall, 4),
        "stage_a_hits": stage_a_hits, "stage_a_retrieved_n": stage_a_retrieved_n,
        "stage_a_retrieval_capped": stage_a_retrieval_capped,
        "stage_a_tp": stage_a_tp, "stage_a_recall": round(stage_a_recall, 4),
        "stage_b_input_n": stage_a_retrieved_n, "stage_b_input_capped": stage_a_retrieval_capped,
        "stage_b_hits": stage_b_hits, "stage_b_recall": round(stage_b_recall, 4),
        "stage_c_k": stage_c_k,
        "phase5_required": phase5_required, "phase5_pending": phase5_pending,
        "phase5_prompt_path": phase5_prompt_path,
        "prime_gate_failed": bool(prime_hits >= 9999),
        "stagec_gate_hits": stagec_gate_hits, "stagec_floor_hits": stagec_floor_hits,
        "stagec_cut_percent": stagec_cut_percent, "use_fixed_k": use_fixed_k,
        "status": "ok",
    }
    return [row], status


# ══════════════════════════════════════════════════════════════════════════════
# Test-mode helpers
# ══════════════════════════════════════════════════════════════════════════════

def _find_base_query_path(paper_dir: Path, provider: str, condition: str) -> Path | None:
    p = paper_dir / "model_outputs" / provider / condition / "normalized_query.txt"
    return p if p.exists() else None


def _uid_recall(query: str, gold_pmids: set[str]) -> tuple[int, float]:
    """UID-based TP/recall. No recall computed during pipeline (post-hoc only)."""
    if not gold_pmids:
        return 0, 0.0
    gold_filter = "(" + " OR ".join(f"{p}[uid]" for p in sorted(gold_pmids)) + ")"
    combined = f"({query}) AND {gold_filter}"
    tp, _ = search_pubmed(combined, retmax=len(gold_pmids) + 10)
    return tp, tp / len(gold_pmids)


def _run_pipeline_test(
    *,
    test_papers: list[dict],
    provider: str,
    condition: str,
    query_condition: str | None = None,
    hyde_provider: str,
    hyde_model: str,
    medcpt_ranker: HybridRanker,
    target: int,
    stagec_min_hits: int,
    stagec_gate_hits: int,
    stagec_floor_hits: int,
    stagec_cut_percent: float,
    use_fixed_k: bool,
    k: int,
    metadata_batch_size: int,
    ts: str,
) -> tuple[list[dict], dict[tuple[str, str], list[str]], dict[tuple[str, str], list[str]]]:
    """Phase 1 (test mode): A' -> A -> B -> C with no recall. Returns (stage_rows, pmids_b_store, pmids_c_store)."""
    stage_rows: list[dict] = []
    pmids_b_store: dict[tuple[str, str], list[str]] = {}
    pmids_c_store: dict[tuple[str, str], list[str]] = {}

    for item in test_papers:
        domain = item["domain_folder"]
        paper = item["paper_folder"]
        logger.info("Processing %s / %s", domain, paper)

        test_paper_dir = TEST_DIR / domain / paper
        query_path = _find_base_query_path(test_paper_dir, provider, query_condition or condition)
        if query_path is None:
            logger.warning("Base query missing: %s / %s / %s", provider, query_condition or condition, paper)
            continue

        detailed_path = test_paper_dir / "input_config_detailed.json"
        if not detailed_path.exists():
            logger.warning("input_config_detailed.json missing: %s", detailed_path)
            continue

        base_query = query_path.read_text(encoding="utf-8-sig").strip()
        detailed = json.loads(detailed_path.read_text(encoding="utf-8-sig"))
        exclusion_text = detailed.get("exclusion_criteria", "")
        inclusion_text = detailed.get("inclusion_criteria", "")
        objectives_text = detailed.get("objectives", "")
        human_query = detailed.get("pmid_query", "")
        a_prime_condition = _a_prime_output_condition(query_condition or condition)

        raw_hits, _ = search_pubmed(base_query, retmax=1)

        # Stage A' (no recall guard — test mode)
        prime_query, prime_hits, prime_meta = run_prime_no_recall(
            base_query=base_query,
            inclusion_text=inclusion_text,
            exclusion_text=exclusion_text,
            human_query=human_query,
            target_hits=target,
            strict_less_than=True,
            objectives_text=objectives_text,
        )
        prime_gate_ok = prime_hits < target
        save_stage_query_snapshot(
            paper_dir=test_paper_dir,
            results_dir=RESULTS_DIR,
            dataset_split="test",
            domain=domain,
            paper_id=paper,
            provider=provider,
            stage="A_prime",
            condition=a_prime_condition,
            source_condition=query_condition or condition,
            query_text=prime_query,
            query_type="pubmed_boolean",
            extra={
                "prime_total_hits": prime_hits,
                "target": target,
                "prime_gate_ok_for_stage_a": prime_gate_ok,
                "phase2_attempted": bool(prime_meta.get("phase2_attempted", False)),
                "phase2_no_further_reduction": bool(prime_meta.get("phase2_no_further_reduction", False)),
            },
        )

        # Initialise empty values for gate-failed papers
        query_a = ""
        stage_a_hits = None
        pmids_a: list[str] = []
        capped = False
        pmids_for_b: list[str] = []
        excluded_b: list = []
        pmids_b: list[str] = []
        pmids_c: list[str] = []
        query_hash = ""
        hyde_text = ""
        abstract_fetch_n = 0
        hyde_newly_generated = False
        actual_k = 0
        stage_c_mode = "not_run_prime_gate_failed"
        phase5_prompt_path = ""

        if not prime_gate_ok:
            # Phase5 prompt generation (test mode: no recall available, so gold_n=0)
            try:
                phase5_prompt_file = _write_phase5_manual_prompt(
                    paper_dir=test_paper_dir,
                    domain=domain,
                    paper_id=paper,
                    provider=provider,
                    objectives_text=objectives_text,
                    inclusion_text=inclusion_text,
                    exclusion_text=exclusion_text,
                    current_query=prime_query,
                    current_hits=prime_hits,
                    target_hits=target,
                )
                phase5_prompt_path = str(phase5_prompt_file)
                logger.warning(
                    "[%s] Phase5 required: prime_hits=%d >= %d. Prompt saved: %s",
                    paper, prime_hits, target, phase5_prompt_file,
                )
            except Exception as exc:
                logger.error("[%s] Phase5 prompt generation failed: %s", paper, exc)

        if prime_gate_ok:
            # Stage A
            parse_log = LOG_DIR / f"{paper}_test_stageA_parse_{ts}.jsonl"
            parsed, query_a = parse_and_log(
                paper_id=paper,
                exclusion_text=exclusion_text,
                base_query=prime_query,
                log_path=parse_log,
            )
            stage_a_hits, pmids_a = search_pubmed(query_a, sort="relevance", retmax=100000)
            save_stage_query_snapshot(
                paper_dir=test_paper_dir,
                results_dir=RESULTS_DIR,
                dataset_split="test",
                domain=domain,
                paper_id=paper,
                provider=provider,
                stage="A",
                condition="with_laws_stageA",
                source_condition=a_prime_condition,
                query_text=query_a,
                query_type="pubmed_boolean",
                extra={"stage_a_total_hits": stage_a_hits},
            )

            # Stage B
            capped = len(pmids_a) > target
            pmids_for_b = pmids_a[:target] if capped else pmids_a
            meta_b = fetch_all_metadata(
                pmids_for_b,
                batch_size=metadata_batch_size,
                cache_file=str(CACHE_ROOT / domain / paper / provider / "pubmed_records.json"),
            )
            kept_b, excluded_b = stage_b_filter(meta_b, parsed)
            pmids_b = [r["pmid"] for r in kept_b]
            pmids_b_store[(domain, paper)] = pmids_b
            logger.info("  Stage B: %d records", len(pmids_b))
            save_stage_query_snapshot(
                paper_dir=test_paper_dir,
                results_dir=RESULTS_DIR,
                dataset_split="test",
                domain=domain,
                paper_id=paper,
                provider=provider,
                stage="B",
                condition="with_laws_stageB",
                source_condition="with_laws_stageA",
                query_text=query_a,
                query_type="pubmed_boolean",
                extra={
                    "stage_b_total_hits": len(pmids_b),
                    "stage_b_input_n": len(pmids_for_b),
                    "stage_b_excluded_n": len(excluded_b),
                    "stage_b_capped_top9999": capped,
                },
            )

            if len(pmids_b) >= stagec_min_hits:
                stage_c_mode = "ranked"
                k_for_stage_c = (
                    min(k, len(pmids_b)) if use_fixed_k
                    else _compute_kept_n_with_gate_floor(
                        stage_b_hits=len(pmids_b),
                        gate_hits=stagec_gate_hits,
                        floor_hits=stagec_floor_hits,
                        cut_percent=stagec_cut_percent,
                    )
                )
                pmids_c, hyde_text, query_hash, abstract_fetch_n, hyde_newly_generated = _run_stage_c(
                    pmids_b=pmids_b,
                    domain=domain,
                    paper_id=paper,
                    provider=provider,
                    hyde_provider=hyde_provider,
                    hyde_model=hyde_model,
                    objectives=objectives_text,
                    inclusion=inclusion_text,
                    exclusion=exclusion_text,
                    k=k_for_stage_c,
                    medcpt_ranker=medcpt_ranker,
                    mode="test",
                )
                actual_k = len(pmids_c)
                pmids_c_store[(domain, paper)] = pmids_c
                save_stage_query_snapshot(
                    paper_dir=test_paper_dir,
                    results_dir=RESULTS_DIR,
                    dataset_split="test",
                    domain=domain,
                    paper_id=paper,
                    provider=provider,
                    stage="C",
                    condition="with_laws_stageC_k500",
                    source_condition="with_laws_stageB",
                    query_text=hyde_text,
                    query_type="hyde_pseudo_abstract",
                    extra={
                        "stage_c_mode": stage_c_mode,
                        "stagec_min_hits": stagec_min_hits,
                        "stagec_gate_hits": stagec_gate_hits,
                        "stagec_floor_hits": stagec_floor_hits,
                        "stagec_cut_percent": stagec_cut_percent,
                        "use_fixed_k": use_fixed_k,
                        "final_formula": "rank(s_q)+rank(s_pos_mean)-rank(s_neg_mean)",
                        "k_used": actual_k,
                        "query_hash": query_hash,
                        "abstract_fetch_n": abstract_fetch_n,
                        "hyde_newly_generated": hyde_newly_generated,
                    },
                )
            else:
                stage_c_mode = "passthrough_stageb"
                pmids_c = list(pmids_b)
                actual_k = len(pmids_c)
                pmids_c_store[(domain, paper)] = pmids_c
                save_stage_query_snapshot(
                    paper_dir=test_paper_dir,
                    results_dir=RESULTS_DIR,
                    dataset_split="test",
                    domain=domain,
                    paper_id=paper,
                    provider=provider,
                    stage="C",
                    condition="with_laws_stageC_passthrough_le1000",
                    source_condition="with_laws_stageB",
                    query_text=query_a,
                    query_type="pubmed_boolean",
                    extra={
                        "stage_c_mode": stage_c_mode,
                        "stagec_min_hits": stagec_min_hits,
                        "stagec_gate_hits": stagec_gate_hits,
                        "stagec_floor_hits": stagec_floor_hits,
                        "stagec_cut_percent": stagec_cut_percent,
                        "use_fixed_k": use_fixed_k,
                        "k_used": actual_k,
                        "passthrough_reason": "stage_b_hits_below_threshold",
                    },
                )

        stage_rows.append({
            "domain": domain,
            "paper_id": paper,
            "provider": provider,
            "condition": condition,
            "base_query_source": str(query_path.relative_to(ROOT)),
            "raw_total_hits": raw_hits,
            "prime_total_hits": prime_hits,
            "prime_gate_ok_for_stage_a": prime_gate_ok,
            "stage_a_total_hits": stage_a_hits,
            "stage_a_retrieved_n": len(pmids_a),
            "stage_b_input_n": len(pmids_for_b),
            "stage_b_total_hits": len(pmids_b),
            "stage_b_excluded_n": len(excluded_b),
            "stage_b_capped_top9999": capped,
            "stage_c_k_used": actual_k,
            "stage_c_mode": stage_c_mode,
            "stagec_min_hits": stagec_min_hits,
            "stagec_gate_hits": stagec_gate_hits,
            "stagec_floor_hits": stagec_floor_hits,
            "stagec_cut_percent": stagec_cut_percent,
            "use_fixed_k": use_fixed_k,
            "stage_c_alpha": None,
            "stage_c_formula": (
                "rank(s_q)+rank(s_pos_mean)-rank(s_neg_mean)"
                if prime_gate_ok and stage_c_mode == "ranked" else None
            ),
            "stage_c_device_effective": (
                getattr(medcpt_ranker.dense, "device", None)
                if prime_gate_ok and stage_c_mode == "ranked" else None
            ),
            "stage_c_query_hash": query_hash,
            "stage_c_abstract_fetch_n": abstract_fetch_n if prime_gate_ok and stage_c_mode == "ranked" else None,
            "stage_c_hyde_newly_generated": hyde_newly_generated if prime_gate_ok and stage_c_mode == "ranked" else None,
            "phase5_prompt_path": phase5_prompt_path,
            "prime_phase2_attempted": bool(prime_meta.get("phase2_attempted", False)),
            "prime_phase2_no_further_reduction": bool(prime_meta.get("phase2_no_further_reduction", False)),
            "raw_query": base_query,
            "prime_query": prime_query,
            "stage_a_query": query_a,
        })

    return stage_rows, pmids_b_store, pmids_c_store


def _compute_posthoc_recall(
    stage_rows: list[dict],
    pmids_b_store: dict[tuple[str, str], list[str]],
    pmids_c_store: dict[tuple[str, str], list[str]],
) -> list[dict]:
    """Phase 2 (test mode): post-hoc recall for all stages using gold_pmids."""
    final_rows: list[dict] = []
    for r in stage_rows:
        domain = r["domain"]
        paper = r["paper_id"]
        gold_path = TEST_DIR / domain / paper / "gold_pmids.json"
        gold_obj = json.loads(gold_path.read_text(encoding="utf-8-sig"))
        gold_pmids = {str(x).strip() for x in gold_obj.get("gold_pmids", []) if str(x).strip()}
        gold_n = len(gold_pmids)
        logger.info("Recall for %s  gold=%d", paper, gold_n)

        tp_raw, rec_raw = _uid_recall(r["raw_query"], gold_pmids)
        tp_prime, rec_prime = _uid_recall(r["prime_query"], gold_pmids)

        gate_ok = bool(r.get("prime_gate_ok_for_stage_a", False))
        if gate_ok:
            tp_a, rec_a = _uid_recall(r["stage_a_query"], gold_pmids)
            pmids_b_set = set(pmids_b_store.get((domain, paper), []))
            tp_b = len(gold_pmids & pmids_b_set)
            rec_b = tp_b / gold_n if gold_n else 0.0
            pmids_c_set = set(pmids_c_store.get((domain, paper), []))
            tp_c = len(gold_pmids & pmids_c_set)
            rec_c = tp_c / gold_n if gold_n else 0.0
        else:
            tp_a = rec_a = tp_b = rec_b = tp_c = rec_c = None

        row = {k: v for k, v in r.items() if k not in {"raw_query", "prime_query", "stage_a_query"}}
        row.update({
            "gold_n": gold_n,
            "raw_tp": tp_raw,
            "raw_recall": round(rec_raw, 4),
            "prime_tp": tp_prime,
            "prime_recall": round(rec_prime, 4),
            "stage_a_tp": tp_a,
            "stage_a_recall": round(rec_a, 4) if rec_a is not None else None,
            "stage_b_tp": tp_b,
            "stage_b_recall": round(rec_b, 4) if rec_b is not None else None,
            "stage_c_tp": tp_c,
            "stage_c_recall": round(rec_c, 4) if rec_c is not None else None,
            "delta_recall_prime_minus_raw": round(rec_prime - rec_raw, 4),
            "delta_recall_A_minus_prime": round(rec_a - rec_prime, 4) if gate_ok else None,
            "delta_recall_B_minus_A": round(rec_b - rec_a, 4) if gate_ok else None,
            "delta_recall_C_minus_B": round(rec_c - rec_b, 4) if gate_ok else None,
            "delta_hits_prime_minus_raw": int(r["prime_total_hits"]) - int(r["raw_total_hits"]),
            "delta_hits_A_minus_prime": (int(r["stage_a_total_hits"]) - int(r["prime_total_hits"])) if gate_ok else None,
            "delta_hits_B_minus_A": (int(r["stage_b_total_hits"]) - int(r["stage_a_total_hits"])) if gate_ok else None,
            "delta_hits_C_minus_B": (int(r["stage_c_k_used"]) - int(r["stage_b_total_hits"])) if gate_ok else None,
        })
        final_rows.append(row)
    return final_rows


# ══════════════════════════════════════════════════════════════════════════════
# Output helpers
# ══════════════════════════════════════════════════════════════════════════════

def _save_test_outputs(
    final_rows: list[dict],
    args: argparse.Namespace,
    ts: str,
) -> None:
    suf = f"{args.provider}_{ts}"

    out_csv = RESULTS_DIR / f"test_prime_A_B_C_posthoc_recall_{suf}.csv"
    if not final_rows:
        logger.warning("No test rows produced; skipping test output files.")
        return
    with out_csv.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(final_rows[0].keys()))
        w.writeheader()
        w.writerows(final_rows)
    logger.info("Saved: %s", out_csv)

    stage_table_csv = RESULTS_DIR / f"test_prime_A_B_C_stage_table_{suf}.csv"
    stage_cols = [
        "domain", "paper_id",
        "raw_total_hits", "raw_recall",
        "prime_total_hits", "prime_recall",
        "stage_a_total_hits", "stage_a_recall",
        "stage_b_total_hits", "stage_b_recall",
        "stage_c_k_used", "stage_c_recall",
        "stage_c_alpha", "prime_gate_ok_for_stage_a",
    ]
    with stage_table_csv.open("w", newline="", encoding="utf-8-sig") as f:
        w2 = csv.DictWriter(f, fieldnames=stage_cols, extrasaction="ignore")
        w2.writeheader()
        w2.writerows(final_rows)
    logger.info("Saved: %s", stage_table_csv)

    stage_table_md = RESULTS_DIR / f"test_prime_A_B_C_stage_table_{suf}.md"
    md_lines = [
        f"# Test27 A'->A->B->C Stage Table ({args.provider} / {args.condition}) {ts}",
        "",
        f"- K: `{args.k}`",
        f"- stagec_gate_hits: `{args.stagec_gate_hits}`",
        f"- stagec_floor_hits: `{args.stagec_floor_hits}`",
        f"- stagec_cut_percent: `{args.stagec_cut_percent}`",
        f"- stagec_min_hits: `{args.stagec_min_hits}`",
        "",
        "| domain | paper_id | raw_hits | raw_rec | prime_hits | prime_rec | "
        "A_hits | A_rec | B_hits | B_rec | C_k | C_rec | gate |",
        "|--------|----------|----------|---------|------------|-----------|"
        "-------|-------|--------|-------|-----|-------|------|",
    ]
    for r in final_rows:
        md_lines.append(
            f"| {r['domain']} | {r['paper_id']} | {r['raw_total_hits']} | {r['raw_recall']} | "
            f"{r['prime_total_hits']} | {r['prime_recall']} | "
            f"{r['stage_a_total_hits']} | {r['stage_a_recall']} | "
            f"{r['stage_b_total_hits']} | {r['stage_b_recall']} | "
            f"{r['stage_c_k_used']} | {r['stage_c_recall']} | "
            f"{r['prime_gate_ok_for_stage_a']} |"
        )
    stage_table_md.write_text("\n".join(md_lines), encoding="utf-8")
    logger.info("Saved: %s", stage_table_md)

    keys = ["raw_recall", "prime_recall", "stage_a_recall", "stage_b_recall", "stage_c_recall"]
    hit_keys = ["raw_total_hits", "prime_total_hits", "stage_a_total_hits", "stage_b_total_hits", "stage_c_k_used"]
    domain_stats: dict[str, dict] = {}
    for row in final_rows:
        d = row["domain"]
        domain_stats.setdefault(d, {"n": 0, **{k: 0.0 for k in keys + hit_keys},
                                     **{f"n_{k}": 0 for k in keys + hit_keys}})
        s = domain_stats[d]
        s["n"] += 1
        for k in keys + hit_keys:
            v = row.get(k)
            if v in (None, "", "None"):
                continue
            s[k] += float(v)
            s[f"n_{k}"] += 1

    overall: dict = {"n": 0, **{k: 0.0 for k in keys + hit_keys},
                     **{f"n_{k}": 0 for k in keys + hit_keys}}
    for d in domain_stats.values():
        overall["n"] += d["n"]
        for k in keys + hit_keys:
            overall[k] += d[k]
            overall[f"n_{k}"] += d[f"n_{k}"]

    def _mean(sv: dict, key: str) -> str:
        nk = f"n_{key}"
        return str(round(sv[key] / sv[nk], 4 if "recall" in key else 1)) if sv[nk] > 0 else "NA"

    summary_csv = RESULTS_DIR / f"test_prime_A_B_C_posthoc_recall_summary_{suf}.csv"
    with summary_csv.open("w", newline="", encoding="utf-8-sig") as f:
        w3 = csv.writer(f)
        w3.writerow(["domain", "n",
                     "mean_raw_recall", "mean_prime_recall", "mean_stage_a_recall",
                     "mean_stage_b_recall", "mean_stage_c_recall",
                     "mean_raw_hits", "mean_prime_hits",
                     "mean_stage_a_hits", "mean_stage_b_hits", "mean_stage_c_k"])
        for domain in sorted(domain_stats.keys()):
            s = domain_stats[domain]
            w3.writerow([domain, s["n"],
                         _mean(s, "raw_recall"), _mean(s, "prime_recall"),
                         _mean(s, "stage_a_recall"), _mean(s, "stage_b_recall"),
                         _mean(s, "stage_c_recall"),
                         _mean(s, "raw_total_hits"), _mean(s, "prime_total_hits"),
                         _mean(s, "stage_a_total_hits"), _mean(s, "stage_b_total_hits"),
                         _mean(s, "stage_c_k_used")])
        w3.writerow(["Overall", overall["n"],
                     _mean(overall, "raw_recall"), _mean(overall, "prime_recall"),
                     _mean(overall, "stage_a_recall"), _mean(overall, "stage_b_recall"),
                     _mean(overall, "stage_c_recall"),
                     _mean(overall, "raw_total_hits"), _mean(overall, "prime_total_hits"),
                     _mean(overall, "stage_a_total_hits"), _mean(overall, "stage_b_total_hits"),
                     _mean(overall, "stage_c_k_used")])
    logger.info("Saved: %s", summary_csv)


def _save_training_outputs(
    all_rows: list[dict],
    paper_status: list[dict],
    args: argparse.Namespace,
    medcpt_ranker: HybridRanker,
    qp: str,
    qc: str,
    hyde_provider: str,
    hyde_model: str,
    ts: str,
) -> None:
    per_paper_csv = RESULTS_DIR / f"training11_stagec_final_medcpt_k{args.k}_{args.provider}_{ts}.csv"
    with per_paper_csv.open("w", newline="", encoding="utf-8-sig") as f:
        fieldnames = list(all_rows[0].keys()) if all_rows else [
            "domain", "paper_id", "method", "gold_n",
            "base_hits", "base_tp", "base_recall",
            "a_prime_hits", "a_prime_tp", "a_prime_recall",
            "stage_a_hits", "stage_a_tp", "stage_a_recall",
            "stage_b_hits", "stage_b_recall", "stage_c_mode",
            "stage_c_hits", "stage_c_recall", "delta_recall_c_minus_b", "query_hash",
        ]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        if all_rows:
            w.writerows(all_rows)
    logger.info("Saved: %s", per_paper_csv)

    n = len(all_rows)
    summary: list[dict] = []
    if all_rows:
        summary.append({
            "method": "final_reference_v1",
            "n_papers": n,
            "mean_base_recall": round(sum(r["base_recall"] for r in all_rows) / n, 4),
            "mean_a_prime_recall": round(sum(r["a_prime_recall"] for r in all_rows) / n, 4),
            "mean_stage_a_recall": round(sum(r["stage_a_recall"] for r in all_rows) / n, 4),
            "mean_stage_b_recall": round(sum(r["stage_b_recall"] for r in all_rows) / n, 4),
            "mean_stage_c_recall": round(sum(r["stage_c_recall"] for r in all_rows) / n, 4),
            "mean_delta_recall": round(sum(r["delta_recall_c_minus_b"] for r in all_rows) / n, 4),
            "mean_stage_c_hits": round(sum(r["stage_c_hits"] for r in all_rows) / n, 1),
            "stagec_gate_hits": args.stagec_gate_hits,
            "stagec_floor_hits": args.stagec_floor_hits,
            "stagec_cut_percent": args.stagec_cut_percent,
            "use_fixed_k": args.use_fixed_k,
        })

    summary_csv = RESULTS_DIR / f"training11_stagec_final_medcpt_k{args.k}_{args.provider}_{ts}_summary.csv"
    with summary_csv.open("w", newline="", encoding="utf-8-sig") as f:
        fieldnames = list(summary[0].keys()) if summary else [
            "method", "n_papers",
            "mean_base_recall", "mean_a_prime_recall", "mean_stage_a_recall",
            "mean_stage_b_recall", "mean_stage_c_recall", "mean_delta_recall", "mean_stage_c_hits",
        ]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        if summary:
            w.writerows(summary)
    logger.info("Saved: %s", summary_csv)

    status_csv = RESULTS_DIR / f"training11_stagec_final_medcpt_k{args.k}_{args.provider}_{ts}_paper_status.csv"
    with status_csv.open("w", newline="", encoding="utf-8-sig") as f:
        fieldnames = list(paper_status[0].keys()) if paper_status else [
            "domain", "paper_id", "gold_n",
            "base_hits", "base_tp", "base_recall",
            "a_prime_hits", "a_prime_tp", "a_prime_recall",
            "stage_a_hits", "stage_a_tp", "stage_a_recall",
            "stage_b_hits", "stage_b_recall", "stage_c_k",
            "stagec_gate_hits", "stagec_floor_hits", "stagec_cut_percent", "use_fixed_k", "status",
        ]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        if paper_status:
            w.writerows(paper_status)
    logger.info("Saved: %s", status_csv)

    report_md = RESULTS_DIR / f"training11_stagec_final_medcpt_k{args.k}_{args.provider}_{ts}.md"
    lines = [
        f"# Training11 StageC Final (MedCPT + BM25 + Anchors), K={args.k}",
        "",
        f"- provider: `{args.provider}`",
        f"- condition: `{args.condition}`",
        f"- query_provider: `{qp}`",
        f"- query_condition: `{qc}`",
        f"- hyde_enabled: `{not args.no_hyde}`",
        f"- hyde_provider_effective: `{hyde_provider}`",
        f"- hyde_model_effective: `{hyde_model}`",
        f"- hyde_api_enabled: `{bool(args.hyde_api)}`",
        f"- device_requested: `{args.device}`",
        f"- device_effective: `{getattr(medcpt_ranker.dense, 'device', 'unknown')}`",
        f"- per-paper CSV: `{per_paper_csv.name}`",
        f"- summary CSV: `{summary_csv.name}`",
        f"- paper status CSV: `{status_csv.name}`",
        "",
        "## Formula",
        "- final = rank(s_q) + rank(s_pos_mean) - rank(s_neg_mean)",
        "- s_q = 0.5*dense + 0.5*bm25",
        f"- stagec_gate_hits: `{args.stagec_gate_hits}`",
        f"- stagec_floor_hits: `{args.stagec_floor_hits}`",
        f"- stagec_cut_percent: `{args.stagec_cut_percent}`",
        f"- stagec_min_hits: `{args.stagec_min_hits}`",
        f"- use_fixed_k: `{args.use_fixed_k}`",
        "- stage_c_mode: ranked when stage_b_hits >= stagec_min_hits AND kept_n < stage_b_hits",
    ]
    report_md.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Saved: %s", report_md)


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Unified A'->A->B->C screening pipeline.\n"
            "  --mode test     : no recall during pipeline; post-hoc recall; papers from manifest\n"
            "  --mode training : live recall at each stage; Phase5 prompt on gate failure; papers from dir scan"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--mode", required=True, choices=["test", "training"],
        help="Pipeline mode.",
    )
    parser.add_argument("--provider", default="claude", choices=["codex", "claude", "gemini"])
    parser.add_argument("--condition", default="with_laws_test_eval",
                        help="Model output condition directory name.")
    parser.add_argument("--hyde-model", default=None,
                        help="Override HyDE model (default: claude-opus-4-5 or gemini-3.0-pro).")
    parser.add_argument("--hyde-api", action="store_true", default=False,
                        help="Use provider API for HyDE generation (default: local-structured).")
    parser.add_argument("--hyde-local-structured", action="store_true", default=False,
                        help="Force local structured pseudo abstracts (same as default).")
    parser.add_argument("--k", type=int, default=500,
                        help="Legacy fixed-K (used only when --use-fixed-k is set).")
    parser.add_argument("--stagec-gate-hits", type=int, default=1000,
                        help="Gate threshold: if stage_b_hits <= gate, passthrough (keep all).")
    parser.add_argument("--stagec-floor-hits", type=int, default=1000,
                        help="Floor: minimum records kept when cut is applied.")
    parser.add_argument("--stagec-cut-percent", type=float, default=0.0,
                        help="Percent to cut above gate (0 = keep all above gate).")
    parser.add_argument("--use-fixed-k", action="store_true", default=False,
                        help="Use legacy fixed-K instead of gate/floor/cut logic.")
    parser.add_argument("--device", default="auto",
                        help="Dense model device: auto|cpu|cuda|cuda:0 ...")
    parser.add_argument("--metadata-batch-size", type=int, default=200)
    parser.add_argument("--stagec-min-hits", type=int, default=1001,
                        help="Minimum stage_b_hits to trigger Stage C ranking (default: >1000).")
    # test-mode specific
    parser.add_argument("--target", type=int, default=9999,
                        help="[test] Hit count target for Stage A' gate. Training always uses 9999.")
    parser.add_argument("--manifest", default=None,
                        help="[test] Override manifest JSON path.")
    # training-mode specific
    parser.add_argument("--query-provider", default=None,
                        help="[training] Query source provider override (default: --provider).")
    parser.add_argument("--query-condition", default=None,
                        help="[training] Query source condition override (default: --condition).")
    parser.add_argument("--no-hyde", action="store_true", default=False,
                        help="[training] Disable HyDE; use objectives+inclusion as query text.")
    parser.add_argument("--paper-id", default=None,
                        help="Run only this paper_id (e.g. 41781415_2026). Works in both modes.")
    parser.add_argument("--recall-threshold", type=float, default=0.02,
                        help="Max allowed recall drop (ΔR) for Phase 1/3 NOT-block acceptance (default: 0.02).")
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)

    use_local_hyde = args.hyde_local_structured or (not args.hyde_api)
    hyde_provider = "local" if use_local_hyde else args.provider
    if use_local_hyde:
        hyde_model = "local-structured-v1"
    elif args.hyde_model:
        hyde_model = args.hyde_model
    else:
        hyde_model = "gemini-3.0-pro" if args.provider == "gemini" else "claude-opus-4-5"

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    medcpt_ranker = HybridRanker(dense_backend="medcpt", alpha=0.5, device=args.device)

    if args.mode == "test":
        manifest_path = (
            Path(args.manifest) if args.manifest
            else TEST_DIR / "test_selection_manifest.json"
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        test_papers = manifest.get("prepared_test_papers", [])
        if args.paper_id:
            test_papers = [p for p in test_papers if p.get("paper_id") == args.paper_id or p.get("paper_folder") == args.paper_id]
            if not test_papers:
                logger.error("No test paper found with paper_id=%s", args.paper_id)
                sys.exit(1)
            logger.info("Filtered to paper_id=%s (%d papers)", args.paper_id, len(test_papers))

        stage_rows, pmids_b_store, pmids_c_store = _run_pipeline_test(
            test_papers=test_papers,
            provider=args.provider,
            condition=args.condition,
            query_condition=args.query_condition,
            hyde_provider=hyde_provider,
            hyde_model=hyde_model,
            medcpt_ranker=medcpt_ranker,
            target=args.target,
            stagec_min_hits=args.stagec_min_hits,
            stagec_gate_hits=args.stagec_gate_hits,
            stagec_floor_hits=args.stagec_floor_hits,
            stagec_cut_percent=args.stagec_cut_percent,
            use_fixed_k=args.use_fixed_k,
            k=args.k,
            metadata_batch_size=args.metadata_batch_size,
            ts=ts,
        )
        final_rows = _compute_posthoc_recall(stage_rows, pmids_b_store, pmids_c_store)
        _save_test_outputs(final_rows, args, ts)

    else:  # training
        qp = args.query_provider or args.provider
        qc = args.query_condition or args.condition
        papers = _load_papers_training(
            provider=args.provider,
            condition=args.condition,
            query_provider=qp,
            query_condition=qc,
        )
        logger.info(
            "Loaded %d papers (provider=%s condition=%s query_provider=%s query_condition=%s)",
            len(papers), args.provider, args.condition, qp, qc,
        )

        if args.paper_id:
            papers = [p for p in papers if p["paper_id"] == args.paper_id]
            if not papers:
                logger.error("No paper found with paper_id=%s", args.paper_id)
                sys.exit(1)
            logger.info("Filtered to paper_id=%s (%d papers)", args.paper_id, len(papers))

        all_rows: list[dict] = []
        paper_status: list[dict] = []
        for p in papers:
            logger.info("Processing %s/%s", p["domain"], p["paper_id"])
            rows, st = _run_one_paper_training(
                paper=p,
                provider=args.provider,
                condition=qc,
                hyde_provider=hyde_provider,
                medcpt_ranker=medcpt_ranker,
                k_fixed=args.k,
                stagec_gate_hits=args.stagec_gate_hits,
                stagec_floor_hits=args.stagec_floor_hits,
                stagec_cut_percent=args.stagec_cut_percent,
                use_fixed_k=args.use_fixed_k,
                hyde_model=hyde_model,
                use_hyde=(not args.no_hyde),
                stagec_min_hits=args.stagec_min_hits,
                ts=ts,
                recall_threshold=args.recall_threshold,
            )
            all_rows.extend(rows)
            paper_status.append(st)

        _save_training_outputs(
            all_rows, paper_status, args, medcpt_ranker, qp, qc, hyde_provider, hyde_model, ts
        )


if __name__ == "__main__":
    main()
