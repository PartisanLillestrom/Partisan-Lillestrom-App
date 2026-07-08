#!/usr/bin/env python3
"""
Henter ferske nyheter (fcstpauli.com + millernton.de) og neste kamp for
FC St. Pauli - HELT GRATIS, uten Anthropic API:

  - fcstpauli.com: lenker scrapes fra nyhetssiden, og:title/og:image
    hentes fra hver artikkelside. Prøver /news/ OG /fussball/aktuelles.
  - millernton.de: uendret - RSS-feed + og:image (som før).
  - Oversettelse tysk -> norsk: MyMemory sin gratis oversettelses-API
    (ingen nøkkel nødvendig, https://mymemory.translated.net/).
  - Neste kamp: scrapes direkte fra FC St. Paulis egen rahmenspielplan-side,
    som også inkluderer testkamper for sesongstart - ingen tredjeparts-API.

Resultatet skrives til data.json i repo-roten. Hvis noe feiler underveis
lar vi eksisterende data.json stå urørt og avslutter med feilkode 1, slik
at GitHub Actions tydelig viser at kjørselen feilet - uten at nettsiden
noensinne viser ødelagt eller tom data.
"""

import base64
import email.utils
import json
import re
import sys
import urllib.parse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

DATA_FILE = "data.json"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

MONTHS_NO = {
    1: "januar", 2: "februar", 3: "mars", 4: "april", 5: "mai", 6: "juni",
    7: "juli", 8: "august", 9: "september", 10: "oktober", 11: "november", 12: "desember",
}


# ---------------------------------------------------------------------------
# Oversettelse (gratis, ingen nøkkel)
# ---------------------------------------------------------------------------

def translate_de_to_no(text: str) -> str:
    """Oversetter kort tysk tekst til norsk via MyMemory sin gratis API.
    Returnerer originalteksten uendret hvis oversettelsen feiler - da vises
    den tyske originaltittelen i stedet, som fortsatt er lesbar."""
    if not text:
        return text
    try:
        q = urllib.parse.quote(text[:490])
        url = f"https://api.mymemory.translated.net/get?q={q}&langpair=de|no"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        translated = (data.get("responseData") or {}).get("translatedText", "")
        if translated and "MYMEMORY WARNING" not in translated.upper():
            return translated
        return text
    except Exception as e:
        print(f"  (advarsel: oversettelse feilet for '{text[:40]}...': {e})", file=sys.stderr)
        return text


# ---------------------------------------------------------------------------
# MillernTon (uendret: RSS + og:image)
# ---------------------------------------------------------------------------

def fetch_millernton_rss(limit: int = 3) -> list:
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

def fetch_og_tag(page_url: str, tag: str) -> str:
    """Henter en og:-meta-tag (f.eks. 'og:image' eller 'og:title') fra en
    artikkelside. Tom streng hvis ikke funnet."""
    try:
        req = urllib.request.Request(page_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read(400_000).decode("utf-8", "replace")
        pattern_a = rf'property=["\']{re.escape(tag)}["\'"][^>]*content=["\'"]([^"\']+)'
        pattern_b = rf'content=["\'"]([^"\']+)["\'"][^>]*property=["\']{re.escape(tag)}'
        m = re.search(pattern_a, html) or re.search(pattern_b, html)
        return m.group(1) if m else ""
    except Exception as e:
        print(f"  (advarsel: fant ikke {tag} på {page_url}: {e})", file=sys.stderr)
        return ""


def fetch_og_image(page_url: str) -> str:
    return fetch_og_tag(page_url, "og:image")


def fetch_og_title(page_url: str) -> str:
    return fetch_og_tag(page_url, "og:title")


# ---------------------------------------------------------------------------
# fcstpauli.com - robust scraping med fallback-URL
# ---------------------------------------------------------------------------

def fetch_fcstpauli_news_urls(limit: int = 3) -> list:
    """Henter de nyeste artikkel-lenkene fra fcstpauli.com sin nyhetsside.
    
    Prøver både /news/ og /fussball/aktuelles - siden siden redirecter
    og URL-strukturen kan variere. Bruker en bred regex som fanger
    alle /news/<slug>-lenker uavhengig av slug-format.
    """
    # Prøv begge URL-er - den ene er redirect-destinasjonen til den andre
    kandidat_sider = [
        "https://www.fcstpauli.com/news/",
        "https://www.fcstpauli.com/fussball/aktuelles",
    ]

    for page_url in kandidat_sider:
        try:
            req = urllib.request.Request(
                page_url,
                headers={"User-Agent": USER_AGENT},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                final_url = resp.url  # følg redirects
                html = resp.read().decode("utf-8", "replace")

            # Bred regex: matcher /news/<hva-som-helst> unntatt query/fragment/whitespace
            # Fanger både relative og absolutte lenker
            raw_links = re.findall(
                r'href=["\'](?:https://www\.fcstpauli\.com)?(/news/[^"\'?#\s]+)["\']',
                html
            )

            urls = []
            seen = set()
            for link in raw_links:
                # Hopp over rotlenken /news/ selv
                if re.match(r'^/news/?$', link):
                    continue
                full = "https://www.fcstpauli.com" + link
                if full in seen:
                    continue
                seen.add(full)
                urls.append(full)
                if len(urls) >= limit:
                    break

            print(f"Scraping: fant {len(urls)} artikkel-lenker på {page_url}"
                  + (f" (→ {final_url})" if final_url != page_url else ""))
            if urls:
                return urls

        except Exception as e:
            print(f"(advarsel: henting fra {page_url} feilet: {e})", file=sys.stderr)

    print("Scraping: fant 0 artikkel-lenker på alle prøvde URL-er", file=sys.stderr)
    return []


# ---------------------------------------------------------------------------
# Neste kamp (scraper fcstpauli.com sin Rahmenspielplan-side)
# ---------------------------------------------------------------------------

RAHMENSPIELPLAN_URL = "https://www.fcstpauli.com/fu%C3%9Fball/teams/profis/rahmenspielplan-2026-27"


def _strip_tags(html_fragment: str) -> str:
    """Fjerner HTML-tagger og dekoder entiteter, returnerer ren tekst."""
    import html as html_mod
    text = re.sub(r'<[^>]+>', ' ', html_fragment)
    text = html_mod.unescape(text)
    return re.sub(r'\s+', ' ', text).strip()


def fetch_next_match_fcstpauli(url: str = RAHMENSPIELPLAN_URL) -> dict:
    """Henter neste kamp direkte fra FC St. Paulis egen Rahmenspielplan-side.
    Dette er den mest pålitelige kilden: den inkluderer også testkamper
    (Testspiel) i forkant av sesongen."""
    m_season = re.search(r'(\d{4})-\d{2}', url)
    season_start_year = int(m_season.group(1)) if m_season else datetime.now(timezone.utc).year

    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as resp:
            html_doc = resp.read().decode("utf-8", "replace")
    except Exception as e:
        print(f"  (advarsel: henting av rahmenspielplan feilet: {e})", file=sys.stderr)
        return {}

    today = datetime.now(timezone.utc).date()
    kandidater = []

    for row_match in re.finditer(r'<tr\b[^>]*>(.*?)</tr>', html_doc, re.DOTALL | re.IGNORECASE):
        cells = re.findall(r'<t[dh]\b[^>]*>(.*?)</t[dh]>', row_match.group(1), re.DOTALL | re.IGNORECASE)
        if len(cells) < 6:
            continue
        wettbewerb, _runde, datum, anstot, hjem, gjest = (_strip_tags(c) for c in cells[:6])
        if not hjem or not gjest:
            continue

        m_dato = re.match(r'(\d{1,2})\.(\d{1,2})\.', datum.strip())
        if not m_dato:
            continue
        dag, maned = int(m_dato.group(1)), int(m_dato.group(2))
        aar = season_start_year if maned >= 7 else season_start_year + 1

        time_str = "12:00"
        m_tid = re.search(r'(\d{1,2})(?::(\d{2}))?\s*Uhr', anstot)
        if m_tid:
            time_str = f"{int(m_tid.group(1)):02d}:{m_tid.group(2) or '00'}"

        try:
            dt = datetime.strptime(
                f"{aar}-{maned:02d}-{dag:02d} {time_str}", "%Y-%m-%d %H:%M"
            ).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if dt.date() < today:
            continue

        hjemme = "pauli" in hjem.lower()
        kandidater.append({
            "dt": dt,
            "motstander": gjest if hjemme else hjem,
            "hjemme": hjemme,
            "turnering": wettbewerb.strip() or "Kamp",
        })

    if not kandidater:
        print("  (advarsel: fant ingen kommende kamp med fastsatt dato på rahmenspielplan-siden)", file=sys.stderr)
        return {}

    kandidater.sort(key=lambda x: x["dt"])
    neste = kandidater[0]
    return {
        "motstander": neste["motstander"],
        "dato": neste["dt"].strftime("%Y-%m-%d"),
        "tid": neste["dt"].strftime("%H:%M"),
        "turnering": neste["turnering"],
        "hjemme": neste["hjemme"],
        "stadion": "Millerntor-Stadion, Hamburg" if neste["hjemme"] else "",
    }


# ---------------------------------------------------------------------------
# Bildenedlasting (uendret)
# ---------------------------------------------------------------------------

def download_image_as_data_uri(url: str, referer: str) -> str:
    """Laster ned et bilde server-side og returnerer det som en base64
    data-URI. Dette omgår hotlink-beskyttelse fullstendig: nettleseren
    trenger aldri kontakte eksterne bildeservere - bildet ligger inni
    data.json. Returnerer tom streng hvis nedlasting feiler eller bildet
    er for stort."""
    if not url or not url.startswith("http"):
        return ""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": USER_AGENT,
            "Referer": referer,
            "Accept": "image/webp,image/jpeg,image/png,image/*,*/*",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            ctype = (resp.headers.get("Content-Type") or "image/webp").split(";")[0].strip()
        if not ctype.startswith("image/"):
            return ""
        if len(data) > 600_000:  # dropp bilder over ~600 KB for å holde data.json liten
            return ""
        return f"data:{ctype};base64," + base64.b64encode(data).decode("ascii")
    except Exception as e:
        print(f"  (advarsel: kunne ikke laste ned bilde {url}: {e})", file=sys.stderr)
        return ""


# ---------------------------------------------------------------------------
# Validering
# ---------------------------------------------------------------------------

def validate(payload: dict) -> None:
    if not payload.get("fcstpauli_news"):
        raise ValueError("fcstpauli_news er tom - noe gikk galt under scraping")
    if not payload.get("millernton_news"):
        raise ValueError("millernton_news er tom - noe gikk galt under RSS-henting")
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

def main() -> int:
    # --- MillernTon ---
    rss_items = fetch_millernton_rss()
    for it in rss_items:
        it["image"] = fetch_og_image(it["url"])
        it["title_no"] = translate_de_to_no(it["title_de"])

    # --- fcstpauli.com ---
    fcstpauli_items = []
    for url in fetch_fcstpauli_news_urls(limit=3):
        title_de = fetch_og_title(url)
        if not title_de:
            continue
        fcstpauli_items.append({
            "title_no": translate_de_to_no(title_de),
            "title_de": title_de,
            "url": url,
            "image": fetch_og_image(url),
        })

    # --- Neste kamp ---
    next_match = fetch_next_match_fcstpauli()

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
    }

    try:
        validate(payload)
    except ValueError as e:
        print(f"FEIL: {e}", file=sys.stderr)
        print("Beholder eksisterende data.json urørt.", file=sys.stderr)
        return 1

    # Hvis vi ikke fant noen kommende kamp, behold den som allerede ligger
    # i data.json fremfor å skrive over med tomt innhold.
    if not next_match.get("motstander"):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                gammel = json.load(f)
            payload["next_match"] = gammel.get("next_match", next_match)
            print("  (info: beholder eksisterende next_match - fant ingen ny kamp)")
        except Exception:
            pass

    # Last ned bildene server-side som base64
    for item in payload["fcstpauli_news"]:
        item["image"] = download_image_as_data_uri(item.get("image", ""), referer="https://www.fcstpauli.com/")
    for item in payload["millernton_news"]:
        item["image"] = download_image_as_data_uri(item.get("image", ""), referer="https://millernton.de/")

    payload["updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"OK: data.json oppdatert ({payload['updated']})")
    print(f"  - {len(payload['fcstpauli_news'])} fcstpauli-nyheter")
    print(f"  - {len(payload['millernton_news'])} millernton-nyheter")
    if payload["next_match"].get("motstander"):
        print(f"  - neste kamp: {payload['next_match']['motstander']} ({payload['next_match']['dato']})")
    else:
        print("  - neste kamp: ikke funnet")
    return 0


if __name__ == "__main__":
    sys.exit(main())
