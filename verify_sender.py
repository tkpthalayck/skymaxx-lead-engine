import urllib.request, json
req = urllib.request.Request('https://skymaxx-lead-engine.onrender.com/api/config')
resp = urllib.request.urlopen(req, timeout=60)
data = json.loads(resp.read())
print('Live config:')
print('  from_email:', data.get('from_email'))
print('  from_name :', data.get('from_name'))
print('  graph_api :', data.get('graph_api'))
print('  zepto_mail:', data.get('zepto_mail'))
with open('sender_verify.txt','w') as f:
    f.write('from_name = ' + data.get('from_name','?'))
