from __future__ import annotations

import csv
import importlib.util
import json
import math
import re
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from statistics import mean

REPO = Path(__file__).resolve().parents[4]
PUBLIC = REPO / "public_release"
BASE = PUBLIC / "revision_reruns" / "rule_extraction_sensitivity"
ANALYZER_PATH = PUBLIC / "02_query_laws_refinement" / "analyze_logs_ver2.py"
OUT_ROOT = BASE / "candidate_rules_pre_refinement"

RUN_SOURCES = {
    "run1_original": PUBLIC / "04_data",
    "run2_rerun": BASE / "raw_training_logs" / "run2" / "04_data",
    "run3_rerun": BASE / "raw_training_logs" / "run3" / "04_data",
}


def load_analyzer():
    spec = importlib.util.spec_from_file_location("query_law_analyzer", ANALYZER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def iter_log_files(root: Path):
    return sorted(root.glob("*/*/search_history.jsonl"))


def read_records_for_roots(roots: list[tuple[str, Path]]):
    records = []
    log_iter_sets: dict[str, set[int]] = defaultdict(set)
    log_files: list[Path] = []

    for run_label, root in roots:
        for log_file in iter_log_files(root):
            rel = log_file.relative_to(root)
            parts = rel.parts
            if len(parts) != 3:
                continue
            domain, paper, _ = parts
            if len(roots) == 1:
                log_name = f"{domain}/{paper}/search_history.jsonl"
            else:
                log_name = f"{domain}/{run_label}__{paper}/search_history.jsonl"
            log_files.append(log_file)
            with log_file.open("r", encoding="utf-8-sig") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    try:
                        iter_num = int(rec.get("iteration", 0))
                    except (TypeError, ValueError):
                        iter_num = 0
                    log_iter_sets[log_name].add(iter_num)
                    records.append((log_name, rec))

    log_weights = {}
    for log_name, iters in log_iter_sets.items():
        n_iter = max(len(iters), 1)
        log_weights[log_name] = max(analyzer.MIN_WEIGHT, min(n_iter / analyzer.WEIGHT_NORM, 1.0))
    return log_files, records, log_weights


def law_key(row: dict) -> tuple[str, ...]:
    return (
        str(row.get("META_ACTION", "")),
        str(row.get("META_CONCEPT", "")),
        str(row.get("Action_Operator", "")),
        str(row.get("Target_Block", "")),
        str(row.get("Target_Slot", "")),
        str(row.get("Field_Policy", "")),
    )


def simple_key(row: dict) -> tuple[str, str]:
    return (str(row.get("META_ACTION", "")), str(row.get("META_CONCEPT", "")))


def write_rows_csv(path: Path, rows: list[dict]):
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def spearman(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 2:
        return None

    def ranks(vals: list[float]) -> list[float]:
        order = sorted(range(len(vals)), key=lambda i: vals[i])
        out = [0.0] * len(vals)
        i = 0
        while i < len(vals):
            j = i
            while j + 1 < len(vals) and vals[order[j + 1]] == vals[order[i]]:
                j += 1
            r = (i + j + 2) / 2.0
            for k in range(i, j + 1):
                out[order[k]] = r
            i = j + 1
        return out

    rx, ry = ranks(xs), ranks(ys)
    mx, my = mean(rx), mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    denx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    deny = math.sqrt(sum((b - my) ** 2 for b in ry))
    if denx == 0 or deny == 0:
        return None
    return num / (denx * deny)


def cosine(xs: list[float], ys: list[float]) -> float | None:
    if not xs or not ys:
        return None
    num = sum(a * b for a, b in zip(xs, ys))
    den = math.sqrt(sum(a * a for a in xs)) * math.sqrt(sum(b * b for b in ys))
    if den == 0:
        return None
    return num / den


def top_set(rows: list[dict], selector: str, n: int = 12) -> set[tuple[str, ...]]:
    if selector == "do":
        selected = analyzer.select_deployment(rows, n=n)
    elif selector == "avoid":
        selected = analyzer.select_negative_laws(rows, n=n)
    else:
        raise ValueError(selector)
    return {law_key(r) for r in selected}


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def fmt_float(x):
    if x is None:
        return "NA"
    return f"{x:.3f}"


def run_extraction(label: str, roots: list[tuple[str, Path]], output_dir: Path):
    log_files, records, log_weights = read_records_for_roots(roots)
    global_rows = analyzer.build_rules(log_files, records, log_weights)
    global_deployment = analyzer.select_deployment(global_rows)
    global_negatives = analyzer.select_negative_laws(global_rows)
    domain_law_dict = analyzer.build_domain_laws(records, log_weights)
    output_text = analyzer.render_output(global_rows, global_deployment, global_negatives, domain_law_dict)

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "query_laws_candidates.txt").write_text(output_text, encoding="utf-8")
    write_rows_csv(output_dir / "candidate_laws_section1.csv", global_rows)
    write_rows_csv(output_dir / "top_do_laws.csv", global_deployment)
    write_rows_csv(output_dir / "top_avoid_laws.csv", global_negatives)

    metadata = {
        "label": label,
        "roots": [{"run_label": rl, "path": root.resolve().relative_to(REPO.resolve()).as_posix() if root.resolve().is_relative_to(REPO.resolve()) else root.as_posix()} for rl, root in roots],
        "n_logs": len(set(ln for ln, _ in records)),
        "n_records": len(records),
        "n_global_laws": len(global_rows),
        "n_top_do": len(global_deployment),
        "n_top_avoid": len(global_negatives),
        "domains": sorted(domain_law_dict.keys()),
        "log_weights": log_weights,
    }
    (output_dir / "extraction_metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {
        "label": label,
        "rows": global_rows,
        "do": global_deployment,
        "avoid": global_negatives,
        "metadata": metadata,
        "output_dir": output_dir,
    }


def pairwise_similarity(results: dict[str, dict]) -> list[dict]:
    out = []
    for a, b in combinations(results.keys(), 2):
        ra, rb = results[a]["rows"], results[b]["rows"]
        map_a = {law_key(r): r for r in ra}
        map_b = {law_key(r): r for r in rb}
        keys_a, keys_b = set(map_a), set(map_b)
        shared = sorted(keys_a & keys_b)
        xs = [float(map_a[k].get("Deploy_Score", 0.0)) for k in shared]
        ys = [float(map_b[k].get("Deploy_Score", 0.0)) for k in shared]
        simple_a = {simple_key(r) for r in ra}
        simple_b = {simple_key(r) for r in rb}
        top_do_a = top_set(ra, "do")
        top_do_b = top_set(rb, "do")
        top_avoid_a = top_set(ra, "avoid")
        top_avoid_b = top_set(rb, "avoid")
        out.append({
            "A": a,
            "B": b,
            "n_A": len(keys_a),
            "n_B": len(keys_b),
            "n_shared_strict": len(shared),
            "jaccard_strict": jaccard(keys_a, keys_b),
            "jaccard_meta_action_concept": jaccard(simple_a, simple_b),
            "top12_do_overlap_n": len(top_do_a & top_do_b),
            "top12_do_jaccard": jaccard(top_do_a, top_do_b),
            "top12_avoid_overlap_n": len(top_avoid_a & top_avoid_b),
            "top12_avoid_jaccard": jaccard(top_avoid_a, top_avoid_b),
            "deploy_score_spearman_shared": spearman(xs, ys),
            "deploy_score_cosine_shared": cosine(xs, ys),
        })
    return out


def write_similarity_outputs(results: dict[str, dict], similarities: list[dict]):
    write_rows_csv(OUT_ROOT / "pairwise_rule_similarity.csv", similarities)
    lines = []
    lines.append("# Rule candidate extraction and similarity")
    lines.append("")
    lines.append("Four candidate rule sets were extracted with `public_release/02_query_laws_refinement/analyze_logs_ver2.py` logic:")
    lines.append("")
    for label, result in results.items():
        m = result["metadata"]
        rel_out = result["output_dir"].relative_to(REPO).as_posix()
        lines.append(f"- `{label}`: {m['n_logs']} logs, {m['n_records']} records, {m['n_global_laws']} candidate laws; output `{rel_out}/`")
    lines.append("")
    lines.append("## Similarity Metrics")
    lines.append("")
    lines.append("- `jaccard_strict`: overlap of fully normalized law keys: META_ACTION, META_CONCEPT, operator, block, slot, field policy.")
    lines.append("- `jaccard_meta_action_concept`: overlap using only the coarse META_ACTION + META_CONCEPT key.")
    lines.append("- `top12_do_jaccard`: overlap among the 12 deployment DO-laws selected by the analyzer.")
    lines.append("- `top12_avoid_jaccard`: overlap among the 12 AVOID/recall-risk laws selected by the analyzer.")
    lines.append("- `deploy_score_spearman_shared` and `deploy_score_cosine_shared`: agreement in Deploy_Score among strictly shared laws.")
    lines.append("")
    lines.append("| A | B | strict Jaccard | coarse Jaccard | shared strict | top12 DO overlap | top12 DO Jaccard | top12 AVOID overlap | top12 AVOID Jaccard | Deploy Spearman | Deploy Cosine |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in similarities:
        lines.append(
            f"| {row['A']} | {row['B']} | {fmt_float(row['jaccard_strict'])} | "
            f"{fmt_float(row['jaccard_meta_action_concept'])} | {row['n_shared_strict']} | "
            f"{row['top12_do_overlap_n']} | {fmt_float(row['top12_do_jaccard'])} | "
            f"{row['top12_avoid_overlap_n']} | {fmt_float(row['top12_avoid_jaccard'])} | "
            f"{fmt_float(row['deploy_score_spearman_shared'])} | {fmt_float(row['deploy_score_cosine_shared'])} |"
        )
    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    lines.append("At the candidate-extraction stage, use strict Jaccard as a conservative structural similarity measure. Use coarse Jaccard and top-law overlap as more reviewer-friendly measures of whether the same rule families recur across independent runs. The pooled rule set is expected to have broader support and therefore may include rules not present in every individual run.")
    (OUT_ROOT / "rule_candidate_similarity_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    results = {}
    for label, root in RUN_SOURCES.items():
        if not root.exists():
            raise FileNotFoundError(root)
        results[label] = run_extraction(label, [(label, root)], OUT_ROOT / label)

    pooled_roots = [(label, root) for label, root in RUN_SOURCES.items()]
    results["pooled_run1_run2_run3"] = run_extraction(
        "pooled_run1_run2_run3",
        pooled_roots,
        OUT_ROOT / "pooled_run1_run2_run3",
    )

    similarities = pairwise_similarity(results)
    write_similarity_outputs(results, similarities)
    print(f"Wrote outputs to {OUT_ROOT}")
    for label, result in results.items():
        m = result["metadata"]
        print(f"{label}: logs={m['n_logs']} records={m['n_records']} laws={m['n_global_laws']}")
    print("Pairwise similarities:")
    for row in similarities:
        print(
            f"{row['A']} vs {row['B']}: strict_j={row['jaccard_strict']:.3f}, "
            f"coarse_j={row['jaccard_meta_action_concept']:.3f}, "
            f"top_do={row['top12_do_overlap_n']}/12, top_avoid={row['top12_avoid_overlap_n']}/12"
        )


if __name__ == "__main__":
    analyzer = load_analyzer()
    main()
