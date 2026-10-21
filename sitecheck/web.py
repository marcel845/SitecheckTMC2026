"""
Eenvoudige web-interface: python -m sitecheck.web  →  http://localhost:5050
Voer een URL in, volg de voortgang, open het rapport.
"""
import threading
import uuid
import time
from pathlib import Path
from collections import Counter

import os
from flask import Flask, request, jsonify, send_from_directory, Response

from .cli import run

app = Flask(__name__)
OUT_DIR = Path(os.environ.get("SITECHECK_REPORTS", "rapporten"))
JOBS = {}
PASSWORD = os.environ.get("SITECHECK_PASSWORD", "").strip()


@app.before_request
def _auth():
    """Eenvoudige wachtwoordbeveiliging (HTTP Basic) als SITECHECK_PASSWORD is gezet."""
    if not PASSWORD or request.path == "/health":
        return None
    a = request.authorization
    if a and a.password == PASSWORD:
        return None
    return Response("Inloggen vereist", 401, {"WWW-Authenticate": 'Basic realm="SiteCheck"'})

PAGE = """<!doctype html><html lang="nl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SiteCheck – Opleveringscheck</title>
<style>
body{margin:0;font:15px/1.5 -apple-system,Segoe UI,Inter,Roboto,sans-serif;background:#f6f7f9;color:#1a1d23}
.wrap{max-width:760px;margin:0 auto;padding:40px 20px}h1{font-size:26px;margin:0 0 6px}.sub{color:#667085;margin-bottom:24px}
.card{background:#fff;border:1px solid #e4e7ec;border-radius:12px;padding:22px}
label{display:block;font-size:13px;color:#667085;margin:12px 0 4px}input[type=text],input[type=number]{width:100%;padding:10px 12px;border:1px solid #d0d5dd;border-radius:8px;font-size:15px}
.row{display:grid;grid-template-columns:1fr 1fr;gap:14px}button{margin-top:18px;background:#0f172a;color:#fff;border:0;border-radius:8px;padding:12px 20px;font-size:15px;cursor:pointer}
button:disabled{opacity:.5}.log{margin-top:18px;font:13px ui-monospace,Menlo,monospace;background:#0f172a;color:#cbd5e1;border-radius:8px;padding:14px;min-height:60px;white-space:pre-wrap;word-break:break-all}
.result{margin-top:18px;padding:16px;border-radius:8px;background:#ecfdf3;border:1px solid #abefc6}.result a{font-weight:600}
.badge{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;font-weight:600;margin-right:6px}
.b-fout{background:#fef3f2;color:#d92d20}.b-waarschuwing{background:#fffaeb;color:#b54708}.b-info{background:#eff8ff;color:#175cd3}
details{margin-top:10px}summary{cursor:pointer;color:#667085;font-size:14px}
h2{font-size:17px;margin:30px 0 10px}ul{padding-left:18px}li{margin:4px 0}
</style></head><body><div class="wrap">
<h1>SiteCheck</h1><div class="sub">Opleveringscheck voor nieuwe websites — controleert de punten uit de checklist en rapporteert per URL.</div>
<div class="card"><form id="f" onsubmit="start();return false">
<label>Website-URL</label><input type="text" id="url" placeholder="https://www.klant.nl" required>
<details><summary>Opties</summary>
<div class="row"><div><label>Max. pagina's</label><input type="number" id="max_pages" value="200"></div><div><label>Pauze tussen pagina's (s)</label><input type="number" id="delay" value="0.2" step="0.1"></div></div>
<div class="row"><div><label>Verwacht telefoonnummer</label><input type="text" id="phone" placeholder="010-1234567"></div><div><label>Verwacht e-mailadres</label><input type="text" id="email" placeholder="info@klant.nl"></div></div>
<div class="row"><div><label>Bedrijfsnaam</label><input type="text" id="company"></div><div><label>Adres (letterlijk)</label><input type="text" id="address" placeholder="Hoofdstraat 1"></div></div>
<label>Oude URL's (één per regel, voor redirect-controle)</label><textarea id="old_urls" rows="4" style="width:100%;border:1px solid #d0d5dd;border-radius:8px;padding:10px;font-size:14px"></textarea>
<label><input type="checkbox" id="no_external"> Externe links niet controleren (sneller)</label>
<label><input type="checkbox" id="render"> Pagina's renderen met browser (JS-sites; vereist Playwright)</label>
</details>
<button id="btn">Start controle</button></form>
<div class="log" id="log" style="display:none"></div>
<div id="res"></div></div>
<h2>Eerdere rapporten</h2><div class="card" id="prev">laden…</div>
</div>
<script>
let job=null,timer=null;
async function start(){
  const body={url:v('url'),max_pages:+v('max_pages'),delay:+v('delay'),phone:v('phone'),email:v('email'),company:v('company'),address:v('address'),
    old_urls:v('old_urls'),no_external:document.getElementById('no_external').checked,render:document.getElementById('render').checked};
  document.getElementById('btn').disabled=true;document.getElementById('res').innerHTML='';
  const r=await fetch('/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  job=(await r.json()).id;document.getElementById('log').style.display='block';timer=setInterval(poll,1000);
}
function v(id){return document.getElementById(id).value.trim()}
async function poll(){
  const r=await fetch('/status/'+job);const s=await r.json();
  document.getElementById('log').textContent=s.log.slice(-25).join('\\n');
  if(s.done){clearInterval(timer);document.getElementById('btn').disabled=false;
    if(s.error){document.getElementById('res').innerHTML='<div class="result" style="background:#fef3f2;border-color:#fda29b">Fout: '+s.error+'</div>';return}
    document.getElementById('res').innerHTML='<div class="result"><span class="badge b-fout">'+s.counts.fout+' fouten</span><span class="badge b-waarschuwing">'+s.counts.waarschuwing+' waarschuwingen</span><span class="badge b-info">'+s.counts.info+' info</span><br><br><a href="/rapport/'+s.file+'" target="_blank">Rapport openen →</a> &nbsp; <a href="/rapport/'+s.file.replace('.html','.csv')+'">CSV</a> &nbsp; <a href="/rapport/'+s.file.replace('.html','.json')+'">JSON</a></div>';
    loadPrev();}
}
async function loadPrev(){const r=await fetch('/list');const l=await r.json();
  document.getElementById('prev').innerHTML=l.length?'<ul>'+l.map(f=>'<li><a href="/rapport/'+f+'" target="_blank">'+f+'</a></li>').join('')+'</ul>':'<span style="color:#667085">Nog geen rapporten.</span>'}
loadPrev();
</script></body></html>"""


@app.get("/health")
def health():
    return "ok"


@app.get("/")
def index():
    return Response(PAGE, mimetype="text/html")


@app.post("/start")
def start():
    d = request.get_json(force=True)
    jid = uuid.uuid4().hex[:8]
    JOBS[jid] = {"log": [f"Start: {d['url']}"], "done": False, "error": None}

    def progress(n_pages, n_queue, current, status):
        s = f"[{status}] " if status is not None else ""
        JOBS[jid]["log"].append(f"{n_pages:>4} pagina's · {n_queue:>4} wachtrij · {s}{current}")

    def work():
        try:
            expected = {k: d.get(k) for k in ("company", "phone", "email", "address") if d.get(k)}
            old = [l for l in (d.get("old_urls") or "").splitlines() if l.strip()] or None
            html_path, findings, pages, checker, duration = run(
                d["url"], out_dir=str(OUT_DIR), max_pages=int(d.get("max_pages") or 200),
                delay=float(d.get("delay") or 0.2), no_external=bool(d.get("no_external")),
                render=bool(d.get("render")), old_urls=old, expected=expected, progress=progress, quiet=True)
            c = Counter(f.severity for f in findings)
            JOBS[jid].update(done=True, file=html_path.name,
                             counts={"fout": c.get("fout", 0), "waarschuwing": c.get("waarschuwing", 0), "info": c.get("info", 0)})
            JOBS[jid]["log"].append(f"Klaar in {duration:.0f} s — {len(pages)} pagina's.")
        except Exception as e:  # noqa
            JOBS[jid].update(done=True, error=f"{e.__class__.__name__}: {e}")

    threading.Thread(target=work, daemon=True).start()
    return jsonify(id=jid)


@app.get("/status/<jid>")
def status(jid):
    return jsonify(JOBS.get(jid, {"done": True, "error": "onbekende job", "log": []}))


@app.get("/list")
def list_reports():
    OUT_DIR.mkdir(exist_ok=True)
    files = sorted((p.name for p in OUT_DIR.glob("sitecheck_*.html")), reverse=True)
    return jsonify(files[:30])


@app.get("/rapport/<path:name>")
def report(name):
    return send_from_directory(OUT_DIR.resolve(), name)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", 5050)))
    ap.add_argument("--host", default="0.0.0.0" if os.environ.get("PORT") else "127.0.0.1")
    a = ap.parse_args()
    print(f"SiteCheck web-interface: http://{a.host}:{a.port}")
    app.run(host=a.host, port=a.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
