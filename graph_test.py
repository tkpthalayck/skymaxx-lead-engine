import os, urllib.request, urllib.error, urllib.parse, json, time, traceback

tenant = os.environ.get('AZURE_TENANT_ID', '')
client = os.environ.get('AZURE_CLIENT_ID', '')
secret = os.environ.get('AZURE_CLIENT_SECRET', '')
mailbox = os.environ.get('MAILBOX_EMAIL', '')

log = []
def p(m): print(m, flush=True); log.append(str(m))

p('=== Microsoft Graph API Test ===')
p('Tenant len: ' + str(len(tenant)))
p('Client len: ' + str(len(client)))
p('Secret len: ' + str(len(secret)))
p('Mailbox: ' + mailbox)
p('')

try:
    p('Step 1: Getting OAuth token...')
    token_url = 'https://login.microsoftonline.com/' + tenant + '/oauth2/v2.0/token'
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
        p('  OK token (len=' + str(len(access_token)) + ')')
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        p('  FAIL HTTP ' + str(e.code) + ': ' + err[:500])
        raise

    p('')
    p('Step 2: Mailbox lookup...')
    graph_url = 'https://graph.microsoft.com/v1.0/users/' + mailbox
    req = urllib.request.Request(graph_url, headers={'Authorization': 'Bearer ' + access_token})
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        user = json.loads(resp.read())
        p('  OK ' + str(user.get('displayName','?')) + ' / ' + str(user.get('mail','?')))
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        p('  FAIL HTTP ' + str(e.code) + ': ' + err[:500])
        raise

    p('')
    p('Step 3: Reading 10 most recent messages...')
    msg_url = 'https://graph.microsoft.com/v1.0/users/' + mailbox + '/messages?$top=10&$select=from,subject,receivedDateTime,isRead'
    req = urllib.request.Request(msg_url, headers={'Authorization': 'Bearer ' + access_token})
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        msgs = json.loads(resp.read()).get('value', [])
        p('  OK Found ' + str(len(msgs)) + ' messages')
        for i, m in enumerate(msgs, 1):
            sender = m.get('from', {}).get('emailAddress', {}).get('address', '?')
            subj = m.get('subject', '')[:60]
            date = m.get('receivedDateTime', '')[:16]
            read = 'read' if m.get('isRead') else 'NEW'
            p('  ' + str(i) + '. [' + read + '] ' + date + ' | ' + sender + ' | ' + subj)
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        p('  FAIL HTTP ' + str(e.code) + ': ' + err[:500])

    p('')
    p('=== SUCCESS ===')

except Exception as e:
    p('')
    p('EXCEPTION: ' + traceback.format_exc())

with open('graph_test.txt', 'w') as f: f.write(chr(10).join(log))
print('File written')
