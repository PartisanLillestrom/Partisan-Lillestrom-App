// At alle script-blokkene i index.html kommer helt gjennom.
//
// index.html har nøyaktig ni separate <script>-blokker. Kaster én av dem
// under innlasting, stopper bare den blokka - resten av appen ser helt
// normal ut, og funksjonene fra den blokka finnes rett og slett ikke.
// Det var slik Arrangementer sluttet å virke i privat nettlesermodus:
// et localStorage-kall kastet øverst i blokka, og alt under forsvant
// uten en feilmelding brukeren kunne se.
//
// Testen sjekker derfor at én funksjon fra hver blokk er definert, både
// normalt og med localStorage som kaster.

import { nyRapport, lagServer, lesKilde } from './felles.mjs';
import { startNettleser, apneApp } from './nettleser.mjs';

// Én representant per script-blokk
const FORVENTET = [
  'sp', 'spMeny', 'renderMatches',                    // kamplogg og navigasjon
  'lastTipping', 'kamper2BL', 'lagICS',               // tipping og kampplan
  'visArr', 'lagreArr',                               // arrangementer
  'renderNyheter', 'visKamp', 'oversettUrl', 'hentNesteKamp',  // nyheter og neste kamp
  'meldPaa', 'getRSVP', 'bekreftNavn', 'oppdaterRSVPVisning',  // påmelding
  'sendKommentar', 'oppdaterKommListe',               // kommentarer
  'lsGet', 'lsSet', 'lsDel',                          // lagringswrappere
];

const t = nyRapport();

const kilde = lesKilde();
const antallBlokker = (kilde.match(/<script(?![^>]*src=)/g) || []).length;
t.overskrift('Antall script-blokker');
t.ok(antallBlokker === 9, `${antallBlokker} inline script-blokker (ventet 9)`);

const server = await lagServer();
const browser = await startNettleser();

for (const localStorageKaster of [false, true]) {
  t.overskrift(localStorageKaster ? 'Med localStorage som kaster' : 'Normalt');
  const { page, jsFeil, lukk } = await apneApp(browser, server, { localStorageKaster, vent: 1800 });

  const mangler = await page.evaluate(
    navn => navn.filter(n => typeof window[n] !== 'function'), FORVENTET);
  t.ok(mangler.length === 0,
       mangler.length ? `funksjoner som IKKE ble definert: ${mangler.join(', ')}` : 'alle funksjoner definert');

  // Praktisk konsekvens: at fanene faktisk kan åpnes
  const virker = await page.evaluate(async () => {
    const res = {};
    for (const [navn, kall] of [['Arrangementer', 'arr'], ['Tipping', 'tipping'], ['Tabell', 'tabell']]) {
      try { sp(kall); await new Promise(r => setTimeout(r, 250)); res[navn] = 'ok'; }
      catch (e) { res[navn] = 'KRASJ: ' + e.message; }
    }
    return res;
  });
  for (const [navn, utfall] of Object.entries(virker)) {
    t.ok(utfall === 'ok', `${navn} kan åpnes: ${utfall}`);
  }

  const ekte = jsFeil.filter(m => !/ServiceWorker/i.test(m));
  t.ok(ekte.length === 0, ekte.slice(0, 2).join(' | ') || 'ingen JS-feil');
  await lukk();
}

await browser.close(); server.lukk();
t.slutt();
