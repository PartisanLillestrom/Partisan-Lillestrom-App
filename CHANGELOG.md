# Endringslogg — Partisan Lillestrøm App

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
