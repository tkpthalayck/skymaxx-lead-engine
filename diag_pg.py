
import urllib.request, json

RENDER_KEY = "rnd_C7jBUGG8sEuBRvqf3U4w4YU4zWsx"
SERVICE_ID = "srv-d88vm9favr4c7396kt00"
HEADERS = {"Authorization": "Bearer " + RENDER_KEY, "Content-Type": "application/json"}

log = []
def L(m): log.append(m); print(m, flush=True)

L("=== DIAGNOSING POSTGRES CONNECTION ===")
L("")

# 1. Check env vars on web service
L("1. Web service env vars:")
req = urllib.request.Request("https://api.render.com/v1/services/" + SERVICE_ID + "/env-vars?limit=100", headers=HEADERS)
try:
    env_vars = json.loads(urllib.request.urlopen(req, timeout=30).read())
    db_url_found = False
    for item in env_vars:
        e = item.get("envVar", {})
        key = e.get("key", "")
        val = e.get("value", "")
        if "DATABASE" in key or "DB_" in key or "POSTGRES" in key:
            db_url_found = (key == "DATABASE_URL")
            L("   " + key + " = " + val[:60] + ("..." if len(val) > 60 else ""))
    L("   DATABASE_URL present: " + str(db_url_found))
    L("   Total env vars: " + str(len(env_vars)))
except Exception as e:
    L("   Error: " + str(e))

# 2. Check the Postgres database itself
L("")
L("2. Render Postgres database status:")
req = urllib.request.Request("https://api.render.com/v1/postgres?limit=10", headers=HEADERS)
try:
    dbs = json.loads(urllib.request.urlopen(req, timeout=30).read())
    L("   Total databases: " + str(len(dbs)))
    for item in dbs:
        db = item.get("postgres", {})
        L("   - " + db.get("name","?") + " id=" + db.get("id","?") + " status=" + db.get("status","?"))
except Exception as e:
    L("   Error: " + str(e))

# 3. Check latest deploy logs for connection errors
L("")
L("3. Latest deploy status:")
req = urllib.request.Request("https://api.render.com/v1/services/" + SERVICE_ID + "/deploys?limit=3", headers=HEADERS)
try:
    deploys = json.loads(urllib.request.urlopen(req, timeout=30).read())
    for d in deploys[:3]:
        dd = d.get("deploy", {})
        L("   " + dd.get("id","")[:25] + " status=" + dd.get("status","?") + " - " + dd.get("commit",{}).get("message","")[:60])
except Exception as e:
    L("   Error: " + str(e))

# 4. Check the test endpoint that tells us the DB type
L("")
L("4. Live app config:")
try:
    r = urllib.request.urlopen("https://skymaxx-lead-engine.onrender.com/api/config", timeout=30)
    cfg = json.loads(r.read().decode())
    for k, v in cfg.items():
        L("   " + str(k) + ": " + str(v)[:80])
except Exception as e:
    L("   Error: " + str(e))

open("diag_pg.txt", "w").write(chr(10).join(log))
