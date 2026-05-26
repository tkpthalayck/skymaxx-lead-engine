
import urllib.request, json, time

BASE = "https://skymaxx-lead-engine.onrender.com"

log = []
def L(m): log.append(str(m)); print(m, flush=True)

def get(p, timeout=20):
    try:
        t0 = time.time()
        r = urllib.request.urlopen(BASE + p, timeout=timeout)
        et = time.time() - t0
        body = r.read().decode()
        return r.getcode(), et, body
    except urllib.error.HTTPError as e:
        return e.code, 0, e.read().decode()[:300]
    except Exception as e:
        return 0, 0, str(e)[:200]

L("=" * 60)
L("FULL ENDPOINT AUDIT — what data is loading?")
L("=" * 60)
L("")

# All the endpoints that the dashboard + other tabs depend on
endpoints = [
    ("/api/stats", "Dashboard stats"),
    ("/api/leads?per_page=5", "All Leads"),
    ("/api/sent_log?limit=5", "Sent emails"),
    ("/api/replies", "Replies"),
    ("/api/campaigns", "Campaigns"),
    ("/api/groups", "Contact Groups"),
    ("/api/sequence", "Email Sequence"),
    ("/api/settings", "Settings"),
    ("/api/linkedin/status", "Orange Slice config"),
    ("/api/business_categories", "Categories"),
    ("/api/job_titles", "Job titles"),
    ("/api/locations/countries", "Countries"),
    ("/api/locations/states/US", "US states"),
    ("/api/debug/db", "DB status"),
]

results_summary = []
for path, desc in endpoints:
    code, et, body = get(path)
    status = "OK" if code == 200 else "FAIL"
    short_body = body[:200] if isinstance(body, str) else str(body)[:200]
    L(f"  [{status:4}] HTTP {code} | {et:.2f}s | {desc:25} | {path}")
    L(f"           {short_body}")
    L("")
    results_summary.append((path, desc, code, et))

L("")
L("=" * 60)
L("SUMMARY")
L("=" * 60)
for path, desc, code, et in results_summary:
    icon = "✓" if code == 200 else "✗"
    L(f"  {icon} {code} {desc:25} {et:.2f}s  {path}")

# Now check the served HTML for the loadStats call and init flow
L("")
L("=" * 60)
L("FRONTEND INIT FLOW CHECK")
L("=" * 60)
_, _, html = get("/")
import re
# Check for the init function
for fn in ["loadStats", "init1", "init2", "DOMContentLoaded", "loadLeads", "loadCampaigns"]:
    if fn in html:
        # Find first usage context
        idx = html.find(fn)
        ctx = html[max(0,idx-30):idx+80].replace(chr(10), " ")
        L(f"  '{fn}': YES — context: {ctx[:130]}")
    else:
        L(f"  '{fn}': MISSING from served HTML!")

open("audit.txt","w").write(chr(10).join(log))
