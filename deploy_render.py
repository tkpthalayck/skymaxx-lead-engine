
import os, sys, json, urllib.request, urllib.error

KEY = os.environ.get("RENDER_API_KEY", "")
print(f"API Key length: {len(KEY)}, starts: {KEY[:8]}...")

BASE = "https://api.render.com/v1"

def api(method, path, data=None):
    url = BASE + path
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method,
        headers={
            "Authorization": f"Bearer {KEY}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        })
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        raw = resp.read()
        print(f"  {method} {path} -> HTTP 200, {len(raw)} bytes")
        return json.loads(raw)
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  {method} {path} -> HTTP {e.code}: {body[:500]}")
        raise

try:
    print("\n--- Step 1: Get owners ---")
    owners = api("GET", "/owners?limit=1")
    print(f"Owners raw: {json.dumps(owners)[:300]}")
    owner_id = owners[0]["owner"]["id"]
    print(f"Owner ID: {owner_id}")

    print("\n--- Step 2: List services ---")
    services = api("GET", "/services?limit=20")
    print(f"Services count: {len(services)}")
    for s in services:
        svc = s.get("service", {})
        print(f"  {svc.get('name')} | {svc.get('id')} | {svc.get('serviceDetails',{}).get('url','?')}")

    existing = next((s["service"] for s in services
                     if s.get("service",{}).get("name") == "skymaxx-lead-engine"), None)

    if existing:
        sid = existing["id"]
        svc_url = existing.get("serviceDetails",{}).get("url","https://skymaxx-lead-engine.onrender.com")
        print(f"\nService found: {sid} -> {svc_url}")
        api("POST", f"/services/{sid}/deploys", {})
        print("Redeploy triggered")
    else:
        print("\nCreating new service...")
        MAPS = os.environ.get("GOOGLE_MAPS_API_KEY","")
        ZEPTO = os.environ.get("ZEPTO_TOKEN","")
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
        svc = result.get("service", {})
        sid = svc.get("id","?")
        svc_url = svc.get("serviceDetails",{}).get("url","https://skymaxx-lead-engine.onrender.com")
        print(f"Created: {sid} -> {svc_url}")

    with open("LIVE_URL.txt", "w") as f:
        f.write(svc_url + "\n")
    print(f"\nDone! Live URL: {svc_url}")

except Exception as e:
    import traceback
    traceback.print_exc()
    sys.exit(1)
