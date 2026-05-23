import os, csv, json, urllib.request, urllib.error, time

KEY = os.environ.get("ZEPTO_TOKEN", "")
FROM_EMAIL = "noreply@skymaxx.company"
FROM_NAME  = "Ali | SKYMAXX IT Solutions"
REPLY_TO   = "support@skymaxx.company"

INTRO_SUBJECT = "Quick question about {{company}}'s Microsoft 365 setup"
INTRO_BODY = """<p>Hi {{first_name}},</p>
<p>I noticed you handle <strong>{{title_short}}</strong> at <strong>{{company}}</strong>, and wanted to reach out briefly.</p>
<p>We help organizations like yours streamline their <strong>Microsoft 365 / Office 365 management</strong> — typically saving 15-20 hours per week of admin overhead while improving security posture and reducing licensing costs by 25-40%.</p>
<p>A few common pain points we solve:</p>
<ul>
  <li>License optimization (catching unused E3/E5 seats)</li>
  <li>Conditional Access & MFA hardening</li>
  <li>SharePoint/Teams governance at scale</li>
  <li>Backup & compliance (Purview, retention policies)</li>
  <li>Automated user provisioning/deprovisioning</li>
</ul>
<p>Would a brief 15-minute call be useful to see if any of this is relevant for <strong>{{company}}</strong>?</p>
<p>Best regards,<br/><strong>Ali</strong><br/>SKYMAXX IT Solutions<br/>support@skymaxx.company<br/>UAE | Global</p>
<hr style="border:none;border-top:1px solid #eee;margin:20px 0"/>
<p style="font-size:11px;color:#999">SKYMAXX IT Solutions. To unsubscribe, <a href="mailto:support@skymaxx.company?subject=UNSUBSCRIBE">reply UNSUBSCRIBE</a>.</p>"""

def personalize(t, lead):
    first = (lead.get("name", "") or "there").split()[0]
    title = lead.get("title", "")
    title_short = title.replace("Chief ","").replace("Senior ","").replace(" Officer","").strip() or "IT"
    return (t.replace("{{first_name}}", first)
             .replace("{{company}}", lead.get("company","your company"))
             .replace("{{title_short}}", title_short))

def send(to_email, to_name, subject, body):
    payload = {
        "from": {"address": FROM_EMAIL, "name": FROM_NAME},
        "to":   [{"email_address": {"address": to_email, "name": to_name or "there"}}],
        "reply_to": [{"address": REPLY_TO}],
        "subject":  subject,
        "htmlbody": body,
    }
    req = urllib.request.Request(
        "https://api.zeptomail.com/v1.1/email",
        data=json.dumps(payload).encode(),
        method="POST",
        headers={"Accept":"application/json","Content-Type":"application/json","Authorization":KEY}
    )
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        return True, resp.read().decode()[:200]
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: " + e.read().decode()[:200]
    except Exception as e:
        return False, str(e)

leads = list(csv.DictReader(open("m365_leads.csv")))
print(f"Loaded {len(leads)} leads")

log = []
log.append(f"=== M365 Campaign — Step 1 (Intro) ===")
log.append(f"Total leads: {len(leads)}")
log.append(f"From: {FROM_EMAIL}")
log.append(f"Reply-to: {REPLY_TO}")
log.append("")

success = 0
failed = 0
for i, lead in enumerate(leads, 1):
    if not lead.get("email"): continue
    subject = personalize(INTRO_SUBJECT, lead)
    body    = personalize(INTRO_BODY,    lead)
    ok, info = send(lead["email"], lead.get("name",""), subject, body)
    line = f"[{i}/{len(leads)}] {lead[\"email\"]} | {lead.get(\"company\",\"\")[:30]} | "
    if ok:
        success += 1
        line += "✅ SENT"
    else:
        failed += 1
        line += f"❌ {info[:100]}"
    print(line, flush=True)
    log.append(line)
    time.sleep(1.5)

log.append("")
log.append(f"=== Summary: {success} sent, {failed} failed ===")
print(f"\nTotal: {success} sent, {failed} failed")

with open("send_log.txt", "w") as f:
    f.write("\n".join(log))
