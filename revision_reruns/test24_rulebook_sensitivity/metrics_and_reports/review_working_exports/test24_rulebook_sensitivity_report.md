# Test24 Rulebook Sensitivity Report

We performed an additional sensitivity analysis using independently derived Run 2, Run 3, and pooled-consensus rulebooks. Each rulebook was applied to the same 24 held-out test SLRs without any test-set feedback. We then compared Stage 1 recall/hits and Stage 2 cutoff performance across rulebooks and providers. This analysis was intended to assess operational stability under default stochastic decoding settings, not to claim deterministic reproduction of proprietary LLM outputs.

## Stage 1 Summary

| provider   | rulebook   |   n |   mean_recall |   median_recall |   min_recall |   mean_hits |   median_hits |   mean_nnr |   median_nnr |
|:-----------|:-----------|----:|--------------:|----------------:|-------------:|------------:|--------------:|-----------:|-------------:|
| gemini     | Pooled     |  24 |        0.6296 |          0.6933 |            0 |     9078.21 |         897.5 |    471.357 |      86.1629 |
| gemini     | Run2       |  24 |        0.6296 |          0.6933 |            0 |     9078.21 |         897.5 |    471.357 |      86.1629 |
| gemini     | Run3       |  24 |        0.6296 |          0.6933 |            0 |     9078.42 |         897.5 |    471.362 |      86.1629 |

## Stage 2 (cut70) Summary

| provider   | rulebook   | cutoff   |   n |   mean_Stage_1_recall |   mean_Stage_C_recall |   mean_Stage_1_hits |   mean_Stage_C_hits |   mean_Stage_C_NNR |   mean_recall_loss |   mean_workload_reduction |
|:-----------|:-----------|:---------|----:|----------------------:|----------------------:|--------------------:|--------------------:|-------------------:|-------------------:|--------------------------:|
| gemini     | Pooled     | cut70    |  24 |                0.6296 |                0.5275 |             9078.21 |             699.583 |            87.3403 |             0.0684 |                    0.3559 |
| gemini     | Run2       | cut70    |  24 |                0.6296 |                0.5275 |             9078.21 |             699.583 |            87.3403 |             0.0684 |                    0.3559 |
| gemini     | Run3       | cut70    |  24 |                0.6296 |                0.5275 |             9078.42 |             699.583 |            87.3403 |             0.0684 |                    0.3559 |

