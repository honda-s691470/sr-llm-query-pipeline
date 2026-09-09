from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


BEGIN_MARKER = "# SECTION_00_REWRITE_BEGIN"
END_MARKER = "# SECTION_00_REWRITE_END"

# All rewritable targets: (variable_name, begin_marker, end_marker)
REWRITE_TARGETS = [
    ("SECTION_00_EDITABLE_BLOCK",                "# SECTION_00_REWRITE_BEGIN",   "# SECTION_00_REWRITE_END"),
    ("TIAB_IMPERATIVE_CONDITIONAL_ADD_EDITABLE", "# TIAB_IMPL_COND_ADD_BEGIN",   "# TIAB_IMPL_COND_ADD_END"),
    ("ONE_SHOT_IMPERATIVE_PRIMARY_EDITABLE",     "# ONE_SHOT_PRIMARY_BEGIN",     "# ONE_SHOT_PRIMARY_END"),
    ("PLACEHOLDER_INITIAL_PRIMARY_EDITABLE",     "# PLACEHOLDER_INIT_BEGIN",     "# PLACEHOLDER_INIT_END"),
]


def configure_stdio() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def run_subprocess(command: list[str], cwd: Path, input_text: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        cwd=str(cwd),
        input=input_text,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


def kill_process_tree(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        return
    subprocess.run(
        ["kill", "-TERM", str(pid)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def run_subprocess_with_timeout(
    command: list[str],
    cwd: Path,
    timeout_seconds: int,
    input_text: str | None = None,
) -> tuple[subprocess.CompletedProcess, bool]:
    proc = subprocess.Popen(
        command,
        cwd=str(cwd),
        stdin=subprocess.PIPE if input_text is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    try:
        stdout, stderr = proc.communicate(input=input_text, timeout=timeout_seconds)
        return (
            subprocess.CompletedProcess(command, proc.returncode, stdout=stdout, stderr=stderr),
            False,
        )
    except subprocess.TimeoutExpired as exc:
        kill_process_tree(proc.pid)
        stdout, stderr = proc.communicate()
        stdout = (exc.output or "") + (stdout or "")
        stderr = (exc.stderr or "") + (stderr or "")
        return (
            subprocess.CompletedProcess(command, -9, stdout=stdout, stderr=stderr),
            True,
        )


def write_failure_log(path: Path, *, command: list[str], timed_out: bool, returncode: int, stdout: str, stderr: str) -> None:
    lines = [
        f"timed_out={timed_out}",
        f"returncode={returncode}",
        f"command={' '.join(command)}",
        "",
        "STDOUT:",
        stdout or "",
        "",
        "STDERR:",
        stderr or "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")



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


def load_openai_api_key(bundle_root: Path) -> str:
    if os.environ.get("OPENAI_API_KEY"):
        return os.environ["OPENAI_API_KEY"]
    for dotenv_path in (bundle_root / ".env", bundle_root.parent / ".env"):
        loaded = load_dotenv_map(dotenv_path)
        if loaded.get("OPENAI_API_KEY"):
            return loaded["OPENAI_API_KEY"]
    return ""


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


def run_openai_responses_api(prompt_text: str, *, model: str, bundle_root: Path, max_output_tokens: int = 8096) -> str:
    api_key = load_openai_api_key(bundle_root)
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY was not found for Codex API fallback.")
    body = json.dumps({"model": model, "input": prompt_text, "max_output_tokens": max_output_tokens}).encode("utf-8")
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return extract_openai_response_text(payload)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:2000]
        raise RuntimeError(f"OpenAI Responses API fallback failed ({exc.code}): {detail}") from exc


def extract_rewrite_block(text: str, begin_marker: str = BEGIN_MARKER, end_marker: str = END_MARKER) -> str | None:
    """Extract text between begin/end markers. Returns None if not found (optional blocks)."""
    pattern = re.compile(
        rf"{re.escape(begin_marker)}.*?{re.escape(end_marker)}",
        re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        return None
    return match.group(0).strip() + "\n"


def latest_query_laws(workflow_dir: Path) -> Path | None:
    candidates = sorted(
        workflow_dir.glob("query_laws_ver*.txt"),
        key=lambda p: int(re.search(r"_ver(\d+)\.txt$", p.name).group(1)) if re.search(r"_ver(\d+)\.txt$", p.name) else 0,
    )
    return candidates[-1] if candidates else None


def main() -> None:
    configure_stdio()
    ap = argparse.ArgumentParser(description="Automatically rewrite SECTION_00 using Codex and low-performing training cases.")
    ap.add_argument("--bundle-root", required=True)
    ap.add_argument("--workflow-prompt", required=True)
    ap.add_argument("--diagnostics-path", required=True)
    ap.add_argument("--codex-command", default="codex")
    ap.add_argument("--codex-model", default="gpt-5.3-codex")
    ap.add_argument("--python-command", default="python")
    ap.add_argument("--low-recall-threshold", type=float, default=0.60)
    ap.add_argument("--delta-threshold", type=float, default=0.05)
    ap.add_argument("--codex-timeout-seconds", type=int, default=900)
    ap.add_argument(
        "--no-codex-api-fallback",
        action="store_true",
        help="Disable OpenAI Responses API fallback when Codex CLI fails.",
    )
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    bundle_root = Path(args.bundle_root).resolve()
    workflow_dir = bundle_root / "02_query_laws_refinement"
    run_logs_dir = workflow_dir / "run_logs"
    run_logs_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(args.diagnostics_path).stem.replace("step3_diagnostics_", "")

    prompt_path = run_logs_dir / f"section00_rewrite_prompt_{stem}.md"
    metadata_path = run_logs_dir / f"section00_rewrite_metadata_{stem}.json"
    raw_output_path = run_logs_dir / f"section00_rewrite_raw_{stem}.txt"
    rewrite_block_path = run_logs_dir / f"section00_rewrite_block_{stem}.txt"
    backup_source_path = run_logs_dir / f"analyze_logs_ver2_before_section00_rewrite_{stem}.py"
    failure_log_path = run_logs_dir / f"section00_rewrite_failure_{stem}.log"

    gen_cmd = [
        args.python_command,
        str(workflow_dir / "generate_section00_rewrite_input.py"),
        "--bundle-root",
        str(bundle_root),
        "--diagnostics-path",
        str(Path(args.diagnostics_path).resolve()),
        "--workflow-prompt",
        str(Path(args.workflow_prompt).resolve()),
        "--analyze-script",
        str(workflow_dir / "analyze_logs_ver2.py"),
        "--output-prompt",
        str(prompt_path),
        "--output-metadata-json",
        str(metadata_path),
        "--low-recall-threshold",
        str(args.low_recall_threshold),
        "--delta-threshold",
        str(args.delta_threshold),
    ]
    gen_proc = run_subprocess(gen_cmd, cwd=bundle_root)
    if gen_proc.returncode != 0:
        raise RuntimeError(f"Prompt generation failed:\nSTDOUT:\n{gen_proc.stdout}\nSTDERR:\n{gen_proc.stderr}")
    print(gen_proc.stdout.strip())

    metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
    if int(metadata.get("selected_case_count", 0)) == 0:
        print("No low-performing cases selected for SECTION_00 rewrite.")
        print(f"PROMPT_PATH={prompt_path}")
        print(f"METADATA_PATH={metadata_path}")
        return

    if args.dry_run:
        print("Dry run requested; skipping Codex rewrite and source update.")
        print(f"PROMPT_PATH={prompt_path}")
        print(f"METADATA_PATH={metadata_path}")
        return

    prompt_text = prompt_path.read_text(encoding="utf-8-sig")
    codex_cmd = [
        args.codex_command,
        "exec",
        "--skip-git-repo-check",
        "-s",
        "danger-full-access",
        "-C",
        ".",
        "-m",
        args.codex_model,
        "-",
    ]
    codex_proc, codex_timed_out = run_subprocess_with_timeout(
        codex_cmd,
        cwd=bundle_root,
        timeout_seconds=args.codex_timeout_seconds,
        input_text=prompt_text,
    )
    raw_output = (codex_proc.stdout or "") + ("\n" + codex_proc.stderr if codex_proc.stderr else "")
    if codex_timed_out or codex_proc.returncode != 0:
        write_failure_log(
            failure_log_path,
            command=codex_cmd,
            timed_out=codex_timed_out,
            returncode=codex_proc.returncode,
            stdout=codex_proc.stdout or "",
            stderr=codex_proc.stderr or "",
        )
        if args.no_codex_api_fallback:
            raw_output_path.write_text(raw_output, encoding="utf-8")
            if codex_timed_out:
                raise RuntimeError(
                    "Codex rewrite timed out. "
                    f"See: {raw_output_path} and {failure_log_path}"
                )
            raise RuntimeError(
                "Codex rewrite failed. "
                f"See: {raw_output_path} and {failure_log_path}"
            )
        raw_output = run_openai_responses_api(prompt_text, model=args.codex_model, bundle_root=bundle_root)
        (run_logs_dir / f"section00_rewrite_api_fallback_{stem}.log").write_text(
            f"codex_cli_returncode={codex_proc.returncode}\ncodex_cli_timed_out={codex_timed_out}\nmodel={args.codex_model}\n",
            encoding="utf-8",
        )

    raw_output_path.write_text(raw_output, encoding="utf-8")

    # Apply each rewritable block found in the LLM output
    applied_targets = []
    first_target = True
    for var_name, begin_m, end_m in REWRITE_TARGETS:
        block_text = extract_rewrite_block(raw_output, begin_m, end_m)
        if block_text is None:
            continue  # LLM did not output this block — skip
        block_path = run_logs_dir / f"rewrite_block_{var_name}_{stem}.txt"
        block_path.write_text(block_text, encoding="utf-8")
        backup_arg = str(backup_source_path) if first_target else str(backup_source_path.with_suffix(f".{var_name}.py"))
        apply_cmd = [
            args.python_command,
            str(workflow_dir / "rewrite_section00_block.py"),
            "--source",
            str(workflow_dir / "analyze_logs_ver2.py"),
            "--rewrite-block",
            str(block_path),
            "--target-variable",
            var_name,
            "--backup-path",
            backup_arg,
        ]
        apply_proc = run_subprocess(apply_cmd, cwd=bundle_root)
        if apply_proc.returncode != 0:
            raise RuntimeError(
                f"Failed to apply rewritten block for {var_name}:\n{apply_proc.stdout}\n{apply_proc.stderr}"
            )
        print(apply_proc.stdout.strip())
        applied_targets.append(var_name)
        first_target = False

    if not applied_targets:
        raise RuntimeError(
            f"LLM output contained no recognized rewrite blocks. "
            f"Expected at least '{BEGIN_MARKER}...{END_MARKER}'. "
            f"See: {raw_output_path}"
        )

    # Save the primary SECTION_00 block path for backward compatibility
    section00_block = extract_rewrite_block(raw_output, BEGIN_MARKER, END_MARKER)
    if section00_block:
        rewrite_block_path.write_text(section00_block, encoding="utf-8")

    rerun_cmd = [args.python_command, str(workflow_dir / "analyze_logs_ver2.py")]
    rerun_proc = run_subprocess(rerun_cmd, cwd=bundle_root)
    if rerun_proc.returncode != 0:
        raise RuntimeError(f"Failed to regenerate query laws after rewrite:\n{rerun_proc.stdout}\n{rerun_proc.stderr}")
    print(rerun_proc.stdout.strip())

    latest = latest_query_laws(workflow_dir)
    if latest:
        print(f"UPDATED_QUERY_LAWS={latest}")
    print(f"PROMPT_PATH={prompt_path}")
    print(f"METADATA_PATH={metadata_path}")
    print(f"RAW_LLM_OUTPUT_PATH={raw_output_path}")
    print(f"REWRITE_BLOCK_PATH={rewrite_block_path}")


if __name__ == "__main__":
    main()
