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

def get(p, timeout=30):
    try:
        r = urllib.request.urlopen(BASE + p, timeout=timeout)
        return r.getcode(), r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:500]
    except Exception as e:
        return 0, 'Exception: ' + str(e)[:300]

def post(p, body=None, timeout=180):
    try:
        data = json.dumps(body or {}).encode()
        req = urllib.request.Request(BASE + p, data=data,
            headers={'Content-Type': 'application/json'}, method='POST')
        r = urllib.request.urlopen(req, timeout=timeout)
        return r.getcode(), r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:500]
    except Exception as e:
        return 0, 'Exception: ' + str(e)[:300]

sect('STEP 1: Verify schema — all tables present?')
code, body = get('/api/debug/ensure_schema')
try:
    d = json.loads(body)
    for tbl, status in d.get('tables', {}).items():
        icon = 'OK' if status == 'ok' else 'FAIL'
        L('  [' + icon + '] ' + tbl + ': ' + status[:80])
except: L('  ' + body[:300])

sect('STEP 2: Fix Campaign 1 — replace stale IDs with current valid leads')
code, body = post('/api/debug/fix_campaign_leads/1', {})
try:
    d = json.loads(body)
    L('  Fixed:           ' + str(d.get('fixed')))
    L('  New lead count:  ' + str(d.get('new_lead_count')))
    L('  New IDs:         ' + str(d.get('new_lead_ids', [])[:14]))
except: L('  ' + body[:300])

sect('STEP 3: Approve campaign 1 (NOW with valid leads)')
code, body = post('/api/campaigns/1/approve', {'approved_by': 'final_test'})
try:
    d = json.loads(body)
    L('  Enrolled:        ' + str(d.get('enrolled')) + ' / ' + str(d.get('total_in_json')))
    L('  Skipped:         ' + str(d.get('skipped')))
    if d.get('skipped_reasons'):
        for s in d.get('skipped_reasons', [])[:5]:
            L('    - ' + str(s))
    L('  Enrolled IDs:    ' + str(d.get('enrolled_ids', [])))
except: L('  ' + body[:500])

sect('STEP 4: Verify leads are now in_sequence')
code, body = get('/api/stats')
try:
    s = json.loads(body)
    L('  Total leads:    ' + str(s.get('total_leads')))
    L('  In sequence:    ' + str(s.get('in_sequence')) + '   ← should be 14!')
    L('  With email:     ' + str(s.get('with_email')))
except: L('  ' + body[:200])

sect('STEP 5: Check upcoming sequence queue')
code, body = get('/api/sequence/queue')
try:
    d = json.loads(body)
    upc = d.get('upcoming', [])
    L('  Upcoming sends in queue: ' + str(len(upc)))
    for u in upc[:10]:
        L('    ' + str(u.get('name', '')) + ' → step ' + str(u.get('next_step')) +
          ' | due ' + str(u.get('due_at'))[:19])
except: L('  ' + body[:200])

sect('STEP 6: Trigger CRON — should now send first emails')
code, body = post('/api/cron/process', {}, timeout=180)
L('  HTTP ' + str(code))
try:
    d = json.loads(body)
    L('  OK:                       ' + str(d.get('ok')))
    L('  Sends pending BEFORE:     ' + str(d.get('sends', {}).get('before_pending')))
    L('  Sends pending AFTER:      ' + str(d.get('sends', {}).get('after_pending')))
    L('  *** SENDS THIS RUN: *** ' + str(d.get('sends', {}).get('sent_this_run')))
    L('  Send error:               ' + str(d.get('sends', {}).get('error')))
    L('  Replies processed:        ' + str(d.get('replies', {}).get('processed')))
    L('  Replies error:            ' + str(d.get('replies', {}).get('error')))
    L('  Duration:                 ' + str(d.get('started_at')) + ' → ' + str(d.get('completed_at')))
except: L('  ' + body[:500])

sect('STEP 7: Final dashboard state')
code, body = get('/api/stats')
try:
    s = json.loads(body)
    L('  Total leads:    ' + str(s.get('total_leads')))
    L('  In sequence:    ' + str(s.get('in_sequence')))
    L('  Today sent:     ' + str(s.get('today_sent')))
    L('  Total sent:     ' + str(s.get('total_sent')))
    L('  Total failed:   ' + str(s.get('total_failed')))
except: pass

L('')
L('  --- Email log (every send attempt) ---')
code, body = get('/api/log')
try:
    d = json.loads(body)
    log = d.get('log', [])
    L('  Total entries: ' + str(len(log)))
    for entry in log[:15]:
        L('    ' + str(entry.get('sent_at', ''))[:19] + ' | ' +
          'step=' + str(entry.get('step')) + ' | ' +
          'status=' + str(entry.get('status')) + ' | ' +
          'to=' + str(entry.get('to_email', ''))[:30] +
          (' | err=' + str(entry.get('error_msg', ''))[:50] if entry.get('error_msg') else ''))
except: L('  ' + body[:200])

with open('verify2.txt', 'w') as f:
    f.write('\n'.join(log_lines))
print('\n=== DONE ===')
