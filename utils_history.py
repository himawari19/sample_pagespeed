from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone

HISTORY_DIR = Path("dashboard/history")
HISTORY_FILE = Path("dashboard/history.json")
HISTORY_MAX_ENTRIES = 500  # ring buffer di file utama, simpan 500 run terakhir

def _ensure_dirs():
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not HISTORY_FILE.exists():
        HISTORY_FILE.write_text("[]", encoding="utf-8")

def _normalize_url(u: str) -> str:
    if not isinstance(u, str): 
        return ""
    # Normalisasi trailing slash → tanpa slash di akhir (kecuali root '/')
    if u.endswith("/") and len(u) > len("https://x/"):
        return u.rstrip("/")
    return u

def append_history_with_rotation(results):
    """
    Append run results to dashboard/history.json and also write monthly archive
    to dashboard/history/YYYY-MM.json. Adds run_at_utc per item if missing.
    """
    _ensure_dirs()
    # timestamp now (UTC)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    # normalize rows
    out_rows = []
    for r in results:
        row = dict(r)
        row["url"] = _normalize_url(row.get("url", ""))
        row["run_at_utc"] = row.get("run_at_utc") or now
        out_rows.append(row)

    # append to head file (ring buffer)
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8") or "[]")
        if not isinstance(data, list):
            data = []
    except Exception:
        data = []
    data.extend(out_rows)
    # keep last HISTORY_MAX_ENTRIES
    if len(data) > HISTORY_MAX_ENTRIES:
        data = data[-HISTORY_MAX_ENTRIES:]
    # tulis dengan indent agar rapih
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    # monthly archive file
    month_key = now[:7]  # YYYY-MM
    month_path = HISTORY_DIR / f"{month_key}.json"
    try:
        mdata = json.loads(month_path.read_text(encoding="utf-8")) if month_path.exists() else []
        if not isinstance(mdata, list):
            mdata = []
    except Exception:
        mdata = []
    mdata.extend(out_rows)
    with open(month_path, "w", encoding="utf-8") as f:
        json.dump(mdata, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(
        f"history.json updated: {len(data)} records (last {HISTORY_MAX_ENTRIES}); "
        f"{month_path.name} archive: {len(mdata)} records"
    )
