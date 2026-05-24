import urllib.request, json
BASE = "https://skymaxx-lead-engine.onrender.com"

def post(p, body):
    try:
        req = urllib.request.Request(BASE+p,
            data=json.dumps(body).encode(),
            headers={"Content-Type":"application/json"},
            method="POST")
        r = urllib.request.urlopen(req, timeout=90)
        return r.getcode(), json.loads(r.read().decode())
    except Exception as e:
        return 0, {"error": str(e)[:120]}

log = []
log.append("=== EMAIL SCRAPING LIVE TEST ===")
log.append("")
log.append("Searching: IT companies in Dubai, UAE...")
log.append("(This will scrape websites for real emails — expect 20-40s)")
log.append("")

code, r = post("/api/search/v2/preview", {
    "country": "United Arab Emirates",
    "state":   "Dubai",
    "category":"IT services company",
})

if code != 200:
    log.append("FAIL: HTTP " + str(code) + " | " + str(r))
else:
    results = r.get("results", [])
    log.append("HTTP 200 - found " + str(len(results)) + " businesses")
    log.append("")

    # Breakdown
    scraped = [x for x in results if x.get("email_source") == "scraped"]
    generated = [x for x in results if x.get("email_source") == "generated"]
    none = [x for x in results if x.get("email_source") == "none"]
    log.append("Email breakdown:")
    log.append("  Verified (scraped from website): " + str(len(scraped)))
    log.append("  Generated (info@domain.com):     " + str(len(generated)))
    log.append("  No email at all:                 " + str(len(none)))
    log.append("")

    log.append("=== Sample results (first 10) ===")
    for i, b in enumerate(results[:10]):
        src = b.get("email_source", "?")
        icon = "[VERIFIED]" if src == "scraped" else "[GUESS]   " if src == "generated" else "[NO EMAIL]"
        log.append(f"{i+1}. {icon} {b.get("name","")[:40]}")
        log.append(f"          email:   {b.get("email","(none)")}")
        log.append(f"          website: {b.get("website","(none)")[:60]}")

with open("email_test.txt","w") as f: f.write(chr(10).join(log))
print(chr(10).join(log))
