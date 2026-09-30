"""
AI/BI approach — publish the dashboard and set up the emailed snapshot.

Publishes the dashboard (required for snapshot rendering), creates a schedule, and
subscribes stakeholders. Databricks then emails a rendered PDF/PNG snapshot — clean
borders preserved, no SMTP, no external provider.

    python3 approaches/02-aibi-api/setup_subscription.py <dashboard_id>
"""
import json
import subprocess
import sys

PROFILE = "e2-demo-field-eng"
WAREHOUSE_ID = "6674ed0664e1e8a3"
TZ = "America/New_York"

# ─────────────────────────────────────────────────────────────────────────────
# RECIPIENTS — subscribe individual users and/or a GROUP email.
#
#   Individual workspace users → user_id:
SUBSCRIBER_USER_IDS = [3224745028999881]        # narasimha.kamathardi@databricks.com
#
#   GROUP / distribution-list email → a notification destination id.
#   A workspace admin creates an EMAIL destination holding the group address
#   (Settings > Notifications, or `databricks notification-destinations create`),
#   then put its id here. The SAME destination_id also works for the SQL alert
#   (approach 01). List existing ones:  databricks notification-destinations list
SUBSCRIBER_DESTINATION_IDS = []                 # e.g. ["00c243ad-88cb-4fc9-93f2-23cd4b337e6b"]
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# SCHEDULING OPTIONS  — Lakeview subscriptions are CRON-DRIVEN. Pick exactly ONE.
# Quartz cron format:  <sec> <min> <hour> <day-of-month> <month> <day-of-week>
#
#   ONE-TIME (demo)       "0 55 14 * * ?"    fires once at 14:55 local time, then
#                                            DELETE the schedule so it doesn't repeat
#                                            daily (teardown command printed below)
#   Every 15 minutes      "0 0/15 * * * ?"
#   Hourly (top of hour)  "0 0 * * * ?"
#   Daily at 07:00        "0 0 7 * * ?"
#   Weekdays at 07:00     "0 0 7 ? * MON-FRI"
#   Weekly Mon at 07:00   "0 0 7 ? * MON"
#
# NOTE: there is NO "on table change" trigger for subscriptions — cron only. For
# instant, event-driven delivery, pair this with the SQL alert (../01-sql-alerts/).
# ─────────────────────────────────────────────────────────────────────────────
CRON = "0 55 14 * * ?"   # ONE-TIME demo default — swap for a recurring option above

DASH = sys.argv[1] if len(sys.argv) > 1 else "01f1bcff3a2e143eb7910e6ca3d8a865"


def lv(*args):
    p = subprocess.run(["databricks", "lakeview", *args, "--profile", PROFILE],
                       capture_output=True, text=True)
    if p.returncode != 0:
        print("ERROR:", p.stderr.strip()[-500:]); sys.exit(1)
    out = p.stdout[p.stdout.find("{"):] if "{" in p.stdout else "{}"
    return json.loads(out) if out.strip() else {}


lv("publish", DASH, "--warehouse-id", WAREHOUSE_ID, "--embed-credentials")
print("published:", DASH)

sched = lv("create-schedule", DASH, "--json", json.dumps({
    "cron_schedule": {"quartz_cron_expression": CRON, "timezone_id": TZ},
    "warehouse_id": WAREHOUSE_ID, "display_name": "dfm-report-schedule"}))
schedule_id = sched["schedule_id"]
print("schedule_id:", schedule_id, "| cron:", CRON, TZ)

for uid in SUBSCRIBER_USER_IDS:
    sub = lv("create-subscription", DASH, schedule_id, "--json", json.dumps({
        "subscriber": {"user_subscriber": {"user_id": uid}}}))
    print("subscription_id:", sub["subscription_id"], "-> user", uid)

for dest_id in SUBSCRIBER_DESTINATION_IDS:  # group / distribution-list email
    sub = lv("create-subscription", DASH, schedule_id, "--json", json.dumps({
        "subscriber": {"destination_subscriber": {"destination_id": dest_id}}}))
    print("subscription_id:", sub["subscription_id"], "-> destination", dest_id)

# For a TRUE one-time send, delete the schedule after the email arrives so it does not
# repeat at the same time tomorrow:
print(f"\nTeardown (run after the one email arrives, for a true one-time send):")
print(f"  databricks lakeview delete-schedule {DASH} {schedule_id} --profile {PROFILE}")
print("\nKeep the dashboard unshared to keep it 'hidden' — subscribers get the email, "
      "not dashboard access.")
