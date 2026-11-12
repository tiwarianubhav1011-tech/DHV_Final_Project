#!/usr/bin/env python3
"""
Rank and Score cleaning steps (Steps 0, 1, 2, 9, 10 of Stage 1 cleaning).
"""

from typing import Callable
import pandas as pd
from config import SCORE_COLS


def fix_embedded_line_breaks(df: pd.DataFrame, log: Callable[[str], None]) -> pd.DataFrame:
    """Step 0: Strip embedded CR/LF from Name column."""
    log("\n── 0. Fixing embedded line breaks in Name ──")
    df["Name"] = df["Name"].astype(str).str.replace(r"[\r\n]+", " ", regex=True)
    df["Name"] = df["Name"].str.strip()
    log("  Stripped embedded CR/LF from Name column.")
    return df


def clean_ranks(df: pd.DataFrame, log: Callable[[str], None]) -> pd.DataFrame:
    """Step 1: Strip alphanumeric rank suffixes, flag 'Rank Withdrawn', convert Rank to Int64."""
    log("\n── 1. Fixing non-numeric Rank values ──")

    rank_str = df["Rank"].astype(str)
    score_str = df["Score"].astype(str)
    withdrawn_mask = (
        rank_str.str.contains("Rank Withdrawn", case=False, na=False)
        | score_str.str.contains("Rank Withdrawn", case=False, na=False)
    )
    alpha_rank_mask = rank_str.str.match(r"^\d+[A-Za-z]+$", na=False)

    log(f"  Found {withdrawn_mask.sum()} 'Rank Withdrawn' rows:")
    for _, r in df[withdrawn_mask].iterrows():
        log(f"    {r['Year']} {r['Category']} — {r['Name']} (Rank={r['Rank']}, Score={r['Score']})")

    log(f"  Found {alpha_rank_mask.sum()} alpha-suffixed ranks:")
    for _, r in df[alpha_rank_mask].iterrows():
        log(f"    {r['Year']} {r['Category']} — {r['Name']} (Rank={r['Rank']})")

    df["Rank_Withdrawn"] = withdrawn_mask
    df["Rank"] = rank_str.str.replace(r"[A-Za-z*]+$", "", regex=True)
    df.loc[df["Rank_Withdrawn"], "Rank"] = pd.NA
    df["Rank"] = pd.to_numeric(df["Rank"], errors="coerce").astype("Int64")

    log("  Rank column converted to Int64. Withdrawn rows flagged in 'Rank_Withdrawn'.")
    return df


def clean_scores(df: pd.DataFrame, log: Callable[[str], None]) -> pd.DataFrame:
    """Step 2: Coerce score columns to numeric and flag rows where all scores are NaN."""
    log("\n── 2. Handling missing parameter scores ──")

    for col in SCORE_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    nan_scores_mask = df[SCORE_COLS].isna().all(axis=1)
    df["Scores_Missing"] = nan_scores_mask
    log(f"  {nan_scores_mask.sum()} rows have ALL score columns NaN.")
    cats_affected = df.loc[nan_scores_mask, "Category"].unique()
    log(f"  Affected categories: {list(cats_affected)}")
    return df


def flag_tied_ranks(df: pd.DataFrame, log: Callable[[str], None]) -> pd.DataFrame:
    """Step 9: Flag category-years with 101 rows (tie at Rank 100)."""
    log("\n── 9. Flagging tied-rank category-years ──")

    cat_year_counts = df.groupby(["Year", "Category"]).size()
    ties = cat_year_counts[cat_year_counts > 100]
    for (year, cat), cnt in ties.items():
        if cnt == 101:
            log(f"  {year} {cat}: 101 rows (tie at Rank 100)")

    df["Has_Rank_Tie"] = df.apply(
        lambda row: cat_year_counts.get((row["Year"], row["Category"]), 0) == 101,
        axis=1,
    )
    return df


def flag_band_comparability(df: pd.DataFrame, log: Callable[[str], None]) -> pd.DataFrame:
    """Step 10: Add cross-year comparability flags In_Top100 and In_Top50."""
    log("\n── 10. Adding cross-year comparability flag ──")

    df["In_Top100"] = (df["Rank"] <= 100).fillna(False).astype(bool)
    df["In_Top50"] = (df["Rank"] <= 50).fillna(False).astype(bool)

    log("  Added 'In_Top100' and 'In_Top50' boolean columns.")
    log("  Use these filters when comparing multi-year trends to avoid band-bias.")
    return df

