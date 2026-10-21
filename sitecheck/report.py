"""
Rapport: HTML (zelfstandig bestand, per URL + checklist) en JSON.
"""
import json
import datetime as dt
from collections import defaultdict, Counter
from html import escape
from urllib.parse import urlparse

from .checklist import CATEGORIES, all_items

SEV_ORDER = {"fout": 0, "waarschuwing": 1, "info": 2}
SEV_LABEL = {"fout": "Fout", "waarschuwing": "Waarschuwing", "info": "Info"}
MODE_LABEL = {"auto": "Automatisch", "assist": "Automatisch + handmatig", "manual": "Handmatig"}

CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#1a1d23;--muted:#667085;--line:#e4e7ec;
--red:#d92d20;--red-bg:#fef3f2;--amber:#b54708;--amber-bg:#fffaeb;--blue:#175cd3;--blue-bg:#eff8ff;
--green:#027a48;--green-bg:#ecfdf3;--grey:#475467;--grey-bg:#f2f4f7;--accent:#0f172a}
*{box-sizing:border-box}body{margin:0;font:15px/1.5 -apple-system,Segoe UI,Inter,Roboto,sans-serif;color:var(--ink);background:var(--bg)}
.wrap{max-width:1180px;margin:0 auto;padding:28px 20px 60px}
header{background:var(--accent);color:#fff;padding:28px 0}header .wrap{padding-top:0;padding-bottom:0}
header h1{margin:0 0 4px;font-size:24px}header .sub{opacity:.75;font-size:14px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:24px 0}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.kpi b{display:block;font-size:26px;line-height:1.1}.kpi span{color:var(--muted);font-size:13px}
.kpi.fout b{color:var(--red)}.kpi.waarschuwing b{color:var(--amber)}.kpi.info b{color:var(--blue)}
h2{font-size:19px;margin:34px 0 12px}h3{font-size:16px;margin:0}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin-bottom:12px}
table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--muted);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.03em}
.badge{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;font-weight:600;white-space:nowrap}
.b-fout{background:var(--red-bg);color:var(--red)}.b-waarschuwing{background:var(--amber-bg);color:var(--amber)}
.b-info{background:var(--blue-bg);color:var(--blue)}.b-ok{background:var(--green-bg);color:var(--green)}.b-manual{background:var(--grey-bg);color:var(--grey)}
.b-auto{background:var(--green-bg);color:var(--green)}.b-assist{background:var(--blue-bg);color:var(--blue)}
.url{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13px;word-break:break-all}
.detail{color:var(--muted);font-size:13px;word-break:break-word}
.page{margin-bottom:14px}.page summary{cursor:pointer;display:flex;gap:12px;align-items:center;flex-wrap:wrap;list-style:none}
.page summary::-webkit-details-marker{display:none}.page summary .url{flex:1;min-width:200px}
.page .cnt{display:flex;gap:6px}.status{font-size:12px;color:var(--muted)}
.cat{margin:12px 0 4px;font-size:13px;color:var(--muted);text-transform:uppercase;letter-spacing:.03em;font-weight:600}
.finding{display:grid;grid-template-columns:120px 1fr;gap:10px;padding:8px 0;border-top:1px solid var(--line)}
.finding:first-of-type{border-top:0}.finding .msg{font-weight:500}
.toolbar{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:14px 0}
.toolbar input#q{padding:8px 12px;border:1px solid var(--line);border-radius:8px;font-size:14px;min-width:260px}
.toolbar label{font-size:14px;display:flex;gap:6px;align-items:center}
.ok-row td{color:var(--muted)}
.hidden{display:none}
.check input[type=checkbox]{transform:scale(1.2);margin-right:6px}
.legend{font-size:13px;color:var(--muted)}
.small{font-size:13px;color:var(--muted)}
@media print{details{open:true}.toolbar{display:none}.page>summary{pointer-events:none}}
@media(max-width:700px){.finding{grid-template-columns:1fr}}
"""

JS = """
function applyFilter(){
  const q=document.getElementById('q').value.toLowerCase();
  const showF=document.getElementById('f-fout').checked, showW=document.getElementById('f-waarschuwing').checked, showI=document.getElementById('f-info').checked;
  document.querySelectorAll('.finding').forEach(el=>{
    const sev=el.dataset.sev; const txt=el.textContent.toLowerCase();
    const ok=((sev=='fout'&&showF)||(sev=='waarschuwing'&&showW)||(sev=='info'&&showI))&&(!q||txt.includes(q));
    el.classList.toggle('hidden',!ok);
  });
  document.querySelectorAll('details.page').forEach(d=>{
    const vis=d.querySelectorAll('.finding:not(.hidden)').length;
    const urlMatch=!q||d.dataset.url.includes(q);
    d.classList.toggle('hidden',vis===0 && !(urlMatch&&q));
    d.querySelectorAll('.cat').forEach(c=>{let n=c.nextElementSibling,any=false;while(n&&n.classList.contains('finding')){if(!n.classList.contains('hidden'))any=true;n=n.nextElementSibling;}c.classList.toggle('hidden',!any);});
  });
}
function toggleAll(open){document.querySelectorAll('details.page').forEach(d=>d.open=open)}
document.addEventListener('DOMContentLoaded',()=>{
  document.querySelectorAll('.check input[type=checkbox]').forEach(cb=>{
    const k='sitecheck:'+location.pathname+':'+cb.dataset.id;
    try{cb.checked=localStorage.getItem(k)==='1'}catch(e){}
    cb.addEventListener('change',()=>{try{localStorage.setItem(k,cb.checked?'1':'0')}catch(e){}});
  });
});
"""


def _badge(sev):
    return f'<span class="badge b-{sev}">{SEV_LABEL.get(sev, sev)}</span>'


def _item_status(item, findings_by_check):
    """Status van een checklistpunt op basis van gevonden issues."""
    sevs = [f.severity for c in item["checks"] for f in findings_by_check.get(c, [])]
    if item["mode"] == "manual":
        return "manual", "Handmatig controleren"
    worst = min(sevs, key=lambda s: SEV_ORDER[s]) if sevs else None
    n_issues = sum(1 for s in sevs if s in ("fout", "waarschuwing"))
    if worst == "fout":
        return "fout", f"{n_issues} issue(s)"
    if worst == "waarschuwing":
        return "waarschuwing", f"{n_issues} issue(s)"
    if item["mode"] == "assist":
        return "assist", ("Geen issues — handmatig bevestigen" if not sevs else f"{len(sevs)} aandachtspunt(en) — handmatig bevestigen")
    return "ok", "Geen issues gevonden"


def build_html(site_info, findings, pages, duration_s, extra_notes=None):
    now = dt.datetime.now().strftime("%d-%m-%Y %H:%M")
    by_page = defaultdict(list)
    by_check = defaultdict(list)
    for f in findings:
        by_page[f.page].append(f)
        by_check[f.check].append(f)
    counts = Counter(f.severity for f in findings)

    check_to_cat = {}
    check_to_item = {}
    for cat, item in all_items():
        for c in item["checks"]:
            check_to_cat.setdefault(c, cat)
            check_to_item.setdefault(c, item)

    out = []
    out.append(f"""<!doctype html><html lang="nl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Opleveringscheck – {escape(urlparse(site_info['start_url']).netloc)}</title><style>{CSS}</style></head><body>
<header><div class="wrap"><h1>Opleveringscheck website</h1>
<div class="sub">{escape(site_info['start_url'])} &nbsp;·&nbsp; {now} &nbsp;·&nbsp; {site_info['pages_crawled']} pagina's gecrawld, {site_info.get('links_checked',0)} links/bestanden gecontroleerd in {duration_s:.0f} s</div></div></header>
<div class="wrap">
<div class="kpis">
<div class="kpi fout"><b>{counts.get('fout',0)}</b><span>Fouten — oplossen vóór oplevering</span></div>
<div class="kpi waarschuwing"><b>{counts.get('waarschuwing',0)}</b><span>Waarschuwingen — beoordelen</span></div>
<div class="kpi info"><b>{counts.get('info',0)}</b><span>Info / handmatig bevestigen</span></div>
<div class="kpi"><b>{sum(1 for p in pages if p.status>=400 or p.error)}</b><span>Pagina's met fout­status</span></div>
</div>""")

    # ------------------------------------------------ checklist overzicht
    out.append("<h2>1. Checklist-overzicht</h2><div class='card'><p class='small'>Status per punt uit de opleveringschecklist. "
               "<span class='badge b-auto'>Automatisch</span> volledig gecontroleerd · <span class='badge b-assist'>Automatisch + handmatig</span> voorbereid, bevestiging nodig · "
               "<span class='badge b-manual'>Handmatig</span> alleen handmatig te toetsen. Vinkjes worden lokaal in uw browser bewaard.</p>")
    for cat in CATEGORIES:
        out.append(f"<h3 style='margin:18px 0 6px'>{cat['id']}. {escape(cat['title'])}</h3><table><thead><tr><th style='width:30px'></th><th style='width:60px'>Nr</th><th>Controlepunt</th><th style='width:170px'>Methode</th><th style='width:220px'>Resultaat</th></tr></thead><tbody>")
        for item in cat["items"]:
            st, label = _item_status(item, by_check)
            badge_cls = {"fout": "b-fout", "waarschuwing": "b-waarschuwing", "ok": "b-ok", "assist": "b-assist", "manual": "b-manual"}[st]
            label_txt = {"fout": "Fout", "waarschuwing": "Let op", "ok": "OK", "assist": "Bevestigen", "manual": "Handmatig"}[st]
            out.append(f"<tr class='check'><td><input type='checkbox' data-id='{item['id']}' title='Afgevinkt'></td><td>{item['id']}</td><td>{escape(item['text'])}</td>"
                       f"<td><span class='badge b-{item['mode']}'>{MODE_LABEL[item['mode']]}</span></td>"
                       f"<td><span class='badge {badge_cls}'>{label_txt}</span> <span class='small'>{escape(label)}</span></td></tr>")
        out.append("</tbody></table>")
    out.append("</div>")

    # ------------------------------------------------ sitebrede bevindingen
    site_f = sorted(by_page.get("", []), key=lambda f: (SEV_ORDER[f.severity], f.check))
    out.append("<h2>2. Sitebrede bevindingen</h2>")
    if site_info.get("analytics"):
        out.append("<div class='card small'><b>Meetscripts:</b> " + "; ".join(f"{escape(k)}: {escape(', '.join(v))}" for k, v in site_info["analytics"].items()) + "</div>")
    if site_f:
        out.append("<div class='card'>")
        last_cat = None
        for f in site_f:
            cat = check_to_cat.get(f.check)
            ct = f"{cat['id']}. {cat['title']}" if cat else "Overig"
            if ct != last_cat:
                out.append(f"<div class='cat'>{escape(ct)}</div>")
                last_cat = ct
            out.append(f"<div class='finding' data-sev='{f.severity}'><div>{_badge(f.severity)}</div><div><div class='msg'>{escape(f.message)}</div>"
                       + (f"<div class='detail'>{escape(f.detail)}</div>" if f.detail else "") + "</div></div>")
        out.append("</div>")
    else:
        out.append("<div class='card small'>Geen sitebrede bevindingen.</div>")

    # ------------------------------------------------ per URL
    out.append("<h2>3. Bevindingen per URL</h2>")
    out.append("""<div class="toolbar"><input id="q" placeholder="Filter op URL of tekst…" oninput="applyFilter()">
<label><input type="checkbox" id="f-fout" checked onchange="applyFilter()"> Fouten</label>
<label><input type="checkbox" id="f-waarschuwing" checked onchange="applyFilter()"> Waarschuwingen</label>
<label><input type="checkbox" id="f-info" onchange="applyFilter()"> Info</label>
<a href="#" onclick="toggleAll(true);return false" class="small">alles openen</a> · <a href="#" onclick="toggleAll(false);return false" class="small">alles sluiten</a></div>""")

    def page_sort(p):
        fs = by_page.get(p.url, [])
        c = Counter(f.severity for f in fs)
        return (-c.get("fout", 0), -c.get("waarschuwing", 0), p.url)

    for p in sorted(pages, key=page_sort):
        fs = sorted(by_page.get(p.url, []), key=lambda f: (SEV_ORDER[f.severity], check_to_cat.get(f.check, {}).get("id", 99), f.check))
        c = Counter(f.severity for f in fs)
        status_txt = (f"{p.status}" if p.status else "—") + (f" · {p.error}" if p.error else "") + (f" · {p.elapsed_ms} ms" if p.elapsed_ms else "")
        if p.redirect_chain:
            status_txt += f" · redirect → {p.final_url}"
        title = ""
        if p.soup and p.soup.title:
            title = p.soup.title.get_text(" ", strip=True)[:90]
        cnt_html = "".join(f"<span class='badge b-{s}'>{c[s]}</span>" for s in ("fout", "waarschuwing", "info") if c.get(s))
        if not fs:
            cnt_html = "<span class='badge b-ok'>OK</span>"
        open_attr = " open" if c.get("fout") else ""
        out.append(f"<details class='page card' data-url='{escape(p.url.lower())}'{open_attr}><summary><span class='url'><a href='{escape(p.url)}' target='_blank' rel='noopener'>{escape(p.url)}</a><br><span class='status'>{escape(title)}{' · ' if title else ''}{escape(status_txt)}</span></span><span class='cnt'>{cnt_html}</span></summary>")
        if fs:
            last_cat = None
            for f in fs:
                cat = check_to_cat.get(f.check)
                item = check_to_item.get(f.check)
                ct = f"{cat['id']}. {cat['title']}" if cat else "Overig"
                if ct != last_cat:
                    out.append(f"<div class='cat'>{escape(ct)}</div>")
                    last_cat = ct
                ref = f"<span class='small'>[{item['id']}]</span> " if item else ""
                out.append(f"<div class='finding' data-sev='{f.severity}'><div>{_badge(f.severity)}</div><div><div class='msg'>{ref}{escape(f.message)}</div>"
                           + (f"<div class='detail'>{escape(f.detail)}</div>" if f.detail else "") + "</div></div>")
        else:
            out.append("<div class='small' style='margin-top:8px'>Geen bevindingen op deze pagina.</div>")
        out.append("</details>")

    # ------------------------------------------------ handmatig
    manual = [(cat, item) for cat, item in all_items() if item["mode"] in ("manual", "assist")]
    out.append("<h2>4. Handmatige controles</h2><div class='card'><p class='small'>Deze punten kan de tool niet (volledig) automatisch toetsen. Loop ze na vóór oplevering.</p><table><thead><tr><th style='width:30px'></th><th style='width:60px'>Nr</th><th>Controlepunt</th><th style='width:160px'>Hulp van de tool</th></tr></thead><tbody>")
    for cat, item in manual:
        hint = {"assist": "Zie bevindingen hierboven", "manual": "—"}[item["mode"]]
        out.append(f"<tr class='check'><td><input type='checkbox' data-id='m-{item['id']}'></td><td>{item['id']}</td><td>{escape(item['text'])}</td><td class='small'>{hint}</td></tr>")
    out.append("</tbody></table></div>")

    if extra_notes:
        out.append("<div class='card small'>" + "<br>".join(escape(n) for n in extra_notes) + "</div>")

    out.append(f"<p class='legend' style='margin-top:30px'>Gegenereerd door SiteCheck · TMC Media · {now}. Automatische controles vervangen geen handmatige eindcontrole.</p>")
    out.append(f"</div><script>{JS}</script><script>applyFilter()</script></body></html>")
    return "".join(out)


def build_json(site_info, findings, pages, duration_s):
    by_page = defaultdict(list)
    for f in findings:
        by_page[f.page].append(f.to_dict())
    return json.dumps({
        "site": site_info,
        "generated": dt.datetime.now().isoformat(timespec="seconds"),
        "duration_s": round(duration_s, 1),
        "summary": dict(Counter(f.severity for f in findings)),
        "pages": [
            {"url": p.url, "status": p.status, "final_url": p.final_url, "error": p.error,
             "elapsed_ms": p.elapsed_ms, "title": (p.soup.title.get_text(strip=True) if p.soup and p.soup.title else ""),
             "findings": by_page.get(p.url, [])}
            for p in pages
        ],
        "site_findings": by_page.get("", []),
        "checklist": [
            {"id": item["id"], "category": cat["title"], "text": item["text"], "mode": item["mode"], "checks": item["checks"]}
            for cat, item in all_items()
        ],
    }, ensure_ascii=False, indent=2)


def build_csv(findings):
    import csv, io
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["URL", "Ernst", "Categorie", "Checklistpunt", "Melding", "Detail"])
    check_to = {}
    for cat, item in all_items():
        for c in item["checks"]:
            check_to.setdefault(c, (cat, item))
    for f in sorted(findings, key=lambda f: (f.page, SEV_ORDER[f.severity])):
        cat, item = check_to.get(f.check, (None, None))
        w.writerow([f.page or "(sitebreed)", SEV_LABEL[f.severity], cat["title"] if cat else "", item["id"] if item else "", f.message, f.detail])
    return buf.getvalue()
