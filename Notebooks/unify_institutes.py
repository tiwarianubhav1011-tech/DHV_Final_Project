#!/usr/bin/env python3
"""
Stage 2: NIRF Institute Unification Orchestrator (v2)
=====================================================
Connects and executes the modular unification steps:
  - normalizer.py     (Name & City normalization and similarity helpers)
  - unify_matcher.py  (Steps A, B, C, D: 2018+ deduplication, 2017 matching,
                       unified column construction, and validation)
"""

import pandas as pd

from config import (
    CLEANED_CSV,
    UNIFIED_CSV,
    MAPPING_CSV,
    MATCHING_LOG,
    UNIFIED_COL_ORDER,
)
from normalizer import norm_city, norm_name
from unify_matcher import (
    merge_post_2017_duplicates,
    match_2017_to_post,
    build_unified_columns,
    validate_and_log_review,
)


def run_unification(
    input_path: str = CLEANED_CSV,
    output_path: str = UNIFIED_CSV,
    map_output_path: str = MAPPING_CSV,
    log_path: str = MATCHING_LOG,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run cross-year institute unification and save unified CSV, mapping table, and log."""
    log_lines: list[str] = []

    def log(msg: str = "") -> None:
        print(msg)
        log_lines.append(msg)

    df = pd.read_csv(input_path)
    log(f"Loaded {len(df)} rows, {df['Base_ID'].nunique()} Base_IDs")

    # Fill City from the latest non-null value of the same Base_ID
    df["City"] = df.groupby("Base_ID")["City"].transform(lambda s: s.ffill().bfill())

    df["_ncity"] = df["City"].map(norm_city)
    df["_nname"] = df["Name"].map(norm_name)

    # Per-Base_ID registry (latest row) + all name variants + Year/Category footprint
    latest = df.sort_values("Year", ascending=False).drop_duplicates("Base_ID").set_index("Base_ID")
    variants = df.groupby("Base_ID")["_nname"].apply(set)
    cities = df.groupby("Base_ID")["_ncity"].apply(set)
    footprint = df.groupby("Base_ID").apply(
        lambda g: set(zip(g["Year"], g["Category"])), include_groups=False
    )

    ids_post = set(df.loc[df["Year"] > 2017, "Base_ID"])
    ids_2017 = set(df.loc[df["Year"] == 2017, "Base_ID"]) - ids_post

    # Step A: Merge duplicate IDs within 2018-2025
    post_canon, canon_variants, canon_cities, _, canon_state = merge_post_2017_duplicates(
        ids_post, latest, variants, cities, footprint, log
    )

    # Step B: Match 2017 IDs to 2018+ canonical institutes
    assigned, unmatched = match_2017_to_post(
        ids_2017, latest, variants, footprint,
        post_canon, canon_variants, canon_cities, canon_state, log
    )

    # Step C: Build Unified_ID, Name_Unified, City_Unified, State_Unified, Name_Display
    df, lat = build_unified_columns(df, post_canon, assigned, unmatched)

    # Step D: Validate and log review summary
    validate_and_log_review(df, latest, lat, assigned, unmatched, log)

    # Format types and save outputs
    df["Rank"] = pd.to_numeric(df["Rank"], errors="coerce").astype("Int64")
    df["In_Top100"] = df["In_Top100"].fillna(False).astype(bool)
    df["In_Top50"] = df["In_Top50"].fillna(False).astype(bool)

    df[UNIFIED_COL_ORDER].to_csv(output_path, index=False)

    mapping = (
        df.groupby(["Unified_ID", "Name_Unified", "City_Unified", "State_Unified"], dropna=False)
        .agg(
            Years=("Year", lambda y: ",".join(map(str, sorted(set(y))))),
            Raw_IDs=("Institute_ID", lambda s: " | ".join(sorted(set(s)))),
            Raw_Names=("Name", lambda s: " | ".join(sorted(set(s)))),
        )
        .reset_index()
    )
    mapping.to_csv(map_output_path, index=False)

    log(f"\n✅ {output_path}")
    log(f"✅ {map_output_path}  (one row per institute: all raw IDs + raw names it absorbed)")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines))

    return df, mapping


if __name__ == "__main__":
    run_unification()
