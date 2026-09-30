"""
Create + seed the CVS DFM report source tables and a reports Volume on
e2-demo-field-eng (users.narasimha_kamathardi). Idempotent.
"""
import json
import subprocess
import sys

PROFILE = "e2-demo-field-eng"
WAREHOUSE_ID = "6674ed0664e1e8a3"  # genie-hls-claims-shared (X-Small, running)
CATALOG, SCHEMA = "users", "narasimha_kamathardi"
FQ = f"{CATALOG}.{SCHEMA}"


def run(sql: str):
    """Execute one SQL statement via the CLI statements API (respects --profile)."""
    label = " ".join(sql.split())[:80]
    payload = json.dumps({"warehouse_id": WAREHOUSE_ID, "statement": sql,
                          "wait_timeout": "50s"})
    proc = subprocess.run(
        ["databricks", "api", "post", "/api/2.0/sql/statements",
         "--profile", PROFILE, "--json", payload],
        capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"  FAIL(cli): {label}\n    -> {proc.stderr.strip()[-400:]}")
        sys.exit(1)
    # CLI prints version preamble before JSON; slice from first '{'.
    out = proc.stdout[proc.stdout.find("{"):]
    state = json.loads(out).get("status", {}).get("state")
    if state != "SUCCEEDED":
        print(f"  FAIL: {label}\n    -> {out[-400:]}")
        sys.exit(1)
    print(f"  ok: {label}")


STATEMENTS = [
    f"CREATE VOLUME IF NOT EXISTS {FQ}.dfm_reports",

    f"""CREATE OR REPLACE TABLE {FQ}.dfm_request_summary (
        run_id STRING, super_client_name STRING, request_run_date STRING,
        parent_request_id STRING, request_id STRING, task_id STRING,
        forecast_start_date STRING, lob STRING, app_id STRING)""",
    f"""INSERT INTO {FQ}.dfm_request_summary VALUES
        ('2088075','S-1981','2026-08-26','6A33E04B98424C2E98741702A13BE6BE',
         '1D781A575E0F4ADC8BBCE1FBC4E72B70','UW-7469','2027-01-01','MMP','NA')""",

    f"""CREATE OR REPLACE TABLE {FQ}.dfm_suite_status (
        run_id STRING, suite_category STRING, execution_status STRING, status STRING,
        total_count INT, success_count INT, failure_count INT,
        elapsed_time STRING, run_user STRING)""",
    f"""INSERT INTO {FQ}.dfm_suite_status VALUES
        ('2088075','DFM_REGRESSION','FAILED','FAIL',447,444,3,'00:55:01',
         'run.user@example.com')""",

    f"""CREATE OR REPLACE TABLE {FQ}.dfm_failed_queries (
        run_id STRING, suite_category STRING, test_code STRING, tags STRING,
        test_description STRING, execution_status STRING)""",
    f"""INSERT INTO {FQ}.dfm_failed_queries VALUES
        ('2088075','DFM_REGRESSION','TQ104','DFM_TEST',
         'PRE-COMPUTATION BASE TABLE FOR RULES AUDIT SUITE TQ534-TQ543','Query Statement Failed'),
        ('2088075','DFM_REGRESSION','TQ750','DFM_OUTPUT',
         'RBTCR_CD Logic for New Column RBTCR_CD in the Output module','FAIL'),
        ('2088075','DFM_REGRESSION','TQ871','DFM_OUTPUT',
         'Checks if selected drugs have ndc11 not present in shifted table and exclusion list.','FAIL')""",

    f"""CREATE OR REPLACE TABLE {FQ}.dfm_threshold_summary (
        run_id STRING, threshold_query_description STRING)""",
    f"""INSERT INTO {FQ}.dfm_threshold_summary VALUES
        ('2088075','Outlier present in COVID VACCN'),
        ('2088075','Outlier present in FORMULARY EXCEPTION')""",
]

if __name__ == "__main__":
    print(f"Setting up {FQ} on {PROFILE} ...")
    for s in STATEMENTS:
        run(s)
    print("Done.")
