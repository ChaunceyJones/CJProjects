-- Basis calculation + rolling z-score anomaly flagging, in SQL.
--
-- This is a deliberate reimplementation of the logic in src/build_basis_table.py, not a
-- replacement for it. The Python version is the one the Airflow pipeline runs; this version
-- exists to be cross-checked against it (see src/run_sql_analysis.py), because two independent
-- implementations agreeing is a much stronger correctness signal than one implementation
-- looking plausible.
--
-- Engine: DuckDB — reads the CSVs directly, no server or load step required.
--
-- The rolling window is the interesting part: 12 OBSERVATIONS, not 12 calendar weeks. The Waha
-- series has real multi-month coverage gaps (see README limitations), so an observation-based
-- window can span a much longer wall-clock period during sparse stretches. This matches the
-- pandas .rolling(12) behavior exactly, which is the point.

WITH joined AS (
    SELECT
        w.report_date,
        w.waha_price,
        h.henry_hub_price,
        w.waha_price - h.henry_hub_price AS basis_calculated
    FROM read_csv_auto('data/raw/waha_weekly_parsed.csv') w
    INNER JOIN read_csv_auto('data/raw/henry_hub_daily_fred.csv') h
        ON w.report_date = h.date
    WHERE w.waha_price IS NOT NULL
),

with_rolling AS (
    SELECT
        *,
        -- ROWS BETWEEN 11 PRECEDING AND CURRENT ROW = a 12-observation trailing window,
        -- matching pandas .rolling(window=12).
        AVG(basis_calculated) OVER w AS rolling_mean,
        STDDEV_SAMP(basis_calculated) OVER w AS rolling_std,
        COUNT(*) OVER w AS window_obs
    FROM joined
    WINDOW w AS (
        ORDER BY report_date
        ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
    )
),

scored AS (
    SELECT
        report_date,
        waha_price,
        henry_hub_price,
        basis_calculated,
        rolling_mean,
        rolling_std,
        -- pandas uses min_periods=6, so rows with fewer than 6 observations in the window get
        -- a null z-score rather than one computed from too little history.
        CASE
            WHEN window_obs >= 6 AND rolling_std > 0
            THEN (basis_calculated - rolling_mean) / rolling_std
        END AS z_score
    FROM with_rolling
)

SELECT
    report_date,
    ROUND(waha_price, 2)        AS waha_price,
    ROUND(henry_hub_price, 2)   AS henry_hub_price,
    ROUND(basis_calculated, 2)  AS basis_calculated,
    ROUND(z_score, 4)           AS z_score,
    COALESCE(ABS(z_score) > 2, FALSE) AS flagged
FROM scored
ORDER BY report_date;
