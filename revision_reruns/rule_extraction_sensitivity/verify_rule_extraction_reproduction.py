from __future__ import annotations

import filecmp
import importlib.util
import json
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PUBLIC = REPO / "public_release"
BASE = PUBLIC / "revision_reruns" / "rule_extraction_sensitivity"
SOURCE_SCRIPT = BASE / "scripts" / "extract_rule_candidates_and_similarity.py"
ANALYZER_PATH = PUBLIC / "02_query_laws_refinement" / "analyze_logs_ver2.py"
EXPECTED = BASE / "candidate_rules_pre_refinement"
OUT = BASE / "reproduction_check" / "generated_candidate_rules_pre_refinement"
REPORT = BASE / "reproduction_check" / "rule_extraction_reproduction_report.json"

RUN_SOURCES = {
    "run1_original": PUBLIC / "04_data",
    "run2_rerun": BASE / "raw_training_logs" / "run2" / "04_data",
    "run3_rerun": BASE / "raw_training_logs" / "run3" / "04_data",
}

COMPARE_FILES = [
    "query_laws_candidates.txt",
    "candidate_laws_section1.csv",
    "top_do_laws.csv",
    "top_avoid_laws.csv",
]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def rewrite_generated_metadata(label: str, path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if label == "run1_original":
        data["roots"] = [{"run_label": "run1_original", "path": "public_release/04_data"}]
    elif label == "run2_rerun":
        data["roots"] = [{"run_label": "run2_rerun", "path": "public_release/revision_reruns/rule_extraction_sensitivity/raw_training_logs/run2/04_data"}]
    elif label == "run3_rerun":
        data["roots"] = [{"run_label": "run3_rerun", "path": "public_release/revision_reruns/rule_extraction_sensitivity/raw_training_logs/run3/04_data"}]
    elif label == "pooled_run1_run2_run3":
        data["roots"] = [
            {"run_label": "run1_original", "path": "public_release/04_data"},
            {"run_label": "run2_rerun", "path": "public_release/revision_reruns/rule_extraction_sensitivity/raw_training_logs/run2/04_data"},
            {"run_label": "run3_rerun", "path": "public_release/revision_reruns/rule_extraction_sensitivity/raw_training_logs/run3/04_data"},
        ]
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def metadata_core(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return {
        "label": data.get("label"),
        "n_logs": data.get("n_logs"),
        "n_records": data.get("n_records"),
        "n_global_laws": data.get("n_global_laws"),
        "n_top_do": data.get("n_top_do"),
        "n_top_avoid": data.get("n_top_avoid"),
        "domains": data.get("domains"),
        "log_weights": data.get("log_weights"),
    }


def main() -> None:
    extractor = load_module("revision_rule_extractor", SOURCE_SCRIPT)
    analyzer = load_module("query_law_analyzer", ANALYZER_PATH)
    extractor.analyzer = analyzer

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)

    results = {}
    for label, source_root in RUN_SOURCES.items():
        generated_dir = OUT / label
        extractor.run_extraction(label, [(label, source_root)], generated_dir)
        rewrite_generated_metadata(label, generated_dir / "extraction_metadata.json")
        results[label] = {"files": {}, "metadata_core_match": None}
        for name in COMPARE_FILES:
            expected = EXPECTED / label / name
            generated = generated_dir / name
            results[label]["files"][name] = {
                "expected": expected.relative_to(REPO).as_posix(),
                "generated": generated.relative_to(REPO).as_posix(),
                "match": filecmp.cmp(expected, generated, shallow=False),
            }
        results[label]["metadata_core_match"] = metadata_core(EXPECTED / label / "extraction_metadata.json") == metadata_core(generated_dir / "extraction_metadata.json")

    pooled_label = "pooled_run1_run2_run3"
    pooled_roots = [
        ("run1_original", PUBLIC / "04_data"),
        ("run2_rerun", RUN_SOURCES["run2_rerun"]),
        ("run3_rerun", RUN_SOURCES["run3_rerun"]),
    ]
    generated_dir = OUT / pooled_label
    extractor.run_extraction(pooled_label, pooled_roots, generated_dir)
    rewrite_generated_metadata(pooled_label, generated_dir / "extraction_metadata.json")
    results[pooled_label] = {"files": {}, "metadata_core_match": None}
    for name in COMPARE_FILES:
        expected = EXPECTED / pooled_label / name
        generated = generated_dir / name
        results[pooled_label]["files"][name] = {
            "expected": expected.relative_to(REPO).as_posix(),
            "generated": generated.relative_to(REPO).as_posix(),
            "match": filecmp.cmp(expected, generated, shallow=False),
        }
    results[pooled_label]["metadata_core_match"] = metadata_core(EXPECTED / pooled_label / "extraction_metadata.json") == metadata_core(generated_dir / "extraction_metadata.json")

    all_match = all(
        all(item["match"] for item in result["files"].values()) and result["metadata_core_match"]
        for result in results.values()
    )
    report = {"all_match": all_match, "results": results}
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
