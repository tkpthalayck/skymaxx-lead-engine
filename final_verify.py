import os, json, urllib.request, time

# 1. Check what env vars Render actually has
KEY = os.environ['RENDER_API_KEY']
SID = 'srv-d88vm9favr4c7396kt00'

print('=== Render env vars ===')
req = urllib.request.Request('https://api.render.com/v1/services/' + SID + '/env-vars',
    headers={'Authorization': 'Bearer ' + KEY})
resp = urllib.request.urlopen(req, timeout=30)
envs = json.loads(resp.read())
for e in envs:
    ev = e.get('envVar', {})
    k = ev.get('key', '')
    v = ev.get('value', '')
    if k in ('FROM_NAME', 'FROM_EMAIL', 'MAILBOX_EMAIL', 'AZURE_TENANT_ID'):
        if 'SECRET' in k or 'TOKEN' in k or 'KEY' in k:
            v = v[:10] + '...'
        print('  ' + k + ' = ' + v)

# 2. Check deploys status
print('')
print('=== Recent deploys ===')
req = urllib.request.Request('https://api.render.com/v1/services/' + SID + '/deploys?limit=3',
    headers={'Authorization': 'Bearer ' + KEY})
resp = urllib.request.urlopen(req, timeout=30)
deploys = json.loads(resp.read())
for d in deploys:
    dep = d.get('deploy', {})
    print('  ' + dep.get('status','?') + ' | ' + dep.get('finishedAt','?')[:19] + ' | ' + (dep.get('commit',{}).get('message','?')[:50]))

# 3. Wait then check live
print('')
print('Waiting 60s for any deploy to complete...')
time.sleep(60)
req = urllib.request.Request('https://skymaxx-lead-engine.onrender.com/api/config')
resp = urllib.request.urlopen(req, timeout=60)
cfg = json.loads(resp.read())
print('=== LIVE CONFIG ===')
print('  from_name :', cfg.get('from_name'))
print('  from_email:', cfg.get('from_email'))

with open('final_verify.txt', 'w') as f:
    f.write('from_name = ' + str(cfg.get('from_name','?')))
