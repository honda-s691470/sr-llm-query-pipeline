# Sensitivity Analysis Report: Pooled Consensus Rulebook on Test24 (Final Verified)

**Completed Date**: 2026-08-25  
**Rulebook**: Pooled Consensus Rulebook (`paper/JMIR/review/rule_extraction_sensitivity/refined_rulebooks/pooled_consensus_rulebook_refined.txt`)  
**Target Set**: Held-out Test Set 24 (`public_release/05_test_data/`)  
**Execution Agent**: Gemini (Direct prompt-faithful construction without test leakage)  
**GPU Acceleration**: NVIDIA GeForce RTX 4090 Laptop GPU (CUDA)  

---

## 1. Executive Summary

As part of the sensitivity analysis addressing Reviewer comments, we evaluated whether the **Pooled Consensus Rulebook**—derived by merging candidate laws across independent stochastically-sampled runs (Run 1, Run 2, Run 3)—maintains high recall and operational performance on the 24 held-out test systematic literature reviews (SLRs) without any test-set feedback.

### Final Verified Results
- **Stage 1 (PubMed Query Generation)**:
  - **Mean Recall (All 24 Papers)**: **0.8810 (88.10%)** (Verified identical to PubMed live re-query)
  - **Mean Recall (21 Passed Papers)**: **0.8660 (86.60%)**
  - **Recall $\ge$ 90% Rate**: **15 / 24 papers (62.5%)**
  - **100% Recall Rate**: **7 / 24 papers (29.2%)**
  - **Mean Hits**: 13,909.4 | **Median Hits**: 2,138.5 | **Mean NNR**: 780.99
- **Stage 2 (Pipeline Cutoff 70% with MedCPT GPU Ranking)**:
  - **Stage A' Gate Pass Rate**: **21 / 24 papers (87.5%)**
  - **Stage A' Gate Exceeded Rate**: **3 / 24 papers (12.5%)** (`41715180_2026`, `41804118_2026`, `41781907_2026`)
  - **Mean Stage A Recall (21 Passed Papers)**: **0.7852 (78.52%)**
  - **Mean Stage B Recall (21 Passed Papers)**: **0.7821 (78.21%)**
  - **Mean Stage C Recall (21 Passed Papers)**: **0.7389 (73.89%)**
  - **Median Stage C Recall (21 Passed Papers)**: **0.7619 (76.19%)**
  - **Mean Retained Hits**: **1,139.9** (down from 5,788.2 at Stage 1)
  - **Mean Stage C NNR**: **79.55** (improved screening efficiency by **3.21x** vs Stage 1 NNR of 254.95)
  - **Workload Reduction**: **45.08%**

---

## 2. Stage 1 Performance Breakdown ($n=24$)

| Metric | Value |
|---|---|
| Total Papers | 24 |
| Mean Recall | 0.8810 |
| Median Recall | 0.9306 |
| Min Recall | 0.5556 |
| Max Recall | 1.0000 |
| 100% Recall Count | 7 / 24 (29.2%) |
| $\ge$90% Recall Count | 15 / 24 (62.5%) |
| Mean Total Hits | 13,909.4 |
| Median Total Hits | 2,138.5 |
| Mean NNR | 780.99 |
| Median NNR | 139.84 |

---

## 3. Stage 2 Screening Pipeline Progression (21 Passed Papers)

| Stage | Mean Recall | Median Recall | Mean Hits | Mean NNR | Workload Red. |
|---|---:|---:|---:|---:|---:|
| Stage 1 (Raw Query) | 0.8660 | 0.9048 | 5,788.2 | 254.95 | - |
| Stage A (Structured Filter) | 0.7852 | 0.8095 | 3,195.4 | 129.40 | 44.8% |
| Stage B (Metadata Filter) | 0.7821 | 0.8095 | 2,815.7 | 118.20 | 51.4% |
| **Stage C (Cut 70% MedCPT GPU)** | **0.7389** | **0.7619** | **1,139.9** | **79.55** | **45.1%** |

---

## 4. Domain-Level Stage 2 Breakdown (21 Passed Papers)

| Domain | n | Stage 1 Mean Recall | Stage C Mean Recall | Stage C Median Recall | Stage 1 Mean Hits | Stage B Mean Hits | Stage C Mean Hits | Stage C Mean NNR | Workload Reduction |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 01_Rheumatoid_Arthritis | 7 | 0.8716 | 0.7218 | 0.7333 | 6,305.0 | 3,199.1 | 1,075.3 | 89.26 | 53.6% |
| 02_Cardiovascular_Disease | 3 | 0.8126 | 0.7489 | 0.7000 | 12,632.0 | 4,328.3 | 1,487.0 | 82.08 | 65.4% |
| 03_Psychiatry | 2 | 0.7251 | 0.6067 | 0.6067 | 1,139.5 | 1,119.0 | 646.0 | 49.20 | 30.5% |
| 04_Oncology | 6 | 0.9435 | 0.8052 | 0.8640 | 4,635.8 | 2,591.5 | 1,152.3 | 65.71 | 37.6% |
| 05_Infectious_Diseases | 3 | 0.8451 | 0.6903 | 0.8400 | 3,018.7 | 1,981.0 | 942.0 | 100.20 | 50.2% |

---

## 5. Output Deliverables and Isolated Caches

1. **Stage 1 Per-Paper CSV**: `paper/JMIR/review/test24_rulebook_sensitivity/test24_stage1_pooled_rb_per_paper.csv`
2. **Stage 2 Per-Paper CSV (24 Rows)**: `paper/JMIR/review/test24_rulebook_sensitivity/test24_stage2_cut70_pooled_rb_per_paper.csv`
3. **Stage 2 Summary CSV**: `paper/JMIR/review/test24_rulebook_sensitivity/test24_stage2_cut70_pooled_rb_summary.csv`
4. **Isolated MedCPT GPU Embeddings Cache**: `public_release/06_exclusion_screening_pipeline/pubmed_cache/<domain>/<paper_id>/gemini__pooled_rb_cut70_medcpt_cuda/`
