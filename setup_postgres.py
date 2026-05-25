
import urllib.request, json, time, os

RENDER_KEY = "rnd_C7jBUGG8sEuBRvqf3U4w4YU4zWsx"
WEB_SERVICE_ID = "srv-d88vm9favr4c7396kt00"
HEADERS = {
    "Authorization": "Bearer " + RENDER_KEY,
    "Content-Type": "application/json",
    "Accept": "application/json",
}

def render_api(method, path, body=None):
    url = "https://api.render.com" + path
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=HEADERS, method=method)
    try:
        r = urllib.request.urlopen(req, timeout=60)
        return r.getcode(), json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try: body = json.loads(e.read().decode())
        except: body = {"raw": str(e)}
        return e.code, body
    except Exception as e:
        return 0, {"error": str(e)}

log = []
def L(msg): log.append(msg); print(msg, flush=True)

L("=== RENDER POSTGRES SETUP ===")
L("")

# Get owner ID from service
L("1. Getting Render account/owner ID...")
code, svc = render_api("GET", "/v1/services/" + WEB_SERVICE_ID)
if code != 200:
    L("   ERROR fetching service: " + str(svc))
    open("setup_log.txt","w").write(chr(10).join(log)); raise SystemExit(1)
owner_id = svc.get("ownerId", "")
L("   Owner ID: " + owner_id)

# Check if a Postgres DB already exists  
L("")
L("2. Checking for existing Postgres databases...")
code, dbs = render_api("GET", "/v1/postgres?limit=20")
existing = None
if code == 200:
    for item in dbs:
        p = item.get("postgres", {})
        if "skymaxx" in p.get("name", "").lower():
            existing = p
            L("   Found existing DB: " + p.get("name", "") + " (status: " + p.get("status", "?") + ")")
            break

if existing:
    db_id = existing["id"]
    L("   Reusing existing database: " + db_id)
else:
    # Create new Postgres DB
    L("")
    L("3. Creating new free Postgres database...")
    db_config = {
        "name":            "skymaxx-db",
        "databaseName":    "skymaxx",
        "databaseUser":    "skymaxx_user",
        "plan":            "free",
        "region":          "oregon",  # Same region as the web service
        "version":         "16",
        "ownerId":         owner_id,
    }
    code, db = render_api("POST", "/v1/postgres", db_config)
    if code not in (200, 201):
        L("   ERROR creating DB: " + str(db))
        open("setup_log.txt","w").write(chr(10).join(log)); raise SystemExit(1)
    db_id = db.get("id", "")
    L("   Created DB: " + db_id)
    L("   Plan: free | Region: oregon | Version: 16")

# Wait for it to be available
L("")
L("4. Waiting for database to become available...")
for attempt in range(30):  # up to 5 minutes
    code, db = render_api("GET", "/v1/postgres/" + db_id)
    status = db.get("status", "unknown") if code == 200 else "error"
    L("   [" + str(attempt+1) + "] status: " + status)
    if status == "available":
        break
    time.sleep(10)

if status != "available":
    L("   ERROR: DB did not become available in time. Last status: " + status)
    open("setup_log.txt","w").write(chr(10).join(log)); raise SystemExit(1)

# Get connection info
L("")
L("5. Fetching connection info...")
code, conn_info = render_api("GET", "/v1/postgres/" + db_id + "/connection-info")
if code != 200:
    L("   ERROR: " + str(conn_info))
    open("setup_log.txt","w").write(chr(10).join(log)); raise SystemExit(1)

# Render Postgres returns multiple URLs
internal_url = conn_info.get("internalConnectionString", "")
external_url = conn_info.get("externalConnectionString", "")
L("   Internal URL available: " + str(bool(internal_url)))
L("   External URL available: " + str(bool(external_url)))

# Prefer internal (same datacenter, faster, no public exposure)
DATABASE_URL = internal_url or external_url
if not DATABASE_URL:
    L("   ERROR: No connection string in response")
    L("   Response keys: " + ", ".join(conn_info.keys()))
    open("setup_log.txt","w").write(chr(10).join(log)); raise SystemExit(1)

L("   Using: " + ("INTERNAL" if internal_url else "EXTERNAL"))
L("   Connection: " + DATABASE_URL[:50] + "...")

# Set DATABASE_URL env var on the web service
L("")
L("6. Setting DATABASE_URL env var on web service...")
# Get existing env vars first
code, env_vars = render_api("GET", "/v1/services/" + WEB_SERVICE_ID + "/env-vars?limit=100")
if code != 200:
    L("   ERROR fetching env vars: " + str(env_vars))
    open("setup_log.txt","w").write(chr(10).join(log)); raise SystemExit(1)

# Build new env var list (preserve existing, set DATABASE_URL)
new_env = []
for item in env_vars:
    e = item.get("envVar", {})
    if e.get("key") and e.get("key") != "DATABASE_URL":
        new_env.append({"key": e["key"], "value": e["value"]})
new_env.append({"key": "DATABASE_URL", "value": DATABASE_URL})

code, result = render_api("PUT", "/v1/services/" + WEB_SERVICE_ID + "/env-vars", new_env)
if code not in (200, 201):
    L("   ERROR setting env vars: " + str(result))
    open("setup_log.txt","w").write(chr(10).join(log)); raise SystemExit(1)
L("   ✓ DATABASE_URL set (" + str(len(new_env)) + " total env vars)")

# Trigger a redeploy
L("")
L("7. Triggering redeploy with new DATABASE_URL...")
code, deploy = render_api("POST", "/v1/services/" + WEB_SERVICE_ID + "/deploys", {"clearCache": "do_not_clear"})
if code in (200, 201):
    L("   ✓ Deploy triggered: " + deploy.get("id", "?"))
else:
    L("   Note: deploy trigger result " + str(code) + ": " + str(result))

L("")
L("✅ SETUP COMPLETE")
L("Render will redeploy in ~2-3 minutes, then the app will use Postgres.")
L("Data will persist across all future deploys.")
L("")
L("Database ID: " + db_id)

open("setup_log.txt","w").write(chr(10).join(log))
