import urllib.request, json
BASE = "https://skymaxx-lead-engine.onrender.com"

def get(p):
    try:
        r = urllib.request.urlopen(BASE+p, timeout=45)
        return r.getcode(), r.read().decode()
    except Exception as e:
        return 0, str(e)[:200]

# Verify all functions present in live HTML
code, html = get("/")
log = []
log.append("=== LIVE HTML FUNCTION CHECK ===")
log.append(f"HTML size: {len(html)} bytes")
log.append("")

required = ["showApprovalModal","closeApprovalModal","campaignAction","loadCampaigns",
            "reopenApproval","campaignPause","campaignResume","campaignStop",
            "newGroup","loadGroups","deleteGroup","viewGroup","campaignFromGroup",
            "openAIPanel","closeAIPanel","runAIAction"]

all_ok = True
for fn in required:
    has = ("function " + fn + "(") in html or ("function " + fn + " (") in html
    if not has and "async function " + fn in html:
        has = True
    log.append(("PASS " if has else "FAIL ") + fn)
    if not has: all_ok = False

log.append("")
log.append("=== END-TO-END CAMPAIGN CREATION ===")

# Now actually create a campaign via the flow
def post(p, body):
    try:
        req = urllib.request.Request(BASE+p, data=json.dumps(body).encode(),
            headers={"Content-Type":"application/json"}, method="POST")
        return urllib.request.urlopen(req, timeout=60).read().decode()
    except urllib.error.HTTPError as e:
        return "ERROR " + str(e.code) + " " + e.read().decode()[:300]
    except Exception as e:
        return "EXC " + str(e)[:300]

# Search
r1 = post("/api/search/v2/preview", {"country":"United Arab Emirates","state":"Dubai","category":"IT services company"})
try:
    res = json.loads(r1)["results"][:3]
    log.append("Search OK: " + str(len(res)) + " leads")
except:
    log.append("Search FAILED: " + r1[:200])
    res = []

if res:
    # Save selected
    r2 = post("/api/search/v2/save_selected", {"leads": res})
    try:
        lead_ids = json.loads(r2)["lead_ids"]
        log.append("Save OK: lead_ids=" + str(lead_ids))
    except:
        log.append("Save FAILED: " + r2[:200])
        lead_ids = []
    
    if lead_ids:
        # Create campaign draft
        r3 = post("/api/campaigns/draft", {"name":"Final Test Campaign","lead_ids":lead_ids})
        try:
            d = json.loads(r3)
            log.append("Draft OK: campaign_id=" + str(d.get("campaign_id")))
            log.append("  Status: " + str(d.get("status")))
            log.append("  Recipients: " + str(d.get("recipient_count")))
            log.append("  Risk Score: " + str(d.get("risk_score")))
            log.append("  Has sequence_steps: " + str(bool(d.get("sequence_steps"))))
            log.append("  Has domain_health: " + str(bool(d.get("domain_health"))))
        except:
            log.append("Draft FAILED: " + r3[:300])

with open("e2e_final.txt","w") as f: f.write(chr(10).join(log))
print(chr(10).join(log))
