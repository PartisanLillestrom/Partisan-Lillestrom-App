#!/usr/bin/env python3
"""Tester for scripts/hent_resultater.py.

Ingen nettverkskall: urlopen og access-token byttes ut med attrapper.
Kjores direkte:  python3 tests/test_hent_resultater.py
"""

import io
import json
import os
import sys

ROT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROT, "scripts"))

import hent_resultater as hr          # noqa: E402
import update_data as u               # noqa: E402

FEIL = 0


def overskrift(t):
    print(f"\n=== {t} ===")


def ok(betingelse, melding):
    global FEIL
    print(("  OK    " if betingelse else "  FEIL  ") + melding)
    if not betingelse:
        FEIL += 1


# --------------------------------------------------------------------------
overskrift("Tokenet sendes i headeren, ikke i adressen")
# Et token i URL-en havner i Firebase sine tilgangslogger og i e.url paa
# en HTTPError. En header gjor ikke det.

fanget = {}


class FalskSvar:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def read(self):
        return b'{"ok":true}'


def falsk_urlopen(req, timeout=None):
    fanget["url"] = req.full_url
    fanget["headers"] = dict(req.headers)
    return FalskSvar()


ekte_urlopen = hr.urllib.request.urlopen
hr.urllib.request.urlopen = falsk_urlopen

hr.lagre_resultat("2026-10-17", {"h": 1, "b": 1}, "ya29.HEMMELIG_TOKEN")
ok("HEMMELIG_TOKEN" not in fanget["url"], f"token ikke i URL: {fanget['url']}")
ok(fanget["headers"].get("Authorization") == "Bearer ya29.HEMMELIG_TOKEN",
   "token ligger i Authorization-headeren")

hr.lagre_resultat("2026-10-17", {"h": 1, "b": 1}, None)
ok("Authorization" not in fanget["headers"], "uten token: ingen Authorization-header")

# --------------------------------------------------------------------------
overskrift("En feilet skriving stopper ikke de ovrige")
# Tidligere avbrot en nettverksblipp hele jobben, og kjoringen ble
# likevel gronn - saa ingen fikk vite at resultatene manglet.

skrevet = []


def feilende_lagring(dato, data, token):
    if dato == "2026-09-20":
        raise OSError("nettverksblipp")
    skrevet.append(dato)


KAMPER = [
    {"dato": "2026-08-14", "h": 1, "b": 0, "hjemmelag": "A", "bortelag": "B", "matchId": 1, "ferdig": True},
    {"dato": "2026-09-20", "h": 2, "b": 2, "hjemmelag": "C", "bortelag": "D", "matchId": 2, "ferdig": True},
    {"dato": "2026-10-17", "h": 1, "b": 1, "hjemmelag": "E", "bortelag": "F", "matchId": 3, "ferdig": True},
]

hr.lagre_resultat = feilende_lagring
hr.hent_access_token = lambda: "token"
hr.hent_openligadb = lambda s: []
hr.hent_firebase_resultater = lambda: {}
hr.finn_ferdige_st_pauli_kamper = lambda m: KAMPER

stderr, sys.stderr = sys.stderr, io.StringIO()
stdout, sys.stdout = sys.stdout, io.StringIO()
kode = hr.main()
logg = sys.stderr.getvalue()
sys.stderr, sys.stdout = stderr, stdout

ok(skrevet == ["2026-08-14", "2026-10-17"], f"kampene etter feilen ble lagret: {skrevet}")
ok(kode == 1, f"main() returnerer {kode} - workflowen blir rod")
ok("FEIL ved lagring av 2026-09-20" in logg, "feilen logges med dato")

# --------------------------------------------------------------------------
overskrift("Alt lykkes -> kode 0")
skrevet.clear()
hr.lagre_resultat = lambda d, x, t: skrevet.append(d)
stdout, sys.stdout = sys.stdout, io.StringIO()
kode = hr.main()
sys.stdout = stdout
ok(kode == 0, "main() returnerer 0")
ok(len(skrevet) == 3, f"{len(skrevet)} resultater lagret")

# --------------------------------------------------------------------------
overskrift("Sesongen regnes likt i begge skriptene")
# En sesong beregnet i ulik tidssone ville gitt to skript som henter fra
# hver sin sesong i noen timer rundt arsskiftet for sesongen.
ok(hr.hent_sesong() == u._openligadb_sesong(),
   f"samme sesong: {hr.hent_sesong()}")
ok(str(hr.TZ_DE) == str(u.TZ_DE), f"samme tidssone: {hr.TZ_DE}")

hr.urllib.request.urlopen = ekte_urlopen
print("\n" + (f"{FEIL} AVVIK" if FEIL else "Alle kontroller OK"))
sys.exit(1 if FEIL else 0)
