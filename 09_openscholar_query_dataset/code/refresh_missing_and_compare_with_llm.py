from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
OPEN_ROOT = REPO / "09_openscholar_query_dataset"
CSV_PATH = REPO / "08_elicit_queryb_dataset" / "elicit_queryB_list_papers.csv"
TEST_ROOT = REPO / "05_test_data"
RESULTS_ROOT = REPO / "06_exclusion_screening_pipeline" / "results"
OUT_DIR = REPO / "08_elicit_queryb_dataset"

ATTACH_PMIDS = OPEN_ROOT / "code" / "attach_pmids.py"
RELAXED_RECALL = OPEN_ROOT / "code" / "compute_relaxed_recall.py"

LLM_SOURCES = {
    "Codex k500": RESULTS_ROOT / "test_prime_A_B_C_posthoc_recall_codex_20260401_150507.csv",
    "Claude k500": RESULTS_ROOT / "test_prime_A_B_C_posthoc_recall_claude_20260401_150457.csv",
    "Gemini cut0": RESULTS_ROOT / "test_prime_A_B_C_posthoc_recall_gemini_20260506_161353.csv",
    "Gemini cut30": RESULTS_ROOT / "test_prime_A_B_C_posthoc_recall_gemini_20260506_170750.csv",
    "Gemini cut50": RESULTS_ROOT / "test_prime_A_B_C_posthoc_recall_gemini_20260506_163349.csv",
    "Gemini cut70": RESULTS_ROOT / "test_prime_A_B_C_posthoc_recall_gemini_20260506_163347.csv",
}


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv_rows(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def to_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        if math.isfinite(value):
            return f"{value:.6f}"
        return ""
    return str(value)


def find_gold_path(paper_id: str) -> Path | None:
    matches = list(TEST_ROOT.glob(f"*/{paper_id}/gold_pmids.json"))
    if matches:
        return matches[0]
    matches = list(TEST_ROOT.glob(f"*/*/{paper_id}/gold_pmids.json"))
    if matches:
        return matches[0]
    return None


def run_python(script: Path, *args: str) -> None:
    cmd = [sys.executable, str(script), *args]
    subprocess.run(cmd, check=True)


def extract_relaxed_metrics(report_path: Path) -> dict[str, tuple[float, int, str]]:
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    out: dict[str, tuple[float, int, str]] = {}
    for rep in payload.get("reports", []):
        file_name = Path(rep["file"]).name
        if "normal" in file_name:
            key = "normal"
        elif "deep" in file_name:
            key = "deep"
        else:
            continue
        tp = int(rep["tp_relaxed_total"])
        hits = int(rep["paper_count"])
        recall = float(rep["recall_relaxed"])
        nnr = "" if tp <= 0 else f"{(hits / tp):.6f}"
        out[key] = (recall, hits, nnr)
    return out


def apply_metrics_to_row(row: dict[str, str], metrics: dict[str, tuple[float, int, str]]) -> None:
    if "normal" in metrics:
        rec, hits, nnr = metrics["normal"]
        row["openscholar_normal_recall"] = to_text(rec)
        row["openscholar_normal_hits"] = to_text(hits)
        row["openscholar_normal_nnr"] = nnr
    if "deep" in metrics:
        rec, hits, nnr = metrics["deep"]
        row["openscholar_deep_recall"] = to_text(rec)
        row["openscholar_deep_hits"] = to_text(hits)
        row["openscholar_deep_nnr"] = nnr


def provisional_fill_from_existing_reports(rows: list[dict[str, str]]) -> dict[str, str]:
    status: dict[str, str] = {}
    for row in rows:
        paper_id = row["paper_id"]
        if row.get("openscholar_normal_recall", "").strip() or row.get("openscholar_deep_recall", "").strip():
            continue
        target_dir = OPEN_ROOT / paper_id
        report_path = target_dir / "relaxed_recall_report.json"
        if not target_dir.is_dir():
            status[paper_id] = "missing_json_dir"
            continue
        if not report_path.exists():
            status[paper_id] = "missing_relaxed_report"
            continue
        metrics = extract_relaxed_metrics(report_path)
        apply_metrics_to_row(row, metrics)
        status[paper_id] = "filled_from_existing_report"
    return status


def final_refresh_with_network(rows: list[dict[str, str]], target_paper_ids: set[str]) -> dict[str, str]:
    refreshed: dict[str, str] = {}
    for row in rows:
        paper_id = row["paper_id"]
        if paper_id not in target_paper_ids:
            continue
        target_dir = OPEN_ROOT / paper_id
        if not target_dir.is_dir():
            refreshed[paper_id] = "missing_json_dir"
            continue

        gold_path = find_gold_path(paper_id)
        if gold_path is None:
            refreshed[paper_id] = "missing_gold_pmids"
            continue

        run_python(ATTACH_PMIDS, str(target_dir))
        run_python(RELAXED_RECALL, str(target_dir), "--gold-path", str(gold_path))

        metrics = extract_relaxed_metrics(target_dir / "relaxed_recall_report.json")
        apply_metrics_to_row(row, metrics)
        refreshed[paper_id] = "computed_with_crossref_pubmed"
    return refreshed


def f1_from_recall_nnr(recall: float, nnr: float | None) -> float:
    if nnr is None:
        return 0.0 if recall == 0.0 else float("nan")
    precision = 1.0 / nnr
    denom = precision + recall
    return 0.0 if denom == 0 else 2.0 * precision * recall / denom


def summarize_openscholar(rows: list[dict[str, str]], mode: str) -> dict[str, str]:
    recall_col = f"openscholar_{mode}_recall"
    hits_col = f"openscholar_{mode}_hits"
    nnr_col = f"openscholar_{mode}_nnr"
    recall_vals: list[float] = []
    hit_vals: list[float] = []
    nnr_vals: list[float] = []
    f1_vals: list[float] = []
    tp_sum = 0
    hit_sum = 0
    gold_sum = 0
    n = 0

    for row in rows:
        recall_text = (row.get(recall_col) or "").strip()
        hits_text = (row.get(hits_col) or "").strip()
        nnr_text = (row.get(nnr_col) or "").strip()
        gold_text = (row.get("included_studies") or row.get("gold_n") or row.get("gold_count") or "").strip()
        if not recall_text or not hits_text or not gold_text:
            continue
        recall = float(recall_text)
        hits = int(float(hits_text))
        gold_n = int(float(gold_text))
        tp = int(round(recall * gold_n))
        n += 1
        recall_vals.append(recall)
        hit_vals.append(hits)
        gold_sum += gold_n
        hit_sum += hits
        tp_sum += tp
        if nnr_text:
            nnr = float(nnr_text)
            nnr_vals.append(nnr)
            f1_vals.append(f1_from_recall_nnr(recall, nnr))
        else:
            f1_vals.append(f1_from_recall_nnr(recall, None))

    micro_recall = (tp_sum / gold_sum) if gold_sum else float("nan")
    micro_precision = (tp_sum / hit_sum) if hit_sum else float("nan")
    micro_nnr = (hit_sum / tp_sum) if tp_sum else float("nan")
    micro_f1 = 0.0 if (micro_precision + micro_recall) == 0 else 2.0 * micro_precision * micro_recall / (micro_precision + micro_recall)

    return {
        "method": f"OpenScholar {mode}",
        "n_papers": str(n),
        "macro_recall_mean": to_text(sum(recall_vals) / len(recall_vals) if recall_vals else None),
        "macro_hits_mean": to_text(sum(hit_vals) / len(hit_vals) if hit_vals else None),
        "macro_nnr_mean": to_text(sum(nnr_vals) / len(nnr_vals) if nnr_vals else None),
        "macro_f1_mean": to_text(sum(f1_vals) / len(f1_vals) if f1_vals else None),
        "micro_tp_sum": str(tp_sum),
        "micro_hit_sum": str(hit_sum),
        "micro_gold_sum": str(gold_sum),
        "micro_recall": to_text(micro_recall),
        "micro_precision": to_text(micro_precision),
        "micro_nnr": to_text(micro_nnr),
        "micro_f1": to_text(micro_f1),
    }


def summarize_llm(result_csv: Path, method: str) -> dict[str, str]:
    rows = load_csv_rows(result_csv)
    recall_vals: list[float] = []
    hit_vals: list[float] = []
    nnr_vals: list[float] = []
    f1_vals: list[float] = []
    tp_sum = 0
    hit_sum = 0
    gold_sum = 0

    for row in rows:
        recall = float(row["stage_c_recall"])
        hits = int(float(row["stage_c_k_used"]))
        tp = int(float(row["stage_c_tp"]))
        gold_n = int(float(row["gold_n"]))
        recall_vals.append(recall)
        hit_vals.append(hits)
        gold_sum += gold_n
        hit_sum += hits
        tp_sum += tp
        if tp > 0:
            nnr = hits / tp
            nnr_vals.append(nnr)
            f1_vals.append(f1_from_recall_nnr(recall, nnr))
        else:
            f1_vals.append(0.0)

    micro_recall = (tp_sum / gold_sum) if gold_sum else float("nan")
    micro_precision = (tp_sum / hit_sum) if hit_sum else float("nan")
    micro_nnr = (hit_sum / tp_sum) if tp_sum else float("nan")
    micro_f1 = 0.0 if (micro_precision + micro_recall) == 0 else 2.0 * micro_precision * micro_recall / (micro_precision + micro_recall)

    return {
        "method": method,
        "n_papers": str(len(rows)),
        "macro_recall_mean": to_text(sum(recall_vals) / len(recall_vals) if recall_vals else None),
        "macro_hits_mean": to_text(sum(hit_vals) / len(hit_vals) if hit_vals else None),
        "macro_nnr_mean": to_text(sum(nnr_vals) / len(nnr_vals) if nnr_vals else None),
        "macro_f1_mean": to_text(sum(f1_vals) / len(f1_vals) if f1_vals else None),
        "micro_tp_sum": str(tp_sum),
        "micro_hit_sum": str(hit_sum),
        "micro_gold_sum": str(gold_sum),
        "micro_recall": to_text(micro_recall),
        "micro_precision": to_text(micro_precision),
        "micro_nnr": to_text(micro_nnr),
        "micro_f1": to_text(micro_f1),
    }


def build_comparison_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    comparison_rows = [
        summarize_openscholar(rows, "normal"),
        summarize_openscholar(rows, "deep"),
    ]
    for method, path in LLM_SOURCES.items():
        comparison_rows.append(summarize_llm(path, method))
    return comparison_rows


def write_comparison_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provisional-only", action="store_true")
    parser.add_argument("--final-only", action="store_true")
    args = parser.parse_args()

    provisional_only = args.provisional_only
    final_only = args.final_only
    original_rows = load_csv_rows(CSV_PATH)
    fieldnames = list(original_rows[0].keys()) if original_rows else []
    target_paper_ids = {
        r["paper_id"]
        for r in original_rows
        if not (r.get("openscholar_normal_recall", "").strip() or r.get("openscholar_deep_recall", "").strip())
    }
    refresh_out = OUT_DIR / "openscholar_refresh_status_20260511.json"

    if final_only:
        if not refresh_out.exists():
            raise SystemExit(f"Missing refresh status file: {refresh_out}")
        status_payload = json.loads(refresh_out.read_text(encoding="utf-8"))
        provisional_status = status_payload.get("provisional", {})
        target_paper_ids = {
            paper_id
            for paper_id, status in provisional_status.items()
            if status != "missing_json_dir"
        }
        final_rows = [dict(r) for r in original_rows]
        final_status = final_refresh_with_network(final_rows, target_paper_ids)
        write_csv_rows(CSV_PATH, final_rows, fieldnames)
        final_comparison = build_comparison_rows(final_rows)
        final_csv = OUT_DIR / "openscholar_vs_llm_test_summary_final_20260511.csv"
        write_comparison_csv(final_csv, final_comparison)
        refresh_out.write_text(
            json.dumps(
                {
                    "provisional": provisional_status,
                    "final": final_status,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"updated_csv={CSV_PATH}")
        print(f"final_comparison_csv={final_csv}")
        print(f"refresh_status_json={refresh_out}")
        print(json.dumps({"final": final_comparison}, ensure_ascii=False, indent=2))
        return 0

    provisional_rows = [dict(r) for r in original_rows]
    provisional_status = provisional_fill_from_existing_reports(provisional_rows)
    write_csv_rows(CSV_PATH, provisional_rows, fieldnames)
    provisional_comparison = build_comparison_rows(provisional_rows)
    provisional_csv = OUT_DIR / "openscholar_vs_llm_test_summary_provisional_20260511.csv"
    write_comparison_csv(provisional_csv, provisional_comparison)

    if provisional_only:
        refresh_out.write_text(
            json.dumps({"provisional": provisional_status, "final": {}}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"updated_csv={CSV_PATH}")
        print(f"provisional_comparison_csv={provisional_csv}")
        print(f"refresh_status_json={refresh_out}")
        print(json.dumps({"provisional": provisional_comparison}, ensure_ascii=False, indent=2))
        return 0

    final_rows = [dict(r) for r in provisional_rows]
    final_status = final_refresh_with_network(final_rows, target_paper_ids)
    write_csv_rows(CSV_PATH, final_rows, fieldnames)
    final_comparison = build_comparison_rows(final_rows)
    final_csv = OUT_DIR / "openscholar_vs_llm_test_summary_final_20260511.csv"
    write_comparison_csv(final_csv, final_comparison)

    refresh_out.write_text(
        json.dumps(
            {
                "provisional": provisional_status,
                "final": final_status,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"updated_csv={CSV_PATH}")
    print(f"provisional_comparison_csv={provisional_csv}")
    print(f"final_comparison_csv={final_csv}")
    print(f"refresh_status_json={refresh_out}")
    print(json.dumps({"provisional": provisional_comparison, "final": final_comparison}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
