# Harmonized Stage C reanalysis (revision 2): data and reproduction code

This folder lets readers reproduce the revised Stage C (MedCPT ranking) results for the 24 test reviews.
It covers the per-review Recall/NNR at every dense weight (alpha) and cut, the comparisons with the human
query, Reduction_search, paired template contrasts, retention categories and the supplementary NNR summaries.
It does not change the original PubMed cache deposit (doi:10.5281/zenodo.20392130), which is still needed
for document text.

## What changed from the original Stage C
The original runs used different pseudo-abstract texts across models, and some deposited score files did not
match the reported aggregates. The revised analysis re-scores the saved candidate sets of all three models
under one protocol (`environment/protocol.json`, version 20261110_v2). The query-side text is the
deterministic T2 template (main analysis). T1 (the earlier template) and LLM (saved LLM pseudo-abstracts) are
reported as comparison arms.

The archived protocol's `analysis` field retains the initial post hoc sensitivity-analysis designation.
It records the protocol's history, not the status of the revised results: the standardized template
(T2) is the revised primary analysis, selected after results were available.

## Contents
| Path | Content |
|---|---|
| `data/candidate_manifest.csv` | One row per scored condition (74): model, review, candidate count and SHA-256, gate count and its source, ZIP entry, provenance class and note, and the scenarios it belongs to |
| `data/candidates/<condition_id>.json` | Candidate PMIDs (sorted) entering Stage C |
| `data/query_texts.json` | Per model and review: T1, T2 and LLM query texts; for LLM, the generator, date and prompt as recorded |
| `data/scores/<condition_id>.npz` | Saved score components and Final for each ranked condition (see "Score files") |
| `code/stagec_core.py` | Scoring functions (verbatim extracts of the code used; source hashes in the header) |
| `code/score_stagec.py` | Step 1 (GPU): recompute score components from candidates, texts and the cache ZIP |
| `code/replay_metrics.py` | Step 2 (CPU): Final → order → retained sets → Recall/NNR (retained sets are fixed before gold is read) |
| `code/statistics.py` | Step 3 (CPU): summaries, tests and contrasts |
| `code/compare_expected.py` | Step 4: compare with `expected/` |
| `expected/` | Values used in the revised manuscript and response |
| `provenance/historical_meta/` | Historical Run1 Stage C metadata files that identify candidate sets for verified variants |
| `environment/` | Protocol, package versions |
| `MANIFEST.sha256` | SHA-256 of every file in this folder |

### Scenarios
- `primary`: verified candidate sets (main analysis).
- `sens_codex_41641734_4b8f`: Codex 41641734 uses the alternative verified set 4b8f instead of 7ffa.
- `sens_gemini_41770755_inferred714`: Gemini 41770755 uses an inferred 714-record set (gate, not ranked). Its
  reconstruction is inferred, not directly recorded (see `provenance_note`).

### Provenance classes (`candidate_manifest.csv`)
`deposited_scored_set` (PMIDs of a deposited Run1 score file), `saved_full_score_set`,
`historical_input_hash_verified` (set whose hash matches a historical metadata file in `provenance/`),
`zip_entry_keys_gate` (gate: all records of the cache entry pass), `inferred_reconstruction`.
The gate count source is either the Run1 Stage B hit count or, where these differ for Gemini, the candidate
count (`gate_count_source`).

## Protocol summary
Document text = title + " " + first 500 characters of the abstract; candidates in lexicographic PMID order.
MedCPT Query/Article encoders at fixed revisions, batch 32, max length 512, float32, TF32 off, 4 torch threads,
mean pooling with L2 normalization. BM25 (k1 1.5, b 0.75) divided by its maximum (all zeros if the maximum
is ≤0). Dense and BM25 components are rounded to 4 decimals and stored as float32.
s_q = alpha·dense + (1−alpha)·BM25. Two top and two bottom anchors by s_q (ties: ascending PMID), reselected at
each alpha. Final = pct(s_q) + pct(mean similarity to top anchors) − pct(mean similarity to bottom anchors).
Order = stable descending sort of Final. Alpha ∈ {0, .25, .5, .75, 1}; cut ∈ {0, 30, 50, 60, 70, 80, 90}.
Retention: conditions with gate count ≤1,000 pass through unranked. Otherwise the number kept is
`min(n, max(1000, round(n·(1−cut/100))))` using Python round (ties to even); see `keep_count`.
Recall = TP / gold count. NNR = retained / TP (undefined if TP = 0).
Main analysis: T2, alpha 0.5, cut70.

## Reproduction
Inputs from the public repository: `05_test_data/<domain>/<review>/gold_pmids.json`,
`07_paper_figures/data/test24_eval/elicit24_points_gate1000_floor1000_20260511.csv` (human-query comparator and
legacy Run1 values), and `pubmed_cache.zip` (Zenodo; SHA-256 checked by step 1).

```
# Level 1 (CPU, minutes): from the saved score components
python code/replay_metrics.py --public-root <repo> --out out/metrics
python code/statistics.py --metrics out/metrics --public-root <repo> --out out/stats
python code/compare_expected.py --metrics out/metrics --stats out/stats

# Level 2 (GPU, about 1 h on one RTX 4090 Laptop GPU): recompute score components, then repeat Level 1
python code/score_stagec.py --zip <path>/pubmed_cache.zip --out out/scores
python code/replay_metrics.py --scores out/scores --public-root <repo> --out out/metrics2
```
Step 1 needs the two MedCPT encoders at the revisions in `protocol.json` in the local Hugging Face cache and
runs offline. Step 2 verifies that the stored Final equals the Final recomputed from the components.

## Score files
`<condition_id>.npz` contains `pmids` and, for each arm in {T1, T2, LLM}, `{arm}_dense` and `{arm}_bm25`; for each
alpha, `{arm}_a{alpha}_s_pos_mean`, `_s_neg_mean`, `_pos_anchor`, `_neg_anchor` (indices into `pmids`) and
`_final`. Gate conditions have no score file.

## Limits
- GPU reproduction on the hardware and versions listed (2026-11-11): the 35 baseline conditions reproduce bitwise.
  For the 12 reconciled candidate variants, dense similarities agree within float32 rounding (|difference| <= 1e-6),
  which can reorder near-tied records and change the rank-based Final by up to 0.0023. Retained sets are identical
  for the primary analysis (T2, alpha 0.50) at every cut; in the T1 sensitivity arm, one non-gold record changed
  places at the retention boundary in a few cuts. All reported recall, NNR and statistics are identical
  (Level 1 comparison: all match). The deposited `data/scores` files are from this run. Other GPUs or library
  versions may also reorder near-tied records.
- LLM pseudo-abstracts were generated once on 2026-11-09 and are provided as saved text. They are not
  regenerated.
- Historical Run1 Final scores are not reproduced here; this package reproduces the harmonized reanalysis.
