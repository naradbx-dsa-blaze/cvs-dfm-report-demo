# Reference — Webhook notification

Serverless, table-triggered job that renders the exact report to a UC volume and **POSTs
a summary card to a webhook** (Teams / Slack / generic) over HTTPS:443 — no SMTP. The
card links to the governed full report.

Kept as reference: it's a native, no-SMTP notification path, but the headline delivery
approaches for this repo are SQL Alerts (`approaches/01-sql-alerts/`) and AI/BI
(`approaches/02-aibi-api/`).

- `dfm_report_job.py` — render + webhook notebook (widgets: `webhook_url`, `webhook_format` = slack|teams|generic, `run_id`)
- `jobs/job.json` — serverless job with a table-update trigger on `dfm_suite_status`

Blank `webhook_url` = dry run (writes the HTML report, prints the card preview).
