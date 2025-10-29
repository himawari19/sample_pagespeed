import os
import argparse
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path
from datetime import datetime, timezone
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

def env(name, default=None, required=False):
    v = os.getenv(name, default)
    if required and (v is None or str(v).strip() == ""):
        raise SystemExit(f"[notify_email] Missing required env: {name}")
    return v

def build_subject(prefix: str, site: str, tzname: str):
    now = datetime.now(timezone.utc)
    if ZoneInfo and tzname:
        try:
            now = datetime.now(ZoneInfo(tzname))
        except Exception:
            pass
    return f"{prefix} {now.strftime('%d %b %Y | %H:%M %Z')}"

def build_body(site: str, status: str, duration: str, dashboard_url: str | None):
    status_text = "Success" if status.lower().startswith("s") else "Fail"
    lines = []
    lines.append(f"<h2>Automation Test Report for {site}</h2>")
    lines.append("<p><b>Summary:</b></p>")
    lines.append("<ul>")
    lines.append(f"<li><b>Status</b>: {status_text}</li>")
    if duration:
        lines.append(f"<li><b>Duration</b>: {duration} seconds</li>")
    lines.append("</ul>")
    if dashboard_url:
        lines.append(f"<p>Dashboard: <a href='{dashboard_url}'>{dashboard_url}</a></p>")
    lines.append("<p>Check the attached HTML report for the full test results.</p>")
    lines.append("<p>This report is auto-generated and maintained by Mazway.</p>")
    return "\n".join(lines)

def send_email(host, port, user, password, sender, to_list, subject, html_body, attachment_path=None):
    msg = EmailMessage()
    if "<" in sender and ">" in sender:
        display, email = sender.split("<", 1)
        email = email.strip(">").strip()
        sender_formatted = formataddr((display.strip(), email))
    else:
        sender_formatted = sender
    msg["From"] = sender_formatted
    msg["To"] = ", ".join(to_list)
    msg["Subject"] = subject
    msg.set_content("This email requires an HTML capable client.")
    msg.add_alternative(html_body, subtype="html")

    if attachment_path:
        p = Path(attachment_path)
        if p.exists():
            data = p.read_bytes()
            msg.add_attachment(data, maintype="text", subtype="html", filename=p.name)

    context = ssl.create_default_context()
    if str(port) == "465":
        with smtplib.SMTP_SSL(host, int(port), context=context) as server:
            if user and password:
                server.login(user, password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(host, int(port)) as server:
            server.starttls(context=context)
            if user and password:
                server.login(user, password)
            server.send_message(msg)

def main():
    parser = argparse.ArgumentParser(description="Send email summary for PSI workflow.")
    parser.add_argument("--site", required=True, help="Target site URL, e.g., https://www.generasimaju.co.id")
    parser.add_argument("--status", required=True, choices=["Success","Fail","Failed","Success/Fail"], help="Execution status")
    parser.add_argument("--duration", required=True, help="Run duration in seconds")
    parser.add_argument("--report", default=None, help="Path to HTML report to attach")
    parser.add_argument("--to", default=None, help="Comma-separated extra recipients override/append")
    parser.add_argument("--dashboard", default=None, help="Dashboard URL to include in the body")
    args = parser.parse_args()

    host = env("SMTP_HOST", required=True)
    port = env("SMTP_PORT", required=True)
    user = env("SMTP_USER", default=None)
    password = env("SMTP_PASS", default=None)
    sender = env("EMAIL_FROM", required=True)
    tzname = os.getenv("TZ", "Asia/Jakarta")
    prefix = os.getenv("EMAIL_SUBJECT_PREFIX", "PageSpeed Insight Report")

    base_to = [e.strip() for e in env("EMAIL_TO", required=True).split(",") if e.strip()]
    if args.to and args.to.strip():
        extra = [e.strip() for e in args.to.split(",") if e.strip()]
        seen = set()
        recipients = []
        for r in base_to + extra:
            if r not in seen:
                recipients.append(r); seen.add(r)
    else:
        recipients = base_to

    subject = build_subject(prefix, args.site, tzname)
    html_body = build_body(args.site, args.status, args.duration, args.dashboard)

    send_email(host, port, user, password, sender, recipients, subject, html_body, args.report)
    print("[notify_email] Sent.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
