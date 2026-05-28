import urllib.request, json, time
BASE='https://skymaxx-lead-engine.onrender.com'
out=[]; PASS=0; FAIL=0
def L(m): out.append(str(m)); print(m,flush=True)
def ok(c,m): 
    global PASS,FAIL
    if c: PASS+=1; L('  ✅ '+m)
    else: FAIL+=1; L('  ❌ '+m)
def get(p,t=40):
    try:
        r=urllib.request.urlopen(BASE+p,timeout=t); return r.getcode(), r.read().decode()
    except urllib.error.HTTPError as e: return e.code, e.read().decode()[:400]
    except Exception as e: return 0, str(e)[:200]
def post(p,b,t=60):
    try:
        req=urllib.request.Request(BASE+p,data=json.dumps(b).encode(),headers={'Content-Type':'application/json'},method='POST')
        r=urllib.request.urlopen(req,timeout=t); return r.getcode(), r.read().decode()
    except urllib.error.HTTPError as e: return e.code, e.read().decode()[:400]
    except Exception as e: return 0, str(e)[:200]

L('='*60); L('END-TO-END FUNCTIONAL TEST'); L('='*60)

# TEST 1: Quick Search returns displayable results
L(''); L('TEST 1: Quick Search (Dubai restaurants)')
code,body=post('/api/search/v2/preview',{'source':'google_maps','country':'AE','state':'Dubai','category':'restaurant'})
d=json.loads(body) if code==200 else {}
res=d.get('results',[])
ok(code==200, 'search returns HTTP 200')
ok(len(res)>0, 'search returns results ('+str(len(res))+' leads)')
if res:
    r0=res[0]
    ok('name' in r0 and r0.get('name'), 'leads have name')
    ok('place_id' in r0, 'leads have place_id (selectable)')
    ok(any(r.get('phone') for r in res), 'at least some have phone')
    ok(any(r.get('website') for r in res), 'at least some have website')

# TEST 2: Campaign draft creation (createCampaign flow) — SAFE create+delete
L(''); L('TEST 2: Campaign draft creation (using leads 59,60)')
code,body=post('/api/campaigns/draft',{'name':'__QA_TEST__','lead_ids':[59,60]})
d=json.loads(body) if code==200 else {}
test_cid=d.get('campaign_id')
ok(code==200, 'draft endpoint returns 200')
ok(test_cid is not None, 'draft created (id='+str(test_cid)+')')
ok(d.get('recipient_count')==2 or d.get('lead_count')==2, 'draft has 2 recipients')
# Verify it shows as pending_approval, then DELETE it (don't approve - would steal leads from camp 1)
if test_cid:
    code2,body2=get('/api/campaigns')
    camps=json.loads(body2).get('campaigns',[]) if code2==200 else []
    tc=[c for c in camps if c.get('id')==test_cid]
    ok(tc and tc[0].get('status')=='pending_approval', 'draft status=pending_approval')
    # cleanup
    post('/api/debug/delete_campaign/'+str(test_cid),{})
    L('  (cleaned up test campaign '+str(test_cid)+')')

# TEST 3: Campaign 1 health
L(''); L('TEST 3: Campaign 1 (live) health')
code,body=get('/api/campaigns')
camps=json.loads(body).get('campaigns',[]) if code==200 else []
c1=[c for c in camps if c.get('id')==1]
if c1:
    c1=c1[0]
    ok(c1.get('status')=='running', 'status=running (got: '+str(c1.get('status'))+')')
    ok(c1.get('actually_sent')==14, 'actually_sent=14 (got: '+str(c1.get('actually_sent'))+')')
    ok(c1.get('next_send_at') is not None, 'next_send_at set ('+str(c1.get('next_send_at'))[:10]+')')

# TEST 4: Pause → Resume (now safe with preserve-future fix)
L(''); L('TEST 4: Pause/Resume cycle on campaign 1 (verify no premature send)')
code,body=post('/api/campaigns/1/pause',{})
ok(code==200, 'pause returns 200')
code,body=get('/api/debug/campaign/1')
d=json.loads(body) if code==200 else {}
in_seq_after_pause=d.get('leads_in_sequence',-1)
ok(in_seq_after_pause==0, 'after pause: 0 leads in_sequence (paused)')
# Resume
code,body=post('/api/campaigns/1/resume',{})
ok(code==200, 'resume returns 200')
code,body=get('/api/debug/campaign/1')
d=json.loads(body) if code==200 else {}
in_seq_after_resume=d.get('leads_in_sequence',-1)
ok(in_seq_after_resume==14, 'after resume: 14 leads in_sequence (restored)')
# Verify next_send_at still in future (May 30, NOT reset to now)
leads=d.get('leads',[])
now=time.strftime('%Y-%m-%dT%H:%M:%S',time.gmtime())
future_count=sum(1 for l in leads if str(l.get('next_send_at') or '') > now)
ok(future_count==14, 'all 14 next_send_at still FUTURE (no premature blast) — got '+str(future_count))

# TEST 5: Stats accuracy
L(''); L('TEST 5: Dashboard stats')
code,body=get('/api/stats')
s=json.loads(body) if code==200 else {}
ok(code==200,'stats returns 200')
ok(s.get('total_leads')==14,'total_leads=14')
ok(s.get('in_sequence')==14,'in_sequence=14')

L(''); L('='*60)
L('RESULTS: '+str(PASS)+' passed, '+str(FAIL)+' failed')
L('='*60)
with open('func_test.txt','w') as f: f.write(chr(10).join(out))
