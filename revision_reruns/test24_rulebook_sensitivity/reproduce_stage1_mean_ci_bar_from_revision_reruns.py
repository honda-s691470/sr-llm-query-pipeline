from __future__ import annotations

from pathlib import Path

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent
FINAL = BASE / "metrics_and_reports" / "final_stage1_all_provider"
DATA = FINAL / "stage1_run1_run2_run3_pooled_all_providers_per_paper.csv"
OUT = BASE / "repro_check_mean_ci_bar"

PROVIDERS = ["Claude", "Codex", "Gemini"]
RULEBOOKS = ["Run 1", "Run 2", "Run 3", "Pooled"]
COLORS = {"Claude": "#2E6FA3", "Codex": "#D97B2B", "Gemini": "#3A9E52"}
SHADE = {"Run 1": 0.45, "Run 2": 0.65, "Run 3": 0.82, "Pooled": 1.0}
N_BOOT = 10_000
SEED = 42
JITTER = 0.12
BAR_WIDTH = 0.62


def color_for(provider: str, rulebook: str) -> tuple[float, float, float]:
    base = np.array(mcolors.to_rgb(COLORS[provider]))
    return tuple(1 - (1 - base) * SHADE[rulebook])


def bootstrap_ci(values: np.ndarray, rng: np.random.Generator) -> tuple[float, float, float]:
    vals = np.asarray(values, dtype=float)
    vals = vals[np.isfinite(vals)]
    if len(vals) == 0:
        return np.nan, np.nan, np.nan
    boots = rng.choice(vals, size=(N_BOOT, len(vals)), replace=True).mean(axis=1)
    return float(vals.mean()), float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))


def load_data() -> pd.DataFrame:
    df = pd.read_csv(DATA)
    df["provider"] = df["provider"].astype(str)
    df["rulebook"] = df["rulebook"].astype(str)
    df["recall"] = pd.to_numeric(df["recall"], errors="coerce")
    df["nnr"] = pd.to_numeric(df["nnr"], errors="coerce")
    df["hits"] = pd.to_numeric(df["hits"], errors="coerce")
    df["tp"] = pd.to_numeric(df["tp"], errors="coerce")
    return df


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for metric in ["recall", "nnr"]:
        rng = np.random.default_rng(SEED)
        for provider in PROVIDERS:
            for rulebook in RULEBOOKS:
                sub = df[(df["provider"] == provider) & (df["rulebook"] == rulebook)]
                vals = sub[metric].replace([np.inf, -np.inf], np.nan).dropna().to_numpy(dtype=float)
                mean, lo, hi = bootstrap_ci(vals, rng)
                rows.append({
                    "metric": metric,
                    "provider": provider,
                    "rulebook": rulebook,
                    "n": int(len(vals)),
                    "mean": mean,
                    "ci95_low": lo,
                    "ci95_high": hi,
                    "median": float(np.nanmedian(vals)) if len(vals) else np.nan,
                    "min": float(np.nanmin(vals)) if len(vals) else np.nan,
                    "max": float(np.nanmax(vals)) if len(vals) else np.nan,
                })
    return pd.DataFrame(rows)


def plot(df: pd.DataFrame, summary: pd.DataFrame) -> tuple[Path, Path]:
    groups = [(p, r) for p in PROVIDERS for r in RULEBOOKS]
    labels = [f"{p}\n{r}" for p, r in groups]
    x = np.arange(len(groups))
    colors = [color_for(p, r) for p, r in groups]

    plt.rcParams.update({
        "font.family": "Arial",
        "font.size": 10,
        "axes.labelsize": 11,
        "axes.spines.top": False,
        "axes.spines.right": False,
    })
    fig, (ax_r, ax_n) = plt.subplots(1, 2, figsize=(16.5, 6.2))
    fig.subplots_adjust(left=0.06, right=0.98, top=0.88, bottom=0.25, wspace=0.25)

    dot_rng = np.random.default_rng(SEED + 1)

    def draw_panel(ax, metric: str, ylabel: str, letter: str, title: str, logy: bool = False, ylim=None):
        s = summary[summary["metric"] == metric].set_index(["provider", "rulebook"])
        means = np.array([s.loc[(p, r), "mean"] for p, r in groups], dtype=float)
        lows = np.array([s.loc[(p, r), "ci95_low"] for p, r in groups], dtype=float)
        highs = np.array([s.loc[(p, r), "ci95_high"] for p, r in groups], dtype=float)
        yerr = np.vstack([means - lows, highs - means])

        ax.bar(x, means, width=BAR_WIDTH, color=colors, alpha=0.78, edgecolor="white", linewidth=0.8, zorder=3)
        ax.errorbar(x, means, yerr=yerr, fmt="none", color="#222222", capsize=4.8, capthick=1.3, linewidth=1.3, zorder=4)

        for xi, (provider, rulebook), color in zip(x, groups, colors):
            vals = df[(df["provider"] == provider) & (df["rulebook"] == rulebook)][metric]
            vals = vals.replace([np.inf, -np.inf], np.nan).dropna().to_numpy(dtype=float)
            jitter = dot_rng.uniform(-JITTER, JITTER, size=len(vals))
            ax.scatter(xi + jitter, vals, s=26, color=color, edgecolors="black", linewidths=0.55, alpha=0.88, zorder=5)

        for xpos in [3.5, 7.5]:
            ax.axvline(xpos, color="#B0B0B0", linewidth=0.8, linestyle=":")
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=8.8)
        ax.set_ylabel(ylabel)
        ax.set_title(f"{letter}  {title}", loc="left", fontweight="bold", fontsize=12)
        ax.yaxis.grid(True, linestyle="--", alpha=0.35, zorder=0)
        if ylim:
            ax.set_ylim(*ylim)
        if logy:
            ax.set_yscale("log")

    draw_panel(ax_r, "recall", "Recall", "A", "Stage 1 Recall", ylim=(0, 1.08))
    draw_panel(ax_n, "nnr", "NNR (log scale)", "B", "Stage 1 NNR", logy=True)
    ax_n.text(
        0.99, 0.02,
        "NNR = raw Stage 1 hits / true-positive hits\nbefore Stage 2 candidate reduction",
        transform=ax_n.transAxes,
        ha="right", va="bottom", fontsize=8, color="#555555", style="italic",
    )
    fig.suptitle("Stage 1 performance across Run 1, Run 2, Run 3, and pooled rulebooks", fontsize=13, y=0.975)
    fig.text(
        0.5, 0.045,
        "Bars show group mean; error bars, 95% bootstrap confidence interval (10,000 resamples; SR as the resampling unit). Dots show individual SRs.",
        ha="center", va="center", fontsize=9.5, color="#333333",
    )

    png = OUT / "stage1_recall_nnr_run1_run2_run3_pooled_all_providers_mean_ci_bar_REPRO.png"
    pdf = OUT / "stage1_recall_nnr_run1_run2_run3_pooled_all_providers_mean_ci_bar_REPRO.pdf"
    fig.savefig(png, dpi=300, bbox_inches="tight")
    fig.savefig(pdf, bbox_inches="tight")
    plt.close(fig)
    return png, pdf


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    df = load_data()
    summary = summarize(df)
    summary_path = OUT / "stage1_run1_run2_run3_pooled_all_providers_mean_ci_summary_REPRO.csv"
    summary.to_csv(summary_path, index=False, encoding="utf-8-sig")
    png, pdf = plot(df, summary)
    print(summary_path.relative_to(BASE))
    print(png.relative_to(BASE))
    print(pdf.relative_to(BASE))


if __name__ == "__main__":
    main()
