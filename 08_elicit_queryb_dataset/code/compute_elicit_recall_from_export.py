from __future__ import annotations

import argparse
import csv
import json
import re
import time
from pathlib import Path
from typing import Any

import requests


REPO = Path(__file__).resolve().parents[2]
ROOT = REPO / "08_elicit_queryb_dataset"
DATA_DIR = REPO / "04_data"
TEST_DIR = REPO / "05_test_data"
PIPELINE_RESULTS = REPO / "06_exclusion_screening_pipeline" / "results"
PUBMED_CACHE = REPO / "06_exclusion_screening_pipeline" / "pubmed_cache"

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
USER_AGENT = "ElicitRecallAudit/1.0"
SLEEP_SECONDS = 0.34
MAX_RETRIES = 6


def normalize_doi(text: str) -> str:
    doi = str(text or "").strip().lower()
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi)
    doi = re.sub(r"^doi:\s*", "", doi)
    doi = doi.replace("–", "-").replace("—", "-").replace("−", "-")
    doi = doi.replace(" ", "")
    doi = doi.rstrip(".")
    return doi


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})
    return s


def post_with_retry(sess: requests.Session, url: str, data: dict[str, Any], timeout: int = 45, sleep_seconds: float = SLEEP_SECONDS) -> requests.Response:
    delay = sleep_seconds
    last_exc: Exception | None = None
    for _ in range(MAX_RETRIES):
        try:
            resp = sess.post(url, data=data, timeout=timeout)
            if resp.status_code in (429, 500, 502, 503, 504):
                last_exc = requests.HTTPError(f"{resp.status_code} for {url}")
                time.sleep(delay)
                delay *= 1.8
                continue
            resp.raise_for_status()
            return resp
        except Exception as exc:
            last_exc = exc
            time.sleep(delay)
            delay *= 1.8
    if last_exc:
        raise last_exc
    raise RuntimeError(f"request failed: {url}")


def load_gold_pmids(gold_path: Path) -> list[str]:
    obj = json.loads(gold_path.read_text(encoding="utf-8-sig"))
    return [str(x).strip() for x in obj.get("gold_pmids", []) if str(x).strip()]


def gold_pmid_to_doi(pmids: list[str], sess: requests.Session, sleep_seconds: float = SLEEP_SECONDS) -> dict[str, str]:
    out: dict[str, str] = {}
    for i in range(0, len(pmids), 50):
        chunk = pmids[i : i + 50]
        time.sleep(sleep_seconds)
        resp = post_with_retry(
            sess,
            ESUMMARY_URL,
            {"db": "pubmed", "id": ",".join(chunk), "retmode": "json"},
            timeout=45,
            sleep_seconds=sleep_seconds,
        )
        result = resp.json().get("result", {})
        for pmid in chunk:
            rec = result.get(str(pmid), {}) or {}
            doi = ""
            for aid in rec.get("articleids", []) or []:
                if str(aid.get("idtype", "")).lower() == "doi":
                    doi = normalize_doi(aid.get("value", ""))
                    break
            out[str(pmid)] = doi
    return out


def doi_to_pmid_set(dois: set[str], sess: requests.Session, sleep_seconds: float = SLEEP_SECONDS) -> set[str]:
    pmids: set[str] = set()
    for doi in sorted(dois):
        if not doi:
            continue
        time.sleep(sleep_seconds)
        resp = post_with_retry(
            sess,
            ESEARCH_URL,
            {"db": "pubmed", "term": f"{doi}[AID]", "retmode": "json", "retmax": 20},
            timeout=45,
            sleep_seconds=sleep_seconds,
        )
        ids = resp.json().get("esearchresult", {}).get("idlist", []) or []
        pmids.update(str(x).strip() for x in ids if str(x).strip())
    return pmids


def read_elicit_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def elicit_doi_set(rows: list[dict[str, str]], include_only: bool) -> set[str]:
    out: set[str] = set()
    for row in rows:
        if include_only and str(row.get("Screening judgement", "")).strip().lower() != "include":
            continue
        doi = normalize_doi(row.get("DOI", ""))
        if doi:
            out.add(doi)
    return out


def detect_domain_for_paper(paper_id: str) -> str:
    for base in (TEST_DIR, DATA_DIR):
        for child in base.iterdir():
            if not child.is_dir():
                continue
            if (child / paper_id).exists():
                return child.name
    raise FileNotFoundError(f"Domain for {paper_id} not found under 04_data or 05_test_data")


def find_posthoc_csv(provider: str) -> Path:
    candidates = sorted(PIPELINE_RESULTS.glob(f"test_prime_A_B_C_posthoc_recall_{provider}_*.csv"))
    if not candidates:
        raise FileNotFoundError(f"No posthoc CSV found for {provider}")
    return candidates[-1]


def load_posthoc_row(provider: str, paper_id: str) -> dict[str, str]:
    path = find_posthoc_csv(provider)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        if row.get("paper_id") == paper_id:
            row["_source_csv"] = str(path)
            return row
    raise KeyError(f"{paper_id} not found in {path}")


def find_stagec_jsonl(domain: str, paper_id: str, provider: str, query_hash: str) -> Path:
    cache_dir = PUBMED_CACHE / domain / paper_id / provider
    exact = sorted(cache_dir.glob(f"stagec_scored_records_medcpt_{query_hash}*.jsonl"))
    if exact:
        return exact[-1]
    raise FileNotFoundError(f"Stage C cache not found for {provider} {paper_id} query_hash={query_hash}")


def load_stagec_records(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def top_recall_from_stagec(
    records: list[dict[str, Any]],
    gold_pmids: set[str],
    keep_n: int,
    score_key: str,
) -> tuple[int, float]:
    ordered = sorted(
        records,
        key=lambda r: (-float(r.get(score_key, 0.0)), str(r.get("pmid", ""))),
    )
    kept = {str(r.get("pmid", "")).strip() for r in ordered[:keep_n] if str(r.get("pmid", "")).strip()}
    tp = len(kept & gold_pmids)
    recall = tp / len(gold_pmids) if gold_pmids else 0.0
    return tp, recall


def compute_paper_metrics(elicit_csv: Path, gold_path: Path, sleep_seconds: float = SLEEP_SECONDS) -> dict[str, Any]:
    paper_id = elicit_csv.parent.name
    domain = detect_domain_for_paper(paper_id)
    sess = session()

    gold_pmids = load_gold_pmids(gold_path)
    gold_set = set(gold_pmids)
    gold_doi_map = gold_pmid_to_doi(gold_pmids, sess, sleep_seconds=sleep_seconds)
    gold_dois = {doi for doi in gold_doi_map.values() if doi}

    rows = read_elicit_rows(elicit_csv)
    all_dois = elicit_doi_set(rows, include_only=False)
    include_dois = elicit_doi_set(rows, include_only=True)
    all_pmids_from_doi = doi_to_pmid_set(all_dois, sess, sleep_seconds=sleep_seconds)
    include_pmids_from_doi = doi_to_pmid_set(include_dois, sess, sleep_seconds=sleep_seconds)

    matched_all_by_gold_to_doi = {
        pmid for pmid, doi in gold_doi_map.items() if doi and doi in all_dois
    }
    matched_include_by_gold_to_doi = {
        pmid for pmid, doi in gold_doi_map.items() if doi and doi in include_dois
    }
    matched_all_by_doi_to_pmid = gold_set & all_pmids_from_doi
    matched_include_by_doi_to_pmid = gold_set & include_pmids_from_doi

    matched_all_union = matched_all_by_gold_to_doi | matched_all_by_doi_to_pmid
    matched_include_union = matched_include_by_gold_to_doi | matched_include_by_doi_to_pmid

    tp_all = len(matched_all_by_gold_to_doi)
    tp_include = len(matched_include_by_gold_to_doi)
    tp_all_rev = len(matched_all_by_doi_to_pmid)
    tp_include_rev = len(matched_include_by_doi_to_pmid)
    tp_all_union = len(matched_all_union)
    tp_include_union = len(matched_include_union)

    out: dict[str, Any] = {
        "paper_id": paper_id,
        "domain": domain,
        "gold_n": len(gold_pmids),
        "gold_doi_resolved_n": len(gold_dois),
        "elicit_rows": len(rows),
        "elicit_all_doi_n": len(all_dois),
        "elicit_include_doi_n": len(include_dois),
        "elicit_all_pmid_from_doi_n": len(all_pmids_from_doi),
        "elicit_include_pmid_from_doi_n": len(include_pmids_from_doi),
        "elicit_all_tp_gold_to_doi": tp_all,
        "elicit_all_recall_gold_to_doi": tp_all / len(gold_pmids) if gold_pmids else 0.0,
        "elicit_include_tp_gold_to_doi": tp_include,
        "elicit_include_recall_gold_to_doi": tp_include / len(gold_pmids) if gold_pmids else 0.0,
        "elicit_all_tp_doi_to_pmid": tp_all_rev,
        "elicit_all_recall_doi_to_pmid": tp_all_rev / len(gold_pmids) if gold_pmids else 0.0,
        "elicit_include_tp_doi_to_pmid": tp_include_rev,
        "elicit_include_recall_doi_to_pmid": tp_include_rev / len(gold_pmids) if gold_pmids else 0.0,
        "elicit_all_tp_union": tp_all_union,
        "elicit_all_recall_union": tp_all_union / len(gold_pmids) if gold_pmids else 0.0,
        "elicit_include_tp_union": tp_include_union,
        "elicit_include_recall_union": tp_include_union / len(gold_pmids) if gold_pmids else 0.0,
        "gold_doi_audit": [
            {
                "pmid": pmid,
                "doi": gold_doi_map.get(pmid, ""),
                "matched_all_gold_to_doi": pmid in matched_all_by_gold_to_doi,
                "matched_include_gold_to_doi": pmid in matched_include_by_gold_to_doi,
                "matched_all_doi_to_pmid": pmid in matched_all_by_doi_to_pmid,
                "matched_include_doi_to_pmid": pmid in matched_include_by_doi_to_pmid,
                "matched_all_union": pmid in matched_all_union,
                "matched_include_union": pmid in matched_include_union,
            }
            for pmid in gold_pmids
        ],
    }

    for provider in ("codex", "claude", "gemini"):
        try:
            row = load_posthoc_row(provider, paper_id)
        except Exception:
            continue
        provider_key = provider
        stage_b_hits = int(float(row.get("stage_b_total_hits", 0) or 0))
        stage_b_tp = int(float(row.get("stage_b_tp", 0) or 0))
        stage_b_recall = float(row.get("stage_b_recall", 0) or 0)
        out[f"{provider_key}_cut0_hit"] = stage_b_hits
        out[f"{provider_key}_cut0_tp"] = stage_b_tp
        out[f"{provider_key}_cut0_recall"] = stage_b_recall
        out[f"{provider_key}_posthoc_csv"] = row["_source_csv"]

        query_hash = str(row.get("stage_c_query_hash", "") or "").strip()
        if query_hash:
            try:
                jsonl = find_stagec_jsonl(domain, paper_id, provider, query_hash)
                recs = load_stagec_records(jsonl)
                keep30 = int(round(len(recs) * 0.7))
                tp30, rec30 = top_recall_from_stagec(recs, gold_set, keep30, "stage_c_score")
                out[f"{provider_key}_cut30_hit"] = keep30
                out[f"{provider_key}_cut30_tp"] = tp30
                out[f"{provider_key}_cut30_recall"] = rec30
                out[f"{provider_key}_stagec_jsonl"] = str(jsonl)

                if stage_b_hits > 1000:
                    tp1000, rec1000 = top_recall_from_stagec(recs, gold_set, min(1000, len(recs)), "final")
                    out[f"{provider_key}_top1000_hit"] = min(1000, len(recs))
                    out[f"{provider_key}_top1000_tp"] = tp1000
                    out[f"{provider_key}_top1000_recall"] = rec1000
            except Exception as exc:
                out[f"{provider_key}_stagec_error"] = str(exc)

    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paper_id")
    parser.add_argument("--elicit-csv", type=Path, required=True)
    parser.add_argument("--gold-path", type=Path, required=True)
    parser.add_argument("--out-prefix", type=Path, default=None)
    parser.add_argument("--sleep-seconds", type=float, default=SLEEP_SECONDS)
    args = parser.parse_args()

    result = compute_paper_metrics(args.elicit_csv, args.gold_path, sleep_seconds=args.sleep_seconds)
    out_prefix = args.out_prefix or (ROOT / args.paper_id / f"comparison_elicit_vs_pipeline_{args.paper_id}")

    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    summary_json = out_prefix.with_suffix(".json")
    audit_csv = out_prefix.parent / f"elicit_gold_doi_match_audit_{args.paper_id}.csv"

    summary_json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with audit_csv.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "pmid",
                "doi",
                "matched_all_gold_to_doi",
                "matched_include_gold_to_doi",
                "matched_all_doi_to_pmid",
                "matched_include_doi_to_pmid",
                "matched_all_union",
                "matched_include_union",
            ],
        )
        w.writeheader()
        w.writerows(result["gold_doi_audit"])

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"summary_json={summary_json}")
    print(f"audit_csv={audit_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
