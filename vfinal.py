import urllib.request, json, http.cookiejar
import base64 as b64
BASE='https://skymaxx-lead-engine.onrender.com'
out=[]
def L(m): out.append(str(m)); print(m,flush=True)

L('='*65)
L('FINAL VERIFICATION')
L('='*65)

cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
data = 'username=admin&password=SKYMAXX@2026'.encode()
req = urllib.request.Request(BASE+'/login', data=data, method='POST',
    headers={'Content-Type':'application/x-www-form-urlencoded'})
op.open(req, timeout=40)
L('Login OK')

# 1. Logo file — check transparency
L(''); L('1. LOGO TRANSPARENCY')
r = op.open(BASE+'/static/logo.png', timeout=20)
data = r.read()
L(f'  /static/logo.png: HTTP {r.getcode()} | {len(data):,} bytes')
if data[:8] == b'\x89PNG\r\n\x1a\n':
    ctype = data[25]
    type_names = {0:'grayscale',2:'RGB',3:'palette',4:'gray+alpha',6:'RGBA'}
    L(f'  PNG color type: {ctype} ({type_names.get(ctype,"?")})')
    L(f'  {"CHECK" if ctype in (4,6) else "FAIL"} Has alpha (transparent corners)')

# 2. Sample email content — render a test campaign to confirm new template
L(''); L('2. SEND A TEST EMAIL TO CONFIRM NEW TEMPLATE')
# Try to find any campaign that's running
r = op.open(BASE+'/api/campaigns', timeout=30)
camps = json.loads(r.read()).get('campaigns', [])
running = [c for c in camps if c.get('status') in ('running','approved')]
L(f'  Running/approved campaigns: {len(running)}')

# Use the email preview endpoint if available (or just check rendered HTML)
# Most apps have /api/sequence/preview or similar
for endpoint in ['/api/sequence/queue', '/api/sequence/preview', '/api/sequence/upcoming']:
    try:
        r = op.open(BASE+endpoint, timeout=20)
        body = r.read()[:500]
        L(f'  {endpoint}: HTTP {r.getcode()}, first 500 chars: {body.decode("utf-8",errors="ignore")[:300]}')
        break
    except urllib.error.HTTPError as e:
        L(f'  {endpoint}: HTTP {e.code}')

# 3. Check email_log for what was actually sent
L(''); L('3. RECENT EMAIL_LOG (check sent email HTML)')
try:
    r = op.open(BASE+'/api/sequence/queue?include_sent=1', timeout=20)
    data = json.loads(r.read())
    L(f'  queue response: {str(data)[:300]}')
except Exception as e:
    L(f'  err: {e}')

with open('vfinal.txt','w') as f: f.write(chr(10).join(out))
