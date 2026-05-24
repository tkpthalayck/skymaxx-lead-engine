import urllib.request, json, csv, io, sys

BASE = "https://skymaxx-lead-engine.onrender.com"

# The 13 M365 leads — restored
leads = [
    {"name":"Aaron Barak", "email":"abarak@maximaapparel.com", "title":"Chief Operations Officer", "company":"Maxima Apparel"},
    {"name":"Chris Kucharski", "email":"chris.kucharski@onerail.io", "title":"Chief Technology Officer", "company":"OneRail"},
    {"name":"Hank Jackson", "email":"hank.jackson@edgewaterit.com", "title":"Chief Operating Officer", "company":"Edgewater Federal Solutions"},
    {"name":"James Stanford", "email":"james.stanford@edgewaterit.com", "title":"Senior Director, Client Delivery", "company":"Edgewater Federal Solutions"},
    {"name":"Raymond Churgovich", "email":"rchurgovich@broomfield.org", "title":"IT Project Manager", "company":"Edgewater Federal Solutions"},
    {"name":"Tom Monahan", "email":"tom.monahan@edgewaterit.com", "title":"IT Manager", "company":"Edgewater Federal Solutions"},
    {"name":"Michael Hinman", "email":"michael.hinman@edgewaterit.com", "title":"IT Project Manager", "company":"Edgewater Federal Solutions"},
    {"name":"Dan Aldis", "email":"daldis@halvik.com", "title":"IT Program Manager", "company":"Halvik"},
    {"name":"Liam Connor", "email":"liam.connor@intercity.technology", "title":"Tech Services Manager", "company":"Intercity"},
    {"name":"Mark Hawkins-Wood", "email":"mark.hawkins-wood@intercity.technology", "title":"Head of Cloud & Managed IT", "company":"Intercity"},
    {"name":"Stewart Nicol", "email":"stewart.nicol@intercity.technology", "title":"Head of Platforms", "company":"Intercity"},
    {"name":"Rick Korsak", "email":"rick.korsak@intercity.technology", "title":"IT Infrastructure Manager", "company":"Intercity"},
    {"name":"Ampem Dako", "email":"ampem.dako@intercity.technology", "title":"Managed IT Manager", "company":"Intercity"},
]

# Build CSV for /api/import
out = io.StringIO()
w = csv.writer(out)
w.writerow(["name","email","title","company","city","country"])
for l in leads:
    w.writerow([l["name"], l["email"], l["title"], l["company"], "", ""])
csv_data = out.getvalue()

# POST as multipart to /api/import
import urllib.request, mimetypes
boundary = "----formboundary123"
body = ""
body += "--" + boundary + chr(13) + chr(10)
body += chr(34) + chr(34)  # placeholder
body_bytes = (
    "--" + boundary + "\r\n" +
    "Content-Disposition: form-data; name=\"file\"; filename=\"m365.csv\"\r\n" +
    "Content-Type: text/csv\r\n\r\n" +
    csv_data + "\r\n" +
    "--" + boundary + "--\r\n"
).encode("utf-8")

req = urllib.request.Request(BASE + "/api/import",
    data=body_bytes,
    headers={"Content-Type": "multipart/form-data; boundary=" + boundary},
    method="POST")

try:
    r = urllib.request.urlopen(req, timeout=60)
    print("Import response:", r.read().decode())
except urllib.error.HTTPError as e:
    print("HTTPError:", e.code, e.read().decode()[:500])
except Exception as e:
    print("Error:", e)

# Verify by listing leads
try:
    r = urllib.request.urlopen(BASE + "/api/leads?per_page=20", timeout=30)
    d = json.loads(r.read().decode())
    print()
    print("Total leads now in DB:", d.get("total"))
    for l in d.get("leads", [])[:15]:
        print(f"  - id={l.get(\"id\")} {l.get(\"name\",\"\")[:30]} | {l.get(\"email\",\"\")[:40]} | source={l.get(\"source\",\"?\")}")
except Exception as e:
    print("Verify error:", e)
