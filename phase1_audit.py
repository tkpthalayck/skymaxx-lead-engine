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

def get(p, timeout=25):
    try:
        t0 = time.time()
        r = urllib.request.urlopen(BASE + p, timeout=timeout)
        return r.getcode(), time.time() - t0, r.read().decode()
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode()[:500]
        except:
            body = '(no body)'
        return e.code, 0, body
    except Exception as e:
        return 0, 0, 'Exception: ' + str(e)[:300]

sect('1A. APPLICATION HEALTH')
paths = ['/api/stats', '/api/config', '/api/leads?per_page=100', '/api/campaigns',
         '/api/log', '/api/sequence/queue', '/api/groups', '/api/debug/db',
         '/api/linkedin/status']
for p in paths:
    code, et, body = get(p)
    status_icon = 'OK' if code == 200 else 'FAIL'
    L('  [' + status_icon + '] HTTP ' + str(code) + ' | ' + format(et, '.2f') + 's | ' + p)
    if code != 200:
        L('      ERROR BODY: ' + body[:300])

sect('1B. STATS DEEP DIVE')
code, _, body = get('/api/stats')
if code == 200:
    try:
        s = json.loads(body)
        for k in sorted(s.keys()):
            L('  ' + str(k).ljust(20) + ' = ' + str(s[k]))
    except Exception as e:
        L('  Parse err: ' + str(e))
        L('  Raw: ' + body[:400])
else:
    L('  Stats endpoint not OK: HTTP ' + str(code))

sect('1C. LEAD STATE')
code, _, body = get('/api/leads?per_page=100')
if code == 200:
    try:
        d = json.loads(body)
        leads = d.get('leads', [])
        L('  Total leads (DB): ' + str(d.get('total', '?')))
        L('  Leads returned: ' + str(len(leads)))
        in_seq = [l for l in leads if l.get('in_sequence')]
        has_email = [l for l in leads if l.get('email')]
        replied = [l for l in leads if l.get('replied')]
        L('  In sequence: ' + str(len(in_seq)))
        L('  With email:  ' + str(len(has_email)))
        L('  Replied:     ' + str(len(replied)))
        if in_seq:
            L('')
            L('  IN-SEQUENCE LEADS (first 10):')
            for l in in_seq[:10]:
                L('    id=' + str(l.get('id')) + ' | ' +
                  str(l.get('name', ''))[:25] + ' | ' +
                  'campaign_id=' + str(l.get('campaign_id')) + ' | ' +
                  'step=' + str(l.get('current_step')) + ' | ' +
                  'last_sent=' + str(l.get('last_sent_at', 'never')))
        else:
            L('')
            L('  ⚠️  NO LEADS IN SEQUENCE — this is a major problem if campaigns were approved!')
        L('')
        L('  SAMPLE LEADS (first 5):')
        for l in leads[:5]:
            L('    id=' + str(l.get('id')) + ' | ' +
              str(l.get('name', ''))[:25] + ' | ' +
              str(l.get('email', ''))[:35] + ' | ' +
              'in_seq=' + str(l.get('in_sequence')) + ' | ' +
              'campaign=' + str(l.get('campaign_id')))
    except Exception as e:
        L('  Err: ' + str(e))
        L('  Raw: ' + body[:400])

sect('1D. CAMPAIGNS')
code, _, body = get('/api/campaigns')
if code == 200:
    try:
        d = json.loads(body)
        camps = d.get('campaigns', [])
        L('  Total campaigns: ' + str(len(camps)))
        for c in camps:
            L('')
            L('  Campaign id=' + str(c.get('id')) + ': ' + str(c.get('name', '(unnamed)'))[:50])
            for k in ['status', 'approved_at', 'created_at', 'total_leads',
                      'actually_started', 'actually_sent', 'actually_failed',
                      'actually_replied']:
                L('    ' + k.ljust(20) + ' = ' + str(c.get(k)))
    except Exception as e:
        L('  Err: ' + str(e))
        L('  Raw: ' + body[:600])

sect('1E. EMAIL LOG (every send attempt)')
code, _, body = get('/api/log')
if code == 200:
    try:
        d = json.loads(body)
        entries = d.get('log', [])
        L('  Total log entries: ' + str(len(entries)))
        if not entries:
            L('  ⚠️  EMAIL LOG IS EMPTY — no sends recorded')
        for entry in entries[:20]:
            L('    ' + str(entry.get('sent_at', ''))[:19] + ' | ' +
              'step=' + str(entry.get('step', '?')) + ' | ' +
              'status=' + str(entry.get('status', '?')) + ' | ' +
              str(entry.get('to_email', ''))[:35])
    except Exception as e:
        L('  Err: ' + str(e))

sect('1F. UPCOMING SENDS (scheduler queue)')
code, _, body = get('/api/sequence/queue')
if code == 200:
    try:
        d = json.loads(body)
        upc = d.get('upcoming', [])
        L('  Upcoming sends in queue: ' + str(len(upc)))
        if not upc:
            L('  ⚠️  NO UPCOMING SENDS — scheduler sees nothing due')
        for u in upc[:10]:
            L('    ' + str(u.get('name', '')) + ' → step ' + str(u.get('next_step')) +
              ' | due ' + str(u.get('due_at')))
    except Exception as e:
        L('  Err: ' + str(e))

sect('1G. SCHEDULER ENDPOINTS — are they exposed?')
# Try common cron/scheduler endpoint patterns
for p in ['/api/cron/process', '/api/scheduler/run', '/api/sequence/process',
          '/api/cron/replies', '/api/send/process', '/api/admin/run_sequence']:
    code, et, body = get(p, timeout=8)
    L('  ' + str(code).ljust(3) + ' | ' + p)

sect('SUMMARY')
L('Audit complete. Key questions for diagnosis:')
L('1. Are leads in_sequence=1?  (if not, "Start Campaign" failed)')
L('2. Is the email_log empty?  (if yes, no sends ever attempted)')
L('3. Is /api/sequence/queue empty?  (if yes, scheduler sees no due work)')
L('4. Is there a cron/scheduler endpoint?  (Render free tier has NO background workers)')

with open('phase1.txt', 'w') as f:
    f.write('\n'.join(log_lines))
print('\n=== Wrote phase1.txt (' + str(len(log_lines)) + ' lines) ===')
