from __future__ import annotations

import argparse
import csv
from pathlib import Path

import requests

from eval_test import fetch_pubmed_stats, load_gold_pmids, safe_metric_value
from pipeline_common import (
    TEST_DATA_DIR,
    normalize_query,
    scan_papers,
    timestamp_for_paths,
    utc_timestamp,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Score already-generated normalized_query.txt files (e.g. from subagent-based "
        "generation) using the same recall/hits logic as eval_test.py, without invoking any provider CLI."
    )
    parser.add_argument("--provider", required=True, help="Provider label used in the output directory, e.g. claude.")
    parser.add_argument("--model", required=True, help="Model label to record in result.json/summary CSV.")
    parser.add_argument("--output-condition", required=True, help="Output condition directory name, e.g. with_laws_run2_rb_test_eval.")
    parser.add_argument("--domain", action="append", default=[], help="Restrict to one or more domain folders.")
    parser.add_argument("--paper", action="append", default=[], help="Restrict to one or more paper folders.")
    parser.add_argument("--pubmed-timeout-seconds", type=int, default=45)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    domain_filter = set(args.domain) if args.domain else None
    paper_filter = set(args.paper) if args.paper else None

    results_dir = TEST_DATA_DIR / "_results"
    run_stamp = timestamp_for_paths()
    summary_rows: list[dict[str, object]] = []

    session = requests.Session()
    session.headers.update({"User-Agent": f"ScoreExistingQueries/{args.provider}/1.0"})

    for domain_folder, paper_folder in scan_papers(TEST_DATA_DIR, domain_filter=domain_filter):
        if paper_filter and paper_folder not in paper_filter:
            continue
        paper_dir = TEST_DATA_DIR / domain_folder / paper_folder
        output_dir = paper_dir / "model_outputs" / args.provider / args.output_condition
        query_path = output_dir / "normalized_query.txt"

        result_record: dict[str, object] = {
            "generated_at": utc_timestamp(),
            "domain_folder": domain_folder,
            "paper_folder": paper_folder,
            "provider": args.provider,
            "model": args.model,
            "condition": args.output_condition,
        }

        if not query_path.exists():
            result_record.update(
                {
                    "status": "missing_normalized_query",
                    "query": "",
                    "query_length": 0,
                    "gold_count": len(load_gold_pmids(paper_dir)),
                    "total_hits": 0,
                    "hit_gold_count": 0,
                    "recall": 0.0,
                    "nnr": None,
                    "f1": 0.0,
                    "error_note": "missing_normalized_query",
                }
            )
            summary_rows.append(result_record)
            continue

        extracted_query = normalize_query(query_path.read_text(encoding="utf-8"))
        gold_pmids = load_gold_pmids(paper_dir)

        if extracted_query:
            total_hits, hit_gold, recall, nnr, f1, error_note = fetch_pubmed_stats(
                extracted_query, gold_pmids, session, args.pubmed_timeout_seconds
            )
            status = "completed" if not error_note else "eval_error"
        else:
            total_hits, hit_gold, recall, nnr, f1, error_note = 0, 0, 0.0, 0.0, 0.0, "no_query_extracted"
            status = "completed_no_query"

        result_payload = {
            **result_record,
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
        print(f"{domain_folder}/{paper_folder}: status={status} recall={recall:.3f} hits={total_hits}")

    results_dir.mkdir(parents=True, exist_ok=True)
    safe_model = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in args.model)
    summary_csv = results_dir / f"score_existing_{args.provider}_{safe_model}_{run_stamp}.csv"
    if summary_rows:
        with summary_csv.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0].keys()))
            writer.writeheader()
            writer.writerows(summary_rows)

    print(summary_csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
