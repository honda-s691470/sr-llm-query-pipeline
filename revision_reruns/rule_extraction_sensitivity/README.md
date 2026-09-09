# Revision Rule Extraction Sensitivity Reruns

This directory contains the public-release copy of the rulebook sensitivity rerun inputs and outputs.

## Layout

- `raw_training_logs/run2/04_data/`: raw training SLR search histories generated in independent Codex Run 2.
- `raw_training_logs/run3/04_data/`: raw training SLR search histories generated in independent Codex Run 3.
- `raw_training_logs/pooled_run1_run2_run3_log_manifest.csv`: repository-relative manifest for the pooled input logs. Run 1 logs are the original training logs in `public_release/04_data/`; Run 2 and Run 3 logs are copied in this directory.
- `candidate_rules_pre_refinement/`: extracted candidate rules before iterative refinement.
- `refined_rulebooks/`: final refined rulebooks for Run 2, Run 3, and pooled consensus.
- `reports/`: similarity summaries for candidate rules and refined rulebooks.

## Model name convention

- Codex: `gpt-5.3-codex`
- Claude Opus: `claude-opus-4-5-20251001`
- Gemini Run 1: `gemini-3.0-pro`
- Gemini Run 2 / Run 3 / Pooled: `gemini-3.1-pro-preview`

All paths in manifests and result files should be repository-relative, not drive-specific absolute paths.

## Supplement Table Reproduction

Run `python scripts/reproduce_supplement_rule_similarity_tables.py` from the repository root to regenerate the supplementary CSV tables:

- `refined_rulebook_shared_by_run.csv`
- `rule_candidate_top_overlap_by_run.csv`

Outputs are written to `reproduction_check/supplement_tables/` and matched the files in `paper/Supplement/` exactly in the 2026-09-02 audit.
