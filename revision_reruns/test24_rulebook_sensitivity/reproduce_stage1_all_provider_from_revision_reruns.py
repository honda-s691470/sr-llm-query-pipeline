from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

BASE = Path(__file__).resolve().parent
SRC = BASE / "metrics_and_reports" / "review_working_exports"
RAW_EXPORTS = BASE / "stage1_metrics" / "raw_eval_exports"
RUN1 = BASE / "stage1_metrics" / "run1_original_sources" / "all_test_metrics.csv"
STAGE2 = BASE / "stage2_cache_and_metrics" / "raw_stage_exports"
OUT = BASE / "repro_check"
FINAL = BASE / "metrics_and_reports" / "final_stage1_all_provider"


def normalize_provider(value):
    value = str(value).strip().lower()
    return {"claude": "Claude", "codex": "Codex", "gemini": "Gemini"}[value]


def build_run1():
    test24_ids = set(pd.read_csv(SRC / "test24_run1_cutsweep_ALL3PROVIDERS_reencoded_20260826.csv")["paper_id"].astype(str))
    df = pd.read_csv(RUN1)
    df = df[
        (df["condition"] == "with_laws_v14")
        & (df["provider"].str.lower().isin(["claude", "codex", "gemini"]))
        & (df["paper_folder"].astype(str).isin(test24_ids))
    ].copy()
    return pd.DataFrame({
        "provider": df["provider"].map(normalize_provider),
        "rulebook": "Run 1",
        "paper_id": df["paper_folder"].astype(str),
        "hits": df["total_hits"].astype(float),
        "tp": df["hit_gold_count"].astype(float),
        "gold_n": df["gold_count"].astype(float),
        "recall": df["recall"].astype(float),
        "source_file": str(RUN1.relative_to(BASE)) + ":with_laws_v14_stage1_raw",
    })


def from_query_eval_csv(path, rulebook):
    df = pd.read_csv(path)
    if "paper_folder" in df.columns:
        paper_id = df["paper_folder"]
        hits = df["total_hits"]
        tp = df["hit_gold_count"]
        gold_n = df["gold_count"]
        recall = df["recall"]
    else:
        paper_id = df["paper_id"]
        hits = df["raw_total_hits"] if "raw_total_hits" in df.columns else df["raw_hits"]
        tp = df["raw_tp"] if "raw_tp" in df.columns else (df["raw_recall"].astype(float) * df["gold_n"].astype(float)).round()
        gold_n = df["gold_n"]
        recall = df["raw_recall"]
    return pd.DataFrame({
        "provider": df["provider"].map(normalize_provider) if "provider" in df.columns else infer_provider(path),
        "rulebook": rulebook,
        "paper_id": paper_id.astype(str),
        "hits": hits.astype(float),
        "tp": tp.astype(float),
        "gold_n": gold_n.astype(float),
        "recall": recall.astype(float),
        "source_file": str(path.relative_to(BASE)),
    })


def infer_provider(path):
    s = str(path).lower()
    if "claude" in s:
        return "Claude"
    if "codex" in s:
        return "Codex"
    if "gemini" in s:
        return "Gemini"
    raise ValueError(path)


def from_claude_stage2_raw(path, rulebook):
    df = pd.read_csv(path).drop_duplicates(subset=["paper_id"], keep="first").copy()
    tp = (df["raw_recall"].astype(float) * df["gold_n"].astype(float)).round()
    return pd.DataFrame({
        "provider": "Claude",
        "rulebook": rulebook,
        "paper_id": df["paper_id"].astype(str),
        "hits": df["raw_hits"].astype(float),
        "tp": tp.astype(float),
        "gold_n": df["gold_n"].astype(float),
        "recall": df["raw_recall"].astype(float),
        "source_file": str(path.relative_to(BASE)),
    })


def build_data():
    frames = [
        build_run1(),
        from_claude_stage2_raw(SRC / "test24_stage2_cut70_rulebook_sensitivity_per_paper.csv", "Run 2"),
        from_query_eval_csv(SRC / "run2_stage2_cut70_phase5_completed_merged.csv", "Run 2"),
        from_query_eval_csv(STAGE2 / "gemini" / "test_prime_A_B_C_posthoc_recall_gemini_20260825_105143.csv", "Run 2"),
        from_claude_stage2_raw(SRC / "test24_stage2_cut70_rulebook_sensitivity_per_paper_run3.csv", "Run 3"),
        from_query_eval_csv(SRC / "run3_stage1_test24_codex_gpt-5_3.csv", "Run 3"),
        from_query_eval_csv(SRC / "test24_stage2_phase5_cut70_run3_rb_per_paper.csv", "Run 3"),
        from_claude_stage2_raw(SRC / "test24_stage2_cut70_rulebook_sensitivity_per_paper_pooled.csv", "Pooled"),
        from_query_eval_csv(SRC / "pooled_stage2_cut70_medcpt_cuda_phase5_completed_merged.csv", "Pooled"),
        from_query_eval_csv(SRC / "test24_stage1_pooled_rb_per_paper.csv", "Pooled"),
    ]
    df = pd.concat(frames, ignore_index=True)
    df["nnr"] = np.where(df["tp"] > 0, df["hits"] / df["tp"], np.nan)
    return df


def summarize(df):
    rows = []
    for provider in ["Claude", "Codex", "Gemini"]:
        for rulebook in ["Run 1", "Run 2", "Run 3", "Pooled"]:
            sub = df[(df.provider == provider) & (df.rulebook == rulebook)]
            rows.append({
                "provider": provider,
                "rulebook": rulebook,
                "n": int(sub["paper_id"].nunique()),
                "mean_recall": sub["recall"].mean(),
                "median_recall": sub["recall"].median(),
                "min_recall": sub["recall"].min(),
                "max_recall": sub["recall"].max(),
                "mean_hits": sub["hits"].mean(),
                "median_hits": sub["hits"].median(),
                "mean_nnr": sub["nnr"].mean(),
                "median_nnr": sub["nnr"].median(),
                "no_tp_n": int((sub["tp"] <= 0).sum()),
                "source_note": "; ".join(sorted(sub["source_file"].unique())),
            })
    return pd.DataFrame(rows)


def display_table(summary):
    piv = summary.pivot(index="rulebook", columns="provider", values="mean_recall").loc[["Run 1", "Run 2", "Run 3", "Pooled"], ["Claude", "Codex", "Gemini"]]
    def disp(idx, v):
        d = Decimal(str(v))
        if idx == "Run 1":
            return str(d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        d4 = d.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        return str(d4.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))
    fmt = pd.DataFrame(index=piv.index)
    for c in piv.columns:
        fmt[c] = [disp(idx, v) for idx, v in piv[c].items()]
    fmt.index = fmt.index.str.replace(" ", "")
    fmt.index.name = "Rulebook"
    return fmt


def plot(df):
    providers = ["Claude", "Codex", "Gemini"]
    rulebooks = ["Run 1", "Run 2", "Run 3", "Pooled"]
    colors = {"Claude": "#2E6FA3", "Codex": "#D97B2B", "Gemini": "#3A9E52"}
    shade = {"Run 1": 0.45, "Run 2": 0.65, "Run 3": 0.82, "Pooled": 1.0}
    groups = [(p, r) for p in providers for r in rulebooks]
    x = np.arange(len(groups))
    labels = [f"{p}\n{r}" for p, r in groups]
    plt.rcParams.update({"font.family": "Arial", "font.size": 10, "axes.labelsize": 11, "axes.spines.top": False, "axes.spines.right": False})
    fig, (ax_r, ax_n) = plt.subplots(1, 2, figsize=(16.5, 6.2))
    fig.subplots_adjust(left=0.06, right=0.98, top=0.90, bottom=0.25, wspace=0.24)
    rng = np.random.default_rng(42)
    def color_for(provider, rulebook):
        import matplotlib.colors as mcolors
        base = np.array(mcolors.to_rgb(colors[provider]))
        return tuple(1 - (1 - base) * shade[rulebook])
    def draw_panel(ax, metric, ylabel, letter, title, logy=False, ylim=None):
        data_list = [df[(df.provider == p) & (df.rulebook == r)][metric].dropna().values for p, r in groups]
        facecolors = [color_for(p, r) for p, r in groups]
        bp = ax.boxplot(data_list, positions=x, widths=0.58, patch_artist=True, medianprops=dict(color="black", linewidth=1.8), whiskerprops=dict(linewidth=1.1), capprops=dict(linewidth=1.1), flierprops=dict(marker="", linestyle="none"), showfliers=False)
        for patch, color, data in zip(bp["boxes"], facecolors, data_list):
            patch.set_facecolor(color if len(data) else "#FFFFFF")
            patch.set_alpha(0.70 if len(data) else 0.15)
            patch.set_edgecolor("white")
        for xi, (data, color) in enumerate(zip(data_list, facecolors)):
            if not len(data):
                ax.text(xi, 0.5 if not logy else 10, "NA", ha="center", va="center", fontsize=9, color="#666666")
                continue
            jitter = rng.uniform(-0.12, 0.12, size=len(data))
            ax.scatter(xi + jitter, data, s=25, color=color, edgecolors="white", linewidths=0.45, alpha=0.93, zorder=4)
            ax.scatter(xi, np.mean(data), marker="D", s=58, color="white", edgecolors="black", linewidths=1.1, zorder=5)
        for xpos in [3.5, 7.5]:
            ax.axvline(xpos, color="#B0B0B0", linewidth=0.8, linestyle=":")
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=8.5)
        ax.set_ylabel(ylabel)
        ax.set_title(f"{letter}  {title}", loc="left", fontweight="bold", fontsize=12)
        ax.yaxis.grid(True, linestyle="--", alpha=0.35, zorder=0)
        if ylim:
            ax.set_ylim(*ylim)
        if logy:
            ax.set_yscale("log")
    draw_panel(ax_r, "recall", "Recall", "A", "Stage 1 Recall", ylim=(0, 1.08))
    draw_panel(ax_n, "nnr", "NNR (log scale)", "B", "Stage 1 NNR", logy=True)
    fig.suptitle("Stage 1 performance across Run 1, Run 2, Run 3, and pooled rulebooks", fontsize=13, y=0.985)
    png = OUT / "stage1_recall_nnr_run1_run2_run3_pooled_all_providers_boxplot_REPRO.png"
    pdf = OUT / "stage1_recall_nnr_run1_run2_run3_pooled_all_providers_boxplot_REPRO.pdf"
    fig.savefig(png, dpi=300, bbox_inches="tight")
    fig.savefig(pdf, bbox_inches="tight")
    plt.close(fig)
    return png, pdf


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    df = build_data()
    summary = summarize(df)
    table = display_table(summary)
    df.to_csv(OUT / "stage1_all_provider_per_paper_REPRO.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(OUT / "stage1_all_provider_summary_REPRO.csv", index=False, encoding="utf-8-sig")
    (OUT / "stage1_recall_fed_to_stage2_table_display_REPRO.md").write_text("## Stage 1 (Query generation; recall of final query entered into Stage 2)\n\n" + table.to_markdown() + "\n", encoding="utf-8")
    table.reset_index().to_csv(OUT / "stage1_recall_fed_to_stage2_table_display_REPRO.csv", index=False, encoding="utf-8-sig")
    png, pdf = plot(df)

    original_summary = pd.read_csv(FINAL / "stage1_run1_run2_run3_pooled_all_providers_summary.csv")
    key = ["provider", "rulebook"]
    merged = summary.merge(original_summary, on=key, suffixes=("_repro", "_original"))
    checks = []
    for col in ["n", "mean_recall", "median_recall", "min_recall", "max_recall", "mean_hits", "median_hits", "mean_nnr", "median_nnr", "no_tp_n"]:
        a = pd.to_numeric(merged[f"{col}_repro"], errors="coerce")
        b = pd.to_numeric(merged[f"{col}_original"], errors="coerce")
        max_abs = float(np.nanmax(np.abs(a - b))) if len(a) else np.nan
        checks.append({"metric": col, "max_abs_diff": max_abs})
    check_df = pd.DataFrame(checks)
    check_df.to_csv(OUT / "reproduction_numeric_check.csv", index=False, encoding="utf-8-sig")
    print(table.to_markdown())
    print("\nNumeric check vs final_stage1_all_provider summary:")
    print(check_df.to_string(index=False))
    print("\nOutputs:")
    for p in [OUT / "stage1_all_provider_per_paper_REPRO.csv", OUT / "stage1_all_provider_summary_REPRO.csv", OUT / "stage1_recall_fed_to_stage2_table_display_REPRO.md", OUT / "stage1_recall_fed_to_stage2_table_display_REPRO.csv", png, pdf, OUT / "reproduction_numeric_check.csv"]:
        print(p)

if __name__ == "__main__":
    main()
