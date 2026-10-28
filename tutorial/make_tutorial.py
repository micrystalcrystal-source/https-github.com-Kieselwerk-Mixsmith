# -*- coding: utf-8 -*-
"""Renders the Mixsmith tutorial video (German) with the mascot Mixi.

  python tutorial/capture_screens.py     (screenshots + control positions, once)
  python tutorial/make_tutorial.py       -> tutorial/Mixsmith-Tutorial.mp4

Voice: Microsoft neural voice "Katja" via edge-tts, a little higher and faster (chosen by ear for Mixi);
alternative offline voice: Piper + Praat "Change gender" (voices/mixi_voice.py, preset thorsten_klein).
Pictures: QPainter frames (screenshots with camera moves and spotlight, the mascot, speech bubbles) piped into ffmpeg."""
import os, sys, json, math, random, subprocess
import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "voices"))
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (QGuiApplication, QImage, QPainter, QColor, QPen, QFont, QFontMetricsF, QLinearGradient,
                           QRadialGradient, QPainterPath)
import mascot

W, H, FPS, SR = 1920, 1080, 30, 44100
VOICE = "katja_mixi"
EDGE_VOICES = {"katja_mixi": dict(voice="de-DE-KatjaNeural", rate="+6%", pitch="+35Hz")}
OUT = os.path.join(HERE, "Mixsmith-Tutorial.mp4")
FFMPEG = os.path.join(ROOT, "bin", "ffmpeg.exe" if os.name == "nt" else "ffmpeg")
ACC, ACC_H, AMBER, VIOLET, TEXT, MUTED, BG0, BG1 = "#4fc8d6", "#72d9e4", "#f5b23a", "#8b7cf6", "#e7ebf1", "#8d98a8", "#0b111a", "#0f2f3b"

# spoken form of words a German voice would mispronounce (subtitles keep the written form)
SAY = [("Mixsmith", "[[ mˈɪkssmɪs ]]"), ("Stems", "[[ stˈɛms ]]"), ("Delay", "[[ dɪlˈeɪ ]]"), ("Fader", "[[ fˈeɪdɜ ]]"), ("Low-Cut", "[[ lˈoʊkˌat ]]"),
       ("Drums", "[[ drˈamz ]]"), ("Keys", "[[ kˈiːs ]]"), ("Spotify", "[[ spˈɔtɪfaɪ ]]"), ("KI", "[[ kaːʔˈiː ]]"), ("A-B-Vorschau", "A-B Vorschau"),
       ("Rohmix", "Roh-Mix"), ("Solo", "[[ zˈoːloː ]]")]

# (chapter, screen, focus, highlights, text, pose)   focus/highlights: names from screens/rects.json, None = whole screen
SCRIPT = [
    ("Willkommen", "intro", None, [], "Hallo! Ich bin Mixi, dein kleiner Klangschmied.", "wave"),
    ("Willkommen", "intro", None, [], "In zweieinhalb Minuten zeige ich dir, wie Mixsmith deine Songs mischt und mastert.", "talk"),
    ("Überblick", "mix_top", None, ["sidebar"], "Links findest du alle Bereiche: Mixing, Mastering, Spur-Angleich, Stems extrahieren und die Einstellungen.", "point"),
    ("Mix-Profil anlernen", "learn_form", ["name", "files"], ["files"], "Alles beginnt mit einem Vorbild: einem oder mehreren Songs, deren Mix dir gefällt.", "point"),
    ("Mix-Profil anlernen", "learn_busy", "panel", ["items"], "Ich zerlege sie per KI in Gesang, Drums, Bass, Gitarre, Keys und den Rest.", "point"),
    ("Mix-Profil anlernen", "learn_busy", "panel", [], "Dann messe ich für jede Spur Lautstärke, Klang, Dynamik und Breite – auf Wunsch sogar Hall und Delay.", "talk"),
    ("Die Referenz", "mix_top", "ref", ["atable"], "Hier siehst du das Ergebnis: wie laut jede Spur im Vorbild ist, gemessen am ganzen Mix.", "point"),
    ("Deine Spuren", "mix_top", "source", ["table"], "Jetzt zu deinem Song. Zieh die Einzelspuren einfach hier hinein. Die Rolle erkenne ich meist schon am Dateinamen.", "point"),
    ("Deine Spuren", "mix_song", "source", ["seg", "table"], "Du hast nur einen fertigen Rohmix? Kein Problem, dann zerlege ich ihn vorher in seine Spuren.", "point"),
    ("Vom Vorbild übernehmen", "mix_top", "take", ["take"], "Mit diesen Reglern bestimmst du, wie viel vom Vorbild übernommen wird: Balance, Klang, Dynamik, Transienten und Breite.", "point"),
    ("Mischpult", "mix_mixer", "mixer", ["strips"], "Am Mischpult hat jede Spur ihren Fader, ihr Panorama, Stumm und Solo. Das wirkt sofort, auch während die Vorschau läuft.", "point"),
    ("Mischpult", "mix_right", "channel", ["channel"], "Ein Klick auf einen Kanal zeigt hier seine Klangregler: Low-Cut, Tiefen, Präsenz, Höhen, Kompressor und Hall.", "point"),
    ("Vorschau", "mix_preview", "preview", ["player"], "Mit „Vorschau berechnen“ hörst du das Ergebnis. Schalte zwischen A, dem Rohmix, und B, dem Mix, um den Unterschied zu hören.", "point"),
    ("Vorschau", "mix_preview", "preview", ["spec"], "Das Spektrum vergleicht jede Spur mit dem Vorbild.", "point"),
    ("Mix & Master", "mix_right", ["summe", "create"], ["summe", "create"], "Zum Schluss klickst du auf „Mix erstellen“. Wenn du willst, mastere ich den Song gleich mit, im Stil deines Vorbilds.", "point"),
    ("Mastering", "master", "target", ["preset"], "Fertige Songs bringst du im Bereich Mastering auf Lautstärke. Wähle ein Profil und eine Plattform, zum Beispiel Spotify.", "point"),
    ("Mastering", "master", "analysis", ["player"], "Mit der A-B-Vorschau hörst du Original und Master gleich laut. So zählt nur der Klang.", "point"),
    ("Spur-Angleich", "track", "profile", ["profile"], "Im Spur-Angleich klingt eine rohe Spur wie das Instrument aus deinem Lieblingssong.", "point"),
    ("Stems", "stems", "model", ["model"], "Und unter „Stems extrahieren“ zerlegst du jeden Song in Einzelspuren, zum Beispiel für Karaoke oder zum Üben.", "point"),
    ("Tipps", "mix_top", "take", ["helpdot"], "Mein Tipp: Fahr mit der Maus über die kleinen Fragezeichen. Dort erkläre ich dir jede Einstellung.", "point"),
    ("Tipps", "settings", "gpu", ["gpu"], "In den Einstellungen legst du fest, wie viel Grafikspeicher die KI benutzen darf.", "point"),
    ("Viel Spaß!", "outro", None, [], "Das war's schon! Viel Spaß beim Mischen und Mastern mit Mixsmith.", "wave"),
]
TOOLTIP = ("Lautstärkeverhältnisse der Rollen wie in der Referenz (z. B. Gesang 5 LU unter dem Mix, Bass 7 LU). "
           "Rollen, die in der Referenz fehlen oder im Song nur als Trennungsrest vorkommen, bleiben unverändert.")

def spoken(text):
    s = text.replace("„", "").replace("“", "")
    if VOICE in EDGE_VOICES: return s                       # the neural voice handles the English words itself
    for a, b in SAY: s = s.replace(a, b)
    return s

def synth(text):
    """Mono float32 at SR for one line."""
    if VOICE in EDGE_VOICES:
        import asyncio, tempfile, edge_tts
        from scipy import signal
        v = EDGE_VOICES[VOICE]; tmp = os.path.join(tempfile.gettempdir(), "mixi_line.mp3")
        asyncio.run(edge_tts.Communicate(text, v["voice"], rate=v["rate"], pitch=v["pitch"]).save(tmp))
        y, sr = sf.read(tmp, dtype="float64", always_2d=True); y = y.mean(axis=1)
        if sr != SR: y = signal.resample_poly(y, SR, sr)
        nz = np.where(np.abs(y) > 0.01*np.max(np.abs(y)))[0]
        if len(nz): y = y[max(0, nz[0]-int(0.02*SR)):nz[-1]+int(0.06*SR)]
        return (y/max(1e-9, np.max(np.abs(y)))*0.89).astype(np.float32)
    import mixi_voice
    return mixi_voice.speak(text, VOICE, SR)

# ============================================================== audio
def jingle(notes=(659.25, 783.99, 987.77, 1318.5), step=0.11, tail=1.4):
    """Short bell-like logo sting (synthesised, no sample)."""
    n = int((step*len(notes)+tail)*SR); y = np.zeros(n)
    for i, f in enumerate(notes):
        t = np.arange(n-int(i*step*SR))/SR; env = np.exp(-t*3.2)*(1-np.exp(-t*200))
        tone = np.sin(2*np.pi*f*t)+0.35*np.sin(2*np.pi*2*f*t)*np.exp(-t*6)+0.12*np.sin(2*np.pi*3.01*f*t)*np.exp(-t*9)
        y[int(i*step*SR):] += 0.16*env*tone
    return y

def build_timeline():
    """TTS per line; returns (events, audio). events: dict(line fields, t0, t1 speech, a0, a1 displayed)."""
    events = []; parts = []; cur = 1.2; prev_screen = None
    cache = os.path.join(HERE, "_tts"); os.makedirs(cache, exist_ok=True)
    for i, (chap, screen, focus, hl, text, pose) in enumerate(SCRIPT):
        f = os.path.join(cache, "%02d_%s.wav" % (i, VOICE))
        say = spoken(text)
        meta = f + ".txt"
        if not (os.path.exists(f) and os.path.exists(meta) and open(meta, encoding="utf-8").read() == say):
            y = synth(say); sf.write(f, y, SR); open(meta, "w", encoding="utf-8").write(say)
        y, _ = sf.read(f, dtype="float32")
        if screen != prev_screen and prev_screen is not None: cur += 0.55          # room for the camera/crossfade
        events.append(dict(chap=chap, screen=screen, focus=focus, hl=hl, text=text, pose=pose, t0=cur, t1=cur+len(y)/SR))
        parts.append((cur, y)); cur += len(y)/SR+0.65; prev_screen = screen
    total = cur+2.6
    audio = np.zeros(int(total*SR)+SR)
    for t, y in parts: s = int(t*SR); audio[s:s+len(y)] += y
    voice = audio[:int(total*SR)].copy()                   # the mouth follows the voice only, not the jingle
    j = jingle(); audio[:len(j)] += j*0.8; s = int((total-2.3)*SR); audio[s:s+len(j)] += j[:len(audio)-s]*0.8
    # displayed ranges: each line stays until the next starts
    for k, e in enumerate(events): e["a0"] = e["t0"]-0.15; e["a1"] = events[k+1]["t0"]-0.15 if k+1 < len(events) else total
    return events, audio[:int(total*SR)], voice, total

def mouth_curve(audio, total):
    hop = SR//FPS; n = int(total*FPS)+1; out = np.zeros(n)
    for k in range(n):
        seg = audio[k*hop:(k+1)*hop]
        out[k] = math.sqrt(float(np.mean(seg**2))) if len(seg) else 0.0
    ref = np.percentile(out[out > 1e-4], 90) if np.any(out > 1e-4) else 1.0
    m = np.clip(out/ref*1.1, 0, 1); sm = np.zeros_like(m); v = 0.0
    for k, x in enumerate(m): v = x if x > v else v*0.55; sm[k] = v
    return np.where(sm > 0.12, sm, 0.0)

# ============================================================== drawing helpers
def ease(x): x = max(0.0, min(1.0, x)); return x*x*(3-2*x)
def lerp(a, b, t): return a+(b-a)*t
def lerp_rect(a, b, t): return [lerp(a[i], b[i], t) for i in range(4)]

class Screens:
    def __init__(self):
        self.rects = json.load(open(os.path.join(HERE, "screens", "rects.json"), encoding="utf-8")); self.img = {}
    def image(self, name):
        if name not in self.img: self.img[name] = QImage(os.path.join(HERE, "screens", name+".png"))
        return self.img[name]
    def size(self, name): return self.rects[name]["size"]
    def rect(self, name, key): return self.rects[name].get(key)
    def view(self, name, focus):
        """Camera rect (image pixels, 16:9) for a focus control (or list of controls) or the whole screen.
        The focus lands in the upper part of the frame (below the chapter chip): the bottom third belongs to Mixi."""
        iw, ih = self.size(name)
        keys = [focus] if isinstance(focus, str) else list(focus or [])
        rs = [self.rect(name, k) for k in keys if self.rect(name, k)]
        if rs:
            x0 = min(r[0] for r in rs); y0 = min(r[1] for r in rs); x1 = max(r[0]+r[2] for r in rs); y1 = max(r[1]+r[3] for r in rs)
            rw, rh = x1-x0, y1-y0; TOP, BOT = 0.11, 0.62                    # safe band of the frame height
            vh = max(rh/(BOT-TOP), rw*1.12*9/16, iw*0.46*9/16); vw = vh*16/9
            vx = (x0+x1)/2-vw/2; vy = y0-TOP*vh
            vx = iw/2-vw/2 if vw >= iw else min(max(vx, -vw*0.04), iw-vw*0.96)
            return [vx, vy, vw, vh]
        h = max(ih, iw*9/16)*1.06; w = h*16/9
        return [iw/2-w/2, ih/2-h/2, w, h]

def to_frame(r, view):
    sx = W/view[2]; sy = H/view[3]
    return QRectF((r[0]-view[0])*sx, (r[1]-view[1])*sy, r[2]*sx, r[3]*sy)

def draw_background(p, t):
    g = QLinearGradient(0, 0, W, H); g.setColorAt(0, QColor(BG0)); g.setColorAt(1, QColor(BG1)); p.fillRect(0, 0, W, H, g)
    for i, (c, ph) in enumerate(((ACC, 0.0), (VIOLET, 2.0), (AMBER, 4.0))):
        x = W*(0.2+0.6*(0.5+0.5*math.sin(t*0.13+ph))); y = H*(0.3+0.4*(0.5+0.5*math.cos(t*0.11+ph*1.3)))
        rg = QRadialGradient(QPointF(x, y), W*0.35); cc = QColor(c); cc.setAlpha(26); rg.setColorAt(0, cc); cc.setAlpha(0); rg.setColorAt(1, cc)
        p.fillRect(0, 0, W, H, rg)

def draw_screen(p, scr, name, view, alpha=1.0):
    img = scr.image(name); iw, ih = scr.size(name); target = to_frame([0, 0, iw, ih], view)
    p.save(); p.setOpacity(alpha)
    sh = QPainterPath(); sh.addRoundedRect(target.adjusted(-2, 6, 2, 16), 18, 18); p.fillPath(sh, QColor(0, 0, 0, 120))
    clip = QPainterPath(); clip.addRoundedRect(target, 14, 14); p.setClipPath(clip)
    p.drawImage(target, img); p.restore()

def draw_spot(p, rects, strength, t):
    if not rects or strength <= 0: return
    p.save(); path = QPainterPath(); path.setFillRule(Qt.OddEvenFill); path.addRect(QRectF(0, 0, W, H))
    for r in rects: path.addRoundedRect(r.adjusted(-10, -10, 10, 10), 14, 14)
    p.fillPath(path, QColor(3, 8, 14, int(150*strength)))
    pulse = 0.5+0.5*math.sin(t*4.2)
    for r in rects:
        rr = r.adjusted(-10, -10, 10, 10)
        for wdt, a in ((14, 40), (8, 70)):
            c = QColor(ACC); c.setAlpha(int(a*strength*(0.6+0.4*pulse))); p.setPen(QPen(c, wdt)); p.setBrush(Qt.NoBrush); p.drawRoundedRect(rr, 14, 14)
        c = QColor(ACC_H); c.setAlpha(int(255*strength)); p.setPen(QPen(c, 3.5)); p.drawRoundedRect(rr, 14, 14)
    p.restore()

def draw_bubble(p, text, anchor, side, alpha, pop, max_w=880):
    """Speech bubble with the subtitle, beside Mixi's head; anchor = head (frame px), side = +1 (bubble right of Mixi) / -1."""
    if alpha <= 0: return
    f = QFont("Segoe UI"); f.setPixelSize(33); f.setWeight(QFont.DemiBold); fm = QFontMetricsF(f)
    br = fm.boundingRect(QRectF(0, 0, max_w, 2000), Qt.TextWordWrap, text); bw, bh = br.width()+64, br.height()+62
    x = anchor.x()+150 if side > 0 else anchor.x()-150-bw; y = min(H-34-bh, anchor.y()-bh*0.35)
    x = min(max(24, x), W-24-bw); y = max(24, y)
    r = QRectF(x, y, bw, bh)
    p.save(); p.setOpacity(alpha)
    sc = 0.85+0.15*ease(pop); p.translate(anchor); p.scale(sc, sc); p.translate(-anchor)
    sh = QPainterPath(); sh.addRoundedRect(r.translated(0, 8), 26, 26); p.fillPath(sh, QColor(0, 0, 0, 90))
    path = QPainterPath(); path.addRoundedRect(r, 26, 26)
    tail = QPainterPath(); edge = r.left()+2 if side > 0 else r.right()-2; by = min(max(anchor.y()+40, r.top()+34), r.bottom()-34)
    tip = QPointF(anchor.x()+side*95, anchor.y()+60)
    tail.moveTo(edge, by-22); tail.lineTo(tip); tail.lineTo(edge, by+22); tail.closeSubpath()
    path = path.united(tail)
    p.fillPath(path, QColor("#f4f8fb")); p.setPen(QPen(QColor(ACC), 3)); p.setBrush(Qt.NoBrush); p.drawPath(path)
    tag = QFont("Segoe UI"); tag.setPixelSize(22); tag.setWeight(QFont.Bold); p.setFont(tag); p.setPen(QColor("#1f8f9c"))
    p.drawText(QRectF(r.left()+32, r.top()+10, 200, 28), Qt.AlignLeft | Qt.AlignVCenter, "Mixi")
    p.setFont(f); p.setPen(QColor("#10202a")); p.drawText(QRectF(r.left()+32, r.top()+40, bw-64, bh-50), Qt.TextWordWrap, text)
    p.restore()

def draw_chip(p, text, idx, n, alpha):
    if alpha <= 0 or not text: return
    f = QFont("Segoe UI"); f.setPixelSize(26); f.setWeight(QFont.DemiBold); fm = QFontMetricsF(f)
    label = "%d / %d   %s" % (idx, n, text); w = fm.horizontalAdvance(label)+56; r = QRectF(36, 32, w, 54)
    p.save(); p.setOpacity(alpha); g = QLinearGradient(r.topLeft(), r.topRight()); g.setColorAt(0, QColor(15, 30, 40, 235)); g.setColorAt(1, QColor(20, 40, 60, 235))
    p.setPen(QPen(QColor(ACC), 2)); p.setBrush(g); p.drawRoundedRect(r, 27, 27)
    p.setFont(f); p.setPen(QColor(TEXT)); p.drawText(r, Qt.AlignCenter, label); p.restore()

def draw_tooltip(p, anchor, alpha):
    if alpha <= 0: return
    f = QFont("Segoe UI"); f.setPixelSize(24); fm = QFontMetricsF(f); br = fm.boundingRect(QRectF(0, 0, 560, 1000), Qt.TextWordWrap, TOOLTIP)
    r = QRectF(anchor.x()-br.width()-60, anchor.y()+28, br.width()+36, br.height()+28)
    if r.left() < 20: r.moveLeft(anchor.x()+20)
    p.save(); p.setOpacity(alpha); p.setPen(QPen(QColor("#2f3a48"), 2)); p.setBrush(QColor("#0a0e13")); p.drawRoundedRect(r, 10, 10)
    p.setFont(f); p.setPen(QColor(TEXT)); p.drawText(r.adjusted(18, 14, -18, -14), Qt.TextWordWrap, TOOLTIP); p.restore()

def draw_title(p, t, title, sub, alpha, logo):
    p.save(); p.setOpacity(alpha)
    s = 400; lx, ly = W*0.20, H*0.5-s/2-40
    glow = QRadialGradient(QPointF(lx+s/2, ly+s/2), s*0.8); c = QColor(ACC); c.setAlpha(70); glow.setColorAt(0, c); c.setAlpha(0); glow.setColorAt(1, c)
    p.fillRect(QRectF(lx-s*0.4, ly-s*0.4, s*1.8, s*1.8), glow)
    p.drawImage(QRectF(lx, ly+8*math.sin(t*1.5), s, s), logo)
    f = QFont("Segoe UI Variable Display"); f.setPixelSize(118); f.setWeight(QFont.DemiBold); p.setFont(f); p.setPen(QColor(TEXT))
    p.drawText(QRectF(lx+s+60, ly+60, 900, 150), Qt.AlignLeft | Qt.AlignVCenter, title)
    f2 = QFont("Segoe UI"); f2.setPixelSize(40); p.setFont(f2); p.setPen(QColor(ACC_H))
    p.drawText(QRectF(lx+s+66, ly+205, 900, 60), Qt.AlignLeft | Qt.AlignVCenter, sub)
    p.restore()

# ============================================================== render
def main(stills=None, still_dir=None):
    """stills: list of times (s) -> PNG frames only (quick check), otherwise the whole video."""
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)  # noqa: F841 (needed for fonts)
    scr = Screens(); events, audio, voice, total = build_timeline(); mouth = mouth_curve(voice, total)
    wav = os.path.join(HERE, "_tts", "narration.wav"); sf.write(wav, (audio*0.95).astype(np.float32), SR)
    logo = QImage(os.path.join(ROOT, "logo_1024.png"))
    chapters = []
    for e in events:
        if not chapters or chapters[-1] != e["chap"]: chapters.append(e["chap"])
    nfr = int(total*FPS); rnd = random.Random(7); blinks = []; tb = 1.5
    while tb < total: blinks.append(tb); tb += rnd.uniform(2.2, 4.8)
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", "%dx%d" % (W, H), "-r", str(FPS), "-i", "-",
           "-i", wav, "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-tune", "animation",
           "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-shortest", OUT]
    ff = None if stills else subprocess.Popen(cmd, stdin=subprocess.PIPE)
    frames = sorted(int(t*FPS) for t in stills) if stills else range(nfr)
    img = QImage(W, H, QImage.Format_ARGB32)
    for e in events:
        if e["screen"] not in ("intro", "outro"): e["view"] = scr.view(e["screen"], e["focus"])
    side_x = {"left": W*0.12, "right": W*0.88}; mx_cur = side_x["right"]
    for k in frames:
        t = k/FPS
        ei = max(0, max([i for i, e in enumerate(events) if e["a0"] <= t] or [0])); e = events[ei]; pe = events[ei-1] if ei > 0 else None
        into = t-e["a0"]
        p = QPainter(img); p.setRenderHint(QPainter.Antialiasing); p.setRenderHint(QPainter.SmoothPixmapTransform); p.setRenderHint(QPainter.TextAntialiasing)
        draw_background(p, t)
        # ---- screen with camera move / crossfade
        focus_center = QPointF(W*0.5, H*0.5); spot_rects = []
        if e["screen"] in ("intro", "outro"):
            fade = ease(into/0.6) if pe and pe["screen"] not in ("intro", "outro") else 1.0
            if pe and pe["screen"] not in ("intro", "outro") and fade < 1: draw_screen(p, scr, pe["screen"], pe["view"], 1-fade)
            draw_title(p, t, "Mixsmith", "Tutorial · Version 1.0" if e["screen"] == "intro" else "Viel Spaß beim Mischen!", fade*ease((t-0.2)/0.8), logo)
            mascot_side = "right"
        else:
            move = ease(into/0.9)
            if pe and pe["screen"] == e["screen"]:
                view = lerp_rect(pe["view"], e["view"], move)
            else:
                view = e["view"]
            zoom = 1.0-0.025*min(1.0, into/6.0)                            # slow push-in while talking
            cx, cy = view[0]+view[2]/2, view[1]+view[3]/2; view = [cx-view[2]*zoom/2, cy-view[3]*zoom/2, view[2]*zoom, view[3]*zoom]
            cross = ease(into/0.5) if pe and pe["screen"] != e["screen"] else 1.0
            if cross < 1 and pe and pe["screen"] not in ("intro", "outro"): draw_screen(p, scr, pe["screen"], pe["view"], 1.0)
            draw_screen(p, scr, e["screen"], view, cross)
            spot_rects = [to_frame(scr.rect(e["screen"], h), view) for h in e["hl"] if scr.rect(e["screen"], h)]
            draw_spot(p, spot_rects, cross*ease((into-0.5)/0.5), t)
            if spot_rects:
                u = spot_rects[0]
                for r in spot_rects[1:]: u = u.united(r)
                focus_center = u.center()
            mascot_side = "left" if focus_center.x() > W*0.55 else "right"
            if e["hl"] == ["helpdot"] and spot_rects: draw_tooltip(p, spot_rects[0].center(), ease((into-1.2)/0.4))
        # ---- chapter chip
        ci = chapters.index(e["chap"]); chip_a = 1.0 if (pe and pe["chap"] == e["chap"]) else ease(into/0.4)
        if e["screen"] not in ("intro", "outro"): draw_chip(p, e["chap"], ci, len(chapters)-2, chip_a)
        # ---- mascot (slides to the side away from the highlighted control)
        mx_cur = side_x[mascot_side] if stills else mx_cur+(side_x[mascot_side]-mx_cur)*0.12
        blink = 0.0
        for b in blinks:
            if 0 <= t-b < 0.16: blink = 1-abs((t-b)/0.08-1)
        mo = float(mouth[min(k, len(mouth)-1)])
        pose = e["pose"] if e["pose"] != "point" or spot_rects else "talk"
        if pose == "point" and t > e["t1"]: pose = "talk"
        size = 260; base_y = H-40; enter = ease((t-0.3)/0.7)
        mascot.draw(p, mx_cur, base_y+(1-enter)*300, size, t, mouth=mo, blink=blink, pose=pose,
                    point_to=(focus_center.x(), focus_center.y()) if pose == "point" else None)
        # ---- speech bubble
        head = QPointF(mx_cur, base_y-size*1.15)
        a = min(ease((t-e["a0"])/0.25), ease((e["a1"]-t)/0.25))
        draw_bubble(p, e["text"], head, -1 if mascot_side == "right" else 1, a, (t-e["a0"])/0.25)
        # ---- progress
        pr = QRectF(0, H-6, W*t/total, 6); g = QLinearGradient(0, 0, W, 0); g.setColorAt(0, QColor(ACC)); g.setColorAt(1, QColor(AMBER)); p.fillRect(pr, g)
        p.end()
        if ff is None:
            img.save(os.path.join(still_dir, "still_%06.1f.png" % t)); continue
        ff.stdin.write(img.constBits().tobytes() if hasattr(img.constBits(), "tobytes") else bytes(img.constBits()))
        if k % (FPS*10) == 0: print("  %3.0f %%  (%s)" % (100*k/nfr, e["chap"]), flush=True)
    if ff is None: return events
    ff.stdin.close(); ff.wait()
    marks = []
    for e in events:
        if not marks or marks[-1]["name"] != e["chap"]: marks.append(dict(name=e["chap"], start=round(max(0.0, e["a0"]-0.6), 2)))
    marks[0]["start"] = 0.0
    json.dump(dict(chapters=marks, duration=round(total, 2)), open(os.path.splitext(OUT)[0]+".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("fertig: %s  (%.0f s, %.1f MB)" % (OUT, total, os.path.getsize(OUT)/2**20))

if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--stills":
        d = sys.argv[3] if len(sys.argv) > 3 else os.path.join(HERE, "_stills"); os.makedirs(d, exist_ok=True)
        main([float(x) for x in sys.argv[2].split(",")], d)
    else:
        main()
