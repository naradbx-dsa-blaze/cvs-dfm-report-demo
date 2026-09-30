# Reference — External email API (NOT CVS-approved)

> ⚠️ **Reference only.** External email providers (Microsoft Graph, Amazon SES, Resend)
> were **not approved for CVS**. Kept here because it's the *only* way to put the **exact,
> clean, bordered HTML** into the email **body** — it sends over HTTPS:443 (no SMTP port
> whitelist), but it does call an external service, which is the disqualifier for CVS.

`dfm_report_email_job.py` renders the exact report and sends it as the HTML email body via
a pluggable provider (`provider` = `resend` | `graph` | `ses`). Credentials come from a
Databricks secret scope; `dry_run=true` prints the exact request without sending.

- `jobs/job_email.json` — the email job spec
- `jobs/job_email_update.json` — reset payload used to repoint the job at a provider

For a CVS-approved path, use `approaches/01-sql-alerts/` (native email, borders stripped)
or `approaches/02-aibi-api/` (native rendered snapshot, borders preserved).
