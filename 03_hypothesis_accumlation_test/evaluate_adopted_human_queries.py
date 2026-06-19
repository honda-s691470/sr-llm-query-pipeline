from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path
from typing import Any

import requests

from pipeline_common import (
    DOMAIN_LABELS,
    SOURCE_DATA_DIR,
    TEST_DATA_DIR,
    extract_gold_pmids,
    extract_human_query_qc,
    load_source_input_config_detailed,
    scan_papers,
    timestamp_for_paths,
    write_json,
)


BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
RATE_LIMIT_SLEEP = 0.34
PLAN_DIR = Path(__file__).resolve().parent / "plan"
TEST_RESULTS_CSV = Path(__file__).resolve().parent.parent / "05_test_data" / "_results" / "all_test_metrics.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate adopted papers' human PubMed queries against source gold PMIDs.")
    parser.add_argument("--domain", action="append", default=[], help="Restrict to one or more domain folders.")
    return parser.parse_args()


def load_adopted_rows() -> list[dict[str, Any]]:
    rows = [{"domain_folder": d, "paper_folder": p} for d, p in scan_papers(SOURCE_DATA_DIR)]
    rows += [{"domain_folder": d, "paper_folder": p} for d, p in scan_papers(TEST_DATA_DIR)]
    rows.sort(key=lambda row: (row["domain_folder"], row["paper_folder"]))
    return rows


def build_role_lookup() -> dict[tuple[str, str], str]:
    lookup: dict[tuple[str, str], str] = {}
    for domain_folder, paper_folder in scan_papers(SOURCE_DATA_DIR):
        lookup[(domain_folder, paper_folder)] = "training"
    for domain_folder, paper_folder in scan_papers(TEST_DATA_DIR):
        lookup[(domain_folder, paper_folder)] = "test"
    return lookup


def load_existing_cvd_human_metrics() -> dict[tuple[str, str], dict[str, Any]]:
    if not TEST_RESULTS_CSV.exists():
        return {}
    with TEST_RESULTS_CSV.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [row for row in reader if row.get("provider") == "human" and row.get("condition") == "human_reference"]
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        if row.get("domain_folder") != "02_Cardiovascular_Disease":
            continue
        out[(row["domain_folder"], row["paper_folder"])] = row
    return out


def fetch_pubmed_stats(query: str, gold_pmids: set[str], session: requests.Session) -> tuple[int, int, float, str]:
    if not query:
        return 0, 0, 0.0, "empty_query"

    last_error = ""
    for attempt in range(3):
        try:
            time.sleep(RATE_LIMIT_SLEEP * (attempt + 1))
            hits_resp = session.post(BASE_URL, data={"db": "pubmed", "term": query, "retmode": "json", "retmax": 0}, timeout=60)
            if hits_resp.status_code == 429:
                last_error = "hit_error: 429 Too Many Requests"
                continue
            hits_resp.raise_for_status()
            hits_data = hits_resp.json()
            total_hits = int(hits_data.get("esearchresult", {}).get("count", "0"))
            break
        except Exception as exc:  # pragma: no cover - network error path
            last_error = f"hit_error: {exc}"
    else:
        return 0, 0, 0.0, last_error or "hit_error"

    if not gold_pmids:
        return total_hits, 0, 0.0, "no_gold_pmids"

    gold_query = " OR ".join(sorted(gold_pmids))
    validation_query = f"({query}) AND ({gold_query})"
    last_error = ""
    for attempt in range(3):
        try:
            time.sleep(RATE_LIMIT_SLEEP * (attempt + 1))
            recall_resp = session.post(
                BASE_URL,
                data={"db": "pubmed", "term": validation_query, "retmode": "json", "retmax": 10000},
                timeout=60,
            )
            if recall_resp.status_code == 429:
                last_error = "recall_error: 429 Too Many Requests"
                continue
            recall_resp.raise_for_status()
            recall_data = recall_resp.json()
            found = set(recall_data.get("esearchresult", {}).get("idlist", []))
            hit_gold = len(found)
            recall = hit_gold / len(gold_pmids)
            return total_hits, hit_gold, recall, ""
        except Exception as exc:  # pragma: no cover - network error path
            last_error = f"recall_error: {exc}"
    return total_hits, 0, 0.0, last_error or "recall_error"


def render_markdown(rows: list[dict[str, Any]]) -> str:
    headers = [
        "Domain",
        "Paper",
        "Role",
        "Source",
        "Usable",
        "Hits",
        "Found",
        "Gold",
        "Recall",
        "Status",
        "Note",
    ]
    lines = ["# Adopted Papers Human Query Recall Audit", "", "| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["domain_folder"]),
                    str(row["paper_folder"]),
                    str(row["role"]),
                    str(row["query_source_field"]),
                    "Y" if row["query_usable"] else "N",
                    str(row["total_hits"]),
                    str(row["hit_gold_count"]),
                    str(row["gold_count"]),
                    f"{float(row['recall']):.4f}",
                    str(row["status"]),
                    str(row["error_note"]).replace("|", "/"),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    domain_filter = set(args.domain) if args.domain else None

    adopted_rows = [row for row in load_adopted_rows() if not domain_filter or row["domain_folder"] in domain_filter]
    existing_cvd = load_existing_cvd_human_metrics()
    role_lookup = build_role_lookup()

    session = requests.Session()
    session.headers.update({"User-Agent": "AdoptedHumanQueryAudit/1.0"})

    results: list[dict[str, Any]] = []
    for row in adopted_rows:
        domain_folder = row["domain_folder"]
        paper_folder = row["paper_folder"]
        source_dir = SOURCE_DATA_DIR / domain_folder / paper_folder
        detailed = load_source_input_config_detailed(domain_folder, paper_folder)
        qc = extract_human_query_qc(domain_folder, paper_folder)
        gold_pmids = set(extract_gold_pmids(domain_folder, paper_folder))

        existing = existing_cvd.get((domain_folder, paper_folder))
        if existing:
            results.append(
                {
                    "domain_folder": domain_folder,
                    "domain_label": DOMAIN_LABELS.get(domain_folder, domain_folder),
                    "paper_folder": paper_folder,
                    "role": role_lookup.get((domain_folder, paper_folder), ""),
                    "query_source_field": existing.get("source_path", "existing_cvd_metric"),
                    "query_usable": existing.get("status") == "OK",
                    "query_length": int(existing.get("query_length", 0) or 0),
                    "raw_query_length": int(existing.get("raw_query_length", 0) or 0),
                    "total_hits": int(existing.get("total_hits", 0) or 0),
                    "hit_gold_count": int(existing.get("hit_gold_count", 0) or 0),
                    "gold_count": int(existing.get("gold_count", 0) or 0),
                    "recall": float(existing.get("recall", 0) or 0),
                    "status": existing.get("status", ""),
                    "error_note": existing.get("error_note", ""),
                    "qc_issues": "",
                    "source_input_config_detailed": str(source_dir / "input_config_detailed.json"),
                    "pmid_query_preview": str(detailed.get("pmid_query", ""))[:200],
                    "reused_existing_cvd_result": True,
                }
            )
            continue

        query = str(qc["executable_query"])
        if not qc["query_usable"]:
            total_hits, hit_gold, recall, error_note = 0, 0, 0.0, "invalid_human_query:" + ";".join(qc["issues"])
            status = "SKIPPED"
        else:
            total_hits, hit_gold, recall, error_note = fetch_pubmed_stats(query, gold_pmids, session)
            status = "OK" if not error_note else "ERROR"

        results.append(
            {
                "domain_folder": domain_folder,
                "domain_label": DOMAIN_LABELS.get(domain_folder, domain_folder),
                "paper_folder": paper_folder,
                "role": role_lookup.get((domain_folder, paper_folder), ""),
                "query_source_field": qc.get("query_source_field", "pmid_query"),
                "query_usable": bool(qc["query_usable"]),
                "query_length": len(query),
                "raw_query_length": len(str(qc.get("raw_query", ""))),
                "total_hits": total_hits,
                "hit_gold_count": hit_gold,
                "gold_count": len(gold_pmids),
                "recall": recall,
                "status": status,
                "error_note": error_note,
                "qc_issues": ";".join(qc.get("issues", [])),
                "source_input_config_detailed": str(source_dir / "input_config_detailed.json"),
                "pmid_query_preview": str(detailed.get("pmid_query", ""))[:200],
                "reused_existing_cvd_result": False,
            }
        )

    PLAN_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"adopted_human_query_recall_{timestamp_for_paths()}"
    csv_path = PLAN_DIR / f"{stem}.csv"
    md_path = PLAN_DIR / f"{stem}.md"
    json_path = PLAN_DIR / f"{stem}.json"

    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0].keys()) if results else [])
        writer.writeheader()
        writer.writerows(results)

    md_path.write_text(render_markdown(results), encoding="utf-8")
    write_json(
        json_path,
        {
            "generated_at": timestamp_for_paths(),
            "results": results,
            "zero_hit_papers": [row for row in results if int(row["total_hits"]) == 0],
            "skipped_papers": [row for row in results if row["status"] == "SKIPPED"],
        },
    )

    print(csv_path)
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
