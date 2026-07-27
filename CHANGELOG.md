# Endringslogg — Partisan Lillestrøm App

## v2.1 — 27. juli 2026
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
