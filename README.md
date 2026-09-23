# Permian–Waha Basis Dashboard & Trade Recommendation

**One-line hook (fill in once you have a finding):**
> "Waha basis widened to $X below Henry Hub in [month] — Y std devs beyond the 2-year norm, driven by [pipeline/weather/storage]."

## 1. Business context
You're acting as a junior trading/market analyst supporting a Gas & Power trading desk (modeled on real
Houston-market JDs: Permian Basin / South Texas fundamentals, basis dislocations, trading insight delivery).
The desk needs an early-warning view of when Waha (Permian hub) gas prices decouple from Henry Hub
(the national benchmark) far enough to matter for positioning or pipeline-capacity decisions.

## 2. The data
| Source | What | Frequency | Notes |
|---|---|---|---|
| **FRED API** (`api.stlouisfed.org`) | Henry Hub spot price (`DHHNGSP`) | Daily | EIA's own v2 route for this **stopped updating in April 2024** — confirmed by inspecting the route directly. FRED mirrors the same underlying EIA data and is still current. |
| **EIA Weekly Update reports** (parsed) | Waha Hub spot price | Weekly | No clean API exists anywhere for Waha (checked EIA v2 and FRED). EIA states the price in prose in each week's report — parsed with regex in `src/parse_waha_weekly.py`. This is the real "messy data" element of the project. |
| EIA API v2 | Lower 48 natural gas storage | Weekly | `natural-gas/stor/wkly` — confirmed still live, separate from the dead `fut` route |
| NOAA API or Baker Hughes rig count (published CSV) | Weather (HDD/CDD) or rig activity | Daily/Weekly | Rig count files are genuinely messy — column layout shifts over time |

Schema (target, after cleaning): `date | hub | price_usd_mmbtu | source`

**Data quality note for your limitations section:** the Waha series is regex-parsed from
narrative text that isn't perfectly consistent week to week. Expect some weeks to not match
the pattern — the parser flags these explicitly rather than silently dropping them. Spot-check
a sample against the source pages before trusting the series for analysis.

## 3. Methodology (fill in as you build)
- Basis = Waha price − Henry Hub price, by day/week
- Flag basis moves beyond N standard deviations of trailing 60/90-day mean
- Correlate basis moves against storage levels, weather, and rig activity

## 4. Key findings
_(3–5 findings, each with a number, once analysis is done)_

## 5. Recommendation
_(Quantified, tied to a specific decision — e.g. hedge timing, capacity nomination)_

## 6. Limitations & assumptions
- **Waha coverage ends January 21, 2026.** EIA discontinued the Natural Gas Weekly Update
  report after that edition, replacing it with a "Weekly Natural Gas Storage Report Supplement"
  on their Beta site, which uses a different structure. All Waha-series analysis in this project
  is scoped to 2022-01-01 through 2026-01-21 as a result.
- **Waha prices are only parsed where EIA chose to write about them.** EIA's Weekly Update only
  includes a specific, parseable price sentence for Waha in weeks where the move was notable
  enough to warrant commentary — quieter weeks simply have no Waha paragraph at all. This is
  confirmed by direct inspection of multiple "no match" weeks against the source, not a parsing
  bug. Result: out of 196 report weeks in range, 111 (~57%) have a usable Waha price, with real
  multi-month gaps in some periods (e.g. summer 2023, summer 2025). Basis conclusions during
  those gap periods should be treated as lower-confidence or excluded rather than interpolated.
- Spot prices ≠ physical delivered cost (transport, fees not included).
- Henry Hub is sourced from FRED (`DHHNGSP`); Waha is regex-parsed prose — the two series come
  from different underlying methodologies (NYMEX close vs. NGI-reported), so basis values are
  directionally reliable but shouldn't be read as penny-precise.
- A denser structured alternative exists but wasn't pursued for this pass: EIA republishes an
  ICE "Wholesale Electricity Market Data" spreadsheet covering seven major hubs, which may
  include Waha as structured (non-prose) data — worth investigating if more density is needed.

## 7. Repo structure
```
permian-waha-basis/
├── README.md
├── requirements.txt
├── .env.example          # copy to .env, add your EIA_API_KEY
├── src/
│   ├── config.py         # series IDs / route constants
│   └── extract_eia.py    # pulls raw data from EIA API → data/raw/
├── data/
│   ├── raw/              # untouched API pulls
│   └── processed/        # cleaned, joined basis table
├── notebooks/            # exploration + basis analysis
└── dags/                 # Airflow DAG (added once extraction is proven out)
```

## Build order (don't build Airflow/dbt first)
1. ~~Get an EIA API key, run `src/extract_eia.py`~~ — done, but confirmed the Henry Hub futures
   route is dead since April 2024. Storage route (`src/extract_eia.py`, unchanged) is still fine.
2. Get a free FRED API key, add it to `.env`, run `python src/extract_fred.py` for current
   Henry Hub prices.
3. Run `python src/parse_waha_weekly.py --start 2022-01-01 --end 2026-09-01` to build the
   Waha series. Check the console output for weeks it couldn't parse and spot-check a few
   against the source URLs before trusting the data.
4. Join Henry Hub (FRED) + Waha (parsed) into a basis table in a notebook; sanity-check
   against numbers EIA states directly in the reports (e.g. "$4.79 below Henry Hub"). Done in
   `notebooks/01_basis_analysis.ipynb`.
5. Build the basis calc, rolling z-score flag, and chart. Also done in that notebook —
   outputs `data/processed/basis_table.csv` and `data/processed/basis_chart.png`.
6. Read the flagged weeks and widest-basis weeks in the notebook's summary output, then write
   the actual "Key findings" and "Recommendation" sections in this README using them.
7. Only then wrap extraction in an Airflow DAG and add dbt if you want the "pipeline" story for your portfolio.
8. Add storage + rig count as enrichment once the core basis chart works.
