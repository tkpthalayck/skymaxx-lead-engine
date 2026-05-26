
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

def get(p, timeout=20):
    try: return urllib.request.urlopen(BASE + p, timeout=timeout).read().decode()
    except: return ""

L("=" * 60)
L("CATEGORY-OPTIONAL VERIFICATION")
L("=" * 60)
L("")

# ── TEST 1: Quick Search with NO category, NO keyword — should still work ──
L("=== TEST 1: Quick Search Wyoming, no category, no keyword ===")
t0 = time.time()
code, et, body = post("/api/search/v2/preview", {
    "source": "google_maps",
    "country": "US",
    "state": "Wyoming"
}, timeout=45)
L(f"  HTTP {code} in {et:.1f}s")
try:
    d = json.loads(body)
    L(f"  search_all_categories: {d.get('search_all_categories')}")
    L(f"  Results found: {d.get('found') or len(d.get('results',[]))}")
    for x in d.get("results",[])[:3]:
        L(f"    - {x.get('name','')[:35]} | {x.get('website','NONE')[:35]}")
except: L(f"  Body: {body[:300]}")
L("")

# ── TEST 2: Quick Search with category (regression) ──
L("=== TEST 2: Regression — Quick Search WITH category (Wyoming IT) ===")
t0 = time.time()
code, et, body = post("/api/search/v2/preview", {
    "source": "google_maps",
    "country": "US",
    "state": "Wyoming",
    "category": "IT services company"
}, timeout=45)
L(f"  HTTP {code} in {et:.1f}s")
try:
    d = json.loads(body)
    L(f"  search_all_categories: {d.get('search_all_categories')}")
    L(f"  Results: {d.get('found') or len(d.get('results',[]))}")
except: L(f"  {body[:200]}")
L("")

# ── TEST 3: Bulk Search with NO categories — should expand to all ──
L("=== TEST 3: Bulk Search — no categories selected ===")
t0 = time.time()
code, et, body = post("/api/search/v2/bulk_preview", {
    "source": "google_maps",
    "countries": ["AE"],
    "states": [],
    "categories": [],
    "job_titles": []
}, timeout=45)
L(f"  HTTP {code} in {et:.1f}s")
try:
    d = json.loads(body)
    L(f"  expanded_all_categories: {d.get('expanded_all_categories')}")
    L(f"  Results: {d.get('found') or len(d.get('results',[]))}")
    L(f"  Combinations run: {len(d.get('summary',[]))}")
    for x in d.get("results",[])[:3]:
        L(f"    - {x.get('name','')[:30]} | {x.get('category','')[:25]} | {x.get('address','')[:30]}")
except: L(f"  Body: {body[:300]}")
L("")

# ── TEST 4: Bulk Search WITH categories (regression) ──
L("=== TEST 4: Regression — Bulk Search WITH categories ===")
t0 = time.time()
code, et, body = post("/api/search/v2/bulk_preview", {
    "source": "google_maps",
    "countries": ["AE"],
    "states": [],
    "categories": ["hotel", "restaurant"],
    "job_titles": []
}, timeout=45)
L(f"  HTTP {code} in {et:.1f}s")
try:
    d = json.loads(body)
    L(f"  expanded_all_categories: {d.get('expanded_all_categories')}")
    L(f"  Results: {d.get('found') or len(d.get('results',[]))}")
except: L(f"  {body[:200]}")
L("")

# ── TEST 5: Frontend ──
L("=== TEST 5: Frontend UI changes ===")
html = get("/")
checks = {
    "QS validation softened": "searching ALL businesses" in html,
    "Bulk validation softened": "Pick at least 1 Country, State, or Category" in html,
    "Category labeled optional": "leave empty to search all" in html or "optional" in html.lower(),
    "Logo present":            "/static/logo.png" in html,
    "Credit lock UI":          "Get Email (locked)" in html,
}
for k, v in checks.items():
    L(f"  {k:35}: {'✓' if v else '✗'}")
L("")

# ── TEST 6: Dashboard stats (regression) ──
L("=== TEST 6: Dashboard stats still working ===")
try:
    stats = json.loads(urllib.request.urlopen(BASE + "/api/stats", timeout=15).read())
    L(f"  Total leads: {stats.get('total_leads')} | With email: {stats.get('with_email')} | Sent: {stats.get('total_sent')}")
except Exception as e:
    L(f"  Stats failed: {e}")

open("optional_test.txt","w").write(chr(10).join(log))
