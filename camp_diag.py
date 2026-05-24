import urllib.request, json, time
BASE = "https://skymaxx-lead-engine.onrender.com"

def post(p, body, timeout=70):
    try:
        req = urllib.request.Request(BASE+p,
            data=json.dumps(body).encode(),
            headers={"Content-Type":"application/json"},
            method="POST")
        r = urllib.request.urlopen(req, timeout=timeout)
        return r.getcode(), json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try: body = json.loads(e.read().decode())
        except: body = {"raw": str(e)}
        return e.code, body
    except Exception as e:
        return 0, {"error": str(e)[:300]}

def get(p):
    try:
        r = urllib.request.urlopen(BASE+p, timeout=30)
        return r.getcode(), json.loads(r.read().decode())
    except Exception as e:
        return 0, {"error":str(e)[:200]}

log = []
log.append("=== CAMPAIGN CREATION FLOW DIAGNOSTIC ===")
log.append("")

# Step 1: Search
log.append("STEP 1: Search")
t0 = time.time()
code, r = post("/api/search/v2/preview", {
    "country": "United Arab Emirates",
    "state":   "Dubai",
    "category":"IT services company",
})
log.append(f"  HTTP {code} in {time.time()-t0:.1f}s")
if code != 200:
    log.append(f"  ERROR: {r}")
    with open("camp_diag.txt","w") as f: f.write(chr(10).join(log))
    exit()

results = r["results"][:5]  # take first 5
log.append(f"  Got {len(results)} leads (showing first 5)")
for x in results:
    log.append(f"  - {x.get("name","")[:30]} | email={x.get("email","NONE")[:40] or "NONE"} | website={bool(x.get("website"))}")

# Step 2: Enrich first batch
log.append("")
log.append("STEP 2: Enrich emails (first 4)")
batch = [{"place_id":x["place_id"], "website":x["website"]} for x in results[:4] if x.get("website")]
t0 = time.time()
code, r2 = post("/api/search/v2/enrich_emails", {"leads": batch})
log.append(f"  HTTP {code} in {time.time()-t0:.1f}s")
if code == 200:
    emails = r2.get("emails", {})
    log.append(f"  Got {len(emails)} email results")
    for x in results[:4]:
        em = emails.get(x["place_id"], {})
        x["email"] = em.get("email","")
        x["email_source"] = em.get("email_source","none")
        x["has_email"] = em.get("has_email",False)
        log.append(f"  - {x.get("name","")[:30]} -> {x.get("email") or "NONE"} ({x.get("email_source")})")

# Step 3: Save selected leads (THIS IS THE CRITICAL STEP)
log.append("")
log.append("STEP 3: Save selected leads (with full lead objects)")
selected = results[:3]  # take 3 with emails
t0 = time.time()
code, r3 = post("/api/search/v2/save_selected", {"leads": selected}, timeout=70)
log.append(f"  HTTP {code} in {time.time()-t0:.1f}s")
log.append(f"  Response: {r3}")

lead_ids = []
if code == 200:
    lead_ids = r3.get("lead_ids", [])
    log.append(f"  Saved {r3.get("saved",0)} leads, IDs: {lead_ids}")

# Step 4: Create campaign draft (THE FINAL STEP)
log.append("")
log.append("STEP 4: Create campaign draft")
if lead_ids:
    t0 = time.time()
    code, r4 = post("/api/campaigns/draft", {
        "name": "Test Campaign " + str(int(time.time())),
        "lead_ids": lead_ids
    }, timeout=70)
    log.append(f"  HTTP {code} in {time.time()-t0:.1f}s")
    if code == 200:
        log.append(f"  ✓ CAMPAIGN CREATED: id={r4.get("campaign_id")}, status={r4.get("status")}")
        log.append(f"  Recipient count: {r4.get("recipient_count")}")
        log.append(f"  Risk score: {r4.get("risk_score")}")
    else:
        log.append(f"  FAIL: {r4}")
else:
    log.append("  SKIPPED - no lead_ids from save step")

# Step 5: List campaigns to verify
log.append("")
log.append("STEP 5: List campaigns")
code, r5 = get("/api/campaigns")
if code == 200:
    cs = r5.get("campaigns", [])
    log.append(f"  Total campaigns: {len(cs)}")
    for c in cs[:5]:
        log.append(f"  - id={c.get("id")} name={c.get("name","")[:40]} status={c.get("status")} recipients={c.get("recipient_count")}")

with open("camp_diag.txt","w") as f: f.write(chr(10).join(log))
print(chr(10).join(log))
