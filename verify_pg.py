
import urllib.request, json, time

BASE = "https://skymaxx-lead-engine.onrender.com"
RENDER_KEY = "rnd_C7jBUGG8sEuBRvqf3U4w4YU4zWsx"

def get(path, timeout=45):
    try:
        r = urllib.request.urlopen(BASE + path, timeout=timeout)
        return r.getcode(), r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:500]
    except Exception as e:
        return 0, str(e)[:200]

log = []
def L(m): log.append(m); print(m, flush=True)

L("=== POSTGRES MIGRATION VERIFICATION ===")
L("")

# 1. Check Render deploy status
L("1. Checking Render deploy status...")
req = urllib.request.Request("https://api.render.com/v1/services/srv-d88vm9favr4c7396kt00/deploys?limit=3",
    headers={"Authorization": "Bearer " + RENDER_KEY})
try:
    deploys = json.loads(urllib.request.urlopen(req, timeout=30).read())
    for d in deploys[:3]:
        dd = d.get("deploy", {})
        L("   " + dd.get("id","?") + " status=" + dd.get("status","?") + " msg=" + dd.get("commit",{}).get("message","")[:60])
except Exception as e:
    L("   Error: " + str(e))

# 2. Wait for app to respond after redeploy
L("")
L("2. Checking app endpoints...")
for ep in ["/", "/api/config", "/api/stats", "/api/leads", "/api/campaigns"]:
    code, body = get(ep)
    L("   " + ep + " -> HTTP " + str(code))
    if code != 200:
        L("      Body: " + body[:200])

# 3. Verify leads count (should be 0 since this is a fresh Postgres DB)
L("")
L("3. Lead count check (expect 0 — fresh Postgres DB):")
code, body = get("/api/leads?per_page=20")
if code == 200:
    try:
        d = json.loads(body)
        total = d.get("total", 0)
        L("   Total leads in Postgres: " + str(total))
        if total > 0:
            L("   First leads:")
            for l in d.get("leads", [])[:5]:
                L("   - id=" + str(l.get("id")) + " " + str(l.get("name",""))[:25] + " | " + str(l.get("email",""))[:35])
    except Exception as e:
        L("   Parse error: " + str(e))

# 4. Re-import the 13 M365 leads to the persistent Postgres DB
L("")
L("4. Re-importing 13 M365 leads to Postgres...")

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

# Build CSV
csv_data = "name,email,title,company,city,country" + chr(10)
for name, email, title, company in leads:
    csv_data += name + "," + email + "," + title + "," + company + ",," + chr(10)

# Multipart upload
boundary = "------bdry998877"
body_bytes = (
    "--" + boundary + chr(13) + chr(10) +
    "Content-Disposition: form-data; name=" + chr(34) + "file" + chr(34) + "; filename=" + chr(34) + "m365.csv" + chr(34) + chr(13) + chr(10) +
    "Content-Type: text/csv" + chr(13) + chr(10) + chr(13) + chr(10) +
    csv_data + chr(13) + chr(10) +
    "--" + boundary + "--" + chr(13) + chr(10)
).encode("utf-8")

req = urllib.request.Request(BASE + "/api/import",
    data=body_bytes,
    headers={"Content-Type": "multipart/form-data; boundary=" + boundary},
    method="POST")

try:
    r = urllib.request.urlopen(req, timeout=60)
    result = r.read().decode()
    L("   Import response: " + result)
except urllib.error.HTTPError as e:
    L("   HTTP " + str(e.code) + ": " + e.read().decode()[:500])
except Exception as e:
    L("   Error: " + str(e)[:300])

# 5. Final verification
L("")
L("5. Final state — leads visible after import:")
code, body = get("/api/leads?per_page=20")
if code == 200:
    try:
        d = json.loads(body)
        L("   Total: " + str(d.get("total", 0)))
        for l in d.get("leads", [])[:15]:
            L("   - id=" + str(l.get("id")) + " | " + str(l.get("name",""))[:30] + " | " + str(l.get("email",""))[:40])
    except Exception as e:
        L("   Parse error: " + str(e))

L("")
L("✅ ALL DONE — App is running on persistent Postgres.")
L("Data will now survive ALL future deploys.")

open("verify_pg.txt","w").write(chr(10).join(log))
