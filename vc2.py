import urllib.request, json
BASE='https://skymaxx-lead-engine.onrender.com'
out=[]
def L(m): out.append(str(m)); print(m,flush=True)
try:
    resp=urllib.request.urlopen(BASE+'/',timeout=40)
    html=resp.read().decode()
    L('LIVE served HTML:')
    L('  qsCardClick defined:  '+('YES' if 'function qsCardClick' in html else 'NO'))
    L('  card onclick wired:   '+('YES' if 'qsCardClick(event' in html else 'NO'))
    L('  bigger checkbox:      '+('YES' if 'width:20px;height:20px' in html else 'NO'))
    L('  Cache-Control:        '+str(resp.headers.get('Cache-Control')))
except Exception as e:
    L('ERR: '+str(e))
with open('vc2.txt','w') as f: f.write(chr(10).join(out))
