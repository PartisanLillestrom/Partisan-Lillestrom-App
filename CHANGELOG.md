# Endringslogg — Partisan Lillestrøm App

## v2.5 — 20. oktober 2026
- **Tester:** Ni testsett lagt inn i `tests/` — tipping og omberamming, escaping, ICS mot RFC 5545, datapipelinen, resultathentingen, oppstart av alle script-blokker, navigasjon mellom alle sider, feilhåndtering når data.json/Firebase/localStorage svikter, og bildekrymping mot Firebase-grensen. Kjøres med `npm test`; ingen av dem går på nettet
- **Robusthet:** All bruk av localStorage går gjennom lsGet/lsSet/lsDel — appen krasjer ikke lenger i privat nettlesermodus eller når lagring er blokkert (Arrangementer sluttet å virke helt)
- **Retting:** Enter i navnefeltet under kommentarer bekrefter navnet i stedet for å sende en tom kommentar
- **Sikkerhet:** Firebase-tokenet sendes i Authorization-headeren i stedet for i adressen (hent_resultater.py, backup_database.py) — havner ikke lenger i tilgangslogger eller feilmeldinger
- **Pipeline:** hent_resultater.py bruker tysk tid for sesongberegning (likt update_data.py), fortsetter etter en feilet skriving og avslutter med feilkode slik at workflowen blir rød
- **Opprydding:** Fjernet død kode (partisan_page_change-lytter, oppdaterKommentarVisning), villedende inline display:none på #kamper
- **Småtteri:** Seksjonslenken peker på fcstpauli.com/fußball/aktuelles; favicon lagt inn (ga 404 i konsollen ved hver sidelasting)
- **Arbeidsflyt:** Resultathentingen kjører nå hver time hele uka. Tidligere dekket den bare fredag–søndag, og siste lørdagskjøring lå før kampslutt for 20:30-kamper — VfL Bochum 21.11 ville fått resultatet 16 timer senere, og midtukekamper to døgn senere. Nå er lengste ventetid 35 minutter.
- **Arbeidsflyt:** «Oppdater nyheter og kampdata» henter inn og prøver på nytt hvis noen pusher til main mens kjøringen er i gang (filopplasting i nettleseren gjorde tidligere kjøringen rød selv om oppdateringen var i orden)
- **Arbeidsflyt:** resultater.yml og backup.yml har fått `permissions: contents: read` — de trenger ikke skrivetilgang til repoet
- **Pipeline:** Duplikatfjerningen i kampplanen nøkler på matchId i stedet for dato. To runder DFL ennå ikke har fastsatt kan ligge på samme plassholderdato i OpenLigaDB, og en dato-nøkkel ville da kastet den ene kampen stille ut av både kampplan og tipping

## v2.4 — 16. oktober 2026
- **Ny funksjon:** Kamptipping — tipp resultat på 2. Bundesliga-kamper, poengberegning og toppliste
- **Navigasjon:** Bunnav: Hjem, Arr., Tabell, Tipping, ☰ Meny — Kamplogg flyttet til hamburgermeny

## v2.3 — 16. oktober 2026
- **Ny funksjon:** Hamburgermeny (☰) med Galleri, Logoer, Om oss og Bli medlem
- **Ny funksjon:** Tabell-fane med live 2. Bundesliga-tabell fra OpenLigaDB (St. Pauli-rad uthevet)
- **Ny funksjon:** Bildegalleri — last opp og vis bilder fra kamper og arrangementer (Firebase)
- **Ny funksjon:** «Legg til i kalender»-knapp (📅) på neste-kamp-stripen (genererer ICS-fil)
- **Navigasjon:** Bunnav redusert til 5 knapper: Hjem, Arr., Kamplogg, Tabell, ☰ Meny

## v2.2 — 16. oktober 2026
- **Pipeline:** OpenLigaDB som kilde for kampplan (erstatter upålitelig scraping av fcstpauli.com)
- **Pipeline:** Stadion-oppslag for bortekamper (OpenLigaDB mangler location-data)
- **Data:** KJENTE_KAMPER oppdatert med alle kamper oktober–desember 2026

## v2.1 — 28. juli 2026
- **Sikkerhet:** XSS-escaping på tittel, sted, beskrivelse og opprettet-av i arrangementkort
- **Sikkerhet:** Firebase databaseregler med feltvalidering og lengdebegrensninger
- **Feilretting:** Fjernet 40 linjer død nesteKampBox-kode
- **Feilretting:** Dobbel </button>-tag, foreldreløse </div>-tagger, «Bjorn» → «Bjørn»
- **Visuelt:** Gradient-kantlinje på filterknapper (Arrangementer)
- **Visuelt:** Varmere --grad-bg gradient som holder brunfargen lenger
- **Visuelt:** Opprett-skjema restylet med card-bg, grå kantlinje og gradient-topplinje
- **Ny funksjon:** Varselprikk på Arr.-fanen ved nye arrangementer
- **Ny funksjon:** Oppdater-knapp på Hjem-fanen for å hente ferske nyheter
- **Ny funksjon:** Nyhetslenker åpnes via Google Translate (tysk → norsk)
- **Pipeline:** Bluesky API som primærkilde for FC St. Pauli-nyheter (erstatter upålitelig scraping)
- **Meta:** Open Graph-tagger for Facebook-forhåndsvisning (regnbueskalle-ikon)

## v2.0 — Tidligere versjon
- Hero-seksjon med 15-årsjubileumslogo
- Statistikkvisning (år / medlemmer / kamper)
- Nyhetsfeeder fra fcstpauli.com og millernton.de
- Sticky «NESTE KAMP»-bar
- Arrangementer med RSVP og kommentarer (Firebase)
- Kamplogg med statistikk fra Excel
- Seks faner: Hjem, Arr., Kamplogg, Logoer, Om oss, Bli medlem
- GitHub Actions data-pipeline (nyheter, kampdata, oversettelse)
- PWA med manifest og service worker
