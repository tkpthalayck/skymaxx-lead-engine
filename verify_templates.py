import urllib.request, json
req = urllib.request.Request('https://skymaxx-lead-engine.onrender.com/api/sequence/templates')
resp = urllib.request.urlopen(req, timeout=60)
templates = json.loads(resp.read())
log = []
log.append('=== LIVE TEMPLATES (' + str(len(templates)) + ' emails) ===')
log.append('')
for t in templates:
    log.append('Step ' + str(t['step']) + ': ' + t['name'])
    log.append('  Subject: ' + t['subject'])
    log.append('  Day +' + str(t['delay_days']))
    log.append('  Body length: ' + str(len(t['body'])) + ' chars')
    has_lies = 'save' in t['body'].lower() and ('K/year' in t['body'] or '$28' in t['body']) or '99.99%' in t['body']
    log.append('  Fabricated claims: ' + ('FOUND!' if has_lies else 'NONE OK'))
    log.append('  Has SKYMAXX Technologies: ' + ('YES' if 'SKYMAXX Technologies' in t['body'] else 'NO'))
    log.append('  Has support@skymaxx: ' + ('YES' if 'support@skymaxx.company' in t['body'] else 'NO'))
    log.append('')

with open('templates_verify.txt','w') as f: f.write(chr(10).join(log))
print(chr(10).join(log))
