"""
Runs sql/basis_anomalies.sql via DuckDB and cross-checks the result against the pandas
implementation in build_basis_table.py.

The point isn't that SQL is better here — it's that two independent implementations agreeing
is a much stronger correctness signal than one implementation looking plausible. If they
disagree, this script says exactly where, rather than quietly picking one.

Usage:
    python src/run_sql_analysis.py

Requires:
    pip install duckdb   (already in requirements.txt)
    data/raw/*.csv from the extraction scripts
"""

from pathlib import Path

import duckdb
import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent
SQL_PATH = PROJECT_ROOT / "sql" / "basis_anomalies.sql"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

TOLERANCE = 0.01  # $/MMBtu — floating-point differences below this aren't real disagreements


def run_sql() -> pd.DataFrame:
    # The SQL uses paths relative to the project root, so run DuckDB from there.
    con = duckdb.connect()
    con.execute(f"SET file_search_path='{PROJECT_ROOT}'")
    query = SQL_PATH.read_text()
    # DuckDB resolves read_csv_auto paths relative to the process cwd, so pass absolute paths.
    query = query.replace("data/raw/", f"{PROJECT_ROOT}/data/raw/")
    return con.execute(query).fetchdf()


def compare_with_pandas(sql_df: pd.DataFrame):
    pandas_path = PROCESSED_DIR / "basis_table_enriched.csv"
    if not pandas_path.exists():
        print(f"No pandas output at {pandas_path} — run src/build_basis_table.py first to "
              f"enable the cross-check. Showing SQL results only.")
        return

    pandas_df = pd.read_csv(pandas_path, parse_dates=["report_date"])
    sql_df["report_date"] = pd.to_datetime(sql_df["report_date"])

    merged = sql_df.merge(
        pandas_df[["report_date", "basis_calculated", "flagged"]],
        on="report_date",
        how="outer",
        suffixes=("_sql", "_pandas"),
        indicator=True,
    )

    only_sql = (merged["_merge"] == "left_only").sum()
    only_pandas = (merged["_merge"] == "right_only").sum()
    if only_sql or only_pandas:
        print(f"Row mismatch: {only_sql} rows only in SQL, {only_pandas} only in pandas.")
    else:
        print(f"Row counts match: {len(merged)} rows in both.")

    both = merged[merged["_merge"] == "both"].copy()
    both["basis_diff"] = (both["basis_calculated_sql"] - both["basis_calculated_pandas"]).abs()
    max_diff = both["basis_diff"].max()
    print(f"Max absolute difference in basis_calculated: {max_diff:.6f} "
          f"({'PASS' if max_diff < TOLERANCE else 'FAIL'}, tolerance {TOLERANCE})")

    flag_disagreements = both[both["flagged_sql"] != both["flagged_pandas"]]
    if len(flag_disagreements):
        print(f"\n{len(flag_disagreements)} weeks where the anomaly flag DISAGREES between "
              f"implementations — worth investigating, likely a rolling-window edge case:")
        print(flag_disagreements[["report_date", "basis_calculated_sql",
                                   "flagged_sql", "flagged_pandas"]].to_string(index=False))
    else:
        print(f"Anomaly flags agree on all {len(both)} weeks.")


if __name__ == "__main__":
    print(f"Running {SQL_PATH.name} via DuckDB...\n")
    sql_df = run_sql()
    print(f"SQL returned {len(sql_df)} rows, {sql_df['flagged'].sum()} flagged as anomalies.\n")
    print("Flagged weeks (SQL):")
    print(sql_df[sql_df["flagged"]][["report_date", "basis_calculated", "z_score"]]
          .to_string(index=False))
    print("\n--- Cross-check against pandas implementation ---")
    compare_with_pandas(sql_df)
