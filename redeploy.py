
import urllib.request, json, time

RENDER_KEY = "rnd_C7jBUGG8sEuBRvqf3U4w4YU4zWsx"
SERVICE_ID = "srv-d88vm9favr4c7396kt00"
BASE = "https://skymaxx-lead-engine.onrender.com"

log = []
def L(m): log.append(str(m)); print(m, flush=True)

# Check recent deploy status
L("=== Recent deploys ===")
req = urllib.request.Request(
    "https://api.render.com/v1/services/" + SERVICE_ID + "/deploys?limit=5",
    headers={"Authorization": "Bearer " + RENDER_KEY})
deploys = json.loads(urllib.request.urlopen(req).read())
for item in deploys[:5]:
    d = item.get("deploy", {})
    L(f"  {d.get('createdAt','')[:19]} | status: {d.get('status')} | commit: {(d.get('commit',{}).get('id','') or '')[:10]} | msg: {(d.get('commit',{}).get('message','') or '')[:60]}")

# Force a manual deploy
L("")
L("=== Triggering manual deploy ===")
req = urllib.request.Request(
    "https://api.render.com/v1/services/" + SERVICE_ID + "/deploys",
    data=json.dumps({"clearCache": "clear"}).encode(), method="POST",
    headers={"Authorization": "Bearer " + RENDER_KEY, "Content-Type": "application/json", "Accept": "application/json"})
try:
    r = urllib.request.urlopen(req)
    result = json.loads(r.read())
    L(f"  Deploy triggered: status={r.getcode()}")
    L(f"  New deploy ID: {result.get('id','?')}")
    new_deploy_id = result.get("id")
except urllib.error.HTTPError as e:
    L(f"  Deploy trigger failed: HTTP {e.code} — {e.read().decode()[:300]}")
    new_deploy_id = None

# Poll status
if new_deploy_id:
    L("")
    L("=== Polling deploy ===")
    for i in range(40):
        time.sleep(8)
        req = urllib.request.Request(
            "https://api.render.com/v1/services/" + SERVICE_ID + "/deploys/" + new_deploy_id,
            headers={"Authorization": "Bearer " + RENDER_KEY})
        d = json.loads(urllib.request.urlopen(req).read())
        L(f"  [{i+1}] status: {d.get('status')}")
        if d.get("status") in ("live", "failed", "canceled", "build_failed", "update_failed"):
            break

# Verify HTML now
L("")
L("=== Verifying live HTML now ===")
time.sleep(5)
html = urllib.request.urlopen(BASE + "/?_=" + str(int(time.time())), timeout=20).read().decode()
L(f"  HTML size: {len(html)}")
for kw in ["/static/logo.png", "goHome", "⚡ SKYMAXX", "favicon"]:
    found = kw in html
    L(f"  '{kw}': {'YES' if found else 'NO'}")

open("redeploy.txt","w").write(chr(10).join(log))
