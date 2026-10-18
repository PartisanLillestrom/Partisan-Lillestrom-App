#!/usr/bin/env python3
"""
Henter kampresultater for FC St. Pauli fra FotMob
og lagrer dem i Firebase Realtime Database.

Kjøres av GitHub Actions etter kampdager.
"""

import json
import os
import sys
import urllib.request

FOTMOB_TEAM_ID = 8152  # FC St. Pauli
FOTMOB_API = f"https://www.fotmob.com/api/teams?id={FOTMOB_TEAM_ID}"

FIREBASE_DB = "https://partisan-lillestrom-default-rtdb.europe-west1.firebasedatabase.app"
RESULTATER_REF = f"{FIREBASE_DB}/kampresultater"


def hent_fotmob():
    """Henter lagdata fra FotMob API."""
    req = urllib.request.Request(FOTMOB_API, headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.fotmob.com/",
        "x-fm-req": "eyJib2R5Ijp7fX0=",
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
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


def finn_ferdige_kamper(team_data):
    """Finner ferdige kamper fra FotMob team-data."""
    ferdige = []

    # FotMob team API returnerer fixtures under fixtures.allFixtures.fixtures
    # eller under overview.fixtures
    fixtures = None

    # Prøv ulike stier i responsen
    if "fixtures" in team_data:
        fix_data = team_data["fixtures"]
        if "allFixtures" in fix_data:
            all_fix = fix_data["allFixtures"]
            if "fixtures" in all_fix:
                fixtures = all_fix["fixtures"]
        # Alternativ: fixtures kan være en liste direkte
        if not fixtures and isinstance(fix_data, list):
            fixtures = fix_data

    if "overview" in team_data:
        ov = team_data["overview"]
        if "fixtures" in ov:
            fixtures = ov["fixtures"]

    if not fixtures:
        print("Kunne ikke finne fixtures i FotMob-data.")
        print("Tilgjengelige nøkler:", list(team_data.keys()) if isinstance(team_data, dict) else "ikke dict")
        # Skriv ut strukturen for debugging
        for key in team_data.keys() if isinstance(team_data, dict) else []:
            val = team_data[key]
            if isinstance(val, dict):
                print(f"  {key}: {list(val.keys())[:10]}")
            elif isinstance(val, list):
                print(f"  {key}: liste med {len(val)} elementer")
            else:
                print(f"  {key}: {type(val).__name__}")
        return ferdige

    for match in fixtures:
        # Sjekk ulike mulige strukturer
        finished = False
        home_score = None
        away_score = None
        home_name = ""
        away_name = ""
        match_date = ""

        if isinstance(match, dict):
            # Status
            status = match.get("status", {})
            if isinstance(status, dict):
                finished = status.get("finished", False)
            else:
                finished = match.get("finished", False)

            if not finished:
                continue

            # Lag og score
            home = match.get("home", match.get("homeTeam", {}))
            away = match.get("away", match.get("awayTeam", {}))

            if isinstance(home, dict):
                home_name = home.get("name", home.get("shortName", ""))
                home_score = home.get("score", None)
            if isinstance(away, dict):
                away_name = away.get("name", away.get("shortName", ""))
                away_score = away.get("score", None)

            # Dato
            match_date = match.get("utcTime", match.get("matchDate", ""))
            if match_date and "T" in match_date:
                match_date = match_date[:10]  # YYYY-MM-DD
            elif match_date and len(match_date) == 8:
                # YYYYMMDD format
                match_date = f"{match_date[:4]}-{match_date[4:6]}-{match_date[6:8]}"

        if finished and home_score is not None and away_score is not None and match_date:
            ferdige.append({
                "dato": match_date,
                "hjemmelag": home_name,
                "bortelag": away_name,
                "h": int(home_score),
                "b": int(away_score),
                "ferdig": True
            })

    return ferdige


def main():
    print("Henter data fra FotMob...")
    try:
        team_data = hent_fotmob()
    except Exception as e:
        print(f"Feil ved henting fra FotMob: {e}")
        sys.exit(1)

    print("Finner ferdige kamper...")
    ferdige = finn_ferdige_kamper(team_data)
    print(f"Fant {len(ferdige)} ferdige kamper")

    if not ferdige:
        print("Ingen ferdige kamper å oppdatere.")
        return

    print("Henter eksisterende resultater fra Firebase...")
    eksisterende = hent_firebase_resultater()

    nye = 0
    for kamp in ferdige:
        dato = kamp["dato"]
        if dato in eksisterende:
            # Sjekk om resultatet er det samme
            eks = eksisterende[dato]
            if eks.get("h") == kamp["h"] and eks.get("b") == kamp["b"]:
                continue

        print(f"  Lagrer: {kamp['hjemmelag']} {kamp['h']}-{kamp['b']} {kamp['bortelag']} ({dato})")
        lagre_resultat(dato, kamp)
        nye += 1

    print(f"Ferdig! {nye} nye/oppdaterte resultater lagret.")


if __name__ == "__main__":
    main()
