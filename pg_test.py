import urllib.request, json, time
BASE='https://skymaxx-lead-engine.onrender.com'
out=[]
def L(m): out.append(str(m)); print(m,flush=True)
def post(p,b,t=90):
    try:
        req=urllib.request.Request(BASE+p,data=json.dumps(b).encode(),headers={'Content-Type':'application/json'},method='POST')
        r=urllib.request.urlopen(req,timeout=t); return r.getcode(), r.read().decode()
    except urllib.error.HTTPError as e: return e.code, e.read().decode()[:400]
    except Exception as e: return 0, str(e)[:200]

L('PAGINATION TEST (after retry fix)')
L('='*50)
t0=time.time()
code, body = post('/api/search/v2/preview', {'source':'google_maps','country':'AE','state':'Dubai','category':'restaurant'})
el=time.time()-t0
L('HTTP '+str(code)+' in '+format(el,'.1f')+'s')
if code==200:
    d=json.loads(body)
    n = d.get('found') or len(d.get('results',[]))
    L('Leads returned: '+str(n)+'  '+('✓ PAGINATION WORKING' if n>20 else '(still 20 — Dubai may have limited results, try broad)'))
    # Show field coverage
    res=d.get('results',[])
    if res:
        with_phone=sum(1 for r in res if r.get('phone'))
        with_web=sum(1 for r in res if r.get('website'))
        L('Field coverage: phone='+str(with_phone)+'/'+str(len(res))+' website='+str(with_web)+'/'+str(len(res)))
else:
    L('Body: '+body[:200])

with open('pg_test.txt','w') as f: f.write(chr(10).join(out))
