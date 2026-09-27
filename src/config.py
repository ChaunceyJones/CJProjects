"""
Data source constants.

RESOLVED (confirmed by checking both APIs directly):
- EIA's v2 route "natural-gas/pri/fut" (Henry Hub) STOPPED updating after April 5, 2024.
  Do not use it for anything current.
- FRED mirrors the same EIA Henry Hub data and IS still current. Use FRED for Henry Hub.
  FRED API: https://api.stlouisfed.org/fred/  (free key: https://fred.stlouisfed.org/docs/api/api_key.html)
  Series: DHHNGSP (daily) or WHHNGSP (weekly)
- Waha Hub has NO clean API anywhere (checked EIA v2 and FRED). It only appears as prose
  inside EIA's weekly "Natural Gas Weekly Update" reports, e.g.:
    "The Waha Hub traded $4.79 below the Henry Hub price yesterday"
    "the price at the Waha Hub ... fell 46 cents ... to -$0.25/MMBtu yesterday"
  These reports are consistently structured enough to parse with regex.
  Archive URL pattern: https://www.eia.gov/naturalgas/weekly/archivenew_ngwu/{year}/{MM}_{DD}
  (one page per report week, going back years)

EIA API (kept for storage data, which IS still current on the v2 route):
"""

EIA_BASE_URL = "https://api.eia.gov/v2"
STORAGE_ROUTE = "natural-gas/stor/wkly"  # still live — confirmed separately from fut route

# FRED (Henry Hub)
FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"
FRED_HENRY_HUB_SERIES = "DHHNGSP"  # daily, still updating

# Waha (parsed from Weekly Update prose, not an API)
EIA_WEEKLY_ARCHIVE_BASE = "https://www.eia.gov/naturalgas/weekly/archivenew_ngwu"
