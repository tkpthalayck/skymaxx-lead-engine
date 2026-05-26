
import urllib.request, json
BASE = "https://skymaxx-lead-engine.onrender.com"

log = []
def L(m): log.append(str(m)); print(m, flush=True)

def get(p):
    try:
        r = urllib.request.urlopen(BASE + p, timeout=15)
        return r.getcode(), r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:500]
    except Exception as e:
        return 0, str(e)[:200]

L("=== Real frontend endpoints ===")
for path in ["/api/stats", "/api/log", "/api/config", "/api/sequence/queue", "/api/sent_today"]:
    code, body = get(path)
    L("HTTP " + str(code) + " | " + path)
    L("  " + body[:300])
    L("")

open("eps2.txt","w").write(chr(10).join(log))
