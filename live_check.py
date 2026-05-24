import urllib.request, json
BASE = 'https://skymaxx-lead-engine.onrender.com'

def get(p):
    try:
        r = urllib.request.urlopen(BASE+p, timeout=45)
        return r.getcode(), r.read().decode()
    except Exception as e:
        return 0, str(e)[:80]

log = []
log.append('=== LIVE VERIFICATION ===')

# Endpoints
for ep in ['/api/locations/countries','/api/locations/states/AE','/api/locations/states/SA','/api/business_categories','/api/job_titles']:
    code, body = get(ep)
    if code == 200:
        d = json.loads(body)
        log.append('PASS ' + ep + ' -> HTTP 200, ' + str(len(d)) + ' items')
    else:
        log.append('FAIL ' + ep + ' -> HTTP ' + str(code) + ' | ' + body)

# HTML markers
code, html = get('/')
log.append('')
log.append('HTML markers (proves new frontend deployed):')
for m in ['B2B Prospect Discovery','qs-country','bulk-countries','quickSearchV2','initV2Search','Business Category','Job Title','State / Region']:
    log.append(('PASS' if m in html else 'FAIL') + ' "' + m + '" ' + ('in HTML' if m in html else 'NOT in HTML'))

with open('live_check.txt','w') as f: f.write(chr(10).join(log))
print(chr(10).join(log))
