from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "processed" / "nirf_2017_2025_unified.csv"
OUT_DIR = ROOT / "Sample_Questions_plots"

# Left = canonical name used in code. Right = column name in the unified CSV.
COLUMNS = {
    "year": "Year",
    "category": "Category",
    "institution": "Name_Unified",
    "institution_id": "Unified_ID",   # stable key: always join on this, never on the name
    "display_name": "Name_Display",   # used only for chart labels
    "state": "State_Unified",
    "city": "City_Unified",
    "rank": "Rank",
    "score": "Score",
    "TLR": "TLR",
    "RPC": "RPC",
    "GO": "GO",
    "OI": "OI",
    "PR": "Perception",
}

SCORE_PARAMS = ["TLR", "RPC", "GO", "OI", "PR"]
DEFAULT_CATEGORY = "Overall"
TOP_N = 100