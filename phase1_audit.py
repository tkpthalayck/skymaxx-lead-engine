
import urllib.request, json, time, datetime as dt

BASE = "https://skymaxx-lead-engine.onrender.com"
RENDER_KEY = "rnd_C7jBUGG8sEuBRvqf3U4w4YU4zWsx"
SERVICE_ID = "srv-d88vm9favr4c7396kt00"

log = []
def L(m): log.append(str(m)); print(m, flush=True)
def sect(t): L(""); L("=" * 70); L(t); L("=" * 70)

def get(p, timeout=20):
    try:
        t0 = time.time()
        r = urllib.request.urlopen(BASE + p, timeout=timeout)
        return r.getcode(), time.time()-t0, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, 0, e.read().decode()[:600]
    except Exception as e:
        return 0, 0, "Exception: " + str(e)[:300]

# ── PHASE 1A: Application Health ──
sect("1A. APPLICATION HEALTH — basic endpoints")
endpoints = [
    "/api/stats",
    "/api/config",
    "/api/leads?per_page=20",
    "/api/campaigns",
    "/api/log",
    "/api/sequence/queue",
    "/api/groups",
    "/api/debug/db",
    "/api/linkedin/status",
]
for p in endpoints:
    code, et, body = get(p)
    short = body[:200] if code == 200 else body[:300]
    L(f"  HTTP {code} | {et:.2f}s | {p}")
    if code != 200:
        L(f"     ERROR: {short}")

# ── PHASE 1B: Detailed database state ──
sect("1B. DATABASE STATE — leads, campaigns, sequence data")
code, _, body = get("/api/debug/db")
try:
    d = json.loads(body)
    for k, v in d.items():
        L(f"  {k}: {v}")
except: L(f"  Body: {body[:400]}")

# Fetch all leads in detail
code, _, body = get("/api/leads?per_page=100")
try:
    d = json.loads(body)
    leads = d.get("leads", [])
    L(f"\n  TOTAL LEADS: {d.get(\"total\")} | retrieved: {len(leads)}")
    in_seq = [l for l in leads if l.get("in_sequence")]
    has_email = [l for l in leads if l.get("email")]
    replied = [l for l in leads if l.get("replied")]
    L(f"  In sequence: {len(in_seq)}")
    L(f"  With email:  {len(has_email)}")
    L(f"  Replied:     {len(replied)}")
    if in_seq:
        L(f"\n  Leads currently in sequence:")
        for l in in_seq[:10]:
            L(f"    id={l.get(\"id\")} | {(l.get(\"name\") or \"\")[:25]} | {(l.get(\"email\") or \"\")[:35]}")
            L(f"      campaign_id={l.get(\"campaign_id\")} | last_sent_at={l.get(\"last_sent_at\")} | current_step={l.get(\"current_step\")}")
    else:
        L(f"\n  ⚠️ NO LEADS IN SEQUENCE — campaigns may have started but failed to mark leads")
except Exception as e:
    L(f"  Err: {e}")
    L(f"  Body: {body[:400]}")

# Detailed campaigns
sect("1C. CAMPAIGNS — pending, approved, sent counts")
code, _, body = get("/api/campaigns")
try:
    d = json.loads(body)
    camps = d.get("campaigns", [])
    L(f"  Total campaigns: {len(camps)}")
    for c in camps:
        L(f"")
        L(f"  Campaign id={c.get(\"id\")}: {c.get(\"name\", \"(no name)\")[:40]}")
        L(f"    status:           {c.get(\"status\")}")
        L(f"    approved_at:      {c.get(\"approved_at\")}")
        L(f"    total_leads:      {c.get(\"total_leads\")} | actually_started: {c.get(\"actually_started\")}")
        L(f"    actually_sent:    {c.get(\"actually_sent\")} | actually_failed: {c.get(\"actually_failed\")}")
        L(f"    actually_replied: {c.get(\"actually_replied\")}")
        L(f"    created_at:       {c.get(\"created_at\")}")
except Exception as e:
    L(f"  Err: {e}")

# ── PHASE 1D: Email log details ──
sect("1D. EMAIL LOG — every send attempt")
code, _, body = get("/api/log")
try:
    d = json.loads(body)
    log_entries = d.get("log", [])
    L(f"  Total log entries: {len(log_entries)}")
    if not log_entries:
        L(f"  ⚠️ EMAIL LOG IS EMPTY — no emails have been recorded as sent OR attempted")
    else:
        for entry in log_entries[:10]:
            L(f"    {entry.get(\"sent_at\", \"\")[:19]} | step={entry.get(\"step\")} | status={entry.get(\"status\")} | {(entry.get(\"to_email\") or \"\")[:35]}")
except Exception as e:
    L(f"  Err: {e}")

# ── PHASE 1E: Sequence queue ──
sect("1E. UPCOMING SENDS — what scheduler thinks is due")
code, _, body = get("/api/sequence/queue")
try:
    d = json.loads(body)
    upc = d.get("upcoming", [])
    L(f"  Upcoming sends: {len(upc)}")
    if not upc:
        L(f"  ⚠️ NO UPCOMING SENDS scheduled — scheduler may not see any due leads")
    for u in upc[:10]:
        L(f"    {u.get(\"name\")} → step {u.get(\"next_step\")} | due: {u.get(\"due_at\")}")
except Exception as e:
    L(f"  Err: {e}")
    L(f"  Body: {body[:300]}")

# ── PHASE 1F: External service health ──
sect("1F. EXTERNAL SERVICES — Zepto, Graph, Maps")
code, _, body = get("/api/config")
try:
    d = json.loads(body)
    L(f"  Google Maps: {d.get(\"google_maps\")}")
    L(f"  Zepto Mail:  {d.get(\"zepto_mail\")}")
    L(f"  Graph API:   {d.get(\"graph_api\")}")
    L(f"  From email:  {d.get(\"from_email\")}")
    L(f"  Mailbox:     {d.get(\"mailbox\")}")
    L(f"  Daily limit: {d.get(\"daily_limit\")}")
except Exception as e:
    L(f"  Err: {e}")

# ── PHASE 1G: Render service info ──
sect("1G. RENDER SERVICE INFO + RECENT DEPLOYS")
try:
    req = urllib.request.Request(
        "https://api.render.com/v1/services/" + SERVICE_ID,
        headers={"Authorization": "Bearer " + RENDER_KEY})
    svc = json.loads(urllib.request.urlopen(req, timeout=15).read())
    L(f"  Service type:  {svc.get(\"type\")}")
    L(f"  Plan:          {svc.get(\"serviceDetails\", {}).get(\"plan\")}")
    L(f"  Region:        {svc.get(\"serviceDetails\", {}).get(\"region\")}")
    L(f"  Suspended:     {svc.get(\"suspended\")}")
    L(f"  Auto deploy:   {svc.get(\"autoDeploy\")}")
    L(f"  Updated at:    {svc.get(\"updatedAt\")}")
except Exception as e:
    L(f"  Service info err: {e}")

try:
    req = urllib.request.Request(
        "https://api.render.com/v1/services/" + SERVICE_ID + "/deploys?limit=3",
        headers={"Authorization": "Bearer " + RENDER_KEY})
    deploys = json.loads(urllib.request.urlopen(req, timeout=15).read())
    L(f"")
    L(f"  Recent deploys:")
    for item in deploys[:3]:
        d = item.get("deploy", {})
        L(f"    {d.get(\"createdAt\",\"\")[:19]} | {d.get(\"status\"):10} | {(d.get(\"commit\",{}).get(\"message\",\"\") or \"\")[:55]}")
except Exception as e:
    L(f"  Deploys err: {e}")

# ── PHASE 1H: Render logs — look for errors ──
sect("1H. RENDER APP LOGS — last 30 min, filtered for errors/scheduler activity")
try:
    end_t = int(time.time() * 1000)
    start_t = end_t - 30 * 60 * 1000
    url = "https://api.render.com/v1/logs?ownerId=tea-d88q6frbc2fs73eh5rmg&resource=" + SERVICE_ID + "&limit=200&type=app&startTime=" + str(start_t) + "&endTime=" + str(end_t)
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + RENDER_KEY, "Accept": "application/json"})
    data = json.loads(urllib.request.urlopen(req, timeout=25).read())
    entries = data.get("logs", [])
    L(f"  Total log lines (last 30 min): {len(entries)}")

    # Filter for important lines
    errors = []
    scheduler_activity = []
    email_sends = []
    crashes = []
    for e in entries:
        msg = e.get("message", "")
        ts = e.get("timestamp","")[:19]
        if any(kw in msg for kw in ["ERROR", "Error", "Traceback", "Exception", "Failed", "FATAL"]):
            errors.append(f"  {ts} | {msg[:280]}")
        if any(kw in msg for kw in ["scheduler", "Scheduler", "[cron]", "[scheduler]", "[sequence]", "process_sequence", "send_next_email"]):
            scheduler_activity.append(f"  {ts} | {msg[:280]}")
        if any(kw in msg for kw in ["[send]", "[zepto]", "ZeptoMail", "sent successfully", "mail_send"]):
            email_sends.append(f"  {ts} | {msg[:280]}")
        if "killed" in msg.lower() or "out of memory" in msg.lower() or "worker" in msg.lower():
            crashes.append(f"  {ts} | {msg[:280]}")

    L("")
    L(f"  📛 ERRORS / EXCEPTIONS ({len(errors)}):")
    for e in errors[-15:]:
        L(e)

    L("")
    L(f"  ⏰ SCHEDULER ACTIVITY ({len(scheduler_activity)}):")
    for s in scheduler_activity[-15:]:
        L(s)

    L("")
    L(f"  📧 EMAIL SENDS ({len(email_sends)}):")
    for s in email_sends[-15:]:
        L(s)

    L("")
    L(f"  💀 CRASHES/WORKERS ({len(crashes)}):")
    for c in crashes[-10:]:
        L(c)

    # Most recent activity
    L("")
    L(f"  📋 LAST 10 LINES:")
    for e in entries[-10:]:
        L(f"    {e.get(\"timestamp\",\"\")[:19]} | {e.get(\"message\",\"\")[:240]}")

except Exception as e:
    L(f"  Logs error: " + str(e))

open("phase1.txt","w").write(chr(10).join(log))
print("\n=== Wrote phase1.txt ({} lines) ===".format(len(log)))
