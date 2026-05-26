
import urllib.request, json, time
BASE = "https://skymaxx-lead-engine.onrender.com"
log = []
def L(m): log.append(str(m)); print(m, flush=True)

def post(p, body, timeout=45):
    try:
        req = urllib.request.Request(BASE + p, data=json.dumps(body).encode(),
            headers={"Content-Type":"application/json"}, method="POST")
        t0 = time.time()
        r = urllib.request.urlopen(req, timeout=timeout)
        return r.getcode(), time.time()-t0, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, 0, e.read().decode()[:500]
    except Exception as e:
        return 0, 0, str(e)[:200]

L("=== RETEST Quick Search ===")
L("")
L("Test A: Quick Search NO category, NO keyword, has country+state")
code, et, body = post("/api/search/v2/preview", {
    "source": "google_maps",
    "country": "US",
    "state": "Wyoming"
}, timeout=45)
L(f"  HTTP {code} in {et:.1f}s")
L(f"  Body: {body[:500]}")
L("")

L("Test B: Quick Search WITH category (regression)")  
code, et, body = post("/api/search/v2/preview", {
    "source": "google_maps",
    "country": "US",
    "state": "Wyoming",
    "category": "IT services company"
}, timeout=45)
L(f"  HTTP {code} in {et:.1f}s")
try:
    d = json.loads(body)
    L(f"  found: {d.get('found') or len(d.get('results',[]))}")
    L(f"  search_all_categories: {d.get('search_all_categories')}")
    for x in d.get("results",[])[:2]:
        L(f"    - {x.get('name','')[:35]}")
except: L(f"  Body: {body[:300]}")
L("")

L("Test C: Quick Search no category, in UAE (faster region)")
code, et, body = post("/api/search/v2/preview", {
    "source": "google_maps",
    "country": "AE",
    "state": "Dubai"
}, timeout=45)
L(f"  HTTP {code} in {et:.1f}s")
try:
    d = json.loads(body)
    L(f"  search_all_categories: {d.get('search_all_categories')}")
    L(f"  found: {d.get('found') or len(d.get('results',[]))}")
    for x in d.get("results",[])[:3]:
        L(f"    - {x.get('name','')[:35]} | category: {x.get('category','')[:30]}")
except: L(f"  Body: {body[:300]}")

open("retest.txt","w").write(chr(10).join(log))
