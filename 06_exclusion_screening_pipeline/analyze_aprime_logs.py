"""
Analyze Stage A' decision logs to compute block/tier scores for self-refinement.

Reads: logs/*_aprime_decisions_*.jsonl  (latest run = files from most recent ts)
Writes: aprime_laws_verN.json  (N = next available version)

Phase 1 score formula (from Refine_exclusion_screening_prompt.md):
  Score(block) = 10 × HRR × SR × C − 0.8 × RP

  HRR = mean(delta_hits / hits_before) over ACCEPTED attempts
  SR  = fraction of attempts where delta_hits > 0  (any action accepted)
  C   = fraction of distinct domains with at least one positive mean hit reduction
  RP  = fraction of attempts where delta_recall > 0.02  (recall penalty events)

Phase 3 tier score formula:
  Tier_Score(tier) = Avg_HRR × SR × Recall_Safety_Rate

  Avg_HRR            = mean(delta_hits / hits_before) over all ACCEPTED entries
  SR                 = fraction(action == "ACCEPTED")
  Recall_Safety_Rate = fraction(action != "REJECTED")   (NO_REDUCTION is safe)
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "06_exclusion_screening_pipeline" / "logs"
OUT_DIR = ROOT / "06_exclusion_screening_pipeline" / "run_logs"


def _latest_run_files(log_dir: Path) -> list[Path]:
    """Return all JSONL files sharing the most-recent timestamp suffix."""
    files = list(log_dir.glob("*_aprime_decisions_*.jsonl"))
    if not files:
        return []
    # extract timestamp part (last segment before .jsonl)
    def _ts(p: Path) -> str:
        m = re.search(r"_aprime_decisions_(.+)\.jsonl$", p.name)
        return m.group(1) if m else ""
    latest_ts = max(_ts(f) for f in files)
    return [f for f in files if _ts(f) == latest_ts]


def _read_records(files: list[Path]) -> list[dict]:
    records: list[dict] = []
    for f in files:
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _score_phase1(records: list[dict]) -> list[dict]:
    # group by block name
    by_block: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        if r.get("phase") == "phase1":
            by_block[r["name"]].append(r)

    results: list[dict] = []
    for name, entries in by_block.items():
        syntax = entries[0].get("syntax", "")
        n = len(entries)

        # HRR: mean over ACCEPTED entries only
        accepted = [e for e in entries if e.get("action") == "ACCEPTED"]
        hrr_vals = [
            e["delta_hits"] / e["hits_before"]
            for e in accepted
            if e.get("hits_before", 0) > 0
        ]
        hrr = sum(hrr_vals) / len(hrr_vals) if hrr_vals else 0.0

        # SR: fraction with delta_hits > 0 (across all attempts)
        sr = sum(1 for e in entries if e.get("delta_hits", 0) > 0) / n if n else 0.0

        # C: fraction of distinct domains with positive mean hit reduction
        domain_means: dict[str, float] = {}
        by_domain: dict[str, list[dict]] = defaultdict(list)
        for e in entries:
            by_domain[e.get("domain", "")].append(e)
        all_domains = set(by_domain.keys()) - {""}
        positive_domains = 0
        for dom, dom_entries in by_domain.items():
            if not dom:
                continue
            mean_delta = sum(e.get("delta_hits", 0) for e in dom_entries) / len(dom_entries)
            if mean_delta > 0:
                positive_domains += 1
            domain_means[dom] = mean_delta
        c = positive_domains / len(all_domains) if all_domains else 0.0

        # RP: fraction with recall penalty
        rp = sum(1 for e in entries if e.get("delta_recall", 0.0) > 0.02) / n if n else 0.0

        score = 10.0 * hrr * sr * c - 0.8 * rp

        results.append({
            "name": name,
            "syntax": syntax,
            "score": round(score, 4),
            "hrr": round(hrr, 4),
            "sr": round(sr, 4),
            "c": round(c, 4),
            "rp": round(rp, 4),
            "n_attempts": n,
            "n_accepted": len(accepted),
            "domain_means": {k: round(v, 2) for k, v in domain_means.items()},
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    for i, r in enumerate(results):
        r["rank"] = i + 1
    return results


def _score_phase3(records: list[dict]) -> list[dict]:
    by_tier: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        if r.get("phase") == "phase3":
            by_tier[r["tier"]].append(r)

    results: list[dict] = []
    for tier, entries in by_tier.items():
        n = len(entries)
        accepted = [e for e in entries if e.get("action") == "ACCEPTED"]

        # Avg_HRR over ACCEPTED
        hrr_vals = [
            e["delta_hits"] / e["hits_before"]
            for e in accepted
            if e.get("hits_before", 0) > 0
        ]
        avg_hrr = sum(hrr_vals) / len(hrr_vals) if hrr_vals else 0.0

        # SR = fraction ACCEPTED
        sr = len(accepted) / n if n else 0.0

        # Recall_Safety_Rate = fraction not REJECTED
        recall_safety = sum(1 for e in entries if e.get("action") != "REJECTED") / n if n else 0.0

        tier_score = avg_hrr * sr * recall_safety

        results.append({
            "tier": tier,
            "tier_score": round(tier_score, 4),
            "avg_hrr": round(avg_hrr, 4),
            "sr": round(sr, 4),
            "recall_safety_rate": round(recall_safety, 4),
            "n_total": n,
            "n_accepted": len(accepted),
            "n_rejected": sum(1 for e in entries if e.get("action") == "REJECTED"),
            "n_no_reduction": sum(1 for e in entries if e.get("action") == "NO_REDUCTION"),
        })

    # sort by tier_score desc; tiers with no data get appended at bottom in natural order
    known_order = [f"tier{i}" for i in range(1, 11)] + ["tierF"]
    scored = [r for r in results if r["tier_score"] > 0]
    zero = [r for r in results if r["tier_score"] == 0]
    scored.sort(key=lambda x: x["tier_score"], reverse=True)
    zero.sort(key=lambda x: known_order.index(x["tier"]) if x["tier"] in known_order else 99)
    ordered = scored + zero

    for i, r in enumerate(ordered):
        r["rank"] = i + 1
    return ordered


def _next_version(out_dir: Path) -> int:
    existing = list(out_dir.glob("aprime_laws_ver*.json"))
    if not existing:
        return 1
    nums = []
    for f in existing:
        m = re.search(r"ver(\d+)", f.stem)
        if m:
            nums.append(int(m.group(1)))
    return max(nums) + 1 if nums else 1


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    files = _latest_run_files(LOG_DIR)
    if not files:
        print(f"No *_aprime_decisions_*.jsonl found in {LOG_DIR} — writing empty laws file", file=sys.stderr)
        version = _next_version(OUT_DIR)
        out_path = OUT_DIR / f"aprime_laws_ver{version}.json"
        empty = {
            "version": version,
            "phase1_blocks": [],
            "phase3_tier_order": [],
            "phase3_tier_scores": [],
            "stats": {"n_records": 0, "n_papers": 0, "n_domains": 0, "paper_ids": [], "domains": []},
        }
        out_path.write_text(json.dumps(empty, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Wrote empty laws file → {out_path}")
        sys.exit(0)

    print(f"Reading {len(files)} log file(s)...")
    records = _read_records(files)
    print(f"  {len(records)} records total")

    phase1_scores = _score_phase1(records)
    phase3_scores = _score_phase3(records)

    version = _next_version(OUT_DIR)
    out_path = OUT_DIR / f"aprime_laws_ver{version}.json"

    paper_ids = sorted({r.get("paper_id", "") for r in records if r.get("paper_id")})
    domains = sorted({r.get("domain", "") for r in records if r.get("domain")})

    output = {
        "version": version,
        "phase1_blocks": phase1_scores,
        "phase3_tier_order": [r["tier"] for r in phase3_scores],
        "phase3_tier_scores": phase3_scores,
        "stats": {
            "n_records": len(records),
            "n_papers": len(paper_ids),
            "n_domains": len(domains),
            "paper_ids": paper_ids,
            "domains": domains,
        },
    }

    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {out_path}")

    print("\nPhase 1 block ranking:")
    for blk in phase1_scores:
        print(f"  {blk['rank']:>2}. {blk['name']:<20} score={blk['score']:.4f}  "
              f"HRR={blk['hrr']:.3f} SR={blk['sr']:.2f} C={blk['c']:.2f} RP={blk['rp']:.2f}  "
              f"n={blk['n_attempts']}")

    print("\nPhase 3 tier ranking:")
    for t in phase3_scores:
        print(f"  {t['rank']:>2}. {t['tier']:<8} score={t['tier_score']:.4f}  "
              f"HRR={t['avg_hrr']:.3f} SR={t['sr']:.2f} RSR={t['recall_safety_rate']:.2f}  "
              f"n={t['n_total']} acc={t['n_accepted']}")


if __name__ == "__main__":
    main()
