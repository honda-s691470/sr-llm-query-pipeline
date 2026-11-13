# Reproducibility Map

Script and input-data mapping for the analyses included in this release. Paths are relative to the repository root.

Figure and table numbers in the second-revision manuscript are listed in "Second-revision (Round 2) numbering" below. The historical sections keep the first-revision numbering: historical Supplementary Tables 7–9 (failure-case analyses) are not the second-revision Supplementary Tables 7–9 (harmonized Stage 2 results), and historical Figures S1/S2 are not the second-revision Figures S1/S2. The May 2026 Stage 2 inputs reproduce historical Run1 summaries, not the revised primary analysis. This is not an exhaustive map of second-revision supplementary outputs.

## Revised primary analysis

`stageC_harmonized/README.md` documents the harmonized Stage 2 primary analysis and sensitivity conditions. Its offline scripts `code/replay_metrics.py`, `code/statistics.py` and `code/compare_expected.py` reproduce and verify the per-review metrics, confidence intervals, paired tests and relative-workload estimates underlying revised Figures 4–5 from saved score components. See the repository README for commands. These are numerical reproduction scripts, not PowerPoint layout generators.

The revised clinical-area classification is `07_paper_figures/clinical_areas/clinical_areas_35reviews.csv`; the accompanying README provides the portable Figure S3 command. The training set comprises CV 3, PSY 3, INF 2 and other 3 reviews; the test set comprises oncology 7, rheumatology 6, CV 4, PSY 3, INF 2 and other 2. The rheumatology/oncology subgroup contains 13 test reviews. Historical subgroup scripts below retain their earlier classification.

---

## Second-revision (Round 2) numbering

This section follows the numbering of the second-revision manuscript and supplementary files. Sections further below that are labelled "historical" keep the first-revision numbering.

### Figures

| Round 2 number | Content | Reproduction in this release |
|---|---|---|
| Figure 1 | Pipeline schematic | Manually laid out; `07_paper_figures/figures/figure1_pipeline.png` |
| Figure 2 | Hypothesis accumulation example (SR 40357797) | `07_paper_figures/scripts/generate_training_figures_v2.py` |
| Figure 3 | Stage 1 recall/NNR, mean ± 95% CI | `07_paper_figures/scripts/figure3_v4_mean_ci_bar.py` |
| Figure 4 | Stage 2 recall/NNR at cut70, harmonized analysis (T2, alpha 0.50) | `07_paper_figures/round2/render_figure4_5.py` (values from `stageC_harmonized/expected/`, produced by `code/replay_metrics.py` and `code/statistics.py`). `figure4_v3_mean_ci_bar.py` renders the historical Run1 values, not this figure. |
| Figure 5 | Relative screening workload versus the human query, harmonized analysis | `07_paper_figures/round2/render_figure4_5.py` (checks the LLM values against `stageC_harmonized/expected/primary_reduction_search.csv`). `figure5_workload_reduction_forest.py` renders the historical Run1 values. |
| Figure S1 | SR selection flow and gold-standard PMID extraction | `07_paper_figures/scripts/gen_selection_flow.py` (historical "Figure S") |
| Figure S2 | Search histories of the remaining 10 training SRs | `07_paper_figures/scripts/generate_training_figures_v2.py` (historical Figure S1) |
| Figure S3 | Stage 1 recall/NNR, rheumatology and oncology (13 reviews) | `07_paper_figures/clinical_areas/figureS3_unseen_areas_mean_ci_bar.py` |
| Figure S4 | Stage 1 recall by rerun rulebook × LLM | `revision_reruns/test24_rulebook_sensitivity/` (see the historical table below) |
| Figure S5 | Cutoff sensitivity, 11 panels (overall, clinical area, broad review type), harmonized analysis | `07_paper_figures/round2/render_figureS5.py` (per-review metrics: `stageC_harmonized/expected/per_sr_metrics_7cuts_independent.csv`, scenario primary, arm T2, alpha 0.5; groupings: `07_paper_figures/clinical_areas/clinical_areas_35reviews.csv` and `revision_reruns/cutoff_sensitivity_overall_domain_reviewtype/data/test24_review_type_classification.csv`). The 10-panel script in `revision_reruns/cutoff_sensitivity_overall_domain_reviewtype/` reproduces the historical Run1 version. |
| Figure S6 | Spearman correlations of article-level scores (pipeline, Elicit, Asta) | `07_paper_figures/round2/spearman_figureS6_table10.py` (see `07_paper_figures/round2/README.md`) |

### Supplementary Tables

| Round 2 number | Content | Source in this release |
|---|---|---|
| Table 1 | Characteristics of the 35 reviews | Clinical-area columns: `07_paper_figures/clinical_areas/clinical_areas_35reviews.csv`; older version: `revision_reruns/failure_case_analysis_run1/inputs/TableS1_35papers_dataset_ver2.csv` |
| Table 2 | PubMed API settings and MedCPT ranking parameters | `06_exclusion_screening_pipeline/README.md`; harmonized protocol: `stageC_harmonized/environment/protocol.json` |
| Table 3 | MedCPT cut threshold on the training set (cut selection) | Source file not mapped in this release |
| Table 4 | Model identifiers and generation settings | Per-run `result.json` / `run_summary.json` (see the historical table below) |
| Tables 5–6 | Candidate-rule and refined-rulebook overlap across reruns | `revision_reruns/rule_extraction_sensitivity/` (see the historical table below) |
| Table 7 | Per-review recall and NNR at cut70 (main analysis) | `stageC_harmonized/expected/per_sr_metrics_all.csv` (arm T2, alpha 0.5, cut 70); human query: `07_paper_figures/data/test24_eval/elicit24_points_gate1000_floor1000_20260511.csv` |
| Table 8 | Paired comparisons with the human query | `stageC_harmonized/expected/primary_tests_vs_human.csv`, `primary_reduction_search.csv`, `c1_nnr_reanalysis_unified.csv` |
| Table 9 | Sensitivity to candidate set, pseudo-abstract and dense weight | `stageC_harmonized/expected/all_condition_summary.csv`, `paired_arm_contrasts_alpha05_cut70.csv`, `per_sr_metrics_codex_4b8f.csv`, `per_sr_metrics_gemini_inferred714.csv` |
| Table 10 | Spearman correlations (data for Figure S6) | `07_paper_figures/round2/spearman_figureS6_table10.py` → `07_paper_figures/round2/output/FigureS6_data.csv` |
| Tables 11–14 | Failure-case analysis recomputed with Stage 1 as the reference | Not included in this release. `revision_reruns/failure_case_analysis_run1/` implements the first-revision attribution (absence at cut0), which the second revision corrected; its outputs do not match Tables 11–14. The metadata-flag rules of Table 13 are `metadata_flags()` in that script, reused unchanged. |

---

## Main-text Figures (historical numbering)

| Figure | Script | Key inputs | Output |
|---|---|---|---|
| Figure 1 (pipeline schematic) | — (manually laid out, no generating script) | — | `07_paper_figures/figures/figure1_pipeline.png` |
| Figure 2 (hypothesis accumulation example, SR 40357797) | `07_paper_figures/scripts/generate_training_figures_v2.py` | `04_data/` training search-history logs | `07_paper_figures/figures/figure2_hypothesis_accumulation_40357797.png` |
| Figure 3 (Stage 1 recall/NNR, mean ± 95% CI) | `07_paper_figures/scripts/figure3_v4_mean_ci_bar.py` | Fixed `07_paper_figures/data/test24_eval/all_test_metrics.csv`, `test24_without_laws_all_providers.csv` | `07_paper_figures/figures/figure3_v4_mean_ci_bar.png` |
| Figure 4 (Stage 2 recall/NNR at cut70, mean ± 95% CI) | `07_paper_figures/scripts/figure4_v3_mean_ci_bar.py` | `07_paper_figures/data/test24_eval/elicit24_points_gate1000_floor1000_20260511.csv` | `07_paper_figures/figures/figure4_v3_mean_ci_bar.png` |
| Figure 4 (alternate boxplot view) | `07_paper_figures/scripts/figure4_stage2_boxplot.py` | same as above | `07_paper_figures/figures/figure4_stage2_boxplot.png` |
| Figure 5 (relative workload reduction, forest plot) | `07_paper_figures/scripts/reproduce_stage2_statistics.py` then `07_paper_figures/scripts/figure5_workload_reduction_forest.py` | `07_paper_figures/data/test24_eval/elicit24_points_gate1000_floor1000_20260511.csv` | `07_paper_figures/figures/figure5_workload_reduction_forest.png` |

## Supplementary Figures (historical numbering)

| Figure | Script | Key inputs | Output |
|---|---|---|---|
| Figure S1 (10-panel training SR combined view + legend) | `07_paper_figures/scripts/generate_training_figures_v2.py` | `04_data/` training search-history logs | `07_paper_figures/figures/figureS1_hypothesis_accumulation_all10.png`, `figureS1_panel_*.png`, `figureS1_legend_only.png` |
| Figure S2 (Stage 1 recall/NNR, novel domains RA + oncology only) | `07_paper_figures/scripts/figureS2_novel_domains_mean_ci_bar.py` | `07_paper_figures/data/test24_eval/all_test_metrics.csv`, `test24_without_laws_all_providers.csv` | `07_paper_figures/figures/figureS2_novel_domains_mean_ci_bar.png` |
| Figure S (SR selection flow / gold PMID extraction) | `07_paper_figures/scripts/gen_selection_flow.py` | — (flow diagram, hardcoded counts from screening log) | `07_paper_figures/figures/figureS_sr_selection_flow_revised.png` |
| Figure S3 (Stage 1 recall/NNR, rheumatology and oncology, 13 reviews) | `07_paper_figures/clinical_areas/figureS3_unseen_areas_mean_ci_bar.py` | Figure 3 CSVs and `07_paper_figures/clinical_areas/clinical_areas_35reviews.csv` | User-selected output directory; see the clinical-area README |
| Figure S4 (Stage 1 recall by rerun rulebook × LLM, Run1/Run2/Run3/pooled) | `revision_reruns/test24_rulebook_sensitivity/reproduce_stage1_all_provider_from_revision_reruns.py`, `reproduce_stage1_mean_ci_bar_from_revision_reruns.py` | `revision_reruns/test24_rulebook_sensitivity/qcache/`, `stage1_metrics/run1_original_sources/all_test_metrics.csv`, `metrics_and_reports/review_working_exports/` | `revision_reruns/test24_rulebook_sensitivity/repro_check_mean_ci_bar/` |
| Figure S5 (cutoff-sensitivity, 10-panel: overall + by domain + by review type) | `revision_reruns/cutoff_sensitivity_overall_domain_reviewtype/scripts/reproduce_cutoff_sensitivity_10panel.py` | `revision_reruns/cutoff_sensitivity_overall_domain_reviewtype/data/` (`cut0_90_old_cache_same_condition_detail.csv`, `test24_review_type_classification.csv`, `TableS1_35papers_dataset_ver2.csv`) | `revision_reruns/cutoff_sensitivity_overall_domain_reviewtype/repro_check/Supplementary_Figure_cutoff_sensitivity_overall_domain_reviewtype_macroNNR_10panel.png` (+ `.pdf`, `_data.csv`, `Legend_10panel.md`) |

## Supplementary Tables (historical numbering)

| Table | Source | Notes |
|---|---|---|
| Table S1 clinical-area columns (35 reviews, training + test) | `07_paper_figures/clinical_areas/clinical_areas_35reviews.csv` | Revised classification. The older `TableS1_35papers_dataset_ver2.csv` under `revision_reruns/` remains an input to historical analyses, not the revised area classification. |
| Table 2 (PubMed API settings + MedCPT ranking parameters) | `06_exclusion_screening_pipeline/README.md` and pipeline config | Operational detail requested by Reviewer I |
| Table 4 (model identifiers, provider, temperature/top-p, run coverage) | `03_hypothesis_accumlation_test/` and `revision_reruns/test24_rulebook_sensitivity/` `result.json` / `run_summary.json` files record the exact `model` string and settings per run | Consolidated in the manuscript supplement; per-run source values live alongside each provider's `result.json` |
| Table 5 (candidate-rule extraction overlap, Run1 vs Run2 vs Run3) | `revision_reruns/rule_extraction_sensitivity/reproduction_check/supplement_tables/rule_candidate_top_overlap_by_run.csv` | Generated by `revision_reruns/rule_extraction_sensitivity/scripts/reproduce_supplement_rule_similarity_tables.py` |
| Table 6 (final refined-rulebook overlap, Run1/Run2/Run3/pooled) | `revision_reruns/rule_extraction_sensitivity/reproduction_check/supplement_tables/refined_rulebook_shared_by_run.csv` | Same script as Table 5 |
| Table 7 (Stage 1 vs Stage 2 attribution of final missed gold PMIDs) | `revision_reruns/failure_case_analysis_run1/outputs/TableSx_run1_failure_case_summary_by_provider.csv` | Generated by `revision_reruns/failure_case_analysis_run1/reproduce_run1_failure_case_analysis.py` |
| Table 8 (dominant failure locus per review-provider pair) | `revision_reruns/failure_case_analysis_run1/outputs/TableSx_run1_failure_case_by_slr_provider.csv` | Same script as Table 7 |
| Table 9 (worst-case missed-study metadata/bias patterns) | `revision_reruns/failure_case_analysis_run1/inputs/pubmed_requery_20260901/TableSx_run1_exact_requery_worst_missed_study_patterns.csv`, `TableSx_run1_missed_study_metadata_and_bias_analysis_exact_requery.md` | Same script as Table 7; requires the cached PubMed requery snapshot in `pubmed_requery_20260901/` |

## Statistical tests / key numerical claims

| Claim | Location | Reproduced by |
|---|---|---|
| Stage 1 recall, human vs. Claude/Codex/Gemini (Table, Results) | Fixed `07_paper_figures/data/test24_eval/all_test_metrics.csv` and `test24_without_laws_all_providers.csv` | `07_paper_figures/scripts/figure3_v4_mean_ci_bar.py` |
| Historical Run1 Stage 2 recall/NNR at cut70, workload reduction % (superseded by the harmonized analysis) | `07_paper_figures/data/test24_eval/elicit24_points_gate1000_floor1000_20260511.csv` | `07_paper_figures/scripts/figure4_v3_mean_ci_bar.py`, `reproduce_stage2_statistics.py`, `figure5_workload_reduction_forest.py` |
| Candidate-rule / rulebook overlap coefficients (Reviewer E Major Comment 2) | `revision_reruns/rule_extraction_sensitivity/reports/` and `reproduction_check/supplement_tables/` | `revision_reruns/rule_extraction_sensitivity/scripts/extract_rule_candidates_and_similarity.py`, `reproduce_supplement_rule_similarity_tables.py`; verified by `verify_rule_extraction_reproduction.py` |
| Cutoff-sensitivity recall/NNR by domain and review type (Reviewer E Major Comment 3 / Reviewer I) | `revision_reruns/cutoff_sensitivity_overall_domain_reviewtype/repro_check/Supplementary_Figure_..._10panel_data.csv` | `revision_reruns/cutoff_sensitivity_overall_domain_reviewtype/scripts/reproduce_cutoff_sensitivity_10panel.py` |
| Historical Stage 1 vs. Stage 2 attribution of missed gold PMIDs (first revision; superseded by second-revision Supplementary Tables 11–14) | `revision_reruns/failure_case_analysis_run1/outputs/` | `revision_reruns/failure_case_analysis_run1/reproduce_run1_failure_case_analysis.py` |
| Elicit / Asta (OpenScholar) recall and NNR | `08_elicit_queryb_dataset/`, `09_openscholar_query_dataset/` | See each directory's `README.md` |

### Stage 1 and historical Stage 2 statistical methods

| Result | Unit / method | Reproduction status |
|---|---|---|
| Stage 1 recall p values | Two-sided exact paired sign-flip test, enumerating all 2^24 sign assignments across the same 24 SLRs | Implemented in `figure3_v4_mean_ci_bar.py`. From the fixed CSVs: with rulebook, Claude/Codex/Gemini p=0.022/0.056/0.001; without rulebook, p=0.529/0.399/0.958 (rounded to three decimals). The historical v3 script retains fixed labels instead. |
| Stage 1 and Stage 2 mean recall/NNR confidence intervals | Nonparametric bootstrap of SLRs, 10,000 resamples, fixed seed 42 | Recomputed by the Figure 3/4 scripts from the listed Test24 CSV files. |
| Stage 2 p-value annotations | Comparison against the human-query baseline | Recomputed by `07_paper_figures/scripts/reproduce_stage2_statistics.py` from `elicit24_points_gate1000_floor1000_20260511.csv` using d_i = NNR_human_i - NNR_method_i and a one-sided paired sign-flip permutation test (100,000 permutations; seed 42). Recalculation gives Claude p=0.0415, Codex p=0.0225, and Gemini p=0.0239, reproducing 0.042/0.023/0.024 after rounding. |
| Figure 5 R_search estimates and confidence intervals | Relative workload reduction versus human query | Recomputed by `07_paper_figures/scripts/reproduce_stage2_statistics.py` as (mean paired NNR_human - mean paired NNR_method) / mean paired NNR_human. Paired bootstrap resampling of SR rows (10,000 resamples; seed 42) reproduces the reported point estimates and CIs within expected Monte Carlo rounding. |

The historical Figure 5 script reads R_search estimates and intervals from the statistics CSV generated by `reproduce_stage2_statistics.py`; its recall labels retain historical rounded values. These outputs are not the revised primary analysis.

---

## Notes

- `revision_reruns/` contains the historical rulebook reproducibility, subgroup cutoff-sensitivity and failure-case analyses listed above. Each subdirectory describes its scope and reproduction steps.
- The revised Stage 2 numerical reproduction uses the saved score components in `stageC_harmonized/`, without PubMed requests or GPU scoring. The original PubMed cache is a separate provenance/raw-scoring resource (see the main README); it is not needed for this offline metrics/statistics replay.

## Historical Run1 Stage 2 provenance

Historical Run1 Stage 1, A′, A and B queries, Stage A decision logs, deposited Stage C scores and Phase 5 prompts are preserved in `run1_stage2/`. See `run1_stage2/README.md` and `run1_stage2/MANIFEST.csv` for provenance and score-file limitations. These files are separate from the harmonized primary analysis. The unsuffixed snapshots in `05_test_data/*/model_outputs/*/with_laws_stageA_prime/` were written by the August 2026 reruns and are not the Run1 files.
