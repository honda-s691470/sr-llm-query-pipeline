# Test24 Stage 1 Check: Run2 Rulebook with Codex

Date: 2026-08-24

## Inputs

- Provider: codex
- Model: gpt-5.3
- Rulebook: `paper/JMIR/review/rule_extraction_sensitivity/refined_rulebooks/run2_rulebook_refined.txt`
- Test set: `public_release/05_test_data/` (24 papers)
- Output condition: `with_laws_run2_rb_test_eval`
- Run summary: `public_release/03_hypothesis_accumlation_test/runs/20260824_110812/codex/run_summary.json`
- Per-paper source CSV: `public_release/05_test_data/_results/eval_test_codex_gpt-5_5_20260824_110812.csv`

## Completion

- Completed: 24/24
- One initial PubMed recall-check 502 error occurred for `02_Cardiovascular_Disease/41715180_2026`; the saved query was re-evaluated without rerunning the model and the result/summary CSV were updated.

## Aggregate Metrics

| Metric | Mean | Median | Min | Max |
|---|---:|---:|---:|---:|
| Recall | 0.857 | 0.919 | 0.500 | 1.000 |
| Total hits | 20512.667 | 2224.500 | 75.000 | 156528.000 |
| NNR | 1060.813 | 216.547 | 5.000 | 9783.000 |
| F1 | 0.041 | 0.009 | 0.000 | 0.330 |

- `recall < 0.60`: 2 papers
- `recall <= 0.60`: 3 papers

## Lowest Recall Papers

| Domain | Paper | Recall | Hits | Found/Gold | NNR |
|---|---|---:|---:|---:|---:|
| 03_Psychiatry | 41804118_2026 | 0.500 | 12777 | 4/8 | 3194.2 |
| 03_Psychiatry | 41796365_2026 | 0.556 | 378 | 5/9 | 75.6 |
| 01_Rheumatoid_Arthritis | 40815363_2025 | 0.600 | 1818 | 9/15 | 202.0 |
| 05_Infectious_Diseases | 41792577_2026 | 0.615 | 156528 | 16/26 | 9783.0 |
| 02_Cardiovascular_Disease | 41709059_2026 | 0.750 | 715 | 15/20 | 47.7 |
| 04_Oncology | 41781990_2026 | 0.800 | 253 | 8/10 | 31.6 |

## Next Step

Run3 and pooled-consensus rulebooks can be evaluated using the same `--query-laws-path` workflow and distinct `--output-condition` labels. Stage 2/cut70 should be run after Stage 1 outputs for the relevant provider/rulebook combinations are complete.
