
import urllib.request, json
BASE = "https://skymaxx-lead-engine.onrender.com"

log = []
def L(m): log.append(str(m)); print(m, flush=True)

def get(p):
    try:
        return urllib.request.urlopen(BASE + p, timeout=30).read().decode()
    except urllib.error.HTTPError as e:
        return "ERR " + str(e.code) + ": " + e.read().decode()[:200]
    except Exception as e:
        return "ERR: " + str(e)

def post(p, body, timeout=80):
    try:
        req = urllib.request.Request(BASE + p, data=json.dumps(body).encode(),
            headers={"Content-Type":"application/json"}, method="POST")
        return urllib.request.urlopen(req, timeout=timeout).read().decode()
    except urllib.error.HTTPError as e:
        return "ERR " + str(e.code) + ": " + e.read().decode()[:500]
    except Exception as e:
        return "ERR: " + str(e)

L("=" * 60)
L("ORANGE SLICE INTEGRATION — END-TO-END TEST")
L("=" * 60)
L("")

# Test 1: status endpoint
L("TEST 1: Orange Slice configuration status")
r = get("/api/linkedin/status")
L("  " + r)
L("")

# Test 2: Search via Orange Slice (LinkedIn) for IT Manager in UAE
L("TEST 2: Search LinkedIn for 'IT Manager' in United Arab Emirates")
r = post("/api/search/v2/preview", {
    "source": "orange_slice",
    "country": "United Arab Emirates",
    "title": "IT Manager",
    "limit": 5
}, timeout=80)
try:
    data = json.loads(r)
    L("  Source: " + str(data.get("source")))
    L("  Count:  " + str(data.get("count")))
    if data.get("results"):
        for x in data["results"][:3]:
            L("    - " + str(x.get("name",""))[:30] + " | " +
              str(x.get("jobTitle",""))[:25] + " | " +
              str(x.get("company",""))[:25] + " | " +
              str(x.get("linkedinUrl",""))[:45])
    else:
        L("  " + r[:600])
except Exception as e:
    L("  Parse err: " + str(e))
    L("  Raw: " + r[:1200])

L("")

# Test 3: Search Google Maps (default) for IT companies in Wyoming (regression test)
L("TEST 3: Search Google Maps (default) — IT services in Wyoming, US (regression)")
r = post("/api/search/v2/preview", {
    "source": "google_maps",
    "country": "US",
    "state":   "Wyoming",
    "category": "IT services company"
}, timeout=80)
try:
    data = json.loads(r)
    L("  Source:  " + str(data.get("source", "google_maps")))
    L("  Results: " + str(len(data.get("results", []))))
    for x in data.get("results", [])[:3]:
        L("    - " + str(x.get("name",""))[:35] + " | " + str(x.get("website","NONE"))[:40])
except Exception as e:
    L("  Err: " + str(e))
    L("  Raw: " + r[:600])

L("")

# Test 4: Source dropdown in HTML
L("TEST 4: Frontend dropdown present?")
html = get("/")
L("  qs-source dropdown:           " + ("YES" if "id=\"qs-source\"" in html else "NO"))
L("  google_maps option:           " + ("YES" if "google_maps" in html else "NO"))
L("  orange_slice option:          " + ("YES" if "orange_slice" in html else "NO"))
L("  qsSourceChanged function:     " + ("YES" if "qsSourceChanged" in html else "NO"))
L("  linkedinGetEmail function:    " + ("YES" if "linkedinGetEmail" in html else "NO"))
L("  /api/linkedin/enrich_contact: " + ("YES" if "linkedin/enrich_contact" in html else "NO"))

L("")
L("TEST 5: Enrich contact endpoint (this DOES use credits — using small test)")
# Just check endpoint exists, don't actually enrich (saves credits)
r = post("/api/linkedin/enrich_contact", {
    "linkedinUrl": "https://www.linkedin.com/in/example-test-only-not-real",
    "required": ["email"]
}, timeout=30)
L("  Response: " + r[:300])

open("orange_test.txt","w").write(chr(10).join(log))
