import os,sys,json,urllib.request,urllib.error
KEY=os.environ.get("RENDER_API_KEY","")
MAPS=os.environ.get("GOOGLE_MAPS_API_KEY","")
ZEPTO=os.environ.get("ZEPTO_TOKEN","")
BASE="https://api.render.com/v1"
HDR={"Authorization":f"Bearer {KEY}","Accept":"application/json","Content-Type":"application/json"}
log=[]
def p(x):
    s=str(x)
    print(s,flush=True)
    log.append(s)
def api(m,path,data=None):
    req=urllib.request.Request(BASE+path,data=json.dumps(data).encode() if data else None,method=m,headers=HDR)
    try:
        r=urllib.request.urlopen(req,timeout=30)
        return json.loads(r.read())
    except urllib.error.HTTPError as e:
        b=e.read().decode()
        p(f"HTTP {e.code}: {b[:400]}")
        raise
try:
    p(f"key_len={len(KEY)} key_start={KEY[:8]}")
    owners=api("GET","/owners?limit=1")
    p(f"owners={json.dumps(owners)[:300]}")
    oid=owners[0]["owner"]["id"]
    p(f"owner_id={oid}")
    svcs=api("GET","/services?limit=20")
    p(f"svc_count={len(svcs)}")
    for s in svcs:
        v=s.get("service",{})
        p(f"  {v.get('name')} {v.get('id')} {v.get('serviceDetails',{}).get('url','?')}")
    ex=next((s["service"] for s in svcs if s.get("service",{}).get("name")=="skymaxx-lead-engine"),None)
    if ex:
        sid=ex["id"]
        url=ex.get("serviceDetails",{}).get("url","https://skymaxx-lead-engine.onrender.com")
        p(f"exists: {sid} {url}")
        r=api("POST",f"/services/{sid}/deploys",{})
        p(f"deploy_id={r.get('id','?')}")
    else:
        p("creating...")
        pl={"type":"web_service","name":"skymaxx-lead-engine","ownerId":oid,"repo":"https://github.com/tkpthalayck/skymaxx-lead-engine","branch":"main","autoDeploy":"yes","serviceDetails":{"runtime":"python","buildCommand":"pip install -r requirements.txt","startCommand":"gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120","plan":"free","region":"oregon","envVars":[{"key":"GOOGLE_MAPS_API_KEY","value":MAPS},{"key":"ZEPTO_TOKEN","value":ZEPTO},{"key":"FROM_EMAIL","value":"support@skymaxx.company"},{"key":"FROM_NAME","value":"Ali | SKYMAXX IT Solutions"},{"key":"DB_PATH","value":"skymaxx.db"}]}}
        r=api("POST","/services",pl)
        p(f"create={json.dumps(r)[:500]}")
        svc=r.get("service",{})
        sid=svc.get("id","?")
        url=svc.get("serviceDetails",{}).get("url","https://skymaxx-lead-engine.onrender.com")
        p(f"created: {sid} {url}")
    open("LIVE_URL.txt","w").write(url+"\n")
    p(f"LIVE:{url}")
except Exception as e:
    import traceback
    p(traceback.format_exc())
open("deploy_debug.txt","w").write("\n".join(log))
