# Test24 Rulebook Sensitivity Rerun Files

Generated: 2026-08-31T09:14:22

This directory reorganizes query outputs, stage-cache outputs, per-SR recall/NNR metrics, and summary reports for Claude, Codex, and Gemini across Run1, Run2, Run3, and pooled rulebooks. Source files are copied, not moved, so original analysis directories remain intact.

## Layout

- `qcache/<provider>/<run>/<stage>/<paper_id>/<condition>/`: per-SR query outputs and Stage A/B/C or Phase5/manual narrowing outputs copied from `public_release/05_test_data`.
- `stage1_metrics/raw_eval_exports/<provider>/`: raw query-evaluation CSV exports.
- `stage1_metrics/run1_original_sources/`: original Run1 source metrics used for `with_laws_v14`.
- `stage2_cache_and_metrics/manifests/`: provider-specific stage-cache manifests.
- `stage2_cache_and_metrics/raw_stage_exports/<provider>/`: Stage A/B/C posthoc recall tables, stage tables, markdown reports, and summaries.
- `metrics_and_reports/review_working_exports/`: working per-SR CSV/JSON/MD files used during revision analyses.
- `metrics_and_reports/final_stage1_all_provider/`: final all-provider Run1/Run2/Run3/Pooled Stage1 recall/NNR table and plot files.
- `qcache_availability_summary.csv`: compact provider/run availability check.

## Final Stage 1 Recall Table

## Stage 1 (Query???????Stage2??????????Recall)

| Rulebook   |   Claude |   Codex |   Gemini |
|:-----------|---------:|--------:|---------:|
| Run1       |    0.83  |   0.83  |    0.89  |
| Run2       |    0.862 |   0.825 |    0.828 |
| Run3       |    0.836 |   0.837 |    0.759 |
| Pooled     |    0.872 |   0.85  |    0.851 |


## Copy Summary

- ('final_stage1_all_provider', 'all', 'all', 'copied'): 12
- ('query_or_stage_cache_dir', 'claude', 'pooled', 'copied_dir'): 30
- ('query_or_stage_cache_dir', 'claude', 'run1', 'copied_dir'): 129
- ('query_or_stage_cache_dir', 'claude', 'run2', 'copied_dir'): 28
- ('query_or_stage_cache_dir', 'claude', 'run3', 'copied_dir'): 35
- ('query_or_stage_cache_dir', 'codex', 'pooled', 'copied_dir'): 123
- ('query_or_stage_cache_dir', 'codex', 'run1', 'copied_dir'): 139
- ('query_or_stage_cache_dir', 'codex', 'run2', 'copied_dir'): 155
- ('query_or_stage_cache_dir', 'codex', 'run3', 'copied_dir'): 120
- ('query_or_stage_cache_dir', 'gemini', 'pooled', 'copied_dir'): 120
- ('query_or_stage_cache_dir', 'gemini', 'run1', 'copied_dir'): 129
- ('query_or_stage_cache_dir', 'gemini', 'run2', 'copied_dir'): 210
- ('query_or_stage_cache_dir', 'gemini', 'run3', 'copied_dir'): 207
- ('review_working_metric_or_report', 'all', 'all', 'copied'): 59
- ('run1_original_source', 'all', 'all', 'copied'): 1
- ('stage1_raw_eval_export', 'claude', 'all', 'copied'): 6
- ('stage1_raw_eval_export', 'codex', 'all', 'copied'): 6
- ('stage1_raw_eval_export', 'gemini', 'all', 'copied'): 20
- ('stage2_cache_manifest', 'claude', 'all', 'copied'): 1
- ('stage2_cache_manifest', 'codex', 'all', 'copied'): 1
- ('stage2_cache_manifest', 'gemini', 'all', 'copied'): 1
- ('stage2_raw_stage_export', 'claude', 'all', 'copied'): 96
- ('stage2_raw_stage_export', 'codex', 'all', 'copied'): 348
- ('stage2_raw_stage_export', 'gemini', 'all', 'copied'): 48

## Reproduction Check

Run `python reproduce_stage1_all_provider_from_revision_reruns.py` from this directory or the repository root to regenerate the Stage 1 all-provider per-SR table, summary table, display table, and boxplot using the reorganized files under this directory. The latest check wrote outputs to `repro_check/` and matched `metrics_and_reports/final_stage1_all_provider/stage1_run1_run2_run3_pooled_all_providers_summary.csv` to numerical precision.

Key check file: `repro_check/reproduction_numeric_check.csv`.

## Mean+CI Stage 1 Figure Reproduction

Run `python reproduce_stage1_mean_ci_bar_from_revision_reruns.py` from the repository root or this directory to regenerate the mean+95% bootstrap CI version of the Stage 1 recall/NNR figure from `metrics_and_reports/final_stage1_all_provider/stage1_run1_run2_run3_pooled_all_providers_per_paper.csv`. Outputs are written to `repro_check_mean_ci_bar/`.

The regenerated summary CSV matched `paper/JMIR/revision_rulebook_sensitivity_figures/stage1_run1_run2_run3_pooled_all_providers_mean_ci_summary.csv` exactly, and the regenerated PNG matched `paper/JMIR/revision_rulebook_sensitivity_figures/stage1_recall_nnr_run1_run2_run3_pooled_all_providers_mean_ci_bar.png` byte-for-byte in the 2026-09-02 audit.

