# Cutoff Sensitivity: Overall, Domain, and Broad Review Type

This package contains the data and code needed to reproduce the 10-panel supplementary cutoff-sensitivity figure added during revision.

## Inputs

- `data/cut0_90_old_cache_same_condition_detail.csv`: per-SR, per-provider cutoff sweep metrics for the 24-SR test set.
- `data/test24_review_type_classification.csv`: post hoc broad review type classification for the 24 test SRs.
- `data/TableS1_35papers_dataset_ver2.csv`: dataset table with the broad review type column.
- `public_release/05_test_data/`: used by the script to map test SR IDs to clinical domains.

## Reproduction

From the repository root, run:

```bash
python revision_reruns/cutoff_sensitivity_overall_domain_reviewtype/scripts/reproduce_cutoff_sensitivity_10panel.py
```

Outputs are written to `repro_check/`:

- `Supplementary_Figure_cutoff_sensitivity_overall_domain_reviewtype_macroNNR_10panel_data.csv`
- `Supplementary_Figure_cutoff_sensitivity_overall_domain_reviewtype_macroNNR_10panel.png`
- `Supplementary_Figure_cutoff_sensitivity_overall_domain_reviewtype_macroNNR_10panel.pdf`
- `Legend_10panel.md`

The regenerated numeric CSV matches `paper/JMIR/revision_supplement_cutoff_sensitivity/Supplementary_Figure_cutoff_sensitivity_overall_domain_reviewtype_macroNNR_10panel_data.csv` exactly. The regenerated PNG also matched the manuscript-side PNG byte-for-byte in the 2026-09-02 audit.
