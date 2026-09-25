# Permian–Waha Basis Dashboard & Trade Recommendation

**One-line hook:**
> Waha traded at a $0.91/MMBtu average discount to Henry Hub from 2022–2026, but 9 weeks saw dislocations beyond 2 standard deviations — including a $5.93/MMBtu collapse in October 2022 and a rare premium (+$2.01) in December 2024.

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
1. **Waha traded below Henry Hub in the large majority of weeks** — median basis of −$0.63/MMBtu
   and a mean of −$0.91/MMBtu across 111 weeks with usable data (2022–2026), consistent with
   known Permian Basin takeaway-capacity constraints.
2. **The distribution has a long negative tail rather than being evenly spread** — the 75th
   percentile basis is still only −$0.30/MMBtu, but the minimum reaches −$5.93/MMBtu. Most
   weeks are a modest, expected discount; a small number are severe dislocations.
3. **9 of 111 weeks (~8%) were flagged as statistically unusual** (|z-score| > 2 vs. a trailing
   12-observation mean), split into two distinct patterns rather than one:
   - **Deep negative dislocations** — Oct 26, 2022 (−$5.93), Aug 28, 2024 (−$5.56), and Mar 19,
     2025 (−$4.78) are the three most severe. These align with the known 2022–2024 period of
     chronic Permian oversupply and pipeline maintenance widely reported by EIA in the same
     period (see raw source commentary in `data/raw/waha_weekly_parsed.csv`).
   - **A rare positive anomaly** — Dec 18, 2024 is the one week where Waha priced *above* Henry
     Hub (+$2.01/MMBtu), the opposite of its usual discount. The exact EIA report for that week
     could not be located to confirm a stated cause. Two pieces of adjacent evidence point toward
     a structural explanation over a weather one: (a) national heating-degree-day data for that
     week was close to normal, not indicative of a demand spike, and (b) EIA's Jan 30, 2025
     report confirms the 2.5 Bcf/d Matterhorn Express Pipeline added new Permian takeaway
     capacity starting October 2024 — weeks before this anomaly — which would structurally
     narrow Waha's discount. This is a plausible, evidence-adjacent hypothesis, not a confirmed
     cause, and should be presented as such rather than asserted.
4. Full flagged-week table and summary stats are reproducible from
   `notebooks/01_basis_analysis.ipynb` and saved to `data/processed/basis_table.csv`.

## 5. Recommendation
For a trading/commercial desk, the practical signal here is the **flag itself, not the raw
basis level** — a trailing-window z-score catches genuine regime shifts rather than reacting to
Waha's normal, expected discount. Concretely:
- Treat a basis move beyond ~2 standard deviations from the trailing 12-week mean (roughly
  ±$2.15/MMBtu from a −$0.91 baseline, based on this dataset) as a trigger for a manual review
  of regional pipeline/maintenance news before the position is adjusted — not an automatic
  trade signal on its own.
- The rare positive-anomaly case (Dec 2024) coincides with new Permian pipeline capacity
  (Matterhorn Express) coming online in October 2024, which is a stronger candidate explanation
  than weather. If confirmed, this reframes the recommendation: **track pipeline capacity
  additions as a leading indicator for structural basis narrowing**, not just weather for
  short-term demand spikes.
- Next step to make this decision-grade rather than descriptive: join in storage and rig-count
  data (already scoped in section 2) to test whether flagged weeks are predictable in advance
  from leading indicators, rather than only identifiable after the fact.

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
8. Add storage + rig count as enrichment once the core basis chart works.     period (see raw source commentary in `data/raw/waha_weekly_parsed.csv`).
   - **A rare positive anomaly** — Dec 18, 2024 is the one week where Waha priced *above* Henry
     Hub (+$2.01/MMBtu), the opposite of its usual discount. Worth a follow-up look at regional
     weather/demand data for that week specifically (a West Texas cold snap is the likely driver,
     not yet confirmed against a weather dataset).
4. Full flagged-week table and summary stats are reproducible from
   `notebooks/01_basis_analysis.ipynb` and saved to `data/processed/basis_table.csv`.

## 5. Recommendation
For a trading/commercial desk, the practical signal here is the **flag itself, not the raw
basis level** — a trailing-window z-score catches genuine regime shifts rather than reacting to
Waha's normal, expected discount. Concretely:
- Treat a basis move beyond ~2 standard deviations from the trailing 12-week mean (roughly
  ±$2.15/MMBtu from a −$0.91 baseline, based on this dataset) as a trigger for a manual review
  of regional pipeline/maintenance news before the position is adjusted — not an automatic
  trade signal on its own.
- The rare positive-anomaly case (Dec 2024) suggests it's worth specifically monitoring winter
  weeks for the *reverse* trade opportunity, since the desk's attention is naturally biased
  toward the more common negative-discount story.
- Next step to make this decision-grade rather than descriptive: join in storage and rig-count
  data (already scoped in section 2) to test whether flagged weeks are predictable in advance
  from leading indicators, rather than only identifiable after the fact.

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
