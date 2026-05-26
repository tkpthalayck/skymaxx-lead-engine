
import urllib.request, json, time
BASE = "https://skymaxx-lead-engine.onrender.com"

log = []
def L(m): log.append(str(m)); print(m, flush=True)

def post(p, body, timeout=80):
    try:
        req = urllib.request.Request(BASE + p, data=json.dumps(body).encode(),
            headers={"Content-Type":"application/json"}, method="POST")
        return urllib.request.urlopen(req, timeout=timeout).getcode(), urllib.request.urlopen(urllib.request.Request(BASE + p, data=json.dumps(body).encode(), headers={"Content-Type":"application/json"}, method="POST"), timeout=timeout).read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:500]
    except Exception as e:
        return 0, str(e)[:300]

def post_v2(p, body, timeout=80):
    """Single-request version that doesn't double-call."""
    try:
        req = urllib.request.Request(BASE + p, data=json.dumps(body).encode(),
            headers={"Content-Type":"application/json"}, method="POST")
        r = urllib.request.urlopen(req, timeout=timeout)
        return r.getcode(), r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:500]
    except Exception as e:
        return 0, str(e)[:300]

def get(p, timeout=30):
    try:
        return urllib.request.urlopen(BASE + p, timeout=timeout).read().decode()
    except: return ""

L("=" * 60)
L("FINAL END-TO-END TEST")
L("=" * 60)
L("")

# ── TEST 1: Quick Search Orange Slice ──
L("TEST 1: Quick Search — Orange Slice (LinkedIn) — IT Manager UAE")
start = time.time()
code, body = post_v2("/api/search/v2/preview", {
    "source": "orange_slice",
    "country": "United Arab Emirates",
    "title": "IT Manager",
    "limit": 5
}, timeout=60)
elapsed = time.time() - start
try:
    d = json.loads(body)
    L(f"  HTTP {code} in {elapsed:.1f}s | Source: {d.get('source')} | Count: {d.get('count')}")
    for x in d.get("results",[])[:3]:
        L(f"    - {(x.get('name') or '')[:25]:25} | {(x.get('jobTitle') or '')[:25]:25} | {(x.get('company') or '')[:25]}")
    # Save sample for later
    sample_results = d.get("results", [])[:2]
except Exception as e:
    L(f"  Parse err: {e} | Body: {body[:300]}")
    sample_results = []

L("")

# ── TEST 2: Bulk Search Orange Slice ──
L("TEST 2: Bulk Search — Orange Slice — IT Manager + CTO in UAE+SA")
start = time.time()
code, body = post_v2("/api/search/v2/bulk_preview", {
    "source": "orange_slice",
    "countries": ["United Arab Emirates"],
    "states": [],
    "categories": [],
    "job_titles": ["IT Manager", "CTO"]
}, timeout=90)
elapsed = time.time() - start
try:
    d = json.loads(body)
    L(f"  HTTP {code} in {elapsed:.1f}s | Source: {d.get('source')} | Found: {d.get('found')}")
    for x in (d.get("results") or [])[:3]:
        L(f"    - {(x.get('name') or '')[:25]:25} | {(x.get('jobTitle') or '')[:25]:25} | {(x.get('company') or '')[:25]}")
    if d.get("error"):
        L(f"  Error: {d.get('error')}")
except Exception as e:
    L(f"  Parse err: {e} | Body: {body[:300]}")

L("")

# ── TEST 3: Save Orange Slice results to leads DB ──
L("TEST 3: Save sample Orange Slice results to leads DB")
if sample_results:
    code, body = post_v2("/api/search/v2/save_selected", {"leads": sample_results}, timeout=60)
    try:
        d = json.loads(body)
        L(f"  HTTP {code} | Saved: {d.get('saved')} | IDs: {d.get('lead_ids')}")
    except Exception as e:
        L(f"  Err: {e} | Body: {body[:300]}")
    
    # Verify by reading them back
    leads_body = get("/api/leads?per_page=5")
    try:
        ld = json.loads(leads_body)
        L(f"  Total leads now: {ld.get('total')}")
        for l in ld.get("leads",[])[:5]:
            L(f"    id={l.get('id')} | {(l.get('name') or '')[:25]:25} | website={(l.get('website') or '')[:50]}")
    except: pass
else:
    L("  Skipped (no sample results from Test 1)")
L("")

# ── TEST 4: Quick Search Google Maps (regression) ──
L("TEST 4: REGRESSION — Quick Search Google Maps — IT in Wyoming, US")
start = time.time()
code, body = post_v2("/api/search/v2/preview", {
    "source": "google_maps",
    "country": "US",
    "state": "Wyoming",
    "category": "IT services company"
}, timeout=60)
elapsed = time.time() - start
try:
    d = json.loads(body)
    L(f"  HTTP {code} in {elapsed:.1f}s | Found: {d.get('found') or len(d.get('results',[]))}")
    for x in d.get("results",[])[:3]:
        L(f"    - {(x.get('name') or '')[:35]} | {(x.get('website') or 'NONE')[:35]}")
except Exception as e:
    L(f"  Err: {e} | Body: {body[:300]}")
L("")

# ── TEST 5: Frontend checks ──
L("TEST 5: Frontend dropdowns (both Quick + Bulk)")
html = get("/")
checks = {
    "qs-source dropdown":      "id=\"qs-source\"" in html,
    "bulk-source dropdown":    "id=\"bulk-source\"" in html,
    "qsSourceChanged":         "qsSourceChanged" in html,
    "bulkSourceChanged":       "bulkSourceChanged" in html,
    "Source param in bulk":    "bulk-source\')?.value" in html or "bulk-source" in html,
    "linkedinGetEmail":        "linkedinGetEmail" in html,
}
for k, v in checks.items():
    L(f"  {k:30}: {'✓ YES' if v else '✗ NO'}")

open("final_test.txt","w").write(chr(10).join(log))
