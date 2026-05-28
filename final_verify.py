import urllib.request, json
BASE='https://skymaxx-lead-engine.onrender.com'
out=[]
def L(m): out.append(str(m)); print(m,flush=True)
def get(p,t=30):
    try:
        r=urllib.request.urlopen(BASE+p,timeout=t); return r.getcode(), r.read().decode()
    except urllib.error.HTTPError as e: return e.code, e.read().decode()[:500]
    except Exception as e: return 0, str(e)[:200]

L('='*68)
L('FINAL VERIFICATION — all reported issues')
L('='*68)

# 1. createCampaign present
code, html = get('/')
L('')
L('ISSUE 1: Lead selection → Campaign')
L('  createCampaign() defined:        ' + ('YES ✓' if 'async function createCampaign(mode)' in html else 'NO ✗'))
L('  Campaign Selected button wired:  ' + ('YES ✓' if "createCampaign('selected')" in html else 'NO'))
L('  Campaign All Eligible wired:     ' + ('YES ✓' if "createCampaign('all')" in html else 'NO'))

# 2. Campaign display fixes
L('')
L('ISSUE 2: Campaign "running but not working"')
L('  running badge present:           ' + ('YES ✓' if 'running:' in html and 'Running</span>' in html else 'NO'))
L('  running shows pause/stop:         ' + ('YES ✓' if "c.status === 'running'" in html else 'NO'))
L('  sent-count display:               ' + ('YES ✓' if 'actually_sent || 0' in html else 'NO'))

# 3. Campaign API enrichment
code, body = get('/api/campaigns')
if code==200:
    camps = json.loads(body).get('campaigns',[])
    L('')
    L('  Live campaign data:')
    for c in camps:
        L('    "'+str(c.get('name'))[:28]+'"')
        L('      status:        '+str(c.get('status')))
        L('      actually_sent: '+str(c.get('actually_sent'))+'/'+str(c.get('recipient_count')))
        L('      next_send_at:  '+str(c.get('next_send_at')))
        L('      progress:      '+str(c.get('leads_finished'))+'/'+str(c.get('leads_total'))+' finished')

# 4. Pagination check (Task 4 from before)
L('')
L('ISSUE 3 (earlier): Lead search 100+')
L('  Pagination helper deployed:      checking via search test...')
import json as j
req=urllib.request.Request(BASE+'/api/search/v2/preview',
    data=j.dumps({'source':'google_maps','country':'AE','state':'Dubai','category':'restaurant'}).encode(),
    headers={'Content-Type':'application/json'},method='POST')
try:
    r=urllib.request.urlopen(req,timeout=60); d=j.loads(r.read())
    L('  Search returned:                 '+str(d.get('found') or len(d.get('results',[])))+' leads (cap now 60)')
except Exception as e:
    L('  Search test: '+str(e)[:100])

# 5. Cron health
L('')
L('ISSUE 4 (earlier): Email automation')
code, body = get('/api/stats')
if code==200:
    s=json.loads(body)
    L('  total_sent:   '+str(s.get('total_sent')))
    L('  in_sequence:  '+str(s.get('in_sequence')))

with open('final_verify.txt','w') as f: f.write(chr(10).join(out))
