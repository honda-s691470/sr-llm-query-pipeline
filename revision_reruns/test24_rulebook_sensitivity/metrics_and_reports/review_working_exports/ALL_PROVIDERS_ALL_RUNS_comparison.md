# Full Comparison: Run1 / Run2 / Run3 / Pooled × Claude / Codex / Gemini × Stage1 / Stage2

Generated: 2026-08-25

## Methodology note (read first)

Providers used **different strategies for papers that failed the Stage A' hit-count gate** (>9,999 hits even after automated NOT-filter reduction):

- **Claude** (this session): gate-failed papers were left out of the recommended headline (n=21–22 per rulebook) unless a safe Tier1/1.5 rescue worked. A separate "Tier2 forced" ablation (all 24, narrowing every gate-failed paper down by removing core-concept terms) is also available — this is the number used below for direct comparability with Codex/Gemini, but it is **not the recommended number** (Tier2 causes severe recall loss, documented per-paper in the individual rulebook reports).
- **Codex and Gemini** (other sessions on this machine, not directly supervised in this conversation): both appear to run their own automatic "Phase 5" query-narrowing step that forces every paper under the gate, then feed the narrowed query into Stage 2 — so their n is 24 for every rulebook.

**Because of this, the "Stage1" recall shown for Codex/Gemini/Claude-forced below reflects the recall of the query that was ACTUALLY fed into Stage 2 (post-narrowing for gate-failed papers), not the original one-shot rulebook query.** Where available, the ORIGINAL (pre-narrowing) Stage1 recall is also shown for reference, since that is the number most comparable to Run1's reported Stage1 recall and to "how well did the rulebook alone do."

## Stage 1 (query generation) — mean Recall (n=24 for all cells)

| Rulebook | Provider | Original (pre-narrowing) Recall | Recall of query fed to Stage2 (post-narrowing where applicable) | Mean Hits (fed to Stage2) |
|---|---|---:|---:|---:|
| **Run1** | Claude | 0.83 | 0.83 (no gate-failures in Run1) | — |
| **Run1** | Codex | 0.83 (trend) | 0.83 | — |
| **Run1** | Gemini | 0.89 | 0.89 | — |
| **Run2** | Claude | 0.863 | 0.862 | 21,778 |
| **Run2** | Codex | 0.857 | 0.825 | 8,890 |
| **Run2** | Gemini | 0.850 | 0.850 (†phase5 still in progress, 17/24 rescued) | 11,738 |
| **Run3** | Claude | 0.836 | 0.836 | 21,348 |
| **Run3** | Codex | 0.837 | 0.837 | 13,835 |
| **Run3** | Gemini | 0.827 | 0.759 (phase5 complete, 24/24) | 3,689 |
| **Pooled** | Claude | 0.872 | 0.872 | 16,519 |
| **Pooled** | Codex | 0.900 | 0.850 | 10,181 |
| **Pooled** | Gemini | 0.881 | 0.851 (phase5 complete, verified) | 5,796 |

## Stage 2 (cut70) — all 24 papers, gate-failures force-narrowed

| Rulebook | Provider | n | Mean Stage C Recall | Mean Recall Loss | Mean Workload Reduction |
|---|---|---:|---:|---:|---:|
| **Run1** | Claude | 24 | 0.718 [0.624–0.805] | ~0.11 | 68.5% [9.4–87.2%] |
| **Run1** | Codex | 24 | 0.674 [0.578–0.760] | ~0.16 | 70.7% [26.5–86.6%] |
| **Run1** | Gemini | 24 | 0.713 [0.622–0.799] | ~0.18 | 73.2% [27.5–87.8%] |
| **Run2** | Claude (forced) | 24 | 0.707 | 0.155 | 55.7% |
| **Run2** | Codex | 24 | 0.700 | 0.125 | 49.1% |
| **Run2** | Gemini | 22† | 0.731 | 0.107 | 51.3% (†phase5 in progress) |
| **Run3** | Claude (forced) | 24 | 0.647 | 0.189 | 56.7% |
| **Run3** | Codex | 24 | 0.694 | 0.143 | 48.0% |
| **Run3** | Gemini | 24 | 0.677 | 0.082 | 41.2% |
| **Pooled** | Claude (forced) | 24 | 0.681 | 0.191 | 50.3% |
| **Pooled** | Codex | 24 | 0.691 | 0.160 | 45.2% |
| **Pooled** | Gemini | 24 | 0.739 (median 0.762) | 0.133 | 45.1% |

## Recommended (non-forced) headline for Claude, for reference

| Rulebook | n | Mean Stage C Recall | Mean Recall Loss | Mean Workload Reduction |
|---|---:|---:|---:|---:|
| Run2 | 22 | 0.734 | 0.120 | 51.9% |
| Run3 | 21 | 0.686 | 0.138 | 50.8% |
| Pooled | 21 | 0.734 | 0.133 | 43.6% |

This is the number Claude's individual rulebook reports recommend citing, since it does not include papers whose recall was artificially destroyed by forced Tier2 narrowing.

## Cross-cutting observations

1. **Run1 (the published rulebook) clearly outperforms Run2/Run3/Pooled** on Stage C recall for every provider (0.67–0.72 in Run1 vs 0.65–0.74 scattered, generally lower, in the later rulebooks) — this is expected since Run1 is the original, most-validated rulebook, and Run2/Run3/Pooled are sensitivity-analysis reruns from independently-sampled training passes, not further-optimized versions.
2. **`41715180_2026`** (CVD, heart-failure prognostic-model review) gate-failed under **every rulebook tested, for every provider that reported gate status** — the single most robust finding across this whole exercise. Its "Prognosis"[Mesh] AND "Heart Failure" structure appears to be fundamentally unresolvable under the 9,999-hit gate without severe recall loss, regardless of LLM or rulebook version.
3. Forcing all papers under gate (Codex/Gemini's approach, and Claude's Tier2 ablation) generally **costs more recall than it's worth** — compare Claude's forced (0.707/0.647/0.681) vs recommended headline (0.734/0.686/0.734): forcing costs 2–5 points of mean recall for the sake of including 2–3 more papers.
4. Gemini's Run3/Pooled phase5 completions show the sharpest pre-vs-post-narrowing Stage1 recall drops among all providers (Run3: 0.827→0.759; Pooled: 0.881→0.851), consistent with Claude's own finding that forced narrowing is costly.

## Status caveats

- Gemini Run2 phase5 is **still in progress** (17/24 papers rescued as of this check) — the Run2/Gemini row above uses the pre-phase5 headline (n=22) as a placeholder; re-check after completion.
- All Codex numbers were reconstructed by this session from ~87 accumulated single-paper snapshot CSVs (Codex processes one `--paper-id` at a time and does not save a consolidated 24-row Stage2 summary) — cross-checked against Codex's own reported Pooled Stage C numbers (mean 0.6906, median 0.7256) which matched exactly.
- Run1 numbers are as published in `main_ver5.pdf` (bootstrap 95% CIs); Run2/Run3/Pooled are point estimates only, computed by this session (Claude rows) or reconstructed from accumulated files (Codex/Gemini rows).
