#!/usr/bin/env python3
"""
notify_email.py — Send PageSpeed Insight Report via SMTP (WIB time, multi-project)

ENV (isi via .env atau GitHub Secrets):
  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS,
  EMAIL_FROM, EMAIL_TO          # comma-separated list
Opsional:
  TZ=Asia/Jakarta

CLI:
  python notify_email.py --site https://www.generasimaju.co.id \
    --status Success --duration 4.99 --report dashboard/index.html
"""

import argparse
import os
import smtplib
import ssl
from email.message import EmailMessage
from datetime import datetime
from zoneinfo import ZoneInfo
import mimetypes
import sys
from typing import List, Optional


# === Utility: current time in WIB ===
def _wib_now(tz_env: Optional[str] = None) -> datetime:
    tzname = tz_env or os.getenv("TZ", "Asia/Jakarta")
    try:
        return datetime.now(ZoneInfo(tzname))
    except Exception:
        return datetime.now(ZoneInfo("Asia/Jakarta"))


# === Build email message ===
def build_message(
    site: str,
    status: str,
    duration: str,
    sender: str,
    recipients: List[str],
    tz_env: Optional[str] = None,
) -> EmailMessage:
    now = _wib_now(tz_env)
    # Subject otomatis: PageSpeed Insight GenMaju Report - DD Mon YYYY | HH:MM WIB
    subject = f"PageSpeed Insight Report - {now.strftime('%d %b %Y')} | {now.strftime('%H:%M')} WIB"

    # Body email lengkap (tampilkan URL site di atas)
    body = (
        f"Site     : {site}\n"
        "Summary:\n"
        f"• Status   : {status}\n"
        f"• Duration : {duration} seconds\n\n"
        "Check the attached HTML report for the full test results\n"
        "This report is auto-generated and maintained by Mazway"
    )

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.set_content(body)
    return msg


# === Attach optional HTML report ===
def attach_file(msg: EmailMessage, path: Optional[str]) -> None:
    if not path:
        return
    if not os.path.exists(path):
        print(f"[notify_email] WARNING: attachment not found: {path}", file=sys.stderr)
        return
    ctype, _ = mimetypes.guess_type(path)
    if not ctype:
        ctype = "application/octet-stream"
    maintype, subtype = ctype.split("/", 1)
    with open(path, "rb") as f:
        msg.add_attachment(
            f.read(),
            maintype=maintype,
            subtype=subtype,
            filename=os.path.basename(path),
        )


# === Send email via SMTP ===
def send_email(msg: EmailMessage, host: str, port: int, user: str, password: str) -> None:
    # 465 = implicit SSL; selain itu gunakan STARTTLS
    if str(port) == "465":
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, context=context) as server:
            if user and password:
                server.login(user, password)
            server.send_message(msg)
        return

    context = ssl.create_default_context()
    with smtplib.SMTP(host, port) as server:
        server.ehlo()
        try:
            server.starttls(context=context)
            server.ehlo()
        except smtplib.SMTPException:
            # server mungkin tidak support STARTTLS (25/plain); lanjutkan
            pass
        if user and password:
            server.login(user, password)
        server.send_message(msg)


# === CLI Arguments ===
def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Send email with PageSpeed Insight summary and HTML report attachment."
    )
    ap.add_argument("--site", required=True, help="Site URL under test")
    ap.add_argument("--status", required=True, choices=["Success", "Fail", "Failed", "Success/Fail"])
    ap.add_argument("--duration", required=True, help="Duration in seconds (string/float)")
    ap.add_argument("--report", default=None, help="Path to HTML report to attach (optional)")
    ap.add_argument(
        "--to",
        default=None,
        help="Comma-separated recipients (override EMAIL_TO from env)",
    )
    return ap.parse_args()


# === Main logic ===
def main() -> int:
    args = parse_args()

    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASS", "")
    sender = os.getenv("EMAIL_FROM")
    env_to = os.getenv("EMAIL_TO", "")
    tz_env = os.getenv("TZ", "Asia/Jakarta")

    if not host or not sender or (not env_to and not args.to):
        print(
            "[notify_email] Missing SMTP_HOST/EMAIL_FROM/EMAIL_TO. "
            "Set via env or GitHub Secrets.",
            file=sys.stderr,
        )
        return 2

    recipients = [e.strip() for e in (args.to.split(",") if args.to else env_to.split(",")) if e.strip()]
    if not recipients:
        print("[notify_email] No recipients resolved.", file=sys.stderr)
        return 2

    msg = build_message(
        site=args.site,
        status="Fail" if args.status == "Failed" else args.status,
        duration=args.duration,
        sender=sender,
        recipients=recipients,
        tz_env=tz_env,
    )
    attach_file(msg, args.report)
    send_email(msg, host=host, port=port, user=user, password=password)

    print(f"[notify_email] Email sent to: {', '.join(recipients)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
