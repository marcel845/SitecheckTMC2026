"""
Commandline: python -m sitecheck https://www.klant.nl [opties]
"""
import argparse
import logging
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from .crawler import Crawler
from .checks import SiteChecker
from .report import build_html, build_json, build_csv


def run(url, out_dir="rapporten", max_pages=200, max_depth=6, delay=0.2, workers=8,
        no_external=False, render=False, old_urls=None, expected=None, extra_hosts=None,
        progress=None, quiet=False):
    t0 = time.time()
    crawler = Crawler(url, max_pages=max_pages, max_depth=max_depth, delay=delay,
                      workers=workers, check_external=not no_external, render=render,
                      extra_hosts=extra_hosts)

    def _progress(n_pages, n_queue, current, status):
        if progress:
            progress(n_pages, n_queue, current, status)
        elif not quiet:
            s = f"[{status}]" if status is not None else ""
            print(f"\r  {n_pages:>4} pagina's · {n_queue:>4} in wachtrij · {s} {current[:70]:<72}", end="", flush=True)

    crawler.crawl(progress=_progress)
    if not quiet and not progress:
        print()
    checker = SiteChecker(crawler, expected_contact=expected or {})
    findings = checker.run()
    if old_urls:
        checker.check_old_urls(old_urls)
    duration = time.time() - t0

    pages = sorted(crawler.pages.values(), key=lambda p: p.url)
    host = urlparse(crawler.start_url).netloc.replace(":", "_")
    stamp = time.strftime("%Y%m%d-%H%M")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    base = str(out / f"sitecheck_{host}_{stamp}")
    html_path = Path(base + ".html")
    html_path.write_text(build_html(checker.site_info, findings, pages, duration), encoding="utf-8")
    Path(base + ".json").write_text(build_json(checker.site_info, findings, pages, duration), encoding="utf-8")
    Path(base + ".csv").write_text(build_csv(findings), encoding="utf-8-sig")
    return html_path, findings, pages, checker, duration


def main(argv=None):
    ap = argparse.ArgumentParser(prog="sitecheck", description="Opleveringscheck voor nieuwe websites (TMC Media)")
    ap.add_argument("url", help="Start-URL, bv. https://www.klant.nl")
    ap.add_argument("-o", "--out", default="rapporten", help="Map voor rapporten (standaard: rapporten/)")
    ap.add_argument("--max-pages", type=int, default=200, help="Maximaal aantal pagina's (standaard 200)")
    ap.add_argument("--max-depth", type=int, default=6, help="Maximale linkdiepte (standaard 6)")
    ap.add_argument("--delay", type=float, default=0.2, help="Pauze tussen pagina's in seconden (standaard 0.2)")
    ap.add_argument("--workers", type=int, default=8, help="Parallelle link-checks (standaard 8)")
    ap.add_argument("--no-external", action="store_true", help="Externe links niet controleren")
    ap.add_argument("--render", action="store_true", help="Pagina's renderen met Playwright (voor JS-sites); vereist 'playwright install chromium'")
    ap.add_argument("--old-urls", help="Tekstbestand met oude URL's (één per regel) om redirects te testen")
    ap.add_argument("--extra-host", action="append", default=[], help="Extra host die als 'intern' geldt (bv. cdn.klant.nl); herhaalbaar")
    ap.add_argument("--company", help="Verwachte bedrijfsnaam (controle op aanwezigheid)")
    ap.add_argument("--phone", help="Verwacht telefoonnummer (controle op afwijkingen)")
    ap.add_argument("--email", help="Verwacht e-mailadres")
    ap.add_argument("--address", help="Verwacht adres (letterlijke tekst, bv. 'Hoofdstraat 1')")
    ap.add_argument("-q", "--quiet", action="store_true")
    ap.add_argument("--open", action="store_true", help="Open het HTML-rapport na afloop in de browser")
    a = ap.parse_args(argv)

    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    old = None
    if a.old_urls:
        old = Path(a.old_urls).read_text(encoding="utf-8").splitlines()
    expected = {k: v for k, v in (("company", a.company), ("phone", a.phone), ("email", a.email), ("address", a.address)) if v}

    if not a.quiet:
        print(f"SiteCheck · {a.url}")
    html_path, findings, pages, checker, duration = run(
        a.url, out_dir=a.out, max_pages=a.max_pages, max_depth=a.max_depth, delay=a.delay,
        workers=a.workers, no_external=a.no_external, render=a.render, old_urls=old,
        expected=expected, extra_hosts=a.extra_host, quiet=a.quiet)

    from collections import Counter
    c = Counter(f.severity for f in findings)
    print(f"\nKlaar in {duration:.0f} s — {len(pages)} pagina's, {len(checker.c.links)} links gecontroleerd.")
    print(f"  Fouten: {c.get('fout',0)}   Waarschuwingen: {c.get('waarschuwing',0)}   Info: {c.get('info',0)}")
    print(f"  Rapport: {html_path}  (+ .json, .csv)")
    if a.open:
        import webbrowser
        webbrowser.open(html_path.resolve().as_uri())
    return 1 if c.get("fout") else 0


if __name__ == "__main__":
    sys.exit(main())
