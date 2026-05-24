import urllib.request, json
BASE = "https://skymaxx-lead-engine.onrender.com"

def get(p):
    try:
        r = urllib.request.urlopen(BASE+p, timeout=45)
        return r.getcode(), r.read().decode()
    except Exception as e:
        return 0, str(e)[:80]

log = []
log.append("=== BUG FIX VERIFICATION ===")
log.append("")

# Get the live HTML
code, html = get("/")
log.append("Dashboard HTML: HTTP " + str(code) + " (" + str(len(html)) + " bytes)")
log.append("")

# Check fix #1: qsSelected is now declared
log.append("FIX 1: qsSelected declaration")
if "qsSelected === \"undefined\"" in html or "qsSelected === undefined" in html or "MISSING SEARCH HELPERS" in html:
    log.append("  PASS: Missing helper block was inserted")
if "window.qsSelected = new Set" in html or "qsSelected = new Set" in html:
    log.append("  PASS: qsSelected is declared")
else:
    log.append("  FAIL: qsSelected still not declared")

# Check helper functions
helpers = ["renderQSResults", "qsToggle", "qsSelectAll", "qsSelectWithEmail", "qsAddToGroup", "updateQSCount"]
for h in helpers:
    if "function " + h in html or "function "+ h + "(" in html:
        log.append("  PASS: function " + h)
    else:
        log.append("  FAIL: function " + h + " missing")

log.append("")

# Check fix #2: defensive renderers
log.append("FIX 2: Defensive renderers (guard against missing DOM)")
for fn, el in [("renderCategoriesGrid","categories-grid"),("renderCitiesGrid","cities-grid"),("renderSequenceCards","sequence-cards"),("renderSequenceOverview","seq-overview")]:
    pat = "function " + fn
    idx = html.find(pat)
    if idx > 0:
        body = html[idx:idx+400]
        if "if (!document.getElementById" in body:
            log.append("  PASS: " + fn + " has guard")
        else:
            log.append("  FAIL: " + fn + " has no guard")

log.append("")

# Verify Email Sequence backend endpoint still works
log.append("Backend check:")
code, body = get("/api/sequence/templates")
log.append("  /api/sequence/templates: HTTP " + str(code))
if code == 200:
    d = json.loads(body)
    log.append("    Templates returned: " + str(len(d)))
    for t in d[:5]:
        log.append("    - Step " + str(t.get("step")) + ": " + t.get("name","")[:50])

code, body = get("/api/locations/countries")
log.append("  /api/locations/countries: HTTP " + str(code))

code, body = get("/api/business_categories")
log.append("  /api/business_categories: HTTP " + str(code))

with open("fix_verify.txt","w") as f: f.write(chr(10).join(log))
print(chr(10).join(log))
