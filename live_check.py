import urllib.request, json
BASE='https://skymaxx-lead-engine.onrender.com'
out=[]
def L(m): out.append(str(m)); print(m,flush=True)
try:
    html = urllib.request.urlopen(BASE+'/', timeout=40).read().decode()
    L('Live HTML size: '+str(len(html)))
    L('')
    L('FIX MARKERS in LIVE served HTML:')
    L('  createCampaign(mode) defined:     '+('YES' if 'async function createCampaign(mode)' in html else 'NO  <-- STALE DEPLOY'))
    L('  qsToggle defined:                  '+('YES' if 'function qsToggle(' in html else 'NO'))
    L('  running badge:                     '+('YES' if 'Running</span>' in html else 'NO'))
    L('  sent-count display:                '+('YES' if 'actually_sent || 0' in html else 'NO'))
    L('  Add to New Campaign button:        '+('YES' if 'Add to New Campaign' in html else 'NO'))
    L('  pagination retry:                  '+('YES' if 'next_page_token' in html or 'pagetoken' in html else 'N/A backend'))
    # Check the qsToggle onchange wiring is present in render
    L('  qsToggle onchange wiring:          '+('YES' if 'onchange=' in html and 'qsToggle' in html else 'NO'))
except Exception as e:
    L('ERR: '+str(e))
with open('live_check.txt','w') as f: f.write(chr(10).join(out))
