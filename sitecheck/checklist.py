"""
Checklist nieuwe website — bron van waarheid voor het rapport.

Elk controlepunt heeft:
  id        korte code (bv. "1.1")
  text      de tekst uit de checklist
  mode      "auto"   = volledig automatisch gecontroleerd
            "assist" = automatisch voorbereid / gesignaleerd, maar handmatige bevestiging nodig
            "manual" = alleen handmatig te controleren
  checks    lijst met check-codes uit checks.py die dit punt afdekken
"""

CATEGORIES = [
    {
        "id": 1,
        "title": "Teksten en voorbeeldcontent",
        "items": [
            {"id": "1.1", "mode": "auto",   "checks": ["placeholder_text"],
             "text": "Nergens staat nog 'Lorem ipsum', 'Tekst volgt', 'Titel hier' of andere tijdelijke tekst."},
            {"id": "1.2", "mode": "assist", "checks": ["sample_content"],
             "text": "Voorbeeldcontent is vervangen, zoals fictieve klantnamen, reviews, projecten, producten en blogartikelen."},
            {"id": "1.3", "mode": "auto",   "checks": ["placeholder_images"],
             "text": "Tijdelijke afbeeldingen, stockfoto's met watermerken en testlogo's zijn verwijderd."},
            {"id": "1.4", "mode": "auto",   "checks": ["internal_notes"],
             "text": "Er staan geen interne opmerkingen of instructies voor de bouwer in beeld."},
            {"id": "1.5", "mode": "assist", "checks": ["text_quality"],
             "text": "Teksten bevatten geen spel-, taal- of opmaakfouten."},
            {"id": "1.6", "mode": "assist", "checks": ["contact_consistency"],
             "text": "Bedrijfsnaam, contactgegevens, openingstijden en adresgegevens kloppen."},
            {"id": "1.7", "mode": "assist", "checks": ["outdated_dates"],
             "text": "Prijzen, aanbiedingen en genoemde datums zijn actueel."},
            {"id": "1.8", "mode": "assist", "checks": ["language"],
             "text": "Alle taalversies zijn volledig vertaald, inclusief knoppen en foutmeldingen."},
        ],
    },
    {
        "id": 2,
        "title": "Knoppen, links en navigatie",
        "items": [
            {"id": "2.1", "mode": "auto",   "checks": ["broken_links", "empty_links"],
             "text": "Alle actieknoppen werken en leiden naar de juiste bestemming."},
            {"id": "2.2", "mode": "assist", "checks": ["generic_link_text"],
             "text": "Knopteksten passen bij wat er na het klikken gebeurt."},
            {"id": "2.3", "mode": "assist", "checks": ["nav_present"],
             "text": "Het hoofdmenu, submenu en mobiele menu werken goed."},
            {"id": "2.4", "mode": "auto",   "checks": ["logo_home_link"],
             "text": "Het logo verwijst naar de homepage."},
            {"id": "2.5", "mode": "auto",   "checks": ["broken_links"],
             "text": "Links in de footer werken."},
            {"id": "2.6", "mode": "auto",   "checks": ["staging_links"],
             "text": "Interne links verwijzen naar het definitieve domein, zonder verwijzingen naar de testomgeving."},
            {"id": "2.7", "mode": "auto",   "checks": ["broken_links"],
             "text": "Externe links verwijzen naar de juiste websites."},
            {"id": "2.8", "mode": "auto",   "checks": ["tel_mailto"],
             "text": "Telefoonnummers en e-mailadressen zijn aanklikbaar en correct ingesteld."},
            {"id": "2.9", "mode": "auto",   "checks": ["downloads"],
             "text": "Downloads openen het juiste, definitieve bestand."},
            {"id": "2.10", "mode": "auto",  "checks": ["anchor_links"],
             "text": "Ankerlinks springen naar het juiste onderdeel van de pagina."},
        ],
    },
    {
        "id": 3,
        "title": "Pagina's en foutmeldingen",
        "items": [
            {"id": "3.1", "mode": "auto",   "checks": ["page_status"],
             "text": "Alle gepubliceerde pagina's openen zonder 404- of serverfout."},
            {"id": "3.2", "mode": "assist", "checks": ["old_urls"],
             "text": "Oude URL's verwijzen waar nodig door naar de juiste nieuwe pagina."},
            {"id": "3.3", "mode": "auto",   "checks": ["redirects"],
             "text": "Er zijn geen onbedoelde doorverwijzingen of redirectlussen."},
            {"id": "3.4", "mode": "auto",   "checks": ["error_page"],
             "text": "De 404-pagina bevat een duidelijke melding en een bruikbare vervolgstap."},
            {"id": "3.5", "mode": "auto",   "checks": ["test_pages"],
             "text": "Testpagina's en ongebruikte ontwerppagina's zijn verwijderd of afgeschermd."},
            {"id": "3.6", "mode": "auto",   "checks": ["empty_pages"],
             "text": "Er zijn geen lege pagina's, categorieën of contentblokken."},
            {"id": "3.7", "mode": "auto",   "checks": ["page_status"],
             "text": "Detailpagina's van bijvoorbeeld producten, diensten, vacatures en nieuwsberichten werken."},
        ],
    },
    {
        "id": 4,
        "title": "Formulieren en bevestigingen",
        "items": [
            {"id": "4.1", "mode": "assist", "checks": ["forms_found"],
             "text": "Alle formulieren zijn daadwerkelijk getest met een inzending."},
            {"id": "4.2", "mode": "assist", "checks": ["form_required"],
             "text": "Verplichte velden en controles op invoer werken."},
            {"id": "4.3", "mode": "manual", "checks": [],
             "text": "Foutmeldingen zijn duidelijk en staan bij het juiste veld."},
            {"id": "4.4", "mode": "manual", "checks": [],
             "text": "Na verzending verschijnt de juiste bevestiging of bedankpagina."},
            {"id": "4.5", "mode": "manual", "checks": [],
             "text": "Inzendingen komen bij de juiste personen en systemen binnen."},
            {"id": "4.6", "mode": "manual", "checks": [],
             "text": "De afzender ontvangt de juiste bevestigingsmail, als die is ingesteld."},
            {"id": "4.7", "mode": "manual", "checks": [],
             "text": "Bevestigingsmails bevatten de juiste huisstijl, links en contactgegevens."},
            {"id": "4.8", "mode": "assist", "checks": ["form_upload"],
             "text": "Bijlagen uploaden werkt, indien van toepassing."},
            {"id": "4.9", "mode": "assist", "checks": ["form_spam"],
             "text": "Spambeveiliging werkt zonder normale inzendingen te blokkeren."},
        ],
    },
    {
        "id": 5,
        "title": "Vormgeving en mobiel gebruik",
        "items": [
            {"id": "5.1", "mode": "auto",   "checks": ["viewport"],
             "text": "De website werkt op mobiel, tablet en desktop."},
            {"id": "5.2", "mode": "manual", "checks": [],
             "text": "Er vallen geen teksten, knoppen of afbeeldingen buiten het scherm."},
            {"id": "5.3", "mode": "manual", "checks": [],
             "text": "Teksten zijn goed leesbaar en knoppen zijn eenvoudig aan te tikken."},
            {"id": "5.4", "mode": "auto",   "checks": ["broken_images"],
             "text": "Afbeeldingen zijn scherp, goed uitgesneden en niet vervormd."},
            {"id": "5.5", "mode": "manual", "checks": [],
             "text": "Lettertypen, kleuren en witruimte zijn consequent toegepast."},
            {"id": "5.6", "mode": "manual", "checks": [],
             "text": "Pop-ups en cookiebanners blokkeren geen belangrijke functies."},
            {"id": "5.7", "mode": "manual", "checks": [],
             "text": "De website werkt in de belangrijkste browsers, zoals Chrome, Safari, Edge en Firefox."},
            {"id": "5.8", "mode": "auto",   "checks": ["favicon"],
             "text": "Het favicon, het kleine icoontje in het browsertabblad, is correct ingesteld."},
        ],
    },
    {
        "id": 6,
        "title": "Zoekfunctie en dynamische onderdelen",
        "items": [
            {"id": "6.1", "mode": "assist", "checks": ["search_found"],
             "text": "De zoekfunctie geeft relevante resultaten."},
            {"id": "6.2", "mode": "manual", "checks": [],
             "text": "Bij geen resultaten verschijnt een duidelijke melding met een vervolgmogelijkheid."},
            {"id": "6.3", "mode": "manual", "checks": [],
             "text": "Filters, sortering en paginering werken, ook in combinatie."},
            {"id": "6.4", "mode": "assist", "checks": ["embeds"],
             "text": "Sliders, video's, uitklapmenu's en tabbladen werken."},
            {"id": "6.5", "mode": "assist", "checks": ["embeds"],
             "text": "Kaarten, boekingsmodules en andere externe onderdelen laden goed."},
            {"id": "6.6", "mode": "manual", "checks": [],
             "text": "Nieuwe of aangepaste content verschijnt correct op overzichts- en detailpagina's."},
        ],
    },
    {
        "id": 7,
        "title": "Vindbaarheid en delen",
        "items": [
            {"id": "7.1", "mode": "auto",   "checks": ["title", "meta_description"],
             "text": "Belangrijke pagina's hebben een passende paginatitel en metaomschrijving."},
            {"id": "7.2", "mode": "auto",   "checks": ["default_seo", "duplicate_seo"],
             "text": "Er staan geen tijdelijke SEO-titels of standaardomschrijvingen meer."},
            {"id": "7.3", "mode": "auto",   "checks": ["noindex", "robots_txt"],
             "text": "De live website is niet onbedoeld geblokkeerd voor zoekmachines."},
            {"id": "7.4", "mode": "manual", "checks": [],
             "text": "Pagina's die privé moeten blijven, zijn passend afgeschermd."},
            {"id": "7.5", "mode": "auto",   "checks": ["sitemap"],
             "text": "De sitemap bevat de juiste live URL's."},
            {"id": "7.6", "mode": "auto",   "checks": ["img_alt"],
             "text": "Afbeeldingen hebben waar nodig een beschrijvende alternatieve tekst."},
            {"id": "7.7", "mode": "auto",   "checks": ["open_graph"],
             "text": "Bij delen via bijvoorbeeld LinkedIn of WhatsApp verschijnen de juiste titel, afbeelding en omschrijving."},
        ],
    },
    {
        "id": 8,
        "title": "Privacy, beveiliging en toegankelijkheid",
        "items": [
            {"id": "8.1", "mode": "auto",   "checks": ["https", "mixed_content", "http_redirect"],
             "text": "De website gebruikt HTTPS en toont geen beveiligingswaarschuwingen."},
            {"id": "8.2", "mode": "auto",   "checks": ["legal_pages"],
             "text": "Privacyverklaring, cookiebeleid en eventuele algemene voorwaarden zijn aanwezig en bereikbaar."},
            {"id": "8.3", "mode": "assist", "checks": ["cookie_banner"],
             "text": "De cookiebanner biedt werkende keuzes en een mogelijkheid om die later te wijzigen."},
            {"id": "8.4", "mode": "manual", "checks": [],
             "text": "Cookies en scripts gedragen zich volgens de gemaakte toestemmingskeuzes."},
            {"id": "8.5", "mode": "assist", "checks": ["keyboard_a11y"],
             "text": "Bezoekers kunnen met het toetsenbord navigeren en zien welk onderdeel geselecteerd is."},
            {"id": "8.6", "mode": "auto",   "checks": ["form_labels"],
             "text": "Formuliervelden hebben duidelijke labels."},
            {"id": "8.7", "mode": "manual", "checks": [],
             "text": "Teksten en knoppen hebben voldoende contrast."},
            {"id": "8.8", "mode": "manual", "checks": [],
             "text": "Beheeraccounts, toegangsrechten en back-ups zijn gecontroleerd."},
        ],
    },
    {
        "id": 9,
        "title": "Snelheid, metingen en koppelingen",
        "items": [
            {"id": "9.1", "mode": "auto",   "checks": ["page_speed"],
             "text": "Pagina's laden vlot, ook via een mobiele verbinding."},
            {"id": "9.2", "mode": "auto",   "checks": ["heavy_media"],
             "text": "Afbeeldingen en video's zijn niet onnodig zwaar."},
            {"id": "9.3", "mode": "assist", "checks": ["analytics"],
             "text": "Statistieken worden op het juiste domein geregistreerd."},
            {"id": "9.4", "mode": "manual", "checks": [],
             "text": "Belangrijke acties, zoals aanvragen en aankopen, worden correct gemeten."},
            {"id": "9.5", "mode": "manual", "checks": [],
             "text": "CRM-, nieuwsbrief-, agenda- en andere koppelingen verwerken gegevens goed."},
            {"id": "9.6", "mode": "manual", "checks": [],
             "text": "Er is iemand verantwoordelijk voor het volgen en oplossen van foutmeldingen na de lancering."},
        ],
    },
]


def all_items():
    for cat in CATEGORIES:
        for item in cat["items"]:
            yield cat, item


def items_for_check(check_code):
    """Geef alle checklistpunten terug die door een check-code worden afgedekt."""
    return [item for _, item in all_items() if check_code in item["checks"]]
