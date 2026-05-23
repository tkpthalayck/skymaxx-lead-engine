# ⚡ SKYMAXX Lead Engine

Full-stack lead generation + email outreach app for UAE & GCC markets.

**Built by:** Ali | SKYMAXX IT Solutions  
**Contact:** support@royalgroups.store

---

## Features

- 🗺️ **Google Maps Lead Finder** — Search UAE/GCC businesses by keyword & city
- 📊 **Lead Dashboard** — Manage, filter, tag & export leads
- 📧 **ZeptoMail Campaigns** — Send personalized outreach emails
- 📥 **CSV Export** — Download all leads anytime
- 🔒 **Secure** — API keys stored as env variables, never in code

---

## Deploy to Render (5 minutes)

### Step 1 — Push to GitHub
```bash
git init
git add .
git commit -m "Initial deploy"
git remote add origin https://github.com/YOUR_USERNAME/skymaxx-lead-engine.git
git push -u origin main
```

### Step 2 — Create Render Web Service
1. Go to [render.com](https://render.com) → New → Web Service
2. Connect your GitHub repo
3. Render auto-detects `render.yaml`

### Step 3 — Set Environment Variables on Render
In your Render dashboard → Environment:

| Key | Value |
|-----|-------|
| `GOOGLE_MAPS_API_KEY` | `AIzaSyC_knxg1Z0ru5xfrLCQ8Rag1w8X1J0A_6Y` |
| `ZEPTO_TOKEN` | Your ZeptoMail send token |
| `FROM_EMAIL` | Your verified sender email |
| `FROM_NAME` | `Ali \| SKYMAXX IT Solutions` |

### Step 4 — Deploy!
Click **Deploy** — your app will be live at:  
`https://skymaxx-lead-engine.onrender.com`

---

## Local Development

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in your keys
python app.py
# Open http://localhost:5000
```

---

## Google Maps API Setup

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Enable **Places API** and **Places Details API**
3. Create an API key and add to `.env`

## ZeptoMail Setup

1. Go to [zeptomail.com](https://www.zeptomail.com)
2. Add & verify your sending domain
3. Copy the **Send Mail Token**
4. Add to `.env` as `ZEPTO_TOKEN`

---

## Tech Stack

- **Backend:** Python / Flask
- **Database:** SQLite (persistent disk on Render)
- **Frontend:** Vanilla HTML/CSS/JS (no build step needed)
- **Deployment:** Render.com
- **APIs:** Google Maps Places API + ZeptoMail
