You are operating inside the `public_release/` bundle.

Your task is to execute the query-laws refinement workflow end-to-end from this bundle, not merely describe it.

Scope:
- Keep all work inside `public_release/`.
- Do not read from or write to files outside this bundle.
- Do not ask for confirmation unless blocked by a hard execution failure.

Objectives:
1. Run the repository-provided orchestration script instead of improvising your own workflow code.
2. Keep all paths relative to the current working directory.
3. Leave a concise execution summary at the end.

Use these rules:

- Do not hard-code any absolute Windows path such as `G:\...`.
- Do not write inline ad hoc Python or PowerShell workflow code unless the repository script fails and you first explain why.
- Use only the current working directory plus repository-relative paths.

Run this command exactly:

```powershell
powershell -ExecutionPolicy Bypass -File 02_query_laws_refinement/run_workflow.ps1 -AutoRewriteSection00
```

After it finishes, read the printed `SUMMARY_PATH=...` file and report:
- the generated query-laws version filename
- how many target SR directories were processed
- for each SR: path, recall, total_hits, and whether output files were successfully written

If the workflow enters a refinement pass after evaluation, use the following integrated SECTION_00 rewrite procedure.

## SECTION_00 Rewrite Scope

- Edit only `02_query_laws_refinement/analyze_logs_ver2.py`.
- The only editable region is the text block between:
  - `# SECTION_00_REWRITE_BEGIN`
  - `# SECTION_00_REWRITE_END`
- Do not modify any other code, metrics logic, rule table logic, or domain-law logic.
- The goal is to improve the next `query_laws_verN+1.txt` by rewriting only the hard-coded `SECTION_00` guidance.

## Trigger for Refinement

- Identify low-performing training SRs:
  - First priority: `Recall < 0.60`
  - Second priority: `delta recall vs previous version <= -0.05`
  - Include at most 2 SRs total across first- and second-priority cases.
  - Do not include any other SRs in the SECTION_00 rewrite prompt.
- Use only training SRs under `04_data/`.
- Never use test-set information for rule changes.

## Inputs for Diagnosis

For each low-performing SR, gather:

- the previous query from `model_outputs/codex/with_laws_v{N}_training_eval/normalized_query.txt`
- the missed PMID list from `last_metrics.json`
- title and abstract for the missed PMIDs
- the SR objective and inclusion criteria from `input_config.json`
- the local `search_history.jsonl` action log
- the current editable `SECTION_00` text from `analyze_logs_ver2.py`
- the current `SECTION_1` laws in the generated `query_laws_verN.txt`
- the current `placeholder_example_for()` behavior in `analyze_logs_ver2.py`, especially the `INITIAL_PRIMARY` branch

## LLM Rewrite Task

When rewriting `SECTION_00`, reason from:

- what terms are missing from the previous query
- whether the miss is caused by an over-restrictive AND block
- whether the miss is caused by omitted tiab/MeSH synonyms
- whether the miss is caused by an unsafe filter/design restriction
- what the training `search_history.jsonl` suggests about recall-protective restorations
- whether any current `SECTION_00` hard rule conflicts with the empirical `SECTION_1` laws
- whether a rule exists in `SECTION_1` but shows low LLM adherence across multiple papers and should be promoted into `SECTION_00`
- whether low adherence is better addressed by improving the generic example structure in `placeholder_example_for()` rather than adding another verbose `SECTION_00` rule

Return a rewritten `SECTION_00` block only.

Output requirements:

- Return only the replacement text for the editable block.
- Include both boundary lines:
  - `# SECTION_00_REWRITE_BEGIN`
  - `# SECTION_00_REWRITE_END`
- Preserve high-level invariants unless there is strong training-only evidence to revise wording:
  - query architecture split between `PRIMARY_CONCEPT` and optional `STUDY_FILTER`
  - recall-first preference
  - `AND` block budget discipline
  - broad fallback floor
  - MeSH protection
- Keep new text concise and high-signal.
- If a new point substantially overlaps an existing rule, merge it into the existing rule instead of adding a near-duplicate standalone rule.
- If the new training-only insight is already covered by `SECTION_00` or `SECTION_1`, prefer revising or tightening existing wording over expanding `SECTION_00`.
- If the new training-only insight is NOT represented in either `SECTION_00` or `SECTION_1`, add the minimum new rule text needed to capture it and expand `SECTION_00` only as much as necessary.
- If LLM adherence is poor even when a rule is already written, first check whether `SECTION_00` and `SECTION_1+` contain conflicting guidance.
- If such a conflict exists and the training evidence supports the downstream law, prefer the `SECTION_1+` guidance or allow the exception conditionally in `SECTION_00`.
- If you do NOT change the rule logic, but adherence is still poor, you may add a concise generic example using meta-level placeholders or class labels rather than domain-specific terms.
- You may:
  - add a new guardrail
  - revise wording of an existing guardrail
  - add a concrete generic example using meta terms rather than paper-specific vocabulary
- You must not:
  - insert any disease names, drug names, outcomes, specific ethnicities, or paper identifiers specific to the training or test sets. When including concrete examples, you must replace them with other generic terminology.
  - remove the overall `SECTION_00` header
  - edit code outside the editable block
  - add domain-specific disease, intervention, drug, or paper-specific examples to `SECTION_00`

## Imperative and Example Block Rewrite

If the diagnosis indicates that low LLM adherence is better addressed by updating the
imperative or example text in `analyze_logs_ver2.py` rather than expanding `SECTION_00`,
you MAY also output one or more of the following optional editable blocks.

These blocks control the text that appears in the **Imperative_EN** and **Example_Placeholder**
columns of the law table for specific law types. Updating them changes what the LLM reads
when it looks at the generated `query_laws.txt`.

### TIAB_IMPERATIVE_CONDITIONAL_ADD block (optional)

Controls the `[ONE-SHOT-GUIDANCE: ADD_TIAB]` guidance in `tiab_imperative()` for the
CONDITIONAL branch (affects LAW_016 Imperative_EN).

Output between these markers if you are changing it:

```
# TIAB_IMPL_COND_ADD_BEGIN
...rewritten text...
Use {target_block} as a Python format placeholder where the block name (PRIMARY/FILTER) appears.
# TIAB_IMPL_COND_ADD_END
```

### ONE_SHOT_IMPERATIVE_PRIMARY block (optional)

Controls the advice portion of `[ONE-SHOT-GUIDANCE]` for PRIMARY-block RESTRICT/REMOVE
operations in `one_shot_imperative()` (affects LAW_020, LAW_022 Imperative_EN).

The generic opening `"[ONE-SHOT-GUIDANCE] {meta_action} on {target_block}/{target_slot} shows
mixed effects across training cases. In initial query construction, favor recall over precision. "`
is **prepended automatically** — do NOT include it here.

Output between these markers if you are changing it:

```
# ONE_SHOT_PRIMARY_BEGIN
...advice text only (starting from "Apply this action ONLY when...")...
# ONE_SHOT_PRIMARY_END
```

### PLACEHOLDER_INITIAL_PRIMARY block (optional)

Controls the Example_Placeholder for `INITIAL_PRIMARY` (LAW_001) in `placeholder_example_for()`.

Output between these markers if you are changing it:

```
# PLACEHOLDER_INIT_BEGIN
...example text (use CONDITION_X, INTERVENTION_Z, TERM_A placeholders; no paper-specific names)...
# PLACEHOLDER_INIT_END
```

### Rules for imperative/example blocks

- Output only the blocks you are changing; omit blocks that do not need to change.
- SECTION_00 block is always required; imperative/example blocks are all optional.
- Use generic placeholders (`CONDITION_X`, `INTERVENTION_Z`, `TERM_A`) — never paper-specific names.
- Do not insert any disease names, drug names, outcomes, specific ethnicities, or paper identifiers specific to the training or test sets. When including concrete examples, you must replace them with other generic terminology.
- Preserve `{target_block}` as a literal Python format string placeholder in TIAB_IMPL text.
- Keep each block's text concise and high-signal.

## Applying the Rewrite

After producing the rewritten block, save it to a temporary text file and apply it with:

```powershell
python 02_query_laws_refinement/rewrite_section00_block.py `
  --source 02_query_laws_refinement/analyze_logs_ver2.py `
  --rewrite-block 02_query_laws_refinement/tmp_section00_rewrite.txt `
  --backup-path 02_query_laws_refinement/run_logs/analyze_logs_ver2_backup_before_section00_rewrite.py
```

Then re-run:

```powershell
python 02_query_laws_refinement/analyze_logs_ver2.py
```

Use the resulting `query_laws_verN+1.txt` for the next evaluation pass.

Do the work now.
