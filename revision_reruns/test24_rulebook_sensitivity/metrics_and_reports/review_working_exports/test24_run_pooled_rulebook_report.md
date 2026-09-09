# Test24 Pooled-Consensus-Rulebook Sensitivity Analysis (Claude only)

Generated: 2026-08-25

## Scope

Pooled consensus rulebook × Claude provider × all 24 held-out test papers,
Stage 2 cutoff = cut bottom 70%. Distinct condition
(`with_laws_pooled_rb_test_eval`) — did not touch Run2/Run3 outputs or
caches.

## Method notes

Same method as Run2/Run3: 5 in-process Claude Sonnet 5 subagents (one per
domain), `test_prompt_with.md` Steps 0–5 against the Pooled rulebook only,
no gold/recall access. Stage 2 via `run_pipeline_prime_A_B_C.py --mode
test`, no LLM calls.

**Operational note:** the first Stage 2 attempt (default `--device auto`)
crashed mid-run with a CUDA `illegal memory access` error, caused by GPU
contention with another concurrently-running process on this machine
(a Gemini pipeline run explicitly using `--device cuda`). The harness's
"exit code 0" for that background task was misleading — the underlying
Python process had actually crashed; the wrapping shell pipe (`| tail`)
masked the real exit status. Re-run with `--device cpu` explicitly
completed cleanly. All subsequent single-paper reruns in this report also
used `--device cpu` and were verified by reading their log files directly
rather than trusting the background-task completion status alone.

## Stage 1 (query generation, Recall / Total Hits)

| Domain | n | Mean Recall | Mean Hits |
|---|---:|---:|---:|
| Rheumatoid Arthritis | 7 | 0.864 | 9,688 |
| Cardiovascular Disease | 4 | 0.878 | 51,636 |
| Psychiatry | 3 | 0.725 | 17,356 |
| Oncology | 7 | 0.940 | 8,058 |
| Infectious Diseases | 3 | 0.872 | 4,539 |
| **Overall** | **24** | **0.872** | **16,519** |

## Stage A' gate: 3 papers initially failed

`41708995_2026` (CVD, raw 124,373), `41715180_2026` (CVD, raw 81,196),
`41804118_2026` (Psychiatry, raw 50,581 — new to this run; not gate-failed
in Run2 or Run3). Automated NOT-block iteration reduced to 30,192 / 42,205
/ 11,320 respectively.

### Tier 1/1.5 attempt

- `41708995_2026`: one Tier 1 candidate (`"Biomarkers"[Mesh]`, backed by
  `"biological marker*"[tiab]`), negligible effect (30,192 → 28,220).
- `41715180_2026`: **no valid candidates** — same conclusion independently
  reached in all three rulebook versions (Run2, Run3, Pooled). The
  bottleneck (`"Prognosis"[Mesh]`, no genuine tiab backup, AND-ed with the
  extremely common "Heart Failure" concept) is a structural property of
  this review's inclusion criteria, not an artifact of any one rulebook.
- `41804118_2026`: no valid candidates. A dangling-`AND` syntax artifact
  was found and verified live against PubMed — confirmed cosmetic, no
  effect on hit count (11,320 either way).

### Tier 2 exception (user-authorized again, one-time, test-only)

| Paper | Terms removed | Hits after |
|---|---|---:|
| `41708995_2026` | `blood[tiab]`, `serum[tiab]` (isolated contributions 21,390 / 5,326 of 30,192) | 5,291 |
| `41715180_2026` | `"Prognosis"[Mesh]`, `"Models, Statistical"[Mesh]` (32,993-equivalent / 6,806 standalone) | 6,027 |
| `41804118_2026` | `UK[tiab]`, `"United States"[tiab]` (2,041 / 3,840 standalone; `[majr]` country tags kept) | 5,385 |

**Recall damage — again consistent with why Tier 2 is forbidden:**

| Paper | Stage 1 (original) Recall | Tier-2-narrowed Stage C Recall | Recall Loss |
|---|---:|---:|---:|
| `41708995_2026` | 0.852 (23/27) | 0.259 (7/27) | **−0.593** |
| `41715180_2026` | 1.000 (44/44) | 0.295 (13/44) | **−0.705** |
| `41804118_2026` | 0.875 (7/8) | 0.375 (3/8) | **−0.500** |

`41715180_2026`'s loss (−0.705) is the largest single recall drop across
all three rulebook runs for this paper family, underscoring that its
"Prognosis"[Mesh] dependency is a hard structural constraint: this review
apparently cannot be searched below the 9,999-hit gate without losing the
majority of its gold set, regardless of rulebook.

## Stage 2, cut bottom 70%

**(a) Headline — excluding the 3 forced Tier-2 papers (21 papers; recommended):**

| Domain | n | Mean Raw Recall | Mean Stage C Recall | Mean Recall Loss | Mean Workload Reduction |
|---|---:|---:|---:|---:|---:|
| Rheumatoid Arthritis | 7 | 0.864 | 0.682 | 0.183 | 62.3% |
| Cardiovascular Disease | 2 | 0.830 | 0.790 | 0.040 | 30.1% |
| Psychiatry | 2 | 0.649 | 0.636 | 0.013 | 9.3% |
| Oncology | 7 | 0.940 | 0.790 | 0.150 | 36.5% |
| Infectious Diseases | 3 | 0.872 | 0.756 | 0.115 | 48.1% |
| **Overall** | **21** | **0.867** | **0.734** | **0.133** | **43.6%** |

**(b) All 24 "as-forced" (ablation only, not recommended):** see
`test24_stage2_cut70_rulebook_sensitivity_summary_ALL24_including_tier2_pooled.csv`.

## Cross-run comparison: Run2 vs Run3 vs Pooled (each excluding its own Tier-2 papers)

| Metric | Run2 (n=22) | Run3 (n=21) | Pooled (n=21) |
|---|---:|---:|---:|
| Mean Stage 1 Recall | 0.853 | 0.824 | 0.867 |
| Mean Stage C Recall | 0.734 | 0.686 | 0.734 |
| Mean Recall Loss (Stage1→StageC) | 0.120 | 0.138 | 0.133 |
| Mean Workload Reduction | 51.9% | 50.8% | 43.6% |

All three rulebook versions land in a narrow band (Stage C recall
0.69–0.73, recall loss 0.12–0.14), suggesting the rulebook refinement
process (Run2/Run3/Pooled) produces broadly consistent downstream pipeline
performance rather than large swings — the dominant source of variance
observed in this whole exercise was not which rulebook was used, but
whether a paper hit the Stage A' hit-count gate at all (CVD's
`41715180_2026` failed in all three; Oncology's `41770755_2026` failed in
Run2/Run3 but passed narrowly in Pooled; Psychiatry's `41804118_2026`
failed only in Pooled). Paper-level composition differences across the
three headline sets mean this is a suggestive, not a strictly matched,
comparison — a fully rigorous comparison would restrict to the papers that
passed the gate in all three runs.

## Files

- `test24_stage1_rulebook_sensitivity_per_paper_pooled.csv`
- `test24_stage1_rulebook_sensitivity_summary_pooled.csv`
- `test24_stage2_cut70_rulebook_sensitivity_per_paper_pooled.csv`
- `test24_stage2_cut70_rulebook_sensitivity_summary_pooled.csv` (21-paper headline)
- `test24_stage2_cut70_rulebook_sensitivity_summary_ALL24_including_tier2_pooled.csv`
- This report: `test24_run_pooled_rulebook_report.md`

## Caveats

Same as Run2/Run3 reports: Codex/Gemini legs pending (other sessions were
observed running some of this independently on this machine during this
work); cutoff sensitivity (cut30/cut50) not run; recall figures depend on
live PubMed results at run time (2026-08-24/25).
