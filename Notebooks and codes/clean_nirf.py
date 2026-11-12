#!/usr/bin/env python3
"""
Stage 1: NIRF 2017-2025 Data Cleaning Orchestrator
==================================================
Connects and executes the modular cleaning steps:
  - clean_ranks_scores.py       (Steps 0, 1, 2, 9, 10)
  - clean_locations_categories.py (Steps 3, 4, 8)
  - clean_names_ids.py          (Steps 5, 6, 7)
"""

import pandas as pd

from config import (
    RAW_INPUT,
    CLEANED_CSV,
    CLEANING_LOG,
    CLEANED_COL_ORDER,
)
from clean_ranks_scores import (
    fix_embedded_line_breaks,
    clean_ranks,
    clean_scores,
    flag_tied_ranks,
    flag_band_comparability,
)
from clean_locations_categories import (
    standardize_states,
    standardize_categories,
    standardize_cities,
)
from clean_names_ids import (
    extract_base_ids,
    clean_institution_names,
    disambiguate_homonymous_colleges,
)


def run_cleaning(
    input_path: str = RAW_INPUT,
    output_path: str = CLEANED_CSV,
    log_path: str = CLEANING_LOG,
) -> pd.DataFrame:
    """Run all 10 data cleaning steps and save cleaned CSV and log."""
    log_lines: list[str] = []

    def log(msg: str = "") -> None:
        print(msg)
        log_lines.append(msg)

    log("Loading data...")
    df = pd.read_csv(input_path, encoding="utf-8-sig")
    log(f"  Loaded {len(df)} rows, {len(df.columns)} columns: {list(df.columns)}")
    initial_rows = len(df)

    # Execute modular cleaning steps in exact pipeline sequence
    df = fix_embedded_line_breaks(df, log)
    df = clean_ranks(df, log)
    df = clean_scores(df, log)
    df = standardize_states(df, log)
    df = standardize_categories(df, log)
    df = extract_base_ids(df, log)
    df = clean_institution_names(df, log)
    df = disambiguate_homonymous_colleges(df, log)
    df = standardize_cities(df, log)
    df = flag_tied_ranks(df, log)
    df = flag_band_comparability(df, log)

    # Reorder columns and save
    df = df[CLEANED_COL_ORDER]

    log("\n── SUMMARY ──")
    log(f"  Input rows:  {initial_rows}")
    log(f"  Output rows: {len(df)}")
    log(f"  Columns:     {list(df.columns)}")

    df.to_csv(output_path, index=False)
    log(f"\n  ✅ Cleaned CSV saved to: {output_path}")

    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines))
    log(f"  📝 Cleaning log saved to: {log_path}")

    return df


if __name__ == "__main__":
    run_cleaning()
