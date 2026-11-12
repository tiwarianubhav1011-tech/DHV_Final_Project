#!/usr/bin/env python3
"""
Main Entry Point — NIRF 2017-2025 Data Cleaning & Unification Pipeline
======================================================================
Runs the complete end-to-end pipeline by connecting all modular Python files:
  1. Stage 1 (`clean_nirf.py` + `clean_ranks_scores.py`, `clean_locations_categories.py`, `clean_names_ids.py`)
     -> Reads `nirf_2017_2025_raw.csv` and produces `nirf_2017_2025_cleaned.csv` & `cleaning_log.txt`
  2. Stage 2 (`unify_institutes.py` + `normalizer.py`, `unify_matcher.py`)
     -> Reads `nirf_2017_2025_cleaned.csv` and produces `nirf_2017_2025_unified.csv`,
        `institute_id_mapping.csv`, & `matching_log.txt`
"""

from clean_nirf import run_cleaning
from unify_institutes import run_unification


def main() -> None:
    print("=" * 75)
    print("🚀 STAGE 1: NIRF 2017-2025 DATA CLEANING")
    print("=" * 75)
    cleaned_df = run_cleaning()

    print("\n" + "=" * 75)
    print("🔗 STAGE 2: CROSS-YEAR INSTITUTE UNIFICATION (2017-2025)")
    print("=" * 75)
    unified_df, mapping_df = run_unification()

    print("\n" + "=" * 75)
    print("🎉 PIPELINE COMPLETED SUCCESSFULLY!")
    print(f"   • Total rows processed : {len(unified_df):,}")
    print(f"   • Unified institutions : {len(mapping_df):,}")
    print("=" * 75)


if __name__ == "__main__":
    main()

