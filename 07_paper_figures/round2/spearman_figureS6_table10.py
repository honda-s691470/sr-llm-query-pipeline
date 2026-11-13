"""Second-revision Figure S6 and Supplementary Table 10: Spearman correlations of article-level scores
between the MedCPT pipeline, Elicit and Asta (formerly OpenScholar; input folder 09_openscholar_query_dataset),
per test review. Pair codes os / OpenScholar in the code refer to Asta.

Pipeline score: Final composite Stage C score of the ChatGPT Codex candidate sets in the main analysis
(harmonized Stage C, T2 pseudo-abstract, dense weight 0.5, primary scenario). For the 10 Codex reviews passed
through unranked (Stage B hits <= 1,000) the harmonized deposit has no score file; their candidates were scored
in the same rescoring run, and those Final scores are supplied in data/codex_gate_reviews_T2_a0.5_final.csv.
Inputs (read only, all in this release; no network):
  ../../stageC_harmonized/data/candidate_manifest.csv, ../../stageC_harmonized/data/scores/<condition_id>.npz
  data/codex_gate_reviews_T2_a0.5_final.csv    Final scores of the gate (pass-through) Codex reviews
  ../../pubmed_cache.zip                       titles (pubmed_records.json; codex, claude, gemini folders in this order)
  data/pmid_doi_codex_primary_candidates.csv   first PubMed ArticleIdList DOI of each candidate PMID
  ../../08_elicit_queryb_dataset/<id>/         Elicit keyword export (question export when no keyword export)
  ../../09_openscholar_query_dataset/<id>/papers_normal.json
Rules: pipeline-Elicit matched by DOI (lowercase, doi.org prefix removed); pairs involving OpenScholar matched by
title (lowercase, characters other than [a-z0-9] removed). Main matching: unique (first occurrence of a key kept per
tool); all_rows is a sensitivity analysis. A test is eligible if n >= 15 and both score vectors are non-constant.
Two-sided Spearman; Holm and Benjamini-Hochberg adjustment across all eligible tests of the same matching mode.
Outputs: output/FigureS6_spearman_all24_T2main.png|pdf, output/FigureS6_data.csv (= Supplementary Table 10,
unique matching), output/S6_correlations_both_matching_modes.csv
"""
import json
import re
import zipfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.stats import spearmanr  # noqa: E402
from statsmodels.stats.multitest import multipletests  # noqa: E402

HERE = Path(__file__).resolve().parent
REL = HERE.parents[1]
SC = REL / "stageC_harmonized/data"
OUT = HERE / "output"
OUT.mkdir(exist_ok=True)

MAN = pd.read_csv(SC / "candidate_manifest.csv")
MAN = MAN[(MAN.model == "Codex") & MAN.scenarios.str.split(";").map(lambda s: "primary" in s)].set_index("paper_id")
assert len(MAN) == 24
GATE = pd.read_csv(HERE / "data/codex_gate_reviews_T2_a0.5_final.csv", dtype={"pmid": str})
DOIMAP = pd.read_csv(HERE / "data/pmid_doi_codex_primary_candidates.csv", dtype=str, keep_default_na=False).set_index("pmid").doi.to_dict()
AREAS = pd.read_csv(REL / "07_paper_figures/clinical_areas/clinical_areas_35reviews.csv", dtype=str).set_index("paper_id").new_domain.to_dict()
Z = zipfile.ZipFile(REL / "pubmed_cache.zip")
NAMES = set(Z.namelist())


def doi(s):
    return re.sub(r'^(https?://)?(dx\.)?doi\.org/', '', str(s or '').strip().lower())


def tit(s):
    return re.sub(r'[^a-z0-9]', '', str(s or '').strip().lower())


def titles(pid):
    t = {}
    for prov in ["codex", "claude", "gemini"]:
        n = f"pubmed_cache/{MAN.loc[pid, 'domain']}/{pid}/{prov}/pubmed_records.json"
        if n in NAMES:
            for k, v in json.loads(Z.read(n)).items():
                t.setdefault(str(k), v.get("title", ""))
    return t


def correlate(A, B, key):
    out = []
    for mode in ["unique", "all_rows"]:
        a, b = A[A[key] != ""], B[B[key] != ""]
        if mode == "unique":
            a, b = a.drop_duplicates(key), b.drop_duplicates(key)
        J = a.merge(b, on=key, suffixes=("_a", "_b"))
        J = J[np.isfinite(J.score_a.astype(float)) & np.isfinite(J.score_b.astype(float))]
        n = len(J)
        ok = n >= 15 and J.score_a.nunique() > 1 and J.score_b.nunique() > 1
        rho, pv = spearmanr(J.score_a, J.score_b) if ok else (np.nan, np.nan)
        out.append(dict(matching=mode, n=n, eligible=ok, rho=rho, p_raw=pv))
    return out


rows, cov = [], []
for pid in sorted(MAN.index):
    eb = REL / "08_elicit_queryb_dataset" / pid
    ep, esrc = eb / f"Elicit - screen-results-review-{pid}_keyword.csv", "keyword"
    if not ep.exists():
        ep, esrc = eb / f"Elicit - screen-results-review-{pid}_question.csv", "question"
    el = pd.read_csv(ep, keep_default_na=False)
    el = pd.DataFrame({"title": el["Title"], "doi": el["DOI"], "score": pd.to_numeric(el["Screening score"], errors="coerce")})
    papers = json.loads((REL / "09_openscholar_query_dataset" / pid / "papers_normal.json").read_text(encoding="utf-8"))["papers"]
    os_ = pd.DataFrame([{"title": r.get("title", ""), "score": r.get("score")} for r in papers])
    for d in (el, os_):
        d["tkey"] = d.title.map(tit)
    el["dkey"] = el.doi.map(doi)
    pairs = [("el_os", el, os_, "tkey")]
    cid = MAN.loc[pid, "condition_id"]
    f = SC / "scores" / f"{cid}.npz"
    if f.exists():
        z = np.load(f)
        p, s, src = [str(x) for x in z["pmids"]], z["T2_a0.5_final"], "stageC_harmonized score file"
    else:
        g = GATE[GATE.condition_id == cid]
        assert bool(MAN.loc[pid, "gate"]) and len(g) == MAN.loc[pid, "n_candidates"], pid
        p, s, src = g.pmid.tolist(), g["T2_a0.5_final"].to_numpy(float), "data/codex_gate_reviews_T2_a0.5_final.csv"
    T = titles(pid)
    pipe = pd.DataFrame({"title": [T.get(x, "") for x in p], "doi": [DOIMAP.get(x, "") for x in p], "score": s})
    pipe["tkey"] = pipe.title.map(tit)
    pipe["dkey"] = pipe.doi.map(doi)
    pairs = [("pipe_el", pipe, el, "dkey"), ("pipe_os", pipe, os_, "tkey")] + pairs
    cov.append(dict(paper_id=pid, condition_id=cid, gate=bool(MAN.loc[pid, "gate"]), score_source=src, n_pipe=len(p),
                    n_with_doi=int((pipe.doi != "").sum()), n_with_title=int((pipe.title != "").sum())))
    for pair, A, B, key in pairs:
        for r in correlate(A, B, key):
            rows.append(dict(paper_id=pid, elicit_export=esrc, pair=pair, **r))
R = pd.DataFrame(rows)
for mode in ["unique", "all_rows"]:  # family = all eligible tests within a matching mode
    m = (R.matching == mode) & R.eligible
    R.loc[m, "p_holm"] = multipletests(R.loc[m, "p_raw"], method="holm")[1]
    R.loc[m, "p_bh"] = multipletests(R.loc[m, "p_raw"], method="fdr_bh")[1]
R.insert(1, "clinical_area", R.paper_id.str[:8].map(AREAS))
R.to_csv(OUT / "S6_correlations_both_matching_modes.csv", index=False)
pd.DataFrame(cov).to_csv(OUT / "S6_pipeline_coverage.csv", index=False)

PAIRS = [("pipe_el", "Pipeline vs Elicit", "#2E6FA3"), ("pipe_os", "Pipeline vs Asta", "#E07B2A"), ("el_os", "Elicit vs Asta", "#3A9E52")]
U = R[R.matching == "unique"]
tab = U[["paper_id", "clinical_area", "pair", "n", "eligible", "rho", "p_raw", "p_holm", "p_bh", "elicit_export"]].copy()
tab["order"] = tab.pair.map({"el_os": 0, "pipe_el": 1, "pipe_os": 2})  # row order of Supplementary Table 10
tab["pair"] = tab.pair.map({p: lab for p, lab, _ in PAIRS})
tab.sort_values(["order", "paper_id"]).drop(columns="order").to_csv(OUT / "FigureS6_data.csv", index=False)

E6 = U[U.eligible.astype(bool)]
assert len(E6) == 37 and E6.groupby("pair").size().to_dict() == {"el_os": 5, "pipe_el": 15, "pipe_os": 17}
ABBR = {"Rheumatology": "RH", "CV": "CV", "Psychiatry": "PSY", "Oncology": "ONC", "Infectious": "INF", "Other": "OTH"}
DOM = {p: AREAS[p[:8]] for p in MAN.index}
pids6 = sorted(E6.paper_id.unique(), key=lambda p: (list(ABBR).index(DOM[p]), p))
plt.rcParams.update({"font.family": "Arial", "font.size": 10, "axes.labelsize": 11})
half = (len(pids6) + 1) // 2
fig, axes = plt.subplots(2, 1, figsize=(16, 9.5), sharey=True)
for ax, chunk in zip(axes, [pids6[:half], pids6[half:]]):
    for gi, pid in enumerate(chunk):
        for k, (pair, _, c) in enumerate(PAIRS):
            x = gi + (k - 1) * 0.27
            r = E6[(E6.paper_id == pid) & (E6.pair == pair)]
            if r.empty:
                ax.plot([x - 0.06, x + 0.06], [0.04, 0.04], color="#999999", linewidth=1)
                continue
            r = r.iloc[0]
            sig = r.p_holm < 0.05
            ax.bar(x, r.rho, width=0.25, color=c if sig else "white", edgecolor=c, hatch=None if sig else "///", linewidth=1.5, alpha=0.85)
            ax.text(x, r.rho + (0.02 if r.rho >= 0 else -0.02), f"n={int(r.n)}", ha="center", va="bottom" if r.rho >= 0 else "top", fontsize=7, color="#444444")
    ax.set_xticks(range(len(chunk)))
    ax.set_xticklabels([f"{p.split('_')[0]}\n({ABBR[DOM[p]]})" for p in chunk], fontsize=8.5)
    ax.axhline(0, color="black", linewidth=1)
    ax.set_xlim(-0.6, half - 0.4)
    ax.yaxis.grid(True, linestyle="--", alpha=0.35)
    ax.set_ylabel("Spearman ρ")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
axes[0].set_ylim(-0.65, 0.95)
h = [mpatches.Patch(facecolor=c, edgecolor=c, label=lab) for _, lab, c in PAIRS] + \
    [mpatches.Patch(facecolor="white", edgecolor="#777777", hatch="///", label="Holm-adjusted p ≥ 0.05 (hatched)"),
     plt.Line2D([], [], color="#999999", label="— : < 15 matched articles (not analysed)")]
fig.legend(handles=h, loc="lower center", ncol=5, frameon=False, fontsize=9.5, bbox_to_anchor=(0.5, -0.01))
fig.tight_layout(rect=[0, 0.04, 1, 1])
for ext in ["png", "pdf"]:
    fig.savefig(OUT / f"FigureS6_spearman_all24_T2main.{ext}", dpi=300, bbox_inches="tight")
plt.close(fig)
print(E6.groupby("pair").agg(k=("n", "size"), rho_min=("rho", "min"), rho_med=("rho", "median"), rho_max=("rho", "max"),
                             holm_sig=("p_holm", lambda s: int((s < .05).sum()))).round(3).to_string())
