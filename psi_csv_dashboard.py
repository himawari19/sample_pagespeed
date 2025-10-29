# pagespeed-monitor-ci/psi_csv_dashboard.py

import os, csv, json, argparse, time
from datetime import datetime, timezone, timedelta
from pathlib import Path
import requests
from dotenv import load_dotenv
from utils_history import append_history_with_rotation
from retry_wrapper import run_psi_until_success

load_dotenv()

PSI_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


# ---------------- PSI Runner ----------------
def run_psi(url: str, strategy: str = "mobile", api_key: str = "", locale: str = "en"):
    params = {
        "url": url,
        "strategy": strategy,
        "category": ["performance", "accessibility", "best-practices", "seo"],
        "locale": locale,
    }
    if api_key:
        params["key"] = api_key

    r = requests.get(PSI_ENDPOINT, params=params, timeout=60)
    r.raise_for_status()
    data = r.json()
    lh = data.get("lighthouseResult", {}) or {}
    cats = (lh.get("categories") or {})

    def get_score(cat):
        v = (cats.get(cat) or {}).get("score")
        try:
            return int(round(float(v or 0) * 100))
        except Exception:
            return 0

    return {
        "url": url,
        "strategy": strategy,
        "performance": get_score("performance"),
        "accessibility": get_score("accessibility"),
        "best_practices": get_score("best-practices"),
        "seo": get_score("seo"),
    }


def collect_psi_results(csv_path: str, sleep_sec: float = 2.0):
    # >>> Tambahan agar api_key & locale tersedia di scope ini
    api_key = os.getenv("PSI_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("PSI_API_KEY is missing")
    locale = (os.getenv("LOCALE", "en") or "en").strip()

    items = []
    with open(csv_path, "r", encoding="utf-8") as f:
        rd = csv.DictReader(f)
        for row in rd:
            url = (row.get("url") or "").strip()
            strat = (row.get("strategy") or "mobile").strip().lower()
            if url and strat in ("mobile", "desktop"):
                items.append((url, strat))

    if not items:
        raise SystemExit("urls.csv empty or invalid (expected headers: url,strategy).")

    results = []  # <- pastikan deklarasi ini ADA sebelum try/except & append

    for i, (u, st) in enumerate(items, start=1):
        try:
            # Loop-until-success (ON via env, OFF kalau LOOP_UNTIL_SUCCESS=0)
            if os.getenv("LOOP_UNTIL_SUCCESS", "1") == "1":
                res = run_psi_until_success(run_psi, u, st, api_key, locale)
            else:
                res = run_psi(u, st, api_key, locale)
        except Exception as e:
            res = {
                "url": u, "strategy": st,
                "performance": 0,
                "accessibility": 0,
                "best_practices": 0,
                "seo": 0,
                "error": str(e),
            }
        results.append(res)
        time.sleep(sleep_sec)

    return results

def write_csv_and_json(rows, out_csv, out_json):
    fields = ["url", "strategy", "performance", "accessibility", "best_practices", "seo", "error"]
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in fields})

    # biarkan struktur JSON original agar kompatibel dengan history aggregator
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({"generated_at": "UTC", "data": rows}, f, ensure_ascii=False, indent=2)


# ---------------- HTML Renderer ----------------
def render_dashboard(rows, out_html, maintainer_name="MaazWay", maintainer_link="https://github.com/maazway"):
    # helpers local (tidak mengubah fungsi lain)
    def _shorten_url(u: str, max_len: int = 50) -> str:
        try:
            from urllib.parse import urlparse
            p = urlparse(u or "")
            disp = f"{p.scheme}://{p.netloc}{p.path or ''}"
            if p.query:
                disp += f"?{p.query}"
        except Exception:
            disp = u or ""
        return disp if len(disp) <= max_len else disp[: max_len - 1] + "…"

    def _extract_error_code(err: str) -> str:
        if not err:
            return ""
        import re as _re

        m = _re.search(r"(\b\d{3}\b)", err)
        return m.group(1) if m else "ERR"

    def badge(val, label):
        if val is None:
            return (
                "<div class='chip chip-gray'><div class='num'>–</div>"
                + f"<div class='lbl'>{label}</div></div>"
            )
        try:
            v = int(val)
        except Exception:
            v = 0
        cls = "green" if v >= 90 else ("orange" if v >= 50 else "red")
        return (
            "<div class='chip chip-"
            + cls
            + "'><div class='num'>"
            + str(v)
            + "</div><div class='lbl'>"
            + label
            + "</div></div>"
        )

    # build cards
    cards = []
    for r in rows:
        url = r.get("url", "")
        strat = r.get("strategy", "")
        perf = r.get("performance")
        acc = r.get("accessibility")
        bp = r.get("best_practices")
        seo = r.get("seo")
        err = r.get("error")
        disp_url = _shorten_url(url, 50)
        code = _extract_error_code(err) if err else ""
        err_html = f"<div class='err-chip'>Error: {code}</div>" if code else ""

        chips = badge(perf, "Performance") + badge(acc, "Accessibility") + badge(bp, "Best Practices") + badge(seo, "SEO")
        cards.append(
        "<div class='card' data-url='" + url + "' data-strategy='" + strat + "'>"
        + "<div class='row'><div class='left'>"
        + "<a class='url urlText' href='" + url + "' target='_blank' rel='noopener'>" + disp_url + "</a>"
        + "<div class='strategy'>[" + strat + "]</div>"
        + err_html
        + "</div><div class='right'>" + chips + "</div></div></div>"
        )
    cards_html = "\n".join(cards)

    # WIB time
    wib = timezone(timedelta(hours=7))
    gen_ts = datetime.now(wib).strftime("%d/%m/%Y %H:%M:%S WIB")

    # HTML template NON f-string (gunakan placeholder)
    html = r"""<!doctype html><html lang='id'>
<meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>PageSpeed Dashboard</title>
<style>
  :root{--bg:#f5f7fb;--card:#fff;--ink:#0f172a;--muted:#64748b;--bd:#e5e7eb;--green:#22c55e;--orange:#f59e0b;--red:#ef4444;--radius:16px;--radius-chip:999px;--primary:#2563eb;--shadow:0 8px 24px rgba(15,23,42,.06)}
  *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 Inter,system-ui,-apple-system,Segoe UI,Roboto,Arial}
  .wrap{max-width:1080px;margin:0 auto;padding:28px 18px}
  h1{font-weight:800;text-align:center;margin:6px 0 8px;letter-spacing:.2px}
  .legend{display:flex;gap:18px;justify-content:center;align-items:center;color:var(--muted);font-size:13px;margin-bottom:14px}
  .dot{width:10px;height:10px;border-radius:999px;display:inline-block;margin-right:6px}
  .dot.green{background:#22c55e}.dot.orange{background:#f59e0b}.dot.red{background:#ef4444}
  .tabs{display:flex;justify-content:center;gap:8px;margin:8px auto 18px;padding:6px;background:#e9eefb;border:1px solid #dbe2f5;border-radius:12px;box-shadow:var(--shadow);width:fit-content;}
  .tabBtn{padding:10px 16px;border:none;background:transparent;border-radius:10px;cursor:pointer;color:#334155;font-weight:600}
  .tabBtn.active{background:var(--primary);color:#fff}

  .toolbar{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin:14px auto 14px;max-width:980px}
  .toolbar .grow{flex:1}
  .input, select{appearance:none;outline:none;border:1px solid var(--bd);background:#fff;border-radius:12px;padding:12px 14px;box-shadow:var(--shadow)}
  .input{width:100%}
  .selectWrap{position:relative}
  .selectWrap::after{content:"▼";position:absolute;right:12px;top:50%;transform:translateY(-50%);font-size:11px;color:#64748b;pointer-events:none}

  .list{display:flex;flex-direction:column;gap:14px}
  .card{background:var(--card);border:1px solid var(--bd);border-radius:var(--radius);padding:16px;box-shadow:var(--shadow)}
  .row{display:flex;align-items:center;gap:18px}
  .left{flex:1 1 auto;min-width:0}
  .right{flex:0 0 auto;display:flex;gap:12px;flex-wrap:wrap}
  .chip{display:flex;flex-direction:column;align-items:center;gap:6px;min-width:76px}
  .chip .num{width:56px;height:56px;border-radius:999px;display:grid;place-items:center;color:#fff;font-weight:800}
  .chip-green .num{background:#16a34a}.chip-orange .num{background:#f59e0b}.chip-red .num{background:#ef4444}.chip-gray .num{background:#94a3b8}
  .chip .lbl{font-size:11.5px;color:#64748b}
  .url{font-weight:700}
  .strategy{display:block;margin-top:4px;color:#64748b;font-size:13px;}
  .urlText{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:inline-block;max-width:100%}
  .err-chip{margin-top:8px;display:inline-block;background:#fee2e2;color:#991b1b;border:1px solid #fecaca;padding:6px 10px;border-radius:10px;font-size:12px;font-family:ui-monospace, SFMono-Regular, Menlo, monospace}
  @media (max-width:640px){.row{flex-direction:column;align-items:flex-start}.right{flex-wrap:wrap}}

  #secTrends .chartWrap{overflow-x:auto;border:1px solid var(--bd);background:#fff;border-radius:16px;padding:14px;box-shadow:var(--shadow)}
  #secTrends .chartInner{min-width:900px}
  footer{margin:22px 0 8px;text-align:center;color:#64748b;font-size:12px}
  footer a{color:#2563eb;text-decoration:none} footer a:hover{text-decoration:underline}
</style>

<div class='wrap'>
  <h1>PageSpeed Dashboard</h1>
  <div class='legend'>
    <span><i class='dot green'></i>90–100</span>
    <span><i class='dot orange'></i>50–89</span>
    <span><i class='dot red'></i>0–49</span>
  </div>

  <div class='tabs'>
    <button id='btnDash' class='tabBtn'>Dashboard</button>
    <button id='btnTrends' class='tabBtn'>Trends</button>
  </div>

  <!-- Dashboard -->
  <section id='secDash'>
    <div class='toolbar'>
      <div class='grow'><input id='search' class='input' placeholder='Cari URL atau strategy (mobile/desktop)...'></div>
      <div class='count' style='color:#64748b;font-size:13px'><span id='count'>__COUNT__</span> hasil</div>
    </div>
    <div id='list' class='list'>__CARDS_HTML__</div>
  </section>

  <!-- Trends -->
  <section id='secTrends' style='display:none'>
    <div class='toolbar'>
      <div class='selectWrap'><select id='trendUrl' class='select'></select></div>
      <div class='selectWrap'><select id='trendMetric' class='select'><option value='performance'>Performance</option><option value='accessibility'>Accessibility</option><option value='best_practices'>Best Practices</option><option value='seo'>SEO</option></select></div>
      <div class='selectWrap'><select id='trendStrategy' class='select'><option value='all'>All strategies</option><option value='mobile'>mobile</option><option value='desktop'>desktop</option></select></div>
      <div class='selectWrap'><select id='trendDate' class='select'></select></div>
      <div class='selectWrap'><select id='trendMonth' class='select'></select></div>
    </div>
    <div class='chartWrap'><div class='chartInner' id='trendChartInner'><canvas id='trendChart' height='260'></canvas></div></div>
    <div class='muted' style='color:#64748b;margin-top:8px'>Sumber: <code>history.json</code> (+ bulanan di <code>history/</code>). Waktu WIB.</div>
  </section>

  <footer>
    Generated: __GEN_TS__<br>
    Maintainer: <a href='__MAINTAINER_LINK__' target='_blank' rel='noopener'>__MAINTAINER_NAME__</a>
  </footer>
</div>

<script src='https://cdn.jsdelivr.net/npm/chart.js'></script>
<script>
(function(){
  // ===== Tabs =====
  const btnDash=document.getElementById('btnDash'), btnTrends=document.getElementById('btnTrends'),
        secDash=document.getElementById('secDash'), secTrends=document.getElementById('secTrends');
  let trendsReady=false;
  function showDash(){secDash.style.display='block';secTrends.style.display='none';btnDash.classList.add('active');btnTrends.classList.remove('active');}
  async function showTrends(){secDash.style.display='none';secTrends.style.display='block';btnTrends.classList.add('active');btnDash.classList.remove('active'); if(!trendsReady){await loadHistory();trendsReady=true;} else {requestAnimationFrame(()=>{if(typeof renderTrend==='function') renderTrend();});}}
  btnDash.addEventListener('click',showDash); btnTrends.addEventListener('click',showTrends); showDash();

  // ===== Search (Dashboard) =====
  const listEl=document.getElementById('list'); const items=Array.from(listEl.querySelectorAll('.card'));
  const searchInput=document.getElementById('search'); const countEl=document.getElementById('count');
  function applyFilter(){const q=(searchInput.value||'').toLowerCase().trim(); let shown=0; items.forEach(el=>{const u=(el.getAttribute('data-url')||'').toLowerCase(); const s=(el.getAttribute('data-strategy')||'').toLowerCase(); const vis=(!q||u.includes(q)||s.includes(q)); el.style.display=vis?'':'none'; if(vis) shown++;}); countEl.textContent=shown;}
  searchInput.addEventListener('input', applyFilter);

  // ===== Trends =====
  // Helpers
  const uniq = (a)=> Array.from(new Set(a));
  function shortenUrl(u,maxLen=50){try{const a=document.createElement('a');a.href=u||'';let disp=(a.protocol?a.protocol+'//':'')+(a.host||'')+(a.pathname||'');if(a.search)disp+=a.search;return disp.length>maxLen?disp.slice(0,maxLen-1)+'…':disp;}catch(e){return u||'';}}
  function pad2(n){return n<10?'0'+n:''+n;}
  function toWIBString(d){ // Date -> 'dd/mm/yyyy HH:MM:SS WIB'
    const w = new Date(d.getTime() + 7*3600*1000);
    return pad2(w.getUTCDate())+'/'+pad2(w.getUTCMonth()+1)+'/'+w.getUTCFullYear()+' '+pad2(w.getUTCHours())+':'+pad2(w.getUTCMinutes())+':'+pad2(w.getUTCSeconds())+' WIB';
  }
  function parseRunAt(s){ // 'YYYY-MM-DDTHH:MM:SSZ' or 'dd/mm/yyyy HH:MM:SS WIB'
    if(!s) return null;
    if(s.includes('WIB')){
      const [dmy, hms] = s.replace(' WIB','').split(' ');
      const [dd,mm,yyyy] = dmy.split('/').map(Number);
      const [HH,MM,SS] = hms.split(':').map(Number);
      const utc = Date.UTC(yyyy, mm-1, dd, HH-7, MM, SS); // WIB -> UTC
      return new Date(utc);
    }
    const d = new Date(s);
    if(String(d)==='Invalid Date') return null;
    return d;
  }
  async function fetchJson(path){try{const res=await fetch(path,{cache:'no-store'}); if(!res.ok) return []; return await res.json();}catch(e){return [];}}

  const urlSel=document.getElementById('trendUrl'),
        metricSel=document.getElementById('trendMetric'),
        stratSel=document.getElementById('trendStrategy'),
        dateSel=document.getElementById('trendDate'),
        monthSel=document.getElementById('trendMonth');
  let historyData=[]; let chart;

  function rebuildSelectors(){
    const urls = uniq(historyData.map(r=>r.url)).sort();
    urlSel.innerHTML = urls.length ? "" : "<option value=''> (no data) </option>";
    urls.forEach(v=>{ const o=document.createElement('option'); o.value=v; o.textContent=shortenUrl(v, 72); urlSel.appendChild(o); });

    // dates: value YYYY-MM-DD; label dd/mm/YYYY
    const rawDates = uniq(historyData.map(r=> (r.run_at_wib||r.run_at_utc||'').slice(0,10))).sort();
    dateSel.innerHTML = "<option value=''> (all dates) </option>";
    rawDates.forEach(v=>{
      let text=v;
      if(/^\d{4}-\d{2}-\d{2}$/.test(v)){ const [Y,M,D]=v.split('-'); text = D+'/'+M+'/'+Y; }
      const o=document.createElement('option'); o.value=v; o.textContent=text; dateSel.appendChild(o);
    });

    // months: value YYYY-MM; label mm/YYYY
    const rawMonths = uniq(historyData.map(r=> (r.run_at_wib||r.run_at_utc||'').slice(0,7))).sort();
    monthSel.innerHTML = "<option value=''> (all months) </option>";
    rawMonths.forEach(v=>{
      let text=v;
      if(/^\d{4}-\d{2}$/.test(v)){ const [Y,M]=v.split('-'); text = M+'/'+Y; }
      const o=document.createElement('option'); o.value=v; o.textContent=text; monthSel.appendChild(o);
    });

    if (!stratSel.value) stratSel.value = 'mobile';
  }

  function buildFiltered(){
    return historyData.filter(r =>
      (!urlSel.value || r.url===urlSel.value) &&
      (!dateSel.value || (r.run_at_wib||r.run_at_utc||'').startsWith(dateSel.value)) &&
      (!monthSel.value || (r.run_at_wib||r.run_at_utc||'').startsWith(monthSel.value)) &&
      (Number(r[metricSel.value]||0) > 0)
    );
  }

  function sortedTimes(a,b){
    const set = new Set([...(a||[]).map(x=>x.t), ...(b||[]).map(x=>x.t)]);
    return Array.from(set).sort((x,y)=>x-y);
  }
  function mapToTimes(times, arr){
    const m = new Map(arr.map(x=>[x.t,x.v]));
    return times.map(t => m.has(t)? m.get(t) : null);
  }

  function renderTrend(){
    const rows = buildFiltered();

    if (stratSel.value === 'all'){
      const byStrat = (key)=> rows
        .filter(r => r.strategy===key)
        .map(r => { const d=parseRunAt(r.run_at_wib || r.run_at_utc); return d && {t:d.getTime(), v:Number(r[metricSel.value]||0)}; })
        .filter(Boolean).sort((a,b)=> a.t-b.t);

      const mb = byStrat('mobile');
      const ds = byStrat('desktop');
      const allTimes = sortedTimes(mb, ds);
      const labs = allTimes.map(t=> toWIBString(new Date(t)));
      const dsArr = [];
      if (mb.length) dsArr.push({label:'mobile', data: mapToTimes(allTimes, mb), spanGaps:true, tension:.25, pointRadius:2});
      if (ds.length) dsArr.push({label:'desktop', data: mapToTimes(allTimes, ds), spanGaps:true, tension:.25, pointRadius:2});

      drawChart(labs, dsArr);
      return;
    }

    const points = rows
      .filter(r=> r.strategy===stratSel.value)
      .map(r => { const d = parseRunAt(r.run_at_wib || r.run_at_utc); return d && {t:d.getTime(), v:Number(r[metricSel.value]||0)}; })
      .filter(Boolean).sort((a,b)=> a.t-b.t)

    const labels = points.map(p => toWIBString(new Date(p.t)));
    const data = points.map(p => p.v);
    drawChart(labels, [{label: metricSel.value+' ('+stratSel.value+')', data, spanGaps:true, tension:.25, pointRadius:2}]);
  }

  function drawChart(labels, datasets){
    const inner = document.getElementById('trendChartInner');
    inner.style.width = Math.max(900, Math.max(1, labels.length) * 60) + 'px';
    const ctx = document.getElementById('trendChart').getContext('2d');
    if (window._chart) window._chart.destroy();
    window._chart = new Chart(ctx, {
      type:'line',
      data:{labels, datasets},
      options:{responsive:true, maintainAspectRatio:false, scales:{y:{min:0,max:100,ticks:{stepSize:10}}}}
    });
    requestAnimationFrame(()=>{ if (window._chart && typeof window._chart.resize==='function') window._chart.resize(); });
  }

  async function loadHistory(){
    let head = await fetchJson('history.json');
    historyData = Array.isArray(head) ? head : [];
    const now = new Date();
    for (let i=1;i<=6;i++){
      const d = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth()-i, 1));
      const mk = d.toISOString().slice(0,7);
      const more = await fetchJson('history/'+mk+'.json');
      if (Array.isArray(more) && more.length) historyData = historyData.concat(more);
    }
    rebuildSelectors();
    renderTrend();
  }

  [urlSel, metricSel, stratSel, dateSel, monthSel].forEach(el => el.addEventListener('change', renderTrend));
})();
</script>
</html>"""

    html = (
        html.replace("__CARDS_HTML__", cards_html)
        .replace("__COUNT__", str(len(rows)))
        .replace("__GEN_TS__", gen_ts)
        .replace("__MAINTAINER_LINK__", maintainer_link)
        .replace("__MAINTAINER_NAME__", maintainer_name)
    )

    out_path = Path(out_html)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"Dashboard HTML saved to {out_html}")


# ---------------- main ----------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default="urls.csv")
    parser.add_argument("--out-csv", default="psi_results.csv")
    parser.add_argument("--out-json", default="psi_results.json")
    parser.add_argument("--out-html", default="dashboard/dashboard.html")
    parser.add_argument("--sleep", type=float, default=2.0, help="Delay (s) between PSI calls")
    parser.add_argument("--maintainer-name", default="MaazWay")
    parser.add_argument("--maintainer-link", default="https://github.com/maazway")
    args = parser.parse_args()

    results = collect_psi_results(args.csv, sleep_sec=args.sleep)
    write_csv_and_json(results, args.out_csv, args.out_json)
    render_dashboard(results, args.out_html, maintainer_name=args.maintainer_name, maintainer_link=args.maintainer_link)
    append_history_with_rotation(results)

    # Optional Telegram notify
    try:
        from notify_telegram import notify_run
        notify_run(results, title="PageSpeed Report")
    except Exception as e:
        print("Telegram notify skipped:", e)


if __name__ == "__main__":
    main()
