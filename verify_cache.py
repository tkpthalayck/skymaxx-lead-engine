import urllib.request, json
BASE='https://skymaxx-lead-engine.onrender.com'
out=[]
def L(m): out.append(str(m)); print(m,flush=True)
try:
    req=urllib.request.Request(BASE+'/')
    resp=urllib.request.urlopen(req,timeout=40)
    html=resp.read().decode()
    L('VERIFY no-cache + click-to-select')
    L('='*50)
    L('Cache-Control header: '+str(resp.headers.get('Cache-Control')))
    L('Pragma header:        '+str(resp.headers.get('Pragma')))
    L('')
    L('qsCardClick defined:        '+('YES ✓' if 'function qsCardClick' in html else 'NO'))
    L('card onclick wired:         '+('YES ✓' if 'qsCardClick(event' in html else 'NO'))
    L('bigger checkbox (20px):     '+('YES ✓' if 'width:20px;height:20px' in html else 'NO'))
    L('checkbox stopPropagation:   '+('YES ✓' if 'event.stopPropagation()' in html else 'NO'))
except Exception as e:
    L('ERR: '+str(e))
with open('verify_cache.txt','w') as f: f.write(chr(10).join(out))
