"""
SKYMAXX Lead Engine v2 — Sequences, Scheduling, Auto-Reply
support@royalgroups.store
"""

from flask import Flask, jsonify, request, render_template, send_file
from flask_cors import CORS
import sqlite3, os, json, requests, time, csv, io, threading
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
ZEPTO_TOKEN         = os.getenv("ZEPTO_TOKEN", "")
FROM_EMAIL          = os.getenv("FROM_EMAIL", "noreply@skymaxx.company")
FROM_NAME           = os.getenv("FROM_NAME", "Ali | SKYMAXX IT Solutions")
REPLY_TO            = os.getenv("REPLY_TO", "support@skymaxx.company")
DAILY_SEND_LIMIT    = int(os.getenv("DAILY_SEND_LIMIT", "300"))
DB_PATH             = os.getenv("DB_PATH", "skymaxx.db")

PLACES_TEXT_URL   = "https://maps.googleapis.com/maps/api/place/textsearch/json"
PLACES_DETAIL_URL = "https://maps.googleapis.com/maps/api/place/details/json"
ZEPTO_API_URL     = "https://api.zeptomail.com/v1.1/email"

UAE_GCC_CITIES = [
    "Dubai, UAE", "Abu Dhabi, UAE", "Sharjah, UAE", "Ajman, UAE",
    "Riyadh, Saudi Arabia", "Jeddah, Saudi Arabia", "Dammam, Saudi Arabia",
    "Doha, Qatar", "Kuwait City, Kuwait", "Muscat, Oman", "Manama, Bahrain"
]

# ─────────────────────────────────────────────
# 5-EMAIL SEQUENCE TEMPLATES
# ─────────────────────────────────────────────
SEQUENCE_TEMPLATES = [
    {
        "step": 1, "delay_days": 0, "name": "Intro",
        "subject": "Quick question about {{company}}'s IT setup",
        "body": """<p>Hi {{name}},</p>
<p>I came across <strong>{{company}}</strong> while researching businesses in {{city}}, and wanted to reach out briefly.</p>
<p>We help SMBs in the UAE & GCC streamline their email and IT operations — typically saving 10-15 hours per week of admin work and reducing IT costs by 30-40%.</p>
<p>Would you be open to a 15-minute call to see if it's relevant for {{company}}?</p>
<p>Best,<br/><strong>Ali</strong><br/>SKYMAXX IT Solutions<br/>support@skymaxx.company</p>"""
    },
    {
        "step": 2, "delay_days": 3, "name": "Value",
        "subject": "How {{company}} can cut email costs by 40%",
        "body": """<p>Hi {{name}},</p>
<p>Following up on my previous note about <strong>{{company}}</strong>.</p>
<p>Here's what we typically deliver for SMBs your size:</p>
<ul>
  <li>✅ Migration to enterprise-grade email (Microsoft 365 / Google Workspace)</li>
  <li>✅ SPF, DKIM, DMARC setup for 99% inbox deliverability</li>
  <li>✅ Spam & phishing protection (block 99.9% of threats)</li>
  <li>✅ 24/7 UAE-based support — Arabic & English</li>
  <li>✅ Backup & disaster recovery</li>
</ul>
<p>Most clients see ROI within 60 days. Worth a quick chat?</p>
<p>Best,<br/><strong>Ali</strong><br/>SKYMAXX IT Solutions</p>"""
    },
    {
        "step": 3, "delay_days": 7, "name": "Social Proof",
        "subject": "How a 50-person Dubai company saved $28K/year on IT",
        "body": """<p>Hi {{name}},</p>
<p>Wanted to share a quick case study that might be relevant for <strong>{{company}}</strong>.</p>
<p><em>One of our recent clients — a 50-person consulting firm in Dubai Internet City — was struggling with:</em></p>
<ul>
  <li>📧 Constant email downtime on a self-hosted server</li>
  <li>💸 $45K/year in licensing + maintenance fees</li>
  <li>🐢 IT tickets taking 3-5 days to resolve</li>
</ul>
<p><strong>After working with us for 90 days:</strong></p>
<ul>
  <li>✅ Zero email outages (99.99% uptime)</li>
  <li>✅ Reduced IT costs to $17K/year (saved $28K)</li>
  <li>✅ Tickets resolved within 4 hours guaranteed</li>
</ul>
<p>Open to a quick 15-min call to discuss your situation?</p>
<p>Best,<br/><strong>Ali</strong></p>"""
    },
    {
        "step": 4, "delay_days": 14, "name": "Follow-up",
        "subject": "Final follow-up — {{company}}",
        "body": """<p>Hi {{name}},</p>
<p>Quick follow-up — I know inboxes get busy, so this will be brief.</p>
<p>If managing IT and email is a priority for <strong>{{company}}</strong> this quarter, I'd love to share how we could help.</p>
<p>Even a quick 10-minute call would give us both clarity on whether there's a fit.</p>
<p>👉 <a href="mailto:support@skymaxx.company?subject=Yes,%20interested%20-%20{{company}}">Reply "Yes" to book a call</a></p>
<p>Best,<br/><strong>Ali</strong><br/>SKYMAXX IT Solutions</p>"""
    },
    {
        "step": 5, "delay_days": 21, "name": "Breakup",
        "subject": "Last note from me",
        "body": """<p>Hi {{name}},</p>
<p>I won't keep crowding your inbox — this'll be my last note.</p>
<p>If <strong>{{company}}</strong>'s IT and email setup is working well, that's great. If it ever becomes a pain point, our door is open.</p>
<p>👉 You can always reach me at <a href="mailto:support@skymaxx.company">support@skymaxx.company</a> when the timing is right.</p>
<p>Wishing you and the {{company}} team continued success.</p>
<p>Best,<br/><strong>Ali</strong><br/>SKYMAXX IT Solutions<br/>UAE | GCC Region</p>"""
    }
]

# Auto-reply template
AUTO_REPLY_TEMPLATE = {
    "subject": "We received your message — SKYMAXX",
    "body": """<p>Hi {{name}},</p>
<p>Thank you for reaching out to SKYMAXX IT Solutions.</p>
<p>We've received your message and one of our team members will respond within <strong>24 hours</strong> (business days, UAE time).</p>
<p>If your matter is urgent, please call us directly or include "URGENT" in your subject line.</p>
<p>Looking forward to connecting,<br/><strong>The SKYMAXX Team</strong><br/>support@skymaxx.company</p>"""
}

# ─────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS leads (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL,
            email         TEXT,
            phone         TEXT,
            intl_phone    TEXT,
            website       TEXT,
            address       TEXT,
            city          TEXT,
            country       TEXT,
            category      TEXT,
            rating        REAL,
            reviews       INTEGER,
            place_id      TEXT UNIQUE,
            maps_url      TEXT,
            status        TEXT DEFAULT 'new',
            in_sequence   INTEGER DEFAULT 0,
            sequence_step INTEGER DEFAULT 0,
            next_send_at  TEXT,
            replied       INTEGER DEFAULT 0,
            unsubscribed  INTEGER DEFAULT 0,
            notes         TEXT,
            created_at    TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS sequences (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL,
            status          TEXT DEFAULT 'active',
            total_leads     INTEGER DEFAULT 0,
            total_sent      INTEGER DEFAULT 0,
            total_failed    INTEGER DEFAULT 0,
            total_replied   INTEGER DEFAULT 0,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS email_log (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id      INTEGER,
            sequence_id  INTEGER,
            step         INTEGER,
            to_email     TEXT,
            subject      TEXT,
            status       TEXT,
            error_msg    TEXT,
            sent_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS daily_send_count (
            date  TEXT PRIMARY KEY,
            count INTEGER DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_leads_sequence ON leads(in_sequence, next_send_at);
        CREATE INDEX IF NOT EXISTS idx_log_sent_at ON email_log(sent_at);
    """)
    conn.commit()
    conn.close()

init_db()

def row_to_dict(row): return dict(row) if row else None
def rows_to_list(rows): return [dict(r) for r in rows]

# ─────────────────────────────────────────────
# EMAIL SENDING
# ─────────────────────────────────────────────
def get_todays_send_count():
    conn = get_db()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    row = conn.execute("SELECT count FROM daily_send_count WHERE date=?", [today]).fetchone()
    conn.close()
    return row["count"] if row else 0

def increment_send_count():
    conn = get_db()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    conn.execute("INSERT INTO daily_send_count (date, count) VALUES (?, 1) "
                 "ON CONFLICT(date) DO UPDATE SET count = count + 1", [today])
    conn.commit()
    conn.close()

def personalize(text, lead):
    return (text.replace("{{name}}", lead.get("name", "there").split()[0] if lead.get("name") else "there")
                .replace("{{company}}", lead.get("name", "your company"))
                .replace("{{city}}", lead.get("city", "your area"))
                .replace("{{website}}", lead.get("website", "")))

def send_via_zepto(to_email, to_name, subject, html_body):
    if not ZEPTO_TOKEN:
        return False, "ZEPTO_TOKEN not configured"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": ZEPTO_TOKEN,
    }
    payload = {
        "from": {"address": FROM_EMAIL, "name": FROM_NAME},
        "to":   [{"email_address": {"address": to_email, "name": to_name or "there"}}],
        "reply_to": [{"address": REPLY_TO}],
        "subject":  subject,
        "htmlbody": html_body + f'<br/><br/><hr style="border:none;border-top:1px solid #eee"/><p style="font-size:11px;color:#999">SKYMAXX IT Solutions, UAE. To unsubscribe, <a href="mailto:{REPLY_TO}?subject=UNSUBSCRIBE">reply UNSUBSCRIBE</a>.</p>'
    }
    try:
        r = requests.post(ZEPTO_API_URL, headers=headers, json=payload, timeout=15)
        if r.status_code in (200, 201):
            return True, None
        return False, f"HTTP {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return False, str(e)

# ─────────────────────────────────────────────
# BACKGROUND SCHEDULER — checks every 60 seconds
# ─────────────────────────────────────────────
def scheduler_loop():
    while True:
        try:
            process_pending_sends()
        except Exception as e:
            print(f"[scheduler] Error: {e}")
        time.sleep(60)

def process_pending_sends():
    today_count = get_todays_send_count()
    if today_count >= DAILY_SEND_LIMIT:
        return
    remaining = DAILY_SEND_LIMIT - today_count

    conn = get_db()
    now = datetime.utcnow().isoformat()
    pending = rows_to_list(conn.execute("""
        SELECT * FROM leads
        WHERE in_sequence=1 AND unsubscribed=0 AND replied=0
          AND email IS NOT NULL AND email != ''
          AND (next_send_at IS NULL OR next_send_at <= ?)
          AND sequence_step < 5
        ORDER BY next_send_at ASC
        LIMIT ?
    """, [now, remaining]).fetchall())
    conn.close()

    for lead in pending:
        next_step = lead["sequence_step"] + 1
        if next_step > 5: continue
        tpl = SEQUENCE_TEMPLATES[next_step - 1]
        subject = personalize(tpl["subject"], lead)
        body    = personalize(tpl["body"],    lead)

        ok, err = send_via_zepto(lead["email"], lead["name"], subject, body)
        conn = get_db()
        conn.execute("""INSERT INTO email_log (lead_id, step, to_email, subject, status, error_msg)
                        VALUES (?, ?, ?, ?, ?, ?)""",
                     [lead["id"], next_step, lead["email"], subject,
                      "success" if ok else "failed", err or ""])
        if ok:
            increment_send_count()
            if next_step >= 5:
                conn.execute("UPDATE leads SET sequence_step=?, in_sequence=0 WHERE id=?",
                             [next_step, lead["id"]])
            else:
                next_tpl = SEQUENCE_TEMPLATES[next_step]
                next_at = (datetime.utcnow() + timedelta(days=next_tpl["delay_days"])).isoformat()
                conn.execute("UPDATE leads SET sequence_step=?, next_send_at=? WHERE id=?",
                             [next_step, next_at, lead["id"]])
        conn.commit()
        conn.close()
        time.sleep(2)  # rate-limit between sends

# Start scheduler thread
threading.Thread(target=scheduler_loop, daemon=True).start()

# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────
@app.route("/")
def index(): return render_template("index.html")

@app.route("/api/stats")
def stats():
    conn = get_db()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    s = {
        "total_leads":  conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0],
        "in_sequence":  conn.execute("SELECT COUNT(*) FROM leads WHERE in_sequence=1").fetchone()[0],
        "with_email":   conn.execute("SELECT COUNT(*) FROM leads WHERE email IS NOT NULL AND email != ''").fetchone()[0],
        "replied":      conn.execute("SELECT COUNT(*) FROM leads WHERE replied=1").fetchone()[0],
        "today_sent":   get_todays_send_count(),
        "daily_limit":  DAILY_SEND_LIMIT,
        "total_sent":   conn.execute("SELECT COUNT(*) FROM email_log WHERE status='success'").fetchone()[0],
        "total_failed": conn.execute("SELECT COUNT(*) FROM email_log WHERE status='failed'").fetchone()[0],
    }
    conn.close()
    return jsonify(s)

@app.route("/api/cities")
def cities(): return jsonify(UAE_GCC_CITIES)

@app.route("/api/sequence/templates")
def get_templates(): return jsonify(SEQUENCE_TEMPLATES)

# ── LEAD SEARCH (Google Maps) ──
@app.route("/api/search", methods=["POST"])
def search():
    data = request.json
    keyword = data.get("keyword", "IT services")
    city    = data.get("city", "Dubai, UAE")
    pages   = min(int(data.get("pages", 2)), 3)
    if not GOOGLE_MAPS_API_KEY:
        return jsonify({"error": "Google Maps API key not configured"}), 400

    results, page_token = [], None
    for _ in range(pages):
        if page_token: time.sleep(2)
        params = {"key": GOOGLE_MAPS_API_KEY, "query": f"{keyword} in {city}"}
        if page_token: params = {"key": GOOGLE_MAPS_API_KEY, "pagetoken": page_token}
        resp = requests.get(PLACES_TEXT_URL, params=params, timeout=15).json()
        if resp.get("status") == "REQUEST_DENIED":
            return jsonify({"error": resp.get("error_message", "API error")}), 403
        if resp.get("status") not in ("OK", "ZERO_RESULTS"): break

        for place in resp.get("results", []):
            pid = place.get("place_id", "")
            det = requests.get(PLACES_DETAIL_URL, params={
                "key": GOOGLE_MAPS_API_KEY, "place_id": pid,
                "fields": "name,formatted_address,formatted_phone_number,international_phone_number,website,rating,user_ratings_total,types"
            }, timeout=15).json().get("result", {})
            time.sleep(0.4)

            # Best-effort email extraction from website domain
            website = det.get("website", "")
            email = ""
            if website:
                domain = website.replace("https://","").replace("http://","").split("/")[0].lstrip("www.")
                email = f"info@{domain}"

            results.append({
                "name":       det.get("name", place.get("name", "")),
                "email":      email,
                "phone":      det.get("formatted_phone_number", ""),
                "intl_phone": det.get("international_phone_number", ""),
                "website":    website,
                "address":    det.get("formatted_address", ""),
                "city":       city,
                "country":    city.split(",")[-1].strip(),
                "category":   ", ".join(place.get("types", [])[:3]),
                "rating":     place.get("rating", 0),
                "reviews":    place.get("user_ratings_total", 0),
                "place_id":   pid,
                "maps_url":   f"https://www.google.com/maps/place/?q=place_id:{pid}",
            })
        page_token = resp.get("next_page_token")
        if not page_token: break

    conn = get_db()
    saved, dupes = 0, 0
    for r in results:
        try:
            conn.execute("""INSERT OR IGNORE INTO leads
                (name,email,phone,intl_phone,website,address,city,country,category,rating,reviews,place_id,maps_url)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                [r["name"],r["email"],r["phone"],r["intl_phone"],r["website"],r["address"],
                 r["city"],r["country"],r["category"],r["rating"],r["reviews"],r["place_id"],r["maps_url"]])
            if conn.execute("SELECT changes()").fetchone()[0]: saved += 1
            else: dupes += 1
        except Exception: dupes += 1
    conn.commit(); conn.close()
    return jsonify({"found": len(results), "saved": saved, "dupes": dupes, "leads": results})

# ── LEADS LIST ──
@app.route("/api/leads")
def leads():
    page    = int(request.args.get("page", 1))
    per_pg  = int(request.args.get("per_page", 50))
    search  = request.args.get("search", "")
    status  = request.args.get("status", "")
    in_seq  = request.args.get("in_sequence", "")
    offset  = (page - 1) * per_pg

    q = "SELECT * FROM leads WHERE 1=1"; params = []
    if search:  q += " AND (name LIKE ? OR website LIKE ? OR email LIKE ?)"; params += [f"%{search}%"]*3
    if status:  q += " AND status=?"; params.append(status)
    if in_seq:  q += " AND in_sequence=?"; params.append(int(in_seq))

    conn = get_db()
    total = conn.execute(q.replace("SELECT *", "SELECT COUNT(*)"), params).fetchone()[0]
    items = rows_to_list(conn.execute(q + f" ORDER BY created_at DESC LIMIT {per_pg} OFFSET {offset}", params).fetchall())
    conn.close()
    return jsonify({"leads": items, "total": total, "page": page})

# ── ENROLL IN SEQUENCE ──
@app.route("/api/sequence/enroll", methods=["POST"])
def enroll():
    data = request.json
    lead_ids = data.get("lead_ids", "all")
    conn = get_db()
    if lead_ids == "all":
        rows = conn.execute("SELECT id FROM leads WHERE email IS NOT NULL AND email != '' AND in_sequence=0 AND unsubscribed=0").fetchall()
        ids = [r["id"] for r in rows]
    else: ids = lead_ids
    for lid in ids:
        conn.execute("UPDATE leads SET in_sequence=1, sequence_step=0, next_send_at=? WHERE id=?",
                     [datetime.utcnow().isoformat(), lid])
    conn.commit(); conn.close()
    return jsonify({"enrolled": len(ids)})

@app.route("/api/sequence/pause", methods=["POST"])
def pause_seq():
    data = request.json
    ids = data.get("lead_ids", [])
    conn = get_db()
    placeholders = ",".join("?"*len(ids)) if ids else "NULL"
    if ids: conn.execute(f"UPDATE leads SET in_sequence=0 WHERE id IN ({placeholders})", ids)
    else: conn.execute("UPDATE leads SET in_sequence=0 WHERE in_sequence=1")
    conn.commit(); conn.close()
    return jsonify({"paused": True})

@app.route("/api/sequence/queue")
def queue():
    conn = get_db()
    upcoming = rows_to_list(conn.execute("""SELECT l.name, l.email, l.city, l.sequence_step, l.next_send_at
        FROM leads l WHERE in_sequence=1 ORDER BY next_send_at ASC LIMIT 50""").fetchall())
    conn.close()
    return jsonify({"upcoming": upcoming})

# ── EMAIL LOG ──
@app.route("/api/log")
def email_log_route():
    conn = get_db()
    logs = rows_to_list(conn.execute("""
        SELECT el.*, l.name AS lead_name FROM email_log el
        LEFT JOIN leads l ON el.lead_id = l.id
        ORDER BY el.sent_at DESC LIMIT 100""").fetchall())
    conn.close()
    return jsonify({"log": logs})

# ── AUTO-REPLY WEBHOOK (called by inbound email service) ──
@app.route("/api/auto_reply", methods=["POST"])
def auto_reply():
    data = request.json or {}
    from_email = data.get("from", "")
    from_name  = data.get("name", from_email.split("@")[0] if "@" in from_email else "there")
    if not from_email or "@" not in from_email:
        return jsonify({"error": "invalid email"}), 400
    subject = AUTO_REPLY_TEMPLATE["subject"]
    body    = AUTO_REPLY_TEMPLATE["body"].replace("{{name}}", from_name)
    ok, err = send_via_zepto(from_email, from_name, subject, body)

    # Mark lead as replied if exists
    conn = get_db()
    conn.execute("UPDATE leads SET replied=1, in_sequence=0 WHERE email=?", [from_email])
    conn.commit(); conn.close()

    return jsonify({"sent": ok, "error": err})

# ── MARK REPLIED MANUALLY ──
@app.route("/api/leads/<int:lid>/mark_replied", methods=["POST"])
def mark_replied(lid):
    conn = get_db()
    conn.execute("UPDATE leads SET replied=1, in_sequence=0, status='qualified' WHERE id=?", [lid])
    conn.commit(); conn.close()
    return jsonify({"ok": True})

# ── UNSUBSCRIBE ──
@app.route("/unsubscribe/<email>")
def unsub(email):
    conn = get_db()
    conn.execute("UPDATE leads SET unsubscribed=1, in_sequence=0 WHERE email=?", [email])
    conn.commit(); conn.close()
    return f"<h2>Unsubscribed: {email}</h2><p>You will not receive further emails from SKYMAXX.</p>"

# ── EXPORT ──
@app.route("/api/export")
def export_leads():
    conn = get_db()
    leads = rows_to_list(conn.execute("SELECT * FROM leads ORDER BY created_at DESC").fetchall())
    conn.close()
    if not leads: return jsonify({"error": "No leads"}), 404
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=leads[0].keys())
    writer.writeheader(); writer.writerows(leads)
    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode()), mimetype="text/csv",
        as_attachment=True, download_name=f"skymaxx_leads_{datetime.now().strftime('%Y%m%d_%H%M')}.csv")

# ── IMPORT CSV ──
@app.route("/api/import", methods=["POST"])
def import_csv():
    if "file" not in request.files: return jsonify({"error": "no file"}), 400
    f = request.files["file"]
    reader = csv.DictReader(io.StringIO(f.read().decode("utf-8")))
    conn = get_db()
    imported = 0
    for row in reader:
        try:
            conn.execute("""INSERT OR IGNORE INTO leads (name,email,phone,website,city,country)
                VALUES (?,?,?,?,?,?)""",
                [row.get("name","").strip(), row.get("email","").strip(),
                 row.get("phone","").strip(), row.get("website","").strip(),
                 row.get("city","").strip(), row.get("country","").strip()])
            if conn.execute("SELECT changes()").fetchone()[0]: imported += 1
        except Exception: pass
    conn.commit(); conn.close()
    return jsonify({"imported": imported})

# ── CONFIG STATUS ──
@app.route("/api/config")
def config_check():
    return jsonify({
        "google_maps":  bool(GOOGLE_MAPS_API_KEY),
        "zepto_mail":   bool(ZEPTO_TOKEN),
        "from_email":   FROM_EMAIL,
        "from_name":    FROM_NAME,
        "reply_to":     REPLY_TO,
        "daily_limit":  DAILY_SEND_LIMIT,
    })

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
