import urllib.request, json
BASE = 'https://skymaxx-lead-engine.onrender.com'
log = []

def get(path):
    try:
        r = urllib.request.urlopen(BASE+path, timeout=60)
        return r.getcode(), r.read().decode()
    except Exception as e:
        return 0, str(e)

# Check key endpoints
for ep, exp in [
    ('/', 200),
    ('/api/config', 200),
    ('/api/prospecting/templates', 200),
    ('/api/sequence/preview/1?name=Test', 200),
    ('/api/sequence/templates', 200),
]:
    code, body = get(ep)
    ok = 'OK' if code==exp else 'FAIL'
    log.append(f'{ok} {ep} -> HTTP {code} | {body[:80]}')

# Check config has bcc_support
try:
    cfg = json.loads(get('/api/config')[1])
    log.append('')
    log.append('Config keys: ' + ', '.join(cfg.keys()))
    log.append('bcc_support: ' + str(cfg.get('bcc_support','MISSING')))
except: pass

with open('upgrade_verify.txt','w') as f: f.write(chr(10).join(log))
print(chr(10).join(log))
