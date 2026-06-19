from __future__ import annotations

import argparse
import json
import re
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
CROSSREF_URL = "https://api.crossref.org/works"
USER_AGENT = "OpenScholarPMIDAttach/1.0"
SLEEP_SECONDS = 0.34
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


DOI_RE = re.compile(r"https?://(?:dx\.)?doi\.org/(.+)$", re.IGNORECASE)
WS_RE = re.compile(r"\s+")
PUNCT_RE = re.compile(r"[^a-z0-9]+")
STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "into",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}


@dataclass
class Resolution:
    pmid: str = ""
    method: str = ""
    note: str = ""
    matched_title: str = ""
    matched_pubdate: str = ""
    matched_source: str = ""
    doi: str = ""


def normalize_text(text: str) -> str:
    text = str(text or "")
    text = text.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = PUNCT_RE.sub(" ", text)
    return WS_RE.sub(" ", text).strip()


def quoted_term(text: str) -> str:
    return '"' + str(text).replace('"', "") + '"'


def extract_doi(paper: dict[str, Any]) -> str:
    for key in ("doi", "DOI"):
        if paper.get(key):
            return str(paper[key]).strip()
    url = str(paper.get("url", "") or "").strip()
    m = DOI_RE.match(url)
    if m:
        return m.group(1).strip()
    return ""


def normalize_doi_text(doi: str) -> str:
    text = str(doi or "").strip()
    text = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", text, flags=re.IGNORECASE)
    return text.strip().lower()


def author_surname(name: str) -> str:
    raw = str(name or "").strip()
    if not raw:
        return ""
    if "," in raw:
        return raw.split(",", 1)[0].strip()
    parts = raw.split()
    return parts[-1].strip() if parts else ""


def abstract_snippet(abstract: str, max_tokens: int = 8) -> str:
    norm = normalize_text(abstract)
    if not norm:
        return ""
    tokens = [tok for tok in norm.split() if tok not in STOPWORDS and len(tok) >= 3]
    return " ".join(tokens[:max_tokens]).strip()


class PubMedResolver:
    def __init__(self, sleep_seconds: float = SLEEP_SECONDS) -> None:
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.sleep_seconds = sleep_seconds
        self.search_cache: dict[str, list[str]] = {}
        self.summary_cache: dict[str, dict[str, Any]] = {}
        self.crossref_cache: dict[str, list[dict[str, Any]]] = {}

    def _sleep(self) -> None:
        time.sleep(self.sleep_seconds)

    def _post_with_retry(self, url: str, data: dict[str, Any], timeout: int = 45) -> requests.Response:
        attempt = 0
        while True:
            self._sleep()
            resp = self.session.post(url, data=data, timeout=timeout)
            if resp.status_code not in RETRYABLE_STATUS:
                resp.raise_for_status()
                return resp
            attempt += 1
            if attempt >= 6:
                resp.raise_for_status()
            time.sleep(self.sleep_seconds * (2**attempt))

    def _get_with_retry(self, url: str, timeout: int = 45) -> requests.Response:
        attempt = 0
        while True:
            self._sleep()
            resp = self.session.get(url, timeout=timeout)
            if resp.status_code not in RETRYABLE_STATUS:
                resp.raise_for_status()
                return resp
            attempt += 1
            if attempt >= 6:
                resp.raise_for_status()
            time.sleep(self.sleep_seconds * (2**attempt))

    def esearch(self, term: str, retmax: int = 10) -> list[str]:
        key = f"{term}||{retmax}"
        if key in self.search_cache:
            return self.search_cache[key]
        resp = self._post_with_retry(
            ESEARCH_URL,
            data={"db": "pubmed", "term": term, "retmode": "json", "retmax": retmax},
            timeout=45,
        )
        ids = [str(x) for x in resp.json().get("esearchresult", {}).get("idlist", [])]
        self.search_cache[key] = ids
        return ids

    def esummary_many(self, pmids: list[str]) -> dict[str, dict[str, Any]]:
        missing = [pmid for pmid in pmids if pmid not in self.summary_cache]
        if missing:
            resp = self._post_with_retry(
                ESUMMARY_URL,
                data={"db": "pubmed", "id": ",".join(missing), "retmode": "json"},
                timeout=45,
            )
            result = resp.json().get("result", {})
            for pmid in missing:
                self.summary_cache[pmid] = result.get(str(pmid), {}) or {}
        return {pmid: self.summary_cache.get(pmid, {}) for pmid in pmids}

    def crossref_candidates(self, title: str, year: str, first_author: str, venue: str, rows: int = 5) -> list[dict[str, Any]]:
        key = f"{title}||{year}||{first_author}||{venue}||{rows}"
        if key in self.crossref_cache:
            return self.crossref_cache[key]

        params = {
            "query.title": title,
            "rows": rows,
            "select": "DOI,title,author,published-print,published-online,container-title,score",
        }
        if first_author:
            params["query.author"] = first_author
        if venue:
            params["query.container-title"] = venue

        url = CROSSREF_URL + "?" + urllib.parse.urlencode(params, doseq=True)
        resp = self._get_with_retry(url, timeout=45)
        items = resp.json().get("message", {}).get("items", []) or []
        self.crossref_cache[key] = items
        return items

    def resolve(self, paper: dict[str, Any]) -> Resolution:
        title = str(paper.get("title", "") or "").strip()
        year = str(paper.get("year", "") or "").strip()
        venue = str(paper.get("venue", "") or "").strip()
        authors = paper.get("authors") or []
        first_author = ""
        if authors and isinstance(authors, list):
            first_author = str((authors[0] or {}).get("name", "") or "").strip()
        abstract = str(paper.get("abstract", "") or "").strip()
        doi = extract_doi(paper)

        if doi:
            res = self._resolve_by_doi(doi, title, year)
            if res.pmid:
                return res
        else:
            crossref_doi = self._resolve_doi_via_crossref(title, year, first_author, venue)
            if crossref_doi:
                res = self._resolve_by_doi(crossref_doi, title, year)
                if res.pmid:
                    res.method = f"crossref_doi->{res.method}"
                    return res

        if title:
            res = self._resolve_by_title(title, year, first_author)
            if res.pmid:
                res.doi = doi
                return res
            res = self._resolve_by_fallback(title, year, first_author, abstract)
            if res.pmid:
                res.doi = doi
                return res

        return Resolution(doi=doi, note="no_match")

    def _resolve_doi_via_crossref(self, title: str, year: str, first_author: str, venue: str) -> str:
        if not title:
            return ""
        try:
            items = self.crossref_candidates(title, year, first_author, venue, rows=8)
        except Exception:
            return ""

        norm_title = normalize_text(title)
        best: tuple[int, str] | None = None
        for item in items:
            doi = normalize_doi_text(item.get("DOI", ""))
            titles = item.get("title") or []
            cand_title = str(titles[0] if titles else "").strip()
            cand_norm = normalize_text(cand_title)
            score = 0
            if cand_norm == norm_title:
                score += 100
            elif cand_norm and norm_title and cand_norm in norm_title:
                score += 70
            elif cand_norm and norm_title and norm_title in cand_norm:
                score += 70

            cand_year = self._crossref_year(item)
            if year and cand_year == year:
                score += 10
            elif year and cand_year and abs(int(cand_year) - int(year)) <= 1:
                score += 4

            if first_author:
                surname = author_surname(first_author).lower()
                authors = item.get("author") or []
                author_hit = any(
                    surname and surname == str(a.get("family", "") or "").strip().lower()
                    for a in authors if isinstance(a, dict)
                )
                if author_hit:
                    score += 8

            if score <= 0 or not doi:
                continue
            if best is None or score > best[0]:
                best = (score, doi)
        return best[1] if best else ""

    def _crossref_year(self, item: dict[str, Any]) -> str:
        for field in ("published-print", "published-online"):
            payload = item.get(field) or {}
            parts = payload.get("date-parts") or []
            if parts and parts[0]:
                year = str(parts[0][0])
                if re.fullmatch(r"(19|20)\d{2}", year):
                    return year
        return ""

    def _resolve_by_doi(self, doi: str, source_title: str, year: str) -> Resolution:
        ids = self.esearch(f"{doi}[AID]", retmax=5)
        if not ids:
            ids = self.esearch(quoted_term(doi), retmax=5)
        if not ids:
            return Resolution(doi=doi, note="doi_not_found")
        return self._pick_best(ids, source_title, year, "doi_search", doi=doi)

    def _resolve_by_title(self, title: str, year: str, first_author: str) -> Resolution:
        queries = [f"{quoted_term(title)}[Title]"]
        if year:
            queries.append(f"{quoted_term(title)}[Title] AND {year}[PDat]")
        if first_author:
            surname = author_surname(first_author)
            queries.append(f"{quoted_term(title)}[Title] AND {quoted_term(surname)}[Author]")
            if year:
                queries.append(f"{quoted_term(title)}[Title] AND {quoted_term(surname)}[Author] AND {year}[PDat]")

        seen: set[str] = set()
        for term in queries:
            ids = [x for x in self.esearch(term, retmax=10) if x not in seen]
            seen.update(ids)
            if not ids:
                continue
            picked = self._pick_best(ids, title, year, f"title_search:{term}")
            if picked.pmid:
                return picked
        return Resolution(note="title_not_found")

    def _resolve_by_fallback(self, title: str, year: str, first_author: str, abstract: str) -> Resolution:
        surname = author_surname(first_author)
        snippet = abstract_snippet(abstract)
        queries: list[str] = []

        if snippet:
            queries.append(f"{quoted_term(title)}[Title] AND ({snippet}[Title/Abstract])")
            if year:
                queries.append(f"{quoted_term(title)}[Title] AND ({snippet}[Title/Abstract]) AND {year}[PDat]")
            if surname:
                queries.append(
                    f"{quoted_term(title)}[Title] AND ({snippet}[Title/Abstract]) AND {quoted_term(surname)}[Author]"
                )
                if year:
                    queries.append(
                        f"{quoted_term(title)}[Title] AND ({snippet}[Title/Abstract]) AND {quoted_term(surname)}[Author] AND {year}[PDat]"
                    )

        if surname:
            queries.append(f"{title}[Title] AND {quoted_term(surname)}[Author]")
            if year:
                queries.append(f"{title}[Title] AND {quoted_term(surname)}[Author] AND {year}[PDat]")

        seen: set[str] = set()
        for term in queries:
            ids = [x for x in self.esearch(term, retmax=10) if x not in seen]
            seen.update(ids)
            if not ids:
                continue
            picked = self._pick_best(ids, title, year, f"fallback_search:{term}")
            if picked.pmid:
                return picked
        return Resolution(note="fallback_not_found")

    def _pick_best(self, pmids: list[str], source_title: str, source_year: str, method: str, doi: str = "") -> Resolution:
        summaries = self.esummary_many(pmids)
        norm_source_title = normalize_text(source_title)
        best: tuple[int, Resolution] | None = None

        for pmid in pmids:
            summary = summaries.get(pmid, {})
            cand_title = str(summary.get("title", "") or "").strip()
            cand_norm = normalize_text(cand_title)
            pubdate = str(summary.get("pubdate", "") or "").strip()
            source = str(summary.get("source", "") or "").strip()
            cand_year_match = re.search(r"\b(19|20)\d{2}\b", pubdate)
            cand_year = cand_year_match.group(0) if cand_year_match else ""

            score = 0
            if cand_norm == norm_source_title:
                score += 100
            elif cand_norm and norm_source_title and cand_norm in norm_source_title:
                score += 70
            elif cand_norm and norm_source_title and norm_source_title in cand_norm:
                score += 70

            if source_year and cand_year == source_year:
                score += 10
            elif source_year and cand_year and abs(int(cand_year) - int(source_year)) <= 1:
                score += 4

            if score <= 0:
                continue

            res = Resolution(
                pmid=str(pmid),
                method=method,
                note="matched",
                matched_title=cand_title,
                matched_pubdate=pubdate,
                matched_source=source,
                doi=doi,
            )
            if best is None or score > best[0]:
                best = (score, res)

        return best[1] if best else Resolution(doi=doi, note="candidate_titles_mismatch")


def augment_json_file(path: Path, resolver: PubMedResolver) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8-sig"))
    papers = obj.get("papers", [])
    resolved = 0
    doi_count = 0
    title_only_resolved = 0
    errors = 0

    for paper in papers:
        try:
            doi = extract_doi(paper)
            if doi:
                doi_count += 1
            result = resolver.resolve(paper)
            if result.pmid:
                resolved += 1
                if result.method.startswith("title_search") or result.method.startswith("fallback_search"):
                    title_only_resolved += 1
            paper["pubmed_id"] = result.pmid
            paper["pubmed_resolution"] = {
                "method": result.method,
                "note": result.note,
                "doi": result.doi,
                "matched_title": result.matched_title,
                "matched_pubdate": result.matched_pubdate,
                "matched_source": result.matched_source,
            }
        except Exception as exc:
            errors += 1
            paper["pubmed_id"] = ""
            paper["pubmed_resolution"] = {"method": "", "note": f"error:{exc}"}

    out_path = path.with_name(path.stem + "_with_pmid.json")
    out_path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "file": str(path),
        "output_file": str(out_path),
        "paper_count": len(papers),
        "resolved_count": resolved,
        "resolved_rate": (resolved / len(papers)) if papers else 0.0,
        "doi_count": doi_count,
        "title_only_resolved_count": title_only_resolved,
        "error_count": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("target_dir", type=Path)
    parser.add_argument("--sleep-seconds", type=float, default=SLEEP_SECONDS)
    args = parser.parse_args()

    target_dir = args.target_dir
    json_files = sorted(target_dir.glob("papers*.json"))
    if not json_files:
        raise SystemExit(f"No JSON files found under {target_dir}")

    resolver = PubMedResolver(sleep_seconds=args.sleep_seconds)
    reports = []
    for path in json_files:
        if path.name.endswith("_with_pmid.json") or path.name.endswith("_pmid_report.json") or path.name == "pmid_resolution_report.json":
            continue
        reports.append(augment_json_file(path, resolver))

    summary = {
        "target_dir": str(target_dir),
        "files": reports,
        "total_papers": sum(r["paper_count"] for r in reports),
        "total_resolved": sum(r["resolved_count"] for r in reports),
        "overall_resolved_rate": (
            sum(r["resolved_count"] for r in reports) / sum(r["paper_count"] for r in reports)
            if sum(r["paper_count"] for r in reports)
            else 0.0
        ),
    }
    report_path = target_dir / "pmid_resolution_report.json"
    report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"report_path={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
