"""
PubMed E-utilities helper for the exclusion screening pipeline.

Fetch strategy (efficiency-optimized):
  Stage A  → esearch (get PMIDs + total count)
  Stage B  → esummary (pub_type / language metadata only; lightweight)
  Stage C  → no fetch (ranking on data already in hand)
  Stage D  → efetch XML (title + abstract for candidates_C only, ≤K records)
"""
from __future__ import annotations
import json
import time
import random
from pathlib import Path
import xml.etree.ElementTree as ET
import urllib.request
import urllib.parse
import urllib.error
import logging

logger = logging.getLogger(__name__)

ESEARCH_URL  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
EFETCH_URL   = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

_MIN_INTERVAL = 0.35   # seconds between requests (NCBI: 3/s without API key)
_last_call: float = 0.0


def _normalize_pmid(pmid: str) -> str:
    return str(pmid).strip()


def _load_cache(cache_file: Path) -> dict[str, dict]:
    if not cache_file.exists():
        return {}
    try:
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def _save_cache(cache_file: Path, cache_map: dict[str, dict]) -> None:
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(
        json.dumps(cache_map, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _throttle() -> None:
    global _last_call
    elapsed = time.time() - _last_call
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _last_call = time.time()


def _sleep_with_jitter(base_seconds: float) -> None:
    # Add small jitter to avoid synchronized retry storms against NCBI.
    time.sleep(max(0.0, base_seconds + random.uniform(0.0, 0.7)))


def _get(url: str, params: dict, retries: int = 8) -> str:
    """GET for small requests; auto-switches to POST if id list is large."""
    id_str = params.get("id", "")
    # Use POST if the id list would make URL too long (>200 PMIDs)
    if id_str and id_str.count(",") >= 199:
        return _post(url, params, retries)
    query = urllib.parse.urlencode(params)
    full_url = f"{url}?{query}"
    for attempt in range(retries):
        _throttle()
        try:
            with urllib.request.urlopen(full_url, timeout=60) as resp:
                return resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            code = getattr(e, "code", None)
            logger.warning("HTTP error (attempt %d/%d, code=%s): %s", attempt + 1, retries, code, e)
            if attempt < retries - 1:
                if code == 429:
                    retry_after = e.headers.get("Retry-After") if getattr(e, "headers", None) else None
                    if retry_after and str(retry_after).isdigit():
                        _sleep_with_jitter(float(retry_after))
                    else:
                        _sleep_with_jitter(min(60.0, 2.0 ** (attempt + 1)))
                else:
                    _sleep_with_jitter(min(30.0, 2.0 ** attempt))
                continue
        except Exception as e:
            logger.warning("HTTP error (attempt %d/%d): %s", attempt + 1, retries, e)
            if attempt < retries - 1:
                if "429" in str(e):
                    _sleep_with_jitter(min(60.0, 2.0 ** (attempt + 1)))
                else:
                    _sleep_with_jitter(min(30.0, 2.0 ** attempt))
    raise RuntimeError(f"Failed after {retries} retries: {full_url}")


def _post(url: str, params: dict, retries: int = 8) -> str:
    """POST request (for large id lists to avoid HTTP 414)."""
    data = urllib.parse.urlencode(params).encode("utf-8")
    for attempt in range(retries):
        _throttle()
        try:
            req = urllib.request.Request(url, data=data, method="POST")
            with urllib.request.urlopen(req, timeout=300) as resp:
                return resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            code = getattr(e, "code", None)
            logger.warning("POST error (attempt %d/%d, code=%s): %s", attempt + 1, retries, code, e)
            if attempt < retries - 1:
                if code == 429:
                    retry_after = e.headers.get("Retry-After") if getattr(e, "headers", None) else None
                    if retry_after and str(retry_after).isdigit():
                        _sleep_with_jitter(float(retry_after))
                    else:
                        _sleep_with_jitter(min(60.0, 2.0 ** (attempt + 1)))
                else:
                    _sleep_with_jitter(min(30.0, 2.0 ** attempt))
                continue
        except Exception as e:
            logger.warning("POST error (attempt %d/%d): %s", attempt + 1, retries, e)
            if attempt < retries - 1:
                if "429" in str(e):
                    _sleep_with_jitter(min(60.0, 2.0 ** (attempt + 1)))
                else:
                    _sleep_with_jitter(min(30.0, 2.0 ** attempt))
    raise RuntimeError(f"POST failed after {retries} retries: {url}")


# ─────────────────────────────────────────────
# Stage A: esearch
# ─────────────────────────────────────────────

def search_pubmed(
    query: str,
    retmax: int = 100_000,
    sort: str = "relevance",
) -> tuple[int, list[str]]:
    """
    Run esearch. Returns (total_count, pmid_list).
    PMIDs are sorted by PubMed relevance (default) unless sort="date".
    retmax is capped at 100,000 (PubMed hard limit per call).
    """
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": min(retmax, 100_000),
        "retmode": "json",
        "sort": sort,
        "usehistory": "n",
    }
    raw = _get(ESEARCH_URL, params)
    data = json.loads(raw)
    result = data.get("esearchresult", {})
    total = int(result.get("count", 0))
    pmids = result.get("idlist", [])
    return total, pmids


# ─────────────────────────────────────────────
# Stage B: esummary (metadata only — lightweight)
# ─────────────────────────────────────────────

def fetch_metadata_batch(pmids: list[str]) -> list[dict]:
    """
    Fetch pub_type + language for a batch of PMIDs via esummary (JSON).
    Returns list of dicts: {pmid, pub_types, languages}.
    NO abstract content fetched here.
    """
    if not pmids:
        return []

    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "json",
    }
    raw = _get(ESUMMARY_URL, params)
    try:
        data = json.loads(raw)
    except Exception as e:
        logger.error("JSON parse error in esummary: %s", e)
        return []

    records: list[dict] = []
    result = data.get("result", {})
    for pmid in pmids:
        doc = result.get(pmid)
        if not isinstance(doc, dict):
            # Missing or non-dict entry: conservative keep
            records.append({"pmid": pmid, "pub_types": [], "languages": [], "title": ""})
            continue
        # pubtype is list of dicts {"value": "...", "uid": "..."} or occasionally strings
        raw_pubtypes = doc.get("pubtype", [])
        pub_types: list[str] = []
        for pt in raw_pubtypes:
            if isinstance(pt, dict):
                v = pt.get("value", "")
                if v:
                    pub_types.append(v)
            elif isinstance(pt, str) and pt:
                pub_types.append(pt)
        # lang is a list of strings in esummary JSON (e.g. ["eng"])
        lang_raw = doc.get("lang", [])
        if isinstance(lang_raw, list):
            langs = [l for l in lang_raw if isinstance(l, str) and l]
        elif isinstance(lang_raw, str):
            langs = [lang_raw] if lang_raw else []
        else:
            langs = []
        title = doc.get("title", "")
        records.append({
            "pmid": pmid,
            "pub_types": pub_types,
            "languages": langs,
            "title": title,
            "species_mesh": [],  # not available from esummary; Stage B animal filter uses Stage A NOT
        })
    return records


def fetch_all_metadata(
    pmids: list[str],
    batch_size: int = 500,
    progress_every: int = 5000,
    auto_tune: bool = False,
    benchmark_sample_size: int = 1000,
    cache_file: str | None = None,
) -> list[dict]:
    """Fetch metadata for all PMIDs in batches (esummary, no abstracts)."""
    if not pmids:
        return []

    cache_path = Path(cache_file) if cache_file else None
    cache_map: dict[str, dict] = _load_cache(cache_path) if cache_path else {}
    need_fetch: list[str] = []
    records_from_cache: list[dict] = []

    for p in pmids:
        pid = _normalize_pmid(p)
        if pid in cache_map:
            rec = cache_map[pid]
            records_from_cache.append({
                "pmid": pid,
                "pub_types": rec.get("pub_types", []),
                "languages": rec.get("languages", []),
                "title": rec.get("title", ""),
                "species_mesh": rec.get("species_mesh", []),
            })
        else:
            need_fetch.append(pid)

    if records_from_cache:
        logger.info("Stage B cache hit: %d / %d metadata records", len(records_from_cache), len(pmids))

    if not need_fetch:
        # Preserve input PMID order
        by_id = {r["pmid"]: r for r in records_from_cache}
        return [by_id[_normalize_pmid(p)] for p in pmids if _normalize_pmid(p) in by_id]

    if auto_tune and len(pmids) >= 500:
        tuned = benchmark_esummary_batch_size(
            pmids=need_fetch,
            candidates=[50, 100, 200, 300, 500],
            sample_size=benchmark_sample_size,
        )
        if tuned:
            logger.info("Stage B auto-tuned batch_size: %d -> %d", batch_size, tuned)
            batch_size = tuned

    fetched_records: list[dict] = []
    total = len(need_fetch)
    for i in range(0, total, batch_size):
        batch = need_fetch[i : i + batch_size]
        t0 = time.time()
        try:
            records = fetch_metadata_batch(batch)
        except Exception as e:
            logger.error("Stage B metadata batch failed [%d:%d]: %s", i, i + len(batch), e)
            # Graceful fallback: keep all records in this batch with empty metadata.
            records = [{"pmid": p, "pub_types": [], "languages": [], "title": "", "species_mesh": []} for p in batch]
        elapsed = time.time() - t0
        fetched_records.extend(records)
        done = min(i + batch_size, total)
        logger.info(
            "Stage B batch done: %d/%d records (batch=%d, %.2fs, %.1f rec/s)",
            done,
            total,
            len(batch),
            elapsed,
            (len(batch) / elapsed) if elapsed > 0 else 0.0,
        )
        if done % progress_every < batch_size or done == total:
            logger.info("Fetched metadata %d / %d", done, total)

    # Upsert cache with fetched metadata
    if cache_path:
        for r in fetched_records:
            pid = _normalize_pmid(r.get("pmid", ""))
            if not pid:
                continue
            prev = cache_map.get(pid, {})
            cache_map[pid] = {
                **prev,
                "pmid": pid,
                "title": r.get("title", prev.get("title", "")),
                "pub_types": r.get("pub_types", prev.get("pub_types", [])),
                "languages": r.get("languages", prev.get("languages", [])),
                "species_mesh": r.get("species_mesh", prev.get("species_mesh", [])),
                "abstract": prev.get("abstract", ""),
            }
        _save_cache(cache_path, cache_map)

    # Merge fetched + cached and preserve input order
    merged = records_from_cache + fetched_records
    by_id = {_normalize_pmid(r.get("pmid", "")): r for r in merged}
    return [by_id[_normalize_pmid(p)] for p in pmids if _normalize_pmid(p) in by_id]


def benchmark_esummary_batch_size(
    pmids: list[str],
    candidates: list[int] | None = None,
    sample_size: int = 1000,
) -> int | None:
    """
    Lightweight throughput benchmark for esummary batch sizes.
    Returns best batch size by records/sec, or None on failure.
    """
    if not pmids:
        return None
    if not candidates:
        candidates = [50, 100, 200, 300, 500]

    sample = pmids[: min(sample_size, len(pmids))]
    scores: dict[int, float] = {}

    for bs in candidates:
        times: list[float] = []
        counts: list[int] = []
        # Benchmark first up to 3 batches per candidate to limit cost.
        for i in range(0, min(len(sample), bs * 3), bs):
            batch = sample[i : i + bs]
            t0 = time.time()
            try:
                _ = fetch_metadata_batch(batch)
                dt = max(time.time() - t0, 1e-6)
                times.append(dt)
                counts.append(len(batch))
            except Exception as e:
                logger.warning("Benchmark failed for batch_size=%d: %s", bs, e)
                times = []
                break

        if times and counts:
            rps = sum(counts) / sum(times)
            scores[bs] = rps
            logger.info("esummary benchmark batch_size=%d -> %.2f rec/s", bs, rps)

    if not scores:
        return None
    best = max(scores, key=scores.get)
    logger.info("esummary benchmark winner: batch_size=%d (%.2f rec/s)", best, scores[best])
    return best


# ─────────────────────────────────────────────
# Stage D: efetch (title + abstract for candidates only)
# ─────────────────────────────────────────────

def fetch_abstracts_batch(pmids: list[str]) -> list[dict]:
    """
    Fetch title + abstract + pub_types + language for a batch of PMIDs via efetch XML.
    Used for Stage D candidates only (≤K records).
    """
    if not pmids:
        return []

    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "rettype": "abstract",
        "retmode": "xml",
    }
    raw = _get(EFETCH_URL, params)

    records: list[dict] = []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        logger.error("XML parse error in efetch: %s", e)
        return []

    for article in root.findall(".//PubmedArticle"):
        rec = _parse_pubmed_article(article)
        records.append(rec)
    return records


def _parse_pubmed_article(article: ET.Element) -> dict:
    pmid_el = article.find(".//PMID")
    pmid = pmid_el.text if pmid_el is not None else ""

    title_el = article.find(".//ArticleTitle")
    title = "".join(title_el.itertext()) if title_el is not None else ""

    abstract_parts = []
    for ab in article.findall(".//AbstractText"):
        label = ab.get("Label", "")
        text = "".join(ab.itertext())
        if label:
            abstract_parts.append(f"{label}: {text}")
        else:
            abstract_parts.append(text)
    abstract = " ".join(abstract_parts).strip()

    pub_types = [
        pt.text for pt in article.findall(".//PublicationTypeList/PublicationType")
        if pt.text
    ]
    langs = [lg.text for lg in article.findall(".//Language") if lg.text]

    return {
        "pmid": pmid,
        "title": title,
        "abstract": abstract,
        "pub_types": pub_types,
        "species_mesh": [],
        "languages": langs,
    }


def fetch_all_abstracts(
    pmids: list[str],
    batch_size: int = 200,
    cache_file: str | None = None,
) -> list[dict]:
    """Fetch abstracts for all PMIDs in batches (for Stage D candidates only)."""
    if not pmids:
        return []

    cache_path = Path(cache_file) if cache_file else None
    cache_map: dict[str, dict] = _load_cache(cache_path) if cache_path else {}

    records_from_cache: list[dict] = []
    need_fetch: list[str] = []
    for p in pmids:
        pid = _normalize_pmid(p)
        rec = cache_map.get(pid)
        has_title = bool((rec or {}).get("title", "").strip()) if rec else False
        has_abstract = bool((rec or {}).get("abstract", "").strip()) if rec else False
        if rec and has_title and has_abstract:
            records_from_cache.append({
                "pmid": pid,
                "title": rec.get("title", ""),
                "abstract": rec.get("abstract", ""),
                "pub_types": rec.get("pub_types", []),
                "species_mesh": rec.get("species_mesh", []),
                "languages": rec.get("languages", []),
            })
        else:
            need_fetch.append(pid)

    if records_from_cache:
        logger.info("Stage C/D cache hit: %d / %d abstract records", len(records_from_cache), len(pmids))

    fetched_records: list[dict] = []
    total = len(need_fetch)
    for i in range(0, total, batch_size):
        batch = need_fetch[i : i + batch_size]
        records = fetch_abstracts_batch(batch)
        fetched_records.extend(records)
        done = min(i + batch_size, total)
        # Log every batch for abstract fetching (large responses, slow)
        logger.info("Fetched abstracts %d / %d", done, total)
        # Incremental cache save — preserves progress on crash or kill
        if cache_path:
            for r in records:
                pid = _normalize_pmid(r.get("pmid", ""))
                if not pid:
                    continue
                prev = cache_map.get(pid, {})
                cache_map[pid] = {
                    **prev,
                    "pmid": pid,
                    "title": r.get("title", prev.get("title", "")),
                    "abstract": r.get("abstract", prev.get("abstract", "")),
                    "pub_types": r.get("pub_types", prev.get("pub_types", [])),
                    "languages": r.get("languages", prev.get("languages", [])),
                    "species_mesh": r.get("species_mesh", prev.get("species_mesh", [])),
                }
            _save_cache(cache_path, cache_map)

    merged = records_from_cache + fetched_records
    by_id = {_normalize_pmid(r.get("pmid", "")): r for r in merged}
    return [by_id[_normalize_pmid(p)] for p in pmids if _normalize_pmid(p) in by_id]
