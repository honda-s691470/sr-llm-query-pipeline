from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple

from fetch_pubmed_metadata import fetch_metadata


SECTION_00_BEGIN = "# SECTION_00_REWRITE_BEGIN"
SECTION_00_END = "# SECTION_00_REWRITE_END"
BLOCK_PATTERN = re.compile(
    r'SECTION_00_EDITABLE_BLOCK\s*=\s*r"""(?P<body>.*?)"""',
    re.DOTALL,
)

# Additional editable blocks (imperative / example)
IMPERATIVE_BLOCKS = [
    {
        "variable": "TIAB_IMPERATIVE_CONDITIONAL_ADD_EDITABLE",
        "begin": "# TIAB_IMPL_COND_ADD_BEGIN",
        "end": "# TIAB_IMPL_COND_ADD_END",
        "label": "TIAB_IMPERATIVE_CONDITIONAL_ADD block",
        "description": (
            "Controls the [ONE-SHOT-GUIDANCE: ADD_TIAB] text in the CONDITIONAL branch of "
            "tiab_imperative(). Affects Imperative_EN for LAW_016 and similar TIAB-ADD laws. "
            "Use {target_block} as a Python format placeholder where the block name ('PRIMARY' etc.) should appear."
        ),
    },
    {
        "variable": "ONE_SHOT_IMPERATIVE_PRIMARY_EDITABLE",
        "begin": "# ONE_SHOT_PRIMARY_BEGIN",
        "end": "# ONE_SHOT_PRIMARY_END",
        "label": "ONE_SHOT_IMPERATIVE_PRIMARY block",
        "description": (
            "Controls the advice portion of the [ONE-SHOT-GUIDANCE] text for PRIMARY-block "
            "RESTRICT/REMOVE operations in one_shot_imperative(). The generic opening "
            "'[ONE-SHOT-GUIDANCE] {meta_action} on {target_block}/{target_slot} shows mixed effects...' "
            "is prepended automatically — do NOT repeat it here."
        ),
    },
    {
        "variable": "PLACEHOLDER_INITIAL_PRIMARY_EDITABLE",
        "begin": "# PLACEHOLDER_INIT_BEGIN",
        "end": "# PLACEHOLDER_INIT_END",
        "label": "PLACEHOLDER_INITIAL_PRIMARY block",
        "description": (
            "Controls the Example_Placeholder for INITIAL_PRIMARY (LAW_001) in "
            "placeholder_example_for(). Use generic placeholders like CONDITION_X, "
            "INTERVENTION_Z, TERM_A — never paper-specific names."
        ),
    },
]


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def extract_section(prompt_text: str, heading: str) -> str:
    marker = f"## {heading}"
    start = prompt_text.find(marker)
    if start == -1:
        raise ValueError(f"Heading not found in RUN_WORKFLOW_PROMPT.md: {heading}")
    next_heading = prompt_text.find("\n## ", start + len(marker))
    if next_heading == -1:
        next_heading = len(prompt_text)
    return prompt_text[start:next_heading].strip()


def extract_editable_block(source_text: str, variable_name: str, begin_marker: str, end_marker: str) -> str:
    """Extract the content between begin/end markers from a named r-string variable."""
    pattern = re.compile(
        rf'{re.escape(variable_name)}\s*=\s*r"""(?P<body>.*?)"""',
        re.DOTALL,
    )
    match = pattern.search(source_text)
    if not match:
        raise ValueError(f"{variable_name} was not found in analyze_logs_ver2.py")
    block = match.group("body").strip()
    start = block.find(begin_marker)
    end = block.find(end_marker)
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"Markers not found inside {variable_name}")
    end += len(end_marker)
    return block[start:end].strip()


def extract_section00_block(source_text: str) -> str:
    return extract_editable_block(source_text, "SECTION_00_EDITABLE_BLOCK", SECTION_00_BEGIN, SECTION_00_END)


def select_low_performing_cases(
    diagnostics: List[Dict],
    low_recall_threshold: float,
    delta_threshold: float,
) -> List[Dict]:
    low_recall_cases = []
    delta_drop_cases = []

    for row in diagnostics:
        recall = float(row.get("recall", 0.0))
        delta = row.get("delta_recall_vs_previous")
        delta_value = float(delta) if delta is not None else None

        if recall < low_recall_threshold:
            row_copy = dict(row)
            row_copy["rewrite_priority_reason"] = "low_recall"
            low_recall_cases.append(row_copy)
            continue

        if delta_value is not None and delta_value <= -delta_threshold:
            row_copy = dict(row)
            row_copy["rewrite_priority_reason"] = "delta_recall_drop"
            delta_drop_cases.append(row_copy)

    low_recall_cases.sort(key=lambda row: (float(row.get("recall", 0.0)), float(row.get("delta_recall_vs_previous") or 0.0)))
    delta_drop_cases.sort(key=lambda row: float(row.get("delta_recall_vs_previous") or 0.0))

    selected = low_recall_cases[:2]
    if len(selected) < 2:
        needed = 2 - len(selected)
        selected.extend(delta_drop_cases[:needed])

    return selected


def build_case_bundle(bundle_root: Path, case: Dict) -> Tuple[Dict, List[Dict]]:
    sr_rel = case["sr_path"].replace("/", "\\")
    sr_dir = bundle_root / Path(sr_rel)
    input_config = read_json(sr_dir / "input_config.json")
    missed_pmids = case.get("missed_pmids", [])
    metadata = fetch_metadata([str(p) for p in missed_pmids]) if missed_pmids else []
    return {
        "sr_path": case["sr_path"],
        "target_name": input_config.get("target_name", ""),
        "objectives": input_config.get("objectives", ""),
        "inclusion_criteria": input_config.get("inclusion_criteria", ""),
        "recall": case.get("recall"),
        "previous_recall": case.get("previous_recall"),
        "delta_recall_vs_previous": case.get("delta_recall_vs_previous"),
        "rewrite_priority_reason": case.get("rewrite_priority_reason", ""),
        "total_hits": case.get("total_hits"),
        "query": case.get("query", ""),
        "missed_pmids": missed_pmids,
        "found_pmids": case.get("found_pmids", []),
        "action_summary": case.get("action_summary", {}),
        "search_history_path": case.get("search_history_path", ""),
    }, metadata


def render_prompt(
    workflow_prompt_text: str,
    current_section00: str,
    cases: List[Tuple[Dict, List[Dict]]],
    imperative_blocks: Dict[str, str] | None = None,
) -> str:
    sections = [
        "# SECTION_00 and Imperative/Example Block Rewrite Task",
        "",
        "You must rewrite the editable SECTION_00 block.",
        "You MAY also rewrite one or more of the imperative/example blocks if the diagnosis "
        "indicates that updating those blocks would better address low LLM adherence than "
        "expanding SECTION_00 with more prose.",
        "Return the rewritten block(s) including their boundary markers.",
        "",
        extract_section(workflow_prompt_text, "SECTION_00 Rewrite Scope"),
        "",
        extract_section(workflow_prompt_text, "Trigger for Refinement"),
        "",
        extract_section(workflow_prompt_text, "Inputs for Diagnosis"),
        "",
        extract_section(workflow_prompt_text, "LLM Rewrite Task"),
        "",
        "## Current editable SECTION_00 block",
        "",
        "```text",
        current_section00,
        "```",
        "",
    ]

    # Append current imperative/example blocks so the LLM can see and optionally rewrite them
    if imperative_blocks:
        for block_info in IMPERATIVE_BLOCKS:
            label = block_info["label"]
            description = block_info["description"]
            current_text = imperative_blocks.get(block_info["variable"], "")
            sections.extend([
                f"## Current {label}",
                "",
                f"*{description}*",
                "",
                "```text",
                current_text,
                "```",
                "",
            ])

    try:
        sections.extend([
            extract_section(workflow_prompt_text, "Imperative and Example Block Rewrite"),
            "",
        ])
    except ValueError:
        pass  # Section not yet in workflow prompt — skip silently

    sections.append("## Low-performing training SR cases")
    sections.append("")

    for idx, (case, metadata) in enumerate(cases, 1):
        sections.extend(
            [
                f"### Case {idx}: {case['sr_path']}",
                "",
                f"- target_name: `{case['target_name']}`",
                f"- objectives: {case['objectives']}",
                f"- inclusion_criteria: {case['inclusion_criteria']}",
                f"- recall: `{case['recall']}`",
                f"- previous_recall: `{case['previous_recall']}`",
                f"- delta_recall_vs_previous: `{case['delta_recall_vs_previous']}`",
                f"- rewrite_priority_reason: `{case.get('rewrite_priority_reason', '')}`",
                f"- total_hits: `{case['total_hits']}`",
                f"- search_history_path: `{case['search_history_path']}`",
                "",
                "#### Previous query",
                "",
                "```text",
                case["query"],
                "```",
                "",
                "#### Missed PMID metadata",
                "",
            ]
        )
        if metadata:
            for row in metadata:
                sections.extend(
                    [
                        f"- PMID `{row.get('pmid', '')}`",
                        f"  Title: {row.get('title', '')}",
                        f"  Abstract: {row.get('abstract', '') or '(no abstract returned)'}",
                        f"  MeSH: {', '.join(row.get('mesh_terms', [])) or '(none)'}",
                    ]
                )
        else:
            sections.append("- No missed PMID metadata available.")

        sections.extend(
            [
                "",
                "#### Action summary",
                "",
                "```json",
                json.dumps(case.get("action_summary", {}), indent=2, ensure_ascii=False),
                "```",
                "",
            ]
        )

    sections.extend(
        [
            "## Output requirement",
            "",
            "Always return the rewritten SECTION_00 block, starting with `# SECTION_00_REWRITE_BEGIN`",
            "and ending with `# SECTION_00_REWRITE_END`.",
            "",
            "Optionally also return any of the following blocks you are changing:",
            "- TIAB_IMPERATIVE_CONDITIONAL_ADD: between `# TIAB_IMPL_COND_ADD_BEGIN` and `# TIAB_IMPL_COND_ADD_END`",
            "- ONE_SHOT_IMPERATIVE_PRIMARY: between `# ONE_SHOT_PRIMARY_BEGIN` and `# ONE_SHOT_PRIMARY_END`",
            "- PLACEHOLDER_INITIAL_PRIMARY: between `# PLACEHOLDER_INIT_BEGIN` and `# PLACEHOLDER_INIT_END`",
            "",
            "Omit any block you are not changing. All blocks are applied independently.",
        ]
    )
    return "\n".join(sections) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate an LLM input file for rewriting SECTION_00.")
    ap.add_argument("--bundle-root", required=True)
    ap.add_argument("--diagnostics-path", required=True)
    ap.add_argument("--workflow-prompt", required=True)
    ap.add_argument("--analyze-script", required=True)
    ap.add_argument("--output-prompt", required=True)
    ap.add_argument("--output-metadata-json", required=True)
    ap.add_argument("--low-recall-threshold", type=float, default=0.60)
    ap.add_argument("--delta-threshold", type=float, default=0.05)
    args = ap.parse_args()

    bundle_root = Path(args.bundle_root).resolve()
    diagnostics = read_json(Path(args.diagnostics_path))
    workflow_prompt_text = read_text(Path(args.workflow_prompt))
    analyze_text = read_text(Path(args.analyze_script))
    current_section00 = extract_section00_block(analyze_text)

    # Extract current imperative/example blocks for the LLM prompt
    current_imperative_blocks: dict[str, str] = {}
    for block_info in IMPERATIVE_BLOCKS:
        try:
            current_imperative_blocks[block_info["variable"]] = extract_editable_block(
                analyze_text,
                block_info["variable"],
                block_info["begin"],
                block_info["end"],
            )
        except ValueError:
            pass  # Block not yet in file — skip

    selected = select_low_performing_cases(
        diagnostics=diagnostics,
        low_recall_threshold=args.low_recall_threshold,
        delta_threshold=args.delta_threshold,
    )

    output_prompt = Path(args.output_prompt)
    output_prompt.parent.mkdir(parents=True, exist_ok=True)
    output_metadata = Path(args.output_metadata_json)
    output_metadata.parent.mkdir(parents=True, exist_ok=True)

    if not selected:
        payload = {"selected_case_count": 0, "cases": []}
        output_metadata.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        output_prompt.write_text("No low-performing cases met the rewrite trigger.\n", encoding="utf-8")
        print("No low-performing cases met the rewrite trigger.")
        print(f"PROMPT_PATH={output_prompt}")
        print(f"METADATA_PATH={output_metadata}")
        return

    case_bundles = [build_case_bundle(bundle_root, case) for case in selected]
    metadata_payload = {
        "selected_case_count": len(case_bundles),
        "cases": [{"case": case, "missed_metadata": metadata} for case, metadata in case_bundles],
    }
    prompt_text = render_prompt(
        workflow_prompt_text=workflow_prompt_text,
        current_section00=current_section00,
        cases=case_bundles,
        imperative_blocks=current_imperative_blocks,
    )

    output_metadata.write_text(json.dumps(metadata_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    output_prompt.write_text(prompt_text, encoding="utf-8")
    print(f"PROMPT_PATH={output_prompt}")
    print(f"METADATA_PATH={output_metadata}")
    print(f"SELECTED_CASE_COUNT={len(case_bundles)}")


if __name__ == "__main__":
    main()
