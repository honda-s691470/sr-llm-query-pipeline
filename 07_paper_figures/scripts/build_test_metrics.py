"""
Build all_test_metrics.csv and test24_without_laws_all_providers.csv
from public_release data only.

Sources (all within public_release/):
  with_laws_test_eval : 05_test_data/{domain}/{paper}/model_outputs/{provider}/
                        with_laws_test_eval/normalized_query.txt
  without_laws        : 05_test_data/{domain}/{paper}/model_outputs/{provider}/
                        without_laws/result.json  -> "query" field
  human_reference     : 05_test_data/{domain}/{paper}/human_query.txt

PubMed API results are cached in data/test24_eval/pubmed_api_cache.json as PMID lists.
Metrics (total_hits, hit_gold_count, recall) are computed from the cache offline.
Re-running the script uses the cache by default; pass --refresh to re-query the API.

Usage (from public_release/):
    python 07_paper_figures/scripts/build_test_metrics.py           # use cache
    python 07_paper_figures/scripts/build_test_metrics.py --refresh # re-query API
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
_SCRIPT_DIR = Path(__file__).resolve().parent
PUBLIC_RELEASE = _SCRIPT_DIR.parent.parent  # public_release/
TEST_DATA = PUBLIC_RELEASE / "05_test_data"
OUT_DIR = _SCRIPT_DIR.parent / "data" / "test24_eval"
CACHE_FILE = OUT_DIR / "pubmed_api_cache.json"

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EMAIL = "researcher@example.com"  # update if you have an NCBI API key
SLEEP = 0.4  # seconds between API calls (NCBI rate limit: 3/sec without key)

PROVIDERS = ["claude", "codex", "gemini"]


def rel_public_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PUBLIC_RELEASE.resolve()).as_posix()
    except ValueError:
        return path.as_posix()

# ── Cache ─────────────────────────────────────────────────────────────────────

def load_cache() -> dict:
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    return {}


def save_cache(cache: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")


# ── PubMed helpers ────────────────────────────────────────────────────────────

def _esearch(term: str, rettype: str = "count", retmax: int = 0) -> str:
    """POST request to eUtils esearch; returns raw XML text."""
    params = {
        "db": "pubmed", "term": term,
        "rettype": rettype, "retmax": str(retmax), "email": EMAIL,
    }
    for attempt in range(3):
        try:
            data = urllib.parse.urlencode(params).encode()
            req = urllib.request.Request(
                EUTILS, data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode()
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    return ""


def _count(xml: str) -> int:
    m = re.search(r"<Count>(\d+)</Count>", xml)
    return int(m.group(1)) if m else 0


def _ids(xml: str) -> list[str]:
    return re.findall(r"<Id>(\d+)</Id>", xml)


def fetch_api(query: str, gold_pmids: list[str],
              domain_folder: str, paper_folder: str,
              provider: str, condition: str) -> dict:
    """Call PubMed API and return cache entry with full provenance."""
    time.sleep(SLEEP)
    xml_total = _esearch(query, rettype="count", retmax=0)
    total_hits = _count(xml_total)

    time.sleep(SLEEP)
    uid_filter = " OR ".join(f"{p}[uid]" for p in gold_pmids)
    combined = f"({query}) AND ({uid_filter})"
    xml_hits = _esearch(combined, rettype="uilist", retmax=len(gold_pmids) + 10)
    hit_pmids = _ids(xml_hits)

    return {
        "domain_folder": domain_folder,
        "paper_folder": paper_folder,
        "provider": provider,
        "condition": condition,
        "total_hits": total_hits,
        "hit_pmids": hit_pmids,
    }


def compute_metrics(cache_entry: dict, gold_pmids: list[str]) -> dict:
    """Derive metrics from a cache entry (no API calls)."""
    total_hits = cache_entry["total_hits"]
    hit_pmids = cache_entry["hit_pmids"]
    hit_gold_count = len(hit_pmids)
    gold_count = len(gold_pmids)
    recall = hit_gold_count / gold_count if gold_count > 0 else 0.0
    return {
        "total_hits": total_hits,
        "hit_gold_count": hit_gold_count,
        "recall": recall,
        "status": "ok",
        "error_note": "",
    }


# ── Data collection ───────────────────────────────────────────────────────────

def load_gold_pmids(paper_dir: Path) -> list[str]:
    gp = paper_dir / "gold_pmids.json"
    if not gp.exists():
        return []
    data = json.loads(gp.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [str(x) for x in data]
    if isinstance(data, dict):
        return [str(x) for x in data.get("pmids", data.get("gold_pmids", []))]
    return []


def collect_rows(test_data: Path, cache: dict, refresh: bool) -> list[dict]:
    rows: list[dict] = []

    domain_dirs = sorted(
        d for d in test_data.iterdir()
        if d.is_dir() and not d.name.startswith("_")
    )

    for domain_dir in domain_dirs:
        for paper_dir in sorted(p for p in domain_dir.iterdir() if p.is_dir()):
            domain_folder = domain_dir.name
            paper_folder = paper_dir.name
            gold_pmids = load_gold_pmids(paper_dir)
            if not gold_pmids:
                print(f"  WARN: no gold_pmids for {domain_folder}/{paper_folder}")
                continue

            model_outputs = paper_dir / "model_outputs"

            # ── human_reference ──────────────────────────────────────────────
            hq_path = paper_dir / "human_query.txt"
            if hq_path.exists():
                query = hq_path.read_text(encoding="utf-8").strip()
                cache_key = f"{domain_folder}/{paper_folder}/human/human_reference"
                print(f"  human  {paper_folder} ...", end=" ", flush=True)

                if refresh or cache_key not in cache:
                    try:
                        cache[cache_key] = fetch_api(
                            query, gold_pmids,
                            domain_folder, paper_folder, "human", "human_reference",
                        )
                        save_cache(cache)
                        print("(API)", end=" ", flush=True)
                    except Exception as e:
                        print(f"ERR: {e}")
                        rows.append({
                            "domain_folder": domain_folder, "paper_folder": paper_folder,
                            "provider": "human", "condition": "human_reference",
                            "method_label": "human::human_reference",
                            "query_length": len(query), "raw_query_length": len(query),
                            "gold_count": len(gold_pmids),
                            "total_hits": -1, "hit_gold_count": -1, "recall": None,
                            "status": "error", "error_note": str(e),
                            "source_path": rel_public_path(hq_path),
                        })
                        continue
                else:
                    print("(cache)", end=" ", flush=True)

                m = compute_metrics(cache[cache_key], gold_pmids)
                rows.append({
                    "domain_folder": domain_folder, "paper_folder": paper_folder,
                    "provider": "human", "condition": "human_reference",
                    "method_label": "human::human_reference",
                    "query_length": len(query), "raw_query_length": len(query),
                    "gold_count": len(gold_pmids), "source_path": rel_public_path(hq_path),
                    **m,
                })
                print(f"hits={m['total_hits']} recall={m['recall']:.3f}")

            # ── with_laws_test_eval & without_laws ────────────────────────────
            for provider in PROVIDERS:
                for condition, rel_path, query_field in [
                    ("with_laws_test_eval",
                     f"{provider}/with_laws_test_eval/normalized_query.txt",
                     None),
                    ("without_laws",
                     f"{provider}/without_laws/result.json",
                     "query"),
                ]:
                    src = model_outputs / rel_path
                    if not src.exists():
                        continue

                    if query_field is None:
                        query = src.read_text(encoding="utf-8").strip()
                    else:
                        data = json.loads(src.read_text(encoding="utf-8"))
                        query = data.get(query_field, "").strip()

                    if not query:
                        continue

                    cache_key = f"{domain_folder}/{paper_folder}/{provider}/{condition}"
                    print(f"  {provider:6s}/{condition[:8]} {paper_folder} ...", end=" ", flush=True)

                    if refresh or cache_key not in cache:
                        try:
                            cache[cache_key] = fetch_api(
                                query, gold_pmids,
                                domain_folder, paper_folder, provider, condition,
                            )
                            save_cache(cache)
                            print("(API)", end=" ", flush=True)
                        except Exception as e:
                            print(f"ERR: {e}")
                            rows.append({
                                "domain_folder": domain_folder, "paper_folder": paper_folder,
                                "provider": provider, "condition": condition,
                                "method_label": f"{provider}::{condition}",
                                "query_length": len(query), "raw_query_length": len(query),
                                "gold_count": len(gold_pmids),
                                "total_hits": -1, "hit_gold_count": -1, "recall": None,
                                "status": "error", "error_note": str(e),
                                "source_path": rel_public_path(src),
                            })
                            continue
                    else:
                        print("(cache)", end=" ", flush=True)

                    m = compute_metrics(cache[cache_key], gold_pmids)
                    rows.append({
                        "domain_folder": domain_folder, "paper_folder": paper_folder,
                        "provider": provider, "condition": condition,
                        "method_label": f"{provider}::{condition}",
                        "query_length": len(query), "raw_query_length": len(query),
                        "gold_count": len(gold_pmids), "source_path": rel_public_path(src),
                        **m,
                    })
                    print(f"hits={m['total_hits']} recall={m['recall']:.3f}")

    return rows


# ── Output ────────────────────────────────────────────────────────────────────

FIELDNAMES = [
    "domain_folder", "paper_folder", "provider", "condition", "method_label",
    "query_length", "raw_query_length", "total_hits", "hit_gold_count",
    "gold_count", "recall", "status", "error_note", "source_path",
]


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows → {path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true",
                        help="Re-query PubMed API even if cache entry exists")
    args = parser.parse_args()

    print(f"Test data: {TEST_DATA}")
    print(f"Output:    {OUT_DIR}")
    print(f"Cache:     {CACHE_FILE}")
    print(f"Mode:      {'--refresh (API)' if args.refresh else 'cache-first'}")
    print()

    cache = load_cache()
    print(f"Loaded {len(cache)} cached entries.")
    print()

    rows = collect_rows(TEST_DATA, cache, refresh=args.refresh)

    all_metrics_path = OUT_DIR / "all_test_metrics.csv"
    write_csv(all_metrics_path, rows)

    without_laws_rows = [r for r in rows if r["condition"] == "without_laws"]
    without_laws_path = OUT_DIR / "test24_without_laws_all_providers.csv"
    write_csv(without_laws_path, without_laws_rows)

    print()
    print(f"Done. Total rows: {len(rows)}, without_laws rows: {len(without_laws_rows)}")


if __name__ == "__main__":
    main()
