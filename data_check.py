import urllib.request, json
BASE = "https://skymaxx-lead-engine.onrender.com"

def get(p):
    try:
        r = urllib.request.urlopen(BASE+p, timeout=30)
        return r.getcode(), json.loads(r.read().decode())
    except Exception as e:
        return 0, str(e)[:200]

log = []
log.append("=== DATA STATE INVESTIGATION ===")
log.append("")

# Check stats
code, r = get("/api/stats")
log.append(f"/api/stats: HTTP {code}")
if code == 200:
    log.append(f"  Total leads:     {r.get("total_leads")}")
    log.append(f"  Total sent:      {r.get("total_sent")}")
    log.append(f"  Total replied:   {r.get("total_replied")}")
    log.append(f"  Failed:          {r.get("total_failed")}")
    log.append(f"  In sequence:     {r.get("in_sequence")}")
    log.append(f"  Pending sends:   {r.get("pending_today")}")
log.append("")

# Check email_log
code, r = get("/api/log")
log.append(f"/api/log: HTTP {code}")
if code == 200:
    logs = r.get("log", []) if isinstance(r, dict) else r if isinstance(r, list) else []
    log.append(f"  Total sent emails in DB: {len(logs)}")
    if logs:
        for e in logs[:5]:
            log.append(f"  - id={e.get("id")} to={e.get("to_email","")[:30]} step={e.get("step")} status={e.get("status")} at={e.get("sent_at","")[:19]}")
log.append("")

# Check leads
code, r = get("/api/leads")
log.append(f"/api/leads: HTTP {code}")
if code == 200:
    leads = r.get("leads", []) if isinstance(r, dict) else []
    total = r.get("total", 0) if isinstance(r, dict) else 0
    log.append(f"  Total leads in DB: {total}")
    if leads:
        log.append(f"  First 5:")
        for l in leads[:5]:
            log.append(f"  - id={l.get("id")} {l.get("name","")[:30]} {l.get("email","")[:30]} step={l.get("sequence_step")} source={l.get("source","?")}")
log.append("")

# Check campaigns
code, r = get("/api/campaigns")
log.append(f"/api/campaigns: HTTP {code}")
if code == 200:
    cs = r.get("campaigns", []) if isinstance(r, dict) else []
    log.append(f"  Total campaigns: {len(cs)}")
    for c in cs[:5]:
        log.append(f"  - id={c.get("id")} {c.get("name","")[:30]} status={c.get("status")} recipients={c.get("recipient_count")}")

# Check disk situation (the smoking gun)
code, r = get("/api/config")
log.append("")
log.append("=== Configuration ===")
if code == 200:
    log.append(f"  Domain: {r.get("domain","?")}")
    log.append(f"  From email: {r.get("from_email","?")}")

with open("data_check.txt","w") as f: f.write(chr(10).join(log))
print(chr(10).join(log))
