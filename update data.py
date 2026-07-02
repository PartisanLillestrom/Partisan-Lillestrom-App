#!/usr/bin/env python3
"""
Henter ferske nyheter (fcstpauli.com + millernton.de) og neste kamp for
FC St. Pauli via Claude (Anthropic API) sin web_search-funksjon, og skriver
resultatet til data.json i repo-roten.

Dette skriptet er ment a kjores server-side (f.eks. i en GitHub Action),
IKKE i nettleseren - fordi det krever en hemmelig API-nokkel
(ANTHROPIC_API_KEY) som aldri skal eksponeres i klientkode.

Hvis noe feiler underveis (nettverksfeil, ugyldig JSON fra modellen, manglende
felter), lar vi den eksisterende data.json sta urort og avslutter med
feilkode 1, slik at GitHub Actions tydelig viser at korselen feilet - uten
at nettsiden noensinne viser odelagt eller tom data.
"""

import base64
import json
import os
import re
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-6"
DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data.json")

SYSTEM_PROMPT = """Du er en research-assistent for en supporterklubb-app for FC St. Pauli (Partisan Lillestrom).

Bruk web_search til a finne:

1. De 3 NYESTE nyhetsartiklene fra https://www.fcstpauli.com/ (offisiell klubbside). For hver artikkel:
   - Hent artikkelens URL
   - Hent bildet fra artikkelsiden: bruk web_search til a ga inn pa hver artikkelside og finn
     <meta property="og:image" content="..."> i HTML-koden. Denne URL-en starter typisk med
     https://www.fcstpauli.com/fileadmin/ eller https://fcstpauli.com/fileadmin/ og er offentlig
     tilgjengelig uten hotlink-beskyttelse. Bruk DENNE URL-en, ikke api.fcstpauli.com-URLer.
     Hvis du ikke finner og:image, sett image til tom streng "".

2. De 3 NYESTE blogginnleggene fra https://millernton.de/ (uavhengig fan-blogg). For hvert innlegg:
   hent ogsa og:image-URL fra innleggssiden (<meta property="og:image">) hvis tilgjengelig,
   ellers tom streng "".

3. NESTE planlagte kamp for FC St. Pauli sitt herrelag. Sjekk den offisielle terminlisten pa
   https://www.fcstpauli.com/fussball/teams/profis?tab=spielplanuebersicht (eller Rahmenspielplan-siden).
   ABSOLUTT KRAV: Kampens dato MA vaere i dag eller senere - ALDRI en dato som allerede har passert.
   Inkluder testkamper (Testspiel), DFB-Pokal og 2. Bundesliga-kamper. Velg den som kommer FORST.

Svar BARE med gyldig JSON - ingen markdown-formatering, ingen forklaringer - i NOYAKTIG dette skjemaet:

{
  "fcstpauli_news": [
    {"title_no": "norsk oversettelse", "title_de": "original tysk tittel", "url": "fullstendig artikkel-URL", "image": "og:image URL eller tom streng"}
  ],
  "millernton_news": [
    {"title_no": "norsk oversettelse", "title_de": "original tysk tittel", "url": "fullstendig URL", "date": "dato pa norsk, f.eks. '2. juli'", "image": "og:image URL eller tom streng"}
  ],
  "next_match": {"motstander": "lagnavn", "dato": "YYYY-MM-DD", "tid": "HH:MM eller tom streng", "turnering": "2. Bundesliga / DFB-Pokal / Testspiel", "hjemme": true eller false, "stadion": "stadionnavn, by"}
}

VIKTIG:
- fcstpauli_news skal inneholde noyaktig 3 elementer.
- millernton_news skal inneholde noyaktig 3 elementer.
- Oversett titlene naturlig til norsk (bokmal).
- Ikke finn pa URL-er du ikke faktisk har funnet.
"""


def call_claude(api_key: str, today: str) -> str:
    body = json.dumps({
        "model": MODEL,
        "max_tokens": 2000,
        "tools": [{"type": "web_search_20250305", "name": "web_search"}],
        "system": SYSTEM_PROMPT,
        "messages": [
            {"role": "user", "content": f"Dagens dato er {today}. Finn fersk informasjon og svar med JSON-objektet som beskrevet."}
        ],
    }).encode("utf-8")

    req = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read()
    return raw.decode("utf-8")


def extract_text(api_response_raw: str) -> str:
    data = json.loads(api_response_raw)
    if "error" in data:
        raise RuntimeError(f"Anthropic API returnerte feil: {data['error']}")
    blocks = data.get("content", [])
    text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
    if not text.strip():
        raise RuntimeError(f"Tomt svar fra API. Full respons: {api_response_raw[:500]}")
    return text


def extract_json_object(text: str) -> dict:
    # Modellen kan av og til pakke JSON i ```json ... ``` eller legge til tekst rundt.
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError(f"Fant ingen JSON i modellsvaret:\n{text[:1000]}")
    return json.loads(match.group(0))


def validate(payload: dict) -> None:
    for key in ("fcstpauli_news", "millernton_news", "next_match"):
        if key not in payload:
            raise ValueError(f"Mangler felt '{key}' i resultatet")

    for item in payload["fcstpauli_news"]:
        for field in ("title_no", "title_de", "url"):
            if not item.get(field):
                raise ValueError(f"fcstpauli_news-element mangler felt '{field}': {item}")

    for item in payload["millernton_news"]:
        for field in ("title_no", "title_de", "url"):
            if not item.get(field):
                raise ValueError(f"millernton_news-element mangler felt '{field}': {item}")

    nm = payload["next_match"]
    for field in ("motstander", "dato", "turnering"):
        if not nm.get(field):
            raise ValueError(f"next_match mangler felt '{field}': {nm}")
    # Valider datoformat OG at kampen ikke er i fortiden
    kampdato = datetime.strptime(nm["dato"], "%Y-%m-%d").date()
    idag = datetime.now(timezone.utc).date()
    if kampdato < idag:
        raise ValueError(
            f"next_match har dato i fortiden ({nm['dato']}, i dag er {idag}) - "
            f"modellen fant feil kamp. Beholder gammel data."
        )

    if len(payload["fcstpauli_news"]) == 0 or len(payload["millernton_news"]) == 0:
        raise ValueError("Nyhetslister kan ikke vaere tomme")


def download_image_as_data_uri(url: str, referer: str = "https://www.fcstpauli.com/") -> str:
    """Laster ned et bilde server-side og returnerer det som en base64 data-URI.

    Dette omgar hotlink-beskyttelse fullstendig: nettleseren trenger aldri
    kontakte eksterne bildeservere - bildet ligger inni data.json.
    Returnerer tom streng hvis nedlasting feiler eller bildet er for stort.
    """
    if not url or not url.startswith("http"):
        return ""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
            "Referer": referer,
            "Accept": "image/webp,image/jpeg,image/png,image/*,*/*",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            ctype = (resp.headers.get("Content-Type") or "image/webp").split(";")[0].strip()
        if not ctype.startswith("image/"):
            return ""
        if len(data) > 600_000:  # dropp bilder over ~600 KB for a holde data.json liten
            return ""
        return f"data:{ctype};base64," + base64.b64encode(data).decode("ascii")
    except Exception as e:
        print(f"  (advarsel: kunne ikke laste ned bilde {url}: {e})", file=sys.stderr)
        return ""


def main() -> int:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("FEIL: miljovariabelen ANTHROPIC_API_KEY er ikke satt.", file=sys.stderr)
        return 1

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    try:
        raw = call_claude(api_key, today)
        text = extract_text(raw)
        payload = extract_json_object(text)
        validate(payload)
    except (urllib.error.URLError, RuntimeError, ValueError, json.JSONDecodeError) as e:
        print(f"FEIL under henting/parsing: {e}", file=sys.stderr)
        print("Beholder eksisterende data.json urort.", file=sys.stderr)
        return 1

    # Last ned bildene server-side og bygg dem inn som base64, slik at
    # nettleseren aldri trenger a hente noe fra eksterne bildeservere.
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
    print(f"  - neste kamp: {payload['next_match']['motstander']} ({payload['next_match']['dato']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
