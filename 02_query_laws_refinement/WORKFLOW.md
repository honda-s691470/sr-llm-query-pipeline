# Query Laws Refinement Workflow

## Directory Layout

```
02_query_laws_refinement/
  analyze_logs_ver2.py       # Law extraction script (Step 1)
  test_prompt_with.md        # Query generation prompt (Step 2)
  query_laws.txt      # Starting 
  WORKFLOW.md                # This file
```

**Training set**: 11 SRs (CVx3, PSYx4, INFx4) from the hypothesis accumulation phase.  
**LLM used for hypothesis accumulation**: GPT-5.3-Codex (OpenAI Codex CLI).

---

## Overview

This pipeline takes `search_history.jsonl` files produced by hypothesis accumulation
and refines `query_laws.txt` - the rule set passed to LLMs for one-shot PubMed query generation.

The loop is: **generate laws -> generate queries -> evaluate recall -> diagnose failures -> update laws**.

---

## Step 1: Generate `query_laws.txt` from training logs

Run `analyze_logs_ver2.py` to extract statistical laws from the 11 training `search_history.jsonl` files.

```bash
cd 02_query_laws_refinement/
python analyze_logs_ver2.py
```

**What it does:**
- Reads all training logs directly from `../04_data/<domain>/<paper_id>/search_history.jsonl`
- Normalizes each action into `(META_ACTION, META_CONCEPT)` key pairs
- Computes weighted law confidence: `Deploy_Score = Rep * Suc * Con * Sup - penalties`
- Classifies laws: `RECALL_PROTECTIVE`, `NOISE_REDUCTION`, `CONDITIONAL`, `AVOID`
- Outputs `query_laws.txt` with four sections:
  - `SECTION_00`: Non-negotiable hard rules (query architecture, AND-block budget, etc.)
  - `SECTION_1`: Full normalized rule table
  - `SECTION_2`: Top DO-laws and AVOID-laws (global)
  - `SECTION_3`: Domain-specific laws (CV / PSY / INF divergence analysis)

**Output**: `query_laws.txt` (overwrites in-place; auto-backup to `query_laws_ver{N}.txt`)

**Log weight scheme (Improvement #1):**  
`weight = clamp(n_iterations / 18.0, min=0.4, max=1.0)`  
Harder papers (more iterations) carry proportionally more evidence weight.

---

## Step 2: Generate queries and evaluate Recall

For each of the 11 training SRs, run **GPT-5.3-Codex** against the target SR directory in `public_release/04_data/`.

Required inputs for each target SR:

1. **`test_prompt_with.md`** - query construction prompt (with_laws condition), located in `public_release/02_query_laws_refinement/`
2. **`query_laws.txt`** - the rule set produced in Step 1, located in `public_release/02_query_laws_refinement/`
3. **`input_config.json`** - located in the target SR directory under `public_release/04_data/<domain>/<paper_id>/input_config.json`; this file contains objectives, inclusion/exclusion criteria, and gold PMIDs

Recommended PowerShell batch run:

```powershell
$promptPath = "public_release/02_query_laws_refinement/test_prompt_with.md"
$queryLawsPath = "public_release/02_query_laws_refinement/query_laws.txt"
$version = "v14"

$targetDirs = Get-ChildItem "public_release/04_data" -Directory -Recurse | Where-Object {
  Test-Path (Join-Path $_.FullName "input_config.json")
} | Sort-Object FullName | Select-Object -ExpandProperty FullName

foreach ($targetDir in $targetDirs) {
  Write-Host "Running Codex for $targetDir"

  $outDir = Join-Path $targetDir "model_outputs/codex/with_laws_${version}_training_eval"
  New-Item -ItemType Directory -Force -Path $outDir | Out-Null

  Copy-Item -LiteralPath $queryLawsPath -Destination (Join-Path $outDir "query_laws_${version}.txt") -Force

  Get-Content -Raw $promptPath |
    codex exec --skip-git-repo-check -s danger-full-access -C $targetDir -m gpt-5.3-codex - |
    Tee-Object -FilePath (Join-Path $outDir "raw_codex_output.txt")
}
```

This pattern automatically picks up every SR directory under `public_release/04_data/` that contains `input_config.json`.

Recommended per-SR output directory:

```text
public_release/04_data/<domain>/<paper_id>/model_outputs/codex/with_laws_v{N}_training_eval/
```

where `{N}` is the `query_laws` version number being evaluated (e.g. `with_laws_v14_training_eval`).

Recommended recording procedure:

1. Run Codex with `test_prompt_with.md` and save the raw terminal output to:
   - `model_outputs/codex/with_laws_v{N}_training_eval/raw_codex_output.txt`
2. Extract the single `FULL_QUERY:` line from that output and save the normalized Boolean query as:
   - `model_outputs/codex/with_laws_v{N}_training_eval/normalized_query.txt`
3. Copy the evaluated law file used for the run into the same directory as:
   - `model_outputs/codex/with_laws_v{N}_training_eval/query_laws_v{N}.txt`

PubMed evaluation should use the dedicated evaluator:

- `public_release/02_query_laws_refinement/tool_evaluator.py`

This variant avoids overwriting `last_metrics.json` produced during hypothesis accumulation.
It reads explicit input and query paths and writes metrics only to the path you specify.

Recommended evaluation sequence:

Run:

```powershell
python public_release/02_query_laws_refinement/tool_evaluator.py `
  --input-config public_release/04_data/<domain>/<paper_id>/input_config.json `
  --query-path public_release/04_data/<domain>/<paper_id>/model_outputs/codex/with_laws_v{N}_training_eval/normalized_query.txt `
  --metrics-path public_release/04_data/<domain>/<paper_id>/model_outputs/codex/with_laws_v{N}_training_eval/last_metrics.json
```

This evaluator uses the PubMed API internally and computes Recall by checking the generated query against the gold PMIDs in `input_config.json`. In effect, it evaluates:

```text
(LLM-generated query) AND (PMID1[uid] OR PMID2[uid] OR ... PMIDn[uid])
```

and writes:

- `query`
- `total_hits`
- `recall`
- `found_count`
- `total_gold`
- `missed_pmids` / `found_pmids` (non-blind mode)

Record per-SR at minimum:

- `normalized_query.txt`
- `query_laws_v{N}.txt`
- `last_metrics.json`

From `last_metrics.json`, report:

- Recall = `found_count / total_gold`
- Total hits = `total_hits`
- NNR = `total_hits / found_count`


## Step 3: Diagnose failures and refine `query_laws.txt`

1. **Identify low-performing SRs**:
   - First priority: training SRs with Recall < 0.60.
   - Second priority: training SRs with delta Recall <= -0.05 vs. the previous version.
   - Keep at most 2 SRs total across both priorities for the SECTION_00 rewrite prompt.
2. **Diagnose**: Compare LLM query vs. gold PMIDs. What MeSH/tiab terms are missing?
   Which AND block over-restricts? Cross-reference `search_history.jsonl` action log.
3. **Fix options**:
   - Add a new rule to `SECTION_00` (if LLM consistently ignores SECTION_1 guidance)
   - Update `placeholder_example_for()` in `analyze_logs_ver2.py` to add a concrete example
   - Re-run Step 1 after revising `analyze_logs_ver2.py` or after updating the training logs in `../04_data/`
4. **Increment version**: Save as `query_laws_ver{N+1}.txt`.
5. **Repeat** Step 2-3 until mean training Recall >= target (paper uses v14, mean Recall ~0.76).

**Detailed refinement checklist:**

1. **Extract low-performing SRs**
   - First priority: training SRs with Recall < 0.60.
   - Second priority: training SRs with delta Recall <= -0.05 relative to the prior `query_laws` version.
   - Include at most 2 SRs total across both priorities in the SECTION_00 rewrite prompt.
   - Exclude all other SRs from the SECTION_00 rewrite prompt.

2. **Inspect failure mode**
   - Compare the generated query, the gold PMID list, and the actually retrieved PMIDs.
   - Determine whether the miss is due to missing MeSH/tiab concepts, over-restrictive AND blocks, or an erroneous NOT-style exclusion pattern.
   - Cross-reference the per-iteration `search_history.jsonl` to identify which action families tended to cause the failure.

3. **Update statistical laws**
   - Re-run `analyze_logs_ver2.py` to regenerate the normalized rule table and top deployment laws from the current training logs.
   - Review `SECTION_1` and `SECTION_2` in `query_laws.txt`.
   - Remove or de-emphasize rules that show weak support or negative deployment score.

4. **Review `SECTION_00` hard rules**
    - Check whether any hard-coded guardrail in `render_output()` conflicts with the empirical laws in `SECTION_1`.
    - If there is a conflict, decide whether `SECTION_00` should remain authoritative or whether the law wording should be adjusted toward the empirical behavior.
    - If a rule is empirically useful but LLM adherence is low across multiple papers, consider promoting it into `SECTION_00`.
    - Keep additions concise and merge overlapping rules instead of adding near-duplicate standalone guardrails.

5. **Update examples**
    - Inspect `placeholder_example_for()` in `analyze_logs_ver2.py`.
    - In particular, review the `INITIAL_PRIMARY` branch and whether its sample query structure reflects the current training-set lessons on `AND` block budget, `STUDY_FILTER`, and broad fallback coverage.
    - If LLM adherence remains poor, consider improving `placeholder_example_for()` before expanding `SECTION_00` with more prose.
    - Add a more explicit placeholder example only when a generic example is likely to improve adherence.
    - Keep examples generic; use placeholders such as `[CONDITION_TERM]` and `[INTERVENTION_TERM]`, not paper-specific disease or intervention names.

6. **Save the next version**
   - Save the revised rule set as `query_laws_ver{N+1}.txt`.
   - Record which training SR failures motivated the change.

**Test set leakage guard**: All refinements must be based ONLY on training SR results.
Never inspect gold PMIDs or recall of test SRs to modify the rules.

---

## Dependency Notes

| File | Portability | Notes |
|---|---|---|
| `analyze_logs_ver2.py` | Yes - fully portable | Reads logs directly from `../04_data/<domain>/<paper_id>/search_history.jsonl` |
| `tool_evaluator.py` | Yes - fully portable | Writes metrics only to the explicitly requested output path |
| `test_prompt_with.md` | Yes - fully portable | References `input_config.json` by filename only |
| `WORKFLOW.md` | Yes - fully portable | Consolidated refinement instructions |
| `../04_data/*/*/search_history.jsonl` | Yes - included | All 11 training papers are read directly from `public_release/04_data/` |
| Eval scripts (`eval_training_*.py`) | No - not included | Depend on `pipeline_common.py` which requires full repo structure (`05_test_data/`, `04_data/`) |
