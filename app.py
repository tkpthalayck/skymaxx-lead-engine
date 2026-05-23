"""
SKYMAXX Lead Engine — Flask Backend
Full-stack lead generation + email outreach app
support@royalgroups.store
"""

from flask import Flask, jsonify, request, render_template, send_file
from flask_cors import CORS
import sqlite3, os, json, requests, time, csv, io
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
ZEPTO_TOKEN         = os.getenv("ZEPTO_TOKEN", "")
FROM_EMAIL          = os.getenv("FROM_EMAIL", "")
FROM_NAME           = os.getenv("FROM_NAME", "SKYMAXX IT Solutions")
DB_PATH             = os.getenv("DB_PATH", "skymaxx.db")

PLACES_TEXT_URL   = "https://maps.googleapis.com/maps/api/place/textsearch/json"
PLACES_DETAIL_URL = "https://maps.googleapis.com/maps/api/place/details/json"
ZEPTO_API_URL     = "https://api.zeptomail.com/v1.1/email"

UAE_GCC_CITIES = [
    "Dubai, UAE", "Abu Dhabi, UAE", "Sharjah, UAE", "Ajman, UAE",
    "Riyadh, Saudi Arabia", "Jeddah, Saudi Arabia", "Dammam, Saudi Arabia",
    "Doha, Qatar", "Kuwait City, Kuwait",
    "Muscat, Oman", "Manama, Bahrain"
]

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
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL,
            phone           TEXT,
            intl_phone      TEXT,
            website         TEXT,
            address         TEXT,
            city            TEXT,
            country         TEXT,
            category        TEXT,
            rating          REAL,
            reviews         INTEGER,
            place_id        TEXT UNIQUE,
            maps_url        TEXT,
            status          TEXT DEFAULT 'new',
            email_sent      INTEGER DEFAULT 0,
            email_sent_at   TEXT,
            email_status    TEXT,
            notes           TEXT,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS campaigns (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL,
            subject         TEXT,
            body_html       TEXT,
            total_sent      INTEGER DEFAULT 0,
            total_success   INTEGER DEFAULT 0,
            total_failed    INTEGER DEFAULT 0,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS email_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id         INTEGER,
            campaign_id     INTEGER,
            to_email        TEXT,
            status          TEXT,
            error_msg       TEXT,
            sent_at         TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()

init_db()

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def row_to_dict(row):
    return dict(row) if row else None

def rows_to_list(rows):
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────
# ROUTES — FRONTEND
# ─────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


# ─────────────────────────────────────────────
# ROUTES — STATS
# ─────────────────────────────────────────────
@app.route("/api/stats")
def get_stats():
    conn = get_db()
    stats = {
        "total_leads":    conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0],
        "emails_sent":    conn.execute("SELECT COUNT(*) FROM leads WHERE email_sent=1").fetchone()[0],
        "success":        conn.execute("SELECT COUNT(*) FROM email_log WHERE status='success'").fetchone()[0],
        "failed":         conn.execute("SELECT COUNT(*) FROM email_log WHERE status='failed'").fetchone()[0],
        "campaigns":      conn.execute("SELECT COUNT(*) FROM campaigns").fetchone()[0],
        "new_leads":      conn.execute("SELECT COUNT(*) FROM leads WHERE status='new'").fetchone()[0],
        "with_phone":     conn.execute("SELECT COUNT(*) FROM leads WHERE phone IS NOT NULL AND phone != ''").fetchone()[0],
        "with_website":   conn.execute("SELECT COUNT(*) FROM leads WHERE website IS NOT NULL AND website != ''").fetchone()[0],
    }
    conn.close()
    return jsonify(stats)


# ─────────────────────────────────────────────
# ROUTES — LEADS
# ─────────────────────────────────────────────
@app.route("/api/leads")
def get_leads():
    status  = request.args.get("status", "")
    city    = request.args.get("city", "")
    search  = request.args.get("search", "")
    page    = int(request.args.get("page", 1))
    per_pg  = int(request.args.get("per_page", 50))
    offset  = (page - 1) * per_pg

    query  = "SELECT * FROM leads WHERE 1=1"
    params = []
    if status:  query += " AND status=?";                params.append(status)
    if city:    query += " AND city LIKE ?";             params.append(f"%{city}%")
    if search:  query += " AND (name LIKE ? OR website LIKE ? OR phone LIKE ?)"; params += [f"%{search}%"]*3

    conn  = get_db()
    total = conn.execute(query.replace("SELECT *", "SELECT COUNT(*)"), params).fetchone()[0]
    leads = rows_to_list(conn.execute(query + f" ORDER BY created_at DESC LIMIT {per_pg} OFFSET {offset}", params).fetchall())
    conn.close()
    return jsonify({"leads": leads, "total": total, "page": page, "per_page": per_pg})


@app.route("/api/leads/<int:lead_id>", methods=["GET"])
def get_lead(lead_id):
    conn = get_db()
    lead = row_to_dict(conn.execute("SELECT * FROM leads WHERE id=?", [lead_id]).fetchone())
    conn.close()
    if not lead: return jsonify({"error": "Not found"}), 404
    return jsonify(lead)


@app.route("/api/leads/<int:lead_id>", methods=["PATCH"])
def update_lead(lead_id):
    data    = request.json
    allowed = ["status", "notes", "phone", "website"]
    sets    = ", ".join(f"{k}=?" for k in data if k in allowed)
    vals    = [data[k] for k in data if k in allowed] + [lead_id]
    if not sets: return jsonify({"error": "Nothing to update"}), 400
    conn = get_db()
    conn.execute(f"UPDATE leads SET {sets} WHERE id=?", vals)
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@app.route("/api/leads/<int:lead_id>", methods=["DELETE"])
def delete_lead(lead_id):
    conn = get_db()
    conn.execute("DELETE FROM leads WHERE id=?", [lead_id])
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@app.route("/api/leads/export")
def export_leads():
    conn   = get_db()
    leads  = rows_to_list(conn.execute("SELECT * FROM leads ORDER BY created_at DESC").fetchall())
    conn.close()
    if not leads:
        return jsonify({"error": "No leads"}), 404

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=leads[0].keys())
    writer.writeheader()
    writer.writerows(leads)
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"skymaxx_leads_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    )


# ─────────────────────────────────────────────
# ROUTES — GOOGLE MAPS SEARCH
# ─────────────────────────────────────────────
@app.route("/api/search", methods=["POST"])
def search_leads():
    data    = request.json
    keyword = data.get("keyword", "IT services")
    city    = data.get("city", "Dubai, UAE")
    pages   = min(int(data.get("pages", 2)), 3)

    if not GOOGLE_MAPS_API_KEY:
        return jsonify({"error": "Google Maps API key not configured"}), 400

    results    = []
    page_token = None

    for page in range(pages):
        if page_token:
            time.sleep(2)
        params = {"key": GOOGLE_MAPS_API_KEY, "query": f"{keyword} in {city}"}
        if page_token:
            params = {"key": GOOGLE_MAPS_API_KEY, "pagetoken": page_token}

        resp   = requests.get(PLACES_TEXT_URL, params=params, timeout=15).json()
        status = resp.get("status", "")

        if status == "REQUEST_DENIED":
            return jsonify({"error": resp.get("error_message", "API key error")}), 403
        if status not in ("OK", "ZERO_RESULTS"):
            break

        for place in resp.get("results", []):
            pid = place.get("place_id", "")
            # Get details (phone + website)
            det = requests.get(PLACES_DETAIL_URL, params={
                "key": GOOGLE_MAPS_API_KEY, "place_id": pid,
                "fields": "name,formatted_address,formatted_phone_number,"
                          "international_phone_number,website,rating,user_ratings_total,types,url"
            }, timeout=15).json().get("result", {})
            time.sleep(0.5)

            results.append({
                "name":       det.get("name", place.get("name", "")),
                "phone":      det.get("formatted_phone_number", ""),
                "intl_phone": det.get("international_phone_number", ""),
                "website":    det.get("website", ""),
                "address":    det.get("formatted_address", place.get("formatted_address", "")),
                "city":       city,
                "country":    city.split(",")[-1].strip(),
                "category":   ", ".join(place.get("types", [])[:3]),
                "rating":     place.get("rating", 0),
                "reviews":    place.get("user_ratings_total", 0),
                "place_id":   pid,
                "maps_url":   f"https://www.google.com/maps/place/?q=place_id:{pid}",
            })

        page_token = resp.get("next_page_token")
        if not page_token:
            break

    # Save to DB
    conn   = get_db()
    saved  = 0
    dupes  = 0
    for r in results:
        try:
            conn.execute("""
                INSERT OR IGNORE INTO leads
                (name,phone,intl_phone,website,address,city,country,category,rating,reviews,place_id,maps_url)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, [r["name"],r["phone"],r["intl_phone"],r["website"],r["address"],
                  r["city"],r["country"],r["category"],r["rating"],r["reviews"],
                  r["place_id"],r["maps_url"]])
            if conn.execute("SELECT changes()").fetchone()[0]:
                saved += 1
            else:
                dupes += 1
        except Exception:
            dupes += 1
    conn.commit()
    conn.close()

    return jsonify({
        "found":  len(results),
        "saved":  saved,
        "dupes":  dupes,
        "leads":  results
    })


@app.route("/api/cities")
def get_cities():
    return jsonify(UAE_GCC_CITIES)


# ─────────────────────────────────────────────
# ROUTES — EMAIL CAMPAIGNS
# ─────────────────────────────────────────────
@app.route("/api/campaigns", methods=["GET"])
def get_campaigns():
    conn = get_db()
    camps = rows_to_list(conn.execute("SELECT * FROM campaigns ORDER BY created_at DESC").fetchall())
    conn.close()
    return jsonify(camps)


@app.route("/api/campaigns", methods=["POST"])
def create_campaign():
    data = request.json
    conn = get_db()
    cur  = conn.execute(
        "INSERT INTO campaigns (name, subject, body_html) VALUES (?,?,?)",
        [data.get("name"), data.get("subject"), data.get("body_html")]
    )
    conn.commit()
    cid  = cur.lastrowid
    conn.close()
    return jsonify({"id": cid, "success": True})


@app.route("/api/send", methods=["POST"])
def send_emails():
    if not ZEPTO_TOKEN or not FROM_EMAIL:
        return jsonify({"error": "ZeptoMail not configured. Set ZEPTO_TOKEN and FROM_EMAIL."}), 400

    data        = request.json
    lead_ids    = data.get("lead_ids", [])      # list of lead IDs or "all"
    campaign_id = data.get("campaign_id")
    subject     = data.get("subject", "SKYMAXX IT Services — Streamline Your Business Email")
    body_html   = data.get("body_html", "")
    test_mode   = data.get("test_mode", True)

    conn = get_db()
    if lead_ids == "all":
        leads = rows_to_list(conn.execute(
            "SELECT * FROM leads WHERE email_sent=0 AND website IS NOT NULL AND website != ''"
        ).fetchall())
    else:
        ph    = ",".join("?" * len(lead_ids))
        leads = rows_to_list(conn.execute(f"SELECT * FROM leads WHERE id IN ({ph})", lead_ids).fetchall())

    results = {"sent": 0, "failed": 0, "skipped": 0, "details": []}

    for lead in leads:
        # Build email from website domain if no direct email
        website = lead.get("website", "")
        name    = lead.get("name", "there")

        # Personalise body
        personalized = body_html.replace("{{name}}", name).replace("{{website}}", website).replace("{{city}}", lead.get("city",""))

        # Use website contact email pattern (best effort)
        domain     = website.replace("https://","").replace("http://","").split("/")[0] if website else ""
        to_email   = f"info@{domain}" if domain else None

        if not to_email:
            results["skipped"] += 1
            results["details"].append({"lead": name, "status": "skipped", "reason": "no website/email"})
            continue

        if test_mode:
            results["sent"] += 1
            results["details"].append({"lead": name, "email": to_email, "status": "test"})
            continue

        # Real send
        headers = {"Accept": "application/json", "Content-Type": "application/json", "Authorization": ZEPTO_TOKEN}
        payload = {
            "from":     {"address": FROM_EMAIL, "name": FROM_NAME},
            "to":       [{"email_address": {"address": to_email, "name": name}}],
            "reply_to": [{"address": "support@royalgroups.store"}],
            "subject":  subject,
            "htmlbody": personalized,
        }
        try:
            r = requests.post(ZEPTO_API_URL, headers=headers, json=payload, timeout=15)
            ok = r.status_code in (200, 201)
            status = "success" if ok else "failed"
            if ok:
                results["sent"] += 1
                conn.execute("UPDATE leads SET email_sent=1, email_sent_at=?, email_status='sent' WHERE id=?",
                             [datetime.now().isoformat(), lead["id"]])
            else:
                results["failed"] += 1
            conn.execute("INSERT INTO email_log (lead_id,campaign_id,to_email,status,error_msg) VALUES (?,?,?,?,?)",
                         [lead["id"], campaign_id, to_email, status, "" if ok else r.text[:200]])
            results["details"].append({"lead": name, "email": to_email, "status": status})
        except Exception as e:
            results["failed"] += 1
            results["details"].append({"lead": name, "email": to_email, "status": "error", "reason": str(e)})
        time.sleep(1.5)

    if campaign_id:
        conn.execute("UPDATE campaigns SET total_sent=total_sent+?, total_success=total_success+?, total_failed=total_failed+? WHERE id=?",
                     [results["sent"]+results["failed"], results["sent"], results["failed"], campaign_id])
    conn.commit()
    conn.close()
    return jsonify(results)


# ─────────────────────────────────────────────
# ROUTES — SETTINGS CHECK
# ─────────────────────────────────────────────
@app.route("/api/config/status")
def config_status():
    return jsonify({
        "google_maps": bool(GOOGLE_MAPS_API_KEY),
        "zepto_mail":  bool(ZEPTO_TOKEN and FROM_EMAIL),
        "from_email":  FROM_EMAIL if FROM_EMAIL else "not set",
        "from_name":   FROM_NAME,
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
