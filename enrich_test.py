import urllib.request, json, time
BASE = "https://skymaxx-lead-engine.onrender.com"

def post(p, body, timeout=90):
    try:
        req = urllib.request.Request(BASE+p,
            data=json.dumps(body).encode(),
            headers={"Content-Type":"application/json"},
            method="POST")
        r = urllib.request.urlopen(req, timeout=timeout)
        return r.getcode(), json.loads(r.read().decode())
    except Exception as e:
        return 0, {"error": str(e)[:200]}

log = []
log.append("=== EMAIL ENRICHMENT END-TO-END TEST ===")
log.append("")

# Step 1: fast search (should return in <30s)
log.append("STEP 1: Fast search (no scraping)")
t0 = time.time()
code, r = post("/api/search/v2/preview", {
    "country": "United Arab Emirates",
    "state":   "Dubai",
    "category":"IT services company",
}, timeout=60)
elapsed = time.time() - t0
log.append(f"  HTTP {code} in {elapsed:.1f}s")

if code != 200:
    log.append(f"  FAIL: {r}")
else:
    results = r.get("results", [])
    log.append(f"  Found {len(results)} businesses")
    with_website = [x for x in results if x.get("website")]
    log.append(f"  With website: {len(with_website)}")
    pending = [x for x in results if x.get("email_source") == "pending"]
    log.append(f"  Email source pending (ready to enrich): {len(pending)}")

# Step 2: enrich emails in batches of 6
if code == 200 and results:
    log.append("")
    log.append("STEP 2: Enrich emails (chunked, 6 per call)")
    leads_to_enrich = [{"place_id":x["place_id"], "website":x["website"]} for x in results if x.get("website")]
    
    all_emails = {}
    for i in range(0, len(leads_to_enrich), 6):
        batch = leads_to_enrich[i:i+6]
        log.append(f"  Batch {i//6 + 1}: {len(batch)} leads...")
        t0 = time.time()
        code2, r2 = post("/api/search/v2/enrich_emails", {"leads": batch}, timeout=70)
        elapsed = time.time() - t0
        log.append(f"    HTTP {code2} in {elapsed:.1f}s")
        if code2 == 200:
            emails = r2.get("emails", {})
            all_emails.update(emails)
            scraped = sum(1 for v in emails.values() if v.get("email_source") == "scraped")
            gen = sum(1 for v in emails.values() if v.get("email_source") == "generated")
            log.append(f"    Scraped: {scraped}, Generated: {gen}")
        else:
            log.append(f"    FAIL: {r2}")
            break
    
    log.append("")
    log.append("=== FINAL RESULTS ===")
    scraped_total = sum(1 for v in all_emails.values() if v.get("email_source") == "scraped")
    gen_total = sum(1 for v in all_emails.values() if v.get("email_source") == "generated")
    log.append(f"Total verified emails: {scraped_total}")
    log.append(f"Total generated emails: {gen_total}")
    log.append("")
    log.append("Sample of REAL scraped emails:")
    for pid, v in list(all_emails.items())[:10]:
        if v.get("email_source") == "scraped":
            # Find the business name
            biz = next((x for x in results if x.get("place_id") == pid), None)
            name = biz.get("name", "?") if biz else "?"
            log.append(f"  [VERIFIED] {name[:40]} -> {v.get("email")}")

with open("enrich_test.txt","w") as f: f.write(chr(10).join(log))
print(chr(10).join(log))
