import numpy as np
import pandas as pd

from config import TOP_N

START_YEAR = 2017
END_YEAR = 2025
PARAMS = ["TLR", "RPC", "GO", "OI", "PR"]
BANDS = [(1, 10, "1-10"), (11, 50, "11-50"), (51, 100, "51-100")]
BAND_ORDER = ["1-10", "11-50", "51-100", ">100", "Not ranked"]


def _category(df, category):
    out = df[df["category"] == category]
    if out.empty:
        raise ValueError(f"No rows for '{category}'. Available: {sorted(df['category'].unique())}")
    return out


def available_years(df, category="Overall"):
    return sorted(_category(df, category)["year"].unique().tolist())


def _pairs(years):
    return list(zip(years[:-1], years[1:]))


def _titled(table, title, **extra):
    table.attrs.update(title=title, **extra)
    return table


def _year_slice(df, year, category, cols):
    d = _category(df, category)
    d = d[d["year"] == year]
    return d[["display_name", "state", *cols]].dropna()


def band_of(rank):
    if pd.isna(rank):
        return "Not ranked"
    for lo, hi, label in BANDS:
        if lo <= rank <= hi:
            return label
    return ">100"


def resolve_institution(d, name=None, year=END_YEAR):
    if name is None:
        ranked = d[d["year"] == year].dropna(subset=["rank"]).sort_values("rank")
        row = ranked.iloc[0]
        return row["institution_id"], row["display_name"]
    lowered = d["display_name"].str.lower()
    hits = d[lowered == name.lower()]
    if hits.empty:
        hits = d[lowered.str.contains(name.lower(), regex=False, na=False)]
    ids = hits["institution_id"].unique()
    if len(ids) == 0:
        raise ValueError(f"No institution matches '{name}'")
    if len(ids) > 1:
        names = hits.drop_duplicates("institution_id")["display_name"].tolist()[:5]
        raise ValueError(f"'{name}' matches several institutions: {names}")
    row = hits[hits["institution_id"] == ids[0]].iloc[0]
    return ids[0], row["display_name"]


# ---------- Section 1: time-series and trend analysis ----------

def q1_1(df, institution=None, category="Overall"):
    d = _category(df, category)
    inst_id, name = resolve_institution(d, institution)
    t = (d[d["institution_id"] == inst_id][["year", "rank", "score"]]
         .set_index("year")
         .reindex(range(START_YEAR, END_YEAR + 1))
         .rename_axis("year")
         .reset_index())
    return _titled(t, f"Q1.1 · Rank of {name} over time, {START_YEAR}–{END_YEAR}", name=name)


def _rank_change(df, category="Overall"):
    d = _category(df, category)
    a = d[(d["year"] == START_YEAR) & d["rank"].notna()][["institution_id", "display_name", "rank"]]
    b = d[(d["year"] == END_YEAR) & d["rank"].notna()][["institution_id", "rank"]]
    m = (a.rename(columns={"rank": "rank_start"})
         .merge(b.rename(columns={"rank": "rank_end"}), on="institution_id"))
    m["improvement"] = m["rank_start"] - m["rank_end"]
    return m


def q1_2(df, n=15, category="Overall"):
    t = _rank_change(df, category).nlargest(n, "improvement")
    return _titled(t, f"Q1.2 · Greatest rank improvements, {START_YEAR}–{END_YEAR}")


def q1_3(df, n=15, category="Overall"):
    t = _rank_change(df, category).nsmallest(n, "improvement")
    return _titled(t, f"Q1.3 · Largest rank declines, {START_YEAR}–{END_YEAR}")


def _score_summary(df, category):
    d = _category(df, category).dropna(subset=["score"])
    return (d.groupby("year")["score"]
            .agg(mean="mean", median="median",
                 q1=lambda s: s.quantile(0.25), q3=lambda s: s.quantile(0.75),
                 minimum="min", maximum="max", n="size")
            .reset_index())


def q1_4(df, category="Overall"):
    return _titled(_score_summary(df, category), f"Q1.4 · Average score over time ({category})")


def q1_5(df, min_years=5, category="Overall"):
    d = _category(df, category)
    top = d[d["rank"] <= 10].copy()
    years_count = top.groupby("institution_id")["year"].nunique()
    keep = years_count[years_count >= min_years].index
    out = top[top["institution_id"].isin(keep)].copy()
    out["years_in_top10"] = out["institution_id"].map(years_count)
    out = out.sort_values(["years_in_top10", "display_name", "year"], ascending=[False, True, True])
    return _titled(out, f"Q1.5 · Institutions in the top 10 in at least {min_years} years")


# ---------- Section 2: geospatial and regional analysis ----------

def _top_counts(d, start, end, top_n):
    top = d[d["rank"] <= top_n]
    counts = top.groupby(["state", "year"]).size().unstack("year", fill_value=0)
    counts = counts.reindex(columns=[start, end], fill_value=0)
    counts.columns = ["start", "end"]
    return counts


def q2_1(df, year=END_YEAR, top_n=TOP_N, category="Overall"):
    d = _category(df, category)
    t = (d[(d["year"] == year) & (d["rank"] <= top_n)]
         .groupby("state").size().rename("institutions").reset_index()
         .sort_values("institutions", ascending=False))
    return _titled(t, f"Q2.1 · States with the most institutions in the top {top_n}, {year}")


def q2_2(df, start=START_YEAR, end=END_YEAR, top_n=TOP_N, category="Overall"):
    counts = _top_counts(_category(df, category), start, end, top_n)
    counts = counts[(counts["start"] > 0) | (counts["end"] > 0)].copy()
    counts["start_share_pct"] = 100 * counts["start"] / top_n
    counts["end_share_pct"] = 100 * counts["end"] / top_n
    t = counts.sort_values("end", ascending=False).reset_index()
    return _titled(t, f"Q2.2 · Geographic distribution of the top {top_n}, {start} vs {end}",
                   start=start, end=end)


def q2_3(df, start=START_YEAR, end=END_YEAR, top_n=TOP_N, category="Overall"):
    counts = _top_counts(_category(df, category), start, end, top_n)
    counts["change"] = counts["end"] - counts["start"]
    t = counts.sort_values(["change", "end"], ascending=False).reset_index()
    return _titled(t, f"Q2.3 · States that improved their top-{top_n} representation, {start}–{end}",
                   start=start, end=end)


def q2_4(df, states=("Karnataka", "Tamil Nadu"), top_n=TOP_N, category="Overall"):
    d = _category(df, category)
    d = d[d["state"].isin(states)]
    t = (d.groupby(["year", "state"])
         .agg(ranked=("institution_id", "nunique"),
              top_n_count=("rank", lambda r: int((r <= top_n).sum())),
              mean_rank=("rank", "mean"),
              median_rank=("rank", "median"),
              best_rank=("rank", "min"),
              median_score=("score", "median"))
         .reset_index())
    return _titled(t, f"Q2.4 · {states[0]} vs {states[1]} in the NIRF {category} ranking",
                   states=list(states))


def q2_5(df, start=START_YEAR, end=END_YEAR, category="Overall"):
    d = _category(df, category)
    first = d.groupby("institution_id")["year"].min().rename("first_year")
    d = d.join(first, on="institution_id")
    new = d[(d["year"] == end) & (d["first_year"] > start)]
    t = (new.groupby(["state", "first_year"]).size().rename("institutions").reset_index()
         .sort_values(["institutions", "state"], ascending=[False, True]))
    return _titled(t, f"Q2.5 · Newly appearing institutions by state, {start} to {end}",
                   start=start, end=end)


# ---------- Section 3: univariate analysis ----------

def q3_1(df, year=END_YEAR, category="Overall"):
    d = _category(df, category)
    t = d[d["year"] == year][["display_name", "state", "score"]].dropna()
    return _titled(t, f"Q3.1 · Score distribution, {category} {year}", year=year)


def q3_2(df, year=END_YEAR, category="Overall"):
    d = _category(df, category)
    t = d[d["year"] == year][["display_name", "state", "rank"]].dropna()
    return _titled(t, f"Q3.2 · Rank distribution, {category} {year}", year=year)


def q3_3(df, year=END_YEAR, category="Overall"):
    s = _category(df, category)
    s = s[s["year"] == year]["score"].dropna()
    t = pd.DataFrame({"statistic": ["institutions", "mean", "median", "minimum", "maximum"],
                      "value": [len(s), s.mean(), s.median(), s.min(), s.max()]})
    return _titled(t, f"Q3.3 · Score summary, {category} {year}", year=year)


def q3_4(df, year=END_YEAR, category="Overall"):
    d = _category(df, category)
    s = d[d["year"] == year][["display_name", "score"]].dropna().copy()
    edges = s["score"].quantile([0, 0.25, 0.5, 0.75, 1.0]).tolist()
    labels = ["Q1 (lowest)", "Q2", "Q3", "Q4 (highest)"]
    s["quartile"] = pd.cut(s["score"], bins=edges, labels=labels, include_lowest=True)
    t = s.groupby("quartile", observed=False).size().rename("institutions").reset_index()
    t["percent"] = 100 * t["institutions"] / t["institutions"].sum()
    t["score_range"] = [f"{edges[i]:.1f} – {edges[i + 1]:.1f}" for i in range(4)]
    return _titled(t, f"Q3.4 · Share of institutions in each score quartile, {category} {year}",
                   year=year)


def q3_5(df, year=END_YEAR, min_n=10):
    d = df[df["year"] == year].dropna(subset=["score"])
    counts = d.groupby("category").size()
    keep = counts[counts >= min_n].index
    t = d[d["category"].isin(keep)][["category", "display_name", "score"]]
    return _titled(t, f"Q3.5 · Score spread across NIRF categories, {year}", year=year)


# ---------- Section 4: bivariate analysis and correlation ----------

def _pair_result(d, x, y, title):
    return _titled(d, title, x=x, y=y,
                   pearson=float(d[x].corr(d[y])),
                   spearman=float(d[x].corr(d[y], method="spearman")))


def q4_1(df, year=END_YEAR, category="Overall"):
    d = _year_slice(df, year, category, ["RPC", "score"])
    return _pair_result(d, "RPC", "score", f"Q4.1 · Research (RPC) vs overall score, {year}")


def q4_2(df, year=END_YEAR, category="Overall"):
    d = _year_slice(df, year, category, ["PR", "score"])
    return _pair_result(d, "PR", "score", f"Q4.2 · Perception (PR) vs overall score, {year}")


def q4_3(df, year=END_YEAR, category="Overall"):
    d = _year_slice(df, year, category, [*PARAMS, "score"])
    rows = [{"parameter": p,
             "pearson": float(d[p].corr(d["score"])),
             "spearman": float(d[p].corr(d["score"], method="spearman"))}
            for p in PARAMS]
    t = pd.DataFrame(rows)
    t = t.reindex(t["pearson"].abs().sort_values(ascending=False).index).reset_index(drop=True)
    return _titled(t, f"Q4.3 · Correlation of each parameter with the overall score, {year}")


def q4_4(df, year=END_YEAR, category="Overall"):
    d = _year_slice(df, year, category, ["TLR", "RPC"])
    return _pair_result(d, "TLR", "RPC", f"Q4.4 · Teaching (TLR) vs research (RPC), {year}")


def q4_5(df, category="Overall"):
    d = _category(df, category)
    rows = []
    for y in available_years(df, category):
        s = d[d["year"] == y][["RPC", "score"]].dropna()
        rows.append({"year": y, "pearson": float(s["RPC"].corr(s["score"])), "n": len(s)})
    return _titled(pd.DataFrame(rows),
                   f"Q4.5 · Correlation of RPC with overall score, {START_YEAR}–{END_YEAR}")


# ---------- Section 5: multivariate analysis ----------

def q5_1(df, year=END_YEAR, n=5, category="Overall"):
    d = _category(df, category)
    d = d[d["year"] == year].dropna(subset=["rank", *PARAMS])
    t = d.nsmallest(n, "rank")[["display_name", "rank", *PARAMS]].reset_index(drop=True)
    return _titled(t, f"Q5.1 · Top {n} institutions across the five parameters, {year}")


def _quadrant(df, high, low, year, title, category="Overall"):
    d = _year_slice(df, year, category, [high, low])
    hi_thr = float(d[high].quantile(0.75))
    lo_thr = float(d[low].quantile(0.25))
    d = d.assign(flag=(d[high] >= hi_thr) & (d[low] <= lo_thr))
    return _titled(d, title, high=high, low=low, hi_thr=hi_thr, lo_thr=lo_thr)


def q5_2(df, year=END_YEAR, category="Overall"):
    return _quadrant(df, "RPC", "TLR", year,
                     f"Q5.2 · High research (RPC) but relatively low teaching (TLR), {year}", category)


def q5_3(df, year=END_YEAR, category="Overall"):
    return _quadrant(df, "TLR", "PR", year,
                     f"Q5.3 · High teaching (TLR) but relatively low perception (PR), {year}", category)


def q5_4(df, start=START_YEAR, end=END_YEAR, category="Overall"):
    d = _category(df, category)
    a = d[d["year"] == start].set_index("institution_id")[["display_name", "score", *PARAMS]]
    b = d[d["year"] == end].set_index("institution_id")[["score", *PARAMS]]
    m = a.join(b, lsuffix="_start", rsuffix="_end", how="inner").dropna()
    m["d_score"] = m["score_end"] - m["score_start"]
    declined = pd.DataFrame({p: m[f"{p}_end"] < m[f"{p}_start"] for p in PARAMS}, index=m.index)
    m["n_declined"] = declined.sum(axis=1)
    m["declined_params"] = declined.apply(lambda r: ", ".join(p for p in PARAMS if r[p]), axis=1)
    t = (m[(m["d_score"] > 0) & (m["n_declined"] > 0)]
         .sort_values("d_score", ascending=False)
         .reset_index())
    return _titled(t, f"Q5.4 · Overall score rose despite falling parameters, {start}–{end}",
                   start=start, end=end)


def q5_5(df, year=END_YEAR, n=15, category="Overall"):
    d = _category(df, category)
    d = d[d["year"] == year].dropna(subset=PARAMS).copy()
    d["strongest"] = d[PARAMS].max(axis=1)
    d["strongest_param"] = d[PARAMS].idxmax(axis=1)
    d["weakest"] = d[PARAMS].min(axis=1)
    d["weakest_param"] = d[PARAMS].idxmin(axis=1)
    d["spread"] = d["strongest"] - d["weakest"]
    t = d.nlargest(n, "spread")[["display_name", "rank", "strongest", "strongest_param",
                                 "weakest", "weakest_param", "spread"]]
    return _titled(t, f"Q5.5 · Largest gap between strongest and weakest parameter, {year}")


# ---------- Section 6: distribution and statistical comparison ----------

def q6_1(df, year=END_YEAR, category="Overall"):
    d = _category(df, category)
    d = d[d["year"] == year].dropna(subset=["score"]).copy()
    d["group"] = np.where(d["rank"] <= 10, "Top 10", "Remaining")
    return _titled(d[["display_name", "rank", "score", "group"]],
                   f"Q6.1 · Score distribution: top 10 vs remaining, {year}")


def q6_2(df, category="Overall"):
    d = _category(df, category).dropna(subset=["score"])
    t = (d.groupby("year")["score"]
         .agg(std="std", n="size",
              q1=lambda s: s.quantile(0.25), q3=lambda s: s.quantile(0.75))
         .reset_index())
    t["iqr"] = t["q3"] - t["q1"]
    return _titled(t, f"Q6.2 · Score dispersion by year ({category})")


def q6_3(df, year=END_YEAR, category="Overall"):
    d = _category(df, category)
    d = d[d["year"] == year][PARAMS].dropna()
    t = pd.DataFrame({"parameter": PARAMS, "mean": d.mean().values, "std": d.std().values})
    t["coefficient_of_variation"] = t["std"] / t["mean"]
    t = t.sort_values("coefficient_of_variation", ascending=False).reset_index(drop=True)
    return _titled(t, f"Q6.3 · Variability of each parameter across institutions, {year}")


def q6_4(df, category="Overall"):
    return _titled(_score_summary(df, category), f"Q6.4 · Median and IQR of scores over time ({category})")


def q6_5(df, year=END_YEAR, min_n=5, category="Overall"):
    d = _category(df, category)
    d = d[d["year"] == year].dropna(subset=["score"])
    counts = d.groupby("state").size()
    keep = counts[counts >= min_n].index
    d = d[d["state"].isin(keep)]
    order = d.groupby("state")["score"].median().sort_values(ascending=False).index.tolist()
    return _titled(d[["display_name", "state", "score"]],
                   f"Q6.5 · Score distribution across states, {year}", order=order)


# ---------- Section 7: ranking transitions and institutional mobility ----------

def q7_1(df, year_from=START_YEAR, year_to=END_YEAR, category="Overall"):
    d = _category(df, category)
    a = d[d["year"] == year_from][["institution_id", "rank"]].rename(columns={"rank": "rank_from"})
    b = d[d["year"] == year_to][["institution_id", "rank"]].rename(columns={"rank": "rank_to"})
    m = a.merge(b, on="institution_id", how="left")
    m["band_from"] = m["rank_from"].map(band_of)
    m["band_to"] = m["rank_to"].map(band_of)
    movers = m[m["rank_from"].between(51, 100) & (m["rank_to"] <= 50)]
    matrix = (pd.crosstab(m["band_from"], m["band_to"])
              .reindex(index=BAND_ORDER, columns=BAND_ORDER, fill_value=0))
    return _titled(matrix, f"Q7.1 · Ranking-band transitions {year_from} to {year_to}",
                   year_from=year_from, year_to=year_to, movers=int(len(movers)))


def q7_2(df, category="Overall", top_n=10):
    d = _category(df, category)
    names = d.drop_duplicates("institution_id").set_index("institution_id")["display_name"]
    rows = []
    periods = [f"{y0}→{y1}" for y0, y1 in _pairs(available_years(df, category))]
    for y0, y1 in _pairs(available_years(df, category)):
        before = set(d[(d["year"] == y0) & (d["rank"] <= top_n)]["institution_id"])
        after = set(d[(d["year"] == y1) & (d["rank"] <= top_n)]["institution_id"])
        period = f"{y0}→{y1}"
        rows += [{"period": period, "event": "Entered", "institution": names[i]}
                 for i in sorted(after - before)]
        rows += [{"period": period, "event": "Exited", "institution": names[i]}
                 for i in sorted(before - after)]
    t = pd.DataFrame(rows, columns=["period", "event", "institution"])
    return _titled(t, f"Q7.2 · Institutions entering or leaving the top {top_n} between consecutive years",
                   periods=periods)


def _consecutive_ranks(df, category="Overall"):
    d = _category(df, category)
    names = d.drop_duplicates("institution_id").set_index("institution_id")["display_name"]
    frames = []
    for y0, y1 in _pairs(available_years(df, category)):
        a = d[d["year"] == y0][["institution_id", "rank"]].rename(columns={"rank": "rank_from"})
        b = d[d["year"] == y1][["institution_id", "rank"]].rename(columns={"rank": "rank_to"})
        m = a.merge(b, on="institution_id").dropna(subset=["rank_from", "rank_to"]).copy()
        m["period"] = f"{y0}→{y1}"
        m["movement"] = m["rank_from"] - m["rank_to"]
        frames.append(m)
    out = pd.concat(frames, ignore_index=True)
    out["display_name"] = out["institution_id"].map(names)
    return out


def q7_3(df, category="Overall"):
    m = _consecutive_ranks(df, category)
    m["same_band"] = m["rank_from"].map(band_of) == m["rank_to"].map(band_of)
    t = (m.groupby("period", sort=False)
         .agg(comparable=("same_band", "size"),
              same_band_pct=("same_band", lambda s: 100 * s.mean()))
         .reset_index())
    return _titled(t, "Q7.3 · Share of institutions staying in the same rank band, consecutive years")


def q7_4(df, category="Overall", n=10):
    m = _consecutive_ranks(df, category)
    t = pd.concat([m.nlargest(n, "movement"), m.nsmallest(n, "movement")]).reset_index(drop=True)
    t["direction"] = np.where(t["movement"] > 0, "Up", "Down")
    return _titled(t, "Q7.4 · Largest upward and downward rank movements, consecutive years")


def q7_5(df, category="Overall"):
    m = _consecutive_ranks(df, category)
    t = (m.groupby("period", sort=False)
         .agg(moved_up=("movement", lambda s: int((s > 0).sum())),
              moved_down=("movement", lambda s: int((s < 0).sum())),
              same_rank=("movement", lambda s: int((s == 0).sum())))
         .reset_index())
    return _titled(t, "Q7.5 · Institutions moving up, down or keeping their rank each year")


# ---------- Section 8: outlier detection and performance gaps ----------

def q8_1(df, year=END_YEAR, category="Overall"):
    d = _year_slice(df, year, category, ["score", "RPC"]).copy()
    slope, intercept = np.polyfit(d["score"], d["RPC"], 1)
    d["expected_RPC"] = intercept + slope * d["score"]
    d["residual"] = d["RPC"] - d["expected_RPC"]
    d["z"] = d["residual"] / d["residual"].std(ddof=0)
    t = d.sort_values("z", ascending=False)
    return _titled(t, f"Q8.1 · Research unusually high relative to overall score, {year}",
                   slope=float(slope), intercept=float(intercept))


def q8_2(df, year=END_YEAR, category="Overall"):
    d = _year_slice(df, year, category, ["RPC", "TLR"]).copy()
    d["gap"] = d["RPC"] - d["TLR"]
    d["z"] = (d["gap"] - d["gap"].mean()) / d["gap"].std(ddof=0)
    t = d.sort_values("gap", ascending=False)
    return _titled(t, f"Q8.2 · Research substantially better than teaching, {year}")


def q8_3(df, category="Overall"):
    d = _category(df, category)
    frames = []
    for y0, y1 in _pairs(available_years(df, category)):
        a = (d[d["year"] == y0][["institution_id", "display_name", "score"]]
             .rename(columns={"score": "score_from"}))
        b = d[d["year"] == y1][["institution_id", "score"]].rename(columns={"score": "score_to"})
        m = a.merge(b, on="institution_id").dropna(subset=["score_from", "score_to"]).copy()
        m["period"] = f"{y0}→{y1}"
        m["change"] = m["score_to"] - m["score_from"]
        frames.append(m)
    t = pd.concat(frames, ignore_index=True)
    t["z"] = (t["change"] - t["change"].mean()) / t["change"].std(ddof=0)
    t = t.reindex(t["z"].abs().sort_values(ascending=False).index).head(15)
    return _titled(t, "Q8.3 · Unusually large year-to-year score changes")


def q8_4(df, year=END_YEAR, category="Overall", rank_cutoff=50, pct=0.75):
    d = _category(df, category)
    d = d[d["year"] == year].dropna(subset=[*PARAMS, "rank"]).copy()
    ranks_pct = d[PARAMS].rank(pct=True)
    d["best_percentile"] = ranks_pct.max(axis=1)
    d["strongest_param"] = ranks_pct.idxmax(axis=1)
    d["flag"] = (d["best_percentile"] >= pct) & (d["rank"] > rank_cutoff)
    t = (d.sort_values(["flag", "best_percentile"], ascending=[False, False])
         [["display_name", "rank", "strongest_param", "best_percentile", "flag", *PARAMS]])
    return _titled(t, f"Q8.4 · Strong parameter score but poor overall rank, {year}",
                   cutoff=rank_cutoff, pct=pct)


def q8_5(df, category="Overall", min_years=5, peer_width=10, min_peers=5):
    d = _category(df, category).dropna(subset=["rank"])
    g = (d.groupby(["institution_id", "display_name"])
         .agg(years=("year", "nunique"), mean_rank=("rank", "mean"), volatility=("rank", "std"))
         .reset_index())
    g = g[g["years"] >= min_years].copy()
    g["peer_group"] = (g["mean_rank"] // peer_width).astype(int)
    stats = g.groupby("peer_group")["volatility"].agg(peer_mean="mean", peer_std="std", peer_n="size")
    g = g.join(stats, on="peer_group")
    g["z"] = (g["volatility"] - g["peer_mean"]) / g["peer_std"]
    g.loc[g["peer_n"] < min_peers, "z"] = np.nan
    t = g.sort_values("z", ascending=False)
    return _titled(t, "Q8.5 · Ranking volatility compared with institutions of similar standing",
                   peer_width=peer_width)


ANALYSES = {
    "1.1": q1_1, "1.2": q1_2, "1.3": q1_3, "1.4": q1_4, "1.5": q1_5,
    "2.1": q2_1, "2.2": q2_2, "2.3": q2_3, "2.4": q2_4, "2.5": q2_5,
    "3.1": q3_1, "3.2": q3_2, "3.3": q3_3, "3.4": q3_4, "3.5": q3_5,
    "4.1": q4_1, "4.2": q4_2, "4.3": q4_3, "4.4": q4_4, "4.5": q4_5,
    "5.1": q5_1, "5.2": q5_2, "5.3": q5_3, "5.4": q5_4, "5.5": q5_5,
    "6.1": q6_1, "6.2": q6_2, "6.3": q6_3, "6.4": q6_4, "6.5": q6_5,
    "7.1": q7_1, "7.2": q7_2, "7.3": q7_3, "7.4": q7_4, "7.5": q7_5,
    "8.1": q8_1, "8.2": q8_2, "8.3": q8_3, "8.4": q8_4, "8.5": q8_5,
}