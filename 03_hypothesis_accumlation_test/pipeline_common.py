from __future__ import annotations

import json
import re

from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
TEST_PIPELINE_DIR = REPO_ROOT / "02_hypothesis_accumlation_test"
TEST_DATA_DIR = REPO_ROOT / "05_test_data"
SOURCE_DATA_DIR = REPO_ROOT / "04_data"

DOMAIN_LABELS = {
    "01_Rheumatoid_Arthritis": "Rheumatoid Arthritis",
    "02_Cardiovascular_Disease": "Cardiovascular Disease",
    "03_Psychiatry": "Psychiatry",
    "04_Oncology": "Oncology",
    "05_Infectious_Diseases": "Infectious Diseases",
}


TRAILING_QUERY_LIMIT_PATTERNS = [
    r";\s*(?:filters?|search limits?|time limits?)\s*:\s*.+$",
    r"(?<!\w)(?:filters?|search limits?|time limits?)\s*:\s*.+$",
]

NARRATIVE_QUERY_PATTERNS = [
    r"^research question\b",
    r"\bsupplementary material[_ ]strings\b",
    r"\bmedline/pubmed search:\b",
    r"\bsearch methods for the identification of studies\b",
    r"\brecords were identified\b",
    r"\bpubmed and embase were searched\b",
    r"\bstudies were identified through systematic searches\b",
]

EXACT_QUERY_SOURCE_FIELDS = (
    "pmid_query_exact_source",
    "pmid_query_pubmed_exact",
)

EXACT_QUERY_FILTER_FIELDS = (
    "pmid_query_filter_query",
    "pmid_query_exact_filter_query",
)



def utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def timestamp_for_paths() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parse_pmid_from_paper_folder(paper_folder: str) -> int:
    head = str(paper_folder).split("_", 1)[0]
    try:
        return int(head)
    except ValueError:
        return 0


def normalize_query(text: str) -> str:
    if text is None:
        return ""
    q = str(text).strip()
    q = re.sub(r"^FULL_QUERY:\s*", "", q, flags=re.IGNORECASE)
    q = re.sub(r"^Search Strategy:\s*", "", q, flags=re.IGNORECASE)
    q = q.replace("\u201c", '"').replace("\u201d", '"').replace("\u2018", "'").replace("\u2019", "'")
    q = re.sub(r"\s+", " ", q)
    return q.strip().strip("`")


def sanitize_query_for_pubmed(text: str) -> tuple[str, list[str]]:
    q = normalize_query(text)
    if not q:
        return "", []

    issues: list[str] = []
    cleaned = q
    for pattern in TRAILING_QUERY_LIMIT_PATTERNS:
        updated = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()
        if updated != cleaned:
            cleaned = updated.rstrip(" ;,.")
            if "stripped_trailing_limits" not in issues:
                issues.append("stripped_trailing_limits")
    return cleaned, issues


def detect_query_issues(text: str) -> list[str]:
    q = normalize_query(text)
    if not q:
        return ["empty_query"]

    issues: list[str] = []
    lowered = q.lower()
    for pattern in NARRATIVE_QUERY_PATTERNS:
        if re.search(pattern, lowered, flags=re.IGNORECASE):
            issues.append("narrative_query_text")
            break
    if not looks_like_pubmed_query(q):
        issues.append("does_not_look_like_pubmed_query")
    return issues


def build_human_query_qc(raw_query: str, filter_query: str = "", query_source_field: str = "pmid_query") -> dict[str, Any]:
    normalized = normalize_query(raw_query)
    executable_query, sanitize_issues = sanitize_query_for_pubmed(normalized)
    issues = sanitize_issues + [issue for issue in detect_query_issues(executable_query) if issue != "empty_query"]
    filter_normalized = normalize_query(filter_query)
    filter_executable, filter_sanitize_issues = sanitize_query_for_pubmed(filter_normalized)
    if filter_normalized:
        issues.extend(f"filter_{issue}" for issue in filter_sanitize_issues)
        for issue in detect_query_issues(filter_executable):
            if issue != "empty_query":
                issues.append(f"filter_{issue}")

    query_usable = bool(executable_query) and "narrative_query_text" not in issues and "does_not_look_like_pubmed_query" not in issues
    if query_usable and filter_normalized:
        query_usable = bool(filter_executable) and "filter_narrative_query_text" not in issues and "filter_does_not_look_like_pubmed_query" not in issues

    final_query = executable_query
    if query_usable and filter_executable:
        final_query = f"({executable_query}) AND ({filter_executable})"

    return {
        "raw_query": normalized,
        "raw_filter_query": filter_normalized,
        "source_query": executable_query,
        "filter_query": filter_executable,
        "query_source_field": query_source_field,
        "executable_query": final_query if query_usable else "",
        "query_usable": query_usable,
        "issues": issues,
    }


def extract_pubmed_query_from_text(text: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""

    direct = re.search(r"FULL_QUERY:\s*(.+)", raw, flags=re.IGNORECASE | re.DOTALL)
    if direct:
        return normalize_query(direct.group(1))

    code_blocks = re.findall(r"```(?:\w+)?\n(.*?)```", raw, flags=re.DOTALL)
    for block in code_blocks:
        candidate = normalize_query(block)
        if looks_like_pubmed_query(candidate):
            return candidate

    lines = [normalize_query(line) for line in raw.splitlines() if normalize_query(line)]
    ranked = sorted(lines, key=lambda line: (looks_like_pubmed_query(line), len(line)), reverse=True)
    if ranked and looks_like_pubmed_query(ranked[0]):
        return ranked[0]

    paragraphs = [normalize_query(part) for part in re.split(r"\n\s*\n", raw) if normalize_query(part)]
    ranked_paragraphs = sorted(paragraphs, key=lambda line: (looks_like_pubmed_query(line), len(line)), reverse=True)
    if ranked_paragraphs:
        return ranked_paragraphs[0]

    return normalize_query(raw)


def looks_like_pubmed_query(text: str) -> bool:
    if not text:
        return False
    tokens = [" AND ", " OR ", "[tiab]", "[Title/Abstract]", "[Mesh]", "[mh]", " NOT ", "("]
    hits = sum(token.lower() in text.lower() for token in tokens)
    return hits >= 2


def scan_papers(base_dir: Path, domain_filter: set[str] | None = None) -> list[tuple[str, str]]:
    """Return (domain_folder, paper_folder) pairs by scanning the directory structure."""
    pairs: list[tuple[str, str]] = []
    for domain in sorted(base_dir.iterdir()):
        if not domain.is_dir() or domain.name.startswith("_"):
            continue
        if domain_filter and domain.name not in domain_filter:
            continue
        for paper in sorted(domain.iterdir()):
            if not paper.is_dir():
                continue
            pairs.append((domain.name, paper.name))
    pairs.sort(key=lambda item: (item[0], parse_pmid_from_paper_folder(item[1])))
    return pairs


def source_paper_dir(domain_folder: str, paper_folder: str) -> Path:
    return SOURCE_DATA_DIR / domain_folder / paper_folder


def test_paper_dir(domain_folder: str, paper_folder: str) -> Path:
    return TEST_DATA_DIR / domain_folder / paper_folder


def load_source_input_config(domain_folder: str, paper_folder: str) -> dict[str, Any]:
    return read_json(source_paper_dir(domain_folder, paper_folder) / "input_config.json")


def load_source_input_config_detailed(domain_folder: str, paper_folder: str) -> dict[str, Any]:
    return read_json(source_paper_dir(domain_folder, paper_folder) / "input_config_detailed.json")


def extract_public_input_config(domain_folder: str, paper_folder: str) -> dict[str, Any]:
    source = load_source_input_config(domain_folder, paper_folder)
    detailed = load_source_input_config_detailed(domain_folder, paper_folder)
    public_keys = ("target_name", "objectives", "inclusion_criteria", "exclusion_criteria")
    public_payload: dict[str, Any] = {}
    for key in public_keys:
        if key in source:
            public_payload[key] = source[key]
        elif key in detailed:
            public_payload[key] = detailed[key]
    return public_payload


def extract_gold_pmids(domain_folder: str, paper_folder: str) -> list[str]:
    source = load_source_input_config(domain_folder, paper_folder)
    detailed = load_source_input_config_detailed(domain_folder, paper_folder)
    gold = source.get("gold_pmids") or detailed.get("gold_pmids") or []
    return [str(pmid).strip() for pmid in gold if str(pmid).strip()]


def extract_human_query(domain_folder: str, paper_folder: str) -> str:
    detailed = load_source_input_config_detailed(domain_folder, paper_folder)
    qc = extract_human_query_qc(domain_folder, paper_folder)
    return str(qc["executable_query"])


def extract_human_query_qc(domain_folder: str, paper_folder: str) -> dict[str, Any]:
    detailed = load_source_input_config_detailed(domain_folder, paper_folder)
    for field in EXACT_QUERY_SOURCE_FIELDS:
        raw_query = str(detailed.get(field, "") or "")
        if raw_query.strip():
            filter_query = ""
            for filter_field in EXACT_QUERY_FILTER_FIELDS:
                filter_query = str(detailed.get(filter_field, "") or "")
                if filter_query.strip():
                    break
            return build_human_query_qc(raw_query, filter_query=filter_query, query_source_field=field)
    return build_human_query_qc(str(detailed.get("pmid_query", "") or ""), query_source_field="pmid_query")



def ensure_clean_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
