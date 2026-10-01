"""
Builds data/processed/basis_table_enriched.csv and the basis chart from the three raw sources.

This is deliberately separate from notebooks/01_basis_analysis.ipynb: this script does the
deterministic, repeatable part of the pipeline (join, basis calc, anomaly flagging) that's safe
to re-run on a schedule. The notebook keeps the deeper hypothesis-testing analysis (correlation
p-values, multiple-comparisons correction) — that's a periodic, human-reviewed analysis step,
not something that needs to recompute every time new data lands.

Usage:
    python src/build_basis_table.py

Reads:
    data/raw/henry_hub_daily_fred.csv
    data/raw/waha_weekly_parsed.csv
    data/raw/storage_weekly_south_central.csv

Writes:
    data/processed/basis_table_enriched.csv
    data/processed/basis_chart.png
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # no display available when run from Airflow/cron
import matplotlib.pyplot as plt
import pandas as pd

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"

ROLLING_WINDOW = 12  # observations, not calendar weeks — see README limitations
N_STD = 2


def load_raw():
    henry_hub = pd.read_csv(RAW_DIR / "henry_hub_daily_fred.csv", parse_dates=["date"])
    waha = pd.read_csv(RAW_DIR / "waha_weekly_parsed.csv", parse_dates=["report_date"])
    waha = waha.dropna(subset=["waha_price"]).copy()
    storage = pd.read_csv(RAW_DIR / "storage_weekly_south_central.csv", parse_dates=["period"])
    storage = storage[["period", "value"]].rename(
        columns={"period": "storage_date", "value": "storage_bcf"}
    )
    return henry_hub, waha, storage


def build_basis_table(henry_hub: pd.DataFrame, waha: pd.DataFrame, storage: pd.DataFrame) -> pd.DataFrame:
    df = waha.merge(
        henry_hub.rename(columns={"date": "report_date"}),
        on="report_date",
        how="left",
    )
    df = df.dropna(subset=["henry_hub_price"]).sort_values("report_date").reset_index(drop=True)

    df["basis_calculated"] = df["waha_price"] - df["henry_hub_price"]
    df["rolling_mean"] = df["basis_calculated"].rolling(ROLLING_WINDOW, min_periods=6).mean()
    df["rolling_std"] = df["basis_calculated"].rolling(ROLLING_WINDOW, min_periods=6).std()
    df["z_score"] = (df["basis_calculated"] - df["rolling_mean"]) / df["rolling_std"]
    df["flagged"] = df["z_score"].abs() > N_STD

    storage_sorted = storage.sort_values("storage_date")
    df = pd.merge_asof(
        df.sort_values("report_date"),
        storage_sorted,
        left_on="report_date",
        right_on="storage_date",
        direction="backward",  # match each Wednesday to the most recent Friday storage figure
    )
    return df


def save_chart(df: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(13, 5))
    ax.plot(df["report_date"], df["basis_calculated"], marker="o", markersize=3,
            linewidth=1, label="Waha − Henry Hub basis")
    ax.axhline(0, color="gray", linewidth=0.8, linestyle="--")

    flagged = df[df["flagged"]]
    ax.scatter(flagged["report_date"], flagged["basis_calculated"], color="red",
               zorder=5, label=f"Flagged (|z| > {N_STD})")

    ax.set_title("Permian (Waha) vs. Henry Hub Natural Gas Basis")
    ax.set_ylabel("$/MMBtu")
    ax.legend()
    plt.tight_layout()
    plt.savefig(PROCESSED_DIR / "basis_chart.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading raw data...")
    henry_hub, waha, storage = load_raw()

    print("Building basis table...")
    df = build_basis_table(henry_hub, waha, storage)
    df.to_csv(PROCESSED_DIR / "basis_table_enriched.csv", index=False)
    print(f"  -> {len(df)} rows saved to data/processed/basis_table_enriched.csv")
    print(f"  -> {df['flagged'].sum()} weeks flagged as unusual")

    print("Saving chart...")
    save_chart(df)
    print("  -> saved to data/processed/basis_chart.png")
