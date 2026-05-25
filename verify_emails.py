
import urllib.request, json

BASE = "https://skymaxx-lead-engine.onrender.com"

def get(p, timeout=45):
    try:
        r = urllib.request.urlopen(BASE+p, timeout=timeout)
        return r.getcode(), r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]
    except Exception as e:
        return 0, str(e)[:200]

log = []
def L(m): log.append(m); print(m, flush=True)

L("=== VERIFY UPDATED EMAIL SEQUENCE ===")
L("")

# Check the new templates
code, body = get("/api/sequence/templates")
L("/api/sequence/templates -> HTTP " + str(code))
if code == 200:
    try:
        templates = json.loads(body)
        L("Templates returned: " + str(len(templates)))
        for t in templates:
            L("  Step " + str(t.get("step")) + " (Day +" + str(t.get("delay_days")) + "): " + t.get("subject", "")[:80])
        # Check that at least one source link is present
        sample_body = templates[0].get("body", "")
        L("")
        L("Sample (Email 1) checks:")
        L("  Has Verizon DBIR mention: " + ("True" if "Verizon" in sample_body else "False"))
        L("  Has source link: " + ("True" if "verizon.com" in sample_body else "False"))
        L("  Has IBM ref: " + ("True" if "IBM" in templates[1].get("body","") else "False"))
        L("  Has Microsoft.com link: " + ("True" if "microsoft.com" in sample_body.lower() else "False"))
        L("  Body length email 1: " + str(len(sample_body)) + " bytes")
    except Exception as e:
        L("Parse error: " + str(e))

# Check email_log endpoint (Sent tab data source)
L("")
L("=== SENT TAB DATA STATE ===")
code, body = get("/api/log")
L("/api/log -> HTTP " + str(code))
if code == 200:
    try:
        d = json.loads(body)
        logs = d.get("log", []) if isinstance(d, dict) else d if isinstance(d, list) else []
        L("Total emails in email_log table: " + str(len(logs)))
        if logs:
            for e in logs[:5]:
                L("  - to=" + str(e.get("to_email",""))[:30] + " step=" + str(e.get("step")) + " status=" + str(e.get("status")))
    except Exception as e:
        L("Parse error: " + str(e))

# Check leads in sequence
L("")
code, body = get("/api/leads?per_page=20")
if code == 200:
    try:
        d = json.loads(body)
        leads = d.get("leads", [])
        in_seq = [l for l in leads if l.get("in_sequence")]
        L("Total leads: " + str(d.get("total", 0)))
        L("Leads in active sequence: " + str(len(in_seq)))
    except Exception as e:
        L("Parse error: " + str(e))

# Check active campaigns
code, body = get("/api/campaigns")
if code == 200:
    try:
        d = json.loads(body)
        cs = d.get("campaigns", []) if isinstance(d, dict) else []
        L("Total campaigns: " + str(len(cs)))
        for c in cs[:5]:
            L("  - " + str(c.get("name",""))[:30] + " status=" + str(c.get("status")) + " recipients=" + str(c.get("recipient_count")))
    except Exception as e:
        L("Parse error: " + str(e))

open("verify_emails.txt","w").write(chr(10).join(log))
