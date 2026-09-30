# Databricks notebook source
# MAGIC %md
# MAGIC # DFM Regression Report — render + webhook deliver (no SMTP)
# MAGIC Triggered when `dfm_suite_status` changes. Renders the exact report HTML from
# MAGIC the 4 source tables, writes it to a UC Volume, and POSTs a summary card to a
# MAGIC webhook (Teams / Slack / generic). All egress is HTTPS:443 — no SMTP whitelist.

# COMMAND ----------

dbutils.widgets.text("run_id", "")             # blank = latest run in the table
dbutils.widgets.text("webhook_url", "")        # Teams/Slack/webhook.site URL
dbutils.widgets.dropdown("webhook_format", "slack", ["slack", "teams", "generic"])

CATALOG, SCHEMA = "users", "narasimha_kamathardi"
FQ = f"{CATALOG}.{SCHEMA}"
VOLUME_DIR = f"/Volumes/{CATALOG}/{SCHEMA}/dfm_reports"

# COMMAND ----------

import json
import urllib.request
from jinja2 import Environment, select_autoescape

run_id = dbutils.widgets.get("run_id").strip()
if not run_id:
    run_id = str(spark.table(f"{FQ}.dfm_suite_status")
                 .orderBy("run_id", ascending=False).first()["run_id"])
print("run_id:", run_id)

def rows(table):
    return [r.asDict() for r in
            spark.sql(f"SELECT * FROM {FQ}.{table} WHERE run_id = '{run_id}'").collect()]

request = rows("dfm_request_summary")
suite = rows("dfm_suite_status")
data = {
    "request": request[0] if request else {},
    "suite": suite[0] if suite else {},
    "failed_queries": rows("dfm_failed_queries"),
    "thresholds": rows("dfm_threshold_summary"),
}

# COMMAND ----------

TEMPLATE = r"""<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:24px;background:#fff;font-family:Arial,Helvetica,sans-serif;color:#000;font-size:14px;">
<hr style="border:none;border-top:1px solid #000;margin:0 0 20px 0;">
{% set th="border:1px solid #000;padding:6px 10px;text-align:center;font-weight:bold;vertical-align:middle;" %}
{% set td="border:1px solid #000;padding:6px 10px;text-align:center;vertical-align:middle;word-break:break-word;" %}
{% set sec="font-size:16px;font-weight:bold;margin:28px 0 10px 0;" %}
{% set outer="border-collapse:collapse;border:3px double #000;width:100%;max-width:1000px;" %}
<div style="{{sec}}">Request Summary</div>
<table style="{{outer}}"><thead><tr>
<th style="{{th}}">Super Client<br>Name</th><th style="{{th}}">Request Run<br>Date</th>
<th style="{{th}}">Parent Request Id</th><th style="{{th}}">Request Id</th>
<th style="{{th}}">Task<br>Id</th><th style="{{th}}">Forecast Start<br>Date</th>
<th style="{{th}}">LOB</th><th style="{{th}}">App<br>ID</th></tr></thead><tbody><tr>
<td style="{{td}}">{{request.super_client_name}}</td><td style="{{td}}">{{request.request_run_date}}</td>
<td style="{{td}}">{{request.parent_request_id}}</td><td style="{{td}}">{{request.request_id}}</td>
<td style="{{td}}">{{request.task_id}}</td><td style="{{td}}">{{request.forecast_start_date}}</td>
<td style="{{td}}">{{request.lob}}</td><td style="{{td}}">{{request.app_id}}</td></tr></tbody></table>
<div style="{{sec}}">Execution Suite Status Summary</div>
<table style="{{outer}}"><thead><tr>
<th style="{{th}}">Run ID</th><th style="{{th}}">Suite Category</th><th style="{{th}}">Execution Status</th>
<th style="{{th}}">Status</th><th style="{{th}}">Total Count</th><th style="{{th}}">Success Count</th>
<th style="{{th}}">Failure Count</th><th style="{{th}}">Elapsed Time</th><th style="{{th}}">Run User</th>
</tr></thead><tbody><tr>
<td style="{{td}}">{{suite.run_id}}</td><td style="{{td}}">{{suite.suite_category}}</td>
<td style="{{td}}">{{suite.execution_status}}</td><td style="{{td}}">{{suite.status}}</td>
<td style="{{td}}">{{suite.total_count}}</td><td style="{{td}}">{{suite.success_count}}</td>
<td style="{{td}}">{{suite.failure_count}}</td><td style="{{td}}">{{suite.elapsed_time}}</td>
<td style="{{td}}"><a href="mailto:{{suite.run_user}}" style="color:#1155cc;">{{suite.run_user}}</a></td>
</tr></tbody></table>
<div style="{{sec}}">Execution Failed Query Summary Status</div>
<table style="{{outer}}"><thead><tr>
<th style="{{th}}">Run ID</th><th style="{{th}}">Suite Category</th><th style="{{th}}">Test<br>Code</th>
<th style="{{th}}">Tags</th><th style="{{th}}">Test Description</th><th style="{{th}}">Execution Status</th>
</tr></thead><tbody>
{% for q in failed_queries %}<tr>
<td style="{{td}}">{{q.run_id}}</td><td style="{{td}}">{{q.suite_category}}</td><td style="{{td}}">{{q.test_code}}</td>
<td style="{{td}}">{{q.tags}}</td><td style="{{td}}">{{q.test_description}}</td><td style="{{td}}">{{q.execution_status}}</td>
</tr>{% endfor %}
</tbody></table>
<div style="{{sec}}">Threshold Summary Status</div>
<table style="border-collapse:collapse;border:1px solid #000;width:100%;max-width:520px;"><thead><tr>
<th style="{{th}}">Threshold Query Description</th></tr></thead><tbody>
{% for t in thresholds %}<tr><td style="{{td}}">{{t.threshold_query_description}}</td></tr>{% endfor %}
</tbody></table></body></html>"""

env = Environment(autoescape=select_autoescape(["html"]))
html = env.from_string(TEMPLATE).render(**data)

report_path = f"{VOLUME_DIR}/dfm_report_run_{run_id}.html"
with open(report_path, "w", encoding="utf-8") as f:
    f.write(html)
print("wrote report ->", report_path)

# COMMAND ----------

# Deliver a summary card to the webhook. No SMTP; HTTPS:443 only.
webhook_url = dbutils.widgets.get("webhook_url").strip()
fmt = dbutils.widgets.get("webhook_format")
s = data["suite"]

summary = (f"DFM Regression run {s.get('run_id')} — {s.get('execution_status')}\n"
           f"Suite: {s.get('suite_category')} | Total {s.get('total_count')} · "
           f"Success {s.get('success_count')} · Failure {s.get('failure_count')} | "
           f"Elapsed {s.get('elapsed_time')}\nRun user: {s.get('run_user')}\n"
           f"Full report on volume: {report_path}")

if not webhook_url:
    print("No webhook_url set — skipping POST. Card preview:\n" + summary)
else:
    if fmt == "teams":
        payload = {"@type": "MessageCard", "@context": "http://schema.org/extensions",
                   "themeColor": "D7263D", "summary": f"DFM run {s.get('run_id')} {s.get('status')}",
                   "title": f"DFM Regression run {s.get('run_id')} — {s.get('execution_status')}",
                   "text": summary.replace("\n", "  \n")}
    else:  # slack + generic both accept {"text": ...}
        payload = {"text": summary}
    req = urllib.request.Request(webhook_url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        print(f"webhook POST status: {resp.status}")
