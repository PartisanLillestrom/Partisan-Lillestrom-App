#!/usr/bin/env python3
"""
Tar backup av hele Firebase Realtime Database
og lagrer som JSON-fil i backups/-mappen.

Kjøres av GitHub Actions på fast tidspunkt.
Bruker Google Service Account for autentisering mot Firebase.
"""

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

FIREBASE_DB = "https://partisan-lillestrom-default-rtdb.europe-west1.firebasedatabase.app"


def hent_access_token():
    """Genererer et OAuth2 access token fra service account."""
    import base64
    import time

    sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT", "")
    if not sa_json:
        print("FEIL: Ingen FIREBASE_SERVICE_ACCOUNT satt.")
        sys.exit(1)

    sa = json.loads(sa_json)

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

    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    private_key = serialization.load_pem_private_key(
        sa["private_key"].encode(), password=None
    )
    signature = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    sig_b64 = base64.urlsafe_b64encode(signature).rstrip(b"=")

    jwt_token = (signing_input + b"." + sig_b64).decode()

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


def hent_hele_databasen(access_token):
    """Henter hele databasen fra Firebase.

    Tokenet sendes i Authorization-headeren, ikke som spoerringsparameter.
    En URL havner i Firebase sine tilgangslogger og i e.url paa en
    HTTPError; en header gjoer ikke det."""
    url = f"{FIREBASE_DB}/.json"
    headers = {}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def main():
    print("Starter Firebase-backup...")

    print("Henter access token...")
    access_token = hent_access_token()
    print("Access token hentet OK")

    print("Henter hele databasen...")
    data = hent_hele_databasen(access_token)

    if not data:
        print("Databasen er tom, ingen backup tatt.")
        return

    # Lag filnavn med dato
    now = datetime.now(timezone.utc)
    filnavn = f"backups/firebase-backup-{now.strftime('%Y-%m-%d')}.json"

    # Opprett backups-mappen om den ikke finnes
    os.makedirs("backups", exist_ok=True)

    with open(filnavn, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    storrelse = os.path.getsize(filnavn)
    print(f"Backup lagret: {filnavn} ({storrelse} bytes)")

    # Her stod det tidligere logikk for aa beholde de siste 30 backupene.
    # Den var daud kode: backups/ er ikke i repoet, og hver GitHub
    # Actions-kjoering starter paa en fersk maskin med tom mappe - saa det
    # fantes aldri mer enn en fil aa rydde i. Oppbevaringen styres i
    # praksis av retention-days i .github/workflows/backup.yml.
    print("Backup fullført!")


if __name__ == "__main__":
    main()
