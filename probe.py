import urllib.request, json, http.cookiejar
BASE='https://skymaxx-lead-engine.onrender.com'
out=[]
def L(m): out.append(str(m)); print(m,flush=True)

L('='*60); L('PROBE: what does the search endpoint return?'); L('='*60)

cookiejar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookiejar))

# Login
L(''); L('Step 1: Login')
data = 'username=admin&password=SKYMAXX@2026'.encode()
req = urllib.request.Request(BASE+'/login', data=data, method='POST',
    headers={'Content-Type':'application/x-www-form-urlencoded'})
r = opener.open(req, timeout=40)
L('  HTTP '+str(r.getcode()))
L('  Final URL: '+r.url)
L('  Cookies: '+str([c.name for c in cookiejar]))

# Now search WITH the cookie
L(''); L('Step 2: POST /api/search/v2/preview with cookie')
body = json.dumps({'source':'google_maps','country':'AE','state':'Dubai','category':'restaurant'}).encode()
req = urllib.request.Request(BASE+'/api/search/v2/preview', data=body, method='POST',
    headers={'Content-Type':'application/json'})
try:
    r = opener.open(req, timeout=60)
    body_text = r.read().decode()
    L('  HTTP '+str(r.getcode()))
    L('  Content-Type: '+str(r.headers.get('Content-Type')))
    L('  Body starts with: '+repr(body_text[:200]))
    L('  Body length: '+str(len(body_text)))
    # Is it JSON or HTML?
    if body_text.lstrip().startswith('<'):
        L('  *** RESPONSE IS HTML — this is the bug ***')
        # Show key html signals
        if 'login' in body_text.lower(): L('  HTML contains "login" — got login page')
        if 'error' in body_text.lower()[:500]: L('  HTML contains "error" — got error page')
        # Try to extract title
        import re
        ti = re.search(r'<title>([^<]+)</title>', body_text, re.I)
        if ti: L('  HTML <title>: '+ti.group(1))
    else:
        try:
            d = json.loads(body_text)
            L('  JSON parsed OK. Keys: '+str(list(d.keys())[:8]))
            L('  Results count: '+str(d.get('found') or len(d.get('results',[]))))
        except: L('  Could not parse JSON')
except urllib.error.HTTPError as e:
    body_text = e.read().decode()
    L('  HTTP '+str(e.code))
    L('  Content-Type: '+str(e.headers.get('Content-Type')))
    L('  Body: '+repr(body_text[:400]))

# Also check a working endpoint
L(''); L('Step 3: GET /api/stats with cookie (control)')
try:
    r = opener.open(BASE+'/api/stats', timeout=30)
    L('  HTTP '+str(r.getcode())+' ✓ '+str(r.headers.get('Content-Type')))
except urllib.error.HTTPError as e:
    L('  HTTP '+str(e.code))
    L('  Body: '+e.read().decode()[:200])

with open('probe.txt','w') as f: f.write(chr(10).join(out))
