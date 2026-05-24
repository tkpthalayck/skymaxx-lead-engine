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
log.append("=== FINAL E2E TEST (after bug fixes) ===")

# Search
t0 = time.time()
code, r = post("/api/search/v2/preview", {
    "country": "United Arab Emirates",
    "state":   "Dubai",
    "category":"IT services company",
})
log.append(f"Search: HTTP {code} in {time.time()-t0:.1f}s")

if code != 200:
    log.append(str(r))
else:
    results = r["results"]
    log.append(f"Found {len(results)} businesses with {sum(1 for x in results if x.get("website"))} websites")
    leads_to_enrich = [{"place_id":x["place_id"], "website":x["website"]} for x in results if x.get("website")]

    all_emails = {}
    succ_batches = 0
    fail_batches = 0
    BATCH = 4
    for i in range(0, len(leads_to_enrich), BATCH):
        batch = leads_to_enrich[i:i+BATCH]
        t0 = time.time()
        code2, r2 = post("/api/search/v2/enrich_emails", {"leads": batch})
        elapsed = time.time() - t0
        if code2 == 200:
            succ_batches += 1
            emails = r2.get("emails", {})
            all_emails.update(emails)
            s = sum(1 for v in emails.values() if v.get("email_source")=="scraped")
            g = sum(1 for v in emails.values() if v.get("email_source")=="generated")
            log.append(f"Batch {i//BATCH+1}: OK {elapsed:.1f}s  scraped={s} generated={g}")
        else:
            fail_batches += 1
            log.append(f"Batch {i//BATCH+1}: FAIL {elapsed:.1f}s  {r2}")

    log.append("")
    log.append(f"=== RESULTS: {succ_batches} batches OK, {fail_batches} failed ===")
    s = sum(1 for v in all_emails.values() if v.get("email_source")=="scraped")
    g = sum(1 for v in all_emails.values() if v.get("email_source")=="generated")
    log.append(f"Verified emails (scraped from real websites): {s}")
    log.append(f"Generated fallback (info@domain):              {g}")
    log.append("")
    log.append("Real email samples:")
    for pid, v in list(all_emails.items())[:25]:
        if v.get("email_source")=="scraped":
            b = next((x for x in results if x.get("place_id")==pid), None)
            n = b.get("name","?")[:35] if b else "?"
            log.append(f"  {n} -> {v.get("email")}")

with open("final_e2e.txt","w") as f: f.write(chr(10).join(log))
print(chr(10).join(log))
