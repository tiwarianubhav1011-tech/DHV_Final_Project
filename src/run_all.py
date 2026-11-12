import argparse

import pandas as pd

import analytics as an
import visualizations as viz
from config import OUT_DIR
from data_loader import check_rank_quality, load_data


def main():
    p = argparse.ArgumentParser(description="Generate charts and tables for NIRF questions 1.1 to 8.5")
    p.add_argument("--only", nargs="*", default=None, help="Question ids to run, e.g. 2.3 5.3 7.1")
    p.add_argument("--institution", default=None, help="Institution name for question 1.1")
    args = p.parse_args()

    df = load_data()
    tables = OUT_DIR / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    check_rank_quality(df).to_csv(tables / "rank_quality_check.csv", index=False)

    ids = args.only or list(an.ANALYSES)
    done, failed = 0, []
    for qid in ids:
        if qid not in an.ANALYSES:
            print(f"Unknown question id: {qid}")
            failed.append(qid)
            continue
        kwargs = {"institution": args.institution} if qid == "1.1" and args.institution else {}
        try:
            result = an.ANALYSES[qid](df, **kwargs)
            viz.PLOTTERS[qid](result, OUT_DIR / f"Q{qid}.png")
            keep_index = not isinstance(result.index, pd.RangeIndex)
            result.to_csv(tables / f"Q{qid}.csv", index=keep_index)
            done += 1
        except Exception as exc:
            print(f"Q{qid} failed: {exc}")
            failed.append(qid)

    print(f"\nFinished {done} of {len(ids)} questions. Charts in {OUT_DIR}")
    if failed:
        print("Failed:", failed)


if __name__ == "__main__":
    main()