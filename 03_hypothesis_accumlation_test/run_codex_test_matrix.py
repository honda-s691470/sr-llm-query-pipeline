from __future__ import annotations

import argparse
import os
import shutil
import subprocess

import requests
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
    parser.add_argument("--model", default="gpt-5.3-codex", help="Codex model ID.")
    parser.add_argument(
        "--no-codex-api-fallback",
        action="store_true",
        help="Disable OpenAI Responses API fallback when Codex CLI fails.",
    )
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
    command.extend(["-m", args.model])
    command.append("-")
    with (run_dir / "codex_stdout.log").open("w", encoding="utf-8") as stdout_handle, (
        run_dir / "codex_stderr.log"
    ).open("w", encoding="utf-8") as stderr_handle:
        completed = subprocess.run(
            command,
            input=prompt_text,
            text=True,
            encoding="utf-8",
            stdout=stdout_handle,
            stderr=stderr_handle,
            check=False,
        )
    if completed.returncode != 0 and not args.no_codex_api_fallback:
        return run_codex_api_fallback(run_dir, args, prompt_text, cli_returncode=completed.returncode)
    return completed


def load_dotenv_map(dotenv_path: Path) -> dict[str, str]:
    loaded: dict[str, str] = {}
    if not dotenv_path.exists():
        return loaded
    for raw_line in dotenv_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        loaded[key.strip()] = value.strip().strip('"').strip("'")
    return loaded


def load_openai_api_key() -> str:
    if os.environ.get("OPENAI_API_KEY"):
        return os.environ["OPENAI_API_KEY"]
    root = TEST_PIPELINE_DIR.parent.parent
    for dotenv_path in (root / ".env", TEST_PIPELINE_DIR.parent / ".env"):
        loaded = load_dotenv_map(dotenv_path)
        if loaded.get("OPENAI_API_KEY"):
            return loaded["OPENAI_API_KEY"]
    return ""


def build_openai_fallback_prompt(run_dir: Path, prompt_text: str) -> str:
    parts = [
        prompt_text.strip(),
        "",
        "The Codex CLI was unavailable. Use the following attached file contents from the run directory.",
    ]
    for name in ("test_prompt_with.md", "test_prompt_without.md", "input_config.json", "query_laws.txt"):
        path = run_dir / name
        if path.exists():
            parts.extend(["", f"===== FILE: {name} =====", path.read_text(encoding="utf-8-sig", errors="replace")])
    return "\n".join(parts).strip() + "\n"


def extract_openai_response_text(payload: dict[str, object]) -> str:
    texts: list[str] = []
    for item in payload.get("output", []) or []:
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []) or []:
            if isinstance(content, dict) and content.get("type") in {"output_text", "text"}:
                texts.append(str(content.get("text", "")))
    if texts:
        return "\n".join(texts)
    return str(payload.get("output_text", ""))


def run_codex_api_fallback(run_dir: Path, args: argparse.Namespace, prompt_text: str, *, cli_returncode: int) -> subprocess.CompletedProcess[str]:
    api_key = load_openai_api_key()
    fallback_log = run_dir / "openai_api_fallback.log"
    if not api_key:
        msg = "Codex CLI failed and OPENAI_API_KEY was not found for API fallback."
        fallback_log.write_text(msg + "\n", encoding="utf-8")
        return subprocess.CompletedProcess(["openai_responses_api", args.model], 1, stdout="", stderr=msg)
    try:
        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": args.model, "input": build_openai_fallback_prompt(run_dir, prompt_text), "max_output_tokens": 8096},
            timeout=300,
        )
        if response.status_code >= 400:
            err = response.text[:2000]
            fallback_log.write_text(f"cli_returncode={cli_returncode}\napi_status={response.status_code}\n{err}\n", encoding="utf-8")
            return subprocess.CompletedProcess(["openai_responses_api", args.model], 1, stdout="", stderr=err)
        payload = response.json()
        response_text = extract_openai_response_text(payload)
        (run_dir / "raw_last_message.txt").write_text(response_text, encoding="utf-8")
        (run_dir / "codex_stdout.log").write_text(response_text, encoding="utf-8")
        fallback_log.write_text(f"cli_returncode={cli_returncode}\napi_status={response.status_code}\nmodel={payload.get('model', args.model)}\n", encoding="utf-8")
        return subprocess.CompletedProcess(["openai_responses_api", args.model], 0, stdout=response_text, stderr="")
    except Exception as exc:
        msg = f"Codex API fallback failed: {exc}"
        fallback_log.write_text(f"cli_returncode={cli_returncode}\n{msg}\n", encoding="utf-8")
        return subprocess.CompletedProcess(["openai_responses_api", args.model], 1, stdout="", stderr=msg)


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
