
import urllib.request, json, time
BASE = "https://skymaxx-lead-engine.onrender.com"

log = []
def L(m): log.append(str(m)); print(m, flush=True)

def get(p, timeout=30):
    try: return urllib.request.urlopen(BASE + p, timeout=timeout).read().decode()
    except urllib.error.HTTPError as e: return "ERR " + str(e.code) + ": " + e.read().decode()[:200]
    except Exception as e: return "ERR: " + str(e)

def post(p, body, timeout=60):
    try:
        req = urllib.request.Request(BASE + p, data=json.dumps(body).encode(),
            headers={"Content-Type":"application/json"}, method="POST")
        r = urllib.request.urlopen(req, timeout=timeout)
        return r.getcode(), r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:600]
    except Exception as e:
        return 0, str(e)[:300]

L("=" * 60)
L("FINAL VERIFICATION")
L("=" * 60)
L("")

# Frontend
html = get("/")
L("=== Frontend ===")
checks = {
    "Quick: qs-source dropdown":     "id=\"qs-source\"" in html,
    "Quick: Orange Slice option":    "🔶 Orange Slice" in html or "orange_slice" in html,
    "Bulk: bulk-source dropdown":    "id=\"bulk-source\"" in html,
    "Bulk: bulkSourceChanged":       "function bulkSourceChanged" in html,
    "Bulk passes source":            "source: document.getElementById(\'bulk-source\')" in html,
    "Quick: linkedinGetEmail":       "function linkedinGetEmail" in html,
}
for k, v in checks.items():
    L(f"  {k:35}: {'✓' if v else '✗'}")
L("")

# Backend
L("=== Backend endpoints ===")
status = get("/api/linkedin/status")
L(f"  /api/linkedin/status: {status[:200]}")
L("")

# Quick Search Orange Slice
L("=== Quick Search — Orange Slice ===")
t0 = time.time()
code, body = post("/api/search/v2/preview", {
    "source": "orange_slice", "country": "United Arab Emirates",
    "title": "IT Manager", "limit": 3
}, timeout=60)
L(f"  HTTP {code} in {time.time()-t0:.1f}s")
try:
    d = json.loads(body)
    L(f"  Found {d.get('count')} results")
    for x in d.get("results",[])[:2]:
        L(f"    - {x.get('name','')[:30]} | {x.get('jobTitle','')[:25]} @ {x.get('company','')[:25]}")
except: L(f"  Body: {body[:300]}")
L("")

# Google Maps regression - retry with retry logic
L("=== Google Maps — Wyoming IT regression test ===")
for attempt in [1,2]:
    t0 = time.time()
    code, body = post("/api/search/v2/preview", {
        "source": "google_maps", "country": "US", "state": "Wyoming",
        "category": "IT services company"
    }, timeout=60)
    L(f"  Attempt {attempt}: HTTP {code} in {time.time()-t0:.1f}s")
    try:
        d = json.loads(body)
        L(f"    Found {d.get('found') or len(d.get('results',[]))} results")
        for x in (d.get("results") or [])[:2]:
            L(f"      - {x.get('name','')[:35]} | {x.get('website','NONE')[:35]}")
        break
    except:
        L(f"    Body: {body[:200]}")
        if attempt == 1: time.sleep(5)
L("")

# Bulk Search Orange Slice
L("=== Bulk Search — Orange Slice ===")
t0 = time.time()
code, body = post("/api/search/v2/bulk_preview", {
    "source": "orange_slice",
    "countries": ["United Arab Emirates", "Saudi Arabia"],
    "states": [],
    "categories": [],
    "job_titles": ["IT Director"]
}, timeout=90)
L(f"  HTTP {code} in {time.time()-t0:.1f}s")
try:
    d = json.loads(body)
    L(f"  Found {d.get('found')} unique results across {d.get('combinations_run')} combos")
    for x in (d.get("results") or [])[:3]:
        L(f"    - {x.get('name','')[:30]} | {x.get('jobTitle','')[:25]} @ {x.get('company','')[:25]}")
except: L(f"  Body: {body[:300]}")
L("")

# Verify lead 72 (saved Orange Slice lead) still exists
L("=== Lead 72 (Orange Slice saved lead) ===")
ld = get("/api/leads?per_page=20")
try:
    d = json.loads(ld)
    L(f"  Total: {d.get('total')}")
    for l in d.get("leads",[]):
        if l.get("id") == 72:
            L(f"  Found id=72: {l.get('name')} | website={l.get('website','')[:50]} | company={l.get('company','')}")
            break
except: pass

open("verify.txt","w").write(chr(10).join(log))
