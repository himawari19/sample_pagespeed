import os
import argparse
import json
import sys
import urllib.parse
import urllib.request

def env(name, default=None, required=False):
    v = os.getenv(name, default)
    if required and (v is None or str(v).strip() == ""):
        print(f"[notify_telegram] Missing required env: {name}", file=sys.stderr)
        sys.exit(2)
    return v

def send_message(token: str, chat_id: str, text: str, parse_mode: str = "HTML"):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(url, data=body)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))

def main():
    parser = argparse.ArgumentParser(description="Send a Telegram notification for PSI workflow.")
    parser.add_argument("--status", required=True, help="SUCCESS or FAILED")
    parser.add_argument("--site", default="https://www.generasimaju.co.id")
    parser.add_argument("--duration", default=None, help="Run duration in seconds")
    parser.add_argument("--dashboard", default=None, help="Dashboard URL to include")
    parser.add_argument("--extra", default=None, help="Extra note to append")
    args = parser.parse_args()

    token = env("TELEGRAM_BOT_TOKEN", required=True)
    chat_id = env("TELEGRAM_CHAT_ID", required=True)

    status = args.status.strip().upper()
    if status in {"FAIL", "FAILED"}:
        badge = "❌ FAILED"
    else:
        badge = "✅ SUCCESS"

    tz = os.getenv("TZ", "Asia/Jakarta")
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        now_str = datetime.now(ZoneInfo(tz)).strftime("%d %b %Y | %H:%M %Z")
    except Exception:
        from datetime import datetime, timezone
        now_str = datetime.now(timezone.utc).strftime("%d %b %Y | %H:%M UTC")

    lines = []
    lines.append(f"<b>PageSpeed Insight Report</b>")
    lines.append(f"Status: <b>{badge}</b>")
    lines.append(f"Site: <code>{args.site}</code>")
    if args.duration:
        lines.append(f"Duration: <b>{args.duration} s</b>")
    lines.append(f"Time: {now_str}")
    if args.dashboard:
        lines.append(f"Dashboard: {args.dashboard}")
    if args.extra:
        lines.append(args.extra)

    text = "\n".join(lines)

    res = send_message(token, chat_id, text)
    ok = bool(res.get("ok"))
    if not ok:
        print(f"[notify_telegram] Telegram API error: {res}", file=sys.stderr)
        sys.exit(1)
    print("[notify_telegram] Sent.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
