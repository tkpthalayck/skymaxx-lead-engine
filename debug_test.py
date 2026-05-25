
import urllib.request, json
BASE = "https://skymaxx-lead-engine.onrender.com"

log = []
def L(m): log.append(m); print(m, flush=True)

# Test 1: Can we INSERT with company via direct endpoint?
L("=== TEST 1: Direct INSERT with company ===")
try:
    r = urllib.request.urlopen(BASE + "/api/debug/test_insert", timeout=30)
    res = json.loads(r.read().decode())
    L("  Result: " + json.dumps(res, indent=2))
except Exception as e:
    L("  Error: " + str(e))

# Test 2: Cleanup all leads
L("")
L("=== TEST 2: Cleanup all leads ===")
try:
    req = urllib.request.Request(BASE + "/api/debug/cleanup_dupes", method="POST")
    r = urllib.request.urlopen(req, timeout=30)
    L("  " + r.read().decode())
except Exception as e:
    L("  Error: " + str(e))

# Test 3: Fresh import (should populate company)
L("")
L("=== TEST 3: Fresh import 13 leads ===")
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

boundary = "------br223344"
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

# Test 4: Verify company is now populated
L("")
L("=== TEST 4: Verify leads have company ===")
try:
    r = urllib.request.urlopen(BASE + "/api/leads?per_page=20", timeout=30)
    d = json.loads(r.read().decode())
    L("  Total: " + str(d.get("total", 0)))
    for l in d.get("leads", [])[:15]:
        co = l.get("company") or "(null)"
        ti = l.get("title") or "(null)"
        L("  - id=" + str(l.get("id")) + " | " + str(l.get("name",""))[:25] + " | co=" + str(co)[:30] + " | ti=" + str(ti)[:30])
except Exception as e:
    L("  Error: " + str(e))

open("debug_test.txt","w").write(chr(10).join(log))
