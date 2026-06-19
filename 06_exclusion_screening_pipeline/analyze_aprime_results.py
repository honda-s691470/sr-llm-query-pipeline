"""
Analyze Stage A' self-refinement loop state and determine whether to continue or stop.

Stop conditions (based on aprime_laws_verN.json ranking convergence):
  1. no_aprime_activity  — latest laws file has n_records == 0
                           (A' was never triggered; all papers already < 9999 hits)
  2. converged           — top-5 Phase 1 block names AND top-5 Phase 3 tier names
                           are identical between the two most recent laws files
  3. max_iterations_reached — iteration_number >= max_iterations

NOTE: phase5_pending is recorded for reference only and is NOT a stop criterion.
Phase 5 is a manual fallback that must be handled separately after the loop.

Stdout (machine-readable, PS1-compatible):
  STOP=true|false STOP_REASON=<reason> DIAGNOSTICS_PATH=<abs_path>

Writes:
  run_logs/aprime_diagnostics_{ts}.json
  run_logs/aprime_review_queue_{ts}.md
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PIPELINE_DIR = ROOT / "06_exclusion_screening_pipeline"
RESULTS_DIR = PIPELINE_DIR / "results"
RUN_LOGS_DIR = PIPELINE_DIR / "run_logs"


# ── A' laws file helpers ──────────────────────────────────────────────────────

def _latest_laws_files(run_logs_dir: Path) -> list[Path]:
    """Return all aprime_laws_verN.json files sorted ascending by version number."""
    files = []
    for p in run_logs_dir.glob("aprime_laws_ver*.json"):
        m = re.search(r"ver(\d+)", p.stem)
        if m:
            files.append((int(m.group(1)), p))
    return [p for _, p in sorted(files)]


def _has_aprime_activity(laws_path: Path) -> bool:
    """Return True if the laws file has any records (A' was triggered this run)."""
    try:
        data = json.loads(laws_path.read_text(encoding="utf-8"))
        return data.get("stats", {}).get("n_records", 0) > 0
    except Exception:
        return False


def _rankings_converged(prev_path: Path, curr_path: Path, top_n: int = 5) -> bool:
    """Return True if top-N Phase 1 blocks and Phase 3 tiers are in the same order."""
    try:
        prev = json.loads(prev_path.read_text(encoding="utf-8"))
        curr = json.loads(curr_path.read_text(encoding="utf-8"))
    except Exception:
        return False

    prev_p1 = [b["name"] for b in prev.get("phase1_blocks", [])[:top_n]]
    curr_p1 = [b["name"] for b in curr.get("phase1_blocks", [])[:top_n]]
    prev_p3 = prev.get("phase3_tier_order", [])[:top_n]
    curr_p3 = curr.get("phase3_tier_order", [])[:top_n]

    return prev_p1 == curr_p1 and prev_p3 == curr_p3


# ── Phase 5 reference (informational only, not used for stop logic) ───────────

def _read_phase5_reference(results_dir: Path) -> list[dict]:
    """Read the latest paper_status CSV and return phase5-pending papers for reference."""
    candidates = sorted(results_dir.glob("*paper_status*.csv"))
    if not candidates:
        return []
    csv_path = candidates[-1]
    try:
        rows: list[dict] = []
        with csv_path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
    except Exception:
        return []

    # Detect phase5 column
    phase5_col = None
    for candidate in ("phase5_pending", "phase5_required", "phase5"):
        if rows and any(candidate in row for row in rows):
            phase5_col = candidate
            break
    if phase5_col is None and rows:
        for col in rows[0].keys():
            if "phase5" in col.lower():
                phase5_col = col
                break

    pending = []
    if phase5_col:
        for row in rows:
            val = str(row.get(phase5_col, "")).strip().lower()
            if val in ("true", "1", "yes"):
                pending.append({
                    "paper_id": row.get("paper_id", ""),
                    "domain": row.get("domain", ""),
                    "a_prime_hits": row.get("a_prime_hits", ""),
                    "status": row.get("status", ""),
                })
    return pending


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iteration", type=int, default=1)
    parser.add_argument("--max-iterations", type=int, default=5)
    args = parser.parse_args()

    RUN_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    all_laws = _latest_laws_files(RUN_LOGS_DIR)
    curr_laws_path: Path | None = all_laws[-1] if all_laws else None
    prev_laws_path: Path | None = all_laws[-2] if len(all_laws) >= 2 else None

    stop_reason = ""
    should_stop = False

    if not all_laws or curr_laws_path is None:
        stop_reason = "no_aprime_activity"
        should_stop = True
    elif not _has_aprime_activity(curr_laws_path):
        stop_reason = "no_aprime_activity"
        should_stop = True
    elif args.iteration >= args.max_iterations:
        stop_reason = f"max_iterations_reached_{args.max_iterations}"
        should_stop = True
    elif prev_laws_path is not None and _rankings_converged(prev_laws_path, curr_laws_path):
        stop_reason = "converged"
        should_stop = True

    # Phase 5 reference — recorded for diagnostics, not used for stop logic
    phase5_ref = _read_phase5_reference(RESULTS_DIR)

    diagnostics = {
        "iteration": args.iteration,
        "max_iterations": args.max_iterations,
        "stop": should_stop,
        "stop_reason": stop_reason or "continue",
        "curr_laws": str(curr_laws_path) if curr_laws_path else None,
        "prev_laws": str(prev_laws_path) if prev_laws_path else None,
        "phase5_reference": phase5_ref,
    }

    diag_path = RUN_LOGS_DIR / f"aprime_diagnostics_{ts}.json"
    diag_path.write_text(json.dumps(diagnostics, indent=2, ensure_ascii=False), encoding="utf-8")

    # Human-readable review queue
    queue_path = RUN_LOGS_DIR / f"aprime_review_queue_{ts}.md"
    lines = [
        f"# Stage A' Refinement Loop — iteration {args.iteration}",
        "",
        f"stop: **{should_stop}**  |  reason: **{stop_reason or 'continue'}**",
        "",
    ]
    if curr_laws_path:
        try:
            curr = json.loads(curr_laws_path.read_text(encoding="utf-8"))
            lines += [
                "## Phase 1 block ranking (current)",
                "| rank | name | score |",
                "|---|---|---|",
            ]
            for b in curr.get("phase1_blocks", []):
                lines.append(f"| {b.get('rank','')} | {b.get('name','')} | {b.get('score','')} |")
            lines += [
                "",
                "## Phase 3 tier ranking (current)",
                " → ".join(curr.get("phase3_tier_order", [])),
                "",
            ]
        except Exception:
            pass
    if phase5_ref:
        lines += [
            "## Phase 5 reference (informational — not a stop criterion)",
            "| paper_id | domain | a_prime_hits | status |",
            "|---|---|---|---|",
        ]
        for p in phase5_ref:
            lines.append(f"| {p['paper_id']} | {p['domain']} | {p['a_prime_hits']} | {p['status']} |")
    queue_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Machine-readable stdout (PS1 parses STOP= token)
    print(f"STOP={'true' if should_stop else 'false'} STOP_REASON={stop_reason or 'continue'} DIAGNOSTICS_PATH={diag_path}")

    # Human-readable stderr
    print(f"iteration={args.iteration}  stop={should_stop}  reason={stop_reason or 'continue'}", file=sys.stderr)
    if curr_laws_path:
        print(f"  curr_laws: {curr_laws_path.name}", file=sys.stderr)
    if prev_laws_path:
        print(f"  prev_laws: {prev_laws_path.name}", file=sys.stderr)
    for p in phase5_ref:
        print(f"  phase5_ref: {p['paper_id']} ({p['domain']})  hits={p['a_prime_hits']}", file=sys.stderr)


if __name__ == "__main__":
    main()
