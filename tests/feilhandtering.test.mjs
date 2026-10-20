// At appen står når noe utenfor den svikter.
//
// Appen henter data.json fra GitHub Pages og Firebase-SDK-en fra
// gstatic.com, og lagrer navn og tipp i localStorage. Alle tre kan
// mangle: en workflow som har feilet, en blokkert CDN, privat
// nettlesermodus. Ingen av dem skal gi en hvit skjerm.

import { nyRapport, lagServer } from './felles.mjs';
import { startNettleser, apneApp } from './nettleser.mjs';

const t = nyRapport();
const browser = await startNettleser();

async function medData(svar, valg = {}) {
  const server = await lagServer({ overstyr: sti => (sti === '/data.json' ? svar : null) });
  const app = await apneApp(browser, server, valg);
  return { ...app, lukkAlt: async () => { await app.lukk(); server.lukk(); } };
}

t.overskrift('1. data.json mangler (404)');
{
  const { page, jsFeil, lukkAlt } = await medData(404);
  const r = await page.evaluate(() => ({
    nyheter: document.querySelectorAll('#fcstpauliNews .nc').length,
    kamper: typeof kamper2BL === 'function' ? kamper2BL().length : -1,
  }));
  t.ok(r.nyheter > 0, `statiske nyhetskort står igjen (${r.nyheter} kort)`);
  t.ok(r.kamper > 0, `kamper2BL() faller tilbake på KJENTE_KAMPER (${r.kamper} kamper)`);
  t.ok(jsFeil.length === 0, jsFeil[0] || 'ingen JS-feil');
  await lukkAlt();
}

t.overskrift('2. data.json er ugyldig JSON');
{
  const { page, jsFeil, lukkAlt } = await medData('{dette er ikke json');
  const r = await page.evaluate(() => ({
    nyheter: document.querySelectorAll('#fcstpauliNews .nc').length,
    kamper: kamper2BL().length,
  }));
  t.ok(r.nyheter > 0, 'appen står - statiske kort beholdes');
  t.ok(r.kamper > 0, 'kampplan faller tilbake');
  t.ok(jsFeil.length === 0, jsFeil[0] || 'ingen JS-feil');
  await lukkAlt();
}

t.overskrift('3. Riktig form, men tomme lister');
{
  const tom = JSON.stringify({ fcstpauli_news: [], millernton_news: [], next_match: {},
                               kampplan: [], kamplogg: [], medlemstall: {}, updated: '' });
  const { page, jsFeil, lukkAlt } = await medData(tom);
  const r = await page.evaluate(() => ({
    kamplogg: document.getElementById('matchList').textContent.trim().slice(0, 40),
    kamper: kamper2BL().length,
  }));
  t.ok(r.kamplogg.includes('Ingen kamper'), `kamplogg viser tom-melding: "${r.kamplogg}"`);
  t.ok(r.kamper > 0, 'tom kampplan ignoreres, fallback brukes');
  t.ok(jsFeil.length === 0, jsFeil[0] || 'ingen JS-feil');
  await lukkAlt();
}

t.overskrift('4. Felter av feil type');
{
  const rar = JSON.stringify({ fcstpauli_news: 'ikke en liste', millernton_news: null,
                               next_match: 'tekst', kampplan: { ikke: 'liste' },
                               kamplogg: 42, medlemstall: [], updated: 123 });
  const { page, jsFeil, lukkAlt } = await medData(rar);
  const r = await page.evaluate(() => ({ kamper: kamper2BL().length }));
  t.ok(r.kamper > 0, 'kampplan som objekt avvises av Array.isArray-sjekken');
  t.ok(jsFeil.length === 0, jsFeil[0] || 'ingen JS-feil');
  await lukkAlt();
}

t.overskrift('5. Firebase lastes ikke');
{
  const { page, jsFeil, lukkAlt } = await medData(null);
  const r = await page.evaluate(async () => {
    const fdbNull = typeof _fdb !== 'undefined' && _fdb === null;
    sp('arr'); await new Promise(r => setTimeout(r, 300));
    return { fdbNull, arrKort: document.querySelectorAll('#arrListe .card-bg').length };
  });
  t.ok(r.fdbNull, '_fdb er null når Firebase ikke lastes');
  t.ok(r.arrKort > 0, `arrangementer vises fra lokal fallback (${r.arrKort} kort)`);
  t.ok(jsFeil.length === 0, jsFeil[0] || 'ingen JS-feil');
  await lukkAlt();
}

t.overskrift('6. localStorage kaster (privat modus / blokkert)');
{
  const { page, jsFeil, lukkAlt } = await medData(null, { localStorageKaster: true });
  const r = await page.evaluate(async () => {
    const res = { lastet: !!document.getElementById('hjem') };
    try { sp('arr'); await new Promise(r => setTimeout(r, 250)); res.arrOk = true; }
    catch (e) { res.arrOk = false; res.arrFeil = e.message; }
    try { sp('tipping'); await new Promise(r => setTimeout(r, 400)); res.tippOk = true; }
    catch (e) { res.tippOk = false; res.tippFeil = e.message; }
    res.paameldKnapp = !!document.querySelector('.meld-btn');
    return res;
  });
  t.ok(r.lastet, 'appen laster');
  t.ok(r.arrOk, 'Arrangementer tåler at localStorage kaster' + (r.arrFeil ? ': ' + r.arrFeil : ''));
  t.ok(r.tippOk, 'Tipping tåler at localStorage kaster' + (r.tippFeil ? ': ' + r.tippFeil : ''));
  t.ok(r.paameldKnapp, 'påmeldingsknappen finnes fortsatt');
  // Feil fra service worker-registrering teller ikke: den avhenger av
  // hvilken MIME-type testtjeneren gir sw.js, ikke av appen.
  const ekte = jsFeil.filter(m => !/ServiceWorker/i.test(m));
  t.ok(ekte.length === 0, ekte.slice(0, 2).join(' | ') || 'ingen JS-feil');
  await lukkAlt();
}

await browser.close();
t.slutt();
