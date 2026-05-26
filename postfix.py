
import urllib.request, json, time
BASE = "https://skymaxx-lead-engine.onrender.com"

log = []
def L(m): log.append(str(m)); print(m, flush=True)

def get(p, timeout=15):
    try:
        t0 = time.time()
        r = urllib.request.urlopen(BASE + p, timeout=timeout)
        return r.getcode(), time.time()-t0, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, 0, e.read().decode()[:300]
    except Exception as e:
        return 0, 0, str(e)[:200]

def post(p, body, timeout=15):
    try:
        req = urllib.request.Request(BASE + p, data=json.dumps(body).encode(),
            headers={"Content-Type":"application/json"}, method="POST")
        t0 = time.time()
        r = urllib.request.urlopen(req, timeout=timeout)
        return r.getcode(), time.time()-t0, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, 0, e.read().decode()[:400]
    except Exception as e:
        return 0, 0, str(e)[:200]

L("=" * 60)
L("POST-FIX VERIFICATION")
L("=" * 60)
L("")

# 1. /api/stats — should be 200 now with bulletproof code
L("=== /api/stats — should NOT 500/timeout anymore ===")
code, et, body = get("/api/stats")
L(f"  HTTP {code} in {et:.2f}s")
try:
    s = json.loads(body)
    for k, v in s.items():
        L(f"    {k:15} = {v}")
except: L(f"  Body: {body[:300]}")
L("")

# 2. Logo serving + HTML has logo
L("=== Logo + HTML deploy ===")
code, _, _ = get("/static/logo.png")
L(f"  /static/logo.png:    HTTP {code}")
code, _, _ = get("/static/favicon.png")
L(f"  /static/favicon.png: HTTP {code}")

code, _, html = get("/")
checks = {
    "/static/logo.png in HTML":      "/static/logo.png" in html,
    "goHome function in HTML":       "function goHome" in html,
    "favicon link in HTML":          "/static/favicon.png" in html,
    "Old ⚡ SKYMAXX removed":         "⚡ SKYMAXX" not in html,
    "loadStats has timeout":         "AbortController" in html,
    "Credit lock warning present":   "Credit usage LOCKED" in html,
    "Get Email button disabled":     "Get Email (locked)" in html,
}
for k, v in checks.items():
    L(f"  {k:35}: {'✓' if v else '✗'}")
L("")

# 3. Orange Slice lock check  
L("=== Orange Slice credits locked ===")
code, _, body = get("/api/linkedin/status")
L(f"  /api/linkedin/status: HTTP {code} | {body[:200]}")

# Test that enrich is blocked
code, _, body = post("/api/linkedin/enrich_contact", {"linkedinUrl": "test"}, timeout=10)
L(f"  enrich_contact attempt: HTTP {code}")
L(f"    Body: {body[:300]}")
L("")

# 4. Other endpoints still work
L("=== Other dashboard endpoints ===")
for path in ["/api/leads?per_page=3", "/api/log", "/api/config", "/api/sequence/queue", "/api/campaigns", "/api/groups"]:
    code, et, body = get(path)
    L(f"  HTTP {code} in {et:.2f}s | {path}")
L("")

# 5. Test Orange Slice search still works (FREE — just listings)
L("=== Orange Slice SEARCH (free) — should still work ===")
code, et, body = post("/api/search/v2/preview", {
    "source": "orange_slice", "country": "United Arab Emirates",
    "title": "IT Manager", "limit": 3
}, timeout=30)
L(f"  HTTP {code} in {et:.2f}s")
try:
    d = json.loads(body)
    L(f"    Count: {d.get('count')}")
    for x in d.get("results",[])[:2]:
        L(f"      - {x.get('name','')[:30]} | {x.get('jobTitle','')[:25]}")
except: L(f"  Body: {body[:200]}")

open("postfix.txt","w").write(chr(10).join(log))
