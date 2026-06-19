from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def parse_version(name: str) -> int:
    stem = Path(name).stem
    if "query_laws_ver" in stem:
        return int(stem.split("query_laws_ver", 1)[1])
    raise ValueError(f"Could not parse query law version from {name}")


def summarize_actions(search_history_path: Path) -> Dict[str, List[Dict[str, Any]]]:
    positive = Counter()
    regression = Counter()
    positive_pairs = Counter()
    regression_pairs = Counter()

    if not search_history_path.exists():
        return {
            "top_positive_action_types": [],
            "top_regression_action_types": [],
            "top_positive_action_pairs": [],
            "top_regression_action_pairs": [],
        }

    for line in search_history_path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        action_type = row.get("action_type", "UNKNOWN")
        concept_category = row.get("concept_category", "UNKNOWN")
        pair = f"{action_type} :: {concept_category}"
        label = row.get("result_label", "")
        delta_recall = float(row.get("delta_recall", 0.0) or 0.0)
        if "Regression" in label or delta_recall < 0:
            regression[action_type] += 1
            regression_pairs[pair] += 1
        elif delta_recall > 0:
            positive[action_type] += 1
            positive_pairs[pair] += 1

    def to_rows(counter: Counter, limit: int = 5) -> List[Dict[str, Any]]:
        return [{"name": k, "count": v} for k, v in counter.most_common(limit)]

    return {
        "top_positive_action_types": to_rows(positive),
        "top_regression_action_types": to_rows(regression),
        "top_positive_action_pairs": to_rows(positive_pairs),
        "top_regression_action_pairs": to_rows(regression_pairs),
    }


def short_list(items: Iterable[str], limit: int = 10) -> List[str]:
    rows = list(items)
    return rows[:limit]


def infer_failure_mode(
    recall: float,
    total_hits: int,
    missed_count: int,
    previous_recall: float | None,
    delta_vs_previous: float | None,
) -> str:
    if missed_count == 0:
        return "No recall failure detected."
    if previous_recall is not None and delta_vs_previous is not None and delta_vs_previous < -0.05:
        return "Large regression vs previous law version; inspect newly introduced constraints first."
    if total_hits <= 500:
        return "Likely over-restrictive query blocks or filters; inspect mandatory AND blocks and restrictive filters."
    if recall < 0.60:
        return "Likely missing concept coverage; inspect missed PMIDs for absent MeSH terms, synonyms, or alternate intervention names."
    return "Partial miss with moderate recall; compare missed PMIDs against current concept blocks and check whether any block is too specific."


def render_markdown_row(d: Dict[str, Any]) -> str:
    prev = "NA" if d["previous_recall"] is None else f'{d["previous_recall"]:.3f}'
    delta = "NA" if d["delta_recall_vs_previous"] is None else f'{d["delta_recall_vs_previous"]:+.3f}'
    return (
        f"| {d['sr_path']} | {d['recall']:.3f} | {prev} | {delta} | "
        f"{d['total_hits']} | {d['missed_count']} | {d['needs_review']} |"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle-root", required=True)
    ap.add_argument("--summary-path", required=True)
    ap.add_argument("--query-laws-file", required=True)
    ap.add_argument("--low-recall-threshold", type=float, default=0.60)
    ap.add_argument("--delta-threshold", type=float, default=0.05)
    args = ap.parse_args()

    bundle_root = Path(args.bundle_root).resolve()
    summary_path = Path(args.summary_path).resolve()
    query_laws_file = Path(args.query_laws_file).resolve()
    workflow_dir = bundle_root / "02_query_laws_refinement"
    run_logs_dir = workflow_dir / "run_logs"
    version = parse_version(query_laws_file.name)
    summary = read_json(summary_path)

    diagnostics: List[Dict[str, Any]] = []

    for row in summary:
        sr_rel = row["path"].replace("/", "\\")
        sr_dir = bundle_root / Path(sr_rel)
        out_dir = sr_dir / "model_outputs" / "codex" / f"with_laws_v{version}_training_eval"
        metrics_path = out_dir / "last_metrics.json"
        query_path = out_dir / "normalized_query.txt"
        input_config_path = sr_dir / "input_config.json"
        search_history_path = sr_dir / "search_history.jsonl"

        metrics = read_json(metrics_path)
        input_config = read_json(input_config_path)

        previous_recall = None
        delta_vs_previous = None
        previous_metrics_path = None
        if version > 1:
            candidate = sr_dir / "model_outputs" / "codex" / f"with_laws_v{version - 1}_training_eval" / "last_metrics.json"
            if candidate.exists():
                previous_metrics = read_json(candidate)
                previous_recall = float(previous_metrics.get("recall", 0.0))
                delta_vs_previous = float(metrics["recall"]) - previous_recall
                previous_metrics_path = candidate

        missed_pmids = metrics.get("missed_pmids", [])
        found_pmids = metrics.get("found_pmids", [])
        missed_count = int(metrics.get("missed_count", len(missed_pmids)))
        needs_review = bool(
            float(metrics["recall"]) < args.low_recall_threshold
            or (delta_vs_previous is not None and abs(delta_vs_previous) > args.delta_threshold)
        )

        action_summary = summarize_actions(search_history_path)
        diagnosis = {
            "sr_path": row["path"],
            "query_laws_file": query_laws_file.name,
            "version": version,
            "recall": float(metrics["recall"]),
            "previous_recall": previous_recall,
            "delta_recall_vs_previous": delta_vs_previous,
            "total_hits": int(metrics["total_hits"]),
            "found_count": int(metrics["found_count"]),
            "total_gold": int(metrics["total_gold"]),
            "missed_count": missed_count,
            "needs_review": needs_review,
            "failure_mode_hint": infer_failure_mode(
                recall=float(metrics["recall"]),
                total_hits=int(metrics["total_hits"]),
                missed_count=missed_count,
                previous_recall=previous_recall,
                delta_vs_previous=delta_vs_previous,
            ),
            "normalized_query_path": str(query_path.relative_to(bundle_root)).replace("\\", "/"),
            "metrics_path": str(metrics_path.relative_to(bundle_root)).replace("\\", "/"),
            "previous_metrics_path": None if previous_metrics_path is None else str(previous_metrics_path.relative_to(bundle_root)).replace("\\", "/"),
            "search_history_path": str(search_history_path.relative_to(bundle_root)).replace("\\", "/"),
            "gold_pmids": input_config.get("gold_pmids", []),
            "found_pmids": found_pmids,
            "missed_pmids": missed_pmids,
            "query": metrics.get("query", read_text(query_path).strip()),
            "action_summary": action_summary,
        }
        diagnostics.append(diagnosis)

        per_sr_path = out_dir / "step3_diagnosis.md"
        lines = [
            f"# Step 3 Diagnosis: {row['path']}",
            "",
            f"- query_laws: `{query_laws_file.name}`",
            f"- recall: `{diagnosis['recall']:.3f}`",
            f"- previous_recall: `{diagnosis['previous_recall'] if diagnosis['previous_recall'] is not None else 'NA'}`",
            f"- delta_recall_vs_previous: `{diagnosis['delta_recall_vs_previous'] if diagnosis['delta_recall_vs_previous'] is not None else 'NA'}`",
            f"- total_hits: `{diagnosis['total_hits']}`",
            f"- missed_count: `{diagnosis['missed_count']}`",
            f"- needs_review: `{diagnosis['needs_review']}`",
            "",
            "## Failure mode hint",
            "",
            diagnosis["failure_mode_hint"],
            "",
            "## Query",
            "",
            "```text",
            diagnosis["query"],
            "```",
            "",
            "## Missed PMIDs",
            "",
            "```text",
            "\n".join(short_list(diagnosis["missed_pmids"], limit=50)) or "(none)",
            "```",
            "",
            "## Found PMIDs",
            "",
            "```text",
            "\n".join(short_list(diagnosis["found_pmids"], limit=50)) or "(none)",
            "```",
            "",
            "## Search-history cross-reference",
            "",
            f"- search_history: `{diagnosis['search_history_path']}`",
            f"- top_positive_action_types: {json.dumps(diagnosis['action_summary']['top_positive_action_types'], ensure_ascii=False)}",
            f"- top_regression_action_types: {json.dumps(diagnosis['action_summary']['top_regression_action_types'], ensure_ascii=False)}",
        ]
        per_sr_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    diagnostics.sort(key=lambda d: (not d["needs_review"], d["recall"], -(d["missed_count"])))

    stem = summary_path.stem.replace("workflow_summary_", "")
    diagnostics_path = run_logs_dir / f"step3_diagnostics_{stem}.json"
    review_queue_path = run_logs_dir / f"step3_review_queue_{stem}.md"
    diagnostics_path.write_text(json.dumps(diagnostics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    md_lines = [
        "# Step 3 Review Queue",
        "",
        f"- source_summary: `{summary_path.name}`",
        f"- query_laws: `{query_laws_file.name}`",
        f"- low_recall_threshold: `{args.low_recall_threshold}`",
        f"- delta_threshold: `{args.delta_threshold}`",
        "",
        "| SR | Recall | Prev | Delta | Total Hits | Missed | Needs Review |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    md_lines.extend(render_markdown_row(d) for d in diagnostics)
    md_lines.extend(
        [
            "",
            "## Priority cases",
            "",
        ]
    )
    priority = [d for d in diagnostics if d["needs_review"]]
    if not priority:
        md_lines.append("No SR met the automatic review criteria.")
    else:
        for d in priority:
            md_lines.extend(
                [
                    f"### {d['sr_path']}",
                    "",
                    f"- recall: `{d['recall']:.3f}`",
                    f"- previous_recall: `{d['previous_recall'] if d['previous_recall'] is not None else 'NA'}`",
                    f"- delta_recall_vs_previous: `{d['delta_recall_vs_previous'] if d['delta_recall_vs_previous'] is not None else 'NA'}`",
                    f"- failure_mode_hint: {d['failure_mode_hint']}",
                    f"- diagnosis_file: `{d['metrics_path'].replace('last_metrics.json', 'step3_diagnosis.md')}`",
                    "",
                ]
            )
    review_queue_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(f"DIAGNOSTICS_PATH={diagnostics_path}")
    print(f"REVIEW_QUEUE_PATH={review_queue_path}")


if __name__ == "__main__":
    main()
