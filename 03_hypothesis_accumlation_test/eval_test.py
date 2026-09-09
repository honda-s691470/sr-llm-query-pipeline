from __future__ import annotations

import argparse
import contextlib
import csv
import json
import math
import os
import shutil
import subprocess
import time
from pathlib import Path

import requests

from pipeline_common import (
    SOURCE_DATA_DIR,
    TEST_DATA_DIR,
    extract_pubmed_query_from_text,
    normalize_query,
    scan_papers,
    timestamp_for_paths,
    utc_timestamp,
    write_json,
)


BASE_DIR = Path(__file__).resolve().parent
PUBLIC_RELEASE_DIR = BASE_DIR.parent
TEST_PROMPT_DIR = PUBLIC_RELEASE_DIR / "03_hypothesis_accumlation_test"
QUERY_LAWS_DIR = PUBLIC_RELEASE_DIR / "02_query_laws_refinement"
TEST_DATA_DIR = PUBLIC_RELEASE_DIR / "05_test_data"
PUBMED_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_RATE_LIMIT_SLEEP = 1.0

CONDITION_CONFIG = {
    "with_laws": {
        "prompt_file": "test_prompt_with.md",
        "uses_laws": True,
        "wrapper": "Read test_prompt_with.md and start the task with the attached files.",
    },
    "without_laws": {
        "prompt_file": "test_prompt_without.md",
        "uses_laws": False,
        "wrapper": "Read test_prompt_without.md and start the task with the attached files.",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate and evaluate test-set PubMed queries across providers.")
    parser.add_argument("--model", required=True, help="Model identifier. Provider is inferred unless --provider is supplied.")
    parser.add_argument("--provider", default="", help="Optional provider override. Example: codex, claude.")
    parser.add_argument("--domain", action="append", default=[], help="Restrict to one or more domain folders.")
    parser.add_argument("--paper", action="append", default=[], help="Restrict to one or more paper folders.")
    parser.add_argument("--condition", choices=["with_laws", "without_laws"], default="with_laws")
    parser.add_argument(
        "--output-condition",
        default="",
        help="Optional output condition label. Default is '<condition>_test_eval'.",
    )
    parser.add_argument(
        "--query-laws-path",
        default="",
        help="Optional explicit query_laws/rulebook path for with_laws runs. If omitted, the newest query_laws_ver*.txt is used.",
    )
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument(
        "--no-codex-api-fallback",
        action="store_true",
        help="Disable OpenAI Responses API fallback when Codex CLI fails.",
    )
    parser.add_argument("--claude-bin", default="claude")
    parser.add_argument("--gemini-bin", default="gemini")
    parser.add_argument("--approval", default="never")
    parser.add_argument("--sandbox", default="danger-full-access")
    parser.add_argument("--skip-existing", action="store_true", help="Skip papers with an existing normalized_query.txt.")
    parser.add_argument("--bundle-only", action="store_true", help="Prepare run bundles but do not execute the model.")
    parser.add_argument("--pubmed-timeout-seconds", type=int, default=45)
    parser.add_argument(
        "--split",
        choices=["train", "test"],
        default="test",
        help="'test' targets 05_test_data (default); 'train' targets 04_data.",
    )
    parser.add_argument(
        "--log",
        action="store_true",
        help="Save log files (bundle_metadata.json, provider_stderr.log) to output_dir.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Iterate through target papers without executing the model or writing any files.",
    )
    return parser.parse_args()


def infer_provider(model: str, provider_override: str) -> str:
    if provider_override.strip():
        return provider_override.strip().lower()
    lowered = model.lower()
    if "claude" in lowered:
        return "claude"
    if "gemini" in lowered:
        return "gemini"
    if "codex" in lowered or lowered.startswith("gpt-"):
        return "codex"
    raise ValueError(f"Could not infer provider from model '{model}'. Pass --provider explicitly.")


def latest_query_laws_path() -> Path:
    candidates = sorted(
        QUERY_LAWS_DIR.glob("query_laws_ver*.txt"),
        key=lambda path: (path.stat().st_mtime, path.name),
    )
    if not candidates:
        raise FileNotFoundError(f"No query_laws_ver*.txt found in {QUERY_LAWS_DIR}")
    return candidates[-1]


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


def prepare_bundle(run_dir: Path, paper_dir: Path, condition: str, laws_path: Path | None, *, save_logs: bool = False) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    cfg = CONDITION_CONFIG[condition]

    prompt_src = TEST_PROMPT_DIR / cfg["prompt_file"]
    if not prompt_src.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_src}")
    shutil.copy2(prompt_src, run_dir / cfg["prompt_file"])
    shutil.copy2(paper_dir / "input_config.json", run_dir / "input_config.json")

    if cfg["uses_laws"]:
        if laws_path is None:
            raise ValueError("laws_path is required for with_laws condition")
        shutil.copy2(laws_path, run_dir / laws_path.name)
        shutil.copy2(laws_path, run_dir / "query_laws.txt")

    (run_dir / "run_instruction.txt").write_text(build_prompt_text(condition), encoding="utf-8")
    if save_logs:
        write_json(
            run_dir / "bundle_metadata.json",
            {
                "generated_at": utc_timestamp(),
                "condition": condition,
                "prompt_file": cfg["prompt_file"],
                "query_laws_file": laws_path.name if laws_path else "",
            },
        )


def run_codex_cli(run_dir: Path, args: argparse.Namespace, prompt_text: str, *, save_logs: bool = False) -> subprocess.CompletedProcess[str]:
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
        "-m",
        args.model,
        "-",
    ]
    stderr_ctx = (
        (run_dir / "provider_stderr.log").open("w", encoding="utf-8")
        if save_logs
        else contextlib.nullcontext(subprocess.DEVNULL)
    )
    with (run_dir / "provider_stdout.log").open("w", encoding="utf-8") as stdout_handle, stderr_ctx as stderr_handle:
        completed = subprocess.run(
            command,
            input=prompt_text,
            text=True,
            encoding="utf-8",
            stdout=stdout_handle,
            stderr=stderr_handle,
            check=False,
            shell=True,
        )
    if completed.returncode != 0 and not args.no_codex_api_fallback:
        return run_codex_api_fallback(run_dir, args, prompt_text, cli_returncode=completed.returncode)
    return completed


def load_openai_api_key() -> str:
    if os.environ.get("OPENAI_API_KEY"):
        return os.environ["OPENAI_API_KEY"]
    for dotenv_path in (PUBLIC_RELEASE_DIR.parent / ".env", PUBLIC_RELEASE_DIR / ".env"):
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
            parts.extend(
                [
                    "",
                    f"===== FILE: {name} =====",
                    path.read_text(encoding="utf-8-sig", errors="replace"),
                ]
            )
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


def run_codex_api_fallback(
    run_dir: Path,
    args: argparse.Namespace,
    prompt_text: str,
    *,
    cli_returncode: int,
) -> subprocess.CompletedProcess[str]:
    api_key = load_openai_api_key()
    fallback_log = run_dir / "openai_api_fallback.log"
    if not api_key:
        msg = "Codex CLI failed and OPENAI_API_KEY was not found for API fallback."
        fallback_log.write_text(msg + "\n", encoding="utf-8")
        return subprocess.CompletedProcess(["openai_responses_api", args.model], 1, stdout="", stderr=msg)

    payload = {
        "model": args.model,
        "input": build_openai_fallback_prompt(run_dir, prompt_text),
        "max_output_tokens": 8096,
    }
    try:
        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=300,
        )
        if response.status_code >= 400:
            err = response.text[:2000]
            fallback_log.write_text(
                f"cli_returncode={cli_returncode}\napi_status={response.status_code}\n{err}\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(["openai_responses_api", args.model], 1, stdout="", stderr=err)
        response_payload = response.json()
        response_text = extract_openai_response_text(response_payload)
        (run_dir / "raw_last_message.txt").write_text(response_text, encoding="utf-8")
        (run_dir / "provider_stdout.log").write_text(response_text, encoding="utf-8")
        fallback_log.write_text(
            f"cli_returncode={cli_returncode}\napi_status={response.status_code}\nmodel={response_payload.get('model', args.model)}\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(["openai_responses_api", args.model], 0, stdout=response_text, stderr="")
    except Exception as exc:
        msg = f"Codex API fallback failed: {exc}"
        fallback_log.write_text(f"cli_returncode={cli_returncode}\n{msg}\n", encoding="utf-8")
        return subprocess.CompletedProcess(["openai_responses_api", args.model], 1, stdout="", stderr=msg)


def run_claude_cli(run_dir: Path, args: argparse.Namespace, prompt_text: str, *, save_logs: bool = False) -> subprocess.CompletedProcess[str]:
    command = [
        args.claude_bin,
        "-p",
        "--model",
        args.model,
        "--add-dir",
        str(run_dir),
    ]
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)
    completed = subprocess.run(
        command,
        input=prompt_text,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
        env=env,
        cwd=run_dir,
    )
    (run_dir / "provider_stdout.log").write_text(completed.stdout or "", encoding="utf-8")
    if save_logs:
        (run_dir / "provider_stderr.log").write_text(completed.stderr or "", encoding="utf-8")
    (run_dir / "raw_last_message.txt").write_text(completed.stdout or "", encoding="utf-8")
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
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            loaded[key] = value
    return loaded


def subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(load_dotenv_map(PUBLIC_RELEASE_DIR.parent / ".env"))
    return env


def resolve_windows_cli(bin_name: str, cmd_fallback_name: str) -> str:
    resolved = shutil.which(bin_name)
    if resolved:
        return resolved
    fallback = shutil.which(cmd_fallback_name)
    if fallback:
        return fallback
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        candidate = Path(appdata) / "npm" / cmd_fallback_name
        if candidate.exists():
            return str(candidate)
    return bin_name


def run_gemini_cli(run_dir: Path, args: argparse.Namespace, prompt_text: str, *, save_logs: bool = False) -> subprocess.CompletedProcess[str]:
    command = [
        resolve_windows_cli(args.gemini_bin, "gemini.cmd"),
        "--yolo",
        "--skip-trust",
        "-m",
        args.model,
        "--output-format",
        "text",
        "-p",
        prompt_text,
    ]
    completed = subprocess.run(
        command,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
        env=subprocess_env(),
        cwd=run_dir,
    )
    (run_dir / "provider_stdout.log").write_text(completed.stdout or "", encoding="utf-8")
    if save_logs:
        (run_dir / "provider_stderr.log").write_text(completed.stderr or "", encoding="utf-8")
    (run_dir / "raw_last_message.txt").write_text(completed.stdout or "", encoding="utf-8")
    return completed


def run_provider(run_dir: Path, args: argparse.Namespace, provider: str, prompt_text: str, *, save_logs: bool = False) -> subprocess.CompletedProcess[str]:
    if provider == "codex":
        return run_codex_cli(run_dir, args, prompt_text, save_logs=save_logs)
    if provider == "claude":
        return run_claude_cli(run_dir, args, prompt_text, save_logs=save_logs)
    if provider == "gemini":
        return run_gemini_cli(run_dir, args, prompt_text, save_logs=save_logs)
    raise NotImplementedError(f"Provider '{provider}' is not implemented in eval_test.py.")


def load_gold_pmids(paper_dir: Path) -> set[str]:
    # 05_test_data papers have gold_pmids.json; 04_data papers have gold_pmids in input_config.json
    for fname in ("gold_pmids.json", "input_config.json"):
        gold_path = paper_dir / fname
        if gold_path.exists():
            gold_data = json.loads(gold_path.read_text(encoding="utf-8-sig"))
            pmids = {str(pmid).strip() for pmid in gold_data.get("gold_pmids", []) if str(pmid).strip()}
            if pmids:
                return pmids
    return set()


def precision_from_hits(hit_gold: int, total_hits: int) -> float:
    if total_hits <= 0 or hit_gold <= 0:
        return 0.0
    return hit_gold / total_hits


def f1_from_precision_recall(precision: float, recall: float) -> float:
    if precision <= 0.0 or recall <= 0.0:
        return 0.0
    return 2.0 * precision * recall / (precision + recall)


def nnr_from_hits(hit_gold: int, total_hits: int) -> float:
    if hit_gold <= 0:
        return math.inf if total_hits > 0 else 0.0
    return total_hits / hit_gold


def fetch_pubmed_stats(
    query: str,
    gold_pmids: set[str],
    session: requests.Session,
    timeout_seconds: int,
) -> tuple[int, int, float, float, float, str]:
    if not query:
        return 0, 0, 0.0, 0.0, 0.0, "empty_query"

    try:
        time.sleep(PUBMED_RATE_LIMIT_SLEEP)
        hits_resp = session.post(
            PUBMED_ESEARCH_URL,
            data={"db": "pubmed", "term": query, "retmode": "json", "retmax": 0},
            timeout=timeout_seconds,
        )
        hits_resp.raise_for_status()
        hits_data = hits_resp.json()
        total_hits = int(hits_data.get("esearchresult", {}).get("count", "0"))
    except Exception as exc:
        return 0, 0, 0.0, 0.0, 0.0, f"hit_error: {exc}"

    if not gold_pmids:
        return total_hits, 0, 0.0, 0.0, 0.0, "no_gold_pmids"

    gold_query = " OR ".join(sorted(gold_pmids))
    validation_query = f"({query}) AND ({gold_query})"
    try:
        time.sleep(PUBMED_RATE_LIMIT_SLEEP)
        recall_resp = session.post(
            PUBMED_ESEARCH_URL,
            data={"db": "pubmed", "term": validation_query, "retmode": "json", "retmax": 10000},
            timeout=timeout_seconds,
        )
        recall_resp.raise_for_status()
        recall_data = recall_resp.json()
        found = set(recall_data.get("esearchresult", {}).get("idlist", []))
        hit_gold = len(found)
        recall = hit_gold / len(gold_pmids)
        precision = precision_from_hits(hit_gold, total_hits)
        f1 = f1_from_precision_recall(precision, recall)
        return total_hits, hit_gold, recall, nnr_from_hits(hit_gold, total_hits), f1, ""
    except Exception as exc:
        return total_hits, 0, 0.0, 0.0, 0.0, f"recall_error: {exc}"


def safe_metric_value(value: float) -> float | None:
    if math.isinf(value) or math.isnan(value):
        return None
    return value


def main() -> int:
    args = parse_args()
    provider = infer_provider(args.model, args.provider)
    domain_filter = set(args.domain) if args.domain else None
    paper_filter = set(args.paper) if args.paper else None
    output_condition = args.output_condition.strip() or f"{args.condition}_test_eval"
    laws_path = None
    if CONDITION_CONFIG[args.condition]["uses_laws"]:
        if args.query_laws_path.strip():
            laws_path = Path(args.query_laws_path).expanduser().resolve()
            if not laws_path.exists():
                raise FileNotFoundError(f"Explicit query laws file not found: {laws_path}")
        else:
            laws_path = latest_query_laws_path()

    base_data_dir = SOURCE_DATA_DIR if args.split == "train" else TEST_DATA_DIR
    results_dir = base_data_dir / "_results"

    run_stamp = timestamp_for_paths()
    run_root = TEST_PROMPT_DIR / "runs" / run_stamp / provider
    summary_rows: list[dict[str, object]] = []

    session = requests.Session()
    session.headers.update({"User-Agent": f"TestQueryEval/{provider}/1.0"})

    for domain_folder, paper_folder in scan_papers(base_data_dir, domain_filter=domain_filter):
        if paper_filter and paper_folder not in paper_filter:
            continue
        paper_dir = base_data_dir / domain_folder / paper_folder
        if not paper_dir.exists():
            continue

        output_dir = paper_dir / "model_outputs" / provider / output_condition
        result_record: dict[str, object] = {
            "generated_at": utc_timestamp(),
            "domain_folder": domain_folder,
            "paper_folder": paper_folder,
            "provider": provider,
            "model": args.model,
            "condition": output_condition,
        }
        if args.skip_existing and (output_dir / "normalized_query.txt").exists():
            extracted_query = (output_dir / "normalized_query.txt").read_text(encoding="utf-8").strip()
            gold_pmids = load_gold_pmids(paper_dir)
            total_hits, hit_gold, recall, nnr, f1, error_note = fetch_pubmed_stats(
                extracted_query, gold_pmids, session, args.pubmed_timeout_seconds
            )
            status = "completed" if not error_note else "eval_error"
            result_payload = {
                **result_record,
                "returncode": 0,
                "status": status,
                "query": extracted_query,
                "query_length": len(extracted_query),
                "gold_count": len(gold_pmids),
                "total_hits": total_hits,
                "hit_gold_count": hit_gold,
                "recall": recall,
                "nnr": safe_metric_value(nnr),
                "f1": f1,
                "error_note": error_note,
            }
            (output_dir / "result.json").write_text(json.dumps(result_payload, indent=2), encoding="utf-8")
            summary_rows.append(result_payload)
            continue

        if args.dry_run:
            print(f"[dry-run] {domain_folder}/{paper_folder}")
            continue

        run_dir = run_root / domain_folder / paper_folder / args.condition
        prepare_bundle(run_dir, paper_dir, args.condition, laws_path, save_logs=args.log)
        prompt_text = (run_dir / "run_instruction.txt").read_text(encoding="utf-8")

        if args.bundle_only:
            result_record["status"] = "bundle_prepared"
            summary_rows.append(result_record)
            continue

        completed = run_provider(run_dir, args, provider, prompt_text, save_logs=args.log)
        raw_message = (
            (run_dir / "raw_last_message.txt").read_text(encoding="utf-8", errors="ignore")
            if (run_dir / "raw_last_message.txt").exists()
            else ""
        )
        extracted_query = normalize_query(extract_pubmed_query_from_text(raw_message))

        output_dir.mkdir(parents=True, exist_ok=True)
        copy_names = ["raw_last_message.txt", "provider_stdout.log"]
        if args.log:
            copy_names += ["provider_stderr.log", "bundle_metadata.json"]
        for name in copy_names:
            path = run_dir / name
            if path.exists():
                shutil.copy2(path, output_dir / name)
        (output_dir / "normalized_query.txt").write_text(extracted_query + "\n", encoding="utf-8")

        gold_pmids = load_gold_pmids(paper_dir)
        if completed.returncode == 0 and extracted_query:
            total_hits, hit_gold, recall, nnr, f1, error_note = fetch_pubmed_stats(
                extracted_query,
                gold_pmids,
                session,
                args.pubmed_timeout_seconds,
            )
            status = "completed" if not error_note else "eval_error"
        elif completed.returncode == 0:
            total_hits, hit_gold, recall, nnr, f1, error_note = 0, 0, 0.0, 0.0, 0.0, "no_query_extracted"
            status = "completed_no_query"
        else:
            total_hits, hit_gold, recall, nnr, f1, error_note = 0, 0, 0.0, 0.0, 0.0, "provider_failed"
            status = "provider_failed"

        result_payload = {
            **result_record,
            "returncode": completed.returncode,
            "status": status,
            "query": extracted_query,
            "query_length": len(extracted_query),
            "gold_count": len(gold_pmids),
            "total_hits": total_hits,
            "hit_gold_count": hit_gold,
            "recall": recall,
            "nnr": safe_metric_value(nnr),
            "f1": f1,
            "error_note": error_note,
        }
        write_json(output_dir / "result.json", result_payload)
        summary_rows.append(result_payload)

    if args.dry_run:
        return 0

    results_dir.mkdir(parents=True, exist_ok=True)
    safe_model = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in args.model)
    summary_csv = results_dir / f"eval_test_{provider}_{safe_model}_{run_stamp}.csv"
    if summary_rows:
        with summary_csv.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0].keys()))
            writer.writeheader()
            writer.writerows(summary_rows)

    run_summary = {
        "generated_at": utc_timestamp(),
        "provider": provider,
        "model": args.model,
        "condition": args.condition,
        "output_condition": output_condition,
        "run_root": str(run_root),
        "query_laws_path": str(laws_path) if laws_path else "",
        "summary_csv": str(summary_csv),
        "job_count": len(summary_rows),
    }
    write_json(run_root / "run_summary.json", run_summary)
    print(run_root / "run_summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

