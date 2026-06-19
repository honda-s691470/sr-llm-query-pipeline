from __future__ import annotations

import argparse
import json
import os
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List

import requests


EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
DEFAULT_TOOL = "pubmed-metadata-fetch"
DEFAULT_EMAIL = ""


def _ncbi_params(api_key: str | None) -> Dict[str, str]:
    params: Dict[str, str] = {"db": "pubmed", "tool": DEFAULT_TOOL}
    if DEFAULT_EMAIL:
        params["email"] = DEFAULT_EMAIL
    if api_key:
        params["api_key"] = api_key
    return params


def _request_text(url: str, params: Dict[str, str], timeout: int = 30, max_retries: int = 4) -> str:
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response.text
        except Exception as exc:  # pragma: no cover - retry path
            last_err = exc
            time.sleep(0.8 * (2 ** attempt))
    raise RuntimeError(f"NCBI request failed after retries: {last_err}")


def _collect_text_nodes(parent: ET.Element | None, path: str) -> List[str]:
    if parent is None:
        return []
    values: List[str] = []
    for node in parent.findall(path):
        text = "".join(node.itertext()).strip()
        if text:
            values.append(text)
    return values


def fetch_metadata(pmids: List[str], api_key: str | None = None, polite_sleep_sec: float = 0.34) -> List[Dict]:
    if not pmids:
        return []

    params = {
        **_ncbi_params(api_key),
        "id": ",".join(pmids),
        "retmode": "xml",
        "rettype": "abstract",
    }
    xml_text = _request_text(EFETCH_URL, params=params)
    time.sleep(polite_sleep_sec)

    root = ET.fromstring(xml_text)
    rows: List[Dict] = []
    for article in root.findall(".//PubmedArticle"):
        medline = article.find("MedlineCitation")
        if medline is None:
            continue

        pmid = "".join(medline.findtext("PMID", default="")).strip()
        article_node = medline.find("Article")
        title = ""
        abstract = ""
        if article_node is not None:
            title = "".join(article_node.findtext("ArticleTitle", default="")).strip()
            abstract_parts = _collect_text_nodes(article_node.find("Abstract"), "AbstractText")
            abstract = "\n".join(abstract_parts).strip()

        mesh_terms = _collect_text_nodes(medline.find("MeshHeadingList"), "MeshHeading/DescriptorName")

        rows.append(
            {
                "pmid": pmid,
                "title": title,
                "abstract": abstract,
                "mesh_terms": mesh_terms,
            }
        )
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description="Fetch PubMed title/abstract metadata for PMIDs.")
    ap.add_argument("--pmids", nargs="+", required=True, help="One or more PubMed IDs")
    ap.add_argument("--output", required=True, help="Path to write metadata JSON")
    args = ap.parse_args()

    api_key = os.getenv("NCBI_API_KEY") or os.getenv("ENTREZ_API_KEY")
    rows = fetch_metadata(pmids=[str(p).strip() for p in args.pmids if str(p).strip()], api_key=api_key)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote metadata for {len(rows)} PMID(s) to: {output_path}")


if __name__ == "__main__":
    main()
