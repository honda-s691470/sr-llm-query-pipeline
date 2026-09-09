import csv
import math
from pathlib import Path

import matplotlib.pyplot as plt


BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[2]
OUTDIR = BASE / "repro_check"
DATA_DIR = BASE / "data"
DETAIL = DATA_DIR / "cut0_90_old_cache_same_condition_detail.csv"
TYPE_CSV = DATA_DIR / "test24_review_type_classification.csv"
TEST_DATA = ROOT / "public_release/05_test_data"

PROVIDERS = ["claude", "codex", "gemini"]
CUTS = [0, 30, 50, 60, 70, 80, 90]
COLORS = {"claude": "#2166AC", "codex": "#D6604D", "gemini": "#1A9850", "pooled": "#000000"}
MARKERS = {"claude": "o", "codex": "s", "gemini": "^", "pooled": "D"}
LABELS = {"claude": "Claude", "codex": "Codex", "gemini": "Gemini", "pooled": "3-LLM mean"}

DOMAIN_ORDER = [
    "01_Rheumatoid_Arthritis",
    "02_Cardiovascular_Disease",
    "03_Psychiatry",
    "04_Oncology",
    "05_Infectious_Diseases",
]
DOMAIN_LABELS = {
    "01_Rheumatoid_Arthritis": "Rheumatoid arthritis",
    "02_Cardiovascular_Disease": "Cardiovascular disease",
    "03_Psychiatry": "Psychiatry",
    "04_Oncology": "Oncology",
    "05_Infectious_Diseases": "Infectious diseases",
}
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


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fieldnames):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_domain_map():
    out = {}
    for domain_dir in TEST_DATA.iterdir():
        if not domain_dir.is_dir() or domain_dir.name.startswith("_"):
            continue
        for paper_dir in domain_dir.iterdir():
            if paper_dir.is_dir():
                out[paper_dir.name] = domain_dir.name
    return out


def review_type_map():
    out = {}
    for row in read_csv(TYPE_CSV):
        out[row["paper_id"]] = BROAD_MAP[row["review_type"]]
    return out


def summarize(rows, stratum_type, stratum, stratum_label):
    summary = []
    for provider in PROVIDERS:
        for cut in CUTS:
            sub = [r for r in rows if r["provider"] == provider and r["cut"] == cut]
            nnrs = [r["hits"] / r["tp"] for r in sub if r["tp"] > 0]
            total_hits = sum(r["hits"] for r in sub)
            total_tp = sum(r["tp"] for r in sub)
            summary.append({
                "stratum_type": stratum_type,
                "stratum": stratum,
                "stratum_label": stratum_label,
                "provider": provider,
                "cut": cut,
                "n_papers": len({r["paper_id"] for r in sub}),
                "mean_recall": sum(r["recall"] for r in sub) / len(sub),
                "mean_hits": sum(r["hits"] for r in sub) / len(sub),
                "macro_mean_nnr": sum(nnrs) / len(nnrs) if nnrs else math.nan,
                "aggregate_nnr": total_hits / total_tp if total_tp > 0 else math.nan,
                "total_hits": total_hits,
                "total_tp": total_tp,
            })
    for cut in CUTS:
        provider_rows = [r for r in summary if r["provider"] in PROVIDERS and r["cut"] == cut]
        summary.append({
            "stratum_type": stratum_type,
            "stratum": stratum,
            "stratum_label": stratum_label,
            "provider": "pooled",
            "cut": cut,
            "n_papers": provider_rows[0]["n_papers"],
            "mean_recall": sum(r["mean_recall"] for r in provider_rows) / len(provider_rows),
            "mean_hits": sum(r["mean_hits"] for r in provider_rows) / len(provider_rows),
            "macro_mean_nnr": sum(r["macro_mean_nnr"] for r in provider_rows) / len(provider_rows),
            "aggregate_nnr": sum(r["aggregate_nnr"] for r in provider_rows) / len(provider_rows),
            "total_hits": "",
            "total_tp": "",
        })
    return summary


def build_rows():
    domains = test_domain_map()
    types = review_type_map()
    rows = []
    for row in read_csv(DETAIL):
        if row.get("table") != "old_cache_recomputed":
            continue
        paper_id = row["paper_id"]
        rows.append({
            "paper_id": paper_id,
            "provider": row["provider"],
            "cut": int(row["cut"]),
            "recall": float(row["recall"]),
            "hits": float(row["hits"]),
            "tp": float(row["tp"]),
            "domain": domains[paper_id],
            "broad_review_type": types[paper_id],
        })
    return rows


def build_summary(rows):
    out = summarize(rows, "overall", "overall_test24", "Overall test set")
    for domain in DOMAIN_ORDER:
        out += summarize(
            [r for r in rows if r["domain"] == domain],
            "domain",
            domain,
            DOMAIN_LABELS[domain],
        )
    for broad in BROAD_ORDER:
        out += summarize(
            [r for r in rows if r["broad_review_type"] == broad],
            "broad_review_type",
            broad,
            broad,
        )
    return out


def draw_panel(ax, summary, stratum, letter):
    panel_rows = [r for r in summary if r["stratum"] == stratum]
    n = next(r["n_papers"] for r in panel_rows if r["provider"] == "pooled" and r["cut"] == 0)
    label = next(r["stratum_label"] for r in panel_rows)
    ax.text(-0.11, 1.08, letter, transform=ax.transAxes, fontsize=14, fontweight="bold", va="top")
    for provider in PROVIDERS + ["pooled"]:
        pts = sorted([r for r in panel_rows if r["provider"] == provider], key=lambda r: r["cut"])
        ax.plot(
            [r["macro_mean_nnr"] for r in pts],
            [r["mean_recall"] for r in pts],
            color=COLORS[provider],
            marker=MARKERS[provider],
            linewidth=3.0 if provider == "pooled" else 2.1,
            markersize=5.0,
            label=LABELS[provider],
            zorder=4 if provider == "pooled" else 2,
        )
        for r in pts:
            ax.annotate(
                str(r["cut"]),
                (r["macro_mean_nnr"], r["mean_recall"]),
                textcoords="offset points",
                xytext=(4, 3),
                fontsize=8,
                color=COLORS[provider],
            )
    ax.set_title(f"{label} (n={n})", fontsize=12)
    ax.set_xlabel("Mean NNR")
    ax.grid(True, color="#D0D5DD", linewidth=0.8, alpha=0.85)


def plot(summary):
    plt.rcParams.update({
        "font.family": "Arial",
        "font.size": 11,
        "axes.spines.top": False,
        "axes.spines.right": False,
    })
    panels = ["overall_test24"] + DOMAIN_ORDER + BROAD_ORDER
    letters = [chr(ord("A") + i) for i in range(len(panels))]
    fig, axes = plt.subplots(5, 2, figsize=(12.6, 18.0), sharey=False)
    for ax, stratum, letter in zip(axes.ravel(), panels, letters):
        draw_panel(ax, summary, stratum, letter)
    for ax in axes[:, 0]:
        ax.set_ylabel("Mean recall")
    handles, labels = axes.ravel()[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4, frameon=False, bbox_to_anchor=(0.5, 0.997))
    fig.suptitle("Cutoff sensitivity in the overall test set, by clinical domain, and by broad review type", fontsize=15, y=1.006)
    fig.text(0.5, 0.008, "Point labels indicate cutoff percentage. NNR is the mean per-SLR number needed to read.", ha="center", fontsize=11)
    fig.tight_layout(rect=(0, 0.02, 1, 0.975))
    png = OUTDIR / "Supplementary_Figure_cutoff_sensitivity_overall_domain_reviewtype_macroNNR_10panel.png"
    pdf = OUTDIR / "Supplementary_Figure_cutoff_sensitivity_overall_domain_reviewtype_macroNNR_10panel.pdf"
    fig.savefig(png, dpi=300, bbox_inches="tight")
    fig.savefig(pdf, bbox_inches="tight")
    plt.close(fig)
    return png, pdf


def write_legend():
    text = """# Legend

**Figure Sx. Cutoff sensitivity in the overall test set, across clinical domains, and across broad review types.**

Panel A shows the overall 24-SR test set. Panels B-F show test-set performance stratified by clinical domain, and Panels G-J show performance stratified by broad review type. Each point represents cutoff 0, 30, 50, 60, 70, 80, or 90. Colored lines show Claude, Codex, and Gemini separately; the black line shows the unweighted mean of the three LLM-specific estimates. Recall is the mean recall across systematic reviews in the stratum. NNR is the ordinary manuscript metric: the mean per-SLR number needed to read, calculated as retained hits divided by true-positive hits within each SLR and then averaged.

Because NNR is averaged per review, it is not mathematically forced to decrease at every stricter cutoff. NNR can increase if a cutoff removes true positives disproportionately in one or more reviews, even though retained hit counts decrease. Domain- and broad review type-specific findings are descriptive because each subgroup contained few reviews, and broad review type was assigned post hoc for robustness assessment rather than for rulebook generation, refinement, or cutoff selection.
"""
    (OUTDIR / "Legend_10panel.md").write_text(text, encoding="utf-8")


def main():
    rows = build_rows()
    summary = build_summary(rows)
    fields = [
        "stratum_type",
        "stratum",
        "stratum_label",
        "provider",
        "cut",
        "n_papers",
        "mean_recall",
        "mean_hits",
        "macro_mean_nnr",
        "aggregate_nnr",
        "total_hits",
        "total_tp",
    ]
    csv_path = OUTDIR / "Supplementary_Figure_cutoff_sensitivity_overall_domain_reviewtype_macroNNR_10panel_data.csv"
    write_csv(csv_path, summary, fields)
    png, pdf = plot(summary)
    write_legend()
    print(csv_path)
    print(png)
    print(pdf)
    print(OUTDIR / "Legend_10panel.md")


if __name__ == "__main__":
    main()

