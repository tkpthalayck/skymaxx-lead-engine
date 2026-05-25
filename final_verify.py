
import urllib.request, json, time

BASE = "https://skymaxx-lead-engine.onrender.com"
log = []
def L(m): log.append(m); print(m, flush=True)

L("=== AFTER PYTHON 3.12 PIN — DEBUG STATE ===")
L("")
try:
    r = urllib.request.urlopen(BASE + "/api/debug/db", timeout=45)
    info = json.loads(r.read().decode())
    for k, v in info.items():
        L("  " + str(k) + ": " + str(v)[:200])
except Exception as e:
    L("Error: " + str(e))

# If USE_POSTGRES is True now, re-import leads and we are done
L("")
L("=== RE-IMPORT LEADS (FINAL) ===")
leads = [
    ("Aaron Barak", "abarak@maximaapparel.com", "COO", "Maxima Apparel"),
    ("Chris Kucharski", "chris.kucharski@onerail.io", "CTO", "OneRail"),
    ("Hank Jackson", "hank.jackson@edgewaterit.com", "COO", "Edgewater"),
    ("James Stanford", "james.stanford@edgewaterit.com", "Sr Director", "Edgewater"),
    ("Raymond Churgovich", "rchurgovich@broomfield.org", "IT PM", "Edgewater"),
    ("Tom Monahan", "tom.monahan@edgewaterit.com", "IT Manager", "Edgewater"),
    ("Michael Hinman", "michael.hinman@edgewaterit.com", "IT PM", "Edgewater"),
    ("Dan Aldis", "daldis@halvik.com", "IT Program Manager", "Halvik"),
    ("Liam Connor", "liam.connor@intercity.technology", "Tech Services Mgr", "Intercity"),
    ("Mark Hawkins-Wood", "mark.hawkins-wood@intercity.technology", "Head of Cloud", "Intercity"),
    ("Stewart Nicol", "stewart.nicol@intercity.technology", "Head of Platforms", "Intercity"),
    ("Rick Korsak", "rick.korsak@intercity.technology", "IT Infra Mgr", "Intercity"),
    ("Ampem Dako", "ampem.dako@intercity.technology", "Managed IT Mgr", "Intercity"),
]
csv_data = "name,email,title,company,city,country" + chr(10)
for name, email, title, company in leads:
    csv_data += name + "," + email + "," + title + "," + company + ",," + chr(10)

boundary = "------brk998877"
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
    L("Import: " + r.read().decode())
except urllib.error.HTTPError as e:
    L("HTTPError " + str(e.code) + ": " + e.read().decode()[:300])
except Exception as e:
    L("Error: " + str(e))

L("")
L("=== FINAL LEAD COUNT ===")
try:
    r = urllib.request.urlopen(BASE + "/api/leads?per_page=20", timeout=30)
    d = json.loads(r.read().decode())
    L("Total: " + str(d.get("total", 0)))
    for l in d.get("leads", [])[:15]:
        L("  - id=" + str(l.get("id")) + " | " + str(l.get("name",""))[:30] + " | " + str(l.get("email",""))[:40])
except Exception as e:
    L("Error: " + str(e))

open("final_verify.txt","w").write(chr(10).join(log))
