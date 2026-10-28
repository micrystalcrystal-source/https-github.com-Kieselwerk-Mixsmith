# -*- coding: utf-8 -*-
"""Takes the screenshots for the tutorial video: drives Mixsmith with real material in an isolated data folder
(own APPDATA, so no profile ends up in the user's program data) and stores every screen as PNG plus the rectangles
of the controls the video points at (screens/rects.json, in image pixels).

  python tutorial/capture_screens.py

Needs the Mastern material (Collected, Stems, songs) and the stem cache of earlier runs (otherwise it separates)."""
import os, sys, json, shutil

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); MASTERN = os.path.dirname(ROOT)
OUT = os.path.join(HERE, "screens"); os.makedirs(OUT, exist_ok=True)
REAL_APPDATA = os.environ.get("APPDATA", "")
ISO = os.path.join(HERE, "_appdata"); shutil.rmtree(ISO, ignore_errors=True); os.makedirs(ISO)
os.environ["APPDATA"] = ISO; os.environ["MT_NO_SPLASH"] = "1"
sys.path.insert(0, ROOT)

import audio_core as mc
mc.save_settings(dict(asked_shortcut=True))                            # no desktop-shortcut question in the capture run
mc.create_desktop_shortcut = lambda: ""
mc.CACHE_DIR = os.path.join(REAL_APPDATA, "Mixsmith", "cache")        # reuse separated stems (read/write, same keys)
import mixsmith_gui as g
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget
from PySide6.QtCore import QTimer, QPoint
from PySide6.QtGui import QImage

QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
QMessageBox.information = staticmethod(lambda *a, **k: None)
QMessageBox.warning = staticmethod(lambda *a, **k: None)

SONGS = [os.path.join(MASTERN, n) for n in ("Better Human.wav", "Tree House.wav", "Footprints.wav")]
REFS = [os.path.join(MASTERN, "Collected", n) for n in ("Enough.wav", "Fate.wav")]
TRACKS = sorted(os.path.join(MASTERN, "Stems", "Better Human", f) for f in os.listdir(os.path.join(MASTERN, "Stems", "Better Human")))
PROFILE = "Indie-Rock Referenz"

app = QApplication(sys.argv); app.setStyle(g.FastTips("Fusion")); app.setStyleSheet(g.QSS)
win = g.MainWindow(); win.show(); win.place(); win.resize(1600, 960)
RECTS = {}

def card_of(w):
    while w is not None and w.objectName() != "card": w = w.parentWidget()
    return w

SCALE = 2.4          # render resolution (independent of the monitor): 1600 px wide window -> 3840 px image

def rect(w, top=None):
    top = top or win; p = w.mapTo(top, QPoint(0, 0))
    return [round(p.x()*SCALE), round(p.y()*SCALE), round(w.width()*SCALE), round(w.height()*SCALE)]

def shot(name, widgets, top=None):
    top = top or win; app.processEvents()
    img = QImage(round(top.width()*SCALE), round(top.height()*SCALE), QImage.Format_ARGB32); img.setDevicePixelRatio(SCALE); img.fill(0)
    top.render(img); img.save(os.path.join(OUT, name+".png"))
    RECTS[name] = dict(size=[img.width(), img.height()], **{k: rect(w, top) for k, w in widgets.items() if w is not None and w.isVisible()})
    json.dump(RECTS, open(os.path.join(OUT, "rects.json"), "w"), indent=1); print("shot", name, flush=True)

def script():
    mix = win.pages["mix"]; win.go("mix")
    yield 0.5
    # ---- learn a mix profile (dialog + animated progress)
    d = g.LearnMixDialog(mix); d.resize(820, 760); d.show(); d.name.setText(PROFILE); d.add(REFS); d.fx.setChecked(True); d.save_master.setChecked(True)
    yield 0.6
    shot("learn_form", dict(files=d.files, fx=d.fx, name=d.name, go=d.go), d)
    d.run(); yield 14
    shot("learn_busy", dict(panel=d.busy, items=d.busy.list_host, step=d.busy.step, bar=d.busy.bar), d)
    yield lambda: not d.isVisible()
    mix.reload_profiles(PROFILE); win.pages["master"].reload_profiles()
    # ---- mixing page with tracks and a computed preview
    mix.set_mode("tracks"); mix.add_files(TRACKS); mix.song_name.setText("Better Human")
    vox = next(i for i, p in enumerate(mix.track_files) if "Vocals" in p)
    mix.make_preview(); yield 1.0
    yield lambda: not mix._busy
    mix.select_channel(vox); mix.strips[vox].fader.setValue(2); mix.lsa.verticalScrollBar().setValue(0); mix.rsa.verticalScrollBar().setValue(0)
    yield 1.2
    helpdots = [h for h in card_of(mix.s_bal).findChildren(g.HelpDot) if h.isVisible()]
    shot("mix_top", dict(sidebar=win.findChild(QWidget, "sidebar"), source=card_of(mix.ttable), table=mix.ttable, mixer=card_of(mix.strip_area),
                         strips=mix.strip_host, ref=card_of(mix.prof), atable=mix.atable, take=card_of(mix.s_bal), balance=mix.s_bal,
                         helpdot=helpdots[1] if len(helpdots) > 1 else None, out=mix.out, create=mix.out.primary, vox_strip=mix.strips[vox]))
    mix.lsa.ensureWidgetVisible(card_of(mix.strip_area), 0, 0); yield 0.8
    shot("mix_mixer", dict(mixer=card_of(mix.strip_area), strips=mix.strip_host, vox_strip=mix.strips[vox], take=card_of(mix.s_bal)))
    mix.lsa.ensureWidgetVisible(card_of(mix.spec), 0, 0); yield 0.8
    shot("mix_preview", dict(preview=card_of(mix.spec), spec=mix.spec, meters=mix.m_lufs.parentWidget(), player=mix.pbar, ab=mix.pbar.ab,
                             bprev=mix.bprev, mixer=card_of(mix.strip_area), ref=card_of(mix.prof)))
    mix.do_master.setChecked(True); mix.mprof.setCurrentIndex(0); mix.rsa.verticalScrollBar().setValue(mix.rsa.verticalScrollBar().maximum()); yield 0.8
    shot("mix_right", dict(channel=mix.ch_card, summe=card_of(mix.s_peak), master=mix.do_master, create=mix.out.primary, out=mix.out))
    # ---- raw mix mode
    mix.set_mode("song"); mix.add_files(SONGS); mix.lsa.verticalScrollBar().setValue(0); yield 0.8
    shot("mix_song", dict(source=card_of(mix.stable), table=mix.stable, seg=mix.src, mixer=card_of(mix.strip_area)))
    mix.set_mode("tracks")
    # ---- mastering with preview
    ms = win.pages["master"]; win.go("master"); ms.add_files(SONGS); yield 0.5
    ms.table.selectRow(0); yield lambda: ms.cur_x is not None and ms.cur in ms.info
    ms.preset.setCurrentIndex(ms.preset.findData("stream")); ms.make_preview(); yield 1.0
    yield lambda: ms.preview is not None and ms.bprev.isEnabled()
    yield 1.0
    shot("master", dict(files=card_of(ms.table), analysis=card_of(ms.spec), spec=ms.spec, target=card_of(ms.prof), preset=ms.preset,
                        player=ms.pbar, sound=card_of(ms.s_strength), create=ms.out.primary))
    # ---- track matching
    tp = win.pages["track"]
    ref = os.path.join(MASTERN, "Stems", "Footprints", "Footprints - Guitar.wav")
    mc.learn_instrument_profile([ref], "Gitarre wie Footprints", "Gitarre", analyse_fx=False, log=lambda m: None)
    win.go("track"); tp.reload("Gitarre wie Footprints"); tp.add_files([os.path.join(MASTERN, "Stems", "Better Human", "Better Human - Guitar.wav")])
    yield lambda: tp.cur_x is not None
    tp.make_preview(); yield 1.0
    yield lambda: tp.preview is not None and tp.bprev.isEnabled()
    yield 0.8
    shot("track", dict(profile=card_of(tp.prof), files=card_of(tp.table), preview=card_of(tp.spec), sound=card_of(tp.s_str)))
    # ---- stems, settings
    sp = win.pages["stems"]; win.go("stems"); sp.add_files(SONGS[:2]+[os.path.join(MASTERN, "TOOL - Forty Six & 2.wav")]); yield 0.8
    shot("stems", dict(songs=card_of(sp.table), model=card_of(sp.mrows["auto"][0]), tracks=sp.stc, hardware=card_of(sp.dev)))
    win.go("settings"); yield 0.8
    st = win.pages["settings"]
    shot("settings", dict(gpu=card_of(st.gpu), cache=card_of(st.cache)))
    win.go("mix"); yield 0.3
    app.quit()

gen = script()
def pump():
    try:
        v = next(gen)
    except StopIteration:
        return
    if callable(v):
        def wait():
            if v(): pump()
            else: QTimer.singleShot(250, wait)
        wait()
    else:
        QTimer.singleShot(int(float(v)*1000), pump)
QTimer.singleShot(800, pump)
app.exec()
mc.kill_workers()
print("fertig:", ", ".join(RECTS))
