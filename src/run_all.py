"""
Runs the full pipeline end to end, in order. Stops at the first failure rather than continuing
with stale data.

Handles one thing automatically that's easy to get wrong by hand: the Waha parser needs a full
historical backfill (--start/--end over the whole range) the first time, but routine runs use
incremental mode. This script picks the right one based on whether the output CSV already
exists.

Note that the Waha step currently finds no NEW data in incremental mode, because EIA
discontinued the Natural Gas Weekly Update after the Jan 21, 2026 edition — see the README's
Limitations section. That's a documented source gap, not a failure, so this script treats a
zero-new-rows result as success.

Usage:
    python src/run_all.py
    python src/run_all.py --rebuild-waha    # force a full historical re-scrape (slow, ~196 weeks)
    python src/run_all.py --skip-sql        # skip the DuckDB cross-check
"""

import argparse
import subprocess
import sys
from pathlib import Path

SRC_DIR = Path(__file__).parent
PROJECT_ROOT = SRC_DIR.parent
WAHA_CSV = PROJECT_ROOT / "data" / "raw" / "waha_weekly_parsed.csv"
ENV_FILE = PROJECT_ROOT / ".env"

# The full range the discontinued EIA report covers. See README Limitations.
BACKFILL_START = "2022-01-01"
BACKFILL_END = "2026-01-21"


def run_step(script: str, label: str, extra_args: list[str] | None = None) -> None:
    print(f"\n{'=' * 70}\n{label}\n{'=' * 70}", flush=True)
    cmd = [sys.executable, str(SRC_DIR / script)] + (extra_args or [])
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    if result.returncode != 0:
        print(f"\nFAILED at {script} (exit code {result.returncode}). Stopping here rather "
              f"than continuing with incomplete data.")
        sys.exit(result.returncode)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild-waha", action="store_true",
                        help="Force a full historical re-scrape of the Waha series "
                             "(~196 report weeks, slow). Normally only needed once.")
    parser.add_argument("--skip-sql", action="store_true",
                        help="Skip the DuckDB cross-check step")
    args = parser.parse_args()

    if not ENV_FILE.exists():
        print(f"No .env found at {ENV_FILE}. Copy .env.example to .env and add your "
              f"EIA_API_KEY and FRED_API_KEY before running — steps 1 and 2 need them.")
        sys.exit(1)

    run_step("extract_fred.py", "1. Henry Hub daily prices (FRED)")
    run_step("extract_eia.py", "2. South Central natural gas storage (EIA API v2)")

    if args.rebuild_waha or not WAHA_CSV.exists():
        reason = ("--rebuild-waha requested" if args.rebuild_waha
                  else f"no existing {WAHA_CSV.name}")
        print(f"\nRunning a FULL Waha backfill ({reason}) — {BACKFILL_START} to "
              f"{BACKFILL_END}, ~196 report weeks. This takes several minutes.")
        run_step("parse_waha_weekly.py", "3. Waha price + rig count (full historical backfill)",
                 ["--start", BACKFILL_START, "--end", BACKFILL_END, "--full-rebuild"])
    else:
        run_step("parse_waha_weekly.py", "3. Waha price + rig count (incremental)")

    run_step("build_basis_table.py", "4. Join sources, compute basis + z-score anomaly flags")

    if not args.skip_sql:
        run_step("run_sql_analysis.py", "5. SQL cross-check (DuckDB vs. pandas)")

    print(f"\n{'=' * 70}\nPipeline complete. Outputs in data/processed/:")
    print("  basis_table_enriched.csv, basis_chart.png")
    print(f"{'=' * 70}")
