import pandas as pd

from config import COLUMNS, DATA_PATH, SCORE_PARAMS


def load_data(path=DATA_PATH) -> pd.DataFrame:
    """Load the unified NIRF file and return it with canonical column names.

    One row = one institution in one year and category.
    Flag columns (Rank_Withdrawn, Has_Rank_Tie, In_Top100, In_Top50) are kept as-is.
    """
    raw = pd.read_csv(path)
    rename = {src: canon for canon, src in COLUMNS.items()}
    df = raw.rename(columns=rename)

    required = ["year", "category", "institution", "institution_id", "state", "rank", "score"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns after mapping: {missing}. Check COLUMNS in config.py")

    df["year"] = df["year"].astype(int)
    df["category"] = df["category"].astype(str).str.strip()
    df["state"] = df["state"].astype(str).str.strip()
    df["institution_id"] = df["institution_id"].astype(str)
    for col in ["rank", "score"] + SCORE_PARAMS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "display_name" not in df.columns:
        df["display_name"] = df["institution"]

    before = len(df)
    df = df.drop_duplicates()
    if before != len(df):
        print(f"Removed {before - len(df)} exact duplicate rows")

    # Same institution twice in one year/category would make every count wrong.
    dup = df.duplicated(["year", "category", "institution_id"], keep=False)
    if dup.any():
        raise ValueError(f"{dup.sum()} rows repeat an institution_id within a year/category")

    print(f"Loaded {len(df):,} rows, years {df['year'].min()}-{df['year'].max()}, "
          f"{df['category'].nunique()} categories")
    return df


def check_rank_quality(df: pd.DataFrame, category: str = "Overall") -> pd.DataFrame:
    """Report duplicate and missing ranks (1..100) per year. Does not change the data."""
    rows = []
    for year, g in df[df["category"] == category].groupby("year"):
        ranks = g["rank"].dropna()
        rows.append({
            "year": year,
            "ranked_rows": len(ranks),
            "duplicate_rank_rows": int(ranks.duplicated(keep=False).sum()),
            "missing_ranks_1_to_100": sorted(set(range(1, 101)) - set(ranks.astype(int))),
        })
    return pd.DataFrame(rows)