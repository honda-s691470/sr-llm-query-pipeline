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
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PIPELINE_DIR = ROOT / "06_exclusion_screening_pipeline"
RUN_LOGS_DIR = PIPELINE_DIR / "run_logs"


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
            capture_output=False,
        )
        if result.returncode != 0:
            print(f"ERROR: codex exec failed (exit {result.returncode})", file=sys.stderr)
            sys.exit(result.returncode)
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
