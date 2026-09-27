"""
Pulls current Henry Hub daily spot prices from the FRED API (EIA's own route died in 2024,
FRED mirrors the same EIA data and is still updated).

Setup:
    1. Free FRED API key: https://fred.stlouisfed.org/docs/api/api_key.html
       (separate from your EIA key — add it to .env as FRED_API_KEY)
    2. pip install -r requirements.txt

Usage:
    python src/extract_fred.py
"""

import os
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

from config import FRED_BASE_URL, FRED_HENRY_HUB_SERIES

load_dotenv()
FRED_API_KEY = os.getenv("FRED_API_KEY")
RAW_DIR = Path(__file__).parent.parent / "data" / "raw"


def pull_henry_hub_fred() -> pd.DataFrame:
    if not FRED_API_KEY:
        raise SystemExit(
            "No FRED_API_KEY found. Get a free one at "
            "https://fred.stlouisfed.org/docs/api/api_key.html and add it to .env"
        )
    params = {
        "series_id": FRED_HENRY_HUB_SERIES,
        "api_key": FRED_API_KEY,
        "file_type": "json",
    }
    resp = requests.get(FRED_BASE_URL, params=params)
    resp.raise_for_status()
    obs = resp.json()["observations"]
    df = pd.DataFrame(obs)[["date", "value"]]
    df.columns = ["date", "henry_hub_price"]
    df["date"] = pd.to_datetime(df["date"])
    # FRED uses "." for missing values (market holidays) — drop those
    df = df[df["henry_hub_price"] != "."]
    df["henry_hub_price"] = df["henry_hub_price"].astype(float)
    return df.sort_values("date")


if __name__ == "__main__":
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print("Pulling Henry Hub prices from FRED...")
    df = pull_henry_hub_fred()
    df.to_csv(RAW_DIR / "henry_hub_daily_fred.csv", index=False)
    print(f"  -> {len(df)} rows saved to data/raw/henry_hub_daily_fred.csv")
    print(f"  -> date range: {df['date'].min().date()} to {df['date'].max().date()}")
