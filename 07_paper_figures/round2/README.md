# Second-revision figures: Figure 4, Figure 5, Figure S5, Figure S6 and Supplementary Table 10

These scripts draw the second-revision (Round 2) figures from the harmonized Stage C analysis in
`stageC_harmonized/` (main analysis: T2 pseudo-abstract, dense weight 0.5, cut70, primary candidate sets).
They run on a CPU and make no network, PubMed or model calls. Run them from any directory:

```bash
python render_figure4_5.py            # Figure 4 and Figure 5
python render_figureS5.py             # Figure S5 (11 panels)
python spearman_figureS6_table10.py   # Figure S6 and Supplementary Table 10
```

Tested with Python 3.14, numpy 2.4.2, pandas 3.0.0, scipy 1.18.1, statsmodels 0.14.6 and matplotlib 3.10.8.
Figures use the Arial font. Outputs are written to `output/`.

| Script | Manuscript item | Main inputs | Outputs |
|---|---|---|---|
| `render_figure4_5.py` | Figure 4, Figure 5 | `../data/test24_eval/elicit24_points_gate1000_floor1000_20260511.csv` (human query, Elicit, OpenScholar); `stageC_harmonized/expected/per_sr_metrics_all.csv` (LLM rows: arm T2, alpha 0.5, cut 70); `stageC_harmonized/expected/primary_tests_vs_human.csv` (p values in Figure 4B) | `Figure4_stage2_mean_ci_bar_T2main.*`, `Figure5_relative_workload_T2main.*`, `Figure4_5_points_data.csv`, `Figure4_5_plotted_values.csv` |
| `render_figureS5.py` | Figure S5 | `stageC_harmonized/expected/per_sr_metrics_7cuts_independent.csv` (scenario primary, arm T2, alpha 0.5); `../clinical_areas/clinical_areas_35reviews.csv`; `revision_reruns/cutoff_sensitivity_overall_domain_reviewtype/data/test24_review_type_classification.csv` | `FigureS5_cutoff_sensitivity_11panel_T2main.*`, `FigureS5_data.csv` |
| `spearman_figureS6_table10.py` | Figure S6, Supplementary Table 10 | `stageC_harmonized/data/` (manifest, score files); `data/` (this folder); `pubmed_cache.zip` (titles); `08_elicit_queryb_dataset/`; `09_openscholar_query_dataset/` | `FigureS6_spearman_all24_T2main.*`, `FigureS6_data.csv` (= Supplementary Table 10), `S6_correlations_both_matching_modes.csv`, `S6_pipeline_coverage.csv` |

## Notes

- Figure 4 confidence intervals: the human-query, Elicit and OpenScholar series use one shared random stream
  (`default_rng(42)`) in method order, as in `../scripts/figure4_v3_mean_ci_bar.py`; each LLM series uses a fresh
  `default_rng(42)`. Figure 5 uses the paired bootstrap of `../scripts/reproduce_stage2_statistics.py`. The script
  checks that the Figure 5 LLM values equal `stageC_harmonized/expected/primary_reduction_search.csv`.
- Figure S6 pipeline scores are the Final Stage C scores of the ChatGPT Codex candidate sets. For the 10 Codex
  reviews passed through without ranking (Stage B hits ≤1,000), `stageC_harmonized/` has no score file. Their
  candidates were scored in the same rescoring run, and those scores are in
  `data/codex_gate_reviews_T2_a0.5_final.csv`.
- `data/pmid_doi_codex_primary_candidates.csv` gives the first DOI in the PubMed ArticleIdList for each Codex
  candidate PMID (PubMed efetch, 2026-11-06; PMIDs without a DOI are omitted). Pipeline and Elicit records are
  matched by DOI. Pairs involving OpenScholar are matched by normalized title.
- The comparator called OpenScholar in input folders and file names (`09_openscholar_query_dataset/`) is labelled
  Asta in the manuscript; the scripts print Asta in figure labels and in `FigureS6_data.csv`.
- These analyses are post hoc and descriptive. No setting was chosen using test-set results.
