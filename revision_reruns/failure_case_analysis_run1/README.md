# Run1 Failure-Case and Missed-Study Metadata Analysis

This directory documents the revision analysis added in response to Reviewer I's request for more attention to failure cases, missed-study patterns, and possible systematic retrieval bias.

## Inputs

- Official Run1 cutoff sweep table: `07_paper_figures/data/test24_eval/elicit24_points_gate1000_floor1000_20260511.csv`
- Test24 gold PMIDs and Run1 generated queries: `05_test_data/*/*/gold_pmids.json` and `05_test_data/*/*/model_outputs/{claude,codex,gemini}/with_laws_test_eval/normalized_query.txt`
- Review metadata and broad review type: `revision_reruns/failure_case_analysis_run1/inputs/TableS1_35papers_dataset_ver2.csv`
- Saved PubMed requery/metadata cache: `revision_reruns/failure_case_analysis_run1/inputs/pubmed_requery_20260901/`

## Reproduction

From the repository root, regenerate all failure-case tables from saved local PubMed requery JSON and metadata:

```powershell
python public_release/revision_reruns/failure_case_analysis_run1/reproduce_run1_failure_case_analysis.py
```

To refresh PubMed ESearch/EFetch results, run:

```powershell
python public_release/revision_reruns/failure_case_analysis_run1/reproduce_run1_failure_case_analysis.py --refresh-pubmed --queried-at 2026-09-01
```

The refresh mode uses exact gold-PMID intersection queries of the form `(Run1 PubMed Boolean query) AND (gold PMID OR block)` to avoid ESearch idlist truncation for broad queries.

## Outputs

Primary outputs are written to:

- `paper/Supplement/failure_case_analysis_run1/`
- `revision_reruns/failure_case_analysis_run1/inputs/pubmed_requery_20260901/`

The main supplement-facing files are:

- `TableSx_run1_failure_case_analysis.md`
- `TableSx_run1_failure_case_by_slr_provider.csv`
- `TableSx_run1_missed_study_metadata_and_bias_analysis_exact_requery.md`
- `TableSx_run1_exact_requery_worst_missed_study_patterns.csv`
- `run1_stage1_missed_gold_pmid_characteristics_exact_requery.csv`
- `run1_sr_level_missed_study_bias_summary_exact_requery.csv`

## Interpretation

The analysis reports descriptive failure loci and metadata-level missed-study patterns. It should not be used to infer the direction of downstream meta-analytic bias without extracting outcomes and effect sizes from the missed primary studies.

