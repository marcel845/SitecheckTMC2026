"""
Crawler: haalt alle interne pagina's op (via links + sitemap.xml) en
controleert de status van alle gevonden links, afbeeldingen en bestanden.
"""
import re
import time
import logging
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse, urldefrag
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

log = logging.getLogger("sitecheck")

USER_AGENT = "Mozilla/5.0 (compatible; TMC-SiteCheck/1.0; +https://tmcmedia.nl)"
HTML_TYPES = ("text/html", "application/xhtml+xml")
DOWNLOAD_EXT = re.compile(r"\.(pdf|docx?|xlsx?|pptx?|zip|rar|csv|txt|epub|dwg|step|stp)$", re.I)
SKIP_SCHEMES = ("mailto:", "tel:", "javascript:", "sms:", "whatsapp:", "data:", "ftp:")


@dataclass
class Page:
    url: str
    status: int = 0
    final_url: str = ""
    redirect_chain: list = field(default_factory=list)
    content_type: str = ""
    html: str = ""
    elapsed_ms: int = 0
    size_bytes: int = 0
    error: str = ""
    depth: int = 0
    from_sitemap: bool = False
    soup: BeautifulSoup = None

    @property
    def ok(self):
        return 200 <= self.status < 300 and not self.error

    @property
    def is_html(self):
        return any(t in self.content_type for t in HTML_TYPES)


@dataclass
class LinkStatus:
    url: str
    status: int = 0
    final_url: str = ""
    content_type: str = ""
    content_length: int = 0
    redirect_chain: list = field(default_factory=list)
    error: str = ""

    @property
    def ok(self):
        return 200 <= self.status < 400 and not self.error


def normalize(url: str) -> str:
    """Strip fragment, normaliseer trailing slash op root en lowercase host."""
    url, _ = urldefrag(url)
    p = urlparse(url)
    netloc = p.netloc.lower()
    path = p.path or "/"
    # verwijder dubbele slashes
    path = re.sub(r"/{2,}", "/", path)
    rebuilt = f"{p.scheme}://{netloc}{path}"
    if p.query:
        rebuilt += "?" + p.query
    return rebuilt


def same_site(url: str, root_host: str) -> bool:
    host = urlparse(url).netloc.lower()
    host = host[4:] if host.startswith("www.") else host
    root = root_host[4:] if root_host.startswith("www.") else root_host
    return host == root


class Crawler:
    def __init__(self, start_url, max_pages=200, max_depth=6, delay=0.2,
                 timeout=15, workers=8, check_external=True, render=False,
                 extra_hosts=None):
        self.start_url = normalize(start_url if "://" in start_url else "https://" + start_url)
        self.root = urlparse(self.start_url)
        self.root_host = self.root.netloc.lower()
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.delay = delay
        self.timeout = timeout
        self.workers = workers
        self.check_external = check_external
        self.render = render
        self.extra_hosts = set(h.lower() for h in (extra_hosts or []))

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
        })
        self.pages: dict[str, Page] = {}
        self.links: dict[str, LinkStatus] = {}
        self.link_sources: dict[str, set] = {}   # link-url -> set(pagina-url's)
        self.sitemap_urls: list[str] = []
        self.sitemap_error = ""
        self.robots_txt = ""
        self.robots_status = 0
        self._renderer = None

    # ------------------------------------------------------------------ fetch
    def _fetch(self, url, method="GET", allow_redirects=True, stream=False):
        return self.session.request(method, url, timeout=self.timeout,
                                    allow_redirects=allow_redirects, stream=stream)

    def _render_html(self, url):
        """Optioneel: render met Playwright voor JS-gedreven sites."""
        if self._renderer is None:
            from playwright.sync_api import sync_playwright
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch()
            self._renderer = self._browser.new_context(user_agent=USER_AGENT)
        page = self._renderer.new_page()
        try:
            page.goto(url, wait_until="networkidle", timeout=self.timeout * 1000)
            return page.content()
        finally:
            page.close()

    def fetch_page(self, url, depth=0, from_sitemap=False) -> Page:
        pg = Page(url=url, depth=depth, from_sitemap=from_sitemap)
        t0 = time.time()
        try:
            r = self._fetch(url)
            pg.elapsed_ms = int((time.time() - t0) * 1000)
            pg.status = r.status_code
            pg.final_url = normalize(r.url)
            pg.redirect_chain = [normalize(h.url) for h in r.history]
            pg.content_type = r.headers.get("Content-Type", "").lower()
            if pg.is_html and pg.status < 400 or (pg.status >= 400 and "html" in pg.content_type):
                pg.html = r.text
                pg.size_bytes = len(r.content)
                if self.render and pg.status < 400:
                    try:
                        pg.html = self._render_html(url)
                    except Exception as e:  # noqa
                        log.warning("Render mislukt voor %s: %s", url, e)
                pg.soup = BeautifulSoup(pg.html, "lxml")
            else:
                pg.size_bytes = int(r.headers.get("Content-Length") or 0)
        except requests.exceptions.SSLError as e:
            pg.error = f"SSL-fout: {e.__class__.__name__}"
        except requests.exceptions.ConnectionError:
            pg.error = "Verbinding mislukt"
        except requests.exceptions.Timeout:
            pg.error = "Time-out"
        except requests.exceptions.TooManyRedirects:
            pg.error = "Te veel redirects (redirectlus)"
        except Exception as e:  # noqa
            pg.error = f"{e.__class__.__name__}: {e}"
        return pg

    def check_link(self, url) -> LinkStatus:
        ls = LinkStatus(url=url)
        try:
            r = self._fetch(url, method="HEAD")
            # Sommige servers weigeren HEAD; val terug op GET
            if r.status_code in (403, 405, 400, 501) or r.status_code >= 500:
                r = self._fetch(url, method="GET", stream=True)
                r.close()
            ls.status = r.status_code
            ls.final_url = r.url
            ls.redirect_chain = [h.url for h in r.history]
            ls.content_type = r.headers.get("Content-Type", "").lower()
            ls.content_length = int(r.headers.get("Content-Length") or 0)
        except requests.exceptions.SSLError:
            ls.error = "SSL-fout"
        except requests.exceptions.ConnectionError:
            ls.error = "Verbinding mislukt"
        except requests.exceptions.Timeout:
            ls.error = "Time-out"
        except requests.exceptions.TooManyRedirects:
            ls.error = "Redirectlus"
        except Exception as e:  # noqa
            ls.error = e.__class__.__name__
        return ls

    # --------------------------------------------------------------- helpers
    def is_internal(self, url):
        host = urlparse(url).netloc.lower()
        return same_site(url, self.root_host) or host in self.extra_hosts

    def extract_links(self, page: Page):
        """Geef (href, absolute_url, tag) voor alle a/link/img/script/iframe/source."""
        out = []
        if not page.soup:
            return out
        base = page.final_url or page.url
        base_tag = page.soup.find("base", href=True)
        if base_tag:
            base = urljoin(base, base_tag["href"])
        for tag, attr in (("a", "href"), ("img", "src"), ("script", "src"),
                          ("link", "href"), ("iframe", "src"), ("source", "src"),
                          ("video", "src"), ("audio", "src"), ("img", "data-src")):
            for el in page.soup.find_all(tag):
                v = el.get(attr)
                if not v or not isinstance(v, str):
                    continue
                v = v.strip()
                if not v or v.startswith("#") or v.lower().startswith(SKIP_SCHEMES):
                    continue
                if v.startswith("{{") or "{{" in v:
                    continue
                try:
                    absu = urljoin(base, v)
                except ValueError:
                    continue
                if not absu.startswith(("http://", "https://")):
                    continue
                out.append((v, absu, el))
        return out

    # --------------------------------------------------------------- sitemap
    def load_robots_and_sitemap(self):
        robots_url = f"{self.root.scheme}://{self.root_host}/robots.txt"
        sitemaps = []
        try:
            r = self._fetch(robots_url)
            self.robots_status = r.status_code
            if r.ok and "html" not in r.headers.get("Content-Type", ""):
                self.robots_txt = r.text
                for line in r.text.splitlines():
                    if line.lower().startswith("sitemap:"):
                        sitemaps.append(line.split(":", 1)[1].strip())
        except Exception as e:  # noqa
            self.robots_status = 0
            log.info("robots.txt niet bereikbaar: %s", e)
        if not sitemaps:
            sitemaps = [f"{self.root.scheme}://{self.root_host}/sitemap.xml"]
        seen = set()
        for sm in sitemaps:
            self._parse_sitemap(sm, seen)

    def _parse_sitemap(self, url, seen, depth=0):
        if url in seen or depth > 3:
            return
        seen.add(url)
        try:
            r = self._fetch(url)
            if r.status_code != 200:
                if depth == 0:
                    self.sitemap_error = f"sitemap niet gevonden ({r.status_code}) op {url}"
                return
            root = ET.fromstring(r.content)
        except Exception as e:  # noqa
            if depth == 0:
                self.sitemap_error = f"sitemap niet leesbaar op {url}: {e.__class__.__name__}"
            return
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        for loc in root.findall(".//sm:sitemap/sm:loc", ns):
            self._parse_sitemap(loc.text.strip(), seen, depth + 1)
        for loc in root.findall(".//sm:url/sm:loc", ns):
            if loc.text:
                self.sitemap_urls.append(loc.text.strip())
        # fallback zonder namespace
        if not self.sitemap_urls:
            for loc in root.iter():
                if loc.tag.endswith("loc") and loc.text and loc.text.strip().startswith("http"):
                    self.sitemap_urls.append(loc.text.strip())

    # ------------------------------------------------------------------ crawl
    def crawl(self, progress=None):
        self.load_robots_and_sitemap()
        queue = deque()
        queued = set()

        def enqueue(u, depth, from_sitemap=False):
            u = normalize(u)
            if u in queued or not self.is_internal(u):
                return
            if DOWNLOAD_EXT.search(urlparse(u).path):
                return
            queued.add(u)
            queue.append((u, depth, from_sitemap))

        enqueue(self.start_url, 0)
        for u in self.sitemap_urls:
            if self.is_internal(u):
                enqueue(u, 1, from_sitemap=True)

        while queue and len(self.pages) < self.max_pages:
            url, depth, from_sm = queue.popleft()
            if url in self.pages:
                continue
            pg = self.fetch_page(url, depth, from_sm)
            self.pages[url] = pg
            if progress:
                progress(len(self.pages), len(queue), url, pg.status)
            # Volg redirect naar eindpagina, ook registreren
            if pg.final_url and pg.final_url != url and self.is_internal(pg.final_url):
                enqueue(pg.final_url, depth)
            if pg.soup and depth < self.max_depth:
                for href, absu, el in self.extract_links(pg):
                    if el.name == "a":
                        enqueue(absu, depth + 1)
                    nu = normalize(absu) if el.name == "a" else absu
                    self.link_sources.setdefault(nu, set()).add(url)
            time.sleep(self.delay)

        if self._renderer is not None:
            try:
                self._browser.close()
                self._pw.stop()
            except Exception:  # noqa
                pass

        self.check_all_links(progress)
        return self.pages

    def check_all_links(self, progress=None):
        """Controleer alle gevonden URL's die geen gecrawlde pagina zijn (HEAD)."""
        todo = []
        for u in self.link_sources:
            if u in self.pages:
                continue
            if not self.check_external and not self.is_internal(u):
                continue
            todo.append(u)
        if not todo:
            return
        with ThreadPoolExecutor(max_workers=self.workers) as ex:
            futs = {ex.submit(self.check_link, u): u for u in todo}
            done = 0
            for f in as_completed(futs):
                ls = f.result()
                self.links[ls.url] = ls
                done += 1
                if progress and done % 20 == 0:
                    progress(len(self.pages), len(todo) - done, f"links controleren… {done}/{len(todo)}", None)

    def status_of(self, url):
        """Status voor een URL: uit gecrawlde pagina's of uit link-checks."""
        nu = normalize(url)
        if nu in self.pages:
            p = self.pages[nu]
            return p.status, p.final_url, p.error, p.redirect_chain
        for key in (url, nu):
            if key in self.links:
                l = self.links[key]
                return l.status, l.final_url, l.error, l.redirect_chain
        return None, None, None, []
