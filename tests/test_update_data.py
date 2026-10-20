#!/usr/bin/env python3
"""Tester for scripts/update_data.py.

Ingen nettverkskall: kampplan-testene mater OpenLigaDB-cachen direkte,
og de ovrige funksjonene er rene.

Kjores direkte:  python3 tests/test_update_data.py
"""

import io
import os
import sys

ROT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROT, "scripts"))

import update_data as u              # noqa: E402

FEIL = 0


def overskrift(t):
    print(f"\n=== {t} ===")


def ok(betingelse, melding):
    global FEIL
    print(("  OK    " if betingelse else "  FEIL  ") + melding)
    if not betingelse:
        FEIL += 1


def stille(fn, *a, **kw):
    """Kjorer fn uten at loggingen forurenser testutskriften."""
    ut, sys.stdout = sys.stdout, io.StringIO()
    feil, sys.stderr = sys.stderr, io.StringIO()
    try:
        return fn(*a, **kw)
    finally:
        sys.stdout, sys.stderr = ut, feil


def kamp(mid, dato, tid, motstander, hjemme=True):
    sp = {"teamId": u.STPAULI_TEAM_ID, "teamName": "FC St. Pauli"}
    mo = {"teamId": 999, "teamName": motstander}
    d = {"matchDateTime": f"{dato}T{tid}:00",
         "team1": sp if hjemme else mo, "team2": mo if hjemme else sp}
    if mid is not None:
        d["matchID"] = mid
    return d


def kampplan(kamper):
    u._OLB_CACHE.clear()
    u._OLB_CACHE[u._openligadb_sesong()] = kamper
    return stille(u.fetch_kampplan_fcstpauli)


# --------------------------------------------------------------------------
overskrift("Duplikatfjerning nokler paa matchId, ikke dato")
# To runder DFL ennaa ikke har fastsatt kan ligge paa samme
# plassholderdato i OpenLigaDB. Med dato som nokkel ble den ene kampen
# kastet stille ut av bade kampplan og tipping.

r = kampplan([kamp(1001, "2027-04-11", "13:30", "VfL Bochum"),
              kamp(1002, "2027-04-11", "13:30", "Hertha BSC")])
ok(len(r) == 2, f"to kamper paa samme plassholderdato: begge beholdt ({len(r)})")
ok({x["motstander"] for x in r} == {"VfL Bochum", "Hertha BSC"},
   f"riktige motstandere: {[x['motstander'] for x in r]}")

r = kampplan([kamp(2001, "2027-04-11", "13:30", "VfL Bochum"),
              kamp(2001, "2027-04-11", "13:30", "VfL Bochum")])
ok(len(r) == 1, f"ekte duplikat (samme matchId): en beholdt ({len(r)})")

r = kampplan([kamp(3001, "2027-04-11", "13:30", "VfL Bochum"),
              kamp(3001, "2027-04-10", "20:30", "VfL Bochum")])
ok(len(r) == 1, f"samme matchId paa to datoer gjenkjennes som en kamp ({len(r)})")

r = kampplan([kamp(None, "2027-04-11", "13:30", "VfL Bochum"),
              kamp(None, "2027-04-11", "13:30", "VfL Bochum")])
ok(len(r) == 1, f"uten matchId hindrer dato+motstander duplikat ({len(r)})")

# --------------------------------------------------------------------------
overskrift("Kampplanens form er den appen forventer")
r = kampplan([kamp(4001, "2027-04-11", "15:30", "VfL Bochum", hjemme=False)])
k = r[0]
ok(k["dato"] == "2027-04-11" and k["tid"] == "15:30", f"dato og tid: {k['dato']} {k['tid']}")
ok(k["matchId"] == 4001, "matchId folger med")
ok(k["hjemme"] is False, "hjemme/borte leses av lag-id, ikke navn")
ok(set(k) == {"matchId", "motstander", "dato", "tid", "turnering", "hjemme", "stadion"},
   f"feltene stemmer: {sorted(k)}")

overskrift("Tom respons gir tom liste, ikke krasj")
# Appen faller da tilbake paa KJENTE_KAMPER, og main() beholder forrige
# kampplan fra data.json.
ok(kampplan([]) == [], "ingen kamper -> tom liste")

# --------------------------------------------------------------------------
overskrift("Overskriften som ble feiloversatt")
# fcstpauli.com korter BAADE og:title og <title> ned. Et avkuttet
# fragment ga motsatt mening: "1. Frauen bezwingen" (de VANT 5-1) ble
# "Kvinnetap". Full tekst finnes bare i sidens egen <h1>.

doc = ('<html><head><title>1. Frauen bezwingen... | FC St. Pauli</title></head>'
       '<body><h1>1. Frauen bezwingen SV Meppen mit 5:1</h1></body></html>')
valgt = u.velg_tittel("FC St. Pauli | 1. Frauen bezwingen…", "", doc)
ok(valgt == "1. Frauen bezwingen SV Meppen mit 5:1", f"full overskrift valgt: {valgt!r}")

# Sikringen: en h1 som IKKE begynner med den kjente teksten velges aldri.
doc_feil = '<html><body><h1>Helt annen sak om billettsalg</h1></body></html>'
valgt = u.velg_tittel("FC St. Pauli | 1. Frauen bezwingen…", "", doc_feil)
ok(valgt == "1. Frauen bezwingen", f"fremmed h1 forkastes: {valgt!r}")

ok(u.rydd_tittel("FC St. Pauli | Noe skjer") == "Noe skjer", "klubbnavn som prefiks fjernes")
ok(u.rydd_tittel("Noe skjer | FC St. Pauli") == "Noe skjer", "klubbnavn som suffiks fjernes")
ok(u.rydd_tittel("1:1 in Hannover - FC St. Pauli jubelt") == "1:1 in Hannover - FC St. Pauli jubelt",
   "bindestrek midt i tittelen kappes ikke")
ok(u.rydd_tittel("Noe skjer…") == "Noe skjer", "avsluttende ellipse fjernes")
ok(u._samme_overskrift("kort", "kort og mer") is False, "for kort basis gir aldri treff")

# --------------------------------------------------------------------------
overskrift("Publiseringsdato")
# Brodteksten skriver gjerne "Ab dem heutigen Montag (19.10.)" uten
# aarstall, og det skal IKKE leses som publiseringsdato.
ok(u._publisert_fra_html('<span>19.10.26</span><span>13:55 Uhr</span>') == "2026-10-19T13:55",
   "dato + klokkeslett leses")
ok(u._publisert_fra_html('<p>Ab dem heutigen Montag (19.10.) gjelder</p>') == "",
   "dato uten aarstall i brodteksten ignoreres")
ok(u._publisert_fra_html('<span>32.13.26</span><span>13:55 Uhr</span>') == "",
   "ugyldig dato gir tom streng")
ok(u._publisert_fra_html("") == "", "tom HTML gir tom streng")

# --------------------------------------------------------------------------
overskrift("Oversettelses-cachen")
# Uten cache oversettes de samme titlene paa nytt tolv ganger daglig, og
# MyMemory-kvoten tar slutt - da faller alle titler tilbake til tysk.
gammel = {"fcstpauli_news": [{"title_de": "Sieg im Derby", "title_no": "Seier i derbyet"},
                             {"title_de": "Uoversatt", "title_no": "Uoversatt"}],
          "millernton_news": [{"title_de": "Neue Kurve", "title_no": "Ny sving"}]}
cache = u.bygg_oversettelses_cache(gammel)
ok(cache.get("Sieg im Derby") == "Seier i derbyet", "ferdig oversettelse gjenbrukes")
ok(cache.get("Neue Kurve") == "Ny sving", "begge nyhetskildene tas med")
ok("Uoversatt" not in cache,
   "mislykket oversettelse caches IKKE - ellers forsokes saken aldri igjen")
ok(u.bygg_oversettelses_cache({}) == {}, "tom data.json gir tom cache")

for n in ("gjenbrukt", "oversatt"):
    u._OVERSETT_TELLER[n] = 0
ok(u.translate_to_no("Sieg im Derby", cache) == "Seier i derbyet", "treff i cache brukes")
ok(u._OVERSETT_TELLER["gjenbrukt"] == 1 and u._OVERSETT_TELLER["oversatt"] == 0,
   "cachetreff teller som gjenbrukt, og ingen API-kall ble gjort")

print("\n" + (f"{FEIL} AVVIK" if FEIL else "Alle kontroller OK"))
sys.exit(1 if FEIL else 0)
