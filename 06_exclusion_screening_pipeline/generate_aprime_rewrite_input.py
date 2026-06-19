"""
Generate a rewrite prompt for the LLM to improve Stage A' block/tier ordering.

Reads:
  - run_logs/aprime_diagnostics_{ts}.json   (latest)
  - aprime_laws_verN.json                   (latest)
  - run_eval_training11_stages.py           (to extract current A_PRIME_BLOCKS verbatim)
  - run_pipeline_prime_A_B_C.py             (to extract current tier_fns list verbatim)

Writes:
  - run_logs/aprime_rewrite_prompt_{ts}.md  (LLM input)

The prompt asks the LLM to output two rewrite blocks delimited by:
  PHASE1_REWRITE_BEGIN / PHASE1_REWRITE_END
  TIER_ORDER_REWRITE_BEGIN / TIER_ORDER_REWRITE_END
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PIPELINE_DIR = ROOT / "06_exclusion_screening_pipeline"
RUN_LOGS_DIR = PIPELINE_DIR / "run_logs"


def _latest_json(pattern: str, directory: Path) -> Path | None:
    files = sorted(directory.glob(pattern))
    return files[-1] if files else None


def _extract_block(text: str, begin_marker: str, end_marker: str) -> str:
    m = re.search(
        re.escape(begin_marker) + r"(.*?)" + re.escape(end_marker),
        text,
        re.DOTALL,
    )
    return m.group(1).strip() if m else ""


def _load_current_a_prime_blocks(py_path: Path) -> str:
    src = py_path.read_text(encoding="utf-8")
    return _extract_block(src, "# A_PRIME_BLOCKS_REWRITE_BEGIN", "# A_PRIME_BLOCKS_REWRITE_END")


def _load_current_tier_fns(py_path: Path) -> str:
    src = py_path.read_text(encoding="utf-8")
    return _extract_block(src, "# TIER_ORDER_REWRITE_BEGIN", "# TIER_ORDER_REWRITE_END")


def main() -> None:
    RUN_LOGS_DIR.mkdir(parents=True, exist_ok=True)

    diag_path = _latest_json("aprime_diagnostics_*.json", RUN_LOGS_DIR)
    if diag_path is None:
        print("ERROR: no aprime_diagnostics_*.json found", file=sys.stderr)
        sys.exit(1)

    laws_path = _latest_json("aprime_laws_ver*.json", RUN_LOGS_DIR)
    if laws_path is None:
        print("ERROR: no aprime_laws_ver*.json found", file=sys.stderr)
        sys.exit(1)

    diag = json.loads(diag_path.read_text(encoding="utf-8"))
    laws = json.loads(laws_path.read_text(encoding="utf-8"))

    eval_stages_path = PIPELINE_DIR / "run_eval_training11_stages.py"
    pipeline_path = PIPELINE_DIR / "run_pipeline_prime_A_B_C.py"

    current_blocks_src = _load_current_a_prime_blocks(eval_stages_path)
    current_tier_src = _load_current_tier_fns(pipeline_path)

    # --- Build Phase 1 stats table ---
    p1_rows = ["| rank | name | syntax | score | HRR | SR | C | RP | n_attempts |",
               "|---|---|---|---|---|---|---|---|---|"]
    for blk in laws.get("phase1_blocks", []):
        p1_rows.append(
            f"| {blk['rank']} | {blk['name']} | `{blk['syntax']}` | {blk['score']} "
            f"| {blk['hrr']} | {blk['sr']} | {blk['c']} | {blk['rp']} | {blk['n_attempts']} |"
        )
    p1_table = "\n".join(p1_rows)

    # --- Build Phase 3 tier stats table ---
    p3_rows = ["| rank | tier | tier_score | avg_HRR | SR | recall_safety_rate | n_total | n_accepted |",
               "|---|---|---|---|---|---|---|---|"]
    for t in laws.get("phase3_tier_scores", []):
        p3_rows.append(
            f"| {t['rank']} | {t['tier']} | {t['tier_score']} "
            f"| {t['avg_hrr']} | {t['sr']} | {t['recall_safety_rate']} "
            f"| {t['n_total']} | {t['n_accepted']} |"
        )
    p3_table = "\n".join(p3_rows)

    # --- Phase5 pending papers ---
    pending = diag.get("phase5_papers", [])
    if pending:
        pending_lines = ["| paper_id | domain | prime_hits | prime_note |", "|---|---|---|---|"]
        for p in pending:
            pending_lines.append(f"| {p['paper_id']} | {p['domain']} | {p['prime_hits']} | {p['prime_note']} |")
        pending_section = "\n".join(pending_lines)
    else:
        pending_section = "(none — all papers are below 9999 hits)"

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    prompt = f"""# Stage A' Self-Refinement Rewrite Request — iteration {diag['iteration']}

## Task

Reorder the Stage A' Phase 1 exclusion blocks and Phase 3 tier functions to improve
hit reduction efficiency on the 11 training papers. Output **exactly two rewrite blocks**
in the format specified at the end of this prompt.

---

## Constraints (DO NOT violate)

1. **Block syntax is immutable.** Never change the `syntax` value of any block.
2. **Block set is immutable.** All 10 existing blocks must remain — no additions or deletions.
3. **SR-of-SRs blocks** (`NOT "Systematic Review"[pt]`, `NOT "Meta-Analysis"[pt]`, `NOT "Review"[pt]`)
   must remain together and adjacent in the list (they are skipped as a group at runtime).
4. **Tier 2 is permanently forbidden** from being moved before Tier 1. Tier 1 (ARC_LAW_A) must
   remain at rank 1 — it is the safest and most universally applicable operation.
5. **Tier F** must always remain last (after Tier 10) — it appends NOT filters and must run after
   all raw_query modifications.
6. **No tier may be removed.** All tiers (1–10 and F) must appear in the output.

---

## Phase 1 block performance (computed from latest training run)

{p1_table}

Score formula: `Score = 10 × HRR × SR × C − 0.8 × RP`
- HRR = mean hit reduction ratio (delta_hits / hits_before) over accepted attempts
- SR = fraction of papers where block reduced hits
- C = fraction of domains (CV/PSY/Infect) with positive mean hit reduction
- RP = recall penalty rate (fraction with delta_recall > 0.02)

---

## Phase 3 tier performance (computed from latest training run)

{p3_table}

Score formula: `Tier_Score = Avg_HRR × SR × Recall_Safety_Rate`
- Avg_HRR = mean HRR over accepted modifications
- SR = fraction accepted
- Recall_Safety_Rate = fraction not rejected (includes NO_REDUCTION as safe)

---

## Papers still above 9999 hits after Stage A' (phase5_pending)

{pending_section}

---

## Current A_PRIME_BLOCKS (verbatim from run_eval_training11_stages.py)

```python
{current_blocks_src}
```

## Current tier_fns (verbatim from run_pipeline_prime_A_B_C.py)

```python
{current_tier_src}
```

---

## Output format

Emit exactly the following two delimited blocks and nothing else outside them.

### Block 1: Phase 1 reorder

```
PHASE1_REWRITE_BEGIN
A_PRIME_BLOCKS = [
    {{"name": "...", "syntax": "..."}},
    ...
]
PHASE1_REWRITE_END
```

### Block 2: Tier order reorder

```
TIER_ORDER_REWRITE_BEGIN
tier_fns = [
    eval_stages._tier1_candidates_from_raw,
    ...
    eval_stages._tier10_candidates_from_raw,
]
TIER_ORDER_REWRITE_END
```

Reasoning: before the blocks, include a brief (3–5 sentence) explanation of why you chose
this ordering based on the statistics above.
"""

    out_path = RUN_LOGS_DIR / f"aprime_rewrite_prompt_{ts}.md"
    out_path.write_text(prompt, encoding="utf-8")
    print(f"PROMPT_PATH={out_path}")
    print(f"Wrote rewrite prompt → {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
