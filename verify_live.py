import urllib.request, json
BASE = 'https://skymaxx-lead-engine.onrender.com'

def get(path):
    try:
        req = urllib.request.Request(BASE + path)
        resp = urllib.request.urlopen(req, timeout=60)
        return resp.getcode(), resp.read().decode()
    except Exception as e:
        return 0, str(e)

def post(path, body):
    try:
        req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), method='POST',
            headers={'Content-Type':'application/json'})
        resp = urllib.request.urlopen(req, timeout=60)
        return resp.getcode(), resp.read().decode()
    except Exception as e:
        return 0, str(e)

log = []
def p(m): print(m, flush=True); log.append(str(m))

p('=== Reply Detection Verification ===')

# 1. Check replies status
c, b = get('/api/replies/status')
p('replies/status: HTTP ' + str(c))
p('  ' + b[:300])

# 2. Check config has graph_api flag
c, b = get('/api/config')
p('')
p('config: HTTP ' + str(c))
p('  ' + b[:400])

# 3. Manual poll (this triggers a Graph API call)
p('')
p('Triggering manual poll...')
c, b = post('/api/replies/poll', {})
p('replies/poll: HTTP ' + str(c))
p('  ' + b[:300])

with open('verify.txt', 'w') as f:
    f.write(chr(10).join(log))
