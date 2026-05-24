import os, urllib.request, urllib.error, json, time

tenant = os.environ['AZURE_TENANT_ID']
client = os.environ['AZURE_CLIENT_ID']
secret = os.environ['AZURE_CLIENT_SECRET']
mailbox = os.environ['MAILBOX_EMAIL']

log = []
def p(m): print(m, flush=True); log.append(str(m))

p('=== Microsoft Graph API Test ===')
p('Tenant: ' + tenant[:12] + '...')
p('Client: ' + client[:12] + '...')
p('Mailbox: ' + mailbox)
p('')

# Step 1: Get token
p('Step 1: Getting OAuth token...')
token_url = f'https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token'
body = urllib.parse.urlencode({
    'client_id': client,
    'client_secret': secret,
    'scope': 'https://graph.microsoft.com/.default',
    'grant_type': 'client_credentials',
}).encode()
req = urllib.request.Request(token_url, data=body, method='POST',
    headers={'Content-Type': 'application/x-www-form-urlencoded'})
try:
    resp = urllib.request.urlopen(req, timeout=30)
    tok_data = json.loads(resp.read())
    access_token = tok_data['access_token']
    p('  OK token acquired (len=' + str(len(access_token)) + ')')
except urllib.error.HTTPError as e:
    err = e.read().decode()
    p('  FAIL ' + str(e.code) + ': ' + err[:400])
    with open('graph_test.txt', 'w') as f: f.write(chr(10).join(log))
    raise SystemExit(1)

# Step 2: Get mailbox info
p('')
p('Step 2: Checking mailbox access...')
graph_url = f'https://graph.microsoft.com/v1.0/users/{mailbox}'
req = urllib.request.Request(graph_url, headers={'Authorization': f'Bearer {access_token}'})
try:
    resp = urllib.request.urlopen(req, timeout=30)
    user = json.loads(resp.read())
    p('  OK ' + user.get('displayName','?') + ' / ' + user.get('mail','?'))
except urllib.error.HTTPError as e:
    err = e.read().decode()
    p('  FAIL ' + str(e.code) + ': ' + err[:400])

# Step 3: Read recent messages
p('')
p('Step 3: Fetching 5 most recent messages...')
msg_url = f'https://graph.microsoft.com/v1.0/users/{mailbox}/messages?$top=5&$select=from,subject,receivedDateTime,isRead'
req = urllib.request.Request(msg_url, headers={'Authorization': f'Bearer {access_token}'})
try:
    resp = urllib.request.urlopen(req, timeout=30)
    msgs = json.loads(resp.read()).get('value', [])
    p('  OK Found ' + str(len(msgs)) + ' messages')
    for i, m in enumerate(msgs, 1):
        sender = m.get('from', {}).get('emailAddress', {}).get('address', '?')
        subj = m.get('subject', '')[:60]
        date = m.get('receivedDateTime', '')[:16]
        read = 'read' if m.get('isRead') else 'NEW'
        p(f'  {i}. [{read}] {date} | {sender} | {subj}')
except urllib.error.HTTPError as e:
    err = e.read().decode()
    p('  FAIL ' + str(e.code) + ': ' + err[:400])

p('')
p('=== Test Complete ===')
with open('graph_test.txt', 'w') as f: f.write(chr(10).join(log))
