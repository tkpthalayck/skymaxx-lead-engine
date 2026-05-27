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

def post(p, body=None, timeout=60):
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

sect('STEP 1: Inspect Campaign 1 — see what lead_ids_json contains')
code, body = get('/api/debug/campaign/1')
if code == 200:
    try:
        d = json.loads(body)
        L('  Campaign name:           ' + str(d.get('campaign', {}).get('name')))
        L('  Campaign status:         ' + str(d.get('campaign', {}).get('status')))
        L('  Approved at:             ' + str(d.get('campaign', {}).get('approved_at')))
        L('  actually_started:        ' + str(d.get('campaign', {}).get('actually_started')))
        L('  Lead IDs in JSON:        ' + str(d.get('lead_ids_count')))
        L('  Leads found in DB:       ' + str(d.get('leads_found')))
        L('  Leads in_sequence=1:     ' + str(d.get('leads_in_sequence')))
        L('  Leads w/ campaign_id=1:  ' + str(d.get('leads_with_campaign_id')))
        L('  Email log entries:       ' + str(d.get('log_count')))
        L('')
        L('  First 5 lead IDs in JSON: ' + str(d.get('lead_ids_in_json', [])[:5]))
        L('')
        L('  Sample of leads:')
        for l in d.get('leads', [])[:5]:
            L('    id=' + str(l.get('id')) +
              ' | name=' + str(l.get('name', ''))[:20] +
              ' | email=' + str(l.get('email', ''))[:30] +
              ' | in_seq=' + str(l.get('in_sequence')) +
              ' | step=' + str(l.get('sequence_step')) +
              ' | next=' + str(l.get('next_send_at') or 'NULL')[:19] +
              ' | replied=' + str(l.get('replied')) +
              ' | campaign_id=' + str(l.get('campaign_id')))
    except Exception as e:
        L('  Parse err: ' + str(e))
        L('  Body: ' + body[:400])
else:
    L('  HTTP ' + str(code) + ' | ' + body[:300])

sect('STEP 2: Reset campaign 1 → pending_approval')
code, body = post('/api/debug/reset_campaign/1', {})
L('  HTTP ' + str(code))
try:
    d = json.loads(body)
    L('  Reset: ' + str(d.get('reset')))
    L('  Leads reset: ' + str(d.get('leads_reset')))
except: L('  Body: ' + body[:300])

sect('STEP 3: Re-approve campaign 1 — should now enroll all leads properly')
code, body = post('/api/campaigns/1/approve', {'approved_by': 'audit_test'})
L('  HTTP ' + str(code))
try:
    d = json.loads(body)
    L('  Enrolled:        ' + str(d.get('enrolled')))
    L('  Skipped:         ' + str(d.get('skipped')))
    L('  Total in JSON:   ' + str(d.get('total_in_json')))
    L('  Message:         ' + str(d.get('message')))
    if d.get('skipped_reasons'):
        L('  Skip reasons:')
        for s in d.get('skipped_reasons', [])[:10]:
            L('    - ' + str(s))
    if d.get('enrolled_ids'):
        L('  Enrolled IDs (first 10): ' + str(d.get('enrolled_ids', [])[:10]))
except Exception as e:
    L('  Err: ' + str(e))
    L('  Body: ' + body[:500])

sect('STEP 4: Verify state — check stats + debug campaign')
code, body = get('/api/stats')
try:
    s = json.loads(body)
    L('  Total leads:    ' + str(s.get('total_leads')))
    L('  In sequence:    ' + str(s.get('in_sequence')) + '  ← should now be > 0')
    L('  With email:     ' + str(s.get('with_email')))
    L('  Today sent:     ' + str(s.get('today_sent')))
    L('  Total sent:     ' + str(s.get('total_sent')))
except: L('  ' + body[:200])

sect('STEP 5: Trigger /api/cron/process — this is what external cron will call')
code, body = post('/api/cron/process', {}, timeout=120)
L('  HTTP ' + str(code))
try:
    d = json.loads(body)
    L('  OK:                       ' + str(d.get('ok')))
    L('  Started:                  ' + str(d.get('started_at')))
    L('  Completed:                ' + str(d.get('completed_at')))
    L('  Sends pending BEFORE:     ' + str(d.get('sends', {}).get('before_pending')))
    L('  Sends pending AFTER:      ' + str(d.get('sends', {}).get('after_pending')))
    L('  Sends THIS RUN:           ' + str(d.get('sends', {}).get('sent_this_run')))
    L('  Send error:               ' + str(d.get('sends', {}).get('error')))
    L('  Replies processed:        ' + str(d.get('replies', {}).get('processed')))
    L('  Replies error:            ' + str(d.get('replies', {}).get('error')))
except Exception as e:
    L('  Err: ' + str(e))
    L('  Body: ' + body[:500])

sect('STEP 6: Final state — what is now in the DB?')
code, body = get('/api/stats')
try:
    s = json.loads(body)
    L('  Total sent:     ' + str(s.get('total_sent')))
    L('  Today sent:     ' + str(s.get('today_sent')))
    L('  In sequence:    ' + str(s.get('in_sequence')))
    L('  Total failed:   ' + str(s.get('total_failed')))
except: pass

L('')
L('  --- Recent email log ---')
code, body = get('/api/log')
try:
    d = json.loads(body)
    log = d.get('log', [])
    L('  Total log entries: ' + str(len(log)))
    for entry in log[:10]:
        L('    ' + str(entry.get('sent_at', ''))[:19] + ' | ' +
          'step=' + str(entry.get('step')) + ' | ' +
          'status=' + str(entry.get('status')) + ' | ' +
          'to=' + str(entry.get('to_email', ''))[:30] + ' | ' +
          'err=' + str(entry.get('error_msg', ''))[:40])
except: L('  ' + body[:200])

with open('verify.txt', 'w') as f:
    f.write('\n'.join(log_lines))
print('\n=== Wrote verify.txt ===')
