
import urllib.request, json, time

RENDER_KEY = "rnd_C7jBUGG8sEuBRvqf3U4w4YU4zWsx"
SERVICE_ID = "srv-d88vm9favr4c7396kt00"
BASE = "https://skymaxx-lead-engine.onrender.com"

log = []
def L(m): log.append(str(m)); print(m, flush=True)

# 1. Test the REAL frontend endpoints
L("=== REAL endpoints frontend calls ===")
for path in ["/api/stats", "/api/log", "/api/config", "/api/sequence/queue", "/api/leads?per_page=5"]:
    try:
        r = urllib.request.urlopen(BASE + path, timeout=15)
        body = r.read().decode()
        L(f"  [OK ] HTTP {r.getcode()} | {path}")
        L(f"        {body[:200]}")
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:400]
        L(f"  [ERR] HTTP {e.code} | {path}")
        L(f"        {body}")
    L("")

# 2. Render logs — get the actual stack trace for stats
L("=== Render app logs (last 5 min) ===")
end_t = int(time.time() * 1000)
start_t = end_t - 5 * 60 * 1000
url = "https://api.render.com/v1/logs?ownerId=tea-d88q6frbc2fs73eh5rmg&resource=" + SERVICE_ID + "&limit=120&type=app&startTime=" + str(start_t) + "&endTime=" + str(end_t)

try:
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + RENDER_KEY, "Accept": "application/json"})
    data = json.loads(urllib.request.urlopen(req, timeout=20).read())
    # Filter for error/stack-trace lines
    relevant = []
    for entry in data.get("logs", []):
        msg = entry.get("message", "")
        if any(kw in msg for kw in ["Error", "error", "Traceback", "Exception", "stats", "500", "psycopg", "FATAL", "ERROR"]):
            relevant.append(entry.get("timestamp","")[:19] + " | " + msg[:300])
    for line in relevant[-30:]:
        L("  " + line)
except Exception as e:
    L("  Logs error: " + str(e))

# 3. Trigger the stats endpoint to generate a fresh stack trace, then read logs
L("")
L("=== Triggering /api/stats to capture fresh stack trace ===")
try:
    urllib.request.urlopen(BASE + "/api/stats?cache_bust=" + str(int(time.time())), timeout=10)
except: pass
time.sleep(4)

end_t = int(time.time() * 1000)
start_t = end_t - 30 * 1000
url = "https://api.render.com/v1/logs?ownerId=tea-d88q6frbc2fs73eh5rmg&resource=" + SERVICE_ID + "&limit=60&type=app&startTime=" + str(start_t) + "&endTime=" + str(end_t)
try:
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + RENDER_KEY, "Accept": "application/json"})
    data = json.loads(urllib.request.urlopen(req, timeout=20).read())
    L("Recent logs (last 30s):")
    for entry in data.get("logs", []):
        msg = entry.get("message", "")
        # Drop health-check noise
        if "GET /api/leads" in msg and "200" in msg: continue
        L("  " + entry.get("timestamp","")[:19] + " | " + msg[:280])
except Exception as e:
    L("  Logs2 error: " + str(e))

open("stats_debug.txt","w").write(chr(10).join(log))
