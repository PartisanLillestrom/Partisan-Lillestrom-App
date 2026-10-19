# Partisan Lillestrøm — medlemsapp

Webapp for medlemmene i Partisan Lillestrøm, norsk supporterklubb for
FC St. Pauli. Publisert som GitHub Pages fra `main`:
https://partisanlillestrom.github.io/Partisan-Lillestrom-App/

## Oppbygning

Appen er én enkelt HTML-fil, `index.html`, med CSS og JavaScript inline.
Ingen byggesteg og ingen avhengigheter å installere — filen lastes rett opp
og er i drift. Den henter data fra tre steder:

- **`data.json`** — nyheter, kampplan, kamplogg og medlemstall. Skrives av
  GitHub Actions, aldri manuelt.
- **Firebase Realtime Database** — alt medlemmene selv lager: arrangementer,
  påmeldinger, kommentarer, oppmøte, bildegalleri og kamptipping.
- **OpenLigaDB** — ligatabellen, hentet direkte fra nettleseren.

`sw.js` er service workeren som gjør appen installerbar som PWA.
`CACHE_VERSION` i den oppdateres automatisk av `update_data.py`, slik at
nettlesere henter nye filer etter en endring.

## Dataflyt (GitHub Actions)

| Workflow | Når | Hva den gjør |
|---|---|---|
| `update-data.yml` | ~12× daglig, 07–19 | Kjører `scripts/update_data.py`: nyheter fra Bluesky/RSS, oversettelse via MyMemory, kampplan fra OpenLigaDB, kamplogg fra Excel. Skriver `data.json` og bumper `sw.js`. |
| `resultater.yml` | Etter kamptider fre/lør/søn | Kjører `scripts/hent_resultater.py`: henter sluttresultater fra OpenLigaDB og skriver dem til Firebase under `kampresultater`. |
| `backup.yml` | Mandager 03:00 UTC | Kjører `scripts/backup_database.py`: full backup av Firebase, lastet opp som artifact med 90 dagers oppbevaring. |

De to siste trenger hemmeligheten `FIREBASE_SERVICE_ACCOUNT` (JSON-nøkkel
for en Google-tjenestekonto med skrivetilgang til databasen).

## Firebase-stier

| Sti | Innhold |
|---|---|
| `arrangementer/<id>` | Medlemsopprettede arrangementer |
| `arr_slettet/<id>` | Skjulte standardarrangementer |
| `rsvp/<arrId>/<navn>` | Påmeldinger |
| `komm/<arrId>/<kommId>` | Kommentarer |
| `oppmote/<kampId>/<navn>` | «Jeg var der» på kamploggen |
| `galleri/<id>` | Bilder (base64 i databasen) |
| `tipping/<kampId>/<navn>` | Kamptipp, `{h, b, ts}` |
| `kampresultater/<dato>` | Sluttresultater, nøklet på dato med `matchId` i raden |

Navn brukt som nøkkel går gjennom `_fbKey()` i `index.html`, som bytter ut
tegnene Firebase ikke tillater (`.#$[]/`).

Tippe-ID-en er `m<matchId>` fra OpenLigaDB, ikke datoen. DFL fastsetter
helgen for hele sesongen men dag og klokkeslett i bolker, så datoen er ikke
stabil — et tipp lagret under en dato som senere flyttes ville mistet
koblingen til resultatet. Appen leser fortsatt gamle dato-baserte nøkler.

Databasereglene ligger i `database-rules.json` og må holdes i synk med det
som faktisk er satt i Firebase-konsollen.

## Manuelle oppdateringer

- **Kamplogg:** rediger `Kamplogg FCSP.xlsx`. Kolonne A er en tellekolonne,
  dato i B, lagene i C og D, resultat i E, utfall i F. Leses fra rad 3.
- **Medlemstall:** `ANTALL_BETALENDE_MEDLEMMER` i `scripts/update_data.py`,
  oppdateres etter årsmøtet.
- **Stadionnavn:** `BORTE_STADION` i samme fil. Nøkkelen må være navnet
  OpenLigaDB bruker, som ikke alltid er lagets fulle navn.

## Lokal kjøring

```
python3 -m http.server 8000
```

Åpne `http://localhost:8000`. Firebase og OpenLigaDB treffes direkte, så
alt virker bortsett fra at service workeren vil cache aggressivt — bruk
hard refresh ved endringer.

For å kjøre datapipelinen lokalt: `pip install openpyxl` og
`python3 scripts/update_data.py`.
