# Stage 1 Rulebook Rerun Sensitivity: All Providers

This figure compares the Stage 1 recall of the final queries that were entered into Stage 2 across Run 1, Run 2, Run 3, and pooled rulebooks for Claude, Codex, and Gemini on the 24 held-out test SRs. Run 1 is taken from all_test_metrics.csv condition with_laws_v14, restricted to the Test24 IDs. For rerun conditions with Phase 5 query narrowing, the post-narrowing query entered into Stage 2 is used. NNR is the ordinary per-SLR NNR (raw hits / true-positive hits), averaged across SLRs in the summary table.

| provider   | rulebook   |   n |   mean_recall |   median_recall |   min_recall |   max_recall |   mean_hits |   median_hits |   mean_nnr |   median_nnr |   no_tp_n | source_note                                                   |
|:-----------|:-----------|----:|--------------:|----------------:|-------------:|-------------:|------------:|--------------:|-----------:|-------------:|----------:|:--------------------------------------------------------------|
| Claude     | Run 1      |  24 |        0.8321 |          0.8731 |       0.3333 |            1 |    16464.6  |        1693   |    999.843 |     146.508  |         0 | all_test_metrics.csv:with_laws_v14_stage1_raw                 |
| Claude     | Run 2      |  24 |        0.8619 |          0.8694 |       0.6154 |            1 |    21778.2  |        3823.5 |    974.704 |     249.972  |         0 | test24_stage2_cut70_rulebook_sensitivity_per_paper.csv        |
| Claude     | Run 3      |  24 |        0.8355 |          0.8619 |       0.5    |            1 |    21347.5  |        3297.5 |   1192.79  |     208.134  |         0 | test24_stage2_cut70_rulebook_sensitivity_per_paper_run3.csv   |
| Claude     | Pooled     |  24 |        0.8722 |          0.9004 |       0.6111 |            1 |    16518.7  |        2625.5 |    923.215 |     164.856  |         0 | test24_stage2_cut70_rulebook_sensitivity_per_paper_pooled.csv |
| Codex      | Run 1      |  24 |        0.8272 |          0.8787 |       0.2667 |            1 |     8719.83 |        2036.5 |    360.354 |     169.66   |         0 | all_test_metrics.csv:with_laws_v14_stage1_raw                 |
| Codex      | Run 2      |  24 |        0.8251 |          0.8794 |       0.5    |            1 |     8889.46 |        1800   |    422.719 |     101.511  |         0 | run2_stage2_cut70_phase5_completed_merged.csv                 |
| Codex      | Run 3      |  24 |        0.8369 |          0.9028 |       0.4667 |            1 |    13834.5  |        1880   |    622.74  |     167.758  |         0 | run3_stage1_test24_codex_gpt-5_5.csv                          |
| Codex      | Pooled     |  24 |        0.8504 |          0.8996 |       0.375  |            1 |    10180.9  |        1358   |    385.947 |     152.194  |         0 | pooled_stage2_cut70_medcpt_cuda_phase5_completed_merged.csv   |
| Gemini     | Run 1      |  24 |        0.8883 |          0.9199 |       0.6154 |            1 |    17737    |        2792   |   1138.45  |     188.854  |         0 | all_test_metrics.csv:with_laws_v14_stage1_raw                 |
| Gemini     | Run 2      |  24 |        0.8277 |          0.8918 |       0.5    |            1 |     7161.54 |        3161.5 |    531.073 |     174.833  |         0 | test_prime_A_B_C_posthoc_recall_gemini_20260825_105143.csv    |
| Gemini     | Run 3      |  24 |        0.7588 |          0.8619 |       0      |            1 |     3688.58 |        1531   |    241.127 |      95.4167 |         1 | test24_stage2_phase5_cut70_run3_rb_per_paper.csv              |
| Gemini     | Pooled     |  24 |        0.8512 |          0.9107 |       0.5556 |            1 |     5795.96 |        2138.5 |    273.713 |     113.927  |         0 | test24_stage1_pooled_rb_per_paper.csv                         |

## Files

- `stage1_run1_run2_run3_pooled_all_providers_per_paper.csv`
- `stage1_run1_run2_run3_pooled_all_providers_summary.csv`
- `stage1_recall_nnr_run1_run2_run3_pooled_all_providers_boxplot.png`
- `stage1_recall_nnr_run1_run2_run3_pooled_all_providers_boxplot.pdf`
