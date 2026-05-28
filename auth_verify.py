import urllib.request, json
BASE='https://skymaxx-lead-engine.onrender.com'
out=[]
def L(m): out.append(str(m)); print(m,flush=True)
def get_raw(p, headers=None, allow_redirect=False):
    try:
        req=urllib.request.Request(BASE+p, headers=headers or {})
        if not allow_redirect:
            opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler)
            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, *a, **kw): return None
            opener = urllib.request.build_opener(NoRedirect)
            r = opener.open(req, timeout=30)
        else:
            r = urllib.request.urlopen(req, timeout=30)
        return r.getcode(), dict(r.headers), r.read().decode()[:300]
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode()[:300]
    except Exception as e:
        return 0, {}, str(e)[:200]

def post_raw(p, body=None, headers=None):
    try:
        h={'Content-Type':'application/json'}
        if headers: h.update(headers)
        req=urllib.request.Request(BASE+p,data=json.dumps(body or {}).encode(),headers=h,method='POST')
        r=urllib.request.urlopen(req,timeout=30); return r.getcode(), dict(r.headers), r.read().decode()[:400]
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode()[:300]
    except Exception as e:
        return 0, {}, str(e)[:200]

L('='*55); L('AUTHENTICATION VERIFICATION'); L('='*55)

# 1. Login page should be public
L(''); L('1. /login (should be PUBLIC, no auth required)')
code,hdr,body = get_raw('/login', allow_redirect=True)
L('   HTTP '+str(code)+(' ✓' if code==200 else ' ✗'))
L('   Has login form: '+('YES' if '<form' in body or 'username' in body.lower() else 'NO'))

# 2. Root should redirect/401 when not logged in
L(''); L('2. / (root) without auth — should redirect to /login')
code,hdr,body = get_raw('/')
L('   HTTP '+str(code)+(' ✓ (302 redirect)' if code in (302,303) else ' ✗ (expected 302)'))
L('   Location header: '+str(hdr.get('Location','none')))

# 3. API without auth — should return 401 JSON
L(''); L('3. /api/stats without auth — should return 401')
code,hdr,body = get_raw('/api/stats')
L('   HTTP '+str(code)+(' ✓' if code==401 else ' ✗ (expected 401)'))
L('   Body: '+body[:120])

# 4. Cron endpoint WITHOUT secret — should also block
L(''); L('4. /api/cron/process WITHOUT secret — should 401')
code,hdr,body = post_raw('/api/cron/process', {})
L('   HTTP '+str(code)+(' ✓ blocked' if code==401 else ' ✗'))

# 5. Cron endpoint WITH secret — should work (no login needed)
L(''); L('5. /api/cron/process WITH X-Cron-Secret — should succeed')
code,hdr,body = post_raw('/api/cron/process', {}, {'X-Cron-Secret':'skx-cron-7eb2f3a4c9d1'})
L('   HTTP '+str(code)+(' ✓ cron works' if code==200 else ' ✗'))
L('   Body: '+body[:200])

# 6. Login with correct credentials → session cookie
L(''); L('6. POST /login with credentials — should set session')
try:
    data = 'username=admin&password=SKYMAXX@2026'.encode()
    req = urllib.request.Request(BASE+'/login', data=data, method='POST',
        headers={'Content-Type':'application/x-www-form-urlencoded'})
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **kw): return None
    opener = urllib.request.build_opener(NoRedirect)
    try: r = opener.open(req, timeout=30)
    except urllib.error.HTTPError as e: r=e
    code=r.getcode(); h=dict(r.headers)
    L('   HTTP '+str(code))
    setcookie = h.get('Set-Cookie','')
    L('   Set-Cookie present: '+('YES ✓' if 'session=' in setcookie else 'NO'))
    L('   Location: '+str(h.get('Location','none')))
except Exception as e:
    L('   ERR: '+str(e))

with open('auth_verify.txt','w') as f: f.write(chr(10).join(out))
