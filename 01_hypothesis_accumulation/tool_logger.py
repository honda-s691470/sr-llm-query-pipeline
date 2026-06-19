# tool_logger.py
"""
Append-only logger (JSONL) with automatic labeling.

- Reads last_metrics.json produced by tool_evaluator.py
- Appends a record to search_history.jsonl
- Computes delta_recall / delta_hits vs previous record
- Automatically assigns result_label (no human label input)

Usage:
  python tool_logger.py \
    --phase "Blind" \
    --primary "(...)" \
    --filter "(...)" \
    --action_type "Broaden_Primary" \
    --concept_category "DEPRESSION_ANXIETY" \
    --rationale "..."

Optional:
  --action_payload '{"added":["..."],"removed":[],"changed":"..."}'
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


LOG_FILE = "search_history.jsonl"
METRICS_FILE = "last_metrics.json"


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_runtime_path(filename: str) -> Path:
    cwd_path = Path.cwd() / filename
    if cwd_path.exists():
        return cwd_path
    return Path(__file__).resolve().parent / filename


def _read_last_record(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    # Read last non-empty line
    with path.open("r", encoding="utf-8") as f:
        last = None
        for line in f:
            line = line.strip()
            if line:
                last = line
        if not last:
            return None
        try:
            return json.loads(last)
        except Exception:
            return None


def _eps_equal(a: float, b: float, eps: float = 1e-12) -> bool:
    return abs(a - b) <= eps


def determine_label(curr_recall: float, curr_hits: int, prev_recall: float, prev_hits: int) -> str:
    """
    Mechanical labeling for training-ready logs.
    """
    delta_recall = curr_recall - prev_recall
    delta_hits = curr_hits - prev_hits

    # Regression: any recall drop
    if delta_recall < -1e-12:
        return "Regression"

    # Explosion: hits >= 2x with no meaningful recall gain
    if prev_hits > 0 and curr_hits >= int(prev_hits * 2.0) and delta_recall <= 1e-12:
        return "Explosion"

    # Positive outcomes
    if delta_recall > 1e-12:
        return "Positive_Recall_Improvement"
    if _eps_equal(delta_recall, 0.0) and delta_hits < 0:
        return "Positive_Hits_Reduction"

    # Neutral
    if _eps_equal(delta_recall, 0.0) and delta_hits == 0:
        return "Neutral"

    # If hits increased but recall didn't drop, still not good
    return "Negative"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", required=True, help="Blind | Peeking | Pruning")
    ap.add_argument("--primary", required=True, help="PRIMARY_CONCEPT string")
    ap.add_argument("--filter", required=True, help="STUDY_FILTER string")
    ap.add_argument("--action_type", required=True)
    ap.add_argument("--concept_category", default="NONE")
    ap.add_argument("--rationale", default="")
    ap.add_argument("--action_payload", default="", help="Optional JSON describing the single atomic change.")
    args = ap.parse_args()

    log_path = Path.cwd() / LOG_FILE
    metrics_path = _resolve_runtime_path(METRICS_FILE)

    try:
        metrics = _read_json(metrics_path)
        curr_recall = float(metrics.get("recall", 0.0))
        curr_hits = int(metrics.get("total_hits", 0))

        last = _read_last_record(log_path)
        prev_recall = float(last["recall"]) if last else 0.0
        prev_hits = int(last["total_hits"]) if last else 0
        iteration = int(last["iteration"]) + 1 if last else 1

        result_label = determine_label(curr_recall, curr_hits, prev_recall, prev_hits)

        # Parse action_payload if provided
        action_payload_obj: Any = None
        if args.action_payload:
            try:
                action_payload_obj = json.loads(args.action_payload)
            except Exception:
                # Keep raw string if invalid JSON, but do not crash
                action_payload_obj = {"raw": args.action_payload}

        record: Dict[str, Any] = {
            "iteration": iteration,
            "timestamp": datetime.now().isoformat(),
            "phase": args.phase,
            "query_parts": {
                "primary": args.primary,
                "filter": args.filter,
            },
            "full_query": metrics.get("query", ""),
            "action_type": args.action_type,
            "concept_category": args.concept_category,
            "rationale": args.rationale,
            "action_payload": action_payload_obj,
            "recall": curr_recall,
            "total_hits": curr_hits,
            "delta_recall": curr_recall - prev_recall,
            "delta_hits": curr_hits - prev_hits,
            "result_label": result_label,
            "evaluator_mode": metrics.get("mode", "unknown"),
        }

        # Append JSONL
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        print(f"Logged Iteration {iteration}: {result_label} (recall={curr_recall:.4f}, hits={curr_hits})")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
