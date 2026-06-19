# 02_query_laws_refinement

This directory contains the public-release workflow for refining `query_laws` from the training SRs in `04_data/`.

## Run The Workflow With Codex CLI

If you downloaded `public_release/` as a standalone bundle, open a shell in the `public_release/` directory and run:

```powershell
Get-Content -Raw "02_query_laws_refinement/RUN_WORKFLOW_PROMPT.md" | codex exec --skip-git-repo-check -s danger-full-access -C . -m gpt-5.3-codex -
```

This prompt now covers:

- query-law generation from training `search_history.jsonl`
- per-SR query generation and PubMed evaluation
- Step 3 diagnostics
- optional `SECTION_00` rewrite orchestration when low-performing training SRs meet the rewrite trigger

## Notes

- Run this command from the `public_release/` directory itself.
- The workflow assumes access to:
  - `02_query_laws_refinement/`
  - `04_data/`
  - `01_hypothesis_accumulation/` (for shared prompt/evaluation logic referenced by the workflow)
- `WORKFLOW.md` is the human-readable procedure.
- `RUN_WORKFLOW_PROMPT.md` is the Codex-execution prompt intended to actually run the workflow.
- In PowerShell, `Get-Content -Raw ... | codex exec ... -` is required because `< file` redirection is not supported for this command form.
- `run_workflow.ps1` supports `-AutoRewriteSection00`; the integrated Codex prompt can use that path when Step 3 identifies eligible low-performing training SRs.
- The workflow may create or update:
  - `02_query_laws_refinement/query_laws_ver*.txt`
  - `02_query_laws_refinement/run_logs/step3_diagnostics_*.json`
  - `02_query_laws_refinement/run_logs/step3_review_queue_*.md`
  - `02_query_laws_refinement/run_logs/section00_rewrite_prompt_*.md`
  - `02_query_laws_refinement/run_logs/section00_rewrite_metadata_*.json`
  - `04_data/<domain>/<paper_id>/model_outputs/codex/with_laws_v{N}_training_eval/`
- `query_laws_v{N}.txt` is intentionally copied into each per-SR output directory. It is needed for provenance so each SR result can be traced to the exact law version used for that evaluation.
