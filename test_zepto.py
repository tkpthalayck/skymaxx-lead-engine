import os, json, urllib.request, urllib.error

KEY = os.environ.get("ZEPTO_TOKEN", "")
log = []
def p(msg): print(str(msg), flush=True); log.append(str(msg))

p("=== ZeptoMail Connection Test ===")
p(f"Token length: {len(KEY)}")
p(f"Token prefix: {KEY[:30]}...")

payload = {
    "from": {"address": "noreply@skymaxx.company"},
    "to": [{"email_address": {"address": "support@skymaxx.company", "name": "support"}}],
    "subject": "SKYMAXX Lead Engine — ZeptoMail Connection Test ✅",
    "htmlbody": "<div style=\"font-family:Arial;padding:20px\"><h2 style=\"color:#3b82f6\">✅ ZeptoMail Test Successful</h2><p>Your SKYMAXX Lead Engine is now connected to ZeptoMail and ready to send outreach emails.</p><p><strong>Sent from:</strong> noreply@skymaxx.company<br/><strong>System:</strong> SKYMAXX Lead Engine v1.0<br/><strong>Powered by:</strong> Render + GitHub Actions + ZeptoMail</p></div>"
}

req = urllib.request.Request(
    "https://api.zeptomail.com/v1.1/email",
    data=json.dumps(payload).encode(),
    method="POST",
    headers={
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": KEY
    }
)

try:
    resp = urllib.request.urlopen(req, timeout=30)
    body = resp.read().decode()
    p(f"HTTP {resp.status}")
    p(f"Response: {body}")
    p("\n✅ SUCCESS — Test email sent to support@skymaxx.company")
except urllib.error.HTTPError as e:
    err = e.read().decode()
    p(f"HTTP ERROR {e.code}: {err}")
except Exception as e:
    p(f"ERROR: {e}")

with open("zepto_test.txt", "w") as f:
    f.write("\n".join(log))
