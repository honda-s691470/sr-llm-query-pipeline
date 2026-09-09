from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Missing: {path}")
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    rows.sort(key=lambda r: int(r.get("iteration", 0)))
    return rows


def resolve_history_path(script_dir: Path, filename: str = "search_history.jsonl") -> Path:
    p1 = script_dir / filename
    if p1.exists():
        return p1
    p2 = Path.cwd() / filename
    if p2.exists():
        return p2
    raise FileNotFoundError(f"{filename} not found. Checked:\n - {p1}\n - {p2}")


def safe_str(value) -> str:
    return "" if value is None else str(value)


def compute_phase_spans(rows: list[dict]) -> list[tuple[int, int, str]]:
    if not rows:
        return []
    spans = []
    current_phase = safe_str(rows[0].get("phase", ""))
    start = int(rows[0].get("iteration", 1))
    for row in rows[1:]:
        it = int(row.get("iteration", 0))
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


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    try:
        jsonl_path = resolve_history_path(base_dir, "search_history.jsonl")
        rows = read_jsonl(jsonl_path)
    except FileNotFoundError:
        print("search_history.jsonl not found.")
        return

    if not rows:
        print("No data in search_history.jsonl")
        return

    iterations = [int(r["iteration"]) for r in rows]
    recalls = [float(r.get("recall", 0.0)) for r in rows]
    hits = [int(r.get("total_hits", 0)) for r in rows]
    spans = compute_phase_spans(rows)

    action_types = [safe_str(r.get("action_type", "UNKNOWN")) for r in rows]
    concepts = [safe_str(r.get("concept_category", "NONE")) for r in rows]
    uniq_actions = sorted(set(action_types))
    uniq_concepts = sorted(set(concepts))

    marker_cycle = ["o", "s", "^", "D", "X", "P", "v", "<", ">", "*", "h", "8"]
    action_to_marker = {a: marker_cycle[i % len(marker_cycle)] for i, a in enumerate(uniq_actions)}
    action_color = "dimgray"
    action_edge = "black"

    color_cycle = plt.rcParams["axes.prop_cycle"].by_key().get("color", [])
    if not color_cycle:
        color_cycle = ["C0", "C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9"]
    concept_to_color = {c: color_cycle[i % len(color_cycle)] for i, c in enumerate(uniq_concepts)}

    plt.rcParams.update(
        {
            "font.size": 11,
            "axes.labelsize": 12,
            "xtick.labelsize": 11,
            "ytick.labelsize": 11,
            "legend.fontsize": 9,
        }
    )

    fig = plt.figure(figsize=(16, 9), constrained_layout=True)
    gs = fig.add_gridspec(nrows=2, ncols=2, height_ratios=[3.0, 2.0], width_ratios=[4.0, 2.4], wspace=0.04)

    ax_top = fig.add_subplot(gs[0, 0])
    ax_bottom = fig.add_subplot(gs[1, 0], sharex=ax_top)
    ax_leg = fig.add_subplot(gs[1, 1])
    ax_leg.axis("off")

    for start, end, phase in spans:
        color, alpha = phase_bg(phase)
        ax_top.axvspan(start - 0.5, end + 0.5, color=color, alpha=alpha, zorder=0)
        ax_bottom.axvspan(start - 0.5, end + 0.5, color=color, alpha=alpha, zorder=0)
        ax_top.text((start + end) / 2, 1.01, phase, ha="center", va="bottom", transform=ax_top.get_xaxis_transform(), fontsize=12, fontweight="bold")

    ax_top.set_ylabel("Recall")
    ax_top.plot(iterations, recalls, marker="o", linewidth=2.5, label="Recall", color="tab:blue")
    ax_top.set_ylim(0, 1.05)
    ax_top.grid(True, axis="y", linestyle="--", alpha=0.25)
    ax_top.axhline(1.0, linestyle="--", linewidth=1, color="black")

    ax_hits = ax_top.twinx()
    ax_hits.set_ylabel("Total Hits")
    ax_hits.plot(iterations, hits, marker="s", linestyle="--", linewidth=2.2, label="Total Hits", color="tab:orange")

    h1, l1 = ax_top.get_legend_handles_labels()
    h2, l2 = ax_hits.get_legend_handles_labels()
    ax_top.legend(h1 + h2, l1 + l2, loc="lower right")

    ax_bottom.set_xlabel("Iteration")
    ax_bottom.set_ylabel("Change Event")
    ax_bottom.set_yticks([])
    ax_bottom.set_ylim(0, 1)
    ax_bottom.set_xticks(iterations)

    y_action = 0.72
    y_concept = 0.30
    for it in iterations:
        ax_bottom.plot([it, it], [0.45, 0.55], color="gray", linewidth=1.5, alpha=0.6)

    for row in rows:
        it = int(row["iteration"])
        action = safe_str(row.get("action_type", "UNKNOWN"))
        concept = safe_str(row.get("concept_category", "NONE"))

        ax_bottom.scatter(it, y_action, marker=action_to_marker[action], s=160, facecolors=action_color, edgecolors=action_edge, linewidth=1.5, zorder=3)
        ax_bottom.scatter(it, y_concept, marker="o", s=160, color=concept_to_color[concept], zorder=3)

    ax_bottom.text(0.01, y_action, "Action\n(Method)", transform=ax_bottom.transAxes, va="center", ha="left", fontweight="bold", fontsize=11, color="dimgray")
    ax_bottom.text(0.01, y_concept, "Concept\n(Topic)", transform=ax_bottom.transAxes, va="center", ha="left", fontweight="bold", fontsize=11)
    plt.setp(ax_top.get_xticklabels(), visible=False)

    action_handles = [
        Line2D([0], [0], marker=action_to_marker[action], color="w", markerfacecolor=action_color, markeredgecolor=action_edge, markeredgewidth=1.5, markersize=9, label=action)
        for action in uniq_actions
    ]
    concept_handles = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor=concept_to_color[concept], markersize=9, label=concept)
        for concept in uniq_concepts
    ]

    leg1 = ax_leg.legend(handles=action_handles, title=f"Action Types (n={len(uniq_actions)})", loc="upper left", bbox_to_anchor=(0.0, 1.0), frameon=True, fancybox=True, labelspacing=0.6, borderaxespad=0.5)
    ax_leg.add_artist(leg1)
    ax_leg.legend(handles=concept_handles, title=f"Concept Categories (n={len(uniq_concepts)})", loc="upper left", bbox_to_anchor=(0.55, 1.0), frameon=True, fancybox=True, labelspacing=0.6, borderaxespad=0.5)

    out_path = base_dir / "search_history_plot.png"
    fig.savefig(out_path, dpi=300)
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
