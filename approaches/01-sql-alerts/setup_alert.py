"""
SQL ALERTS approach — reproducible setup.

Creates the query + alert + sql_task job that delivers the DFM regression report as a
Databricks-native email (no SMTP, no external provider). Run `common/setup_uc.py` first
so the source tables exist.

    python3 approaches/01-sql-alerts/setup_alert.py
"""
import json
import os
import re
import subprocess
import sys

PROFILE = "e2-demo-field-eng"
WAREHOUSE_ID = "6674ed0664e1e8a3"
WSDIR = "/Workspace/Users/narasimha.kamathardi@databricks.com/cvs-dfm-report-demo"
FQ = "users.narasimha_kamathardi"
SUBSCRIBER = "narasimha.kamathardi@databricks.com"
HERE = os.path.dirname(os.path.abspath(__file__))


def cli(args, inp=None):
    p = subprocess.run(["databricks", *args, "--profile", PROFILE],
                       capture_output=True, text=True, input=inp)
    if p.returncode != 0:
        print("ERROR:", p.stderr.strip()[-500:]); sys.exit(1)
    out = p.stdout[p.stdout.find("{"):] if "{" in p.stdout else "{}"
    return json.loads(out) if out.strip() else {}


# 1) Saved query — returns the latest run summary (failure_count drives the alert)
query_text = (f"SELECT s.run_id, s.suite_category, s.execution_status, s.status, "
              f"s.total_count, s.success_count, s.failure_count, s.elapsed_time, s.run_user "
              f"FROM {FQ}.dfm_suite_status s "
              f"WHERE s.run_id = (SELECT MAX(run_id) FROM {FQ}.dfm_suite_status)")
q = cli(["queries", "create", "--json", json.dumps({"query": {
    "display_name": "cvs-dfm-run-summary", "warehouse_id": WAREHOUSE_ID,
    "query_text": query_text, "parent_path": WSDIR,
    "description": "Latest DFM regression run summary (drives the alert)"}})])
query_id = q["id"]
print("query_id:", query_id)

# 2) Alert — fires when failure_count > 0. custom_body = the report (email-safe HTML;
#    Databricks sanitizes borders out — see this approach's README).
body = open(os.path.join(HERE, "email_report_body.html"), encoding="utf-8").read()
a = cli(["alerts", "create", "--json", json.dumps({"alert": {
    "display_name": "cvs-dfm-regression-alert", "query_id": query_id, "parent_path": WSDIR,
    "condition": {"op": "GREATER_THAN",
                  "operand": {"column": {"name": "failure_count"}},
                  "threshold": {"value": {"double_value": 0}}},
    "custom_subject": "DFM Regression Report - Run 2088075 - FAILED",
    "custom_body": body, "seconds_to_retrigger": 0}})])
alert_id = a["id"]
print("alert_id:", alert_id)

# 3) Job — sql_task alert with the stakeholder as subscriber. Databricks sends the email
#    when the alert triggers. Add more subscribers or a schedule as needed.
#    subscriptions accept BOTH individual users and GROUP emails:
#      {"user_name": "person@corp.com"}          individual workspace user
#      {"destination_id": "<email-destination>"} group / distribution list
#    (create/list group destinations: databricks notification-destinations list)
subscriptions = [{"user_name": SUBSCRIBER}]
# subscriptions.append({"destination_id": "00c243ad-88cb-4fc9-93f2-23cd4b337e6b"})  # group DL
j = cli(["jobs", "create", "--json", json.dumps({
    "name": "cvs-dfm-alert-email",
    "tasks": [{"task_key": "fire_alert", "sql_task": {
        "warehouse_id": WAREHOUSE_ID,
        "alert": {"alert_id": alert_id,
                  "subscriptions": subscriptions,
                  "pause_subscriptions": False}}}],
    "queue": {"enabled": True}, "max_concurrent_runs": 1})])
print("job_id:", j["job_id"])
print("\nDone. Run the job to evaluate the alert and email subscribers.")
