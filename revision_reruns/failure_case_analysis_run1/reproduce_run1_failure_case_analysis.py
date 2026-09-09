from __future__ import annotations

import argparse
import json
import math
import re
import time
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

import pandas as pd
import requests

BASE = Path(__file__).resolve().parent
PUBLIC = Path(__file__).resolve().parents[2]
DEFAULT_OUT = BASE / "outputs"
POINTS = PUBLIC / "07_paper_figures" / "data" / "test24_eval" / "elicit24_points_gate1000_floor1000_20260511.csv"
TABLE_S1 = BASE / "inputs" / "TableS1_35papers_dataset_ver2.csv"
TEST_DATA = PUBLIC / "05_test_data"
ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
PROVIDERS = ["claude", "codex", "gemini"]
LABELS = {"claude": "Claude", "codex": "Codex", "gemini": "Gemini"}
GENERIC = set(
    "a an and are as at be by for from has have in into is it its of on or our review reviews systematic meta analysis "
    "study studies trial trials patient patients human humans using use used among with without to the this that which whether "
    "what how across based include included including outcome outcomes effect effects association associations treatment therapy disease diseases".split()
)


def read_meta_s1() -> dict:
    with TABLE_S1.open(encoding="utf-8-sig") as handle:
        header_row = next(i for i, line in enumerate(handle) if line.lstrip().startswith("PubmedID,"))
    s1 = pd.read_csv(TABLE_S1, header=header_row)
    s1["PubmedID"] = s1["PubmedID"].astype(str).str.replace(r"\.0$", "", regex=True)
    return s1[s1["Set"].astype(str).str.lower().eq("test")].set_index("PubmedID")[["Domain", "Broad review type", "query", "gold_count"]].to_dict("index")


def collect_items() -> list[dict]:
    items = []
    for gold_path in sorted(TEST_DATA.glob("*/*/gold_pmids.json")):
        domain = gold_path.parent.parent.name
        paper_id = gold_path.parent.name
        review_pmid = paper_id.split("_")[0]
        gold = [str(x) for x in json.loads(gold_path.read_text(encoding="utf-8")).get("gold_pmids", [])]
        for provider in PROVIDERS:
            query_path = gold_path.parent / "model_outputs" / provider / "with_laws_test_eval" / "normalized_query.txt"
            if query_path.exists():
                items.append(
                    {
                        "domain_folder": domain,
                        "paper_id": paper_id,
                        "review_pmid": review_pmid,
                        "provider": provider,
                        "query_path": str(query_path.relative_to(PUBLIC)),
                        "query": query_path.read_text(encoding="utf-8").strip(),
                        "gold_pmids": gold,
                    }
                )
    if len(items) != 72:
        raise RuntimeError(f"Expected 72 Run1 query items, found {len(items)}")
    return items


def request_post(session: requests.Session, url: str, data: dict) -> requests.Response:
    last = None
    for attempt in range(5):
        try:
            response = session.post(url, data=data, timeout=60)
            response.raise_for_status()
            return response
        except Exception as exc:  # pragma: no cover - network retry path
            last = exc
            time.sleep(1.0 * (2**attempt))
    raise RuntimeError(f"NCBI request failed: {last}")


def esearch_gold_intersection(session: requests.Session, query: str, gold_pmids: list[str]) -> dict:
    gold_block = " OR ".join(f"{pmid}[uid]" for pmid in gold_pmids)
    term = f"({query}) AND ({gold_block})"
    response = request_post(
        session,
        ESEARCH,
        {"db": "pubmed", "term": term, "retmode": "json", "retmax": str(len(gold_pmids) + 5), "tool": "jmir-run1-gold-intersection"},
    )
    result = response.json()["esearchresult"]
    time.sleep(0.34)
    return {"gold_intersection_count": int(result.get("count", "0")), "gold_hit_pmids": [str(x) for x in result.get("idlist", [])]}


def esearch_count(session: requests.Session, query: str) -> int:
    response = request_post(session, ESEARCH, {"db": "pubmed", "term": query, "retmode": "json", "retmax": "0", "tool": "jmir-run1-count-only"})
    result = response.json()["esearchresult"]
    time.sleep(0.34)
    return int(result.get("count", "0"))


def text_nodes(parent: ET.Element | None, path: str) -> list[str]:
    if parent is None:
        return []
    values = []
    for node in parent.findall(path):
        value = "".join(node.itertext()).strip()
        if value:
            values.append(value)
    return values


def fetch_meta_batch(session: requests.Session, pmids: list[str]) -> dict:
    response = request_post(session, EFETCH, {"db": "pubmed", "id": ",".join(pmids), "retmode": "xml", "rettype": "abstract", "tool": "jmir-run1-failure-analysis"})
    root = ET.fromstring(response.text)
    rows = {}
    for article in root.findall(".//PubmedArticle"):
        medline = article.find("MedlineCitation")
        if medline is None:
            continue
        pmid = "".join(medline.findtext("PMID", default="")).strip()
        article_node = medline.find("Article")
        title = "".join(article_node.findtext("ArticleTitle", default="")).strip() if article_node is not None else ""
        abstract = "\n".join(text_nodes(article_node.find("Abstract") if article_node is not None else None, "AbstractText"))
        pub_types = text_nodes(article_node.find("PublicationTypeList") if article_node is not None else None, "PublicationType")
        languages = text_nodes(article_node, "Language") if article_node is not None else []
        journal = "".join(article_node.findtext("Journal/Title", default="")).strip() if article_node is not None else ""
        year = ""
        if article_node is not None:
            year_raw = article_node.findtext("Journal/JournalIssue/PubDate/Year") or article_node.findtext("Journal/JournalIssue/PubDate/MedlineDate") or ""
            year = "".join(year_raw).strip()[:4]
        rows[pmid] = {
            "pmid": pmid,
            "title": title,
            "abstract": abstract,
            "pub_types": pub_types,
            "languages": languages,
            "journal": journal,
            "year": year,
            "mesh_terms": text_nodes(medline.find("MeshHeadingList"), "MeshHeading/DescriptorName"),
            "chemicals": text_nodes(medline.find("ChemicalList"), "Chemical/NameOfSubstance"),
        }
    time.sleep(0.34)
    return rows


def refresh_pubmed(items: list[dict], requery_dir: Path, queried_at: str) -> tuple[dict, dict]:
    session = requests.Session()
    requery = {}
    for item in items:
        key = f"{item['domain_folder']}/{item['paper_id']}/{item['provider']}"
        inter = esearch_gold_intersection(session, item["query"], item["gold_pmids"])
        requery[key] = {
            **{k: item[k] for k in ["domain_folder", "paper_id", "review_pmid", "provider", "query_path", "query"]},
            "queried_at": queried_at,
            "requery_total_hits": esearch_count(session, item["query"]),
            **inter,
        }
    all_gold = sorted({pmid for item in items for pmid in item["gold_pmids"]})
    metadata = {}
    for i in range(0, len(all_gold), 150):
        metadata.update(fetch_meta_batch(session, all_gold[i : i + 150]))
    requery_dir.mkdir(parents=True, exist_ok=True)
    (requery_dir / f"run1_pubmed_requery_gold_intersection_{queried_at.replace('-', '')}.json").write_text(json.dumps(requery, ensure_ascii=False, indent=2), encoding="utf-8")
    (requery_dir / "gold_pubmed_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return requery, metadata


def tokens(value: str) -> list[str]:
    return [token for token in re.findall(r"[a-z][a-z0-9]{2,}", (value or "").lower()) if token not in GENERIC]


def design_class(record: dict) -> str:
    text = " ".join([record.get("title", ""), record.get("abstract", ""), " ".join(record.get("pub_types", []))]).lower()
    pub_types = " | ".join(record.get("pub_types", [])).lower()
    if "systematic review" in text or "meta-analysis" in pub_types or re.search(r"\breview\b", pub_types):
        return "Review/SR-of-SRs record"
    if "randomized controlled trial" in pub_types or "clinical trial" in pub_types or "randomised" in text or "randomized" in text or "randomly assigned" in text:
        return "Randomized/clinical trial"
    if any(term in text for term in ["cohort", "case-control", "cross-sectional", "registry", "observational", "retrospective", "prospective", "case series"]):
        return "Observational study"
    if any(term in text for term in ["diagnostic", "prognostic", "prediction model", "biomarker", "sensitivity", "specificity", "c-statistic", "auc"]):
        return "Diagnostic/prognostic/biomarker study"
    if any(term in text for term in ["qualitative", "interview", "focus group", "thematic analysis", "mixed methods"]):
        return "Qualitative/mixed-methods study"
    if "case reports" in pub_types or "case report" in text:
        return "Case report/series"
    if any(term in text for term in ["mouse", "mice", "rat", "animal", "in vitro", "cell line", "murine"]):
        return "Preclinical/animal/in vitro"
    return "Other/unclear design"


def metadata_flags(record: dict, query: str) -> tuple[list[str], float]:
    title = record.get("title", "") or ""
    abstract = record.get("abstract", "") or ""
    mesh = record.get("mesh_terms", []) or []
    text = " ".join([title, abstract, " ".join(mesh)]).lower()
    pub_types = " | ".join(record.get("pub_types", [])).lower()
    flags = []
    if len(abstract.strip()) < 150:
        flags.append("sparse_or_no_abstract")
    if not mesh or len(mesh) < 3:
        flags.append("limited_mesh_indexing")
    if "review" in pub_types or "meta-analysis" in pub_types or "guideline" in pub_types:
        flags.append("publication_type_filter_sensitive")
    query_tokens = {token for token in tokens(re.sub(r"\[[^\]]+\]", " ", query)) if len(token) >= 4}
    meta_tokens = set(tokens(text))
    ratio = len(query_tokens & meta_tokens) / max(1, min(len(query_tokens), 60))
    if ratio < 0.10:
        flags.append("low_literal_overlap_with_generated_query_terms")
    elif ratio < 0.20:
        flags.append("moderate_literal_overlap_with_generated_query_terms")
    try:
        year = int(str(record.get("year", ""))[:4])
        if year < 2000:
            flags.append("older_record_pre_2000")
        elif year < 2010:
            flags.append("older_record_2000_2009")
    except Exception:
        flags.append("publication_year_missing")
    return flags, ratio


def dominant_characteristic(flags: list[str], design: str) -> str:
    if "sparse_or_no_abstract" in flags or "limited_mesh_indexing" in flags:
        return "Sparse PubMed metadata/indexing"
    if "publication_type_filter_sensitive" in flags or design == "Review/SR-of-SRs record":
        return "Publication-type/filter-sensitive record"
    if "low_literal_overlap_with_generated_query_terms" in flags:
        return "Terminology mismatch with generated Boolean terms"
    if design == "Other/unclear design":
        return "Non-standard or unclear study-design label"
    if any(flag.startswith("older_record") for flag in flags):
        return "Older record with possible indexing/terminology drift"
    return "No single dominant metadata signal"


def run_count_based(points: pd.DataFrame, meta_s1: dict, out_dir: Path) -> None:
    rows = []
    for paper_id in sorted(points["paper_id"].unique()):
        pmid = str(paper_id).split("_")[0]
        meta = meta_s1.get(pmid, {})
        for provider in ["Claude", "Codex", "Gemini"]:
            cut0 = points[(points["paper_id"].eq(paper_id)) & (points["method"].eq(f"{provider} cut0"))].iloc[0]
            cut70 = points[(points["paper_id"].eq(paper_id)) & (points["method"].eq(f"{provider} cut70"))].iloc[0]
            gold_n = int(round(float(cut70["gold_n"])))
            cut0_tp = int(round(float(cut0["tp"])))
            cut70_tp = int(round(float(cut70["tp"])))
            stage1_miss = max(gold_n - cut0_tp, 0)
            stage2_loss = max(cut0_tp - cut70_tp, 0)
            final_miss = max(gold_n - cut70_tp, 0)
            rows.append(
                {
                    "paper_id": paper_id,
                    "review_pmid": pmid,
                    "domain": meta.get("Domain", ""),
                    "broad_review_type": meta.get("Broad review type", ""),
                    "provider": provider,
                    "gold_n": gold_n,
                    "stage1_cut0_hits": int(round(float(cut0["hits"]))),
                    "stage1_cut0_tp": cut0_tp,
                    "stage1_cut0_recall": float(cut0["recall"]),
                    "stage2_cut70_hits": int(round(float(cut70["hits"]))),
                    "stage2_cut70_tp": cut70_tp,
                    "stage2_cut70_recall": float(cut70["recall"]),
                    "stage2_cut70_nnr": float(cut70["nnr"]) if not pd.isna(cut70["nnr"]) else math.nan,
                    "stage1_retrieval_miss_count": stage1_miss,
                    "stage2_candidate_reduction_loss_count": stage2_loss,
                    "final_missed_gold_count_at_cut70": final_miss,
                }
            )
    df = pd.DataFrame(rows)
    df.to_csv(out_dir / "TableSx_run1_failure_case_by_slr_provider.csv", index=False, encoding="utf-8-sig")
    summary = df.groupby("provider").agg(
        n_slr=("paper_id", "count"),
        mean_cut0_recall=("stage1_cut0_recall", "mean"),
        mean_cut70_recall=("stage2_cut70_recall", "mean"),
        mean_cut70_nnr=("stage2_cut70_nnr", "mean"),
        total_gold_pmids=("gold_n", "sum"),
        total_stage1_retrieval_misses=("stage1_retrieval_miss_count", "sum"),
        total_stage2_candidate_reduction_losses=("stage2_candidate_reduction_loss_count", "sum"),
        total_final_missed_gold_at_cut70=("final_missed_gold_count_at_cut70", "sum"),
    ).reset_index()
    summary.to_csv(out_dir / "TableSx_run1_failure_case_summary_by_provider.csv", index=False, encoding="utf-8-sig")


def run_metadata_analysis(items: list[dict], points: pd.DataFrame, meta_s1: dict, requery: dict, metadata: dict, out_dir: Path) -> None:
    rows = []
    for item in items:
        key = f"{item['domain_folder']}/{item['paper_id']}/{item['provider']}"
        rq = requery[key]
        hit_set = set(rq.get("gold_hit_pmids", []))
        label = LABELS[item["provider"]]
        official = points[(points["paper_id"].eq(item["paper_id"])) & (points["method"].eq(f"{label} cut0"))].iloc[0]
        for pmid in item["gold_pmids"]:
            record = metadata.get(str(pmid), {"pmid": str(pmid)})
            retrieved = str(pmid) in hit_set
            flags, ratio = metadata_flags(record, item["query"])
            design = design_class(record)
            rows.append(
                {
                    "paper_id": item["paper_id"],
                    "review_pmid": item["review_pmid"],
                    "domain": meta_s1.get(item["review_pmid"], {}).get("Domain", ""),
                    "broad_review_type": meta_s1.get(item["review_pmid"], {}).get("Broad review type", ""),
                    "provider": label,
                    "gold_pmid": str(pmid),
                    "retrieved_by_run1_query_requery": retrieved,
                    "requery_total_hits": rq.get("requery_total_hits"),
                    "requery_gold_tp": rq.get("gold_intersection_count"),
                    "official_cut0_hits": int(round(float(official["hits"]))),
                    "official_cut0_tp": int(round(float(official["tp"]))),
                    "official_cut0_recall": float(official["recall"]),
                    "title": record.get("title", ""),
                    "year": record.get("year", ""),
                    "journal": record.get("journal", ""),
                    "pub_types": " | ".join(record.get("pub_types", [])),
                    "languages": " | ".join(record.get("languages", [])),
                    "mesh_terms": " | ".join(record.get("mesh_terms", [])),
                    "abstract_available": bool((record.get("abstract", "") or "").strip()),
                    "abstract_length": len(record.get("abstract", "") or ""),
                    "study_design_or_record_type": design,
                    "query_metadata_token_overlap_ratio": round(ratio, 3),
                    "metadata_flags": ";".join(flags),
                    "dominant_missed_study_characteristic": dominant_characteristic(flags, design) if not retrieved else "",
                }
            )
    per = pd.DataFrame(rows)
    per.to_csv(out_dir / "run1_gold_pmid_requery_exact_and_metadata_characteristics.csv", index=False, encoding="utf-8-sig")
    missed = per[~per["retrieved_by_run1_query_requery"]].copy()
    missed.to_csv(out_dir / "run1_stage1_missed_gold_pmid_characteristics_exact_requery.csv", index=False, encoding="utf-8-sig")
    summary_provider = missed.groupby("provider").agg(
        missed_gold_pmids=("gold_pmid", "count"),
        unique_missed_gold_pmids=("gold_pmid", "nunique"),
        median_year=("year", lambda s: pd.to_numeric(s, errors="coerce").median()),
        no_abstract_n=("abstract_available", lambda s: int((~s).sum())),
        low_query_overlap_n=("metadata_flags", lambda s: int(s.str.contains("low_literal_overlap", na=False).sum())),
        limited_mesh_n=("metadata_flags", lambda s: int(s.str.contains("limited_mesh_indexing", na=False).sum())),
        pubtype_filter_sensitive_n=("metadata_flags", lambda s: int(s.str.contains("publication_type_filter_sensitive", na=False).sum())),
    ).reset_index()
    for col in ["no_abstract_n", "low_query_overlap_n", "limited_mesh_n", "pubtype_filter_sensitive_n"]:
        summary_provider[col.replace("_n", "_pct")] = (summary_provider[col] / summary_provider["missed_gold_pmids"] * 100).round(1)
    summary_provider.to_csv(out_dir / "run1_missed_gold_summary_by_provider_exact_requery.csv", index=False, encoding="utf-8-sig")
    summary_design = missed.groupby(["provider", "study_design_or_record_type"]).size().reset_index(name="missed_gold_pmids")
    summary_design.to_csv(out_dir / "run1_missed_gold_summary_by_study_design_exact_requery.csv", index=False, encoding="utf-8-sig")
    summary_flags = missed.assign(flag=missed["metadata_flags"].str.split(";")).explode("flag").query("flag != ''").groupby(["provider", "flag"]).size().reset_index(name="missed_gold_pmids")
    summary_flags.to_csv(out_dir / "run1_missed_gold_summary_by_metadata_flag_exact_requery.csv", index=False, encoding="utf-8-sig")

    sr_rows = []
    for (paper_id, provider), group in per.groupby(["paper_id", "provider"]):
        first = group.iloc[0]
        missed_group = group[~group["retrieved_by_run1_query_requery"]]
        gold_n = len(group)
        miss_n = len(missed_group)
        if miss_n:
            design_counts = Counter(missed_group["study_design_or_record_type"])
            char_counts = Counter(missed_group["dominant_missed_study_characteristic"])
            flags = Counter(";".join(missed_group["metadata_flags"]).split(";")); flags.pop("", None)
            top_design = "; ".join(f"{k} ({v})" for k, v in design_counts.most_common(3))
            top_char = "; ".join(f"{k} ({v})" for k, v in char_counts.most_common(3))
            top_flags = "; ".join(f"{k} ({v})" for k, v in flags.most_common(4))
        else:
            top_design = top_char = top_flags = ""
        sr_rows.append(
            {
                "paper_id": paper_id,
                "provider": provider,
                "domain": first["domain"],
                "broad_review_type": first["broad_review_type"],
                "gold_n": gold_n,
                "missed_gold_pmids_by_exact_requery": miss_n,
                "requery_recall": round(1 - miss_n / gold_n, 3) if gold_n else math.nan,
                "official_cut0_recall": first["official_cut0_recall"],
                "top_missed_record_types": top_design,
                "top_missed_characteristics": top_char,
                "top_metadata_flags": top_flags,
            }
        )
    sr = pd.DataFrame(sr_rows)
    sr.to_csv(out_dir / "run1_sr_level_missed_study_bias_summary_exact_requery.csv", index=False, encoding="utf-8-sig")
    worst = sr[(sr["requery_recall"] <= 0.5) | (sr["missed_gold_pmids_by_exact_requery"] >= 10)].sort_values(["requery_recall", "missed_gold_pmids_by_exact_requery"], ascending=[True, False])
    worst.to_csv(out_dir / "TableSx_run1_exact_requery_worst_missed_study_patterns.csv", index=False, encoding="utf-8-sig")

    md = []
    md.append("# Supplementary Table Sx. Run1 missed-study metadata and potential retrieval-bias analysis")
    md.append("")
    md.append("For each Run1 query, gold PMID retrieval was determined using an exact intersection query: `(Run1 PubMed Boolean query) AND (gold PMID OR block)`. PubMed metadata were used for descriptive classification of missed-study patterns. Because PubMed indexing can change over time, these results should be interpreted alongside the official Run1 cut0/cut70 metrics.")
    md.append("")
    md.append("## Summary by provider")
    md.append(summary_provider.to_markdown(index=False))
    md.append("")
    md.append("## Missed gold PMIDs by record/study type")
    md.append(summary_design.pivot_table(index="study_design_or_record_type", columns="provider", values="missed_gold_pmids", aggfunc="sum", fill_value=0).reset_index().to_markdown(index=False))
    md.append("")
    md.append("## Common metadata flags among missed gold PMIDs")
    md.append(summary_flags.pivot_table(index="flag", columns="provider", values="missed_gold_pmids", aggfunc="sum", fill_value=0).reset_index().to_markdown(index=False))
    md.append("")
    md.append("## Worst SR/provider patterns")
    md.append(worst.head(25).to_markdown(index=False))
    md.append("")
    md.append("Interpretation: these categories describe metadata-level patterns of missed records. They do not establish that the downstream meta-analytic effect estimate would change in a specific direction, because that would require extracting outcomes and effect sizes from each missed primary study.")
    (out_dir / "TableSx_run1_missed_study_metadata_and_bias_analysis_exact_requery.md").write_text("\n".join(md), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Reproduce Run1 failure-case and missed-study metadata analyses.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUT), help="Output directory for failure-case tables.")
    parser.add_argument("--requery-dir", default=str(BASE / "inputs" / "pubmed_requery_20260901"), help="Directory containing or receiving PubMed requery JSON/metadata.")
    parser.add_argument("--refresh-pubmed", action="store_true", help="Refresh PubMed ESearch/EFetch files instead of reusing saved JSON.")
    parser.add_argument("--queried-at", default="2026-09-01", help="Date label for refreshed PubMed outputs.")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    requery_dir = Path(args.requery_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    requery_dir.mkdir(parents=True, exist_ok=True)
    points = pd.read_csv(POINTS)
    meta_s1 = read_meta_s1()
    items = collect_items()

    run_count_based(points, meta_s1, out_dir)

    if args.refresh_pubmed:
        requery, metadata = refresh_pubmed(items, requery_dir, args.queried_at)
    else:
        requery_files = sorted(requery_dir.glob("run1_pubmed_requery_gold_intersection_*.json"))
        if not requery_files:
            raise FileNotFoundError("No saved gold-intersection requery JSON found. Use --refresh-pubmed first.")
        requery = json.loads(requery_files[-1].read_text(encoding="utf-8"))
        metadata = json.loads((requery_dir / "gold_pubmed_metadata.json").read_text(encoding="utf-8"))

    run_metadata_analysis(items, points, meta_s1, requery, metadata, requery_dir)
    print(f"Wrote failure-case outputs to {out_dir}")
    print(f"Wrote metadata-pattern outputs to {requery_dir}")


if __name__ == "__main__":
    main()

