import urllib.request, json, time
BASE = 'https://skymaxx-lead-engine.onrender.com'
log_lines = []
def L(m): log_lines.append(str(m)); print(m, flush=True)

def get(p, timeout=30):
    try:
        r = urllib.request.urlopen(BASE + p, timeout=timeout)
        return r.getcode(), r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:500]
    except Exception as e:
        return 0, str(e)[:200]

def post(p, body=None, timeout=45):
    try:
        req = urllib.request.Request(BASE + p, data=json.dumps(body or {}).encode(),
            headers={'Content-Type':'application/json'}, method='POST')
        r = urllib.request.urlopen(req, timeout=timeout)
        return r.getcode(), r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:500]
    except Exception as e:
        return 0, str(e)[:200]

L('=' * 70)
L('FINAL VERIFICATION')
L('=' * 70)
L('')
L('Before cron — current state:')
code, body = get('/api/stats')
try:
    s = json.loads(body)
    L('  In sequence: ' + str(s.get('in_sequence')))
    L('  Total sent:  ' + str(s.get('total_sent')))
    L('  Today sent:  ' + str(s.get('today_sent')))
except: pass
L('')

L('Triggering cron (capped at 8/run)...')
code, body = post('/api/cron/process', {}, timeout=45)
L('  HTTP ' + str(code))
try:
    d = json.loads(body)
    L('  OK:           ' + str(d.get('ok')))
    L('  Pending before: ' + str(d.get('sends', {}).get('before_pending')))
    L('  Pending after:  ' + str(d.get('sends', {}).get('after_pending')))
    L('  Sent this run:  ' + str(d.get('sends', {}).get('sent_this_run')))
    L('  Send error:     ' + str(d.get('sends', {}).get('error')))
    L('  Duration:       ' + str(d.get('started_at')) + ' → ' + str(d.get('completed_at')))
except: L('  ' + body[:300])

L('')
L('After cron — final state:')
code, body = get('/api/stats')
try:
    s = json.loads(body)
    L('  In sequence: ' + str(s.get('in_sequence')))
    L('  Total sent:  ' + str(s.get('total_sent')))
    L('  Today sent:  ' + str(s.get('today_sent')))
    L('  Total failed:' + str(s.get('total_failed')))
except: pass

L('')
L('Email log:')
code, body = get('/api/log')
try:
    d = json.loads(body)
    log = d.get('log', [])
    L('  Total entries: ' + str(len(log)))
    successes = [e for e in log if e.get('status') == 'success']
    failures = [e for e in log if e.get('status') != 'success']
    L('  Successes: ' + str(len(successes)))
    L('  Failures:  ' + str(len(failures)))
    if failures:
        L('  Failure details:')
        for e in failures[:5]:
            L('    - ' + str(e.get('to_email')) + ' | ' + str(e.get('error_msg','')[:80]))
except: pass

with open('final_v.txt', 'w') as f: f.write('\n'.join(log_lines))
