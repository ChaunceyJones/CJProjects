"""
Pulls natural gas storage data from the EIA Open Data API v2 and writes it to data/raw/.

Note: Henry Hub prices now come from FRED instead (see extract_fred.py) — EIA's own v2 route
for that stopped updating in April 2024. This script is storage-only.

Usage:
    python src/extract_eia.py --list-facets natural-gas/stor/wkly   # explore region/process codes
    python src/extract_eia.py                                        # pulls South Central (default: duoarea=R33, process=SWO)
    python src/extract_eia.py --region R31 --process SWO             # e.g. East region instead

Setup:
    1. Get a free key: https://www.eia.gov/opendata/register.php
    2. Copy .env.example to .env and paste your key in as EIA_API_KEY
    3. pip install -r requirements.txt
"""

import argparse
import os
import sys
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

sys.path.append(str(Path(__file__).parent))
from config import EIA_BASE_URL, STORAGE_ROUTE

load_dotenv()
API_KEY = os.getenv("EIA_API_KEY")
RAW_DIR = Path(__file__).parent.parent / "data" / "raw"


def _check_key():
    if not API_KEY:
        raise SystemExit(
            "No EIA_API_KEY found. Copy .env.example to .env and add your free key "
            "(https://www.eia.gov/opendata/register.php)."
        )


def list_routes(route: str):
    """Explore what's available under a route."""
    _check_key()
    url = f"{EIA_BASE_URL}/{route}"
    resp = requests.get(url, params={"api_key": API_KEY})
    resp.raise_for_status()
    data = resp.json().get("response", {})
    print(f"Routes/facets under '{route}':")
    for key, val in data.items():
        print(f"  {key}: {val}")


def list_facets(route: str):
    """
    Show the facets (filter dimensions) available on a route, e.g. region codes for storage.
    Use this to find the exact region facet name and value for South Central before
    filtering pull_storage() to it.
    """
    _check_key()
    url = f"{EIA_BASE_URL}/{route}"
    resp = requests.get(url, params={"api_key": API_KEY})
    resp.raise_for_status()
    data = resp.json().get("response", {})
    facets = data.get("facets", [])
    if not facets:
        print(f"No facets listed directly on '{route}' — it may only be a container route. "
              f"Try --list-routes {route} instead to find its data sub-route.")
        return
    for f in facets:
        facet_id = f.get("id")
        print(f"\nFacet '{facet_id}' ({f.get('description', '')}):")
        vals_resp = requests.get(f"{url}/facet/{facet_id}", params={"api_key": API_KEY})
        if vals_resp.status_code == 200:
            for v in vals_resp.json().get("response", {}).get("facets", [])[:20]:
                print(f"    {v}")


def pull_storage(facets: dict[str, str] | None = None) -> pd.DataFrame:
    """
    facets: e.g. {"duoarea": "R33", "process": "SWO"} for South Central total working gas.
    R33 = South Central was confirmed by reading EIA's own series names via --list-facets,
    since the duoarea facet's own "name" field is unhelpfully blank ("NA") in this API.
    "process" matters too — the same region is split into Salt (SSO), Non-Salt (SNO), and
    total Working Gas (SWO) subcategories; SWO is what you want for a single combined figure.
    None (no facets) pulls everything unfiltered, which will include all regions mixed together
    — almost never what you want; always pass facets for a specific analysis.
    """
    _check_key()
    url = f"{EIA_BASE_URL}/{STORAGE_ROUTE}/data/"
    params = {
        "api_key": API_KEY,
        "data[0]": "value",
        "sort[0][column]": "period",
        "sort[0][direction]": "desc",
        "length": 5000,
    }
    for key, val in (facets or {}).items():
        params[f"facets[{key}][]"] = val
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    rows = resp.json()["response"]["data"]
    df = pd.DataFrame(rows)
    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--list-routes", type=str, help="Explore a route, e.g. natural-gas/stor")
    parser.add_argument("--list-facets", type=str, help="Show facet values for a route, e.g. natural-gas/stor/wkly")
    parser.add_argument("--region", type=str, default="R33",
                         help="duoarea facet value. Defaults to R33 (South Central, confirmed via "
                              "--list-facets series names). Use 'ALL' to pull unfiltered (all regions mixed).")
    parser.add_argument("--process", type=str, default="SWO",
                         help="process facet value. Defaults to SWO (total Working Gas, not just Salt/Non-Salt).")
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    if args.list_routes:
        list_routes(args.list_routes)
    elif args.list_facets:
        list_facets(args.list_facets)
    else:
        if args.region == "ALL":
            facets = None
            out_name = "storage_weekly_all_regions_unfiltered.csv"
            print("Pulling storage data (unfiltered — all regions/processes mixed together)...")
        else:
            facets = {"duoarea": args.region, "process": args.process}
            out_name = "storage_weekly_south_central.csv" if args.region == "R33" else f"storage_weekly_{args.region}.csv"
            print(f"Pulling storage data (duoarea={args.region}, process={args.process})...")

        storage = pull_storage(facets=facets)
        storage.to_csv(RAW_DIR / out_name, index=False)
        print(f"  -> {len(storage)} rows saved to data/raw/{out_name}")
