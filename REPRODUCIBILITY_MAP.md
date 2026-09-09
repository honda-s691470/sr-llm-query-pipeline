# Reproducibility Map

Every figure, table, and statistical result reported in the manuscript and its supplement, together with the script and input data used to produce it. Paths are relative to `public_release/`.

Produced in response to Reviewer I (Technical: Code/data availability), JMIR AI revision.

---

## Main-text Figures

| Figure | Script | Key inputs | Output |
|---|---|---|---|
| Figure 1 (pipeline schematic) | 窶・(manually laid out, no generating script) | 窶・| `07_paper_figures/figures/figure1_pipeline.png` |
| Figure 2 (hypothesis accumulation example, SR 40357797) | `07_paper_figures/scripts/generate_training_figures_v2.py` | `04_data/` training search-history logs | `07_paper_figures/figures/figure2_hypothesis_accumulation_40357797.png` |
| Figure 3 (Stage 1 recall/NNR, mean ﾂｱ 95% CI) | `07_paper_figures/scripts/figure3_v3_mean_ci_bar.py` | `07_paper_figures/data/test24_eval/all_test_metrics.csv`, `test24_without_laws_all_providers.csv` (built by `build_test_metrics.py`) | `07_paper_figures/figures/figure3_v3_mean_ci_bar.png` |
| Figure 4 (Stage 2 recall/NNR at cut70, mean ﾂｱ 95% CI) | `07_paper_figures/scripts/figure4_v3_mean_ci_bar.py` | `07_paper_figures/data/test24_eval/elicit24_points_gate1000_floor1000_20260511.csv` | `07_paper_figures/figures/figure4_v3_mean_ci_bar.png` |
| Figure 4 (alternate boxplot view) | `07_paper_figures/scripts/figure4_stage2_boxplot.py` | same as above | `07_paper_figures/figures/figure4_stage2_boxplot.png` |
| Figure 5 (relative workload reduction, forest plot) | `07_paper_figures/scripts/reproduce_stage2_statistics.py` then `07_paper_figures/scripts/figure5_workload_reduction_forest.py` | `07_paper_figures/data/test24_eval/elicit24_points_gate1000_floor1000_20260511.csv` | `07_paper_figures/figures/figure5_workload_reduction_forest.png` |

## Supplementary Figures

| Figure | Script | Key inputs | Output |
|---|---|---|---|
| Figure S1 (10-panel training SR combined view + legend) | `07_paper_figures/scripts/generate_training_figures_v2.py` | `04_data/` training search-history logs | `07_paper_figures/figures/figureS1_hypothesis_accumulation_all10.png`, `figureS1_panel_*.png`, `figureS1_legend_only.png` |
| Figure S2 (Stage 1 recall/NNR, novel domains RA + oncology only) | `07_paper_figures/scripts/figureS2_novel_domains_mean_ci_bar.py` | `07_paper_figures/data/test24_eval/all_test_metrics.csv`, `test24_without_laws_all_providers.csv` | `07_paper_figures/figures/figureS2_novel_domains_mean_ci_bar.png` |
| Figure S (SR selection flow / gold PMID extraction) | `07_paper_figures/scripts/gen_selection_flow.py` | 窶・(flow diagram, hardcoded counts from screening log) | `07_paper_figures/figures/figureS_sr_selection_flow_revised.png` |
| Figure S3 (Stage 1 recall, two domains absent from training) | see Figure 3/S2 scripts, subset to RA + oncology rows | same as Figure 3 | (subset view of Figure 3/S2 outputs) |
| Figure S4 (Stage 1 recall by rerun rulebook ﾃ・LLM, Run1/Run2/Run3/pooled) | `revision_reruns/test24_rulebook_sensitivity/reproduce_stage1_all_provider_from_revision_reruns.py`, `reproduce_stage1_mean_ci_bar_from_revision_reruns.py` | `revision_reruns/test24_rulebook_sensitivity/qcache/`, `stage1_metrics/run1_original_sources/all_test_metrics.csv`, `metrics_and_reports/review_working_exports/` | `revision_reruns/test24_rulebook_sensitivity/repro_check_mean_ci_bar/` |
| Figure S5 (cutoff-sensitivity, 10-panel: overall + by domain + by review type) | `revision_reruns/cutoff_sensitivity_overall_domain_reviewtype/scripts/reproduce_cutoff_sensitivity_10panel.py` | `revision_reruns/cutoff_sensitivity_overall_domain_reviewtype/data/` (`cut0_90_old_cache_same_condition_detail.csv`, `test24_review_type_classification.csv`, `TableS1_35papers_dataset_ver2.csv`) | `revision_reruns/cutoff_sensitivity_overall_domain_reviewtype/repro_check/Supplementary_Figure_cutoff_sensitivity_overall_domain_reviewtype_macroNNR_10panel.png` (+ `.pdf`, `_data.csv`, `Legend_10panel.md`) |

## Supplementary Tables

| Table | Source | Notes |
|---|---|---|
| Table S1 (35-paper dataset, training + test) | `revision_reruns/failure_case_analysis_run1/inputs/TableS1_35papers_dataset_ver2.csv` (also duplicated under `cutoff_sensitivity_overall_domain_reviewtype/data/`) | Shared reference dataset used by the S4/S5/failure-case analyses |
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
| Stage 1 recall, human vs. Claude/Codex/Gemini (Table, Results) | `07_paper_figures/data/test24_eval/all_test_metrics.csv` | `07_paper_figures/scripts/build_test_metrics.py` 竊・`figure3_v3_mean_ci_bar.py` |
| Stage 2 recall/NNR at cut70, workload reduction % (Results) | `07_paper_figures/data/test24_eval/elicit24_points_gate1000_floor1000_20260511.csv` | `07_paper_figures/scripts/figure4_v3_mean_ci_bar.py`, `reproduce_stage2_statistics.py`, `figure5_workload_reduction_forest.py` |
| Candidate-rule / rulebook overlap coefficients (Reviewer E Major Comment 2) | `revision_reruns/rule_extraction_sensitivity/reports/` and `reproduction_check/supplement_tables/` | `revision_reruns/rule_extraction_sensitivity/scripts/extract_rule_candidates_and_similarity.py`, `reproduce_supplement_rule_similarity_tables.py`; verified by `verify_rule_extraction_reproduction.py` |
| Cutoff-sensitivity recall/NNR by domain and review type (Reviewer E Major Comment 3 / Reviewer I) | `revision_reruns/cutoff_sensitivity_overall_domain_reviewtype/repro_check/Supplementary_Figure_..._10panel_data.csv` | `revision_reruns/cutoff_sensitivity_overall_domain_reviewtype/scripts/reproduce_cutoff_sensitivity_10panel.py` |
| Stage 1 vs. Stage 2 attribution of missed gold PMIDs, per-provider percentages (Reviewer I - Failure cases) | `revision_reruns/failure_case_analysis_run1/outputs/` | `revision_reruns/failure_case_analysis_run1/reproduce_run1_failure_case_analysis.py` |
| Elicit / Asta (OpenScholar) recall and NNR | `08_elicit_queryb_dataset/`, `09_openscholar_query_dataset/` | See each directory's `README.md` |

### Statistical-method audit

| Result | Unit / method | Reproduction status |
|---|---|---|
| Stage 1 recall p values | One-sided paired sign-flip permutation test (100,000 permutations; seed 42) across the same 24 SLRs | Recomputable from `all_test_metrics.csv`; Claude p=0.022, Codex p=0.056, and Gemini p=0.002 after rounding. |
| Stage 1 and Stage 2 mean recall/NNR confidence intervals | Nonparametric bootstrap of SLRs, 10,000 resamples, fixed seed 42 | Recomputed by the Figure 3/4 scripts from the listed Test24 CSV files. |
| Stage 2 p-value annotations | Comparison against the human-query baseline | Recomputed by `07_paper_figures/scripts/reproduce_stage2_statistics.py` from `elicit24_points_gate1000_floor1000_20260511.csv` using d_i = NNR_human_i - NNR_method_i and a one-sided paired sign-flip permutation test (100,000 permutations; seed 42). Recalculation gives Claude p=0.0415, Codex p=0.0225, and Gemini p=0.0239, reproducing 0.042/0.023/0.024 after rounding. |
| Figure 5 R_search estimates and confidence intervals | Relative workload reduction versus human query | Recomputed by `07_paper_figures/scripts/reproduce_stage2_statistics.py` as (mean paired NNR_human - mean paired NNR_method) / mean paired NNR_human. Paired bootstrap resampling of SR rows (10,000 resamples; seed 42) reproduces the reported point estimates and CIs within expected Monte Carlo rounding. |
| Projected weeks and USD saved | Screening-rate constants applied to R_search | Recomputed by `07_paper_figures/scripts/reproduce_stage2_statistics.py` as weeks = 67.3 x 0.20 x R_search and USD = 141,194.80 x 0.20 x R_search; these remain modeled projections, not prospective measurements. |

The plotting scripts retain the rounded manuscript values for visual stability; the formulas above identify how to recompute them from the public per-SLR data.
---

## Notes

- `revision_reruns/` contains all analyses added or expanded during peer review (rerun-based rulebook reproducibility, cutoff-sensitivity by subgroup, failure-case analysis, and absolute-path/model-name sanitization of the release). Each subdirectory has its own `README.md` describing its scope and reproduction steps.
- Files under `05_test_data/_results/`, `revision_reruns/test24_rulebook_sensitivity/stage1_metrics/raw_eval_exports/`, `revision_reruns/test24_rulebook_sensitivity/audit_model_names_and_paths/`, and the file-level manifest `revision_reruns/test24_rulebook_sensitivity/MANIFEST_revision_reruns_test24_rulebook_sensitivity.jsonl` are regenerable run logs / audit artifacts, not required to reproduce any reported figure, table, or statistic; they are excluded via `.gitignore`.
- The large PubMed API response cache used by Stage 2 (`06_exclusion_screening_pipeline/pubmed_cache/`) is hosted on Zenodo (see main `README.md`) and is not required to reproduce the figures/tables above, which read from precomputed CSV/JSON summaries checked into this repository.




