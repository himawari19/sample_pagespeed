
#!/usr/bin/env python3
import os, sys, json, argparse, urllib.parse, urllib.request, urllib.error, re

def env(name, default=None, required=False):
    v = os.getenv(name, default)
    if required and (v is None or str(v).strip() == ""):
        print(f"[notify_telegram] Missing required env: {name}", file=sys.stderr)
        sys.exit(2)
    return v

def is_probably_valid_token(tok: str) -> bool:
    # e.g., 123456789:AA... (basic sanity check)
    return bool(re.match(r"^\d{6,}:[A-Za-z0-9_-]{20,}$", tok or ""))

def is_probably_valid_chat_id(cid: str) -> bool:
    # user/group/channel ids: numbers (may start with -100...), or @username
    return bool(re.match(r"^(-?\d+|@[A-Za-z0-9_]{5,})$", cid or ""))

def send_message(token: str, chat_id: str, text: str, parse_mode: str = "HTML", debug=False):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(url, data=body)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        print(f"[notify_telegram] HTTPError {e.code}: {e.reason}. Response: {detail}", file=sys.stderr)
        if debug:
            print(f"[notify_telegram] Debug payload: {json.dumps(data)}", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Send a Telegram notification for PSI workflow.")
    parser.add_argument("--status", required=True, help="SUCCESS or FAILED")
    parser.add_argument("--site", default="https://www.nutriclub.co.id")
    parser.add_argument("--duration", default=None, help="Run duration in seconds")
    parser.add_argument("--dashboard", default="https://maazway.github.io/pagespeed-monitor-nr")
    parser.add_argument("--extra", default=None, help="Extra note to append")
    args = parser.parse_args()

    token = env("TELEGRAM_BOT_TOKEN", required=True).strip()
    chat_id = env("TELEGRAM_CHAT_ID", required=True).strip()
    debug = os.getenv("DEBUG_TELEGRAM") == "1"

    if not is_probably_valid_token(token):
        print("[notify_telegram] Your TELEGRAM_BOT_TOKEN looks invalid. Expected format like '1234567:ABC...'", file=sys.stderr)
    if not is_probably_valid_chat_id(chat_id):
        print("[notify_telegram] Your TELEGRAM_CHAT_ID looks invalid. Use numeric ID (e.g., 12345678 or -100...) or @channelusername.", file=sys.stderr)

    status = args.status.strip().upper()
    badge = f"<b>{'✅ SUCCESS' if status.startswith('S') else '❌ FAILED'}</b>"

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
    lines.append(f"<b>Site: {args.site}</b>")
    lines.append("")  # spasi baris kosong
    lines.append(f"Time: {now_str}")
    lines.append(f"Status: {badge}")
    lines.append("")  # spasi baris kosong
    if args.dashboard:
        lines.append(f"Dashboard: {args.dashboard}")

    # IMPORTANT: buat variabel `text`
    text = "\n".join(lines)

    # Kirim
    res = send_message(token, chat_id, text, debug=debug)

    # Masked debug header
    if debug:
        print(f"[notify_telegram] token={token[:8]}*** chat_id={chat_id} len(text)={len(text)}", file=sys.stderr)

    res = send_message(token, chat_id, text, debug=debug)
    ok = bool(res.get("ok"))
    if not ok:
        print(f"[notify_telegram] Telegram API error: {res}", file=sys.stderr)
        sys.exit(1)
    print("[notify_telegram] Sent.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
