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
        return 0, str(e)

log.append('=== FULL PLATFORM AUDIT ===')
log.append('')

# All endpoints
tests = [
    ('GET',  '/',                         None,                              'Homepage'),
    ('GET',  '/api/config',               None,                              'Config'),
    ('GET',  '/api/stats',                None,                              'Stats'),
    ('GET',  '/api/cities',               None,                              'Cities'),
    ('GET',  '/api/prospecting/templates',None,                              'Prospecting templates'),
    ('GET',  '/api/sequence/templates',   None,                              'Sequence templates'),
    ('GET',  '/api/leads',                None,                              'Leads list'),
    ('GET',  '/api/log',                  None,                              'Email log'),
    ('GET',  '/api/sequence/queue',       None,                              'Queue'),
    ('GET',  '/api/campaigns',            None,                              'Campaigns list'),
    ('GET',  '/api/groups',               None,                              'Contact groups'),
    ('GET',  '/api/domain/health',        None,                              'Domain health'),
    ('GET',  '/api/ai/status',            None,                              'AI status'),
    ('GET',  '/api/analytics/summary',    None,                              'Analytics summary'),
    ('GET',  '/api/analytics/by_step',    None,                              'Analytics by step'),
    ('GET',  '/api/replies/status',       None,                              'Replies status'),
    ('POST', '/api/groups',               {'name':'_test_audit_group','description':'audit'}, 'Create group'),
    ('GET',  '/api/groups',               None,                              'List groups (after create)'),
    ('POST', '/api/search/preview',       {'keyword':'IT services','city':'Dubai, UAE'}, 'Search preview'),
]

passes = 0; fails = 0
for method, path, body, label in tests:
    code, resp = call(method, path, body)
    ok = (code == 200)
    status = 'PASS' if ok else 'FAIL'
    if ok: passes += 1
    else: fails += 1
    log.append(f'[{status}] {method:4} {path:38} | HTTP {code} | {resp[:100]}')

log.append('')
log.append(f'=== Summary: {passes} passed, {fails} failed ===')

# Cleanup test group
groups = json.loads(call('GET', '/api/groups')[1]).get('groups', [])
for g in groups:
    if g['name'] == '_test_audit_group':
        call('DELETE', '/api/groups/' + str(g['id']))
        log.append('Cleaned up test group')

with open('audit.txt','w') as f: f.write(chr(10).join(log))
print(chr(10).join(log))
