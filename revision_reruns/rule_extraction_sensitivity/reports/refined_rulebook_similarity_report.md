# Refined Rulebook Similarity

This analysis compares the final selected laws in the Run1, Run2, Run3, and pooled-consensus refined rulebooks. The strict key is `META_ACTION + META_CONCEPT + Action_Operator + Target_Block + Target_Slot + Field_Policy`; score values and rank positions are not part of the key.

## Pairwise Similarity

### ALL

| A | B | Shared | Strict Jaccard | Shared / smaller set | Coarse Jaccard | Deploy Spearman |
|---|---|---:|---:|---:|---:|---:|
| run1_rulebook | run2_rulebook | 13/19 | 0.500 | 0.684 | 0.500 | 0.599 |
| run1_rulebook | run3_rulebook | 16/20 | 0.615 | 0.800 | 0.615 | 0.535 |
| run1_rulebook | pooled_consensus_rulebook | 17/20 | 0.680 | 0.850 | 0.680 | 0.811 |
| run2_rulebook | run3_rulebook | 16/19 | 0.640 | 0.842 | 0.640 | 0.791 |
| run2_rulebook | pooled_consensus_rulebook | 17/19 | 0.708 | 0.895 | 0.708 | 0.833 |
| run3_rulebook | pooled_consensus_rulebook | 18/22 | 0.692 | 0.818 | 0.692 | 0.897 |

### DO

| A | B | Shared | Strict Jaccard | Shared / smaller set | Coarse Jaccard | Deploy Spearman |
|---|---|---:|---:|---:|---:|---:|
| run1_rulebook | run2_rulebook | 8/12 | 0.500 | 0.667 | 0.500 | 0.452 |
| run1_rulebook | run3_rulebook | 8/12 | 0.500 | 0.667 | 0.500 | 0.452 |
| run1_rulebook | pooled_consensus_rulebook | 9/12 | 0.600 | 0.750 | 0.600 | 0.933 |
| run2_rulebook | run3_rulebook | 7/12 | 0.412 | 0.583 | 0.412 | 0.714 |
| run2_rulebook | pooled_consensus_rulebook | 9/12 | 0.600 | 0.750 | 0.600 | 0.633 |
| run3_rulebook | pooled_consensus_rulebook | 10/12 | 0.714 | 0.833 | 0.714 | 0.709 |

### AVOID

| A | B | Shared | Strict Jaccard | Shared / smaller set | Coarse Jaccard | Deploy Spearman |
|---|---|---:|---:|---:|---:|---:|
| run1_rulebook | run2_rulebook | 6/9 | 0.500 | 0.667 | 0.500 | 0.714 |
| run1_rulebook | run3_rulebook | 6/9 | 0.400 | 0.667 | 0.400 | 0.657 |
| run1_rulebook | pooled_consensus_rulebook | 8/9 | 0.615 | 0.889 | 0.615 | 0.786 |
| run2_rulebook | run3_rulebook | 8/9 | 0.615 | 0.889 | 0.615 | 0.667 |
| run2_rulebook | pooled_consensus_rulebook | 8/9 | 0.615 | 0.889 | 0.615 | 0.929 |
| run3_rulebook | pooled_consensus_rulebook | 9/12 | 0.600 | 0.750 | 0.600 | 0.917 |

## Top-N Strict Overlap

### ALL

| Top N | A | B | Shared | Strict Jaccard | Shared / smaller set |
|---:|---|---|---:|---:|---:|
| 5 | run1_rulebook | run2_rulebook | 3/5 | 0.429 | 0.600 |
| 5 | run1_rulebook | run3_rulebook | 3/5 | 0.429 | 0.600 |
| 5 | run1_rulebook | pooled_consensus_rulebook | 4/5 | 0.667 | 0.800 |
| 5 | run2_rulebook | run3_rulebook | 4/5 | 0.667 | 0.800 |
| 5 | run2_rulebook | pooled_consensus_rulebook | 4/5 | 0.667 | 0.800 |
| 5 | run3_rulebook | pooled_consensus_rulebook | 4/5 | 0.667 | 0.800 |
| 10 | run1_rulebook | run2_rulebook | 6/10 | 0.429 | 0.600 |
| 10 | run1_rulebook | run3_rulebook | 6/10 | 0.429 | 0.600 |
| 10 | run1_rulebook | pooled_consensus_rulebook | 7/10 | 0.538 | 0.700 |
| 10 | run2_rulebook | run3_rulebook | 7/10 | 0.538 | 0.700 |
| 10 | run2_rulebook | pooled_consensus_rulebook | 8/10 | 0.667 | 0.800 |
| 10 | run3_rulebook | pooled_consensus_rulebook | 8/10 | 0.667 | 0.800 |
| 12 | run1_rulebook | run2_rulebook | 8/11 | 0.533 | 0.727 |
| 12 | run1_rulebook | run3_rulebook | 6/11 | 0.353 | 0.545 |
| 12 | run1_rulebook | pooled_consensus_rulebook | 8/11 | 0.533 | 0.727 |
| 12 | run2_rulebook | run3_rulebook | 8/12 | 0.500 | 0.667 |
| 12 | run2_rulebook | pooled_consensus_rulebook | 8/12 | 0.500 | 0.667 |
| 12 | run3_rulebook | pooled_consensus_rulebook | 9/12 | 0.600 | 0.750 |
| 15 | run1_rulebook | run2_rulebook | 8/14 | 0.400 | 0.571 |
| 15 | run1_rulebook | run3_rulebook | 9/14 | 0.450 | 0.643 |
| 15 | run1_rulebook | pooled_consensus_rulebook | 11/14 | 0.611 | 0.786 |
| 15 | run2_rulebook | run3_rulebook | 12/14 | 0.706 | 0.857 |
| 15 | run2_rulebook | pooled_consensus_rulebook | 12/14 | 0.706 | 0.857 |
| 15 | run3_rulebook | pooled_consensus_rulebook | 12/15 | 0.667 | 0.800 |
| 20 | run1_rulebook | run2_rulebook | 12/19 | 0.462 | 0.632 |
| 20 | run1_rulebook | run3_rulebook | 14/19 | 0.560 | 0.737 |
| 20 | run1_rulebook | pooled_consensus_rulebook | 14/19 | 0.583 | 0.737 |
| 20 | run2_rulebook | run3_rulebook | 15/19 | 0.625 | 0.789 |
| 20 | run2_rulebook | pooled_consensus_rulebook | 16/19 | 0.727 | 0.842 |
| 20 | run3_rulebook | pooled_consensus_rulebook | 14/19 | 0.560 | 0.737 |
| 24 | run1_rulebook | run2_rulebook | 13/19 | 0.500 | 0.684 |
| 24 | run1_rulebook | run3_rulebook | 16/20 | 0.615 | 0.800 |
| 24 | run1_rulebook | pooled_consensus_rulebook | 17/20 | 0.680 | 0.850 |
| 24 | run2_rulebook | run3_rulebook | 16/19 | 0.640 | 0.842 |
| 24 | run2_rulebook | pooled_consensus_rulebook | 17/19 | 0.708 | 0.895 |
| 24 | run3_rulebook | pooled_consensus_rulebook | 18/22 | 0.692 | 0.818 |

### DO

| Top N | A | B | Shared | Strict Jaccard | Shared / smaller set |
|---:|---|---|---:|---:|---:|
| 5 | run1_rulebook | run2_rulebook | 2/5 | 0.250 | 0.400 |
| 5 | run1_rulebook | run3_rulebook | 2/5 | 0.250 | 0.400 |
| 5 | run1_rulebook | pooled_consensus_rulebook | 3/5 | 0.429 | 0.600 |
| 5 | run2_rulebook | run3_rulebook | 3/5 | 0.429 | 0.600 |
| 5 | run2_rulebook | pooled_consensus_rulebook | 3/5 | 0.429 | 0.600 |
| 5 | run3_rulebook | pooled_consensus_rulebook | 4/5 | 0.667 | 0.800 |
| 10 | run1_rulebook | run2_rulebook | 6/10 | 0.429 | 0.600 |
| 10 | run1_rulebook | run3_rulebook | 6/10 | 0.429 | 0.600 |
| 10 | run1_rulebook | pooled_consensus_rulebook | 7/10 | 0.538 | 0.700 |
| 10 | run2_rulebook | run3_rulebook | 5/10 | 0.333 | 0.500 |
| 10 | run2_rulebook | pooled_consensus_rulebook | 7/10 | 0.538 | 0.700 |
| 10 | run3_rulebook | pooled_consensus_rulebook | 7/10 | 0.538 | 0.700 |
| 12 | run1_rulebook | run2_rulebook | 8/12 | 0.500 | 0.667 |
| 12 | run1_rulebook | run3_rulebook | 8/12 | 0.500 | 0.667 |
| 12 | run1_rulebook | pooled_consensus_rulebook | 9/12 | 0.600 | 0.750 |
| 12 | run2_rulebook | run3_rulebook | 7/12 | 0.412 | 0.583 |
| 12 | run2_rulebook | pooled_consensus_rulebook | 9/12 | 0.600 | 0.750 |
| 12 | run3_rulebook | pooled_consensus_rulebook | 10/12 | 0.714 | 0.833 |
| 15 | run1_rulebook | run2_rulebook | 8/12 | 0.500 | 0.667 |
| 15 | run1_rulebook | run3_rulebook | 8/12 | 0.500 | 0.667 |
| 15 | run1_rulebook | pooled_consensus_rulebook | 9/12 | 0.600 | 0.750 |
| 15 | run2_rulebook | run3_rulebook | 7/12 | 0.412 | 0.583 |
| 15 | run2_rulebook | pooled_consensus_rulebook | 9/12 | 0.600 | 0.750 |
| 15 | run3_rulebook | pooled_consensus_rulebook | 10/12 | 0.714 | 0.833 |
| 20 | run1_rulebook | run2_rulebook | 8/12 | 0.500 | 0.667 |
| 20 | run1_rulebook | run3_rulebook | 8/12 | 0.500 | 0.667 |
| 20 | run1_rulebook | pooled_consensus_rulebook | 9/12 | 0.600 | 0.750 |
| 20 | run2_rulebook | run3_rulebook | 7/12 | 0.412 | 0.583 |
| 20 | run2_rulebook | pooled_consensus_rulebook | 9/12 | 0.600 | 0.750 |
| 20 | run3_rulebook | pooled_consensus_rulebook | 10/12 | 0.714 | 0.833 |
| 24 | run1_rulebook | run2_rulebook | 8/12 | 0.500 | 0.667 |
| 24 | run1_rulebook | run3_rulebook | 8/12 | 0.500 | 0.667 |
| 24 | run1_rulebook | pooled_consensus_rulebook | 9/12 | 0.600 | 0.750 |
| 24 | run2_rulebook | run3_rulebook | 7/12 | 0.412 | 0.583 |
| 24 | run2_rulebook | pooled_consensus_rulebook | 9/12 | 0.600 | 0.750 |
| 24 | run3_rulebook | pooled_consensus_rulebook | 10/12 | 0.714 | 0.833 |

### AVOID

| Top N | A | B | Shared | Strict Jaccard | Shared / smaller set |
|---:|---|---|---:|---:|---:|
| 5 | run1_rulebook | run2_rulebook | 3/5 | 0.429 | 0.600 |
| 5 | run1_rulebook | run3_rulebook | 3/5 | 0.429 | 0.600 |
| 5 | run1_rulebook | pooled_consensus_rulebook | 4/5 | 0.667 | 0.800 |
| 5 | run2_rulebook | run3_rulebook | 4/5 | 0.667 | 0.800 |
| 5 | run2_rulebook | pooled_consensus_rulebook | 4/5 | 0.667 | 0.800 |
| 5 | run3_rulebook | pooled_consensus_rulebook | 4/5 | 0.667 | 0.800 |
| 10 | run1_rulebook | run2_rulebook | 6/9 | 0.500 | 0.667 |
| 10 | run1_rulebook | run3_rulebook | 6/9 | 0.462 | 0.667 |
| 10 | run1_rulebook | pooled_consensus_rulebook | 7/9 | 0.583 | 0.778 |
| 10 | run2_rulebook | run3_rulebook | 7/9 | 0.583 | 0.778 |
| 10 | run2_rulebook | pooled_consensus_rulebook | 8/9 | 0.727 | 0.889 |
| 10 | run3_rulebook | pooled_consensus_rulebook | 8/10 | 0.667 | 0.800 |
| 12 | run1_rulebook | run2_rulebook | 6/9 | 0.500 | 0.667 |
| 12 | run1_rulebook | run3_rulebook | 6/9 | 0.400 | 0.667 |
| 12 | run1_rulebook | pooled_consensus_rulebook | 8/9 | 0.615 | 0.889 |
| 12 | run2_rulebook | run3_rulebook | 8/9 | 0.615 | 0.889 |
| 12 | run2_rulebook | pooled_consensus_rulebook | 8/9 | 0.615 | 0.889 |
| 12 | run3_rulebook | pooled_consensus_rulebook | 9/12 | 0.600 | 0.750 |
| 15 | run1_rulebook | run2_rulebook | 6/9 | 0.500 | 0.667 |
| 15 | run1_rulebook | run3_rulebook | 6/9 | 0.400 | 0.667 |
| 15 | run1_rulebook | pooled_consensus_rulebook | 8/9 | 0.615 | 0.889 |
| 15 | run2_rulebook | run3_rulebook | 8/9 | 0.615 | 0.889 |
| 15 | run2_rulebook | pooled_consensus_rulebook | 8/9 | 0.615 | 0.889 |
| 15 | run3_rulebook | pooled_consensus_rulebook | 9/12 | 0.600 | 0.750 |
| 20 | run1_rulebook | run2_rulebook | 6/9 | 0.500 | 0.667 |
| 20 | run1_rulebook | run3_rulebook | 6/9 | 0.400 | 0.667 |
| 20 | run1_rulebook | pooled_consensus_rulebook | 8/9 | 0.615 | 0.889 |
| 20 | run2_rulebook | run3_rulebook | 8/9 | 0.615 | 0.889 |
| 20 | run2_rulebook | pooled_consensus_rulebook | 8/9 | 0.615 | 0.889 |
| 20 | run3_rulebook | pooled_consensus_rulebook | 9/12 | 0.600 | 0.750 |
| 24 | run1_rulebook | run2_rulebook | 6/9 | 0.500 | 0.667 |
| 24 | run1_rulebook | run3_rulebook | 6/9 | 0.400 | 0.667 |
| 24 | run1_rulebook | pooled_consensus_rulebook | 8/9 | 0.615 | 0.889 |
| 24 | run2_rulebook | run3_rulebook | 8/9 | 0.615 | 0.889 |
| 24 | run2_rulebook | pooled_consensus_rulebook | 8/9 | 0.615 | 0.889 |
| 24 | run3_rulebook | pooled_consensus_rulebook | 9/12 | 0.600 | 0.750 |

