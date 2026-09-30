"""
AI/BI approach — build the hidden, dynamic DFM report dashboard.

4 table widgets (clean gridlines) = the 4 report sections, sourced live from the
dfm_* tables (always latest run). Deploy, then run setup_subscription.py to schedule
the emailed snapshot.

    python3 approaches/02-aibi-api/build_dashboard.py
"""
import json
import subprocess
import sys

PROFILE = "e2-demo-field-eng"
WAREHOUSE_ID = "6674ed0664e1e8a3"
PARENT = "/Workspace/Users/narasimha.kamathardi@databricks.com/cvs-dfm-report-demo"
FQ = "users.narasimha_kamathardi"
LATEST = f"(SELECT MAX(run_id) FROM {FQ}.dfm_suite_status)"


def cols(*pairs):
    return [{"fieldName": f, "displayName": d} for f, d in pairs]


def table_widget(name, dataset, columns, title):
    # No frame title — the section header text widget already labels each table, so a
    # frame title would duplicate it. This matches the customer's original layout.
    fields = [{"name": f["fieldName"], "expression": f'`{f["fieldName"]}`'} for f in columns]
    return {"widget": {
        "name": name,
        "queries": [{"name": "main_query", "query": {
            "datasetName": dataset, "fields": fields, "disaggregated": True}}],
        "spec": {"version": 2, "widgetType": "table",
                 "encodings": {"columns": columns},
                 "frame": {"showTitle": False}}}}


def text(name, md):
    return {"widget": {"name": name, "multilineTextboxSpec": {"lines": [md]}}}


datasets = [
    {"name": "request_ds", "displayName": "Request Summary", "queryLines": [
        "SELECT super_client_name, request_run_date, parent_request_id, request_id, ",
        "task_id, forecast_start_date, lob, app_id ",
        f"FROM {FQ}.dfm_request_summary WHERE run_id = {LATEST}"]},
    {"name": "suite_ds", "displayName": "Execution Suite Status", "queryLines": [
        "SELECT run_id, suite_category, execution_status, status, total_count, ",
        "success_count, failure_count, elapsed_time, run_user ",
        f"FROM {FQ}.dfm_suite_status WHERE run_id = {LATEST}"]},
    {"name": "failed_ds", "displayName": "Execution Failed Query Summary", "queryLines": [
        "SELECT run_id, suite_category, test_code, tags, test_description, execution_status ",
        f"FROM {FQ}.dfm_failed_queries WHERE run_id = {LATEST}"]},
    {"name": "threshold_ds", "displayName": "Threshold Summary", "queryLines": [
        f"SELECT threshold_query_description FROM {FQ}.dfm_threshold_summary WHERE run_id = {LATEST}"]},
]

request_cols = cols(
    ("super_client_name", "Super Client Name"), ("request_run_date", "Request Run Date"),
    ("parent_request_id", "Parent Request Id"), ("request_id", "Request Id"),
    ("task_id", "Task Id"), ("forecast_start_date", "Forecast Start Date"),
    ("lob", "LOB"), ("app_id", "App ID"))
suite_cols = cols(
    ("run_id", "Run ID"), ("suite_category", "Suite Category"),
    ("execution_status", "Execution Status"), ("status", "Status"),
    ("total_count", "Total Count"), ("success_count", "Success Count"),
    ("failure_count", "Failure Count"), ("elapsed_time", "Elapsed Time"),
    ("run_user", "Run User"))
failed_cols = cols(
    ("run_id", "Run ID"), ("suite_category", "Suite Category"), ("test_code", "Test Code"),
    ("tags", "Tags"), ("test_description", "Test Description"),
    ("execution_status", "Execution Status"))
threshold_cols = cols(("threshold_query_description", "Threshold Query Description"))

layout = [
    (text("title", "## DFM Regression Report"), 0, 0, 12, 1),
    (text("subtitle", "Latest run — sourced live from Unity Catalog. Delivered natively via AI/BI subscription."), 0, 1, 12, 1),
    (text("h_req", "### Request Summary"), 0, 2, 12, 1),
    (table_widget("t_req", "request_ds", request_cols, "Request Summary"), 0, 3, 12, 3),
    (text("h_suite", "### Execution Suite Status Summary"), 0, 6, 12, 1),
    (table_widget("t_suite", "suite_ds", suite_cols, "Execution Suite Status Summary"), 0, 7, 12, 3),
    (text("h_failed", "### Execution Failed Query Summary Status"), 0, 10, 12, 1),
    (table_widget("t_failed", "failed_ds", failed_cols, "Execution Failed Query Summary Status"), 0, 11, 12, 4),
    (text("h_thr", "### Threshold Summary Status"), 0, 15, 12, 1),
    (table_widget("t_thr", "threshold_ds", threshold_cols, "Threshold Summary Status"), 0, 16, 12, 3),
]

spec = {
    "datasets": datasets,
    "pages": [{
        "name": "report", "displayName": "DFM Regression Report",
        "pageType": "PAGE_TYPE_CANVAS", "layoutVersion": "GRID_V1",
        "layout": [{"widget": w["widget"],
                    "position": {"x": x, "y": y, "width": ww, "height": hh}}
                   for (w, x, y, ww, hh) in layout]}]
}

serialized = json.dumps(spec)
existing = sys.argv[1] if len(sys.argv) > 1 else None  # pass a dashboard_id to update in place

if existing:  # update existing dashboard (no duplicate)
    p = subprocess.run(["databricks", "lakeview", "update", existing,
                        "--display-name", "CVS DFM Regression Report",
                        "--serialized-dashboard", serialized,
                        "--warehouse-id", WAREHOUSE_ID, "--profile", PROFILE],
                       capture_output=True, text=True)
else:  # create new
    p = subprocess.run(["databricks", "lakeview", "create", "--json", json.dumps({
        "display_name": "CVS DFM Regression Report", "parent_path": PARENT,
        "serialized_dashboard": serialized, "warehouse_id": WAREHOUSE_ID}),
        "--profile", PROFILE], capture_output=True, text=True)

out = p.stdout[p.stdout.find("{"):] if "{" in p.stdout else ""
if p.returncode != 0 or not out:
    print("ERROR:", p.stderr.strip()[-800:]); sys.exit(1)
d = json.loads(out)
print("dashboard_id:", d.get("dashboard_id"))
print("path:", d.get("path"))
