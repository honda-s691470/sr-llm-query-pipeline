"""Second-revision Figure S5: 11-panel cutoff sensitivity (overall, clinical area, broad review type).

Main analysis: harmonized Stage C, T2 pseudo-abstract, dense weight (alpha) 0.5, primary candidate sets,
cuts 0, 30, 50, 60, 70, 80 and 90 (each cut applied independently to the same ranking).
Inputs (read only, all in this release):
  ../../stageC_harmonized/expected/per_sr_metrics_7cuts_independent.csv   (scenario primary, arm T2, alpha 0.5)
  ../clinical_areas/clinical_areas_35reviews.csv                            clinical area (new_domain, set == test)
  ../../revision_reruns/cutoff_sensitivity_overall_domain_reviewtype/data/test24_review_type_classification.csv
Outputs: output/FigureS5_cutoff_sensitivity_11panel_T2main.png|pdf, output/FigureS5_data.csv
The summary and plotting functions are those of the 11-panel script used for the manuscript; only the input
rows differ from the historical Run1 version in ../../revision_reruns/cutoff_sensitivity_overall_domain_reviewtype/.
CPU only; no network or model calls.
"""
import csv
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
REL = HERE.parents[1]
OUTDIR = HERE / "output"
OUTDIR.mkdir(exist_ok=True)
METRICS = REL / "stageC_harmonized/expected/per_sr_metrics_7cuts_independent.csv"
AREAS = REL / "07_paper_figures/clinical_areas/clinical_areas_35reviews.csv"
TYPE_CSV = REL / "revision_reruns/cutoff_sensitivity_overall_domain_reviewtype/data/test24_review_type_classification.csv"

PROVIDERS = ["claude", "codex", "gemini"]
CUTS = [0, 30, 50, 60, 70, 80, 90]
COLORS = {"claude": "#2166AC", "codex": "#D6604D", "gemini": "#1A9850", "pooled": "#000000"}
MARKERS = {"claude": "o", "codex": "s", "gemini": "^", "pooled": "D"}
LABELS = {"claude": "Claude", "codex": "Codex", "gemini": "Gemini", "pooled": "3-LLM mean"}
DOMAIN_ORDER = ["Rheumatology", "CV", "Psychiatry", "Oncology", "Infectious", "Other"]
DOMAIN_LABELS = {"Rheumatology": "Rheumatology", "CV": "Cardiovascular disease", "Psychiatry": "Psychiatry",
                 "Oncology": "Oncology", "Infectious": "Infectious diseases", "Other": "Other"}
BROAD_ORDER = [
    "Intervention / management",
    "Exposure / risk / association",
    "Diagnostic / biomarker / prognostic",
    "Mixed-methods / qualitative / methodological",
]
BROAD_MAP = {
    "Intervention/effectiveness": "Intervention / management",
    "Intervention/mechanistic mixed evidence": "Intervention / management",
    "Intervention/implementation mixed-methods": "Intervention / management",
    "Intervention/safety": "Intervention / management",
    "Intervention/safety-effectiveness": "Intervention / management",
    "Intervention/effectiveness-safety": "Intervention / management",
    "Intervention/comparative management": "Intervention / management",
    "Exposure-risk/etiology": "Exposure / risk / association",
    "Prevalence/association": "Exposure / risk / association",
    "Association/biomarker": "Exposure / risk / association",
    "Association/quality-of-life factors": "Exposure / risk / association",
    "Prevalence/risk-factor": "Exposure / risk / association",
    "Prevalence/clinical phenotype": "Exposure / risk / association",
    "Diagnostic/biomarker": "Diagnostic / biomarker / prognostic",
    "Diagnostic/referral criteria": "Diagnostic / biomarker / prognostic",
    "Prognostic/prediction model": "Diagnostic / biomarker / prognostic",
    "Prognostic/biomarker": "Diagnostic / biomarker / prognostic",
    "Mechanistic/preclinical-translational": "Mixed-methods / qualitative / methodological",
    "Methods/reporting epidemiology": "Mixed-methods / qualitative / methodological",
    "Qualitative/mixed-methods evidence synthesis": "Mixed-methods / qualitative / methodological",
}
FIELDS = ["stratum_type", "stratum", "stratum_label", "provider", "cut", "n_papers", "mean_recall", "mean_hits",
          "macro_mean_nnr", "aggregate_nnr", "total_hits", "total_tp"]


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def test_domain_map():
    return {r["paper_id"]: r["new_domain"] for r in read_csv(AREAS) if r["set"] == "test"}  # 8-digit PMID keys


def review_type_map():
    return {r["paper_id"]: BROAD_MAP[r["review_type"]] for r in read_csv(TYPE_CSV)}


def summarize(rows, stratum_type, stratum, stratum_label):
    summary = []
    for provider in PROVIDERS:
        for cut in CUTS:
            sub = [r for r in rows if r["provider"] == provider and r["cut"] == cut]
            nnrs = [r["hits"] / r["tp"] for r in sub if r["tp"] > 0]
            total_hits = sum(r["hits"] for r in sub)
            total_tp = sum(r["tp"] for r in sub)
            summary.append({
                "stratum_type": stratum_type, "stratum": stratum, "stratum_label": stratum_label,
                "provider": provider, "cut": cut,
                "n_papers": len({r["paper_id"] for r in sub}),
                "mean_recall": sum(r["recall"] for r in sub) / len(sub),
                "mean_hits": sum(r["hits"] for r in sub) / len(sub),
                "macro_mean_nnr": sum(nnrs) / len(nnrs) if nnrs else math.nan,
                "aggregate_nnr": total_hits / total_tp if total_tp > 0 else math.nan,
                "total_hits": total_hits, "total_tp": total_tp,
            })
    for cut in CUTS:
        pr = [r for r in summary if r["provider"] in PROVIDERS and r["cut"] == cut]
        summary.append({
            "stratum_type": stratum_type, "stratum": stratum, "stratum_label": stratum_label,
            "provider": "pooled", "cut": cut, "n_papers": pr[0]["n_papers"],
            "mean_recall": sum(r["mean_recall"] for r in pr) / len(pr),
            "mean_hits": sum(r["mean_hits"] for r in pr) / len(pr),
            "macro_mean_nnr": sum(r["macro_mean_nnr"] for r in pr) / len(pr),
            "aggregate_nnr": sum(r["aggregate_nnr"] for r in pr) / len(pr),
            "total_hits": "", "total_tp": "",
        })
    return summary


def build_rows():
    domains, types = test_domain_map(), review_type_map()
    rows = []
    for r in read_csv(METRICS):
        if r["scenario"] != "primary" or r["arm"] != "T2" or float(r["alpha"]) != 0.5:
            continue
        pid = r["paper_id"]
        rows.append({"paper_id": pid, "provider": r["model"].lower(), "cut": int(r["cut"]), "recall": float(r["recall"]),
                     "hits": float(r["keep"]), "tp": float(r["tp"]), "domain": domains[pid[:8]], "broad_review_type": types[pid]})
    assert len(rows) == 24 * 3 * len(CUTS), len(rows)
    return rows


def build_summary(rows):
    out = summarize(rows, "overall", "overall_test24", "Overall test set")
    for d in DOMAIN_ORDER:
        out += summarize([r for r in rows if r["domain"] == d], "domain", d, DOMAIN_LABELS[d])
    for b in BROAD_ORDER:
        out += summarize([r for r in rows if r["broad_review_type"] == b], "broad_review_type", b, b)
    return out


def draw_panel(ax, summary, stratum, letter):
    panel_rows = [r for r in summary if r["stratum"] == stratum]
    n = next(r["n_papers"] for r in panel_rows if r["provider"] == "pooled" and r["cut"] == 0)
    label = next(r["stratum_label"] for r in panel_rows)
    ax.text(-0.11, 1.08, letter, transform=ax.transAxes, fontsize=14, fontweight="bold", va="top")
    for provider in PROVIDERS + ["pooled"]:
        pts = sorted([r for r in panel_rows if r["provider"] == provider], key=lambda r: r["cut"])
        ax.plot([r["macro_mean_nnr"] for r in pts], [r["mean_recall"] for r in pts], color=COLORS[provider],
                marker=MARKERS[provider], linewidth=3.0 if provider == "pooled" else 2.1, markersize=5.0,
                label=LABELS[provider], zorder=4 if provider == "pooled" else 2)
        for r in pts:
            ax.annotate(str(r["cut"]), (r["macro_mean_nnr"], r["mean_recall"]), textcoords="offset points",
                        xytext=(4, 3), fontsize=8, color=COLORS[provider])
    ax.set_title(f"{label} (n={n})", fontsize=12)
    ax.set_xlabel("Mean NNR")
    ax.grid(True, color="#D0D5DD", linewidth=0.8, alpha=0.85)


def plot(summary):
    plt.rcParams.update({"font.family": "Arial", "font.size": 11, "axes.spines.top": False, "axes.spines.right": False})
    panels = ["overall_test24"] + DOMAIN_ORDER + BROAD_ORDER
    letters = [chr(ord("A") + i) for i in range(len(panels))]
    fig, axes = plt.subplots(6, 2, figsize=(12.6, 21.6), sharey=False)
    axes.ravel()[-1].set_visible(False)
    for ax, stratum, letter in zip(axes.ravel(), panels, letters):
        draw_panel(ax, summary, stratum, letter)
    for ax in axes[:, 0]:
        ax.set_ylabel("Mean recall")
    handles, labels = axes.ravel()[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4, frameon=False, bbox_to_anchor=(0.5, 0.997))
    fig.suptitle("Cutoff sensitivity in the overall test set, by clinical area, and by broad review type", fontsize=15, y=1.006)
    fig.text(0.5, 0.008, "Point labels indicate cutoff percentage. NNR is the mean per-SLR number needed to read.", ha="center", fontsize=11)
    fig.tight_layout(rect=(0, 0.02, 1, 0.975))
    for ext in ["png", "pdf"]:
        fig.savefig(OUTDIR / f"FigureS5_cutoff_sensitivity_11panel_T2main.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)


def main():
    summary = build_summary(build_rows())
    with (OUTDIR / "FigureS5_data.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(summary)
    plot(summary)
    print("rows", len(summary))


if __name__ == "__main__":
    main()
