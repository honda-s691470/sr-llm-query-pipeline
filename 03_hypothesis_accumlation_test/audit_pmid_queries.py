from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

import requests

from pipeline_common import (
    DOMAIN_LABELS,
    SOURCE_DATA_DIR,
    TEST_DATA_DIR,
    TEST_PIPELINE_DIR,
    extract_human_query_qc,
    read_json,
    scan_papers,
    source_paper_dir,
    timestamp_for_paths,
    write_json,
)


BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
RATE_LIMIT_SLEEP = 0.34


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit test/train papers for usable human `pmid_query` strings.")
    parser.add_argument("--domain", action="append", default=[], help="Restrict to one or more domain folders.")
    parser.add_argument("--skip-pubmed-check", action="store_true", help="Only check for non-empty query strings.")
    return parser.parse_args()


def validate_query(query: str, session: requests.Session) -> tuple[bool, int | None, str]:
    if not query:
        return False, None, "empty_query"

    last_error = ""
    for attempt in range(3):
        try:
            time.sleep(RATE_LIMIT_SLEEP * (attempt + 1))
            response = session.post(
                BASE_URL,
                data={"db": "pubmed", "term": query, "retmode": "json", "retmax": 0},
                timeout=30,
            )
            if response.status_code == 429:
                last_error = "pubmed_check_failed: 429 Client Error: Too Many Requests"
                continue
            response.raise_for_status()
            data = response.json()
            count = int(data.get("esearchresult", {}).get("count", "0"))
            if count == 0:
                return False, count, "zero_pubmed_hits"
            return True, count, ""
        except Exception as exc:  # pragma: no cover - network error path
            last_error = f"pubmed_check_failed: {exc}"
    return False, None, last_error or "pubmed_check_failed"


def main() -> int:
    args = parse_args()
    domain_filter = set(args.domain) if args.domain else None

    session = requests.Session()
    session.headers.update({"User-Agent": "PMIDQueryAudit/1.0"})

    rows: list[dict[str, object]] = []
    for base_dir, role in ((SOURCE_DATA_DIR, "training"), (TEST_DATA_DIR, "test")):
        for domain_folder, paper_folder in scan_papers(base_dir, domain_filter=domain_filter):
            qc = extract_human_query_qc(domain_folder, paper_folder)
            query = str(qc["executable_query"])
            if args.skip_pubmed_check:
                usable = bool(qc["query_usable"])
                hit_count = None
                note = "" if usable else ";".join(qc["issues"]) or "empty_query"
            else:
                if not qc["query_usable"]:
                    usable = False
                    hit_count = None
                    note = ";".join(qc["issues"]) or "invalid_query"
                else:
                    usable, hit_count, note = validate_query(query, session)

            rows.append(
                {
                    "domain_folder": domain_folder,
                    "domain_label": DOMAIN_LABELS.get(domain_folder, domain_folder),
                    "paper_folder": paper_folder,
                    "role": role,
                    "query_length": len(query),
                    "raw_query_length": len(str(qc["raw_query"])),
                    "query_usable": usable,
                    "pubmed_hit_count": hit_count,
                    "note": note,
                    "qc_issues": ";".join(qc["issues"]),
                    "source_input_config_detailed": str(source_paper_dir(domain_folder, paper_folder) / "input_config_detailed.json"),
                }
            )

    output_dir = TEST_PIPELINE_DIR / "plan"
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"pmid_query_audit_{timestamp_for_paths()}"
    csv_path = output_dir / f"{stem}.csv"
    json_path = output_dir / f"{stem}.json"

    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)

    write_json(
        json_path,
        {
            "generated_at": timestamp_for_paths(),
            "skip_pubmed_check": args.skip_pubmed_check,
            "rows": rows,
            "all_queries_usable": all(bool(row["query_usable"]) for row in rows),
        },
    )

    usable_count = sum(1 for row in rows if row["query_usable"])
    print(f"Audited {len(rows)} papers. Usable pmid_query count: {usable_count}/{len(rows)}")
    print(csv_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
