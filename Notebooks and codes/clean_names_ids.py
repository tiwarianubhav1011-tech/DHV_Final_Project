#!/usr/bin/env python3
"""
Institute ID extraction, Name cleaning, and Homonymous college disambiguation
steps (Steps 5, 6, 7 of Stage 1 cleaning).
"""

import re
from typing import Callable
import pandas as pd


def extract_base_id(raw_id: str) -> str:
    """
    Extract a stable base identifier from the varying NIRF ID formats.

    2017:  IR17-I-2-18243       → U-18243
           IR17-COLL-1-29115    → C-29115
           IR17-ENGG-2-18243    → U-18243  (same institute, diff category)
           IR17-PHRM-1-47655    → S-47655

    2018:  IR-1-O-O-U-0220      → U-0220
           IR-2-E-OE-U-0456     → U-0456
           IR-1-M-M-S-8890      → S-8890
           IR-1-C-C-C-29115     → C-29115

    2019+: IR-O-U-0456          → U-0456
           IR-E-U-0456          → U-0456
           IR-C-C-6355          → C-6355
           IR-M-S-8890          → S-8890
    """
    s = str(raw_id).strip()

    # 2017 format: IR17-{CAT}-{sub}-{num}
    m = re.match(r"^IR17-(?:I|COLL|ENGG|MGMT|PHRM)-(\d+)-(.+)$", s)
    if m:
        _, num = m.group(1), m.group(2)
        if "COLL" in s:
            return f"C-{num}"
        parts = num.split("-")
        return f"U-{parts[-1]}" if len(parts) > 1 else f"U-{num}"

    # 2018 format: IR-{n}-{cat}-{cats}-{type}-{num}
    m = re.match(r"^IR-\d+-\w+-\w+-([A-Z])-(.+)$", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    # 2019+ format: IR-{cat}-{type}-{num}
    m = re.match(r"^IR-[A-Z]-([A-Z])-(.+)$", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    return s


def extract_base_ids(df: pd.DataFrame, log: Callable[[str], None]) -> pd.DataFrame:
    """Step 5: Extract base Institute ID suffix."""
    log("\n── 5. Extracting base Institute ID suffix ──")

    df["Base_ID"] = df["Institute_ID"].apply(extract_base_id)

    n_raw = df["Institute_ID"].nunique()
    n_base = df["Base_ID"].nunique()
    log(f"  Raw unique Institute_IDs: {n_raw}")
    log(f"  Unique Base_IDs: {n_base}")
    log(f"  Reduction: {n_raw - n_base} duplicate IDs collapsed.")
    return df


def clean_institution_names(df: pd.DataFrame, log: Callable[[str], None]) -> pd.DataFrame:
    """Step 6: Clean institution names and map each Base_ID to its latest name."""
    log("\n── 6. Cleaning institution names ──")

    # 6a. Replace backticks with apostrophes
    backtick_mask = df["Name"].str.contains("`", na=False)
    log(f"  Names with backticks: {backtick_mask.sum()}")
    df["Name"] = df["Name"].str.replace(r"\\`", "'", regex=True)
    df["Name"] = df["Name"].str.replace("`", "'", regex=False)

    # 6b. Replace ? that should be apostrophes (encoding artifacts)
    df["Name"] = df["Name"].str.replace("â\x80\x99", "'", regex=False)
    df["Name"] = df["Name"].str.replace("’", "'", regex=False).str.replace("‘", "'", regex=False)
    question_apos = df["Name"].str.contains(r"\w\?\w", na=False)
    log(f"  Names with '?' likely apostrophe: {question_apos.sum()}")
    df["Name"] = df["Name"].str.replace(r"(\w)\?s\b", r"\1's", regex=True)

    # 6c. Collapse double/multiple spaces
    multi_space = df["Name"].str.contains(r"  +", na=False)
    log(f"  Names with multiple consecutive spaces: {multi_space.sum()}")
    df["Name"] = df["Name"].str.replace(r" {2,}", " ", regex=True)

    # 6d. Strip leading/trailing whitespace
    df["Name"] = df["Name"].str.strip()

    # 6e. Map every Base_ID to its latest (2025 or most recent) name
    log("  Mapping each institute to its latest name...")
    df_sorted = df.sort_values(["Base_ID", "Year"], ascending=[True, False])
    latest_names = df_sorted.drop_duplicates(subset="Base_ID", keep="first")[
        ["Base_ID", "Name"]
    ].rename(columns={"Name": "Name_Standardized"})

    df = df.merge(latest_names, on="Base_ID", how="left")

    changed = (df["Name"] != df["Name_Standardized"]).sum()
    log(f"  Name variations unified: {changed} rows updated to latest name.")
    return df


def disambiguate_homonymous_colleges(df: pd.DataFrame, log: Callable[[str], None]) -> pd.DataFrame:
    """Step 7: Append '(City)' to Name_Display for homonymous colleges."""
    log("\n── 7. Disambiguating homonymous colleges ──")

    name_city = df.groupby("Name_Standardized")["Base_ID"].nunique()
    homonymous = name_city[name_city > 1]
    log(f"  Names shared by multiple institutes: {len(homonymous)}")

    df["Name_Display"] = df["Name_Standardized"]
    homo_names = set(homonymous.index)
    mask = df["Name_Standardized"].isin(homo_names)
    df.loc[mask, "Name_Display"] = (
        df.loc[mask, "Name_Standardized"] + " (" + df.loc[mask, "City"] + ")"
    )
    log(f"  {mask.sum()} rows got '(City)' appended for disambiguation.")
    return df

