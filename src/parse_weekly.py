"""
Parses Waha Hub natural gas prices, and (as a bonus, since we're already fetching these
pages) weekly rig counts, out of EIA's Natural Gas Weekly Update reports.

There's no clean API for Waha — EIA states the price in prose inside each week's report,
e.g.:
    "The price at the Waha Hub ... fell 46 cents this report week, from $0.21/MMBtu
     last Wednesday to -$0.25/MMBtu yesterday."
    "The Waha Hub traded $4.79 below the Henry Hub price yesterday."

Rig counts appear in the same pages in two different formats depending on the report's era —
an older narrative style and a newer table style — both are handled, best-effort.

This is a heuristic regex parser, not a guaranteed-clean extraction — spot-check the
output against a few source pages before trusting it for analysis. That's expected:
flag any weeks that don't match as a known limitation in your README, don't silently
drop them.

Usage:
    python src/parse_waha_weekly.py --start 2024-01-01 --end 2024-12-31

Each Weekly Update covers a report week ending on a Wednesday and is published the
next day (Thursday). This script steps through Wednesdays in the given range and
tries the archive URL for each.
"""

import argparse
import re
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

from config import EIA_WEEKLY_ARCHIVE_BASE

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"

# EIA's server rejects requests with the default python-requests User-Agent (looks like a bot).
# A normal browser-style header fixes it.
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

# Matches e.g. "to -$0.25/MMBtu yesterday" or "to $1.37/MMBtu yesterday"
PRICE_TO_YESTERDAY = re.compile(r"to\s+(-?\$[\d.]+)\s*/MMBtu yesterday")
# Search for this pattern within a window of text AFTER "Waha Hub" is mentioned, rather than
# splitting into "sentences" — the prices themselves contain periods (e.g. $3.57), so naive
# sentence-splitting on "." shreds every dollar figure and breaks the match.
WAHA_PRICE_WINDOW = re.compile(r"Waha Hub(.{0,300}?to\s+-?\$[\d.]+\s*/MMBtu yesterday)", re.DOTALL)
# Matches e.g. "Waha Hub traded $4.79 below the Henry Hub price"
BASIS_PATTERN = re.compile(
    r"Waha Hub traded\s+\$?([\d.]+)\s+(below|above)\s+the Henry Hub price"
)
# Rig count wording changed over the years EIA published this report — try both formats.
# Older narrative style: "the total rig count ... now stands at 589 rigs"
RIG_COUNT_NARRATIVE = re.compile(r"total rig count.*?now stands at (\d+)\s*rigs", re.DOTALL)
# Newer table style: "Oil rigs 424 ... Natural gas rigs 117 ..."
RIG_COUNT_TABLE = re.compile(r"Oil rigs\s*(\d+)\D{0,80}?Natural gas rigs\s*(\d+)", re.DOTALL)


def report_dates(start: date, end: date):
    """Yield Wednesdays (report-week-ending dates) between start and end."""
    d = start
    while d.weekday() != 2:  # 2 = Wednesday
        d += timedelta(days=1)
    while d <= end:
        yield d
        d += timedelta(days=7)


def fetch_report_text(report_date: date) -> tuple[str | None, date | None]:
    """
    report_date is the Wednesday the report week ends on. EIA publishes the report the
    next day (usually Thursday), and the archive URL uses that RELEASE date, not the
    Wednesday. Holidays occasionally push the release to Friday, so try both.
    Returns (text, actual_url_date_used) — url_date is None if nothing worked.
    """
    for offset in (1, 2, 0):  # Thursday, then Friday, then same-day as last resort
        url_date = report_date + timedelta(days=offset)
        url = f"{EIA_WEEKLY_ARCHIVE_BASE}/{url_date.year}/{url_date.month:02d}_{url_date.day:02d}"
        for attempt in range(3):  # retry transient timeouts before giving up on this URL
            try:
                resp = requests.get(url, headers=HEADERS, timeout=45)
            except requests.exceptions.RequestException as e:
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))  # brief backoff, then retry
                    continue
                print(f"  [{report_date}] network error on {url}: {type(e).__name__} (gave up after 3 tries)")
                break
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                return soup.get_text(separator=" "), url_date
            break  # non-timeout HTTP error (e.g. 404) — no point retrying, try next offset
    print(f"  [{report_date}] no working URL found (tried Thu/Fri/Wed)")
    return None, None


def parse_week(report_date: date, text: str) -> dict:
    row = {
        "report_date": report_date,
        "waha_price": None,
        "basis_vs_henry_hub": None,
        "total_rig_count": None,
        "oil_rigs": None,
        "gas_rigs": None,
    }

    m = WAHA_PRICE_WINDOW.search(text)
    if m:
        price_match = PRICE_TO_YESTERDAY.search(m.group(1))
        if price_match:
            row["waha_price"] = float(price_match.group(1).replace("$", ""))

    m = BASIS_PATTERN.search(text)
    if m:
        val, direction = m.groups()
        row["basis_vs_henry_hub"] = -float(val) if direction == "below" else float(val)

    m = RIG_COUNT_TABLE.search(text)
    if m:
        row["oil_rigs"] = int(m.group(1))
        row["gas_rigs"] = int(m.group(2))
        row["total_rig_count"] = row["oil_rigs"] + row["gas_rigs"]  # excludes misc rigs
    else:
        m = RIG_COUNT_NARRATIVE.search(text)
        if m:
            row["total_rig_count"] = int(m.group(1))
            # narrative format doesn't split oil/gas — leave those None

    return row


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", help="YYYY-MM-DD. Omit for incremental mode (last 3 weeks).")
    parser.add_argument("--end", help="YYYY-MM-DD. Omit for incremental mode (defaults to today).")
    parser.add_argument("--full-rebuild", action="store_true",
                         help="Overwrite the existing CSV entirely instead of merging new rows in. "
                              "Use for the initial historical backfill; omit for routine/scheduled runs.")
    args = parser.parse_args()

    out_path = RAW_DIR / "waha_weekly_parsed.csv"

    if args.start and args.end:
        start = date.fromisoformat(args.start)
        end = date.fromisoformat(args.end)
    else:
        # Incremental mode: only check the last few report weeks. A 3-week lookback tolerates
        # a run being skipped once without needing a full historical re-scrape.
        # NOTE: EIA discontinued this exact report after the Jan 21, 2026 edition (see README
        # Limitations). Incremental mode will currently find nothing and report every week as
        # "no working URL found" until this parser is migrated to the replacement report
        # (the WNGSR Supplement on EIA's Beta site) — that migration hasn't been done yet.
        end = date.today()
        start = end - timedelta(weeks=3)
        print(f"No --start/--end given — running incremental mode ({start} to {end}).")

    rows = []
    misses = []
    for d in report_dates(start, end):
        text, url_date = fetch_report_text(d)
        if text is None:
            misses.append(d)
            continue
        row = parse_week(d, text)
        rows.append(row)
        status = "OK" if row["waha_price"] is not None else "no Waha price match"
        print(f"  [{d}] fetched ({url_date}) - {status}", flush=True)
        time.sleep(0.5)  # be polite to EIA's servers

    new_df = pd.DataFrame(rows)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    if not args.full_rebuild and out_path.exists():
        existing = pd.read_csv(out_path, parse_dates=["report_date"])
        new_df["report_date"] = pd.to_datetime(new_df["report_date"])
        combined = pd.concat([existing, new_df])
        # Keep the newest parse of any report_date that appears in both (in case wording/parsing
        # improved since the last run), rather than silently duplicating rows.
        combined = combined.drop_duplicates(subset="report_date", keep="last")
        df = combined.sort_values("report_date").reset_index(drop=True)
        print(f"Merged {len(new_df)} newly-fetched weeks with {len(existing)} existing rows "
              f"-> {len(df)} total rows.")
    else:
        df = new_df
        if args.full_rebuild:
            print("Full rebuild requested — overwriting any existing file.")

    df.to_csv(out_path, index=False)

    n_found = new_df["waha_price"].notna().sum() if len(new_df) else 0
    n_rigs = new_df["total_rig_count"].notna().sum() if len(new_df) else 0
    print(f"This run: parsed {len(new_df)} report weeks, found a Waha price in {n_found} of them, "
          f"and a rig count in {n_rigs} of them.")
    if misses:
        print(f"Could not fetch {len(misses)} weeks (bad URL or network issue): {misses[:5]}...")
    unmatched = new_df[new_df["waha_price"].isna()] if len(new_df) else pd.DataFrame()
    if len(unmatched):
        print(f"{len(unmatched)} weeks fetched but no price pattern matched — "
              f"spot-check these manually, wording sometimes varies:")
        print(unmatched["report_date"].tolist())
