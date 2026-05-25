import urllib.request, json
BASE = "https://skymaxx-lead-engine.onrender.com"
def get(p):
    try:
        r = urllib.request.urlopen(BASE+p, timeout=45)
        return r.getcode()
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:
        return 0

log = ["=== App health check ==="]
for ep in ["/", "/api/config", "/api/stats", "/api/leads", "/api/campaigns", "/api/sequence/templates", "/api/log"]:
    log.append(f"  {ep}: HTTP {get(ep)}")

# Check the 13 leads survived
try:
    r = urllib.request.urlopen(BASE + "/api/leads?per_page=20", timeout=30)
    d = json.loads(r.read().decode())
    log.append("")
    log.append(f"Total leads in DB: {d.get(\"total\", 0)}")
    for l in d.get("leads", [])[:5]:
        log.append(f"  - {l.get(\"name\",\"\")[:30]} | {l.get(\"email\",\"\")[:35]}")
except Exception as e:
    log.append(f"Leads check error: {e}")

with open("alive.txt","w") as f: f.write(chr(10).join(log))
print(chr(10).join(log))
