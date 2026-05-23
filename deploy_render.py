import os,sys,json,urllib.request,urllib.error,base64
KEY=os.environ.get("RENDER_API_KEY","")
MAPS=os.environ.get("GOOGLE_MAPS_API_KEY","")
ZEPTO=os.environ.get("ZEPTO_TOKEN","")
GH_TOKEN=os.environ.get("GH_TOKEN","")
BASE="https://api.render.com/v1"
HDR={"Authorization":f"Bearer {KEY}","Accept":"application/json","Content-Type":"application/json"}
log=[]
def p(x): s=str(x); print(s,flush=True); log.append(s)
def api(m,path,data=None):
    req=urllib.request.Request(BASE+path,data=json.dumps(data).encode() if data else None,method=m,headers=HDR)
    try:
        r=urllib.request.urlopen(req,timeout=30); return json.loads(r.read())
    except urllib.error.HTTPError as e:
        b=e.read().decode(); p(f"HTTP {e.code}: {b[:400]}"); raise
def gh_put(path,content,msg):
    enc=base64.b64encode(content.encode()).decode()
    try:
        r2=urllib.request.Request(f"https://api.github.com/repos/tkpthalayck/skymaxx-lead-engine/contents/{path}",headers={"Authorization":f"token {GH_TOKEN}"})
        sha=json.loads(urllib.request.urlopen(r2).read()).get("sha")
    except: sha=None
    pl={"message":msg,"content":enc}
    if sha: pl["sha"]=sha
    req=urllib.request.Request(f"https://api.github.com/repos/tkpthalayck/skymaxx-lead-engine/contents/{path}",data=json.dumps(pl).encode(),method="PUT",headers={"Authorization":f"token {GH_TOKEN}","Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(req).read())
url="https://skymaxx-lead-engine.onrender.com"
try:
    p(f"key_len={len(KEY)}")
    owners=api("GET","/owners?limit=1")
    p(f"owners={json.dumps(owners)[:200]}")
    oid=owners[0]["owner"]["id"]
    p(f"oid={oid}")
    svcs=api("GET","/services?limit=20")
    p(f"svc_count={len(svcs)}")
    for s in svcs:
        v=s.get("service",{}); p(f"  {v.get('name')} {v.get('id')} {v.get('serviceDetails',{}).get('url','?')}")
    ex=next((s["service"] for s in svcs if s.get("service",{}).get("name")=="skymaxx-lead-engine"),None)
    if ex:
        sid=ex["id"]; url=ex.get("serviceDetails",{}).get("url",url)
        p(f"exists:{sid} {url}")
        r=api("POST",f"/services/{sid}/deploys",{}); p(f"deploy:{r.get('id','?')}")
    else:
        p("creating...")
        pl={"type":"web_service","name":"skymaxx-lead-engine","ownerId":oid,"repo":"https://github.com/tkpthalayck/skymaxx-lead-engine","branch":"main","autoDeploy":"yes","serviceDetails":{"runtime":"python","buildCommand":"pip install -r requirements.txt","startCommand":"gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120","plan":"free","region":"oregon","envVars":[{"key":"GOOGLE_MAPS_API_KEY","value":MAPS},{"key":"ZEPTO_TOKEN","value":ZEPTO},{"key":"FROM_EMAIL","value":"support@skymaxx.company"},{"key":"FROM_NAME","value":"Ali | SKYMAXX IT Solutions"},{"key":"DB_PATH","value":"skymaxx.db"}]}}
        r=api("POST","/services",pl); p(f"created={json.dumps(r)[:400]}")
        svc=r.get("service",{}); sid=svc.get("id","?")
        url=svc.get("serviceDetails",{}).get("url",url); p(f"url={url}")
    p(f"DONE url={url}")
except Exception as e:
    import traceback; p(traceback.format_exc())
result="\n".join(log)
p("Writing to GitHub API...")
gh_put("deploy_debug.txt",result,"debug output [skip ci]")
gh_put("LIVE_URL.txt",url+"\n","live url [skip ci]")
p("Done writing to GitHub")
