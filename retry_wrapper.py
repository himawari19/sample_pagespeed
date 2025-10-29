# retry_wrapper.py
import os, time, random
from typing import Dict

def _is_valid_result(res: Dict) -> bool:
    """
    Hasil dianggap valid jika 4 kategori ada dan berupa angka 0..100.
    (Skor 0 itu valid di PSI; yang kita hindari adalah None/missing/format aneh)
    """
    try:
        for k in ("performance", "accessibility", "best_practices", "seo"):
            v = res.get(k, None)
            if v is None:
                return False
            if not isinstance(v, (int, float)):
                return False
            if v < 0 or v > 100:
                return False
        return True
    except Exception:
        return False


def run_psi_until_success(run_psi_func, url: str, strategy: str, api_key: str, locale: str):
    """
    LOOP sampai run_psi_func(...) mengembalikan hasil valid.
    - Backoff eksponensial + jitter (default base=3s, max sleep=120s).
    - Guard-rails:
        * MAX_MINUTES (default 55 di GitHub Actions) → elak job timeout 60m.
        * MAX_ATTEMPTS (0 = tak dibatasi).
    - Bisa dimatikan via LOOP_UNTIL_SUCCESS=0 (kembali ke perilaku lama).
    """
    require_success = os.getenv("LOOP_UNTIL_SUCCESS", "1") == "1"
    max_attempts = int(os.getenv("MAX_ATTEMPTS", "0"))  # 0 = unlimited
    max_minutes = int(os.getenv("MAX_MINUTES", "55" if os.getenv("GITHUB_ACTIONS") else "0"))
    base = float(os.getenv("RETRY_BASE_SECONDS", "3"))
    cap  = float(os.getenv("RETRY_MAX_SECONDS", "120"))

    started = time.time()
    attempt = 0
    last_error = None

    while True:
        attempt += 1
        try:
            res = run_psi_func(url, strategy=strategy, api_key=api_key, locale=locale)
            if _is_valid_result(res):
                if attempt > 1:
                    res["retry_attempts"] = attempt
                return res
            else:
                last_error = "invalid result (missing categories/scores)"
        except Exception as e:
            last_error = str(e)

        if not require_success:
            # kembali ke perilaku lama (biar kompatibel saat debug)
            raise Exception(last_error or "PSI failed")

        # Guard-rails untuk CI (hindari job 60m mati)
        if max_attempts and attempt >= max_attempts:
            raise Exception(f"PSI failed after {attempt} attempts: {last_error}")
        if max_minutes and (time.time() - started) / 60.0 >= max_minutes:
            raise Exception(f"PSI time budget exceeded (~{max_minutes} min): {last_error}")

        # Exponential backoff + jitter
        sleep_s = min(cap, base * (2 ** min(attempt, 6))) + random.uniform(0, 1.5)
        if sleep_s > cap:
            sleep_s = cap
        print(f"[retry] {strategy} {url} attempt {attempt} failed: {last_error}. sleep {sleep_s:.1f}s")
        time.sleep(sleep_s)
