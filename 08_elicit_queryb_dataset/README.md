# 08_elicit_queryb_dataset

Elicit query B retrieval results and recall metrics for the 24 test systematic reviews.

## Directory structure

```
08_elicit_queryb_dataset/
  {paper_id}/
    Elicit - screen-results-review-{paper_id}_keyword.csv   -- Elicit Keyword search export
    Elicit - screen-results-review-{paper_id}_question.csv  -- Elicit Question search export
  elicit_queryB_list_papers.csv   -- per-paper recall/hits for Elicit and OpenScholar methods (24 papers)
  elicit24_points_gate1000_floor1000_20260511.csv  -- per-paper per-method recall/NNR points (input to Figure 4)
  code/
    compute_elicit_recall_from_export.py          -- DOI→PMID conversion + recall per paper (CLI)
    compute_24paper_aggregate_gate_floor.py       -- aggregates all methods → elicit24_points_*.csv
    refresh_missing_and_compare_with_llm.py       -- updates elicit_queryB_list_papers.csv with OpenScholar recall
    (other scripts: utilities for DOI resolution and debugging)
```

## Key files

| File | Description |
|---|---|
| `elicit24_points_gate1000_floor1000_20260511.csv` | Pre-generated. Input to `07_paper_figures/scripts/figure4_stage2_boxplot.py` |
| `elicit_queryB_list_papers.csv` | Per-paper recall/hits for Elicit (keyword/question), OpenScholar (normal/deep), and human query |

## Recall computation logic (`compute_elicit_recall_from_export.py`)

Elicit export CSVs include DOIs, so recall is computed via **bidirectional DOI matching**.
Title-based matching is not used.

| Direction | Matching axis |
|---|---|
| Forward | gold PMID → DOI (PubMed esummary) → check if gold DOI exists in Elicit DOI list |
| Reverse | Elicit DOI → PMID (PubMed esearch `[AID]`) → check if resolved PMID is in gold set |

Final TP is the union of both directions. Computed separately for `all` (all results) and
`include` (Elicit include-filtered results).

---

## Regenerating `elicit24_points_gate1000_floor1000_20260511.csv`

Run from `public_release/`:

```bash
# Step 1: compute recall per paper (repeat for each paper_id)
python 08_elicit_queryb_dataset/code/compute_elicit_recall_from_export.py \
  {paper_id} \
  --elicit-csv 08_elicit_queryb_dataset/{paper_id}/"Elicit - screen-results-review-{paper_id}_question.csv" \
  --gold-path 05_test_data/{domain}/{paper_id}/gold_pmids.json

# Step 2: aggregate all 24 papers
python 08_elicit_queryb_dataset/code/compute_24paper_aggregate_gate_floor.py
```

Step 2 also requires LLM posthoc recall CSVs from `06_exclusion_screening_pipeline/results/`
and OpenScholar recall data from `09_openscholar_query_dataset/`.
