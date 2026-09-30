# Approach 02 — AI/BI (Dashboard + Subscription)

> **Status: built.** Delivers the report as a **clean, rendered snapshot** (PDF/PNG)
> emailed on a schedule via an AI/BI dashboard subscription — fully Databricks-native.
> Because the email carries a *rendered image*, **the table borders survive** (unlike the
> SQL-alert path, where the sanitizer strips them).

## How it works

```
dfm_* tables ──> hidden AI/BI dashboard (4 table widgets, live "latest run" queries)
                      │
                      ▼  cron schedule + subscription (Lakeview API)
             Databricks emails a rendered PDF/PNG snapshot ──> stakeholders
```

- **Dashboard** `CVS DFM Regression Report - AIBI` (`01f1bcff3a2e143eb7910e6ca3d8a865`) — 4 table widgets = the 4 report sections, each querying `WHERE run_id = (SELECT MAX(run_id) …)` so it always shows the latest run. **Dynamic** by construction.
- **Schedule** — cron-driven. `setup_subscription.py` defaults to a **one-time** fire and documents multiple options in-code (15 min / hourly / daily / weekdays / weekly). Swap the `CRON` constant to change cadence.
- **Subscription** — stakeholder inbox; Databricks renders + emails the snapshot.
- **True one-time:** delete the schedule after the single email arrives (teardown command is printed by the script) so it doesn't repeat.
- **Hidden** — the dashboard is published only so the schedule can render it; it isn't shared with stakeholders. They receive the email, not dashboard access.

## Setup

```bash
python3 ../../common/setup_uc.py     # source tables + volume (run once)
python3 build_dashboard.py           # create + deploy the dashboard
python3 setup_subscription.py <dashboard_id>   # publish + schedule + subscribe
```

## ✅ What you get / ⚠️ what you don't

- ✅ **Clean, bordered tables** — it's a rendered snapshot, not sanitized HTML.
- ✅ **Dynamic** — always reflects the latest run in the tables.
- ✅ **Native** — no SMTP, no external provider; Databricks sends it.
- ⚠️ **Scheduled, not event-driven.** The Lakeview API only offers cron schedules — there
  is **no "send on table change" trigger**. A frequent cron makes it *near-real-time*, but
  it is not literally "the instant the table changes." (Demo default is one-time.)

## Pairing for instant + clean
Want both instant notification *and* the clean report? Pair the two approaches:
- **SQL Alert** (`../01-sql-alerts/`) fires the *instant* the table changes ("failures detected") — event-driven.
- **This AI/BI subscription** carries the *clean, formatted* snapshot on its schedule.

That combination is the closest native answer to "clean + dynamic + pushed on change."

## Files
- `build_dashboard.py` — builds + deploys the 4-section dashboard
- `setup_subscription.py` — publish + cron schedule + subscription
