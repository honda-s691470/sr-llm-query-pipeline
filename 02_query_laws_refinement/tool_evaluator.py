"""
Evaluation-only PubMed query evaluator for query-laws refinement.

This variant is intended for use from public_release/02_query_laws_refinement and avoids
overwriting hypothesis-accumulation artifacts under public_release/04_data by allowing all
runtime paths to be specified explicitly.

Usage example:
  python tool_evaluator.py ^
    --input-config public_release/04_data/02_Cardiovascular_Disease/41522206_2026/input_config.json ^
    --query-path public_release/04_data/02_Cardiovascular_Disease/41522206_2026/model_outputs/codex/with_laws_v14_training_eval/normalized_query.txt ^
    --metrics-path public_release/04_data/02_Cardiovascular_Disease/41522206_2026/model_outputs/codex/with_laws_v14_training_eval/last_metrics.json
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Set, Tuple

import requests


ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
DEFAULT_TOOL = "pubmed-query-coverage"
DEFAULT_EMAIL = ""


def _read_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    return path.read_text(encoding="utf-8-sig").strip()


def _read_json(path: Path) -> Dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, obj: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


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
            time.sleep(0.8 * (2**attempt))
    raise RuntimeError(f"NCBI request failed after retries: {last_err}")


def get_total_hits(query: str, api_key: str | None) -> int:
    params = {**_ncbi_params(api_key), "term": query, "retmax": "0"}
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
    gold_set: Set[str] = set(gold_pmids)
    found: Set[str] = set()
    base = _ncbi_params(api_key)

    if not gold_pmids:
        return set(), set()

    for batch in _chunk(gold_pmids, chunk_size):
        id_clause = " OR ".join([f"{pmid}[uid]" for pmid in batch])
        validation_query = f"({query}) AND ({id_clause})"
        data = _request_json(
            "POST",
            ESEARCH_URL,
            params=base,
            data={"term": validation_query, "retmax": "100000"},
        )
        try:
            for pmid in data["esearchresult"].get("idlist", []):
                found.add(_normalize_pmid(pmid))
        except Exception:
            raise RuntimeError(f"Unexpected esearch response (validation): {data}")
        time.sleep(polite_sleep_sec)

    missed = gold_set - found
    return found, missed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-config", required=True, help="Path to input_config.json")
    ap.add_argument("--query-path", required=True, help="Path to normalized_query.txt or current_query.txt")
    ap.add_argument("--metrics-path", required=True, help="Path to write last_metrics.json")
    ap.add_argument("--blind_mode", action="store_true", help="Do not save/show missed PMIDs")
    ap.add_argument("--chunk_size", type=int, default=80, help="Gold PMID OR-batch size")
    args = ap.parse_args()

    input_config = Path(args.input_config)
    query_path = Path(args.query_path)
    metrics_path = Path(args.metrics_path)

    config = _read_json(input_config)
    gold_pmids = [_normalize_pmid(p) for p in config.get("gold_pmids", []) if str(p).strip()]
    query = _read_text(query_path)
    if not query:
        raise ValueError(f"Query file is empty: {query_path}")

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

    metrics: Dict = {
        "query": query,
        "query_path": str(query_path),
        "input_config_path": str(input_config),
        "total_hits": total_hits,
        "recall": recall,
        "found_count": found_count,
        "total_gold": total_gold,
        "mode": "blind" if args.blind_mode else "open",
        "timestamp_unix": int(time.time()),
    }

    if args.blind_mode:
        metrics["missed_count"] = len(missed_pmids)
    else:
        metrics["missed_pmids"] = sorted(missed_pmids)
        metrics["found_pmids"] = sorted(found_pmids)
        metrics["missed_count"] = len(missed_pmids)

    _write_json(metrics_path, metrics)

    if args.blind_mode:
        print(json.dumps({"status": "success", "recall": recall, "total_hits": total_hits, "missed_count": len(missed_pmids)}, indent=2))
    else:
        print(json.dumps({"status": "success", "recall": recall, "total_hits": total_hits, "found_count": found_count, "total_gold": total_gold}, indent=2))


if __name__ == "__main__":
    main()
