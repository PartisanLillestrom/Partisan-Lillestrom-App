// At et bilde fra mobilkameraet faktisk kommer under Firebase-grensen.
//
// Galleribildene lagres som base64 inne i databasen, og regelen tillater
// 2 000 000 tegn per bilde - altså ca. 1,43 MB originalfil. Appen tillot
// tidligere 5 MB, så alt mellom 1,43 og 5 MB feilet stille ved
// opplasting. Løsningen er å krympe i nettleseren før opplasting, og
// denne testen måler at det holder også i verste tilfelle.
//
// Bildene genereres av lag_testbilder.py (se README).

import fs from 'fs';
import path from 'path';
import { nyRapport, lesKilde, hentFunksjon, ROT, lagServer } from './felles.mjs';
import { startNettleser } from './nettleser.mjs';

const BILDER = path.join(ROT, 'tests', '.bilder');
if (!fs.existsSync(BILDER) || fs.readdirSync(BILDER).length === 0) {
  console.error('\nTestbildene mangler. Lag dem med:\n'
    + '  python3 tests/lag_testbilder.py\n');
  process.exit(2);
}

const kilde = lesKilde();
const konstanter = kilde.match(/const GALLERI_MAKS_PX[\s\S]*?const GALLERI_MAKS_FIL = [^;]+;/)[0];
const kode = konstanter + '\n' + hentFunksjon('krympBilde', kilde);

const MAKS_TEGN = Number(konstanter.match(/GALLERI_MAKS_TEGN = (\d+)/)[1]);
const MAKS_PX = Number(konstanter.match(/GALLERI_MAKS_PX = (\d+)/)[1]);

// Bildene serveres over HTTP. Å sende dem som byte-arrayer gjennom
// page.evaluate() sprengte minnet - hver byte ble et JS-tall.
const server = await lagServer({ rot: BILDER, overstyr: sti =>
  (sti === '/index.html' ? '<!doctype html><html><body></body></html>' : null) });

const browser = await startNettleser();
const page = await browser.newPage();
await page.goto(`${server.url}/`, { waitUntil: 'load' });
await page.addScriptTag({ content: kode + '\nwindow.krympBilde = krympBilde;' });

const t = nyRapport();
t.overskrift(`Krymping (grense ${MAKS_TEGN.toLocaleString('nb-NO')} tegn, maks ${MAKS_PX} px)`);
console.log('  ' + 'fil'.padEnd(26) + 'inn'.padStart(10) + 'ut'.padStart(10)
            + 'data-URL'.padStart(13) + 'px'.padStart(12));
console.log('  ' + '-'.repeat(71));

for (const f of fs.readdirSync(BILDER).sort()) {
  const inn = fs.statSync(path.join(BILDER, f)).size;
  const res = await page.evaluate(async ({ fil, url }) => {
    const blob = await (await fetch(`${url}/${encodeURIComponent(fil)}`)).blob();
    const file = new File([blob], fil, { type: blob.type });
    try {
      const u = await window.krympBilde(file);
      const im = new Image();
      await new Promise(r => { im.onload = r; im.onerror = r; im.src = u; });
      return { ok: true, len: u.length, w: im.naturalWidth, h: im.naturalHeight,
               jpeg: u.startsWith('data:image/jpeg') };
    } catch (e) { return { ok: false, msg: e.message }; }
  }, { fil: f, url: server.url });

  if (!res.ok) { t.ok(false, `${f}: krympBilde() feilet - ${res.msg}`); continue; }

  const utBytes = Math.round(res.len * 3 / 4);
  const innenfor = res.len <= MAKS_TEGN;
  const pxOk = Math.max(res.w, res.h) <= MAKS_PX;
  console.log('  ' + f.padEnd(26)
    + (inn / 1048576).toFixed(2).padStart(8) + ' MB'
    + (utBytes / 1024).toFixed(0).padStart(7) + ' kB'
    + res.len.toLocaleString('nb-NO').padStart(13)
    + `${res.w}x${res.h}`.padStart(12));
  t.ok(innenfor && pxOk && res.jpeg,
       `${f}: tegn=${innenfor ? 'ok' : 'FOR STOR'} px=${pxOk ? 'ok' : 'FOR STOR'} jpeg=${res.jpeg}`);
}

t.overskrift('Udekodbar fil gir forståelig feil');
const melding = await page.evaluate(async () => {
  const file = new File([new Uint8Array([0, 1, 2, 3, 4, 5, 6, 7])], 'x.heic', { type: 'image/heic' });
  try { await window.krympBilde(file); return '(ingen feil - uventet)'; } catch (e) { return e.message; }
});
t.ok(melding === 'format', `kaster "${melding}" slik opplasteren kan si "ukjent format"`);

await browser.close(); server.lukk();
t.slutt();
