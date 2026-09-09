# Rule candidate extraction and similarity

Four candidate rule sets were extracted with `public_release/02_query_laws_refinement/analyze_logs_ver2.py` logic:

- `run1_original`: 11 logs, 175 records, 29 candidate laws; output `public_release/revision_reruns/rule_extraction_sensitivity/candidate_rules_pre_refinement/run1_original/`
- `run2_rerun`: 11 logs, 195 records, 30 candidate laws; output `public_release/revision_reruns/rule_extraction_sensitivity/candidate_rules_pre_refinement/run2_rerun/`
- `run3_rerun`: 11 logs, 187 records, 32 candidate laws; output `public_release/revision_reruns/rule_extraction_sensitivity/candidate_rules_pre_refinement/run3_rerun/`
- `pooled_run1_run2_run3`: 33 logs, 557 records, 37 candidate laws; output `public_release/revision_reruns/rule_extraction_sensitivity/candidate_rules_pre_refinement/pooled_run1_run2_run3/`

## Similarity Metrics

- `jaccard_strict`: overlap of fully normalized law keys: META_ACTION, META_CONCEPT, operator, block, slot, field policy.
- `jaccard_meta_action_concept`: overlap using only the coarse META_ACTION + META_CONCEPT key.
- `top12_do_jaccard`: overlap among the 12 deployment DO-laws selected by the analyzer.
- `top12_avoid_jaccard`: overlap among the 12 AVOID/recall-risk laws selected by the analyzer.
- `deploy_score_spearman_shared` and `deploy_score_cosine_shared`: agreement in Deploy_Score among strictly shared laws.

| A | B | strict Jaccard | coarse Jaccard | shared strict | top12 DO overlap | top12 DO Jaccard | top12 AVOID overlap | top12 AVOID Jaccard | Deploy Spearman | Deploy Cosine |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| run1_original | run2_rerun | 0.686 | 0.686 | 24 | 8 | 0.500 | 6 | 0.500 | 0.681 | 0.709 |
| run1_original | run3_rerun | 0.694 | 0.694 | 25 | 8 | 0.500 | 6 | 0.400 | 0.682 | 0.603 |
| run1_original | pooled_run1_run2_run3 | 0.784 | 0.784 | 29 | 9 | 0.600 | 8 | 0.615 | 0.865 | 0.878 |
| run2_rerun | run3_rerun | 0.771 | 0.771 | 27 | 7 | 0.412 | 8 | 0.615 | 0.716 | 0.854 |
| run2_rerun | pooled_run1_run2_run3 | 0.811 | 0.811 | 30 | 9 | 0.600 | 8 | 0.615 | 0.850 | 0.925 |
| run3_rerun | pooled_run1_run2_run3 | 0.865 | 0.865 | 32 | 10 | 0.714 | 9 | 0.600 | 0.871 | 0.884 |

## Interpretation

At the candidate-extraction stage, use strict Jaccard as a conservative structural similarity measure. Use coarse Jaccard and top-law overlap as more reviewer-friendly measures of whether the same rule families recur across independent runs. The pooled rule set is expected to have broader support and therefore may include rules not present in every individual run.
