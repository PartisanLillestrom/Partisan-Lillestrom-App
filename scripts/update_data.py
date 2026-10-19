#!/usr/bin/env python3
"""
Henter ferske nyheter (fcstpauli.com + millernton.de) og neste kamp for
FC St. Pauli - HELT GRATIS, uten Anthropic API:

  - fcstpauli.com: artikkel-lenker hentes primaert via Bluesky sitt
    offentlige API (@fcstpauli.com), med direkte scraping og Jina Reader
    som fallback. og:title/og:image hentes fra hver artikkelside.
  - millernton.de: uendret - RSS-feed + og:image (som før).
  - Oversettelse tysk -> norsk: MyMemory sin gratis oversettelses-API
    (ingen nøkkel nødvendig, https://mymemory.translated.net/).
  - Neste kamp: hentes fra OpenLigaDB (api.openligadb.de), et gratis
    JSON-API for tysk fotball - ingen noekkel noedvendig, paalitelig
    strukturert data som erstatter upaalitelig scraping av fcstpauli.com.

Resultatet skrives til data.json i repo-roten. Hvis noe feiler underveis
lar vi eksisterende data.json stå urørt og avslutter med feilkode 1, slik
at GitHub Actions tydelig viser at kjørselen feilet - uten at nettsiden
noensinne viser ødelagt eller tom data.
"""

import email.utils
import json
import re
import sys
import urllib.parse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
# Alias fordi 'html' brukes som lokalt variabelnavn flere steder i filen
from html import unescape as html_unescape

# Kamptider i Rahmenspielplan er tysk lokaltid (CET/CEST). Norge deler
# tidssone med Tyskland, saa tidene kan vises direkte i appen.
try:
    from zoneinfo import ZoneInfo
    TZ_DE = ZoneInfo("Europe/Berlin")
except Exception:  # svaert usannsynlig paa GitHub Actions, men aldri krasj
    TZ_DE = timezone.utc

DATA_FILE = "data.json"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

# Fulle nettleser-headere - passerer bot-filtre oftere enn bare User-Agent
BROWSER_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    "Accept-Encoding": "identity",
    "Cache-Control": "no-cache",
}


def http_get_text(url: str, timeout: int = 30, max_bytes: int = 800_000) -> str:
    """Direkte henting av en side som tekst. Kaster exception ved feil."""
    req = urllib.request.Request(url, headers=BROWSER_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read(max_bytes).decode("utf-8", "replace")


def fetch_via_jina(url: str, timeout: int = 45) -> str:
    """Henter en side via Jina Reader-proxyen (r.jina.ai - gratis, ingen
    nokkel). Jinas servere gjor selve hentingen, sa dette omgar
    IP-blokkering av GitHub Actions fullstendig. Returnerer sidens innhold
    som markdown-tekst (lenker star som fulle URL-er)."""
    proxy_url = "https://r.jina.ai/" + url
    req = urllib.request.Request(proxy_url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read(900_000).decode("utf-8", "replace")

MONTHS_NO = {
    1: "januar", 2: "februar", 3: "mars", 4: "april", 5: "mai", 6: "juni",
    7: "juli", 8: "august", 9: "september", 10: "oktober", 11: "november", 12: "desember",
}


# ---------------------------------------------------------------------------
# Oversettelse (gratis, ingen nøkkel)
# ---------------------------------------------------------------------------

def detect_lang(text: str) -> str:
    """Enkel heuristikk: er tittelen tysk eller engelsk? Returnerer 'de'
    eller 'en'. Tyske spesialtegn og smaaord teller for tysk, engelske
    smaaord for engelsk. Ved tvil antar vi tysk (vanligst for begge kilder)."""
    t = " " + text.lower() + " "
    score = 0
    # Sikre tyske signaler
    if re.search(r'[äöüß]|„|“', text):
        score += 2
    DE_WORDS = ("der", "die", "das", "und", "mit", "für", "fuer", "im", "ein",
                "eine", "ist", "nicht", "beim", "gegen", "nach", "zum", "zur",
                "auf", "bei", "wir", "neue", "neuer", "spiel", "sieg")
    EN_WORDS = ("the", "and", "of", "for", "with", "at", "is", "on",
                "new", "match", "win", "against", "battle", "first", "our")
    for w in DE_WORDS:
        if f" {w} " in t or t.startswith(f" {w} "):
            score += 1
    for w in EN_WORDS:
        if f" {w} " in t:
            score -= 1
    # Engelske suffikser (svakt signal - avgjør bare naar tyske ord mangler)
    if re.search(r'\b\w+(?:tions?|ings?)\b', t):
        score -= 1
    return "de" if score >= 0 else "en"


def _mymemory(text: str, src: str) -> str:
    """Ett enkelt kall til MyMemory ({src}|no). Returnerer oversettelsen,
    eller tom streng hvis kallet feiler, kvoten er brukt opp, API-et svarer
    med feilstatus, eller 'oversettelsen' er identisk med originalen
    (dvs. ingen reell oversettelse skjedde)."""
    try:
        q = urllib.parse.quote(text[:490])
        url = f"https://api.mymemory.translated.net/get?q={q}&langpair={src}|no"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        # MyMemory legger feilmeldinger inni translatedText med status != 200
        if str(data.get("responseStatus")) != "200":
            print(f"  (oversettelse {src}|no ga status {data.get('responseStatus')}: {data.get('responseDetails','')[:60]})", file=sys.stderr)
            return ""
        translated = ((data.get("responseData") or {}).get("translatedText") or "").strip()
        if not translated or "MYMEMORY WARNING" in translated.upper():
            return ""
        # Identisk svar = ingen reell oversettelse
        if translated.strip().lower() == text.strip().lower():
            return ""
        return translated
    except Exception as e:
        print(f"  (advarsel: oversettelse ({src}|no) feilet for '{text[:40]}...': {e})", file=sys.stderr)
        return ""


def translate_to_no(text: str) -> str:
    """Oversetter en kort tittel (tysk ELLER engelsk) til norsk. Prover
    forst spraket som detekteres, deretter det andre som fallback - MT-
    motoren bak MyMemory takler ofte 'feil' kildesprak helt fint. Returnerer
    originalteksten uendret hvis begge forsok feiler."""
    if not text:
        return text
    src = detect_lang(text)
    for lang in (src, "en" if src == "de" else "de"):
        result = _mymemory(text, lang)
        if result:
            if lang != src:
                print(f"  (oversatt via fallback {lang}|no: '{text[:40]}')")
            return result
    return text


# ---------------------------------------------------------------------------
# MillernTon (uendret: RSS + og:image)
# ---------------------------------------------------------------------------

def fetch_millernton_rss(limit: int = 5) -> list:
    """Henter de nyeste innleggene direkte fra MillernTon sin RSS-feed."""
    try:
        req = urllib.request.Request(
            "https://millernton.de/feed/",
            headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml,application/xml,*/*"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            xml_data = resp.read()
        root = ET.fromstring(xml_data)
        items = []
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub = (item.findtext("pubDate") or "").strip()
            if not (title and link):
                continue
            date_no = ""
            if pub:
                try:
                    dt = email.utils.parsedate_to_datetime(pub)
                    date_no = f"{dt.day}. {MONTHS_NO[dt.month]}"
                except Exception:
                    pass
            items.append({"title_de": title, "url": link, "date": date_no})
            if len(items) >= limit:
                break
        print(f"RSS: hentet {len(items)} innlegg fra millernton.de/feed/")
        return items
    except Exception as e:
        print(f"(advarsel: RSS-henting fra millernton.de feilet: {e})", file=sys.stderr)
        return []


# ---------------------------------------------------------------------------
# Felles og:tag-henting (brukes av begge kilder)
# ---------------------------------------------------------------------------

def hent_artikkel_html(page_url: str) -> str:
    """Henter en artikkelside EN gang. Tidligere hentet fetch_og_title og
    fetch_og_image siden hver for seg - to kall per artikkel, ti per
    kjoering. Naa trekker vi alt vi trenger ut av samme HTML."""
    try:
        req = urllib.request.Request(page_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read(400_000).decode("utf-8", "replace")
    except Exception as e:
        print(f"  (advarsel: kunne ikke hente {page_url}: {e})", file=sys.stderr)
        return ""


def _og_fra_html(doc: str, tag: str) -> str:
    """Trekker ut en og:-meta-tag (f.eks. 'og:image') fra ferdig hentet HTML."""
    if not doc:
        return ""
    pattern_a = rf'property=["\']{re.escape(tag)}["\'][^>]*content=["\']([^"\']+)'
    pattern_b = rf'content=["\']([^"\']+)["\'][^>]*property=["\']{re.escape(tag)}'
    m = re.search(pattern_a, doc) or re.search(pattern_b, doc)
    return html_unescape(m.group(1)) if m else ""


def _tittel_tag(doc: str) -> str:
    """Trekker ut innholdet i <title> fra ferdig hentet HTML.

    fcstpauli.com korter og:title ned til ca. 50 tegn, mens <title> er hele
    overskriften med " | FC St. Pauli" bakpaa - og det suffikset fjerner
    rydd_tittel() allerede. Den fulle teksten er viktig fordi en avkuttet
    tittel gir feiloversettelser: "1. Frauen bezwingen" (de VANT) ble
    "Kvinnetap"."""
    if not doc:
        return ""
    m = re.search(r'<title[^>]*>(.*?)</title>', doc, re.S | re.I)
    if not m:
        return ""
    return html_unescape(re.sub(r'\s+', ' ', m.group(1)).strip())


def fetch_og_tag(page_url: str, tag: str) -> str:
    """Henter en og:-meta-tag fra en artikkelside (egen henting).
    Brukes av millernton-loypa, som bare trenger og:image."""
    return _og_fra_html(hent_artikkel_html(page_url), tag)


def fetch_og_image(page_url: str) -> str:
    return fetch_og_tag(page_url, "og:image")


def fetch_og_title(page_url: str) -> str:
    return fetch_og_tag(page_url, "og:title")


def velg_tittel(og_title: str, title_tag: str) -> str:
    """Velger den mest komplette overskriften av og:title og <title>.

    Begge ryddes foerst for klubbnavn og ellipse. Den som gir mest tekst
    vinner: er <title> bare "FC St. Pauli" eller "Startseite | FC St.
    Pauli", blir den kort etter rydding og og:title beholdes."""
    og = rydd_tittel(og_title)
    tt = rydd_tittel(title_tag)
    if not tt:
        return og
    if not og:
        return tt
    return tt if len(tt) > len(og) else og


# ---------------------------------------------------------------------------
# fcstpauli.com - robust scraping med fallback-URL
# ---------------------------------------------------------------------------

def _extract_news_links(text: str, limit: int) -> list:
    """Trekker ut /news/<slug>-lenker fra HTML eller markdown.
    Matcher bade relative og absolutte lenker, i href="..." og i ren tekst."""
    raw = re.findall(
        r'(?:https://www\.fcstpauli\.com)?(/news/[a-zA-Z0-9\-_/]+)',
        text
    )
    urls, seen = [], set()
    for link in raw:
        link = link.rstrip("/")
        if link in ("/news", ""):
            continue
        full = "https://www.fcstpauli.com" + link
        if full in seen:
            continue
        seen.add(full)
        urls.append(full)
        if len(urls) >= limit:
            break
    return urls


def fetch_fcstpauli_news_urls(limit: int = 5) -> list:
    """Henter de nyeste artikkel-lenkene fra fcstpauli.com.

    Flerlags-strategi slik at dette ALLTID fungerer fra GitHub Actions:
      1. Bluesky API (paalitelig, strukturert JSON, ingen blokkering)
      2. Direkte henting med fulle nettleser-headere
      3. Jina Reader-proxy (r.jina.ai)
    """

    # --- Lag 1: Bluesky API ---
    try:
        bsky_url = "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed?actor=fcstpauli.com&limit=100"
        req = urllib.request.Request(bsky_url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        urls, seen = [], set()

        def _legg_til(u):
            if u and "/news/" in u and "fcstpauli.com" in u:
                u = u.split("?")[0].rstrip("/")
                if u not in seen:
                    seen.add(u)
                    urls.append(u)

        def _resolve_short(u):
            """Foelg forkortede lenker (fcsp.in) for aa finne faktisk URL."""
            if not u:
                return u
            if "fcsp.in" in u or ("fcstpauli" not in u and len(u) < 40):
                try:
                    req2 = urllib.request.Request(u, method="HEAD", headers={"User-Agent": USER_AGENT})
                    req2.add_header("Accept", "*/*")
                    with urllib.request.urlopen(req2, timeout=10) as resp2:
                        return resp2.url
                except Exception:
                    try:
                        req2 = urllib.request.Request(u, headers={"User-Agent": USER_AGENT})
                        with urllib.request.urlopen(req2, timeout=10) as resp2:
                            return resp2.url
                    except Exception:
                        pass
            return u

        for item in data.get("feed", []):
            post = item.get("post", {})
            record = post.get("record", {})
            # 1. embed.external.uri (vanligste for lenkeposter)
            for embed_loc in [post.get("embed", {}), record.get("embed", {})]:
                external = (embed_loc.get("external") or {})
                _legg_til(_resolve_short(external.get("uri", "")))
                # Sjekk ogsaa record_with_media embedder
                media_embed = embed_loc.get("media", {})
                _legg_til(_resolve_short((media_embed.get("external") or {}).get("uri", "")))
                rec_embed = embed_loc.get("record", {})
                _legg_til(_resolve_short((rec_embed.get("external") or {}).get("uri", "")))
            # 2. facets (klikkbare lenker i teksten)
            for facet in record.get("facets", []):
                for feature in facet.get("features", []):
                    _legg_til(_resolve_short(feature.get("uri", "")))
            # 3. Ren tekst-soek (lenker uten facet-markering)
            tekst = record.get("text", "")
            for m in re.finditer(r'https?://[^\s)"\'<>]+', tekst):
                _legg_til(_resolve_short(m.group(0)))
            if len(urls) >= limit:
                break
        print(f"Bluesky API: fant {len(urls)} artikkel-lenker fra @fcstpauli.com")
        if urls:
            return urls[:limit]
    except Exception as e:
        print(f"  (Bluesky API feilet: {e})", file=sys.stderr)

    kandidat_sider = [
        "https://www.fcstpauli.com/news/",
        "https://www.fcstpauli.com/fussball/aktuelles",
    ]

    # --- Lag 2: direkte ---
    for page_url in kandidat_sider:
        try:
            html = http_get_text(page_url)
            urls = _extract_news_links(html, limit)
            print(f"Scraping (direkte): fant {len(urls)} artikkel-lenker pa {page_url}")
            if urls:
                return urls
        except Exception as e:
            print(f"  (direkte henting av {page_url} feilet: {e})", file=sys.stderr)

    # --- Lag 3: Jina Reader-proxy ---
    for page_url in kandidat_sider:
        try:
            md = fetch_via_jina(page_url)
            urls = _extract_news_links(md, limit)
            print(f"Scraping (via Jina-proxy): fant {len(urls)} artikkel-lenker pa {page_url}")
            if urls:
                return urls
        except Exception as e:
            print(f"  (Jina-henting av {page_url} feilet: {e})", file=sys.stderr)

    print("Scraping: fant 0 artikkel-lenker pa alle veier", file=sys.stderr)
    return []


def rydd_tittel(t: str) -> str:
    """Fjerner klubbnavn-prefiks/suffiks og avsluttende ellipse fra en raa
    og:title.

    fcstpauli.com sin CMS setter "FC St. Pauli | " foran hver og:title og
    korter den ned med ellipse. Prefikset spiser ~15 tegn av nyhetskortet
    paa noe medlemmene allerede vet. Ellipsen er verre enn kosmetisk:
    oversettelses-API-et faar et fragment der objektet mangler og gjetter
    feil - "1. Frauen bezwingen..." ble oversatt til "Kvinnene taper...",
    altsaa stikk motsatt av resultatet (de vant 5-1). Vi rydder derfor
    FOER teksten sendes til oversetting.

    Suffiks-regelen er ankret til slutten av strengen med vilje. Den gamle
    varianten brukte '.*$' og ville kappe en tittel som "1:1 in Hannover -
    FC St. Pauli jubelt" midt i setningen."""
    if not t:
        return t
    t = t.strip()
    # Klubbnavn som prefiks: "FC St. Pauli | Tittel"
    t = re.sub(r'^FC St\.?\s*Pauli\s*[|\u2013\u2014-]\s*', '', t)
    # Klubbnavn som suffiks: "Tittel | FC St. Pauli"
    t = re.sub(r'\s*[|\u2013\u2014-]\s*FC St\.?\s*Pauli\s*$', '', t)
    # Avsluttende ellipse (\u2026 eller ...)
    t = re.sub(r'\s*(?:\u2026|\.\.\.)\s*$', '', t)
    return t.strip()


def fetch_article_meta(url: str) -> tuple:
    """Henter (tittel, bilde-URL) for en artikkel. Prover direkte meta-tagger
    forst, deretter Jina-proxyen (som gir 'Title:'-linje + markdown-bilder).

    Artikkelsiden hentes EN gang, og baade og:title, <title> og og:image
    leses ut av samme HTML. Tittelen velges av velg_tittel(), som
    foretrekker <title> naar den er mer komplett enn den avkuttede
    og:title."""
    # Lag 1: direkte meta-tagger - én henting
    doc = hent_artikkel_html(url)
    title = velg_tittel(_og_fra_html(doc, "og:title"), _tittel_tag(doc))
    if title:
        return title, verifiser_artikkelbilde(url, _og_fra_html(doc, "og:image"))

    # Lag 2: via Jina
    try:
        md = fetch_via_jina(url)
        m_title = re.match(r'Title:\s*(.+)', md)
        title = rydd_tittel(m_title.group(1) if m_title else "")
        m_img = re.search(r'!\[[^\]]*\]\((https://[^)\s]+)\)', md)
        image = m_img.group(1) if m_img else ""
        if title:
            print(f"  (artikkel-metadata hentet via Jina for {url})")
        return title, verifiser_artikkelbilde(url, image)
    except Exception as e:
        print(f"  (Jina-metadata feilet for {url}: {e})", file=sys.stderr)
        return "", ""


def bilde_kan_hentes(url: str) -> bool:
    """Verifiserer via weserv (8-px testhenting) at bildet faktisk finnes.
    fcstpauli.com sitt CMS peker av og til paa bildevarianter som er slettet
    (og:image med utdatert versjonsstempel), og da vil vi heller finne et
    annet bilde enn aa publisere en dod lenke."""
    if not url or not url.startswith("http"):
        return False
    try:
        test = "https://images.weserv.nl/?url=" + urllib.parse.quote(url, safe="") + "&w=8"
        req = urllib.request.Request(test, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=20) as resp:
            ctype = (resp.headers.get("Content-Type") or "")
            return resp.status == 200 and ctype.startswith("image/")
    except Exception:
        return False


def _forste_innholdsbilde(tekst: str, unngaa: str = "") -> str:
    """Finner forste innholdsbilde i artikkel-HTML/markdown. Hopper over
    logoer, sponsorbilder, annonser - og 'unngaa'-URL-en (den dode
    og:image-adressen, som ogsaa ligger i <head>-metataggene og ellers
    ville blitt matchet forst)."""
    pattern = r'(https://(?:api\.fcstpauli\.com|millernton\.de)/[^\s"\'()<>]+\.(?:jpe?g|png|webp)[^\s"\'()<>]*)'
    for m in re.finditer(pattern, tekst):
        kandidat = m.group(1)
        if unngaa and kandidat == unngaa:
            continue
        if any(x in kandidat for x in ('/Logos/', '/Ads/', 'Sponsorenlogo', '/logo')):
            continue
        return kandidat
    return ""


def verifiser_artikkelbilde(page_url: str, og_bilde: str) -> str:
    """Returnerer og:image hvis det finnes, ellers forste innholdsbilde
    fra artikkelsiden. Beholder og:image som siste utvei (frontend har
    egen fallback), eller tom streng hvis ingenting fantes."""
    if bilde_kan_hentes(og_bilde):
        return og_bilde
    # og:image er dodt - hent artikkelsiden (direkte, saa Jina) og let
    # etter det forste ekte innholdsbildet
    tekst = ""
    try:
        req = urllib.request.Request(page_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as resp:
            tekst = resp.read(400_000).decode("utf-8", "replace")
    except Exception:
        try:
            tekst = fetch_via_jina(page_url)
        except Exception:
            pass
    if tekst:
        kandidat = _forste_innholdsbilde(tekst, unngaa=og_bilde)
        if kandidat and bilde_kan_hentes(kandidat):
            print(f"  (info: og:image utilgjengelig for {page_url} - bruker innholdsbilde i stedet)")
            return kandidat
    return og_bilde


# ---------------------------------------------------------------------------
# OpenLigaDB — paalitelig JSON-API for 2. Bundesliga-kamper
# Gratis, ingen noekkel, returnerer alle kamper for sesongen.
# Erstatter upaalitelig scraping av fcstpauli.com/rahmenspielplan.
# ---------------------------------------------------------------------------

STPAULI_TEAM_ID = 98  # FC St. Paulis team-ID i OpenLigaDB

# Stadion-oppslag for bortekamper (OpenLigaDB har location=null).
# Hjemmekamper er alltid Millerntor. Oppdater ved behov.
#
# NB: OpenLigaDB bruker ikke alltid lagets fulle navn - "Dynamo Dresden"
# der andre kilder skriver "SG Dynamo Dresden". Oppslaget skjer paa det
# navnet API-et faktisk returnerer, saa begge skrivemaatene ligger inne.
# Uten treff blir stadion tom, og kampkortet mister stedsangivelsen.
BORTE_STADION = {
    "Holstein Kiel":          "Holstein-Stadion, Kiel",
    "SpVgg Greuther Fürth":   "Sportpark Ronhof, Fürth",
    "Arminia Bielefeld":      "SchücoArena, Bielefeld",
    "DSC Arminia Bielefeld":  "SchücoArena, Bielefeld",
    "VfL Wolfsburg":          "Volkswagen Arena, Wolfsburg",
    "FC Energie Cottbus":     "Stadion der Freundschaft, Cottbus",
    "Energie Cottbus":        "Stadion der Freundschaft, Cottbus",
    "Karlsruher SC":          "BBBank Wildpark, Karlsruhe",
    "Hannover 96":            "Heinz von Heiden Arena, Hannover",
    "SV Darmstadt 98":        "Merck-Stadion am Böllenfalltor, Darmstadt",
    "1. FC Nürnberg":         "Max-Morlock-Stadion, Nürnberg",
    "1. FC Magdeburg":        "MDCC-Arena, Magdeburg",
    "SG Dynamo Dresden":      "Rudolf-Harbig-Stadion, Dresden",
    "Dynamo Dresden":         "Rudolf-Harbig-Stadion, Dresden",
    "1. FC Heidenheim 1846":  "Voith-Arena, Heidenheim",
    "VfL Osnabrück":          "Bremer Brücke, Osnabrück",
    "Hertha BSC":             "Olympiastadion, Berlin",
    "VfL Bochum":             "Vonovia Ruhrstadion, Bochum",
    "Eintracht Braunschweig": "Eintracht-Stadion, Braunschweig",
    "1. FC Kaiserslautern":   "Fritz-Walter-Stadion, Kaiserslautern",
}


def _openligadb_sesong() -> int:
    """Returnerer sesongaar for OpenLigaDB (2026 for 2026/27-sesongen).
    Sesongen starter i juli/august."""
    now = datetime.now(TZ_DE)
    return now.year if now.month >= 7 else now.year - 1


def fetch_next_match_fcstpauli() -> dict:
    """Henter neste kamp for FC St. Pauli fra OpenLigaDB (2. Bundesliga).
    Faller tilbake til forrige sesong hvis gjeldende sesong ikke har data
    (rundt sesongskiftet i juni/juli)."""
    for sesong in (_openligadb_sesong(), _openligadb_sesong() + 1):
        resultat = _next_match_openligadb(sesong)
        if resultat.get("motstander"):
            return resultat
    print("  (advarsel: fant ingen kommende St. Pauli-kamp i OpenLigaDB)", file=sys.stderr)
    return {}


_OLB_CACHE = {}


def _openligadb_kamper(sesong: int) -> list:
    """Henter alle 2. Bundesliga-kamper for en sesong fra OpenLigaDB.
    Resultatet caches per sesong, slik at kampplanen og neste kamp deler
    ett og samme API-kall i stedet for aa hente de samme dataene to ganger.
    Returnerer tom liste ved feil - kallerne har egne fallback-veier."""
    if sesong in _OLB_CACHE:
        return _OLB_CACHE[sesong]
    url = f"https://api.openligadb.de/getmatchdata/bl2/{sesong}"
    data = []
    try:
        req = urllib.request.Request(url, headers={
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  (OpenLigaDB-henting feilet for sesong {sesong}: {e})", file=sys.stderr)
        data = []
    if not isinstance(data, list):
        print(f"  (OpenLigaDB: uventet dataformat for sesong {sesong})", file=sys.stderr)
        data = []
    _OLB_CACHE[sesong] = data
    return data


def _er_stpauli_kamp(m: dict) -> bool:
    """Sant hvis FC St. Pauli er ett av lagene i kampen."""
    return STPAULI_TEAM_ID in (
        m.get("team1", {}).get("teamId"),
        m.get("team2", {}).get("teamId"),
    )


def _next_match_openligadb(sesong: int) -> dict:
    """Henter alle 2. Bundesliga-kamper for en sesong fra OpenLigaDB og
    returnerer neste uspilte FC St. Pauli-kamp."""
    data = _openligadb_kamper(sesong)
    if not data:
        return {}

    # Filtrer St. Pauli-kamper som ikke er spilt ennaa
    kommende = []
    for m in data:
        if not _er_stpauli_kamp(m):
            continue
        if m.get("matchIsFinished", False):
            continue
        kommende.append(m)

    if not kommende:
        print(f"  (OpenLigaDB sesong {sesong}: ingen kommende St. Pauli-kamper)")
        return {}

    # Sorter etter kamptidspunkt
    kommende.sort(key=lambda x: x.get("matchDateTime", ""))
    neste = kommende[0]

    hjemme = neste["team1"]["teamId"] == STPAULI_TEAM_ID
    motstander_obj = neste["team2"] if hjemme else neste["team1"]
    motstander = motstander_obj.get("teamName", "")

    # matchDateTime er tysk lokaltid (CET/CEST), f.eks. "2026-10-11T11:30:00"
    dt_str = neste.get("matchDateTime", "")
    dato = ""
    tid = ""
    kickoff_iso = ""
    if dt_str:
        try:
            dt = datetime.strptime(dt_str[:19], "%Y-%m-%dT%H:%M:%S")
            dt = dt.replace(tzinfo=TZ_DE)
            dato = dt.strftime("%Y-%m-%d")
            tid = dt.strftime("%H:%M")
            kickoff_iso = dt.isoformat()
        except ValueError:
            dato = dt_str[:10]

    # Stadion
    if hjemme:
        stadion = "Millerntor-Stadion, Hamburg"
    else:
        stadion = BORTE_STADION.get(motstander, "")

    # Turneringsnavn — OpenLigaDB gir "2. Fußball-Bundesliga 2026/2027"
    turnering = neste.get("leagueName", "2. Bundesliga")
    # Forkort til "2. Bundesliga" for visning i appen
    if "bundesliga" in turnering.lower():
        turnering = "2. Bundesliga"

    spilldag = neste.get("group", {}).get("groupOrderID", "")

    print(f"OpenLigaDB: neste kamp = {motstander} ({dato} {tid}), spilldag {spilldag}")
    return {
        "matchId": neste.get("matchID") or neste.get("matchId"),
        "motstander": motstander,
        "dato": dato,
        "tid": tid,
        "kickoff_iso": kickoff_iso,
        "turnering": turnering,
        "hjemme": hjemme,
        "stadion": stadion,
    }


def _kamp_til_appform(m: dict) -> dict:
    """Gjoer en OpenLigaDB-kamp om til NOEYAKTIG samme form som appens
    KJENTE_KAMPER-liste bruker, slik at index.html kan bruke kampplanen
    direkte uten aa oversette feltnavn."""
    hjemme = m.get("team1", {}).get("teamId") == STPAULI_TEAM_ID
    motstander = (m.get("team2") if hjemme else m.get("team1")) or {}
    motstander = motstander.get("teamName", "")

    # matchDateTime er tysk lokaltid (CET/CEST), f.eks. "2026-10-23T18:30:00"
    dt_str = m.get("matchDateTime", "")
    dato, tid = "", ""
    if dt_str:
        try:
            dt = datetime.strptime(dt_str[:19], "%Y-%m-%dT%H:%M:%S")
            dato = dt.strftime("%Y-%m-%d")
            tid = dt.strftime("%H:%M")
        except ValueError:
            dato = dt_str[:10]

    stadion = "Millerntor-Stadion, Hamburg" if hjemme else BORTE_STADION.get(motstander, "")

    return {
        # matchId foelger kampen gjennom omberamminger. DFL fastsetter
        # helgen for hele sesongen, men dag og klokkeslett kommer i bolker
        # gjennom sesongen - saa datoen er IKKE en stabil noekkel. Appen
        # bruker matchId som tippe-noekkel slik at et tipp ikke mister
        # koblingen til resultatet hvis kampen flyttes fra loerdag til
        # soendag. Feltnavnet varierer i OpenLigaDB-dokumentasjonen, saa
        # vi leser begge skrivemaatene.
        "matchId": m.get("matchID") or m.get("matchId"),
        "motstander": motstander,
        "dato": dato,
        "tid": tid,
        "turnering": "2. Bundesliga",
        "hjemme": hjemme,
        "stadion": stadion,
    }


def fetch_kampplan_fcstpauli() -> list:
    """Henter HELE 2. Bundesliga-kampplanen for FC St. Pauli - spilte og
    uspilte kamper - sortert paa dato.

    Appen (index.html) brukte tidligere en hardkodet KJENTE_KAMPER-liste som
    kilde for tippingen. Avsparkstider fastsettes av DFL i puljer bare noen
    uker i forveien, saa en haandvedlikeholdt liste drifter uunngaaelig fra
    virkeligheten - og da stengte tippefristen paa feil klokkeslett. Ved aa
    levere kampplanen her blir den oppdatert hver gang denne jobben kjoerer.

    Returnerer tom liste ved feil; appen faller da tilbake paa sin egen
    innebygde liste, og main() beholder forrige kampplan fra data.json."""
    kamper = []
    for sesong in (_openligadb_sesong(), _openligadb_sesong() + 1):
        for m in _openligadb_kamper(sesong):
            if not _er_stpauli_kamp(m):
                continue
            k = _kamp_til_appform(m)
            if k["dato"] and k["motstander"]:
                kamper.append(k)
        if kamper:
            break

    # Sorter kronologisk - appen forutsetter denne rekkefoelgen naar den
    # leter bakover etter sist spilte kamp.
    kamper.sort(key=lambda k: (k["dato"], k["tid"]))

    # Samme dato skal bare forekomme en gang (vern mot duplikater i API-et)
    unike, sett = [], set()
    for k in kamper:
        if k["dato"] in sett:
            continue
        sett.add(k["dato"])
        unike.append(k)

    if unike:
        print(f"OpenLigaDB: kampplan med {len(unike)} 2. Bundesliga-kamper "
              f"({unike[0]['dato']} - {unike[-1]['dato']})")
    else:
        print("  (advarsel: fant ingen 2. Bundesliga-kampplan i OpenLigaDB)", file=sys.stderr)
    return unike


# ---------------------------------------------------------------------------
# Bilde-URL via weserv-proxy (ingen nedlasting, ingen base64)
# ---------------------------------------------------------------------------

def weserv_image_url(url: str) -> str:
    """Returnerer en images.weserv.nl-URL som peker paa originalbildet.
    Weserv henter, cacher og krymper bildet paa sine servere (400 px bredde,
    webp) - det omgaar hotlink-blokkering OG holder data.json paa noen faa KB
    i stedet for flere MB med innbakt base64. Nettleseren laster bildet
    direkte fra weserv sitt CDN. Tom streng hvis URL-en er ubrukelig."""
    if not url or not url.startswith("http"):
        return ""
    if url.startswith("https://images.weserv.nl/"):
        return url  # allerede pakket inn (gjenbrukt fra forrige data.json)
    return (
        "https://images.weserv.nl/?url="
        + urllib.parse.quote(url, safe="")
        + "&w=400&output=webp&q=70"
    )


# ---------------------------------------------------------------------------
# Kamplogg og medlemsregister (Excel-filer i repo-et)
# ---------------------------------------------------------------------------

KAMPLOGG_FILE = "Kamplogg FCSP.xlsx"
ANTALL_BETALENDE_MEDLEMMER = 32  # Oppdateres manuelt etter årsmøtet


def les_kamplogg() -> list:
    """Leser kamploggen fra Excel-filen. Returnerer en liste med kamper
    sortert fra nyest til eldst, klar for JSON-serialisering."""
    try:
        import openpyxl
    except ImportError:
        print("  (advarsel: openpyxl ikke installert - kan ikke lese kamplogg)", file=sys.stderr)
        return []
    try:
        wb = openpyxl.load_workbook(KAMPLOGG_FILE, data_only=True, read_only=True)
        ws = wb.active
        kamper = []
        for row in ws.iter_rows(min_row=3, max_row=ws.max_row, values_only=True):
            nr, dato, hjemme, borte, resultat, utfall = row[0], row[1], row[2], row[3], row[4], row[5]
            if nr is None or dato is None:
                continue
            if not isinstance(dato, datetime):
                continue
            # Bygg kampstreng: "Hjemmelag - Bortelag"
            kamp_str = f"{hjemme} - {borte}" if hjemme and borte else ""
            kamper.append({
                "nr": int(nr) if isinstance(nr, (int, float)) else nr,
                "dato": dato.strftime("%Y-%m-%d"),
                "dato_no": f"{dato.day}. {MONTHS_NO[dato.month]} {dato.year}",
                "kamp": kamp_str,
                "resultat": str(resultat or ""),
                "utfall": str(utfall or "").strip(),
            })
        wb.close()
        # Sorter nyest forst
        kamper.sort(key=lambda k: k["dato"], reverse=True)
        print(f"Kamplogg: leste {len(kamper)} kamper fra {KAMPLOGG_FILE}")
        return kamper
    except FileNotFoundError:
        print(f"  (info: {KAMPLOGG_FILE} ikke funnet - hopper over kamplogg)", file=sys.stderr)
        return []
    except Exception as e:
        print(f"  (advarsel: kunne ikke lese kamplogg: {e})", file=sys.stderr)
        return []


def les_medlemstall() -> dict:
    """Returnerer antall betalende medlemmer. Oppdater konstanten
    ANTALL_BETALENDE_MEDLEMMER øverst i denne seksjonen etter årsmøtet."""
    return {"betalende": ANTALL_BETALENDE_MEDLEMMER}


def les_gammel_data() -> dict:
    """Leser eksisterende data.json. Returnerer tom dict hvis filen mangler
    eller er korrupt - da finnes det rett og slett ingen gammel data aa
    falle tilbake paa."""
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def validate(payload: dict) -> None:
    """Feiler KUN hvis begge nyhetskildene er tomme (etter fallback til
    forrige data.json). En enkelt kilde som feiler skal aldri blokkere
    oppdateringer fra den andre."""
    if not payload.get("fcstpauli_news") and not payload.get("millernton_news"):
        raise ValueError("Begge nyhetskildene er tomme - noe er alvorlig galt")
    for item in payload["fcstpauli_news"]:
        for field in ("title_no", "title_de", "url"):
            if not item.get(field):
                raise ValueError(f"fcstpauli_news-element mangler felt '{field}': {item}")
    for item in payload["millernton_news"]:
        for field in ("title_no", "title_de", "url"):
            if not item.get(field):
                raise ValueError(f"millernton_news-element mangler felt '{field}': {item}")


# ---------------------------------------------------------------------------
# Hovedprogram
# ---------------------------------------------------------------------------

SW_FILE = "sw.js"


def oppdater_sw_versjon():
    """Oppdaterer CACHE_VERSION i sw.js til dagens dato, slik at nettlesere
    oppdager endringer og henter nye filer. Gjør ingenting hvis datoen
    allerede er dagens."""
    idag = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        with open(SW_FILE, "r", encoding="utf-8") as f:
            innhold = f.read()
        ny = re.sub(
            r"const CACHE_VERSION = '[^']+';",
            f"const CACHE_VERSION = '{idag}';",
            innhold,
        )
        if ny != innhold:
            with open(SW_FILE, "w", encoding="utf-8") as f:
                f.write(ny)
            print(f"  - sw.js CACHE_VERSION oppdatert til {idag}")
        else:
            print(f"  - sw.js CACHE_VERSION allerede {idag}")
    except Exception as e:
        print(f"  (advarsel: kunne ikke oppdatere sw.js: {e})", file=sys.stderr)


def main() -> int:
    # --- MillernTon ---
    rss_items = fetch_millernton_rss()
    for it in rss_items:
        it["image"] = fetch_og_image(it["url"])
        it["title_no"] = translate_to_no(it["title_de"])

    # --- fcstpauli.com ---
    fcstpauli_items = []
    for url in fetch_fcstpauli_news_urls(limit=5):
        title_de, image_url = fetch_article_meta(url)
        if not title_de:
            continue
        fcstpauli_items.append({
            "title_no": translate_to_no(title_de),
            "title_de": title_de,
            "url": url,
            "image": image_url,
        })

    # --- Neste kamp og hele kampplanen (deler ett OpenLigaDB-kall) ---
    next_match = fetch_next_match_fcstpauli()
    kampplan = fetch_kampplan_fcstpauli()

    # --- Kamplogg og medlemstall (fra Excel-filer i repo-et) ---
    kamplogg = les_kamplogg()
    medlemstall = les_medlemstall()

    payload = {
        "fcstpauli_news": fcstpauli_items,
        "millernton_news": [
            {
                "title_no": it["title_no"],
                "title_de": it["title_de"],
                "url": it["url"],
                "date": it.get("date", ""),
                "image": it.get("image", ""),
            }
            for it in rss_items
        ],
        "next_match": next_match,
        "kampplan": kampplan,
        "kamplogg": kamplogg,
        "medlemstall": medlemstall,
    }

    # Per-kilde fallback: hvis én kilde feilet i natt, gjenbruk forrige
    # liste for AKKURAT den kilden - den andre oppdateres som normalt.
    gammel = les_gammel_data()
    if not payload["fcstpauli_news"] and gammel.get("fcstpauli_news"):
        payload["fcstpauli_news"] = gammel["fcstpauli_news"]
        print("  (info: fcstpauli-scraping ga ingenting - beholder forrige nyhetsliste)")
    if not payload["millernton_news"] and gammel.get("millernton_news"):
        payload["millernton_news"] = gammel["millernton_news"]
        print("  (info: millernton-RSS ga ingenting - beholder forrige nyhetsliste)")
    if not payload["kampplan"] and gammel.get("kampplan"):
        payload["kampplan"] = gammel["kampplan"]
        print("  (info: kampplan-henting ga ingenting - beholder forrige kampplan)")
    if not payload["kamplogg"] and gammel.get("kamplogg"):
        payload["kamplogg"] = gammel["kamplogg"]
        print("  (info: kamplogg-lesing feilet - beholder forrige kamplogg)")
    if not payload["medlemstall"] and gammel.get("medlemstall"):
        payload["medlemstall"] = gammel["medlemstall"]
        print("  (info: medlemstall-lesing feilet - beholder forrige tall)")

    try:
        validate(payload)
    except ValueError as e:
        print(f"FEIL: {e}", file=sys.stderr)
        print("Beholder eksisterende data.json urørt.", file=sys.stderr)
        return 1

    # Hvis vi ikke fant noen kommende kamp, behold den som allerede ligger
    # i data.json - MEN kun hvis den fortsatt er frem i tid. En passert kamp
    # skal aldri vises som "neste kamp"; da er det bedre aa levere tomt og
    # la appens egen fallback-liste ta over.
    if not next_match.get("motstander") and gammel.get("next_match"):
        gammel_dato = (gammel["next_match"] or {}).get("dato", "")
        idag = datetime.now(TZ_DE).strftime("%Y-%m-%d")
        if gammel_dato >= idag:
            payload["next_match"] = gammel["next_match"]
            print("  (info: beholder eksisterende next_match - fant ingen ny kamp)")
        else:
            print(f"  (info: forkaster utdatert next_match fra {gammel_dato} - kampen er spilt)")

    # Legg inn weserv-proxy-URL-er i stedet for aa bake inn bildene som
    # base64 - nettleseren henter bildene direkte fra weserv sitt CDN,
    # og data.json holder seg paa noen faa KB.
    for item in payload["fcstpauli_news"]:
        item["image"] = weserv_image_url(item.get("image", ""))
    for item in payload["millernton_news"]:
        item["image"] = weserv_image_url(item.get("image", ""))

    payload["updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")

    # Oppdater service worker cache-versjon slik at brukerne får nye filer
    oppdater_sw_versjon()

    print(f"OK: data.json oppdatert ({payload['updated']})")
    print(f"  - {len(payload['fcstpauli_news'])} fcstpauli-nyheter")
    print(f"  - {len(payload['millernton_news'])} millernton-nyheter")
    if payload["next_match"].get("motstander"):
        print(f"  - neste kamp: {payload['next_match']['motstander']} ({payload['next_match']['dato']})")
    else:
        print("  - neste kamp: ikke funnet")
    print(f"  - {len(payload.get('kampplan', []))} kamper i kampplan")
    print(f"  - {len(payload.get('kamplogg', []))} kamper i kamplogg")
    if payload.get("medlemstall"):
        print(f"  - medlemstall: {payload['medlemstall'].get('betalende', '?')} betalende")
    return 0


if __name__ == "__main__":
    sys.exit(main())
