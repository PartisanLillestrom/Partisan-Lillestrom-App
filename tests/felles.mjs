// Felles hjelpere for testene. Appen er én enkelt index.html uten
// byggesteg og uten moduler, så testene plukker funksjonene de trenger
// rett ut av kildefila og kjører dem i en sandkasse. Det er litt uvanlig,
// men det holder testene fri for en kopi av koden som kan drifte fra
// originalen.

import fs from 'fs';
import http from 'node:http';
import path from 'path';
import { fileURLToPath } from 'url';

export const ROT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

export function lesKilde(fil = 'index.html') {
  return fs.readFileSync(path.join(ROT, fil), 'utf8');
}

// Henter kildeteksten til én funksjon. Forutsetter at funksjonen starter
// på kolonne 0 og avsluttes av en } på kolonne 0 - som er stilen i
// index.html. Kaster hvis navnet ikke finnes, slik at en omdøpt funksjon
// gir en tydelig feil i stedet for en test som stilltiende slutter å
// sjekke noe.
export function hentFunksjon(navn, kilde = lesKilde()) {
  const re = new RegExp('(?:^|\\n)(?:async )?function ' + navn + '\\([\\s\\S]*?\\n\\}', 'm');
  const m = kilde.match(re);
  if (!m) throw new Error(`fant ikke funksjonen ${navn}() i index.html`);
  return m[0] + '\n';
}

// Bygger en sandkasse med de oppgitte funksjonene. `forord` er kode som
// legges først (konstanter, variabler funksjonene leser).
export function sandkasse(navn, { forord = '', kilde = lesKilde() } = {}) {
  const kode = forord + '\n' + navn.map(n => hentFunksjon(n, kilde)).join('\n');
  return new Function(kode + `\nreturn { ${navn.join(', ')} };`)();
}

// --- Enkel rapportering -----------------------------------------------

export function nyRapport() {
  let feil = 0;
  return {
    overskrift(t) { console.log(`\n=== ${t} ===`); },
    ok(betingelse, melding) {
      if (betingelse) console.log('  OK    ' + melding);
      else { console.log('  FEIL  ' + melding); feil++; }
    },
    linje(t) { console.log('        ' + t); },
    get feil() { return feil; },
    slutt() {
      console.log(feil ? `\n${feil} AVVIK` : '\nAlle kontroller OK');
      process.exitCode = feil ? 1 : 0;
    },
  };
}

// --- Lokal HTTP-tjener ------------------------------------------------
// Appen må serveres over HTTP, ikke file://, fordi service workeren,
// fetch('data.json') og localStorage alle oppfører seg annerledes på
// file://.

const MIME = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript',
  '.json': 'application/json', '.css': 'text/css',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
  '.webp': 'image/webp', '.svg': 'image/svg+xml', '.ico': 'image/x-icon',
  '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
};

// `overstyr` lar en test svare noe annet enn fila for en gitt sti,
// f.eks. ugyldig JSON eller 404 for data.json.
export async function lagServer({ rot = ROT, overstyr = () => null } = {}) {
  const server = http.createServer((req, res) => {
    let u = decodeURIComponent(req.url.split('?')[0]);
    if (u === '/') u = '/index.html';

    const eget = overstyr(u);
    if (eget !== null && eget !== undefined) {
      if (eget === 404) { res.writeHead(404); return res.end('ikke funnet'); }
      res.writeHead(200, { 'Content-Type': MIME[path.extname(u)] || 'text/plain' });
      return res.end(eget);
    }

    const f = path.join(rot, u);
    if (!f.startsWith(rot) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) {
      res.writeHead(404); return res.end('ikke funnet');
    }
    res.writeHead(200, { 'Content-Type': MIME[path.extname(f)] || 'application/octet-stream' });
    fs.createReadStream(f).pipe(res);
  });
  await new Promise(r => server.listen(0, '127.0.0.1', r));
  return {
    port: server.address().port,
    get url() { return `http://127.0.0.1:${server.address().port}`; },
    lukk: () => server.close(),
  };
}
