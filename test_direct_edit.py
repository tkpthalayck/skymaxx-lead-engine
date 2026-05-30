"""End-to-end test for the new direct edit functionality."""
import json, urllib.request, urllib.parse, http.cookiejar, sys

BASE = "https://skymaxx-lead-engine.onrender.com"
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

failures = 0

def check(name, ok, detail=""):
    global failures
    if ok:
        print(f"  ✓ {name}" + (f": {detail}" if detail else ""))
    else:
        failures += 1
        print(f"  ✗ {name}" + (f": {detail}" if detail else ""))

# 1. Login
print("\n=== 1. Login ===")
data = urllib.parse.urlencode({"password": "SKYMAXX@2026"}).encode()
r = opener.open(urllib.request.Request(f"{BASE}/login", data=data,
    headers={"Content-Type": "application/x-www-form-urlencoded"}))
check("Login", r.status == 200, f"HTTP {r.status}")

# 2. Get templates - check 'edited' field exists
print("\n=== 2. GET /api/sequence/templates ===")
r = opener.open(f"{BASE}/api/sequence/templates")
tpl = json.loads(r.read())
check("Got 5 templates", len(tpl) == 5, f"got {len(tpl)}")
check("All templates have 'edited' field", all("edited" in t for t in tpl))
for t in tpl:
    print(f"     step {t['step']}: edited={t.get('edited')}, subj={t['subject'][:55]}")

# 3. Save edit
print("\n=== 3. POST save_template ===")
payload = json.dumps({
    "step": 1,
    "subject": "DIAG TEST - Step 1 edited",
    "body": "<p>Test body for {{name}} at {{company}}.</p>"
}).encode()
r = opener.open(urllib.request.Request(f"{BASE}/api/sequence/save_template",
    data=payload, headers={"Content-Type": "application/json"}, method="POST"))
resp = json.loads(r.read())
check("Save returns ok", resp.get("ok") == True, str(resp))

# 4. Verify edit persisted
print("\n=== 4. Verify edit persisted ===")
r = opener.open(f"{BASE}/api/sequence/templates")
tpl = json.loads(r.read())
s1 = next(t for t in tpl if t["step"] == 1)
check("Step 1 has edited=True", s1.get("edited") == True)
check("Step 1 subject updated", "DIAG TEST" in s1["subject"], s1["subject"][:80])
check("Step 1 has edited_by", s1.get("edited_by") is not None, f"edited_by={s1.get('edited_by')}")

# 5. Reset
print("\n=== 5. POST reset_template/1 ===")
r = opener.open(urllib.request.Request(f"{BASE}/api/sequence/reset_template/1",
    method="POST", data=b""))
resp = json.loads(r.read())
check("Reset returns ok", resp.get("ok") == True, str(resp))

# 6. Verify reset
print("\n=== 6. Verify reset ===")
r = opener.open(f"{BASE}/api/sequence/templates")
tpl = json.loads(r.read())
s1 = next(t for t in tpl if t["step"] == 1)
check("Step 1 edited=False after reset", s1.get("edited") == False)
check("Step 1 subject reverted to default", "DIAG TEST" not in s1["subject"], s1["subject"][:80])

# 7. Audit assumptions in ALL templates
print("\n=== 7. Audit all 5 templates for infrastructure assumptions ===")
bad_phrases = ["their tenants", "1 in 323", "43% of m365", "61% of smbs were breached", "your tenant"]
for t in tpl:
    combined = (t["body"] + " " + t["subject"]).lower()
    found = [p for p in bad_phrases if p in combined]
    check(f"step{t['step']} clean", len(found) == 0, str(found) if found else "no assumptions")

# 8. Test preview endpoint works
print("\n=== 8. Test /api/sequence/preview/<step> ===")
for step in [1, 2, 3, 4, 5]:
    r = opener.open(f"{BASE}/api/sequence/preview/{step}?name=Sarah")
    pv = json.loads(r.read())
    check(f"Preview step {step}", "subject" in pv and "body" in pv, pv.get("subject","")[:50])

# 9. Test save_template with invalid input
print("\n=== 9. Validation tests ===")
try:
    r = opener.open(urllib.request.Request(f"{BASE}/api/sequence/save_template",
        data=b'{"step":99,"subject":"x","body":"y"}',
        headers={"Content-Type":"application/json"}, method="POST"))
    resp = json.loads(r.read())
    check("Invalid step rejected", False, "should have returned 400")
except urllib.error.HTTPError as e:
    check("Invalid step rejected", e.code == 400, f"HTTP {e.code}")

try:
    r = opener.open(urllib.request.Request(f"{BASE}/api/sequence/save_template",
        data=b'{"step":1,"subject":"","body":"y"}',
        headers={"Content-Type":"application/json"}, method="POST"))
    resp = json.loads(r.read())
    check("Empty subject rejected", False, "should have returned 400")
except urllib.error.HTTPError as e:
    check("Empty subject rejected", e.code == 400, f"HTTP {e.code}")

print(f"\n=== RESULT: {failures} failures ===")
sys.exit(failures)
