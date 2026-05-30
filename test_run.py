import urllib.request, json, http.cookiejar
BASE='https://skymaxx-lead-engine.onrender.com'
out=[]
def L(m): out.append(str(m)); print(m,flush=True)

cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
data = 'username=admin&password=SKYMAXX@2026'.encode()
req = urllib.request.Request(BASE+'/login', data=data, method='POST',
    headers={'Content-Type':'application/x-www-form-urlencoded'})
op.open(req, timeout=40)
L('Login OK')

L('')
L('='*70)
L('LIVE END-TO-END TEST: Force progression from step 1 to step 2')
L('='*70)
L('Picking ONE lead from Campaign #1 (your oldest campaign)')
L('Setting next_send_at to 1 minute ago')
L('Running cron logic — should send EMAIL #2 to that lead')
L('')

# Force-send ONE lead from Campaign #1
body = json.dumps({'campaign_id': 1, 'limit': 1}).encode()
req = urllib.request.Request(BASE+'/api/admin/force_send_one', data=body, method='POST',
    headers={'Content-Type':'application/json'})
try:
    r = op.open(req, timeout=120)  # send_via_zepto + sleep(2) — be patient
    result = json.loads(r.read())
    L('BEFORE state:')
    for b in result.get('before', []):
        L(f"  Lead #{b.get('id')}: {b.get('name','?')[:35]:35} | step={b.get('step',0)} | next_send_at={b.get('next_send_at','?')}")
    L('')
    L('AFTER cron run:')
    for a in result.get('after', []):
        L(f"  Lead #{a.get('id')}: {a.get('name','?')[:35]:35} | step={a.get('sequence_step',0)} | next_send_at={a.get('next_send_at','?')} | in_seq={a.get('in_sequence','?')}")
    L('')
    L('FRESH EMAIL_LOG (most recent 10 for this lead):')
    for log in result.get('recent_logs', [])[:10]:
        err = ' ERR:'+str(log.get('error_msg','')) if log.get('status')=='failed' else ''
        L(f"  log_id={log.get('id'):<5} step={log.get('step',0)} | {log.get('to_email','?')[:35]:35} | status={log.get('status','?'):8} | sent_at={log.get('sent_at','?')[:30]}{err}")
except urllib.error.HTTPError as e:
    L(f'HTTP {e.code}: {e.read().decode()[:500]}')
except Exception as e:
    L(f'ERR: {e}')

import time as _t
ts = str(int(_t.time()))
with open(f'test_{ts}.txt','w') as f: f.write(chr(10).join(out))
