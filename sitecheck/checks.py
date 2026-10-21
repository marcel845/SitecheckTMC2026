"""
Alle controles. Elke check produceert Findings met:
  check     check-code (gekoppeld aan checklist.py)
  severity  "fout" | "waarschuwing" | "info"
  page      URL van de pagina waarop het gevonden is ("" = sitebreed)
  message   korte omschrijving
  detail    extra context (element, URL, waarde)
"""
import re
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from urllib.parse import urlparse, urljoin
import datetime as dt

from .crawler import Crawler, Page, normalize, DOWNLOAD_EXT


@dataclass
class Finding:
    check: str
    severity: str
    page: str
    message: str
    detail: str = ""

    def to_dict(self):
        return asdict(self)


# ---------------------------------------------------------------- patronen
PLACEHOLDER_RE = re.compile(
    r"\b(lorem ipsum|dolor sit amet|consectetur|tekst volgt|titel hier|title here|"
    r"heading here|your heading|your text here|insert text|placeholder|voorbeeldtekst|"
    r"dummy ?tekst|dummy ?text|coming soon|binnenkort meer|nog in te vullen|pm invullen|"
    r"\[tekst\]|\[titel\]|\[naam\]|xxx+|tbd|t\.b\.d\.|nader te bepalen|"
    r"add your (text|content|title)|this is a (sample|example)|"
    r"body text|rich text element|heading \d+ goes here|"
    r"klik hier om te bewerken|click here to edit)\b", re.I)

SAMPLE_CONTENT_RE = re.compile(
    r"\b(john doe|jane doe|jan jansen|piet(je)? puk|henk de vries|test ?klant|test ?bedrijf|"
    r"bedrijfsnaam b\.?v\.?|acme|example\.com|voorbeeld\.nl|voorbeeldbedrijf|"
    r"naam klant|klantnaam|voorbeeld review|test ?review|voorbeeldproject|testproduct|"
    r"example (product|project|article)|sample (product|project|article|review)|"
    r"012-?3456789|0612345678|06-12345678|\+31 ?6 ?12345678|info@(example|voorbeeld|test)\.)\b", re.I)

INTERNAL_NOTE_RE = re.compile(
    r"(\bTODO\b|\bFIXME\b|\bTBD\b|\bnog (aanpassen|checken|vullen|invullen|doen)\b|"
    r"\bcheck(en)? met klant\b|\bvraag (aan )?klant\b|\bafstemmen met\b|\bopmerking voor\b|"
    r"\bnote to (self|dev|builder)\b|\bdev ?note\b|\bbouwer:|\bnavragen\b|\blet op:|"
    r"\b\[\s*(todo|check|nog doen|intern)\s*[:\]]|\bPLACEHOLDER\b)", re.I)

PLACEHOLDER_IMG_RE = re.compile(
    r"(placehold\.it|placeholder\.com|via\.placeholder|placekitten|picsum\.photos|dummyimage|"
    r"lorempixel|loremflickr|unsplash\.it|placeimg|fakeimg|placeholder|"
    r"image-placeholder|img-placeholder|/temp/|/tmp/|/test/|testlogo|test-logo|"
    r"logo-placeholder|preview\.redd|shutterstock\.com/image|istockphoto\.com/photo|"
    r"gettyimages\.(com|nl)/detail|adobe\.com/.*preview|comp\.|_comp\.|watermark|"
    r"uploads-ssl\.webflow\.com/img/placeholder|d3e54v103j8qbb\.cloudfront\.net/plugins)", re.I)

STAGING_RE = re.compile(
    r"(\.webflow\.io|\.wixsite\.com|\.squarespace\.com|\.myshopify\.com|\.netlify\.app|"
    r"\.vercel\.app|\.pages\.dev|\.herokuapp\.com|\.wpengine\.com|\.wpenginepowered\.com|"
    r"\.kinsta\.cloud|\.flywheelsites\.com|\.staging\.|staging\.|\.test\b|\.local\b|"
    r"localhost|127\.0\.0\.1|\bdev\.|\.dev\b|acceptatie|acceptance|\btest\.|\.test\.|"
    r"\bbeta\.|\bpreview\.|\bdemo\.|\bsandbox\b|\btmp\.|\.ngrok\.|\bconcept\.|"
    r"\.sitepreview\.|\.pantheonsite\.io|\.lightningbase|\.cloudwaysapps\.com)", re.I)

TEST_PAGE_RE = re.compile(
    r"(/test(-|_)?(page|pagina)?/?$|/test[-_/]|/concept|/draft|/template|/templates/|"
    r"/style-?guide|/styleguide|/stijlgids|/components?/?$|/ui-?kit|/licens(e|ing)|"
    r"/changelog|/instructions|/sample|/voorbeeld|/dummy|/old|/oud|/backup|/kopie|/copy|"
    r"/untitled|/nieuwe-pagina|/new-page|/page-?\d+$|/home-?(2|copy|old|v2)|/401$|/password)", re.I)

GENERIC_LINK_TEXT = {"klik hier", "click here", "hier", "lees meer", "read more", "meer", "more",
                     "link", "knop", "button", "learn more"}

LEGAL_PATTERNS = {
    "privacyverklaring": re.compile(r"privacy", re.I),
    "cookiebeleid": re.compile(r"cookie", re.I),
    "algemene voorwaarden": re.compile(r"(algemene[- ]voorwaarden|voorwaarden|terms|conditions)", re.I),
}

COOKIE_TOOLS = re.compile(
    r"(cookiebot|cookieyes|complianz|cookiefirst|onetrust|iubenda|usercentrics|borlabs|"
    r"cookie-?consent|cookieconsent|cookie-?banner|cookie-?notice|cookie-?bar|cc-window|"
    r"gdpr|consentmanager|termly|osano|klaro|tarteaucitron|cookie_?law|cmplz|moove_gdpr|"
    r"fs-cc|finsweet.*cookie)", re.I)

ANALYTICS_RE = {
    "Google Analytics 4": re.compile(r"gtag\(\s*['\"]config['\"]\s*,\s*['\"](G-[A-Z0-9]+)['\"]"),
    "Google Analytics (UA, verouderd)": re.compile(r"(UA-\d{4,10}-\d{1,4})"),
    "Google Tag Manager": re.compile(r"googletagmanager\.com/gtm\.js\?id=(GTM-[A-Z0-9]+)|GTM-[A-Z0-9]{4,10}"),
    "Matomo": re.compile(r"(matomo|piwik)\.(js|php)", re.I),
    "Plausible": re.compile(r"plausible\.io/js", re.I),
    "Hotjar": re.compile(r"hotjar\.com|hjid", re.I),
    "Meta Pixel": re.compile(r"fbq\(\s*['\"]init['\"]"),
    "LinkedIn Insight": re.compile(r"snap\.licdn\.com|_linkedin_partner_id"),
    "Microsoft Clarity": re.compile(r"clarity\.ms"),
}

SPAM_RE = re.compile(r"(recaptcha|hcaptcha|turnstile|honeypot|cf-turnstile|g-recaptcha|"
                     r"h-captcha|friendly-?captcha|akismet|antispam|anti-spam|formspree|"
                     r"type=['\"]hidden['\"][^>]*name=['\"](website|url|fax|_gotcha|bot-field))", re.I)

EMBED_RE = {
    "Google Maps": re.compile(r"google\.com/maps|maps\.googleapis\.com|maps\.google", re.I),
    "YouTube": re.compile(r"youtube(-nocookie)?\.com/embed|youtu\.be", re.I),
    "Vimeo": re.compile(r"player\.vimeo\.com", re.I),
    "Calendly / boeking": re.compile(r"calendly\.com|acuityscheduling|booking|afspraak", re.I),
    "Typeform / formulier": re.compile(r"typeform\.com|jotform|hubspotforms|hsforms", re.I),
    "Slider": re.compile(r"swiper|slick|splide|w-slider|carousel|flickity|glide", re.I),
    "Tabs / accordion": re.compile(r"w-tabs|accordion|collapse|tabs", re.I),
}

DATE_RE = re.compile(r"(?:©|copyright|&copy;)\s*(?:\d{4}\s*[-–]\s*)?(\d{4})\b", re.I)
OLD_YEAR_RE = re.compile(r"\b(20[0-2]\d)\b")

TEL_RE = re.compile(r"^\+?[\d\s\-().]{6,20}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)
EMAIL_TEXT_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
PHONE_TEXT_RE = re.compile(r"(?<!\d)(\+31|0031|0)[\s\-]?(\(0\)\s?)?[1-9](?:[\s\-]?\d){8}(?!\d)")

DEFAULT_TITLES = re.compile(r"^(home|homepage|untitled|new page|nieuwe pagina|page|pagina|"
                            r"website|site|titel|title|webflow|wordpress|my site|mijn website|"
                            r"document|index|startpagina|just another wordpress site|"
                            r"home\s*[-|–]\s*\w+)$", re.I)


def visible_text(soup):
    s = BeautifulSoup_copy(soup)
    for t in s(["script", "style", "noscript", "template", "svg", "head"]):
        t.decompose()
    return re.sub(r"\s+", " ", s.get_text(" ")).strip()


def BeautifulSoup_copy(soup):
    from copy import copy
    return copy(soup)


def main_text(soup):
    """Tekst zonder header/footer/nav (voor 'lege pagina'-detectie)."""
    s = BeautifulSoup_copy(soup)
    for t in s(["script", "style", "noscript", "template", "svg", "head", "header", "footer", "nav"]):
        t.decompose()
    return re.sub(r"\s+", " ", s.get_text(" ")).strip()


def el_snippet(el, n=120):
    txt = re.sub(r"\s+", " ", el.get_text(" ", strip=True) if hasattr(el, "get_text") else str(el))
    return (txt[:n] + "…") if len(txt) > n else txt


# ================================================================ SITE CHECKER
class SiteChecker:
    def __init__(self, crawler: Crawler, expected_contact: dict | None = None,
                 max_findings_per_check=25):
        self.c = crawler
        self.findings: list[Finding] = []
        self.expected = expected_contact or {}
        self.limit = max_findings_per_check
        self._count = Counter()
        self.site_info = {}

    def add(self, check, severity, page, message, detail=""):
        key = (check, page, message, detail)
        self._count[key] += 1
        if self._count[key] > 1:
            return
        self.findings.append(Finding(check, severity, page, message, detail))

    # ----------------------------------------------------------------- run
    def run(self):
        pages = [p for p in self.c.pages.values()]
        # Pagina's die doorverwijzen naar een andere gecrawlde pagina niet dubbel inhoudelijk checken
        html_pages = [p for p in pages if p.soup is not None and p.status < 400
                      and not (p.final_url and p.final_url != p.url and p.final_url in self.c.pages)]

        self.check_site_level(pages, html_pages)
        for p in pages:
            self.check_page_status(p)
        for p in html_pages:
            self.check_content(p)
            self.check_links(p)
            self.check_images(p)
            self.check_seo(p)
            self.check_forms(p)
            self.check_security(p)
            self.check_performance(p)
            self.check_dynamic(p)
        self.check_duplicates(html_pages)
        self.check_consistency(html_pages)
        self.collapse_repeated(len(html_pages))
        return self.findings

    def collapse_repeated(self, n_pages, min_pages=3, ratio=0.6):
        """Identieke bevindingen op veel pagina's (header/footer/template) → één sitebrede melding."""
        if n_pages < min_pages:
            return
        groups = defaultdict(list)
        for f in self.findings:
            if f.page:
                groups[(f.check, f.message, f.detail)].append(f)
        remove = set()
        new = []
        for (check, msg, detail), fs in groups.items():
            pages = {f.page for f in fs}
            if len(pages) >= min_pages and len(pages) >= ratio * n_pages:
                for f in fs:
                    remove.add(id(f))
                scope = "alle" if len(pages) == n_pages else f"{len(pages)} van {n_pages}"
                new.append(Finding(check, fs[0].severity, "", f"{msg}", (f"Op {scope} pagina's (waarschijnlijk header/footer/template). " + detail).strip()))
        self.findings = [f for f in self.findings if id(f) not in remove] + new

    # ---------------------------------------------------------- site-level
    def check_site_level(self, pages, html_pages):
        c = self.c
        root = c.start_url
        self.site_info["start_url"] = root
        self.site_info["pages_crawled"] = len(pages)
        self.site_info["links_checked"] = len(c.links)

        # HTTPS
        if urlparse(root).scheme != "https":
            self.add("https", "fout", "", "Website draait niet op HTTPS", root)
        else:
            http_url = root.replace("https://", "http://", 1)
            ls = c.check_link(http_url)
            if ls.error:
                self.add("http_redirect", "waarschuwing", "", "HTTP-versie niet bereikbaar / geen redirect naar HTTPS", f"{http_url}: {ls.error}")
            elif not ls.final_url.startswith("https://"):
                self.add("http_redirect", "fout", "", "HTTP wordt niet doorgestuurd naar HTTPS", f"{http_url} → {ls.final_url} ({ls.status})")
            # www / non-www consistentie
            host = urlparse(root).netloc
            alt = host[4:] if host.startswith("www.") else "www." + host
            alt_url = f"https://{alt}/"
            ls2 = c.check_link(alt_url)
            if ls2.error:
                self.add("redirects", "waarschuwing", "", f"Variant {alt} niet bereikbaar (geen redirect ingesteld?)", f"{alt_url}: {ls2.error}")
            elif ls2.status == 200 and urlparse(ls2.final_url).netloc.lower() not in (host, urlparse(ls2.final_url).netloc.lower()) :
                pass
            elif ls2.status == 200 and urlparse(ls2.final_url).netloc.lower() != host and not ls2.redirect_chain:
                self.add("redirects", "waarschuwing", "", f"Zowel {host} als {alt} geven 200 zonder redirect (dubbele content)", alt_url)

        # robots.txt
        if c.robots_txt:
            lines = [l.strip() for l in c.robots_txt.splitlines()]
            ua_all = False
            for l in lines:
                low = l.lower()
                if low.startswith("user-agent:"):
                    ua_all = low.split(":", 1)[1].strip() == "*"
                elif ua_all and re.match(r"disallow:\s*/\s*$", low):
                    self.add("robots_txt", "fout", "", "robots.txt blokkeert de hele website voor zoekmachines", "Disallow: /")
            if not any(l.lower().startswith("sitemap:") for l in lines):
                self.add("robots_txt", "info", "", "robots.txt verwijst niet naar een sitemap", "Voeg 'Sitemap: https://…/sitemap.xml' toe")
        elif c.robots_status == 404:
            self.add("robots_txt", "info", "", "Geen robots.txt gevonden", "Niet verplicht, maar aanbevolen (incl. sitemap-verwijzing)")

        # sitemap
        if c.sitemap_error:
            self.add("sitemap", "waarschuwing", "", "Sitemap ontbreekt of is onleesbaar", c.sitemap_error)
        else:
            host = urlparse(root).netloc.lower()
            wrong_host = [u for u in c.sitemap_urls if not c.is_internal(u)]
            for u in wrong_host[: self.limit]:
                self.add("sitemap", "fout", "", "Sitemap bevat URL van ander domein (testomgeving?)", u)
            http_in_sm = [u for u in c.sitemap_urls if u.startswith("http://")]
            for u in http_in_sm[: self.limit]:
                self.add("sitemap", "waarschuwing", "", "Sitemap bevat http:// URL", u)
            for u in c.sitemap_urls:
                nu = normalize(u)
                if nu in c.pages:
                    p = c.pages[nu]
                    if p.status >= 400 or p.error:
                        self.add("sitemap", "fout", "", f"Sitemap-URL geeft {p.status or p.error}", u)
                    elif p.redirect_chain:
                        self.add("sitemap", "waarschuwing", "", "Sitemap-URL is een redirect (hoort definitieve URL te zijn)", f"{u} → {p.final_url}")
                    elif p.soup and self._is_noindex(p):
                        self.add("sitemap", "waarschuwing", "", "Sitemap-URL staat op noindex", u)
            if not c.sitemap_urls:
                self.add("sitemap", "waarschuwing", "", "Sitemap bevat geen URL's", "")
            # pagina's die wel gecrawld maar niet in sitemap staan (info)
            sm_set = {normalize(u) for u in c.sitemap_urls}
            missing = [p.url for p in html_pages if p.url not in sm_set and not p.redirect_chain
                       and not self._is_noindex(p) and p.status == 200]
            if c.sitemap_urls and missing:
                for u in missing[: self.limit]:
                    self.add("sitemap", "info", "", "Pagina staat niet in de sitemap", u)

        # 404-pagina
        test404 = urljoin(root, "/sitecheck-deze-pagina-bestaat-niet-" + dt.datetime.now().strftime("%H%M%S"))
        p404 = c.fetch_page(test404)
        if p404.status == 200 and not p404.error:
            self.add("error_page", "fout", "", "Niet-bestaande URL geeft status 200 i.p.v. 404 (soft 404)", test404)
        elif p404.status in (301, 302, 307, 308) or (p404.redirect_chain and p404.final_url != normalize(test404)):
            self.add("error_page", "waarschuwing", "", "Niet-bestaande URL wordt doorgestuurd i.p.v. een 404-pagina te tonen", f"{test404} → {p404.final_url}")
        elif p404.status == 404:
            if p404.soup:
                txt = visible_text(p404.soup)
                has_msg = bool(re.search(r"(niet gevonden|not found|bestaat niet|404|oeps|oops|helaas|sorry)", txt, re.I))
                links = [a for a in p404.soup.find_all("a", href=True) if c.is_internal(urljoin(root, a["href"]))]
                has_search = bool(p404.soup.find("input", {"type": "search"}) or p404.soup.find("form", role="search"))
                if not has_msg:
                    self.add("error_page", "waarschuwing", "", "404-pagina bevat geen duidelijke 'niet gevonden'-melding", test404)
                if len(links) < 2 and not has_search:
                    self.add("error_page", "waarschuwing", "", "404-pagina biedt geen bruikbare vervolgstap (link naar home / menu / zoekfunctie)", test404)
                if len(txt) < 40:
                    self.add("error_page", "waarschuwing", "", "404-pagina is (bijna) leeg — standaard serverpagina?", test404)
            else:
                self.add("error_page", "waarschuwing", "", "404 zonder HTML-pagina (standaard servermelding)", test404)
        elif p404.error:
            self.add("error_page", "info", "", "404-test kon niet worden uitgevoerd", p404.error)

        # favicon (sitebreed)
        home = c.pages.get(root) or next((p for p in html_pages if p.depth == 0), None)
        if home and home.soup:
            icons = home.soup.find_all("link", rel=lambda r: r and any("icon" in x.lower() for x in (r if isinstance(r, list) else [r])))
            fav_urls = [urljoin(home.final_url or root, i.get("href", "")) for i in icons if i.get("href")]
            if not fav_urls:
                fav_urls = [urljoin(root, "/favicon.ico")]
                ls = c.check_link(fav_urls[0])
                if not ls.ok:
                    self.add("favicon", "fout", "", "Geen favicon ingesteld (geen <link rel=icon> en /favicon.ico ontbreekt)", "")
                else:
                    self.add("favicon", "info", "", "Favicon alleen via /favicon.ico — voeg <link rel=icon> toe", fav_urls[0])
            else:
                for fu in fav_urls[:3]:
                    ls = c.check_link(fu)
                    if not ls.ok:
                        self.add("favicon", "fout", "", f"Favicon niet bereikbaar ({ls.status or ls.error})", fu)
                    elif PLACEHOLDER_IMG_RE.search(fu) or re.search(r"(webflow|wordpress|wix|default|placeholder)", fu, re.I):
                        self.add("favicon", "waarschuwing", "", "Favicon lijkt een standaard/placeholder-icoon", fu)
            apple = home.soup.find("link", rel=lambda r: r and "apple-touch-icon" in " ".join(r if isinstance(r, list) else [r]))
            if not apple:
                self.add("favicon", "info", "", "Geen apple-touch-icon (webclip) ingesteld", "")

        # juridische pagina's
        all_anchor_text = defaultdict(set)
        for p in html_pages:
            for a in p.soup.find_all("a", href=True):
                t = (a.get_text(" ", strip=True) + " " + a["href"]).lower()
                all_anchor_text[p.url].add(t)
        combined = " || ".join(t for s in all_anchor_text.values() for t in s)
        for name, rx in LEGAL_PATTERNS.items():
            if not rx.search(combined):
                sev = "fout" if name != "algemene voorwaarden" else "info"
                self.add("legal_pages", sev, "", f"Geen link naar {name} gevonden", "Hoort in de footer te staan" if sev == "fout" else "Alleen nodig indien van toepassing")

        # cookiebanner
        has_cookie_tool = any(COOKIE_TOOLS.search(p.html) for p in html_pages[:10])
        has_tracking = any(rx.search(p.html) for p in html_pages[:10] for rx in ANALYTICS_RE.values())
        self.site_info["cookie_tool"] = has_cookie_tool
        if has_tracking and not has_cookie_tool:
            self.add("cookie_banner", "waarschuwing", "", "Trackingscripts gevonden maar geen cookiebanner/consent-tool herkend", "Controleer AVG-conformiteit")
        elif has_cookie_tool:
            self.add("cookie_banner", "info", "", "Cookie-consent tool herkend — controleer handmatig of keuzes werken en later aanpasbaar zijn", "")

        # analytics
        ids = defaultdict(set)
        for p in html_pages:
            for name, rx in ANALYTICS_RE.items():
                for m in rx.finditer(p.html):
                    ids[name].add(m.group(1) if m.groups() and m.group(1) else "aanwezig")
        self.site_info["analytics"] = {k: sorted(v) for k, v in ids.items()}
        if not ids:
            self.add("analytics", "waarschuwing", "", "Geen statistiek-/tagscript gevonden (GA4, GTM, Matomo, Plausible…)", "Controleer of meten gewenst is")
        else:
            for name, vals in ids.items():
                real = [v for v in vals if v != "aanwezig"]
                if len(real) > 1:
                    self.add("analytics", "waarschuwing", "", f"Meerdere {name}-ID's gevonden op de site", ", ".join(real))
                if "verouderd" in name:
                    self.add("analytics", "waarschuwing", "", "Verouderde Universal Analytics-code aanwezig (meet niet meer)", ", ".join(vals))
            pages_without = [p.url for p in html_pages if not any(rx.search(p.html) for rx in ANALYTICS_RE.values())]
            if ids and pages_without and len(pages_without) < len(html_pages):
                for u in pages_without[: self.limit]:
                    self.add("analytics", "waarschuwing", u, "Pagina bevat geen statistiekscript terwijl andere pagina's dat wel hebben", "")
            self.add("analytics", "info", "", "Gevonden meetscripts: " + "; ".join(f"{k}: {', '.join(v)}" for k, v in self.site_info["analytics"].items()),
                     "Controleer in de tool zelf of het juiste property/domein wordt gemeten")

        # taal
        langs = Counter((p.soup.html.get("lang") or "").lower() if p.soup.html else "" for p in html_pages)
        self.site_info["languages"] = dict(langs)
        if "" in langs:
            n = langs[""]
            self.add("language", "waarschuwing", "", f"{n} pagina('s) zonder lang-attribuut op <html>", "Nodig voor toegankelijkheid en vertaling")
        hreflang_pages = [p for p in html_pages if p.soup.find("link", rel="alternate", hreflang=True)]
        if len(langs) > 1 or hreflang_pages:
            self.add("language", "info", "", f"Meertalige site gedetecteerd ({', '.join(k or 'geen' for k in langs)}) — controleer handmatig of alle knoppen, formulieren en foutmeldingen vertaald zijn", "")

    # ---------------------------------------------------------- per pagina
    def check_page_status(self, p: Page):
        if p.error:
            self.add("page_status", "fout", p.url, f"Pagina niet bereikbaar: {p.error}", "")
            return
        if p.status >= 500:
            self.add("page_status", "fout", p.url, f"Serverfout {p.status}", self._sources(p.url))
        elif p.status == 404 or p.status == 410:
            self.add("page_status", "fout", p.url, f"Pagina niet gevonden ({p.status})", self._sources(p.url))
        elif p.status in (401, 403):
            self.add("page_status", "waarschuwing", p.url, f"Pagina afgeschermd ({p.status}) — bedoeld?", self._sources(p.url))
        elif p.status >= 400:
            self.add("page_status", "fout", p.url, f"Foutstatus {p.status}", self._sources(p.url))
        # redirects
        if p.redirect_chain:
            if len(p.redirect_chain) > 1:
                self.add("redirects", "waarschuwing", p.url, f"Redirectketen van {len(p.redirect_chain)} stappen",
                         " → ".join(p.redirect_chain + [p.final_url]))
            if p.final_url and not self.c.is_internal(p.final_url):
                self.add("redirects", "fout", p.url, "Interne URL stuurt door naar ander domein", f"→ {p.final_url}")
            if p.final_url and STAGING_RE.search(p.final_url):
                self.add("staging_links", "fout", p.url, "Redirect naar testomgeving", f"→ {p.final_url}")
        if p.status == 200 and p.soup and p.redirect_chain:
            # Interne links naar deze redirect-URL: beter direct linken
            srcs = self.c.link_sources.get(p.url, set())
            if srcs and not p.from_sitemap:
                self.add("redirects", "info", p.url, f"Interne link(s) verwijzen naar redirect i.p.v. eindbestemming ({len(srcs)} pagina's)", f"→ {p.final_url}")
        # testpagina
        if p.status == 200 and TEST_PAGE_RE.search(urlparse(p.url).path):
            self.add("test_pages", "waarschuwing", p.url, "URL lijkt een test-/ontwerp-/templatepagina", "Verwijderen, afschermen of op noindex zetten")
        if p.status == 200 and p.soup:
            t = p.soup.title.get_text(strip=True) if p.soup.title else ""
            if re.search(r"\b(test|concept|draft|template|styleguide|style guide|stijlgids|kopie|copy of|untitled|voorbeeld)\b", t, re.I):
                self.add("test_pages", "waarschuwing", p.url, "Paginatitel lijkt een test-/ontwerppagina", t)

    def _sources(self, url):
        s = self.c.link_sources.get(url) or self.c.link_sources.get(normalize(url)) or set()
        if not s:
            return ""
        lst = sorted(s)
        return "Gelinkt vanaf: " + ", ".join(lst[:3]) + (f" (+{len(lst)-3})" if len(lst) > 3 else "")

    def _is_noindex(self, p: Page):
        if not p.soup:
            return False
        for m in p.soup.find_all("meta", attrs={"name": re.compile(r"^robots$|googlebot", re.I)}):
            if "noindex" in (m.get("content") or "").lower():
                return True
        return False

    # -------------------------------------------------------------- content
    def check_content(self, p: Page):
        soup = p.soup
        text = visible_text(soup)
        p_text_len = len(main_text(soup))

        # placeholder tekst
        for m in PLACEHOLDER_RE.finditer(text):
            ctx = text[max(0, m.start() - 40): m.end() + 40]
            self.add("placeholder_text", "fout", p.url, f"Tijdelijke tekst: '{m.group(0)}'", f"…{ctx}…")
        # ook in title / meta
        for m in soup.find_all("meta", attrs={"name": "description"}):
            if PLACEHOLDER_RE.search(m.get("content", "")):
                self.add("placeholder_text", "fout", p.url, "Tijdelijke tekst in meta description", m.get("content"))
        if soup.title and PLACEHOLDER_RE.search(soup.title.get_text()):
            self.add("placeholder_text", "fout", p.url, "Tijdelijke tekst in paginatitel", soup.title.get_text(strip=True))

        # voorbeeldcontent
        for m in SAMPLE_CONTENT_RE.finditer(text):
            ctx = text[max(0, m.start() - 40): m.end() + 40]
            self.add("sample_content", "waarschuwing", p.url, f"Mogelijke voorbeeldcontent: '{m.group(0)}'", f"…{ctx}…")

        # interne opmerkingen in zichtbare tekst
        for m in INTERNAL_NOTE_RE.finditer(text):
            ctx = text[max(0, m.start() - 40): m.end() + 60]
            self.add("internal_notes", "fout", p.url, f"Interne opmerking zichtbaar: '{m.group(0).strip()}'", f"…{ctx}…")
        # HTML-comments met opmerkingen (niet zichtbaar, wel info)
        from bs4 import Comment
        for cm in soup.find_all(string=lambda s: isinstance(s, Comment)):
            if INTERNAL_NOTE_RE.search(cm) and len(cm) < 400:
                self.add("internal_notes", "info", p.url, "Opmerking in HTML-commentaar (niet zichtbaar voor bezoeker)", el_snippet(cm))

        # lege pagina
        if p.status == 200 and p_text_len < 150 and not self._is_noindex(p):
            self.add("empty_pages", "waarschuwing", p.url, f"Pagina bevat weinig eigen inhoud ({p_text_len} tekens buiten menu/footer)", "Lege pagina, categorie of contentblok?")
        # lege headings / lege contentblokken
        for h in soup.find_all(["h1", "h2", "h3"]):
            if not h.get_text(strip=True) and not h.find("img"):
                self.add("empty_pages", "waarschuwing", p.url, f"Lege <{h.name}>", str(h)[:100])
        for tag in soup.find_all(["p", "li", "blockquote"]):
            if tag.get_text(strip=True) == "" and not tag.find(["img", "svg", "iframe", "br", "input", "a"]) and tag.get("class"):
                pass  # te veel ruis bij lege <p> in builders; overslaan
        if not soup.find("h1"):
            self.add("empty_pages", "waarschuwing", p.url, "Geen H1-kop op de pagina", "")
        elif len(soup.find_all("h1")) > 1:
            self.add("text_quality", "info", p.url, f"{len(soup.find_all('h1'))} H1-koppen op de pagina", "; ".join(el_snippet(h, 50) for h in soup.find_all("h1")[:4]))

        # tekstkwaliteit: dubbele spaties, dubbele woorden, dubbele punten
        for m in re.finditer(r"\b(\w{3,})\s+\1\b", text):
            if m.group(1).lower() not in ("die", "dat", "een", "het", "van", "en", "voor", "zijn", "haar", "hun", "ooh", "zie", "bij"):
                ctx = text[max(0, m.start() - 30): m.end() + 30]
                self.add("text_quality", "info", p.url, f"Dubbel woord: '{m.group(0)}'", f"…{ctx}…")
        for m in re.finditer(r"[a-z]\s+[,.;:!?]\s", text):
            ctx = text[max(0, m.start() - 30): m.end() + 30]
            self.add("text_quality", "info", p.url, "Spatie vóór leesteken", f"…{ctx}…")
        for m in re.finditer(r"[.!?]\s+[a-z]{3,}\s", text):
            pass  # te veel false positives (merknamen), overslaan
        if re.search(r"\?\?\?|!!!|\.\.\.\.", text):
            self.add("text_quality", "info", p.url, "Opvallende leestekens (???, !!!, ....)", "")
        # encodingproblemen
        if re.search(r"Ã©|Ã«|Ã¯|Ã¶|Ã¼|â€™|â€œ|â€\u009d|Â ", p.html):
            self.add("text_quality", "waarschuwing", p.url, "Tekencodering-fout (bv. Ã© i.p.v. é)", "")
        # gemengde taal: Engelse standaardknoppen op NL-site
        lang = (soup.html.get("lang") or "").lower() if soup.html else ""
        if lang.startswith("nl"):
            eng = re.findall(r"\b(Read more|Learn more|Submit|Send message|Contact us|Thank you!|Oops! Something went wrong|"
                             r"Something went wrong while submitting the form|Your submission has been received|"
                             r"Please fill|This field is required|Previous|Next|View all|Get started|Sign up|Log in)\b", text)
            for e in sorted(set(eng))[:10]:
                self.add("language", "waarschuwing", p.url, f"Engelse standaardtekst op Nederlandse pagina: '{e}'", "Vertaal knop-/formuliertekst")
            for inp in soup.find_all("input", attrs={"type": "submit"}):
                v = inp.get("value", "")
                if re.match(r"^(submit|send)$", v, re.I):
                    self.add("language", "waarschuwing", p.url, f"Onvertaalde verzendknop: '{v}'", "")
            # Webflow standaard formulierteksten
            for div in soup.find_all(class_=re.compile(r"w-form-(done|fail)")):
                t = div.get_text(" ", strip=True)
                if re.search(r"(thank you|something went wrong|submission has been received)", t, re.I):
                    self.add("language", "waarschuwing", p.url, "Onvertaalde formulierbevestiging/-foutmelding", t[:120])

        # datums / copyright
        year = dt.date.today().year
        for m in DATE_RE.finditer(text):
            y = int(m.group(1))
            if y < year:
                self.add("outdated_dates", "waarschuwing", p.url, f"Copyright-jaar {y} is verouderd (nu {year})", m.group(0))
        # datums in teksten die oud lijken (alleen informatief)
        old = [y for y in OLD_YEAR_RE.findall(text) if int(y) <= year - 2]
        if old:
            cnt = Counter(old)
            self.add("outdated_dates", "info", p.url, "Oudere jaartallen in tekst — controleer actualiteit", ", ".join(f"{k} ({v}x)" for k, v in sorted(cnt.items())[:6]))

    # ---------------------------------------------------------------- links
    def check_links(self, p: Page):
        soup = p.soup
        base = p.final_url or p.url
        host = urlparse(base).netloc
        ids = {el.get("id") for el in soup.find_all(id=True)}
        names = {el.get("name") for el in soup.find_all("a", attrs={"name": True})}
        anchors = soup.find_all("a")

        for a in anchors:
            href = (a.get("href") or "").strip()
            txt = a.get_text(" ", strip=True)
            label = txt or a.get("aria-label") or (a.find("img") and a.find("img").get("alt")) or ""
            snippet = f"'{label[:60]}'" if label else f"<a> zonder tekst ({str(a)[:60]}…)"

            if not a.get("href") or href in ("", "#", "#!", "javascript:void(0)", "javascript:;", "javascript:"):
                # lege link = niet-gekoppelde knop
                if a.get("role") == "button" or a.get("data-toggle") or a.get("aria-haspopup") or a.get("data-w-id") or a.find_parent(class_=re.compile(r"dropdown|accordion|tab|menu|nav|slider|toggle|collapse", re.I)):
                    continue  # waarschijnlijk JS-element
                self.add("empty_links", "fout", p.url, f"Knop/link zonder bestemming: {snippet}", f'href="{href}"')
                continue
            low = href.lower()
            if low.startswith("tel:"):
                num = href[4:].strip()
                if not TEL_RE.match(num) or len(re.sub(r"\D", "", num)) < 9:
                    self.add("tel_mailto", "fout", p.url, f"Ongeldig telefoonnummer in link: {href}", snippet)
                elif not num.startswith("+") and not num.startswith("00"):
                    self.add("tel_mailto", "info", p.url, f"Telefoonnummer zonder landcode: {href}", "Gebruik tel:+31… voor internationaal gebruik")
                elif re.search(r"\s|\(|\)", num):
                    self.add("tel_mailto", "info", p.url, f"Spaties/haakjes in tel:-link (werkt meestal, maar niet overal): {href}", "")
                if self.expected.get("phone") and re.sub(r"\D", "", num)[-9:] != re.sub(r"\D", "", self.expected["phone"])[-9:]:
                    self.add("contact_consistency", "waarschuwing", p.url, f"Telefoonnummer in link wijkt af van opgegeven nummer: {num}", f"Verwacht: {self.expected['phone']}")
                continue
            if low.startswith("mailto:"):
                addr = href[7:].split("?")[0].strip()
                if not EMAIL_RE.match(addr):
                    self.add("tel_mailto", "fout", p.url, f"Ongeldig e-mailadres in link: {href}", snippet)
                elif re.search(r"(example|voorbeeld|test|dummy|placeholder|email@|naam@|info@domein)", addr, re.I):
                    self.add("tel_mailto", "fout", p.url, f"Voorbeeld-e-mailadres in link: {addr}", snippet)
                if self.expected.get("email") and addr.lower() != self.expected["email"].lower():
                    self.add("contact_consistency", "waarschuwing", p.url, f"E-mailadres in link wijkt af: {addr}", f"Verwacht: {self.expected['email']}")
                continue
            if low.startswith(("javascript:", "sms:", "whatsapp:", "data:")):
                continue
            if href.startswith("#"):
                frag = href[1:]
                if frag and frag not in ids and frag not in names:
                    self.add("anchor_links", "fout", p.url, f"Ankerlink #{frag} verwijst naar niet-bestaand onderdeel", snippet)
                continue

            absu = urljoin(base, href)
            if not absu.startswith(("http://", "https://")):
                continue
            # anker op andere pagina
            if "#" in absu:
                target, frag = absu.split("#", 1)
                tn = normalize(target)
                if frag and tn in self.c.pages and self.c.pages[tn].soup:
                    tsoup = self.c.pages[tn].soup
                    if not tsoup.find(id=frag) and not tsoup.find("a", attrs={"name": frag}):
                        self.add("anchor_links", "fout", p.url, f"Ankerlink naar {target}#{frag}: onderdeel bestaat niet op doelpagina", snippet)

            # staging / testomgeving
            if STAGING_RE.search(absu) and not self.c.is_internal(absu):
                self.add("staging_links", "fout", p.url, f"Link naar testomgeving: {absu}", snippet)
            elif absu.startswith("http://") and self.c.is_internal(absu) and self.c.start_url.startswith("https://"):
                self.add("staging_links", "waarschuwing", p.url, f"Interne link via http:// i.p.v. https://: {absu}", snippet)

            # generieke linktekst
            if txt.lower().strip(" .>›»→") in GENERIC_LINK_TEXT:
                self.add("generic_link_text", "info", p.url, f"Generieke linktekst '{txt}'", f"→ {absu}")

            # status
            status, final, err, chain = self.c.status_of(absu)
            is_dl = bool(DOWNLOAD_EXT.search(urlparse(absu).path))
            code = "downloads" if is_dl else "broken_links"
            ext = "externe " if not self.c.is_internal(absu) else ""
            if err:
                self.add(code, "fout" if self.c.is_internal(absu) else "waarschuwing", p.url, f"{ext.capitalize()}{'download' if is_dl else 'link'} niet bereikbaar ({err}): {absu}", snippet)
            elif status is not None and status >= 400:
                sev = "fout" if status in (404, 410, 500, 502, 503) else "waarschuwing"
                if not self.c.is_internal(absu) and status in (403, 429, 999):
                    sev = "info"  # bot-blokkade (LinkedIn geeft 999)
                self.add(code, sev, p.url, f"{ext.capitalize()}{'download' if is_dl else 'link'} geeft {status}: {absu}", snippet)
            elif chain and self.c.is_internal(absu) and len(chain) >= 1 and final and normalize(final) != normalize(absu):
                self.add("redirects", "info", p.url, f"Interne link gaat via redirect: {absu}", f"→ {final}")
            if is_dl and status and status < 400:
                ls = self.c.links.get(absu)
                if ls and ls.content_type and "html" in ls.content_type:
                    self.add("downloads", "waarschuwing", p.url, f"Download-link levert HTML i.p.v. bestand: {absu}", snippet)
                if re.search(r"(concept|draft|test|oud|old|kopie|copy|v\d|versie|final_?final|def)[-_. ]", urlparse(absu).path, re.I):
                    self.add("downloads", "waarschuwing", p.url, f"Bestandsnaam suggereert concept/oude versie: {urlparse(absu).path.rsplit('/',1)[-1]}", absu)
            # externe link: open in nieuw venster zonder rel=noopener
            if not self.c.is_internal(absu) and a.get("target") == "_blank" and "noopener" not in (a.get("rel") or []):
                pass  # moderne browsers regelen dit; geen melding

        # logo → home
        logo_candidates = []
        header = soup.find("header") or soup.find(class_=re.compile(r"header|navbar|nav-?bar|topbar", re.I)) or soup.find("nav")
        scope = header or soup
        for a in scope.find_all("a"):
            img = a.find("img") or a.find("svg")
            cls = " ".join(a.get("class") or []) + " " + (a.get("id") or "") + " " + (a.get("aria-label") or "")
            if (img and re.search(r"logo|brand", (img.get("alt") or "") + " " + (img.get("src") or "") + " " + " ".join(img.get("class") or []) + cls, re.I)) or re.search(r"\b(logo|brand)\b", cls, re.I):
                logo_candidates.append(a)
        if header and not logo_candidates:
            for a in header.find_all("a"):
                if a.find("img") or a.find("svg"):
                    logo_candidates.append(a)
                    break
        for a in logo_candidates[:2]:
            href = a.get("href", "")
            if not href or href in ("#", ""):
                self.add("logo_home_link", "fout", p.url, "Logo is niet gekoppeld aan de homepage (lege link)", str(a)[:120])
                continue
            target = normalize(urljoin(base, href))
            home = normalize(self.c.start_url)
            home_alt = home.rstrip("/") + "/"
            tgt_path = urlparse(target).path.rstrip("/") or "/"
            if self.c.is_internal(target) and tgt_path in ("/", "/home", "/index", "/index.html", "/nl", "/en", "/de", "/fr"):
                continue
            if target in (home, home_alt):
                continue
            self.add("logo_home_link", "waarschuwing", p.url, f"Logo verwijst niet naar de homepage maar naar {href}", "")

        # navigatie aanwezig
        if not soup.find("nav") and not soup.find(role="navigation") and not soup.find(class_=re.compile(r"\bnav|menu", re.I)):
            self.add("nav_present", "waarschuwing", p.url, "Geen navigatiemenu gevonden op de pagina", "")
        # mobiel menu aanwezig (hamburger)
        if soup.find("nav") and not soup.find(class_=re.compile(r"hamburger|menu-?button|menu-?toggle|navbar-?toggler|w-nav-button|burger|mobile-?menu|menu-?icon|nav-?toggle", re.I)) and not soup.find(attrs={"aria-label": re.compile(r"menu", re.I)}):
            self.add("nav_present", "info", p.url, "Geen mobiele menuknop herkend — controleer mobiel menu handmatig", "")

    # --------------------------------------------------------------- images
    def check_images(self, p: Page):
        soup = p.soup
        base = p.final_url or p.url
        for img in soup.find_all("img"):
            src = (img.get("src") or img.get("data-src") or "").strip()
            if not src or src.startswith("data:"):
                if not src and not img.get("srcset") and not img.get("data-srcset"):
                    self.add("broken_images", "waarschuwing", p.url, "Afbeelding zonder src", str(img)[:120])
                continue
            absu = urljoin(base, src)
            alt = img.get("alt")
            role = img.get("role")
            decorative = (alt == "" ) or role == "presentation" or img.get("aria-hidden") == "true"
            # alt
            if alt is None:
                self.add("img_alt", "waarschuwing", p.url, "Afbeelding zonder alt-attribuut", absu)
            elif alt and re.search(r"^(image|img|afbeelding|foto|photo|picture|logo|icon|icoon|untitled|dsc[_-]?\d+|img[_-]?\d+|screenshot|schermafbeelding|\d+|placeholder)[\s\-_.]*\d*$", alt.strip(), re.I):
                self.add("img_alt", "info", p.url, f"Weinig beschrijvende alt-tekst: '{alt}'", absu)
            elif alt and re.search(r"\.(jpe?g|png|gif|webp|svg|avif)$", alt.strip(), re.I):
                self.add("img_alt", "waarschuwing", p.url, f"Alt-tekst is een bestandsnaam: '{alt}'", absu)
            # placeholder/stock
            if PLACEHOLDER_IMG_RE.search(absu) or (alt and PLACEHOLDER_IMG_RE.search(alt)):
                self.add("placeholder_images", "fout", p.url, "Placeholder-/stock-/testafbeelding", absu)
            if re.search(r"(shutterstock|istock|gettyimages|adobestock|depositphotos|dreamstime|123rf|alamy)", (alt or "") + src, re.I):
                self.add("placeholder_images", "fout", p.url, "Afbeelding verwijst naar stockfotosite (watermerk/preview?)", absu)
            if STAGING_RE.search(absu) and not self.c.is_internal(absu) and not re.search(r"(webflow\.com|cloudfront|cdn\.|cloudinary|imgix|amazonaws|googleusercontent|wp\.com|squarespace-cdn|wixstatic|shopify)", absu, re.I):
                self.add("staging_links", "fout", p.url, f"Afbeelding geladen vanaf testomgeving: {absu}", "")
            # status
            status, final, err, chain = self.c.status_of(absu)
            if err or (status is not None and status >= 400):
                self.add("broken_images", "fout", p.url, f"Afbeelding laadt niet ({err or status})", absu)
            # zwaarte
            ls = self.c.links.get(absu)
            if ls and ls.content_length:
                kb = ls.content_length / 1024
                if kb > 1024:
                    self.add("heavy_media", "fout", p.url, f"Zeer zware afbeelding: {kb/1024:.1f} MB", absu)
                elif kb > 400:
                    self.add("heavy_media", "waarschuwing", p.url, f"Zware afbeelding: {kb:.0f} KB", absu)
                if ls.content_type and re.search(r"image/(png|jpe?g|bmp|tiff)", ls.content_type) and kb > 200:
                    self.add("heavy_media", "info", p.url, f"Afbeelding ({kb:.0f} KB) kan lichter als WebP/AVIF", absu)
            # afmetingen
            w, h = img.get("width"), img.get("height")
            if not (w and h) and not img.get("style") and "svg" not in absu.lower():
                pass  # te veel ruis; builders zetten vaak CSS. Niet melden.
            # vervorming: width/height attribuut in andere verhouding dan natuurlijk is niet te zien zonder render → overslaan
        # video's
        for v in soup.find_all(["video", "source"]):
            src = v.get("src") or ""
            if src:
                absu = urljoin(base, src)
                ls = self.c.links.get(absu)
                status, final, err, chain = self.c.status_of(absu)
                if err or (status and status >= 400):
                    self.add("broken_images", "fout", p.url, f"Video laadt niet ({err or status})", absu)
                if ls and ls.content_length > 10 * 1024 * 1024:
                    self.add("heavy_media", "waarschuwing", p.url, f"Zware video: {ls.content_length/1024/1024:.0f} MB — overweeg streaming (YouTube/Vimeo) of compressie", absu)
        # srcset / lazy loading
        imgs = soup.find_all("img")
        if len(imgs) > 6 and not any(i.get("loading") == "lazy" for i in imgs):
            self.add("page_speed", "info", p.url, f"{len(imgs)} afbeeldingen zonder lazy loading", "Voeg loading=\"lazy\" toe aan afbeeldingen onder de vouw")

    # ------------------------------------------------------------------ SEO
    def check_seo(self, p: Page):
        soup = p.soup
        base = p.final_url or p.url
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        if not title:
            self.add("title", "fout", p.url, "Geen paginatitel (<title>)", "")
        else:
            if len(title) < 20:
                self.add("title", "waarschuwing", p.url, f"Korte paginatitel ({len(title)} tekens): '{title}'", "Streef naar 30–60 tekens")
            elif len(title) > 65:
                self.add("title", "info", p.url, f"Lange paginatitel ({len(title)} tekens) wordt afgekapt in Google", title)
            if DEFAULT_TITLES.match(title.strip()):
                self.add("default_seo", "fout", p.url, f"Standaard/tijdelijke paginatitel: '{title}'", "")
            m = re.match(r"^(.*?)\s*[-|–—]\s*(.*)$", title)
            if m and m.group(1).strip().lower() in ("home", "homepage", "untitled", "nieuwe pagina", "new page", "page", "pagina"):
                if urlparse(p.url).path.strip("/"):
                    self.add("default_seo", "waarschuwing", p.url, f"Paginatitel begint met '{m.group(1)}' op een subpagina", title)
        descs = soup.find_all("meta", attrs={"name": re.compile(r"^description$", re.I)})
        if not descs or not (descs[0].get("content") or "").strip():
            if not self._is_noindex(p):
                self.add("meta_description", "waarschuwing", p.url, "Geen meta description", "")
        else:
            d = descs[0].get("content").strip()
            if len(d) < 50:
                self.add("meta_description", "info", p.url, f"Korte meta description ({len(d)} tekens)", d)
            elif len(d) > 165:
                self.add("meta_description", "info", p.url, f"Lange meta description ({len(d)} tekens) wordt afgekapt", d[:100] + "…")
            if PLACEHOLDER_RE.search(d) or re.search(r"^(description|omschrijving|meta description|beschrijving|enter .*description|.*description here)", d, re.I):
                self.add("default_seo", "fout", p.url, "Tijdelijke/standaard meta description", d)
            if len(descs) > 1:
                self.add("meta_description", "info", p.url, "Meerdere meta descriptions", "")
        # noindex
        if self._is_noindex(p):
            if urlparse(p.url).path in ("/", "") or p.from_sitemap:
                self.add("noindex", "fout", p.url, "Pagina staat op noindex (homepage of in sitemap) — site geblokkeerd voor Google?", "")
            else:
                self.add("noindex", "waarschuwing", p.url, "Pagina staat op noindex — bedoeld?", "")
        # X-Robots-Tag kunnen we hier niet lezen zonder headers → overslaan (headers niet bewaard)
        # canonical
        can = soup.find("link", rel="canonical")
        if can and can.get("href"):
            cu = urljoin(base, can["href"])
            if not self.c.is_internal(cu):
                self.add("staging_links", "fout", p.url, f"Canonical verwijst naar ander domein: {cu}", "Testomgeving-canonical?")
            elif normalize(cu) != normalize(p.final_url or p.url) and urlparse(cu).path.rstrip("/") != urlparse(p.url).path.rstrip("/"):
                self.add("noindex", "info", p.url, f"Canonical wijst naar andere pagina: {cu}", "Bedoeld? Anders wordt deze pagina niet geïndexeerd")
        else:
            self.add("noindex", "info", p.url, "Geen canonical-tag", "Aanbevolen, niet verplicht")
        # Open Graph
        og = {m.get("property"): (m.get("content") or "").strip() for m in soup.find_all("meta", property=re.compile(r"^og:", re.I))}
        tw = {m.get("name"): (m.get("content") or "").strip() for m in soup.find_all("meta", attrs={"name": re.compile(r"^twitter:", re.I)})}
        if not og.get("og:title") and not tw.get("twitter:title"):
            self.add("open_graph", "waarschuwing", p.url, "Geen og:title (deel-titel voor LinkedIn/WhatsApp)", "")
        if not og.get("og:description") and not tw.get("twitter:description"):
            self.add("open_graph", "waarschuwing", p.url, "Geen og:description", "")
        ogi = og.get("og:image") or tw.get("twitter:image")
        if not ogi:
            self.add("open_graph", "waarschuwing", p.url, "Geen og:image (deel-afbeelding)", "Zonder afbeelding ziet een gedeelde link er kaal uit")
        else:
            ogi_abs = urljoin(base, ogi)
            if not ogi_abs.startswith("https://") and self.c.start_url.startswith("https://"):
                self.add("open_graph", "waarschuwing", p.url, "og:image is geen https:// URL", ogi_abs)
            if STAGING_RE.search(ogi_abs) and not self.c.is_internal(ogi_abs) and not re.search(r"(webflow\.com|cloudfront|cdn\.|cloudinary|imgix|amazonaws|googleusercontent|wp\.com|squarespace-cdn|wixstatic|shopify)", ogi_abs, re.I):
                self.add("staging_links", "fout", p.url, f"og:image verwijst naar testomgeving: {ogi_abs}", "")
            if PLACEHOLDER_IMG_RE.search(ogi_abs):
                self.add("open_graph", "fout", p.url, "og:image is een placeholder", ogi_abs)
            ls = self.c.links.get(ogi_abs)
            if ls is None:
                ls = self.c.check_link(ogi_abs)
                self.c.links[ogi_abs] = ls
            if not ls.ok:
                self.add("open_graph", "fout", p.url, f"og:image niet bereikbaar ({ls.status or ls.error})", ogi_abs)
        if og.get("og:url"):
            ou = og["og:url"]
            if not self.c.is_internal(ou):
                self.add("staging_links", "fout", p.url, f"og:url verwijst naar ander domein: {ou}", "")
        if og.get("og:title") and PLACEHOLDER_RE.search(og["og:title"]):
            self.add("open_graph", "fout", p.url, "Placeholder in og:title", og["og:title"])

    # ---------------------------------------------------------------- forms
    def check_forms(self, p: Page):
        soup = p.soup
        forms = soup.find_all("form")
        for i, f in enumerate(forms, 1):
            fields = f.find_all(["input", "textarea", "select"])
            real = [x for x in fields if (x.get("type") or "text").lower() not in ("hidden", "submit", "button", "reset", "image")]
            is_search = (f.get("role") == "search") or any((x.get("type") or "").lower() == "search" for x in fields) or re.search(r"search|zoek", " ".join(f.get("class") or []) + (f.get("id") or "") + (f.get("action") or ""), re.I)
            if is_search:
                self.add("search_found", "info", p.url, "Zoekformulier gevonden — test handmatig op relevante resultaten en 'geen resultaten'-melding", (f.get("action") or ""))
                continue
            if not real:
                continue
            name = f.get("name") or f.get("id") or f.get("data-name") or f"formulier {i}"
            action = f.get("action") or ""
            abs_action = urljoin(p.final_url or p.url, action) if action else ""
            self.add("forms_found", "info", p.url, f"Formulier '{name}' met {len(real)} veld(en) — test met een echte inzending", f"action: {abs_action or '(JS/onzelfde pagina)'}")
            if abs_action and STAGING_RE.search(abs_action) and not self.c.is_internal(abs_action) and not re.search(r"webflow\.com|formspree|hsforms|hubspot|mailchimp|activehosted|getform|basin|netlify", abs_action, re.I):
                self.add("staging_links", "fout", p.url, f"Formulier verzendt naar testomgeving: {abs_action}", name)
            if abs_action.startswith("http://"):
                self.add("https", "fout", p.url, f"Formulier verzendt via http:// (onveilig): {abs_action}", name)
            # labels
            for x in real:
                xid = x.get("id")
                has_label = False
                if xid and soup.find("label", attrs={"for": xid}):
                    has_label = True
                elif x.find_parent("label"):
                    has_label = True
                elif x.get("aria-label") or x.get("aria-labelledby") or x.get("title"):
                    has_label = True
                if not has_label:
                    if x.get("placeholder"):
                        self.add("form_labels", "waarschuwing", p.url, f"Veld '{x.get('name') or x.get('placeholder')}' heeft alleen een placeholder, geen label", f"Formulier '{name}'")
                    else:
                        self.add("form_labels", "fout", p.url, f"Veld '{x.get('name') or xid or x.name}' heeft geen label", f"Formulier '{name}'")
            # verplichte velden
            req = [x for x in real if x.has_attr("required") or x.get("aria-required") == "true"]
            if not req and len(real) >= 2:
                self.add("form_required", "waarschuwing", p.url, f"Formulier '{name}' heeft geen verplichte velden (required)", "E-mail/naam verplicht maken?")
            emails = [x for x in real if (x.get("type") or "").lower() == "email" or re.search(r"e-?mail", (x.get("name") or "") + (x.get("id") or ""), re.I)]
            for e in emails:
                if (e.get("type") or "text").lower() != "email":
                    self.add("form_required", "info", p.url, f"E-mailveld '{e.get('name')}' heeft type='{e.get('type','text')}' i.p.v. 'email'", "Geen automatische invoercontrole")
            # upload
            if any((x.get("type") or "").lower() == "file" for x in real):
                self.add("form_upload", "info", p.url, f"Formulier '{name}' heeft een upload-veld — test uploaden handmatig", "")
            # spam
            if not SPAM_RE.search(str(f)) and not SPAM_RE.search(p.html):
                self.add("form_spam", "waarschuwing", p.url, f"Geen spambeveiliging herkend bij formulier '{name}'", "reCAPTCHA/Turnstile/honeypot aanbevolen")
            # submit-knop
            sub = f.find(["button", "input"], attrs={"type": "submit"}) or f.find("button")
            if not sub:
                self.add("form_required", "waarschuwing", p.url, f"Formulier '{name}' heeft geen verzendknop", "")
            # Webflow: redirect/success
            if f.get("data-redirect") and STAGING_RE.search(f["data-redirect"]):
                self.add("staging_links", "fout", p.url, f"Bedankpagina-redirect naar testomgeving: {f['data-redirect']}", name)
            if f.get("data-redirect"):
                st, fin, err, ch = self.c.status_of(urljoin(p.url, f["data-redirect"]))
                if st is None:
                    ls = self.c.check_link(urljoin(p.url, f["data-redirect"]))
                    st, err = ls.status, ls.error
                if err or (st and st >= 400):
                    self.add("broken_links", "fout", p.url, f"Bedankpagina na formulier niet bereikbaar ({err or st})", f["data-redirect"])

    # ------------------------------------------------------------- security
    def check_security(self, p: Page):
        soup = p.soup
        base = p.final_url or p.url
        if base.startswith("https://"):
            for tag, attr in (("img", "src"), ("script", "src"), ("link", "href"), ("iframe", "src"), ("source", "src"), ("video", "src")):
                for el in soup.find_all(tag):
                    v = el.get(attr) or ""
                    if v.startswith("http://"):
                        if tag == "link" and not any(r in (el.get("rel") or []) for r in ("stylesheet", "icon", "preload")):
                            continue
                        self.add("mixed_content", "fout", p.url, f"Mixed content: <{tag}> via http://", v)
        # keyboard / a11y
        skip = soup.find("a", href=re.compile(r"^#(main|content|inhoud|skip)", re.I))
        if not skip:
            self.add("keyboard_a11y", "info", p.url, "Geen 'skip to content'-link voor toetsenbordgebruikers", "Optioneel, wel aanbevolen")
        if re.search(r"outline\s*:\s*(none|0)\s*[;!}]", p.html) and not re.search(r":focus-visible", p.html):
            self.add("keyboard_a11y", "waarschuwing", p.url, "CSS verbergt focus-rand (outline: none) zonder focus-visible-alternatief", "Toetsenbordgebruikers zien niet welk element geselecteerd is")
        for el in soup.find_all(["div", "span"], onclick=True):
            if not el.get("tabindex") and not el.get("role"):
                self.add("keyboard_a11y", "waarschuwing", p.url, "Klikbaar element (div/span met onclick) niet met toetsenbord bereikbaar", el_snippet(el, 60))
        # knoppen zonder tekst
        for b in soup.find_all("button"):
            if not b.get_text(strip=True) and not b.get("aria-label") and not b.get("title") and not (b.find("img") and b.find("img").get("alt")):
                self.add("keyboard_a11y", "waarschuwing", p.url, "Knop zonder tekst of aria-label", str(b)[:100])
        for a in soup.find_all("a", href=True):
            if not a.get_text(strip=True) and not a.get("aria-label") and not a.get("title") and not (a.find("img") and (a.find("img").get("alt") or "").strip()) and not a.find("svg", attrs={"aria-label": True}):
                if a.find(["img", "svg"]):
                    self.add("keyboard_a11y", "info", p.url, "Link met alleen afbeelding/icoon zonder alt of aria-label", a["href"][:80])

    # ---------------------------------------------------------- performance
    def check_performance(self, p: Page):
        if p.elapsed_ms > 3000:
            self.add("page_speed", "fout", p.url, f"Trage serverreactie: {p.elapsed_ms/1000:.1f} s", "HTML-document, zonder afbeeldingen")
        elif p.elapsed_ms > 1500:
            self.add("page_speed", "waarschuwing", p.url, f"Langzame serverreactie: {p.elapsed_ms/1000:.1f} s", "")
        if p.size_bytes > 1_500_000:
            self.add("page_speed", "waarschuwing", p.url, f"Groot HTML-document: {p.size_bytes/1024:.0f} KB", "")
        # totale paginagewicht (benadering op basis van bekende Content-Length)
        total = 0
        for href, absu, el in self.c.extract_links(p):
            if el.name in ("img", "script", "link", "source", "video"):
                ls = self.c.links.get(absu)
                if ls and ls.content_length:
                    total += ls.content_length
        if total > 5_000_000:
            self.add("page_speed", "fout", p.url, f"Pagina laadt ≈{total/1024/1024:.1f} MB aan media/scripts", "Te zwaar voor mobiel")
        elif total > 2_500_000:
            self.add("page_speed", "waarschuwing", p.url, f"Pagina laadt ≈{total/1024/1024:.1f} MB aan media/scripts", "")
        # viewport
        vp = p.soup.find("meta", attrs={"name": "viewport"})
        if not vp:
            self.add("viewport", "fout", p.url, "Geen viewport-meta — pagina schaalt niet op mobiel", "")
        elif re.search(r"user-scalable\s*=\s*(no|0)|maximum-scale\s*=\s*1(\.0)?\b", vp.get("content", ""), re.I):
            self.add("viewport", "waarschuwing", p.url, "Viewport blokkeert inzoomen (user-scalable=no / maximum-scale=1)", vp.get("content"))
        # scripts
        scripts = [s for s in p.soup.find_all("script", src=True)]
        if len(scripts) > 25:
            self.add("page_speed", "info", p.url, f"{len(scripts)} externe scripts geladen", "")

    # -------------------------------------------------------------- dynamic
    def check_dynamic(self, p: Page):
        html = p.html
        found = [name for name, rx in EMBED_RE.items() if rx.search(html)]
        if found:
            self.add("embeds", "info", p.url, "Dynamische/externe onderdelen: " + ", ".join(found), "Controleer handmatig of ze laden en werken (ook op mobiel)")
        for ifr in p.soup.find_all("iframe", src=True):
            src = ifr["src"]
            if src.startswith("http://"):
                self.add("mixed_content", "fout", p.url, "iframe via http://", src)
            if STAGING_RE.search(src) and not re.search(r"(youtube|vimeo|google|calendly|typeform|hubspot|maps)", src, re.I):
                self.add("staging_links", "fout", p.url, f"iframe laadt vanaf testomgeving: {src}", "")
            if re.search(r"maps\.google|google\.com/maps", src) and not re.search(r"(q=|place|pb=|embed\?)", src):
                self.add("embeds", "waarschuwing", p.url, "Google Maps-embed zonder locatie", src[:120])
            if "youtube.com/embed/" in src and re.search(r"embed/?(\?|$)", src):
                self.add("embeds", "fout", p.url, "YouTube-embed zonder video-ID", src)
        for v in p.soup.find_all("video"):
            if not v.get("src") and not v.find("source"):
                self.add("embeds", "fout", p.url, "Video-element zonder bron", str(v)[:100])

    # ---------------------------------------------------- site-brede checks
    def check_duplicates(self, html_pages):
        titles = defaultdict(list)
        descs = defaultdict(list)
        for p in html_pages:
            if p.redirect_chain or self._is_noindex(p) or p.status != 200:
                continue
            t = p.soup.title.get_text(" ", strip=True) if p.soup.title else ""
            if t:
                titles[t].append(p.url)
            d = p.soup.find("meta", attrs={"name": "description"})
            if d and d.get("content"):
                descs[d["content"].strip()].append(p.url)
        for t, urls in titles.items():
            if len(urls) > 1:
                for u in urls[: self.limit]:
                    self.add("duplicate_seo", "waarschuwing", u, f"Dubbele paginatitel ('{t[:60]}') op {len(urls)} pagina's", "Elke pagina hoort een unieke titel te hebben")
        for d, urls in descs.items():
            if len(urls) > 1:
                for u in urls[: self.limit]:
                    self.add("duplicate_seo", "waarschuwing", u, f"Dubbele meta description op {len(urls)} pagina's", d[:100])
        # dubbele content (zelfde hoofdtekst)
        bodies = defaultdict(list)
        for p in html_pages:
            if p.status == 200 and not p.redirect_chain:
                mt = main_text(p.soup)
                if len(mt) > 200:
                    bodies[hash(mt)].append(p.url)
        for h, urls in bodies.items():
            if len(urls) > 1:
                for u in urls[: self.limit]:
                    self.add("empty_pages", "warning" if False else "waarschuwing", u, f"Identieke inhoud als {len(urls)-1} andere pagina('s)", ", ".join(x for x in urls if x != u)[:200])

    def check_consistency(self, html_pages):
        """Contactgegevens: verzamel alle telefoonnummers/e-mails en meld afwijkingen."""
        phones, emails = Counter(), Counter()
        where_p, where_e = defaultdict(set), defaultdict(set)
        for p in html_pages:
            txt = visible_text(p.soup)
            for m in PHONE_TEXT_RE.finditer(txt):
                norm = re.sub(r"\D", "", m.group(0))
                norm = norm[-9:]
                phones[norm] += 1
                where_p[norm].add(p.url)
            for m in EMAIL_TEXT_RE.finditer(txt):
                e = m.group(0).lower().rstrip(".")
                if not re.search(r"\.(png|jpg|svg|js|css|webp)$", e):
                    emails[e] += 1
                    where_e[e].add(p.url)
        self.site_info["phones"] = {k: v for k, v in phones.items()}
        self.site_info["emails"] = {k: v for k, v in emails.items()}
        if len(phones) > 1:
            self.add("contact_consistency", "waarschuwing", "", f"{len(phones)} verschillende telefoonnummers op de site gevonden",
                     "; ".join(f"…{k} ({v}x)" for k, v in phones.most_common(6)))
        if len(emails) > 2:
            self.add("contact_consistency", "info", "", f"{len(emails)} verschillende e-mailadressen op de site",
                     "; ".join(f"{k} ({v}x)" for k, v in emails.most_common(6)))
        for e in emails:
            if re.search(r"(example|voorbeeld|test@|dummy|@domein|@website|@bedrijf|naam@|email@|@mail\.com)", e):
                self.add("sample_content", "fout", "", f"Voorbeeld-e-mailadres in tekst: {e}", ", ".join(sorted(where_e[e])[:3]))
        if self.expected.get("phone"):
            exp = re.sub(r"\D", "", self.expected["phone"])[-9:]
            for k in phones:
                if k != exp:
                    self.add("contact_consistency", "waarschuwing", "", f"Telefoonnummer …{k} wijkt af van opgegeven {self.expected['phone']}", ", ".join(sorted(where_p[k])[:3]))
        if self.expected.get("email"):
            for e in emails:
                if e != self.expected["email"].lower():
                    self.add("contact_consistency", "info", "", f"E-mailadres {e} wijkt af van opgegeven {self.expected['email']}", ", ".join(sorted(where_e[e])[:3]))
        if self.expected.get("company"):
            comp = self.expected["company"].lower()
            miss = [p.url for p in html_pages if comp not in visible_text(p.soup).lower() and comp not in (p.soup.title.get_text().lower() if p.soup.title else "")]
            if miss and len(miss) == len(html_pages):
                self.add("contact_consistency", "waarschuwing", "", f"Bedrijfsnaam '{self.expected['company']}' komt op geen enkele pagina voor", "")
        if self.expected.get("address"):
            addr = self.expected["address"].lower()
            found = any(addr in visible_text(p.soup).lower() for p in html_pages)
            if not found:
                self.add("contact_consistency", "waarschuwing", "", f"Adres '{self.expected['address']}' niet (letterlijk) gevonden op de site", "Controleer footer/contactpagina")
        # old urls: alleen info als redirect-rapport gewenst
        self.add("old_urls", "info", "", "Oude URL's: lever een lijst met oude URL's aan (--old-urls bestand.txt) om redirects automatisch te testen", "")

    # --------------------------------------------------------- oude URL's
    def check_old_urls(self, old_urls: list[str]):
        for u in old_urls:
            u = u.strip()
            if not u or u.startswith("#"):
                continue
            if not u.startswith("http"):
                u = urljoin(self.c.start_url, u)
            ls = self.c.check_link(u)
            if ls.error:
                self.add("old_urls", "fout", "", f"Oude URL niet bereikbaar ({ls.error})", u)
            elif ls.status == 404 or ls.status == 410:
                self.add("old_urls", "fout", "", f"Oude URL geeft {ls.status} — geen redirect ingesteld", u)
            elif not ls.redirect_chain:
                self.add("old_urls", "info", "", f"Oude URL bestaat nog (status {ls.status}, geen redirect)", u)
            elif len(ls.redirect_chain) > 1:
                self.add("old_urls", "waarschuwing", "", f"Oude URL redirect in {len(ls.redirect_chain)} stappen", f"{u} → {ls.final_url}")
            elif ls.status >= 400:
                self.add("old_urls", "fout", "", f"Oude URL redirect eindigt in {ls.status}", f"{u} → {ls.final_url}")
            elif urlparse(ls.final_url).path.rstrip("/") in ("", "/"):
                self.add("old_urls", "waarschuwing", "", "Oude URL redirect naar homepage (geen specifieke pagina)", f"{u} → {ls.final_url}")
            else:
                self.add("old_urls", "info", "", f"OK: redirect ({ls.redirect_chain and 'via ' + str(len(ls.redirect_chain)) + ' stap'})", f"{u} → {ls.final_url}")
