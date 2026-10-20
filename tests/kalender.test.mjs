// «Legg til i kalender»-knappen: at ICS-fila følger RFC 5545.
//
// En ICS-fil som ser riktig ut kan likevel avvises stille av Google
// Calendar og iOS. De tre fellene her er uescapede komma i LOCATION,
// manglende UID/DTSTAMP, og linjer over 75 oktetter. UID-en er bygget på
// matchId, slik at en omberammet kamp oppdaterer den eksisterende
// kalenderoppføringen i stedet for å lage en ny ved siden av.

import { nyRapport, lesKilde, hentFunksjon } from './felles.mjs';

const kilde = lesKilde();
// lagICS() laster ned fila til slutt; vi bytter den delen med en retur
// slik at vi får teksten i stedet.
const kode = hentFunksjon('icsTekst', kilde) + hentFunksjon('icsFold', kilde)
  + hentFunksjon('lagICS', kilde)
      .replace(/const blob[\s\S]*?URL\.revokeObjectURL\(a\.href\);/, 'return ics;');
const F = new Function(kode + '\nreturn { lagICS, icsTekst, icsFold };')();

const t = nyRapport();

t.overskrift('ICS for en bortekamp');
const ics = F.lagICS('SV Darmstadt 98', '2026-10-23', '18:30',
                     'Merck-Stadion am Böllenfalltor, Darmstadt', false, 83648);
for (const l of ics.split('\r\n').filter(Boolean)) t.linje(l);

t.overskrift('RFC 5545');
const linjer = ics.split('\r\n').filter(Boolean);
const finn = p => linjer.find(l => l.startsWith(p));
t.ok(/LOCATION:.*\\,/.test(finn('LOCATION:')), 'komma i LOCATION er escapet som \\,');
t.ok(!/[^\\],/.test(finn('LOCATION:')), 'ingen uescapede komma igjen');
t.ok(!!finn('UID:'), `UID finnes: ${finn('UID:')}`);
t.ok(/^DTSTAMP:\d{8}T\d{6}Z$/.test(finn('DTSTAMP:') || ''), 'DTSTAMP finnes og er i UTC-format');
t.ok(linjer.every(l => new TextEncoder().encode(l).length <= 75), 'alle linjer <= 75 oktetter');
t.ok(linjer[0] === 'BEGIN:VCALENDAR' && linjer[linjer.length - 1] === 'END:VCALENDAR', 'korrekt ramme');
t.ok(ics.endsWith('\r\n'), 'filen avsluttes med CRLF');

t.overskrift('Sluttid ruller over døgnet');
for (const [tid, forventet] of [['13:30', '20261023T153000'], ['20:30', '20261023T223000'],
                                ['22:30', '20261024T003000'], ['23:30', '20261024T013000']]) {
  const i = F.lagICS('X', '2026-10-23', tid, '', true, 1);
  const dtend = i.split('\r\n').find(l => l.startsWith('DTEND')).split(':')[1];
  t.ok(dtend === forventet, `avspark ${tid} -> DTEND ${dtend}`);
}
const mnd = F.lagICS('X', '2026-10-31', '23:00', '', true, 1);
t.ok(mnd.includes('DTEND;TZID=Europe/Berlin:20261101T010000'),
     'månedsskifte: 31.10 kl 23:00 -> 01.11 kl 01:00');

t.overskrift('UID er stabil gjennom omberamming');
const a = F.lagICS('SV Darmstadt 98', '2026-10-23', '18:30', '', false, 83648);
const b = F.lagICS('SV Darmstadt 98', '2026-10-24', '15:30', '', false, 83648);
const uidA = a.split('\r\n').find(l => l.startsWith('UID:'));
t.ok(uidA === b.split('\r\n').find(l => l.startsWith('UID:')),
     `samme UID etter flytting (${uidA}) - kalenderen oppdaterer i stedet for å duplisere`);
const utenId = F.lagICS('SV Darmstadt 98', '2026-10-23', '18:30', '', false, null);
t.ok(/UID:kamp-2026-10-23-SVDarmstadt98@/.test(utenId), 'uten matchId: UID bygges av dato og motstander');

t.overskrift('Escaping av spesialtegn');
t.ok(F.icsTekst('a,b') === 'a\\,b', 'komma');
t.ok(F.icsTekst('a;b') === 'a\\;b', 'semikolon');
t.ok(F.icsTekst('a\\b') === 'a\\\\b', 'backslash');
t.ok(F.icsTekst('a\nb') === 'a\\nb', 'linjeskift');
t.ok(F.icsTekst(null) === '', 'null -> tom streng');

t.overskrift('Folding deler ikke multibyte-tegn');
const lang = F.icsFold('LOCATION:' + 'ø'.repeat(60));
const deler = lang.split('\r\n ');
t.ok(deler.length > 1, `lang linje ble foldet i ${deler.length} deler`);
t.ok(deler.join('') === 'LOCATION:' + 'ø'.repeat(60), 'innholdet er uendret etter folding');
t.ok(!lang.includes('�'), 'ingen ødelagte tegn (U+FFFD)');

t.slutt();
