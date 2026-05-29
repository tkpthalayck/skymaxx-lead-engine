import urllib.request, json, http.cookiejar, time
BASE='https://skymaxx-lead-engine.onrender.com'
out=[]
def L(m): out.append(str(m)); print(m,flush=True)

cookiejar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookiejar))
data = 'username=admin&password=SKYMAXX@2026'.encode()
req = urllib.request.Request(BASE+'/login', data=data, method='POST',
    headers={'Content-Type':'application/x-www-form-urlencoded'})
opener.open(req, timeout=40)

# Try multiple queries to find what works
test_queries = [
    {'source':'google_maps','country':'AE','category':'manufacturing'},
    {'source':'google_maps','country':'AE','category':'manufacturer','state':'Dubai'},
    {'source':'google_maps','country':'AE','state':'Dubai','keyword':'manufacturing companies'},
    {'source':'google_maps','country':'AE','state':'Dubai','keyword':'factory'},
    {'source':'google_maps','country':'United Arab Emirates','keyword':'manufacturer'},
]
for q in test_queries:
    L(''); L('Query: '+json.dumps(q))
    body = json.dumps(q).encode()
    req = urllib.request.Request(BASE+'/api/search/v2/preview', data=body, method='POST',
        headers={'Content-Type':'application/json'})
    try:
        t0 = time.time()
        r = opener.open(req, timeout=120)
        elapsed = time.time() - t0
        d = json.loads(r.read())
        results = d.get('results',[])
        with_email = sum(1 for x in results if x.get('email'))
        with_phone = sum(1 for x in results if x.get('phone'))
        scraped = sum(1 for x in results if x.get('email_source')=='scraped')
        gen = sum(1 for x in results if x.get('email_source')=='generated')
        L(f'  → {len(results)} results in {elapsed:.1f}s | email={with_email} (scraped={scraped} gen={gen}) | phone={with_phone}')
        L(f'  → query sent to Google: {d.get("query","?")}')
        # Show first 3
        for r in results[:3]:
            L(f'    - {r.get("name","?")[:30]:30} | email={r.get("email","-")[:30]} | phone={r.get("phone","-")[:20]} | src={r.get("email_source","?")}')
    except urllib.error.HTTPError as e:
        L('  HTTP '+str(e.code)+': '+e.read().decode()[:200])

with open('uae_test.txt','w') as f: f.write(chr(10).join(out))
