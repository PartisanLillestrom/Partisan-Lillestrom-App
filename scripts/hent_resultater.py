#!/usr/bin/env python3
"""
Henter kampresultater for FC St. Pauli fra OpenLigaDB
og lagrer dem i Firebase Realtime Database.

Kjøres av GitHub Actions etter kampdager.
"""

import json
import sys
import urllib.request
from datetime import datetime

# OpenLigaDB: bl2 = 2. Bundesliga
OPENLIGA_API = "https://api.openligadb.de/getmatchdata/bl2"

FIREBASE_DB = "https://partisan-lillestrom-default-rtdb.europe-west1.firebasedatabase.app"
RESULTATER_REF = f"{FIREBASE_DB}/kampresultater"

ST_PAULI_NAMES = ["st. pauli", "st pauli", "fc st. pauli"]


def er_st_pauli(lagnavn):
    """Sjekker om et lagnavn er St. Pauli."""
    return any(n in lagnavn.lower() for n in ST_PAULI_NAMES)


def hent_sesong():
    """Beregner gjeldende sesong (2026 = 2026/27-sesongen)."""
    now = datetime.utcnow()
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


def lagre_resultat(dato, data):
    """Lagrer et kampresultat i Firebase."""
    url = f"{RESULTATER_REF}/{dato}.json"
    payload = json.dumps(data).encode()
    req = urllib.request.Request(url, data=payload, method="PUT", headers={
        "Content-Type": "application/json"
    })
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

        # Hent sluttresultat (siste i matchResults-listen)
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
        return

    print("Henter eksisterende resultater fra Firebase...")
    eksisterende = hent_firebase_resultater()

    nye = 0
    for kamp in ferdige:
        dato = kamp["dato"]
        if dato in eksisterende:
            eks = eksisterende[dato]
            if eks.get("h") == kamp["h"] and eks.get("b") == kamp["b"]:
                continue

        print(f"  Lagrer: {kamp['hjemmelag']} {kamp['h']}-{kamp['b']} {kamp['bortelag']} ({dato})")
        lagre_resultat(dato, kamp)
        nye += 1

    print(f"Ferdig! {nye} nye/oppdaterte resultater lagret.")


if __name__ == "__main__":
    main()
