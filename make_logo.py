# -*- coding: utf-8 -*-
"""Draws the Mastering-Tool logo (logo.png 512 px, logo.ico 16-256 px).

Motif: a loudness-meter ring (cyan -> violet -> amber, open at the bottom like a gauge) around a waveform with an amber
centre peak. The ring's bright tip marks the target loudness.
Rendered with numpy at 4x and downsampled, so every edge is anti-aliased."""
import numpy as np
from PIL import Image

S = 2048                                   # supersampled canvas
y, x = np.mgrid[0:S, 0:S].astype(np.float32) + 0.5
u, v = x / S, y / S                        # 0..1

def smoothstep(a, b, t):
    t = np.clip((t - a) / (b - a), 0, 1); return t * t * (3 - 2 * t)

def cover(d, aa=1.5):                      # signed distance (px, negative inside) -> coverage
    return np.clip(0.5 - d / aa, 0, 1)

def squircle(cx, cy, r, n=5.0):
    d = (np.abs(x - cx) / r) ** n + (np.abs(y - cy) / r) ** n
    return (d ** (1 / n) - 1) * r

def rgb(h): h = h.lstrip("#"); return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float32) / 255

img = np.zeros((S, S, 4), np.float32)
def over(color, alpha):                    # color: (..,3) or (3,), alpha: (S,S)
    a = alpha[..., None]; img[..., :3] = img[..., :3] * (1 - a) + color * a; img[..., 3:] = img[..., 3:] * (1 - a) + a

# 1. background squircle: deep night-blue to teal, soft light from the top left
bgmask = cover(squircle(S / 2, S / 2, S * 0.47))
t = np.clip(0.65 * u + 0.35 * v, 0, 1)[..., None]
bg = rgb("#0c1320") * (1 - t) + rgb("#0f3a4a") * t
glow = np.exp(-(((u - 0.3) ** 2 + (v - 0.22) ** 2) / 0.08))[..., None]
bg = bg + glow * rgb("#1b5f73") * 0.45
over(bg, bgmask)

# 2. meter ring (270 degrees, gap at the bottom), angular gradient cyan -> violet -> amber
cx, cy = S / 2, S * 0.51; R = S * 0.33; W = S * 0.055
r = np.hypot(x - cx, y - cy); ang = np.degrees(np.arctan2(x - cx, cy - y))          # 0 = top, clockwise positive
sweep = (ang + 135) % 360                                                              # 0 at lower left, 270 at lower right
on = sweep <= 270
ring_d = np.abs(r - R) - W / 2
ring = cover(ring_d) * on
# round caps
for a0 in (-135, 135):
    a = np.radians(a0); px, py = cx + R * np.sin(a), cy - R * np.cos(a)
    ring = np.maximum(ring, cover(np.hypot(x - px, y - py) - W / 2))
s01 = np.clip(sweep / 270, 0, 1)[..., None]
c1, c2, c3 = rgb("#3fd0dc"), rgb("#8b7cf6"), rgb("#f6b336")
ringcol = np.where(s01 < 0.5, c1 * (1 - s01 * 2) + c2 * (s01 * 2), c2 * (2 - s01 * 2) + c3 * (s01 * 2 - 1))
# track under the ring (dim), then the lit part up to 82 % (the "target")
track = cover(ring_d) * on
over(np.broadcast_to(rgb("#ffffff"), (S, S, 3)), track * 0.08)
lit = ring * (sweep <= 270 * 0.82)
over(ringcol, lit)
# glowing tip at 82 %
a = np.radians(-135 + 270 * 0.82); tx, ty = cx + R * np.sin(a), cy - R * np.cos(a)
dtip = np.hypot(x - tx, y - ty)
over(np.broadcast_to(rgb("#ffe7a8"), (S, S, 3)), np.exp(-(dtip / (W * 1.4)) ** 2) * 0.55 * bgmask)
over(np.broadcast_to(rgb("#fff6dd"), (S, S, 3)), cover(dtip - W * 0.42))

# 3. waveform bars inside the ring (symmetric around the centre line)
heights = [0.26, 0.46, 0.70, 1.00, 0.70, 0.46, 0.26]
bw = S * 0.050; gap = S * 0.030; total = len(heights) * bw + (len(heights) - 1) * gap
x0 = cx - total / 2; Hmax = S * 0.40; ceil_y = cy - Hmax / 2
for i, h in enumerate(heights):
    bx = x0 + i * (bw + gap) + bw / 2; hh = Hmax * h
    qx = np.abs(x - bx); qy = np.abs(y - cy) - (hh / 2 - bw / 2)                        # pill (rounded rect, radius bw/2)
    d = np.hypot(qx, np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) * 0 - bw / 2
    m = cover(d)
    if i == 3:
        col = (rgb("#ffd36b") * (1 - smoothstep(cy - hh / 2, cy + hh / 2, y))[..., None] + rgb("#f39a1f") * smoothstep(cy - hh / 2, cy + hh / 2, y)[..., None])
    else:
        k = smoothstep(cy - hh / 2, cy + hh / 2, y)[..., None]
        col = rgb("#e9fbff") * (1 - k) * 0.35 + rgb("#4fd3df") * (0.65 + 0.35 * k)
    over(col, m)
# 4. subtle top highlight on the squircle edge
edge = cover(np.abs(squircle(S / 2, S / 2, S * 0.47)) - S * 0.003) * np.clip(1.2 - v * 2.2, 0, 1)
over(np.broadcast_to(rgb("#9fe9f2"), (S, S, 3)), edge * 0.25)

rgba = (np.clip(img, 0, 1) * 255).astype(np.uint8)
big = Image.fromarray(rgba, "RGBA")
big.resize((512, 512), Image.LANCZOS).save("logo.png")
big.resize((1024, 1024), Image.LANCZOS).save("logo_1024.png")
sizes = [(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48), (64, 64), (128, 128), (256, 256)]
big.resize((256, 256), Image.LANCZOS).save("logo.ico", sizes=sizes)
print("ok")
