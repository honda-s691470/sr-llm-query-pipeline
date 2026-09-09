# tool_fetch_misses.py
"""
Fetch Title/Abstract/MeSH for missed PMIDs (Phase 2+ only).

- Reads last_metrics.json (must be from non-blind evaluator run).
- Random-samples missed PMIDs with reproducible seeding.
- Fetches MEDLINE records via efetch to get:
  - TI (Title)
  - AB (Abstract)
  - MH (MeSH headings) when present
- Writes missed_papers_context.txt for the agent to analyze.

Usage:
  python tool_fetch_misses.py --n 5
  python tool_fetch_misses.py --n 8 --seed 123

Notes:
- Will refuse to run if last_metrics.json does not contain missed_pmids (i.e., blind mode).
- Set NCBI_API_KEY env var if you have one.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path
from typing import Dict, List

import requests


EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
DEFAULT_TOOL = "pubmed-miss-fetch"
DEFAULT_EMAIL = ""


def _read_json(path: Path) -> Dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _ncbi_params(api_key: str | None) -> Dict[str, str]:
    params: Dict[str, str] = {"db": "pubmed", "tool": DEFAULT_TOOL}
    if DEFAULT_EMAIL:
        params["email"] = DEFAULT_EMAIL
    if api_key:
        params["api_key"] = api_key
    return params


def _request_text(
    method: str,
    url: str,
    params: Dict[str, str] | None = None,
    data: Dict[str, str] | None = None,
    timeout: int = 40,
    max_retries: int = 4,
) -> str:
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            if method.upper() == "GET":
                r = requests.get(url, params=params, timeout=timeout)
            else:
                r = requests.post(url, params=params, data=data, timeout=timeout)
            r.raise_for_status()
            return r.text
        except Exception as e:
            last_err = e
            time.sleep(0.8 * (2**attempt))
    raise RuntimeError(f"NCBI efetch failed after retries: {last_err}")


def _resolve_runtime_path(filename: str) -> Path:
    cwd_path = Path.cwd() / filename
    if cwd_path.exists():
        return cwd_path
    return Path(__file__).resolve().parent / filename


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=5, help="Number of missed PMIDs to sample.")
    ap.add_argument("--seed", type=int, default=None, help="Random seed for reproducible sampling.")
    args = ap.parse_args()

    last_metrics = _resolve_runtime_path("last_metrics.json")
    out_path = Path.cwd() / "missed_papers_context.txt"

    try:
        metrics = _read_json(last_metrics)

        missed = metrics.get("missed_pmids", None)
        if missed is None:
            raise RuntimeError(
                "last_metrics.json does not contain missed_pmids. "
                "This usually means tool_evaluator.py was run with --blind_mode. "
                "Run evaluator without --blind_mode in Phase 2+ before fetching misses."
            )

        missed = [str(x).strip() for x in missed if str(x).strip()]
        if not missed:
            print("No missed PMIDs to fetch.")
            return

        # Reproducible sampling
        if args.seed is not None:
            random.seed(args.seed)
        else:
            # Derive seed from timestamp/iteration if available, else fixed fallback
            seed_base = metrics.get("timestamp_unix", 0)
            random.seed(int(seed_base) or 42)

        n = max(1, min(args.n, len(missed)))
        targets = random.sample(missed, n)

        api_key = os.getenv("NCBI_API_KEY") or os.getenv("ENTREZ_API_KEY")
        base = _ncbi_params(api_key)

        # Use MEDLINE for MH/AB/TI when present
        payload = {
            "id": ",".join(targets),
            "retmode": "text",
            "rettype": "medline",
        }

        text_data = _request_text("POST", EFETCH_URL, params=base, data=payload)

        header = []
        header.append(f"--- Missed Papers Context (sampled) ---")
        header.append(f"Sample size: {n} / Missed count: {len(missed)}")
        header.append(f"Seed: {args.seed if args.seed is not None else metrics.get('timestamp_unix', 'NA')}")
        header.append(f"Sampled PMIDs: {', '.join(targets)}")
        header.append("")
        header.append("MEDLINE FIELDS OF INTEREST:")
        header.append("- TI: Title")
        header.append("- AB: Abstract")
        header.append("- MH: MeSH Headings")
        header.append("")
        header_text = "\n".join(header)

        out_path.write_text(header_text + "\n" + text_data, encoding="utf-8")
        print(f"Saved MEDLINE data (Title/Abstract/MeSH when available) to: {out_path.name}")
        print(f"Sampled PMIDs: {targets}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
