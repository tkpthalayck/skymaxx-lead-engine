
import urllib.request, json, time

RENDER_KEY = "rnd_C7jBUGG8sEuBRvqf3U4w4YU4zWsx"
SERVICE_ID = "srv-d88vm9favr4c7396kt00"
HEADERS = {"Authorization": "Bearer " + RENDER_KEY}

log = []
def L(m): log.append(m); print(m, flush=True)

L("=== RENDER LOG INVESTIGATION ===")
L("")

# Wait for any in-progress deploy
L("Waiting 60s for any in-progress deploy...")
time.sleep(60)

# Get the latest live deploy
req = urllib.request.Request("https://api.render.com/v1/services/" + SERVICE_ID + "/deploys?limit=5", headers=HEADERS)
try:
    deploys = json.loads(urllib.request.urlopen(req, timeout=30).read())
    live_deploy = None
    for d in deploys:
        dd = d.get("deploy", {})
        if dd.get("status") == "live":
            live_deploy = dd
            break
    if live_deploy:
        L("Latest live deploy: " + live_deploy.get("id",""))
        L("  Commit: " + live_deploy.get("commit",{}).get("message","")[:100])
    else:
        L("No live deploy found")
except Exception as e:
    L("Error: " + str(e))

# Get the logs URL for the deploy
L("")
L("Fetching service logs...")
# Render API: GET /logs
end_time = int(time.time())
start_time = end_time - 600  # last 10 minutes

# Use the logs API
import urllib.parse
params = urllib.parse.urlencode({
    "ownerId": "tea-d88q6frbc2fs73eh5rmg",
    "resource": SERVICE_ID,
    "limit": 100,
})
req = urllib.request.Request("https://api.render.com/v1/logs?" + params, headers=HEADERS)
try:
    r = urllib.request.urlopen(req, timeout=30)
    code = r.getcode()
    body = r.read().decode()
    L("HTTP " + str(code))
    try:
        data = json.loads(body)
        logs = data.get("logs", []) if isinstance(data, dict) else []
        L("Got " + str(len(logs)) + " log entries")
        # Show last 40, filter for interesting ones
        for entry in logs[-50:]:
            msg = entry.get("message", "")
            ts = entry.get("timestamp", "")[:19]
            # Show interesting lines
            if any(k in msg for k in ["init_pg", "POSTGRES", "psycopg", "Error", "Traceback", "leads", "leadcount", "imported", "database"]):
                L("  [" + ts + "] " + msg[:250])
    except Exception as ex:
        L("Parse error: " + str(ex))
        L("Body sample: " + body[:500])
except urllib.error.HTTPError as e:
    L("HTTP error " + str(e.code) + ": " + e.read().decode()[:300])
except Exception as e:
    L("Error: " + str(e))

# Check app endpoint
L("")
L("Live app check:")
try:
    r = urllib.request.urlopen("https://skymaxx-lead-engine.onrender.com/api/leads?per_page=20", timeout=30)
    d = json.loads(r.read().decode())
    L("  Total: " + str(d.get("total", 0)))
    L("  Leads visible: " + str(len(d.get("leads", []))))
    for l in d.get("leads", [])[:3]:
        L("  - id=" + str(l.get("id")) + " " + str(l.get("name",""))[:25])
except Exception as e:
    L("  Error: " + str(e))

open("logs.txt","w").write(chr(10).join(log))
