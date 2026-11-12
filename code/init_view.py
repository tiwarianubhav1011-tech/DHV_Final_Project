"""
Creates/updates the read-only view public."NIRF" that the chatbot queries.

The raw table public.nirf_rankings (loaded from nirf_2017_2025_unified.csv)
uses the CSV's column names; this view exposes the canonical column names
expected by the chatbot, including the five NIRF parameter scores.

Run once (or after reloading the table):  python init_view.py
"""

from sqlalchemy import text
from nirf_chatbot.database import engine

VIEW_SQL = """
CREATE OR REPLACE VIEW public."NIRF" AS
SELECT
    "Year",
    "Category",
    COALESCE("Unified_ID", "Institute_ID") AS "Institution_ID",
    COALESCE("Name_Display", "Name", "Name_Unified") AS "Institution_Name",
    COALESCE("City_Unified", "City") AS "City",
    COALESCE("State_Unified", "State") AS "State",
    "Score",
    CAST("Rank" AS INTEGER) AS "Rank_Numeric",
    CAST(NULL AS VARCHAR) AS "Band",
    CASE WHEN "Rank_Withdrawn" THEN 'Withdrawn' ELSE 'Ranked' END AS "Rank_Status",
    CASE WHEN "Scores_Missing" THEN 'Missing' ELSE 'Scored' END AS "Score_Status",
    "TLR",
    "RPC",
    "GO",
    "OI",
    "Perception"
FROM public.nirf_rankings;
"""


def create_view():
    with engine.connect() as conn:
        with conn.begin():
            conn.execute(text(VIEW_SQL))
    print('View public."NIRF" created/updated (source: public.nirf_rankings).')


if __name__ == "__main__":
    create_view()
