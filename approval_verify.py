import urllib.request, json
BASE = 'https://skymaxx-lead-engine.onrender.com'
log = []

def get(p):
    try:
        r = urllib.request.urlopen(BASE+p, timeout=60)
        return r.getcode(), r.read().decode()
    except Exception as e:
        return 0, str(e)

# Verify new endpoints exist
endpoints = [
    '/',
    '/api/config',
    '/api/campaigns',
    '/api/domain/health',
    '/api/ai/status',
]
for ep in endpoints:
    code, body = get(ep)
    ok = 'OK' if code==200 else 'FAIL'
    log.append(f'{ok} {ep} -> HTTP {code} | {body[:120]}')

# Check domain health for skymaxx.company
log.append('')
log.append('=== Domain Health for skymaxx.company ===')
code, body = get('/api/domain/health?domain=skymaxx.company')
if code==200:
    h = json.loads(body)
    log.append('SPF:   ' + h['spf']['status'] + (' | ' + (h['spf']['value'] or '')[:80] if h['spf']['value'] else ''))
    log.append('DKIM:  ' + h['dkim']['status'] + ' | selectors: ' + str([s['name'] for s in h['dkim']['selectors']]))
    log.append('DMARC: ' + h['dmarc']['status'])
    log.append('Score: ' + str(h['score']) + '/100')

with open('approval_verify.txt','w') as f: f.write(chr(10).join(log))
print(chr(10).join(log))
