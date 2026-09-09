from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

import requests

from pipeline_common import TEST_DATA_DIR, normalize_query, scan_papers, test_paper_dir


BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
RATE_LIMIT_SLEEP = 1.0


def rel_test_data_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(TEST_DATA_DIR.parent.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate prepared test queries against gold PMIDs.")
    parser.add_argument("--domain", action="append", default=[], help="Restrict to one or more domain folders.")
    parser.add_argument("--paper", action="append", default=[], help="Restrict to one or more paper folders.")
    return parser.parse_args()


def fetch_pubmed_stats(query: str, gold_pmids: set[str], session: requests.Session) -> tuple[int, int, float, str]:
    if not query:
        return 0, 0, 0.0, "empty_query"

    try:
        time.sleep(RATE_LIMIT_SLEEP)
        hits_resp = session.post(BASE_URL, data={"db": "pubmed", "term": query, "retmode": "json", "retmax": 0}, timeout=30)
        hits_resp.raise_for_status()
        hits_data = hits_resp.json()
        total_hits = int(hits_data.get("esearchresult", {}).get("count", "0"))
    except Exception as exc:  # pragma: no cover - network error path
        return 0, 0, 0.0, f"hit_error: {exc}"

    if not gold_pmids:
        return total_hits, 0, 0.0, "no_gold_pmids"

    gold_query = " OR ".join(sorted(gold_pmids))
    validation_query = f"({query}) AND ({gold_query})"
    try:
        time.sleep(RATE_LIMIT_SLEEP)
        recall_resp = session.post(BASE_URL, data={"db": "pubmed", "term": validation_query, "retmode": "json", "retmax": 10000}, timeout=30)
        recall_resp.raise_for_status()
        recall_data = recall_resp.json()
        found = set(recall_data.get("esearchresult", {}).get("idlist", []))
        hit_gold = len(found)
        recall = hit_gold / len(gold_pmids)
        return total_hits, hit_gold, recall, ""
    except Exception as exc:  # pragma: no cover - network error path
        return total_hits, 0, 0.0, f"recall_error: {exc}"


def collect_queries(paper_dir: Path) -> list[dict[str, str]]:
    queries: list[dict[str, str]] = []

    human_query_path = paper_dir / "human_query.txt"
    human_qc_path = paper_dir / "human_query_qc.json"
    if human_query_path.exists():
        human_qc = {}
        if human_qc_path.exists():
            human_qc = json.loads(human_qc_path.read_text(encoding="utf-8-sig"))
        queries.append(
            {
                "provider": "human",
                "condition": "human_reference",
                "query": normalize_query(human_query_path.read_text(encoding="utf-8")),
                "source_path": rel_test_data_path(human_qc_path if human_qc_path.exists() else human_query_path),
                "raw_query_length": len(str(human_qc.get("raw_query", ""))),
                "skip_reason": "" if bool(human_qc.get("query_usable", True)) else f"invalid_human_query:{';'.join(human_qc.get('issues', []))}",
            }
        )

    model_root = paper_dir / "model_outputs"
    if model_root.exists():
        for provider_dir in sorted(model_root.iterdir()):
            if not provider_dir.is_dir():
                continue
            for condition_dir in sorted(provider_dir.iterdir()):
                result_path = condition_dir / "result.json"
                query_path = condition_dir / "normalized_query.txt"
                if result_path.exists():
                    result = json.loads(result_path.read_text(encoding="utf-8-sig"))
                    query = normalize_query(str(result.get("query", "")))
                elif query_path.exists():
                    query = normalize_query(query_path.read_text(encoding="utf-8"))
                else:
                    continue
                queries.append(
                    {
                        "provider": provider_dir.name,
                        "condition": condition_dir.name,
                        "query": query,
                        "source_path": rel_test_data_path(result_path if result_path.exists() else query_path),
                        "raw_query_length": len(query),
                        "skip_reason": "",
                    }
                )
    return queries


def main() -> int:
    args = parse_args()
    domain_filter = set(args.domain) if args.domain else None
    paper_filter = set(args.paper) if args.paper else None
    rows: list[dict[str, object]] = []
    session = requests.Session()
    session.headers.update({"User-Agent": "TestQueryEvaluator/1.0"})

    for domain_folder, paper_folder in scan_papers(TEST_DATA_DIR, domain_filter=domain_filter):
        if paper_filter and paper_folder not in paper_filter:
            continue
        paper_dir = test_paper_dir(domain_folder, paper_folder)
        if not paper_dir.exists():
            continue
        gold_data = json.loads((paper_dir / "gold_pmids.json").read_text(encoding="utf-8-sig"))
        gold_pmids = {str(pmid).strip() for pmid in gold_data.get("gold_pmids", []) if str(pmid).strip()}

        paper_rows: list[dict[str, object]] = []
        for query_info in collect_queries(paper_dir):
            skip_reason = str(query_info.get("skip_reason", ""))
            if skip_reason:
                total_hits, hit_gold, recall, error_note = 0, 0, 0.0, skip_reason
                status = "SKIPPED"
            else:
                total_hits, hit_gold, recall, error_note = fetch_pubmed_stats(query_info["query"], gold_pmids, session)
                status = "OK" if not error_note else "ERROR"
            row = {
                "domain_folder": domain_folder,
                "paper_folder": paper_folder,
                "provider": query_info["provider"],
                "condition": query_info["condition"],
                "method_label": f"{query_info['provider']}::{query_info['condition']}",
                "query_length": len(query_info["query"]),
                "raw_query_length": int(query_info.get("raw_query_length", len(query_info["query"]))),
                "total_hits": total_hits,
                "hit_gold_count": hit_gold,
                "gold_count": len(gold_pmids),
                "recall": recall,
                "status": status,
                "error_note": error_note,
                "source_path": query_info["source_path"],
            }
            rows.append(row)
            paper_rows.append(row)

        if paper_rows:
            per_paper_csv = paper_dir / "metrics_summary.csv"
            with per_paper_csv.open("w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(paper_rows[0].keys()))
                writer.writeheader()
                writer.writerows(paper_rows)

    results_dir = TEST_DATA_DIR / "_results"
    results_dir.mkdir(parents=True, exist_ok=True)
    all_csv = results_dir / "all_test_metrics.csv"
    if rows:
        with all_csv.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    print(all_csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
