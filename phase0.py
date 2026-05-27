import urllib.request
import json
import time

BASE = 'https://skymaxx-lead-engine.onrender.com'
log_lines = []

def L(m):
    log_lines.append(str(m))
    print(m, flush=True)

def sect(t):
    L('')
    L('=' * 70)
    L(t)
    L('=' * 70)

def get(p, timeout=20):
    try:
        t0 = time.time()
        r = urllib.request.urlopen(BASE + p, timeout=timeout)
        return r.getcode(), time.time() - t0, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, 0, e.read().decode()[:400]
    except Exception as e:
        return 0, 0, 'Exception: ' + str(e)[:300]

sect('0A. CORE ENDPOINTS HEALTH')
endpoints = ['/api/stats', '/api/campaigns', '/api/leads?per_page=200',
             '/api/log', '/api/sequence/queue', '/api/config',
             '/api/debug/db', '/api/debug/ensure_schema']
for p in endpoints:
    code, et, body = get(p)
    L('  [' + ('OK' if code == 200 else 'X') + '] HTTP ' + str(code) +
      ' | ' + format(et, '.2f') + 's | ' + p)

sect('0B. STATS — what does dashboard see?')
code, _, body = get('/api/stats')
if code == 200:
    try:
        s = json.loads(body)
        for k in sorted(s.keys()):
            L('  ' + k.ljust(20) + ' = ' + str(s[k]))
    except: L('  ' + body[:300])

sect('0C. ALL CAMPAIGNS — full state')
code, _, body = get('/api/campaigns')
if code == 200:
    try:
        d = json.loads(body)
        camps = d.get('campaigns', [])
        L('  Total campaigns: ' + str(len(camps)))
        for c in camps:
            L('')
            L('  Campaign id=' + str(c.get('id')) + ': ' + str(c.get('name'))[:50])
            for k in ['status', 'approved_at', 'created_at', 'recipient_count',
                      'actually_started', 'actually_sent', 'actually_failed',
                      'actually_replied']:
                v = c.get(k)
                L('    ' + k.ljust(20) + ' = ' + str(v))
    except Exception as e:
        L('  Err: ' + str(e))

sect('0D. EMAIL LOG — what has been sent?')
code, _, body = get('/api/log')
if code == 200:
    try:
        d = json.loads(body)
        log = d.get('log', [])
        L('  Total entries: ' + str(len(log)))
        succ = sum(1 for e in log if e.get('status') == 'success')
        fail = sum(1 for e in log if e.get('status') == 'failed')
        L('  Success: ' + str(succ))
        L('  Failed:  ' + str(fail))
        L('')
        L('  Last 10:')
        for entry in log[:10]:
            L('    ' + str(entry.get('sent_at', ''))[:24] +
              ' | step=' + str(entry.get('step')) +
              ' | ' + str(entry.get('status')) +
              ' | ' + str(entry.get('to_email', ''))[:32] +
              (' | err=' + str(entry.get('error_msg', ''))[:50] if entry.get('error_msg') else ''))
    except Exception as e:
        L('  Err: ' + str(e))

sect('0E. SCHEMA — all tables present?')
code, _, body = get('/api/debug/ensure_schema')
if code == 200:
    try:
        d = json.loads(body)
        for tbl, status in d.get('tables', {}).items():
            icon = 'OK' if status == 'ok' else 'X'
            L('  [' + icon + '] ' + tbl + ': ' + str(status)[:80])
    except: L('  ' + body[:200])

sect('0F. LEAD STATE')
code, _, body = get('/api/leads?per_page=200')
if code == 200:
    try:
        d = json.loads(body)
        leads = d.get('leads', [])
        L('  Total: ' + str(d.get('total')))
        L('  In sequence: ' + str(sum(1 for l in leads if l.get('in_sequence'))))
        L('  With email:  ' + str(sum(1 for l in leads if l.get('email'))))
        L('  Replied:     ' + str(sum(1 for l in leads if l.get('replied'))))
        L('  Linked to campaign: ' + str(sum(1 for l in leads if l.get('campaign_id'))))
    except Exception as e:
        L('  Err: ' + str(e))

sect('0G. LOGO FILE')
code, _, body = get('/static/logo.png')
L('  /static/logo.png: HTTP ' + str(code) + ' | bytes: ' + (str(len(body)) if code == 200 else 'N/A'))

with open('phase0.txt', 'w') as f:
    f.write('\n'.join(log_lines))
print('\nDONE')
