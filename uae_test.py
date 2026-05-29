import urllib.request, json, http.cookiejar
BASE='https://skymaxx-lead-engine.onrender.com'
out=[]
def L(m): out.append(str(m)); print(m,flush=True)

L('='*65)
L('UAE MANUFACTURING SEARCH — VERIFY EMAIL + PHONE ENRICHMENT')
L('='*65)

cookiejar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookiejar))

# Login
data = 'username=admin&password=SKYMAXX@2026'.encode()
req = urllib.request.Request(BASE+'/login', data=data, method='POST',
    headers={'Content-Type':'application/x-www-form-urlencoded'})
opener.open(req, timeout=40)
L('Login OK')

# Run UAE Manufacturing search
body = json.dumps({'source':'google_maps','country':'AE','category':'Manufacturing'}).encode()
req = urllib.request.Request(BASE+'/api/search/v2/preview', data=body, method='POST',
    headers={'Content-Type':'application/json'})

import time
t0 = time.time()
try:
    r = opener.open(req, timeout=90)
    elapsed = time.time() - t0
    L(f'Search HTTP {r.getcode()} ({elapsed:.1f}s)')
    data = json.loads(r.read())
    results = data.get('results', [])
    L(f'Total results: {len(results)}')
    L('')
    
    # Count fields
    with_email = sum(1 for r in results if r.get('email'))
    with_phone = sum(1 for r in results if r.get('phone'))
    with_website = sum(1 for r in results if r.get('website'))
    scraped_email = sum(1 for r in results if r.get('email_source')=='scraped')
    generated_email = sum(1 for r in results if r.get('email_source')=='generated')
    L(f'  Has email:      {with_email}/{len(results)} ({scraped_email} scraped + {generated_email} generated@domain)')
    L(f'  Has phone:      {with_phone}/{len(results)}')
    L(f'  Has website:    {with_website}/{len(results)}')
    L('')
    L('Sample (first 10):')
    L('-'*65)
    for i, r in enumerate(results[:10]):
        L(f"  {i+1:2d}. {r.get('name','?')[:30]:30}")
        L(f"      email:   {r.get('email','-')[:45]:45} [{r.get('email_source','?')}]")
        L(f"      phone:   {r.get('phone','-')[:25]:25}")
        L(f"      website: {r.get('website','-')[:45]}")
        L('')
except urllib.error.HTTPError as e:
    L(f'HTTP {e.code}: '+e.read().decode()[:300])
except Exception as e:
    L(f'ERR: {e}')

with open('uae_test.txt','w') as f: f.write(chr(10).join(out))
