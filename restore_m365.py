import urllib.request, json

BASE = "https://skymaxx-lead-engine.onrender.com"

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

# Build CSV string
csv_data = "name,email,title,company,city,country" + chr(10)
for name, email, title, company in leads:
    csv_data += name + "," + email + "," + title + "," + company + ",," + chr(10)

# Multipart upload
boundary = "------boundary12345"
body = ("--" + boundary + chr(13) + chr(10) +
    chr(34) + "Content-Disposition: form-data; name=" + chr(34) + "file" + chr(34) + "; filename=" + chr(34) + "m365.csv" + chr(34) + chr(13) + chr(10) +
    "Content-Type: text/csv" + chr(13) + chr(10) + chr(13) + chr(10) +
    csv_data + chr(13) + chr(10) +
    "--" + boundary + "--" + chr(13) + chr(10))

# Need to use bytes
body_bytes = ("--" + boundary + chr(13) + chr(10) +
    "Content-Disposition: form-data; name=" + chr(34) + "file" + chr(34) + "; filename=" + chr(34) + "m365.csv" + chr(34) + chr(13) + chr(10) +
    "Content-Type: text/csv" + chr(13) + chr(10) + chr(13) + chr(10) +
    csv_data + chr(13) + chr(10) +
    "--" + boundary + "--" + chr(13) + chr(10)).encode("utf-8")

req = urllib.request.Request(BASE + "/api/import",
    data=body_bytes,
    headers={"Content-Type": "multipart/form-data; boundary=" + boundary},
    method="POST")

try:
    r = urllib.request.urlopen(req, timeout=60)
    print("Import:", r.read().decode())
except urllib.error.HTTPError as e:
    print("HTTPError", e.code, e.read().decode()[:500])
except Exception as e:
    print("Err:", e)

# Verify
try:
    r = urllib.request.urlopen(BASE + "/api/leads?per_page=20", timeout=30)
    d = json.loads(r.read().decode())
    print()
    print("Total leads now:", d.get("total"))
    for l in d.get("leads", [])[:15]:
        line = "  - id=" + str(l.get("id")) + " | " + str(l.get("name",""))[:30] + " | " + str(l.get("email",""))[:40] + " | source=" + str(l.get("source","?"))
        print(line)
except Exception as e:
    print("Verify err:", e)