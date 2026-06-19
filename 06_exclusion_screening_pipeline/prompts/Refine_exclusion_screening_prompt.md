# Refine Exclusion Screening Prompt — Workflow

## Overview

`exclusion_screening_training_prompt_stageAtoD.md` is the training-mode prompt for the Stage A' → A → B → C exclusion screening pipeline.
This document describes the standard workflow for refining that prompt.

Primary targets for refinement:
1. **Phase 1 priority score table** (application order of NOT blocks)
2. **Phase 3 Tier order** (priority of safe operations in raw query narrowing)

---

## Prompt Synchronization Policy

All refinements are driven by Training data (11 papers), but the content of both prompt files must be managed according to the following principle.

**Rule: Training and Test prompt content must be kept identical unless there is a specific reason to differ.**

| File | Role |
|---|---|
| `active/exclusion_screening_training_prompt_stageAtoD.md` | Training mode (with recall guard, recall logging, uid-based evaluation) |
| `active/exclusion_screening_test_prompt_stageAtoD.md` | Test mode (no recall check; hits-only decisions) |

**Permitted differences** (legitimate reasons to diverge):
- Behavioral differences between Training/Test modes (recall guard, uid-based recall, Phase 5 recall check presence/absence)
- Descriptions tied to mode-specific code (`run_eval_training11_stages.py` vs `run_pipeline_prime_A_B_C.py`)
- Labels that identify file role, e.g. `(Training)` suffix in section titles

**Must be kept in sync** (update both files whenever either changes):
- Phase 1 priority score table
- Phase 3 Tier order and definitions
- Stage A' structure (Phase 1 → 2 → 3 → 4 → 5)
- Stage C implementation contract (6.7 C-6)
- Non-Negotiable Constraints and associated rules (SR-of-SRs exception, etc.)

**Update procedure**: Whenever the Training prompt is refined, always propagate the change to the corresponding section of the Test prompt. Missed synchronization causes behavioral divergence on the test set.

---

## Workflow

### Step 1: Run the pipeline on the 11 training papers

```powershell
python 06_exclusion_screening_pipeline/run_pipeline_prime_A_B_C.py `
  --mode training `
  --provider <codex|gemini|claude> `
  --condition with_laws_stage0 `
  --query-provider <codex|gemini|claude> `
  --query-condition with_laws_stage0 `
  --stagec-gate-hits 1000 `
  --stagec-floor-hits 1000 `
  --stagec-cut-percent 30
```

Training data: 11 papers (CV 3, PSY 4, INF 4).

For each paper, record:
- `hits_raw` → `hits_prime` → `hits_a` → `hits_b` → Stage C retained count
- `recall_raw` → `recall_prime` → `recall_a` → `recall_b` → Stage C recall
- ΔHits and ΔRecall for each block applied in Stage A' Phase 1

---

### Step 2: Recompute Phase 1 priority scores

Scores are computed statistically from Stage A' Phase 1 logs across the 11 training papers.

**Score formula**:

```
Score(block) = Hit_Reduction_Rate × Success_Rate × Consistency − Recall_Penalty
```

- `Hit_Reduction_Rate`: mean ΔHits when block is applied (normalized)
- `Success_Rate`: fraction of papers where hits decreased after applying the block
- `Consistency`: fraction of domain pairs (CV / PSY / INF) with stable hit reduction
- `Recall_Penalty`: frequency of `delta_recall > 0.02` events, penalized at α=0.8

**Update criteria**:
- Blocks whose score deviates ≥ 0.5 from the current table should be re-ranked.
- Newly stable NOT blocks (effective in ≥ 8 papers) should be added to the table.
- Blocks that frequently cause recall loss (`delta_recall > 0.02`) should be removed or demoted.

**Current table (baseline for comparison)**:

| Priority | Block | PubMed Syntax | Score |
|---|---|---|---|
| 1 | English language | `english[lang]` | 9.64 |
| 2 | Meeting abstracts | `NOT "Meeting Abstract"[pt]` | 8.50 |
| 3 | Trial protocols | `NOT "Clinical Trial Protocol"[pt]` | 8.39 |
| 4 | Systematic reviews | `NOT "Systematic Review"[pt]` | 8.33 |
| 5 | Meta-analyses | `NOT "Meta-Analysis"[pt]` | 8.08 |
| 6 | Reviews (general) | `NOT "Review"[pt]` | 8.00 |
| 7 | Adult age MeSH | `("Adult"[Mesh] OR "Middle Aged"[Mesh] OR "Aged"[Mesh])` | 6.81 |
| 8 | Journal Article only | `"Journal Article"[pt]` | 6.71 |
| 9 | Retracted publications | `NOT "Retracted Publication"[pt]` | 5.04 |
| 10 | Preprints | `NOT "Preprint"[pt]` | 3.04 |

After updating, apply the new table to both `exclusion_screening_training_prompt_stageAtoD.md` and `exclusion_screening_test_prompt_stageAtoD.md`.

---

### Step 3: Review Phase 3 Tier order

The Tier order for Phase 3 (raw query narrowing) is evaluated from the Phase 3 logs of the 11 training papers using the following metric.

**Evaluation metric**:

```
Tier_Score(tier) = Avg_Hit_Reduction × Success_Rate × Recall_Safety_Rate
```

- `Avg_Hit_Reduction`: mean ΔHits when the Tier operation is applied (positive)
- `Success_Rate`: fraction of applications where hits decreased
- `Recall_Safety_Rate`: fraction of applications satisfying `delta_recall <= 0.02` (training gate threshold)

**Criteria for reordering**:
- A Tier with `Recall_Safety_Rate < 0.70` should be considered for demotion even if currently high-ranked.
- A Tier with `Success_Rate > 0.80` and `Recall_Safety_Rate > 0.90` should be considered for promotion even if currently low-ranked.
- Newly discovered safe operation patterns should be added as a new Tier (record in archived laws).

**Current Tier order** (Tier 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → F):

1. **Tier 1**: Remove `[Mesh]` when tiab backup exists
2. **Tier 2**: Remove wildcard-redundant tiab
3. **Tier 3**: Remove generic/broad tiab via word-boundary suffix match
4. **Tier 4**: Remove 2–4 ALL-CAPS acronym tiab when full-form tiab backup (≥8 chars) exists
5. **Tier 5**: Replace `[tiab]` → `[ti]` when `[Mesh]`/`[Mesh:NoExp]` backup exists
6. **Tier 6**: Replace scope-restrictor `[tiab]` with proximity phrase
7. **Tier 7**: `[Mesh]` → `[Mesh:NoExp]` when tiab backup exists
8. **Tier 8**: `[Mesh:NoExp]` → `[majr]` one term at a time
9. **Tier 9**: Batch-apply `[majr]` to largest AND-block (≥2 convertible terms)
10. **Tier 10**: Replace wildcard-pair `[tiab]` with proximity phrase
- **Tier F**: Append safe NOT publication-type filters

**Reference files** (always review before changing Tier definitions):
- `06_exclusion_screening_pipeline/prompts/reference/phase4_hit_reduction_archived_laws.md` — canonical Tier definitions
- `06_exclusion_screening_pipeline/prompts/reference/training11_llm_v14_query_efficiency_analysis_20260326.md` — evidence-based safety analysis

When changing Tier definitions, record the reason and supporting papers in `phase4_hit_reduction_archived_laws.md` and increment the version number.

---

### Step 4: Diagnose low-recall papers

Prioritize investigation of papers that meet any of the following conditions:
- Recall dropped ≥ 0.05 compared to the previous version after Stage A'
- hits remained ≥ 9,999 after Stage A', requiring Phase 5 (manual rewrite)

For each such paper:
- Verify that applied NOT blocks did not incorrectly exclude any gold PMIDs.
- Check whether tiab/MeSH terms removed in Phase 3 caused the recall loss.
- Check for duplicate application between Stage A allowlist and Phase 1/2.

---

### Step 5: Update and save prompts

1. Increment the version number in `exclusion_screening_training_prompt_stageAtoD.md`.
2. Update the Phase 1 table.
3. Update the Tier order or definitions if changed.
4. Propagate the same Phase 1 table to `exclusion_screening_test_prompt_stageAtoD.md`.
5. Append the change history to `phase4_hit_reduction_archived_laws.md`.

---

### Automated loop stop conditions

The self-refinement loop (`run_exclusion_refinement.ps1`) stops when any of the following is true:

1. **`no_aprime_activity`** — `aprime_laws_verN.json` has `n_records == 0` (A' was never triggered; all papers already < 9999 hits)
2. **`converged`** — top-5 Phase 1 block names AND top-5 Phase 3 tier names are identical between the two most recent laws files
3. **`max_iterations_reached`** — iteration count reaches `MaxIterations` (default: 5)

Phase 5 papers are recorded in loop diagnostics for reference only. `phase5_pending` is **not** a stop criterion. Phase 5 is a separate manual fallback applied after the loop completes, for papers that still exceed 9999 hits.

The loop always uses `with_laws_test_eval` queries as input. Phase 5 rewritten queries (`with_laws_stageA_prime`) are not used as loop input.

---

## Constraints

- **No test set data leakage**: All refinements must be based solely on the 11 training papers. Never use test set gold PMIDs or recall to drive prompt changes.
- **SR-of-SRs exception must be preserved**: The rule prohibiting `NOT "Review"[pt]` when inclusion criteria include systematic reviews must never be changed.
- **Tier 2 old is permanently forbidden**: Removing tiab terms from CONDITION/POPULATION/INTERVENTION core axes causes recall loss and must never be applied under any circumstances.

---

## File reference

| Role | File |
|---|---|
| Training screening prompt (refinement target) | `06_exclusion_screening_pipeline/prompts/active/exclusion_screening_training_prompt_stageAtoD.md` |
| Test screening prompt (sync target) | `06_exclusion_screening_pipeline/prompts/active/exclusion_screening_test_prompt_stageAtoD.md` |
| Canonical Tier definitions | `06_exclusion_screening_pipeline/prompts/reference/phase4_hit_reduction_archived_laws.md` |
| Training 11 efficiency analysis | `06_exclusion_screening_pipeline/prompts/reference/training11_llm_v14_query_efficiency_analysis_20260326.md` |
| Pipeline execution script | `06_exclusion_screening_pipeline/run_pipeline_prime_A_B_C.py` |
