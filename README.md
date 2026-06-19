# SR Benchmark — Public Release

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
```

---

## Quick Start

### 1. Generate a PubMed query for a new SR (Stage 1, one-shot)

Provide an LLM (Claude / Codex / Gemini) with:
- `02_query_laws_refinement/test_prompt_with.md` — query construction prompt (with rulebook)
- `02_query_laws_refinement/query_laws_ver14.txt` — finalized rulebook (v14, used in paper)
- `05_test_data/{domain}/{paper_id}/input_config.json` — SR objectives and criteria

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

```bash
cd 07_paper_figures/scripts/
python figure1_pipeline.py   # requires manual layout; see script comments
python figure2_recall_hits_training.py
python figure3_recall_comparison.py
python figure4_nnr_comparison.py
python figure5_workload_reduction_forest.py
```

---

## Datasets

| Set | N | Domains | Purpose |
|---|---:|---|---|
| Training | 11 | CV×3, PSY×4, INF×4 | Hypothesis accumulation + rulebook refinement |
| Test | 24 | RA×7, ONC×7, CV×4, PSY×3, INF×3 | Benchmark evaluation (held out) |

---

## Key Results (Test Set, N=24)

### Stage 1: Recall (raw queries, with rulebook)

| Method | Recall | vs. Human |
|---|---|---|
| Human query | 0.699 [0.592–0.802] | — |
| Gemini with rulebook | **0.888** [0.820–0.943] | +19 pp, p=0.002 |
| Claude with rulebook | **0.832** [0.749–0.904] | +13 pp, p=0.022 |
| Codex with rulebook | **0.817** [0.733–0.893] | +12 pp, p=0.022 |

Recall gains generalized to the two domains absent from training (RA, oncology): +14 to +20 pp vs. human queries.

### Stage 2: Recall vs. NNR after cut70 (top 30% by MedCPT rank, floor=1,000)

| Method | Recall | NNR | Workload reduction vs. Human |
|---|---|---|---|
| Human query | 0.699 | 418 | — |
| Claude cut70 | 0.718 | **93** | −68.5% (p<0.05) |
| Codex cut70 | 0.674 | **100** | −70.7% (p<0.05) |
| Gemini cut70 | 0.713 | **93** | −73.2% (p<0.05) |
| Elicit Question all | 0.591 | 108 | (low recall) |
| OpenScholar normal | 0.301 | 34 | (low recall) |

NNR = Number Needed to Read (hits / TP). Lower is better for screening efficiency.  
All three LLM cut70 conditions maintained recall comparable to the human baseline while reducing NNR by ~4.5×.

---

## Large Data (Zenodo)

The PubMed API response cache (~694 MB, excluded from this repository) is available on Zenodo:

> Honda S, Knevel R, van den Akker EB. *PubMed Cache Data for SR-LLM Query Pipeline Benchmark.* Zenodo, 2026. DOI: [10.5281/zenodo.20392130](https://doi.org/10.5281/zenodo.20392130)

Place the extracted `pubmed_cache/` directory under `06_exclusion_screening_pipeline/` before running Stage 2.

---

## Citation

*(To be added upon publication)*
