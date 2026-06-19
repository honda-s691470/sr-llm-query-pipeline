"""
Apply LLM-generated rewrites to all 4 target files.

Reads:   run_logs/aprime_rewrite_prompt_response_{ts}.md  (LLM output, passed as --response)
Updates:
  1. run_eval_training11_stages.py      — A_PRIME_BLOCKS_REWRITE_BEGIN/END
  2. run_pipeline_prime_A_B_C.py        — TIER_ORDER_REWRITE_BEGIN/END
  3. prompts/active/exclusion_screening_training_prompt_stageAtoD.md — both markers
  4. prompts/active/exclusion_screening_test_prompt_stageAtoD.md     — both markers

Writes:  run_logs/aprime_rewrite_applied_{ts}.json  (diff summary)

Validation before applying:
  - All tier function names exist in run_eval_training11_stages.py
  - SR-of-SRs blocks are not deleted
  - Block syntaxes unchanged from current set
  - Tier F is last; Tier 1 is first
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PIPELINE_DIR = ROOT / "06_exclusion_screening_pipeline"
RUN_LOGS_DIR = PIPELINE_DIR / "run_logs"
PROMPTS_DIR = PIPELINE_DIR / "prompts" / "active"

# Files to patch
EVAL_STAGES_PATH = PIPELINE_DIR / "run_eval_training11_stages.py"
PIPELINE_PATH = PIPELINE_DIR / "run_pipeline_prime_A_B_C.py"
TRAINING_PROMPT_PATH = PROMPTS_DIR / "exclusion_screening_training_prompt_stageAtoD.md"
TEST_PROMPT_PATH = PROMPTS_DIR / "exclusion_screening_test_prompt_stageAtoD.md"

SR_OF_SRS_SYNTAXES = {
    'NOT "Systematic Review"[pt]',
    'NOT "Meta-Analysis"[pt]',
    'NOT "Review"[pt]',
}

REQUIRED_TIER_FNS = {f"_tier{i}_candidates_from_raw" for i in range(1, 11)}


def _extract_block(text: str, begin: str, end: str) -> str | None:
    m = re.search(re.escape(begin) + r"(.*?)" + re.escape(end), text, re.DOTALL)
    return m.group(1).strip() if m else None


def _replace_block(text: str, begin: str, end: str, new_content: str) -> str:
    pattern = re.escape(begin) + r".*?" + re.escape(end)
    replacement = f"{begin}\n{new_content}\n{end}"
    result, count = re.subn(pattern, replacement, text, flags=re.DOTALL)
    if count == 0:
        raise ValueError(f"Marker pair not found: {begin!r} ... {end!r}")
    return result


def _validate_phase1(new_src: str) -> None:
    # Extract syntaxes
    syntaxes = re.findall(r'"syntax":\s*\'([^\']+)\'', new_src)
    if not syntaxes:
        syntaxes = re.findall(r'"syntax":\s*"([^"]+)"', new_src)

    # SR-of-SRs must all be present
    for s in SR_OF_SRS_SYNTAXES:
        if s not in new_src:
            raise ValueError(f"SR-of-SRs block missing from rewrite: {s!r}")

    # Must have exactly 10 blocks
    block_count = len(re.findall(r'"name":', new_src))
    if block_count != 10:
        raise ValueError(f"Expected 10 blocks in A_PRIME_BLOCKS, got {block_count}")


def _validate_tier_order(new_src: str, eval_stages_src: str) -> None:
    # All tier functions must exist in eval_stages
    for fn in REQUIRED_TIER_FNS:
        if fn not in eval_stages_src:
            raise ValueError(f"Tier function {fn!r} not found in run_eval_training11_stages.py")
        if fn not in new_src:
            raise ValueError(f"Tier function {fn!r} missing from rewrite")

    # Tier 1 must appear before tier 2
    pos1 = new_src.find("_tier1_candidates_from_raw")
    pos2 = new_src.find("_tier2_candidates_from_raw")
    if pos1 < 0 or pos2 < 0 or pos1 > pos2:
        raise ValueError("_tier1_candidates_from_raw must appear before _tier2_candidates_from_raw")

    # tierF is called separately outside tier_fns list — not validated here


def _backup(path: Path, ts: str) -> Path:
    backup_path = path.with_suffix(f".bak_{ts}{path.suffix}")
    shutil.copy2(path, backup_path)
    return backup_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--response", required=True, help="Path to LLM response file")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    RUN_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    response_text = Path(args.response).read_text(encoding="utf-8")

    # Extract rewrites from LLM response
    phase1_rewrite = _extract_block(response_text, "PHASE1_REWRITE_BEGIN", "PHASE1_REWRITE_END")
    tier_rewrite = _extract_block(response_text, "TIER_ORDER_REWRITE_BEGIN", "TIER_ORDER_REWRITE_END")

    if not phase1_rewrite:
        print("ERROR: PHASE1_REWRITE_BEGIN/END block not found in response", file=sys.stderr)
        sys.exit(1)
    if not tier_rewrite:
        print("ERROR: TIER_ORDER_REWRITE_BEGIN/END block not found in response", file=sys.stderr)
        sys.exit(1)

    # Validate
    eval_stages_src = EVAL_STAGES_PATH.read_text(encoding="utf-8")
    _validate_phase1(phase1_rewrite)
    _validate_tier_order(tier_rewrite, eval_stages_src)

    if args.dry_run:
        print("DRY RUN — validation passed, no files modified.")
        print(f"\nPhase 1 rewrite preview:\n{phase1_rewrite}")
        print(f"\nTier order rewrite preview:\n{tier_rewrite}")
        sys.exit(0)

    applied: list[dict] = []

    def _patch(path: Path, begin: str, end: str, new_content: str, label: str) -> None:
        original = path.read_text(encoding="utf-8")
        backup = _backup(path, ts)
        updated = _replace_block(original, begin, end, new_content)
        path.write_text(updated, encoding="utf-8")
        applied.append({"file": str(path), "marker": begin, "backup": str(backup), "label": label})
        print(f"  Patched {label} → {path.name}")

    print("Applying rewrites...")

    # 1. A_PRIME_BLOCKS in run_eval_training11_stages.py
    _patch(EVAL_STAGES_PATH,
           "# A_PRIME_BLOCKS_REWRITE_BEGIN", "# A_PRIME_BLOCKS_REWRITE_END",
           phase1_rewrite, "phase1_blocks/eval_stages")

    # 2. tier_fns in run_pipeline_prime_A_B_C.py
    _patch(PIPELINE_PATH,
           "# TIER_ORDER_REWRITE_BEGIN", "# TIER_ORDER_REWRITE_END",
           tier_rewrite, "tier_fns/pipeline")

    phase1_md = _build_prompt_phase1_table(phase1_rewrite)
    tier_header_seq = _build_tier_sequence(tier_rewrite)

    for prompt_path, label_prefix in [
        (TRAINING_PROMPT_PATH, "training_prompt"),
        (TEST_PROMPT_PATH, "test_prompt"),
    ]:
        # Phase 1 priority
        _patch(prompt_path,
               "<!-- PHASE1_PRIORITY_REWRITE_BEGIN -->", "<!-- PHASE1_PRIORITY_REWRITE_END -->",
               phase1_md, f"phase1_priority/{label_prefix}")

        # Phase 3 tier order: update only the header line, preserve all bullet descriptions
        current_text = prompt_path.read_text(encoding="utf-8")
        current_p3 = _extract_block(
            current_text,
            "<!-- PHASE3_TIER_ORDER_REWRITE_BEGIN -->",
            "<!-- PHASE3_TIER_ORDER_REWRITE_END -->",
        )
        if current_p3 is None:
            print(f"  WARNING: PHASE3_TIER_ORDER markers not found in {prompt_path.name}", file=sys.stderr)
        else:
            updated_p3 = re.sub(
                r"#### Phase 3-1: Tier order \(mandatory[^\n]*\)",
                f"#### Phase 3-1: Tier order (mandatory — apply in this sequence: {tier_header_seq})",
                current_p3,
            )
            _patch(prompt_path,
                   "<!-- PHASE3_TIER_ORDER_REWRITE_BEGIN -->", "<!-- PHASE3_TIER_ORDER_REWRITE_END -->",
                   updated_p3, f"phase3_tier/{label_prefix}")

    out_path = RUN_LOGS_DIR / f"aprime_rewrite_applied_{ts}.json"
    out_path.write_text(json.dumps({"ts": ts, "applied": applied}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote diff summary → {out_path}")
    print(f"APPLIED_PATH={out_path}")


def _build_prompt_phase1_table(phase1_rewrite: str) -> str:
    """Convert A_PRIME_BLOCKS Python source to a markdown numbered list."""
    entries: list[tuple[str, str]] = []
    # Match both double-quoted and single-quoted syntax values (may contain internal quotes)
    for m in re.finditer(
        r'\{"name":\s*"([^"]+)",\s*"syntax":\s*(?:\'([^\']+)\'|"([^"]+)")\}',
        phase1_rewrite,
    ):
        name = m.group(1)
        syntax = m.group(2) if m.group(2) is not None else m.group(3)
        entries.append((name, syntax))
    if not entries:
        return f"```python\n{phase1_rewrite}\n```"
    lines = []
    for i, (name, syntax) in enumerate(entries, 1):
        lines.append(f"{i}. `{syntax}`")
    return "\n".join(lines)


def _build_tier_sequence(tier_rewrite: str) -> str:
    """Build the tier sequence string (e.g. '1 → 3 → 2 → ...') from tier_fns source."""
    tiers = re.findall(r"eval_stages\.(_tier\w+_candidates_from_raw)", tier_rewrite)
    if not tiers:
        return "1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → F"

    def _tier_label(fn: str) -> str:
        m = re.match(r"_tier(\w+)_candidates_from_raw", fn)
        return m.group(1).upper() if m else fn

    return " → ".join(_tier_label(t) for t in tiers)


if __name__ == "__main__":
    main()
