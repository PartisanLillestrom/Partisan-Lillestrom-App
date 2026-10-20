#!/usr/bin/env python3
"""Lager testbildene bildekrymping.test.mjs bruker.

Bildene genereres i stedet for aa ligge i repoet: det storste er over
16 MB, og de er likevel bare stoy. Mappen tests/.bilder/ er i .gitignore.

Krever Pillow:  pip install --break-system-packages pillow
"""

import os
import sys

MAPPE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".bilder")

# (filnavn, bredde, hoyde, modus, kvalitet) - dekker de tilfellene som
# faktisk oppstaar: et absurd stort kamerabilde, et mobilbilde i begge
# retninger, et lite bilde som ikke skal krympes, og en PNG med
# gjennomsiktighet (som maa bli hvit, ikke svart, naar den blir JPEG).
#
# Kvaliteten er satt slik at filene holder seg under appens egen
# 25 MB-grense (GALLERI_MAKS_FIL). Et stoybilde paa 6000x4000 med
# quality=95 blir naermere 27 MB, og ville blitt avvist for krympingen -
# da hadde testen maalt noe appen aldri ser.
BILDER = [
    ("enorm_6000x4000.jpg",   6000, 4000, "RGB", 80),
    ("mobil_4032x3024.jpg",   4032, 3024, "RGB", 95),
    ("portrett_3024x4032.jpg", 3024, 4032, "RGB", 95),
    ("liten_800x600.jpg",      800,  600, "RGB", 95),
    ("gjennomsiktig.png",     1200, 1200, "RGBA", 0),
]


def main():
    try:
        from PIL import Image
    except ImportError:
        print("Pillow mangler. Installer med:\n"
              "  pip install --break-system-packages pillow", file=sys.stderr)
        return 1

    os.makedirs(MAPPE, exist_ok=True)
    for navn, b, h, modus, kvalitet in BILDER:
        sti = os.path.join(MAPPE, navn)
        if os.path.exists(sti):
            print(f"  finnes alt: {navn}")
            continue
        if modus == "RGBA":
            im = Image.new("RGBA", (b, h), (0, 0, 0, 0))
            # Et halvgjennomsiktig kryss, slik at flatingen mot hvit blir synlig
            pk = im.load()
            for x in range(b):
                for y in (x % h, (h - 1 - x) % h):
                    pk[x, y] = (255, 0, 0, 128)
            im.save(sti)
        else:
            # Stoy komprimerer daarlig, og det er med vilje: det gir
            # verste tilfelle for datastorrelsen etter krymping.
            im = Image.frombytes("RGB", (b, h), os.urandom(b * h * 3))
            im.save(sti, "JPEG", quality=kvalitet)
        print(f"  laget: {navn}  ({os.path.getsize(sti) / 1048576:.2f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
