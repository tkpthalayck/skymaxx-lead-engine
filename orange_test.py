
import urllib.request, json

ORANGE_URL = "https://www.orangeslice.ai/mcp"
ORANGE_KEY = "osk_2ebad93f315f7f54b13887e6f871391f95681071"

def call(method, params=None, id_=1):
    payload = {"jsonrpc": "2.0", "id": id_, "method": method}
    if params is not None: payload["params"] = params
    req = urllib.request.Request(ORANGE_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": "Bearer " + ORANGE_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        method="POST")
    try:
        r = urllib.request.urlopen(req, timeout=60)
        body = r.read().decode()
        # Parse SSE
        for line in body.split(chr(10)):
            if line.startswith("data: "):
                return json.loads(line[6:])
        return json.loads(body)
    except urllib.error.HTTPError as e:
        return {"_http_error": e.code, "body": e.read().decode()[:600]}
    except Exception as e:
        return {"_error": str(e)}

log = []
def L(m): log.append(str(m)); print(m, flush=True)

# Get linkedin_search detailed schema (re-list tools so we can find its full input schema)
L("=== STEP 1: Get linkedin_search full schema ===")
r = call("tools/list", {}, id_=1)
if "result" in r:
    for t in r["result"].get("tools", []):
        if t.get("name") == "linkedin_search":
            L("Description: " + str(t.get("description","")))
            L("Input schema:")
            L(json.dumps(t.get("inputSchema"), indent=2))
            break

# Try a simple LinkedIn search — find IT Managers in UAE
L("")
L("=== STEP 2: Search LinkedIn — IT Manager OR IT Director in UAE ===")
sql = """
SELECT firstName, lastName, headline, currentTitle, currentCompany, location, profileUrl
FROM people
WHERE LOWER(currentTitle) LIKE '%it manager%' OR LOWER(currentTitle) LIKE '%it director%'
  AND LOWER(location) LIKE '%united arab emirates%'
LIMIT 5
"""
r = call("tools/call", {"name": "linkedin_search", "arguments": {"sql": sql}}, id_=2)
L("Response type: " + str(type(r).__name__))
if "result" in r:
    content = r["result"].get("content", [])
    for c in content:
        if c.get("type") == "text":
            text = c.get("text", "")
            L("  Text result (first 3000 chars):")
            L(text[:3000])
elif "error" in r:
    L("  Error: " + json.dumps(r["error"])[:500])
else:
    L("  Unexpected: " + json.dumps(r)[:1500])

L("")
L("=== STEP 3: Try Ocean.io people search ===")
r = call("tools/call", {
    "name": "ocean_search_people",
    "arguments": {
        "titles": ["IT Manager", "IT Director"],
        "locations": ["United Arab Emirates"],
        "limit": 5
    }
}, id_=3)
if "result" in r:
    content = r["result"].get("content", [])
    for c in content:
        if c.get("type") == "text":
            L("  " + c.get("text","")[:2500])
elif "error" in r:
    L("  Error: " + json.dumps(r["error"])[:500])
else:
    L("  Unexpected: " + json.dumps(r)[:1500])

L("")
L("=== STEP 4: company_get_employees_from_linkedin for OneRail ===")
r = call("tools/call", {
    "name": "company_get_employees_from_linkedin",
    "arguments": {
        "companySlug": "onerail",
        "titleVariations": ["IT Manager", "CTO", "CIO"],
        "limit": 5
    }
}, id_=4)
if "result" in r:
    content = r["result"].get("content", [])
    for c in content:
        if c.get("type") == "text":
            L("  " + c.get("text","")[:2500])
elif "error" in r:
    L("  Error: " + json.dumps(r["error"])[:500])

open("orange_test.txt","w").write(chr(10).join(log))
