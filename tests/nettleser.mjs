// Nettleser-hjelpere. Skilt ut fra felles.mjs slik at de rene
// JS-testene (tipping, escaping, kalender) kan kjøres uten Playwright
// installert.

import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

// --- Finn en Chromium å kjøre i --------------------------------------------------------

function finnChromium() {
  if (process.env.PARTISAN_CHROMIUM) return process.env.PARTISAN_CHROMIUM;
  try {
    const p = chromium.executablePath();
    if (p && fs.existsSync(p)) return p;
  } catch { /* playwright vet ikke hvor den er - vi leter selv */ }

  const baser = [
    process.env.PLAYWRIGHT_BROWSERS_PATH,
    '/opt/pw-browsers',
    path.join(process.env.HOME || '', '.cache/ms-playwright'),
    path.join(process.env.LOCALAPPDATA || '', 'ms-playwright'),
  ].filter(Boolean);
  const relative = [
    'chrome-linux/chrome',
    'chrome-mac/Chromium.app/Contents/MacOS/Chromium',
    'chrome-mac-arm64/Chromium.app/Contents/MacOS/Chromium',
    'chrome-win/chrome.exe',
  ];
  for (const b of baser) {
    if (!fs.existsSync(b)) continue;
    for (const d of fs.readdirSync(b)) {
      const direkte = path.join(b, d);
      if (fs.statSync(direkte).isFile() && /^chrom/i.test(d)) return direkte;
      for (const rel of relative) {
        const f = path.join(direkte, rel);
        if (fs.existsSync(f)) return f;
      }
    }
  }
  return null;
}

export async function startNettleser() {
  const exe = finnChromium();
  try {
    return await chromium.launch(exe ? { executablePath: exe } : {});
  } catch (e) {
    console.error(
      '\nFant ingen Chromium å kjøre testene i.\n' +
      'Installer den med:  npx playwright install chromium\n' +
      'eller sett PARTISAN_CHROMIUM til stien for en egen Chromium.\n' +
      `(underliggende feil: ${e.message.split('\n')[0]})\n`
    );
    process.exit(2);
  }
}

// Åpner appen i en ny fane. `blokkerNett` hindrer at testene treffer
// fcstpauli.com, Firebase og OpenLigaDB - vi tester appen, ikke nettet.
export async function apneApp(browser, server, {
  blokkerNett = true,
  slippFirebase = false,
  localStorageKaster = false,
  vent = 2200,
} = {}) {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await ctx.newPage();
  const jsFeil = [];
  page.on('pageerror', e => jsFeil.push(e.message));

  if (localStorageKaster) {
    await page.addInitScript(() => {
      const kast = () => { throw new DOMException('Access denied', 'SecurityError'); };
      Object.defineProperty(window, 'localStorage', {
        configurable: true,
        get() {
          return { getItem: kast, setItem: kast, removeItem: kast, clear: kast, key: kast, length: 0 };
        },
      });
    });
  }

  if (blokkerNett) {
    await page.route('**', r => {
      const u = r.request().url();
      if (u.includes('127.0.0.1')) return r.continue();
      if (slippFirebase && u.includes('gstatic.com/firebasejs')) return r.continue();
      return r.abort();
    });
  }

  await page.goto(`${server.url}/index.html`, { waitUntil: 'domcontentloaded' }).catch(() => {});
  await page.waitForTimeout(vent);
  return { page, ctx, jsFeil, lukk: () => ctx.close() };
}
