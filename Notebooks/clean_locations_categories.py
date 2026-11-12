#!/usr/bin/env python3
"""
Location (State, City) and Category standardization steps (Steps 3, 4, 8 of Stage 1 cleaning).
"""

from typing import Callable
import pandas as pd
from config import STATE_MAP, CATEGORY_MAP, CITY_CLEAN_MAP


def standardize_states(df: pd.DataFrame, log: Callable[[str], None]) -> pd.DataFrame:
    """Step 3: Standardize State names."""
    log("\n── 3. Standardizing State names ──")

    for old, new in STATE_MAP.items():
        count = (df["State"] == old).sum()
        if count:
            log(f"  '{old}' → '{new}'  ({count} rows)")
            df["State"] = df["State"].replace(old, new)

    log(f"  Unique states after fix: {df['State'].nunique()}")
    return df


def standardize_categories(df: pd.DataFrame, log: Callable[[str], None]) -> pd.DataFrame:
    """Step 4: Standardize Category labels."""
    log("\n── 4. Standardizing Category labels ──")

    for old, new in CATEGORY_MAP.items():
        count = (df["Category"] == old).sum()
        if count:
            log(f"  '{old}' → '{new}'  ({count} rows)")
            df["Category"] = df["Category"].replace(old, new)

    log(f"  Categories: {sorted(df['Category'].unique())}")
    return df


def standardize_cities(df: pd.DataFrame, log: Callable[[str], None]) -> pd.DataFrame:
    """Step 8: Standardize City names and recover missing cities from institution names."""
    log("\n── 8. Standardizing City names ──")

    # 8a. Remove "Dist. " and "District " prefixes
    dist_mask = df["City"].str.contains(r"^Dist\.|^District ", na=False)
    log(f"  Cities with 'Dist.'/'District' prefix: {dist_mask.sum()}")
    df["City"] = df["City"].str.replace(r"^Dist\.\s*", "", regex=True)
    df["City"] = df["City"].str.replace(r"^District\s+", "", regex=True)

    # 8b. Old → new city name mappings
    for old, new in CITY_CLEAN_MAP.items():
        count = (df["City"] == old).sum()
        if count:
            log(f"  '{old}' → '{new}'  ({count} rows)")
            df.loc[df["City"] == old, "City"] = new

    # 8c. Strip whitespace
    df["City"] = df["City"].str.strip()

    # 8d. Recover city from the name when the source had a placeholder ("Select City")
    missing_city = df["City"].isna() & df["Name"].str.contains(r",\s*[A-Z][a-z]+$", na=False)
    df.loc[missing_city, "City"] = df.loc[missing_city, "Name"].str.extract(r",\s*([A-Z][a-z]+)$")[0]
    log(f"  Recovered {missing_city.sum()} missing city value(s) from the institute name")

    log(f"  Unique cities after cleanup: {df['City'].nunique()}")
    return df

