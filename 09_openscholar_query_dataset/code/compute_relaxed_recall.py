from __future__ import annotations

import argparse
import json
import re
import time
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import requests


ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
USER_AGENT = "OpenScholarRelaxedRecall/1.0"
SLEEP_SECONDS = 0.34
WS_RE = re.compile(r"\s+")
PUNCT_RE = re.compile(r"[^a-z0-9]+")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_gold_pmids(path: Path) -> list[str]:
    obj = load_json(path)
    return [str(x).strip() for x in obj.get("gold_pmids", []) if str(x).strip()]


def normalize_text(text: str) -> str:
    text = str(text or "")
    text = (
        text.replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2013", "-")
        .replace("\u2014", "-")
    )
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = PUNCT_RE.sub(" ", text)
    return WS_RE.sub(" ", text).strip()


def summary_year(summary: dict[str, Any]) -> str:
    pubdate = str(summary.get("pubdate", "") or "")
    m = re.search(r"\b(19|20)\d{2}\b", pubdate)
    return m.group(0) if m else ""


def pubmed_summary_many(pmids: list[str], sleep_seconds: float = SLEEP_SECONDS) -> dict[str, dict[str, Any]]:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    result: dict[str, dict[str, Any]] = {}
    chunk_size = 50
    for i in range(0, len(pmids), chunk_size):
        chunk = pmids[i : i + chunk_size]
        attempt = 0
        while True:
            time.sleep(sleep_seconds * max(1, 2**attempt))
            resp = session.post(
                ESUMMARY_URL,
                data={"db": "pubmed", "id": ",".join(chunk), "retmode": "json"},
                timeout=45,
            )
            if resp.status_code not in (429, 500, 502, 503, 504):
                resp.raise_for_status()
                break
            attempt += 1
            if attempt >= 6:
                resp.raise_for_status()
        payload = resp.json().get("result", {})
        for pmid in chunk:
            result[pmid] = payload.get(str(pmid), {}) or {}
    return result


def load_papers(path: Path) -> list[dict[str, Any]]:
    obj = load_json(path)
    return obj.get("papers", []) or []


def title_ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()


def year_close(gold_year: str, paper_year: str, tolerance: int = 1) -> bool:
    if not gold_year or not paper_year:
        return False
    try:
        return abs(int(gold_year) - int(paper_year)) <= tolerance
    except ValueError:
        return False


def evaluate_file(
    papers_path: Path,
    gold_pmids: list[str],
    gold_summaries: dict[str, dict[str, Any]],
    fuzzy_threshold_same_year: float,
    fuzzy_threshold_near_year: float,
) -> dict[str, Any]:
    papers = load_papers(papers_path)
    gold_set = set(gold_pmids)

    matched_pmid: set[str] = set()
    matched_exact_title_year: set[str] = set()
    matched_fuzzy_title_year: set[str] = set()

    unmatched_gold: dict[str, dict[str, str]] = {}
    for pmid in gold_pmids:
        summary = gold_summaries.get(pmid, {})
        unmatched_gold[pmid] = {
            "title": str(summary.get("title", "") or ""),
            "norm_title": normalize_text(str(summary.get("title", "") or "")),
            "year": summary_year(summary),
        }

    for paper in papers:
        paper_pmid = str(paper.get("pubmed_id", "") or "").strip()
        if paper_pmid and paper_pmid in gold_set:
            matched_pmid.add(paper_pmid)
            unmatched_gold.pop(paper_pmid, None)

    exact_details: list[dict[str, Any]] = []
    fuzzy_details: list[dict[str, Any]] = []

    for paper in papers:
        paper_title = str(paper.get("title", "") or "")
        paper_norm_title = normalize_text(paper_title)
        paper_year = str(paper.get("year", "") or "").strip()
        corpus_id = str(paper.get("corpusId", "") or "").strip()
        source_pmid = str(paper.get("pubmed_id", "") or "").strip()

        if not paper_norm_title:
            continue

        for gold_pmid, gold in list(unmatched_gold.items()):
            gold_title = gold["title"]
            gold_norm_title = gold["norm_title"]
            gold_year = gold["year"]
            if not gold_norm_title or not gold_year or not paper_year:
                continue

            if gold_norm_title == paper_norm_title and gold_year == paper_year:
                matched_exact_title_year.add(gold_pmid)
                exact_details.append(
                    {
                        "gold_pmid": gold_pmid,
                        "gold_title": gold_title,
                        "gold_year": gold_year,
                        "matched_title": paper_title,
                        "matched_year": paper_year,
                        "matched_pubmed_id": source_pmid,
                        "matched_corpusId": corpus_id,
                        "source_file": papers_path.name,
                    }
                )
                unmatched_gold.pop(gold_pmid, None)

    for paper in papers:
        paper_title = str(paper.get("title", "") or "")
        paper_norm_title = normalize_text(paper_title)
        paper_year = str(paper.get("year", "") or "").strip()
        corpus_id = str(paper.get("corpusId", "") or "").strip()
        source_pmid = str(paper.get("pubmed_id", "") or "").strip()

        if not paper_norm_title:
            continue

        for gold_pmid, gold in list(unmatched_gold.items()):
            gold_title = gold["title"]
            gold_norm_title = gold["norm_title"]
            gold_year = gold["year"]
            if not gold_norm_title or not gold_year or not paper_year:
                continue

            ratio = title_ratio(gold_title, paper_title)
            if gold_year == paper_year:
                threshold = fuzzy_threshold_same_year
            elif year_close(gold_year, paper_year, tolerance=1):
                threshold = fuzzy_threshold_near_year
            else:
                continue

            if ratio >= threshold:
                matched_fuzzy_title_year.add(gold_pmid)
                fuzzy_details.append(
                    {
                        "gold_pmid": gold_pmid,
                        "gold_title": gold_title,
                        "gold_year": gold_year,
                        "matched_title": paper_title,
                        "matched_year": paper_year,
                        "matched_pubmed_id": source_pmid,
                        "matched_corpusId": corpus_id,
                        "ratio": round(ratio, 6),
                        "source_file": papers_path.name,
                    }
                )
                unmatched_gold.pop(gold_pmid, None)

    strict_matched = matched_pmid | matched_exact_title_year
    relaxed_matched = strict_matched | matched_fuzzy_title_year

    return {
        "file": str(papers_path),
        "paper_count": len(papers),
        "gold_count": len(gold_pmids),
        "tp_pmid_exact": len(matched_pmid),
        "tp_title_year_exact_additional": len(matched_exact_title_year),
        "tp_title_year_fuzzy_additional": len(matched_fuzzy_title_year),
        "tp_strict_total": len(strict_matched),
        "tp_relaxed_total": len(relaxed_matched),
        "recall_pmid_exact": (len(matched_pmid) / len(gold_pmids)) if gold_pmids else 0.0,
        "recall_strict": (len(strict_matched) / len(gold_pmids)) if gold_pmids else 0.0,
        "recall_relaxed": (len(relaxed_matched) / len(gold_pmids)) if gold_pmids else 0.0,
        "matched_pmids_pmid_exact": sorted(matched_pmid, key=int),
        "matched_pmids_strict": sorted(strict_matched, key=int),
        "matched_pmids_relaxed": sorted(relaxed_matched, key=int),
        "exact_title_year_details": exact_details,
        "fuzzy_title_year_details": fuzzy_details,
        "unmatched_gold_pmids_after_relaxed": sorted(unmatched_gold.keys(), key=int),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("target_dir", type=Path)
    parser.add_argument("--gold-path", type=Path, required=True)
    parser.add_argument("--sleep-seconds", type=float, default=SLEEP_SECONDS)
    parser.add_argument("--fuzzy-threshold-same-year", type=float, default=0.95)
    parser.add_argument("--fuzzy-threshold-near-year", type=float, default=0.98)
    args = parser.parse_args()

    gold_pmids = load_gold_pmids(args.gold_path)
    gold_summaries = pubmed_summary_many(gold_pmids, sleep_seconds=args.sleep_seconds)

    reports = []
    pairs = [
        ("papers_normal_with_pmid.json", "papers_normal.json"),
        ("papers_deep_with_pmid.json", "papers_deep.json"),
    ]
    for preferred, fallback in pairs:
        path = args.target_dir / preferred
        if not path.exists():
            path = args.target_dir / fallback
        if path.exists():
            reports.append(
                evaluate_file(
                    path,
                    gold_pmids,
                    gold_summaries,
                    fuzzy_threshold_same_year=args.fuzzy_threshold_same_year,
                    fuzzy_threshold_near_year=args.fuzzy_threshold_near_year,
                )
            )

    summary = {
        "target_dir": str(args.target_dir),
        "gold_path": str(args.gold_path),
        "fuzzy_threshold_same_year": args.fuzzy_threshold_same_year,
        "fuzzy_threshold_near_year": args.fuzzy_threshold_near_year,
        "reports": reports,
    }
    out_path = args.target_dir / "relaxed_recall_report.json"
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=True, indent=2))
    print(f"output_path={out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
