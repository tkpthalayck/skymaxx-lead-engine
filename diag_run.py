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

r = op.open(BASE+'/api/admin/diag', timeout=60)
data = json.loads(r.read())

L('='*70)
L('SEQUENCE HEALTH DIAGNOSTIC')
L('='*70)
L(f"Server UTC time: {data.get('server_time_utc')}")
L(f"Today's send count: {data.get('today_send_count')}/{data.get('daily_limit')}")
L('')
L('CAMPAIGNS:')
for c in data.get('campaigns', []):
    L(f"  #{c.get('id')} {c.get('name','?')[:40]:40} | status={c.get('status','?'):10} | sent={c.get('actually_sent',0)}/{c.get('recipient_count',0)} | leads={c.get('lead_count','?')}")

L('')
L('LEAD SEQUENCE_STEP DISTRIBUTION:')
L(f"  {'step':<5} {'in_seq':<6} {'replied':<7} {'unsub':<5} {'count':<5}")
for r in data.get('lead_step_distribution', []):
    L(f"  {r.get('sequence_step',0):<5} {r.get('in_sequence',0):<6} {r.get('replied',0):<7} {r.get('unsubscribed',0):<5} {r.get('cnt',0):<5}")

L('')
L('EMAIL_LOG BY STEP:')
L(f"  {'step':<5} {'status':<10} {'count':<5}")
for r in data.get('email_log_by_step', []):
    L(f"  {r.get('step',0):<5} {str(r.get('status','?')):<10} {r.get('cnt',0):<5}")

L('')
L(f"PENDING NOW (should be sent immediately): {data.get('pending_count',0)} leads")
for p in data.get('pending_now', [])[:10]:
    L(f"  - {p.get('name','?')[:30]:30} | step={p.get('sequence_step',0)} | next_send={p.get('next_send_at','?')} | camp={p.get('campaign_id','?')}")

L('')
L(f"FUTURE-PENDING (waiting): {data.get('future_pending_count',0)} leads")
for p in data.get('future_pending', [])[:10]:
    L(f"  - {p.get('name','?')[:30]:30} | step={p.get('sequence_step',0)} | next_send={p.get('next_send_at','?')}")

L('')
L(f"STUCK LEADS (in_sequence=1, step>=1, next_send_at=NULL): {len(data.get('stuck_no_next_send_at', []))}")
for s in data.get('stuck_no_next_send_at', [])[:10]:
    L(f"  - {s.get('name','?')[:30]:30} | step={s.get('sequence_step',0)} | camp={s.get('campaign_id','?')}")

L('')
L('RECENT EMAILS (last 20):')
for e in data.get('recent_emails', [])[:20]:
    err = ' ERR:'+str(e.get('error_msg','')[:30]) if e.get('status')=='failed' else ''
    L(f"  {e.get('sent_at','?')[:19]} | step{e.get('step','?')} | {e.get('to_email','?')[:35]:35} | {e.get('status','?')[:9]:9}{err}")

import time as _t
ts = str(int(_t.time()))
with open(f'diag_{ts}.txt','w') as f: f.write(chr(10).join(out))
print(f'\n>>> Output saved to diag_{ts}.txt')
