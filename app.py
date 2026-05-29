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
_PUBLIC_ENDPOINTS = {"login", "static", "logout"}

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
SEQUENCE_TEMPLATES = [
    {
        'step':       1,
        'delay_days': 0,
        'name':       'Initial Outreach',
        'subject':    '1 in 323 emails to SMBs is malicious — quick note on {{company}}',
        'body':       '<!DOCTYPE html><html><body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Arial,sans-serif"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f3f4f6;padding:24px 12px"><tr><td align="center"><table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.08);max-width:600px"><tr><td style="background:linear-gradient(135deg,#0f172a 0%,#1e3a8a 100%);padding:24px 32px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="color:#ffffff;font-size:22px;font-weight:700;letter-spacing:0.5px">&#9889; SKYMAXX <span style="color:#60a5fa;font-weight:500">TECHNOLOGIES</span></td><td align="right" style="color:#cbd5e1;font-size:12px;font-weight:500">Microsoft 365 Specialists</td></tr></table></td></tr><tr><td style="padding:36px 36px 28px;color:#1f2937;font-size:15px;line-height:1.7"><p style="margin:0 0 16px;font-size:16px">Hello <strong>{{first_name}}</strong>,</p><p style="margin:0 0 16px">I came across <strong>{{company}}</strong> while researching SMBs in the region that depend on Microsoft 365 for daily operations &mdash; and I wanted to share something that may be worth a few minutes of your time.</p><div style="background:#fef3c7;border-left:4px solid #f59e0b;padding:14px 18px;margin:0 0 18px;border-radius:6px"><p style="margin:0;font-size:14px;color:#78350f"><strong>Verizon DBIR 2025</strong> finding: small and mid-sized businesses now receive <strong>1 targeted malicious email for every 323 messages</strong> &mdash; the highest rate of any company size. 88% of SMB breaches in 2025 included ransomware, versus just 39% at large enterprises.</p></div><p style="margin:0 0 16px">Most of these incidents trace back to <strong>misconfigured Microsoft 365 tenants</strong>, not to missing software. The Microsoft 365 Business Premium licence many SMBs already pay for ($22/user/month) includes Defender, Intune, and Conditional Access &mdash; but the features only protect when configured correctly.</p><p style="margin:0 0 16px">At <strong>SKYMAXX Technologies</strong>, we focus on one thing: making sure SMBs get the full security and reliability of the M365 stack they already pay for. We are happy to do a no-obligation 30-minute review of your tenant and share what we find.</p><p style="margin:0 0 8px">If that sounds useful, a one-line reply is enough.</p><table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:24px 0 8px"><tr><td style="background:#2563eb;border-radius:8px;box-shadow:0 1px 2px rgba(37,99,235,0.3)"><a href="mailto:support@skymaxx.company?subject=Yes%20—%20I%27d%20like%20to%20learn%20more%20about%20SKYMAXX" style="display:inline-block;padding:13px 28px;color:#ffffff;font-weight:600;text-decoration:none;font-size:14px;letter-spacing:0.3px">&rarr; Yes, let\'s talk</a></td></tr></table><p style="margin:24px 0 0;color:#374151">Best regards,<br/><strong style="color:#0f172a">SKYMAXX Support Team</strong><br/><span style="color:#64748b;font-size:13px">SKYMAXX Technologies</span><br/><a href="https://www.skymaxx.company" style="color:#2563eb;text-decoration:none;font-size:13px;font-weight:500">www.SKYMAXX.Company</a></p></td></tr><tr><td style="background:#f8fafc;padding:16px 36px;border-top:1px solid #e5e7eb"><p style="margin:0 0 6px;color:#64748b;font-size:11px;font-weight:600;letter-spacing:0.5px;text-transform:uppercase">Sources &amp; Further Reading</p><div style="color:#64748b;font-size:11px;line-height:1.6">&bull; Verizon Data Breach Investigations Report 2025: <a href="https://www.verizon.com/business/resources/reports/dbir/" style="color:#2563eb">verizon.com/business/resources/reports/dbir</a><br/>&bull; Microsoft 365 Security Features: <a href="https://learn.microsoft.com/en-us/microsoft-365/security/" style="color:#2563eb">learn.microsoft.com/microsoft-365/security</a></div></td></tr><tr><td style="background:#0f172a;padding:18px 36px;color:#94a3b8;font-size:11px;line-height:1.5"><p style="margin:0">SKYMAXX Technologies &middot; Microsoft 365 Management for SMBs &middot; UAE</p><p style="margin:6px 0 0"><a href="mailto:support@skymaxx.company" style="color:#60a5fa;text-decoration:none">support@skymaxx.company</a> &middot; If you prefer not to receive these messages, just reply with "unsubscribe" and we\'ll remove you immediately.</p></td></tr></table></td></tr></table></body></html>',
    },
    {
        'step':       2,
        'delay_days': 3,
        'name':       'Cost of Doing Nothing',
        'subject':    'Three numbers from IBM that may be worth a minute',
        'body':       '<!DOCTYPE html><html><body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Arial,sans-serif"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f3f4f6;padding:24px 12px"><tr><td align="center"><table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.08);max-width:600px"><tr><td style="background:linear-gradient(135deg,#0f172a 0%,#1e3a8a 100%);padding:24px 32px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="color:#ffffff;font-size:22px;font-weight:700;letter-spacing:0.5px">&#9889; SKYMAXX <span style="color:#60a5fa;font-weight:500">TECHNOLOGIES</span></td><td align="right" style="color:#cbd5e1;font-size:12px;font-weight:500">Microsoft 365 Specialists</td></tr></table></td></tr><tr><td style="padding:36px 36px 28px;color:#1f2937;font-size:15px;line-height:1.7"><p style="margin:0 0 16px;font-size:16px">Hello <strong>{{first_name}}</strong>,</p><p style="margin:0 0 16px">Following up on my earlier note. I will keep this short with three numbers worth knowing.</p><div style="background:#fef2f2;border-left:4px solid #dc2626;padding:14px 18px;margin:0 0 18px;border-radius:6px"><p style="margin:0 0 8px;font-size:14px;color:#7f1d1d;font-weight:600">IBM Cost of a Data Breach Report 2025 (the industry benchmark, conducted by Ponemon Institute):</p><p style="margin:0;font-size:14px;color:#7f1d1d">&bull; Average global cost per breach: <strong>$4.44 million</strong><br/>&bull; Average cost when phishing was the entry point: <strong>$4.80 million</strong><br/>&bull; Average cost of a ransomware or extortion incident: <strong>$5.08 million</strong><br/>&bull; Average time to identify and contain a breach: <strong>241 days</strong></p></div><p style="margin:0 0 16px">For SMBs, recovery rarely matches the headline figures &mdash; the real outcome is often closure. The cost is not just financial: it is the months of operational disruption, regulatory exposure, and lost client trust that follow.</p><p style="margin:0 0 16px">The good news in the same report: organisations that used <strong>security AI and automation extensively</strong> cut their breach lifecycle by 80 days and saved an average of <strong>$1.9 million</strong>. Microsoft 365 Business Premium already includes most of these capabilities &mdash; if they are turned on and configured correctly.</p><p style="margin:0 0 8px">Happy to show you what is currently active on your tenant, free of charge.</p><table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:24px 0 8px"><tr><td style="background:#2563eb;border-radius:8px;box-shadow:0 1px 2px rgba(37,99,235,0.3)"><a href="mailto:support@skymaxx.company?subject=Show%20me%20what%27s%20active%20on%20my%20M365%20tenant" style="display:inline-block;padding:13px 28px;color:#ffffff;font-weight:600;text-decoration:none;font-size:14px;letter-spacing:0.3px">&rarr; Show me my tenant</a></td></tr></table><p style="margin:24px 0 0;color:#374151">Best regards,<br/><strong style="color:#0f172a">SKYMAXX Support Team</strong><br/><span style="color:#64748b;font-size:13px">SKYMAXX Technologies</span><br/><a href="https://www.skymaxx.company" style="color:#2563eb;text-decoration:none;font-size:13px;font-weight:500">www.SKYMAXX.Company</a></p></td></tr><tr><td style="background:#f8fafc;padding:16px 36px;border-top:1px solid #e5e7eb"><p style="margin:0 0 6px;color:#64748b;font-size:11px;font-weight:600;letter-spacing:0.5px;text-transform:uppercase">Sources &amp; Further Reading</p><div style="color:#64748b;font-size:11px;line-height:1.6">&bull; IBM Cost of a Data Breach Report 2025: <a href="https://www.ibm.com/reports/data-breach" style="color:#2563eb">ibm.com/reports/data-breach</a><br/>&bull; Microsoft Defender for Business: <a href="https://learn.microsoft.com/en-us/defender-business/" style="color:#2563eb">learn.microsoft.com/defender-business</a></div></td></tr><tr><td style="background:#0f172a;padding:18px 36px;color:#94a3b8;font-size:11px;line-height:1.5"><p style="margin:0">SKYMAXX Technologies &middot; Microsoft 365 Management for SMBs &middot; UAE</p><p style="margin:6px 0 0"><a href="mailto:support@skymaxx.company" style="color:#60a5fa;text-decoration:none">support@skymaxx.company</a> &middot; If you prefer not to receive these messages, just reply with "unsubscribe" and we\'ll remove you immediately.</p></td></tr></table></td></tr></table></body></html>',
    },
    {
        'step':       3,
        'delay_days': 4,
        'name':       'M365 Specific Gaps',
        'subject':    '43% of M365 breaches start the same 5 ways',
        'body':       '<!DOCTYPE html><html><body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Arial,sans-serif"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f3f4f6;padding:24px 12px"><tr><td align="center"><table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.08);max-width:600px"><tr><td style="background:linear-gradient(135deg,#0f172a 0%,#1e3a8a 100%);padding:24px 32px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="color:#ffffff;font-size:22px;font-weight:700;letter-spacing:0.5px">&#9889; SKYMAXX <span style="color:#60a5fa;font-weight:500">TECHNOLOGIES</span></td><td align="right" style="color:#cbd5e1;font-size:12px;font-weight:500">Microsoft 365 Specialists</td></tr></table></td></tr><tr><td style="padding:36px 36px 28px;color:#1f2937;font-size:15px;line-height:1.7"><p style="margin:0 0 16px;font-size:16px">Hello <strong>{{first_name}}</strong>,</p><p style="margin:0 0 16px">One more piece of context that may be useful for {{company}}.</p><div style="background:#eff6ff;border-left:4px solid #2563eb;padding:14px 18px;margin:0 0 18px;border-radius:6px"><p style="margin:0;font-size:14px;color:#1e3a8a">The <strong>Paubox 2025 Email Security Report</strong> analysed 180 breaches reported between January 2024 and January 2025. <strong>43.3% of those breaches involved Microsoft 365</strong> &mdash; largely due to misconfigurations in email security settings, not platform flaws.</p></div><p style="margin:0 0 12px">In October 2025 alone, Microsoft Threat Intelligence reported <strong>blocking over 13 million AI-generated phishing emails</strong> from a single campaign source. The attacks that succeed almost always trace back to the same gaps:</p><table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin:0 0 18px"><tr><td style="padding:8px 0;border-bottom:1px solid #e5e7eb;color:#374151;font-size:14px"><strong style="color:#0f172a">1. Identity risk detection exists but is not enforced.</strong> Microsoft Entra ID Protection signals are visible in the portal, but no Conditional Access policy actually blocks risky sign-ins.</td></tr><tr><td style="padding:8px 0;border-bottom:1px solid #e5e7eb;color:#374151;font-size:14px"><strong style="color:#0f172a">2. MFA is deployed but bypassable.</strong> Legacy authentication protocols (IMAP, POP, SMTP basic auth) remain enabled, allowing attackers to skip MFA entirely.</td></tr><tr><td style="padding:8px 0;border-bottom:1px solid #e5e7eb;color:#374151;font-size:14px"><strong style="color:#0f172a">3. DMARC is set to p=none.</strong> Spoofed emails appearing to come from your domain still reach customers and partners. Most SMB tenants we audit have never moved past p=none.</td></tr><tr><td style="padding:8px 0;border-bottom:1px solid #e5e7eb;color:#374151;font-size:14px"><strong style="color:#0f172a">4. Exchange Online Protection on defaults.</strong> Default rules are intentionally conservative. Tuning anti-phishing, anti-spam, and Safe Links / Safe Attachments policies to your business raises the bar significantly.</td></tr><tr><td style="padding:8px 0;color:#374151;font-size:14px"><strong style="color:#0f172a">5. Microsoft Secure Score never reviewed.</strong> Microsoft assigns every tenant a Secure Score with prioritised recommendations. Most owners have never opened it.</td></tr></table><p style="margin:0 0 8px">Each of these takes one to three hours to fix properly. Reply if you would like a written summary of where {{company}} stands on these five items &mdash; I can have a one-page report to you within 48 hours, no commitment required.</p><table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:24px 0 8px"><tr><td style="background:#2563eb;border-radius:8px;box-shadow:0 1px 2px rgba(37,99,235,0.3)"><a href="mailto:support@skymaxx.company?subject=Send%20me%20the%20one-page%20tenant%20report" style="display:inline-block;padding:13px 28px;color:#ffffff;font-weight:600;text-decoration:none;font-size:14px;letter-spacing:0.3px">&rarr; Send the 1-page report</a></td></tr></table><p style="margin:24px 0 0;color:#374151">Best regards,<br/><strong style="color:#0f172a">SKYMAXX Support Team</strong><br/><span style="color:#64748b;font-size:13px">SKYMAXX Technologies</span><br/><a href="https://www.skymaxx.company" style="color:#2563eb;text-decoration:none;font-size:13px;font-weight:500">www.SKYMAXX.Company</a></p></td></tr><tr><td style="background:#f8fafc;padding:16px 36px;border-top:1px solid #e5e7eb"><p style="margin:0 0 6px;color:#64748b;font-size:11px;font-weight:600;letter-spacing:0.5px;text-transform:uppercase">Sources &amp; Further Reading</p><div style="color:#64748b;font-size:11px;line-height:1.6">&bull; Paubox 2025 Healthcare Email Security Report: <a href="https://www.paubox.com/blog" style="color:#2563eb">paubox.com</a><br/>&bull; Microsoft Secure Score documentation: <a href="https://learn.microsoft.com/en-us/defender-xdr/microsoft-secure-score" style="color:#2563eb">learn.microsoft.com/defender-xdr/microsoft-secure-score</a><br/>&bull; DMARC.org &mdash; SMB implementation guide: <a href="https://dmarc.org/overview/" style="color:#2563eb">dmarc.org/overview</a></div></td></tr><tr><td style="background:#0f172a;padding:18px 36px;color:#94a3b8;font-size:11px;line-height:1.5"><p style="margin:0">SKYMAXX Technologies &middot; Microsoft 365 Management for SMBs &middot; UAE</p><p style="margin:6px 0 0"><a href="mailto:support@skymaxx.company" style="color:#60a5fa;text-decoration:none">support@skymaxx.company</a> &middot; If you prefer not to receive these messages, just reply with "unsubscribe" and we\'ll remove you immediately.</p></td></tr></table></td></tr></table></body></html>',
    },
    {
        'step':       4,
        'delay_days': 7,
        'name':       'Industry Pattern',
        'subject':    '61% of SMBs were breached last year — what we see in their tenants',
        'body':       '<!DOCTYPE html><html><body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Arial,sans-serif"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f3f4f6;padding:24px 12px"><tr><td align="center"><table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.08);max-width:600px"><tr><td style="background:linear-gradient(135deg,#0f172a 0%,#1e3a8a 100%);padding:24px 32px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="color:#ffffff;font-size:22px;font-weight:700;letter-spacing:0.5px">&#9889; SKYMAXX <span style="color:#60a5fa;font-weight:500">TECHNOLOGIES</span></td><td align="right" style="color:#cbd5e1;font-size:12px;font-weight:500">Microsoft 365 Specialists</td></tr></table></td></tr><tr><td style="padding:36px 36px 28px;color:#1f2937;font-size:15px;line-height:1.7"><p style="margin:0 0 16px;font-size:16px">Hello <strong>{{first_name}}</strong>,</p><p style="margin:0 0 16px">Stepping back from product details, here is the wider pattern from the field.</p><div style="background:#f0fdf4;border-left:4px solid #16a34a;padding:14px 18px;margin:0 0 18px;border-radius:6px"><p style="margin:0;font-size:14px;color:#14532d"><strong>ConnectWise SMB Threat Report 2025:</strong> 61% of small businesses experienced a breach in the past 12 months. 79% experienced at least one cyber incident in the past five years. 57% now rank cybersecurity as their #1 operational priority.</p></div><p style="margin:0 0 16px">The pattern these reports describe is consistent with what we see in SMB tenants we audit:</p><ul style="margin:0 0 16px 0;padding:0 0 0 22px;color:#374151;font-size:14px"><li style="margin:0 0 8px"><strong>Most SMBs already own the right tools.</strong> Microsoft 365 Business Premium contains Defender, Intune Mobile Device Management, and Entra ID P1 &mdash; capabilities that, configured properly, give SMBs enterprise-grade defences for roughly $22 per user per month.</li><li style="margin:0 0 8px"><strong>The gap is operational, not financial.</strong> Settings drift over time. Staff turnover leaves orphaned accounts and stale policies. New Microsoft features ship monthly and rarely get reviewed.</li><li style="margin:0 0 8px"><strong>Recovery is far more expensive than prevention.</strong> The same IBM report referenced earlier shows that breaches discovered by the attacker (extortion, public leak) cost <strong>$5.08 million on average</strong>, compared to <strong>$4.18 million</strong> when internal security teams catch them first.</li><li style="margin:0 0 8px"><strong>The 2024 Microsoft &ldquo;Midnight Blizzard&rdquo; breach</strong> &mdash; which affected Microsoft itself &mdash; began with a single legacy test tenant that had no MFA enabled. If a misconfigured corner of Microsoft\'s own environment can be the entry point, every SMB tenant has the same risk surface.</li></ul><p style="margin:0 0 16px">SKYMAXX exists to close that operational gap for SMBs that do not have a dedicated security team. We are a small, focused team in the UAE &mdash; not a generalist IT shop &mdash; and Microsoft 365 management is all we do.</p><p style="margin:0 0 8px">If you would like that one-page tenant review I mentioned, just reply <em>&ldquo;audit&rdquo;</em> and I will start it.</p><table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:24px 0 8px"><tr><td style="background:#2563eb;border-radius:8px;box-shadow:0 1px 2px rgba(37,99,235,0.3)"><a href="mailto:support@skymaxx.company?subject=Start%20the%20SKYMAXX%20tenant%20audit" style="display:inline-block;padding:13px 28px;color:#ffffff;font-weight:600;text-decoration:none;font-size:14px;letter-spacing:0.3px">&rarr; Start the audit</a></td></tr></table><p style="margin:24px 0 0;color:#374151">Best regards,<br/><strong style="color:#0f172a">SKYMAXX Support Team</strong><br/><span style="color:#64748b;font-size:13px">SKYMAXX Technologies</span><br/><a href="https://www.skymaxx.company" style="color:#2563eb;text-decoration:none;font-size:13px;font-weight:500">www.SKYMAXX.Company</a></p></td></tr><tr><td style="background:#f8fafc;padding:16px 36px;border-top:1px solid #e5e7eb"><p style="margin:0 0 6px;color:#64748b;font-size:11px;font-weight:600;letter-spacing:0.5px;text-transform:uppercase">Sources &amp; Further Reading</p><div style="color:#64748b;font-size:11px;line-height:1.6">&bull; ConnectWise SMB Threat Report 2025: <a href="https://www.connectwise.com/blog/smb-cybersecurity-statistics-and-trends" style="color:#2563eb">connectwise.com/smb-cybersecurity-trends</a><br/>&bull; CSA Analysis of Microsoft Midnight Blizzard Breach: <a href="https://cloudsecurityalliance.org/blog/2025/09/15/reflecting-on-the-2024-microsoft-breach" style="color:#2563eb">cloudsecurityalliance.org</a><br/>&bull; FBI 2024 Internet Crime Report: <a href="https://www.ic3.gov/AnnualReport/Reports/2024_IC3Report.pdf" style="color:#2563eb">ic3.gov/AnnualReport</a></div></td></tr><tr><td style="background:#0f172a;padding:18px 36px;color:#94a3b8;font-size:11px;line-height:1.5"><p style="margin:0">SKYMAXX Technologies &middot; Microsoft 365 Management for SMBs &middot; UAE</p><p style="margin:6px 0 0"><a href="mailto:support@skymaxx.company" style="color:#60a5fa;text-decoration:none">support@skymaxx.company</a> &middot; If you prefer not to receive these messages, just reply with "unsubscribe" and we\'ll remove you immediately.</p></td></tr></table></td></tr></table></body></html>',
    },
    {
        'step':       5,
        'delay_days': 7,
        'name':       'Breakup — Resources',
        'subject':    'Closing the file — and 4 free resources for {{company}}',
        'body':       '<!DOCTYPE html><html><body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Arial,sans-serif"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f3f4f6;padding:24px 12px"><tr><td align="center"><table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.08);max-width:600px"><tr><td style="background:linear-gradient(135deg,#0f172a 0%,#1e3a8a 100%);padding:24px 32px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="color:#ffffff;font-size:22px;font-weight:700;letter-spacing:0.5px">&#9889; SKYMAXX <span style="color:#60a5fa;font-weight:500">TECHNOLOGIES</span></td><td align="right" style="color:#cbd5e1;font-size:12px;font-weight:500">Microsoft 365 Specialists</td></tr></table></td></tr><tr><td style="padding:36px 36px 28px;color:#1f2937;font-size:15px;line-height:1.7"><p style="margin:0 0 16px;font-size:16px">Hello <strong>{{first_name}}</strong>,</p><p style="margin:0 0 16px">This will be my last note for now.</p><p style="margin:0 0 16px">I respect that no reply is itself a reply, and I will close your file after this. I wanted to leave a few resources behind that may be genuinely useful for {{company}} regardless of whether we ever speak.</p><table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin:0 0 18px;background:#f8fafc;border-radius:8px;padding:0"><tr><td style="padding:14px 18px;color:#374151;font-size:14px"><p style="margin:0 0 10px;font-weight:600;color:#0f172a">Free resources worth bookmarking:</p><p style="margin:0 0 8px">&bull; <strong>Your Microsoft Secure Score</strong> &mdash; sign in to the Microsoft 365 admin centre and search &ldquo;Secure Score&rdquo;. It gives a numeric rating and prioritised list of fixes specific to your tenant. <a href="https://security.microsoft.com/securescore" style="color:#2563eb">security.microsoft.com/securescore</a></p><p style="margin:0 0 8px">&bull; <strong>CISA &ldquo;Bad Practices&rdquo;</strong> &mdash; the US Cybersecurity Agency&rsquo;s short list of practices to retire immediately. Free, plain-English, and applies to every SMB. <a href="https://www.cisa.gov/BadPractices" style="color:#2563eb">cisa.gov/BadPractices</a></p><p style="margin:0 0 8px">&bull; <strong>DMARC checker</strong> &mdash; tells you in seconds whether your domain can be spoofed by attackers. <a href="https://dmarcian.com/dmarc-inspector/" style="color:#2563eb">dmarcian.com/dmarc-inspector</a></p><p style="margin:0">&bull; <strong>Have I Been Pwned</strong> &mdash; check whether any {{company}} email addresses appear in known data breaches. <a href="https://haveibeenpwned.com" style="color:#2563eb">haveibeenpwned.com</a></p></td></tr></table><p style="margin:0 0 16px">If anything changes in the future &mdash; a phishing incident, a compliance question, an upcoming audit, or simple curiosity about your tenant&rsquo;s posture &mdash; you can reach me at <a href="mailto:support@skymaxx.company" style="color:#2563eb">support@skymaxx.company</a>. A human from our team responds, and we only work with Microsoft 365 for SMBs.</p><p style="margin:0 0 8px">Wishing you and {{company}} secure operations going forward.</p><table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:24px 0 8px"><tr><td style="background:#2563eb;border-radius:8px;box-shadow:0 1px 2px rgba(37,99,235,0.3)"><a href="mailto:support@skymaxx.company?subject=Hi%20SKYMAXX%20—%20keep%20me%20on%20your%20list" style="display:inline-block;padding:13px 28px;color:#ffffff;font-weight:600;text-decoration:none;font-size:14px;letter-spacing:0.3px">&rarr; Stay in touch</a></td></tr></table><p style="margin:24px 0 0;color:#374151">Best regards,<br/><strong style="color:#0f172a">SKYMAXX Support Team</strong><br/><span style="color:#64748b;font-size:13px">SKYMAXX Technologies</span><br/><a href="https://www.skymaxx.company" style="color:#2563eb;text-decoration:none;font-size:13px;font-weight:500">www.SKYMAXX.Company</a></p></td></tr><tr><td style="background:#f8fafc;padding:16px 36px;border-top:1px solid #e5e7eb"><p style="margin:0 0 6px;color:#64748b;font-size:11px;font-weight:600;letter-spacing:0.5px;text-transform:uppercase">Sources &amp; Further Reading</p><div style="color:#64748b;font-size:11px;line-height:1.6">&bull; Microsoft Secure Score: <a href="https://learn.microsoft.com/en-us/defender-xdr/microsoft-secure-score" style="color:#2563eb">learn.microsoft.com/defender-xdr/microsoft-secure-score</a><br/>&bull; CISA Bad Practices: <a href="https://www.cisa.gov/BadPractices" style="color:#2563eb">cisa.gov/BadPractices</a><br/>&bull; Have I Been Pwned: <a href="https://haveibeenpwned.com" style="color:#2563eb">haveibeenpwned.com</a></div></td></tr><tr><td style="background:#0f172a;padding:18px 36px;color:#94a3b8;font-size:11px;line-height:1.5"><p style="margin:0">SKYMAXX Technologies &middot; Microsoft 365 Management for SMBs &middot; UAE</p><p style="margin:6px 0 0"><a href="mailto:support@skymaxx.company" style="color:#60a5fa;text-decoration:none">support@skymaxx.company</a> &middot; If you prefer not to receive these messages, just reply with "unsubscribe" and we\'ll remove you immediately.</p></td></tr></table></td></tr></table></body></html>',
    },
]

# Auto-reply template
AUTO_REPLY_TEMPLATE = {
    'subject': 'We received your message \u2014 SKYMAXX Technologies',
    'body': '<!DOCTYPE html><html><body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,Arial,sans-serif"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f3f4f6;padding:24px 12px"><tr><td align="center"><table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.08);max-width:600px"><tr><td style="background:linear-gradient(135deg,#0f172a 0%,#1e3a8a 100%);padding:24px 32px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="color:#ffffff;font-size:22px;font-weight:700;letter-spacing:0.5px">&#9889; SKYMAXX <span style="color:#60a5fa;font-weight:500">TECHNOLOGIES</span></td><td align="right" style="color:#cbd5e1;font-size:12px;font-weight:500">Microsoft 365 Specialists</td></tr></table></td></tr><tr><td style="padding:36px 36px 28px;color:#1f2937;font-size:15px;line-height:1.7"><p style="margin:0 0 16px;font-size:16px">Hello <strong>{{name}}</strong>,</p><p style="margin:0 0 16px">Thank you for reaching out to <strong>SKYMAXX Technologies</strong>.</p><p style="margin:0 0 16px">We\'ve received your message and a member of our team will respond within <strong>24 hours</strong> (business days, UAE time).</p><p style="margin:0 0 16px">If your matter is urgent, please include "URGENT" in your subject line and we\'ll prioritize it.</p><p style="margin:0 0 8px">In the meantime, you can learn more about our Microsoft 365 management services at <a href="https://www.skymaxx.company" style="color:#2563eb;text-decoration:none;font-weight:600">www.SKYMAXX.Company</a>.</p><p style="margin:24px 0 0;color:#374151">Best regards,<br/><strong style="color:#0f172a">SKYMAXX Support Team</strong><br/><span style="color:#64748b;font-size:13px">SKYMAXX Technologies</span><br/><a href="https://www.skymaxx.company" style="color:#2563eb;text-decoration:none;font-size:13px;font-weight:500">www.SKYMAXX.Company</a></p></td></tr><tr><td style="background:#f8fafc;padding:22px 36px;border-top:1px solid #e5e7eb"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="color:#64748b;font-size:12px;line-height:1.6"><strong style="color:#0f172a">SKYMAXX Technologies</strong> &nbsp;&middot;&nbsp; Microsoft 365 Management for SMBs<br/><a href="https://www.skymaxx.company" style="color:#2563eb;text-decoration:none;font-weight:500">www.SKYMAXX.Company</a> &nbsp;&middot;&nbsp; <a href="mailto:support@skymaxx.company" style="color:#2563eb;text-decoration:none;font-weight:500">support@skymaxx.company</a><br/><br/><span style="font-size:11px;color:#94a3b8">You\'re receiving this because your business profile matched our outreach criteria. <a href="mailto:support@skymaxx.company?subject=UNSUBSCRIBE" style="color:#94a3b8;text-decoration:underline">Unsubscribe</a></span></td></tr></table></td></tr></table></td></tr></table></body></html>',
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


def send_via_zepto(to_email, to_name, subject, html_body, log_id=None):
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
        "from": {"address": FROM_EMAIL, "name": FROM_NAME},
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
        tpl = SEQUENCE_TEMPLATES[next_step - 1]
        subject = personalize(tpl["subject"], lead)
        body    = personalize(tpl["body"],    lead)

        # Insert log first to get log_id for tracking
        conn = get_db()
        cur = conn.execute("""INSERT INTO email_log (lead_id, step, to_email, subject, status, error_msg)
                        VALUES (?, ?, ?, ?, 'sending', '')""",
                     [lead["id"], next_step, lead["email"], subject])
        log_id = cur.lastrowid
        conn.commit(); conn.close()

        ok, err = send_via_zepto(lead["email"], lead["name"], subject, body, log_id=log_id)
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
                next_tpl = SEQUENCE_TEMPLATES[next_step]
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
    """Dashboard stats — bulletproof, never raises 500."""
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

    s = {
        "total_leads":   _safe_count("SELECT COUNT(*) FROM leads"),
        "in_sequence":   _safe_count("SELECT COUNT(*) FROM leads WHERE in_sequence=1"),
        "with_email":    _safe_count("SELECT COUNT(*) FROM leads WHERE email IS NOT NULL AND email != ''"),
        "replied":       _safe_count("SELECT COUNT(*) FROM leads WHERE replied=1"),
        "today_sent":    _safe_call(get_todays_send_count) if "get_todays_send_count" in globals() else 0,
        "daily_limit":   DAILY_SEND_LIMIT if "DAILY_SEND_LIMIT" in globals() else 300,
        "bcc_support":   BCC_SUPPORT if "BCC_SUPPORT" in globals() else True,
        "total_sent":    _safe_count("SELECT COUNT(*) FROM email_log WHERE status='success'"),
        "total_failed":  _safe_count("SELECT COUNT(*) FROM email_log WHERE status='failed'"),
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
    next_tpl = SEQUENCE_TEMPLATES[next_step - 1]
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
    if not (1 <= step <= len(SEQUENCE_TEMPLATES)):
        return jsonify({"error": "invalid step"}), 400
    name = request.args.get("name", "Sarah Johnson")
    tpl = SEQUENCE_TEMPLATES[step - 1]
    fake_lead = {"name": name, "city": "Dubai", "website": "example.com"}
    return jsonify({
        "step":    tpl["step"],
        "subject": personalize(tpl["subject"], fake_lead),
        "body":    personalize(tpl["body"], fake_lead),
        "from_email": FROM_EMAIL,
        "from_name":  FROM_NAME,
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
    tpl = SEQUENCE_TEMPLATES[step - 1]
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
        else:
            c["next_send_at"] = None
            c["leads_finished"] = 0
            c["leads_total"] = 0
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
            SET in_sequence=1, sequence_step=0, next_send_at=?, campaign_id=?
            WHERE id=?""",
            [now_iso, cid, lid_int])
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
        GROUP BY g.id ORDER BY g.name""").fetchall())
    conn.close()
    return jsonify({"groups": rows})


@app.route("/api/groups", methods=["POST"])
def create_group():
    data = request.json or {}
    name = (data.get("name") or "").strip()
    if not name: return jsonify({"error": "name required"}), 400
    conn = get_db()
    try:
        cur = conn.execute("INSERT INTO contact_groups (name, description, color) VALUES (?,?,?)",
                           [name, data.get("description",""), data.get("color","#3b82f6")])
        conn.commit()
        gid = cur.lastrowid
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 400
    conn.close()
    return jsonify({"id": gid, "name": name})


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
            "step": step, "name": SEQUENCE_TEMPLATES[step-1]["name"],
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
