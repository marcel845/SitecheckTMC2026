# SiteCheck – Opleveringscheck voor nieuwe websites

Controleert een (nieuwe) website automatisch op de punten uit de TMC Media
*Checklist nieuwe website* en rapporteert de bevindingen **per URL**.

- Crawlt de site (via links én sitemap.xml), controleert alle interne/externe links,
  afbeeldingen en downloads.
- ~50 automatische controles, gekoppeld aan de 75 checklistpunten.
- Rapport als **HTML** (filterbaar, afvinkbaar), **CSV** (Excel) en **JSON**.
- Punten die niet automatisch te toetsen zijn (bevestigingsmails, back-ups, contrast…)
  staan als handmatige checklist in het rapport.

## Installatie (eenmalig)

Vereist Python 3.10 of hoger.

```bash
cd sitecheck
pip install -r requirements.txt
```

Optioneel, voor websites die hun inhoud volledig met JavaScript opbouwen (React/Vue/Nuxt
zonder server-rendering):

```bash
pip install playwright
playwright install chromium
```

## Gebruik

### Commandline

```bash
python -m sitecheck https://www.klant.nl
```

Het rapport komt in `rapporten/sitecheck_<domein>_<datum>.html` (+ `.csv`, `.json`).
Voeg `--open` toe om het direct in de browser te openen.

Handige opties:

| Optie | Betekenis |
|---|---|
| `--max-pages 500` | Maximaal aantal pagina's (standaard 200) |
| `--no-external` | Externe links niet controleren (sneller) |
| `--phone 010-1234567` | Verwacht telefoonnummer; afwijkende nummers worden gemeld |
| `--email info@klant.nl` | Verwacht e-mailadres |
| `--company "Klant B.V."` | Verwachte bedrijfsnaam |
| `--address "Hoofdstraat 1"` | Verwacht adres (letterlijke tekst) |
| `--old-urls oud.txt` | Tekstbestand met oude URL's (één per regel): test of redirects goed staan |
| `--extra-host cdn.klant.nl` | Extra domein dat als 'intern' telt |
| `--render` | Pagina's renderen met Playwright (JS-sites) |
| `--delay 0.5` | Pauze tussen pagina's (standaard 0,2 s) |

Voorbeeld volledige check vóór oplevering:

```bash
python -m sitecheck https://www.klant.nl --phone "0182-123456" --email info@klant.nl --company "Klant B.V." --old-urls oude-urls.txt --open
```

De exit-code is `1` als er fouten zijn gevonden — bruikbaar in een CI/deploy-pipeline.

### Web-interface (voor collega's)

```bash
python -m sitecheck.web
```

Open <http://localhost:5050>, vul de URL in, volg de voortgang en open het rapport.
Eerdere rapporten blijven in de lijst staan. Met `--host 0.0.0.0` is de interface ook
voor anderen op het netwerk bereikbaar.

## Online zetten (vaste link)

### Render (gratis, aanbevolen)

1. Zet deze map in een GitHub-repository (bv. `tmcmedia/sitecheck`).
2. Open `https://render.com/deploy?repo=https://github.com/<account>/sitecheck`
   (of: Render dashboard → *New* → *Blueprint* → kies de repo). `render.yaml` regelt de rest.
3. Vul bij `SITECHECK_PASSWORD` een wachtwoord in — de web-interface vraagt daar om
   (gebruikersnaam mag leeg of willekeurig zijn).
4. Na ~3 minuten staat de app op `https://sitecheck-xxxx.onrender.com`.

Let op bij het gratis plan: de instance gaat na 15 min inactiviteit slapen (eerste
request duurt dan ~30 s) en rapporten verdwijnen bij een herstart — download ze dus.
Het *Starter*-plan (~$7/mnd) lost beide op; voeg dan in `render.yaml` een disk toe op `/data`.

### Eigen server (Docker)

```bash
docker compose up -d        # http://server:5050, wachtwoord in docker-compose.yml
```

Zet er een reverse proxy met https voor (Caddy/nginx/Traefik) en een subdomein als
`check.tmcmedia.nl`.

## Wat wordt gecontroleerd?

| Categorie | Automatisch |
|---|---|
| 1. Teksten | Lorem ipsum & andere placeholder-tekst, voorbeeldnamen (John Doe, example.com…), zichtbare TODO's/bouwersnotities, placeholder-/stockafbeeldingen, dubbele woorden, tekencodering, verouderd copyright-jaar, onvertaalde standaardteksten op NL-pagina's, ontbrekend `lang`-attribuut |
| 2. Links | Kapotte interne/externe links, lege knoppen (`href="#"`), links naar testomgeving (webflow.io, staging., localhost…), http-links op https-site, `tel:`/`mailto:` geldigheid, ankerlinks naar niet-bestaande id's, downloads (status, HTML i.p.v. bestand, 'concept'/'v2' in bestandsnaam), logo → homepage, generieke linkteksten, aanwezigheid menu/mobiele menuknop |
| 3. Pagina's | 404/5xx, redirectketens & -lussen, redirects naar ander domein, 404-pagina (soft-404, melding, vervolgstap), test-/template-/concept-URL's, (bijna) lege pagina's, ontbrekende H1, identieke inhoud op meerdere pagina's, oude URL's (optioneel) |
| 4. Formulieren | Formulieren gevonden (ter handmatige test), labels bij velden, `required`, e-mailveldtype, upload-velden, spambeveiliging herkend, verzendknop, action via http of naar testomgeving, bedankpagina bereikbaar |
| 5. Vormgeving | Viewport-meta (mobiel), zoomblokkade, favicon + apple-touch-icon, kapotte afbeeldingen/video's |
| 6. Dynamisch | Zoekformulier, YouTube/Vimeo/Maps/sliders/tabs herkend (ter handmatige test), lege embeds |
| 7. SEO | Titel (ontbreekt/kort/lang/standaard/dubbel), meta description (idem), noindex, robots.txt `Disallow: /`, sitemap (bestaat, juiste domein, geen 404/redirect/noindex-URL's, ontbrekende pagina's), canonical, alt-teksten, Open Graph (titel/omschrijving/afbeelding bereikbaar) |
| 8. Privacy/veiligheid | HTTPS, http→https redirect, www/non-www, mixed content, privacy-/cookie-/voorwaardenlink, cookiebanner herkend bij tracking, focus-outline verborgen, knoppen zonder tekst, onbereikbare klik-elementen, skip-link |
| 9. Snelheid/meting | Serverreactietijd, HTML-grootte, totaal paginagewicht, zware afbeeldingen/video's, lazy loading, GA4/GTM/Matomo/Plausible/pixels gevonden, meerdere ID's, verouderde UA-code, pagina's zonder meetscript |

Bevindingen die op (vrijwel) alle pagina's identiek voorkomen (header/footer) worden
samengevoegd tot één sitebrede melding, zodat het rapport leesbaar blijft.

## Ernst-niveaus

- **Fout** – oplossen vóór oplevering.
- **Waarschuwing** – beoordelen; vaak terecht, soms bewuste keuze.
- **Info** – ter kennisgeving of handmatig te bevestigen.

## Aanpassen

- `sitecheck/checklist.py` – de checklistpunten en de koppeling met de checks.
- `sitecheck/checks.py` – alle controles en de herkenningspatronen (bovenaan het
  bestand: `PLACEHOLDER_RE`, `STAGING_RE`, `SAMPLE_CONTENT_RE`, enz.). Voeg hier
  bv. extra placeholder-termen of testdomeinen toe.
- `sitecheck/report.py` – opmaak van het rapport.

## Testen

`tests/testsite/app.py` is een lokale testsite met opzettelijk geplante fouten:

```bash
python tests/testsite/app.py            # start op http://127.0.0.1:8765
python -m sitecheck http://127.0.0.1:8765 --no-external
```

## Beperkingen

- Zonder `--render` wordt de HTML gelezen zoals de server die levert; inhoud die pas na
  JavaScript verschijnt wordt dan niet gezien (Webflow, WordPress, Shopify e.d. zijn
  prima zonder render).
- Visuele zaken (vervormde afbeeldingen, contrast, overlappende elementen, browsers)
  en e-mailbevestigingen blijven handmatig werk — die staan in het rapport onder
  *Handmatige controles*.
- Externe sites blokkeren soms geautomatiseerde checks (LinkedIn geeft 999, sommige
  sites 403); die worden als *info* gemeld, niet als fout.
