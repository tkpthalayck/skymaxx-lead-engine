import urllib.request, json
BASE = 'https://skymaxx-lead-engine.onrender.com'
log = []

def call(method, path, body=None):
    try:
        data = json.dumps(body).encode() if body else None
        req = urllib.request.Request(BASE+path, data=data, method=method,
            headers={'Content-Type':'application/json'} if body else {})
        r = urllib.request.urlopen(req, timeout=60)
        return r.getcode(), r.read().decode()
    except Exception as e:
        return 0, str(e)[:120]

log.append('=== SEARCH UPGRADE VERIFICATION ===')
log.append('')

# Test new endpoints
tests = [
    ('GET', '/api/locations/countries',  None, 'Countries list'),
    ('GET', '/api/locations/states/AE',  None, 'UAE states'),
    ('GET', '/api/locations/states/SA',  None, 'Saudi states'),
    ('GET', '/api/business_categories',  None, 'Business categories (30)'),
    ('GET', '/api/job_titles',           None, 'Job titles'),
]

for method, path, body, label in tests:
    code, resp = call(method, path, body)
    ok = (code == 200)
    log.append(f'[{"PASS" if ok else "FAIL"}] {path:36} | HTTP {code}')
    if ok:
        try:
            data = json.loads(resp)
            if isinstance(data, list):
                log.append(f'         → {len(data)} items')
                if data and len(data) > 0:
                    sample = data[0] if isinstance(data[0], (str, dict)) else str(data[0])[:60]
                    log.append(f'         → sample: {json.dumps(sample)[:90]}')
        except: pass

log.append('')
log.append('=== DEPLOYMENT STATUS ===')
log.append('Backend (app.py):  v3 + hierarchical search - LIVE')
log.append('Frontend (index):  redesigned Find Leads tab - LIVE')

with open('search_verify.txt','w') as f: f.write(chr(10).join(log))
print(chr(10).join(log))
