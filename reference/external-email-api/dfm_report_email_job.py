# Databricks notebook source
# MAGIC %md
# MAGIC # DFM Regression Report — email via HTTPS API (no SMTP)
# MAGIC Scenario 2. Renders the exact report HTML and emails it as the message **body**
# MAGIC via **Microsoft Graph** or **Amazon SES** — a REST call over HTTPS:443, not SMTP.
# MAGIC Default `dry_run=true` prints the exact request (no send, no creds needed).

# COMMAND ----------

dbutils.widgets.text("run_id", "")
dbutils.widgets.dropdown("provider", "resend", ["resend", "graph", "ses"])
dbutils.widgets.text("sender", "")           # from mailbox (graph) / verified identity (ses)
dbutils.widgets.text("recipients", "")       # comma-separated; DEMO: use a test inbox only
dbutils.widgets.text("subject", "")
dbutils.widgets.dropdown("dry_run", "true", ["true", "false"])
dbutils.widgets.text("secret_scope", "")     # Databricks secret scope holding creds

CATALOG, SCHEMA = "users", "narasimha_kamathardi"
FQ = f"{CATALOG}.{SCHEMA}"
VOLUME_DIR = f"/Volumes/{CATALOG}/{SCHEMA}/dfm_reports"

# COMMAND ----------

import json
import urllib.request
import urllib.parse
from jinja2 import Environment, select_autoescape

run_id = dbutils.widgets.get("run_id").strip()
if not run_id:
    run_id = str(spark.table(f"{FQ}.dfm_suite_status")
                 .orderBy("run_id", ascending=False).first()["run_id"])

def rows(table):
    return [r.asDict() for r in
            spark.sql(f"SELECT * FROM {FQ}.{table} WHERE run_id = '{run_id}'").collect()]

data = {
    "request": (rows("dfm_request_summary") or [{}])[0],
    "suite": (rows("dfm_suite_status") or [{}])[0],
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
print("rendered ->", report_path)

# COMMAND ----------

provider = dbutils.widgets.get("provider")
sender = dbutils.widgets.get("sender").strip()
recipients = [r.strip() for r in dbutils.widgets.get("recipients").split(",") if r.strip()]
dry_run = dbutils.widgets.get("dry_run") == "true"
scope = dbutils.widgets.get("secret_scope").strip()
s = data["suite"]
subject = (dbutils.widgets.get("subject").strip()
           or f"DFM Regression Report — Run {s.get('run_id')} — {s.get('execution_status')}")

def secret(key):
    return dbutils.secrets.get(scope=scope, key=key)

def redact(tok):
    return (tok[:6] + "…redacted…") if tok else "<none>"

# ---- Microsoft Graph: sendMail over HTTPS:443 ----------------------------- #
def send_graph():
    endpoint = f"https://graph.microsoft.com/v1.0/users/{sender}/sendMail"
    msg = {"message": {"subject": subject,
                       "body": {"contentType": "HTML", "content": html},
                       "toRecipients": [{"emailAddress": {"address": r}} for r in recipients]},
           "saveToSentItems": True}
    if dry_run:
        print("DRY RUN — Microsoft Graph")
        print(f"  POST {endpoint}")
        print(f"  Authorization: Bearer {redact('token-would-be-fetched')}")
        print(f"  Content-Type: application/json")
        print(f"  body(message minus html): "
              f"{json.dumps({**msg['message'], 'body': {'contentType':'HTML','content':f'<{len(html)} bytes of HTML>'}})}")
        return
    # 1) OAuth2 client-credentials token (login.microsoftonline.com, 443)
    tok_body = urllib.parse.urlencode({
        "client_id": secret("graph_client_id"),
        "client_secret": secret("graph_client_secret"),
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials"}).encode()
    tok_req = urllib.request.Request(
        f"https://login.microsoftonline.com/{secret('graph_tenant_id')}/oauth2/v2.0/token",
        data=tok_body)
    token = json.loads(urllib.request.urlopen(tok_req, timeout=30).read())["access_token"]
    # 2) sendMail
    req = urllib.request.Request(endpoint, data=json.dumps(msg).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        print(f"Graph sendMail status: {resp.status} (202 = accepted)")

# ---- Amazon SES: SendEmail over HTTPS:443 (boto3) ------------------------- #
def send_ses():
    region = secret("ses_region") if not dry_run else "<region>"
    if dry_run:
        print("DRY RUN — Amazon SES")
        print(f"  ses:SendEmail  region={region}  endpoint=https://email.{region}.amazonaws.com")
        print(f"  Source={sender}  To={recipients}")
        print(f"  Subject={subject!r}  Body=<{len(html)} bytes of HTML>")
        return
    import boto3
    ses = boto3.client("ses", region_name=region,
                       aws_access_key_id=secret("ses_access_key"),
                       aws_secret_access_key=secret("ses_secret_key"))
    resp = ses.send_email(Source=sender,
        Destination={"ToAddresses": recipients},
        Message={"Subject": {"Data": subject},
                 "Body": {"Html": {"Data": html}}})
    print(f"SES MessageId: {resp['MessageId']}")

# ---- Resend: emails/send over HTTPS:443 (exact HTML as the body) --------- #
def send_resend():
    endpoint = "https://api.resend.com/emails"
    payload = {"from": sender or "onboarding@resend.dev",
               "to": recipients, "subject": subject, "html": html}
    if dry_run:
        print("DRY RUN — Resend")
        print(f"  POST {endpoint}")
        print(f"  Authorization: Bearer {redact('resend-key')}")
        print(f"  from={payload['from']} to={recipients} subject={subject!r} "
              f"html=<{len(html)} bytes, the exact report>")
        return
    req = urllib.request.Request(endpoint, data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {secret('resend_api_key')}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        print(f"Resend status: {resp.status}  {resp.read().decode()[:200]}")

# COMMAND ----------

if not recipients:
    print("No recipients set — rendered report only. (Set 'recipients' to a TEST inbox.)")
elif provider == "resend":
    send_resend()
elif provider == "graph":
    send_graph()
else:
    send_ses()
