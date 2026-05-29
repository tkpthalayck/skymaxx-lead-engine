import urllib.request, json, http.cookiejar
from datetime import datetime, timedelta
BASE='https://skymaxx-lead-engine.onrender.com'
out=[]
def L(m): out.append(str(m)); print(m,flush=True)

L('='*65)
L('SEQUENCE PROCESSING DIAGNOSTIC')
L('='*65)

cookiejar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookiejar))

# Login
data = 'username=admin&password=SKYMAXX@2026'.encode()
req = urllib.request.Request(BASE+'/login', data=data, method='POST',
    headers={'Content-Type':'application/x-www-form-urlencoded'})
opener.open(req, timeout=40)

# 1. List campaigns
L(''); L('1. CAMPAIGNS')
L('-'*65)
try:
    r = opener.open(BASE+'/api/campaigns', timeout=30)
    camps = json.loads(r.read())
    if isinstance(camps, dict): camps = camps.get('campaigns', camps.get('items', []))
    for c in camps:
        L(f"  ID={c.get('id')} | {c.get('name','?')[:40]:40} | status={c.get('status'):12} | sent={c.get('actually_sent',0)}/{c.get('total_leads', c.get('lead_count','?'))} | next_send={c.get('next_send_at','-')[:19] if c.get('next_send_at') else '-'}")
except Exception as e:
    L('  ERR: '+str(e)[:200])

# 2. Get details of campaign 1 — leads + state
L(''); L('2. CAMPAIGN 1 LEAD STATES')
L('-'*65)
try:
    r = opener.open(BASE+'/api/campaigns/1', timeout=30)
    detail = json.loads(r.read())
    L('  Campaign: '+str(detail.get('name')))
    L('  Status: '+str(detail.get('status')))
    L('  Leads in campaign: '+str(len(detail.get('leads',[]))))
    L('')
    for lead in detail.get('leads',[])[:20]:
        L(f"    lead#{lead.get('id'):3} {lead.get('email','?')[:35]:35} step={lead.get('sequence_step','?')} in_seq={lead.get('in_sequence','?')} replied={lead.get('replied','?')} next_at={lead.get('next_send_at','-')[:19] if lead.get('next_send_at') else 'NULL'}")
except urllib.error.HTTPError as e:
    L('  HTTP '+str(e.code)+': '+e.read().decode()[:200])
except Exception as e:
    L('  ERR: '+str(e)[:200])

# 3. Email log
L(''); L('3. RECENT EMAIL LOG (last 20)')
L('-'*65)
try:
    r = opener.open(BASE+'/api/email-log?limit=20', timeout=30)
    logs = json.loads(r.read())
    if isinstance(logs, dict): logs = logs.get('logs', logs.get('items', []))
    for log in logs[:20]:
        L(f"    {log.get('created_at','?')[:19]} | step={log.get('step','?')} | {log.get('status','?'):8} | {log.get('to_email','?')[:40]}")
except urllib.error.HTTPError as e:
    L('  HTTP '+str(e.code))
except Exception as e:
    L('  ERR: '+str(e)[:200])

# 4. TRIGGER cron manually + see what happens
L(''); L('4. MANUAL CRON TRIGGER')
L('-'*65)
try:
    req = urllib.request.Request(BASE+'/api/cron/process', method='POST',
        headers={'Content-Type':'application/json','X-Cron-Secret':'skx-cron-7eb2f3a4c9d1'},
        data=b'{}')
    r = urllib.request.urlopen(req, timeout=120)
    result = json.loads(r.read())
    L('  HTTP '+str(r.getcode()))
    L('  Report: '+json.dumps(result, indent=2)[:1500])
except urllib.error.HTTPError as e:
    L('  HTTP '+str(e.code)+': '+e.read().decode()[:400])
except Exception as e:
    L('  ERR: '+str(e)[:200])

# 5. NOW check email log AGAIN to see if cron sent anything
L(''); L('5. EMAIL LOG AFTER CRON RUN')
L('-'*65)
try:
    r = opener.open(BASE+'/api/email-log?limit=10', timeout=30)
    logs = json.loads(r.read())
    if isinstance(logs, dict): logs = logs.get('logs', logs.get('items', []))
    for log in logs[:10]:
        L(f"    {log.get('created_at','?')[:19]} | step={log.get('step','?')} | {log.get('status','?'):8} | {log.get('to_email','?')[:40]}")
except Exception as e:
    L('  ERR: '+str(e)[:120])

# 6. Current UTC time
L(''); L('UTC now: '+datetime.utcnow().isoformat())

with open('seq_diag.txt','w') as f: f.write(chr(10).join(out))
