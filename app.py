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

# ─────────────────────────────────────────────
# 5-EMAIL SEQUENCE TEMPLATES
# ─────────────────────────────────────────────
SEQUENCE_TEMPLATES = [
    {
        'step': 1,
        'delay_days': 0,
        'name': 'Initial Outreach',
        'subject': 'Quick question about your Office 365 environment',
        'body': '<!DOCTYPE html><html><body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,Arial,sans-serif"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f3f4f6;padding:24px 12px"><tr><td align="center"><table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.08);max-width:600px"><tr><td style="background:linear-gradient(135deg,#0f172a 0%,#1e3a8a 100%);padding:24px 32px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="color:#ffffff;font-size:22px;font-weight:700;letter-spacing:0.5px">&#9889; SKYMAXX <span style="color:#60a5fa;font-weight:500">TECHNOLOGIES</span></td><td align="right" style="color:#cbd5e1;font-size:12px;font-weight:500">Microsoft 365 Specialists</td></tr></table></td></tr><tr><td style="padding:36px 36px 28px;color:#1f2937;font-size:15px;line-height:1.7"><p style="margin:0 0 16px;font-size:16px">Hello <strong>{{first_name}}</strong>,</p><p style="margin:0 0 16px">I noticed many growing businesses are using Microsoft 365 but often struggle with the day-to-day management that comes with it.</p><p style="margin:0 0 16px">Tasks such as <strong>email administration, user onboarding/offboarding, license management, Microsoft Teams support, SharePoint administration, security settings, MFA, backups, and troubleshooting</strong> can consume significant time and resources.</p><p style="margin:0 0 16px">At <strong>SKYMAXX Technologies</strong>, we provide complete Microsoft 365 management and support services for SMBs &mdash; helping businesses maintain a secure, reliable, and well-managed environment without the expense of a large internal IT team.</p><p style="margin:0 0 8px">Would you be open to a brief conversation to see if we could help reduce the workload on your team?</p><table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:24px 0 8px"><tr><td style="background:#2563eb;border-radius:8px;box-shadow:0 1px 2px rgba(37,99,235,0.3)"><a href="mailto:support@skymaxx.company?subject=Yes,%20let%27s%20talk%20about%20Microsoft%20365" style="display:inline-block;padding:13px 28px;color:#ffffff;font-weight:600;text-decoration:none;font-size:14px;letter-spacing:0.3px">Reply &raquo;&nbsp; Let&rsquo;s Talk</a></td></tr></table><p style="margin:24px 0 0;color:#374151">Best regards,<br/><strong style="color:#0f172a">{{sender_name}}</strong><br/><span style="color:#64748b;font-size:13px">SKYMAXX Technologies</span><br/><a href="https://www.skymaxx.company" style="color:#2563eb;text-decoration:none;font-size:13px;font-weight:500">www.SKYMAXX.Company</a></p></td></tr><tr><td style="background:#f8fafc;padding:22px 36px;border-top:1px solid #e5e7eb"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="color:#64748b;font-size:12px;line-height:1.6"><strong style="color:#0f172a">SKYMAXX Technologies</strong> &nbsp;&middot;&nbsp; Microsoft 365 Management for SMBs<br/><a href="https://www.skymaxx.company" style="color:#2563eb;text-decoration:none;font-weight:500">www.SKYMAXX.Company</a> &nbsp;&middot;&nbsp; <a href="mailto:support@skymaxx.company" style="color:#2563eb;text-decoration:none;font-weight:500">support@skymaxx.company</a><br/><br/><span style="font-size:11px;color:#94a3b8">You\'re receiving this because your business profile matched our outreach criteria. <a href="mailto:support@skymaxx.company?subject=UNSUBSCRIBE" style="color:#94a3b8;text-decoration:underline">Unsubscribe</a></span></td></tr></table></td></tr></table></td></tr></table></body></html>',
    },
    {
        'step': 2,
        'delay_days': 3,
        'name': 'Follow-up',
        'subject': 'Re: Microsoft 365 Support',
        'body': '<!DOCTYPE html><html><body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,Arial,sans-serif"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f3f4f6;padding:24px 12px"><tr><td align="center"><table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.08);max-width:600px"><tr><td style="background:linear-gradient(135deg,#0f172a 0%,#1e3a8a 100%);padding:24px 32px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="color:#ffffff;font-size:22px;font-weight:700;letter-spacing:0.5px">&#9889; SKYMAXX <span style="color:#60a5fa;font-weight:500">TECHNOLOGIES</span></td><td align="right" style="color:#cbd5e1;font-size:12px;font-weight:500">Microsoft 365 Specialists</td></tr></table></td></tr><tr><td style="padding:36px 36px 28px;color:#1f2937;font-size:15px;line-height:1.7"><p style="margin:0 0 16px;font-size:16px">Hello <strong>{{first_name}}</strong>,</p><p style="margin:0 0 16px">Just following up on my previous email.</p><p style="margin:0 0 8px">Many SMBs reach out to us when their internal teams become overwhelmed with Microsoft 365 administration tasks &mdash; or when they want additional expertise without hiring more IT staff.</p><p style="margin:18px 0 6px;font-weight:600;color:#0f172a">We regularly assist with:</p><table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:12px 0 20px"><tr><td style="padding:7px 0;color:#374151;vertical-align:top;width:24px"><span style="color:#2563eb;font-weight:700;font-size:16px">&#10003;</span></td><td style="padding:7px 0;color:#374151">Exchange Online administration</td></tr><tr><td style="padding:7px 0;color:#374151;vertical-align:top;width:24px"><span style="color:#2563eb;font-weight:700;font-size:16px">&#10003;</span></td><td style="padding:7px 0;color:#374151">Microsoft Teams support</td></tr><tr><td style="padding:7px 0;color:#374151;vertical-align:top;width:24px"><span style="color:#2563eb;font-weight:700;font-size:16px">&#10003;</span></td><td style="padding:7px 0;color:#374151">SharePoint &amp; OneDrive management</td></tr><tr><td style="padding:7px 0;color:#374151;vertical-align:top;width:24px"><span style="color:#2563eb;font-weight:700;font-size:16px">&#10003;</span></td><td style="padding:7px 0;color:#374151">User and license administration</td></tr><tr><td style="padding:7px 0;color:#374151;vertical-align:top;width:24px"><span style="color:#2563eb;font-weight:700;font-size:16px">&#10003;</span></td><td style="padding:7px 0;color:#374151">MFA and security configurations</td></tr><tr><td style="padding:7px 0;color:#374151;vertical-align:top;width:24px"><span style="color:#2563eb;font-weight:700;font-size:16px">&#10003;</span></td><td style="padding:7px 0;color:#374151">Backup and recovery support</td></tr><tr><td style="padding:7px 0;color:#374151;vertical-align:top;width:24px"><span style="color:#2563eb;font-weight:700;font-size:16px">&#10003;</span></td><td style="padding:7px 0;color:#374151">Technical troubleshooting</td></tr></table><p style="margin:0 0 8px">If Microsoft 365 management is taking valuable time away from your team, I\'d be happy to discuss how we may be able to assist.</p><table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:24px 0 8px"><tr><td style="background:#2563eb;border-radius:8px;box-shadow:0 1px 2px rgba(37,99,235,0.3)"><a href="mailto:support@skymaxx.company?subject=Re%3A%20Microsoft%20365%20Support" style="display:inline-block;padding:13px 28px;color:#ffffff;font-weight:600;text-decoration:none;font-size:14px;letter-spacing:0.3px">Reply &raquo;&nbsp; Discuss Support</a></td></tr></table><p style="margin:24px 0 0;color:#374151">Best regards,<br/><strong style="color:#0f172a">{{sender_name}}</strong><br/><span style="color:#64748b;font-size:13px">SKYMAXX Technologies</span><br/><a href="https://www.skymaxx.company" style="color:#2563eb;text-decoration:none;font-size:13px;font-weight:500">www.SKYMAXX.Company</a></p></td></tr><tr><td style="background:#f8fafc;padding:22px 36px;border-top:1px solid #e5e7eb"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="color:#64748b;font-size:12px;line-height:1.6"><strong style="color:#0f172a">SKYMAXX Technologies</strong> &nbsp;&middot;&nbsp; Microsoft 365 Management for SMBs<br/><a href="https://www.skymaxx.company" style="color:#2563eb;text-decoration:none;font-weight:500">www.SKYMAXX.Company</a> &nbsp;&middot;&nbsp; <a href="mailto:support@skymaxx.company" style="color:#2563eb;text-decoration:none;font-weight:500">support@skymaxx.company</a><br/><br/><span style="font-size:11px;color:#94a3b8">You\'re receiving this because your business profile matched our outreach criteria. <a href="mailto:support@skymaxx.company?subject=UNSUBSCRIBE" style="color:#94a3b8;text-decoration:underline">Unsubscribe</a></span></td></tr></table></td></tr></table></td></tr></table></body></html>',
    },
    {
        'step': 3,
        'delay_days': 7,
        'name': 'Problem-Focused',
        'subject': 'Is your Microsoft 365 environment fully protected?',
        'body': '<!DOCTYPE html><html><body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,Arial,sans-serif"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f3f4f6;padding:24px 12px"><tr><td align="center"><table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.08);max-width:600px"><tr><td style="background:linear-gradient(135deg,#0f172a 0%,#1e3a8a 100%);padding:24px 32px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="color:#ffffff;font-size:22px;font-weight:700;letter-spacing:0.5px">&#9889; SKYMAXX <span style="color:#60a5fa;font-weight:500">TECHNOLOGIES</span></td><td align="right" style="color:#cbd5e1;font-size:12px;font-weight:500">Microsoft 365 Specialists</td></tr></table></td></tr><tr><td style="padding:36px 36px 28px;color:#1f2937;font-size:15px;line-height:1.7"><p style="margin:0 0 16px;font-size:16px">Hello <strong>{{first_name}}</strong>,</p><p style="margin:0 0 16px">A common challenge we see among SMBs is that Microsoft 365 is deployed successfully &mdash; but <strong>ongoing management and security reviews</strong> often receive less attention due to limited resources.</p><p style="margin:0 0 4px">This can lead to issues such as:</p><table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:16px 0 22px;background:#fef3c7;border-left:4px solid #f59e0b;border-radius:6px;width:100%"><tr><td style="padding:16px 22px"><table role="presentation" cellpadding="0" cellspacing="0" border="0" style="width:100%"><tr><td style="padding:4px 0;color:#78350f">&middot;&nbsp;&nbsp;Inactive accounts remaining enabled</td></tr><tr><td style="padding:4px 0;color:#78350f">&middot;&nbsp;&nbsp;Unused licenses increasing costs</td></tr><tr><td style="padding:4px 0;color:#78350f">&middot;&nbsp;&nbsp;Incomplete MFA deployment</td></tr><tr><td style="padding:4px 0;color:#78350f">&middot;&nbsp;&nbsp;Limited backup strategies</td></tr><tr><td style="padding:4px 0;color:#78350f">&middot;&nbsp;&nbsp;Security settings that haven\'t been reviewed recently</td></tr></table></td></tr></table><p style="margin:0 0 16px">Our team helps businesses <strong>manage and maintain</strong> their Microsoft 365 environments so they can focus on operations and growth.</p><p style="margin:0 0 8px">Would it make sense to have a quick discussion about your current setup?</p><table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:24px 0 8px"><tr><td style="background:#2563eb;border-radius:8px;box-shadow:0 1px 2px rgba(37,99,235,0.3)"><a href="mailto:support@skymaxx.company?subject=Microsoft%20365%20Review" style="display:inline-block;padding:13px 28px;color:#ffffff;font-weight:600;text-decoration:none;font-size:14px;letter-spacing:0.3px">Reply &raquo;&nbsp; Review My Setup</a></td></tr></table><p style="margin:24px 0 0;color:#374151">Best regards,<br/><strong style="color:#0f172a">{{sender_name}}</strong><br/><span style="color:#64748b;font-size:13px">SKYMAXX Technologies</span><br/><a href="https://www.skymaxx.company" style="color:#2563eb;text-decoration:none;font-size:13px;font-weight:500">www.SKYMAXX.Company</a></p></td></tr><tr><td style="background:#f8fafc;padding:22px 36px;border-top:1px solid #e5e7eb"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="color:#64748b;font-size:12px;line-height:1.6"><strong style="color:#0f172a">SKYMAXX Technologies</strong> &nbsp;&middot;&nbsp; Microsoft 365 Management for SMBs<br/><a href="https://www.skymaxx.company" style="color:#2563eb;text-decoration:none;font-weight:500">www.SKYMAXX.Company</a> &nbsp;&middot;&nbsp; <a href="mailto:support@skymaxx.company" style="color:#2563eb;text-decoration:none;font-weight:500">support@skymaxx.company</a><br/><br/><span style="font-size:11px;color:#94a3b8">You\'re receiving this because your business profile matched our outreach criteria. <a href="mailto:support@skymaxx.company?subject=UNSUBSCRIBE" style="color:#94a3b8;text-decoration:underline">Unsubscribe</a></span></td></tr></table></td></tr></table></td></tr></table></body></html>',
    },
    {
        'step': 4,
        'delay_days': 14,
        'name': 'Value Follow-up',
        'subject': 'Additional Microsoft 365 support when needed',
        'body': '<!DOCTYPE html><html><body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,Arial,sans-serif"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f3f4f6;padding:24px 12px"><tr><td align="center"><table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.08);max-width:600px"><tr><td style="background:linear-gradient(135deg,#0f172a 0%,#1e3a8a 100%);padding:24px 32px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="color:#ffffff;font-size:22px;font-weight:700;letter-spacing:0.5px">&#9889; SKYMAXX <span style="color:#60a5fa;font-weight:500">TECHNOLOGIES</span></td><td align="right" style="color:#cbd5e1;font-size:12px;font-weight:500">Microsoft 365 Specialists</td></tr></table></td></tr><tr><td style="padding:36px 36px 28px;color:#1f2937;font-size:15px;line-height:1.7"><p style="margin:0 0 16px;font-size:16px">Hello <strong>{{first_name}}</strong>,</p><p style="margin:0 0 16px">I wanted to reach out one more time regarding <strong>Microsoft 365 support</strong>.</p><p style="margin:0 0 8px">Some organizations prefer to manage Microsoft 365 internally but occasionally need assistance with:</p><table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:12px 0 20px"><tr><td style="padding:7px 0;color:#374151;vertical-align:top;width:24px"><span style="color:#2563eb;font-weight:700;font-size:16px">&#10003;</span></td><td style="padding:7px 0;color:#374151">Migrations and upgrades</td></tr><tr><td style="padding:7px 0;color:#374151;vertical-align:top;width:24px"><span style="color:#2563eb;font-weight:700;font-size:16px">&#10003;</span></td><td style="padding:7px 0;color:#374151">Tenant administration</td></tr><tr><td style="padding:7px 0;color:#374151;vertical-align:top;width:24px"><span style="color:#2563eb;font-weight:700;font-size:16px">&#10003;</span></td><td style="padding:7px 0;color:#374151">Security improvements</td></tr><tr><td style="padding:7px 0;color:#374151;vertical-align:top;width:24px"><span style="color:#2563eb;font-weight:700;font-size:16px">&#10003;</span></td><td style="padding:7px 0;color:#374151">User provisioning and licensing</td></tr><tr><td style="padding:7px 0;color:#374151;vertical-align:top;width:24px"><span style="color:#2563eb;font-weight:700;font-size:16px">&#10003;</span></td><td style="padding:7px 0;color:#374151">Troubleshooting complex issues</td></tr><tr><td style="padding:7px 0;color:#374151;vertical-align:top;width:24px"><span style="color:#2563eb;font-weight:700;font-size:16px">&#10003;</span></td><td style="padding:7px 0;color:#374151">Ongoing administration support</td></tr></table><p style="margin:0 0 16px">Whether you need <strong>occasional assistance or ongoing management</strong>, our team can provide support based on your requirements.</p><p style="margin:0 0 8px">Would a short call next week be worth considering?</p><table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:24px 0 8px"><tr><td style="background:#2563eb;border-radius:8px;box-shadow:0 1px 2px rgba(37,99,235,0.3)"><a href="mailto:support@skymaxx.company?subject=Microsoft%20365%20support" style="display:inline-block;padding:13px 28px;color:#ffffff;font-weight:600;text-decoration:none;font-size:14px;letter-spacing:0.3px">Reply &raquo;&nbsp; Schedule a Call</a></td></tr></table><p style="margin:24px 0 0;color:#374151">Best regards,<br/><strong style="color:#0f172a">{{sender_name}}</strong><br/><span style="color:#64748b;font-size:13px">SKYMAXX Technologies</span><br/><a href="https://www.skymaxx.company" style="color:#2563eb;text-decoration:none;font-size:13px;font-weight:500">www.SKYMAXX.Company</a></p></td></tr><tr><td style="background:#f8fafc;padding:22px 36px;border-top:1px solid #e5e7eb"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="color:#64748b;font-size:12px;line-height:1.6"><strong style="color:#0f172a">SKYMAXX Technologies</strong> &nbsp;&middot;&nbsp; Microsoft 365 Management for SMBs<br/><a href="https://www.skymaxx.company" style="color:#2563eb;text-decoration:none;font-weight:500">www.SKYMAXX.Company</a> &nbsp;&middot;&nbsp; <a href="mailto:support@skymaxx.company" style="color:#2563eb;text-decoration:none;font-weight:500">support@skymaxx.company</a><br/><br/><span style="font-size:11px;color:#94a3b8">You\'re receiving this because your business profile matched our outreach criteria. <a href="mailto:support@skymaxx.company?subject=UNSUBSCRIBE" style="color:#94a3b8;text-decoration:underline">Unsubscribe</a></span></td></tr></table></td></tr></table></td></tr></table></body></html>',
    },
    {
        'step': 5,
        'delay_days': 21,
        'name': 'Breakup',
        'subject': 'Should I close the file?',
        'body': '<!DOCTYPE html><html><body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,Arial,sans-serif"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f3f4f6;padding:24px 12px"><tr><td align="center"><table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.08);max-width:600px"><tr><td style="background:linear-gradient(135deg,#0f172a 0%,#1e3a8a 100%);padding:24px 32px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="color:#ffffff;font-size:22px;font-weight:700;letter-spacing:0.5px">&#9889; SKYMAXX <span style="color:#60a5fa;font-weight:500">TECHNOLOGIES</span></td><td align="right" style="color:#cbd5e1;font-size:12px;font-weight:500">Microsoft 365 Specialists</td></tr></table></td></tr><tr><td style="padding:36px 36px 28px;color:#1f2937;font-size:15px;line-height:1.7"><p style="margin:0 0 16px;font-size:16px">Hello <strong>{{first_name}}</strong>,</p><p style="margin:0 0 16px">I\'ve reached out a few times regarding Microsoft 365 management and support services.</p><p style="margin:0 0 16px">I understand this may not be a priority right now, so I don\'t want to continue filling your inbox unnecessarily.</p><p style="margin:0 0 16px">If managing <strong>Microsoft 365, Exchange Online, Teams, SharePoint, licensing, security, backups, or user administration</strong> becomes a challenge in the future, we\'d be happy to have a conversation.</p><p style="margin:0 0 16px">You can learn more about our services here: <a href="https://www.skymaxx.company" style="color:#2563eb;text-decoration:none;font-weight:600">www.SKYMAXX.Company</a></p><p style="margin:0 0 8px">Thank you for your time, and I wish you and your team continued success.</p><p style="margin:24px 0 0;color:#374151">Best regards,<br/><strong style="color:#0f172a">{{sender_name}}</strong><br/><span style="color:#64748b;font-size:13px">SKYMAXX Technologies</span><br/><a href="https://www.skymaxx.company" style="color:#2563eb;text-decoration:none;font-size:13px;font-weight:500">www.SKYMAXX.Company</a></p></td></tr><tr><td style="background:#f8fafc;padding:22px 36px;border-top:1px solid #e5e7eb"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="color:#64748b;font-size:12px;line-height:1.6"><strong style="color:#0f172a">SKYMAXX Technologies</strong> &nbsp;&middot;&nbsp; Microsoft 365 Management for SMBs<br/><a href="https://www.skymaxx.company" style="color:#2563eb;text-decoration:none;font-weight:500">www.SKYMAXX.Company</a> &nbsp;&middot;&nbsp; <a href="mailto:support@skymaxx.company" style="color:#2563eb;text-decoration:none;font-weight:500">support@skymaxx.company</a><br/><br/><span style="font-size:11px;color:#94a3b8">You\'re receiving this because your business profile matched our outreach criteria. <a href="mailto:support@skymaxx.company?subject=UNSUBSCRIBE" style="color:#94a3b8;text-decoration:underline">Unsubscribe</a></span></td></tr></table></td></tr></table></td></tr></table></body></html>',
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
    full_name = (lead.get("name") or "").strip()
    first_name = full_name.split()[0] if full_name else "there"
    return (text.replace("{{first_name}}", first_name)
                .replace("{{name}}", first_name)
                .replace("{{sender_name}}", FROM_NAME)
                .replace("{{company}}", lead.get("name", "your company"))
                .replace("{{city}}", lead.get("city", "your area"))
                .replace("{{website}}", lead.get("website", "")))

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
        "bcc_support":  BCC_SUPPORT,
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
            conn.execute("""INSERT OR IGNORE INTO leads (name,email,phone,website,city,country,source,status)
                VALUES (?,?,?,?,?,?,'uploaded','new')""",
                [row.get("name","").strip(), row.get("email","").strip(),
                 row.get("phone","").strip(), row.get("website","").strip(),
                 row.get("city","").strip(), row.get("country","").strip()])
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
    """Approve campaign and actually enroll leads."""
    conn = get_db()
    camp = conn.execute("SELECT * FROM campaigns WHERE id=? AND status='pending_approval'",
                        [cid]).fetchone()
    if not camp:
        conn.close()
        return jsonify({"error": "campaign not found or not pending"}), 404
    
    lead_ids = json.loads(camp["lead_ids_json"])
    enrolled = 0
    for lid in lead_ids:
        cur = conn.execute("""UPDATE leads 
            SET in_sequence=1, sequence_step=0, next_send_at=?
            WHERE id=? AND replied=0 AND unsubscribed=0""",
            [datetime.utcnow().isoformat(), lid])
        if cur.rowcount > 0: enrolled += 1
    
    approved_by = (request.json or {}).get("approved_by", "user")
    conn.execute("""UPDATE campaigns 
        SET status='approved', approved_at=?, approved_by=?, actually_started=?
        WHERE id=?""", 
        [datetime.utcnow().isoformat(), approved_by, enrolled, cid])
    conn.commit()
    conn.close()
    
    return jsonify({"approved": True, "campaign_id": cid, "enrolled": enrolled})


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
        conn.execute(f"""UPDATE leads SET in_sequence=1, next_send_at=?
            WHERE id IN ({placeholders}) AND sequence_step<5 AND replied=0 AND unsubscribed=0""",
            [datetime.utcnow().isoformat()] + lead_ids)
    conn.execute("UPDATE campaigns SET status='approved' WHERE id=?", [cid])
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

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
