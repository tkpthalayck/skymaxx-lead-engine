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
    full_name = (lead.get("name") or "").strip()
    first_name = full_name.split()[0] if full_name else "there"
    return (text.replace("{{first_name}}", first_name)
                .replace("{{name}}", first_name)
                .replace("{{sender_name}}", FROM_NAME)
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
        "htmlbody": html_body
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
            conn.execute("""INSERT OR IGNORE INTO leads (name,email,phone,website,city,country)
                VALUES (?,?,?,?,?,?)""",
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
        "graph_api":    bool(AZURE_TENANT_ID and AZURE_CLIENT_ID and AZURE_CLIENT_SECRET),
        "mailbox":      MAILBOX_EMAIL,
    })

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
