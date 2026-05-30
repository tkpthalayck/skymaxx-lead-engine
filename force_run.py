import urllib.request, json, http.cookiejar, time
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
L('STEP 1: Force-progress remaining Campaign #1 leads to step 2')
L('='*70)
# All campaign #1 leads — limit 14 to cover all
body = json.dumps({'campaign_id': 1, 'limit': 14}).encode()
req = urllib.request.Request(BASE+'/api/admin/force_send_one', data=body, method='POST',
    headers={'Content-Type':'application/json'})
t0 = time.time()
try:
    r = op.open(req, timeout=180)  # 14 sends * 2s rate-limit + send time = ~60s
    res = json.loads(r.read())
    elapsed = time.time() - t0
    L(f'Force-send completed in {elapsed:.0f}s')
    L('')
    L('After state of all Campaign #1 leads:')
    step1_after, step2_after, step3plus = 0, 0, 0
    for a in res.get('after', []):
        s = a.get('sequence_step', 0)
        if s == 1: step1_after += 1
        elif s == 2: step2_after += 1
        elif s >= 3: step3plus += 1
        if step2_after <= 5:  # show first 5
            L(f"  Lead #{a.get('id')}: step={s} | next_send={a.get('next_send_at','?')[:19]}")
    L(f'  ... (total: {len(res.get("after",[]))} leads)')
    L('')
    L(f'Distribution AFTER: step=1: {step1_after} | step=2: {step2_after} | step≥3: {step3plus}')
    L('')
    L('Step 2 email log entries (count):')
    step2_logs = [x for x in res.get('recent_logs',[]) if x.get('step')==2]
    L(f'  {len(step2_logs)} step-2 emails in fresh logs')
    success = sum(1 for x in step2_logs if x.get('status')=='success')
    failed  = sum(1 for x in step2_logs if x.get('status')=='failed')
    L(f'  success={success} | failed={failed}')
    if failed:
        L('Failed sends:')
        for x in step2_logs:
            if x.get('status')=='failed':
                L(f"  - {x.get('to_email','?')[:40]:40} ERR: {x.get('error_msg','?')[:100]}")
except urllib.error.HTTPError as e:
    L(f'HTTP {e.code}: '+e.read().decode()[:500])
except Exception as e:
    L(f'ERR: {e}')

# Now get fresh diag
L('')
L('='*70)
L('STEP 2: Final overall sequence health')
L('='*70)
try:
    r = op.open(BASE+'/api/admin/diag', timeout=60)
    d = json.loads(r.read())
    L(f'Server time: {d.get("server_time_utc","?")}')
    L(f'Pending NOW: {d.get("pending_count",0)} leads')
    L(f'Future pending: {d.get("future_pending_count",0)} leads')
    L('')
    L('Lead step distribution:')
    L(f"  {'step':<5} {'in_seq':<6} {'replied':<7} {'unsub':<5} {'count':<5}")
    for r2 in d.get('lead_step_distribution', []):
        L(f"  {r2.get('sequence_step',0):<5} {r2.get('in_sequence',0):<6} {r2.get('replied',0):<7} {r2.get('unsubscribed',0):<5} {r2.get('cnt',0):<5}")
    L('')
    L('Email log by step:')
    for r2 in d.get('email_log_by_step', []):
        L(f"  step={r2.get('step','?')} status={r2.get('status','?'):<10} count={r2.get('cnt',0)}")
except Exception as e:
    L(f'diag err: {e}')

import time as _t
ts = str(int(_t.time()))
with open(f'force_{ts}.txt','w') as f: f.write(chr(10).join(out))
