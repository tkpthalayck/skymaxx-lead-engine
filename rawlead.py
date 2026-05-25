
import urllib.request, json
BASE = "https://skymaxx-lead-engine.onrender.com"

log = []
def L(m): log.append(m); print(m, flush=True)

# Get raw lead JSON
try:
    r = urllib.request.urlopen(BASE + "/api/leads?per_page=2", timeout=30)
    d = json.loads(r.read().decode())
    L("=== RAW LEAD JSON (first lead) ===")
    if d.get("leads"):
        L(json.dumps(d["leads"][0], indent=2))
    L("")
    L("Total leads: " + str(d.get("total")))
except Exception as e:
    L("Error: " + str(e))

# Test the debug endpoint with column info  
L("")
L("=== Test extended debug ===")
try:
    r = urllib.request.urlopen(BASE + "/api/debug/db", timeout=30)
    info = json.loads(r.read().decode())
    for k, v in info.items():
        if k not in ("DATABASE_URL_prefix",):
            L("  " + k + ": " + str(v)[:150])
except Exception as e:
    L("Error: " + str(e))

open("rawlead.txt","w").write(chr(10).join(log))
