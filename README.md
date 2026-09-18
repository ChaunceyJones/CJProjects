# Permian-to-Gulf Coast Natural Gas Basis & Bottleneck Arbitrage Tracker
├── requirements.txt
├── data/
│   ├── raw/                 # Unprocessed API JSON responses & scraped HTML
│   └── processed/           # Cleaned CSV/Parquet files
├── scripts/
│   ├── 01_eia_api_ingest.py # Python API client
│   ├── 02_scrape_notices.py # Scraper for pipeline maintenance
│   └── 03_clean_transform.py
├── sql/
│   ├── schema.sql
│   └── basis_analysis.sql   # SQL queries for rolling averages & spread analysis
├── models/
│   └── transport_netback.xlsx
└── dashboard/
    └── basis_tracker.twbx   # Tableau/Power BI workbook
