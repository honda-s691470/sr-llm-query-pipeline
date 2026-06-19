from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

from pipeline_common import (
    TEST_DATA_DIR,
    TEST_PIPELINE_DIR,
    extract_pubmed_query_from_text,
    normalize_query,
    scan_papers,
    test_paper_dir,
    timestamp_for_paths,
    utc_timestamp,
    write_json,
)


CONDITION_CONFIG = {
    "with_laws": {
        "prompt_file": "test_prompt_with.md",
        "bundle_files": ("test_prompt_with.md", "input_config.json", "query_laws.txt"),
        "wrapper": "Read test_prompt_with.md and start the task with the attached files.",
    },
    "without_laws": {
        "prompt_file": "test_prompt_without.md",
        "bundle_files": ("test_prompt_without.md", "input_config.json"),
        "wrapper": "Read test_prompt_without.md and start the task with the attached files.",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run isolated Codex test-phase jobs for with/without laws.")
    parser.add_argument("--domain", action="append", default=[], help="Restrict to one or more domain folders.")
    parser.add_argument("--paper", action="append", default=[], help="Restrict to one or more paper folders.")
    parser.add_argument("--condition", choices=["with_laws", "without_laws", "both"], default="both")
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--approval", default="never")
    parser.add_argument("--sandbox", default="danger-full-access")
    parser.add_argument("--model", default="", help="Optional Codex model override.")
    parser.add_argument(
        "--output-condition",
        default="",
        help="Optional output condition label override (example: with_laws_v9). If omitted, uses --condition value.",
    )
    parser.add_argument("--skip-existing", action="store_true", help="Skip if normalized_query.txt already exists in model_outputs.")
    parser.add_argument("--bundle-only", action="store_true", help="Prepare isolated run bundles but do not execute Codex.")
    return parser.parse_args()


def selected_conditions(condition: str) -> list[str]:
    if condition == "both":
        return ["without_laws", "with_laws"]
    return [condition]


def build_prompt_text(condition: str) -> str:
    cfg = CONDITION_CONFIG[condition]
    lines = [
        cfg["wrapper"],
        "",
        "Use only the attached files in this run directory.",
        "Return exactly one final PubMed query.",
        "Preferred output format: FULL_QUERY: <query>",
    ]
    return "\n".join(lines) + "\n"


def prepare_bundle(run_dir: Path, paper_dir: Path, condition: str) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    cfg = CONDITION_CONFIG[condition]

    prompt_src = TEST_PIPELINE_DIR / cfg["prompt_file"]
    shutil.copy2(prompt_src, run_dir / cfg["prompt_file"])
    shutil.copy2(paper_dir / "input_config.json", run_dir / "input_config.json")

    if condition == "with_laws":
        shutil.copy2(TEST_PIPELINE_DIR.parent / "03_meta_extraction_prompt" / "query_laws.txt", run_dir / "query_laws.txt")

    (run_dir / "run_instruction.txt").write_text(build_prompt_text(condition), encoding="utf-8")


def run_codex(run_dir: Path, args: argparse.Namespace, prompt_text: str) -> subprocess.CompletedProcess[str]:
    command = [
        args.codex_bin,
        "-a",
        args.approval,
        "exec",
        "--ephemeral",
        "--skip-git-repo-check",
        "-s",
        args.sandbox,
        "-C",
        str(run_dir),
        "-o",
        str(run_dir / "raw_last_message.txt"),
    ]
    if args.model:
        command.extend(["-m", args.model])
    command.append("-")
    with (run_dir / "codex_stdout.log").open("w", encoding="utf-8") as stdout_handle, (
        run_dir / "codex_stderr.log"
    ).open("w", encoding="utf-8") as stderr_handle:
        return subprocess.run(
            command,
            input=prompt_text,
            text=True,
            encoding="utf-8",
            stdout=stdout_handle,
            stderr=stderr_handle,
            check=False,
        )


def main() -> int:
    args = parse_args()
    domain_filter = set(args.domain) if args.domain else None
    paper_filter = set(args.paper) if args.paper else None
    run_stamp = timestamp_for_paths()
    run_root = TEST_PIPELINE_DIR / "runs" / run_stamp / "codex"

    jobs: list[dict[str, str]] = []
    for domain_folder, paper_folder in scan_papers(TEST_DATA_DIR, domain_filter=domain_filter):
        if paper_filter and paper_folder not in paper_filter:
            continue
        paper_dir = test_paper_dir(domain_folder, paper_folder)
        if not paper_dir.exists():
            continue
        for condition in selected_conditions(args.condition):
            jobs.append({"domain_folder": domain_folder, "paper_folder": paper_folder, "condition": condition})

    summary: dict[str, object] = {
        "generated_at": utc_timestamp(),
        "run_root": str(run_root),
        "bundle_only": args.bundle_only,
        "jobs": [],
    }

    for job in jobs:
        domain_folder = job["domain_folder"]
        paper_folder = job["paper_folder"]
        condition = job["condition"]
        output_condition = args.output_condition.strip() or condition
        paper_dir = test_paper_dir(domain_folder, paper_folder)
        output_dir = paper_dir / "model_outputs" / "codex" / output_condition

        if args.skip_existing and (output_dir / "normalized_query.txt").exists():
            summary["jobs"].append({**job, "status": "skipped_existing"})
            continue

        run_dir = run_root / domain_folder / paper_folder / condition
        prepare_bundle(run_dir, paper_dir, condition)
        prompt_text = (run_dir / "run_instruction.txt").read_text(encoding="utf-8")

        result_record: dict[str, object] = {
            **job,
            "run_dir": str(run_dir),
            "status": "bundle_prepared",
        }

        if not args.bundle_only:
            completed = run_codex(run_dir, args, prompt_text)
            raw_message = (
                (run_dir / "raw_last_message.txt").read_text(encoding="utf-8", errors="ignore")
                if (run_dir / "raw_last_message.txt").exists()
                else ""
            )
            extracted_query = normalize_query(extract_pubmed_query_from_text(raw_message))
            output_dir.mkdir(parents=True, exist_ok=True)
            if (run_dir / "raw_last_message.txt").exists():
                shutil.copy2(run_dir / "raw_last_message.txt", output_dir / "raw_last_message.txt")
            shutil.copy2(run_dir / "codex_stdout.log", output_dir / "codex_stdout.log")
            shutil.copy2(run_dir / "codex_stderr.log", output_dir / "codex_stderr.log")
            (output_dir / "normalized_query.txt").write_text(extracted_query + "\n", encoding="utf-8")
            write_json(
                output_dir / "result.json",
                {
                    "generated_at": utc_timestamp(),
                    "provider": "codex",
                    "condition": output_condition,
                    "paper_folder": paper_folder,
                    "domain_folder": domain_folder,
                    "returncode": completed.returncode,
                    "status": "completed"
                    if completed.returncode == 0 and extracted_query
                    else ("completed_no_query" if completed.returncode == 0 else "codex_failed"),
                    "query": extracted_query,
                    "run_dir": str(run_dir),
                },
            )
            result_record.update(
                {
                    "returncode": completed.returncode,
                    "normalized_query_length": len(extracted_query),
                    "status": "completed"
                    if completed.returncode == 0 and extracted_query
                    else ("completed_no_query" if completed.returncode == 0 else "codex_failed"),
                    "output_dir": str(output_dir),
                }
            )
        summary["jobs"].append(result_record)

    write_json(run_root / "run_summary.json", summary)
    print(run_root / "run_summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
