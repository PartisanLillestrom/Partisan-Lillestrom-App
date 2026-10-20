#!/usr/bin/env python3
"""
Henter kampresultater for FC St. Pauli fra OpenLigaDB
og lagrer dem i Firebase Realtime Database.

Kjøres av GitHub Actions etter kampdager.
Bruker Google Service Account for autentisering mot Firebase.
"""

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

# OpenLigaDB: bl2 = 2. Bundesliga
OPENLIGA_API = "https://api.openligadb.de/getmatchdata/bl2"

FIREBASE_DB = "https://partisan-lillestrom-default-rtdb.europe-west1.firebasedatabase.app"
RESULTATER_REF = f"{FIREBASE_DB}/kampresultater"

ST_PAULI_NAMES = ["st. pauli", "st pauli", "fc st. pauli"]

# Kamptider fra OpenLigaDB er tysk lokaltid. Samme kilde som update_data.py.
try:
    from zoneinfo import ZoneInfo
    TZ_DE = ZoneInfo("Europe/Berlin")
except Exception:  # svaert usannsynlig paa GitHub Actions, men aldri krasj
    TZ_DE = timezone.utc


def hent_access_token():
    """Genererer et OAuth2 access token fra service account."""
    import base64
    import time

    sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT", "")
    if not sa_json:
        print("ADVARSEL: Ingen FIREBASE_SERVICE_ACCOUNT satt, prøver uten autentisering.")
        return None

    sa = json.loads(sa_json)
    # Bygg JWT
    header = base64.urlsafe_b64encode(json.dumps({
        "alg": "RS256", "typ": "JWT"
    }).encode()).rstrip(b"=")

    now = int(time.time())
    claims = base64.urlsafe_b64encode(json.dumps({
        "iss": sa["client_email"],
        "scope": "https://www.googleapis.com/auth/firebase.database https://www.googleapis.com/auth/userinfo.email",
        "aud": "https://oauth2.googleapis.com/token",
        "iat": now,
        "exp": now + 3600
    }).encode()).rstrip(b"=")

    signing_input = header + b"." + claims

    # RS256-signering med private key
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    private_key = serialization.load_pem_private_key(
        sa["private_key"].encode(), password=None
    )
    signature = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    sig_b64 = base64.urlsafe_b64encode(signature).rstrip(b"=")

    jwt_token = (signing_input + b"." + sig_b64).decode()

    # Bytt JWT mot access token
    token_url = "https://oauth2.googleapis.com/token"
    token_data = urllib.parse.urlencode({
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": jwt_token
    }).encode()
    req = urllib.request.Request(token_url, data=token_data, headers={
        "Content-Type": "application/x-www-form-urlencoded"
    })
    with urllib.request.urlopen(req, timeout=10) as resp:
        token_resp = json.loads(resp.read().decode())
    return token_resp["access_token"]


def er_st_pauli(lagnavn):
    """Sjekker om et lagnavn er St. Pauli."""
    return any(n in lagnavn.lower() for n in ST_PAULI_NAMES)


def hent_sesong():
    """Beregner gjeldende sesong (2026 = 2026/27-sesongen).

    Regnes i tysk tid, som i update_data.py. Med UTC ga de to skriptene
    ulikt svar de to foerste timene av 1. juli hvert aar."""
    now = datetime.now(TZ_DE)
    return now.year if now.month >= 7 else now.year - 1


def hent_openligadb(sesong):
    """Henter alle kamper for sesongen fra OpenLigaDB."""
    url = f"{OPENLIGA_API}/{sesong}"
    print(f"Henter fra: {url}")
    req = urllib.request.Request(url, headers={
        "User-Agent": "PartisanLillestrom/1.0"
    })
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def hent_firebase_resultater():
    """Henter eksisterende resultater fra Firebase."""
    req = urllib.request.Request(f"{RESULTATER_REF}.json")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return data if data else {}
    except Exception:
        return {}


def lagre_resultat(dato, data, access_token):
    """Lagrer et kampresultat i Firebase med autentisering.

    Tokenet sendes i Authorization-headeren, ikke som spoerringsparameter.
    En URL havner i Firebase sine tilgangslogger og i e.url paa en
    HTTPError; en header gjoer ikke det."""
    url = f"{RESULTATER_REF}/{dato}.json"
    headers = {"Content-Type": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    payload = json.dumps(data).encode()
    req = urllib.request.Request(url, data=payload, method="PUT", headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def finn_ferdige_st_pauli_kamper(matches):
    """Finner ferdige St. Pauli-kamper fra OpenLigaDB-data."""
    ferdige = []

    for match in matches:
        if not match.get("matchIsFinished", False):
            continue

        hjemme = match.get("team1", {}).get("teamName", "")
        borte = match.get("team2", {}).get("teamName", "")

        # Filtrer: bare St. Pauli-kamper
        if not er_st_pauli(hjemme) and not er_st_pauli(borte):
            continue

        # Hent sluttresultat
        results = match.get("matchResults", [])
        if not results:
            continue

        # Bruk resulttype 2 (sluttresultat) om tilgjengelig, ellers siste
        slutt = None
        for r in results:
            if r.get("resultTypeID") == 2:
                slutt = r
                break
        if not slutt:
            slutt = results[-1]

        h_score = slutt.get("pointsTeam1")
        b_score = slutt.get("pointsTeam2")
        if h_score is None or b_score is None:
            continue

        # Dato fra matchDateTime (format: "2026-10-04T15:30:00")
        match_dt = match.get("matchDateTime", match.get("matchDateTimeUTC", ""))
        if not match_dt:
            continue
        dato = match_dt[:10]  # YYYY-MM-DD

        ferdige.append({
            # matchId knytter resultatet til kampen uavhengig av dato.
            # DFL fastsetter helgen for hele sesongen, men dag og
            # klokkeslett kommer i bolker - flyttes en kamp fra loerdag
            # til soendag, endrer datoen seg, og et tipp lagret under den
            # gamle datoen ville mistet koblingen til resultatet. Noden
            # noekles fortsatt paa dato (uendret for eksisterende data),
            # men appen slaar opp paa matchId naar det finnes.
            "matchId": match.get("matchID") or match.get("matchId"),
            "dato": dato,
            "hjemmelag": hjemme,
            "bortelag": borte,
            "h": int(h_score),
            "b": int(b_score),
            "ferdig": True
        })

    return ferdige


def main():
    sesong = hent_sesong()
    print(f"Sesong: {sesong}/{sesong + 1}")

    # Autentisering mot Firebase
    print("Henter Firebase access token...")
    try:
        access_token = hent_access_token()
        if access_token:
            print("Access token hentet OK")
        else:
            print("Kjører uten autentisering")
    except Exception as e:
        print(f"Kunne ikke hente access token: {e}")
        sys.exit(1)

    print("Henter data fra OpenLigaDB...")
    try:
        matches = hent_openligadb(sesong)
    except Exception as e:
        print(f"Feil ved henting fra OpenLigaDB: {e}")
        sys.exit(1)

    print(f"Hentet {len(matches)} kamper totalt")

    ferdige = finn_ferdige_st_pauli_kamper(matches)
    print(f"Fant {len(ferdige)} ferdige St. Pauli-kamper")

    if not ferdige:
        print("Ingen ferdige kamper å oppdatere.")
        return 0

    print("Henter eksisterende resultater fra Firebase...")
    eksisterende = hent_firebase_resultater()

    nye = 0
    feilet = 0
    for kamp in ferdige:
        dato = kamp["dato"]
        if dato in eksisterende:
            eks = eksisterende[dato]
            uendret_resultat = (
                eks.get("h") == kamp["h"] and eks.get("b") == kamp["b"]
            )
            # Rader lagret for matchId ble innfoert mangler feltet. De maa
            # skrives om selv om selve resultatet er uendret, ellers blir de
            # aldri etterfylt og appen maa falle tilbake paa dato-oppslag.
            har_match_id = eks.get("matchId") is not None
            if uendret_resultat and har_match_id:
                continue

        print(f"  Lagrer: {kamp['hjemmelag']} {kamp['h']}-{kamp['b']} {kamp['bortelag']} ({dato})")
        try:
            lagre_resultat(dato, kamp, access_token)
            nye += 1
        except Exception as e:
            # En enkelt feilet skriving skal ikke stoppe de oevrige. Uten
            # dette avbroet foerste nettverksblipp hele loekka, og kampene
            # etter den ble staaende uskrevet til neste kjoering.
            print(f"  FEIL ved lagring av {dato}: {e}", file=sys.stderr)
            feilet += 1

    print(f"Ferdig! {nye} nye/oppdaterte resultater lagret.")
    if feilet:
        print(f"{feilet} resultat(er) kunne ikke lagres - se feilmeldinger over.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
