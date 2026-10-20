// At data utenfra aldri havner i DOM-en som HTML.
//
// Alt i nyhetskortene kommer fra data.json, som bygges av scraping av
// fcstpauli.com og millernton.de. En overskrift med anførselstegn eller
// en < i den var nok til å bryte ut av attributtet; derfor går alle
// slike verdier gjennom esc(). Testen sjekker både esc() selv og at
// mønstrene som gjorde den nødvendig er borte fra kilden.

import { sandkasse, nyRapport, lesKilde } from './felles.mjs';

const kilde = lesKilde();
const F = sandkasse(['esc'], { kilde });
const t = nyRapport();

t.overskrift('esc() dekker de farlige tegnene');
t.ok(F.esc('<script>alert(1)</script>') === '&lt;script&gt;alert(1)&lt;/script&gt;', 'tagger');
t.ok(F.esc(`O'Neill`) === 'O&#39;Neill', 'apostrof');
t.ok(F.esc('5" skjerm') === '5&quot; skjerm', 'anførselstegn');
t.ok(F.esc('A & B') === 'A &amp; B', 'ampersand');
t.ok(F.esc(undefined) === 'undefined', 'undefined blir streng, ikke krasj');

t.overskrift('Nyhetskort: felter som tidligere stod uescapet');
const n = {
  title_no: `Kiezkicker "vant" <b>stort</b>`,
  title_de: `Kiezkicker 'gewannen' & mehr`,
};
const kort = `<div class="nt">${F.esc(n.title_no)}</div><div class="no">${F.esc(n.title_de)}</div>`;
t.ok(!kort.includes('<b>'), 'HTML i title_no blir inert');
t.ok(!/<div class="nt">[^<]*"/.test(kort), 'anførselstegn i tittel brøt ikke ut');
t.ok(kort.includes('&amp;'), 'ampersand escapet i title_de');
t.linje(kort);

t.overskrift('Kalenderknappen flettes ikke sammen som streng');
t.ok(!/onclick="lagICS\('\$\{/.test(kilde), 'onclick-attributt med flettede verdier er borte');
t.ok(/kalBtn\.addEventListener\('click'/.test(kilde), 'erstattet med addEventListener');
// Bekrefter at den gamle varianten faktisk var utsatt: et stadionnavn med
// anførselstegn lukket attributtet for tidlig.
const slemtStadion = `Stadion "Am Böllenfalltor"`;
const gammelFletting = `onclick="lagICS('${slemtStadion.replace(/'/g, "\\'")}')"`;
t.ok(gammelFletting.split('"').length > 3, 'gammel variant: anførselstegn brøt attributtet (bekreftet)');

t.overskrift('localStorage går gjennom wrapperne');
// Tre treff er wrapperne selv (lsGet/lsSet/lsDel). Flere betyr at et
// kallsted har sneket seg inn uten try/catch, og da krasjer appen i
// privat nettlesermodus.
const raa = (kilde.match(/localStorage\.(get|set|remove)Item/g) || []).length;
t.ok(/function lsGet\(/.test(kilde) && /function lsSet\(/.test(kilde) && /function lsDel\(/.test(kilde),
     'lsGet/lsSet/lsDel finnes');
t.ok(raa === 3, `${raa} direkte localStorage-kall (skal være 3: wrapperne selv)`);

t.overskrift('Tabell-cachen er tidsstyrt, ikke en engangssperre');
t.ok(/let _tabellHentetTs = 0;/.test(kilde), '_tabellLastet erstattet med tidsstempel');
t.ok(/if \(!force && _tabellHentetTs/.test(kilde), 'force=true overstyrer cachen');
t.ok(!/_tabellLastet/.test(kilde), 'ingen rester av den gamle sperren');

t.overskrift('Død kode');
for (const d of ['const LOGO=', 'let _tippLastet', '_origVisArr',
                 'partisan_page_change', 'oppdaterKommentarVisning']) {
  t.ok(!kilde.includes(d), `${d} er borte`);
}

t.slutt();
