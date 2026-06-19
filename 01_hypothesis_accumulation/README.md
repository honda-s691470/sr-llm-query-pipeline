# Hypothesis Accumulation Pipeline — Public Release

## Overview

This directory contains the code for the **hypothesis accumulation** phase of the PubMed query generation pipeline.
Hypothesis accumulation is a Codex-driven iterative search refinement process: starting from an initial query,
the pipeline was executed using GPT-5.3-Codex (OpenAI Codex CLI, `codex exec`),
keeping only modifications that improve recall on the training gold PMIDs.


## Files

| File | Description |
|---|---|
| `prompt_latest.md` | Prompt template for hypothesis accumulation (Codex) |
| `tool_evaluator.py` | Evaluates candidate query modifications against gold PMIDs |
| `tool_fetch_misses.py` | Fetches missed gold PMIDs for targeted term proposal |
| `tool_logger.py` | Logs search history to `search_history.jsonl` |
| `plot_history_ver2.py` | Generates `search_history_plot.png` from search_history.jsonl |

## Training Data

Training outputs (search_history.jsonl, search_history_plot.png) for the 11 training SRs are available at:
`../04_data/{domain}/{paper_id}/`

Domains: 02_Cardiovascular_Disease (3 SRs), 03_Psychiatry (4 SRs), 05_Infectious_Diseases (4 SRs)

## Usage

Pass `prompt_latest.md` to Codex CLI for each target SR. The prompt assumes that:

- `<target_dir>` is an SR-specific working directory under `public_release/04_data/<domain>/<paper_id>/`
- `input_config.json` is present in `<target_dir>`
- the tool files remain in `public_release/01_hypothesis_accumulation/` and are referenced from the prompt via repository-relative paths

```powershell
codex exec --skip-git-repo-check -s danger-full-access -C public_release/04_data/<domain>/<paper_id> -m gpt-5.3-codex - < public_release/01_hypothesis_accumulation/prompt_latest.md
```

In PowerShell, stdin redirection with `< file` is not supported for this command form. Use:

```powershell
Get-Content -Raw "public_release/01_hypothesis_accumulation/prompt_latest.md" | codex exec --skip-git-repo-check -s danger-full-access -C public_release/04_data/02_Cardiovascular_Disease/41684373_2026 -m gpt-5.3-codex -
```

The prompt instructs Codex to run the iterative refinement loop and write `search_history.jsonl` to `<target_dir>`. `input_config.json` (gold PMIDs and SR metadata) must be present in `<target_dir>`. The tool files (`tool_evaluator.py`, `tool_fetch_misses.py`, `tool_logger.py`) do not need to be copied into `<target_dir>`; they are called from `public_release/01_hypothesis_accumulation/` using repository-relative paths.
