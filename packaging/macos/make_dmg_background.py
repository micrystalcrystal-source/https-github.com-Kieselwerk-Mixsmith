# -*- coding: utf-8 -*-
"""Background of the macOS disk image in Kieselwerk style (660 x 400 pt, plus @2x).

  python packaging/macos/make_dmg_background.py

Needs the Kieselwerk logo package (KIESELWERK_LOGOS, default: Desktop/Kieselwerk/Kieselwerk_Logopaket)."""
import os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
LOGOS = os.environ.get("KIESELWERK_LOGOS", os.path.join(os.path.expanduser("~"), "Desktop", "Kieselwerk", "Kieselwerk_Logopaket"))
SAND, PETROL, GRAPHIT, KIESEL = (239, 235, 228), (37, 108, 112), (31, 36, 34), (168, 161, 150)

def make(k):
    w, h = 660*k, 400*k
    pat = Image.open(os.path.join(LOGOS, "09_Muster_Hoehenlinien", "muster_petrol-auf-sand.png")).convert("RGB")
    s = max(w/pat.width, h/pat.height)
    bg = pat.resize((round(pat.width*s), round(pat.height*s)), Image.LANCZOS).crop((0, 0, w, h)).convert("RGBA")
    veil = Image.new("RGBA", (w, h), SAND+(200,)); bg = Image.alpha_composite(bg, veil)       # lines stay faint (about 20 %)
    d = ImageDraw.Draw(bg)
    mono = ImageFont.truetype(os.path.join(LOGOS, "10_Schriften", "IBMPlexMono-Medium.ttf"), 12*k)
    sans = ImageFont.truetype(os.path.join(LOGOS, "10_Schriften", "SchibstedGrotesk-SemiBold.ttf"), 22*k)
    d.text((w//2, 46*k), "MIXSMITH INSTALLIEREN", font=mono, fill=PETROL, anchor="mm")
    d.text((w//2, 78*k), "In den Programme-Ordner ziehen", font=sans, fill=GRAPHIT, anchor="mm")
    y = 205*k; d.line((250*k, y, 410*k, y), fill=KIESEL, width=2*k)                            # arrow between app (165) and Applications (495)
    d.polygon([(410*k, y-8*k), (424*k, y), (410*k, y+8*k)], fill=KIESEL)
    kw = Image.open(os.path.join(LOGOS, "01_Logo_horizontal", "kieselwerk_logo_horizontal_positiv.png")).convert("RGBA")
    lw = 120*k; ki = kw.resize((lw, round(kw.height*lw/kw.width)), Image.LANCZOS)
    bg.alpha_composite(ki, ((w-lw)//2, 352*k-ki.height//2))
    return bg.convert("RGB")

make(1).save(os.path.join(HERE, "dmg_background.png"))
make(2).save(os.path.join(HERE, "dmg_background@2x.png"))
print("ok")
