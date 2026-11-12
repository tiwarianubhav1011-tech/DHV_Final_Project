"""
Database loader script to import NIRF unified CSV dataset into PostgreSQL public."NIRF" table.
Usage:
    python load_dataset.py --csv /path/to/nirf_2017_2025_unified.csv
"""

import argparse
import os
import sys
import pandas as pd
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

from nirf_chatbot.database import engine


def setup_nirf_table(csv_path: str):
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found at {csv_path}", file=sys.stderr)
        return False

    print(f"Reading CSV from {csv_path}...")
    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df)} rows from CSV.")

    # Map CSV columns to NIRF schema expected by chatbot
    column_mapping = {
        "Year": "Year",
        "Category": "Category",
        "Institute_ID": "Institution_ID",
        "Unified_ID": "Institution_ID",
        "Name_Display": "Institution_Name",
        "Name": "Institution_Name",
        "City_Unified": "City",
        "City": "City",
        "State_Unified": "State",
        "State": "State",
        "Score": "Score",
        "Rank": "Rank_Numeric",
    }

    # Standardize columns
    target_columns = [
        "Year", "Category", "Institution_ID", "Institution_Name",
        "City", "State", "Score", "Rank_Numeric"
    ]

    clean_df = pd.DataFrame()
    for col in target_columns:
        if col in df.columns:
            clean_df[col] = df[col]
        else:
            # Check mapped columns
            found = False
            for src_col, dest_col in column_mapping.items():
                if dest_col == col and src_col in df.columns:
                    clean_df[col] = df[src_col]
                    found = True
                    break
            if not found:
                clean_df[col] = None

    # Handle status & band
    clean_df["Band"] = df.get("Band", None)
    clean_df["Rank_Status"] = df.get("Rank_Status", "Ranked")
    clean_df["Score_Status"] = df.get("Score_Status", "Scored")

    # Clean numeric types
    clean_df["Year"] = pd.to_numeric(clean_df["Year"], errors="coerce").astype("Int64")
    clean_df["Score"] = pd.to_numeric(clean_df["Score"], errors="coerce")
    clean_df["Rank_Numeric"] = pd.to_numeric(clean_df["Rank_Numeric"], errors="coerce").astype("Int64")

    print("Connecting to PostgreSQL and creating public.\"NIRF\" table...")
    with engine.connect() as conn:
        with conn.begin():
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS public."NIRF" (
                    "Year" INTEGER,
                    "Category" VARCHAR(100),
                    "Institution_ID" VARCHAR(100),
                    "Institution_Name" TEXT,
                    "City" VARCHAR(150),
                    "State" VARCHAR(100),
                    "Score" NUMERIC(6, 2),
                    "Score_Status" VARCHAR(50),
                    "Rank_Numeric" INTEGER,
                    "Rank_Status" VARCHAR(50),
                    "Band" VARCHAR(50)
                );
                CREATE INDEX IF NOT EXISTS idx_nirf_year ON public."NIRF"("Year");
                CREATE INDEX IF NOT EXISTS idx_nirf_cat ON public."NIRF"("Category");
                CREATE INDEX IF NOT EXISTS idx_nirf_state ON public."NIRF"("State");
                CREATE INDEX IF NOT EXISTS idx_nirf_name ON public."NIRF"("Institution_Name");
            """))

    print("Uploading records to PostgreSQL...")
    clean_df.to_sql("NIRF", con=engine, schema="public", if_exists="append", index=False)
    print("Successfully populated public.\"NIRF\" table.")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load NIRF CSV to Postgres")
    parser.add_argument("--csv", default="data/nirf_2017_2025_unified.csv", help="Path to unified CSV")
    args = parser.parse_args()
    setup_nirf_table(args.csv)

