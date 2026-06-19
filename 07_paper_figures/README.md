# 07_paper_figures

Scripts and data to reproduce all figures in the paper from `public_release/` data only.

## Requirements

Install dependencies from the repository root:

```bash
pip install -r requirements.txt  # matplotlib, pandas, numpy, requests, python-dotenv
```

## Quick start

Run from `public_release/`:

```bash
# Step 1: build Stage 1 evaluation CSVs from pre-fetched cache (no internet required)
python 07_paper_figures/scripts/build_test_metrics.py

# Step 2: generate all figures
python 07_paper_figures/scripts/figure3_stage1_recall_nnr.py
python 07_paper_figures/scripts/figure3_stage1_boxplot.py
python 07_paper_figures/scripts/figureS2_novel_domains_boxplot.py
python 07_paper_figures/scripts/figure4_stage2_boxplot.py
python 07_paper_figures/scripts/figure5_workload_reduction_forest.py
python 07_paper_figures/scripts/generate_training_figures_v2.py
python 07_paper_figures/scripts/gen_selection_flow.py
```

Output PNGs are written to `07_paper_figures/figures/`.

To re-query the PubMed eUtils API (requires internet, ~5–10 min):

```bash
python 07_paper_figures/scripts/build_test_metrics.py --refresh
```

---

## Directory structure

```
07_paper_figures/
  scripts/
    build_test_metrics.py             -- generates CSVs from cache; --refresh re-queries API
    figure3_stage1_recall_nnr.py      -- Figure 3 bar chart (hardcoded values)
    figure3_stage1_boxplot.py         -- Figure 3 boxplot (reads CSVs)
    figureS2_novel_domains_boxplot.py -- Figure S2 (reads CSVs)
    figure4_stage2_boxplot.py         -- Figure 4 (reads elicit24 CSV)
    figure5_workload_reduction_forest.py -- Figure 5 (hardcoded values)
    generate_training_figures_v2.py   -- Figure 2 + Figure S1 (reads search_history.jsonl)
    gen_selection_flow.py             -- Figure S flow (hardcoded values)
  data/
    test24_eval/
      pubmed_api_cache.json           -- fixed PubMed API results (PMID lists, 168 entries)
      all_test_metrics.csv            -- Stage 1 recall metrics (generated from cache)
      test24_without_laws_all_providers.csv -- without-laws subset
      elicit24_points_gate1000_floor1000_20260511.csv -- Stage 2 metrics
  figures/                            -- output PNGs (generated on run)
```

All scripts read exclusively from within `public_release/`. No external paths are referenced.

---

## Data sources

| Figure | Script | Input | Source |
|---|---|---|---|
| Figure 2, S1 | `generate_training_figures_v2.py` | `search_history.jsonl` × 11 papers | `public_release/04_data/` |
| Figure 3 (bar) | `figure3_stage1_recall_nnr.py` | hardcoded values | — |
| Figure 3 (boxplot), S2 | `figure3_stage1_boxplot.py`, `figureS2_...py` | `all_test_metrics.csv` | `pubmed_api_cache.json` via `build_test_metrics.py` |
| Figure 4 | `figure4_stage2_boxplot.py` | `elicit24_points_*.csv` | `data/test24_eval/` |
| Figure 5 | `figure5_workload_reduction_forest.py` | hardcoded values | — |
| Figure S (flow) | `gen_selection_flow.py` | hardcoded values | — |

---

## PubMed API cache (`pubmed_api_cache.json`)

`pubmed_api_cache.json` stores the PubMed eUtils API results as PMID lists, fixing the
retrieval snapshot used to compute recall. Each entry contains:

```json
{
  "01_Rheumatoid_Arthritis/40815363_2025/claude/with_laws_test_eval": {
    "domain_folder": "01_Rheumatoid_Arthritis",
    "paper_folder":  "40815363_2025",
    "provider":      "claude",
    "condition":     "with_laws_test_eval",
    "total_hits":    1519,
    "hit_pmids":     ["33794784", "29946368", ...]
  }
}
```

`build_test_metrics.py` derives `hit_gold_count` and `recall` from `hit_pmids` offline,
so figures reproduce identically regardless of future PubMed database changes.

---

## Condition label mapping

The published paper refers to the final query version as "with Rulebook (v14)".
In this repository, the same queries are stored under condition `with_laws_test_eval`.
The figure scripts filter on `with_laws_test_eval` accordingly.

---

## Known differences from paper figures

Figures 3 (bar), 4, 5, 2, S1, and S (flow) reproduce **exactly** (pixel-identical).

`figure3_stage1_boxplot.png` and `figureS2_novel_domains_boxplot.png` show minor
distributional differences in the Codex w/o Rulebook group because 15 RA/Oncology
papers' Codex without-laws queries were stored under `without_laws_v13` rather than
`without_laws` and carry slightly different recall values. All other conditions
(`with_laws_test_eval`, `human_reference`, Claude/Gemini `without_laws`) are identical.
