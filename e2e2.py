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
    except Exception as e:
        return 0, {"error": str(e)[:200]}

log = []
log.append("=== HARDENED EMAIL SCRAPING E2E TEST ===")
log.append("")

# Search
t0 = time.time()
code, r = post("/api/search/v2/preview", {
    "country": "United Arab Emirates",
    "state":   "Dubai",
    "category":"IT services company",
})
log.append(f"Search: HTTP {code} in {time.time()-t0:.1f}s, found {len(r.get("results",[]))}")

if code != 200: 
    log.append(str(r))
else:
    results = r["results"]
    leads_to_enrich = [{"place_id":x["place_id"], "website":x["website"]} for x in results if x.get("website")]
    log.append(f"To enrich: {len(leads_to_enrich)}")
    log.append("")
    
    all_emails = {}
    failed_batches = 0
    BATCH = 4
    for i in range(0, len(leads_to_enrich), BATCH):
        batch = leads_to_enrich[i:i+BATCH]
        log.append(f"Batch {i//BATCH+1} ({len(batch)} leads):")
        t0 = time.time()
        code2, r2 = post("/api/search/v2/enrich_emails", {"leads": batch})
        elapsed = time.time() - t0
        if code2 == 200:
            emails = r2.get("emails", {})
            all_emails.update(emails)
            scraped = sum(1 for v in emails.values() if v.get("email_source")=="scraped")
            gen = sum(1 for v in emails.values() if v.get("email_source")=="generated")
            log.append(f"  OK {elapsed:.1f}s | scraped={scraped} generated={gen}")
        else:
            failed_batches += 1
            log.append(f"  FAIL {elapsed:.1f}s | {r2}")
    
    log.append("")
    log.append("=== FINAL ===")
    s = sum(1 for v in all_emails.values() if v.get("email_source")=="scraped")
    g = sum(1 for v in all_emails.values() if v.get("email_source")=="generated")
    log.append(f"Verified (scraped real emails): {s}")
    log.append(f"Generated (info@ fallback):     {g}")
    log.append(f"Failed batches:                 {failed_batches}")
    log.append("")
    log.append("Sample real emails found:")
    for pid, v in list(all_emails.items())[:20]:
        if v.get("email_source")=="scraped":
            biz = next((x for x in results if x.get("place_id")==pid), None)
            n = biz.get("name","?")[:40] if biz else "?"
            log.append(f"  {n} -> {v.get("email")}")

with open("e2e2.txt","w") as f: f.write(chr(10).join(log))
print(chr(10).join(log))
