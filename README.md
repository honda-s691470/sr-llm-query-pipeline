# SR Benchmark 窶・Public Release

Reproducibility package for the paper:  
**"An Agentic Learning Framework for Systematic Review Literature Search"**

Suguru Honda, Rachel Knevel, Erik B van den Akker  
Leiden University Medical Center

---

## Pipeline Overview

![Figure 1: SR-LLM Query Pipeline](07_paper_figures/figures/figure1_pipeline.png)

**Figure 1.** Overview of the two-stage pipeline. Stage 1 derives a structured Boolean query rulebook through iterative hypothesis accumulation on training SRs (left), then applies it one-shot to generate queries for held-out SRs. Stage 2 applies exclusion-criteria-based filtering and MedCPT semantic re-ranking to reduce screening workload while preserving recall (right).

---

## Directory Structure

```
public_release/
  01_hypothesis_accumulation/          # Stage 1: Iterative hypothesis accumulation pipeline (Codex CLI)
  02_query_laws_refinement/            # Stage 1: Law extraction + iterative rulebook refinement workflow
  03_hypothesis_accumlation_test/      # Stage 1: One-shot query generation & evaluation (Claude / Codex / Gemini)
  04_data/                             # Training SR input configs (11 papers) and model outputs
  05_test_data/                        # Test SR data (24 papers: gold PMIDs, human queries, input configs, model outputs)
  06_exclusion_screening_pipeline/     # Stage 2: Exclusion filtering + MedCPT semantic re-ranking pipeline
  07_paper_figures/                    # Scripts and data to reproduce all paper figures
  08_elicit_queryb_dataset/            # Elicit retrieval results and recall computation
  09_openscholar_query_dataset/        # OpenScholar (Asta) retrieval results and recall computation
  revision_reruns/                     # Reviewer-requested analyses added during peer review (rerun reproducibility, cutoff sensitivity, failure cases)
```

See `REPRODUCIBILITY_MAP.md` for the complete figure/table/statistic 竊・script/data mapping, including the `revision_reruns/` analyses.

---

## Quick Start

### 1. Generate a PubMed query for a new SR (Stage 1, one-shot)

Provide an LLM (Claude / Codex / Gemini) with:
- `02_query_laws_refinement/test_prompt_with.md` 窶・query construction prompt (with rulebook)
- `02_query_laws_refinement/query_laws_ver14.txt` 窶・finalized rulebook (v14, used in paper)
- `05_test_data/{domain}/{paper_id}/input_config.json` 窶・SR objectives and criteria

Evaluate recall via PubMed:
```
(generated_query) AND (PMID1[uid] OR PMID2[uid] OR ...)
```
Gold PMIDs are in `05_test_data/{domain}/{paper_id}/gold_pmids.json`.

### 2. Reproduce hypothesis accumulation (training set)

See `01_hypothesis_accumulation/README.md`.  
Training search histories are in `02_query_laws_refinement/02_input_logs/`.

### 3. Reproduce query law refinement

See `02_query_laws_refinement/WORKFLOW.md` for the full 3-step workflow.

### 4. Reproduce Stage 2 exclusion screening + re-ranking

See `06_exclusion_screening_pipeline/README.md`.

### 5. Reproduce paper figures

Figure 1 is a manually laid-out schematic (no generating script); the remaining figures are reproduced with:

```bash
cd 07_paper_figures/scripts/
python build_test_metrics.py             # builds data/test24_eval/all_test_metrics.csv + test24_without_laws_all_providers.csv (must run first)
python generate_training_figures_v2.py   # Figure 2, Figure S1, legend-only panel
python figure3_v3_mean_ci_bar.py         # Figure 3 (Stage 1 recall/NNR)
python figure4_v3_mean_ci_bar.py         # Figure 4 (Stage 2 recall/NNR, cut70)
python figure4_stage2_boxplot.py         # Figure 4 alternate boxplot view
python figureS2_novel_domains_mean_ci_bar.py  # Figure S2 (RA + oncology only)
python gen_selection_flow.py             # Figure S: SR selection flow / gold PMID extraction
python reproduce_stage2_statistics.py        # Stage 2 NNR tests, R_search, projected savings
python figure5_workload_reduction_forest.py   # Figure 5 (workload reduction forest plot)
```

For the reviewer-requested supplementary analyses added during revision (rerun-based rulebook reproducibility, cutoff-sensitivity by domain/review-type, and failure-case analysis), see `REPRODUCIBILITY_MAP.md`, which lists every figure/table together with its generating script and required inputs, including the analyses under `revision_reruns/`.

---

## Datasets

| Set | N | Domains | Purpose |
|---|---:|---|---|
| Training | 11 | CVﾃ・, PSYﾃ・, INFﾃ・ | Hypothesis accumulation + rulebook refinement |
| Test | 24 | RAﾃ・, ONCﾃ・, CVﾃ・, PSYﾃ・, INFﾃ・ | Benchmark evaluation (held out) |

---

## Key Results (Test Set, N=24)

### Stage 1: Recall (raw queries, with rulebook)

| Method | Recall | vs. Human |
|---|---|---|
| Human query | 0.699 [0.592窶・.802] | 窶・|
| Gemini with rulebook | **0.888** [0.820窶・.943] | +19 pp, p=0.002 |
| Claude with rulebook | **0.832** [0.749窶・.904] | +13 pp, p=0.022 |
| Codex with rulebook | **0.817** [0.733窶・.893] | +12 pp, p=0.022 |

Recall gains generalized to the two domains absent from training (RA, oncology): +14 to +20 pp vs. human queries.

### Stage 2: Recall vs. NNR after cut70 (top 30% by MedCPT rank, floor=1,000)

| Method | Recall | NNR | Workload reduction vs. Human |
|---|---|---|---|
| Human query | 0.699 | 418 | 窶・|
| Claude cut70 | 0.718 | **93** | 竏・8.5% (p<0.05) |
| Codex cut70 | 0.674 | **100** | 竏・0.7% (p<0.05) |
| Gemini cut70 | 0.713 | **93** | 竏・3.2% (p<0.05) |
| Elicit Question all | 0.591 | 108 | (low recall) |
| OpenScholar normal | 0.301 | 34 | (low recall) |

NNR = Number Needed to Read (hits / TP). Lower is better for screening efficiency.  
All three LLM cut70 conditions maintained recall comparable to the human baseline while reducing NNR by ~4.5ﾃ・

---

## Large Data (Zenodo)

The PubMed API response cache (~694 MB, excluded from this repository) is available on Zenodo:

> Honda S, Knevel R, van den Akker EB. *PubMed Cache Data for SR-LLM Query Pipeline Benchmark.* Zenodo, 2026. DOI: [10.5281/zenodo.20392130](https://doi.org/10.5281/zenodo.20392130)

Place the extracted `pubmed_cache/` directory under `06_exclusion_screening_pipeline/` before running Stage 2.

---

## Citation

*(To be added upon publication)*


