"""
Render the CVS DFM regression run report (exact format from the source system)
from Unity Catalog tables, and deliver it WITHOUT SMTP.

Delivery paths demonstrated (all serverless-friendly, no SMTP egress whitelist):
  1. Write the rendered HTML to a UC Volume  (durable, linkable artifact)
  2. POST a summary card to a webhook         (Teams / Slack / generic HTTPS:443)

Run locally for a preview (uses embedded sample data == the screenshot), or as a
serverless job task against real tables.
"""
from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

CATALOG = os.environ.get("REPORT_CATALOG", "users")
SCHEMA = os.environ.get("REPORT_SCHEMA", "narasimha_kamathardi")
TEMPLATE_DIR = Path(__file__).parent


# --------------------------------------------------------------------------- #
# Sample data — mirrors the source screenshot exactly, used for local preview  #
# and as the shape the UC queries must return.                                 #
# --------------------------------------------------------------------------- #
SAMPLE = {
    "request": {
        "super_client_name": "S-1981",
        "request_run_date": "2026-08-26",
        "parent_request_id": "6A33E04B98424C2E98741702A13BE6BE",
        "request_id": "1D781A575E0F4ADC8BBCE1FBC4E72B70",
        "task_id": "UW-7469",
        "forecast_start_date": "2027-01-01",
        "lob": "MMP",
        "app_id": "NA",
    },
    "suite": {
        "run_id": "2088075",
        "suite_category": "DFM_REGRESSION",
        "execution_status": "FAILED",
        "status": "FAIL",
        "total_count": 447,
        "success_count": 444,
        "failure_count": 3,
        "elapsed_time": "00:55:01",
        "run_user": "run.user@example.com",
    },
    "failed_queries": [
        {"run_id": "2088075", "suite_category": "DFM_REGRESSION", "test_code": "TQ104",
         "tags": "DFM_TEST",
         "test_description": "PRE-COMPUTATION BASE TABLE FOR RULES AUDIT SUITE TQ534-TQ543",
         "execution_status": "Query Statement Failed"},
        {"run_id": "2088075", "suite_category": "DFM_REGRESSION", "test_code": "TQ750",
         "tags": "DFM_OUTPUT",
         "test_description": "RBTCR_CD Logic for New Column RBTCR_CD in the Output module",
         "execution_status": "FAIL"},
        {"run_id": "2088075", "suite_category": "DFM_REGRESSION", "test_code": "TQ871",
         "tags": "DFM_OUTPUT",
         "test_description": "Checks if selected drugs have ndc11 not present in shifted table and exclusion list.",
         "execution_status": "FAIL"},
    ],
    "thresholds": [
        {"threshold_query_description": "Outlier present in COVID VACCN"},
        {"threshold_query_description": "Outlier present in FORMULARY EXCEPTION"},
    ],
}


def load_from_uc(spark, run_id: str) -> dict:
    """Pull the four report sections for a given run_id from UC tables."""
    def rows(table, where):
        return [r.asDict() for r in
                spark.sql(f"SELECT * FROM {CATALOG}.{SCHEMA}.{table} WHERE {where}").collect()]

    request = rows("dfm_request_summary", f"run_id = '{run_id}'")
    suite = rows("dfm_suite_status", f"run_id = '{run_id}'")
    return {
        "request": request[0] if request else {},
        "suite": suite[0] if suite else {},
        "failed_queries": rows("dfm_failed_queries", f"run_id = '{run_id}'"),
        "thresholds": rows("dfm_threshold_summary", f"run_id = '{run_id}'"),
    }


def render(data: dict) -> str:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    return env.get_template("report_template.html").render(**data)


def post_webhook(url: str, data: dict, report_link: str | None = None) -> None:
    """POST a compact summary card to a webhook (Teams/Slack/generic). HTTPS:443,
    no SMTP. Full HTML lives at report_link."""
    s = data["suite"]
    text = (
        f"*DFM Regression run {s.get('run_id')} — {s.get('execution_status')}*\n"
        f"Suite: {s.get('suite_category')} | "
        f"Total {s.get('total_count')} · Success {s.get('success_count')} · "
        f"Failure {s.get('failure_count')} | Elapsed {s.get('elapsed_time')}\n"
        f"Run user: {s.get('run_user')}"
    )
    if report_link:
        text += f"\nFull report: {report_link}"
    payload = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(url, data=payload,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        print(f"webhook status: {resp.status}")


if __name__ == "__main__":
    html = render(SAMPLE)
    out = TEMPLATE_DIR / "sample_report.html"
    out.write_text(html, encoding="utf-8")
    print(f"Rendered preview -> {out}")
