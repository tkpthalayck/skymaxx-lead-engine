import os, sys, json, urllib.request, urllib.error

KEY  = os.environ.get("RENDER_API_KEY", "")
MAPS = os.environ.get("GOOGLE_MAPS_API_KEY", "")
ZEPTO= os.environ.get("ZEPTO_TOKEN", "")
BASE = "https://api.render.com/v1"
HDR  = {"Authorization": "Bearer " + KEY,
        "Accept": "application/json",
        "Content-Type": "application/json"}

log = []
def p(msg): s = str(msg); print(s, flush=True); log.append(s)

def api(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req  = urllib.request.Request(BASE + path, data=data, method=method, headers=HDR)
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        result = json.loads(resp.read())
        p("OK " + method + " " + path)
        return result
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        p("ERR " + method + " " + path + " HTTP " + str(e.code) + ": " + err[:300])
        raise

url = "https://skymaxx-lead-engine.onrender.com"
try:
    p("key_len=" + str(len(KEY)))
    owners = api("GET", "/owners?limit=1")
    p("owners=" + json.dumps(owners)[:200])
    owner_id = owners[0]["owner"]["id"]
    p("owner_id=" + owner_id)

    services = api("GET", "/services?limit=20")
    p("services_count=" + str(len(services)))

    existing = None
    for s in services:
        svc = s.get("service", {})
        p("svc=" + svc.get("name","?") + " " + svc.get("id","?"))
        if svc.get("name") == "skymaxx-lead-engine":
            existing = svc

    if existing:
        sid = existing["id"]
        url = existing.get("serviceDetails", {}).get("url", url)
        p("found=" + sid + " url=" + url)
        r = api("POST", "/services/" + sid + "/deploys", {})
        p("deploy_id=" + r.get("id", "?"))
    else:
        p("creating service...")
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
                    {"key": "FROM_EMAIL",          "value": "support@skymaxx.company"},
                    {"key": "FROM_NAME",           "value": "Ali | SKYMAXX IT Solutions"},
                    {"key": "DB_PATH",             "value": "skymaxx.db"},
                ]
            }
        }
        result = api("POST", "/services", payload)
        p("create_result=" + json.dumps(result)[:400])
        svc = result.get("service", {})
        url = svc.get("serviceDetails", {}).get("url", url)
        p("created url=" + url)

    p("LIVE_URL=" + url)

except Exception as exc:
    import traceback
    p("EXCEPTION: " + traceback.format_exc())

# Always write output files
with open("deploy_debug.txt", "w") as f:
    f.write("\n".join(log))
with open("LIVE_URL.txt", "w") as f:
    f.write(url + "\n")
p("Files written.")
