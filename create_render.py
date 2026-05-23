import os, json, urllib.request, urllib.error, time

KEY   = os.environ.get("RENDER_API_KEY", "")
MAPS  = os.environ.get("GOOGLE_MAPS_API_KEY", "")
ZEPTO = os.environ.get("ZEPTO_TOKEN", "")
BASE  = "https://api.render.com/v1"
HDR   = {"Authorization": "Bearer " + KEY, "Accept": "application/json", "Content-Type": "application/json"}

log = []
def p(msg): s = str(msg); print(s, flush=True); log.append(s)

def api(method, path, body=None, retries=2):
    data = json.dumps(body).encode() if body is not None else None
    for attempt in range(retries):
        req = urllib.request.Request(BASE + path, data=data, method=method, headers=HDR)
        try:
            resp = urllib.request.urlopen(req, timeout=30)
            return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            err = e.read().decode()
            p(f"ERR {method} {path} HTTP {e.code} attempt {attempt+1}: {err[:200]}")
            if e.code == 429 and attempt < retries-1:
                time.sleep(60 * (attempt + 1))
            else:
                raise
    raise Exception("retries exhausted")

url = "https://skymaxx-lead-engine.onrender.com"
try:
    p(f"key_len={len(KEY)}")
    owners = api("GET", "/owners?limit=1")
    owner_id = owners[0]["owner"]["id"]
    p(f"owner_id={owner_id}")
    services = api("GET", "/services?limit=20")
    p(f"services_count={len(services)}")

    existing = None
    for s in services:
        svc = s.get("service", {})
        if svc.get("name") == "skymaxx-lead-engine":
            existing = svc

    if existing:
        sid = existing["id"]
        url = existing.get("serviceDetails", {}).get("url", url)
        p(f"EXISTS! sid={sid} url={url}")
        suspended = existing.get("suspended", "?")
        p(f"suspended={suspended}")
        deploys = api("GET", f"/services/{sid}/deploys?limit=3")
        for d in deploys:
            dep = d.get("deploy", {})
            p(f"  deploy: status={dep.get('status')} created={dep.get('createdAt')}")
    else:
        p("Service does NOT exist - attempting to create...")
        payload = {
            "type": "web_service",
            "name": "skymaxx-lead-engine",
            "ownerId": owner_id,
            "repo": "https://github.com/tkpthalayck/skymaxx-lead-engine",
            "branch": "main",
            "autoDeploy": "yes",
            "serviceDetails": {
                "runtime": "python",
                "buildCommand": "pip install -r requirements.txt",
                "startCommand": "gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120",
                "plan": "free",
                "region": "oregon",
                "envVars": [
                    {"key": "GOOGLE_MAPS_API_KEY", "value": MAPS},
                    {"key": "ZEPTO_TOKEN",         "value": ZEPTO},
                    {"key": "FROM_EMAIL",          "value": "noreply@skymaxx.company"},
                    {"key": "FROM_NAME",           "value": "Ali | SKYMAXX IT Solutions"},
                    {"key": "DB_PATH",             "value": "skymaxx.db"},
                ]
            }
        }
        result = api("POST", "/services", payload)
        svc = result.get("service", {})
        sid = svc.get("id", "?")
        url = svc.get("serviceDetails", {}).get("url", url)
        p(f"CREATED! sid={sid} url={url}")

except Exception as e:
    import traceback
    p(f"EXCEPTION: {traceback.format_exc()}")

with open("deploy_debug.txt", "w") as f: f.write("\n".join(log))
with open("LIVE_URL.txt", "w") as f: f.write(url + "\n")
