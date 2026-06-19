"""
Generate unified training SR figures using the same style as plot_history_ver2.py.
- Globally unified marker (per action type) and color (per concept category)
- Figure 2 (40357797): standalone with legend for types present in that SR
- Individual panels (10 remaining SRs): no legend, same 2-column layout as original
- Figure S1: 10-panel combined, no per-panel legends
- Legend-only figure: standalone legend for Figure S1 caption
"""

from __future__ import annotations
import json
import os
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
from matplotlib.gridspec import GridSpec

# ── Paths ───────────────────────────────────────────────────────────────────
_SCRIPT_DIR = Path(__file__).resolve().parent
BASE = _SCRIPT_DIR.parent.parent.parent / "04_data"  # public_release/04_data/
OUT  = _SCRIPT_DIR.parent / "figures"
OUT.mkdir(parents=True, exist_ok=True)

# ── All action types & concept categories (global) ──────────────────────────
ALL_ACTION_TYPES = sorted([
    "EXPAND_FILTER_STUDY_DESIGN",
    "EXPAND_PRIMARY_CONDITION",
    "EXPAND_PRIMARY_INTERVENTION",
    "EXPAND_PRIMARY_MEASUREMENT",
    "EXPAND_PRIMARY_POPULATION",
    "EXPAND_PRIMARY_SETTING_PROVIDER",
    "EXPAND_PRIMARY_STUDY_DESIGN",
    "INITIAL_PRIMARY_BASE_QUERY",
    "RESTORE_FILTER_AFTER_RECALL_DROP",
    "RESTORE_FILTER_AGE_CONSTRAINT",
    "RESTORE_FILTER_AGE_CONSTRAINT_TEST",
    "RESTORE_FILTER_HUMAN_SYNTAX",
    "RESTORE_PRIMARY_AFTER_RECALL_DROP",
    "RESTRICT_FIELD_AUXILIARY_TIAB",
    "RESTRICT_FILTER_HUMANS",
    "RESTRICT_FILTER_LANGUAGE",
    "RESTRICT_FILTER_PUBLICATION_TYPE",
    "RESTRICT_FILTER_STUDY_DESIGN",
    "RESTRICT_PRIMARY_AUXILIARY_TERM",
    "RESTRICT_PRIMARY_CONDITION",
    "RESTRICT_PRIMARY_INTERVENTION",
    "RESTRICT_PRIMARY_OUTCOME",
    "RESTRICT_PRIMARY_POPULATION",
])

ALL_CONCEPT_CATS = sorted([
    "CONDITION_OUTCOME",
    "INTERVENTION_EXPOSURE",
    "MEASUREMENT_INSTRUMENT",
    "OTHER",
    "POPULATION_CONTEXT",
    "SETTING_PROVIDER",
    "STUDY_DESIGN_METHOD",
])

# ── Global unified marker+color per action type (1-to-1 mapping) ─────────────
# Color encodes direction group; marker shape distinguishes within group.
# Every (color, marker) pair is unique across all 23 action types.
ACTION_EDGE = "black"

ACTION_STYLE: dict[str, tuple[str, str]] = {
    # INITIAL — dark gray
    "INITIAL_PRIMARY_BASE_QUERY":          ("D",  "#444444"),

    # EXPAND — blue, 7 unique markers
    "EXPAND_FILTER_STUDY_DESIGN":          ("o",  "#2166AC"),
    "EXPAND_PRIMARY_CONDITION":            ("s",  "#2166AC"),
    "EXPAND_PRIMARY_INTERVENTION":         ("^",  "#2166AC"),
    "EXPAND_PRIMARY_MEASUREMENT":          ("v",  "#2166AC"),
    "EXPAND_PRIMARY_POPULATION":           ("<",  "#2166AC"),
    "EXPAND_PRIMARY_SETTING_PROVIDER":     (">",  "#2166AC"),
    "EXPAND_PRIMARY_STUDY_DESIGN":         ("p",  "#2166AC"),

    # RESTORE — green, 5 unique markers
    "RESTORE_FILTER_AFTER_RECALL_DROP":    ("o",  "#1A9641"),
    "RESTORE_FILTER_AGE_CONSTRAINT":       ("s",  "#1A9641"),
    "RESTORE_FILTER_AGE_CONSTRAINT_TEST":  ("^",  "#1A9641"),
    "RESTORE_FILTER_HUMAN_SYNTAX":         ("h",  "#1A9641"),
    "RESTORE_PRIMARY_AFTER_RECALL_DROP":   ("H",  "#1A9641"),

    # RESTRICT — red, 10 unique markers
    "RESTRICT_FIELD_AUXILIARY_TIAB":       ("o",  "#D7191C"),
    "RESTRICT_FILTER_HUMANS":              ("s",  "#D7191C"),
    "RESTRICT_FILTER_LANGUAGE":            ("^",  "#D7191C"),
    "RESTRICT_FILTER_PUBLICATION_TYPE":    ("v",  "#D7191C"),
    "RESTRICT_FILTER_STUDY_DESIGN":        ("<",  "#D7191C"),
    "RESTRICT_PRIMARY_AUXILIARY_TERM":     (">",  "#D7191C"),
    "RESTRICT_PRIMARY_CONDITION":          ("D",  "#D7191C"),
    "RESTRICT_PRIMARY_INTERVENTION":       ("p",  "#D7191C"),
    "RESTRICT_PRIMARY_OUTCOME":            ("*",  "#D7191C"),
    "RESTRICT_PRIMARY_POPULATION":         ("X",  "#D7191C"),
}

def _action_marker(action: str) -> str:
    return ACTION_STYLE.get(action, ("o", "#888888"))[0]

def _action_color(action: str) -> str:
    return ACTION_STYLE.get(action, ("o", "#888888"))[1]

_color_cycle = plt.rcParams["axes.prop_cycle"].by_key().get(
    "color", ["C0","C1","C2","C3","C4","C5","C6","C7","C8","C9"]
)
GLOBAL_CONCEPT_TO_COLOR = {
    c: _color_cycle[i % len(_color_cycle)]
    for i, c in enumerate(ALL_CONCEPT_CATS)
}

DOMAIN_LABEL = {
    "02_Cardiovascular_Disease": "Cardiovascular Disease",
    "03_Psychiatry":             "Psychiatry",
    "05_Infectious_Diseases":    "Infectious Diseases",
}

# ── Helpers ──────────────────────────────────────────────────────────────────
def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    rows.sort(key=lambda r: int(r.get("iteration", 0)))
    return rows

def safe_str(value) -> str:
    return "" if value is None else str(value)

def compute_phase_spans(rows: list[dict]) -> list[tuple[int, int, str]]:
    if not rows:
        return []
    spans = []
    current_phase = safe_str(rows[0].get("phase", ""))
    start = int(rows[0].get("iteration", 1))
    for row in rows[1:]:
        it    = int(row.get("iteration", 0))
        phase = safe_str(row.get("phase", ""))
        if phase != current_phase:
            spans.append((start, it - 1, current_phase))
            start = it
            current_phase = phase
    spans.append((start, int(rows[-1].get("iteration", start)), current_phase))
    return spans

def phase_bg(phase: str) -> tuple[str, float]:
    text = (phase or "").lower()
    if "peeking" in text:
        return "#fff7cc", 0.40
    if "pruning" in text:
        return "#dff5df", 0.40
    return "#eaf2fb", 0.35

# ── Core draw function (same logic as original plot_history_ver2.py) ─────────
def draw_axes(ax_top, ax_bottom, rows, title: str,
              show_legend_inline=True, fontsize_base=11):
    iterations = [int(r["iteration"]) for r in rows]
    recalls    = [float(r.get("recall", 0.0)) for r in rows]
    hits       = [int(r.get("total_hits", 0)) for r in rows]
    spans      = compute_phase_spans(rows)

    # Phase backgrounds + labels
    for start, end, phase in spans:
        color, alpha = phase_bg(phase)
        for ax in [ax_top, ax_bottom]:
            ax.axvspan(start - 0.5, end + 0.5, color=color, alpha=alpha, zorder=0)
        ax_top.text(
            (start + end) / 2, 1.01, phase,
            ha="center", va="bottom",
            transform=ax_top.get_xaxis_transform(),
            fontsize=fontsize_base, fontweight="bold",
        )

    # Top: Recall
    ax_top.set_ylabel("Recall", fontsize=fontsize_base)
    ax_top.plot(iterations, recalls, marker="o", linewidth=2.5,
                label="Recall", color="tab:blue")
    ax_top.set_ylim(0, 1.05)
    ax_top.grid(True, axis="y", linestyle="--", alpha=0.25)
    ax_top.axhline(1.0, linestyle="--", linewidth=1, color="black")
    ax_top.set_title(title, fontsize=fontsize_base, fontweight="bold",
                     loc="left", pad=4)

    # Top: Total Hits (twin)
    ax_hits = ax_top.twinx()
    ax_hits.set_ylabel("Total Hits", fontsize=fontsize_base - 1,
                        rotation=270, labelpad=10)
    ax_hits.plot(iterations, hits, marker="s", linestyle="--", linewidth=2.2,
                 label="Total Hits", color="tab:orange")
    ax_hits.yaxis.set_major_formatter(
        matplotlib.ticker.FuncFormatter(
            lambda x, _: f"{int(x/1000)}k" if x >= 1000 else str(int(x))
        )
    )

    if show_legend_inline:
        h1, l1 = ax_top.get_legend_handles_labels()
        h2, l2 = ax_hits.get_legend_handles_labels()
        ax_top.legend(h1 + h2, l1 + l2, loc="lower right",
                      fontsize=fontsize_base - 2)

    plt.setp(ax_top.get_xticklabels(), visible=False)

    # Bottom: action markers + concept dots
    ax_bottom.set_xlabel("Iteration", fontsize=fontsize_base)
    ax_bottom.set_ylabel("Change Event", fontsize=fontsize_base)
    ax_bottom.set_ylim(0, 1)
    ax_bottom.set_xticks(iterations)
    ax_bottom.tick_params(axis="x", labelsize=fontsize_base - 1)

    y_action  = 0.72
    y_concept = 0.30
    for it in iterations:
        ax_bottom.plot([it, it], [0.45, 0.55],
                       color="gray", linewidth=1.5, alpha=0.6)

    for row in rows:
        it      = int(row["iteration"])
        action  = safe_str(row.get("action_type",      "UNKNOWN"))
        concept = safe_str(row.get("concept_category", "NONE"))

        ax_bottom.scatter(
            it, y_action,
            marker=_action_marker(action),
            s=160, facecolors=_action_color(action), edgecolors=ACTION_EDGE,
            linewidth=1.5, zorder=3,
        )
        ax_bottom.scatter(
            it, y_concept,
            marker="o", s=160,
            color=GLOBAL_CONCEPT_TO_COLOR.get(concept, "C0"),
            zorder=3,
        )

    ax_bottom.set_yticks([y_concept, y_action])
    ax_bottom.set_yticklabels(
        ["Concept\n(Topic)", "Action\n(Method)"],
        fontsize=fontsize_base,
    )
    for lbl in ax_bottom.get_yticklabels():
        lbl.set_fontweight("bold")
    ax_bottom.get_yticklabels()[1].set_color("dimgray")

# ── Legend handle builders ────────────────────────────────────────────────────
def make_action_handles(action_list):
    return [
        Line2D([0], [0],
               marker=_action_marker(a),
               color="w", markerfacecolor=_action_color(a),
               markeredgecolor=ACTION_EDGE, markeredgewidth=1.5,
               markersize=9, label=a)
        for a in action_list
    ]

def make_concept_handles(concept_list):
    return [
        Line2D([0], [0], marker="o", color="w",
               markerfacecolor=GLOBAL_CONCEPT_TO_COLOR[c],
               markersize=9, label=c)
        for c in concept_list
    ]

# Training 11 paper IDs (TableS1 training set)
TRAINING_PMIDS = {
    "41522206", "41684373", "41707176",        # CV
    "40357797", "41582468", "41582599", "41694153",  # PSY
    "41770456", "41781415", "41789521", "41790564",  # INF
}

# ── Collect training SRs only ─────────────────────────────────────────────────
ALL_SRS: list[dict] = []
for _domain in sorted(os.listdir(BASE)):
    _dpath = BASE / _domain
    if not _dpath.is_dir():
        continue
    for _sr in sorted(os.listdir(_dpath)):
        _pmid = _sr.split("_")[0]
        if _pmid not in TRAINING_PMIDS:
            continue
        _fpath = _dpath / _sr / "search_history.jsonl"
        if not _fpath.exists():
            continue
        ALL_SRS.append({
            "domain":       _domain,
            "domain_label": DOMAIN_LABEL.get(_domain, _domain),
            "sr":           _sr,
            "pmid":         _pmid,
            "rows":         read_jsonl(_fpath),
        })

FIG2_PMID = "40357797"
fig2_sr   = next(s for s in ALL_SRS if s["pmid"] == FIG2_PMID)
remaining = [s for s in ALL_SRS if s["pmid"] != FIG2_PMID]

# ── Shared rcParams ───────────────────────────────────────────────────────────
plt.rcParams.update({
    "font.size":       11,
    "axes.labelsize":  12,
    "xtick.labelsize": 11,
    "ytick.labelsize": 11,
    "legend.fontsize": 9,
})

# ─────────────────────────────────────────────────────────────────────────────
# 1.  Figure 2 — standalone with legend (identical layout to original)
# ─────────────────────────────────────────────────────────────────────────────
def make_figure2(info: dict, outpath: Path) -> None:
    rows = info["rows"]
    fig  = plt.figure(figsize=(16, 9), constrained_layout=True)
    gs   = fig.add_gridspec(2, 2,
                            height_ratios=[3.0, 2.0],
                            width_ratios=[4.0, 2.4],
                            wspace=0.04)

    ax_top    = fig.add_subplot(gs[0, 0])
    ax_bottom = fig.add_subplot(gs[1, 0], sharex=ax_top)
    ax_leg    = fig.add_subplot(gs[:, 1])
    ax_leg.axis("off")

    draw_axes(ax_top, ax_bottom, rows,
              f"PMID {info['pmid']}  |  {info['domain_label']}",
              show_legend_inline=True)

    # Legend: only types present in this SR
    present_actions  = sorted({safe_str(r.get("action_type"))      for r in rows})
    present_concepts = sorted({safe_str(r.get("concept_category")) for r in rows})

    leg1 = ax_leg.legend(
        handles=make_action_handles(present_actions),
        title=f"Action Types (n={len(present_actions)})",
        loc="upper left", bbox_to_anchor=(0.05, 0.72),
        frameon=True, fancybox=True, labelspacing=0.6,
    )
    ax_leg.add_artist(leg1)
    ax_leg.legend(
        handles=make_concept_handles(present_concepts),
        title=f"Concept Categories (n={len(present_concepts)})",
        loc="upper left", bbox_to_anchor=(0.05, 0.30),
        frameon=True, fancybox=True, labelspacing=0.6,
    )

    fig.savefig(outpath, dpi=300)
    plt.close(fig)
    print(f"Saved: {outpath}")

# ─────────────────────────────────────────────────────────────────────────────
# 2.  Individual panels — same 2-column layout, right column EMPTY
#     (identical left-margin space as Figure 2 → labels don't overlap)
# ─────────────────────────────────────────────────────────────────────────────
def make_individual(info: dict, outpath: Path) -> None:
    rows = info["rows"]
    fig  = plt.figure(figsize=(16, 9), constrained_layout=True)
    gs   = fig.add_gridspec(2, 2,
                            height_ratios=[3.0, 2.0],
                            width_ratios=[4.0, 2.4],
                            wspace=0.04)

    ax_top    = fig.add_subplot(gs[0, 0])
    ax_bottom = fig.add_subplot(gs[1, 0], sharex=ax_top)
    ax_leg    = fig.add_subplot(gs[:, 1])
    ax_leg.axis("off")                  # right column: empty, no legend

    draw_axes(ax_top, ax_bottom, rows,
              f"PMID {info['pmid']}  |  {info['domain_label']}",
              show_legend_inline=True)

    fig.savefig(outpath, dpi=300)
    plt.close(fig)
    print(f"Saved: {outpath}")

# ─────────────────────────────────────────────────────────────────────────────
# 3.  Figure S1 — 10-panel combined, NO per-panel legends
#     3-column gridspec: left narrow col = SR label/space,
#     mid + right cols = two SR columns
# ─────────────────────────────────────────────────────────────────────────────
def make_figure_s1(srs_list: list[dict], outpath: Path) -> None:
    n        = len(srs_list)
    NCOLS    = 2
    NROWS_SR = (n + NCOLS - 1) // NCOLS  # 5

    plt.rcParams.update({
        "font.size":       9,
        "axes.labelsize":  10,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.fontsize": 8,
    })

    # Each SR = 2 gridspec rows; no legend row in combined figure
    height_ratios = []
    for _ in range(NROWS_SR):
        height_ratios += [3.0, 2.0]

    # Use 3 cols: [narrow_spacer, plot_col_A, plot_col_B]
    # narrow_spacer gives room for y-tick labels on left edge
    fig = plt.figure(figsize=(28, NROWS_SR * 5.5), constrained_layout=True)
    gs  = GridSpec(
        len(height_ratios), NCOLS,
        figure=fig,
        height_ratios=height_ratios,
        hspace=0.08, wspace=0.35,
    )

    for idx, info in enumerate(srs_list):
        col    = idx % NCOLS
        sr_row = idx // NCOLS
        row_u  = sr_row * 2
        row_l  = sr_row * 2 + 1

        ax_top    = fig.add_subplot(gs[row_u, col])
        ax_bottom = fig.add_subplot(gs[row_l, col], sharex=ax_top)

        draw_axes(ax_top, ax_bottom, info["rows"],
                  f"PMID {info['pmid']}  |  {info['domain_label']}",
                  show_legend_inline=False, fontsize_base=9)

    fig.savefig(outpath, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {outpath}")

# ─────────────────────────────────────────────────────────────────────────────
# 4.  Legend-only figure
#     Layout: 3 dedicated axes so legends never overwrite each other
#       Left (full height) : Action Types (23 items, ncol=2)
#       Upper right        : Concept Categories (7 items, ncol=1)
#       Lower right        : Background shading (3 items, ncol=1)
# ─────────────────────────────────────────────────────────────────────────────
def make_legend_only(outpath: Path) -> None:
    plt.rcParams.update({"font.size": 11, "legend.fontsize": 10.5})

    # Layout (figure width = 22 in):
    #   ax_act [0.01–0.65]: all 23 action types (ncol=2)
    #   ax_con [0.68–1.00]: concept categories (upper)
    #   ax_ph  [0.68–1.00]: phase shading (lower)
    fig = plt.figure(figsize=(22, 7.5))

    ax_act = fig.add_axes([0.01, 0.04, 0.64, 0.88])
    ax_con = fig.add_axes([0.68, 0.40, 0.30, 0.53])
    ax_ph  = fig.add_axes([0.68, 0.04, 0.30, 0.30])
    for ax in [ax_act, ax_con, ax_ph]:
        ax.axis("off")

    # ── Action Types (single legend, ncol=2) ─────────────────────────────────
    ax_act.legend(
        handles=make_action_handles(ALL_ACTION_TYPES),
        title=(f"Action Types (n={len(ALL_ACTION_TYPES)})  —  color = direction group  "
               "(blue=EXPAND  |  red=RESTRICT  |  green=RESTORE  |  gray=INITIAL)"),
        loc="upper left", bbox_to_anchor=(0.0, 1.0),
        frameon=True, fancybox=True,
        fontsize=10.5, title_fontsize=10.5,
        labelspacing=0.45, ncol=2,
        handlelength=1.3, handletextpad=0.6, columnspacing=1.2,
    )

    # ── Concept Categories ───────────────────────────────────────────────────
    ax_con.legend(
        handles=make_concept_handles(ALL_CONCEPT_CATS),
        title=(f"Concept Categories (n={len(ALL_CONCEPT_CATS)})"
               "   dot color = category"),
        loc="upper left", bbox_to_anchor=(0.0, 1.0),
        frameon=True, fancybox=True,
        fontsize=10.5, title_fontsize=10.5,
        labelspacing=0.50, ncol=1,
        handlelength=1.3, handletextpad=0.6,
    )

    # ── Phase shading ────────────────────────────────────────────────────────
    phase_patches = [
        mpatches.Patch(facecolor="#eaf2fb", edgecolor="#888888",
                       label="Blind phase"),
        mpatches.Patch(facecolor="#fff7cc", edgecolor="#888888",
                       label="Peeking phase"),
        mpatches.Patch(facecolor="#dff5df", edgecolor="#888888",
                       label="Pruning phase"),
    ]
    ax_ph.legend(
        handles=phase_patches,
        title="Background shading",
        loc="upper left", bbox_to_anchor=(0.0, 1.0),
        frameon=True, fancybox=True,
        fontsize=10.5, title_fontsize=10.5,
        labelspacing=0.50, ncol=1,
        handlelength=2.2, handletextpad=0.6,
    )

    fig.text(
        0.5, 0.97,
        "Legend for Figure S1  \u2014  unified across all 10 systematic review panels",
        ha="center", va="top", fontsize=12, fontweight="bold",
    )

    fig.savefig(outpath, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {outpath}")

# ─────────────────────────────────────────────────────────────────────────────
# Run
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    plt.rcParams.update({
        "font.size": 11, "axes.labelsize": 12,
        "xtick.labelsize": 11, "ytick.labelsize": 11, "legend.fontsize": 9,
    })

    make_figure2(fig2_sr, OUT / "figure2_hypothesis_accumulation_40357797.png")

    for info in remaining:
        make_individual(info, OUT / f"figureS1_panel_{info['pmid']}.png")

    make_figure_s1(remaining, OUT / "figureS1_hypothesis_accumulation_all10.png")

    make_legend_only(OUT / "figureS1_legend_only.png")

    print("\nDone.")
