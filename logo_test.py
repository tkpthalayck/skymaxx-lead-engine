
import urllib.request, json, hashlib

BASE = "https://skymaxx-lead-engine.onrender.com"

log = []
def L(m): log.append(str(m)); print(m, flush=True)

L("=" * 60)
L("LOGO INTEGRATION VERIFICATION")
L("=" * 60)
L("")

# 1. Logo file accessible?
L("=== 1. Static logo file ===")
for path in ["/static/logo.png", "/static/favicon.png"]:
    try:
        r = urllib.request.urlopen(BASE + path, timeout=20)
        body = r.read()
        L(f"  {path}: HTTP {r.getcode()} | {len(body)} bytes | content-type: {r.headers.get('Content-Type')}")
        # Verify it is the right image by hashing
        h = hashlib.md5(body).hexdigest()
        L(f"    MD5: {h[:16]}")
    except urllib.error.HTTPError as e:
        L(f"  {path}: HTTP {e.code} — {e.read().decode()[:200]}")
    except Exception as e:
        L(f"  {path}: ERROR — {e}")
L("")

# 2. HTML has the right tags?
L("=== 2. HTML structure ===")
html = urllib.request.urlopen(BASE + "/", timeout=20).read().decode()
checks = {
    "Logo image tag":           "/static/logo.png" in html,
    "Click-to-home (goHome)":   "onclick=\"goHome()" in html,
    "goHome function":          "function goHome" in html,
    "Favicon link":             "/static/favicon.png" in html,
    "Old ⚡ SKYMAXX removed":   "⚡ SKYMAXX" not in html,
    "Alt text present":         "SKYMAXX Technologies" in html,
}
for k, v in checks.items():
    L(f"  {k:30}: {'✓' if v else '✗'}")
L("")

# 3. Locate logo HTML in actual output
L("=== 3. Logo HTML snippet from live page ===")
import re
m = re.search(r"<div class=\"logo\"[^>]*onclick.{0,500}", html)
if m:
    L(m.group(0)[:500])
else:
    L("  Logo div with onclick not found in served HTML!")

open("logo_test.txt","w").write(chr(10).join(log))
