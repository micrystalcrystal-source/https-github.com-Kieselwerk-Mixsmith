# -*- coding: utf-8 -*-
"""Wizard pictures of the Windows installer in Kieselwerk style (petrol, sand contour lines, Mixsmith icon, Kieselwerk logo).

  python packaging/windows/make_wizard_images.py

Needs the Kieselwerk logo package (KIESELWERK_LOGOS, default: Desktop/Kieselwerk/Kieselwerk_Logopaket)."""
import os
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
LOGOS = os.environ.get("KIESELWERK_LOGOS", os.path.join(os.path.expanduser("~"), "Desktop", "Kieselwerk", "Kieselwerk_Logopaket"))
PETROL = (37, 108, 112)

pat = Image.open(os.path.join(LOGOS, "09_Muster_Hoehenlinien", "muster_sand-auf-petrol.png")).convert("RGB")
app = Image.open(os.path.join(ROOT, "logo_1024.png")).convert("RGBA")
kw = Image.open(os.path.join(LOGOS, "01_Logo_horizontal", "kieselwerk_logo_horizontal_negativ-sand.png")).convert("RGBA")

def big(w, h):
    s = h/pat.height*0.9
    p = pat.resize((round(pat.width*s), round(pat.height*s)), Image.LANCZOS)
    l = round(p.width*0.08)
    bg = Image.new("RGB", (w, h), PETROL); bg.paste(p.crop((l, 0, l+w, min(p.height, h))), (0, round(h*0.05)))
    bg = bg.convert("RGBA"); ImageDraw.Draw(bg).rectangle((0, round(h*0.80), w, h), fill=PETROL+(255,))   # no lines behind the logo
    a = round(w*0.60); bg.alpha_composite(app.resize((a, a), Image.LANCZOS), ((w-a)//2, round(h*0.36)-a//2))
    kw_w = round(w*0.62); ki = kw.resize((kw_w, round(kw.height*kw_w/kw.width)), Image.LANCZOS)
    bg.alpha_composite(ki, ((w-kw_w)//2, round(h*0.90)-ki.height//2))
    return bg.convert("RGB")

for w, h in [(164, 314), (205, 393), (246, 471), (328, 628)]:          # 100, 125, 150, 200 % display scaling
    big(w, h).convert("RGBA").save(os.path.join(HERE, "wizard_%d.bmp" % w))       # 32 bit (WizardImageAlphaFormat=defined)
for s in [55, 69, 83, 110]:                                                       # header picture, transparent on the petrol header
    app.resize((s, s), Image.LANCZOS).save(os.path.join(HERE, "wizard_small_%d.bmp" % s))
print("ok")
