import urllib.request, json, time
BASE='https://skymaxx-lead-engine.onrender.com'
out=[]
def L(m): out.append(str(m)); print(m,flush=True)

def get(p,t=30):
    try:
        r=urllib.request.urlopen(BASE+p,timeout=t); return r.getcode(), r.read().decode()
    except urllib.error.HTTPError as e: return e.code, e.read().decode()[:500]
    except Exception as e: return 0, str(e)[:200]

L('='*68)
L('CAMPAIGN 1 DEEP DIAGNOSTIC')
L('='*68)
code, body = get('/api/debug/campaign/1')
if code==200:
    d=json.loads(body)
    c=d.get('campaign',{})
    L('Campaign status: '+str(c.get('status')))
    L('actually_sent:   '+str(c.get('actually_sent')))
    L('actually_failed: '+str(c.get('actually_failed')))
    L('actually_replied:'+str(c.get('actually_replied')))
    L('lead_ids count:  '+str(d.get('lead_ids_count')))
    L('leads in_seq:    '+str(d.get('leads_in_sequence')))
    L('')
    L('PER-LEAD STATE (sequence_step + next_send_at):')
    now = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime())
    L('  (current UTC: '+now+')')
    L('')
    due_now=0; future=0; done=0
    for l in d.get('leads',[]):
        step=l.get('sequence_step'); nsa=l.get('next_send_at'); inseq=l.get('in_sequence')
        L('  id='+str(l.get('id')).ljust(3)+' step='+str(step)+
          ' in_seq='+str(inseq)+' next_send='+str(nsa or 'NULL')[:19]+
          ' replied='+str(l.get('replied')))
        if not inseq: done+=1
        elif nsa and str(nsa) > now: future+=1
        else: due_now+=1
    L('')
    L('SUMMARY:')
    L('  Due now (should send next cron): '+str(due_now))
    L('  Scheduled future (waiting):      '+str(future))
    L('  Finished/not in seq:             '+str(done))
else:
    L('HTTP '+str(code)+': '+body[:300])

# Also check the email log count
L('')
code, body = get('/api/log')
if code==200:
    d=json.loads(body)
    log=d.get('log',[])
    L('Email log total: '+str(len(log)))
    by_step={}
    for e in log:
        s=e.get('step'); by_step[s]=by_step.get(s,0)+1
    L('By step: '+str(by_step))

with open('camp_diag.txt','w') as f: f.write(chr(10).join(out))
