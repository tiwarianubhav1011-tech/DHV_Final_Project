import functools
import textwrap
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

BLUE = "#0072B2"
ORANGE = "#E69F00"
VERMILION = "#D55E00"
GREEN = "#009E73"
PURPLE = "#CC79A7"
SKY = "#56B4E9"
GREY = "#9a9a9a"
PALETTE = [BLUE, ORANGE, VERMILION, GREEN, PURPLE, SKY, "#F0E442", "#000000"]

PARAMS = ["TLR", "RPC", "GO", "OI", "PR"]
LABELS = {
    "score": "Overall score",
    "rank": "Overall rank",
    "TLR": "Teaching, learning & resources (TLR)",
    "RPC": "Research & professional practice (RPC)",
    "GO": "Graduation outcomes (GO)",
    "OI": "Outreach & inclusivity (OI)",
    "PR": "Perception (PR)",
}


def _save(fig, out_path):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {out_path}")


def _plot(func):
    @functools.wraps(func)
    def wrapper(result, out_path):
        if result.empty:
            print(f"Skipped {out_path}: no data")
            return None
        return func(result, out_path)
    return wrapper


def _title(result, fallback=""):
    return result.attrs.get("title", fallback)


def _cell(v, width=16):
    if isinstance(v, (float, np.floating)):
        return "" if pd.isna(v) else f"{v:.2f}"
    return "\n".join(textwrap.wrap(str(v), width)) or str(v)


def _hbar(data, label_col, value_col, out_path, xlabel, title, fmt="{:+.0f}"):
    data = data.iloc[::-1]
    colors = [BLUE if v > 0 else VERMILION if v < 0 else GREY for v in data[value_col]]
    fig, ax = plt.subplots(figsize=(10, max(4, 0.4 * len(data) + 1.5)))
    ax.barh(data[label_col].astype(str), data[value_col], color=colors)
    ax.axvline(0, color="black", lw=0.8)
    for i, v in enumerate(data[value_col]):
        ax.text(v, i, " " + fmt.format(v) if v >= 0 else fmt.format(v) + " ",
                va="center", ha="left" if v >= 0 else "right", fontsize=8)
    ax.set(xlabel=xlabel, title=title)
    ax.grid(axis="x", alpha=0.3)
    _save(fig, out_path)


def _numbered_scatter(base, flagged, x, y, xlabel, ylabel, title, out_path, table_cols, extra=None):
    fig, (ax, tax) = plt.subplots(1, 2, figsize=(15, 6.5), gridspec_kw={"width_ratios": [1.3, 1]})
    ax.scatter(base[x], base[y], s=24, color=GREY, alpha=0.6, edgecolor="white", lw=0.3)
    if extra is not None:
        extra(ax, base)
    flagged = flagged.reset_index(drop=True)
    ax.scatter(flagged[x], flagged[y], s=170, color=VERMILION, edgecolor="white", zorder=3)
    for i, r in flagged.iterrows():
        ax.text(r[x], r[y], str(i + 1), ha="center", va="center", color="white",
                fontsize=8, fontweight="bold", zorder=4)
    ax.set(xlabel=xlabel, ylabel=ylabel, title=title)
    ax.grid(alpha=0.3)
    tax.axis("off")
    body = [[str(i + 1)] + [_cell(r[c], 38 if c == "display_name" else 16) for c, _ in table_cols]
            for i, r in flagged.iterrows()]
    if body:
        keys = ["__no"] + [c for c, _ in table_cols]
        name_w = 0.40 if "display_name" in keys else 0.0
        rest = (1 - 0.07 - name_w) / max(1, len(keys) - 1 - (1 if name_w else 0))
        widths = [0.07 if k == "__no" else name_w if k == "display_name" else rest for k in keys]
        tbl = tax.table(cellText=body, colLabels=["No."] + [h for _, h in table_cols],
                        loc="center", cellLoc="left", colWidths=widths)
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(8)
        tbl.scale(1, 1.8)
    tax.set_title("Flagged institutions")
    _save(fig, out_path)


def _quadrant_extra(result):
    hi, lo = result.attrs["high"], result.attrs["low"]
    hi_thr, lo_thr = result.attrs["hi_thr"], result.attrs["lo_thr"]

    def draw(ax, base):
        xmin, xmax = base[lo].min() - 2, base[lo].max() + 2
        ymin, ymax = base[hi].min() - 2, base[hi].max() + 2
        ax.add_patch(plt.Rectangle((xmin, hi_thr), lo_thr - xmin, ymax - hi_thr,
                                   color=VERMILION, alpha=0.12, zorder=0))
        ax.axhline(hi_thr, ls="--", color="#555555", lw=1)
        ax.axvline(lo_thr, ls="--", color="#555555", lw=1)
        ax.set_xlim(xmin, xmax)
        ax.set_ylim(ymin, ymax)
    return draw


def _scatter_fit(result, out_path):
    x, y = result.attrs["x"], result.attrs["y"]
    fig, ax = plt.subplots(figsize=(9, 6.5))
    ax.scatter(result[x], result[y], s=26, alpha=0.7, color=BLUE, edgecolor="white", lw=0.4)
    slope, intercept = np.polyfit(result[x], result[y], 1)
    xs = np.linspace(result[x].min(), result[x].max(), 100)
    ax.plot(xs, intercept + slope * xs, color=VERMILION, lw=2, label="Linear trend")
    ax.set(xlabel=LABELS.get(x, x), ylabel=LABELS.get(y, y),
           title=f"{_title(result)}\nPearson r = {result.attrs['pearson']:.2f}    "
                 f"Spearman ρ = {result.attrs['spearman']:.2f}")
    ax.grid(alpha=0.3)
    ax.legend()
    _save(fig, out_path)


def _quadrant_plot(result, out_path):
    hi, lo = result.attrs["high"], result.attrs["low"]
    flagged = result[result["flag"]].sort_values(hi, ascending=False)
    table_cols = [("display_name", "Institution"), ("state", "State"), (hi, hi), (lo, lo)]
    _numbered_scatter(result, flagged, lo, hi, LABELS[lo], LABELS[hi], _title(result), out_path,
                      table_cols, extra=_quadrant_extra(result))


@_plot
def plot_1_1(result, out_path):
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.plot(result["year"], result["rank"], marker="o", color=BLUE, lw=2)
    for x, y in zip(result["year"], result["rank"]):
        if pd.notna(y):
            ax.annotate(f"{int(y)}", (x, y), textcoords="offset points", xytext=(0, 9),
                        ha="center", fontsize=9)
    ax.invert_yaxis()
    ax.set_xticks(result["year"])
    ax.set(xlabel="Year", ylabel="Overall rank (lower is better)", title=_title(result))
    ax.grid(alpha=0.3)
    _save(fig, out_path)


@_plot
def plot_1_2(result, out_path):
    _hbar(result, "display_name", "improvement", out_path,
          "Places gained (rank at start minus rank at end)", _title(result))


@_plot
def plot_1_3(result, out_path):
    _hbar(result, "display_name", "improvement", out_path,
          "Places lost (rank at start minus rank at end)", _title(result))


@_plot
def plot_1_4(result, out_path):
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.fill_between(result["year"], result["q1"], result["q3"], color=BLUE, alpha=0.15,
                    label="Interquartile range")
    ax.plot(result["year"], result["mean"], marker="o", color=BLUE, lw=2, label="Mean")
    ax.plot(result["year"], result["median"], marker="s", color=ORANGE, lw=2, label="Median")
    ax.set_xticks(result["year"])
    ax.set(xlabel="Year", ylabel="Overall score", title=_title(result))
    ax.legend()
    ax.grid(alpha=0.3)
    _save(fig, out_path)


@_plot
def plot_1_5(result, out_path):
    grid = result.pivot_table(index="display_name", columns="year", values="rank", aggfunc="first")
    order = result.drop_duplicates("display_name").set_index("display_name")["years_in_top10"]
    grid = grid.loc[order.sort_values(ascending=False, kind="stable").index]
    cmap = plt.get_cmap("Blues_r").copy()
    cmap.set_bad("#f2f2f2")
    data = np.ma.masked_invalid(grid.values.astype(float))
    fig, ax = plt.subplots(figsize=(max(8, 0.9 * grid.shape[1] + 4), max(4, 0.45 * grid.shape[0] + 2)))
    im = ax.imshow(data, cmap=cmap, vmin=1, vmax=10, aspect="auto")
    ax.set_xticks(range(grid.shape[1]), [str(c) for c in grid.columns])
    ax.set_yticks(range(grid.shape[0]), grid.index)
    for i in range(grid.shape[0]):
        for j in range(grid.shape[1]):
            v = grid.values[i, j]
            if pd.notna(v):
                ax.text(j, i, f"{int(v)}", ha="center", va="center", fontsize=8,
                        color="white" if v <= 5 else "black")
    ax.set(xlabel="Year", title=_title(result))
    fig.colorbar(im, ax=ax, label="Rank in that year (1 = best)")
    _save(fig, out_path)


@_plot
def plot_2_1(result, out_path):
    data = result.iloc[::-1]
    fig, ax = plt.subplots(figsize=(10, max(4, 0.35 * len(data) + 1.5)))
    ax.barh(data["state"], data["institutions"], color=BLUE)
    for i, v in enumerate(data["institutions"]):
        ax.text(v, i, f" {v}", va="center", fontsize=8)
    ax.set(xlabel="Institutions in the top 100", ylabel="State", title=_title(result))
    ax.grid(axis="x", alpha=0.3)
    _save(fig, out_path)


@_plot
def plot_2_2(result, out_path):
    data = result.iloc[::-1].reset_index(drop=True)
    y = np.arange(len(data))
    h = 0.38
    fig, ax = plt.subplots(figsize=(10, max(5, 0.45 * len(data) + 1.5)))
    ax.barh(y - h / 2, data["start"], h, color=GREY, label=str(result.attrs.get("start")))
    ax.barh(y + h / 2, data["end"], h, color=BLUE, label=str(result.attrs.get("end")))
    ax.set_yticks(y, data["state"])
    ax.set(xlabel="Institutions in the top 100", title=_title(result))
    ax.legend()
    ax.grid(axis="x", alpha=0.3)
    _save(fig, out_path)


@_plot
def plot_2_3(result, out_path):
    _hbar(result[result["change"] != 0], "state", "change", out_path,
          "Change in institutions in the top 100", _title(result))


@_plot
def plot_2_4(result, out_path):
    states = result.attrs.get("states", sorted(result["state"].unique()))
    years = sorted(result["year"].unique())
    x = np.arange(len(years))
    w = 0.38
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    for k, (state, color) in enumerate(zip(states, [BLUE, ORANGE])):
        t = result[result["state"] == state].set_index("year").reindex(years)
        ax1.bar(x + (k - 0.5) * w, t["top_n_count"], w, color=color, label=state)
        ax2.plot(years, t["mean_rank"], marker="o", color=color, lw=2, label=state)
    ax1.set_xticks(x, [str(y) for y in years], rotation=45)
    ax1.set(ylabel="Institutions in the top 100", title="Institutions in the top 100 per year")
    ax2.set_xticks(years, [str(y) for y in years], rotation=45)
    ax2.invert_yaxis()
    ax2.set(xlabel="Year", ylabel="Mean rank", title="Mean rank per year (lower is better)")
    for ax in (ax1, ax2):
        ax.legend()
        ax.grid(alpha=0.3)
    fig.suptitle(_title(result))
    _save(fig, out_path)


@_plot
def plot_2_5(result, out_path):
    pv = result.pivot_table(index="state", columns="first_year", values="institutions",
                            aggfunc="sum", fill_value=0)
    pv = pv.loc[pv.sum(axis=1).sort_values().index]
    fig, ax = plt.subplots(figsize=(10, max(4, 0.4 * len(pv) + 2)))
    left = np.zeros(len(pv))
    colors = plt.get_cmap("Blues")(np.linspace(0.35, 0.95, pv.shape[1]))
    for color, col in zip(colors, pv.columns):
        ax.barh(pv.index, pv[col], left=left, color=color, label=f"First ranked {int(col)}")
        left = left + pv[col].values
    ax.set(xlabel="Newly appearing institutions", title=_title(result))
    ax.legend()
    ax.grid(axis="x", alpha=0.3)
    _save(fig, out_path)


@_plot
def plot_3_1(result, out_path):
    s = result["score"]
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.hist(s, bins=25, color=BLUE, edgecolor="white", alpha=0.9)
    ax.axvline(s.mean(), color=VERMILION, ls="--", lw=2, label=f"Mean {s.mean():.1f}")
    ax.axvline(s.median(), color=ORANGE, ls=":", lw=2, label=f"Median {s.median():.1f}")
    ax.set(xlabel="Overall score", ylabel="Number of institutions", title=_title(result))
    ax.legend()
    ax.grid(alpha=0.3)
    _save(fig, out_path)


@_plot
def plot_3_2(result, out_path):
    r = result["rank"]
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.hist(r, bins=np.arange(0, r.max() + 11, 10), color=BLUE, edgecolor="white")
    ax.set(xlabel="Overall rank (bins of 10)", ylabel="Number of institutions", title=_title(result))
    ax.grid(alpha=0.3)
    _save(fig, out_path)


@_plot
def plot_3_3(result, out_path):
    fig, ax = plt.subplots(figsize=(7, 3.2))
    ax.axis("off")
    rows = [[r.statistic, f"{r.value:,.0f}" if r.statistic == "institutions" else f"{r.value:.2f}"]
            for r in result.itertuples()]
    tbl = ax.table(cellText=rows, colLabels=["Statistic", "Value"], loc="center", cellLoc="left")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(11)
    tbl.scale(1, 1.6)
    ax.set_title(_title(result))
    _save(fig, out_path)


@_plot
def plot_3_4(result, out_path):
    labels = result["quartile"].astype(str) + "\n" + result["score_range"]
    fig, ax = plt.subplots(figsize=(9, 5.5))
    bars = ax.bar(labels, result["percent"], color=[BLUE, GREEN, ORANGE, VERMILION])
    for b, p, n in zip(bars, result["percent"], result["institutions"]):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height(), f"{p:.1f}%\n({n})",
                ha="center", va="bottom", fontsize=9)
    ax.set_ylim(0, max(result["percent"]) * 1.25)
    ax.set(ylabel="Percent of institutions", title=_title(result))
    ax.grid(axis="y", alpha=0.3)
    _save(fig, out_path)


@_plot
def plot_3_5(result, out_path):
    order = result.groupby("category")["score"].median().sort_values().index.tolist()
    data = [result.loc[result["category"] == c, "score"] for c in order]
    fig, ax = plt.subplots(figsize=(max(9, 0.8 * len(order) + 3), 6))
    ax.boxplot(data, patch_artist=True, boxprops=dict(facecolor=SKY, alpha=0.6))
    ax.set_xticks(range(1, len(order) + 1), order, rotation=35, ha="right")
    ax.set(ylabel="Overall score", title=_title(result))
    ax.grid(axis="y", alpha=0.3)
    _save(fig, out_path)


@_plot
def plot_4_1(result, out_path):
    _scatter_fit(result, out_path)


@_plot
def plot_4_2(result, out_path):
    _scatter_fit(result, out_path)


@_plot
def plot_4_3(result, out_path):
    x = np.arange(len(result))
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.bar(x - 0.2, result["pearson"], 0.4, color=BLUE, label="Pearson r")
    ax.bar(x + 0.2, result["spearman"], 0.4, color=ORANGE, label="Spearman ρ")
    ax.set_xticks(x, [LABELS[p] for p in result["parameter"]], rotation=20, ha="right")
    ax.axhline(0, color="black", lw=0.8)
    ax.set(ylabel="Correlation with overall score", title=_title(result))
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    _save(fig, out_path)


@_plot
def plot_4_4(result, out_path):
    _scatter_fit(result, out_path)


@_plot
def plot_4_5(result, out_path):
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.plot(result["year"], result["pearson"], marker="o", color=BLUE, lw=2)
    for x, y, n in zip(result["year"], result["pearson"], result["n"]):
        ax.annotate(f"r={y:.2f}\n(n={n})", (x, y), textcoords="offset points", xytext=(0, 9),
                    ha="center", fontsize=8)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xticks(result["year"])
    ax.set(xlabel="Year", ylabel="Pearson r: RPC vs overall score", title=_title(result))
    ax.grid(alpha=0.3)
    _save(fig, out_path)


@_plot
def plot_5_1(result, out_path):
    angles = np.linspace(0, 2 * np.pi, len(PARAMS), endpoint=False).tolist()
    closed = angles + angles[:1]
    fig, ax = plt.subplots(figsize=(8.5, 7.5), subplot_kw={"polar": True})
    for color, (_, row) in zip(PALETTE, result.iterrows()):
        vals = [row[p] for p in PARAMS]
        vals += vals[:1]
        label = f"{int(row['rank'])}. {str(row['display_name'])[:45]}"
        ax.plot(closed, vals, color=color, lw=2, label=label)
        ax.fill(closed, vals, color=color, alpha=0.08)
    ax.set_xticks(angles, PARAMS)
    ax.set_ylim(0, 100)
    ax.set_title(_title(result), pad=20)
    ax.legend(loc="upper left", bbox_to_anchor=(1.05, 1.0), fontsize=8)
    _save(fig, out_path)


plot_5_2 = _plot(_quadrant_plot)
plot_5_3 = _plot(_quadrant_plot)


@_plot
def plot_5_4(result, out_path):
    labels = [f"{str(n)[:40]}  (fell: {p})" for n, p in zip(result["display_name"], result["declined_params"])]
    _hbar(result.assign(label=labels), "label", "d_score", out_path,
          "Change in overall score", _title(result), fmt="{:+.2f}")


@_plot
def plot_5_5(result, out_path):
    data = result.iloc[::-1].reset_index(drop=True)
    y = np.arange(len(data))
    fig, ax = plt.subplots(figsize=(10, max(5, 0.45 * len(data) + 1.5)))
    for i, r in data.iterrows():
        ax.plot([r["weakest"], r["strongest"]], [i, i], color=GREY, lw=2, zorder=1)
    ax.scatter(data["weakest"], y, color=VERMILION, zorder=2, label="Weakest parameter")
    ax.scatter(data["strongest"], y, color=BLUE, zorder=2, label="Strongest parameter")
    for i, r in data.iterrows():
        ax.text(r["strongest"] + 0.8, i, f"{r['strongest_param']} / {r['weakest_param']}",
                va="center", fontsize=8)
    ax.set_yticks(y, [str(n)[:45] for n in data["display_name"]])
    ax.set(xlabel="Parameter score", title=_title(result))
    ax.legend(loc="lower right")
    ax.grid(axis="x", alpha=0.3)
    _save(fig, out_path)


@_plot
def plot_6_1(result, out_path):
    groups = ["Top 10", "Remaining"]
    data = [result.loc[result["group"] == g, "score"] for g in groups]
    rng = np.random.default_rng(0)
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.boxplot(data, patch_artist=True, widths=0.5, boxprops=dict(facecolor=SKY, alpha=0.6))
    for i, vals in enumerate(data, start=1):
        jitter = rng.normal(0, 0.05, len(vals))
        ax.scatter(np.full(len(vals), i) + jitter, vals, s=12, color=GREY, alpha=0.7)
    ax.set_xticks([1, 2], [f"{g} (n={len(v)})" for g, v in zip(groups, data)])
    ax.set(ylabel="Overall score", title=_title(result))
    ax.grid(axis="y", alpha=0.3)
    _save(fig, out_path)


@_plot
def plot_6_2(result, out_path):
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.plot(result["year"], result["std"], marker="o", color=BLUE, lw=2, label="Standard deviation")
    ax.plot(result["year"], result["iqr"], marker="s", color=ORANGE, lw=2, label="Interquartile range")
    ax.set_xticks(result["year"])
    ax.set(xlabel="Year", ylabel="Spread of overall score", title=_title(result))
    ax.legend()
    ax.grid(alpha=0.3)
    _save(fig, out_path)


@_plot
def plot_6_3(result, out_path):
    fig, ax = plt.subplots(figsize=(9, 5.5))
    names = [LABELS[p] for p in result["parameter"]]
    ax.bar(names, result["coefficient_of_variation"], color=BLUE)
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right")
    ax.set(ylabel="Coefficient of variation (std / mean)", title=_title(result))
    ax.grid(axis="y", alpha=0.3)
    _save(fig, out_path)


@_plot
def plot_6_4(result, out_path):
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.fill_between(result["year"], result["q1"], result["q3"], color=BLUE, alpha=0.15,
                    label="Interquartile range")
    ax.plot(result["year"], result["median"], marker="o", color=BLUE, lw=2, label="Median")
    ax.set_xticks(result["year"])
    ax.set(xlabel="Year", ylabel="Overall score", title=_title(result))
    ax.legend()
    ax.grid(alpha=0.3)
    _save(fig, out_path)


@_plot
def plot_6_5(result, out_path):
    order = result.attrs.get("order", sorted(result["state"].unique()))
    data = [result.loc[result["state"] == s, "score"] for s in order]
    fig, ax = plt.subplots(figsize=(max(9, 0.7 * len(order) + 3), 6))
    ax.boxplot(data, patch_artist=True, boxprops=dict(facecolor=SKY, alpha=0.6))
    ax.set_xticks(range(1, len(order) + 1), order, rotation=40, ha="right")
    ax.set(ylabel="Overall score", title=_title(result))
    ax.grid(axis="y", alpha=0.3)
    _save(fig, out_path)


@_plot
def plot_7_1(result, out_path):
    fig, ax = plt.subplots(figsize=(8.5, 6.5))
    ax.imshow(result.values, cmap="Blues")
    ax.set_xticks(range(len(result.columns)), result.columns)
    ax.set_yticks(range(len(result.index)), result.index)
    for i in range(result.shape[0]):
        for j in range(result.shape[1]):
            ax.text(j, i, int(result.values[i, j]), ha="center", va="center", color="black")
    ax.add_patch(plt.Rectangle((-0.5, 1.5), 2, 1, fill=False, ec=VERMILION, lw=2.5))
    ax.set(xlabel=f"Band in {result.attrs['year_to']}", ylabel=f"Band in {result.attrs['year_from']}",
           title=f"{_title(result)}\nMoved from 51–100 into top 50: {result.attrs['movers']}")
    _save(fig, out_path)


@_plot
def plot_7_2(result, out_path):
    periods = result.attrs["periods"]
    entered = [int(((result["period"] == p) & (result["event"] == "Entered")).sum()) for p in periods]
    exited = [int(((result["period"] == p) & (result["event"] == "Exited")).sum()) for p in periods]
    fig, (ax, tax) = plt.subplots(1, 2, figsize=(15, max(5, 0.6 * len(periods) + 2)),
                                  gridspec_kw={"width_ratios": [1, 1.4]})
    y = np.arange(len(periods))
    h = 0.38
    ax.barh(y - h / 2, entered, h, color=BLUE, label="Entered top 10")
    ax.barh(y + h / 2, exited, h, color=VERMILION, label="Exited top 10")
    ax.set_yticks(y, periods)
    ax.invert_yaxis()
    ax.xaxis.set_major_locator(plt.MaxNLocator(integer=True))
    ax.set(xlabel="Institutions", title=_title(result))
    ax.legend(loc="lower right")
    ax.grid(axis="x", alpha=0.3)
    rows = []
    for p in periods:
        ins = result.loc[(result["period"] == p) & (result["event"] == "Entered"), "institution"]
        outs = result.loc[(result["period"] == p) & (result["event"] == "Exited"), "institution"]
        rows.append([p,
                     "\n".join(textwrap.wrap("; ".join(ins) or "-", 60)),
                     "\n".join(textwrap.wrap("; ".join(outs) or "-", 60))])
    tax.axis("off")
    tbl = tax.table(cellText=rows, colLabels=["Period", "Entered top 10", "Exited top 10"],
                    loc="center", cellLoc="left", colWidths=[0.12, 0.44, 0.44])
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(7)
    tbl.scale(1, 1.5)
    _save(fig, out_path)


@_plot
def plot_7_3(result, out_path):
    x = np.arange(len(result))
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.plot(x, result["same_band_pct"], marker="o", color=BLUE, lw=2)
    for xi, v in zip(x, result["same_band_pct"]):
        ax.annotate(f"{v:.0f}%", (xi, v), textcoords="offset points", xytext=(0, 8),
                    ha="center", fontsize=8)
    ax.set_xticks(x, result["period"], rotation=35, ha="right")
    ax.set_ylim(0, 100)
    ax.set(ylabel="% of institutions in the same band", title=_title(result))
    ax.grid(alpha=0.3)
    _save(fig, out_path)


@_plot
def plot_7_4(result, out_path):
    data = result.assign(label=result["display_name"].astype(str).str.slice(0, 40)
                         + "  (" + result["period"] + ")")
    _hbar(data, "label", "movement", out_path,
          "Rank places moved (positive = moved up)", _title(result))


@_plot
def plot_7_5(result, out_path):
    x = np.arange(len(result))
    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.bar(x, result["moved_up"], color=BLUE, label="Moved up")
    ax.bar(x, result["same_rank"], bottom=result["moved_up"], color=GREY, label="Same rank")
    ax.bar(x, result["moved_down"], bottom=result["moved_up"] + result["same_rank"],
           color=VERMILION, label="Moved down")
    ax.set_xticks(x, result["period"], rotation=35, ha="right")
    ax.set(ylabel="Institutions", title=_title(result))
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    _save(fig, out_path)


@_plot
def plot_8_1(result, out_path):
    slope, intercept = result.attrs["slope"], result.attrs["intercept"]

    def draw(ax, base):
        xs = np.linspace(base["score"].min(), base["score"].max(), 100)
        ax.plot(xs, intercept + slope * xs, color=BLUE, lw=2, label="Expected RPC from overall score")
        ax.legend()

    table_cols = [("display_name", "Institution"), ("score", "Score"), ("RPC", "RPC"),
                  ("expected_RPC", "Expected RPC"), ("z", "z-score")]
    _numbered_scatter(result, result.nlargest(10, "z"), "score", "RPC", "Overall score",
                      "RPC score", _title(result), out_path, table_cols, extra=draw)


@_plot
def plot_8_2(result, out_path):
    _hbar(result.head(15), "display_name", "gap", out_path,
          "RPC minus TLR (points)", _title(result), fmt="{:+.1f}")


@_plot
def plot_8_3(result, out_path):
    data = result.assign(label=result["display_name"].astype(str).str.slice(0, 40)
                         + " (" + result["period"] + ")")
    _hbar(data, "label", "change", out_path,
          "Change in overall score between consecutive years", _title(result), fmt="{:+.1f}")


@_plot
def plot_8_4(result, out_path):
    cutoff, pct = result.attrs["cutoff"], result.attrs["pct"]
    flagged = result[result["flag"]]

    def draw(ax, base):
        top = base["rank"].max() + 5
        ax.add_patch(plt.Rectangle((cutoff, pct), top - cutoff, 1 - pct,
                                   color=VERMILION, alpha=0.1, zorder=0))
        ax.axhline(pct, ls="--", color="#555555", lw=1)
        ax.axvline(cutoff, ls="--", color="#555555", lw=1)
        ax.set_xlim(0, top)
        ax.set_ylim(0, 1.02)

    table_cols = [("display_name", "Institution"), ("rank", "Overall rank"),
                  ("strongest_param", "Strongest parameter"), ("best_percentile", "Best percentile")]
    _numbered_scatter(result, flagged, "rank", "best_percentile", "Overall rank (lower is better)",
                      "Best parameter percentile", _title(result), out_path, table_cols, extra=draw)


@_plot
def plot_8_5(result, out_path):
    table_cols = [("display_name", "Institution"), ("mean_rank", "Mean rank"),
                  ("volatility", "Rank std. dev."), ("z", "z vs peers")]
    _numbered_scatter(result, result.nlargest(10, "z"), "mean_rank", "volatility",
                      "Mean overall rank", "Rank volatility (std. dev.)", _title(result),
                      out_path, table_cols)


PLOTTERS = {
    "1.1": plot_1_1, "1.2": plot_1_2, "1.3": plot_1_3, "1.4": plot_1_4, "1.5": plot_1_5,
    "2.1": plot_2_1, "2.2": plot_2_2, "2.3": plot_2_3, "2.4": plot_2_4, "2.5": plot_2_5,
    "3.1": plot_3_1, "3.2": plot_3_2, "3.3": plot_3_3, "3.4": plot_3_4, "3.5": plot_3_5,
    "4.1": plot_4_1, "4.2": plot_4_2, "4.3": plot_4_3, "4.4": plot_4_4, "4.5": plot_4_5,
    "5.1": plot_5_1, "5.2": plot_5_2, "5.3": plot_5_3, "5.4": plot_5_4, "5.5": plot_5_5,
    "6.1": plot_6_1, "6.2": plot_6_2, "6.3": plot_6_3, "6.4": plot_6_4, "6.5": plot_6_5,
    "7.1": plot_7_1, "7.2": plot_7_2, "7.3": plot_7_3, "7.4": plot_7_4, "7.5": plot_7_5,
    "8.1": plot_8_1, "8.2": plot_8_2, "8.3": plot_8_3, "8.4": plot_8_4, "8.5": plot_8_5,
}