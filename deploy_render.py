
import os, sys, json, urllib.request, urllib.error

KEY = os.environ["RENDER_API_KEY"]
MAPS_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")
ZEPTO = os.environ.get("ZEPTO_TOKEN", "")

BASE = "https://api.render.com/v1"

def api(method, path, data=None):
    url = BASE + path
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method,
        headers={"Authorization": f"Bearer {KEY}", "Accept": "application/json",
                 "Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"HTTP {e.code} on {method} {path}: {body}")
        sys.exit(1)

# 1. Get owner
print("Getting owner...")
owners = api("GET", "/owners?limit=1")
print("Owners:", json.dumps(owners)[:200])
owner_id = owners[0]["owner"]["id"]
print(f"Owner ID: {owner_id}")

# 2. List services
print("\nListing services...")
services = api("GET", "/services?limit=20")
print(f"Found {len(services)} services")

# 3. Find existing
existing = None
for s in services:
    svc = s.get("service", {})
    print(f"  - {svc.get('name')} ({svc.get('id')})")
    if svc.get("name") == "skymaxx-lead-engine":
        existing = svc
        break

if existing:
    sid = existing["id"]
    url = existing.get("serviceDetails", {}).get("url", "https://skymaxx-lead-engine.onrender.com")
    print(f"\nService exists: {sid}")
    print(f"URL: {url}")
    # Redeploy
    resp = api("POST", f"/services/{sid}/deploys", {})
    print(f"Deploy triggered: {resp.get('id','?')}")
else:
    print("\nCreating service...")
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
                {"key": "GOOGLE_MAPS_API_KEY", "value": MAPS_KEY},
                {"key": "ZEPTO_TOKEN",         "value": ZEPTO},
                {"key": "FROM_EMAIL",          "value": "support@skymaxx.company"},
                {"key": "FROM_NAME",           "value": "Ali | SKYMAXX IT Solutions"},
                {"key": "DB_PATH",             "value": "skymaxx.db"},
            ]
        }
    }
    result = api("POST", "/services", payload)
    svc = result.get("service", {})
    sid = svc.get("id", "?")
    url = svc.get("serviceDetails", {}).get("url", "https://skymaxx-lead-engine.onrender.com")
    print(f"Created: {sid}")
    print(f"URL: {url}")

# Write URL to file
with open("LIVE_URL.txt", "w") as f:
    f.write(url + "\n")
print(f"\nLIVE_URL.txt written: {url}")
