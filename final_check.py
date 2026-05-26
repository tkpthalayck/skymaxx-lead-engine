
import urllib.request, time
BASE = "https://skymaxx-lead-engine.onrender.com"
log = []
def L(m): log.append(m); print(m, flush=True)

L("=== Static file final check ===")
for path in ["/static/logo.png", "/static/favicon.png"]:
    for attempt in range(2):
        try:
            t0 = time.time()
            r = urllib.request.urlopen(BASE + path, timeout=20)
            body = r.read()
            ct = r.headers.get("Content-Type")
            L(f"  attempt {attempt+1}: {path} → HTTP {r.getcode()} | {len(body)} bytes | {ct} | {time.time()-t0:.2f}s")
            break
        except Exception as e:
            L(f"  attempt {attempt+1}: {path} → {e}")
            if attempt == 0: time.sleep(3)

L("")
L("=== Loading dashboard page ===")
t0 = time.time()
r = urllib.request.urlopen(BASE + "/", timeout=20)
html = r.read().decode()
L(f"  Dashboard page: HTTP {r.getcode()} | {len(html)} bytes | {time.time()-t0:.2f}s")

# Test the logo path the page references
import re
m = re.search(r"src=[\"\']/static/logo[^\"\']*[\"\']", html)
if m: L(f"  Logo referenced as: {m.group(0)}")

open("final.txt","w").write(chr(10).join(log))
