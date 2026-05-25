
import urllib.request, json
BASE = "https://skymaxx-lead-engine.onrender.com"

log = []
def L(m): log.append(m); print(m, flush=True)

L("=== CHECK DEBUG ENDPOINT ===")
try:
    r = urllib.request.urlopen(BASE + "/api/debug/db", timeout=45)
    info = json.loads(r.read().decode())
    for k, v in info.items():
        if k != "DATABASE_URL_prefix":
            L("  " + k + ": " + str(v)[:120])
except Exception as e:
    L("  Error: " + str(e))

# Re-import leads with company column populated (delete existing first to ensure clean state)
L("")
L("=== RE-IMPORTING WITH PROPER COMPANY COLUMN ===")
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

boundary = "------br554433"
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
    L("HTTPError " + str(e.code) + ": " + e.read().decode()[:400])
except Exception as e:
    L("Error: " + str(e))

# Verify leads + company field
L("")
L("=== VERIFY LEADS WITH COMPANY FIELD ===")
try:
    r = urllib.request.urlopen(BASE + "/api/leads?per_page=20", timeout=30)
    d = json.loads(r.read().decode())
    L("Total: " + str(d.get("total", 0)))
    for l in d.get("leads", [])[:13]:
        L("  - id=" + str(l.get("id")) + " | " + str(l.get("name",""))[:25] + " | company=" + str(l.get("company","NONE"))[:30] + " | title=" + str(l.get("title","NONE"))[:30])
except Exception as e:
    L("Error: " + str(e))

# Test the email template preview shows proper company
L("")
L("=== TEST EMAIL TEMPLATE PERSONALIZATION ===")
try:
    r = urllib.request.urlopen(BASE + "/api/leads?per_page=5", timeout=30)
    d = json.loads(r.read().decode())
    if d.get("leads"):
        lead = d["leads"][0]
        L("Test lead: " + lead.get("name","") + " at " + lead.get("company","NONE"))
        # Trigger a template preview
        req = urllib.request.Request(BASE + "/api/sequence/preview",
            data=json.dumps({"lead_id": lead["id"], "step": 1}).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            pr = urllib.request.urlopen(req, timeout=30)
            preview = json.loads(pr.read().decode())
            subject = preview.get("subject", "")
            body = preview.get("body", "")
            L("  Preview subject: " + subject[:100])
            L("  Body has {{company}} unreplaced: " + str("{{company}}" in body))
            L("  Body has lead name as company: " + str(lead.get("name","") in body and "{{company}}" not in body))
            # Show actual company text in body
            if "Maxima" in body:
                L("  ✓ Body correctly contains company name 'Maxima'")
            if "Aaron Barak" in body and lead.get("name") == "Aaron Barak":
                L("  Note: name appears in body (could be greeting)")
        except urllib.error.HTTPError as e:
            L("  Preview HTTPError: " + str(e.code) + " " + e.read().decode()[:200])
        except Exception as e:
            L("  Preview error: " + str(e))
except Exception as e:
    L("Test error: " + str(e))

open("final_fix.txt","w").write(chr(10).join(log))
