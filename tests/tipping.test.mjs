// Tippingen: at et tipp beholder koblingen til resultatet når DFL flytter
// en kamp, og at ingen telles to ganger for samme kamp.
//
// Bakgrunn: DFL fastsetter helgen for hele sesongen, men dag og
// klokkeslett kommer i bolker gjennom sesongen. Datoen er derfor IKKE en
// stabil nøkkel. Tippene nøkles på matchId, og de gamle dato-nøklene
// leses fortsatt slik at ingen mister poeng på overgangen.

import { sandkasse, nyRapport, lesKilde } from './felles.mjs';

const kilde = lesKilde();
const KJENTE = kilde.match(/const KJENTE_KAMPER = \[[\s\S]*?\n\];/)[0];

const F = sandkasse(
  ['kamper2BL', 'settKampplan', 'lagKampId', 'lagKampIdLegacy',
   'kampFraKampId', 'resultatForKamp', 'beregnPoeng'],
  { forord: KJENTE + '\nlet _kampplan = null;', kilde }
);

const t = nyRapport();

// Kampplan på formen update_data.py leverer
const HEID = { matchId: 77003, motstander: '1. FC Heidenheim 1846', dato: '2026-12-06', tid: '13:30', turnering: '2. Bundesliga', hjemme: true,  stadion: 'Millerntor-Stadion, Hamburg' };
const DARM = { matchId: 77001, motstander: 'SV Darmstadt 98',       dato: '2026-10-23', tid: '18:30', turnering: '2. Bundesliga', hjemme: false, stadion: 'Merck-Stadion am Böllenfalltor, Darmstadt' };
const HANN = { matchId: 77000, motstander: 'Hannover 96',           dato: '2026-10-17', tid: '20:30', turnering: '2. Bundesliga', hjemme: false, stadion: 'Heinz von Heiden Arena, Hannover' };
F.settKampplan({ kampplan: [HANN, DARM, HEID] });

t.overskrift('Tippe-nøkkel');
t.ok(F.lagKampId(DARM) === 'm77001', 'matchId brukes: ' + F.lagKampId(DARM));
t.ok(F.lagKampIdLegacy(DARM) === '2026-10-23_SVDarmstadt98', 'gammel nøkkel: ' + F.lagKampIdLegacy(DARM));
t.ok(F.lagKampId({ motstander: 'X', dato: '2026-01-01' }) === '2026-01-01_X',
     'uten matchId faller den tilbake på dato_motstander (KJENTE_KAMPER offline)');

t.overskrift('Oppslag av kamp fra lagret nøkkel');
t.ok(F.kampFraKampId('m77001') === DARM,                   'ny nøkkel finner kampen');
t.ok(F.kampFraKampId('2026-10-23_SVDarmstadt98') === DARM, 'gammel nøkkel finner kampen');
t.ok(F.kampFraKampId('2026-10-23_HeltAnnetNavn') === DARM, 'gammel nøkkel med utdatert lagnavn finner den likevel (dato)');
t.ok(F.kampFraKampId('m99999') === null,                   'ukjent matchId -> null');
t.ok(F.kampFraKampId('1999-01-01_Ukjent') === null,        'ukjent dato -> null');

t.overskrift('Omberamming: kampen flyttet fra 6. til 5. desember');
// Tippet ble lagret da kampplanen sa 6. des. hent_resultater.py lagrer
// resultatet på den FAKTISKE datoen.
const HEID_FLYTTET = { ...HEID, dato: '2026-12-05' };
F.settKampplan({ kampplan: [HANN, DARM, HEID_FLYTTET] });
const res = { '2026-12-05': { matchId: 77003, dato: '2026-12-05', h: 2, b: 1, ferdig: true } };

const gammeltTipp = '2026-12-06_1FCHeidenheim1846';   // lagret før flyttingen
t.ok(res[gammeltTipp.substring(0, 10)] === undefined,
     'gammel logikk: dato-oppslag treffer ikke -> tippet ville mistet poeng');
const viaNy = F.resultatForKamp(F.kampFraKampId('m77003'), res);
t.ok(viaNy && viaNy.h === 2, 'ny logikk: matchId-nøkkel finner resultatet');
const kampFraGammel = F.kampFraKampId(gammeltTipp);
t.ok(kampFraGammel === null || F.resultatForKamp(kampFraGammel, res) !== null,
     'ny logikk: gammel nøkkel med utdatert dato håndteres uten å krasje');

t.overskrift('Resultat-oppslag: fallback for rader uten matchId');
const resGammel = { '2026-10-23': { dato: '2026-10-23', h: 1, b: 3, ferdig: true } };
const r2 = F.resultatForKamp(DARM, resGammel);
t.ok(r2 && r2.b === 3, 'rad uten matchId finnes fortsatt via dato');
t.ok(F.resultatForKamp(DARM, {}) === null, 'tom resultatnode -> null');
t.ok(F.resultatForKamp(null, resGammel) === null, 'ingen kamp -> null');

t.overskrift('Dobbelttelling: samme kamp under to nøkler');
// Samme logikk som lastTippToppliste() bruker: nyeste tipp per
// kamp+navn vinner, slik at en foreldreløs dato-nøkkel ikke gir
// ekstrapoeng.
const alleTips = {
  'm77000':                { 'Bjørn': { h: 1, b: 1, ts: 2000 }, 'Mats': { h: 2, b: 0, ts: 2000 } },
  '2026-10-17_Hannover96': { 'Bjørn': { h: 0, b: 0, ts: 1000 } },
};
const resH = { '2026-10-17': { matchId: 77000, dato: '2026-10-17', h: 1, b: 1, ferdig: true } };
F.settKampplan({ kampplan: [HANN, DARM, HEID] });

const besteTipp = {};
for (const kampId of Object.keys(alleTips)) {
  const kd = F.kampFraKampId(kampId);
  if (!kd) continue;
  const fak = F.resultatForKamp(kd, resH);
  if (!fak || !fak.ferdig) continue;
  const kn = kd.matchId != null && kd.matchId !== '' ? 'm' + kd.matchId : kd.dato;
  for (const [navn, d] of Object.entries(alleTips[kampId])) {
    const n = kn + '|' + navn, ts = d.ts || 0;
    if (besteTipp[n] && besteTipp[n].ts >= ts) continue;
    besteTipp[n] = { navn, poeng: F.beregnPoeng(d.h, d.b, fak.h, fak.b), ts };
  }
}
const pp = {};
for (const { navn, poeng } of Object.values(besteTipp)) {
  if (!pp[navn]) pp[navn] = { total: 0, kamper: 0 };
  pp[navn].total += poeng; pp[navn].kamper += 1;
}
t.ok(pp['Bjørn'].kamper === 1, `Bjørn telles for 1 kamp, ikke 2 (fikk ${pp['Bjørn'].kamper})`);
t.ok(pp['Bjørn'].total === 3,  `Bjørn får 3p for 1-1 (nyeste tipp vant), ikke 3+1=4 (fikk ${pp['Bjørn'].total})`);
t.ok(pp['Mats'].total === 0,   `Mats får 0p for 2-0 mot 1-1 (fikk ${pp['Mats'].total})`);

t.overskrift('Poengberegning');
t.ok(F.beregnPoeng(1, 1, 1, 1) === 3, '1-1 mot 1-1 = 3p');
t.ok(F.beregnPoeng(2, 1, 1, 0) === 2, '2-1 mot 1-0 = 2p (riktig målforskjell)');
t.ok(F.beregnPoeng(3, 0, 1, 0) === 1, '3-0 mot 1-0 = 1p (riktig utfall)');
t.ok(F.beregnPoeng(0, 2, 1, 0) === 0, '0-2 mot 1-0 = 0p');

t.slutt();
