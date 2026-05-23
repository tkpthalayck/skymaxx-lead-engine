
import os, sys, json, urllib.request, urllib.error, traceback

log = []
def p(msg):
    print(msg)
    log.append(str(msg))

KEY = os.environ.get("RENDER_API_KEY", "")
p(f"Key length: {len(KEY)}, prefix: '{KEY[:12]}'")

def api(method, path, data=None):
    url = "https://api.render.com/v1" + path
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method,
        headers={"Authorization": f"Bearer {KEY}",
                 "Accept": "application/json",
                 "Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        raw = resp.read()
        parsed = json.loads(raw)
        p(f"  OK {method} {path} [{len(raw)}b]")
        return parsed
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        p(f"  ERR {method} {path} HTTP {e.code}: {body[:600]}")
        return {"error": e.code, "body": body}
    except Exception as e:
        p(f"  EXC {method} {path}: {e}")
        return {"error": str(e)}

try:
    p("=== Getting owners ===")
    owners = api("GET", "/owners?limit=1")
    p(f"Raw: {json.dumps(owners)[:400]}")

    if "error" in owners:
        p("FAILED at owners step")
    else:
        owner_id = owners[0]["owner"]["id"]
        p(f"Owner ID: {owner_id}")

        p("=== Listing services ===")
        services = api("GET", "/services?limit=20")
        p(f"Services raw: {json.dumps(services)[:600]}")

except Exception:
    p("EXCEPTION:")
    p(traceback.format_exc())

with open("deploy_debug.txt", "w") as f:
    f.write("\n".join(log))
p("Wrote deploy_debug.txt")
