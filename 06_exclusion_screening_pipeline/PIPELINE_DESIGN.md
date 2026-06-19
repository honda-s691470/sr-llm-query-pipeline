# Pipeline Design

## Stage overview

```
Raw PubMed query  (loaded from 04_data/ or 05_test_data/ → with_laws_test_eval/)
    │
    ▼
Stage A' — Prime Hit Reduction   (reduce total hits to < 9999)
    │  Phase 1: A_PRIME_BLOCKS (ordered NOT/filter blocks)
    │  Phase 3: Tier-based raw query narrowing (dynamic loop)
    │  Phase 4: Transition → writes phase5_manual_prompt.md if still ≥ 9999
    │  Phase 5: Manual LLM rewrite (final fallback)
    │
    ▼
Stage A  — Safe NOT filters      (publication type / animal-only only)
    │
    ▼
Stage B  — Metadata post-filter  (language, publication type, animal)
    │
    ▼
Stage C  — Ranking + retention   (BM25 + MedCPT hybrid, gate/floor logic)
```

---

## Data layout

| Mode | Training papers | Test papers |
|---|---|---|
| Source directory | `04_data/` (11 papers) | `05_test_data/` (24 papers) |
| Query condition | `with_laws_test_eval` | `with_laws_test_eval` |
| Recall during pipeline | Live (Δrecall ≤ 0.02 gate) | Post-hoc only |

---

## Stage A' — Prime Hit Reduction

Reduces total PubMed hits to < 9999 before deeper screening.

- **Test mode**: hit-count gate only (no recall check)
- **Training mode**: Δrecall ≤ 0.02 gate at every candidate step

### Phase 1: A_PRIME_BLOCKS

Ordered list of NOT/filter blocks tried one-by-one, applying those that reduce hits
(training: with recall gate; test: hits-only).

Block order and definitions live in `run_eval_training11_stages.py` (`A_PRIME_BLOCKS` list).
Priority order is improved automatically by the self-refinement loop.

### Phase 3: Tier-based raw query narrowing

Triggered when Phase 1 exhausts all blocks and hits remain ≥ 9999.
Modifies only the `raw_query` portion; accepted NOT suffix blocks are preserved.

Tier functions live in `run_eval_training11_stages.py`.
Tier order is improved automatically by the self-refinement loop.

### Phase 4 / 5: Manual rewrite fallback

If Phase 3 cannot reach < 9999:
- `phase5_required = true`; pipeline stops before Stage A/B/C.
- Prompt file written to:
  - Training: `04_data/<domain>/<paper_id>/model_outputs/<provider>/with_laws_stageA_prime_phase5_pending/phase5_manual_prompt.md`
  - Test: `05_test_data/<domain>/<paper_id>/model_outputs/<provider>/with_laws_stageA_prime_phase5_pending/phase5_manual_prompt.md`

After accepting a rewrite:
1. Save the new query to `with_laws_stageA_prime/normalized_query.txt`
2. Rerun with `--query-condition with_laws_stageA_prime`

---

## Stage A' Self-Refinement Loop

After a full training run, `run_exclusion_refinement.ps1` iterates:

```
run_pipeline_prime_A_B_C.py --mode training  (always with_laws_test_eval)
  │  writes logs/{paper_id}_aprime_decisions_{ts}.jsonl
  │
  ▼
analyze_aprime_logs.py
  │  Score formula (Phase 1): Score = 10 × HRR × SR × C − 0.8 × RP
  │  Score formula (Phase 3): Tier_Score = Avg_HRR × SR × Recall_Safety_Rate
  │  writes aprime_laws_verN.json
  │
  ▼
analyze_aprime_results.py
  │  compares latest two aprime_laws_verN.json for ranking convergence
  │  emits STOP=true/false
  │
  ▼ (if STOP=false)
auto_rewrite_aprime.py --skip-analyze
  │  generate_aprime_rewrite_input.py → LLM → rewrite_aprime_blocks.py
  │  updates A_PRIME_BLOCKS in run_eval_training11_stages.py
  │  updates tier_fns in run_pipeline_prime_A_B_C.py
  │  updates both prompt files (PHASE1 + PHASE3 markers)
  │
  └─ loop
```

Stop conditions:
1. `no_aprime_activity` — `aprime_laws_verN.json` has `n_records == 0` (A' was never triggered)
2. `converged` — top-5 Phase 1 block names AND top-5 Phase 3 tier names are identical between the two most recent laws files
3. `max_iterations_reached` — iteration count ≥ max_iterations (default: 5)

Phase 5 papers are recorded in diagnostics for reference only. Phase 5 is a manual fallback applied separately after the loop, and is NOT a stop criterion for the A' self-refinement loop. Phase 5 rewritten queries (`with_laws_stageA_prime`) are not used as loop input.

---

## Stage A — Safe NOT filters

Parses `exclusion_criteria` free text and applies allowlisted `NOT` clauses.

**Allowlisted classes only:**
- Publication type (e.g., `NOT "Letter"[pt]`)
- Animal-only studies

Anything outside the allowlist is dropped regardless of parser/LLM output.

---

## Stage B — Metadata post-filter

Deterministic filtering using PubMed metadata fields.

- publication type
- language
- animal-only (where safely inferable)

**Conservative rule:** missing metadata → **keep**. Never exclude aggressively on incomplete data.

---

## Stage C — Ranking and retention

Hybrid ranker (BM25 + MedCPT dense embeddings) with HyDE-style pseudo-abstract as query text.

**Retention logic (gate/floor):**
- `hits_b ≤ 1000`: passthrough (all records kept)
- `hits_b > 1000`: `kept_n = max(floor_hits, round(hits_b × (1 − cut_percent/100)))`

Default canonical flags: `--stagec-gate-hits 1000 --stagec-floor-hits 1000 --stagec-cut-percent 30`

**Score formula:** `rank(s_q) + rank(s_pos_mean) − rank(s_neg_mean)`

Reference implementation: `src/stagec_final.py`

---

## Behavioral invariants

1. **Recall protection dominates** — missing abstract or metadata → retain
2. **Query-time NOT is hard-restricted** — publication type / animal-only only; no prompt-dependent expansion
3. **Retention is data-driven** — gate/floor logic (floor = 1000), not fixed-K
4. **Block/tier ordering is empirically improved** — self-refinement loop uses training-set hit/recall statistics

---

## Data leakage prevention

- Gold PMIDs from test papers are only read during post-hoc recall computation, never during the pipeline.
- Training set: `04_data/` (11 papers)
- Test set: `05_test_data/` (24 non-training papers)
- All prompt/code improvements must be grounded in training set results only.
