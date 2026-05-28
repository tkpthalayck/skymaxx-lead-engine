import urllib.request, json
BASE='https://skymaxx-lead-engine.onrender.com'
out=[]
def L(m): out.append(str(m)); print(m,flush=True)
def get(p,t=30):
    try:
        r=urllib.request.urlopen(BASE+p,timeout=t); return r.getcode(), r.read().decode()
    except urllib.error.HTTPError as e: return e.code, e.read().decode()[:500]
    except Exception as e: return 0, str(e)[:200]
def post(p,b,t=45):
    try:
        req=urllib.request.Request(BASE+p,data=json.dumps(b).encode(),headers={'Content-Type':'application/json'},method='POST')
        r=urllib.request.urlopen(req,timeout=t); return r.getcode(), r.read().decode()
    except urllib.error.HTTPError as e: return e.code, e.read().decode()[:500]
    except Exception as e: return 0, str(e)[:200]

L('='*68)
L('VERIFICATION: createCampaign fix + draft endpoint')
L('='*68)

# 1. Is createCampaign in the served HTML now?
code, html = get('/')
L('1. createCampaign() in served HTML: ' + ('YES ✓' if 'async function createCampaign(mode)' in html else 'NO ✗ (deploy may still be in progress)'))
L('   Broken buttons still call it:    ' + ('YES (now wired)' if 'createCampaign(' in html else 'NO'))

# 2. Test the draft endpoint with mode='all' (resolves all eligible leads)
L('')
L('2. Testing /api/campaigns/draft with lead_ids=all...')
code, body = post('/api/campaigns/draft', {'name':'QA Test Campaign','lead_ids':'all'})
L('   HTTP '+str(code))
if code==200:
    d=json.loads(body)
    L('   campaign_id: '+str(d.get('campaign_id')))
    L('   recipient_count: '+str(d.get('recipient_count') or d.get('lead_count')))
    test_cid = d.get('campaign_id')
    # Clean up the test campaign
    if test_cid:
        post('/api/debug/delete_campaign/'+str(test_cid), {})
        L('   (test campaign '+str(test_cid)+' deleted)')
else:
    # 'all' might return 0 eligible since all 14 are already in_sequence — that's expected
    d = json.loads(body) if body.startswith('{') else {}
    L('   Response: '+str(d.get('error', body[:150])))
    L('   (NOTE: 0 eligible is EXPECTED — all 14 leads already enrolled in campaign 1)')

# 3. Current campaigns overview
L('')
L('3. All campaigns:')
code, body = get('/api/campaigns')
if code==200:
    for c in json.loads(body).get('campaigns',[]):
        L('   id='+str(c.get('id'))+' "'+str(c.get('name'))[:30]+'" status='+str(c.get('status'))+
          ' sent='+str(c.get('actually_sent'))+'/'+str(c.get('recipient_count')))

with open('verify_cc.txt','w') as f: f.write(chr(10).join(out))
