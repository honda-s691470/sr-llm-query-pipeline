# Top-N Rule Similarity

Rules were ranked by `Deploy_Score`, with ties ordered by Rep/Suc/Con/Sup. Jaccard uses the same strict structural key as before and does not include score values or rank positions in the key.

## Top 5

| A | B | Shared | Jaccard | Shared / smaller set |
|---|---|---:|---:|---:|
| run1_original | run2_rerun | 2/5 | 0.250 | 0.400 |
| run1_original | run3_rerun | 2/5 | 0.250 | 0.400 |
| run1_original | pooled_run1_run2_run3 | 3/5 | 0.429 | 0.600 |
| run2_rerun | run3_rerun | 3/5 | 0.429 | 0.600 |
| run2_rerun | pooled_run1_run2_run3 | 3/5 | 0.429 | 0.600 |
| run3_rerun | pooled_run1_run2_run3 | 4/5 | 0.667 | 0.800 |

## Top 10

| A | B | Shared | Jaccard | Shared / smaller set |
|---|---|---:|---:|---:|
| run1_original | run2_rerun | 6/10 | 0.429 | 0.600 |
| run1_original | run3_rerun | 5/10 | 0.333 | 0.500 |
| run1_original | pooled_run1_run2_run3 | 7/10 | 0.538 | 0.700 |
| run2_rerun | run3_rerun | 5/10 | 0.333 | 0.500 |
| run2_rerun | pooled_run1_run2_run3 | 7/10 | 0.538 | 0.700 |
| run3_rerun | pooled_run1_run2_run3 | 7/10 | 0.538 | 0.700 |

## Top 12

| A | B | Shared | Jaccard | Shared / smaller set |
|---|---|---:|---:|---:|
| run1_original | run2_rerun | 7/12 | 0.412 | 0.583 |
| run1_original | run3_rerun | 7/12 | 0.412 | 0.583 |
| run1_original | pooled_run1_run2_run3 | 8/12 | 0.500 | 0.667 |
| run2_rerun | run3_rerun | 7/12 | 0.412 | 0.583 |
| run2_rerun | pooled_run1_run2_run3 | 9/12 | 0.600 | 0.750 |
| run3_rerun | pooled_run1_run2_run3 | 10/12 | 0.714 | 0.833 |

## Top 15

| A | B | Shared | Jaccard | Shared / smaller set |
|---|---|---:|---:|---:|
| run1_original | run2_rerun | 11/15 | 0.579 | 0.733 |
| run1_original | run3_rerun | 9/15 | 0.429 | 0.600 |
| run1_original | pooled_run1_run2_run3 | 12/15 | 0.667 | 0.800 |
| run2_rerun | run3_rerun | 11/15 | 0.579 | 0.733 |
| run2_rerun | pooled_run1_run2_run3 | 13/15 | 0.765 | 0.867 |
| run3_rerun | pooled_run1_run2_run3 | 11/15 | 0.579 | 0.733 |

## Top 20

| A | B | Shared | Jaccard | Shared / smaller set |
|---|---|---:|---:|---:|
| run1_original | run2_rerun | 16/20 | 0.667 | 0.800 |
| run1_original | run3_rerun | 15/20 | 0.600 | 0.750 |
| run1_original | pooled_run1_run2_run3 | 17/20 | 0.739 | 0.850 |
| run2_rerun | run3_rerun | 16/20 | 0.667 | 0.800 |
| run2_rerun | pooled_run1_run2_run3 | 17/20 | 0.739 | 0.850 |
| run3_rerun | pooled_run1_run2_run3 | 18/20 | 0.818 | 0.900 |

## Top 25

| A | B | Shared | Jaccard | Shared / smaller set |
|---|---|---:|---:|---:|
| run1_original | run2_rerun | 19/25 | 0.613 | 0.760 |
| run1_original | run3_rerun | 19/25 | 0.613 | 0.760 |
| run1_original | pooled_run1_run2_run3 | 19/25 | 0.613 | 0.760 |
| run2_rerun | run3_rerun | 21/25 | 0.724 | 0.840 |
| run2_rerun | pooled_run1_run2_run3 | 21/25 | 0.724 | 0.840 |
| run3_rerun | pooled_run1_run2_run3 | 21/25 | 0.724 | 0.840 |
