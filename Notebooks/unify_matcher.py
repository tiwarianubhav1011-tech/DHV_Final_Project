#!/usr/bin/env python3
"""
Core matching algorithms for NIRF Institute Unification (Steps A, B, C, D).
"""

from typing import Callable
import pandas as pd

from config import (
    MANUAL_2017,
    MANUAL_POST,
    REJECT_PAIRS,
    DO_NOT_MERGE_POST,
)
from normalizer import norm_city, strip_city, sim


def merge_post_2017_duplicates(
    ids_post: set[str],
    latest: pd.DataFrame,
    variants: pd.Series,
    cities: pd.Series,
    footprint: pd.Series,
    log: Callable[[str], None],
) -> tuple[dict[str, str], dict[str, set], dict[str, set], dict[str, set], dict[str, str]]:
    """
    Step A: Merge duplicate IDs within 2018-2025 (same normalized name + city,
    never co-occurring in the same Year+Category).
    """
    log("\n── A. Merging duplicate IDs within 2018-2025 ──")
    parent = {b: b for b in ids_post}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(keep: str, drop: str) -> None:
        rk, rd = find(keep), find(drop)
        if rk != rd:
            parent[rd] = rk

    def overlap(a: str, b: str) -> bool:
        return bool(footprint[a] & footprint[b])

    for drop, keep in MANUAL_POST.items():
        union(keep, drop)
        log(f"  manual  {drop:<10} → {keep:<10} {latest.loc[drop, 'Name']}  →  {latest.loc[keep, 'Name']}")

    post_list = sorted(ids_post)
    for i, a in enumerate(post_list):
        for b in post_list[i + 1:]:
            if frozenset({a, b}) in DO_NOT_MERGE_POST or not (cities[a] & cities[b]):
                continue
            if not (variants[a] & variants[b]):
                continue
            if overlap(a, b):
                continue
            keep, drop = (a, b) if latest.loc[a, "Year"] >= latest.loc[b, "Year"] else (b, a)
            union(keep, drop)
            log(f"  auto    {drop:<10} → {keep:<10} {latest.loc[drop, 'Name']}  ({latest.loc[drop, 'City']})")

    post_canon = {b: find(b) for b in ids_post}
    canon_variants: dict[str, set] = {}
    canon_cities: dict[str, set] = {}
    canon_foot: dict[str, set] = {}
    canon_state: dict[str, str] = {}

    for b, c in post_canon.items():
        canon_variants.setdefault(c, set()).update(variants[b])
        canon_cities.setdefault(c, set()).update(cities[b])
        canon_foot.setdefault(c, set()).update(footprint[b])
        canon_state[c] = str(latest.loc[c, "State"])

    log(f"  2018+ IDs: {len(ids_post)} → {len(canon_variants)} institutes")
    return post_canon, canon_variants, canon_cities, canon_foot, canon_state


def match_2017_to_post(
    ids_2017: set[str],
    latest: pd.DataFrame,
    variants: pd.Series,
    footprint: pd.Series,
    post_canon: dict[str, str],
    canon_variants: dict[str, set],
    canon_cities: dict[str, set],
    canon_state: dict[str, str],
    log: Callable[[str], None],
) -> tuple[dict[str, tuple[str, str]], list[str]]:
    """
    Step B: Match 2017 Base_IDs to 2018+ canonical institutes using manual overrides
    and tiered similarity rules with greedy conflict-free assignment.
    """
    log("\n── B. Matching 2017 IDs to 2018+ institutes ──")

    canon_stripped = {
        c: {strip_city(v, nc, nc) for v in canon_variants[c] for nc in canon_cities[c]} | canon_variants[c]
        for c in canon_variants
    }

    name_state_count: dict[tuple[str, str], int] = {}
    for c, vs in canon_variants.items():
        for v in vs:
            k = (v, canon_state[c])
            name_state_count[k] = name_state_count.get(k, 0) + 1

    reject_resolved = {(a, post_canon.get(b, b)) for a, b in REJECT_PAIRS}

    candidates: list[tuple[float, str, str, str]] = []
    for b17 in ids_2017:
        r = latest.loc[b17]
        nc17 = norm_city(r["City"])
        st17 = str(r["State"])
        v17 = variants[b17]
        s17 = {strip_city(v, nc17, r["City"]) for v in v17} | v17

        for c in canon_variants:
            if (b17, c) in reject_resolved:
                continue
            same_city = nc17 in canon_cities[c]
            same_state = st17 == canon_state[c]
            if not (same_city or same_state):
                continue
            best, rule = 0.0, ""
            if v17 & canon_variants[c]:
                if same_city:
                    best, rule = 1.00, "exact name + city"
                elif same_state and all(name_state_count.get((v, st17), 0) == 1 for v in v17 & canon_variants[c]):
                    best, rule = 0.96, "exact name, unique in state"
            if best < 0.95 and same_city and (s17 & canon_stripped[c]):
                best, rule = 0.95, "name minus city + city"
            if best < 0.9:
                ratio = max(sim(a, b) for a in s17 for b in canon_stripped[c])
                if same_city and ratio >= 0.85:
                    best, rule = 0.80 + 0.1 * ratio, f"fuzzy {ratio:.2f} + city"
                elif same_state and ratio >= 0.94:
                    best, rule = 0.75 + 0.1 * ratio, f"fuzzy {ratio:.2f}, same state"
            if best:
                candidates.append((best, b17, c, rule))

    assigned: dict[str, tuple[str, str]] = {}
    covered: dict[str, set] = {}
    for b17, bpost in MANUAL_2017.items():
        if b17 in ids_2017 and bpost in post_canon:
            c = post_canon[bpost]
            assigned[b17] = (c, "manual")
            covered.setdefault(c, set()).update(footprint[b17])

    for score, b17, c, rule in sorted(candidates, key=lambda x: -x[0]):
        if b17 in assigned:
            continue
        if covered.get(c, set()) & footprint[b17]:
            continue
        assigned[b17] = (c, rule)
        covered.setdefault(c, set()).update(footprint[b17])

    unmatched = sorted(ids_2017 - set(assigned))
    by_rule: dict[str, int] = {}
    for _, (_, rule) in assigned.items():
        key = rule.split(" ")[0] if rule.startswith("fuzzy") else rule
        by_rule[key] = by_rule.get(key, 0) + 1
    log(f"  2017 IDs: {len(ids_2017)}  matched: {len(assigned)}  unmatched (dropped out after 2017): {len(unmatched)}")
    for k, v in sorted(by_rule.items(), key=lambda x: -x[1]):
        log(f"    {k:<30} {v}")

    return assigned, unmatched


def build_unified_columns(
    df: pd.DataFrame,
    post_canon: dict[str, str],
    assigned: dict[str, tuple[str, str]],
    unmatched: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Step C: Populate Unified_ID, Name_Unified, City_Unified, State_Unified,
    and disambiguated Name_Display on the DataFrame.
    """
    unified = dict(post_canon)
    for b17, (c, _) in assigned.items():
        unified[b17] = c
    for b17 in unmatched:
        unified[b17] = b17
    df["Unified_ID"] = df["Base_ID"].map(unified)

    lat = (
        df.sort_values("Year", ascending=False)
        .drop_duplicates("Unified_ID")
        .set_index("Unified_ID")
    )
    df["Name_Unified"] = df["Unified_ID"].map(lat["Name"])
    df["City_Unified"] = df["Unified_ID"].map(lat["City"])
    df["State_Unified"] = df["Unified_ID"].map(lat["State"])

    n_ids = df.groupby("Name_Unified")["Unified_ID"].transform("nunique")
    df["Name_Display"] = df["Name_Unified"]
    m = n_ids > 1
    df.loc[m, "Name_Display"] = df.loc[m, "Name_Unified"] + " (" + df.loc[m, "City_Unified"].fillna("?") + ")"

    n_ids2 = df.groupby("Name_Display")["Unified_ID"].transform("nunique")
    m2 = n_ids2 > 1
    df.loc[m2, "Name_Display"] = df.loc[m2, "Name_Display"] + " [" + df.loc[m2, "Unified_ID"] + "]"

    return df, lat


def validate_and_log_review(
    df: pd.DataFrame,
    latest: pd.DataFrame,
    lat: pd.DataFrame,
    assigned: dict[str, tuple[str, str]],
    unmatched: list[str],
    log: Callable[[str], None],
) -> None:
    """
    Step D: Validate uniqueness of Unified_ID per (Year, Category) and log
    non-exact matches and unmatched 2017 institutes for review.
    """
    log("\n── D. Validation ──")
    dup = df[df.duplicated(["Unified_ID", "Year", "Category"], keep=False)]
    log(
        f"  Same Unified_ID twice in one Year+Category: {len(dup)} rows "
        f"{'✅' if dup.empty else '❌'}"
    )
    if not dup.empty:
        log(dup[["Year", "Category", "Base_ID", "Unified_ID", "Name", "City"]].to_string())

    spans = df.groupby("Unified_ID")["Year"].agg(lambda y: 2017 in set(y) and max(y) > 2017).sum()
    log(f"  Base_IDs {df['Base_ID'].nunique()} → Unified_IDs {df['Unified_ID'].nunique()}")
    log(f"  Institutes tracked from 2017 into 2018+: {spans}")
    log(
        f"  Institutes with >1 raw name merged under one ID: "
        f"{(df.groupby('Unified_ID')['Name'].nunique() > 1).sum()}"
    )

    log("\n── Matches needing a glance (non-exact) ──")
    for b17, (c, rule) in sorted(assigned.items(), key=lambda x: x[1][1]):
        if rule.startswith("exact name + city"):
            continue
        log(
            f"  [{rule:<28}] {latest.loc[b17, 'Name'][:55]:<55} ({latest.loc[b17, 'City']})"
            f"  →  {lat.loc[c, 'Name'][:55]} ({lat.loc[c, 'City']})"
        )

    log(f"\n── 2017 institutes with no 2018+ appearance ({len(unmatched)}) ──")
    for b in unmatched:
        log(f"  {b:<16} {latest.loc[b, 'Name'][:65]:<65} {latest.loc[b, 'City']}, {latest.loc[b, 'State']}")

