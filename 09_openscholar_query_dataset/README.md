# 09_openscholar_query_dataset

OpenScholar retrieval results and recall metrics for the 24 test systematic reviews.

## Directory structure

```
09_openscholar_query_dataset/
  {paper_id}/
    papers_normal.json              -- OpenScholar normal search results (raw)
    papers_deep.json                -- OpenScholar deep search results (raw)
    papers_normal_with_pmid.json    -- normal results with PMID attached
    papers_deep_with_pmid.json      -- deep results with PMID attached
    relaxed_recall_report.json      -- recall computed by relaxed title/DOI matching
    pmid_resolution_report.json     -- PMID resolution audit
  code/
    attach_pmids.py                 -- DOI/title → PMID via PubMed/CrossRef API
    compute_relaxed_recall.py       -- recall via relaxed title+DOI matching
    refresh_missing_and_compare_with_llm.py  -- updates elicit_queryB_list_papers.csv with OpenScholar recall
```

## Pipeline

```
papers_normal.json / papers_deep.json
    ↓ attach_pmids.py          (DOI/title → PMID via API)
papers_normal_with_pmid.json / papers_deep_with_pmid.json
    ↓ compute_relaxed_recall.py
relaxed_recall_report.json     (per paper)
    ↓ refresh_missing_and_compare_with_llm.py
08_elicit_queryb_dataset/elicit_queryB_list_papers.csv  (openscholar_normal/deep columns updated)
```

## Recall computation logic (`compute_relaxed_recall.py`)

Because OpenScholar results do not reliably include PMIDs, recall is computed via three
matching stages applied in order. Gold PMIDs matched at an earlier stage are skipped in
subsequent stages.

| Stage | Matching axis | Condition |
|---|---|---|
| 1. PMID exact | `pubmed_id` field ↔ gold PMID | Exact match |
| 2. Title exact + year exact | Normalized title ↔ gold title | Both exact match |
| 3. Fuzzy title + near year | `difflib.SequenceMatcher` ratio | Same year: ≥0.95 / ±1 year: ≥0.98 / ≥2 years apart: skip |

`recall_relaxed` (union of all three stages) is used as the final recall value.

---

Run from `public_release/`:

```bash
# Per paper
python 09_openscholar_query_dataset/code/attach_pmids.py {paper_id}
python 09_openscholar_query_dataset/code/compute_relaxed_recall.py {paper_id}

# Aggregate all 24 papers into elicit_queryB_list_papers.csv
python 09_openscholar_query_dataset/code/refresh_missing_and_compare_with_llm.py
```
