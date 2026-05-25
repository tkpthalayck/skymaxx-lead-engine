
import urllib.request, json, time

BASE = "https://skymaxx-lead-engine.onrender.com"

log = []
def L(m): log.append(m); print(m, flush=True)

def get(p, timeout=45):
    try:
        r = urllib.request.urlopen(BASE + p, timeout=timeout)
        return r.getcode(), json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode()[:300]}
    except Exception as e:
        return 0, {"error": str(e)[:200]}

def post(p, body=None, timeout=60):
    try:
        data = json.dumps(body or {}).encode()
        req = urllib.request.Request(BASE + p, data=data, headers={"Content-Type":"application/json"}, method="POST")
        r = urllib.request.urlopen(req, timeout=timeout)
        return r.getcode(), json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode()[:300]}
    except Exception as e:
        return 0, {"error": str(e)[:200]}

L("=" * 60)
L("LEAD SEARCHER AGENT — FULL APP AUDIT")
L("=" * 60)
L("")

# ────────────────────────────────────────────────────
# TEST 1: Countries list completeness
# ────────────────────────────────────────────────────
L("TEST 1: Countries endpoint")
code, countries = get("/api/locations/countries")
L("  HTTP " + str(code) + " | Total countries: " + str(len(countries) if isinstance(countries, list) else "?"))
if isinstance(countries, list):
    regions = {}
    for c in countries:
        r = c.get("region", "?")
        regions.setdefault(r, []).append(c.get("code") + ":" + c.get("name"))
    for region, items in regions.items():
        L("  " + region + " (" + str(len(items)) + "): " + ", ".join(items[:8]) + ("..." if len(items) > 8 else ""))
    # Sample countries to verify
    codes = [c.get("code") for c in countries]
    L("")
    L("  Critical countries check:")
    for code_check in ["US", "AE", "CA", "GB", "DE", "AU", "JP", "MX", "BR", "IT", "ES", "NL"]:
        L("    " + code_check + ": " + ("YES" if code_check in codes else "MISSING"))
L("")

# ────────────────────────────────────────────────────
# TEST 2: US states (Wyoming check!)
# ────────────────────────────────────────────────────
L("TEST 2: US states endpoint")
code, states = get("/api/locations/states/US")
L("  HTTP " + str(code) + " | Total US states: " + str(len(states) if isinstance(states, list) else "?"))
if isinstance(states, list):
    L("  Wyoming present: " + ("YES ✓" if "Wyoming" in states else "MISSING ✗"))
    # Check all 50
    expected_states = [
        "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut",
        "Delaware", "Florida", "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa",
        "Kansas", "Kentucky", "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan",
        "Minnesota", "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire",
        "New Jersey", "New Mexico", "New York", "North Carolina", "North Dakota", "Ohio",
        "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota",
        "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington", "West Virginia",
        "Wisconsin", "Wyoming"
    ]
    missing = [s for s in expected_states if s not in states]
    L("  All 50 states: " + ("YES ✓" if not missing else "MISSING " + str(len(missing)) + ": " + ", ".join(missing[:10])))
    L("  Has DC: " + ("YES" if "District of Columbia" in states else "NO"))
L("")

# ────────────────────────────────────────────────────
# TEST 3: Other key country states
# ────────────────────────────────────────────────────
L("TEST 3: Other countries — state coverage")
for cc in ["CA", "GB", "DE", "AU", "IN", "JP", "FR", "BR"]:
    code, states = get("/api/locations/states/" + cc)
    if isinstance(states, list):
        L("  " + cc + ": " + str(len(states)) + " regions, e.g. " + ", ".join(states[:4]))
L("")

# ────────────────────────────────────────────────────
# TEST 4: Categories
# ────────────────────────────────────────────────────
L("TEST 4: Business categories")
code, cats = get("/api/business_categories")
if isinstance(cats, list):
    L("  Total: " + str(len(cats)))
    for c in cats[:8]:
        L("    - " + c.get("label","") + " (kw: " + c.get("keyword","") + ")")
    L("    ...")
L("")

# ────────────────────────────────────────────────────
# TEST 5: Job titles
# ────────────────────────────────────────────────────
L("TEST 5: Job titles")
code, titles = get("/api/job_titles")
if isinstance(titles, list):
    L("  Total: " + str(len(titles)))
    for t in titles[:8]:
        L("    - " + t.get("label","") + " (kw: " + t.get("keyword","") + ")")
    L("    ...")
L("")

# ────────────────────────────────────────────────────
# TEST 6: Cleanup duplicate leads
# ────────────────────────────────────────────────────
L("TEST 6: Cleanup duplicate leads")
code, before = get("/api/leads?per_page=5")
L("  Before cleanup: " + str(before.get("total", 0)) + " leads")

code, result = post("/api/debug/cleanup_dupes")
L("  Cleanup result: " + json.dumps(result))

# Re-import 13 leads
L("")
L("TEST 7: Fresh import of 13 M365 leads")
leads = [
    ("Aaron Barak", "abarak@maximaapparel.com", "COO", "Maxima Apparel"),
    ("Chris Kucharski", "chris.kucharski@onerail.io", "CTO", "OneRail"),
    ("Hank Jackson", "hank.jackson@edgewaterit.com", "COO", "Edgewater Federal Solutions"),
    ("James Stanford", "james.stanford@edgewaterit.com", "Sr Director Client Delivery", "Edgewater Federal Solutions"),
    ("Raymond Churgovich", "rchurgovich@broomfield.org", "IT Project Manager", "Edgewater Federal Solutions"),
    ("Tom Monahan", "tom.monahan@edgewaterit.com", "IT Manager", "Edgewater Federal Solutions"),
    ("Michael Hinman", "michael.hinman@edgewaterit.com", "IT Project Manager", "Edgewater Federal Solutions"),
    ("Dan Aldis", "daldis@halvik.com", "IT Program Manager", "Halvik"),
    ("Liam Connor", "liam.connor@intercity.technology", "Tech Services Manager", "Intercity"),
    ("Mark Hawkins-Wood", "mark.hawkins-wood@intercity.technology", "Head of Cloud and Managed IT", "Intercity"),
    ("Stewart Nicol", "stewart.nicol@intercity.technology", "Head of Platforms", "Intercity"),
    ("Rick Korsak", "rick.korsak@intercity.technology", "IT Infrastructure Manager", "Intercity"),
    ("Ampem Dako", "ampem.dako@intercity.technology", "Managed IT Manager", "Intercity"),
]
csv_data = "name,email,title,company,city,country" + chr(10)
for name, email, title, company in leads:
    csv_data += name + "," + email + "," + title + "," + company + ",," + chr(10)

boundary = "------brk998"
body_bytes = (
    "--" + boundary + chr(13) + chr(10) +
    "Content-Disposition: form-data; name=" + chr(34) + "file" + chr(34) + "; filename=" + chr(34) + "m.csv" + chr(34) + chr(13) + chr(10) +
    "Content-Type: text/csv" + chr(13) + chr(10) + chr(13) + chr(10) +
    csv_data + chr(13) + chr(10) +
    "--" + boundary + "--" + chr(13) + chr(10)
).encode("utf-8")
req = urllib.request.Request(BASE + "/api/import", data=body_bytes,
    headers={"Content-Type": "multipart/form-data; boundary=" + boundary}, method="POST")
try:
    r = urllib.request.urlopen(req, timeout=60)
    L("  Import: " + r.read().decode())
except Exception as e:
    L("  Error: " + str(e))

# Verify count + company field
code, after = get("/api/leads?per_page=20")
L("  After: " + str(after.get("total", 0)) + " leads")
for l in after.get("leads", [])[:5]:
    L("  - id=" + str(l.get("id")) + " | " + str(l.get("name",""))[:25] + " | " + str(l.get("company","NULL"))[:30])

# ────────────────────────────────────────────────────
# TEST 8: Actual lead search via Google Maps
# ────────────────────────────────────────────────────
L("")
L("TEST 8: Live lead search — IT companies in Wyoming, US")
code, r = post("/api/search/v2/preview", {
    "country": "United States",
    "state":   "Wyoming",
    "category":"IT services company"
})
L("  HTTP " + str(code))
if code == 200:
    results = r.get("results", [])
    L("  Got " + str(len(results)) + " results")
    for x in results[:3]:
        L("    - " + str(x.get("name",""))[:40] + " | " + str(x.get("website","NONE"))[:50])

open("audit.txt","w").write(chr(10).join(log))
