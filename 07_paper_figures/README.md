# 07_paper_figures

Scripts and data for selected training and Stage 1 figures, together with historical Run1 Stage 2 plots. The historical Stage 2 inputs are not the harmonized primary results used in revision 2.

For revised Stage 2 primary metrics, tests and sensitivity analyses, use `../stageC_harmonized/README.md` and the repository-level reproduction commands.

## Requirements

Install dependencies from the repository root:

```bash
pip install -r requirements.txt  # matplotlib, pandas, numpy, requests, python-dotenv
```

## Quick start

Run from `public_release/`:

```bash
# Stage 1: use the supplied fixed CSVs; no input rebuilding is needed
python 07_paper_figures/scripts/figure3_v4_mean_ci_bar.py .
python 07_paper_figures/clinical_areas/figureS3_unseen_areas_mean_ci_bar.py --release-root . --output-dir ../clinical_area_reproduction

# Selected training and selection-flow figures
python 07_paper_figures/scripts/generate_training_figures_v2.py
python 07_paper_figures/scripts/gen_selection_flow.py

# Historical Run1 Stage 2 plots (not revision 2 primary results)
python 07_paper_figures/scripts/reproduce_stage2_statistics.py
python 07_paper_figures/scripts/figure4_stage2_boxplot.py
python 07_paper_figures/scripts/figure5_workload_reduction_forest.py
```

Figure 3 and historical PNGs are written to `07_paper_figures/figures/`; Figure S3 uses the explicitly selected output directory.

To re-query the PubMed eUtils API (requires internet, ~5–10 min):

```bash
python 07_paper_figures/scripts/build_test_metrics.py --refresh
```

---

## Directory structure

```
07_paper_figures/
  scripts/
    figure3_v4_mean_ci_bar.py         -- Figure 3 from fixed CSVs, exact paired tests
    build_test_metrics.py             -- generates CSVs from cache; --refresh re-queries API
    figure3_stage1_recall_nnr.py      -- historical bar chart (hardcoded values)
    figure3_stage1_boxplot.py         -- Figure 3 boxplot (reads CSVs)
    figureS2_novel_domains_boxplot.py -- historical Round 1 Figure S2 (reads CSVs)
    figure4_stage2_boxplot.py         -- Figure 4 (reads elicit24 CSV)
    figure5_workload_reduction_forest.py -- historical Figure 5 (statistics CSV and legacy recall labels)
    generate_training_figures_v2.py   -- Figure 2 + Round 2 Figure S2 (historical Figure S1; reads search_history.jsonl)
    gen_selection_flow.py             -- Round 2 Figure S1 flow (historical Figure S; hardcoded values)
  data/
    test24_eval/
      pubmed_api_cache.json           -- fixed PubMed API results (PMID lists, 168 entries)
      all_test_metrics.csv            -- Stage 1 recall metrics (generated from cache)
      test24_without_laws_all_providers.csv -- without-laws subset
      elicit24_points_gate1000_floor1000_20260511.csv -- Stage 2 metrics
  figures/                            -- output PNGs (generated on run)
  clinical_areas/                     -- revised classification and portable Figure S3
```

Run the commands from the repository root using the supplied input files. Historical plotting scripts retain their original figure numbering. Second-revision numbering: see `REPRODUCIBILITY_MAP.md`. Second-revision Figures 4, 5, S5 and S6 and Supplementary Table 10 are drawn by the scripts in `round2/` (see `round2/README.md`).

---

## Data sources

| Figure | Script | Input | Source |
|---|---|---|---|
| Figure 2, Round 2 S2 (historical S1) | `generate_training_figures_v2.py` | `search_history.jsonl` × 11 papers | `public_release/04_data/` |
| Figure 3 (bar) | `figure3_v4_mean_ci_bar.py` | fixed `all_test_metrics.csv` and `test24_without_laws_all_providers.csv` | `data/test24_eval/` |
| Figure S3 | `clinical_areas/figureS3_unseen_areas_mean_ci_bar.py` | Figure 3 CSVs plus `clinical_areas_35reviews.csv` | `clinical_areas/README.md` |
| Figure 3 (boxplot), historical S2 | `figure3_stage1_boxplot.py`, `figureS2_...py` | `all_test_metrics.csv` | `pubmed_api_cache.json` via `build_test_metrics.py` |
| Historical Figure 4 | `figure4_stage2_boxplot.py` | `elicit24_points_*.csv` | `data/test24_eval/` |
| Historical Figure 5 | `figure5_workload_reduction_forest.py` | `reproduced_stage2_statistics.csv` and legacy recall labels | `reproduce_stage2_statistics.py` |
| Round 2 Figure S1 (flow) | `gen_selection_flow.py` | hardcoded values | — |

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
using the fixed retrieval snapshot rather than today's PubMed results. Using `--refresh` creates a new retrieval snapshot and is not historical reproduction.

---

## Condition label mapping

The published paper refers to the final query version as "with Rulebook (v14)".
In this repository, the same queries are stored under condition `with_laws_test_eval`.
The figure scripts filter on `with_laws_test_eval` accordingly.

---

## Historical figure inputs

These scripts include historical plots; their presence does not imply pixel-identical reproduction of every revised manuscript figure.

`figure3_stage1_boxplot.png` and `figureS2_novel_domains_boxplot.png` show minor
distributional differences in the Codex w/o Rulebook group because 15 RA/Oncology
papers' Codex without-laws queries were stored under `without_laws_v13` rather than
`without_laws` and carry slightly different recall values. All other conditions
(`with_laws_test_eval`, `human_reference`, Claude/Gemini `without_laws`) are identical.
