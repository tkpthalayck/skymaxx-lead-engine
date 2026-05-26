
import urllib.request, time, re
BASE = "https://skymaxx-lead-engine.onrender.com"

log = []
def L(m): log.append(str(m)); print(m, flush=True)

# Force fresh fetch with cache-buster
url = BASE + "/?_=" + str(int(time.time()))
html = urllib.request.urlopen(url, timeout=20).read().decode()
L("Fetched URL: " + url)
L("HTML size: " + str(len(html)))
L("")

# Check what is in the sidebar/logo area
m = re.search(r"<aside.{0,2000}", html)
if m:
    L("=== <aside> first 2000 chars ===")
    L(m.group(0)[:2000])

L("")
# Look for ANY reference to logo or skymaxx
L("=== Searches in served HTML ===")
for kw in ["⚡", "SKYMAXX", "logo.png", "favicon", "goHome", "/static/"]:
    cnt = html.count(kw)
    L("  " + kw + ": appears " + str(cnt) + " times")
L("")
# Show any /static references
for m in re.finditer(r"/static/[^\"\'\\s>]+", html):
    L("  static ref: " + m.group(0))
L("")
# Show any onclick=goHome references
for m in re.finditer(r"onclick=[\"\']goHome[^\"\']*[\"\']\\s*", html):
    L("  goHome ref: " + m.group(0))

open("compare.txt","w").write(chr(10).join(log))
