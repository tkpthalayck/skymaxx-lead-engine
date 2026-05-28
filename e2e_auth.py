import urllib.request, json, http.cookiejar
BASE='https://skymaxx-lead-engine.onrender.com'
out=[]
def L(m): out.append(str(m)); print(m,flush=True)

L('='*60); L('END-TO-END AUTH FLOW TEST'); L('='*60)

# Build a cookie-aware opener (like a browser session)
cookiejar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookiejar))

# 1. POST /login with credentials
L(''); L('1. POST /login (admin / SKYMAXX@2026)')
try:
    data = 'username=admin&password=SKYMAXX@2026'.encode()
    req = urllib.request.Request(BASE+'/login', data=data, method='POST',
        headers={'Content-Type':'application/x-www-form-urlencoded'})
    r = opener.open(req, timeout=40)
    L('   HTTP '+str(r.getcode())+' (redirected: '+r.url+')')
    cookies = [c.name+'='+c.value[:25]+'...' for c in cookiejar]
    L('   Cookies stored: '+str(cookies))
except urllib.error.HTTPError as e:
    L('   HTTP '+str(e.code)+': '+e.read().decode()[:200])

# 2. Use the cookie to call /api/stats (should now succeed)
L(''); L('2. GET /api/stats WITH session cookie (should be 200)')
try:
    req = urllib.request.Request(BASE+'/api/stats')
    r = opener.open(req, timeout=30)
    L('   HTTP '+str(r.getcode())+' ✓')
    s = json.loads(r.read())
    L('   total_leads: '+str(s.get('total_leads')))
except urllib.error.HTTPError as e:
    L('   HTTP '+str(e.code)+' ✗: '+e.read().decode()[:200])

# 3. Use the cookie to do a Quick Search (the user's actual flow)
L(''); L('3. POST /api/search/v2/preview WITH session cookie')
try:
    body = json.dumps({'source':'google_maps','country':'AE','state':'Dubai','category':'restaurant'}).encode()
    req = urllib.request.Request(BASE+'/api/search/v2/preview', data=body, method='POST',
        headers={'Content-Type':'application/json'})
    r = opener.open(req, timeout=60)
    L('   HTTP '+str(r.getcode())+' ✓ — SEARCH WORKS')
    d = json.loads(r.read())
    L('   Results: '+str(d.get('found') or len(d.get('results',[]))))
except urllib.error.HTTPError as e:
    L('   HTTP '+str(e.code)+' ✗: '+e.read().decode()[:200])
except Exception as e:
    L('   ERR: '+str(e)[:200])

# 4. Verify no-auth still blocks
L(''); L('4. Same search WITHOUT cookie (should be 401)')
try:
    body = json.dumps({'source':'google_maps','country':'AE'}).encode()
    req = urllib.request.Request(BASE+'/api/search/v2/preview', data=body, method='POST',
        headers={'Content-Type':'application/json'})
    r = urllib.request.urlopen(req, timeout=30)
    L('   HTTP '+str(r.getcode())+' ⚠ should have been 401')
except urllib.error.HTTPError as e:
    L('   HTTP '+str(e.code)+' ✓ correctly blocked')

# 5. Verify session config in served HTML
L(''); L('5. fetch credentials override present?')
try:
    html = urllib.request.urlopen(BASE+'/login', timeout=20).read().decode()
    # login page won't have it; let's hit / with cookie
    req = urllib.request.Request(BASE+'/')
    r = opener.open(req, timeout=30); html = r.read().decode()
    L('   _origFetch override: '+('YES ✓' if '_origFetch' in html else 'NO'))
    L('   credentials = same-origin: '+('YES ✓' if 'same-origin' in html else 'NO'))
except Exception as e:
    L('   ERR: '+str(e)[:120])

with open('e2e_auth.txt','w') as f: f.write(chr(10).join(out))
