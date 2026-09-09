"""
Orchestrate one iteration of the Stage A' self-refinement loop.

Steps:
  1. analyze_aprime_logs.py     → aprime_laws_verN.json
  2. generate_aprime_rewrite_input.py → run_logs/aprime_rewrite_prompt_{ts}.md
  3. Call LLM (codex / claude) with the prompt
  4. rewrite_aprime_blocks.py   → patch 4 target files

Usage:
  python auto_rewrite_aprime.py --iteration 1 [--model gpt-5.3-codex] [--dry-run]
"""
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

ROOT = Path(__file__).resolve().parent.parent
PIPELINE_DIR = ROOT / "06_exclusion_screening_pipeline"
RUN_LOGS_DIR = PIPELINE_DIR / "run_logs"



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
    for dotenv_path in (ROOT.parent / ".env", ROOT / ".env"):
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


def call_openai_responses_api(prompt_text: str, *, model: str, max_output_tokens: int = 8096) -> str:
    api_key = load_openai_api_key()
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


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=False, text=True)
    if check and result.returncode != 0:
        print(f"ERROR: command failed (exit {result.returncode})", file=sys.stderr)
        sys.exit(result.returncode)
    return result


def _capture(cmd: list[str]) -> str:
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)
    return result.stdout.strip()


def _extract_path(output: str, key: str) -> str | None:
    m = re.search(rf"{re.escape(key)}=(\S+)", output)
    return m.group(1) if m else None


def _call_llm(prompt_path: Path, model: str) -> Path:
    """Call the configured rewrite LLM and save the raw response to a file."""
    from datetime import datetime

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    response_path = RUN_LOGS_DIR / f"aprime_rewrite_prompt_response_{ts}.md"
    prompt_text = prompt_path.read_text(encoding="utf-8")
    lowered = model.lower()

    if "claude" in lowered:
        import anthropic

        client = anthropic.Anthropic()
        message = client.messages.create(
            model=model,
            max_tokens=8096,
            messages=[{"role": "user", "content": prompt_text}],
        )
        response_text = message.content[0].text
        response_path.write_text(response_text, encoding="utf-8")
        return response_path

    if "codex" in lowered or lowered.startswith("gpt-"):
        cmd = [
            "codex",
            "exec",
            "--skip-git-repo-check",
            "-s",
            "danger-full-access",
            "-C",
            str(ROOT),
            "-m",
            model,
            "-o",
            str(response_path),
            "-",
        ]
        print(f"  $ {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            input=prompt_text,
            text=True,
            encoding="utf-8",
            capture_output=True,
        )
        if result.returncode != 0:
            fallback_log = RUN_LOGS_DIR / f"aprime_rewrite_api_fallback_{ts}.log"
            try:
                response_text = call_openai_responses_api(prompt_text, model=model)
            except Exception as exc:
                fallback_log.write_text(
                    f"codex_cli_returncode={result.returncode}\nSTDOUT:\n{result.stdout or ''}\nSTDERR:\n{result.stderr or ''}\nAPI_ERROR:\n{exc}\n",
                    encoding="utf-8",
                )
                print(f"ERROR: codex exec failed and API fallback failed: {exc}", file=sys.stderr)
                sys.exit(result.returncode)
            response_path.write_text(response_text, encoding="utf-8")
            fallback_log.write_text(
                f"codex_cli_returncode={result.returncode}\nmodel={model}\n",
                encoding="utf-8",
            )
            return response_path
        if result.stdout and not response_path.exists():
            response_path.write_text(result.stdout, encoding="utf-8")
        return response_path

    print(f"ERROR: unsupported rewrite model '{model}'", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iteration", type=int, default=1)
    parser.add_argument("--model", default="gpt-5.3-codex",
                        help="Rewrite model ID for prompt-driven A' updates")
    parser.add_argument("--skip-analyze", action="store_true",
                        help="Skip analyze_aprime_logs.py (already run by orchestrator)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    RUN_LOGS_DIR.mkdir(parents=True, exist_ok=True)

    python = sys.executable

    print(f"\n[auto_rewrite_aprime] iteration={args.iteration}")

    # Step 1: compute scores (skipped when orchestrator already ran analyze_aprime_logs)
    if not args.skip_analyze:
        print("\n--- Step 1: analyze_aprime_logs ---")
        _run([python, str(PIPELINE_DIR / "analyze_aprime_logs.py")])
    else:
        print("\n--- Step 1: analyze_aprime_logs (skipped - already run by orchestrator) ---")

    # Step 2: generate rewrite prompt
    print("\n--- Step 2: generate_aprime_rewrite_input ---")
    out = _capture([python, str(PIPELINE_DIR / "generate_aprime_rewrite_input.py"),
                    "--iteration", str(args.iteration)])
    prompt_path_str = _extract_path(out, "PROMPT_PATH")
    if not prompt_path_str:
        print("ERROR: PROMPT_PATH not found in generate_aprime_rewrite_input output", file=sys.stderr)
        sys.exit(1)
    prompt_path = Path(prompt_path_str)
    print(f"  Prompt → {prompt_path}")

    if args.dry_run:
        print("\nDRY RUN - stopping before LLM call.")
        print(f"  Review prompt: {prompt_path}")
        return

    # Step 3: call LLM
    print(f"\n--- Step 3: call LLM ({args.model}) ---")
    response_path = _call_llm(prompt_path, args.model)
    print(f"  Response → {response_path}")

    # Step 4: apply rewrites
    print("\n--- Step 4: rewrite_aprime_blocks ---")
    _run([python, str(PIPELINE_DIR / "rewrite_aprime_blocks.py"),
          "--response", str(response_path)])

    print(f"\n[auto_rewrite_aprime] iteration={args.iteration} complete ({args.model}).")


if __name__ == "__main__":
    main()
