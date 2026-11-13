# Clinical areas of the 35 benchmark reviews

This directory contains the clinical-area classification and Figure S3 reproduction script.

## Files
- `clinical_areas_35reviews.csv` — clinical-area classification
  (sha256 99be5fd9c16932ff36aeafb6caa51e2bff7b411205b035d1b61cab16174d43b2). Columns: paper_id, set (train/test), old_domain (label of the collection search), primary_condition,
  mesh_category, rule (1/2/3), new_domain, changed, note. Source of Supplementary Table 1 area columns and Figure S3.
- `figureS3_unseen_areas_mean_ci_bar.py` — reads
  `07_paper_figures/data/test24_eval/all_test_metrics.csv`,
  `07_paper_figures/data/test24_eval/test24_without_laws_all_providers.csv`
  and the classification CSV alongside the script. No internal workspace inputs are required.

## Reproduce Figure S3

Install Python packages `numpy`, `pandas` and `matplotlib`. From the repository root:

```sh
python 07_paper_figures/clinical_areas/figureS3_unseen_areas_mean_ci_bar.py --release-root . --output-dir ../clinical_area_reproduction
```

The script also auto-detects the repository root from its location if `--release-root`
is omitted. It writes only to the output directory, not to the input CSVs.
The figure shows mean recall and NNR with 95% percentile bootstrap intervals
(10,000 resamples, NumPy random seed 42) and individual review values.

## Classification rule (applied to each review's stated objectives)
1. Area = MeSH disease category of the primary condition (population or exposure): CV [C14], PSY [F03], INF [C01],
   ONC [C04], RH (inflammatory/autoimmune rheumatic diseases: inflammatory arthritides, C17.300, C20.111).
2. If Rule 1 assigns no area, the area of the primary outcome.
3. Otherwise "Other".

Composition: training CV 3 / PSY 3 / INF 2 / Other 3; test ONC 7 / RH 6 / CV 4 / PSY 3 / INF 2 / Other 2.
Figure S3: RH + ONC, n = 13.

