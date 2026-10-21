"""Testsite met opzettelijk geplante fouten, om SiteCheck te valideren.
Start: python tests/testsite/app.py  →  http://127.0.0.1:8765
"""
from flask import Flask, Response, redirect, request

app = Flask(__name__)

HEAD = """<!doctype html><html lang="nl"><head><meta charset="utf-8">{viewport}
<title>{title}</title>{meta}
<link rel="icon" href="/favicon.png">
<style>a:focus{{outline:none}}</style></head><body>
<header><a href="/" class="logo"><img src="/img/logo.png" alt="Logo Testbedrijf"></a>
<nav><a href="/">Home</a> <a href="/diensten">Diensten</a> <a href="/contact">Contact</a> <a href="/over-ons">Over ons</a>
<a href="/test-pagina">Test</a> <a href="/bestaat-niet">Kapot</a> <a href="/redirect-a">Redirect</a><a href="/blog/artikel-1">Blog</a></nav>
<div class="w-nav-button"></div></header><main>"""
FOOT = """</main><footer><p>© 2023 Testbedrijf B.V. · Hoofdstraat 1 · <a href="tel:0101234567">010-1234567</a> · <a href="mailto:info@example.com">mail</a>
· <a href="/privacy">Privacyverklaring</a> · <a href="https://testbedrijf.webflow.io/oude-pagina">oude link</a> · <a href="http://127.0.0.1:8765/diensten">http-link</a></p>
<a href="#">Lees meer</a> <a href="/downloads/brochure_concept_v2.pdf">Brochure</a>
<script async src="https://www.googletagmanager.com/gtag/js?id=G-TEST12345"></script><script>gtag('config','G-TEST12345');</script>
</footer></body></html>"""


def page(title, body, meta="", viewport='<meta name="viewport" content="width=device-width,initial-scale=1">', status=200):
    return Response(HEAD.format(title=title, meta=meta, viewport=viewport) + body + FOOT, status=status, mimetype="text/html")


@app.get("/")
def home():
    return page("Home", """<h1>Welkom bij Testbedrijf</h1>
<p>Lorem ipsum dolor sit amet, consectetur adipiscing elit. Wij helpen u verder verder met alles.</p>
<p>TODO: tekst nog aanpassen na feedback klant</p>
<img src="https://via.placeholder.com/600x400" alt="placeholder">
<img src="/img/foto.jpg">
<img src="/img/kapot.jpg" alt="team.jpg">
<a href="#offerte">Naar offerte</a>
<p>Bel ons: 06-12345678 of 010-7654321</p>
<form name="contact"><input type="text" name="naam" placeholder="Naam"><input type="text" name="email"><button>Submit</button></form>
<div class="w-form-done">Thank you! Your submission has been received!</div>
<iframe src="https://www.youtube.com/embed/"></iframe>
""", meta='<meta name="description" content="Description here">')


@app.get("/diensten")
def diensten():
    return page("Home", "<h1>Diensten</h1><p>Onze diensten zijn goed. " + "Tekst over diensten. " * 20 + "</p><a href='/diensten/detail'>detail</a>",
                meta='<meta name="description" content="Onze diensten voor de industrie, van A tot Z. Lees meer over wat wij voor u kunnen betekenen."><meta property="og:title" content="Diensten"><meta property="og:image" content="http://127.0.0.1:8765/img/og.jpg">')


@app.get("/diensten/detail")
def detail():
    return page("Diensten – Testbedrijf", "<h1>Detail</h1>" + "<p>Inhoud van de detailpagina. </p>" * 10,
                meta='<meta name="description" content="Onze diensten voor de industrie, van A tot Z. Lees meer over wat wij voor u kunnen betekenen."><meta name="robots" content="noindex">')


@app.get("/contact")
def contact():
    return page("Contact – Testbedrijf", """<h1>Contact</h1><p>Neem contact op met John Doe via het formulier.</p>
<form action="/verzend" method="post"><label for="n">Naam</label><input id="n" name="naam" required>
<label for="e">E-mail</label><input id="e" type="email" name="email" required><input type="file" name="bijlage">
<input type="hidden" name="website"><textarea aria-label="Bericht" name="bericht"></textarea><button type="submit">Verstuur</button></form>
<iframe src="https://www.google.com/maps/embed?pb=!1m18"></iframe>""",
                meta='<meta name="description" content="Neem contact op met Testbedrijf. Wij staan voor u klaar met advies op maat voor uw project."><meta property="og:title" content="Contact"><meta property="og:description" content="Contact"><meta property="og:image" content="/img/og.jpg">')


@app.get("/over-ons")
def over():
    return page("Over ons – Testbedrijf", "<h2>Over ons</h2><p>Kort.</p>",
                meta='<meta name="description" content="Alles over Testbedrijf: ons team, onze geschiedenis en onze manier van werken in de techniek.">')


@app.get("/test-pagina")
def test():
    return page("Test pagina", "<h1>Test</h1>" + "<p>Dit is een testpagina met wat inhoud erop. </p>" * 8)


@app.get("/blog/artikel-1")
def blog():
    return page("Artikel 1 – Testbedrijf", "<h1>Artikel</h1>" + "<p>Inhoud van het artikel over techniek en pompen. </p>" * 10,
                meta='<meta name="description" content="Een artikel over techniek, pompen en instrumentatie voor de procesindustrie van vandaag.">')


@app.get("/privacy")
def privacy():
    return page("Privacyverklaring – Testbedrijf", "<h1>Privacy</h1>" + "<p>Wij gaan zorgvuldig om met uw gegevens. </p>" * 10,
                meta='<meta name="description" content="Privacyverklaring van Testbedrijf B.V. Lees hoe wij omgaan met uw persoonsgegevens.">')


@app.get("/redirect-a")
def ra():
    return redirect("/redirect-b", 301)


@app.get("/redirect-b")
def rb():
    return redirect("/diensten", 302)


@app.get("/img/logo.png")
@app.get("/img/foto.jpg")
@app.get("/img/og.jpg")
@app.get("/favicon.png")
def img():
    return Response(b"\x89PNG" + b"\0" * (600 * 1024), mimetype="image/png")


@app.get("/downloads/brochure_concept_v2.pdf")
def pdf():
    return Response("<html>login</html>", mimetype="text/html")


@app.get("/robots.txt")
def robots():
    return Response("User-agent: *\nDisallow: /\nSitemap: http://127.0.0.1:8765/sitemap.xml\n", mimetype="text/plain")


@app.get("/sitemap.xml")
def sitemap():
    urls = ["http://127.0.0.1:8765/", "http://127.0.0.1:8765/diensten", "http://127.0.0.1:8765/contact",
            "http://127.0.0.1:8765/verwijderd", "https://testbedrijf.webflow.io/over-ons", "http://127.0.0.1:8765/redirect-a"]
    xml = '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(f"<url><loc>{u}</loc></url>" for u in urls) + "</urlset>"
    return Response(xml, mimetype="application/xml")


@app.errorhandler(404)
def nf(e):
    return Response("<html><body>Error</body></html>", status=404, mimetype="text/html")


if __name__ == "__main__":
    app.run(port=8765, debug=False)
