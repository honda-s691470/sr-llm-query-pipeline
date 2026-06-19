## Overview

`public_release/03_hypothesis_accumlation_test` is the query generation and evaluation directory for both the test set and the training set.

Its purpose is to:

- provide the LLM with:
  - `test_prompt_with.md` or `test_prompt_without.md`
  - the latest `public_release/02_query_laws_refinement/query_laws_ver*.txt` when running `with_laws`
  - `input_config.json` for each target paper
- generate one PubMed query per paper
- evaluate the generated query against gold PMIDs
- save outputs under the paper's `model_outputs/` directory

The main entry point is [eval_test.py](eval_test.py).

## Split: test vs train

`eval_test.py` supports two operating modes controlled by `--split`:

| `--split` | Target papers | Output location |
|---|---|---|
| `test` (default) | `05_test_data/` (24 papers) | `05_test_data/<domain>/<paper>/model_outputs/<provider>/<condition>/` |
| `train` | `04_data/` (11 training papers) | `04_data/<domain>/<paper>/model_outputs/<provider>/<condition>/` |

The training set outputs feed directly into the Stage A' training phase in `06_exclusion_screening_pipeline`.

## Inputs

- [test_prompt_with.md](test_prompt_with.md)
- [test_prompt_without.md](test_prompt_without.md)
- the latest `query_laws_ver*.txt` in [02_query_laws_refinement](../02_query_laws_refinement) when `--condition with_laws`
- `input_config.json` in each paper directory (gold PMIDs are read from `gold_pmids.json` for test papers, or from `input_config.json` for training papers)

## What `eval_test.py` does

For each selected paper, the script:

1. prepares an isolated run bundle under `03_hypothesis_accumlation_test/runs/<timestamp>/<provider>/...`
2. copies the prompt, `input_config.json`, and optionally the latest `query_laws_ver*.txt`
3. calls the selected model (Codex / Claude / Gemini via CLI)
4. extracts one final PubMed query from the model response
5. saves outputs to the paper's `model_outputs/<provider>/<condition>/` directory
6. evaluates: `total_hits`, `hit_gold_count`, `recall`, `NNR`, `F1`
7. writes a run-level summary CSV in `<base_data_dir>/_results/`

## Provider Behavior

Provider is inferred from `--model` unless `--provider` is explicitly passed.

- `gpt-5.3-codex` → `codex`
- `claude-*` → `claude`
- `gemini-*` → `gemini`

## Basic Usage

### Test set (default)

```powershell
# All test papers
python public_release/03_hypothesis_accumlation_test/eval_test.py --model gpt-5.3-codex

# Single paper
python public_release/03_hypothesis_accumlation_test/eval_test.py --model gpt-5.3-codex --domain 03_Psychiatry --paper 41796365_2026
```

### Training set

```powershell
# All 11 training papers
python public_release/03_hypothesis_accumlation_test/eval_test.py --model gpt-5.3-codex --split train

# Single training paper
python public_release/03_hypothesis_accumlation_test/eval_test.py --model gpt-5.3-codex --split train --domain 03_Psychiatry --paper 41707176_2026
```

### Gemini

Requires `@google/gemini-cli` and `GEMINI_API_KEY` (read from `.env` at repo root).

```powershell
python public_release/03_hypothesis_accumlation_test/eval_test.py --model gemini-3.0-pro
python public_release/03_hypothesis_accumlation_test/eval_test.py --model gemini-3.0-pro --split train
```

### Claude

The Claude provider calls `claude -p --model <model> --add-dir <run_dir>` via subprocess.

- **Model name:** Use `claude-opus-4-5` (without snapshot date suffix).
- **Binary path (Windows):** `claude.exe` is typically not on the system PATH. Pass the full path with `--claude-bin`.
- **Nested session:** The subprocess automatically unsets `CLAUDECODE`. No manual action required.

```powershell
python public_release/03_hypothesis_accumlation_test/eval_test.py `
  --model claude-opus-4-5 `
  --claude-bin "C:/Users/<your_username>/.local/bin/claude.exe"

python public_release/03_hypothesis_accumlation_test/eval_test.py `
  --model claude-opus-4-5 --split train `
  --claude-bin "C:/Users/<your_username>/.local/bin/claude.exe"
```

### Common options

```powershell
# Prepare bundles only without calling the model
python public_release/03_hypothesis_accumlation_test/eval_test.py --model gpt-5.3-codex --bundle-only

# Skip papers that already have normalized_query.txt
python public_release/03_hypothesis_accumlation_test/eval_test.py --model gpt-5.3-codex --skip-existing

# Override the output condition label
python public_release/03_hypothesis_accumlation_test/eval_test.py --model gpt-5.3-codex --output-condition with_laws_custom_eval
```

## Arguments

| Argument | Default | Description |
|---|---|---|
| `--model` | *(required)* | Model identifier |
| `--split` | `test` | `test` = 05_test_data; `train` = 04_data |
| `--provider` | *(inferred)* | Explicit provider override |
| `--domain` | *(all)* | Restrict to one or more domain folders |
| `--paper` | *(all)* | Restrict to one or more paper folders |
| `--condition` | `with_laws` | `with_laws` or `without_laws` |
| `--output-condition` | `<condition>_test_eval` | Output directory label under `model_outputs/<provider>/` |
| `--skip-existing` | off | Skip papers that already have `normalized_query.txt` |
| `--bundle-only` | off | Prepare input bundles only, do not call the model |

## Outputs

For each paper:

- `normalized_query.txt`
- `raw_last_message.txt`
- `result.json`
- `provider_stdout.log`, `provider_stderr.log`

Run-level files:

- `03_hypothesis_accumlation_test/runs/<timestamp>/<provider>/run_summary.json`
- `<base_data_dir>/_results/eval_test_<provider>_<model>_<timestamp>.csv`

## Notes

- `with_laws` always uses the newest available `query_laws_ver*.txt`.
- Training set gold PMIDs are read from `input_config.json`; test set from `gold_pmids.json`.
