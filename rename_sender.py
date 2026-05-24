import os, json, urllib.request, urllib.error

KEY = os.environ['RENDER_API_KEY']
SID = 'srv-d88vm9favr4c7396kt00'
hdr = {'Authorization': 'Bearer ' + KEY, 'Accept': 'application/json'}
url = 'https://api.render.com/v1/services/' + SID + '/env-vars'

# Get all current vars
req = urllib.request.Request(url, headers=hdr)
existing = json.loads(urllib.request.urlopen(req, timeout=30).read())

current_map = {}
for item in existing:
    ev = item.get('envVar', {})
    current_map[ev.get('key')] = ev.get('value', '')

# Update FROM_NAME only
current_map['FROM_NAME'] = 'SKYMAXX Support Team'

final_list = [{'key': k, 'value': v} for k, v in current_map.items()]
body = json.dumps(final_list).encode()
req = urllib.request.Request(url, data=body, method='PUT',
    headers={**hdr, 'Content-Type': 'application/json'})
resp = urllib.request.urlopen(req, timeout=30)
print('FROM_NAME updated to: SKYMAXX Support Team')
print('HTTP', resp.status)

with open('rename_log.txt', 'w') as f:
    f.write('FROM_NAME = SKYMAXX Support Team\nHTTP ' + str(resp.status))
