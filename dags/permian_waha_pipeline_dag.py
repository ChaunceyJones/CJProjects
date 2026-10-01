"""
Weekly Airflow DAG for the Permian-Waha basis pipeline.

Runs every Thursday (after EIA's weekly reports would historically have posted), pulling fresh
Henry Hub, storage, and Waha data, then rebuilding the basis table and chart.

KNOWN LIMITATION — read before enabling this DAG on a schedule:
EIA discontinued the Natural Gas Weekly Update report (the source parse_waha_weekly.py depends
on) after the January 21, 2026 edition — see the main README's "Limitations & assumptions"
section. The parse_waha_weekly task below is included for completeness and will run without
erroring, but it will currently find zero new Waha data every single week, since there's nothing
left at the URLs it checks. Fixing this requires migrating the parser to EIA's replacement report
(the "Weekly Natural Gas Storage Report Supplement" on their Beta site), which hasn't been built
yet. The Henry Hub and storage tasks are unaffected — those sources are both still live.

Setup:
    1. This file expects standard Airflow environment variables / .env-style secrets to already
       be configured for EIA_API_KEY and FRED_API_KEY in the Airflow worker's environment, the
       same names used by src/extract_eia.py and src/extract_fred.py.
    2. Update PROJECT_DIR below to wherever this repo actually lives on the Airflow host.
    3. Copy or symlink this file into your Airflow DAGs folder.
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

PROJECT_DIR = "/opt/airflow/projects/permian-waha-basis"  # <-- update to your actual path

default_args = {
    "owner": "chauncey",
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
}

with DAG(
    dag_id="permian_waha_basis_pipeline",
    description="Weekly refresh of Henry Hub, storage, and Waha data, then rebuild the basis table.",
    default_args=default_args,
    schedule="0 12 * * THU",  # Thursdays at noon — after EIA's historical weekly release day
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["permian-waha-basis"],
) as dag:

    extract_henry_hub = BashOperator(
        task_id="extract_henry_hub",
        bash_command=f"cd {PROJECT_DIR} && python src/extract_fred.py",
    )

    extract_storage = BashOperator(
        task_id="extract_storage",
        bash_command=f"cd {PROJECT_DIR} && python src/extract_eia.py",
    )

    # See the KNOWN LIMITATION note at the top of this file — this task currently finds no new
    # data every run, through no fault of the code, until the parser is migrated to EIA's
    # replacement report. Left in the DAG rather than removed, so the pipeline's shape is honest
    # about what it's supposed to do once that migration happens.
    extract_waha = BashOperator(
        task_id="extract_waha_weekly",
        bash_command=f"cd {PROJECT_DIR} && python src/parse_waha_weekly.py",
    )

    build_basis_table = BashOperator(
        task_id="build_basis_table",
        bash_command=f"cd {PROJECT_DIR} && python src/build_basis_table.py",
    )

    [extract_henry_hub, extract_storage, extract_waha] >> build_basis_table
