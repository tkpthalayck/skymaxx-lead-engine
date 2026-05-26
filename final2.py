
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
        return e.code, 0, e.read().decode()[:400]
    except Exception as e:
        return 0, 0, str(e)[:200]

# Warm-up call first (avoid cold start affecting measurement)
post("/api/stats", {}, timeout=10)
time.sleep(1)

L("=== Final Performance Tests ===")
L("")

# Test 1: Wyoming + no category (the original problematic case)
L("--- Wyoming, NO category (the case that 502d before) ---")
code, et, body = post("/api/search/v2/preview", {
    "source": "google_maps", "country": "US", "state": "Wyoming"
}, timeout=45)
L(f"  HTTP {code} in {et:.1f}s")
try:
    d = json.loads(body)
    L(f"  search_all_categories: {d.get('search_all_categories')}")
    L(f"  Results: {d.get('found') or len(d.get('results',[]))}")
    for x in d.get("results",[])[:3]:
        L(f"    - {x.get('name','')[:35]} | {(x.get('website') or '—')[:40]}")
except: L(f"  Body: {body[:400]}")
L("")

# Test 2: Wyoming WITH category (regression — should be even faster now)
L("--- Wyoming WITH category IT (regression — speed test) ---")
code, et, body = post("/api/search/v2/preview", {
    "source": "google_maps", "country": "US", "state": "Wyoming",
    "category": "IT services company"
}, timeout=45)
L(f"  HTTP {code} in {et:.1f}s")
try:
    d = json.loads(body)
    L(f"  Results: {d.get('found') or len(d.get('results',[]))}")
except: L(f"  {body[:300]}")
L("")

# Test 3: UAE no category — should be fast
L("--- UAE Dubai, NO category ---")
code, et, body = post("/api/search/v2/preview", {
    "source": "google_maps", "country": "AE", "state": "Dubai"
}, timeout=45)
L(f"  HTTP {code} in {et:.1f}s | Results: ")
try:
    d = json.loads(body)
    L(f"    {d.get('found') or len(d.get('results',[]))} | all_cats: {d.get('search_all_categories')}")
except: L(f"  {body[:200]}")
L("")

# Test 4: Bulk search no categories (regression)  
L("--- Bulk Search no categories, UAE (regression) ---")
code, et, body = post("/api/search/v2/bulk_preview", {
    "source": "google_maps",
    "countries": ["AE"], "states": [], "categories": [], "job_titles": []
}, timeout=45)
L(f"  HTTP {code} in {et:.1f}s")
try:
    d = json.loads(body)
    L(f"  expanded_all: {d.get('expanded_all_categories')} | Results: {d.get('found') or len(d.get('results',[]))}")
except: L(f"  {body[:200]}")

open("final2.txt","w").write(chr(10).join(log))
