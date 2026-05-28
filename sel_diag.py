import urllib.request, json
BASE='https://skymaxx-lead-engine.onrender.com'
out=[]
def L(m): out.append(str(m)); print(m,flush=True)
def post(p,b,t=60):
    try:
        req=urllib.request.Request(BASE+p,data=json.dumps(b).encode(),headers={'Content-Type':'application/json'},method='POST')
        r=urllib.request.urlopen(req,timeout=t); return r.getcode(), r.read().decode()
    except urllib.error.HTTPError as e: return e.code, e.read().decode()[:400]
    except Exception as e: return 0, str(e)[:200]

L('SEARCH-RESULT SELECTION DIAGNOSTIC')
L('='*55)
# Search same kind of leads the user would
code, body = post('/api/search/v2/preview', {'source':'google_maps','country':'AE','state':'Dubai','category':'IT services'})
if code==200:
    d=json.loads(body)
    res=d.get('results',[])
    L('Results: '+str(len(res)))
    already=sum(1 for r in res if r.get('already_saved'))
    L('Flagged already_saved (checkbox DISABLED): '+str(already)+' / '+str(len(res)))
    if already==len(res) and len(res)>0:
        L('  *** ALL disabled — this is the bug! Every checkbox is greyed out ***')
    elif already>0:
        L('  Some disabled (already in DB), rest should be selectable')
    else:
        L('  None disabled — checkboxes should all be clickable')
    L('')
    L('place_id format check (special chars break onclick):')
    bad=0
    for r in res[:10]:
        pid=str(r.get('place_id',''))
        has_special = any(c in pid for c in [chr(39), '"', chr(92)])
        if has_special: bad+=1
        L('  pid='+pid[:45]+(' <-- HAS SPECIAL CHAR!' if has_special else ''))
    L('')
    L('place_ids with special chars: '+str(bad))
    # Show a sample result's full fields
    if res:
        L('')
        L('Sample result keys: '+str(list(res[0].keys())))
        L('  already_saved value: '+repr(res[0].get('already_saved')))
else:
    L('Search failed: HTTP '+str(code)+' '+body[:200])

with open('sel_diag.txt','w') as f: f.write(chr(10).join(out))
