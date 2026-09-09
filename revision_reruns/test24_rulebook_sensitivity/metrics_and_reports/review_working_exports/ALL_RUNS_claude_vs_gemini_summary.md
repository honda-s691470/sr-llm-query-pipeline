# Rulebook Sensitivity Analysis — Full Summary (Run1 / Run2 / Run3 / Pooled) × (Claude / Gemini) × (Stage1 / Stage2)

Generated: 2026-08-25

## Status flags (read first)

- **Run1**: from the submitted manuscript (`main_ver5.pdf`), the original/main rulebook, n=24 test papers, 3 LLMs (Claude, Codex, Gemini) reported. Numbers below are as published.
- **Run2, Run3**: Claude — complete (this session, including Tier1/Tier2 sensitivity work). Gemini — complete (independently run on this machine by another session; verified here by re-querying PubMed live for all 24 saved queries per condition — recall matched the recorded summary CSVs exactly in both runs).
- **Pooled**: Claude — complete (this session, including Tier1/Tier2 sensitivity work). Gemini — **Stage 1 complete** (all 24 queries present, freshly generated ~09:00–09:01 today; Stage1 recall computed here via live PubMed verification since no matching Stage1-only summary CSV existed for this exact query batch). **Stage 2 still running** (background process, PID 58068, started 09:33 today; manifest shows 15/24 papers touched, 14 reached Stage C as of this check) — NOT yet reportable.

---

## Stage 1 (query generation, mean Recall / mean Total Hits, n=24 unless noted)

| Rulebook | Claude Recall | Claude Hits | Gemini Recall | Gemini Hits | Human baseline |
|---|---:|---:|---:|---:|---:|
| **Run1** (main manuscript) | 0.83 (p=0.02 vs human) | 360–1,139 (range, not broken out per-LLM) | 0.89 (p=0.002 vs human) | (same range) | 0.70 |
| **Run2** | 0.863 | 22,157 | 0.850 | 11,738 | — |
| **Run3** | 0.836 | 21,348 | 0.827 | 11,166 | — |
| **Pooled** | 0.872 | 16,519 | 0.881 | 13,909 | — |

Notes:
- Run1's raw Stage1 NNR (hits/TP) was reported only as a pooled range across all three LLMs (360–1,139), not split per model, in the manuscript text.
- Run2/Run3/Pooled Stage1 numbers here are the mean **raw** recall/hits over all 24 papers (before any Stage A' NOT-filter reduction), matching how Run1's Stage1 recall is defined (query-level recall against gold PMIDs).
- Gemini Run2/Run3 verified live against PubMed (see below); Gemini Pooled Stage1 computed live here (23/24 queries succeeded on first pass, 1 retried successfully — final n=24).

---

## Stage 2 (cut70: exclusion NOT-filters + MedCPT re-ranking, top 30% retained)

Each rulebook run had some papers that failed the Stage A' hit-count gate (>9,999 hits even after automated NOT-filter reduction) and therefore have no Stage 2 output. The table below reports the **headline number excluding gate-failed papers** (Claude: after safe Tier1/1.5 rescue only, per this session's established protocol; Gemini: as gate-failed/passed natively, no manual intervention performed on Gemini's queries in this session).

| Rulebook | Provider | n (Stage C) | Mean Stage C Recall | Mean Recall Loss (Stage1→StageC) | Mean Workload Reduction |
|---|---|---:|---:|---:|---:|
| **Run1** (main manuscript) | Claude | 24 | 0.718 [0.624–0.805] | ~0.11 (0.83→0.72) | 68.5% [9.4–87.2%] |
| **Run1** (main manuscript) | Gemini | 24 | 0.713 [0.622–0.799] | ~0.18 (0.89→0.71) | 73.2% [27.5–87.8%] |
| **Run2** | Claude | 22 (2 rescued via Tier1) | 0.734 | 0.120 | 51.9% |
| **Run2** | Gemini | 22 (2 gate-failed: 41715180, 41781907) | 0.731 | 0.107 | 51.3% |
| **Run3** | Claude | 21 (3 gate-failed, Tier1-only headline) | 0.686 | 0.138 | 50.8% |
| **Run3** | Gemini | 21 (3 gate-failed: 41715180, 41804118, 41781907) | 0.733 | 0.076 | 37.7% |
| **Pooled** | Claude | 21 (3 gate-failed, Tier1-only headline) | 0.734 | 0.133 | 43.6% |
| **Pooled** | Gemini | **in progress** | — | — | — |

Notes:
- Run1's Stage2 CIs are bootstrap 95% CIs from the manuscript (n=24, no gate-failures reported for Run1 — the original rulebook evidently kept all 24 papers under the Stage A' gate; this differs from Run2/Run3/Pooled, where the newer rulebook derivations produced some very broad queries that could not always clear the same gate).
- Claude's Run2/Run3/Pooled headline numbers here are **Tier1/1.5-only** (i.e., excluding gate-failed papers rather than force-narrowing them) — this is the number recommended for reporting. A separate Tier2 ablation exists per rulebook (see `test24_run2_rulebook_report.md` / `test24_run3_rulebook_report.md` / `test24_run_pooled_rulebook_report.md`) showing that forcing all papers under gate via Tier2 causes severe recall loss (e.g., −0.43 to −0.71 per paper) and is not part of the recommended pipeline.
- Gemini's gate-failure set overlaps partially with Claude's but is not identical (e.g., `41781907_2026` gate-failed for Gemini in both Run2 and Run3, but never gate-failed for Claude in any rulebook) — provider-specific query breadth differences drive this, not the rulebook alone.
- `41715180_2026` (CVD, heart-failure prognostic-model review) gate-failed for **both Claude and Gemini in every rulebook version tested** (Run2, Run3, Pooled for Claude; Run2, Run3 for Gemini) — this is the strongest cross-provider, cross-rulebook signal that this specific review's inclusion criteria produce a structurally unresolvable Stage A' hit count without unsafe (Tier 2) term removal.

---

## Cross-run comparison (Claude only, all three post-Run1 rulebook versions, headline/Tier1-only)

| Metric | Run2 | Run3 | Pooled |
|---|---:|---:|---:|
| Mean Stage1 Recall | 0.853 | 0.824 | 0.867 |
| Mean StageC Recall | 0.734 | 0.686 | 0.734 |
| Mean Recall Loss | 0.120 | 0.138 | 0.133 |
| Mean Workload Reduction | 51.9% | 50.8% | 43.6% |

(Uses the n=22/21/21 headline subsets per rulebook, i.e., excludes that rulebook's own gate-failed papers — see individual reports for full detail.)

## Cross-run comparison (Gemini only, Run2 vs Run3; Pooled Stage2 pending)

| Metric | Run2 | Run3 |
|---|---:|---:|
| Mean Stage1 Recall (n=24) | 0.850 | 0.827 |
| Mean StageC Recall (n=22/21) | 0.731 | 0.733 |
| Mean Recall Loss | 0.107 | 0.076 |
| Mean Workload Reduction | 51.3% | 37.7% |

---

## Caveats

- Run1 numbers are as published (manuscript-level aggregates with bootstrap CIs); Run2/Run3/Pooled numbers are this session's own computation (no CIs computed here — point estimates only).
- Claude and Gemini query generation methods differ operationally in this project: Claude's Run2/Run3/Pooled queries were generated via in-process model subagents in this session (to avoid a nested-Claude-Code-session conflict); Gemini's were generated via the `gemini` CLI directly by another session on this machine, independently. Both were scored the same way (rule-based Stage A/B/C pipeline, no LLM calls in Stage 2).
- Gemini used model `gemini-3.1-pro` for at least the Pooled attempt (per `eval_test_gemini_gemini-3.1-pro_*.csv`), not `gemini-3.0-pro` as used in the original Run1 manuscript — this is a model-version difference on top of the rulebook difference, and should be noted if comparing Pooled/Gemini numbers against Run1.
- Pooled/Gemini Stage 2 must be re-checked once the currently-running background process (PID 58068, started 2026-08-25 09:33) finishes — do not treat any number here as final for that cell.
- Codex results exist for all four rulebook versions (observed running concurrently on this machine throughout this session) but were not requested here and are not included.
