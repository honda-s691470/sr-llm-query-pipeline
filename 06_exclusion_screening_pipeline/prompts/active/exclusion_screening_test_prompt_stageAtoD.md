# Exclusion Screening Test Prompt (Stage A' -> A -> B -> C)

Version: 3.0 (2026-05-20) — Paths updated to 06_; query condition unified to with_laws_test_eval; Phase 2 removed (merged into Phase 1 A_PRIME_BLOCKS); reference file paths updated
Mode: **TEST ONLY (no Recall / no Gold PMIDs)**

Canonical execution (run from repo root `public_release/`):
```bash
python 06_exclusion_screening_pipeline/run_pipeline_prime_A_B_C.py \
  --mode test \
  --provider <codex|gemini|claude> \
  --stagec-gate-hits 1000 \
  --stagec-floor-hits 1000 \
  --stagec-cut-percent 30 \
  --target 9999 \
  --device cuda
```

> **Query source**: Test queries are read from
> `05_test_data/<domain>/<paper_id>/model_outputs/<provider>/with_laws_test_eval/normalized_query.txt`.

Provider default HyDE model mapping in script:
- codex -> `gpt-5.3-codex`
- codex -> `gpt-5.3-codex`
- gemini -> `gemini-3.0-pro`

HyDE default:
- local structured generation (API-free).
- add `--hyde-api` only if provider API generation is explicitly required.

Stage C retention policy (gate/floor, **not** fixed-K):
- `hits_b <= 1000`: passthrough (all records kept)
- `hits_b > 1000`: `kept_n = max(floor_hits, round(hits_b × (1 − cut_percent/100)))`
  - floor = **1000** (minimum records after cut)
  - With `--stagec-cut-percent 30`: cut 30 %, floor at 1000
  - Legacy fixed-K (`--use-fixed-k --k 500`) is disabled by default

Reference documents:
- `06_exclusion_screening_pipeline/prompts/Refine_exclusion_screening_prompt.md`

## 0. Critical Test Constraint

- You may use:
  - PubMed **total hit count**
  - Query text
  - Objectives / inclusion / exclusion criteria
  - Metadata and abstract text for screened candidates
- You must **not** use:
  - Gold PMIDs
  - Recall / sensitivity / TP/FN-like information
  - Any hidden reference set

If any recall-like signal is available in the environment, ignore it and continue in test mode.

---

## 1. Inputs

You will receive:

1. `base_query` (LLM-generated query before exclusion screening, from `with_laws_test_eval/`)
2. `objectives`
3. `inclusion_criteria`
4. `exclusion_criteria`
5. Optional `human_query` (from supplementary search strategy)

Query source policy (multi-LLM compatible):
- The same pipeline must work for any provider/condition pair, e.g.:
  - `codex / with_laws_test_eval`
  - `codex / with_laws_test_eval`
  - `gemini / with_laws_test_eval`
- Always document which provider/condition generated `base_query`.

---

## 2. Non-Negotiable Constraints

1. **Stage B -> Stage C cardinality must match**
   - Stage C input PMID set must equal Stage B output PMID set exactly.
   - Abort if mismatch.

2. **Cache is metadata lookup only**
   - Do not derive Stage C candidate count from cache file size.
   - Derive Stage C set strictly from Stage B output PMIDs.

3. **Stage C abstract fetch is mandatory**
   - For each Stage B PMID, if abstract missing in cache, fetch via PubMed API.
   - Delta update cache.

4. **HyDE freeze**
   - One pseudo abstract per paper/provider.
   - Reuse fixed text across all runs.

5. **Test mode uses hits-only decisions (no recall gate)**
   - Accept/reject modifications based on total hits only.
   - Never use gold PMIDs or recall signals for any decision.

---

## 3. Stage A' (Prime Hit Reduction)

Goal: reduce total hits to `< 9999` before deeper screening.

### Phase 1: Exclusion-driven candidate blocks

Build candidate blocks only when justified by exclusion criteria.

Examples:
- language exclusion present -> `english[lang]`
- pediatric/non-adult exclusion present -> `("Adult"[Mesh] OR "Middle Aged"[Mesh] OR "Aged"[Mesh])`
- publication-type exclusions present -> corresponding NOT blocks
- animal-only exclusion present -> `NOT (animals[mh] NOT humans[mh])`

Do not apply generic fixed blocks unless exclusion criteria explicitly supports them.

**Phase 1 candidate priority order** (training-derived scores): when multiple blocks are applicable, apply them in descending score order. In test mode, scores serve as ordering guidance only — accept/reject is by hits-only (no recall gate).

<!-- PHASE1_PRIORITY_REWRITE_BEGIN -->
1. `english[lang]`
2. `NOT "Systematic Review"[pt]`
3. `NOT "Meta-Analysis"[pt]`
4. `NOT "Review"[pt]`
5. `NOT "Clinical Trial Protocol"[pt]`
6. `NOT "Preprint"[pt]`
7. `NOT "Retracted Publication"[pt]`
8. `NOT "Meeting Abstract"[pt]`
9. `("Adult"[Mesh] OR "Middle Aged"[Mesh] OR "Aged"[Mesh])`
10. `"Journal Article"[pt]`
<!-- PHASE1_PRIORITY_REWRITE_END -->

**Stage A Allowlist** (already handled in Stage A — do NOT re-apply in Stage A'):
- `NOT "Case Reports"[pt]`, `NOT "Letter"[pt]`, `NOT "Editorial"[pt]`, `NOT "Comment"[pt]`,
  `NOT "News"[pt]`, `NOT "Published Erratum"[pt]`, `NOT (animals[mh] NOT humans[mh])`

---

### SR-of-SRs exception (mandatory)

**⚠️ MANDATORY SR-OF-SRs CHECK — MUST EXECUTE BEFORE ANY NOT-FILTER APPLICATION ⚠️**

Before adding ANY of the following blocks, read `objectives` AND `inclusion_criteria` in full:
- `NOT "Review"[pt]`
- `NOT "Systematic Review"[pt]`
- `NOT "Meta-Analysis"[pt]`
- `NOT "Scoping Review"[pt]`

**If `objectives` or `inclusion_criteria` mention ANY of the following as eligible study types — even implicitly — then ALL of the above NOT blocks are PERMANENTLY FORBIDDEN for this paper:**
- systematic review(s), meta-analysis/meta-analyses, scoping review(s), narrative review(s), umbrella review(s), review article(s), literature review(s)

This check is not optional. Skipping it and applying `NOT "Review"[pt]` when gold papers are review-type articles causes **catastrophic recall=0**. There is no recovery from this error.

**When in doubt about whether reviews are eligible: DO NOT add `NOT "Review"[pt]`.** Use `NOT "Systematic Review"[pt]` as a safer alternative if needed.

---

### Per-candidate decision (test mode)

- For each candidate block:
  - Apply block to current query.
  - Fetch total hits.
  - **Accept** only if total hits decreases.
  - **Reject** if no reduction or if syntax breaks query.
- Objective: choose the next accepted block that makes total hits closest to `9999`.
- Continue until total hits `< 9999`.
- If a candidate overshoots far below target and there is an alternative closer to target, prefer the closer one (overshoot backtrack rule).

### Phase 3: Raw query narrowing (dynamic loop)

**Triggered when**: Phase 1 exhausted all candidate blocks AND `hits_prime >= 9999`.

At this stage the current query has the structure:
```
(raw_query) [NOT block1] [NOT block2] ...
```
Phase 3 modifies **only the `raw_query` portion** — the NOT suffix blocks added in Phase 1 are preserved as-is.

<!-- PHASE3_TIER_ORDER_REWRITE_BEGIN -->
#### Phase 3-1: Tier order (mandatory — apply in this sequence: 1 → 9 → 6 → 5 → 7 → 3 → 2 → 4 → 8 → 10 → F)
- **Tier 1 (ARC_LAW_A)**: Remove `"TERM"[Mesh]` when tiab backup exists in same OR block.
- **Tier 2**: Remove a **wildcard-redundant tiab** — a non-wildcard term already covered by a wildcard in the same OR block (e.g., `"inflammation"[tiab]` when `inflammat*[tiab]` exists).
- **Tier 3**: Remove a **generic/broad tiab** when a more-specific tiab covers it via **word-boundary suffix match** in the same OR block (e.g., `"lipid"[tiab]` when `"blood lipid"[tiab]` present). Safety guards: min 4 chars; specific term ≥2 chars longer; wildcards excluded.
- **Tier 4**: Remove a **2–4 ALL-CAPS acronym [tiab]** (e.g. `"BMI"[tiab]`, `"HR"[tiab]`) when the same OR block has a non-wildcard tiab with ≥ 8 chars (full-form proxy).**[Mesh] backup is no longer required** — a long full-form tiab alone is sufficient guard. Rationale: short uppercase acronyms are ambiguous across domains; full-form tiab provides sufficient coverage.
- **Tier 5**: Replace `"TERM"[tiab]` → `"TERM"[ti]` when `[Mesh]` or `[Mesh:NoExp]` backup covers the same concept in the same OR block.
- **Tier 6**: Replace a **scope-restrictor [tiab]** (`predict*`, `prognos*`, `screen*`, `diagnos*`, `mortalit*`, `surviv*`, `inciden*`, `prevalenc*`, `assess*`, `measur*`, `outcom*`) with proximity phrase `"restrictor* content"[tiab:~5]`; block must have ≥ 3 tiab terms.
- **Tier 7 (ARC_LAW_E)**: `"TERM"[Mesh]` → `"TERM"[Mesh:NoExp]` when tiab backup exists.
- **Tier 8 (ARC_LAW_G)**: `"TERM"[Mesh:NoExp]` (or `[Mesh]`) → `"TERM"[majr]` one term at a time when tiab backup exists.
- **Tier 9**: Batch-apply `[majr]` to ALL eligible terms in the single AND-block with ≥ 2 convertible terms; more aggressive than Tier 8.
- **Tier 10**: Replace a pair of wildcard `[tiab]` terms in the same OR block with proximity phrase `"stem1* stem2*"[tiab:~3]`; both stems ≥ 4 chars; block must have ≥ 3 tiab terms.
- **Tier F (ARC_LAW_F)**: Append safe NOT publication-type filters not already present in the query.
<!-- PHASE3_TIER_ORDER_REWRITE_END -->

#### Phase 3-2: Gate policy (test mode)

- Test each modification individually against PubMed (total hits only — no recall check).
- **Accept** if total hits decreases. **Reject** if no reduction.
- Choose the modification whose result is closest to 9999 from above.
- Iterate until `hits < 9999` or no candidate in the current round produces any reduction.
- After each accepted modification, re-examine the remaining raw_query for newly applicable candidates (dynamic loop — never stop because a pre-defined list ran out).

#### Phase 3-3: Hard forbidden operations

- Do not remove the last tiab coverage of a core concept (CONDITION, INTERVENTION, or POPULATION).
- Do not convert OR to AND inside primary concept blocks.
- Do not mutate already accepted NOT suffix blocks.
- Do not add new mandatory AND blocks unrelated to core query structure.
- SR-of-SRs check applies here too: do not add `NOT "Review"[pt]` or `NOT "Meta-Analysis"[pt]` in Tier F if the exception applies.

### Phase 4: Transition (manual rewrite trigger)

**Triggered when**: Phase 3 completes with `hits_prime >= 9999` and no further Tier reduction is possible.

- Script sets `phase5_required=true` and stops the pipeline before Stage A/B/C.
- `phase5_manual_prompt.md` is written automatically to
  `05_test_data/<domain>/<paper_id>/model_outputs/<provider>/with_laws_stageA_prime_phase5_pending/`.

### Phase 5: Manual rewrite (LLM full rewrite, final fallback)

**Triggered when**: `phase5_required=true`.

1. Open `phase5_manual_prompt.md` from `with_laws_stageA_prime_phase5_pending/`.
2. Send contents to the LLM; obtain one complete rewritten query on a `FULL_QUERY:` line.
3. Verify: hits < 9999 (test mode — no recall check).
4. If accepted: save to `with_laws_stageA_prime/normalized_query.txt`.
5. Rerun with `--query-condition with_laws_stageA_prime`; other flags unchanged.

Output of Stage A': `query_prime`, `hits_prime`.

---

## 4. Stage A (Safe NOT from Exclusion Criteria)

Apply only allowlisted query-time NOT templates:

- `NOT "Case Reports"[pt]`
- `NOT "Letter"[pt]`
- `NOT "Editorial"[pt]`
- `NOT "Comment"[pt]`
- `NOT "News"[pt]`
- `NOT "Published Erratum"[pt]`
- `NOT (animals[mh] NOT humans[mh])`

No free-form NOT clauses outside allowlist.

Output:
- `query_a`
- `hits_a`
- parse log with applied/dropped candidates

---

## 5. Stage B (Deterministic Metadata Filter)

Input:
- PMIDs from Stage A.

Filter dimensions:
- publication type
- language (only if explicitly required)
- animal-only exclusion

Conservative rule:
- missing metadata => keep.

Output:
- `pmids_b`
- `hits_b`
- `excluded_b_count`

---

## 6. Stage C (Ranking)

Goal:
- rank Stage B candidates and retain top records for bounded downstream review.

Required packages: `pip install rank_bm25`; `transformers` and `torch` for MedCPT (`ncbi/MedCPT-Query-Encoder`, `ncbi/MedCPT-Article-Encoder`).

### 6.1 C-0 Cardinality check

Before starting scoring:
1. Load Stage B output PMID list (`pmids_b`) from the Stage B run record.
2. Verify that the set of PMIDs entering Stage C is **exactly** `pmids_b`.
3. If Stage C input count ≠ Stage B output count, **abort with error**:
   ```
   ERROR: cardinality mismatch — Stage B output={n_stage_b_output}, Stage C input={n_stage_c_input}
   ```
4. **Never use the pubmed_cache file record count to determine Stage C input.** The cache may contain stale/accumulated records from prior runs and will often exceed Stage B output count.

### 6.2 C-1 HyDE pseudo abstract (fixed per paper)

Generate **one** HyDE-style pseudo abstract per SR from:
- `objectives`
- `inclusion_criteria`
- `exclusion_criteria`

Prompt template:
```
You are generating a HyDE-style pseudo abstract for biomedical retrieval (PubMed/MedCPT).

Goal:
Write ONE hypothetical abstract of a study that would be INCLUDED in the target systematic review.
The abstract is for retrieval only (not for factual reporting).

Input:
- Objective: {objectives}
- Inclusion criteria: {inclusion_criteria}
- Exclusion criteria: {exclusion_criteria}

Requirements:
- Language: English only.
- Length: 140-220 words.
- Style: PubMed-like scientific abstract with exactly 4 labeled sections:
  Background:
  Methods:
  Results:
  Conclusions:
- Preserve critical biomedical entities exactly when provided:
  disease names, interventions/exposures, population descriptors, outcomes, study design terms.
- Add common synonym/abbreviation in parentheses only when high-confidence and standard.
- Prefer broad-but-relevant wording to maximize recall within inclusion scope.
- Do NOT invent highly specific unsupported details:
  exact effect sizes, p-values, confidence intervals, trial IDs, PMIDs, institution names, precise drug doses/timelines
  unless explicitly provided in the input.
- Do NOT mention information outside inclusion scope.
- Output ONLY the abstract text (no title, no bullets, no explanations).

Now write the pseudo abstract.
```

**HyDE freeze (MANDATORY)**: Generate once per paper/provider, then reuse:
- Save to: `06_exclusion_screening_pipeline/pubmed_cache/<domain>/<paper>/<provider>/hyde_query_test.txt`
- If file already exists, load and reuse — do **not** regenerate.

Provider-specific generation model:
- Codex run: `gpt-5.3-codex`
- Codex run: `gpt-5.3-codex`
- Gemini run: `gemini-3.0-pro`

If HyDE generation fails, fallback to:
- plain text concat: `objectives + inclusion_criteria`
- Save fallback text to the same file (still frozen).

### 6.3 C-2 Abstract fetch

Stage B fetches only `pub_types`, `languages`, and `species_mesh`. **Abstracts are absent from the cache after Stage B.**

For each PMID in `pmids_b`:
1. Check if its `abstract` field in the cache is non-empty.
2. Collect all PMIDs where `abstract == ""` or missing → these are the **fetch targets**.
3. Fetch abstracts from PubMed API for all fetch targets (delta fetch).
4. Update the cache with fetched abstracts without overwriting other fields.

On first Stage C run for a paper/provider, expect all PMIDs to require fetching.

### 6.4 C-3 Execution policy

- If `hits_b <= 1000`: Stage C ranking is skipped and `pmids_c = pmids_b` (passthrough).
- If `hits_b > 1000`: run full Stage C Final scoring on all `pmids_b`.
- No automatic 2000-cap prefilter in default mode (full scoring even when `hits_b > 2000`).

### 6.5 C-4 Stage C retention (gate/floor)

**Retention policy** (gate/floor/cut logic):
- `kept_n = max(floor_hits, round(hits_b × (1 − cut_percent/100)))` when `hits_b > gate_hits`
- Default flags: `--stagec-gate-hits 1000 --stagec-floor-hits 1000 --stagec-cut-percent 30`
- Floor = **1000**: the pipeline never outputs fewer than 1000 Stage C candidates (unless hits_b < 1000).

### 6.6 C-5 Final-score feature construction

Compute base scores for all Stage B candidates:
- `dense_sim(MedCPT)` — models: `ncbi/MedCPT-Query-Encoder`, `ncbi/MedCPT-Article-Encoder`
- `bm25_score`

Persist: `stagec_scored_records_medcpt_<query_hash>_<pmid_set_hash>.jsonl` and metadata `.meta.json` including `n_stage_b_input`.

For each Stage B candidate PMID, compute:

1. `s_q = 0.5 * dense_sim_medcpt + 0.5 * bm25_score`
2. Select anchors within the same paper:
   - `pos_anchors`: top-2 by `s_q`
   - `neg_anchors`: bottom-2 by `s_q`
3. Compute anchor similarity features:
   - `s_pos1`, `s_pos2`: candidate vs each pos anchor
   - `s_neg1`, `s_neg2`: candidate vs each neg anchor
   - (optional summary) `s_pos_mean`, `s_neg_mean`

Use percentile ranks (descending, per paper):
- `rank(s_q)`, `rank(s_pos1)`, `rank(s_pos2)`, `rank(s_neg1)`, `rank(s_neg2)`

### 6.7 C-6 Reference implementation contract (MUST)

Use exactly the same Final computation as the code reference implementation:

- Core formula module: `06_exclusion_screening_pipeline/src/stagec_final.py`
- Unified runner: `06_exclusion_screening_pipeline/run_pipeline_prime_A_B_C.py`

Deterministic rules (non-negotiable):
- Canonical candidate order: PMID lexicographic ascending.
- `rank()` uses descending percentile rank in `[0,1]` with stable mergesort.
- Anchor tie-break: PMID lexicographic ascending.
- Final tie-break for sorting: `(-final, pmid)`.

This contract prevents provider-specific implementation drift.

For each candidate PMID (within one paper):
1. Compute base relevance:
   - `s_q = 0.5 * dense_sim_medcpt + 0.5 * bm25_score`
2. Select anchors from same candidate set:
   - `pos_anchors`: top-2 by `s_q`
   - `neg_anchors`: bottom-2 by `s_q`
3. Compute anchor similarities:
   - `s_pos1`, `s_pos2`, `s_neg1`, `s_neg2`
   - optional summaries: `s_pos_mean`, `s_neg_mean`
4. Convert each score to per-paper descending percentile ranks.

Final score:
`final = rank(s_q) + rank(s_pos_mean) - rank(s_neg_mean)`

Equivalent 5D form:
`final = rank(s_q) + 0.5*(rank(s_pos1)+rank(s_pos2)) - 0.5*(rank(s_neg1)+rank(s_neg2))`

Sort descending by `final`.

Persist scored records to cache:
- `06_exclusion_screening_pipeline/pubmed_cache/<domain>/<paper>/<provider>/stagec_scored_records_medcpt_<query_hash>_<pmid_set_hash>.jsonl`
- Fields must include: `pmid`, `dense_sim_medcpt`, `bm25_score`, anchor feature values, `final`

Output of Stage C:
- `hyde_query_text` (if ranking branch executed)
- `candidates_c` (ranked by `final`)
- `stage_c_mode` (`ranked` or `passthrough_stageb`)
- `k_used`
- `final_formula_used`
- `dense_backend_used` (`medcpt`)
- `abstract_fetch_n`

---

## 7. Required Final Output (JSON)

```json
{
  "mode": "test_no_recall",
  "query_raw": "<base_query>",
  "hits_raw": 0,
  "query_prime": "<after_stage_a_prime>",
  "hits_prime": 0,
  "query_a": "<after_stage_a>",
  "hits_a": 0,
  "hits_b": 0,
  "excluded_b_count": 0,
  "k_used_stage_c": 0,
  "stage_c_mode": "ranked|passthrough_stageb",
  "final_formula_used": "rank(s_q)+rank(s_pos_mean)-rank(s_neg_mean)",
  "abstract_fetch_n_stage_c": 0,
  "phase5_required": false,
  "notes": []
}
```

No recall-like field is allowed in output.

---

## 8. Safety and Leakage Guard

- Never ask for or infer gold PMIDs.
- Never output or compute Recall/Sensitivity.
- If a tool returns recall accidentally, ignore it and do not log it.
