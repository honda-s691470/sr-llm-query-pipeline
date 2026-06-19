# 06_exclusion_screening_pipeline

Exclusion-screening pipeline for systematic review candidate reduction.
Takes a PubMed query, applies staged exclusion logic, and reduces the candidate universe without sacrificing recall.

For stage design details see [PIPELINE_DESIGN.md](PIPELINE_DESIGN.md).

---

## Entry point

`run_pipeline_prime_A_B_C.py` — unified runner for both training and test modes.

| Mode | Dataset | Query source | Recall during pipeline |
|---|---|---|---|
| `training` | `04_data/` (11 papers) | `04_data/…/model_outputs/<provider>/with_laws_test_eval/` | Live (Δrecall ≤ `--recall-threshold` gate, default 0.02) |
| `test` | `05_test_data/` (24 papers, via manifest) | `05_test_data/…/model_outputs/<provider>/with_laws_test_eval/` | Post-hoc only |

---

## Usage

Run from the repository root (`public_release/`).

### Training mode
```bash
python 06_exclusion_screening_pipeline/run_pipeline_prime_A_B_C.py \
  --mode training --provider codex \
  --stagec-gate-hits 1000 --stagec-floor-hits 1000 --stagec-cut-percent 30
```

### Test mode
```bash
python 06_exclusion_screening_pipeline/run_pipeline_prime_A_B_C.py \
  --mode test --provider codex \
  --stagec-gate-hits 1000 --stagec-floor-hits 1000 --stagec-cut-percent 30
```

Supported `--provider` values: `codex`, `claude`, `gemini`.

### Optional flags
```
--manifest path/to/manifest.json   Override test manifest
--query-provider <provider>        Override query source provider
--query-condition <condition>      Override query source condition (default: with_laws_test_eval)
--paper-id <paper_id>              Run only one paper (works in both modes)
--no-hyde                          Use objectives+inclusion text instead of HyDE
--hyde-api                         HyDE via API call (default: local structured)
--device cuda                      GPU device for MedCPT
--target 9999                      [test] Hit count target for Stage A' gate
--recall-threshold 0.02            Max ΔRecall allowed for Phase 1/3 NOT-block acceptance
                                   (default: 0.02; raise e.g. to 0.075 to allow more hits
                                   reduction at the cost of some recall loss)
```

### Phase 5 manual rewrite via Codex CLI
Run from `public_release/`. Send the paper-specific `phase5_manual_prompt.md` to Codex, save the raw one-line query directly to `with_laws_stageA_prime/normalized_query.txt`, then rerun the pipeline.

```powershell
# Example paper: 04_data/02_Cardiovascular_Disease/41684373_2026

Get-Content -Raw "04_data/02_Cardiovascular_Disease/41684373_2026/model_outputs/codex/with_laws_stageA_prime_phase5_pending/phase5_manual_prompt.md" `
  | codex exec --skip-git-repo-check -s danger-full-access -C . -m gpt-5.3-codex - `
  | Set-Content "04_data/02_Cardiovascular_Disease/41684373_2026/model_outputs/codex/with_laws_stageA_prime/normalized_query.txt"

python 06_exclusion_screening_pipeline/run_pipeline_prime_A_B_C.py `
  --mode training --provider codex `
  --paper-id 41684373_2026 `
  --query-condition with_laws_stageA_prime `
  --stagec-gate-hits 1000 --stagec-floor-hits 1000 --stagec-cut-percent 30
```

---

### Phase 5 rerun (after manual rewrite)
```bash
python 06_exclusion_screening_pipeline/run_pipeline_prime_A_B_C.py \
  --mode training --provider codex \
  --query-condition with_laws_stageA_prime \
  --stagec-gate-hits 1000 --stagec-floor-hits 1000 --stagec-cut-percent 30
```
---

## Source files

| File | Purpose |
|---|---|
| `run_pipeline_prime_A_B_C.py` | Unified runner (test + training) |
| `run_eval_training11_stages.py` | Stage A' Phase 1 block definitions and Phase 3 tier functions |
| `src/exclusion_parser.py` | Stage A NOT-filter parser and Stage B metadata filter |
| `src/pubmed_fetcher.py` | PubMed esearch / esummary / efetch with throttling |
| `src/ranker.py` | BM25 + MedCPT hybrid ranker, HyDE generation |
| `src/stagec_final.py` | Stage C final score formula |
| `src/stage_query_storage.py` | Stage snapshot persistence |
| `src/phase5_rewriter.py` | Phase 5 manual-rewrite prompt builder |

---

## Stage A' Self-Refinement Loop

Automatically improves Phase 1 block priority order and Phase 3 tier order from empirical training-set statistics.

The loop always uses `with_laws_test_eval` queries as input. Phase 5 rewritten queries (`with_laws_stageA_prime`) are NOT used as loop input. Phase 5 is a separate manual fallback applied after the loop completes, for papers that still exceed 9999 hits.

Each iteration runs 4 steps:
1. `run_pipeline_prime_A_B_C.py --mode training` — generates `logs/*_aprime_decisions_*.jsonl`
2. `analyze_aprime_logs.py` — computes block/tier scores → `aprime_laws_verN.json`
3. `analyze_aprime_results.py` — checks convergence stop condition
4. `auto_rewrite_aprime.py --skip-analyze` — calls LLM to rewrite code blocks

Input logs are not limited to one paper's latest file. `analyze_aprime_logs.py` reads every file matching `logs/*_aprime_decisions_*.jsonl` that shares the most recent timestamp suffix, so one refinement iteration scores the full latest training run across all papers that produced A' logs in that run.

```bash
# Full refinement loop (up to 5 iterations)
powershell -File 06_exclusion_screening_pipeline/run_exclusion_refinement.ps1

# Dry run (prepare LLM prompt only — no file modifications)
powershell -File 06_exclusion_screening_pipeline/run_exclusion_refinement.ps1 -DryRun -MaxIterations 1

# With a different model
powershell -File 06_exclusion_screening_pipeline/run_exclusion_refinement.ps1 -Model gpt-5.3-codex
```

| Script | Purpose |
|---|---|
| `run_exclusion_refinement.ps1` | Full-loop orchestrator (pipeline → analyze logs → stop-check → rewrite → loop) |
| `analyze_aprime_logs.py` | Reads `logs/*_aprime_decisions_*.jsonl`, computes block/tier scores, writes `aprime_laws_verN.json` |
| `analyze_aprime_results.py` | Compares latest two `aprime_laws_verN.json` files for ranking convergence; emits `STOP=true/false` |
| `generate_aprime_rewrite_input.py` | Builds LLM rewrite prompt from scores + current code |
| `rewrite_aprime_blocks.py` | Applies LLM response to 4 target files with validation + backups |
| `auto_rewrite_aprime.py` | Single-iteration orchestrator (prompt → LLM → apply) |

Stop conditions:
1. `no_aprime_activity` — `aprime_laws_verN.json` has `n_records == 0` (A' was never triggered; all papers already < 9999 hits)
2. `converged` — top-5 Phase 1 block names AND top-5 Phase 3 tier names are identical between the two most recent laws files
3. `max_iterations_reached` — iteration count reaches `MaxIterations` (default: 5)

Phase 5 papers are recorded in diagnostics (`run_logs/aprime_diagnostics_*.json`) for reference only. Phase 5 is not a stop criterion.

Decision logs written per paper during training runs:
- `logs/{paper_id}_aprime_decisions_{ts}.jsonl` — one JSON record per Phase 1 block attempt and Phase 3 tier candidate

---

## Outputs

| Path | Content |
|---|---|
| `results/` | Per-run CSV / JSON summary files |
| `logs/` | Per-paper Stage A parse logs and A' decision JSONL |
| `pubmed_cache/` | Cached PubMed abstract/metadata fetches |
| `run_logs/` | Self-refinement loop artifacts (diagnostics, prompts, applied rewrites) |

---

## Prompts

| Path | Purpose |
|---|---|
| `prompts/active/exclusion_screening_training_prompt_stageAtoD.md` | Training mode protocol |
| `prompts/active/exclusion_screening_test_prompt_stageAtoD.md` | Test mode protocol |
| `prompts/Refine_exclusion_screening_prompt.md` | Self-refinement scoring specification |
