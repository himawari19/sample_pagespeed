import os
import requests
from datetime import datetime, timezone, timedelta
import argparse
import time  # tambahan

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")  # single chat or channel id (@channelusername)

def _post(text: str) -> bool:
    if not BOT_TOKEN or not CHAT_ID:
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        r = requests.post(url, json=payload, timeout=20)
        r.raise_for_status()
        return True
    except Exception:
        return False

# === tambahan
def format_duration(seconds: int) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s}s" if m else f"{s}s"

def notify_simple_report(status: str = "SUCCESS") -> bool:
    """Kirim pesan ringkas hasil PageSpeed Nutriclub ke Telegram + durasi run."""
    wib = timezone(timedelta(hours=7))
    ts = datetime.now(wib).strftime("%d/%m/%Y %H:%M:%S WIB")

    # === tambahan: ambil total durasi workflow dari env
    start = float(os.getenv("START_TS", time.time()))
    end = float(os.getenv("END_TS", time.time()))
    duration = format_duration(end - start)

    lines = [
        "<b>Hasil Pengecekan PageSpeed Nutriclub</b>",
        "",
        f"Tanggal & Waktu: <b>{ts}</b>",
        f"Status: <b>{status}</b>",
        f"Durasi Run: <b>{duration}</b>",  # tambahan
        "",
        "Dashboard utama:",
        "<a href=\"https://maazway.github.io/pagespeed-monitor-nr\">https://maazway.github.io/pagespeed-monitor-nr</a>",
        "",
        "History (json file):",
        "<a href=\"https://maazway.github.io/pagespeed-monitor-nr/history.json\">https://maazway.github.io/pagespeed-monitor-nr/history.json</a>",
    ]
    return _post("\n".join(lines))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", default="SUCCESS", help="Status laporan (SUCCESS/FAILED)")
    args = parser.parse_args()

    notify_simple_report(
        status=args.status,
    )
