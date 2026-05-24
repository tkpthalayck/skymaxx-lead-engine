import urllib.request, json
BASE = "https://skymaxx-lead-engine.onrender.com"
def get(p):
    try:
        r = urllib.request.urlopen(BASE+p, timeout=45)
        return r.getcode(), r.read().decode()
    except Exception as e:
        return 0, str(e)[:200]

log = ["=== LIVE APP STATE (with new adapter, SQLite mode) ==="]
for ep in ["/api/config","/api/stats","/api/leads","/api/campaigns","/api/sequence/templates"]:
    code, body = get(ep)
    log.append(f"  {ep}: HTTP {code}")
    if code == 200 and ep == "/api/leads":
        try:
            d = json.loads(body)
            log.append(f"    Total: {d.get(\"total\",0)}")
        except: pass

with open("post_adapter.txt","w") as f: f.write(chr(10).join(log))
print(chr(10).join(log))
