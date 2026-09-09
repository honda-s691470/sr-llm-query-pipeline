# Stage 1 Rulebook Rerun Sensitivity: Codex Provider

This figure compares Stage 1 raw query-generation performance across the original Run 1 rulebook, independently derived Run 2 and Run 3 rulebooks, and the pooled-consensus rulebook. All values use the 24 held-out test SRs and the Codex provider. NNR is the ordinary per-SLR NNR (hits/true-positive hits), averaged across SLRs in the summary table.

| provider   | rulebook   |   n |   mean_recall |   median_recall |   min_recall |   max_recall |   mean_hits |   median_hits |   mean_nnr |   median_nnr |   no_tp_n |
|:-----------|:-----------|----:|--------------:|----------------:|-------------:|-------------:|------------:|--------------:|-----------:|-------------:|----------:|
| Codex      | Run 1      |  24 |        0.7576 |          0.8454 |       0.1111 |            1 |     3063.25 |        1875.5 |    265.353 |      147.667 |         0 |
| Codex      | Run 2      |  24 |        0.8574 |          0.9189 |       0.5    |            1 |    20512.7  |        2224.5 |   1060.81  |      216.547 |         0 |
| Codex      | Run 3      |  24 |        0.8369 |          0.9028 |       0.4667 |            1 |    13834.5  |        1880   |    622.74  |      167.758 |         0 |
| Codex      | Pooled     |  24 |        0.9003 |          0.9235 |       0.6154 |            1 |    19388.4  |        1996   |   1183.9   |      159.388 |         0 |

## Files

- `stage1_run1_run2_run3_pooled_codex_per_paper.csv`
- `stage1_run1_run2_run3_pooled_codex_summary.csv`
- `stage1_recall_nnr_run1_run2_run3_pooled_codex_boxplot.png`
- `stage1_recall_nnr_run1_run2_run3_pooled_codex_boxplot.pdf`
