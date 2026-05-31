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

# ═══════════════════════════════════════════════════════════════════════
# AUTHENTICATION
# ═══════════════════════════════════════════════════════════════════════
import secrets as _secrets
from functools import wraps as _wraps

# Session secret (random fallback if env not set — sessions invalidate on restart, which is fine)
# Stable fallback secret — sessions survive Render free-tier cold starts.
# Strongly recommended: set FLASK_SECRET_KEY env var in Render for production.
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or "skx-stable-7b3f2e8c4a91d6f0e5a8b2c7d4e9f1a3"

# Session config
from datetime import timedelta as _td
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SECURE"]   = True  # HTTPS only (Render is always HTTPS)
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["PERMANENT_SESSION_LIFETIME"] = _td(days=30)

# Credentials from env vars (with a default that DEMANDS to be changed)
AUTH_USER     = os.environ.get("SKYMAXX_AUTH_USER", "admin")
AUTH_PASSWORD = os.environ.get("SKYMAXX_AUTH_PASSWORD", "SKYMAXX@2026")
CRON_SECRET   = os.environ.get("SKYMAXX_CRON_SECRET", "skx-cron-7eb2f3a4c9d1")

# Public endpoints that don't require login
_PUBLIC_ENDPOINTS = {"login", "static", "logout", "health"}

# Endpoints that allow CRON_SECRET as alternative auth (for GitHub Actions cron)
_CRON_ENDPOINTS = {"cron_process"}


@app.before_request
def require_auth():
    from flask import session, request, redirect, url_for, jsonify
    endpoint = request.endpoint or ""

    # Allow public endpoints + static files
    if endpoint in _PUBLIC_ENDPOINTS:
        return None

    # For cron endpoints, accept X-Cron-Secret header OR ?token= as alternative to session
    if endpoint in _CRON_ENDPOINTS:
        provided = request.headers.get("X-Cron-Secret") or request.args.get("token") or ""
        if provided and provided == CRON_SECRET:
            return None
        # No valid cron secret → fall through to session check

    # Session-based auth
    if session.get("user"):
        return None

    # Not authenticated — API → JSON 401, page → redirect to login
    if request.path.startswith("/api/"):
        return jsonify({"error": "unauthorized", "login_url": "/login"}), 401
    return redirect(url_for("login"))


@app.route("/api/health")
def health():
    """Public health check for uptime monitoring (no auth required).
    Returns 200 with status if DB reachable, 503 if degraded.
    Cheap, fast, side-effect-free except for triggering piggyback cron on /api/* paths."""
    import time as _time
    db_status = "ok"
    db_latency_ms = 0
    try:
        _t0 = _time.time()
        conn = get_db()
        conn.execute("SELECT 1")
        db_latency_ms = int((_time.time() - _t0) * 1000)
        try: conn.close()
        except Exception: pass
    except Exception as e:
        db_status = "down"
        db_latency_ms = -1
    
    payload = {
        "status":   "ok" if db_status == "ok" else "degraded",
        "service":  "skymaxx-lead-engine",
        "db":       db_status,
        "db_latency_ms": db_latency_ms,
        "ts":       int(_time.time()),
    }
    return jsonify(payload), 200 if db_status == "ok" else 503



@app.before_request
def _piggyback_cron_hook():
    """Triggers process_pending_sends in background on API requests — keeps email sequence engine moving."""
    try:
        if request.path.startswith('/api/') and not request.path.startswith('/api/cron'):
            _piggyback_cron_check()
    except Exception as e:
        print(f"[piggyback-hook] err: {e}")


@app.route("/login", methods=["GET", "POST"])
def login():
    from flask import session, request, redirect, url_for, render_template_string
    error = None
    if request.method == "POST":
        u = (request.form.get("username") or "").strip()
        p = request.form.get("password") or ""
        if u == AUTH_USER and p == AUTH_PASSWORD:
            session.permanent = True
            session["user"] = u
            return redirect(request.args.get("next") or url_for("index"))
        error = "Invalid username or password"

    page = """<!doctype html><html><head>
    <title>SKYMAXX Login</title>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <link rel="icon" href="/static/favicon.png" type="image/png"/>
    <style>
      *{box-sizing:border-box;margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif}
      body{background:linear-gradient(135deg,#0f172a 0%,#1e293b 100%);min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}
      .card{background:white;border-radius:12px;padding:40px;width:100%;max-width:400px;box-shadow:0 20px 50px rgba(0,0,0,.5)}
      .logo{text-align:center;margin-bottom:24px}
      .logo img{width:80px;height:80px}
      h1{font-size:24px;font-weight:700;color:#0f172a;text-align:center;margin-bottom:8px}
      .sub{text-align:center;color:#64748b;font-size:13px;margin-bottom:28px}
      label{display:block;font-size:13px;font-weight:500;color:#334155;margin-bottom:6px}
      input{width:100%;padding:11px 14px;border:1px solid #cbd5e1;border-radius:8px;font-size:14px;margin-bottom:16px;transition:border-color .2s}
      input:focus{outline:none;border-color:#3b82f6;box-shadow:0 0 0 3px rgba(59,130,246,.1)}
      button{width:100%;padding:12px;background:#3b82f6;color:white;border:none;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer;transition:background .2s}
      button:hover{background:#2563eb}
      .error{background:#fef2f2;border:1px solid #fecaca;color:#991b1b;padding:10px 12px;border-radius:8px;font-size:13px;margin-bottom:16px}
      .hint{margin-top:18px;text-align:center;font-size:11px;color:#94a3b8}
    </style></head><body>
    <div class="card">
      <div class="logo"><img src="/static/logo.png" alt="SKYMAXX"/></div>
      <h1>SKYMAXX Lead Engine</h1>
      <div class="sub">Sign in to continue</div>
      {% if error %}<div class="error">{{ error }}</div>{% endif %}
      <form method="POST">
        <label>Username</label>
        <input name="username" autofocus autocomplete="username" required>
        <label>Password</label>
        <input name="password" type="password" autocomplete="current-password" required>
        <button type="submit">Sign in</button>
      </form>
      <div class="hint">Authorized access only</div>
    </div>
    </body></html>"""
    return render_template_string(page, error=error)


@app.route("/logout")
def logout():
    from flask import session, redirect, url_for
    session.clear()
    return redirect(url_for("login"))





# ═══════════════════════════════════════════════════════════════════════
# GLOBAL ERROR HANDLERS — guarantee /api/* always returns JSON, never HTML
# ═══════════════════════════════════════════════════════════════════════
@app.errorhandler(404)
def _api_json_404(e):
    from flask import request, jsonify
    if request.path.startswith("/api/"):
        return jsonify({"error": "not found", "path": request.path}), 404
    return e

@app.errorhandler(405)
def _api_json_405(e):
    from flask import request, jsonify
    if request.path.startswith("/api/"):
        return jsonify({"error": "method not allowed", "path": request.path}), 405
    return e

@app.errorhandler(500)
def _api_json_500(e):
    from flask import request, jsonify
    if request.path.startswith("/api/"):
        return jsonify({"error": "server error", "detail": str(e)[:200]}), 500
    return e

@app.errorhandler(Exception)
def _api_json_error(e):
    from flask import request, jsonify
    import traceback
    if request.path.startswith("/api/"):
        # Log full traceback to stderr, return safe JSON to client
        print(f"[api error] {request.path}: {type(e).__name__}: {e}")
        traceback.print_exc()
        return jsonify({
            "error": type(e).__name__,
            "detail": str(e)[:300]
        }), 500
    # Non-API routes — let Flask's default HTML error pages handle
    raise e


@app.after_request
def add_no_cache_headers(response):
    """Prevent browsers from caching the HTML/JS so users always get the latest UI."""
    if response.content_type and response.content_type.startswith("text/html"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

CORS(app)

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
ZEPTO_TOKEN         = os.getenv("ZEPTO_TOKEN", "")
FROM_EMAIL          = os.getenv("FROM_EMAIL", "noreply@skymaxx.company")
FROM_NAME           = os.getenv("FROM_NAME", "SKYMAXX Support Team")
REPLY_TO            = os.getenv("REPLY_TO", "support@skymaxx.company")
BCC_SUPPORT         = os.getenv("BCC_SUPPORT", "true").lower() == "true"  # BCC support@ on all sends
APP_URL             = os.getenv("APP_URL", "https://skymaxx-lead-engine.onrender.com").rstrip("/")
TRACKING_ENABLED    = os.getenv("TRACKING_ENABLED", "true").lower() == "true"
DAILY_SEND_LIMIT    = int(os.getenv("DAILY_SEND_LIMIT", "300"))


# ═══════════════════════════════════════════════════════════════════════
# PIGGYBACK CRON: Keep sequence engine progressing without external cron
# Every API request checks if process_pending_sends has run recently.
# If 5+ minutes passed, fires it in a background daemon thread.
# Works in tandem with GitHub Actions cron (which still fires every 1-3 hours)
# Net effect: cron runs much more frequently when the app is active.
# ═══════════════════════════════════════════════════════════════════════
import threading as _piggy_threading
import time as _piggy_time

_PIGGYBACK_CRON_LAST_RUN = 0.0
_PIGGYBACK_CRON_INTERVAL = 300.0  # 5 minutes
_PIGGYBACK_CRON_LOCK = _piggy_threading.Lock()

def _piggyback_cron_check():
    """Called on every request. Triggers process_pending_sends if interval elapsed.
    Non-blocking: runs in background daemon thread."""
    global _PIGGYBACK_CRON_LAST_RUN
    now = _piggy_time.time()
    if now - _PIGGYBACK_CRON_LAST_RUN < _PIGGYBACK_CRON_INTERVAL:
        return
    if not _PIGGYBACK_CRON_LOCK.acquire(blocking=False):
        return  # another check is already in progress
    try:
        _PIGGYBACK_CRON_LAST_RUN = now
    except Exception:
        _PIGGYBACK_CRON_LOCK.release()
        return
    
    def _run_cron_bg():
        try:
            # Cap to a small batch — keep response fast
            process_pending_sends(max_per_run=10)
        except Exception as e:
            print(f"[piggyback-cron] err: {e}")
        finally:
            try:
                _PIGGYBACK_CRON_LOCK.release()
            except Exception:
                pass
    
    t = _piggy_threading.Thread(target=_run_cron_bg, daemon=True)
    t.start()
DB_PATH             = os.getenv("DB_PATH", "skymaxx.db")

PLACES_TEXT_URL   = "https://maps.googleapis.com/maps/api/place/textsearch/json"
PLACES_DETAIL_URL = "https://maps.googleapis.com/maps/api/place/details/json"
ZEPTO_API_URL     = "https://api.zeptomail.com/v1.1/email"

UAE_GCC_CITIES = [
    "Dubai, UAE", "Abu Dhabi, UAE", "Sharjah, UAE", "Ajman, UAE",
    "Riyadh, Saudi Arabia", "Jeddah, Saudi Arabia", "Dammam, Saudi Arabia",
    "Doha, Qatar", "Kuwait City, Kuwait", "Muscat, Oman", "Manama, Bahrain"
]

# Hierarchical geography: Country → States/Regions
COUNTRIES = [
    # GCC & MENA - primary market
    {"code": "AE", "name": "United Arab Emirates", "region": "GCC"},
    {"code": "SA", "name": "Saudi Arabia",         "region": "GCC"},
    {"code": "QA", "name": "Qatar",                "region": "GCC"},
    {"code": "KW", "name": "Kuwait",               "region": "GCC"},
    {"code": "OM", "name": "Oman",                 "region": "GCC"},
    {"code": "BH", "name": "Bahrain",              "region": "GCC"},
    {"code": "EG", "name": "Egypt",                "region": "MENA"},
    {"code": "JO", "name": "Jordan",               "region": "MENA"},
    {"code": "LB", "name": "Lebanon",              "region": "MENA"},
    {"code": "TR", "name": "Turkey",               "region": "MENA"},
    {"code": "MA", "name": "Morocco",              "region": "MENA"},
    {"code": "TN", "name": "Tunisia",              "region": "MENA"},
    {"code": "DZ", "name": "Algeria",              "region": "MENA"},
    {"code": "IQ", "name": "Iraq",                 "region": "MENA"},
    {"code": "IL", "name": "Israel",               "region": "MENA"},
    # Asia
    {"code": "IN", "name": "India",                "region": "Asia"},
    {"code": "PK", "name": "Pakistan",             "region": "Asia"},
    {"code": "BD", "name": "Bangladesh",           "region": "Asia"},
    {"code": "LK", "name": "Sri Lanka",            "region": "Asia"},
    {"code": "NP", "name": "Nepal",                "region": "Asia"},
    {"code": "SG", "name": "Singapore",            "region": "Asia"},
    {"code": "MY", "name": "Malaysia",             "region": "Asia"},
    {"code": "ID", "name": "Indonesia",            "region": "Asia"},
    {"code": "TH", "name": "Thailand",             "region": "Asia"},
    {"code": "VN", "name": "Vietnam",              "region": "Asia"},
    {"code": "PH", "name": "Philippines",          "region": "Asia"},
    {"code": "JP", "name": "Japan",                "region": "Asia"},
    {"code": "KR", "name": "South Korea",          "region": "Asia"},
    {"code": "CN", "name": "China",                "region": "Asia"},
    {"code": "HK", "name": "Hong Kong",            "region": "Asia"},
    {"code": "TW", "name": "Taiwan",               "region": "Asia"},
    # Americas
    {"code": "US", "name": "United States",        "region": "Americas"},
    {"code": "CA", "name": "Canada",               "region": "Americas"},
    {"code": "MX", "name": "Mexico",               "region": "Americas"},
    {"code": "BR", "name": "Brazil",               "region": "Americas"},
    {"code": "AR", "name": "Argentina",            "region": "Americas"},
    {"code": "CL", "name": "Chile",                "region": "Americas"},
    {"code": "CO", "name": "Colombia",             "region": "Americas"},
    # Europe
    {"code": "GB", "name": "United Kingdom",       "region": "Europe"},
    {"code": "IE", "name": "Ireland",              "region": "Europe"},
    {"code": "DE", "name": "Germany",              "region": "Europe"},
    {"code": "FR", "name": "France",               "region": "Europe"},
    {"code": "IT", "name": "Italy",                "region": "Europe"},
    {"code": "ES", "name": "Spain",                "region": "Europe"},
    {"code": "PT", "name": "Portugal",             "region": "Europe"},
    {"code": "NL", "name": "Netherlands",          "region": "Europe"},
    {"code": "BE", "name": "Belgium",              "region": "Europe"},
    {"code": "CH", "name": "Switzerland",          "region": "Europe"},
    {"code": "AT", "name": "Austria",              "region": "Europe"},
    {"code": "PL", "name": "Poland",               "region": "Europe"},
    {"code": "SE", "name": "Sweden",               "region": "Europe"},
    {"code": "NO", "name": "Norway",               "region": "Europe"},
    {"code": "DK", "name": "Denmark",              "region": "Europe"},
    {"code": "FI", "name": "Finland",              "region": "Europe"},
    {"code": "GR", "name": "Greece",               "region": "Europe"},
    {"code": "CZ", "name": "Czech Republic",       "region": "Europe"},
    {"code": "RO", "name": "Romania",              "region": "Europe"},
    {"code": "HU", "name": "Hungary",              "region": "Europe"},
    # Oceania
    {"code": "AU", "name": "Australia",            "region": "Oceania"},
    {"code": "NZ", "name": "New Zealand",          "region": "Oceania"},
    # Africa (Sub-Saharan)
    {"code": "ZA", "name": "South Africa",         "region": "Africa"},
    {"code": "NG", "name": "Nigeria",              "region": "Africa"},
    {"code": "KE", "name": "Kenya",                "region": "Africa"},
    {"code": "GH", "name": "Ghana",                "region": "Africa"},
    {"code": "ET", "name": "Ethiopia",             "region": "Africa"},
]

# States/Regions per country
COUNTRY_STATES = {
    # ── GCC ──
    "AE": ["Dubai", "Abu Dhabi", "Sharjah", "Ajman", "Ras Al Khaimah", "Umm Al Quwain", "Fujairah"],
    "SA": ["Riyadh", "Mecca (Jeddah)", "Eastern Province (Dammam)", "Medina", "Asir (Abha)",
           "Tabuk", "Ha'il", "Northern Borders (Arar)", "Jazan", "Najran", "Al-Bahah", "Al-Jouf", "Qassim"],
    "QA": ["Doha", "Al Rayyan", "Al Wakrah", "Al Khor", "Al Daayen", "Umm Salal"],
    "KW": ["Kuwait City", "Hawalli", "Al Farwaniyah", "Al Ahmadi", "Mubarak Al-Kabeer", "Jahra"],
    "OM": ["Muscat", "Salalah", "Sohar", "Nizwa", "Sur", "Ibri", "Buraimi", "Rustaq"],
    "BH": ["Manama", "Muharraq", "Riffa", "Hamad Town", "A'ali", "Isa Town", "Sitra"],
    # ── MENA ──
    "EG": ["Cairo", "Alexandria", "Giza", "Sharm El Sheikh", "Hurghada", "Luxor", "Aswan", "Port Said", "Suez", "Mansoura", "Tanta"],
    "JO": ["Amman", "Zarqa", "Irbid", "Aqaba", "Salt", "Madaba", "Karak", "Mafraq"],
    "LB": ["Beirut", "Tripoli", "Sidon", "Tyre", "Zahle", "Jounieh", "Byblos"],
    "TR": ["Istanbul", "Ankara", "Izmir", "Bursa", "Antalya", "Adana", "Konya", "Gaziantep", "Kayseri", "Mersin", "Eskisehir"],
    "MA": ["Casablanca", "Rabat", "Marrakesh", "Tangier", "Fes", "Agadir", "Meknes", "Oujda", "Tetouan"],
    "TN": ["Tunis", "Sfax", "Sousse", "Kairouan", "Bizerte", "Gabes", "Ariana"],
    "DZ": ["Algiers", "Oran", "Constantine", "Annaba", "Blida", "Batna", "Setif"],
    "IQ": ["Baghdad", "Basra", "Mosul", "Erbil", "Sulaymaniyah", "Najaf", "Karbala"],
    "IL": ["Tel Aviv", "Jerusalem", "Haifa", "Beersheba", "Netanya", "Ashdod", "Petah Tikva", "Rishon LeZion"],
    # ── ASIA ──
    "IN": ["Mumbai (Maharashtra)", "Delhi", "Bangalore (Karnataka)", "Hyderabad (Telangana)", "Chennai (Tamil Nadu)",
           "Kolkata (West Bengal)", "Pune (Maharashtra)", "Ahmedabad (Gujarat)", "Jaipur (Rajasthan)", "Surat (Gujarat)",
           "Lucknow (Uttar Pradesh)", "Kanpur (Uttar Pradesh)", "Nagpur (Maharashtra)", "Indore (Madhya Pradesh)",
           "Bhopal (Madhya Pradesh)", "Patna (Bihar)", "Vadodara (Gujarat)", "Ghaziabad (Uttar Pradesh)",
           "Ludhiana (Punjab)", "Coimbatore (Tamil Nadu)", "Kochi (Kerala)", "Thiruvananthapuram (Kerala)",
           "Visakhapatnam (Andhra Pradesh)", "Chandigarh", "Goa", "Guwahati (Assam)", "Bhubaneswar (Odisha)"],
    "PK": ["Karachi", "Lahore", "Islamabad", "Rawalpindi", "Faisalabad", "Multan", "Peshawar", "Quetta", "Sialkot", "Gujranwala"],
    "BD": ["Dhaka", "Chittagong", "Khulna", "Rajshahi", "Sylhet", "Barisal", "Rangpur"],
    "LK": ["Colombo", "Kandy", "Galle", "Jaffna", "Negombo", "Trincomalee"],
    "NP": ["Kathmandu", "Pokhara", "Lalitpur", "Biratnagar", "Birgunj"],
    "SG": ["Singapore (Central)", "Singapore (North)", "Singapore (East)", "Singapore (West)", "Singapore (Northeast)"],
    "MY": ["Kuala Lumpur", "Penang", "Johor Bahru", "Ipoh", "Shah Alam", "Petaling Jaya", "Kuching", "Kota Kinabalu", "Malacca"],
    "ID": ["Jakarta", "Surabaya", "Bandung", "Medan", "Bekasi", "Semarang", "Palembang", "Makassar", "Yogyakarta", "Denpasar (Bali)"],
    "TH": ["Bangkok", "Chiang Mai", "Pattaya", "Phuket", "Hat Yai", "Nakhon Ratchasima", "Khon Kaen"],
    "VN": ["Ho Chi Minh City", "Hanoi", "Da Nang", "Hai Phong", "Can Tho", "Bien Hoa"],
    "PH": ["Manila", "Cebu", "Davao", "Quezon City", "Makati", "Taguig", "Pasig", "Baguio", "Iloilo", "Bacolod"],
    "JP": ["Tokyo", "Yokohama", "Osaka", "Nagoya", "Sapporo", "Fukuoka", "Kobe", "Kyoto", "Kawasaki", "Saitama", "Hiroshima"],
    "KR": ["Seoul", "Busan", "Incheon", "Daegu", "Daejeon", "Gwangju", "Suwon", "Ulsan"],
    "CN": ["Beijing", "Shanghai", "Guangzhou", "Shenzhen", "Chengdu", "Hangzhou", "Tianjin", "Wuhan", "Xi'an", "Nanjing", "Suzhou", "Chongqing"],
    "HK": ["Hong Kong Island", "Kowloon", "New Territories"],
    "TW": ["Taipei", "Kaohsiung", "Taichung", "Tainan", "Hsinchu"],
    # ── AMERICAS ──
    "US": ["Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut", "Delaware",
           "District of Columbia", "Florida", "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa",
           "Kansas", "Kentucky", "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota",
           "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire", "New Jersey", "New Mexico",
           "New York", "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island",
           "South Carolina", "South Dakota", "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington",
           "West Virginia", "Wisconsin", "Wyoming"],
    "CA": ["Ontario", "Quebec", "British Columbia", "Alberta", "Manitoba", "Saskatchewan", "Nova Scotia",
           "New Brunswick", "Newfoundland and Labrador", "Prince Edward Island",
           "Northwest Territories", "Yukon", "Nunavut"],
    "MX": ["Mexico City", "Guadalajara", "Monterrey", "Puebla", "Tijuana", "Leon", "Ciudad Juarez", "Merida",
           "Cancun", "Queretaro", "Aguascalientes", "Toluca", "Saltillo"],
    "BR": ["Sao Paulo", "Rio de Janeiro", "Brasilia", "Salvador", "Fortaleza", "Belo Horizonte", "Manaus",
           "Curitiba", "Recife", "Porto Alegre", "Belem", "Goiania", "Guarulhos", "Campinas"],
    "AR": ["Buenos Aires", "Cordoba", "Rosario", "Mendoza", "La Plata", "Mar del Plata", "Tucuman", "Salta"],
    "CL": ["Santiago", "Valparaiso", "Concepcion", "Antofagasta", "La Serena", "Temuco"],
    "CO": ["Bogota", "Medellin", "Cali", "Barranquilla", "Cartagena", "Bucaramanga", "Cucuta"],
    # ── EUROPE ──
    "GB": ["London", "Manchester", "Birmingham", "Leeds", "Glasgow", "Edinburgh", "Liverpool", "Bristol",
           "Sheffield", "Cardiff", "Belfast", "Newcastle", "Nottingham", "Aberdeen", "Brighton", "Oxford",
           "Cambridge", "Coventry", "Reading", "Leicester"],
    "IE": ["Dublin", "Cork", "Galway", "Limerick", "Waterford", "Kilkenny"],
    "DE": ["Berlin", "Hamburg", "Munich", "Cologne", "Frankfurt", "Stuttgart", "Dusseldorf", "Leipzig",
           "Dortmund", "Essen", "Bremen", "Dresden", "Hannover", "Nuremberg", "Bonn"],
    "FR": ["Paris", "Marseille", "Lyon", "Toulouse", "Nice", "Nantes", "Strasbourg", "Montpellier", "Bordeaux",
           "Lille", "Rennes", "Reims"],
    "IT": ["Rome", "Milan", "Naples", "Turin", "Palermo", "Genoa", "Bologna", "Florence", "Bari", "Catania",
           "Venice", "Verona"],
    "ES": ["Madrid", "Barcelona", "Valencia", "Seville", "Zaragoza", "Malaga", "Murcia", "Palma", "Las Palmas", "Bilbao"],
    "PT": ["Lisbon", "Porto", "Braga", "Coimbra", "Funchal", "Faro"],
    "NL": ["Amsterdam", "Rotterdam", "The Hague", "Utrecht", "Eindhoven", "Tilburg", "Groningen", "Almere"],
    "BE": ["Brussels", "Antwerp", "Ghent", "Bruges", "Liege", "Charleroi"],
    "CH": ["Zurich", "Geneva", "Basel", "Bern", "Lausanne", "Lugano"],
    "AT": ["Vienna", "Graz", "Linz", "Salzburg", "Innsbruck", "Klagenfurt"],
    "PL": ["Warsaw", "Krakow", "Lodz", "Wroclaw", "Poznan", "Gdansk", "Szczecin", "Lublin"],
    "SE": ["Stockholm", "Gothenburg", "Malmo", "Uppsala", "Vasteras", "Linkoping"],
    "NO": ["Oslo", "Bergen", "Trondheim", "Stavanger", "Drammen"],
    "DK": ["Copenhagen", "Aarhus", "Odense", "Aalborg"],
    "FI": ["Helsinki", "Espoo", "Tampere", "Vantaa", "Oulu", "Turku"],
    "GR": ["Athens", "Thessaloniki", "Patras", "Heraklion", "Larissa"],
    "CZ": ["Prague", "Brno", "Ostrava", "Plzen", "Liberec"],
    "RO": ["Bucharest", "Cluj-Napoca", "Timisoara", "Iasi", "Constanta", "Brasov"],
    "HU": ["Budapest", "Debrecen", "Szeged", "Miskolc", "Pecs"],
    # ── OCEANIA ──
    "AU": ["Sydney (NSW)", "Melbourne (VIC)", "Brisbane (QLD)", "Perth (WA)", "Adelaide (SA)",
           "Gold Coast (QLD)", "Newcastle (NSW)", "Canberra (ACT)", "Wollongong (NSW)", "Hobart (TAS)",
           "Darwin (NT)", "Geelong (VIC)", "Townsville (QLD)", "Cairns (QLD)"],
    "NZ": ["Auckland", "Wellington", "Christchurch", "Hamilton", "Tauranga", "Dunedin", "Palmerston North", "Napier"],
    # ── AFRICA ──
    "ZA": ["Johannesburg", "Cape Town", "Durban", "Pretoria", "Port Elizabeth", "Bloemfontein", "East London"],
    "NG": ["Lagos", "Abuja", "Kano", "Ibadan", "Port Harcourt", "Benin City", "Kaduna"],
    "KE": ["Nairobi", "Mombasa", "Kisumu", "Nakuru", "Eldoret"],
    "GH": ["Accra", "Kumasi", "Tamale", "Sekondi-Takoradi", "Cape Coast"],
    "ET": ["Addis Ababa", "Dire Dawa", "Mekelle", "Gondar", "Bahir Dar"],
}

# Expanded Business Categories (matches user spec)
BUSINESS_CATEGORIES = [
    {"id": "real_estate",        "label": "Real Estate Agencies",    "keyword": "real estate agency"},
    {"id": "hospitals",          "label": "Hospitals",                "keyword": "hospital"},
    {"id": "medical_clinics",    "label": "Medical Clinics",          "keyword": "medical clinic"},
    {"id": "dental_clinics",     "label": "Dental Clinics",           "keyword": "dental clinic"},
    {"id": "construction",       "label": "Construction Companies",   "keyword": "construction company"},
    {"id": "manufacturing",      "label": "Manufacturing Companies",  "keyword": "manufacturing company"},
    {"id": "law_firms",          "label": "Law Firms",                "keyword": "law firm"},
    {"id": "accounting",         "label": "Accounting Firms",         "keyword": "accounting firm"},
    {"id": "insurance",          "label": "Insurance Companies",      "keyword": "insurance company"},
    {"id": "retail",             "label": "Retail Stores",            "keyword": "retail store"},
    {"id": "restaurants",        "label": "Restaurants",              "keyword": "restaurant"},
    {"id": "hotels",             "label": "Hotels",                   "keyword": "hotel"},
    {"id": "logistics",          "label": "Logistics Companies",      "keyword": "logistics company"},
    {"id": "transportation",     "label": "Transportation Companies", "keyword": "transportation company"},
    {"id": "it_companies",       "label": "IT Companies",             "keyword": "IT services company"},
    {"id": "software",           "label": "Software Companies",       "keyword": "software development company"},
    {"id": "marketing",          "label": "Marketing Agencies",       "keyword": "digital marketing agency"},
    {"id": "education",          "label": "Educational Institutions", "keyword": "training institute"},
    {"id": "govt_contractors",   "label": "Government Contractors",   "keyword": "government contractor"},
    {"id": "engineering",        "label": "Engineering Firms",        "keyword": "engineering consultancy"},
    {"id": "financial",          "label": "Financial Services",       "keyword": "financial services"},
    {"id": "healthcare",         "label": "Healthcare Providers",     "keyword": "healthcare provider"},
    {"id": "consulting",         "label": "Consulting Firms",         "keyword": "business consulting firm"},
    {"id": "automotive",         "label": "Automotive",               "keyword": "auto dealership"},
    {"id": "trading",            "label": "Trading Companies",        "keyword": "trading company"},
    {"id": "fitness",            "label": "Fitness Centers",          "keyword": "fitness gym"},
    {"id": "beauty",             "label": "Beauty & Wellness",        "keyword": "beauty salon spa"},
    {"id": "advertising",        "label": "Advertising Agencies",     "keyword": "advertising agency"},
    {"id": "interior_design",    "label": "Interior Designers",       "keyword": "interior design firm"},
    {"id": "event_planning",     "label": "Event Planning",           "keyword": "event management company"},
]

# Job Title suggestions (used as KEYWORD modifier in Google Maps search,
# OR for filtering after B2B database integration)
JOB_TITLES = [
    {"id": "founder",            "label": "Founder",                  "keyword": "founder"},
    {"id": "cofounder",          "label": "Co-Founder",               "keyword": "co-founder"},
    {"id": "ceo",                "label": "CEO",                      "keyword": "CEO"},
    {"id": "managing_director",  "label": "Managing Director",        "keyword": "managing director"},
    {"id": "owner",              "label": "Owner",                    "keyword": "owner"},
    {"id": "president",          "label": "President",                "keyword": "president"},
    {"id": "partner",            "label": "Partner",                  "keyword": "partner"},
    {"id": "general_manager",    "label": "General Manager",          "keyword": "general manager"},
    {"id": "operations_manager", "label": "Operations Manager",       "keyword": "operations manager"},
    {"id": "it_manager",         "label": "IT Manager",               "keyword": "IT manager"},
    {"id": "it_director",        "label": "IT Director",              "keyword": "IT director"},
    {"id": "cto",                "label": "CTO",                      "keyword": "CTO"},
    {"id": "cio",                "label": "CIO",                      "keyword": "CIO"},
    {"id": "ciso",               "label": "CISO",                     "keyword": "CISO"},
    {"id": "procurement_mgr",    "label": "Procurement Manager",      "keyword": "procurement manager"},
    {"id": "purchasing_mgr",     "label": "Purchasing Manager",       "keyword": "purchasing manager"},
    {"id": "marketing_manager",  "label": "Marketing Manager",        "keyword": "marketing manager"},
    {"id": "sales_director",     "label": "Sales Director",           "keyword": "sales director"},
    {"id": "hr_manager",         "label": "HR Manager",               "keyword": "HR manager"},
    {"id": "finance_manager",    "label": "Finance Manager",          "keyword": "finance manager"},
    {"id": "cfo",                "label": "CFO",                      "keyword": "CFO"},
    {"id": "bdm",                "label": "Business Development Mgr", "keyword": "business development manager"},
]

# ─────────────────────────────────────────────
# 5-EMAIL SEQUENCE TEMPLATES
# ─────────────────────────────────────────────
DOMAIN_CONFIG = {
    'skymaxx': {
        'key': 'skymaxx',
        'label': 'SKYMAXX.Company',
        'website': 'https://www.SKYMAXX.Company',
        'website_display': 'www.SKYMAXX.Company',
        'company': 'SKYMAXX Technologies',
        'sender_name': 'SKYMAXX Support Team',
        'sender_email': 'support@skymaxx.company',
        'tagline': 'Microsoft 365 Specialists',
        'footer_tag': 'Microsoft 365 Management for SMBs',
        'footer_geo': 'UAE',
        'logo_url': 'https://skymaxx-lead-engine.onrender.com/static/logo_email.png',
        'header_bg': '#0f172a',
        'accent': '#60a5fa',
        'audience': 'b2b',
        'group_name': 'SKYMAXX.Company Leads',
        'group_color': '#0284c7',
    },
    'toolsshopy': {
        'key': 'toolsshopy',
        'label': 'ToolsShopy.Store',
        'website': 'https://www.ToolsShopy.Store',
        'website_display': 'www.ToolsShopy.Store',
        'company': 'ToolsShopy',
        'sender_name': 'ToolsShopy Team',
        'sender_email': 'support@toolsshopy.store',
        'tagline': 'Tools that work as hard as you do',
        'footer_tag': 'Curated tools and hardware',
        'footer_geo': 'USA',
        'logo_url': 'https://skymaxx-lead-engine.onrender.com/static/logo_email.png',
        'header_bg': '#1e293b',
        'accent': '#f97316',
        'audience': 'b2c',
        'group_name': 'ToolsShopy.Store Leads',
        'group_color': '#f97316',
    },
    'royalgroups': {
        'key': 'royalgroups',
        'label': 'RoyalGroups.Shop',
        'website': 'https://www.RoyalGroups.Shop',
        'website_display': 'www.RoyalGroups.Shop',
        'company': 'RoyalGroups',
        'sender_name': 'RoyalGroups Team',
        'sender_email': 'support@royalgroups.shop',
        'tagline': 'Curated premium products',
        'footer_tag': 'Premium product curation',
        'footer_geo': 'USA',
        'logo_url': 'https://skymaxx-lead-engine.onrender.com/static/logo_email.png',
        'header_bg': '#1e1b4b',
        'accent': '#a78bfa',
        'audience': 'b2c',
        'group_name': 'RoyalGroups.Shop Leads',
        'group_color': '#7c3aed',
    },
}

SEQUENCE_TEMPLATES_BY_DOMAIN = {
    'skymaxx': [
        {
            'step':       1,
            'delay_days': 0,
            'name':       'Initial Outreach',
            'subject':    'Office 365 Email Services for {{company}} - productivity, security, cost',
            'body':       '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd"><html xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office"><head><meta http-equiv="Content-Type" content="text/html; charset=UTF-8" /><meta http-equiv="X-UA-Compatible" content="IE=edge" /><meta name="viewport" content="width=device-width, initial-scale=1.0" /><meta name="format-detection" content="telephone=no, date=no, address=no, email=no" /><title>SKYMAXX Technologies</title><!--[if mso]><xml><o:OfficeDocumentSettings><o:AllowPNG/><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml><![endif]--><style type="text/css">body{margin:0!important;padding:0!important;width:100%!important;-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;mso-line-height-rule:exactly}table{border-collapse:collapse!important;mso-table-lspace:0pt;mso-table-rspace:0pt}img{-ms-interpolation-mode:bicubic;border:0;outline:none;text-decoration:none;display:block}a{text-decoration:none}</style></head><body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,Helvetica,sans-serif;-webkit-font-smoothing:antialiased;mso-line-height-rule:exactly"><div style="display:none;max-height:0;overflow:hidden;mso-hide:all">Benefits of Office 365 Email Services plus one-day assessment offer</div><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f3f4f6"><tr><td align="center" style="padding:24px 12px"><table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="background:#ffffff;border-radius:12px;overflow:hidden;max-width:600px"><tr><td bgcolor="#0f172a" style="background-color:#0f172a;padding:20px 32px;mso-line-height-rule:exactly;line-height:1.2"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse"><tr><td valign="middle" width="76" style="padding-right:14px;width:76px"><a href="https://www.SKYMAXX.Company" style="text-decoration:none"><img src="https://skymaxx-lead-engine.onrender.com/static/logo_email.png" alt="SKYMAXX.Company" width="60" height="60" style="display:block;width:60px;height:60px;max-width:60px;border-radius:50%;border:0;outline:none;text-decoration:none;-ms-interpolation-mode:bicubic" /></a></td><td valign="middle" style="color:#ffffff;font-size:22px;font-weight:700;letter-spacing:0.5px;font-family:Arial,Helvetica,sans-serif;mso-line-height-rule:exactly;line-height:1.2"><a href="https://www.SKYMAXX.Company" style="color:#ffffff;text-decoration:none">SKYMAXX TECHNOLOGIES</a><div style="color:#cbd5e1;font-size:12px;font-weight:500;margin-top:2px;font-family:Arial,Helvetica,sans-serif">Microsoft 365 Specialists</div><div style="margin-top:4px"><a href="https://www.SKYMAXX.Company" style="color:#60a5fa;font-size:12px;text-decoration:none;font-weight:600;font-family:Arial,Helvetica,sans-serif">www.SKYMAXX.Company</a></div></td></tr></table></td></tr><tr><td style="padding:32px 36px;font-family:Arial,Helvetica,sans-serif;color:#1f2937;font-size:15px;line-height:1.6"><p style="margin:0 0 16px">Hi {{name}},</p><p style="margin:0 0 16px">I am reaching out from <strong>SKYMAXX Technologies</strong>. We help organizations get the most from their email infrastructure &mdash; whether you are evaluating <strong>Office 365 Email Services</strong> for the first time, or already using it and looking to optimize.</p><p style="margin:0 0 14px;font-size:14px;color:#475569">Learn more about our approach at <a href="https://www.SKYMAXX.Company" style="color:#2563eb;text-decoration:underline;font-weight:600">www.SKYMAXX.Company</a>.</p><p style="margin:0 0 12px">Office 365 Email Services can deliver real value for organizations of any size:</p><ul style="margin:0 0 16px;padding-left:22px"><li style="margin-bottom:6px"><strong>Improved productivity</strong> &mdash; integrated apps, shared mailboxes, and consistent access across devices</li><li style="margin-bottom:6px"><strong>Better collaboration</strong> &mdash; shared calendars, Teams integration, and seamless document workflows</li><li style="margin-bottom:6px"><strong>Stronger security</strong> &mdash; built-in anti-phishing, encryption, and identity protection</li><li style="margin-bottom:0"><strong>Automation</strong> &mdash; workflows, auto-responses, and rules that reduce repetitive work</li></ul><p style="margin:0 0 14px;font-size:14px;color:#475569">More on our services and case context: <a href="https://www.SKYMAXX.Company" style="color:#2563eb;text-decoration:underline;font-weight:600">www.SKYMAXX.Company</a>.</p><div style="background:#f0f9ff;border-left:4px solid #0284c7;padding:16px 20px;margin:18px 0;border-radius:4px"><p style="margin:0 0 6px;font-weight:700;color:#075985">Already using Office 365 Email Services?</p><p style="margin:0;color:#0c4a6e;font-size:14px;line-height:1.55">We can conduct a one-day assessment of your email environment to identify opportunities for improvement &mdash; including enhancing email security, reducing unnecessary licensing and billing costs, optimizing configurations, implementing additional automation, and improving overall productivity. Details at <a href="https://www.SKYMAXX.Company" style="color:#2563eb;text-decoration:underline;font-weight:600">www.SKYMAXX.Company</a>.</p></div><p style="margin:0 0 16px">Would 15 minutes next week work to discuss whether either path fits the needs at {{company}}? You can also learn more at <a href="https://www.SKYMAXX.Company" style="color:#2563eb;text-decoration:underline;font-weight:600">www.SKYMAXX.Company</a> before we connect.</p><p style="margin:0 0 4px">Best regards,</p><p style="margin:0;font-weight:600">SKYMAXX Support Team</p><p style="margin:0;color:#64748b;font-size:13px">SKYMAXX Technologies &middot; <a href="https://www.SKYMAXX.Company" style="color:#2563eb;text-decoration:underline;font-weight:600">www.SKYMAXX.Company</a> &middot; support@skymaxx.company</p></td></tr><tr><td style="background:#0f172a;padding:18px 36px;color:#94a3b8;font-size:11px;line-height:1.5;font-family:Arial,Helvetica,sans-serif"><p style="margin:0"><strong style="color:#cbd5e1">SKYMAXX Technologies</strong> &middot; <a href="https://www.SKYMAXX.Company" style="color:#60a5fa;text-decoration:none;font-weight:600">www.SKYMAXX.Company</a> &middot; Microsoft 365 Management for SMBs &middot; UAE</p><p style="margin:6px 0 0"><a href="mailto:support@skymaxx.company" style="color:#60a5fa;text-decoration:none">support@skymaxx.company</a> &middot; Visit us at <a href="https://www.SKYMAXX.Company" style="color:#60a5fa;text-decoration:none">www.SKYMAXX.Company</a></p><p style="margin:6px 0 0">If you prefer not to receive these messages, just reply with "unsubscribe" and we will remove you immediately.</p></td></tr></table></td></tr></table></body></html>',
        },
        {
            'step':       2,
            'delay_days': 3,
            'name':       'Follow-up',
            'subject':    'A practical look at Office 365 Email Services',
            'body':       '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd"><html xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office"><head><meta http-equiv="Content-Type" content="text/html; charset=UTF-8" /><meta http-equiv="X-UA-Compatible" content="IE=edge" /><meta name="viewport" content="width=device-width, initial-scale=1.0" /><meta name="format-detection" content="telephone=no, date=no, address=no, email=no" /><title>SKYMAXX Technologies</title><!--[if mso]><xml><o:OfficeDocumentSettings><o:AllowPNG/><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml><![endif]--><style type="text/css">body{margin:0!important;padding:0!important;width:100%!important;-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;mso-line-height-rule:exactly}table{border-collapse:collapse!important;mso-table-lspace:0pt;mso-table-rspace:0pt}img{-ms-interpolation-mode:bicubic;border:0;outline:none;text-decoration:none;display:block}a{text-decoration:none}</style></head><body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,Helvetica,sans-serif;-webkit-font-smoothing:antialiased;mso-line-height-rule:exactly"><div style="display:none;max-height:0;overflow:hidden;mso-hide:all">Productivity, collaboration, security, automation</div><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f3f4f6"><tr><td align="center" style="padding:24px 12px"><table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="background:#ffffff;border-radius:12px;overflow:hidden;max-width:600px"><tr><td bgcolor="#0f172a" style="background-color:#0f172a;padding:20px 32px;mso-line-height-rule:exactly;line-height:1.2"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse"><tr><td valign="middle" width="76" style="padding-right:14px;width:76px"><a href="https://www.SKYMAXX.Company" style="text-decoration:none"><img src="https://skymaxx-lead-engine.onrender.com/static/logo_email.png" alt="SKYMAXX.Company" width="60" height="60" style="display:block;width:60px;height:60px;max-width:60px;border-radius:50%;border:0;outline:none;text-decoration:none;-ms-interpolation-mode:bicubic" /></a></td><td valign="middle" style="color:#ffffff;font-size:22px;font-weight:700;letter-spacing:0.5px;font-family:Arial,Helvetica,sans-serif;mso-line-height-rule:exactly;line-height:1.2"><a href="https://www.SKYMAXX.Company" style="color:#ffffff;text-decoration:none">SKYMAXX TECHNOLOGIES</a><div style="color:#cbd5e1;font-size:12px;font-weight:500;margin-top:2px;font-family:Arial,Helvetica,sans-serif">Microsoft 365 Specialists</div><div style="margin-top:4px"><a href="https://www.SKYMAXX.Company" style="color:#60a5fa;font-size:12px;text-decoration:none;font-weight:600;font-family:Arial,Helvetica,sans-serif">www.SKYMAXX.Company</a></div></td></tr></table></td></tr><tr><td style="padding:32px 36px;font-family:Arial,Helvetica,sans-serif;color:#1f2937;font-size:15px;line-height:1.6"><p style="margin:0 0 16px">Hi {{name}},</p><p style="margin:0 0 16px">Following up on my earlier note from <strong>SKYMAXX Technologies</strong>. Email is one of the most-used business tools &mdash; and often one of the most overlooked when it comes to optimization.</p><p style="margin:0 0 14px;font-size:14px;color:#475569">Reference: <a href="https://www.SKYMAXX.Company" style="color:#2563eb;text-decoration:underline;font-weight:600">www.SKYMAXX.Company</a>.</p><p style="margin:0 0 12px">A few practical ways well-implemented email infrastructure can help {{company}}:</p><ul style="margin:0 0 16px;padding-left:22px"><li style="margin-bottom:6px"><strong>Productivity</strong> &mdash; fewer dropped messages, faster searches, unified inboxes for shared roles</li><li style="margin-bottom:6px"><strong>Collaboration</strong> &mdash; shared calendars, meeting scheduling, inline document editing</li><li style="margin-bottom:6px"><strong>Security</strong> &mdash; phishing protection, data loss prevention, access controls</li><li style="margin-bottom:0"><strong>Cost control</strong> &mdash; right-sized licenses, archiving instead of expensive storage, eliminating unused subscriptions</li></ul><p style="margin:0 0 16px">If you are already using Office 365 Email Services, our one-day assessment looks specifically at where these opportunities exist in your environment. If you are not yet, we can advise on whether it fits your needs. Full details on our services: <a href="https://www.SKYMAXX.Company" style="color:#2563eb;text-decoration:underline;font-weight:600">www.SKYMAXX.Company</a>.</p><p style="margin:0 0 16px">Happy to share more if useful &mdash; just reply to this email or visit <a href="https://www.SKYMAXX.Company" style="color:#2563eb;text-decoration:underline;font-weight:600">www.SKYMAXX.Company</a>.</p><p style="margin:0 0 4px">Best regards,</p><p style="margin:0;font-weight:600">SKYMAXX Support Team</p><p style="margin:0;color:#64748b;font-size:13px">SKYMAXX Technologies &middot; <a href="https://www.SKYMAXX.Company" style="color:#2563eb;text-decoration:underline;font-weight:600">www.SKYMAXX.Company</a></p></td></tr><tr><td style="background:#0f172a;padding:18px 36px;color:#94a3b8;font-size:11px;line-height:1.5;font-family:Arial,Helvetica,sans-serif"><p style="margin:0"><strong style="color:#cbd5e1">SKYMAXX Technologies</strong> &middot; <a href="https://www.SKYMAXX.Company" style="color:#60a5fa;text-decoration:none;font-weight:600">www.SKYMAXX.Company</a> &middot; Microsoft 365 Management for SMBs &middot; UAE</p><p style="margin:6px 0 0"><a href="mailto:support@skymaxx.company" style="color:#60a5fa;text-decoration:none">support@skymaxx.company</a> &middot; Visit us at <a href="https://www.SKYMAXX.Company" style="color:#60a5fa;text-decoration:none">www.SKYMAXX.Company</a></p><p style="margin:6px 0 0">If you prefer not to receive these messages, just reply with "unsubscribe" and we will remove you immediately.</p></td></tr></table></td></tr></table></body></html>',
        },
        {
            'step':       3,
            'delay_days': 4,
            'name':       'Educational',
            'subject':    'What our one-day email assessment covers',
            'body':       '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd"><html xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office"><head><meta http-equiv="Content-Type" content="text/html; charset=UTF-8" /><meta http-equiv="X-UA-Compatible" content="IE=edge" /><meta name="viewport" content="width=device-width, initial-scale=1.0" /><meta name="format-detection" content="telephone=no, date=no, address=no, email=no" /><title>SKYMAXX Technologies</title><!--[if mso]><xml><o:OfficeDocumentSettings><o:AllowPNG/><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml><![endif]--><style type="text/css">body{margin:0!important;padding:0!important;width:100%!important;-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;mso-line-height-rule:exactly}table{border-collapse:collapse!important;mso-table-lspace:0pt;mso-table-rspace:0pt}img{-ms-interpolation-mode:bicubic;border:0;outline:none;text-decoration:none;display:block}a{text-decoration:none}</style></head><body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,Helvetica,sans-serif;-webkit-font-smoothing:antialiased;mso-line-height-rule:exactly"><div style="display:none;max-height:0;overflow:hidden;mso-hide:all">Security, licensing, configuration, automation, productivity</div><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f3f4f6"><tr><td align="center" style="padding:24px 12px"><table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="background:#ffffff;border-radius:12px;overflow:hidden;max-width:600px"><tr><td bgcolor="#0f172a" style="background-color:#0f172a;padding:20px 32px;mso-line-height-rule:exactly;line-height:1.2"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse"><tr><td valign="middle" width="76" style="padding-right:14px;width:76px"><a href="https://www.SKYMAXX.Company" style="text-decoration:none"><img src="https://skymaxx-lead-engine.onrender.com/static/logo_email.png" alt="SKYMAXX.Company" width="60" height="60" style="display:block;width:60px;height:60px;max-width:60px;border-radius:50%;border:0;outline:none;text-decoration:none;-ms-interpolation-mode:bicubic" /></a></td><td valign="middle" style="color:#ffffff;font-size:22px;font-weight:700;letter-spacing:0.5px;font-family:Arial,Helvetica,sans-serif;mso-line-height-rule:exactly;line-height:1.2"><a href="https://www.SKYMAXX.Company" style="color:#ffffff;text-decoration:none">SKYMAXX TECHNOLOGIES</a><div style="color:#cbd5e1;font-size:12px;font-weight:500;margin-top:2px;font-family:Arial,Helvetica,sans-serif">Microsoft 365 Specialists</div><div style="margin-top:4px"><a href="https://www.SKYMAXX.Company" style="color:#60a5fa;font-size:12px;text-decoration:none;font-weight:600;font-family:Arial,Helvetica,sans-serif">www.SKYMAXX.Company</a></div></td></tr></table></td></tr><tr><td style="padding:32px 36px;font-family:Arial,Helvetica,sans-serif;color:#1f2937;font-size:15px;line-height:1.6"><p style="margin:0 0 16px">Hi {{name}},</p><p style="margin:0 0 16px">A quick note from <strong>SKYMAXX Technologies</strong> on what we typically review during our <strong>one-day email assessment</strong>, in case it is useful context for {{company}}.</p><p style="margin:0 0 14px;font-size:14px;color:#475569">More background: <a href="https://www.SKYMAXX.Company" style="color:#2563eb;text-decoration:underline;font-weight:600">www.SKYMAXX.Company</a>.</p><p style="margin:0 0 12px">For organizations already using Office 365 Email Services, our review covers:</p><ol style="margin:0 0 16px;padding-left:22px"><li style="margin-bottom:6px"><strong>Security posture</strong> &mdash; phishing and malware protection, MFA coverage, suspicious sign-in patterns</li><li style="margin-bottom:6px"><strong>Licensing optimization</strong> &mdash; assigned vs unused licenses, plan mix, potential cost savings</li><li style="margin-bottom:6px"><strong>Configuration review</strong> &mdash; mail flow rules, retention policies, shared mailbox setup</li><li style="margin-bottom:6px"><strong>Automation opportunities</strong> &mdash; auto-replies, distribution lists, Power Automate flows</li><li style="margin-bottom:0"><strong>Productivity quick wins</strong> &mdash; search performance, mobile access, calendar workflows</li></ol><p style="margin:0 0 16px">The output is a written report with specific findings and prioritized recommendations. No commitment beyond the assessment itself &mdash; full details at <a href="https://www.SKYMAXX.Company" style="color:#2563eb;text-decoration:underline;font-weight:600">www.SKYMAXX.Company</a>.</p><p style="margin:0 0 16px">If {{company}} is not currently using Office 365 Email Services, we are equally happy to discuss whether and how it might benefit you.</p><p style="margin:0 0 16px">Is there a good time this week or next to talk? You can also browse <a href="https://www.SKYMAXX.Company" style="color:#2563eb;text-decoration:underline;font-weight:600">www.SKYMAXX.Company</a> anytime.</p><p style="margin:0 0 4px">Best regards,</p><p style="margin:0;font-weight:600">SKYMAXX Support Team</p><p style="margin:0;color:#64748b;font-size:13px">SKYMAXX Technologies &middot; <a href="https://www.SKYMAXX.Company" style="color:#2563eb;text-decoration:underline;font-weight:600">www.SKYMAXX.Company</a></p></td></tr><tr><td style="background:#0f172a;padding:18px 36px;color:#94a3b8;font-size:11px;line-height:1.5;font-family:Arial,Helvetica,sans-serif"><p style="margin:0"><strong style="color:#cbd5e1">SKYMAXX Technologies</strong> &middot; <a href="https://www.SKYMAXX.Company" style="color:#60a5fa;text-decoration:none;font-weight:600">www.SKYMAXX.Company</a> &middot; Microsoft 365 Management for SMBs &middot; UAE</p><p style="margin:6px 0 0"><a href="mailto:support@skymaxx.company" style="color:#60a5fa;text-decoration:none">support@skymaxx.company</a> &middot; Visit us at <a href="https://www.SKYMAXX.Company" style="color:#60a5fa;text-decoration:none">www.SKYMAXX.Company</a></p><p style="margin:6px 0 0">If you prefer not to receive these messages, just reply with "unsubscribe" and we will remove you immediately.</p></td></tr></table></td></tr></table></body></html>',
        },
        {
            'step':       4,
            'delay_days': 7,
            'name':       'Value / Curation',
            'subject':    'Why email infrastructure matters for {{company}}',
            'body':       '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd"><html xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office"><head><meta http-equiv="Content-Type" content="text/html; charset=UTF-8" /><meta http-equiv="X-UA-Compatible" content="IE=edge" /><meta name="viewport" content="width=device-width, initial-scale=1.0" /><meta name="format-detection" content="telephone=no, date=no, address=no, email=no" /><title>SKYMAXX Technologies</title><!--[if mso]><xml><o:OfficeDocumentSettings><o:AllowPNG/><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml><![endif]--><style type="text/css">body{margin:0!important;padding:0!important;width:100%!important;-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;mso-line-height-rule:exactly}table{border-collapse:collapse!important;mso-table-lspace:0pt;mso-table-rspace:0pt}img{-ms-interpolation-mode:bicubic;border:0;outline:none;text-decoration:none;display:block}a{text-decoration:none}</style></head><body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,Helvetica,sans-serif;-webkit-font-smoothing:antialiased;mso-line-height-rule:exactly"><div style="display:none;max-height:0;overflow:hidden;mso-hide:all">Practical reasons to take a closer look at email security and cost</div><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f3f4f6"><tr><td align="center" style="padding:24px 12px"><table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="background:#ffffff;border-radius:12px;overflow:hidden;max-width:600px"><tr><td bgcolor="#0f172a" style="background-color:#0f172a;padding:20px 32px;mso-line-height-rule:exactly;line-height:1.2"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse"><tr><td valign="middle" width="76" style="padding-right:14px;width:76px"><a href="https://www.SKYMAXX.Company" style="text-decoration:none"><img src="https://skymaxx-lead-engine.onrender.com/static/logo_email.png" alt="SKYMAXX.Company" width="60" height="60" style="display:block;width:60px;height:60px;max-width:60px;border-radius:50%;border:0;outline:none;text-decoration:none;-ms-interpolation-mode:bicubic" /></a></td><td valign="middle" style="color:#ffffff;font-size:22px;font-weight:700;letter-spacing:0.5px;font-family:Arial,Helvetica,sans-serif;mso-line-height-rule:exactly;line-height:1.2"><a href="https://www.SKYMAXX.Company" style="color:#ffffff;text-decoration:none">SKYMAXX TECHNOLOGIES</a><div style="color:#cbd5e1;font-size:12px;font-weight:500;margin-top:2px;font-family:Arial,Helvetica,sans-serif">Microsoft 365 Specialists</div><div style="margin-top:4px"><a href="https://www.SKYMAXX.Company" style="color:#60a5fa;font-size:12px;text-decoration:none;font-weight:600;font-family:Arial,Helvetica,sans-serif">www.SKYMAXX.Company</a></div></td></tr></table></td></tr><tr><td style="padding:32px 36px;font-family:Arial,Helvetica,sans-serif;color:#1f2937;font-size:15px;line-height:1.6"><p style="margin:0 0 16px">Hi {{name}},</p><p style="margin:0 0 16px">Quick note from <strong>SKYMAXX Technologies</strong>. I will keep this brief.</p><p style="margin:0 0 14px;font-size:14px;color:#475569">More details: <a href="https://www.SKYMAXX.Company" style="color:#2563eb;text-decoration:underline;font-weight:600">www.SKYMAXX.Company</a>.</p><p style="margin:0 0 16px">The reason we focus on email is straightforward: it is where most security incidents start, where licensing costs quietly accumulate, and where small improvements compound into measurable productivity gains over time.</p><p style="margin:0 0 12px">For organizations using Office 365 Email Services today, there are usually opportunities to:</p><ul style="margin:0 0 16px;padding-left:22px"><li style="margin-bottom:6px">Reduce monthly costs by identifying unused or oversized licenses</li><li style="margin-bottom:6px">Tighten security without adding friction for users</li><li style="margin-bottom:6px">Automate repetitive tasks such as responses, sorting, and routing</li><li style="margin-bottom:0">Improve collaboration through better-configured Teams and shared resources</li></ul><p style="margin:0 0 14px;font-size:14px;color:#475569">A more detailed breakdown of how we approach each is on <a href="https://www.SKYMAXX.Company" style="color:#2563eb;text-decoration:underline;font-weight:600">www.SKYMAXX.Company</a>.</p><div style="background:#f0f9ff;border-left:4px solid #0284c7;padding:16px 20px;margin:18px 0;border-radius:4px"><p style="margin:0 0 6px;font-weight:700;color:#075985">Already using Office 365 Email Services?</p><p style="margin:0;color:#0c4a6e;font-size:14px;line-height:1.55">We can conduct a one-day assessment of your email environment to identify opportunities for improvement &mdash; including enhancing email security, reducing unnecessary licensing and billing costs, optimizing configurations, implementing additional automation, and improving overall productivity. Details at <a href="https://www.SKYMAXX.Company" style="color:#2563eb;text-decoration:underline;font-weight:600">www.SKYMAXX.Company</a>.</p></div><p style="margin:0 0 16px">If {{company}} is considering Office 365 for the first time or evaluating alternatives, we can also help you think through the right fit.</p><p style="margin:0 0 16px">Either way, a short call would tell us if there is a fit. Visit <a href="https://www.SKYMAXX.Company" style="color:#2563eb;text-decoration:underline;font-weight:600">www.SKYMAXX.Company</a> or simply reply to this email.</p><p style="margin:0 0 4px">Best regards,</p><p style="margin:0;font-weight:600">SKYMAXX Support Team</p><p style="margin:0;color:#64748b;font-size:13px">SKYMAXX Technologies &middot; <a href="https://www.SKYMAXX.Company" style="color:#2563eb;text-decoration:underline;font-weight:600">www.SKYMAXX.Company</a></p></td></tr><tr><td style="background:#0f172a;padding:18px 36px;color:#94a3b8;font-size:11px;line-height:1.5;font-family:Arial,Helvetica,sans-serif"><p style="margin:0"><strong style="color:#cbd5e1">SKYMAXX Technologies</strong> &middot; <a href="https://www.SKYMAXX.Company" style="color:#60a5fa;text-decoration:none;font-weight:600">www.SKYMAXX.Company</a> &middot; Microsoft 365 Management for SMBs &middot; UAE</p><p style="margin:6px 0 0"><a href="mailto:support@skymaxx.company" style="color:#60a5fa;text-decoration:none">support@skymaxx.company</a> &middot; Visit us at <a href="https://www.SKYMAXX.Company" style="color:#60a5fa;text-decoration:none">www.SKYMAXX.Company</a></p><p style="margin:6px 0 0">If you prefer not to receive these messages, just reply with "unsubscribe" and we will remove you immediately.</p></td></tr></table></td></tr></table></body></html>',
        },
        {
            'step':       5,
            'delay_days': 7,
            'name':       'Closing',
            'subject':    'Closing the loop - and 4 free resources for {{company}}',
            'body':       '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd"><html xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office"><head><meta http-equiv="Content-Type" content="text/html; charset=UTF-8" /><meta http-equiv="X-UA-Compatible" content="IE=edge" /><meta name="viewport" content="width=device-width, initial-scale=1.0" /><meta name="format-detection" content="telephone=no, date=no, address=no, email=no" /><title>SKYMAXX Technologies</title><!--[if mso]><xml><o:OfficeDocumentSettings><o:AllowPNG/><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml><![endif]--><style type="text/css">body{margin:0!important;padding:0!important;width:100%!important;-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;mso-line-height-rule:exactly}table{border-collapse:collapse!important;mso-table-lspace:0pt;mso-table-rspace:0pt}img{-ms-interpolation-mode:bicubic;border:0;outline:none;text-decoration:none;display:block}a{text-decoration:none}</style></head><body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,Helvetica,sans-serif;-webkit-font-smoothing:antialiased;mso-line-height-rule:exactly"><div style="display:none;max-height:0;overflow:hidden;mso-hide:all">Final note plus useful resources you can keep regardless</div><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f3f4f6"><tr><td align="center" style="padding:24px 12px"><table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="background:#ffffff;border-radius:12px;overflow:hidden;max-width:600px"><tr><td bgcolor="#0f172a" style="background-color:#0f172a;padding:20px 32px;mso-line-height-rule:exactly;line-height:1.2"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse"><tr><td valign="middle" width="76" style="padding-right:14px;width:76px"><a href="https://www.SKYMAXX.Company" style="text-decoration:none"><img src="https://skymaxx-lead-engine.onrender.com/static/logo_email.png" alt="SKYMAXX.Company" width="60" height="60" style="display:block;width:60px;height:60px;max-width:60px;border-radius:50%;border:0;outline:none;text-decoration:none;-ms-interpolation-mode:bicubic" /></a></td><td valign="middle" style="color:#ffffff;font-size:22px;font-weight:700;letter-spacing:0.5px;font-family:Arial,Helvetica,sans-serif;mso-line-height-rule:exactly;line-height:1.2"><a href="https://www.SKYMAXX.Company" style="color:#ffffff;text-decoration:none">SKYMAXX TECHNOLOGIES</a><div style="color:#cbd5e1;font-size:12px;font-weight:500;margin-top:2px;font-family:Arial,Helvetica,sans-serif">Microsoft 365 Specialists</div><div style="margin-top:4px"><a href="https://www.SKYMAXX.Company" style="color:#60a5fa;font-size:12px;text-decoration:none;font-weight:600;font-family:Arial,Helvetica,sans-serif">www.SKYMAXX.Company</a></div></td></tr></table></td></tr><tr><td style="padding:32px 36px;font-family:Arial,Helvetica,sans-serif;color:#1f2937;font-size:15px;line-height:1.6"><p style="margin:0 0 16px">Hi {{name}},</p><p style="margin:0 0 16px">This will be my last note for now from <strong>SKYMAXX Technologies</strong> &mdash; I do not want to crowd your inbox.</p><p style="margin:0 0 14px;font-size:14px;color:#475569">Our service overview: <a href="https://www.SKYMAXX.Company" style="color:#2563eb;text-decoration:underline;font-weight:600">www.SKYMAXX.Company</a>.</p><p style="margin:0 0 12px">To leave you with something useful, here are four resources worth bookmarking regardless of whether we ever speak:</p><ol style="margin:0 0 16px;padding-left:22px"><li style="margin-bottom:6px"><strong>Microsoft Secure Score</strong> &mdash; free dashboard showing tenant security posture for Office 365 users: <a href="https://security.microsoft.com" style="color:#2563eb">security.microsoft.com</a></li><li style="margin-bottom:6px"><strong>Microsoft 365 Admin Center licensing report</strong> &mdash; shows assigned vs active users if you have an Office 365 tenant</li><li style="margin-bottom:6px"><strong>Have I Been Pwned</strong> &mdash; check if any of your domain addresses are in known breaches: <a href="https://haveibeenpwned.com" style="color:#2563eb">haveibeenpwned.com</a></li><li style="margin-bottom:0"><strong>CISA cybersecurity guides for SMBs</strong> &mdash; practical, vendor-neutral guidance: <a href="https://cisa.gov/cybersecurity" style="color:#2563eb">cisa.gov/cybersecurity</a></li></ol><p style="margin:0 0 16px">Additional guides and our service overview live on <a href="https://www.SKYMAXX.Company" style="color:#2563eb;text-decoration:underline;font-weight:600">www.SKYMAXX.Company</a>, where you can also book a discovery call when ready.</p><p style="margin:0 0 16px">If circumstances change and you would like to discuss Office 365 Email Services for {{company}}, or have us conduct a one-day assessment, just reply to this email or reach out via <a href="https://www.SKYMAXX.Company" style="color:#2563eb;text-decoration:underline;font-weight:600">www.SKYMAXX.Company</a>.</p><p style="margin:0 0 4px">Best regards,</p><p style="margin:0;font-weight:600">SKYMAXX Support Team</p><p style="margin:0;color:#64748b;font-size:13px">SKYMAXX Technologies &middot; <a href="https://www.SKYMAXX.Company" style="color:#2563eb;text-decoration:underline;font-weight:600">www.SKYMAXX.Company</a> &middot; support@skymaxx.company</p></td></tr><tr><td style="background:#0f172a;padding:18px 36px;color:#94a3b8;font-size:11px;line-height:1.5;font-family:Arial,Helvetica,sans-serif"><p style="margin:0"><strong style="color:#cbd5e1">SKYMAXX Technologies</strong> &middot; <a href="https://www.SKYMAXX.Company" style="color:#60a5fa;text-decoration:none;font-weight:600">www.SKYMAXX.Company</a> &middot; Microsoft 365 Management for SMBs &middot; UAE</p><p style="margin:6px 0 0"><a href="mailto:support@skymaxx.company" style="color:#60a5fa;text-decoration:none">support@skymaxx.company</a> &middot; Visit us at <a href="https://www.SKYMAXX.Company" style="color:#60a5fa;text-decoration:none">www.SKYMAXX.Company</a></p><p style="margin:6px 0 0">If you prefer not to receive these messages, just reply with "unsubscribe" and we will remove you immediately.</p></td></tr></table></td></tr></table></body></html>',
        },
    ],
    'toolsshopy': [
        {
            'step':       1,
            'delay_days': 0,
            'name':       'Initial Outreach',
            'subject':    'Welcome to ToolsShopy.Store',
            'body':       '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd"><html xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office"><head><meta http-equiv="Content-Type" content="text/html; charset=UTF-8" /><meta http-equiv="X-UA-Compatible" content="IE=edge" /><meta name="viewport" content="width=device-width, initial-scale=1.0" /><meta name="format-detection" content="telephone=no, date=no, address=no, email=no" /><title>ToolsShopy</title><!--[if mso]><xml><o:OfficeDocumentSettings><o:AllowPNG/><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml><![endif]--><style type="text/css">body{margin:0!important;padding:0!important;width:100%!important;-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;mso-line-height-rule:exactly}table{border-collapse:collapse!important;mso-table-lspace:0pt;mso-table-rspace:0pt}img{-ms-interpolation-mode:bicubic;border:0;outline:none;text-decoration:none;display:block}a{text-decoration:none}</style></head><body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,Helvetica,sans-serif;-webkit-font-smoothing:antialiased;mso-line-height-rule:exactly"><div style="display:none;max-height:0;overflow:hidden;mso-hide:all">Curated tools at fair prices with honest descriptions</div><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f3f4f6"><tr><td align="center" style="padding:24px 12px"><table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="background:#ffffff;border-radius:12px;overflow:hidden;max-width:600px"><tr><td bgcolor="#1e293b" style="background-color:#1e293b;padding:20px 32px;mso-line-height-rule:exactly;line-height:1.2"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse"><tr><td valign="middle" width="76" style="padding-right:14px;width:76px"><a href="https://www.ToolsShopy.Store" style="text-decoration:none"><img src="https://skymaxx-lead-engine.onrender.com/static/logo_email.png" alt="ToolsShopy.Store" width="60" height="60" style="display:block;width:60px;height:60px;max-width:60px;border-radius:50%;border:0;outline:none;text-decoration:none;-ms-interpolation-mode:bicubic" /></a></td><td valign="middle" style="color:#ffffff;font-size:22px;font-weight:700;letter-spacing:0.5px;font-family:Arial,Helvetica,sans-serif;mso-line-height-rule:exactly;line-height:1.2"><a href="https://www.ToolsShopy.Store" style="color:#ffffff;text-decoration:none">TOOLSSHOPY</a><div style="color:#cbd5e1;font-size:12px;font-weight:500;margin-top:2px;font-family:Arial,Helvetica,sans-serif">Tools that work as hard as you do</div><div style="margin-top:4px"><a href="https://www.ToolsShopy.Store" style="color:#f97316;font-size:12px;text-decoration:none;font-weight:600;font-family:Arial,Helvetica,sans-serif">www.ToolsShopy.Store</a></div></td></tr></table></td></tr><tr><td style="padding:32px 36px;font-family:Arial,Helvetica,sans-serif;color:#1f2937;font-size:15px;line-height:1.6"><p style="margin:0 0 16px">Hi {{name}},</p><p style="margin:0 0 16px">Welcome to <strong>ToolsShopy.Store</strong>! We are glad to have you with us.</p><p style="margin:0 0 14px;font-size:14px;color:#475569">Browse our full selection at <a href="https://www.ToolsShopy.Store" style="color:#2563eb;text-decoration:underline;font-weight:600">www.ToolsShopy.Store</a>.</p><p style="margin:0 0 16px">Our focus is straightforward: curated tools and hardware at fair prices, with real warranties and honest descriptions. No filler products.</p><p style="margin:0 0 12px">A quick look at what we offer:</p><ul style="margin:0 0 16px;padding-left:22px"><li style="margin-bottom:6px"><strong>Power Tools</strong> &mdash; drills, drivers, saws, sanders</li><li style="margin-bottom:6px"><strong>Hand Tools</strong> &mdash; wrenches, pliers, screwdrivers, measuring</li><li style="margin-bottom:6px"><strong>Workshop &amp; Storage</strong> &mdash; toolboxes, workbenches, organization</li><li style="margin-bottom:0"><strong>Outdoor &amp; Garden</strong> &mdash; cutting tools, garden hardware</li></ul><p style="margin:0 0 14px;font-size:14px;color:#475569">All categories are organized at <a href="https://www.ToolsShopy.Store" style="color:#2563eb;text-decoration:underline;font-weight:600">www.ToolsShopy.Store</a> for easy browsing.</p><table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:18px 0"><tr><td bgcolor="#f97316" style="background-color:#f97316;border-radius:6px"><a href="https://www.ToolsShopy.Store" style="display:inline-block;padding:12px 28px;color:#ffffff;font-weight:700;font-size:15px;text-decoration:none">Visit www.ToolsShopy.Store &rarr;</a></td></tr></table><p style="margin:0 0 16px">Have a question or want a recommendation? Reply to this email or visit <a href="https://www.ToolsShopy.Store" style="color:#2563eb;text-decoration:underline;font-weight:600">www.ToolsShopy.Store</a> anytime &mdash; we read every message.</p><p style="margin:0 0 4px">Thanks for stopping by,</p><p style="margin:0;font-weight:600">ToolsShopy Team</p><p style="margin:0;color:#64748b;font-size:13px">ToolsShopy.Store &middot; <a href="https://www.ToolsShopy.Store" style="color:#2563eb;text-decoration:underline;font-weight:600">www.ToolsShopy.Store</a></p></td></tr><tr><td style="background:#1e293b;padding:18px 36px;color:#94a3b8;font-size:11px;line-height:1.5;font-family:Arial,Helvetica,sans-serif"><p style="margin:0"><strong style="color:#cbd5e1">ToolsShopy</strong> &middot; <a href="https://www.ToolsShopy.Store" style="color:#f97316;text-decoration:none;font-weight:600">www.ToolsShopy.Store</a> &middot; Curated tools and hardware &middot; USA</p><p style="margin:6px 0 0"><a href="mailto:support@toolsshopy.store" style="color:#f97316;text-decoration:none">support@toolsshopy.store</a> &middot; Visit us at <a href="https://www.ToolsShopy.Store" style="color:#f97316;text-decoration:none">www.ToolsShopy.Store</a></p><p style="margin:6px 0 0">If you prefer not to receive these messages, just reply with "unsubscribe" and we will remove you immediately.</p></td></tr></table></td></tr></table></body></html>',
        },
        {
            'step':       2,
            'delay_days': 3,
            'name':       'Follow-up',
            'subject':    'Tools our customers reach for most',
            'body':       '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd"><html xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office"><head><meta http-equiv="Content-Type" content="text/html; charset=UTF-8" /><meta http-equiv="X-UA-Compatible" content="IE=edge" /><meta name="viewport" content="width=device-width, initial-scale=1.0" /><meta name="format-detection" content="telephone=no, date=no, address=no, email=no" /><title>ToolsShopy</title><!--[if mso]><xml><o:OfficeDocumentSettings><o:AllowPNG/><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml><![endif]--><style type="text/css">body{margin:0!important;padding:0!important;width:100%!important;-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;mso-line-height-rule:exactly}table{border-collapse:collapse!important;mso-table-lspace:0pt;mso-table-rspace:0pt}img{-ms-interpolation-mode:bicubic;border:0;outline:none;text-decoration:none;display:block}a{text-decoration:none}</style></head><body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,Helvetica,sans-serif;-webkit-font-smoothing:antialiased;mso-line-height-rule:exactly"><div style="display:none;max-height:0;overflow:hidden;mso-hide:all">A few categories our customers come back to most</div><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f3f4f6"><tr><td align="center" style="padding:24px 12px"><table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="background:#ffffff;border-radius:12px;overflow:hidden;max-width:600px"><tr><td bgcolor="#1e293b" style="background-color:#1e293b;padding:20px 32px;mso-line-height-rule:exactly;line-height:1.2"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse"><tr><td valign="middle" width="76" style="padding-right:14px;width:76px"><a href="https://www.ToolsShopy.Store" style="text-decoration:none"><img src="https://skymaxx-lead-engine.onrender.com/static/logo_email.png" alt="ToolsShopy.Store" width="60" height="60" style="display:block;width:60px;height:60px;max-width:60px;border-radius:50%;border:0;outline:none;text-decoration:none;-ms-interpolation-mode:bicubic" /></a></td><td valign="middle" style="color:#ffffff;font-size:22px;font-weight:700;letter-spacing:0.5px;font-family:Arial,Helvetica,sans-serif;mso-line-height-rule:exactly;line-height:1.2"><a href="https://www.ToolsShopy.Store" style="color:#ffffff;text-decoration:none">TOOLSSHOPY</a><div style="color:#cbd5e1;font-size:12px;font-weight:500;margin-top:2px;font-family:Arial,Helvetica,sans-serif">Tools that work as hard as you do</div><div style="margin-top:4px"><a href="https://www.ToolsShopy.Store" style="color:#f97316;font-size:12px;text-decoration:none;font-weight:600;font-family:Arial,Helvetica,sans-serif">www.ToolsShopy.Store</a></div></td></tr></table></td></tr><tr><td style="padding:32px 36px;font-family:Arial,Helvetica,sans-serif;color:#1f2937;font-size:15px;line-height:1.6"><p style="margin:0 0 16px">Hi {{name}},</p><p style="margin:0 0 16px">Quick follow-up from <strong>ToolsShopy.Store</strong>.</p><p style="margin:0 0 14px;font-size:14px;color:#475569">Latest at <a href="https://www.ToolsShopy.Store" style="color:#2563eb;text-decoration:underline;font-weight:600">www.ToolsShopy.Store</a>.</p><p style="margin:0 0 16px">A few categories that customers come back to most often:</p><ul style="margin:0 0 16px;padding-left:22px"><li style="margin-bottom:6px"><strong>Cordless drill kits</strong> &mdash; reliable everyday workhorses</li><li style="margin-bottom:6px"><strong>Multi-tool sets</strong> &mdash; covers most general household work</li><li style="margin-bottom:6px"><strong>Storage solutions</strong> &mdash; rolling toolboxes, magnetic strips</li><li style="margin-bottom:0"><strong>Measuring tools</strong> &mdash; digital calipers, laser distance meters</li></ul><p style="margin:0 0 14px;font-size:14px;color:#475569">All of these and more at <a href="https://www.ToolsShopy.Store" style="color:#2563eb;text-decoration:underline;font-weight:600">www.ToolsShopy.Store</a>.</p><table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:18px 0"><tr><td bgcolor="#f97316" style="background-color:#f97316;border-radius:6px"><a href="https://www.ToolsShopy.Store" style="display:inline-block;padding:12px 28px;color:#ffffff;font-weight:700;font-size:15px;text-decoration:none">Visit www.ToolsShopy.Store &rarr;</a></td></tr></table><p style="margin:0 0 16px">If you spot something useful or want a recommendation, just reply &mdash; or browse the full lineup at <a href="https://www.ToolsShopy.Store" style="color:#2563eb;text-decoration:underline;font-weight:600">www.ToolsShopy.Store</a>.</p><p style="margin:0 0 4px">Cheers,</p><p style="margin:0;font-weight:600">ToolsShopy Team</p><p style="margin:0;color:#64748b;font-size:13px">ToolsShopy.Store &middot; <a href="https://www.ToolsShopy.Store" style="color:#2563eb;text-decoration:underline;font-weight:600">www.ToolsShopy.Store</a></p></td></tr><tr><td style="background:#1e293b;padding:18px 36px;color:#94a3b8;font-size:11px;line-height:1.5;font-family:Arial,Helvetica,sans-serif"><p style="margin:0"><strong style="color:#cbd5e1">ToolsShopy</strong> &middot; <a href="https://www.ToolsShopy.Store" style="color:#f97316;text-decoration:none;font-weight:600">www.ToolsShopy.Store</a> &middot; Curated tools and hardware &middot; USA</p><p style="margin:6px 0 0"><a href="mailto:support@toolsshopy.store" style="color:#f97316;text-decoration:none">support@toolsshopy.store</a> &middot; Visit us at <a href="https://www.ToolsShopy.Store" style="color:#f97316;text-decoration:none">www.ToolsShopy.Store</a></p><p style="margin:6px 0 0">If you prefer not to receive these messages, just reply with "unsubscribe" and we will remove you immediately.</p></td></tr></table></td></tr></table></body></html>',
        },
        {
            'step':       3,
            'delay_days': 4,
            'name':       'Educational',
            'subject':    'How we curate what we sell',
            'body':       '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd"><html xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office"><head><meta http-equiv="Content-Type" content="text/html; charset=UTF-8" /><meta http-equiv="X-UA-Compatible" content="IE=edge" /><meta name="viewport" content="width=device-width, initial-scale=1.0" /><meta name="format-detection" content="telephone=no, date=no, address=no, email=no" /><title>ToolsShopy</title><!--[if mso]><xml><o:OfficeDocumentSettings><o:AllowPNG/><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml><![endif]--><style type="text/css">body{margin:0!important;padding:0!important;width:100%!important;-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;mso-line-height-rule:exactly}table{border-collapse:collapse!important;mso-table-lspace:0pt;mso-table-rspace:0pt}img{-ms-interpolation-mode:bicubic;border:0;outline:none;text-decoration:none;display:block}a{text-decoration:none}</style></head><body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,Helvetica,sans-serif;-webkit-font-smoothing:antialiased;mso-line-height-rule:exactly"><div style="display:none;max-height:0;overflow:hidden;mso-hide:all">How we decide what makes it to the store</div><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f3f4f6"><tr><td align="center" style="padding:24px 12px"><table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="background:#ffffff;border-radius:12px;overflow:hidden;max-width:600px"><tr><td bgcolor="#1e293b" style="background-color:#1e293b;padding:20px 32px;mso-line-height-rule:exactly;line-height:1.2"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse"><tr><td valign="middle" width="76" style="padding-right:14px;width:76px"><a href="https://www.ToolsShopy.Store" style="text-decoration:none"><img src="https://skymaxx-lead-engine.onrender.com/static/logo_email.png" alt="ToolsShopy.Store" width="60" height="60" style="display:block;width:60px;height:60px;max-width:60px;border-radius:50%;border:0;outline:none;text-decoration:none;-ms-interpolation-mode:bicubic" /></a></td><td valign="middle" style="color:#ffffff;font-size:22px;font-weight:700;letter-spacing:0.5px;font-family:Arial,Helvetica,sans-serif;mso-line-height-rule:exactly;line-height:1.2"><a href="https://www.ToolsShopy.Store" style="color:#ffffff;text-decoration:none">TOOLSSHOPY</a><div style="color:#cbd5e1;font-size:12px;font-weight:500;margin-top:2px;font-family:Arial,Helvetica,sans-serif">Tools that work as hard as you do</div><div style="margin-top:4px"><a href="https://www.ToolsShopy.Store" style="color:#f97316;font-size:12px;text-decoration:none;font-weight:600;font-family:Arial,Helvetica,sans-serif">www.ToolsShopy.Store</a></div></td></tr></table></td></tr><tr><td style="padding:32px 36px;font-family:Arial,Helvetica,sans-serif;color:#1f2937;font-size:15px;line-height:1.6"><p style="margin:0 0 16px">Hi {{name}},</p><p style="margin:0 0 16px">A quick note from <strong>ToolsShopy.Store</strong> on how we curate what we feature.</p><p style="margin:0 0 14px;font-size:14px;color:#475569">See our current selection: <a href="https://www.ToolsShopy.Store" style="color:#2563eb;text-decoration:underline;font-weight:600">www.ToolsShopy.Store</a>.</p><p style="margin:0 0 12px">We do not list everything just to fill a catalog. A product makes it to our store only if:</p><ul style="margin:0 0 16px;padding-left:22px"><li style="margin-bottom:6px">It comes from a brand with a real warranty</li><li style="margin-bottom:6px">Reviews and ratings hold up over time, not just at launch</li><li style="margin-bottom:6px">Specs match what is actually delivered</li><li style="margin-bottom:0">Price is fair against the broader market</li></ul><p style="margin:0 0 14px;font-size:14px;color:#475569">Read more about our approach at <a href="https://www.ToolsShopy.Store" style="color:#2563eb;text-decoration:underline;font-weight:600">www.ToolsShopy.Store</a>.</p><table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:18px 0"><tr><td bgcolor="#f97316" style="background-color:#f97316;border-radius:6px"><a href="https://www.ToolsShopy.Store" style="display:inline-block;padding:12px 28px;color:#ffffff;font-weight:700;font-size:15px;text-decoration:none">Visit www.ToolsShopy.Store &rarr;</a></td></tr></table><p style="margin:0 0 16px">Questions about a specific category? Reply or browse <a href="https://www.ToolsShopy.Store" style="color:#2563eb;text-decoration:underline;font-weight:600">www.ToolsShopy.Store</a> &mdash; happy to help either way.</p><p style="margin:0 0 4px">Best,</p><p style="margin:0;font-weight:600">ToolsShopy Team</p><p style="margin:0;color:#64748b;font-size:13px">ToolsShopy.Store &middot; <a href="https://www.ToolsShopy.Store" style="color:#2563eb;text-decoration:underline;font-weight:600">www.ToolsShopy.Store</a></p></td></tr><tr><td style="background:#1e293b;padding:18px 36px;color:#94a3b8;font-size:11px;line-height:1.5;font-family:Arial,Helvetica,sans-serif"><p style="margin:0"><strong style="color:#cbd5e1">ToolsShopy</strong> &middot; <a href="https://www.ToolsShopy.Store" style="color:#f97316;text-decoration:none;font-weight:600">www.ToolsShopy.Store</a> &middot; Curated tools and hardware &middot; USA</p><p style="margin:6px 0 0"><a href="mailto:support@toolsshopy.store" style="color:#f97316;text-decoration:none">support@toolsshopy.store</a> &middot; Visit us at <a href="https://www.ToolsShopy.Store" style="color:#f97316;text-decoration:none">www.ToolsShopy.Store</a></p><p style="margin:6px 0 0">If you prefer not to receive these messages, just reply with "unsubscribe" and we will remove you immediately.</p></td></tr></table></td></tr></table></body></html>',
        },
        {
            'step':       4,
            'delay_days': 7,
            'name':       'Value / Curation',
            'subject':    'New arrivals and continuing favorites',
            'body':       '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd"><html xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office"><head><meta http-equiv="Content-Type" content="text/html; charset=UTF-8" /><meta http-equiv="X-UA-Compatible" content="IE=edge" /><meta name="viewport" content="width=device-width, initial-scale=1.0" /><meta name="format-detection" content="telephone=no, date=no, address=no, email=no" /><title>ToolsShopy</title><!--[if mso]><xml><o:OfficeDocumentSettings><o:AllowPNG/><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml><![endif]--><style type="text/css">body{margin:0!important;padding:0!important;width:100%!important;-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;mso-line-height-rule:exactly}table{border-collapse:collapse!important;mso-table-lspace:0pt;mso-table-rspace:0pt}img{-ms-interpolation-mode:bicubic;border:0;outline:none;text-decoration:none;display:block}a{text-decoration:none}</style></head><body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,Helvetica,sans-serif;-webkit-font-smoothing:antialiased;mso-line-height-rule:exactly"><div style="display:none;max-height:0;overflow:hidden;mso-hide:all">A short list of what is new and what continues to ship well</div><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f3f4f6"><tr><td align="center" style="padding:24px 12px"><table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="background:#ffffff;border-radius:12px;overflow:hidden;max-width:600px"><tr><td bgcolor="#1e293b" style="background-color:#1e293b;padding:20px 32px;mso-line-height-rule:exactly;line-height:1.2"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse"><tr><td valign="middle" width="76" style="padding-right:14px;width:76px"><a href="https://www.ToolsShopy.Store" style="text-decoration:none"><img src="https://skymaxx-lead-engine.onrender.com/static/logo_email.png" alt="ToolsShopy.Store" width="60" height="60" style="display:block;width:60px;height:60px;max-width:60px;border-radius:50%;border:0;outline:none;text-decoration:none;-ms-interpolation-mode:bicubic" /></a></td><td valign="middle" style="color:#ffffff;font-size:22px;font-weight:700;letter-spacing:0.5px;font-family:Arial,Helvetica,sans-serif;mso-line-height-rule:exactly;line-height:1.2"><a href="https://www.ToolsShopy.Store" style="color:#ffffff;text-decoration:none">TOOLSSHOPY</a><div style="color:#cbd5e1;font-size:12px;font-weight:500;margin-top:2px;font-family:Arial,Helvetica,sans-serif">Tools that work as hard as you do</div><div style="margin-top:4px"><a href="https://www.ToolsShopy.Store" style="color:#f97316;font-size:12px;text-decoration:none;font-weight:600;font-family:Arial,Helvetica,sans-serif">www.ToolsShopy.Store</a></div></td></tr></table></td></tr><tr><td style="padding:32px 36px;font-family:Arial,Helvetica,sans-serif;color:#1f2937;font-size:15px;line-height:1.6"><p style="margin:0 0 16px">Hi {{name}},</p><p style="margin:0 0 16px">Hello again from <strong>ToolsShopy.Store</strong>.</p><p style="margin:0 0 14px;font-size:14px;color:#475569">What is fresh: <a href="https://www.ToolsShopy.Store" style="color:#2563eb;text-decoration:underline;font-weight:600">www.ToolsShopy.Store</a>.</p><p style="margin:0 0 16px">A short list of what is new and what continues to ship well:</p><ul style="margin:0 0 16px;padding-left:22px"><li style="margin-bottom:6px">New <strong>cordless lineups</strong> with improved battery runtime</li><li style="margin-bottom:6px">Updated <strong>workshop organizers</strong> for small garages</li><li style="margin-bottom:6px">Seasonal <strong>outdoor hardware</strong> additions</li><li style="margin-bottom:0">Restocked <strong>customer-favorite</strong> hand tool sets</li></ul><p style="margin:0 0 14px;font-size:14px;color:#475569">Browse new arrivals at <a href="https://www.ToolsShopy.Store" style="color:#2563eb;text-decoration:underline;font-weight:600">www.ToolsShopy.Store</a>.</p><table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:18px 0"><tr><td bgcolor="#f97316" style="background-color:#f97316;border-radius:6px"><a href="https://www.ToolsShopy.Store" style="display:inline-block;padding:12px 28px;color:#ffffff;font-weight:700;font-size:15px;text-decoration:none">Visit www.ToolsShopy.Store &rarr;</a></td></tr></table><p style="margin:0 0 16px">If you would like a suggestion based on what you are looking for, just reply with a few words &mdash; or explore <a href="https://www.ToolsShopy.Store" style="color:#2563eb;text-decoration:underline;font-weight:600">www.ToolsShopy.Store</a> at your own pace.</p><p style="margin:0 0 4px">Cheers,</p><p style="margin:0;font-weight:600">ToolsShopy Team</p><p style="margin:0;color:#64748b;font-size:13px">ToolsShopy.Store &middot; <a href="https://www.ToolsShopy.Store" style="color:#2563eb;text-decoration:underline;font-weight:600">www.ToolsShopy.Store</a></p></td></tr><tr><td style="background:#1e293b;padding:18px 36px;color:#94a3b8;font-size:11px;line-height:1.5;font-family:Arial,Helvetica,sans-serif"><p style="margin:0"><strong style="color:#cbd5e1">ToolsShopy</strong> &middot; <a href="https://www.ToolsShopy.Store" style="color:#f97316;text-decoration:none;font-weight:600">www.ToolsShopy.Store</a> &middot; Curated tools and hardware &middot; USA</p><p style="margin:6px 0 0"><a href="mailto:support@toolsshopy.store" style="color:#f97316;text-decoration:none">support@toolsshopy.store</a> &middot; Visit us at <a href="https://www.ToolsShopy.Store" style="color:#f97316;text-decoration:none">www.ToolsShopy.Store</a></p><p style="margin:6px 0 0">If you prefer not to receive these messages, just reply with "unsubscribe" and we will remove you immediately.</p></td></tr></table></td></tr></table></body></html>',
        },
        {
            'step':       5,
            'delay_days': 7,
            'name':       'Closing',
            'subject':    'A few favorites worth bookmarking',
            'body':       '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd"><html xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office"><head><meta http-equiv="Content-Type" content="text/html; charset=UTF-8" /><meta http-equiv="X-UA-Compatible" content="IE=edge" /><meta name="viewport" content="width=device-width, initial-scale=1.0" /><meta name="format-detection" content="telephone=no, date=no, address=no, email=no" /><title>ToolsShopy</title><!--[if mso]><xml><o:OfficeDocumentSettings><o:AllowPNG/><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml><![endif]--><style type="text/css">body{margin:0!important;padding:0!important;width:100%!important;-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;mso-line-height-rule:exactly}table{border-collapse:collapse!important;mso-table-lspace:0pt;mso-table-rspace:0pt}img{-ms-interpolation-mode:bicubic;border:0;outline:none;text-decoration:none;display:block}a{text-decoration:none}</style></head><body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,Helvetica,sans-serif;-webkit-font-smoothing:antialiased;mso-line-height-rule:exactly"><div style="display:none;max-height:0;overflow:hidden;mso-hide:all">Three categories worth bookmarking before signing off</div><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f3f4f6"><tr><td align="center" style="padding:24px 12px"><table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="background:#ffffff;border-radius:12px;overflow:hidden;max-width:600px"><tr><td bgcolor="#1e293b" style="background-color:#1e293b;padding:20px 32px;mso-line-height-rule:exactly;line-height:1.2"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse"><tr><td valign="middle" width="76" style="padding-right:14px;width:76px"><a href="https://www.ToolsShopy.Store" style="text-decoration:none"><img src="https://skymaxx-lead-engine.onrender.com/static/logo_email.png" alt="ToolsShopy.Store" width="60" height="60" style="display:block;width:60px;height:60px;max-width:60px;border-radius:50%;border:0;outline:none;text-decoration:none;-ms-interpolation-mode:bicubic" /></a></td><td valign="middle" style="color:#ffffff;font-size:22px;font-weight:700;letter-spacing:0.5px;font-family:Arial,Helvetica,sans-serif;mso-line-height-rule:exactly;line-height:1.2"><a href="https://www.ToolsShopy.Store" style="color:#ffffff;text-decoration:none">TOOLSSHOPY</a><div style="color:#cbd5e1;font-size:12px;font-weight:500;margin-top:2px;font-family:Arial,Helvetica,sans-serif">Tools that work as hard as you do</div><div style="margin-top:4px"><a href="https://www.ToolsShopy.Store" style="color:#f97316;font-size:12px;text-decoration:none;font-weight:600;font-family:Arial,Helvetica,sans-serif">www.ToolsShopy.Store</a></div></td></tr></table></td></tr><tr><td style="padding:32px 36px;font-family:Arial,Helvetica,sans-serif;color:#1f2937;font-size:15px;line-height:1.6"><p style="margin:0 0 16px">Hi {{name}},</p><p style="margin:0 0 16px">This is my last note for now from <strong>ToolsShopy.Store</strong> &mdash; I do not want to crowd your inbox.</p><p style="margin:0 0 14px;font-size:14px;color:#475569">Full store: <a href="https://www.ToolsShopy.Store" style="color:#2563eb;text-decoration:underline;font-weight:600">www.ToolsShopy.Store</a>.</p><p style="margin:0 0 16px">Before signing off, three categories worth bookmarking:</p><ul style="margin:0 0 16px;padding-left:22px"><li style="margin-bottom:6px"><strong>Essential starter kits</strong> &mdash; the basics anyone needs</li><li style="margin-bottom:6px"><strong>Best-value picks</strong> &mdash; quality without overspending</li><li style="margin-bottom:0"><strong>Workshop upgrades</strong> &mdash; for when you are ready for the next step</li></ul><p style="margin:0 0 14px;font-size:14px;color:#475569">All available at <a href="https://www.ToolsShopy.Store" style="color:#2563eb;text-decoration:underline;font-weight:600">www.ToolsShopy.Store</a>.</p><table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:18px 0"><tr><td bgcolor="#f97316" style="background-color:#f97316;border-radius:6px"><a href="https://www.ToolsShopy.Store" style="display:inline-block;padding:12px 28px;color:#ffffff;font-weight:700;font-size:15px;text-decoration:none">Visit www.ToolsShopy.Store &rarr;</a></td></tr></table><p style="margin:0 0 16px">Whenever you are ready to browse, reach out, or share feedback, you will find us at <a href="https://www.ToolsShopy.Store" style="color:#2563eb;text-decoration:underline;font-weight:600">www.ToolsShopy.Store</a>. Thanks for being on the list.</p><p style="margin:0 0 4px">All the best,</p><p style="margin:0;font-weight:600">ToolsShopy Team</p><p style="margin:0;color:#64748b;font-size:13px">ToolsShopy.Store &middot; <a href="https://www.ToolsShopy.Store" style="color:#2563eb;text-decoration:underline;font-weight:600">www.ToolsShopy.Store</a> &middot; support@toolsshopy.store</p></td></tr><tr><td style="background:#1e293b;padding:18px 36px;color:#94a3b8;font-size:11px;line-height:1.5;font-family:Arial,Helvetica,sans-serif"><p style="margin:0"><strong style="color:#cbd5e1">ToolsShopy</strong> &middot; <a href="https://www.ToolsShopy.Store" style="color:#f97316;text-decoration:none;font-weight:600">www.ToolsShopy.Store</a> &middot; Curated tools and hardware &middot; USA</p><p style="margin:6px 0 0"><a href="mailto:support@toolsshopy.store" style="color:#f97316;text-decoration:none">support@toolsshopy.store</a> &middot; Visit us at <a href="https://www.ToolsShopy.Store" style="color:#f97316;text-decoration:none">www.ToolsShopy.Store</a></p><p style="margin:6px 0 0">If you prefer not to receive these messages, just reply with "unsubscribe" and we will remove you immediately.</p></td></tr></table></td></tr></table></body></html>',
        },
    ],
    'royalgroups': [
        {
            'step':       1,
            'delay_days': 0,
            'name':       'Initial Outreach',
            'subject':    'Welcome to RoyalGroups.Shop',
            'body':       '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd"><html xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office"><head><meta http-equiv="Content-Type" content="text/html; charset=UTF-8" /><meta http-equiv="X-UA-Compatible" content="IE=edge" /><meta name="viewport" content="width=device-width, initial-scale=1.0" /><meta name="format-detection" content="telephone=no, date=no, address=no, email=no" /><title>RoyalGroups</title><!--[if mso]><xml><o:OfficeDocumentSettings><o:AllowPNG/><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml><![endif]--><style type="text/css">body{margin:0!important;padding:0!important;width:100%!important;-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;mso-line-height-rule:exactly}table{border-collapse:collapse!important;mso-table-lspace:0pt;mso-table-rspace:0pt}img{-ms-interpolation-mode:bicubic;border:0;outline:none;text-decoration:none;display:block}a{text-decoration:none}</style></head><body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,Helvetica,sans-serif;-webkit-font-smoothing:antialiased;mso-line-height-rule:exactly"><div style="display:none;max-height:0;overflow:hidden;mso-hide:all">Premium quality, carefully selected</div><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f3f4f6"><tr><td align="center" style="padding:24px 12px"><table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="background:#ffffff;border-radius:12px;overflow:hidden;max-width:600px"><tr><td bgcolor="#1e1b4b" style="background-color:#1e1b4b;padding:20px 32px;mso-line-height-rule:exactly;line-height:1.2"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse"><tr><td valign="middle" width="76" style="padding-right:14px;width:76px"><a href="https://www.RoyalGroups.Shop" style="text-decoration:none"><img src="https://skymaxx-lead-engine.onrender.com/static/logo_email.png" alt="RoyalGroups.Shop" width="60" height="60" style="display:block;width:60px;height:60px;max-width:60px;border-radius:50%;border:0;outline:none;text-decoration:none;-ms-interpolation-mode:bicubic" /></a></td><td valign="middle" style="color:#ffffff;font-size:22px;font-weight:700;letter-spacing:0.5px;font-family:Arial,Helvetica,sans-serif;mso-line-height-rule:exactly;line-height:1.2"><a href="https://www.RoyalGroups.Shop" style="color:#ffffff;text-decoration:none">ROYALGROUPS</a><div style="color:#cbd5e1;font-size:12px;font-weight:500;margin-top:2px;font-family:Arial,Helvetica,sans-serif">Curated premium products</div><div style="margin-top:4px"><a href="https://www.RoyalGroups.Shop" style="color:#a78bfa;font-size:12px;text-decoration:none;font-weight:600;font-family:Arial,Helvetica,sans-serif">www.RoyalGroups.Shop</a></div></td></tr></table></td></tr><tr><td style="padding:32px 36px;font-family:Arial,Helvetica,sans-serif;color:#1f2937;font-size:15px;line-height:1.6"><p style="margin:0 0 16px">Hi {{name}},</p><p style="margin:0 0 16px">Welcome to <strong>RoyalGroups.Shop</strong>! We are glad to have you with us.</p><p style="margin:0 0 14px;font-size:14px;color:#475569">Browse our full selection at <a href="https://www.RoyalGroups.Shop" style="color:#2563eb;text-decoration:underline;font-weight:600">www.RoyalGroups.Shop</a>.</p><p style="margin:0 0 16px">Our focus is on premium quality, carefully selected by our team. Fewer products, higher standards, each one chosen for craftsmanship and longevity.</p><p style="margin:0 0 12px">A quick look at what we offer:</p><ul style="margin:0 0 16px;padding-left:22px"><li style="margin-bottom:6px"><strong>Home &amp; Living</strong> &mdash; premium home essentials</li><li style="margin-bottom:6px"><strong>Personal Care</strong> &mdash; thoughtfully sourced everyday items</li><li style="margin-bottom:6px"><strong>Lifestyle &amp; Gifts</strong> &mdash; curated for special occasions</li><li style="margin-bottom:0"><strong>Accessories</strong> &mdash; small details that make a difference</li></ul><p style="margin:0 0 14px;font-size:14px;color:#475569">All categories are organized at <a href="https://www.RoyalGroups.Shop" style="color:#2563eb;text-decoration:underline;font-weight:600">www.RoyalGroups.Shop</a> for easy browsing.</p><table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:18px 0"><tr><td bgcolor="#a78bfa" style="background-color:#a78bfa;border-radius:6px"><a href="https://www.RoyalGroups.Shop" style="display:inline-block;padding:12px 28px;color:#ffffff;font-weight:700;font-size:15px;text-decoration:none">Visit www.RoyalGroups.Shop &rarr;</a></td></tr></table><p style="margin:0 0 16px">Have a question or want a recommendation? Reply to this email or visit <a href="https://www.RoyalGroups.Shop" style="color:#2563eb;text-decoration:underline;font-weight:600">www.RoyalGroups.Shop</a> anytime &mdash; we read every message.</p><p style="margin:0 0 4px">Thanks for stopping by,</p><p style="margin:0;font-weight:600">RoyalGroups Team</p><p style="margin:0;color:#64748b;font-size:13px">RoyalGroups.Shop &middot; <a href="https://www.RoyalGroups.Shop" style="color:#2563eb;text-decoration:underline;font-weight:600">www.RoyalGroups.Shop</a></p></td></tr><tr><td style="background:#1e1b4b;padding:18px 36px;color:#94a3b8;font-size:11px;line-height:1.5;font-family:Arial,Helvetica,sans-serif"><p style="margin:0"><strong style="color:#cbd5e1">RoyalGroups</strong> &middot; <a href="https://www.RoyalGroups.Shop" style="color:#a78bfa;text-decoration:none;font-weight:600">www.RoyalGroups.Shop</a> &middot; Premium product curation &middot; USA</p><p style="margin:6px 0 0"><a href="mailto:support@royalgroups.shop" style="color:#a78bfa;text-decoration:none">support@royalgroups.shop</a> &middot; Visit us at <a href="https://www.RoyalGroups.Shop" style="color:#a78bfa;text-decoration:none">www.RoyalGroups.Shop</a></p><p style="margin:6px 0 0">If you prefer not to receive these messages, just reply with "unsubscribe" and we will remove you immediately.</p></td></tr></table></td></tr></table></body></html>',
        },
        {
            'step':       2,
            'delay_days': 3,
            'name':       'Follow-up',
            'subject':    "This month's editor picks",
            'body':       '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd"><html xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office"><head><meta http-equiv="Content-Type" content="text/html; charset=UTF-8" /><meta http-equiv="X-UA-Compatible" content="IE=edge" /><meta name="viewport" content="width=device-width, initial-scale=1.0" /><meta name="format-detection" content="telephone=no, date=no, address=no, email=no" /><title>RoyalGroups</title><!--[if mso]><xml><o:OfficeDocumentSettings><o:AllowPNG/><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml><![endif]--><style type="text/css">body{margin:0!important;padding:0!important;width:100%!important;-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;mso-line-height-rule:exactly}table{border-collapse:collapse!important;mso-table-lspace:0pt;mso-table-rspace:0pt}img{-ms-interpolation-mode:bicubic;border:0;outline:none;text-decoration:none;display:block}a{text-decoration:none}</style></head><body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,Helvetica,sans-serif;-webkit-font-smoothing:antialiased;mso-line-height-rule:exactly"><div style="display:none;max-height:0;overflow:hidden;mso-hide:all">Editor curated essentials and member favorites</div><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f3f4f6"><tr><td align="center" style="padding:24px 12px"><table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="background:#ffffff;border-radius:12px;overflow:hidden;max-width:600px"><tr><td bgcolor="#1e1b4b" style="background-color:#1e1b4b;padding:20px 32px;mso-line-height-rule:exactly;line-height:1.2"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse"><tr><td valign="middle" width="76" style="padding-right:14px;width:76px"><a href="https://www.RoyalGroups.Shop" style="text-decoration:none"><img src="https://skymaxx-lead-engine.onrender.com/static/logo_email.png" alt="RoyalGroups.Shop" width="60" height="60" style="display:block;width:60px;height:60px;max-width:60px;border-radius:50%;border:0;outline:none;text-decoration:none;-ms-interpolation-mode:bicubic" /></a></td><td valign="middle" style="color:#ffffff;font-size:22px;font-weight:700;letter-spacing:0.5px;font-family:Arial,Helvetica,sans-serif;mso-line-height-rule:exactly;line-height:1.2"><a href="https://www.RoyalGroups.Shop" style="color:#ffffff;text-decoration:none">ROYALGROUPS</a><div style="color:#cbd5e1;font-size:12px;font-weight:500;margin-top:2px;font-family:Arial,Helvetica,sans-serif">Curated premium products</div><div style="margin-top:4px"><a href="https://www.RoyalGroups.Shop" style="color:#a78bfa;font-size:12px;text-decoration:none;font-weight:600;font-family:Arial,Helvetica,sans-serif">www.RoyalGroups.Shop</a></div></td></tr></table></td></tr><tr><td style="padding:32px 36px;font-family:Arial,Helvetica,sans-serif;color:#1f2937;font-size:15px;line-height:1.6"><p style="margin:0 0 16px">Hi {{name}},</p><p style="margin:0 0 16px">Quick follow-up from <strong>RoyalGroups.Shop</strong>.</p><p style="margin:0 0 14px;font-size:14px;color:#475569">Latest at <a href="https://www.RoyalGroups.Shop" style="color:#2563eb;text-decoration:underline;font-weight:600">www.RoyalGroups.Shop</a>.</p><p style="margin:0 0 16px">Items our customers consistently come back to:</p><ul style="margin:0 0 16px;padding-left:22px"><li style="margin-bottom:6px"><strong>Editor-curated essentials</strong> &mdash; the staples we recommend most often</li><li style="margin-bottom:6px"><strong>Premium gifting picks</strong> &mdash; thoughtful options for any occasion</li><li style="margin-bottom:6px"><strong>Seasonal favorites</strong> &mdash; refreshed throughout the year</li><li style="margin-bottom:0"><strong>Limited-availability finds</strong> &mdash; harder-to-source quality items</li></ul><p style="margin:0 0 14px;font-size:14px;color:#475569">All of these and more at <a href="https://www.RoyalGroups.Shop" style="color:#2563eb;text-decoration:underline;font-weight:600">www.RoyalGroups.Shop</a>.</p><table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:18px 0"><tr><td bgcolor="#a78bfa" style="background-color:#a78bfa;border-radius:6px"><a href="https://www.RoyalGroups.Shop" style="display:inline-block;padding:12px 28px;color:#ffffff;font-weight:700;font-size:15px;text-decoration:none">Visit www.RoyalGroups.Shop &rarr;</a></td></tr></table><p style="margin:0 0 16px">If you spot something useful or want a recommendation, just reply &mdash; or browse the full lineup at <a href="https://www.RoyalGroups.Shop" style="color:#2563eb;text-decoration:underline;font-weight:600">www.RoyalGroups.Shop</a>.</p><p style="margin:0 0 4px">Cheers,</p><p style="margin:0;font-weight:600">RoyalGroups Team</p><p style="margin:0;color:#64748b;font-size:13px">RoyalGroups.Shop &middot; <a href="https://www.RoyalGroups.Shop" style="color:#2563eb;text-decoration:underline;font-weight:600">www.RoyalGroups.Shop</a></p></td></tr><tr><td style="background:#1e1b4b;padding:18px 36px;color:#94a3b8;font-size:11px;line-height:1.5;font-family:Arial,Helvetica,sans-serif"><p style="margin:0"><strong style="color:#cbd5e1">RoyalGroups</strong> &middot; <a href="https://www.RoyalGroups.Shop" style="color:#a78bfa;text-decoration:none;font-weight:600">www.RoyalGroups.Shop</a> &middot; Premium product curation &middot; USA</p><p style="margin:6px 0 0"><a href="mailto:support@royalgroups.shop" style="color:#a78bfa;text-decoration:none">support@royalgroups.shop</a> &middot; Visit us at <a href="https://www.RoyalGroups.Shop" style="color:#a78bfa;text-decoration:none">www.RoyalGroups.Shop</a></p><p style="margin:6px 0 0">If you prefer not to receive these messages, just reply with "unsubscribe" and we will remove you immediately.</p></td></tr></table></td></tr></table></body></html>',
        },
        {
            'step':       3,
            'delay_days': 4,
            'name':       'Educational',
            'subject':    'A note on how we curate our selection',
            'body':       '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd"><html xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office"><head><meta http-equiv="Content-Type" content="text/html; charset=UTF-8" /><meta http-equiv="X-UA-Compatible" content="IE=edge" /><meta name="viewport" content="width=device-width, initial-scale=1.0" /><meta name="format-detection" content="telephone=no, date=no, address=no, email=no" /><title>RoyalGroups</title><!--[if mso]><xml><o:OfficeDocumentSettings><o:AllowPNG/><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml><![endif]--><style type="text/css">body{margin:0!important;padding:0!important;width:100%!important;-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;mso-line-height-rule:exactly}table{border-collapse:collapse!important;mso-table-lspace:0pt;mso-table-rspace:0pt}img{-ms-interpolation-mode:bicubic;border:0;outline:none;text-decoration:none;display:block}a{text-decoration:none}</style></head><body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,Helvetica,sans-serif;-webkit-font-smoothing:antialiased;mso-line-height-rule:exactly"><div style="display:none;max-height:0;overflow:hidden;mso-hide:all">Quality, maker reputation, value, gift-worthy</div><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f3f4f6"><tr><td align="center" style="padding:24px 12px"><table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="background:#ffffff;border-radius:12px;overflow:hidden;max-width:600px"><tr><td bgcolor="#1e1b4b" style="background-color:#1e1b4b;padding:20px 32px;mso-line-height-rule:exactly;line-height:1.2"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse"><tr><td valign="middle" width="76" style="padding-right:14px;width:76px"><a href="https://www.RoyalGroups.Shop" style="text-decoration:none"><img src="https://skymaxx-lead-engine.onrender.com/static/logo_email.png" alt="RoyalGroups.Shop" width="60" height="60" style="display:block;width:60px;height:60px;max-width:60px;border-radius:50%;border:0;outline:none;text-decoration:none;-ms-interpolation-mode:bicubic" /></a></td><td valign="middle" style="color:#ffffff;font-size:22px;font-weight:700;letter-spacing:0.5px;font-family:Arial,Helvetica,sans-serif;mso-line-height-rule:exactly;line-height:1.2"><a href="https://www.RoyalGroups.Shop" style="color:#ffffff;text-decoration:none">ROYALGROUPS</a><div style="color:#cbd5e1;font-size:12px;font-weight:500;margin-top:2px;font-family:Arial,Helvetica,sans-serif">Curated premium products</div><div style="margin-top:4px"><a href="https://www.RoyalGroups.Shop" style="color:#a78bfa;font-size:12px;text-decoration:none;font-weight:600;font-family:Arial,Helvetica,sans-serif">www.RoyalGroups.Shop</a></div></td></tr></table></td></tr><tr><td style="padding:32px 36px;font-family:Arial,Helvetica,sans-serif;color:#1f2937;font-size:15px;line-height:1.6"><p style="margin:0 0 16px">Hi {{name}},</p><p style="margin:0 0 16px">A quick note from <strong>RoyalGroups.Shop</strong> on how we curate what we feature.</p><p style="margin:0 0 14px;font-size:14px;color:#475569">See our current selection: <a href="https://www.RoyalGroups.Shop" style="color:#2563eb;text-decoration:underline;font-weight:600">www.RoyalGroups.Shop</a>.</p><p style="margin:0 0 12px">Our curation criteria are simple but strict. A product joins our selection only if it meets all four:</p><ul style="margin:0 0 16px;padding-left:22px"><li style="margin-bottom:6px">Made with quality materials that last</li><li style="margin-bottom:6px">Comes from a maker with a clear quality record</li><li style="margin-bottom:6px">Delivers value relative to its price tier</li><li style="margin-bottom:0">We would gift it to someone we care about</li></ul><p style="margin:0 0 14px;font-size:14px;color:#475569">Read more about our approach at <a href="https://www.RoyalGroups.Shop" style="color:#2563eb;text-decoration:underline;font-weight:600">www.RoyalGroups.Shop</a>.</p><table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:18px 0"><tr><td bgcolor="#a78bfa" style="background-color:#a78bfa;border-radius:6px"><a href="https://www.RoyalGroups.Shop" style="display:inline-block;padding:12px 28px;color:#ffffff;font-weight:700;font-size:15px;text-decoration:none">Visit www.RoyalGroups.Shop &rarr;</a></td></tr></table><p style="margin:0 0 16px">Questions about a specific category? Reply or browse <a href="https://www.RoyalGroups.Shop" style="color:#2563eb;text-decoration:underline;font-weight:600">www.RoyalGroups.Shop</a> &mdash; happy to help either way.</p><p style="margin:0 0 4px">Best,</p><p style="margin:0;font-weight:600">RoyalGroups Team</p><p style="margin:0;color:#64748b;font-size:13px">RoyalGroups.Shop &middot; <a href="https://www.RoyalGroups.Shop" style="color:#2563eb;text-decoration:underline;font-weight:600">www.RoyalGroups.Shop</a></p></td></tr><tr><td style="background:#1e1b4b;padding:18px 36px;color:#94a3b8;font-size:11px;line-height:1.5;font-family:Arial,Helvetica,sans-serif"><p style="margin:0"><strong style="color:#cbd5e1">RoyalGroups</strong> &middot; <a href="https://www.RoyalGroups.Shop" style="color:#a78bfa;text-decoration:none;font-weight:600">www.RoyalGroups.Shop</a> &middot; Premium product curation &middot; USA</p><p style="margin:6px 0 0"><a href="mailto:support@royalgroups.shop" style="color:#a78bfa;text-decoration:none">support@royalgroups.shop</a> &middot; Visit us at <a href="https://www.RoyalGroups.Shop" style="color:#a78bfa;text-decoration:none">www.RoyalGroups.Shop</a></p><p style="margin:6px 0 0">If you prefer not to receive these messages, just reply with "unsubscribe" and we will remove you immediately.</p></td></tr></table></td></tr></table></body></html>',
        },
        {
            'step':       4,
            'delay_days': 7,
            'name':       'Value / Curation',
            'subject':    'New arrivals and member favorites',
            'body':       '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd"><html xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office"><head><meta http-equiv="Content-Type" content="text/html; charset=UTF-8" /><meta http-equiv="X-UA-Compatible" content="IE=edge" /><meta name="viewport" content="width=device-width, initial-scale=1.0" /><meta name="format-detection" content="telephone=no, date=no, address=no, email=no" /><title>RoyalGroups</title><!--[if mso]><xml><o:OfficeDocumentSettings><o:AllowPNG/><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml><![endif]--><style type="text/css">body{margin:0!important;padding:0!important;width:100%!important;-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;mso-line-height-rule:exactly}table{border-collapse:collapse!important;mso-table-lspace:0pt;mso-table-rspace:0pt}img{-ms-interpolation-mode:bicubic;border:0;outline:none;text-decoration:none;display:block}a{text-decoration:none}</style></head><body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,Helvetica,sans-serif;-webkit-font-smoothing:antialiased;mso-line-height-rule:exactly"><div style="display:none;max-height:0;overflow:hidden;mso-hide:all">New additions and what is back in stock</div><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f3f4f6"><tr><td align="center" style="padding:24px 12px"><table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="background:#ffffff;border-radius:12px;overflow:hidden;max-width:600px"><tr><td bgcolor="#1e1b4b" style="background-color:#1e1b4b;padding:20px 32px;mso-line-height-rule:exactly;line-height:1.2"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse"><tr><td valign="middle" width="76" style="padding-right:14px;width:76px"><a href="https://www.RoyalGroups.Shop" style="text-decoration:none"><img src="https://skymaxx-lead-engine.onrender.com/static/logo_email.png" alt="RoyalGroups.Shop" width="60" height="60" style="display:block;width:60px;height:60px;max-width:60px;border-radius:50%;border:0;outline:none;text-decoration:none;-ms-interpolation-mode:bicubic" /></a></td><td valign="middle" style="color:#ffffff;font-size:22px;font-weight:700;letter-spacing:0.5px;font-family:Arial,Helvetica,sans-serif;mso-line-height-rule:exactly;line-height:1.2"><a href="https://www.RoyalGroups.Shop" style="color:#ffffff;text-decoration:none">ROYALGROUPS</a><div style="color:#cbd5e1;font-size:12px;font-weight:500;margin-top:2px;font-family:Arial,Helvetica,sans-serif">Curated premium products</div><div style="margin-top:4px"><a href="https://www.RoyalGroups.Shop" style="color:#a78bfa;font-size:12px;text-decoration:none;font-weight:600;font-family:Arial,Helvetica,sans-serif">www.RoyalGroups.Shop</a></div></td></tr></table></td></tr><tr><td style="padding:32px 36px;font-family:Arial,Helvetica,sans-serif;color:#1f2937;font-size:15px;line-height:1.6"><p style="margin:0 0 16px">Hi {{name}},</p><p style="margin:0 0 16px">Hello again from <strong>RoyalGroups.Shop</strong>.</p><p style="margin:0 0 14px;font-size:14px;color:#475569">What is fresh: <a href="https://www.RoyalGroups.Shop" style="color:#2563eb;text-decoration:underline;font-weight:600">www.RoyalGroups.Shop</a>.</p><p style="margin:0 0 16px">Recent additions and member favorites:</p><ul style="margin:0 0 16px;padding-left:22px"><li style="margin-bottom:6px"><strong>Newly added</strong> premium pieces just in</li><li style="margin-bottom:6px"><strong>Restocked classics</strong> our subscribers asked for</li><li style="margin-bottom:6px"><strong>Seasonal collection</strong> updates</li><li style="margin-bottom:0"><strong>Gift-ready</strong> selections with elegant packaging</li></ul><p style="margin:0 0 14px;font-size:14px;color:#475569">Browse new arrivals at <a href="https://www.RoyalGroups.Shop" style="color:#2563eb;text-decoration:underline;font-weight:600">www.RoyalGroups.Shop</a>.</p><table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:18px 0"><tr><td bgcolor="#a78bfa" style="background-color:#a78bfa;border-radius:6px"><a href="https://www.RoyalGroups.Shop" style="display:inline-block;padding:12px 28px;color:#ffffff;font-weight:700;font-size:15px;text-decoration:none">Visit www.RoyalGroups.Shop &rarr;</a></td></tr></table><p style="margin:0 0 16px">If you would like a suggestion based on what you are looking for, just reply with a few words &mdash; or explore <a href="https://www.RoyalGroups.Shop" style="color:#2563eb;text-decoration:underline;font-weight:600">www.RoyalGroups.Shop</a> at your own pace.</p><p style="margin:0 0 4px">Cheers,</p><p style="margin:0;font-weight:600">RoyalGroups Team</p><p style="margin:0;color:#64748b;font-size:13px">RoyalGroups.Shop &middot; <a href="https://www.RoyalGroups.Shop" style="color:#2563eb;text-decoration:underline;font-weight:600">www.RoyalGroups.Shop</a></p></td></tr><tr><td style="background:#1e1b4b;padding:18px 36px;color:#94a3b8;font-size:11px;line-height:1.5;font-family:Arial,Helvetica,sans-serif"><p style="margin:0"><strong style="color:#cbd5e1">RoyalGroups</strong> &middot; <a href="https://www.RoyalGroups.Shop" style="color:#a78bfa;text-decoration:none;font-weight:600">www.RoyalGroups.Shop</a> &middot; Premium product curation &middot; USA</p><p style="margin:6px 0 0"><a href="mailto:support@royalgroups.shop" style="color:#a78bfa;text-decoration:none">support@royalgroups.shop</a> &middot; Visit us at <a href="https://www.RoyalGroups.Shop" style="color:#a78bfa;text-decoration:none">www.RoyalGroups.Shop</a></p><p style="margin:6px 0 0">If you prefer not to receive these messages, just reply with "unsubscribe" and we will remove you immediately.</p></td></tr></table></td></tr></table></body></html>',
        },
        {
            'step':       5,
            'delay_days': 7,
            'name':       'Closing',
            'subject':    'Three categories worth knowing about',
            'body':       '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd"><html xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office"><head><meta http-equiv="Content-Type" content="text/html; charset=UTF-8" /><meta http-equiv="X-UA-Compatible" content="IE=edge" /><meta name="viewport" content="width=device-width, initial-scale=1.0" /><meta name="format-detection" content="telephone=no, date=no, address=no, email=no" /><title>RoyalGroups</title><!--[if mso]><xml><o:OfficeDocumentSettings><o:AllowPNG/><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml><![endif]--><style type="text/css">body{margin:0!important;padding:0!important;width:100%!important;-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;mso-line-height-rule:exactly}table{border-collapse:collapse!important;mso-table-lspace:0pt;mso-table-rspace:0pt}img{-ms-interpolation-mode:bicubic;border:0;outline:none;text-decoration:none;display:block}a{text-decoration:none}</style></head><body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,Helvetica,sans-serif;-webkit-font-smoothing:antialiased;mso-line-height-rule:exactly"><div style="display:none;max-height:0;overflow:hidden;mso-hide:all">Everyday luxury, premium gifts, editor picks</div><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f3f4f6"><tr><td align="center" style="padding:24px 12px"><table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="background:#ffffff;border-radius:12px;overflow:hidden;max-width:600px"><tr><td bgcolor="#1e1b4b" style="background-color:#1e1b4b;padding:20px 32px;mso-line-height-rule:exactly;line-height:1.2"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse"><tr><td valign="middle" width="76" style="padding-right:14px;width:76px"><a href="https://www.RoyalGroups.Shop" style="text-decoration:none"><img src="https://skymaxx-lead-engine.onrender.com/static/logo_email.png" alt="RoyalGroups.Shop" width="60" height="60" style="display:block;width:60px;height:60px;max-width:60px;border-radius:50%;border:0;outline:none;text-decoration:none;-ms-interpolation-mode:bicubic" /></a></td><td valign="middle" style="color:#ffffff;font-size:22px;font-weight:700;letter-spacing:0.5px;font-family:Arial,Helvetica,sans-serif;mso-line-height-rule:exactly;line-height:1.2"><a href="https://www.RoyalGroups.Shop" style="color:#ffffff;text-decoration:none">ROYALGROUPS</a><div style="color:#cbd5e1;font-size:12px;font-weight:500;margin-top:2px;font-family:Arial,Helvetica,sans-serif">Curated premium products</div><div style="margin-top:4px"><a href="https://www.RoyalGroups.Shop" style="color:#a78bfa;font-size:12px;text-decoration:none;font-weight:600;font-family:Arial,Helvetica,sans-serif">www.RoyalGroups.Shop</a></div></td></tr></table></td></tr><tr><td style="padding:32px 36px;font-family:Arial,Helvetica,sans-serif;color:#1f2937;font-size:15px;line-height:1.6"><p style="margin:0 0 16px">Hi {{name}},</p><p style="margin:0 0 16px">This is my last note for now from <strong>RoyalGroups.Shop</strong> &mdash; I do not want to crowd your inbox.</p><p style="margin:0 0 14px;font-size:14px;color:#475569">Full store: <a href="https://www.RoyalGroups.Shop" style="color:#2563eb;text-decoration:underline;font-weight:600">www.RoyalGroups.Shop</a>.</p><p style="margin:0 0 16px">Three categories worth keeping in mind:</p><ul style="margin:0 0 16px;padding-left:22px"><li style="margin-bottom:6px"><strong>Everyday luxury</strong> &mdash; small upgrades that add up</li><li style="margin-bottom:6px"><strong>Premium gifts</strong> &mdash; thoughtful for any occasion</li><li style="margin-bottom:0"><strong>Editor picks</strong> &mdash; what our team uses themselves</li></ul><p style="margin:0 0 14px;font-size:14px;color:#475569">All available at <a href="https://www.RoyalGroups.Shop" style="color:#2563eb;text-decoration:underline;font-weight:600">www.RoyalGroups.Shop</a>.</p><table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:18px 0"><tr><td bgcolor="#a78bfa" style="background-color:#a78bfa;border-radius:6px"><a href="https://www.RoyalGroups.Shop" style="display:inline-block;padding:12px 28px;color:#ffffff;font-weight:700;font-size:15px;text-decoration:none">Visit www.RoyalGroups.Shop &rarr;</a></td></tr></table><p style="margin:0 0 16px">Whenever you are ready to browse, reach out, or share feedback, you will find us at <a href="https://www.RoyalGroups.Shop" style="color:#2563eb;text-decoration:underline;font-weight:600">www.RoyalGroups.Shop</a>. Thanks for being on the list.</p><p style="margin:0 0 4px">All the best,</p><p style="margin:0;font-weight:600">RoyalGroups Team</p><p style="margin:0;color:#64748b;font-size:13px">RoyalGroups.Shop &middot; <a href="https://www.RoyalGroups.Shop" style="color:#2563eb;text-decoration:underline;font-weight:600">www.RoyalGroups.Shop</a> &middot; support@royalgroups.shop</p></td></tr><tr><td style="background:#1e1b4b;padding:18px 36px;color:#94a3b8;font-size:11px;line-height:1.5;font-family:Arial,Helvetica,sans-serif"><p style="margin:0"><strong style="color:#cbd5e1">RoyalGroups</strong> &middot; <a href="https://www.RoyalGroups.Shop" style="color:#a78bfa;text-decoration:none;font-weight:600">www.RoyalGroups.Shop</a> &middot; Premium product curation &middot; USA</p><p style="margin:6px 0 0"><a href="mailto:support@royalgroups.shop" style="color:#a78bfa;text-decoration:none">support@royalgroups.shop</a> &middot; Visit us at <a href="https://www.RoyalGroups.Shop" style="color:#a78bfa;text-decoration:none">www.RoyalGroups.Shop</a></p><p style="margin:6px 0 0">If you prefer not to receive these messages, just reply with "unsubscribe" and we will remove you immediately.</p></td></tr></table></td></tr></table></body></html>',
        },
    ],
}

# Backward compatibility: legacy SEQUENCE_TEMPLATES = SKYMAXX templates
SEQUENCE_TEMPLATES = SEQUENCE_TEMPLATES_BY_DOMAIN['skymaxx']
# ── Template Overrides (DB-stored edits to SEQUENCE_TEMPLATES) ──
def get_template_overrides():
    """Backward-compat: returns SKYMAXX domain overrides only."""
    return get_template_overrides_for_domain('skymaxx')

def _DEPRECATED_get_template_overrides():
    """Old implementation kept for reference only."""
    try:
        conn = get_db()
        cur = conn.execute("SELECT step, subject, body, updated_at, updated_by FROM template_overrides")
        rows = cur.fetchall()
        if hasattr(conn, 'close'):
            try: conn.close()
            except Exception: pass
        result = {}
        for r in rows:
            step = r[0] if not isinstance(r, dict) else r['step']
            result[step] = {
                'subject':    r[1] if not isinstance(r, dict) else r['subject'],
                'body':       r[2] if not isinstance(r, dict) else r['body'],
                'updated_at': str(r[3]) if r[3] and not isinstance(r, dict) else (str(r['updated_at']) if isinstance(r, dict) and r['updated_at'] else None),
                'updated_by': r[4] if not isinstance(r, dict) else r.get('updated_by'),
            }
        return result
    except Exception as e:
        print(f"[get_template_overrides] err: {e}")
        return {}

def get_template_overrides_for_domain(domain_key):
    """Returns {step: {subject,body,updated_at,updated_by}} for a domain."""
    try:
        conn = get_db()
        if USE_POSTGRES:
            cur = conn.execute(
                "SELECT step, subject, body, updated_at, updated_by FROM template_overrides WHERE domain_key=%s",
                (domain_key,))
        else:
            cur = conn.execute(
                "SELECT step, subject, body, updated_at, updated_by FROM template_overrides WHERE domain_key=?",
                (domain_key,))
        rows = cur.fetchall()
        try: conn.close()
        except Exception: pass
        result = {}
        for r in rows:
            step = r[0] if not isinstance(r, dict) else r['step']
            result[step] = {
                'subject':    r[1] if not isinstance(r, dict) else r['subject'],
                'body':       r[2] if not isinstance(r, dict) else r['body'],
                'updated_at': str(r[3]) if r[3] and not isinstance(r, dict) else (str(r['updated_at']) if isinstance(r, dict) and r['updated_at'] else None),
                'updated_by': r[4] if not isinstance(r, dict) else r.get('updated_by'),
            }
        return result
    except Exception as e:
        print(f"[get_overrides] err: {e}")
        return {}

def get_effective_templates(domain_key='skymaxx'):
    """Returns SEQUENCE_TEMPLATES_BY_DOMAIN[domain_key] with DB overrides applied.
    Each template gets 'edited':bool, 'domain_key': str."""
    if domain_key not in SEQUENCE_TEMPLATES_BY_DOMAIN:
        domain_key = 'skymaxx'  # fallback
    base = SEQUENCE_TEMPLATES_BY_DOMAIN[domain_key]
    overrides = get_template_overrides_for_domain(domain_key)
    result = []
    for tpl in base:
        step = tpl['step']
        merged = dict(tpl)
        merged['domain_key'] = domain_key
        if step in overrides:
            ov = overrides[step]
            if ov.get('subject'): merged['subject'] = ov['subject']
            if ov.get('body'):    merged['body']    = ov['body']
            merged['edited']      = True
            merged['edited_at']   = ov.get('updated_at')
            merged['edited_by']   = ov.get('updated_by')
        else:
            merged['edited'] = False
        result.append(merged)
    return result

def get_effective_template_for_step(step, domain_key='skymaxx'):
    """Returns merged template for a single step in a domain."""
    for tpl in get_effective_templates(domain_key):
        if tpl['step'] == step:
            return tpl
    return None

def _legacy_get_template_overrides():
    """Backward compat shim - returns SKYMAXX overrides only."""
    return get_template_overrides_for_domain('skymaxx')

# Auto-reply template
AUTO_REPLY_TEMPLATE = {
    'subject': 'We received your message \u2014 SKYMAXX Technologies',
    'body': '<!DOCTYPE html><html><body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,Arial,sans-serif"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f3f4f6;padding:24px 12px"><tr><td align="center"><table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.08);max-width:600px"><tr><td bgcolor="#0f172a" style="background-color:#0f172a;padding:20px 32px;mso-line-height-rule:exactly;line-height:1.2"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse"><tr><td valign="middle" width="76" style="padding-right:14px;width:76px"><img src="https://skymaxx-lead-engine.onrender.com/static/logo_email.png" alt="SKYMAXX" width="60" height="60" style="display:block;width:60px;height:60px;max-width:60px;border-radius:50%;border:0;outline:none;text-decoration:none;-ms-interpolation-mode:bicubic" /></td><td valign="middle" style="color:#ffffff;font-size:22px;font-weight:700;letter-spacing:0.5px;font-family:Arial,Helvetica,sans-serif;mso-line-height-rule:exactly;line-height:1.2">SKYMAXX <span style="color:#60a5fa;font-weight:500">TECHNOLOGIES</span><div style="color:#cbd5e1;font-size:12px;font-weight:500;margin-top:2px;font-family:Arial,Helvetica,sans-serif">Microsoft 365 Specialists</div></td></tr></table></td></tr><tr><td style="padding:36px 36px 28px;color:#1f2937;font-size:15px;line-height:1.7"><p style="margin:0 0 16px;font-size:16px">Hello <strong>{{name}}</strong>,</p><p style="margin:0 0 16px">Thank you for reaching out to <strong>SKYMAXX Technologies</strong>.</p><p style="margin:0 0 16px">We\'ve received your message and a member of our team will respond within <strong>24 hours</strong> (business days, UAE time).</p><p style="margin:0 0 16px">If your matter is urgent, please include "URGENT" in your subject line and we\'ll prioritize it.</p><p style="margin:0 0 8px">In the meantime, you can learn more about our Microsoft 365 management services at <a href="https://www.skymaxx.company" style="color:#2563eb;text-decoration:none;font-weight:600">www.SKYMAXX.Company</a>.</p><p style="margin:24px 0 0;color:#374151">Best regards,<br/><strong style="color:#0f172a">SKYMAXX Support Team</strong><br/><span style="color:#64748b;font-size:13px">SKYMAXX Technologies</span><br/><a href="https://www.skymaxx.company" style="color:#2563eb;text-decoration:none;font-size:13px;font-weight:500">www.SKYMAXX.Company</a></p></td></tr><tr><td style="background:#f8fafc;padding:22px 36px;border-top:1px solid #e5e7eb"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="color:#64748b;font-size:12px;line-height:1.6"><strong style="color:#0f172a">SKYMAXX Technologies</strong> &nbsp;&middot;&nbsp; Microsoft 365 Management for SMBs<br/><a href="https://www.skymaxx.company" style="color:#2563eb;text-decoration:none;font-weight:500">www.SKYMAXX.Company</a> &nbsp;&middot;&nbsp; <a href="mailto:support@skymaxx.company" style="color:#2563eb;text-decoration:none;font-weight:500">support@skymaxx.company</a><br/><br/><span style="font-size:11px;color:#94a3b8">You\'re receiving this because your business profile matched our outreach criteria. <a href="mailto:support@skymaxx.company?subject=UNSUBSCRIBE" style="color:#94a3b8;text-decoration:underline">Unsubscribe</a></span></td></tr></table></td></tr></table></td></tr></table></body></html>',
}

# ─────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────

# ════════════════════════════════════════════════════════════════════════
# DATABASE ADAPTER — supports both SQLite (dev) and Postgres (production)
# Set DATABASE_URL env var to switch to Postgres. Otherwise uses SQLite.
# ════════════════════════════════════════════════════════════════════════
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
USE_POSTGRES = bool(DATABASE_URL and DATABASE_URL.startswith("postgresql://"))

try:
    if USE_POSTGRES:
        import psycopg2
        import psycopg2.extras
except ImportError:
    print("[WARN] psycopg2 not installed — falling back to SQLite")
    USE_POSTGRES = False


class _Row(dict):
    """Dict-like row that supports both row[\'col\'] and row[0]."""
    def __init__(self, columns, values):
        if columns and values is not None:
            for i, c in enumerate(columns):
                dict.__setitem__(self, c, values[i])
        self._values = tuple(values) if values is not None else ()
    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return dict.__getitem__(self, key)


class _PGCursor:
    def __init__(self, raw_cur, lastrowid=None):
        self._cur = raw_cur
        self.lastrowid = lastrowid
        try: self.rowcount = raw_cur.rowcount
        except Exception: self.rowcount = 0
        try: self._cols = [d[0] for d in raw_cur.description] if raw_cur.description else None
        except Exception: self._cols = None
    def fetchone(self):
        try: row = self._cur.fetchone()
        except Exception: return None
        if row is None: return None
        return _Row(self._cols, row)
    def fetchall(self):
        try: rows = self._cur.fetchall()
        except Exception: return []
        return [_Row(self._cols, r) for r in rows]


def _translate_to_pg(sql):
    sql = sql.replace("?", "%s")
    sql = sql.replace("INSERT OR IGNORE INTO", "INSERT INTO")
    sql = sql.replace("INSERT OR REPLACE INTO", "INSERT INTO")
    sql = sql.replace("datetime(\'now\')", "CURRENT_TIMESTAMP")
    sql = sql.replace("date(\'now\')", "CURRENT_DATE")
    sql = sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
    return sql


class _PGConn:
    def __init__(self, conn):
        self.conn = conn
        self._last_rowcount = 0
    def execute(self, sql, params=()):
        original = sql
        sql = _translate_to_pg(sql)
        # Handle SELECT changes() — return last rowcount
        if sql.strip().upper() == "SELECT CHANGES()":
            val = self._last_rowcount
            class _Fake:
                def fetchone(self): return (val,)
                def fetchall(self): return [(val,)]
            return _Fake()
        is_or_ignore = "INSERT OR IGNORE INTO" in original
        if is_or_ignore and "ON CONFLICT" not in sql.upper():
            up = sql.upper()
            if " RETURNING " in up:
                idx = up.rindex(" RETURNING ")
                sql = sql[:idx] + " ON CONFLICT DO NOTHING " + sql[idx:]
            else:
                sql = sql.rstrip("; ") + " ON CONFLICT DO NOTHING"
        up = sql.upper().strip()
        needs_returning = (up.startswith("INSERT INTO") and "RETURNING" not in up)
        if needs_returning:
            sql = sql.rstrip("; ") + " RETURNING id"
        try:
            cur = self.conn.cursor()
            cur.execute(sql, params if params else None)
        except Exception as e:
            try: self.conn.rollback()
            except Exception: pass
            raise
        lastrowid = None
        if needs_returning:
            try:
                row = cur.fetchone()
                if row: lastrowid = row[0]
            except Exception: pass
        try: self._last_rowcount = cur.rowcount
        except Exception: pass
        return _PGCursor(cur, lastrowid=lastrowid)
    def executemany(self, sql, paramslist):
        sql = _translate_to_pg(sql)
        cur = self.conn.cursor()
        cur.executemany(sql, paramslist)
        try: self._last_rowcount = cur.rowcount
        except Exception: pass
        return _PGCursor(cur)
    def commit(self):
        try: self.conn.commit()
        except Exception: pass
    def close(self):
        try: self.conn.close()
        except Exception: pass


def _get_pg_conn():
    return _PGConn(psycopg2.connect(DATABASE_URL, sslmode="require"))


def _init_pg_schema(conn):
    """Postgres-compatible schema. Idempotent."""
    stmts = [
        """CREATE TABLE IF NOT EXISTS leads (
            id SERIAL PRIMARY KEY,
            name TEXT, email TEXT, phone TEXT, intl_phone TEXT, website TEXT,
            address TEXT, city TEXT, country TEXT, category TEXT,
            rating REAL DEFAULT 0, reviews INTEGER DEFAULT 0,
            place_id TEXT UNIQUE, maps_url TEXT,
            in_sequence INTEGER DEFAULT 0, sequence_step INTEGER DEFAULT 0,
            next_send_at TEXT, replied INTEGER DEFAULT 0, unsubscribed INTEGER DEFAULT 0,
            source TEXT DEFAULT 'manual', status TEXT DEFAULT 'new', campaign_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS email_log (
            id SERIAL PRIMARY KEY, lead_id INTEGER, step INTEGER,
            to_email TEXT, subject TEXT, status TEXT, error_msg TEXT,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS sequences (
            id SERIAL PRIMARY KEY, name TEXT NOT NULL, status TEXT DEFAULT 'active',
            total_leads INTEGER DEFAULT 0, total_sent INTEGER DEFAULT 0,
            total_failed INTEGER DEFAULT 0, total_replied INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS campaigns (
            id SERIAL PRIMARY KEY, name TEXT NOT NULL, summary TEXT,
            status TEXT DEFAULT 'draft', lead_ids_json TEXT NOT NULL,
            recipient_count INTEGER DEFAULT 0, schedule_starts TEXT,
            risk_score INTEGER DEFAULT 0, risk_notes TEXT,
            est_open_rate REAL DEFAULT 0, est_reply_rate REAL DEFAULT 0,
            deliverability TEXT, spf_status TEXT, dkim_status TEXT, dmarc_status TEXT,
            approved_at TEXT, approved_by TEXT, rejected_reason TEXT,
            actually_started INTEGER DEFAULT 0, actually_sent INTEGER DEFAULT 0,
            actually_failed INTEGER DEFAULT 0, actually_replied INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS tracking_events (
            id SERIAL PRIMARY KEY, log_id INTEGER, lead_id INTEGER,
            event_type TEXT NOT NULL, url TEXT, ip TEXT, user_agent TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS contact_groups (
            id SERIAL PRIMARY KEY, name TEXT NOT NULL UNIQUE, description TEXT,
            color TEXT DEFAULT '#3b82f6', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS lead_group_assignments (
            id SERIAL PRIMARY KEY, lead_id INTEGER NOT NULL, group_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE(lead_id, group_id)
        )""",
        "ALTER TABLE leads ADD COLUMN IF NOT EXISTS company TEXT",
        "ALTER TABLE leads ADD COLUMN IF NOT EXISTS title TEXT",
        "DROP TABLE IF EXISTS template_overrides",
        
        """CREATE TABLE IF NOT EXISTS template_overrides (
            id SERIAL PRIMARY KEY,
            step INTEGER UNIQUE NOT NULL,
            subject TEXT,
            body TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS domains (
            id SERIAL PRIMARY KEY,
            domain_key TEXT UNIQUE NOT NULL,
            label TEXT NOT NULL,
            website TEXT NOT NULL,
            company TEXT NOT NULL,
            sender_email TEXT NOT NULL,
            sender_name TEXT NOT NULL,
            audience TEXT DEFAULT 'b2b',
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS domain_key TEXT DEFAULT 'skymaxx'",
        "ALTER TABLE contact_groups ADD COLUMN IF NOT EXISTS domain_key TEXT DEFAULT 'skymaxx'",
        "ALTER TABLE leads ADD COLUMN IF NOT EXISTS domain_key TEXT DEFAULT 'skymaxx'",
        "ALTER TABLE template_overrides ADD COLUMN IF NOT EXISTS domain_key TEXT DEFAULT 'skymaxx'",
        "UPDATE campaigns SET domain_key='skymaxx' WHERE domain_key IS NULL",
        "UPDATE contact_groups SET domain_key='skymaxx' WHERE domain_key IS NULL",
        "UPDATE leads SET domain_key='skymaxx' WHERE domain_key IS NULL",
        "UPDATE template_overrides SET domain_key='skymaxx' WHERE domain_key IS NULL",
        "CREATE INDEX IF NOT EXISTS idx_campaigns_domain ON campaigns(domain_key)",
        "CREATE INDEX IF NOT EXISTS idx_groups_domain ON contact_groups(domain_key)",
        "CREATE INDEX IF NOT EXISTS idx_leads_domain ON leads(domain_key)",
        "DROP INDEX IF EXISTS idx_tovr_step",
        "ALTER TABLE template_overrides DROP CONSTRAINT IF EXISTS template_overrides_step_key",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_tovr_domain_step ON template_overrides(domain_key, step)",
        "CREATE INDEX IF NOT EXISTS idx_leads_sequence ON leads(in_sequence, next_send_at)",
        "CREATE INDEX IF NOT EXISTS idx_log_sent_at ON email_log(sent_at)",
        "CREATE INDEX IF NOT EXISTS idx_track_log ON tracking_events(log_id)",
        "CREATE INDEX IF NOT EXISTS idx_track_event ON tracking_events(event_type)",
        "CREATE INDEX IF NOT EXISTS idx_lga_lead ON lead_group_assignments(lead_id)",
        "CREATE INDEX IF NOT EXISTS idx_lga_group ON lead_group_assignments(group_id)",
    ]
    for s in stmts:
        try:
            conn.execute(s)
            conn.commit()
        except Exception as e:
            print("[init_pg]", str(e)[:200])
            try: conn.conn.rollback()
            except Exception: pass



def get_db():
    if USE_POSTGRES:
        return _get_pg_conn()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    if USE_POSTGRES:
        # Postgres-compatible schema with SERIAL instead of AUTOINCREMENT
        _init_pg_schema(conn)
        return
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

        CREATE TABLE IF NOT EXISTS campaigns (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            name              TEXT NOT NULL,
            summary           TEXT,
            status            TEXT DEFAULT 'draft',
            lead_ids_json     TEXT NOT NULL,
            recipient_count   INTEGER DEFAULT 0,
            schedule_starts   TEXT,
            risk_score        INTEGER DEFAULT 0,
            risk_notes        TEXT,
            est_open_rate     REAL DEFAULT 0,
            est_reply_rate    REAL DEFAULT 0,
            deliverability    TEXT,
            spf_status        TEXT,
            dkim_status       TEXT,
            dmarc_status      TEXT,
            approved_at       TEXT,
            approved_by       TEXT,
            rejected_reason   TEXT,
            actually_started  INTEGER DEFAULT 0,
            actually_sent     INTEGER DEFAULT 0,
            actually_failed   INTEGER DEFAULT 0,
            actually_replied  INTEGER DEFAULT 0,
            created_at        TEXT DEFAULT (datetime('now'))
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

        CREATE TABLE IF NOT EXISTS tracking_events (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            log_id       INTEGER,
            lead_id      INTEGER,
            event_type   TEXT NOT NULL,
            url          TEXT,
            ip           TEXT,
            user_agent   TEXT,
            created_at   TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS contact_groups (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL UNIQUE,
            description TEXT,
            color       TEXT DEFAULT '#3b82f6',
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS lead_group_assignments (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id    INTEGER NOT NULL,
            group_id   INTEGER NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(lead_id, group_id)
        );

        CREATE INDEX IF NOT EXISTS idx_leads_sequence ON leads(in_sequence, next_send_at);
        CREATE INDEX IF NOT EXISTS idx_log_sent_at ON email_log(sent_at);
        CREATE INDEX IF NOT EXISTS idx_track_log ON tracking_events(log_id);
        CREATE INDEX IF NOT EXISTS idx_track_event ON tracking_events(event_type);
        CREATE INDEX IF NOT EXISTS idx_lga_lead ON lead_group_assignments(lead_id);
        CREATE INDEX IF NOT EXISTS idx_lga_group ON lead_group_assignments(group_id);
        CREATE TABLE IF NOT EXISTS domains (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain_key TEXT UNIQUE NOT NULL,
            label TEXT NOT NULL,
            website TEXT NOT NULL,
            company TEXT NOT NULL,
            sender_email TEXT NOT NULL,
            sender_name TEXT NOT NULL,
            audience TEXT DEFAULT 'b2b',
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS template_overrides (
            id SERIAL PRIMARY KEY,
            step INTEGER UNIQUE NOT NULL,
            subject TEXT,
            body TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT
        );
    """)

    # Migration: add source column if missing
    cols = [r[1] for r in conn.execute("PRAGMA table_info(leads)").fetchall()]
    if 'source' not in cols:
        try: conn.execute("ALTER TABLE leads ADD COLUMN source TEXT DEFAULT 'manual'")
        except Exception: pass
    if 'campaign_id' not in cols:
        try: conn.execute("ALTER TABLE leads ADD COLUMN campaign_id INTEGER")
        except Exception: pass

    conn.commit()
    # ── Idempotent column additions (safe on both fresh and existing DBs) ──
    for col_sql in [
        "ALTER TABLE leads ADD COLUMN company TEXT",
        "ALTER TABLE leads ADD COLUMN title TEXT",
    ]:
        try:
            conn.execute(col_sql)
            conn.commit()
        except Exception:
            pass  # column already exists

    conn.close()

init_db()


def seed_domains_and_default_groups():
    """Seed DOMAIN_CONFIG into the domains table + create default contact group per domain.
    Idempotent: safe to call on every startup."""
    try:
        conn = get_db()
        for dkey, cfg in DOMAIN_CONFIG.items():
            # Upsert domain
            try:
                if USE_POSTGRES:
                    conn.execute("""INSERT INTO domains 
                        (domain_key, label, website, company, sender_email, sender_name, audience)
                        VALUES (%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (domain_key) DO UPDATE SET
                            label=EXCLUDED.label, website=EXCLUDED.website, company=EXCLUDED.company,
                            sender_email=EXCLUDED.sender_email, sender_name=EXCLUDED.sender_name,
                            audience=EXCLUDED.audience""",
                        (dkey, cfg['label'], cfg['website'], cfg['company'],
                         cfg['sender_email'], cfg['sender_name'], cfg['audience']))
                else:
                    conn.execute("DELETE FROM domains WHERE domain_key=?", (dkey,))
                    conn.execute("""INSERT INTO domains 
                        (domain_key, label, website, company, sender_email, sender_name, audience)
                        VALUES (?,?,?,?,?,?,?)""",
                        (dkey, cfg['label'], cfg['website'], cfg['company'],
                         cfg['sender_email'], cfg['sender_name'], cfg['audience']))
            except Exception as e:
                print(f"[seed_domains] upsert {dkey}: {e}")
            
            # Create default contact group if it does not exist
            try:
                group_name = cfg['group_name']
                existing = conn.execute(
                    "SELECT id FROM contact_groups WHERE name=?", (group_name,)).fetchone()
                if not existing:
                    conn.execute(
                        "INSERT INTO contact_groups (name, description, color, domain_key) VALUES (?,?,?,?)",
                        (group_name, f"Default leads group for {cfg['label']}", cfg.get('group_color', '#3b82f6'), dkey))
            except Exception as e:
                print(f"[seed_domains] group {dkey}: {e}")
        
        conn.commit()
        try: conn.close()
        except Exception: pass
        print(f"[seed_domains] OK: {len(DOMAIN_CONFIG)} domains + groups seeded")
    except Exception as e:
        print(f"[seed_domains] err: {e}")

seed_domains_and_default_groups()


def row_to_dict(row): return dict(row) if row else None
def rows_to_list(rows): return [dict(r) for r in rows]

# ─────────────────────────────────────────────
# EMAIL SENDING
# ─────────────────────────────────────────────
def _ensure_daily_send_count_table():
    """Defensive: create daily_send_count table if it does not exist.
    Works for both Postgres and SQLite."""
    try:
        conn = get_db()
        if USE_POSTGRES if "USE_POSTGRES" in globals() else False:
            conn.execute("""CREATE TABLE IF NOT EXISTS daily_send_count (
                date TEXT PRIMARY KEY,
                count INTEGER DEFAULT 0
            )""")
        else:
            conn.execute("""CREATE TABLE IF NOT EXISTS daily_send_count (
                date TEXT PRIMARY KEY,
                count INTEGER DEFAULT 0
            )""")
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[ensure_daily_send_count] {type(e).__name__}: {e}")


def get_todays_send_count():
    _ensure_daily_send_count_table()
    try:
        conn = get_db()
        today = datetime.utcnow().strftime("%Y-%m-%d")
        row = conn.execute("SELECT count FROM daily_send_count WHERE date=?", [today]).fetchone()
        conn.close()
        return row["count"] if row else 0
    except Exception as e:
        print(f"[get_todays_send_count] {type(e).__name__}: {e}")
        return 0

def increment_send_count():
    _ensure_daily_send_count_table()
    try:
        conn = get_db()
        today = datetime.utcnow().strftime("%Y-%m-%d")
        conn.execute("INSERT INTO daily_send_count (date, count) VALUES (?, 1) "
                     "ON CONFLICT(date) DO UPDATE SET count = count + 1", [today])
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[increment_send_count] {type(e).__name__}: {e}")

def personalize(text, lead):
    full_name = (lead.get("name") or "").strip()
    first_name = full_name.split()[0] if full_name else "there"
    # Smart company resolution: explicit column > email domain > fallback
    company = (lead.get("company") or "").strip()
    if not company:
        email = (lead.get("email") or "").strip()
        if "@" in email:
            domain = email.split("@")[1].lower()
            base = domain.split(".")[0]
            # Common transformations: maximaapparel → Maxima Apparel
            company = base.replace("-", " ").replace("_", " ").title()
        if not company:
            company = "your business"
    return (text.replace("{{first_name}}", first_name)
                .replace("{{name}}", first_name)
                .replace("{{sender_name}}", FROM_NAME)
                .replace("{{company}}", company)
                .replace("{{city}}", lead.get("city", "your area") or "your area")
                .replace("{{website}}", lead.get("website", "") or ""))

def inject_tracking(html_body, log_id):
    """Add tracking pixel + rewrite links for open/click tracking."""
    if not TRACKING_ENABLED or not log_id:
        return html_body
    import re as _re, urllib.parse as _up
    def _rewrite(m):
        url = m.group(1)
        if (APP_URL in url or url.startswith("mailto:") or url.startswith("#")
            or "unsubscribe" in url.lower()):
            return m.group(0)
        encoded = _up.quote(url, safe="")
        return 'href="' + APP_URL + '/track/click/' + str(log_id) + '?url=' + encoded + '"'
    html_body = _re.sub(r'href="(https?://[^"]+)"', _rewrite, html_body)
    pixel = '<img src="' + APP_URL + '/track/open/' + str(log_id) + '.png" width="1" height="1" style="display:none;border:0" alt=""/>'
    if "</body>" in html_body:
        html_body = html_body.replace("</body>", pixel + "</body>", 1)
    else:
        html_body = html_body + pixel
    return html_body


def send_via_zepto(to_email, to_name, subject, html_body, log_id=None, from_email=None, from_name=None):
    # Domain-aware sender resolution
    _from_email = from_email or _from_email
    _from_name  = from_name  or _from_name
    if not ZEPTO_TOKEN:
        return False, "ZEPTO_TOKEN not configured"
    if log_id and TRACKING_ENABLED:
        html_body = inject_tracking(html_body, log_id)
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": ZEPTO_TOKEN,
    }
    payload = {
        "from": {"address": _from_email, "name": _from_name},
        "to":   [{"email_address": {"address": to_email, "name": to_name or "there"}}],
        "reply_to": [{"address": REPLY_TO}],
        "subject":  subject,
        "htmlbody": html_body
    }
    if BCC_SUPPORT and to_email.lower() != REPLY_TO.lower():
        payload["bcc"] = [{"email_address": {"address": REPLY_TO, "name": "SKYMAXX (BCC)"}}]
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



def update_campaign_counters(campaign_id=None):
    """Recompute actually_sent/failed/replied counters for a campaign (or all campaigns).
    Also transitions status: approved → running (if any sends), → completed (if all leads done).
    Skips campaigns in: paused, cancelled, draft, pending_approval."""
    if campaign_id is None:
        # Update all active campaigns
        conn = get_db()
        camps = conn.execute(
            "SELECT id FROM campaigns WHERE status IN ('approved', 'running', 'scheduled')"
        ).fetchall()
        conn.close()
        for c in camps:
            update_campaign_counters(c["id"])
        return

    conn = get_db()
    camp = conn.execute("SELECT * FROM campaigns WHERE id=?", [campaign_id]).fetchone()
    if not camp:
        conn.close()
        return

    try:
        lead_ids = json.loads(camp["lead_ids_json"] or "[]")
        lead_ids = [int(x) for x in lead_ids if x]
    except Exception:
        lead_ids = []

    if not lead_ids:
        conn.close()
        return

    placeholders = ",".join("?" * len(lead_ids))

    # Count sends from email_log
    sent_count = conn.execute(
        f"SELECT COUNT(*) FROM email_log WHERE lead_id IN ({placeholders}) AND status='success'",
        lead_ids).fetchone()[0]
    failed_count = conn.execute(
        f"SELECT COUNT(*) FROM email_log WHERE lead_id IN ({placeholders}) AND status='failed'",
        lead_ids).fetchone()[0]

    # Replied & lead state counts
    replied_count = conn.execute(
        f"SELECT COUNT(*) FROM leads WHERE id IN ({placeholders}) AND replied=1",
        lead_ids).fetchone()[0]
    in_seq_count = conn.execute(
        f"SELECT COUNT(*) FROM leads WHERE id IN ({placeholders}) AND in_sequence=1",
        lead_ids).fetchone()[0]
    finished_seq = conn.execute(
        f"SELECT COUNT(*) FROM leads WHERE id IN ({placeholders}) AND sequence_step >= 5",
        lead_ids).fetchone()[0]
    unsubscribed = conn.execute(
        f"SELECT COUNT(*) FROM leads WHERE id IN ({placeholders}) AND unsubscribed=1",
        lead_ids).fetchone()[0]

    # Determine new status (do not override paused/cancelled/failed/scheduled)
    current_status = camp["status"]
    new_status = current_status
    if current_status not in ("paused", "cancelled", "failed", "draft", "pending_approval"):
        # Has any send happened?
        any_activity = sent_count > 0 or failed_count > 0
        # Are all leads done (replied, unsubscribed, finished sequence)?
        done_count = replied_count + unsubscribed + finished_seq
        # But avoid double counting — a lead can be both finished AND replied. Better:
        terminal_leads = conn.execute(
            f"""SELECT COUNT(*) FROM leads WHERE id IN ({placeholders})
                AND (replied=1 OR unsubscribed=1 OR sequence_step >= 5)""",
            lead_ids).fetchone()[0]

        if terminal_leads >= len(lead_ids):
            new_status = "completed"
        elif any_activity:
            new_status = "running"
        # else: keep as 'approved' (just enrolled, no sends yet)

    conn.execute(
        """UPDATE campaigns
           SET status=?, actually_sent=?, actually_failed=?, actually_replied=?
           WHERE id=?""",
        [new_status, sent_count, failed_count, replied_count, campaign_id])
    conn.commit()
    conn.close()



def _places_text_search_paginated(query, max_pages=3, max_results=60):
    """Fetch Google Maps Text Search results across multiple pages.
    Returns up to `max_results` combined results from up to `max_pages` pages.
    Handles Google's next_page_token activation delay with retries."""
    all_results = []
    next_token = None
    for page_num in range(max_pages):
        if next_token:
            # Google's next_page_token needs a few seconds to activate.
            # Retry with backoff if we get INVALID_REQUEST.
            resp = None
            for attempt in range(2):
                time.sleep(2 + attempt)  # 2s, 3s (keep search fast)
                try:
                    resp = requests.get(PLACES_TEXT_URL, params={
                        "key": GOOGLE_MAPS_API_KEY, "pagetoken": next_token
                    }, timeout=15).json()
                except Exception as e:
                    print(f"[places_paginated] page {page_num+1} attempt {attempt+1}: {e}")
                    continue
                status = resp.get("status")
                if status == "INVALID_REQUEST":
                    # token not ready yet — retry
                    continue
                break
            if resp is None:
                break
        else:
            try:
                resp = requests.get(PLACES_TEXT_URL, params={
                    "key": GOOGLE_MAPS_API_KEY, "query": query
                }, timeout=15).json()
            except Exception as e:
                print(f"[places_paginated] page 1: {e}")
                break
        if resp.get("status") not in ("OK", "ZERO_RESULTS"):
            print(f"[places_paginated] page {page_num+1} status={resp.get('status')}")
            break
        all_results.extend(resp.get("results", []))
        if len(all_results) >= max_results:
            all_results = all_results[:max_results]
            break
        next_token = resp.get("next_page_token")
        if not next_token:
            break
    return all_results


def process_pending_sends(max_per_run=None):

    # Cache effective templates per domain (avoid repeated DB queries in the loop)
    _templates_cache = {}
    def _get_tpls(dk):
        if dk not in _templates_cache:
            _templates_cache[dk] = get_effective_templates(dk)
        return _templates_cache[dk]
    # Backward compat: SKYMAXX templates available as default
    _effective_templates = _get_tpls('skymaxx')
    today_count = get_todays_send_count()
    if today_count >= DAILY_SEND_LIMIT:
        return
    remaining = DAILY_SEND_LIMIT - today_count
    if max_per_run is not None:
        remaining = min(remaining, max_per_run)

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
        # Resolve domain: prefer lead.domain_key, fallback to skymaxx
        lead_domain = lead.get("domain_key") or "skymaxx"
        if lead_domain not in SEQUENCE_TEMPLATES_BY_DOMAIN:
            lead_domain = "skymaxx"
        lead_tpls = _get_tpls(lead_domain)
        tpl = lead_tpls[next_step - 1]
        subject = personalize(tpl["subject"], lead)
        body    = personalize(tpl["body"],    lead)
        # Track which from-address to use
        lead_cfg = DOMAIN_CONFIG.get(lead_domain, DOMAIN_CONFIG["skymaxx"])

        # Insert log first to get log_id for tracking
        conn = get_db()
        cur = conn.execute("""INSERT INTO email_log (lead_id, step, to_email, subject, status, error_msg)
                        VALUES (?, ?, ?, ?, 'sending', '')""",
                     [lead["id"], next_step, lead["email"], subject])
        log_id = cur.lastrowid
        conn.commit(); conn.close()

        ok, err = send_via_zepto(lead["email"], lead["name"], subject, body,
                                  log_id=log_id,
                                  from_email=lead_cfg["sender_email"],
                                  from_name=lead_cfg["sender_name"])
        conn = get_db()
        conn.execute("UPDATE email_log SET status=?, error_msg=? WHERE id=?",
                     ["success" if ok else "failed", err or "", log_id])
        # Update parent campaign counters + status
        if lead.get("campaign_id"):
            try:
                conn.execute("""UPDATE campaigns SET
                    actually_sent = actually_sent + ?,
                    actually_failed = actually_failed + ?
                    WHERE id = ?""", [1 if ok else 0, 0 if ok else 1, lead["campaign_id"]])
                # Transition approved → running on first send
                conn.execute("""UPDATE campaigns SET status='running'
                    WHERE id=? AND status='approved'""", [lead["campaign_id"]])
            except Exception as ce:
                print(f"[counter] Campaign update err: {ce}")
        # Auto-update lead status
        if ok:
            conn.execute("UPDATE leads SET status='contacted' WHERE id=? AND status NOT IN ('replied','qualified','interested')",
                         [lead["id"]])
        if ok:
            increment_send_count()
            if next_step >= 5:
                conn.execute("UPDATE leads SET sequence_step=?, in_sequence=0 WHERE id=?",
                             [next_step, lead["id"]])
            else:
                next_tpl = lead_tpls[next_step]
                next_at = (datetime.utcnow() + timedelta(days=next_tpl["delay_days"])).isoformat()
                conn.execute("UPDATE leads SET sequence_step=?, next_send_at=? WHERE id=?",
                             [next_step, next_at, lead["id"]])
        conn.commit()
        conn.close()
        time.sleep(2)  # rate-limit between sends



# ═══════════════════════════════════════════════════════════════════════
# CRON ENDPOINT — call this every 5 min from an external cron service
# (e.g. cron-job.com, UptimeRobot) to keep Render awake AND process sends
# ═══════════════════════════════════════════════════════════════════════


@app.route("/api/admin/diag", methods=["GET"])
def admin_diag():
    """Comprehensive sequence/campaign health check."""
    conn = get_db()
    report = {}
    
    # Campaigns overview
    report["campaigns"] = []
    for c in rows_to_list(conn.execute("SELECT id, name, status, actually_sent, recipient_count, created_at FROM campaigns ORDER BY id DESC LIMIT 10").fetchall()):
        try:
            lids = json.loads(c.get("lead_ids_json") or "[]")
        except: lids = []
        if not lids:
            # fetch lead_ids_json
            row = conn.execute("SELECT lead_ids_json FROM campaigns WHERE id=?", [c["id"]]).fetchone()
            try: lids = json.loads(row[0] if row else "[]")
            except: lids = []
        c["lead_count"] = len(lids)
        report["campaigns"].append(c)

    # Leads breakdown — sequence_step distribution
    step_breakdown = rows_to_list(conn.execute("""
        SELECT sequence_step, in_sequence, replied, unsubscribed, COUNT(*) as cnt
        FROM leads
        GROUP BY sequence_step, in_sequence, replied, unsubscribed
        ORDER BY sequence_step
    """).fetchall())
    report["lead_step_distribution"] = step_breakdown
    
    # Email log breakdown by step
    log_breakdown = rows_to_list(conn.execute("""
        SELECT step, status, COUNT(*) as cnt FROM email_log
        GROUP BY step, status ORDER BY step, status
    """).fetchall())
    report["email_log_by_step"] = log_breakdown

    # Pending leads — what SHOULD be sent right now
    now = datetime.utcnow().isoformat()
    pending = rows_to_list(conn.execute("""
        SELECT id, name, email, sequence_step, next_send_at, campaign_id
        FROM leads
        WHERE in_sequence=1 AND unsubscribed=0 AND replied=0
          AND email IS NOT NULL AND email != ''
          AND (next_send_at IS NULL OR next_send_at <= ?)
          AND sequence_step < 5
        ORDER BY next_send_at ASC LIMIT 20
    """, [now]).fetchall())
    report["pending_now"] = pending
    report["pending_count"] = len(pending)
    report["server_time_utc"] = now

    # Future-pending leads (waiting their turn)
    future = rows_to_list(conn.execute("""
        SELECT id, name, sequence_step, next_send_at, campaign_id
        FROM leads
        WHERE in_sequence=1 AND unsubscribed=0 AND replied=0
          AND next_send_at > ?
          AND sequence_step < 5
        ORDER BY next_send_at ASC LIMIT 20
    """, [now]).fetchall())
    report["future_pending"] = future
    report["future_pending_count"] = len(future)
    
    # Stuck leads — in_sequence=1, sequence_step >= 1, but no next_send_at set
    stuck = rows_to_list(conn.execute("""
        SELECT id, name, sequence_step, next_send_at, in_sequence, campaign_id
        FROM leads
        WHERE in_sequence=1 AND sequence_step >= 1 AND sequence_step < 5
          AND next_send_at IS NULL
          AND replied=0 AND unsubscribed=0
    """).fetchall())
    report["stuck_no_next_send_at"] = stuck

    # Recent email log
    report["recent_emails"] = rows_to_list(conn.execute("""
        SELECT id, lead_id, step, to_email, subject, status, error_msg, sent_at
        FROM email_log ORDER BY id DESC LIMIT 20
    """).fetchall())

    # Daily send count
    today = datetime.utcnow().strftime("%Y-%m-%d")
    cnt_row = conn.execute("SELECT count FROM daily_send_count WHERE date=?", [today]).fetchone()
    report["today_send_count"] = cnt_row[0] if cnt_row else 0
    report["daily_limit"] = DAILY_SEND_LIMIT
    
    conn.close()
    return jsonify(report)




@app.route("/api/admin/force_send_one", methods=["POST"])
def admin_force_send_one():
    """Force-advance ONE lead's next_send_at to now and immediately process sequence sends.
    Use this to verify end-to-end that the sequence engine actually progresses to step 2+.
    
    POST body: {"lead_id": 123}  OR  {"campaign_id": 1, "limit": 1}
    """
    data = request.json or {}
    lead_id = data.get("lead_id")
    campaign_id = data.get("campaign_id")
    limit = int(data.get("limit") or 1)
    
    conn = get_db()
    if lead_id:
        rows = rows_to_list(conn.execute(
            "SELECT id, name, email, sequence_step, next_send_at FROM leads WHERE id=?",
            [lead_id]).fetchall())
    elif campaign_id:
        # Find lead_ids_json for the campaign
        row = conn.execute("SELECT lead_ids_json FROM campaigns WHERE id=?", [campaign_id]).fetchone()
        try:
            lids = json.loads(row[0]) if row and row[0] else []
            lids = [int(x) for x in lids]
        except: lids = []
        if not lids:
            conn.close()
            return jsonify({"error": "No leads in that campaign"}), 400
        # Get first N leads that are pending
        ph = ",".join("?" * len(lids))
        rows = rows_to_list(conn.execute(
            f"""SELECT id, name, email, sequence_step, next_send_at FROM leads
                WHERE id IN ({ph}) AND in_sequence=1 AND replied=0 AND unsubscribed=0
                AND sequence_step < 5 ORDER BY id LIMIT ?""",
            lids + [limit]).fetchall())
    else:
        conn.close()
        return jsonify({"error": "Provide lead_id or campaign_id"}), 400
    
    if not rows:
        conn.close()
        return jsonify({"error": "No eligible leads found"}), 404
    
    # Force their next_send_at to 1 minute ago
    now_minus_1min = (datetime.utcnow() - timedelta(minutes=1)).isoformat()
    target_ids = [r["id"] for r in rows]
    ph = ",".join("?" * len(target_ids))
    conn.execute(f"UPDATE leads SET next_send_at=? WHERE id IN ({ph})",
                 [now_minus_1min] + target_ids)
    conn.commit()
    conn.close()
    
    # Snapshot BEFORE state
    before = []
    for r in rows:
        before.append({"id": r["id"], "name": r.get("name"), "step": r.get("sequence_step"),
                       "next_send_at": r.get("next_send_at")})
    
    # Run process_pending_sends with limit
    try:
        process_pending_sends(max_per_run=limit)
    except Exception as e:
        return jsonify({"error": "process_pending_sends raised", "detail": str(e)}), 500
    
    # Snapshot AFTER state
    conn = get_db()
    after = rows_to_list(conn.execute(
        f"SELECT id, name, sequence_step, next_send_at, in_sequence FROM leads WHERE id IN ({ph})",
        target_ids).fetchall())
    # Get fresh email_log entries
    logs = rows_to_list(conn.execute(
        f"""SELECT id, lead_id, step, to_email, subject, status, error_msg, sent_at
            FROM email_log WHERE lead_id IN ({ph}) ORDER BY id DESC LIMIT 10""",
        target_ids).fetchall())
    conn.close()
    
    return jsonify({
        "before": before,
        "after": after,
        "recent_logs": logs,
        "triggered_at": now_minus_1min,
        "note": "Forced next_send_at to 1 min ago, then ran process_pending_sends"
    })

@app.route("/api/admin/cron_trigger", methods=["POST"])
def admin_cron_trigger():
    """Manually trigger the cron processor and return what it did."""
    before = None
    try:
        conn = get_db()
        before = conn.execute(
            "SELECT COUNT(*) FROM email_log").fetchone()[0]
        conn.close()
    except: pass
    
    try:
        process_pending_sends()
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
    after = None
    try:
        conn = get_db()
        after = conn.execute("SELECT COUNT(*) FROM email_log").fetchone()[0]
        # Get most recent log entries
        recent = rows_to_list(conn.execute(
            "SELECT id, lead_id, step, to_email, status, sent_at FROM email_log ORDER BY id DESC LIMIT 5"
        ).fetchall())
        conn.close()
    except: pass
    
    return jsonify({
        "email_log_before": before,
        "email_log_after": after,
        "sent_this_run": (after - before) if (before is not None and after is not None) else None,
        "recent_logs": recent if 'recent' in dir() else []
    })


@app.route("/api/cron/process", methods=["GET", "POST"])
def cron_process():
    """External-cron-driven processor. Call from cron-job.com every 5 min.
    Processes: (a) pending email sends, (b) inbox replies via Microsoft Graph."""
    started = datetime.utcnow().isoformat()
    report = {
        "started_at":   started,
        "completed_at": None,
        "ok":           True,
        "sends": {"before_pending": 0, "after_pending": 0, "sent_this_run": 0, "error": None},
        "replies": {"processed": 0, "error": None},
    }

    # --- Process pending sends ---
    try:
        conn = get_db()
        now_iso = datetime.utcnow().isoformat()
        before_pending = conn.execute("""
            SELECT COUNT(*) FROM leads
            WHERE in_sequence=1 AND unsubscribed=0 AND replied=0
              AND email IS NOT NULL AND email != ''
              AND (next_send_at IS NULL OR next_send_at <= ?)
              AND sequence_step < 5
        """, [now_iso]).fetchone()[0]
        before_sent = conn.execute("SELECT COUNT(*) FROM email_log WHERE status='success'").fetchone()[0]
        conn.close()

        report["sends"]["before_pending"] = before_pending
        # Cap to 8 sends per cron run (fits in Render's 30s HTTP budget; cron runs every 5min anyway)
        process_pending_sends(max_per_run=8)

        conn = get_db()
        after_pending = conn.execute("""
            SELECT COUNT(*) FROM leads
            WHERE in_sequence=1 AND unsubscribed=0 AND replied=0
              AND email IS NOT NULL AND email != ''
              AND (next_send_at IS NULL OR next_send_at <= ?)
              AND sequence_step < 5
        """, [datetime.utcnow().isoformat()]).fetchone()[0]
        after_sent = conn.execute("SELECT COUNT(*) FROM email_log WHERE status='success'").fetchone()[0]
        conn.close()

        report["sends"]["after_pending"] = after_pending
        report["sends"]["sent_this_run"] = after_sent - before_sent
    except Exception as e:
        report["sends"]["error"] = str(e)[:300]
        report["ok"] = False

    # --- Process replies (if Microsoft Graph configured) ---
    try:
        if "process_replies" in globals():
            process_replies()
            report["replies"]["processed"] = 1
    except Exception as e:
        report["replies"]["error"] = str(e)[:300]

    # --- Update campaign counters + auto-transition statuses ---
    try:
        update_campaign_counters()
        report["campaigns_updated"] = True
    except Exception as e:
        report["campaigns_updated"] = False
        report["campaign_error"] = str(e)[:300]

    report["completed_at"] = datetime.utcnow().isoformat()
    return jsonify(report)


# ═══════════════════════════════════════════════════════════════════════
# DEBUG: Inspect campaign + leads state in one call
# ═══════════════════════════════════════════════════════════════════════
@app.route("/api/debug/campaign/<int:cid>")
def debug_campaign(cid):
    """Returns full campaign + all referenced leads with their current sequence state."""
    conn = get_db()
    camp_row = conn.execute("SELECT * FROM campaigns WHERE id=?", [cid]).fetchone()
    if not camp_row:
        conn.close()
        return jsonify({"error": "campaign not found"}), 404

    camp = dict(camp_row)
    try:
        lead_ids = json.loads(camp.get("lead_ids_json") or "[]")
    except Exception:
        lead_ids = []
    lead_ids = [int(x) for x in lead_ids if x]

    leads = []
    if lead_ids:
        placeholders = ",".join("?" * len(lead_ids))
        leads = rows_to_list(conn.execute(
            f"""SELECT id, name, email, in_sequence, sequence_step, next_send_at,
                       replied, unsubscribed, campaign_id, status
                FROM leads WHERE id IN ({placeholders})""",
            lead_ids).fetchall())

    # Email log entries for this campaign's leads
    log_entries = []
    if lead_ids:
        placeholders = ",".join("?" * len(lead_ids))
        log_entries = rows_to_list(conn.execute(
            f"""SELECT id, lead_id, step, to_email, status, sent_at, error_msg
                FROM email_log WHERE lead_id IN ({placeholders})
                ORDER BY sent_at DESC LIMIT 50""",
            lead_ids).fetchall())

    conn.close()
    return jsonify({
        "campaign":         camp,
        "lead_ids_in_json": lead_ids,
        "lead_ids_count":   len(lead_ids),
        "leads_found":      len(leads),
        "leads_in_sequence": sum(1 for l in leads if l.get("in_sequence")),
        "leads_with_campaign_id": sum(1 for l in leads if l.get("campaign_id") == cid),
        "leads":            leads,
        "email_log":        log_entries,
        "log_count":        len(log_entries),
    })


# ═══════════════════════════════════════════════════════════════════════
# DEBUG: Reset campaign to pending_approval (to allow re-approve)
# ═══════════════════════════════════════════════════════════════════════
@app.route("/api/debug/reset_campaign/<int:cid>", methods=["POST"])
def reset_campaign(cid):
    """Reset campaign to 'pending_approval' + clear in_sequence on its leads."""
    conn = get_db()
    camp = conn.execute("SELECT * FROM campaigns WHERE id=?", [cid]).fetchone()
    if not camp:
        conn.close()
        return jsonify({"error": "not found"}), 404

    try:
        lead_ids = json.loads(camp["lead_ids_json"] or "[]")
    except Exception:
        lead_ids = []
    lead_ids = [int(x) for x in lead_ids if x]

    leads_reset = 0
    if lead_ids:
        placeholders = ",".join("?" * len(lead_ids))
        conn.execute(
            f"""UPDATE leads
                SET in_sequence=0, sequence_step=0, next_send_at=NULL, campaign_id=NULL
                WHERE id IN ({placeholders})""",
            lead_ids)
        leads_reset = len(lead_ids)

    conn.execute("""UPDATE campaigns
        SET status='pending_approval', approved_at=NULL, approved_by=NULL, actually_started=0
        WHERE id=?""", [cid])
    conn.commit()
    conn.close()

    return jsonify({
        "reset":        True,
        "campaign_id":  cid,
        "leads_reset":  leads_reset,
        "next_step":    "POST /api/campaigns/" + str(cid) + "/approve to re-enroll leads"
    })


# ═══════════════════════════════════════════════════════════════════════
# DEBUG: Send a single test email to verify Zepto is configured + working
# ═══════════════════════════════════════════════════════════════════════
@app.route("/api/debug/test_zepto", methods=["POST"])
def debug_test_zepto():
    """Send a tiny test email to verify ZeptoMail credentials work."""
    data = request.json or {}
    to_email = (data.get("to") or "").strip()
    if not to_email:
        return jsonify({"error": "Provide 'to' in body"}), 400
    try:
        ok, err = send_via_zepto(
            to_email, "Test Recipient",
            "SKYMAXX Test Email — please ignore",
            "<p>This is a test from SKYMAXX cron diagnostics.</p>",
            log_id=None)
        return jsonify({"ok": ok, "error": err or None, "to": to_email})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:300]}), 500




@app.route("/api/debug/fix_campaign_leads/<int:cid>", methods=["POST"])
def debug_fix_campaign_leads(cid):
    """Replace this campaign's stale lead_ids_json with current valid leads (with email).
    Use this when the original lead IDs were deleted (e.g. after cleanup_dupes).
    Optionally provide ?ids=72,73,74 in body to use specific IDs instead."""
    conn = get_db()
    camp = conn.execute("SELECT * FROM campaigns WHERE id=?", [cid]).fetchone()
    if not camp:
        conn.close()
        return jsonify({"error": "campaign not found"}), 404

    data = request.json or {}
    specific_ids = data.get("lead_ids")  # optional

    if specific_ids and isinstance(specific_ids, list):
        try:
            valid_ids = [int(x) for x in specific_ids]
        except Exception:
            conn.close()
            return jsonify({"error": "lead_ids must be integers"}), 400
    else:
        # Default: all leads with email, not unsubscribed, not replied
        rows = conn.execute("""SELECT id FROM leads
            WHERE email IS NOT NULL AND email != ''
              AND unsubscribed=0 AND replied=0
            ORDER BY id""").fetchall()
        valid_ids = [r["id"] for r in rows]

    # Reset campaign state + replace IDs
    conn.execute("""UPDATE campaigns
        SET lead_ids_json=?, recipient_count=?, status='pending_approval',
            approved_at=NULL, approved_by=NULL, actually_started=0
        WHERE id=?""", [json.dumps(valid_ids), len(valid_ids), cid])
    conn.commit()
    conn.close()

    return jsonify({
        "fixed":           True,
        "campaign_id":     cid,
        "new_lead_count":  len(valid_ids),
        "new_lead_ids":    valid_ids[:30],
        "next_step":       "POST /api/campaigns/" + str(cid) + "/approve to enroll these leads"
    })


@app.route("/api/debug/delete_campaign/<int:cid>", methods=["POST"])
def debug_delete_campaign(cid):
    """Delete a campaign + clear in_sequence on any leads currently linked to it."""
    conn = get_db()
    conn.execute("""UPDATE leads
        SET in_sequence=0, sequence_step=0, next_send_at=NULL, campaign_id=NULL
        WHERE campaign_id=?""", [cid])
    conn.execute("DELETE FROM campaigns WHERE id=?", [cid])
    conn.commit()
    conn.close()
    return jsonify({"deleted": True, "campaign_id": cid})


@app.route("/api/debug/ensure_schema", methods=["POST", "GET"])
def debug_ensure_schema():
    """Run all CREATE TABLE IF NOT EXISTS statements + verify each table exists.
    Use this if you suspect schema drift."""
    results = {}
    tables_to_check = ["leads", "campaigns", "email_log", "sequences",
                       "daily_send_count", "tracking_events",
                       "contact_groups", "lead_group_assignments"]

    # Ensure daily_send_count (the known-missing one)
    _ensure_daily_send_count_table()

    # Verify each table exists
    conn = get_db()
    for tbl in tables_to_check:
        try:
            conn.execute(f"SELECT 1 FROM {tbl} LIMIT 1").fetchone()
            results[tbl] = "ok"
        except Exception as e:
            results[tbl] = f"MISSING: {type(e).__name__}: {str(e)[:120]}"
    conn.close()

    return jsonify({"tables": results, "checked_at": datetime.utcnow().isoformat()})


# Start scheduler thread
threading.Thread(target=scheduler_loop, daemon=True).start()

# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────

# ───────────────────────────────────────────────────────────────────────
# Orange Slice MCP Client — LinkedIn lead search (1.15B profiles)
# ───────────────────────────────────────────────────────────────────────

# ───────────────────────────────────────────────────────────────────────
# CREDIT SAFETY LOCK — set to True to block all credit-consuming Orange Slice calls
# This protects against unexpected billing while we evaluate the service.
# Set ORANGE_SLICE_CREDITS_LOCKED env var to "false" to re-enable.
# ───────────────────────────────────────────────────────────────────────
ORANGE_SLICE_CREDITS_LOCKED = os.getenv("ORANGE_SLICE_CREDITS_LOCKED", "true").lower() != "false"

class OrangeSliceClient:
    """JSON-RPC over SSE client for orangeslice.ai MCP server."""
    URL = "https://www.orangeslice.ai/mcp"

    def __init__(self):
        self.api_key = os.getenv("ORANGESLICE_API_KEY", "").strip()

    def is_configured(self):
        return bool(self.api_key)

    def call(self, tool_name, args, timeout=60):
        """Call an Orange Slice MCP tool. Returns parsed result or {"_error": str}."""
        if not self.api_key:
            return {"_error": "ORANGESLICE_API_KEY not set"}
        payload = {
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": tool_name, "arguments": args},
        }
        import urllib.request as _ur, urllib.error as _ue
        req = _ur.Request(self.URL,
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
            method="POST")
        try:
            r = _ur.urlopen(req, timeout=timeout)
            body = r.read().decode()
        except _ue.HTTPError as e:
            return {"_error": f"HTTP {e.code}: {e.read().decode()[:300]}"}
        except Exception as e:
            return {"_error": str(e)[:300]}

        # Parse SSE format: lines like "event: message" and "data: {json}"
        parsed = None
        for line in body.split("\n"):
            if line.startswith("data: "):
                try:
                    parsed = json.loads(line[6:])
                    break
                except Exception:
                    pass
        if parsed is None:
            try:
                parsed = json.loads(body)
            except Exception:
                return {"_error": "Could not parse response", "_body": body[:400]}

        if "error" in parsed:
            return {"_error": json.dumps(parsed["error"])[:400]}

        # Extract content text — Orange Slice returns result.content[].text as JSON string
        content = parsed.get("result", {}).get("content", [])
        for c in content:
            if c.get("type") == "text":
                try:
                    return json.loads(c.get("text", "{}"))
                except Exception:
                    return {"_raw": c.get("text", "")}
        return parsed.get("result", {})


_orange = OrangeSliceClient()

@app.route("/")
def index(): return render_template("index.html")

@app.route("/api/stats")
def stats():
    """Dashboard stats — bulletproof, never raises 500. Includes per-domain breakdown + 7-day trend."""
    def _safe_count(sql, default=0):
        try:
            c = get_db()
            try:
                return c.execute(sql).fetchone()[0]
            finally:
                try: c.close()
                except: pass
        except Exception as e:
            print(f"[stats] {sql[:50]}... → {type(e).__name__}: {e}")
            return default

    def _safe_call(fn, default=0):
        try:
            return fn()
        except Exception as e:
            print(f"[stats] {fn.__name__ if hasattr(fn,'__name__') else 'fn'} → {type(e).__name__}: {e}")
            return default

    def _safe_rows(sql, default=None):
        try:
            c = get_db()
            try:
                rows = c.execute(sql).fetchall()
                return rows_to_list(rows) if rows else (default or [])
            finally:
                try: c.close()
                except: pass
        except Exception as e:
            print(f"[stats] rows {sql[:60]}... → {type(e).__name__}: {e}")
            return default or []

    # Cross-check: count from email_log using TODAY (UTC) — alternative to daily_send_count
    today_utc = datetime.utcnow().strftime("%Y-%m-%d")
    today_from_log = _safe_count(
        f"SELECT COUNT(*) FROM email_log WHERE status='success' AND DATE(sent_at)='{today_utc}'"
    )

    # Per-domain sent counts (via campaigns join)
    sent_by_domain = {}
    try:
        rows = _safe_rows("""SELECT c.domain_key AS dk, COUNT(el.id) AS cnt
                             FROM email_log el
                             LEFT JOIN leads l ON el.lead_id = l.id
                             LEFT JOIN campaigns c ON l.campaign_id = c.id
                             WHERE el.status='success'
                             GROUP BY c.domain_key""")
        for r in rows:
            dk = (r.get("dk") if isinstance(r, dict) else r[0]) or "skymaxx"
            cnt = r.get("cnt") if isinstance(r, dict) else r[1]
            sent_by_domain[dk] = int(cnt or 0)
    except Exception as e:
        print(f"[stats] sent_by_domain err: {e}")
        sent_by_domain = {}
    # Ensure all configured domains present (even with 0)
    for dk in DOMAIN_CONFIG.keys():
        if dk not in sent_by_domain:
            sent_by_domain[dk] = 0

    # Last 7 days trend (success only) — for charting in UI
    sent_last_7d = []
    try:
        rows = _safe_rows(f"""SELECT DATE(sent_at) AS d, COUNT(*) AS cnt
                              FROM email_log
                              WHERE status='success' AND sent_at >= '{(datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")}'
                              GROUP BY DATE(sent_at) ORDER BY d""")
        for r in rows:
            sent_last_7d.append({
                "date": str(r.get("d") if isinstance(r, dict) else r[0]),
                "count": int(r.get("cnt") if isinstance(r, dict) else r[1] or 0)
            })
    except Exception as e:
        print(f"[stats] 7d trend err: {e}")

    # Per-domain lead counts
    leads_by_domain = {}
    try:
        rows = _safe_rows("SELECT COALESCE(domain_key,'skymaxx') AS dk, COUNT(*) AS cnt FROM leads GROUP BY domain_key")
        for r in rows:
            dk = (r.get("dk") if isinstance(r, dict) else r[0]) or "skymaxx"
            cnt = r.get("cnt") if isinstance(r, dict) else r[1]
            leads_by_domain[dk] = int(cnt or 0)
    except Exception as e:
        print(f"[stats] leads_by_domain err: {e}")
    for dk in DOMAIN_CONFIG.keys():
        if dk not in leads_by_domain:
            leads_by_domain[dk] = 0

    # Active campaigns by domain
    active_campaigns_by_domain = {}
    try:
        rows = _safe_rows("""SELECT COALESCE(domain_key,'skymaxx') AS dk, COUNT(*) AS cnt
                             FROM campaigns WHERE status IN ('approved','running')
                             GROUP BY domain_key""")
        for r in rows:
            dk = (r.get("dk") if isinstance(r, dict) else r[0]) or "skymaxx"
            cnt = r.get("cnt") if isinstance(r, dict) else r[1]
            active_campaigns_by_domain[dk] = int(cnt or 0)
    except Exception as e:
        print(f"[stats] active_campaigns err: {e}")
    for dk in DOMAIN_CONFIG.keys():
        if dk not in active_campaigns_by_domain:
            active_campaigns_by_domain[dk] = 0

    s = {
        # Existing fields (backward compatible)
        "total_leads":   _safe_count("SELECT COUNT(*) FROM leads"),
        "in_sequence":   _safe_count("SELECT COUNT(*) FROM leads WHERE in_sequence=1"),
        "with_email":    _safe_count("SELECT COUNT(*) FROM leads WHERE email IS NOT NULL AND email != ''"),
        "replied":       _safe_count("SELECT COUNT(*) FROM leads WHERE replied=1"),
        "today_sent":    _safe_call(get_todays_send_count) if "get_todays_send_count" in globals() else 0,
        "daily_limit":   DAILY_SEND_LIMIT if "DAILY_SEND_LIMIT" in globals() else 300,
        "bcc_support":   BCC_SUPPORT if "BCC_SUPPORT" in globals() else True,
        "total_sent":    _safe_count("SELECT COUNT(*) FROM email_log WHERE status='success'"),
        "total_failed":  _safe_count("SELECT COUNT(*) FROM email_log WHERE status='failed'"),
        # NEW: enhanced visibility
        "today_sent_from_log":      today_from_log,  # cross-check with daily_send_count
        "sent_by_domain":           sent_by_domain,
        "leads_by_domain":          leads_by_domain,
        "active_campaigns_by_domain": active_campaigns_by_domain,
        "sent_last_7d":             sent_last_7d,
        "total_campaigns":          _safe_count("SELECT COUNT(*) FROM campaigns"),
        "active_campaigns":         _safe_count("SELECT COUNT(*) FROM campaigns WHERE status IN ('approved','running')"),
        "total_groups":             _safe_count("SELECT COUNT(*) FROM contact_groups"),
        "total_sending_pending":    _safe_count("SELECT COUNT(*) FROM email_log WHERE status='sending'"),
        "as_of_utc":                datetime.utcnow().isoformat() + "Z",
    }
    return jsonify(s)

@app.route("/api/cities")
def cities(): return jsonify(UAE_GCC_CITIES)



@app.route("/api/debug/test_insert")
def debug_test_insert():
    """Test INSERT with company field directly."""
    import time as _t
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO leads (name, email, company, title, source, status) VALUES (?, ?, ?, ?, ?, ?)",
            ["Test User", f"test_{int(_t.time())}@debug.local", "Test Company Inc", "Test CTO", "uploaded", "new"]
        )
        conn.commit()
        new_id = cur.lastrowid
        # Read it back
        row = conn.execute("SELECT id, name, email, company, title FROM leads WHERE id = ?", [new_id]).fetchone()
        result = {"insert_ok": True, "lastrowid": new_id, "readback": dict(row) if row else None}
    except Exception as e:
        result = {"insert_ok": False, "error": str(e)[:300]}
    finally:
        conn.close()
    return jsonify(result)


@app.route("/api/debug/cleanup_dupes", methods=["POST"])
def debug_cleanup_dupes():
    """Delete all leads from the database (CAUTION — full reset)."""
    conn = get_db()
    try:
        # First, count what we have
        before = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        # Delete from related tables first to avoid FK issues
        conn.execute("DELETE FROM lead_group_assignments")
        conn.execute("DELETE FROM email_log")
        conn.execute("DELETE FROM tracking_events")
        conn.execute("DELETE FROM leads")
        conn.commit()
        result = {"ok": True, "deleted": before}
    except Exception as e:
        result = {"ok": False, "error": str(e)[:300]}
    finally:
        conn.close()
    return jsonify(result)

@app.route("/api/debug/db")
def debug_db():
    """Diagnostic — tells us which DB is in use and why."""
    import sys as _sys
    info = {
        "USE_POSTGRES": bool(USE_POSTGRES),
        "DATABASE_URL_set": bool(DATABASE_URL),
        "DATABASE_URL_prefix": DATABASE_URL[:30] if DATABASE_URL else "",
        "python_version": _sys.version,
    }
    # Try importing psycopg2
    try:
        import psycopg2
        info["psycopg2_importable"] = True
        info["psycopg2_version"] = psycopg2.__version__
    except ImportError as e:
        info["psycopg2_importable"] = False
        info["psycopg2_error"] = str(e)
    # Try a live DB query
    try:
        conn = get_db()
        cur = conn.execute("SELECT COUNT(*) FROM leads")
        row = cur.fetchone()
        info["leads_count"] = row[0] if row else 0
        info["db_query_works"] = True
        conn.close()
    except Exception as e:
        info["db_query_works"] = False
        info["db_query_error"] = str(e)[:300]
    return jsonify(info)

@app.route("/api/sequence/save_template", methods=["POST"])
def save_template():
    """Persist a manual edit to a sequence template. Body: {step, subject, body, domain}."""
    data = request.json or {}
    try:
        step = int(data.get("step", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "invalid step"}), 400
    subject    = (data.get("subject") or "").strip()
    body       = (data.get("body") or "").strip()
    domain_key = (data.get("domain") or "skymaxx").strip().lower()
    if domain_key not in SEQUENCE_TEMPLATES_BY_DOMAIN:
        return jsonify({"error": f"unknown domain: {domain_key}"}), 400
    if not (1 <= step <= len(SEQUENCE_TEMPLATES_BY_DOMAIN[domain_key])):
        return jsonify({"error": f"step must be 1..{len(SEQUENCE_TEMPLATES_BY_DOMAIN[domain_key])}"}), 400
    if not subject or not body:
        return jsonify({"error": "subject and body are required"}), 400
    if len(subject) > 500:
        return jsonify({"error": "subject too long (max 500 chars)"}), 400
    if len(body) > 200000:
        return jsonify({"error": "body too long (max 200k chars)"}), 400
    
    from flask import session as _session
    user = _session.get("user", "admin") if _session else "admin"
    try:
        conn = get_db()
        if USE_POSTGRES:
            conn.execute(
                """INSERT INTO template_overrides (step, domain_key, subject, body, updated_at, updated_by)
                   VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, %s)
                   ON CONFLICT (domain_key, step) DO UPDATE SET subject=EXCLUDED.subject, body=EXCLUDED.body,
                       updated_at=CURRENT_TIMESTAMP, updated_by=EXCLUDED.updated_by""",
                (step, domain_key, subject, body, user))
        else:
            conn.execute("DELETE FROM template_overrides WHERE step=? AND domain_key=?", (step, domain_key))
            conn.execute(
                "INSERT INTO template_overrides (step, domain_key, subject, body, updated_by) VALUES (?,?,?,?,?)",
                (step, domain_key, subject, body, user))
        conn.commit()
        try: conn.close()
        except Exception: pass
        return jsonify({"ok": True, "step": step, "domain": domain_key, "saved_by": user})
    except Exception as e:
        return jsonify({"error": f"save failed: {e}"}), 500

@app.route("/api/sequence/reset_template/<int:step>", methods=["POST"])
def reset_template(step):
    """Remove the override for a step in a domain, reverting to the code default."""
    domain_key = (request.args.get("domain") or "skymaxx").strip().lower()
    if domain_key not in SEQUENCE_TEMPLATES_BY_DOMAIN:
        return jsonify({"error": f"unknown domain: {domain_key}"}), 400
    if not (1 <= step <= len(SEQUENCE_TEMPLATES_BY_DOMAIN[domain_key])):
        return jsonify({"error": f"step must be 1..{len(SEQUENCE_TEMPLATES_BY_DOMAIN[domain_key])}"}), 400
    try:
        conn = get_db()
        if USE_POSTGRES:
            conn.execute("DELETE FROM template_overrides WHERE step=%s AND domain_key=%s", (step, domain_key))
        else:
            conn.execute("DELETE FROM template_overrides WHERE step=? AND domain_key=?", (step, domain_key))
        conn.commit()
        try: conn.close()
        except Exception: pass
        return jsonify({"ok": True, "step": step, "domain": domain_key})
    except Exception as e:
        return jsonify({"error": f"reset failed: {e}"}), 500

@app.route("/api/domains")
def list_domains():
    """List all configured domains for selection in UI (campaigns, sequences, groups)."""
    out = []
    for dkey, cfg in DOMAIN_CONFIG.items():
        out.append({
            "key":           dkey,
            "label":         cfg["label"],
            "website":       cfg["website"],
            "website_display": cfg["website_display"],
            "company":       cfg["company"],
            "sender_email":  cfg["sender_email"],
            "sender_name":   cfg["sender_name"],
            "tagline":       cfg["tagline"],
            "audience":      cfg["audience"],
            "accent":        cfg["accent"],
            "group_name":    cfg["group_name"],
        })
    return jsonify({"domains": out})

@app.route("/api/sequence/templates")
def get_templates():
    dk = (request.args.get("domain") or "skymaxx").strip().lower()
    return jsonify(get_effective_templates(dk))

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
    # Attach group memberships
    if items:
        ids = [l["id"] for l in items]
        placeholders = ",".join("?" * len(ids))
        memberships = conn.execute(f"""SELECT lga.lead_id, g.id, g.name, g.color
            FROM lead_group_assignments lga JOIN contact_groups g ON g.id = lga.group_id
            WHERE lga.lead_id IN ({placeholders})""", ids).fetchall()
        group_map = {}
        for m in memberships:
            group_map.setdefault(m["lead_id"], []).append({"id": m["id"], "name": m["name"], "color": m["color"]})
        for l in items:
            l["groups"] = group_map.get(l["id"], [])
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


# ─────────────────────────────────────────────
# MICROSOFT GRAPH API — REPLY DETECTION
# ─────────────────────────────────────────────
import urllib.parse as _urlparse

AZURE_TENANT_ID     = os.getenv("AZURE_TENANT_ID", "")
AZURE_CLIENT_ID     = os.getenv("AZURE_CLIENT_ID", "")
AZURE_CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET", "")
MAILBOX_EMAIL       = os.getenv("MAILBOX_EMAIL", "support@skymaxx.company")
REPLY_POLL_MINUTES  = int(os.getenv("REPLY_POLL_MINUTES", "5"))

_graph_token_cache = {"token": None, "expires_at": 0}

def get_graph_token():
    """Get cached or fresh OAuth token for Microsoft Graph."""
    now = time.time()
    if _graph_token_cache["token"] and now < _graph_token_cache["expires_at"] - 60:
        return _graph_token_cache["token"]
    if not (AZURE_TENANT_ID and AZURE_CLIENT_ID and AZURE_CLIENT_SECRET):
        return None
    url = f"https://login.microsoftonline.com/{AZURE_TENANT_ID}/oauth2/v2.0/token"
    body = _urlparse.urlencode({
        "client_id":     AZURE_CLIENT_ID,
        "client_secret": AZURE_CLIENT_SECRET,
        "scope":         "https://graph.microsoft.com/.default",
        "grant_type":    "client_credentials",
    }).encode()
    try:
        r = requests.post(url, data=body, headers={"Content-Type":"application/x-www-form-urlencoded"}, timeout=20)
        if r.status_code == 200:
            d = r.json()
            _graph_token_cache["token"]      = d["access_token"]
            _graph_token_cache["expires_at"] = now + d.get("expires_in", 3600)
            return d["access_token"]
        print(f"[graph] Token fetch failed: {r.status_code} {r.text[:200]}")
    except Exception as e:
        print(f"[graph] Token error: {e}")
    return None

def fetch_recent_replies(minutes_ago=10):
    """Fetch emails received in the last N minutes from MAILBOX_EMAIL."""
    token = get_graph_token()
    if not token: return []
    since_iso = (datetime.utcnow() - timedelta(minutes=minutes_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
    url = (f"https://graph.microsoft.com/v1.0/users/{MAILBOX_EMAIL}/messages"
           f"?$filter=receivedDateTime ge {since_iso}"
           f"&$select=from,subject,receivedDateTime,internetMessageId"
           f"&$top=50&$orderby=receivedDateTime desc")
    try:
        r = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=20)
        if r.status_code == 200:
            return r.json().get("value", [])
        print(f"[graph] Messages fetch failed: {r.status_code} {r.text[:200]}")
    except Exception as e:
        print(f"[graph] Messages error: {e}")
    return []

def process_replies():
    """Check inbox for replies from leads and auto-pause their sequences."""
    if not (AZURE_TENANT_ID and AZURE_CLIENT_ID and AZURE_CLIENT_SECRET):
        return  # Not configured
    messages = fetch_recent_replies(REPLY_POLL_MINUTES * 2)  # slight overlap to avoid misses
    if not messages: return

    conn = get_db()
    matched = 0
    for msg in messages:
        sender = (msg.get("from", {}).get("emailAddress", {}).get("address", "") or "").lower().strip()
        if not sender: continue

        # Match sender against any lead with status not already 'replied'
        row = conn.execute("SELECT id, name FROM leads WHERE LOWER(email)=? AND replied=0", [sender]).fetchone()
        if not row: continue

        lead_id, name = row["id"], row["name"]
        subject = msg.get("subject", "")[:200]

        # Mark as replied, pause sequence, change status
        conn.execute("UPDATE leads SET replied=1, in_sequence=0, status='qualified' WHERE id=?", [lead_id])
        conn.execute("""INSERT INTO email_log (lead_id, step, to_email, subject, status, error_msg)
                        VALUES (?, 0, ?, ?, 'reply_detected', ?)""",
                     [lead_id, sender, "REPLY: " + subject, msg.get("receivedDateTime", "")])

        # Send auto-acknowledgment
        ack_subject = AUTO_REPLY_TEMPLATE["subject"]
        ack_body    = AUTO_REPLY_TEMPLATE["body"].replace("{{name}}", (name.split()[0] if name else "there"))
        send_via_zepto(sender, name, ack_subject, ack_body)

        matched += 1
        print(f"[reply-detected] {sender} ({name}) — sequence paused, auto-ack sent")

    if matched:
        conn.commit()
    conn.close()
    return matched

def reply_poller_loop():
    """Background thread: polls inbox every REPLY_POLL_MINUTES."""
    while True:
        try:
            n = process_replies()
            if n: print(f"[reply-poller] Detected {n} reply(ies)")
        except Exception as e:
            print(f"[reply-poller] Error: {e}")
        time.sleep(REPLY_POLL_MINUTES * 60)

# Start reply detection thread if configured
if AZURE_TENANT_ID and AZURE_CLIENT_ID and AZURE_CLIENT_SECRET:
    threading.Thread(target=reply_poller_loop, daemon=True).start()
    print(f"[reply-poller] Started — polling {MAILBOX_EMAIL} every {REPLY_POLL_MINUTES} min")

# ── Manual trigger endpoint ──
@app.route("/api/replies/poll", methods=["POST"])
def manual_poll_replies():
    n = process_replies()
    return jsonify({"detected": n or 0})

# ── Replies status endpoint ──
@app.route("/api/replies/status")
def replies_status():
    return jsonify({
        "configured":   bool(AZURE_TENANT_ID and AZURE_CLIENT_ID and AZURE_CLIENT_SECRET),
        "mailbox":      MAILBOX_EMAIL,
        "poll_minutes": REPLY_POLL_MINUTES,
    })


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
            conn.execute("""INSERT OR IGNORE INTO leads (name,email,phone,website,city,country,company,title,source,status)
                VALUES (?,?,?,?,?,?,?,?,'uploaded','new')""",
                [row.get("name","").strip(), row.get("email","").strip(),
                 row.get("phone","").strip(), row.get("website","").strip(),
                 row.get("city","").strip(), row.get("country","").strip(),
                 row.get("company","").strip(), row.get("title","").strip()])
            if conn.execute("SELECT changes()").fetchone()[0]: imported += 1
        except Exception: pass
    conn.commit(); conn.close()
    return jsonify({"imported": imported})

# ── BULK SET SEQUENCE STEP (for leads already sent outside the app) ──
@app.route("/api/sequence/set_step", methods=["POST"])
def set_step():
    """Mark leads as already at step N (so they don't get sent step 1 again).
    Useful after sending step 1 externally via GitHub Actions."""
    data = request.json
    emails = data.get("emails", [])
    step   = int(data.get("step", 1))
    if not emails: return jsonify({"error": "no emails"}), 400
    
    from datetime import datetime, timedelta
    conn = get_db()
    next_step = step + 1
    if next_step > 5:
        return jsonify({"error": "step must be 1-4"}), 400
    next_tpl = get_effective_template_for_step(next_step)
    next_at = (datetime.utcnow() + timedelta(days=next_tpl["delay_days"])).isoformat()
    
    updated = 0
    for email in emails:
        cur = conn.execute("""UPDATE leads 
            SET sequence_step=?, in_sequence=1, next_send_at=?
            WHERE email=?""", [step, next_at, email])
        if cur.rowcount > 0: updated += 1
    conn.commit(); conn.close()
    return jsonify({"updated": updated, "next_send_at": next_at, "next_step": next_step})



# ── EMAIL LOG DETAIL (for previewing sent emails) ──
@app.route("/api/email_log/<int:log_id>")
def email_log_detail(log_id):
    conn = get_db()
    row = conn.execute("""SELECT el.*, l.name AS lead_name, l.email AS lead_email, l.city AS lead_city
        FROM email_log el LEFT JOIN leads l ON el.lead_id = l.id WHERE el.id=?""",
        [log_id]).fetchone()
    conn.close()
    if not row: return jsonify({"error": "not found"}), 404

    # Reconstruct the email body using template + lead data for preview
    log = dict(row)
    body_html = ""
    if log.get("step") and 1 <= log["step"] <= 5:
        tpl = SEQUENCE_TEMPLATES[log["step"] - 1]
        # Build a minimal lead dict to personalize
        lead_for_preview = {
            "name":    log.get("lead_name") or "there",
            "city":    log.get("lead_city") or "",
        }
        body_html = personalize(tpl["body"], lead_for_preview)
    log["body_preview"] = body_html
    return jsonify(log)


# ── TEMPLATE PREVIEW (render a template with custom name) ──
@app.route("/api/sequence/preview/<int:step>")
def template_preview(step):
    domain_key = (request.args.get("domain") or "skymaxx").strip().lower()
    if domain_key not in SEQUENCE_TEMPLATES_BY_DOMAIN:
        domain_key = "skymaxx"
    if not (1 <= step <= len(SEQUENCE_TEMPLATES_BY_DOMAIN[domain_key])):
        return jsonify({"error": "invalid step"}), 400
    name = request.args.get("name", "Sarah Johnson")
    tpl = get_effective_template_for_step(step, domain_key)
    # Domain-specific sender + sample company so {{company}} renders properly
    dcfg = DOMAIN_CONFIG.get(domain_key, DOMAIN_CONFIG["skymaxx"])
    sample_company = "Acme Corp" if dcfg["audience"] == "b2b" else "[your name]"
    fake_lead = {
        "name":    name,
        "city":    "Dubai" if dcfg["audience"] == "b2b" else "Austin",
        "website": "example.com",
        "company": sample_company,
        "first_name": name.split(" ")[0] if name else "Sarah",
    }
    return jsonify({
        "step":       tpl["step"],
        "subject":    personalize(tpl["subject"], fake_lead),
        "body":       personalize(tpl["body"], fake_lead),
        "from_email": dcfg["sender_email"],
        "from_name":  dcfg["sender_name"],
        "domain":     domain_key,
        "domain_label": dcfg["label"],
    })


# ── SEND TEST EMAIL ──
@app.route("/api/sequence/send_test", methods=["POST"])
def send_test_email():
    data = request.json or {}
    step      = int(data.get("step", 1))
    to_email  = (data.get("email") or "").strip()
    test_name = data.get("name", "Test User")
    if not to_email or "@" not in to_email:
        return jsonify({"error": "invalid email"}), 400
    if not (1 <= step <= len(SEQUENCE_TEMPLATES)):
        return jsonify({"error": "invalid step"}), 400
    tpl = get_effective_template_for_step(step)
    fake_lead = {"name": test_name, "city": "Dubai"}
    subject = "[TEST] " + personalize(tpl["subject"], fake_lead)
    body    = personalize(tpl["body"], fake_lead)
    ok, err = send_via_zepto(to_email, test_name, subject, body)
    return jsonify({"sent": ok, "error": err})


# ── BULK DELETE LEADS ──
@app.route("/api/leads/bulk_delete", methods=["POST"])
def bulk_delete_leads():
    data = request.json or {}
    ids = data.get("lead_ids", [])
    if not ids: return jsonify({"deleted": 0})
    conn = get_db()
    placeholders = ",".join("?" * len(ids))
    conn.execute(f"DELETE FROM leads WHERE id IN ({placeholders})", ids)
    conn.commit()
    deleted = conn.execute("SELECT changes()").fetchone()[0]
    conn.close()
    return jsonify({"deleted": deleted})


# ── DELETE LEADS WITHOUT EMAIL ──
@app.route("/api/leads/clean_no_email", methods=["POST"])
def clean_no_email():
    conn = get_db()
    conn.execute("DELETE FROM leads WHERE email IS NULL OR email = ''")
    conn.commit()
    deleted = conn.execute("SELECT changes()").fetchone()[0]
    conn.close()
    return jsonify({"deleted": deleted})


# ── PROSPECTING TEMPLATES (pre-built searches) ──
PROSPECTING_TEMPLATES = [
    {"id": "it_services",  "label": "IT Services & MSPs",      "keyword": "IT services company"},
    {"id": "consulting",   "label": "Consulting Firms",        "keyword": "business consulting firm"},
    {"id": "real_estate",  "label": "Real Estate Agencies",    "keyword": "real estate agency"},
    {"id": "marketing",    "label": "Marketing Agencies",      "keyword": "digital marketing agency"},
    {"id": "law",          "label": "Law Firms",               "keyword": "law firm"},
    {"id": "accounting",   "label": "Accounting Firms",        "keyword": "accounting firm"},
    {"id": "manufacturing","label": "Manufacturing Companies", "keyword": "manufacturing company"},
    {"id": "retail",       "label": "Retail Businesses",       "keyword": "retail store"},
    {"id": "healthcare",   "label": "Healthcare Clinics",      "keyword": "medical clinic"},
    {"id": "education",    "label": "Schools & Training",      "keyword": "training institute"},
    {"id": "construction", "label": "Construction Firms",      "keyword": "construction company"},
    {"id": "logistics",    "label": "Logistics & Shipping",    "keyword": "logistics company"},
    {"id": "trading",      "label": "Trading Companies",       "keyword": "trading company"},
    {"id": "hospitality",  "label": "Hotels & Restaurants",    "keyword": "hotel"},
    {"id": "automotive",   "label": "Automotive Businesses",   "keyword": "auto dealership"},
    {"id": "fitness",      "label": "Fitness Centers",         "keyword": "fitness gym"},
]

@app.route("/api/prospecting/templates")
def prospecting_templates():
    return jsonify(PROSPECTING_TEMPLATES)


# ── MULTI-CITY SEARCH ──
@app.route("/api/search/multi", methods=["POST"])
def search_multi():
    """Search multiple cities + multiple keywords in one batch."""
    data = request.json or {}
    keywords = data.get("keywords", [])
    cities   = data.get("cities", [])
    pages    = min(int(data.get("pages", 1)), 2)
    if not keywords or not cities:
        return jsonify({"error": "need keywords and cities"}), 400
    if not GOOGLE_MAPS_API_KEY:
        return jsonify({"error": "Google Maps not configured"}), 400

    all_results = []
    total_saved = 0
    total_dupes = 0
    summary = []

    for keyword in keywords:
        for city in cities:
            try:
                resp = requests.get(PLACES_TEXT_URL,
                    params={"key": GOOGLE_MAPS_API_KEY, "query": f"{keyword} in {city}"},
                    timeout=15).json()
                if resp.get("status") not in ("OK", "ZERO_RESULTS"):
                    summary.append({"keyword": keyword, "city": city, "found": 0,
                                    "error": resp.get("status")})
                    continue
                places = resp.get("results", [])[:10]  # cap at 10 per combination
                count = 0
                conn = get_db()
                for place in places:
                    pid = place.get("place_id", "")
                    det = requests.get(PLACES_DETAIL_URL, params={
                        "key": GOOGLE_MAPS_API_KEY, "place_id": pid,
                        "fields": "name,formatted_address,formatted_phone_number,international_phone_number,website,rating,user_ratings_total,types"
                    }, timeout=15).json().get("result", {})
                    time.sleep(0.3)
                    website = det.get("website", "") or ""
                    email = ""
                    if website:
                        domain = website.replace("https://","").replace("http://","").split("/")[0]
                        if domain.startswith("www."): domain = domain[4:]
                        email = f"info@{domain}"
                    try:
                        conn.execute("""INSERT OR IGNORE INTO leads
                            (name,email,phone,intl_phone,website,address,city,country,category,rating,reviews,place_id,maps_url)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            [det.get("name", place.get("name", "")), email,
                             det.get("formatted_phone_number",""), det.get("international_phone_number",""),
                             website, det.get("formatted_address",""), city, city.split(",")[-1].strip(),
                             ", ".join(place.get("types", [])[:3]), place.get("rating", 0),
                             place.get("user_ratings_total", 0), pid,
                             f"https://www.google.com/maps/place/?q=place_id:{pid}"])
                        if conn.execute("SELECT changes()").fetchone()[0]:
                            total_saved += 1; count += 1
                        else:
                            total_dupes += 1
                    except Exception: total_dupes += 1
                conn.commit(); conn.close()
                summary.append({"keyword": keyword, "city": city, "found": count, "error": None})
            except Exception as e:
                summary.append({"keyword": keyword, "city": city, "found": 0, "error": str(e)[:60]})
    return jsonify({"saved": total_saved, "dupes": total_dupes, "summary": summary})



# ─────────────────────────────────────────────
# DOMAIN HEALTH CHECK — SPF / DKIM / DMARC
# ─────────────────────────────────────────────
import socket

def _dns_txt_lookup(domain):
    """Lookup TXT records by calling Google DNS-over-HTTPS (works on Render)."""
    try:
        url = f"https://dns.google/resolve?name={domain}&type=TXT"
        r = requests.get(url, timeout=10)
        if r.status_code != 200: return []
        data = r.json()
        if data.get("Status") != 0: return []
        return [a.get("data","").strip('"') for a in data.get("Answer", [])]
    except Exception:
        return []

def check_domain_health(domain):
    """Check SPF, DKIM, DMARC for the sending domain."""
    domain = (domain or "").lower().strip()
    if not domain: domain = "skymaxx.company"
    result = {
        "domain":  domain,
        "spf":     {"status": "missing", "value": None, "issues": []},
        "dkim":    {"status": "unknown", "selectors": []},
        "dmarc":   {"status": "missing", "value": None, "policy": None},
        "mx":      {"status": "unknown", "records": []},
        "score":   0,
    }

    # SPF check
    txts = _dns_txt_lookup(domain)
    spf = next((t for t in txts if t.startswith("v=spf1")), None)
    if spf:
        result["spf"]["value"] = spf
        result["spf"]["status"] = "ok"
        if "include:zeptomail.zoho.com" not in spf and "zeptomail" not in spf:
            result["spf"]["issues"].append("ZeptoMail not authorized — emails may go to spam")
            result["spf"]["status"] = "warning"
        if "include:spf.protection.outlook.com" not in spf and "outlook" not in spf:
            result["spf"]["issues"].append("Outlook 365 not authorized (skip if not using M365 to send)")
        result["score"] += 30

    # DKIM check — try common selectors
    for selector in ("zoho", "default", "google", "selector1", "s1"):
        dkim_txts = _dns_txt_lookup(f"{selector}._domainkey.{domain}")
        dkim = next((t for t in dkim_txts if "v=DKIM1" in t or "k=" in t), None)
        if dkim:
            result["dkim"]["selectors"].append({"name": selector, "found": True})
            result["dkim"]["status"] = "ok"
    if not result["dkim"]["selectors"]:
        result["dkim"]["status"] = "missing"
    else:
        result["score"] += 30

    # DMARC check
    dmarc_txts = _dns_txt_lookup(f"_dmarc.{domain}")
    dmarc = next((t for t in dmarc_txts if t.startswith("v=DMARC1")), None)
    if dmarc:
        result["dmarc"]["value"] = dmarc
        result["dmarc"]["status"] = "ok"
        for part in dmarc.split(";"):
            if part.strip().startswith("p="):
                result["dmarc"]["policy"] = part.strip().split("=")[1]
        result["score"] += 30

    # MX check
    mx_txts = _dns_txt_lookup(f"{domain}")  # use TXT for now, MX needs special query
    result["score"] += 10  # baseline for domain existing

    return result


@app.route("/api/domain/health")
def domain_health():
    domain = request.args.get("domain", FROM_EMAIL.split("@")[-1] if "@" in FROM_EMAIL else "skymaxx.company")
    return jsonify(check_domain_health(domain))


# ─────────────────────────────────────────────
# MANDATORY APPROVAL WORKFLOW — CAMPAIGNS
# ─────────────────────────────────────────────

def calculate_risk_score(lead_count, domain_health_result):
    """Score 0-100, higher = more risk."""
    score = 0; notes = []
    if lead_count > 100: score += 20; notes.append(f"High volume ({lead_count} recipients)")
    elif lead_count > 50: score += 10; notes.append(f"Medium volume ({lead_count} recipients)")
    if domain_health_result["spf"]["status"] != "ok":
        score += 25; notes.append("SPF not properly configured")
    if domain_health_result["dkim"]["status"] != "ok":
        score += 25; notes.append("DKIM not properly configured")
    if domain_health_result["dmarc"]["status"] != "ok":
        score += 15; notes.append("DMARC missing — recommended for deliverability")
    return min(score, 100), notes


@app.route("/api/campaigns", methods=["GET"])
def list_campaigns():
    conn = get_db()
    rows = rows_to_list(conn.execute("""SELECT * FROM campaigns 
        ORDER BY created_at DESC LIMIT 50""").fetchall())
    # Enrich each campaign with next_send_at + live sent count
    for c in rows:
        try:
            lead_ids = json.loads(c.get("lead_ids_json") or "[]")
            lead_ids = [int(x) for x in lead_ids if x]
        except Exception:
            lead_ids = []
        if lead_ids:
            ph = ",".join("?" * len(lead_ids))
            # next scheduled send among active leads
            nxt = conn.execute(
                f"""SELECT MIN(next_send_at) FROM leads
                    WHERE id IN ({ph}) AND in_sequence=1 AND replied=0 AND unsubscribed=0
                    AND sequence_step < 5""", lead_ids).fetchone()[0]
            c["next_send_at"] = nxt
            # progress: how many leads finished vs total
            finished = conn.execute(
                f"""SELECT COUNT(*) FROM leads WHERE id IN ({ph})
                    AND (sequence_step >= 5 OR replied=1 OR unsubscribed=1)""",
                lead_ids).fetchone()[0]
            c["leads_finished"] = finished
            c["leads_total"] = len(lead_ids)
            
            # Per-step progress: sent count for each of the 5 steps
            step_progress = []
            for step_num in range(1, 6):
                sent_at_step = conn.execute(
                    f"""SELECT COUNT(*) FROM email_log
                        WHERE lead_id IN ({ph}) AND step=? AND status='success'""",
                    lead_ids + [step_num]).fetchone()[0]
                # Get template name + delay for this step
                try:
                    tpl = get_effective_template_for_step(step_num)
                    step_name = tpl.get('name', f'Email {step_num}')
                except Exception:
                    step_name = f'Email {step_num}'
                # Status: completed (all sent), active (some sent or due now), pending (nothing yet)
                if sent_at_step >= len(lead_ids):
                    status = 'completed'
                elif sent_at_step > 0:
                    status = 'active'
                else:
                    # Pending — but is it the NEXT step to send?
                    prev_sent = conn.execute(
                        f"""SELECT COUNT(*) FROM email_log
                            WHERE lead_id IN ({ph}) AND step=? AND status='success'""",
                        lead_ids + [step_num - 1] if step_num > 1 else lead_ids + [0]).fetchone()[0]
                    if step_num == 1:
                        status = 'pending'
                    elif prev_sent > 0 and sent_at_step == 0:
                        status = 'next'  # this step is about to start
                    else:
                        status = 'pending'
                step_progress.append({
                    'step': step_num,
                    'name': step_name,
                    'sent': sent_at_step,
                    'total': len(lead_ids),
                    'status': status
                })
            c["step_progress"] = step_progress
        else:
            c["next_send_at"] = None
            c["leads_finished"] = 0
            c["leads_total"] = 0
            c["step_progress"] = []
    conn.close()
    return jsonify({"campaigns": rows})


@app.route("/api/campaigns/<int:cid>", methods=["GET"])
def get_campaign(cid):
    conn = get_db()
    row = conn.execute("SELECT * FROM campaigns WHERE id=?", [cid]).fetchone()
    conn.close()
    if not row: return jsonify({"error": "not found"}), 404
    return jsonify(dict(row))


@app.route("/api/campaigns/draft", methods=["POST"])
def create_campaign_draft():
    """Create a campaign in 'pending_approval' status with all metadata for the approval popup."""
    data = request.json or {}
    name      = (data.get("name") or f"Campaign {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}").strip()
    domain_key = (data.get("domain") or "skymaxx").strip().lower()
    if domain_key not in DOMAIN_CONFIG:
        domain_key = "skymaxx"
    lead_ids  = data.get("lead_ids", [])
    
    # If lead_ids == "all", resolve them
    conn = get_db()
    if lead_ids == "all":
        rows = conn.execute("""SELECT id FROM leads 
            WHERE email IS NOT NULL AND email != '' 
            AND in_sequence=0 AND unsubscribed=0 AND replied=0""").fetchall()
        lead_ids = [r["id"] for r in rows]
    elif lead_ids == "filtered":
        # respect current filter state from query params
        rows = conn.execute("""SELECT id FROM leads 
            WHERE email IS NOT NULL AND email != ''""").fetchall()
        lead_ids = [r["id"] for r in rows]
    
    lead_ids = [int(x) for x in lead_ids if x]
    if not lead_ids:
        conn.close()
        return jsonify({"error": "no eligible leads selected"}), 400
    
    # Pull lead samples for preview
    placeholders = ",".join("?" * len(lead_ids[:5]))
    sample_leads = rows_to_list(conn.execute(f"""SELECT id,name,email,city 
        FROM leads WHERE id IN ({placeholders}) LIMIT 5""", lead_ids[:5]).fetchall())
    conn.close()
    
    # Domain health check
    domain = FROM_EMAIL.split("@")[-1] if "@" in FROM_EMAIL else "skymaxx.company"
    dh = check_domain_health(domain)
    risk_score, risk_notes = calculate_risk_score(len(lead_ids), dh)
    
    # Estimate open/reply (industry averages for B2B cold outreach)
    base_open = 35.0; base_reply = 6.0
    if risk_score > 50: base_open -= 10; base_reply -= 2
    if dh["score"] >= 60: base_open += 5
    
    # Schedule (sequence runs over 21 days)
    schedule_starts = datetime.utcnow().isoformat()
    
    # Build summary
    summary = (f"Send 5-email sequence over 21 days to {len(lead_ids)} prospects. "
               f"Sender: {FROM_NAME} <{FROM_EMAIL}>. Topics: Microsoft 365 management.")
    
    conn = get_db()
    cur = conn.execute("""INSERT INTO campaigns 
        (name, summary, status, lead_ids_json, recipient_count, schedule_starts,
         risk_score, risk_notes, est_open_rate, est_reply_rate, deliverability,
         spf_status, dkim_status, dmarc_status)
        VALUES (?,?,'pending_approval',?,?,?,?,?,?,?,?,?,?,?)""",
        [name, summary, json.dumps(lead_ids), len(lead_ids), schedule_starts,
         risk_score, " • ".join(risk_notes) if risk_notes else "All checks passed",
         base_open, base_reply, f"Domain health score: {dh['score']}/100",
         dh["spf"]["status"], dh["dkim"]["status"], dh["dmarc"]["status"]])
    conn.commit()
    campaign_id = cur.lastrowid
    conn.close()
    
    return jsonify({
        "campaign_id": campaign_id,
        "status": "pending_approval",
        "name": name,
        "summary": summary,
        "recipient_count": len(lead_ids),
        "sample_leads": sample_leads,
        "schedule_starts": schedule_starts,
        "schedule_ends":   (datetime.utcnow() + timedelta(days=21)).isoformat(),
        "risk_score": risk_score,
        "risk_notes": risk_notes,
        "est_open_rate":  round(base_open, 1),
        "est_reply_rate": round(base_reply, 1),
        "domain_health":  dh,
        "sequence_steps": [{"step": t["step"], "name": t["name"], 
            "subject": t["subject"], "day": [0,3,7,14,21][i]} 
            for i, t in enumerate(SEQUENCE_TEMPLATES)],
    })


@app.route("/api/campaigns/<int:cid>/approve", methods=["POST"])
def approve_campaign(cid):
    """Approve campaign and actually enroll leads. Sets campaign_id, in_sequence, sequence_step.
    Idempotent: works whether status is 'pending_approval' OR 'approved' (re-enrollment).
    Returns detailed report of which leads were enrolled vs skipped + why."""
    conn = get_db()
    camp = conn.execute("SELECT * FROM campaigns WHERE id=?", [cid]).fetchone()
    if not camp:
        conn.close()
        return jsonify({"error": "campaign not found"}), 404

    try:
        lead_ids = json.loads(camp["lead_ids_json"] or "[]")
    except Exception:
        lead_ids = []

    if not lead_ids:
        conn.close()
        return jsonify({"error": "campaign has no leads", "campaign_id": cid}), 400

    enrolled = 0
    enrolled_ids = []
    skipped = []
    now_iso = datetime.utcnow().isoformat()

    for lid in lead_ids:
        try:
            lid_int = int(lid)
        except (ValueError, TypeError):
            skipped.append({"id": lid, "reason": "invalid_id_format"})
            continue

        lead = conn.execute(
            "SELECT id, email, replied, unsubscribed, in_sequence FROM leads WHERE id=?",
            [lid_int]).fetchone()

        if not lead:
            skipped.append({"id": lid_int, "reason": "lead_not_in_db"})
            continue
        if not (lead["email"] or "").strip():
            skipped.append({"id": lid_int, "reason": "no_email"})
            continue
        if lead["replied"]:
            skipped.append({"id": lid_int, "reason": "already_replied"})
            continue
        if lead["unsubscribed"]:
            skipped.append({"id": lid_int, "reason": "unsubscribed"})
            continue

        # ENROLL: set in_sequence + campaign_id + reset sequence_step + schedule first send
        conn.execute("""UPDATE leads
            SET in_sequence=1, sequence_step=0, next_send_at=?, campaign_id=?, domain_key=?
            WHERE id=?""",
            [now_iso, cid, camp.get("domain_key") if camp.get("domain_key") else "skymaxx", lid_int])
        enrolled += 1
        enrolled_ids.append(lid_int)

    approved_by = (request.json or {}).get("approved_by", "user")
    conn.execute("""UPDATE campaigns
        SET status='approved', approved_at=?, approved_by=?, actually_started=?
        WHERE id=?""",
        [now_iso, approved_by, enrolled, cid])
    conn.commit()
    conn.close()

    print(f"[approve] Campaign {cid}: enrolled {enrolled}/{len(lead_ids)} leads. "
          f"Skipped {len(skipped)}: {skipped[:5]}")

    return jsonify({
        "approved":        True,
        "campaign_id":     cid,
        "enrolled":        enrolled,
        "skipped":         len(skipped),
        "skipped_reasons": skipped[:30],
        "enrolled_ids":    enrolled_ids[:30],
        "total_in_json":   len(lead_ids),
        "message":         f"Enrolled {enrolled} of {len(lead_ids)} leads. "
                          f"{len(skipped)} skipped (see skipped_reasons for details)."
    })



@app.route("/api/campaigns/<int:cid>/reject", methods=["POST"])
def reject_campaign(cid):
    reason = (request.json or {}).get("reason", "Rejected by user")
    conn = get_db()
    conn.execute("UPDATE campaigns SET status='rejected', rejected_reason=? WHERE id=? AND status='pending_approval'",
                 [reason, cid])
    conn.commit()
    conn.close()
    return jsonify({"rejected": True})


@app.route("/api/campaigns/<int:cid>/modify", methods=["POST"])
def modify_campaign(cid):
    """Mark for modification — moves back to draft for re-editing."""
    conn = get_db()
    conn.execute("UPDATE campaigns SET status='draft' WHERE id=?", [cid])
    conn.commit()
    conn.close()
    return jsonify({"status": "draft"})


# ─── AI ASSISTANT — placeholder endpoints (require API key to power) ──
AI_PROVIDER = os.getenv("AI_PROVIDER", "")  # 'anthropic' or 'openai'
AI_API_KEY  = os.getenv("AI_API_KEY", "")

def _call_ai(system_prompt, user_prompt, max_tokens=1200):
    """Call Anthropic or OpenAI based on AI_PROVIDER env var."""
    if not AI_API_KEY:
        return None, "AI not configured — set AI_PROVIDER and AI_API_KEY env vars"
    try:
        if AI_PROVIDER == "anthropic":
            r = requests.post("https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": AI_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": max_tokens,
                    "system": system_prompt,
                    "messages": [{"role":"user","content": user_prompt}],
                },
                timeout=60)
            if r.status_code == 200:
                return r.json()["content"][0]["text"], None
            return None, f"AI error {r.status_code}: {r.text[:200]}"
        elif AI_PROVIDER == "openai":
            r = requests.post("https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "gpt-4o-mini",
                    "max_tokens": max_tokens,
                    "messages": [
                        {"role":"system","content": system_prompt},
                        {"role":"user","content": user_prompt},
                    ],
                },
                timeout=60)
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"], None
            return None, f"AI error {r.status_code}: {r.text[:200]}"
        return None, f"Unknown AI_PROVIDER: {AI_PROVIDER}"
    except Exception as e:
        return None, str(e)


AI_ACTION_PROMPTS = {
    "rewrite":           "Rewrite this email to be more compelling while keeping the same intent, structure, and HTML formatting. Preserve all {{placeholders}} exactly.",
    "improve_conversion":"Rewrite this email to maximize reply rate. Use psychology-driven copywriting (specific outcomes, low commitment, easy yes). Keep HTML structure and {{placeholders}}.",
    "personalize":       "Make this email more personalized and conversational, as if written to one specific person. Keep HTML and {{placeholders}}.",
    "make_professional": "Rewrite to be more formal and professional. Keep HTML and {{placeholders}}.",
    "make_friendly":     "Rewrite to be warmer, friendlier, more conversational. Keep HTML and {{placeholders}}.",
    "make_technical":    "Rewrite to be more technically detailed for technical buyers (CTOs, IT Directors). Keep HTML and {{placeholders}}.",
    "shorten":           "Shorten this email by 40% while keeping the key message and CTA. Keep HTML and {{placeholders}}.",
    "expand":            "Expand this email with one more benefit-focused paragraph. Keep HTML and {{placeholders}}.",
    "grammar":           "Fix any grammar, spelling, or awkward phrasing. Keep HTML, structure, and {{placeholders}} unchanged.",
    "improve_subject":   "Suggest 5 alternative subject lines optimized for B2B cold email open rates. Return as a numbered list, no HTML.",
    "improve_cta":       "Strengthen the call-to-action in this email — make it more specific and benefit-driven. Keep HTML and {{placeholders}}.",
    "improve_readability":"Improve readability: shorter sentences, simpler words, better flow. Keep HTML and {{placeholders}}.",
    "improve_deliverability":"Rewrite to reduce spam-trigger words (free, guarantee, urgent, $$, etc.). Suggest changes. Keep HTML and {{placeholders}}.",
    "compliance_check":  "Check this email for compliance issues (CAN-SPAM, GDPR). List any concerns. Don't rewrite — just audit.",
    "translate_arabic":  "Translate this email to Arabic, preserving HTML structure and {{placeholders}}.",
}


@app.route("/api/ai/edit_email", methods=["POST"])
def ai_edit_email():
    """Run an AI action on an email. Returns the edited content."""
    data = request.json or {}
    action  = data.get("action", "")
    subject = data.get("subject", "")
    body    = data.get("body", "")
    
    if action not in AI_ACTION_PROMPTS:
        return jsonify({"error": f"unknown action {action}", "available": list(AI_ACTION_PROMPTS.keys())}), 400
    
    if not AI_API_KEY:
        return jsonify({
            "error": "AI not configured",
            "message": "Set AI_PROVIDER (anthropic|openai) and AI_API_KEY in Render env vars",
            "action": action,
            "preview": "AI feature requires an API key. The action would " + AI_ACTION_PROMPTS[action].lower()
        }), 503
    
    sys_prompt = "You are an expert B2B cold email writer. Always preserve HTML structure and {{placeholders}} like {{first_name}} and {{sender_name}}."
    nl = chr(10)
    user_prompt = ("Action: " + AI_ACTION_PROMPTS[action] + nl + nl +
                   "Subject: " + subject + nl + nl +
                   "Body HTML:" + nl + body + nl + nl +
                   "Return the result. If only the body changed, return just the new body HTML. "
                   "If both subject and body changed, return them as: SUBJECT: ...|BODY: ...")
    
    result, err = _call_ai(sys_prompt, user_prompt)
    if err:
        return jsonify({"error": err}), 500
    
    return jsonify({"action": action, "result": result})


@app.route("/api/ai/status")
def ai_status():
    return jsonify({
        "configured": bool(AI_API_KEY and AI_PROVIDER),
        "provider":   AI_PROVIDER or None,
        "available_actions": list(AI_ACTION_PROMPTS.keys()),
    })



# ─────────────────────────────────────────────
# CONTACT GROUPS
# ─────────────────────────────────────────────
@app.route("/api/groups", methods=["GET"])
def list_groups():
    conn = get_db()
    rows = rows_to_list(conn.execute("""
        SELECT g.*, COUNT(lga.lead_id) AS lead_count
        FROM contact_groups g
        LEFT JOIN lead_group_assignments lga ON g.id = lga.group_id
        GROUP BY g.id ORDER BY g.domain_key, g.name""").fetchall())
    conn.close()
    # Annotate with domain label for UI
    for r in rows:
        dk = r.get("domain_key") or "skymaxx"
        cfg = DOMAIN_CONFIG.get(dk, DOMAIN_CONFIG["skymaxx"])
        r["domain_label"] = cfg["label"]
        r["domain_accent"] = cfg["accent"]
    return jsonify({"groups": rows})


@app.route("/api/groups", methods=["POST"])
def create_group():
    data = request.json or {}
    name = (data.get("name") or "").strip()
    domain_key = (data.get("domain") or "skymaxx").strip().lower()
    if domain_key not in DOMAIN_CONFIG:
        domain_key = "skymaxx"
    if not name: return jsonify({"error": "name required"}), 400
    conn = get_db()
    try:
        cur = conn.execute("INSERT INTO contact_groups (name, description, color, domain_key) VALUES (?,?,?,?)",
                           [name, data.get("description",""), data.get("color","#3b82f6"), domain_key])
        conn.commit()
        gid = cur.lastrowid
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 400
    conn.close()
    return jsonify({"id": gid, "name": name, "domain": domain_key})


@app.route("/api/groups/<int:gid>", methods=["DELETE"])
def delete_group(gid):
    conn = get_db()
    conn.execute("DELETE FROM lead_group_assignments WHERE group_id=?", [gid])
    conn.execute("DELETE FROM contact_groups WHERE id=?", [gid])
    conn.commit(); conn.close()
    return jsonify({"deleted": True})


@app.route("/api/groups/<int:gid>/leads", methods=["GET"])
def group_leads(gid):
    conn = get_db()
    rows = rows_to_list(conn.execute("""
        SELECT l.* FROM leads l
        JOIN lead_group_assignments lga ON l.id = lga.lead_id
        WHERE lga.group_id=? ORDER BY l.name""", [gid]).fetchall())
    conn.close()
    return jsonify({"leads": rows})


@app.route("/api/groups/<int:gid>/add", methods=["POST"])
def add_leads_to_group(gid):
    data = request.json or {}
    lead_ids = data.get("lead_ids", [])
    if not lead_ids: return jsonify({"error": "no lead_ids"}), 400
    conn = get_db()
    added = 0
    for lid in lead_ids:
        try:
            conn.execute("INSERT OR IGNORE INTO lead_group_assignments (lead_id, group_id) VALUES (?,?)", [lid, gid])
            if conn.execute("SELECT changes()").fetchone()[0]: added += 1
        except Exception: pass
    conn.commit(); conn.close()
    return jsonify({"added": added})


@app.route("/api/groups/<int:gid>/remove", methods=["POST"])
def remove_leads_from_group(gid):
    data = request.json or {}
    lead_ids = data.get("lead_ids", [])
    if not lead_ids: return jsonify({"error": "no lead_ids"}), 400
    placeholders = ",".join("?" * len(lead_ids))
    conn = get_db()
    conn.execute(f"DELETE FROM lead_group_assignments WHERE group_id=? AND lead_id IN ({placeholders})",
                 [gid] + lead_ids)
    removed = conn.execute("SELECT changes()").fetchone()[0]
    conn.commit(); conn.close()
    return jsonify({"removed": removed})


# ─────────────────────────────────────────────
# CAMPAIGN PAUSE / RESUME / STOP
# ─────────────────────────────────────────────
@app.route("/api/campaigns/<int:cid>/pause", methods=["POST"])
def pause_campaign(cid):
    """Pause: keep leads in sequence record but stop sending."""
    conn = get_db()
    camp = conn.execute("SELECT lead_ids_json FROM campaigns WHERE id=?", [cid]).fetchone()
    if not camp:
        conn.close()
        return jsonify({"error": "not found"}), 404
    lead_ids = json.loads(camp["lead_ids_json"])
    placeholders = ",".join("?" * len(lead_ids)) if lead_ids else "NULL"
    if lead_ids:
        conn.execute(f"UPDATE leads SET in_sequence=0 WHERE id IN ({placeholders})", lead_ids)
    conn.execute("UPDATE campaigns SET status='paused' WHERE id=?", [cid])
    conn.commit(); conn.close()
    return jsonify({"paused": True})


@app.route("/api/campaigns/<int:cid>/resume", methods=["POST"])
def resume_campaign(cid):
    """Resume: re-enable in_sequence for leads not yet completed."""
    conn = get_db()
    camp = conn.execute("SELECT lead_ids_json FROM campaigns WHERE id=?", [cid]).fetchone()
    if not camp:
        conn.close()
        return jsonify({"error": "not found"}), 404
    lead_ids = json.loads(camp["lead_ids_json"])
    placeholders = ",".join("?" * len(lead_ids)) if lead_ids else "NULL"
    if lead_ids:
        # Preserve future next_send_at (don't blast everyone immediately on resume).
        # Only set to now for leads whose next_send_at is NULL or already past.
        now_iso = datetime.utcnow().isoformat()
        conn.execute(f"""UPDATE leads SET in_sequence=1,
            next_send_at = CASE
                WHEN next_send_at IS NULL OR next_send_at < ? THEN ?
                ELSE next_send_at END
            WHERE id IN ({placeholders}) AND sequence_step<5 AND replied=0 AND unsubscribed=0""",
            [now_iso, now_iso] + lead_ids)
    conn.execute("UPDATE campaigns SET status='running' WHERE id=?", [cid])
    conn.commit(); conn.close()
    return jsonify({"resumed": True})


@app.route("/api/campaigns/<int:cid>/stop", methods=["POST"])
def stop_campaign(cid):
    """Stop permanently: remove leads from sequence, mark campaign completed."""
    conn = get_db()
    camp = conn.execute("SELECT lead_ids_json FROM campaigns WHERE id=?", [cid]).fetchone()
    if not camp:
        conn.close()
        return jsonify({"error": "not found"}), 404
    lead_ids = json.loads(camp["lead_ids_json"])
    placeholders = ",".join("?" * len(lead_ids)) if lead_ids else "NULL"
    if lead_ids:
        conn.execute(f"UPDATE leads SET in_sequence=0 WHERE id IN ({placeholders})", lead_ids)
    conn.execute("UPDATE campaigns SET status='stopped' WHERE id=?", [cid])
    conn.commit(); conn.close()
    return jsonify({"stopped": True})


# ─────────────────────────────────────────────
# SEARCH PREVIEW (no auto-save) + quick campaign
# ─────────────────────────────────────────────
@app.route("/api/search/preview", methods=["POST"])
def search_preview():
    """Search Google Maps but DON'T save - return results so user can select before saving."""
    data = request.json or {}
    keyword = data.get("keyword", "")
    city = data.get("city", "Dubai, UAE")
    if not GOOGLE_MAPS_API_KEY:
        return jsonify({"error": "Google Maps not configured"}), 400
    if not keyword:
        return jsonify({"error": "keyword required"}), 400

    try:
        resp = requests.get(PLACES_TEXT_URL, params={
            "key": GOOGLE_MAPS_API_KEY, "query": f"{keyword} in {city}"
        }, timeout=15).json()
        if resp.get("status") not in ("OK", "ZERO_RESULTS"):
            return jsonify({"error": resp.get("error_message", resp.get("status"))}), 403
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    results = []
    for place in resp.get("results", [])[:20]:
        pid = place.get("place_id", "")
        # Quick details only
        try:
            det = requests.get(PLACES_DETAIL_URL, params={
                "key": GOOGLE_MAPS_API_KEY, "place_id": pid,
                "fields": "name,formatted_address,formatted_phone_number,international_phone_number,website,rating,user_ratings_total,types"
            }, timeout=10).json().get("result", {})
        except Exception:
            det = {}
        time.sleep(0.3)
        website = det.get("website", "") or ""
        email = ""
        if website:
            domain = website.replace("https://","").replace("http://","").split("/")[0]
            if domain.startswith("www."): domain = domain[4:]
            email = f"info@{domain}"

        results.append({
            "place_id":   pid,
            "name":       det.get("name") or place.get("name", ""),
            "email":      email,
            "phone":      det.get("formatted_phone_number", ""),
            "website":    website,
            "address":    det.get("formatted_address", ""),
            "city":       city,
            "country":    city.split(",")[-1].strip(),
            "category":   ", ".join(place.get("types", [])[:3]),
            "rating":     place.get("rating", 0),
            "reviews":    place.get("user_ratings_total", 0),
            "maps_url":   f"https://www.google.com/maps/place/?q=place_id:{pid}",
            "has_email":  bool(email),
        })

    # Check which are already in our DB
    if results:
        place_ids = [r["place_id"] for r in results]
        conn = get_db()
        placeholders = ",".join("?" * len(place_ids))
        existing = {r["place_id"] for r in conn.execute(
            f"SELECT place_id FROM leads WHERE place_id IN ({placeholders})", place_ids).fetchall()}
        conn.close()
        for r in results:
            r["already_saved"] = r["place_id"] in existing
    return jsonify({"results": results, "found": len(results)})


@app.route("/api/search/save_selected", methods=["POST"])
def search_save_selected():
    """Save selected leads from search preview (after user picks them)."""
    data = request.json or {}
    leads = data.get("leads", [])
    if not leads: return jsonify({"error": "no leads"}), 400

    conn = get_db()
    saved = 0
    saved_ids = []
    for r in leads:
        try:
            cur = conn.execute("""INSERT OR IGNORE INTO leads
                (name,email,phone,website,address,city,country,category,rating,reviews,place_id,maps_url,source,status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,'searched','new')""",
                [r.get("name",""), r.get("email",""), r.get("phone",""), r.get("website",""),
                 r.get("address",""), r.get("city",""), r.get("country",""),
                 r.get("category",""), r.get("rating",0), r.get("reviews",0),
                 r.get("place_id",""), r.get("maps_url","")])
            if cur.rowcount:
                saved += 1
                saved_ids.append(cur.lastrowid)
        except Exception: pass
    conn.commit(); conn.close()
    return jsonify({"saved": saved, "lead_ids": saved_ids})


# ─────────────────────────────────────────────
# OPEN / CLICK TRACKING ENDPOINTS
# ─────────────────────────────────────────────
from flask import redirect, Response

_TRACKING_PIXEL = bytes([
    0x47,0x49,0x46,0x38,0x39,0x61,0x01,0x00,0x01,0x00,0x80,0x00,0x00,
    0xff,0xff,0xff,0x00,0x00,0x00,0x21,0xf9,0x04,0x01,0x00,0x00,0x00,
    0x00,0x2c,0x00,0x00,0x00,0x00,0x01,0x00,0x01,0x00,0x00,0x02,0x02,
    0x44,0x01,0x00,0x3b
])

@app.route("/track/open/<int:log_id>.png")
def track_open(log_id):
    try:
        ua = (request.headers.get("User-Agent", "") or "")[:200]
        ip = (request.headers.get("X-Forwarded-For") or request.remote_addr or "")[:50]
        conn = get_db()
        row = conn.execute("SELECT lead_id FROM email_log WHERE id=?", [log_id]).fetchone()
        lead_id = row["lead_id"] if row else None
        is_proxy = any(b in ua.lower() for b in ["googleimageproxy", "googlebot", "yahoo", "bot"])
        conn.execute("""INSERT INTO tracking_events (log_id, lead_id, event_type, ip, user_agent)
                        VALUES (?, ?, ?, ?, ?)""",
                     [log_id, lead_id, "open_proxy" if is_proxy else "open", ip, ua])
        # If real open (not proxy), update lead status
        if not is_proxy and lead_id:
            conn.execute("""UPDATE leads SET status='opened'
                WHERE id=? AND status NOT IN ('replied','qualified','interested','clicked')""",
                [lead_id])
        conn.commit(); conn.close()
    except Exception as e:
        print(f"[track-open] {e}")
    resp = Response(_TRACKING_PIXEL, mimetype="image/gif")
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    return resp


@app.route("/track/click/<int:log_id>")
def track_click(log_id):
    url = request.args.get("url", "")
    if not url or not (url.startswith("http://") or url.startswith("https://")):
        return "Invalid URL", 400
    try:
        ua = (request.headers.get("User-Agent", "") or "")[:200]
        ip = (request.headers.get("X-Forwarded-For") or request.remote_addr or "")[:50]
        conn = get_db()
        row = conn.execute("SELECT lead_id FROM email_log WHERE id=?", [log_id]).fetchone()
        lead_id = row["lead_id"] if row else None
        conn.execute("""INSERT INTO tracking_events (log_id, lead_id, event_type, url, ip, user_agent)
                        VALUES (?, ?, 'click', ?, ?, ?)""",
                     [log_id, lead_id, url[:500], ip, ua])
        if lead_id:
            conn.execute("""UPDATE leads SET status='clicked'
                WHERE id=? AND status NOT IN ('replied','qualified','interested')""", [lead_id])
        conn.commit(); conn.close()
    except Exception as e:
        print(f"[track-click] {e}")
    return redirect(url, code=302)


# ─────────────────────────────────────────────
# ANALYTICS
# ─────────────────────────────────────────────
@app.route("/api/analytics/summary")
def analytics_summary():
    conn = get_db()
    sent      = conn.execute("SELECT COUNT(*) FROM email_log WHERE status='success'").fetchone()[0]
    opens_u   = conn.execute("SELECT COUNT(DISTINCT log_id) FROM tracking_events WHERE event_type='open'").fetchone()[0]
    clicks_u  = conn.execute("SELECT COUNT(DISTINCT log_id) FROM tracking_events WHERE event_type='click'").fetchone()[0]
    replied   = conn.execute("SELECT COUNT(*) FROM leads WHERE replied=1").fetchone()[0]
    failed    = conn.execute("SELECT COUNT(*) FROM email_log WHERE status='failed'").fetchone()[0]
    conn.close()
    pct = lambda n, d: round(n*100.0/d, 1) if d else 0
    return jsonify({
        "sent": sent, "delivered": sent-failed, "failed": failed,
        "opens_unique": opens_u, "clicks_unique": clicks_u, "replies": replied,
        "open_rate":  pct(opens_u, sent),
        "click_rate": pct(clicks_u, sent),
        "reply_rate": pct(replied, sent),
    })


@app.route("/api/analytics/by_step")
def analytics_by_step():
    conn = get_db()
    rows = []
    for step in range(1, 6):
        sent = conn.execute("SELECT COUNT(*) FROM email_log WHERE step=? AND status='success'", [step]).fetchone()[0]
        opens = conn.execute("""SELECT COUNT(DISTINCT te.log_id) FROM tracking_events te
            JOIN email_log el ON te.log_id=el.id WHERE el.step=? AND te.event_type='open'""", [step]).fetchone()[0]
        clicks = conn.execute("""SELECT COUNT(DISTINCT te.log_id) FROM tracking_events te
            JOIN email_log el ON te.log_id=el.id WHERE el.step=? AND te.event_type='click'""", [step]).fetchone()[0]
        pct = lambda n, d: round(n*100.0/d, 1) if d else 0
        rows.append({
            "step": step, "name": get_effective_template_for_step(step)["name"],
            "sent": sent, "opens": opens, "clicks": clicks,
            "open_rate": pct(opens, sent), "click_rate": pct(clicks, sent),
        })
    conn.close()
    return jsonify({"by_step": rows})



# ─────────────────────────────────────────────
# GEOGRAPHIC + INDUSTRY + TITLE DATA ENDPOINTS
# ─────────────────────────────────────────────
@app.route("/api/locations/countries")
def locations_countries():
    return jsonify(COUNTRIES)


@app.route("/api/locations/states/<country_code>")
def locations_states(country_code):
    states = COUNTRY_STATES.get(country_code.upper(), [])
    return jsonify(states)


@app.route("/api/business_categories")
def business_categories():
    return jsonify(BUSINESS_CATEGORIES)


@app.route("/api/job_titles")
def job_titles_list():
    return jsonify(JOB_TITLES)


def _build_search_query(category, job_title, country, state, city):
    """Construct an optimized Google Maps Places query string."""
    parts = []
    if job_title: parts.append(job_title)
    if category:  parts.append(category)
    location_parts = []
    if city:    location_parts.append(city)
    if state and state.lower() not in (city or "").lower(): location_parts.append(state)
    if country: location_parts.append(country)
    location = ", ".join(location_parts) if location_parts else ""
    base = " ".join(p for p in parts if p)
    if location:
        return f"{base} in {location}".strip()
    return base


# ─────────────────────────────────────────────
# ENHANCED SEARCH PREVIEW (hierarchical filters)
# ─────────────────────────────────────────────
@app.route("/api/search/v2/preview", methods=["POST"])
def search_v2_preview():
    # NEW: Route to Orange Slice (LinkedIn) if source is set
    _data = request.get_json(silent=True) or {}
    _source = (_data.get("source") or request.args.get("source") or "google_maps").strip().lower()
    if _source == "orange_slice":
        if not _orange.is_configured():
            return jsonify({"error": "ORANGESLICE_API_KEY not configured on server"}), 400
        # Build ocean_search_people args
        titles_raw = (_data.get("title") or _data.get("keyword") or "").strip()
        country    = (_data.get("country") or "").strip()
        state      = (_data.get("state") or "").strip()
        city       = (_data.get("city") or "").strip()
        limit      = min(int(_data.get("limit") or 25), 50)

        titles_list = []
        if titles_raw:
            # Split by comma if user entered multiple
            titles_list = [t.strip() for t in titles_raw.split(",") if t.strip()]
        if not titles_list:
            return jsonify({"error": "Job title or keyword required for LinkedIn search"}), 400

        # Build location list (Ocean uses country name primarily)
        locations = []
        if country:
            locations.append(country)
        if state and country:
            locations.append(f"{state}, {country}")
        if city and country:
            locations.append(f"{city}, {country}")

        args = {"titles": titles_list, "limit": limit}
        if locations:
            args["locations"] = locations

        os_result = _orange.call("ocean_search_people", args, timeout=60)
        if "_error" in os_result:
            return jsonify({"error": os_result["_error"], "source": "orange_slice"}), 502

        # Normalize to same shape as Google Maps results
        people = os_result.get("people", []) if isinstance(os_result, dict) else []
        results = []
        for p in people:
            # Build a normalized result dict
            company_obj = p.get("company") or {}
            company_name = company_obj.get("name") if isinstance(company_obj, dict) else ""
            results.append({
                "name":       p.get("name") or f"{p.get('firstName','')} {p.get('lastName','')}".strip(),
                "email":      "",  # No email at this stage — requires enrichment
                "phone":      "",
                "website":    p.get("linkedinUrl") or "",
                "address":    p.get("location") or "",
                "category":   p.get("jobTitle") or p.get("headline") or "",
                "rating":     None,
                "reviews":    None,
                "source":     "orange_slice",
                # Orange Slice extras
                "linkedinUrl":   p.get("linkedinUrl") or "",
                "jobTitle":      p.get("jobTitle") or "",
                "headline":      p.get("headline") or "",
                "company":       company_name,
                "companyDomain": p.get("domain") or "",
                "firstName":     p.get("firstName") or "",
                "lastName":      p.get("lastName") or "",
                "photo":         p.get("photo") or "",
                "country":       p.get("country","").upper(),
                "state":         p.get("state") or "",
            })
        return jsonify({
            "ok": True,
            "source": "orange_slice",
            "count": len(results),
            "results": results,
        })


    """New search with full hierarchical filters: country, state, city, category, job title."""
    data = request.json or {}
    category   = (data.get("category")   or "").strip()
    job_title  = (data.get("job_title")  or "").strip()
    country    = (data.get("country")    or "").strip()
    state      = (data.get("state")      or "").strip()
    city       = (data.get("city")       or "").strip()
    custom_kw  = (data.get("keyword")    or "").strip()

    if not GOOGLE_MAPS_API_KEY:
        return jsonify({"error": "Google Maps not configured"}), 400

    # Build keyword: prefer custom keyword if provided, otherwise use category
    # If neither set, fallback to generic "company" search — returns broad business mix
    keyword = custom_kw if custom_kw else category
    search_all_categories = False
    if not keyword:
        keyword = "company"
        search_all_categories = True
    if not (country or state or city):
        return jsonify({"error": "Please pick a Country, State, or City"}), 400

    query = _build_search_query(keyword, job_title, country, state, city)

    # Paginated fetch: up to 60 results via 3-page sweep (Google Maps Text Search limit)
    try:
        places_raw = _places_text_search_paginated(query, max_pages=2, max_results=40)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    if not places_raw:
        # No results found (treat as ZERO_RESULTS)
        places_raw = []
    resp = {"status": "OK", "results": places_raw}

    location_label = ", ".join(p for p in [city, state, country] if p)

    # Parallelize detail fetches with ThreadPoolExecutor — ~3x faster than sequential
    from concurrent.futures import ThreadPoolExecutor
    # In "search all" mode, fetch fewer detailed results to keep response fast (15 vs 20)
    cap = 30 if search_all_categories else 60  # up to 60 per single keyword via pagination

    def _fetch_detail(place):
        pid = place.get("place_id", "")
        try:
            det = requests.get(PLACES_DETAIL_URL, params={
                "key": GOOGLE_MAPS_API_KEY, "place_id": pid,
                "fields": "name,formatted_address,formatted_phone_number,international_phone_number,website,rating,user_ratings_total,types"
            }, timeout=8).json().get("result", {})
        except Exception:
            det = {}
        return (place, pid, det)

    results = []
    places_to_detail = resp.get("results", [])[:cap]
    with ThreadPoolExecutor(max_workers=8) as pool:
        details_list = list(pool.map(_fetch_detail, places_to_detail))

    for place, pid, det in details_list:
        website = det.get("website", "") or ""
        # Pre-set has_email/email_source if no website (final state)
        # If website exists, frontend will enrich via /api/search/v2/enrich_emails
        results.append({
            "place_id":   pid,
            "name":       det.get("name") or place.get("name", ""),
            "email":      "",
            "phone":      det.get("formatted_phone_number", ""),
            "website":    website,
            "address":    det.get("formatted_address", ""),
            "city":       city or state or country,
            "country":    country or (city.split(",")[-1].strip() if city else ""),
            "category":   category or ", ".join(place.get("types", [])[:3]),
            "rating":     place.get("rating", 0),
            "reviews":    place.get("user_ratings_total", 0),
            "maps_url":   f"https://www.google.com/maps/place/?q=place_id:{pid}",
            "has_email":  False,
            "email_source": "pending" if website else "none",
        })

    # ─── INLINE EMAIL + PHONE ENRICHMENT (parallel website scraping) ───
    def _enrich_lead(r):
        try:
            website = (r.get('website') or '').strip()
            already_has_email = bool(r.get('email'))
            already_has_phone = bool(r.get('phone'))
            if not website:
                r['email_source'] = 'none'
                return r
            if already_has_email and already_has_phone:
                return r  # nothing to enrich
            
            # Scrape both emails and phones in one website visit
            contacts = scrape_contacts_from_website(website, per_url_timeout=2)
            
            # Fill email if missing
            if not already_has_email:
                domain = website.replace('https://', '').replace('http://', '').split('/')[0]
                if domain.startswith('www.'):
                    domain = domain[4:]
                try:
                    best = _pick_best_email(contacts.get('emails', []), target_domain=domain)
                except Exception:
                    best = contacts.get('emails', [None])[0] if contacts.get('emails') else None
                if best:
                    r['email'] = best
                    r['has_email'] = True
                    r['email_source'] = 'scraped'
                elif domain:
                    # Fallback: info@domain (user can verify before sending)
                    r['email'] = 'info@' + domain
                    r['has_email'] = True
                    r['email_source'] = 'generated'
            
            # Fill phone if missing
            if not already_has_phone:
                phones = contacts.get('phones', [])
                if phones:
                    r['phone'] = phones[0]
        except Exception as e:
            print(f"[enrich] err on {r.get('name','?')}: {e}")
        return r

    # Run enrichment in parallel with strict time budget (Render has 30s HTTP limit)
    if results:
        import time as _t
        from concurrent.futures import as_completed as _as_completed
        enrich_cap = min(15, len(results))  # cap at 15 to fit in time budget
        enrich_budget = 18.0  # seconds — leave headroom for Google Maps detail (5-8s) + response (2s)
        _enrich_start = _t.time()
        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(_enrich_lead, r) for r in results[:enrich_cap]]
            for fut in _as_completed(futures, timeout=enrich_budget):
                try:
                    fut.result(timeout=1)
                except Exception as fe:
                    print(f"[enrich] future err: {fe}")
                if _t.time() - _enrich_start > enrich_budget:
                    # Cancel remaining
                    for f in futures:
                        if not f.done():
                            f.cancel()
                    break
        # Lead dicts mutated in place; results already reflects enrichment

    # Mark already-saved
    if results:
        place_ids = [r["place_id"] for r in results]
        conn = get_db()
        placeholders = ",".join("?" * len(place_ids))
        existing = {r["place_id"] for r in conn.execute(
            f"SELECT place_id FROM leads WHERE place_id IN ({placeholders})", place_ids).fetchall()}
        conn.close()
        for r in results:
            r["already_saved"] = r["place_id"] in existing

    return jsonify({
        "search_all_categories": search_all_categories,
        "results": results,
        "found":   len(results),
        "query":   query,
        "location_label": location_label,
        "note":    ("Job title filtering uses the title as a search keyword. "
                    "For verified job-title-targeted prospect lists, a B2B database "
                    "(Apollo, Vibe Prospecting, etc.) is recommended.") if job_title else None,
    })


# ─────────────────────────────────────────────
# BULK MULTI-DIMENSIONAL SEARCH (preview, no save)
# ─────────────────────────────────────────────

@app.route("/api/search/v2/enrich_emails", methods=["POST"])
def search_v2_enrich_emails():
    """Scrape emails for a batch of leads. Called after preview returns.

    Input: {"leads": [{"place_id": "...", "website": "..."}, ...]}  (max 8 per call)
    Output: {"emails": {"place_id_1": {"email": "info@x.com", "email_source": "scraped"|"generated"|"none"}, ...}}
    """
    data = request.json or {}
    leads = data.get("leads", [])
    if not leads:
        return jsonify({"emails": {}})
    # Cap at 8 to stay under Render's proxy timeout
    leads = leads[:8]

    # Build minimal dicts for parallel scraping
    work = [{"place_id": l.get("place_id",""), "website": l.get("website","")} for l in leads]
    # Parallel scrape — should take ~5-15s for 8 leads
    enriched = enrich_leads_parallel(work, max_workers=4)

    out = {}
    for e in enriched:
        pid = e.get("place_id")
        if pid:
            out[pid] = {
                "email": e.get("email", ""),
                "email_source": e.get("email_source", "none"),
                "has_email": e.get("has_email", False),
            }
    return jsonify({"emails": out})


@app.route("/api/search/v2/bulk_preview", methods=["POST"])
def search_v2_bulk_preview():
    # NEW: Route bulk search to Orange Slice when source set
    _data = request.get_json(silent=True) or {}
    _source = (_data.get("source") or "google_maps").strip().lower()
    if _source == "orange_slice":
        if not _orange.is_configured():
            return jsonify({"error": "ORANGESLICE_API_KEY not configured on server"}), 400
        countries  = _data.get("countries") or []
        states     = _data.get("states") or []
        titles_in  = _data.get("job_titles") or _data.get("titles") or []
        categories = _data.get("categories") or []  # used as title fallback if no titles
        if not titles_in and not categories:
            return jsonify({"error": "Pick at least one Job Title (Orange Slice searches by title)"}), 400

        titles_list = titles_in if titles_in else categories[:5]
        if not titles_list:
            return jsonify({"error": "No titles specified"}), 400

        # Build location combos
        location_combos = []
        if countries and states:
            for c in countries:
                for s in states:
                    location_combos.append((c, s))
        elif countries:
            for c in countries:
                location_combos.append((c, None))
        elif states:
            for s in states:
                location_combos.append((None, s))
        location_combos = location_combos[:6]  # cap at 6 to prevent timeout

        all_results = []
        summary = []
        for country, state in location_combos:
            locs = []
            if country:
                locs.append(country)
            if state and country:
                locs.append(f"{state}, {country}")
            elif state:
                locs.append(state)

            args = {"titles": titles_list, "limit": 15}
            if locs:
                args["locations"] = locs

            os_result = _orange.call("ocean_search_people", args, timeout=45)
            if "_error" in os_result:
                summary.append({"country": country, "state": state, "category": "+".join(titles_list[:3]), "found": 0, "error": os_result["_error"][:100]})
                continue

            people = os_result.get("people", []) if isinstance(os_result, dict) else []
            for idx_p, p in enumerate(people):
                company_obj = p.get("company") or {}
                company_name = company_obj.get("name") if isinstance(company_obj, dict) else ""
                link = p.get("linkedinUrl") or ""
                # Use linkedin URL as unique key
                synth_id = "os_" + (link or p.get("name","") or str(idx_p)).replace("/", "_").replace(":","_")[:60]
                all_results.append({
                    "place_id":     synth_id,
                    "name":         p.get("name") or f"{p.get('firstName','')} {p.get('lastName','')}".strip(),
                    "email":        "",
                    "phone":        "",
                    "website":      link,
                    "address":      p.get("location") or "",
                    "category":     p.get("jobTitle") or p.get("headline") or "",
                    "rating":       None,
                    "reviews":      None,
                    "source":       "orange_slice",
                    "linkedinUrl":  link,
                    "jobTitle":     p.get("jobTitle") or "",
                    "headline":     p.get("headline") or "",
                    "company":      company_name,
                    "companyDomain":p.get("domain") or "",
                    "firstName":    p.get("firstName") or "",
                    "lastName":     p.get("lastName") or "",
                    "country":      p.get("country","").upper(),
                    "state":        p.get("state") or "",
                })
            summary.append({"country": country, "state": state, "category": "+".join(titles_list[:3]), "found": len(people)})

        # Dedupe by linkedinUrl
        seen = set(); unique = []
        for r in all_results:
            k = r.get("linkedinUrl") or r.get("place_id")
            if k not in seen:
                seen.add(k); unique.append(r)

        return jsonify({
            "ok": True, "source": "orange_slice",
            "found": len(unique), "combinations_run": len(location_combos),
            "capped": len(location_combos) >= 6,
            "results": unique, "summary": summary,
            "note": "Orange Slice / LinkedIn search via Ocean.io. Location filtering is approximate."
        })


    """Bulk search: multiple countries × states × categories × job titles in one batch."""
    data = request.json or {}
    countries  = data.get("countries", [])
    states     = data.get("states", [])
    categories = data.get("categories", [])  # keyword strings, not IDs
    titles     = data.get("job_titles", [])  # keyword strings, not IDs
    if not GOOGLE_MAPS_API_KEY:
        return jsonify({"error": "Google Maps not configured"}), 400
    # If no categories selected, search ALL categories (top 20 most diverse)
    expanded_all = False
    if not categories:
        categories = [c["keyword"] for c in BUSINESS_CATEGORIES[:20]]
        expanded_all = True
    if not (countries or states):
        return jsonify({"error": "Pick at least 1 country or state"}), 400

    # Build search combinations (capped to prevent abuse)
    title_combos = titles if titles else [""]
    geo_combos = []
    for c in (countries or [""]):
        for s in (states or [""]):
            if c or s:
                geo_combos.append((c, s))
    if not geo_combos:
        geo_combos = [("", "")]

    combinations = []
    for cat in categories:
        for jt in title_combos:
            for (country, state) in geo_combos:
                combinations.append({
                    "category":  cat,
                    "job_title": jt,
                    "country":   country,
                    "state":     state,
                })
    # Cap at 24 (parallel execution: ~5s with 8 workers, plenty of headroom under 30s)
    if len(combinations) > 24:
        combinations = combinations[:24]
        capped = True
    else:
        capped = False

    all_results = []
    summary = []
    seen_pids = set()

    # Parallel search via ThreadPoolExecutor — keeps total time under Render's 30s timeout
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _do_one_search(combo):
        q = _build_search_query(combo["category"], combo["job_title"],
                                combo["country"], combo["state"], "")
        try:
            resp = requests.get(PLACES_TEXT_URL, params={
                "key": GOOGLE_MAPS_API_KEY, "query": q
            }, timeout=15).json()
            if resp.get("status") not in ("OK", "ZERO_RESULTS"):
                return (combo, [], resp.get("status"))
            return (combo, resp.get("results", [])[:8], None)
        except Exception as e:
            return (combo, [], str(e)[:100])

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(_do_one_search, c) for c in combinations]
        for fut in as_completed(futures):
            combo, places, err = fut.result()
            if err:
                summary.append({**combo, "found": 0, "error": err})
                continue
            local_count = 0
            for place in places:
                pid = place.get("place_id", "")
                if not pid or pid in seen_pids:
                    continue
                seen_pids.add(pid)
                all_results.append({
                    "place_id":  pid,
                    "name":      place.get("name", ""),
                    "email":     "",
                    "phone":     "",
                    "website":   "",
                    "address":   place.get("formatted_address", ""),
                    "city":      combo["state"] or combo["country"],
                    "country":   combo["country"],
                    "category":  combo["category"],
                    "job_title": combo["job_title"],
                    "rating":    place.get("rating", 0),
                    "reviews":   place.get("user_ratings_total", 0),
                    "maps_url":  "https://www.google.com/maps/place/?q=place_id:" + pid,
                    "has_email": False,
                })
                local_count += 1
            summary.append({**combo, "found": local_count, "error": None})

    return jsonify({
        "expanded_all_categories": expanded_all,
        "results": all_results,
        "found":      len(all_results),
        "summary":    summary,
        "capped":     capped,
        "combinations_run": len(combinations),
        "note":       "Bulk preview returns names and addresses only (fast). Full contact details will be fetched when you save selected leads.",
    })


# ─────────────────────────────────────────────
# ENHANCE save_selected to fetch full details
# ─────────────────────────────────────────────
@app.route("/api/search/v2/save_selected", methods=["POST"])
def search_v2_save_selected():
    """Save selected leads. For bulk-preview results without details, fetches them now."""
    data = request.json or {}
    leads = data.get("leads", [])
    if not leads: return jsonify({"error": "no leads"}), 400

    conn = get_db()
    saved = 0
    saved_ids = []
    needs_details = [l for l in leads if not l.get("email") and not l.get("phone") and l.get("place_id")]
    detail_map = {}
    # Fetch missing details in parallel (capped at 30)
    for l in needs_details[:30]:
        try:
            det = requests.get(PLACES_DETAIL_URL, params={
                "key": GOOGLE_MAPS_API_KEY, "place_id": l["place_id"],
                "fields": "name,formatted_address,formatted_phone_number,international_phone_number,website,rating,user_ratings_total,types"
            }, timeout=10).json().get("result", {})
            time.sleep(0.25)
            detail_map[l["place_id"]] = det
        except Exception:
            pass

    # First, fill websites from detail_map where missing
    for r in leads:
        det = detail_map.get(r.get("place_id"), {})
        if not r.get("website") and det.get("website"):
            r["website"] = det["website"]

    # Scrape emails for any lead missing a real email
    leads_needing_email = [l for l in leads if not l.get("email") and l.get("website")]
    if leads_needing_email:
        enriched = enrich_leads_parallel(leads_needing_email, max_workers=4)
        # Merge back
        by_pid = {l["place_id"]: l for l in enriched if l.get("place_id")}
        for r in leads:
            if r.get("place_id") in by_pid:
                r["email"] = by_pid[r["place_id"]].get("email", "")
                r["email_source"] = by_pid[r["place_id"]].get("email_source", "none")

    for r in leads:
        det = detail_map.get(r.get("place_id"), {})
        website = r.get("website", "") or det.get("website", "") or ""
        email = r.get("email", "") or ""
        # Final fallback if nothing else worked
        if not email and website:
            domain = website.replace("https://","").replace("http://","").split("/")[0]
            if domain.startswith("www."): domain = domain[4:]
            email = f"info@{domain}"
        phone = r.get("phone", "") or det.get("formatted_phone_number", "")
        try:
            cur = conn.execute("""INSERT OR IGNORE INTO leads
                (name,email,phone,website,address,city,country,category,rating,reviews,place_id,maps_url,source,status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,'searched','new')""",
                [r.get("name") or det.get("name", ""),
                 email, phone, website,
                 r.get("address") or det.get("formatted_address", ""),
                 r.get("city",""), r.get("country",""),
                 r.get("category",""), r.get("rating",0) or det.get("rating",0),
                 r.get("reviews",0) or det.get("user_ratings_total",0),
                 r.get("place_id",""), r.get("maps_url","")])
            if cur.rowcount:
                saved += 1
                saved_ids.append(cur.lastrowid)
        except Exception: pass
    conn.commit(); conn.close()
    return jsonify({"saved": saved, "lead_ids": saved_ids})



# ─────────────────────────────────────────────
# EMAIL SCRAPING FROM BUSINESS WEBSITES
# ─────────────────────────────────────────────
import concurrent.futures
import re as _re

_EMAIL_RE = _re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
_EMAIL_PRIORITY = ['info@','contact@','hello@','sales@','enquiry@','enquiries@','inquiries@','admin@','support@','office@','team@','marketing@','reservations@','bookings@']
_EMAIL_BLOCKLIST = ['example.com','yourdomain','test@','noreply','no-reply','donotreply','sentry.io','wixpress','squarespace-cdn','typeform','.png','.jpg','.jpeg','.gif','.svg','.webp','.ico','privacy@','postmaster@','abuse@','dmca@','copyright@','legal@','jobs@','careers@','recruit@']

def _normalize_email(e):
    e = e.lower().strip().rstrip('.')
    # Strip any URL-encoded suffix
    if '?' in e: e = e.split('?')[0]
    if '&' in e: e = e.split('&')[0]
    return e

def _is_valid_email(e):
    if not e or len(e) > 80 or len(e) < 6: return False
    if '@' not in e or '.' not in e.split('@')[1]: return False
    for bad in _EMAIL_BLOCKLIST:
        if bad in e: return False
    # Must have at least 2 chars before @
    local = e.split('@')[0]
    if len(local) < 2: return False
    return True

def _pick_best_email(emails, target_domain=None):
    """Pick the best email from a list. Prefer same-domain + priority prefixes."""
    if not emails: return None
    # Dedupe + normalize
    seen = []
    for e in emails:
        n = _normalize_email(e)
        if _is_valid_email(n) and n not in seen:
            seen.append(n)
    if not seen: return None

    # Score: same domain (+10), priority prefix (+5 to 0 by index), generic prefix (+1)
    def score(e):
        s = 0
        domain = e.split('@')[1]
        if target_domain and (domain == target_domain or domain.endswith('.' + target_domain)):
            s += 100
        for i, p in enumerate(_EMAIL_PRIORITY):
            if e.startswith(p):
                s += 50 - i
                break
        return s

    seen.sort(key=score, reverse=True)
    return seen[0]

def scrape_emails_from_website(website, per_url_timeout=4):
    """Visit homepage + contact, return list of emails. Streams response to cap memory."""
    if not website: return []
    if not website.startswith(('http://','https://')):
        website = 'https://' + website
    base = website.rstrip('/')
    urls = [base, base + '/contact']  # only 2 URLs for speed
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate',
    }
    all_emails = []
    MAX_BYTES = 200_000
    for url in urls:
        try:
            r = requests.get(url, timeout=per_url_timeout, headers=headers, allow_redirects=True,
                             verify=False, stream=True)
            if r.status_code != 200:
                r.close(); continue
            # Stream-read up to MAX_BYTES
            buf = b""
            for chunk in r.iter_content(chunk_size=16384):
                if not chunk: continue
                buf += chunk
                if len(buf) >= MAX_BYTES: break
            r.close()
            try:
                text = buf.decode('utf-8', errors='ignore')
            except Exception:
                text = ""
            if not text: continue
            found = _EMAIL_RE.findall(text)
            mailtos = _re.findall(r"mailto:([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})", text)
            for e in mailtos + found:
                ne = _normalize_email(e)
                if _is_valid_email(ne) and ne not in all_emails:
                    all_emails.append(ne)
            if len(all_emails) >= 5 and url == base: break  # enough from homepage
        except Exception:
            try: r.close()
            except: pass
            continue
    return all_emails




def scrape_contacts_from_website(website, per_url_timeout=2):
    """Visit homepage + /contact + /about. Returns {emails: [...], phones: [...]}."""
    if not website:
        return {'emails': [], 'phones': []}
    if not website.startswith(('http://', 'https://')):
        website = 'https://' + website
    base = website.rstrip('/')
    urls = [base, base + '/contact']  # just 2 URLs for speed
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate',
    }
    all_emails = []
    all_phones = []
    MAX_BYTES = 100_000  # cap page size for speed
    for url in urls:
        try:
            r = requests.get(url, timeout=per_url_timeout, headers=headers, allow_redirects=True, verify=False, stream=True)
            if r.status_code != 200:
                r.close()
                continue
            buf = b""
            for chunk in r.iter_content(chunk_size=16384):
                if not chunk:
                    continue
                buf += chunk
                if len(buf) >= MAX_BYTES:
                    break
            r.close()
            try:
                text = buf.decode('utf-8', errors='ignore')
            except Exception:
                text = ""
            if not text:
                continue

            # EMAILS — both raw and mailto:
            try:
                for e in _EMAIL_RE.findall(text):
                    ne = _normalize_email(e)
                    if _is_valid_email(ne) and ne not in all_emails:
                        all_emails.append(ne)
            except Exception:
                pass
            try:
                for e in _re.findall(r"mailto:([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})", text):
                    ne = _normalize_email(e)
                    if _is_valid_email(ne) and ne not in all_emails:
                        all_emails.append(ne)
            except Exception:
                pass

            # PHONES — tel: links + UAE/international patterns
            try:
                for p in _re.findall(r"tel:([+\d\s().\-]{7,25})", text):
                    digits = _re.sub(r'[^\d+]', '', p)
                    if 7 <= len(digits.lstrip('+')) <= 15 and digits not in all_phones:
                        all_phones.append(digits)
            except Exception:
                pass
            try:
                # UAE-specific: +971 with 8-9 digits OR local 04/05/06/07/02 + 7 digits
                for m_phone in _re.finditer(r'(\+971[\s\-]?\d{1,2}[\s\-]?\d{3}[\s\-]?\d{4}|0\d[\s\-]?\d{3}[\s\-]?\d{4})', text):
                    digits = _re.sub(r'[^\d+]', '', m_phone.group(0))
                    if 7 <= len(digits.lstrip('+')) <= 15 and digits not in all_phones:
                        all_phones.append(digits)
            except Exception:
                pass
            try:
                # Generic international (+CC ...)
                for m_phone in _re.finditer(r'(\+\d{1,3}[\s\-]?\d{2,4}[\s\-]?\d{3,4}[\s\-]?\d{3,4})', text):
                    digits = _re.sub(r'[^\d+]', '', m_phone.group(0))
                    if 8 <= len(digits.lstrip('+')) <= 15 and digits not in all_phones:
                        all_phones.append(digits)
            except Exception:
                pass

            # Stop early if we have enough
            if len(all_emails) >= 5 and len(all_phones) >= 2 and url == base:
                break
        except Exception:
            try:
                r.close()
            except Exception:
                pass
            continue

    return {'emails': all_emails[:10], 'phones': all_phones[:5]}


def enrich_lead_with_email(lead):
    """Take a lead dict (with 'website'), scrape its site, fill 'email'."""
    website = (lead.get('website') or '').strip()
    if not website:
        lead['has_email'] = False
        lead['email_source'] = 'none'
        return lead

    # Derive target domain for same-domain matching
    domain = website.replace('https://','').replace('http://','').split('/')[0]
    if domain.startswith('www.'): domain = domain[4:]

    emails = scrape_emails_from_website(website, per_url_timeout=4)
    best = _pick_best_email(emails, target_domain=domain)
    if best:
        lead['email'] = best
        lead['has_email'] = True
        lead['email_source'] = 'scraped'
    else:
        # Fall back to generated info@domain
        lead['email'] = 'info@' + domain
        lead['has_email'] = True
        lead['email_source'] = 'generated'
    return lead


def enrich_leads_parallel(leads, max_workers=4):
    """Enrich emails for many leads in parallel. Preserves order."""
    if not leads: return leads
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        return list(ex.map(enrich_lead_with_email, leads))


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
        "bcc_support":  BCC_SUPPORT,
        "graph_api":    bool(AZURE_TENANT_ID and AZURE_CLIENT_ID and AZURE_CLIENT_SECRET),
        "mailbox":      MAILBOX_EMAIL,
    })



@app.route("/api/linkedin/enrich_contact", methods=["POST"])
def linkedin_enrich_contact():
    if ORANGE_SLICE_CREDITS_LOCKED:
        return jsonify({
            "error": "Orange Slice credit usage is currently locked by the administrator. "
                     "Email enrichment is disabled to prevent unexpected charges. "
                     "Set ORANGE_SLICE_CREDITS_LOCKED=false in environment to re-enable.",
            "locked": True
        }), 423  # 423 Locked

    """Get verified email/phone for a LinkedIn profile via Orange Slice. Consumes credits."""
    if not _orange.is_configured():
        return jsonify({"error": "ORANGESLICE_API_KEY not configured"}), 400
    data = request.get_json(silent=True) or {}
    linkedin_url = (data.get("linkedinUrl") or "").strip()
    first_name   = (data.get("firstName") or "").strip()
    last_name    = (data.get("lastName") or "").strip()
    company      = (data.get("company") or "").strip()
    required     = data.get("required") or ["email"]

    if not linkedin_url and not (first_name and last_name and company):
        return jsonify({"error": "Need linkedinUrl OR (firstName + lastName + company)"}), 400

    args = {"required": required}
    if linkedin_url:
        args["linkedinUrl"] = linkedin_url
    if first_name:
        args["firstName"] = first_name
    if last_name:
        args["lastName"] = last_name
    if company:
        args["company"] = company

    result = _orange.call("person_contact_get", args, timeout=90)
    if "_error" in result:
        return jsonify({"error": result["_error"]}), 502

    # Extract email/phone from response
    email      = result.get("email") or result.get("work_email") or ""
    work_email = result.get("work_email") or ""
    phone      = result.get("phone") or ""

    return jsonify({
        "ok": True,
        "email": email,
        "work_email": work_email,
        "phone": phone,
        "raw": result,
    })


@app.route("/api/linkedin/status")
def linkedin_status():
    """Quick health check for Orange Slice integration."""
    return jsonify({
        "credits_locked": ORANGE_SLICE_CREDITS_LOCKED,
        "configured": _orange.is_configured(),
        "key_prefix": _orange.api_key[:8] + "..." if _orange.api_key else None,
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
