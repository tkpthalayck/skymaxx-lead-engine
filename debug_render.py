
import urllib.request, json, time

BASE = "https://skymaxx-lead-engine.onrender.com"
RENDER_KEY = "rnd_C7jBUGG8sEuBRvqf3U4w4YU4zWsx"
SERVICE_ID = "srv-d88vm9favr4c7396kt00"

log = []
def L(m): log.append(str(m)); print(m, flush=True)

# 1. Get recent app logs
L("=== Recent app logs ===")
end_t = int(time.time() * 1000)
start_t = end_t - 600 * 1000  # last 10 min
req = urllib.request.Request(
    "https://api.render.com/v1/logs?ownerId=tea-d88q6frbc2fs73eh5rmg&resource=" + SERVICE_ID + "&limit=80&type=app&startTime=" + str(start_t) + "&endTime=" + str(end_t),
    headers={"Authorization": "Bearer " + RENDER_KEY, "Accept": "application/json"})
try:
    data = json.loads(urllib.request.urlopen(req, timeout=30).read())
    for entry in data.get("logs", [])[-50:]:
        msg = entry.get("message","")
        # Filter out healthchecks
        if "GET /api/leads" in msg and "200" in msg: continue
        if "GET /static/" in msg: continue
        L(entry.get("timestamp","")[:19] + " | " + msg[:240])
except Exception as e:
    L("Logs error: " + str(e))

# 2. Try a fast test against the endpoint with timing
L("")
L("=== Endpoint timing tests ===")

import time as t
def timed_post(path, body, timeout=35):
    start = t.time()
    try:
        req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
            headers={"Content-Type":"application/json"}, method="POST")
        r = urllib.request.urlopen(req, timeout=timeout)
        elapsed = t.time() - start
        return r.getcode(), elapsed, r.read().decode()[:500]
    except urllib.error.HTTPError as e:
        elapsed = t.time() - start
        return e.code, elapsed, e.read().decode()[:500]
    except Exception as e:
        elapsed = t.time() - start
        return 0, elapsed, str(e)[:300]

# Fastest possible Google Maps query
L("--- GMaps quick: AE hotel ---")
code, et, body = timed_post("/api/search/v2/preview", {
    "source": "google_maps", "country": "AE", "category": "hotel"
}, timeout=40)
L(f"  HTTP {code} in {et:.1f}s")
L(f"  Body: {body[:400]}")

L("")
L("--- Orange Slice quick: IT Manager UAE limit=3 ---")
code, et, body = timed_post("/api/search/v2/preview", {
    "source": "orange_slice", "country": "United Arab Emirates",
    "title": "IT Manager", "limit": 3
}, timeout=40)
L(f"  HTTP {code} in {et:.1f}s")
L(f"  Body: {body[:400]}")

open("debug.txt","w").write(chr(10).join(log))
