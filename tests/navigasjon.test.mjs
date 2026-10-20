// At hver side faktisk blir synlig når man navigerer til den, og at bare
// én er synlig om gangen.
//
// Sidene byttes ved å flytte klassen .active. En etterlatt inline
// display:none, eller en side som mangler i CSS-regelen, gir en fane som
// ser ut som den virker i koden men er tom på skjermen. Det er ikke noe
// en enhetstest fanger - det må måles i en ekte nettleser.

import { nyRapport, lagServer } from './felles.mjs';
import { startNettleser, apneApp } from './nettleser.mjs';

const t = nyRapport();
const server = await lagServer();
const browser = await startNettleser();
// slippFirebase: vi vil se at appen ikke roter det til når SDK-en er
// lastet, selv om selve databasekallene blokkeres.
const { page, jsFeil, lukk } = await apneApp(browser, server, { slippFirebase: true, vent: 2500 });

const konsollfeil = [];
page.on('console', m => {
  if (m.type() === 'error' && !/favicon|firebase|net::ERR/i.test(m.text())) {
    konsollfeil.push(m.text().slice(0, 140) + '  <- ' + (m.location().url || '?'));
  }
});

t.overskrift('Blir hver side synlig?');
const sider = [
  ['hjem', "sp('hjem')"], ['arr', "sp('arr')"], ['tabell', "sp('tabell')"],
  ['tipping', "sp('tipping')"], ['kamper', "spMeny('kamper')"], ['galleri', "spMeny('galleri')"],
  ['logoer', "spMeny('logoer')"], ['om', "spMeny('om')"], ['medlem', "spMeny('medlem')"],
];
for (const [id, kall] of sider) {
  const r = await page.evaluate(async ({ id, kall }) => {
    eval(kall);
    await new Promise(r => setTimeout(r, 120));
    const el = document.getElementById(id);
    const cs = getComputedStyle(el);
    const boks = el.getBoundingClientRect();
    return {
      aktiv: el.classList.contains('active'),
      display: cs.display,
      inline: el.style.display || '(ingen)',
      synlig: boks.width > 0 && boks.height > 0,
      hoyde: Math.round(boks.height),
    };
  }, { id, kall });
  t.ok(r.synlig && r.display !== 'none',
       `${id.padEnd(8)} active=${r.aktiv} computed=${r.display.padEnd(6)} inline=${String(r.inline).padEnd(7)} h=${r.hoyde}px`);
}

t.overskrift('Bare én side synlig om gangen');
const synlige = await page.evaluate(() =>
  [...document.querySelectorAll('.page')].filter(p => getComputedStyle(p).display !== 'none').map(p => p.id));
t.ok(synlige.length === 1, `synlige sider: ${JSON.stringify(synlige)}`);

t.overskrift('Bunnmenyen markerer riktig knapp');
const nav = await page.evaluate(async () => {
  [...document.querySelectorAll('.bb')][0].click();
  await new Promise(r => setTimeout(r, 120));
  return {
    aktive: [...document.querySelectorAll('.bb.active')].length,
    hjemSynlig: getComputedStyle(document.getElementById('hjem')).display !== 'none',
  };
});
t.ok(nav.aktive === 1, `${nav.aktive} knapp(er) markert aktiv`);
t.ok(nav.hjemSynlig, 'hjem vises etter klikk på Hjem');

t.overskrift('JS-feil underveis');
t.ok(jsFeil.length === 0, jsFeil.slice(0, 3).join(' | ') || 'ingen');
t.ok(konsollfeil.length === 0, konsollfeil.slice(0, 3).join('\n        ') || 'ingen console.error');

await lukk(); await browser.close(); server.lukk();
t.slutt();
