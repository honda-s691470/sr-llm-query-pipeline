# tool_evaluator.py
"""
Robust PubMed query evaluator with leakage-safe blind mode.

- Computes:
  - total_hits: via esearch count-only (retmax=0)
  - recall: via checking gold PMIDs against the query (batched OR of <pmid>[uid])
- Writes last_metrics.json for downstream tools.
- IMPORTANT (Leakage prevention):
  - If --blind_mode is set, missed_pmids / found_pmids are NOT written to last_metrics.json.

Usage:
  python tool_evaluator.py --blind_mode
  python tool_evaluator.py                 # non-blind (Phase 2+)
Optional:
  export NCBI_API_KEY="..."
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Set, Tuple

import requests


ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
DEFAULT_TOOL = "pubmed-query-coverage"
DEFAULT_EMAIL = ""  # optionally set for NCBI etiquette


def _read_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    return path.read_text(encoding="utf-8-sig").strip()


def _read_json(path: Path) -> Dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, obj: Dict) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _resolve_runtime_path(filename: str) -> Path:
    cwd_path = Path.cwd() / filename
    if cwd_path.exists():
        return cwd_path
    return Path(__file__).resolve().parent / filename


def _normalize_pmid(p: str) -> str:
    return str(p).strip()


def _chunk(lst: List[str], size: int) -> List[List[str]]:
    return [lst[i : i + size] for i in range(0, len(lst), size)]


def _ncbi_params(api_key: str | None) -> Dict[str, str]:
    params: Dict[str, str] = {"db": "pubmed", "retmode": "json", "tool": DEFAULT_TOOL}
    if DEFAULT_EMAIL:
        params["email"] = DEFAULT_EMAIL
    if api_key:
        params["api_key"] = api_key
    return params


def _request_json(
    method: str,
    url: str,
    params: Dict[str, str] | None = None,
    data: Dict[str, str] | None = None,
    timeout: int = 30,
    max_retries: int = 4,
) -> Dict:
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            if method.upper() == "GET":
                r = requests.get(url, params=params, timeout=timeout)
            else:
                r = requests.post(url, params=params, data=data, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_err = e
            # backoff
            time.sleep(0.8 * (2**attempt))
    raise RuntimeError(f"NCBI request failed after retries: {last_err}")


def get_total_hits(query: str, api_key: str | None) -> int:
    base = _ncbi_params(api_key)
    # count-only request
    params = {**base, "term": query, "retmax": "0"}
    data = _request_json("GET", ESEARCH_URL, params=params)
    try:
        return int(data["esearchresult"]["count"])
    except Exception:
        raise RuntimeError(f"Unexpected esearch response (count): {data}")


def check_gold_pmids_batched(
    query: str,
    gold_pmids: List[str],
    api_key: str | None,
    chunk_size: int = 80,
    polite_sleep_sec: float = 0.34,
) -> Tuple[Set[str], Set[str]]:
    """
    Returns (found_pmids, missed_pmids) for gold set.
    Uses batched OR queries with [uid] to avoid retmax issues.
    """
    gold_set: Set[str] = set(gold_pmids)
    found: Set[str] = set()

    base = _ncbi_params(api_key)

    # If gold list is empty, shortcut
    if not gold_pmids:
        return set(), set()

    for batch in _chunk(gold_pmids, chunk_size):
        # Build "(pmid1[uid] OR pmid2[uid] ...)"
        id_clause = " OR ".join([f"{pmid}[uid]" for pmid in batch])
        # AND with user query
        validation_query = f"({query}) AND ({id_clause})"

        # POST is safer for long terms
        data = _request_json(
            "POST",
            ESEARCH_URL,
            params=base,
            data={"term": validation_query, "retmax": "100000"},
        )

        try:
            idlist = data["esearchresult"].get("idlist", [])
            # idlist are PMIDs as strings
            for pmid in idlist:
                found.add(_normalize_pmid(pmid))
        except Exception:
            raise RuntimeError(f"Unexpected esearch response (validation): {data}")

        time.sleep(polite_sleep_sec)

    missed = gold_set - found
    return found, missed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--blind_mode", action="store_true", help="Do not save/show missed PMIDs (prevents leakage).")
    ap.add_argument("--chunk_size", type=int, default=80, help="Gold PMID OR-batch size (smaller if term too long).")
    args = ap.parse_args()

    input_config = _resolve_runtime_path("input_config.json")
    current_query = _resolve_runtime_path("current_query.txt")
    last_metrics = Path.cwd() / "last_metrics.json"

    try:
        config = _read_json(input_config)
        gold_pmids = [_normalize_pmid(p) for p in config.get("gold_pmids", []) if str(p).strip()]
        query = _read_text(current_query)

        if not query:
            raise ValueError("current_query.txt is empty.")

        api_key = os.getenv("NCBI_API_KEY") or os.getenv("ENTREZ_API_KEY")

        total_hits = get_total_hits(query, api_key)

        found_pmids, missed_pmids = check_gold_pmids_batched(
            query=query,
            gold_pmids=gold_pmids,
            api_key=api_key,
            chunk_size=max(10, args.chunk_size),
        )

        total_gold = len(gold_pmids)
        found_count = len(found_pmids)
        recall = (found_count / total_gold) if total_gold > 0 else 0.0

        # Leakage-safe metrics
        metrics: Dict = {
            "query": query,
            "total_hits": total_hits,
            "recall": recall,
            "found_count": found_count,
            "total_gold": total_gold,
            "mode": "blind" if args.blind_mode else "open",
            "timestamp_unix": int(time.time()),
        }

        if args.blind_mode:
            metrics["missed_count"] = len(missed_pmids)
            # DO NOT WRITE missed_pmids / found_pmids in blind mode
        else:
            metrics["missed_pmids"] = sorted(missed_pmids)
            metrics["found_pmids"] = sorted(found_pmids)
            metrics["missed_count"] = len(missed_pmids)

        _write_json(last_metrics, metrics)

        # Console output (safe)
        if args.blind_mode:
            print(f"Recall: {recall:.2%} (Missed: {len(missed_pmids)}) [BLIND MODE]")
            print(json.dumps({"status": "success", "recall": recall, "total_hits": total_hits, "missed_count": len(missed_pmids)}, indent=2))
        else:
            sample = sorted(missed_pmids)[:5]
            print(f"Recall: {recall:.2%} (Missed: {len(missed_pmids)})")
            print(json.dumps({"status": "success", "recall": recall, "total_hits": total_hits, "missed_count": len(missed_pmids), "missed_pmids_sample": sample}, indent=2))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
