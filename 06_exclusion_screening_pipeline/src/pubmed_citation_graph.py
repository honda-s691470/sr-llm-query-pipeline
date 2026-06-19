"""
PubMed citation graph utilities.

Supports:
- refs:    pubmed_pubmed_refs    (paper -> references)
- citedin: pubmed_pubmed_citedin (citing papers -> paper)

Key design:
- Use repeated `id` params (id=1&id=2...) to preserve one-to-one mapping.
- Detect grouped/incomplete responses and fallback to per-ID calls.
- Optional re-fetch rounds for cached-empty refs/citedin entries.
"""
from __future__ import annotations

import json
import logging
import random
import re
import time
from datetime import datetime, timezone
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ELINK_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"
ICITE_PUBS_URL = "https://icite.od.nih.gov/api/pubs"
OPENALEX_WORKS_URL = "https://api.openalex.org/works"
ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
_MIN_INTERVAL = 0.35
_last_call: float = 0.0


def _throttle() -> None:
    global _last_call
    elapsed = time.time() - _last_call
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _last_call = time.time()


def _sleep_with_jitter(base_seconds: float) -> None:
    time.sleep(max(0.0, base_seconds + random.uniform(0.0, 0.7)))


def _load_usage_counter(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _save_usage_counter(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def _utc_date_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _post(url: str, params: dict[str, Any], retries: int = 8) -> str:
    # doseq=True is required to support repeated id parameters:
    # id=123&id=456&id=789
    # This preserves one-to-one input/output mapping in ELink.
    data = urllib.parse.urlencode(params, doseq=True).encode("utf-8")
    for attempt in range(retries):
        _throttle()
        try:
            req = urllib.request.Request(url, data=data, method="POST")
            with urllib.request.urlopen(req, timeout=180) as resp:
                return resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            code = getattr(e, "code", None)
            logger.warning("ELink POST error (attempt %d/%d, code=%s): %s", attempt + 1, retries, code, e)
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
            logger.warning("ELink POST error (attempt %d/%d): %s", attempt + 1, retries, e)
            if attempt < retries - 1:
                if "429" in str(e):
                    _sleep_with_jitter(min(60.0, 2.0 ** (attempt + 1)))
                else:
                    _sleep_with_jitter(min(30.0, 2.0 ** attempt))
    raise RuntimeError(f"ELink POST failed after {retries} retries: {url}")


def _get_json(url: str, params: dict[str, Any], retries: int = 8, min_interval: float = 0.35) -> Any:
    global _last_call
    q = urllib.parse.urlencode(params, doseq=True)
    full = f"{url}?{q}" if q else url
    for attempt in range(retries):
        elapsed = time.time() - _last_call
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        _last_call = time.time()
        try:
            req = urllib.request.Request(full, method="GET")
            with urllib.request.urlopen(req, timeout=180) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            code = getattr(e, "code", None)
            logger.warning("GET JSON error (attempt %d/%d, code=%s): %s", attempt + 1, retries, code, e)
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
            logger.warning("GET JSON error (attempt %d/%d): %s", attempt + 1, retries, e)
            if attempt < retries - 1:
                if "429" in str(e):
                    _sleep_with_jitter(min(60.0, 2.0 ** (attempt + 1)))
                else:
                    _sleep_with_jitter(min(30.0, 2.0 ** attempt))
    raise RuntimeError(f"GET JSON failed after {retries} retries: {full}")


def _load_cache(cache_file: Path) -> dict[str, list[str]]:
    if not cache_file.exists():
        return {}
    try:
        obj = json.loads(cache_file.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(obj, dict):
        return {}
    out: dict[str, list[str]] = {}
    for k, v in obj.items():
        if isinstance(v, list):
            out[str(k).strip()] = [str(x).strip() for x in v if str(x).strip()]
    return out


def _save_cache(cache_file: Path, cache_map: dict[str, list[str]]) -> None:
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(cache_map, ensure_ascii=False), encoding="utf-8")


def _parse_elink_links(xml_text: str, linkname: str) -> tuple[dict[str, list[str]], int]:
    root = ET.fromstring(xml_text)
    out: dict[str, list[str]] = {}
    multi_id_linkset_count = 0
    for link_set in root.findall(".//LinkSet"):
        src_ids = [x.text.strip() for x in link_set.findall("./IdList/Id") if x.text and x.text.strip()]
        if not src_ids:
            continue
        if len(src_ids) > 1:
            multi_id_linkset_count += 1
        refs: list[str] = []
        for ldb in link_set.findall("./LinkSetDb"):
            # We request a fixed linkname, but keep defensive checks.
            lnk_name = (ldb.findtext("LinkName") or "").strip()
            if lnk_name and lnk_name != linkname:
                continue
            for lk in ldb.findall("./Link/Id"):
                if lk.text and lk.text.strip():
                    refs.append(lk.text.strip())
        # preserve order while deduplicating
        seen = set()
        uniq = []
        for r in refs:
            if r not in seen:
                seen.add(r)
                uniq.append(r)
        for src in src_ids:
            # For one-to-one requests this is exactly one source PMID.
            # If upstream unexpectedly returns grouped IdList, this keeps keys complete;
            # caller will detect grouped-linksets and fall back to per-ID calls.
            out[src] = uniq
    return out, multi_id_linkset_count


def fetch_pubmed_link_map(
    pmids: list[str],
    cache_file: Path,
    linkname: str,
    batch_size: int = 200,
    email: str | None = None,
    api_key: str | None = None,
    max_calls: int | None = None,
    refresh_empty_rounds: int = 0,
) -> tuple[dict[str, list[str]], int]:
    """
    Return PMID -> linked PMIDs for given ELink linkname.
    Also returns number of API calls used in this run.
    """
    norm_pmids = [str(p).strip() for p in pmids if str(p).strip()]
    if not norm_pmids:
        return {}, 0

    cache = _load_cache(cache_file)
    missing = [p for p in norm_pmids if p not in cache]
    used_calls = 0

    if missing:
        logger.info("Citation cache miss (%s): %d / %d PMIDs", linkname, len(missing), len(norm_pmids))

    for i in range(0, len(missing), batch_size):
        if max_calls is not None and used_calls >= max_calls:
            logger.warning("Reached max_calls=%d. Remaining PMIDs will stay uncached.", max_calls)
            break
        batch = missing[i : i + batch_size]
        params = {
            "dbfrom": "pubmed",
            # Repeated id parameters preserve one-to-one mapping in ELink.
            "id": batch,
            "linkname": linkname,
            "retmode": "xml",
        }
        if email:
            params["email"] = email
        if api_key:
            params["api_key"] = api_key
        raw = _post(ELINK_URL, params)
        used_calls += 1
        parsed, multi_linkset = _parse_elink_links(raw, linkname=linkname)

        batch_set = set(batch)
        parsed_keys = set(parsed.keys())
        missing_ids = sorted(batch_set - parsed_keys)
        need_fallback = (multi_linkset > 0) or bool(missing_ids)

        if need_fallback:
            logger.warning(
                "ELink batch returned grouped/incomplete mapping (multi_linkset=%d, parsed=%d, batch=%d, missing=%d). "
                "Running per-ID fallback.",
                multi_linkset,
                len(parsed_keys),
                len(batch_set),
                len(missing_ids),
            )
            # If grouped linkset detected, fallback all IDs in batch.
            # If only some IDs are missing, fallback those missing IDs only.
            fallback_targets = batch if multi_linkset > 0 else missing_ids
            for p in fallback_targets:
                if max_calls is not None and used_calls >= max_calls:
                    logger.warning("Reached max_calls=%d during per-ID fallback.", max_calls)
                    break
                single_params = {
                    "dbfrom": "pubmed",
                    "id": [p],
                    "linkname": linkname,
                    "retmode": "xml",
                }
                if email:
                    single_params["email"] = email
                if api_key:
                    single_params["api_key"] = api_key
                sraw = _post(ELINK_URL, single_params)
                used_calls += 1
                sparsed, _ = _parse_elink_links(sraw, linkname=linkname)
                cache[p] = sparsed.get(p, [])
            # For parsed IDs not requiring fallback, keep parsed results.
            for p in batch:
                if p not in cache:
                    cache[p] = parsed.get(p, [])
        else:
            for p in batch:
                cache[p] = parsed.get(p, [])
        if (i // batch_size + 1) % 10 == 0:
            _save_cache(cache_file, cache)

    # Optional refresh rounds for cached-empty entries (to reduce transient empty-link misses).
    # This does not forcefully make missing links appear, but recovers unstable/partial responses.
    for rr in range(max(0, refresh_empty_rounds)):
        empties = [p for p in norm_pmids if p in cache and len(cache.get(p, [])) == 0]
        if not empties:
            break
        logger.info("Empty-link refresh round %d (%s): %d PMIDs", rr + 1, linkname, len(empties))
        for p in empties:
            if max_calls is not None and used_calls >= max_calls:
                logger.warning("Reached max_calls=%d during refresh rounds.", max_calls)
                break
            single_params = {
                "dbfrom": "pubmed",
                "id": [p],
                "linkname": linkname,
                "retmode": "xml",
            }
            if email:
                single_params["email"] = email
            if api_key:
                single_params["api_key"] = api_key
            sraw = _post(ELINK_URL, single_params)
            used_calls += 1
            sparsed, _ = _parse_elink_links(sraw, linkname=linkname)
            cache[p] = sparsed.get(p, [])
        _save_cache(cache_file, cache)

    _save_cache(cache_file, cache)
    out = {p: cache.get(p, []) for p in norm_pmids}
    return out, used_calls


def fetch_pubmed_refs_map(
    pmids: list[str],
    cache_file: Path,
    batch_size: int = 200,
    email: str | None = None,
    api_key: str | None = None,
    max_calls: int | None = None,
    refresh_empty_rounds: int = 0,
) -> tuple[dict[str, list[str]], int]:
    return fetch_pubmed_link_map(
        pmids=pmids,
        cache_file=cache_file,
        linkname="pubmed_pubmed_refs",
        batch_size=batch_size,
        email=email,
        api_key=api_key,
        max_calls=max_calls,
        refresh_empty_rounds=refresh_empty_rounds,
    )


def fetch_pubmed_citedin_map(
    pmids: list[str],
    cache_file: Path,
    batch_size: int = 200,
    email: str | None = None,
    api_key: str | None = None,
    max_calls: int | None = None,
    refresh_empty_rounds: int = 0,
) -> tuple[dict[str, list[str]], int]:
    return fetch_pubmed_link_map(
        pmids=pmids,
        cache_file=cache_file,
        linkname="pubmed_pubmed_citedin",
        batch_size=batch_size,
        email=email,
        api_key=api_key,
        max_calls=max_calls,
        refresh_empty_rounds=refresh_empty_rounds,
    )


def fetch_icite_refs_map(
    pmids: list[str],
    cache_file: Path,
    batch_size: int = 200,
    max_calls: int | None = None,
    calls_per_day: int = 10000,
    req_per_sec: float = 3.0,
    usage_file: Path | None = None,
) -> tuple[dict[str, list[str]], int]:
    """
    Fetch PMID -> references (PMIDs) from NIH iCite/OCC endpoint.

    Guards:
    - req_per_sec: API request rate cap.
    - calls_per_day: daily call cap (UTC day), tracked in usage_file.
    """
    norm_pmids = [str(p).strip() for p in pmids if str(p).strip()]
    if not norm_pmids:
        return {}, 0
    cache = _load_cache(cache_file)
    missing = [p for p in norm_pmids if p not in cache]
    used_calls = 0

    if usage_file is None:
        usage_file = cache_file.with_name(cache_file.stem + "_usage.json")
    usage = _load_usage_counter(usage_file)
    today = _utc_date_str()
    if usage.get("date") != today:
        usage = {"date": today, "calls": 0}
    day_calls = int(usage.get("calls", 0))
    min_interval = 1.0 / max(0.01, float(req_per_sec))

    if missing:
        logger.info("iCite refs cache miss: %d / %d PMIDs", len(missing), len(norm_pmids))

    for i in range(0, len(missing), batch_size):
        if max_calls is not None and used_calls >= max_calls:
            logger.warning("Reached iCite max_calls=%d. Remaining PMIDs stay uncached.", max_calls)
            break
        if calls_per_day > 0 and day_calls >= calls_per_day:
            logger.warning("Reached iCite calls_per_day=%d (UTC). Stop for today.", calls_per_day)
            break

        batch = missing[i : i + batch_size]
        obj = _get_json(ICITE_PUBS_URL, {"pmids": ",".join(batch)}, min_interval=min_interval)
        used_calls += 1
        day_calls += 1

        recs: list[dict[str, Any]] = []
        if isinstance(obj, dict):
            if isinstance(obj.get("data"), list):
                recs = [x for x in obj["data"] if isinstance(x, dict)]
            else:
                recs = [obj]
        elif isinstance(obj, list):
            recs = [x for x in obj if isinstance(x, dict)]

        found_keys: set[str] = set()
        for rec in recs:
            pmid = str(rec.get("pmid", "")).strip()
            if not pmid:
                continue
            refs = rec.get("references")
            if not isinstance(refs, list):
                refs = rec.get("citedPmids")
            if not isinstance(refs, list):
                refs = []
            out = [str(x).strip() for x in refs if str(x).strip()]
            # deduplicate while preserving order
            seen = set()
            uniq: list[str] = []
            for x in out:
                if x not in seen:
                    seen.add(x)
                    uniq.append(x)
            cache[pmid] = uniq
            found_keys.add(pmid)

        # ensure queried PMIDs are marked in cache (empty if absent in response)
        for p in batch:
            if p not in found_keys and p not in cache:
                cache[p] = []

        if (i // batch_size + 1) % 10 == 0:
            _save_cache(cache_file, cache)
            usage["calls"] = day_calls
            usage["date"] = today
            _save_usage_counter(usage_file, usage)

    _save_cache(cache_file, cache)
    usage["calls"] = day_calls
    usage["date"] = today
    _save_usage_counter(usage_file, usage)
    out = {p: cache.get(p, []) for p in norm_pmids}
    return out, used_calls


def _parse_openalex_pmid_from_obj(work_obj: dict[str, Any]) -> str:
    ids = work_obj.get("ids")
    if not isinstance(ids, dict):
        return ""
    pm = ids.get("pmid")
    if not pm:
        return ""
    s = str(pm).strip()
    m = re.search(r"(\d+)", s)
    return m.group(1) if m else ""


def fetch_openalex_refs_map(
    pmids: list[str],
    cache_file: Path,
    work_cache_file: Path,
    batch_size: int = 50,
    max_calls: int | None = None,
    calls_per_day: int = 100000,
    req_per_sec: float = 5.0,
    usage_file: Path | None = None,
    mailto: str | None = None,
) -> tuple[dict[str, list[str]], int]:
    """
    Fetch PMID -> references (PMIDs) from OpenAlex.

    Strategy:
    - Query source work by ids.pmid:<PMID>
    - Convert referenced_works (OpenAlex IDs) to PMIDs using ids.openalex filter (batched)
    - Cache both PMID->refs and OpenAlexID->PMID mappings
    """
    norm_pmids = [str(p).strip() for p in pmids if str(p).strip()]
    if not norm_pmids:
        return {}, 0
    cache = _load_cache(cache_file)
    missing = [p for p in norm_pmids if p not in cache]
    used_calls = 0

    # OpenAlex-ID -> PMID (or empty string when unresolved)
    work_cache_raw = _load_usage_counter(work_cache_file)
    work_cache: dict[str, str] = {}
    if isinstance(work_cache_raw, dict):
        for k, v in work_cache_raw.items():
            if isinstance(v, str):
                work_cache[str(k).strip()] = v.strip()

    if usage_file is None:
        usage_file = cache_file.with_name(cache_file.stem + "_usage.json")
    usage = _load_usage_counter(usage_file)
    today = _utc_date_str()
    if usage.get("date") != today:
        usage = {"date": today, "calls": 0}
    day_calls = int(usage.get("calls", 0))
    min_interval = 1.0 / max(0.01, float(req_per_sec))

    if missing:
        logger.info("OpenAlex refs cache miss: %d / %d PMIDs", len(missing), len(norm_pmids))

    resolve_queue: set[str] = set()
    pending_refs: dict[str, list[str]] = {}

    def maybe_stop() -> bool:
        if max_calls is not None and used_calls >= max_calls:
            logger.warning("Reached OpenAlex max_calls=%d. Remaining PMIDs stay uncached.", max_calls)
            return True
        if calls_per_day > 0 and day_calls >= calls_per_day:
            logger.warning("Reached OpenAlex calls_per_day=%d (UTC). Stop for today.", calls_per_day)
            return True
        return False

    for i in range(0, len(missing), batch_size):
        if maybe_stop():
            break
        batch = missing[i : i + batch_size]

        for p in batch:
            if maybe_stop():
                break
            params = {"filter": f"ids.pmid:{p}", "per-page": 1}
            if mailto:
                params["mailto"] = mailto
            obj = _get_json(OPENALEX_WORKS_URL, params, min_interval=min_interval)
            used_calls += 1
            day_calls += 1

            results = obj.get("results", []) if isinstance(obj, dict) else []
            if not isinstance(results, list) or not results:
                cache[p] = []
                continue
            work = results[0] if isinstance(results[0], dict) else {}
            refs = work.get("referenced_works", [])
            if not isinstance(refs, list):
                refs = []
            refs = [str(x).strip() for x in refs if str(x).strip()]
            pending_refs[p] = refs
            for wid in refs:
                if wid not in work_cache:
                    resolve_queue.add(wid)

        # Resolve new referenced OpenAlex IDs -> PMID in chunks
        unresolved = sorted(resolve_queue)
        for j in range(0, len(unresolved), 50):
            if maybe_stop():
                break
            chunk = unresolved[j : j + 50]
            if not chunk:
                continue
            # ids.openalex supports OR by pipe
            filt = "ids.openalex:" + "|".join(chunk)
            params = {"filter": filt, "per-page": len(chunk)}
            if mailto:
                params["mailto"] = mailto
            obj = _get_json(OPENALEX_WORKS_URL, params, min_interval=min_interval)
            used_calls += 1
            day_calls += 1
            results = obj.get("results", []) if isinstance(obj, dict) else []
            returned: set[str] = set()
            if isinstance(results, list):
                for it in results:
                    if not isinstance(it, dict):
                        continue
                    wid = str(it.get("id", "")).strip()
                    if not wid:
                        continue
                    returned.add(wid)
                    work_cache[wid] = _parse_openalex_pmid_from_obj(it)
            for wid in chunk:
                if wid not in returned and wid not in work_cache:
                    work_cache[wid] = ""

        # materialize current batch into PMID refs
        for p in batch:
            if p in cache:
                continue
            refs_ids = pending_refs.get(p, [])
            refs_pmids: list[str] = []
            seen = set()
            for wid in refs_ids:
                rp = work_cache.get(wid, "")
                if rp and rp not in seen and rp != p:
                    seen.add(rp)
                    refs_pmids.append(rp)
            cache[p] = refs_pmids

        resolve_queue.clear()
        pending_refs.clear()

        if (i // batch_size + 1) % 5 == 0:
            _save_cache(cache_file, cache)
            _save_usage_counter(work_cache_file, work_cache)
            usage["calls"] = day_calls
            usage["date"] = today
            _save_usage_counter(usage_file, usage)

    _save_cache(cache_file, cache)
    _save_usage_counter(work_cache_file, work_cache)
    usage["calls"] = day_calls
    usage["date"] = today
    _save_usage_counter(usage_file, usage)
    out = {p: cache.get(p, []) for p in norm_pmids}
    return out, used_calls


def merge_refs_preferring_pubmed(
    pmids: list[str],
    pubmed_refs_map: dict[str, list[str]],
    fallback_refs_map: dict[str, list[str]],
) -> tuple[dict[str, list[str]], int]:
    """
    Fill only PubMed-empty refs with fallback refs.
    Returns merged map and count of PMIDs recovered from empty->non-empty.
    """
    out: dict[str, list[str]] = {}
    recovered = 0
    for p in pmids:
        base = list(pubmed_refs_map.get(p, []))
        if base:
            out[p] = base
            continue
        fb = list(fallback_refs_map.get(p, []))
        out[p] = fb
        if fb:
            recovered += 1
    return out, recovered


def _parse_pub_year_from_esummary_item(item: dict[str, Any]) -> int | None:
    cand = []
    for k in ("pubdate", "sortpubdate", "epubdate", "pdat"):
        v = item.get(k)
        if v:
            cand.append(str(v))
    for s in cand:
        m = re.search(r"(19|20)\d{2}", s)
        if m:
            y = int(m.group(0))
            if 1800 <= y <= 2100:
                return y
    return None


def fetch_pubmed_year_map(
    pmids: list[str],
    cache_file: Path,
    batch_size: int = 200,
    email: str | None = None,
    api_key: str | None = None,
    max_calls: int | None = None,
) -> tuple[dict[str, int | None], int]:
    """
    Fetch PMID -> publication year (int or None) using PubMed ESummary.
    Cached to avoid repeated requests.
    """
    norm_pmids = [str(p).strip() for p in pmids if str(p).strip()]
    if not norm_pmids:
        return {}, 0

    raw_cache = _load_usage_counter(cache_file)
    cache: dict[str, int | None] = {}
    if isinstance(raw_cache, dict):
        for k, v in raw_cache.items():
            kk = str(k).strip()
            if isinstance(v, int):
                cache[kk] = v
            else:
                cache[kk] = None

    missing = [p for p in norm_pmids if p not in cache]
    used_calls = 0
    if missing:
        logger.info("PubYear cache miss: %d / %d PMIDs", len(missing), len(norm_pmids))

    for i in range(0, len(missing), batch_size):
        if max_calls is not None and used_calls >= max_calls:
            logger.warning("Reached year max_calls=%d. Remaining PMIDs stay uncached.", max_calls)
            break
        batch = missing[i : i + batch_size]
        params: dict[str, Any] = {
            "db": "pubmed",
            "id": ",".join(batch),
            "retmode": "json",
        }
        if email:
            params["email"] = email
        if api_key:
            params["api_key"] = api_key
        obj = _get_json(ESUMMARY_URL, params, min_interval=0.12)
        used_calls += 1
        if not isinstance(obj, dict):
            for p in batch:
                cache[p] = None
            continue
        result = obj.get("result", {})
        if not isinstance(result, dict):
            for p in batch:
                cache[p] = None
            continue
        for p in batch:
            it = result.get(p)
            if not isinstance(it, dict):
                cache[p] = None
                continue
            cache[p] = _parse_pub_year_from_esummary_item(it)

        if (i // batch_size + 1) % 10 == 0:
            _save_usage_counter(cache_file, cache)

    _save_usage_counter(cache_file, cache)
    out = {p: cache.get(p) for p in norm_pmids}
    return out, used_calls


def build_internal_edges(pmids: list[str], refs_map: dict[str, list[str]]) -> list[tuple[str, str]]:
    """
    Build directed edges among pmids using references:
      source -> target, if source cites target and target is in candidate set.
    """
    cand = set(pmids)
    edges: list[tuple[str, str]] = []
    for s in pmids:
        refs = refs_map.get(s, [])
        for t in refs:
            if t in cand and t != s:
                edges.append((s, t))
    return edges


def build_internal_edges_with_citedin(
    pmids: list[str],
    refs_map: dict[str, list[str]],
    citedin_map: dict[str, list[str]],
) -> list[tuple[str, str]]:
    """
    Build directed internal edges using both refs and citedin.

    refs edge:
      s -> t, if s cites t.
    citedin edge:
      c -> s, if c cites s.
    """
    cand = set(pmids)
    edges: set[tuple[str, str]] = set()

    for s in pmids:
        for t in refs_map.get(s, []):
            if t in cand and t != s:
                edges.add((s, t))

    for s in pmids:
        for c in citedin_map.get(s, []):
            if c in cand and c != s:
                edges.add((c, s))

    return list(edges)
