import urllib.request, json
BASE = "https://skymaxx-lead-engine.onrender.com"

# Try the endpoint with a minimal payload
req = urllib.request.Request(BASE + "/api/search/v2/enrich_emails",
    data=json.dumps({"leads": [{"place_id":"test","website":"https://google.com"}]}).encode(),
    headers={"Content-Type":"application/json"},
    method="POST")

try:
    r = urllib.request.urlopen(req, timeout=60)
    print("HTTP", r.getcode())
    print(r.read().decode()[:2000])
except urllib.error.HTTPError as e:
    print("HTTPError:", e.code)
    print("Body:", e.read().decode()[:2000])
except Exception as e:
    print("Error:", e)

# Also test if other endpoints work
print()
print("=== Other endpoints ===")
for ep in ["/api/config", "/api/stats", "/api/sequence/templates"]:
    try:
        r = urllib.request.urlopen(BASE+ep, timeout=30)
        print(f"{ep}: HTTP {r.getcode()}")
    except Exception as e:
        print(f"{ep}: ERROR {e}")
