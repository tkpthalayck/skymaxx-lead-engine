import os, json, urllib.request, urllib.error

RENDER_KEY = os.environ['RENDER_API_KEY']
SERVICE_ID = 'srv-d88vm9favr4c7396kt00'

new_vars = [
    {'key': 'AZURE_TENANT_ID',     'value': os.environ['AZURE_TENANT_ID']},
    {'key': 'AZURE_CLIENT_ID',     'value': os.environ['AZURE_CLIENT_ID']},
    {'key': 'AZURE_CLIENT_SECRET', 'value': os.environ['AZURE_CLIENT_SECRET']},
    {'key': 'MAILBOX_EMAIL',       'value': 'support@skymaxx.company'},
    {'key': 'REPLY_POLL_MINUTES',  'value': '5'},
    {'key': 'FROM_EMAIL',          'value': 'noreply@skymaxx.company'},
    {'key': 'FROM_NAME',           'value': 'Ali | SKYMAXX IT Solutions'},
]

log = []
def p(m): print(m, flush=True); log.append(str(m))

p('=== Updating Render Env Vars ===')

# Get existing env vars first
hdr = {'Authorization': 'Bearer ' + RENDER_KEY, 'Accept': 'application/json'}
url = 'https://api.render.com/v1/services/' + SERVICE_ID + '/env-vars'

try:
    req = urllib.request.Request(url, headers=hdr)
    resp = urllib.request.urlopen(req, timeout=30)
    existing = json.loads(resp.read())
    p('Existing vars: ' + str(len(existing)))
    
    # Map existing by key
    existing_map = {}
    for item in existing:
        ev = item.get('envVar', {})
        existing_map[ev.get('key')] = ev.get('value', '')
    
    # Merge new + existing
    final = dict(existing_map)
    for v in new_vars:
        final[v['key']] = v['value']
    
    final_list = [{'key': k, 'value': v} for k, v in final.items()]
    p('Setting ' + str(len(final_list)) + ' total env vars')
    
    # PUT the full env vars list
    body = json.dumps(final_list).encode()
    req = urllib.request.Request(url, data=body, method='PUT',
        headers={**hdr, 'Content-Type': 'application/json'})
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        p('  OK env vars updated (HTTP ' + str(resp.status) + ')')
    except urllib.error.HTTPError as e:
        p('  FAIL env update HTTP ' + str(e.code) + ': ' + e.read().decode()[:300])
except urllib.error.HTTPError as e:
    p('FAIL list HTTP ' + str(e.code) + ': ' + e.read().decode()[:300])

with open('render_env_update.txt', 'w') as f:
    f.write(chr(10).join(log))
