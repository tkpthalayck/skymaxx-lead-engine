import urllib.request, json, http.cookiejar
BASE='https://skymaxx-lead-engine.onrender.com'
out=[]
def L(m): out.append(str(m)); print(m,flush=True)

L('FINAL VERIFY: ALL API responses are JSON, never HTML')
L('='*55)
cookiejar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookiejar))

# 1. API without auth → must be JSON 401 (never HTML)
L(''); L('1. /api/stats WITHOUT auth')
try:
    r = urllib.request.urlopen(BASE+'/api/stats', timeout=30)
    L('  HTTP '+str(r.getcode())+' Content-Type: '+str(r.headers.get('Content-Type')))
except urllib.error.HTTPError as e:
    body = e.read().decode()
    L('  HTTP '+str(e.code)+' Content-Type: '+str(e.headers.get('Content-Type')))
    L('  Body is JSON: '+('YES ✓' if body.lstrip().startswith('{') else 'NO ✗'))
    L('  Body: '+body[:120])

# 2. Login
L(''); L('2. Login')
data = 'username=admin&password=SKYMAXX@2026'.encode()
req = urllib.request.Request(BASE+'/login', data=data, method='POST',
    headers={'Content-Type':'application/x-www-form-urlencoded'})
r = opener.open(req, timeout=40)
L('  HTTP '+str(r.getcode())+' → '+r.url)

# 3. Search WITH auth
L(''); L('3. Search WITH auth')
body = json.dumps({'source':'google_maps','country':'AE','state':'Dubai','category':'restaurant'}).encode()
req = urllib.request.Request(BASE+'/api/search/v2/preview', data=body, method='POST',
    headers={'Content-Type':'application/json'})
try:
    r = opener.open(req, timeout=60)
    L('  HTTP '+str(r.getcode())+' Content-Type: '+str(r.headers.get('Content-Type')))
    d = json.loads(r.read())
    L('  Results: '+str(d.get('found') or len(d.get('results',[]))))
except urllib.error.HTTPError as e:
    L('  HTTP '+str(e.code)+': '+e.read().decode()[:200])

# 4. Hit a non-existent /api/* path — should return JSON 404
L(''); L('4. /api/nonexistent (test 404 handler)')
try:
    r = opener.open(BASE+'/api/nonexistent', timeout=20)
    L('  HTTP '+str(r.getcode())+' Content-Type: '+str(r.headers.get('Content-Type')))
except urllib.error.HTTPError as e:
    body = e.read().decode()
    L('  HTTP '+str(e.code)+' Content-Type: '+str(e.headers.get('Content-Type')))
    L('  Body is JSON: '+('YES ✓' if body.lstrip().startswith('{') else 'NO ✗ '+body[:120]))

# 5. Confirm fetch wrapper deployed in HTML
L(''); L('5. Bulletproof fetch wrapper in served HTML')
r = opener.open(BASE+'/', timeout=30)
html = r.read().decode()
L('  Session-expired handler: '+('YES ✓' if 'session_expired' in html else 'NO'))
L('  401 auto-redirect:       '+('YES ✓' if '/login?next=' in html else 'NO'))

with open('verify_final.txt','w') as f: f.write(chr(10).join(out))
