import os, json, urllib.request, urllib.error, time

KEY = os.environ.get("RENDER_API_KEY", "")
HDR = {"Authorization": "Bearer " + KEY, "Accept": "application/json"}

log = []
def p(msg): s = str(msg); print(s, flush=True); log.append(s)

# 1. List Render services
p("=== Render Services ===")
try:
    req = urllib.request.Request("https://api.render.com/v1/services?limit=10", headers=HDR)
    resp = urllib.request.urlopen(req, timeout=30)
    services = json.loads(resp.read())
    p("Total services: " + str(len(services)))
    target_url = None
    target_id = None
    for s in services:
        svc = s.get("service", {})
        name = svc.get("name", "?")
        sid  = svc.get("id", "?")
        url  = svc.get("serviceDetails", {}).get("url", "no-url")
        suspended = svc.get("suspended", "?")
        p("  - " + name + " | " + sid + " | " + url + " | suspended=" + suspended)
        if name == "skymaxx-lead-engine":
            target_url = url
            target_id = sid
except Exception as e:
    p("Render API error: " + str(e))

# 2. Check deploy status of our service
if target_id:
    p("\n=== Latest Deploy Status ===")
    try:
        req = urllib.request.Request(
            "https://api.render.com/v1/services/" + target_id + "/deploys?limit=1",
            headers=HDR)
        resp = urllib.request.urlopen(req, timeout=30)
        deploys = json.loads(resp.read())
        for d in deploys:
            dep = d.get("deploy", {})
            p("  Status: " + str(dep.get("status","?")))
            p("  Created: " + str(dep.get("createdAt","?")))
            p("  Finished: " + str(dep.get("finishedAt","?")))
            p("  Commit: " + str(dep.get("commit",{}).get("message","?"))[:80])
    except Exception as e:
        p("Deploy check error: " + str(e))

# 3. Ping the live URL
if target_url:
    p("\n=== Pinging Live URL: " + target_url + " ===")
    for attempt in range(3):
        try:
            req = urllib.request.Request(target_url, headers={"User-Agent": "SKYMAXX-Health-Check"})
            resp = urllib.request.urlopen(req, timeout=30)
            code = resp.getcode()
            body = resp.read()[:300].decode("utf-8", errors="replace")
            p("Attempt " + str(attempt+1) + ": HTTP " + str(code) + " | " + str(len(body)) + " bytes")
            p("Body preview: " + body[:200])
            break
        except urllib.error.HTTPError as e:
            p("Attempt " + str(attempt+1) + ": HTTP " + str(e.code) + " " + e.reason)
            if attempt < 2:
                time.sleep(10)
        except Exception as e:
            p("Attempt " + str(attempt+1) + ": ERROR " + str(e))
            if attempt < 2:
                time.sleep(10)

# 4. Test API endpoint
if target_url:
    p("\n=== Testing /api/stats endpoint ===")
    try:
        req = urllib.request.Request(target_url + "/api/stats")
        resp = urllib.request.urlopen(req, timeout=30)
        body = resp.read().decode()
        p("HTTP " + str(resp.getcode()) + " | " + body[:300])
    except Exception as e:
        p("API test error: " + str(e))

with open("deploy_debug.txt", "w") as f:
    f.write("\n".join(log))
with open("LIVE_URL.txt", "w") as f:
    f.write((target_url or "https://skymaxx-lead-engine.onrender.com") + "\n")
p("Done.")
