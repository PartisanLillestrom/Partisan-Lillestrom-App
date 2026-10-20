# Tester

Appen er én enkelt `index.html` uten byggesteg. Testene plukker derfor
funksjonene de trenger rett ut av kildefila og kjører dem i en sandkasse,
i stedet for å holde en kopi av koden som kan drifte fra originalen. Er en
funksjon omdøpt, feiler testen med navnet sitt — det er med vilje.

## Kjøre dem

```bash
npm install                 # henter Playwright (bare første gang)
npx playwright install chromium

npm test                    # alt
npm run test:rask           # bare det som ikke trenger nettleser
node tests/tipping.test.mjs # én enkelt test
```

`--rask` hopper over de fire nettlesertestene. De tre rene JS-testene og
Python-testene trenger bare `node` og `python3`, og tar under et sekund.

Finner ikke Playwright sin Chromium seg selv, kan stien oppgis:

```bash
PARTISAN_CHROMIUM=/sti/til/chrome npm test
```

Ingen test går på nettet. Alt utenfor appen — `fcstpauli.com`,
`millernton.de`, Firebase, OpenLigaDB, MyMemory — blokkeres eller byttes
ut med attrapper, så testene gir samme svar uansett hva som skjer ute.

## Hva de dekker

| Test | Trenger nettleser | Dekker |
|---|---|---|
| `test_update_data.py` | nei | Duplikatfjerning på `matchId`, kampplanens form, overskriftsvalget som ga feiloversettelser, publiseringsdato, oversettelses-cachen |
| `test_hent_resultater.py` | nei | Token i header og ikke i adressen, at én feilet skriving ikke stopper de øvrige, exitkode, at begge skript regner sesongen likt |
| `tipping.test.mjs` | nei | Tippenøkkel på `matchId`, omberamming, dobbelttelling, poengberegning |
| `escaping.test.mjs` | nei | `esc()` på data utenfra, at `localStorage` bare nås gjennom wrapperne, at død kode er borte |
| `kalender.test.mjs` | nei | ICS mot RFC 5545: escaping, UID, DTSTAMP, 75-oktetters linjer, døgn- og månedsskifte |
| `oppstart.test.mjs` | ja | At alle ni script-blokker kommer gjennom, også når `localStorage` kaster |
| `navigasjon.test.mjs` | ja | At hver av de ni sidene blir synlig, og bare én om gangen |
| `feilhandtering.test.mjs` | ja | `data.json` mangler, er ugyldig, er tom eller har feil typer; Firebase utilgjengelig; `localStorage` blokkert |
| `bildekrymping.test.mjs` | ja | At et 15 MB mobilbilde kommer under Firebase-grensen på 2 000 000 tegn |

## Testbildene

`bildekrymping.test.mjs` trenger noen store bilder. De genereres i stedet
for å ligge i repoet — det største er over 15 MB, og de er likevel bare
støy:

```bash
python3 tests/lag_testbilder.py     # krever pillow
```

De havner i `tests/.bilder/`, som er i `.gitignore`. `kjor_alle.sh` lager
dem selv hvis de mangler.

Støy er valgt med vilje: den komprimerer dårligst og gir derfor verste
tilfelle for hvor stor data-URL-en blir etter krymping.

## Hvorfor en ekte nettleser

Fire av testene starter Chromium. Det er tyngre enn en enhetstest, men de
måler ting ingen enhetstest ser:

- En side kan ha riktig klasse i DOM-en og likevel være usynlig, fordi en
  etterlatt `display:none` overstyrer CSS-regelen.
- Kaster et `localStorage`-kall øverst i en script-blokk, forsvinner alt
  under det i blokka — uten feilmelding brukeren kan se. Det var slik
  Arrangementer sluttet å virke i privat nettlesermodus.
- Bildekrympingen bruker `createImageBitmap`, `canvas` og
  `toDataURL`. Hvor stor fila faktisk blir kan bare måles, ikke regnes ut.

## Når noe feiler

Testene skriver én linje per kontroll og avslutter med `Alle kontroller
OK` eller antall avvik. Exitkoden er 1 ved avvik, så de kan brukes
direkte i en GitHub Actions-workflow.

Feiler en test etter en endring i `index.html`, er det verdt å sjekke om
det er appen eller forventningen som er utdatert — flere av kontrollene
beskriver en feil som faktisk oppstod, og kommentaren over hver bolk sier
hvilken.
