# -*- coding: utf-8 -*-
"""
Mixsmith – Start, Kommandozeile und Trennungs-Worker.

  python mixsmith.py                                                   -> grafische Oberfläche
  python mixsmith.py --learn-mix ref1.wav ref2.wav --name "Mein Mix"  -> Mix-Profil aus Referenzsongs
  python mixsmith.py --mix-profile "Mein Mix" --tracks --name "Song" --out "C:\\Ausgabe" kick.wav snare.wav bass.wav vox.wav
  python mixsmith.py --mix-profile "Mein Mix" --out "C:\\Ausgabe" rohmix1.wav rohmix2.wav    (Rohmix: KI-Trennung, dann Mix)
  python mixsmith.py --profile "Laut und hell" --out "C:\\Ausgabe" song1.wav song2.wav     (nur Mastering)
  python mixsmith.py --learn "C:\\Referenzen" --name "Mein Profil"
  python mixsmith.py --extract-stems --model auto --out "C:\\Stems" song.wav

Mix-Optionen: --balance --tone --dynamics --transients --stereo --fx (je 0..1) --peak-db -3 --master [--master-profile NAME] [--preset stream|…]
Mastering-Optionen: --preset stream|apple|loud|club|cd --peak sample|true --ceiling -0.1 --lufs -11.4 --strength 1.0 --max-eq 9
  --presence-full 4 --presence-cap 7 --deharsh 0.5 --warm 0 --air 0 --bass-mono 150 --width profil|aus|<dB> --release 120
  --glue 0.0 --clip 1.0 --vocals 0 --drums 0 --bass 0 --other 0 --bits 24|16 --no-declip
"""
import os, sys, argparse

APP = "Mixsmith"

def _ensure_streams():
    """Windowed builds have no console: route stdout/stderr into a log file so libraries that print do not crash."""
    if sys.stdout is None or sys.stderr is None:
        if sys.platform == "win32": base = os.environ.get("APPDATA", os.path.expanduser("~"))
        elif sys.platform == "darwin": base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
        else: base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
        d = os.path.join(base, APP)
        try:
            os.makedirs(d, exist_ok=True); f = open(os.path.join(d, "log.txt"), "a", encoding="utf-8", errors="replace")
        except Exception:
            f = open(os.devnull, "w")
        if sys.stdout is None: sys.stdout = f
        if sys.stderr is None: sys.stderr = f
    for s in (sys.stdout, sys.stderr):      # Windows-Konsole (cp1252) soll an Sonderzeichen nicht scheitern
        try: s.reconfigure(errors="replace")
        except Exception: pass

GUI_FLAGS = ("--no-splash",)

def _cli(argv):
    import audio_core as mc
    ap = argparse.ArgumentParser(prog="mixsmith", description="Mixsmith – Mixing und Mastering nach Referenz")
    ap.add_argument("files", nargs="*"); ap.add_argument("--profile"); ap.add_argument("--out"); ap.add_argument("--learn"); ap.add_argument("--name")
    ap.add_argument("--preset", choices=[k for k in mc.PRESETS if k != "profil"])
    ap.add_argument("--peak", choices=["sample", "true"]); ap.add_argument("--ceiling", type=float); ap.add_argument("--lufs", type=float)
    ap.add_argument("--strength", type=float, default=1.0); ap.add_argument("--max-eq", type=float, default=9.0)
    ap.add_argument("--presence-full", type=float, default=4.0); ap.add_argument("--presence-cap", type=float, default=7.0); ap.add_argument("--deharsh", type=float, default=0.5)
    ap.add_argument("--warm", type=float, default=0.0); ap.add_argument("--air", type=float, default=0.0); ap.add_argument("--bass-mono", type=float, default=150.0)
    ap.add_argument("--width", default="profil", help="profil | aus | Zahl in dB (manuell)"); ap.add_argument("--release", type=float, default=120.0)
    ap.add_argument("--glue", type=float, default=0.0, help="Bus-Kompression 0..1"); ap.add_argument("--clip", type=float, default=1.0, help="Soft-Clipper in dB (0 = aus)")
    for s in ("vocals", "drums", "bass", "other"): ap.add_argument("--" + s, type=float, default=0.0, help="Stem-Balance in dB")
    ap.add_argument("--bits", type=int, default=24, choices=[16, 24]); ap.add_argument("--no-declip", action="store_true")
    ap.add_argument("--model", default="auto", choices=["auto"]+[k for k, v in mc.SEP_MODELS.items() if not v.get("internal")], help="Trennmodell")
    ap.add_argument("--extract-stems", action="store_true", help="Dateien in Einzelspuren zerlegen")
    ap.add_argument("--learn-track", nargs="+", metavar="REF", help="Instrument-Profil aus Referenzdateien lernen"); ap.add_argument("--instrument", default="Gitarre", choices=mc.INSTRUMENTS)
    ap.add_argument("--separate", action="store_true", help="Referenzen sind komplette Songs (Stem-Trennung nötig)"); ap.add_argument("--track-profile", help="Spuren an dieses Instrument-Profil angleichen")
    ap.add_argument("--saturation", type=float, default=0.0); ap.add_argument("--stems-dir", help="Stems der Referenzsongs hier speichern")
    ap.add_argument("--fx", type=float, default=None, help="Stärke der übernommenen Effekte 0..1 (Spur-Angleich Standard 1, Mix Standard 0)")
    # mixing
    ap.add_argument("--learn-mix", nargs="+", metavar="REF", help="Mix-Profil aus Referenzsongs lernen"); ap.add_argument("--no-fx-analysis", action="store_true")
    ap.add_argument("--mix-profile", help="Mix-Profil, nach dem gemischt wird ('-' = ohne Referenz)"); ap.add_argument("--tracks", action="store_true", help="Dateien sind Einzelspuren eines Songs (sonst Rohmixe)")
    ap.add_argument("--balance", type=float, default=1.0); ap.add_argument("--tone", type=float, default=0.7); ap.add_argument("--dynamics", type=float, default=0.6)
    ap.add_argument("--transients", type=float, default=0.5); ap.add_argument("--stereo", type=float, default=0.7); ap.add_argument("--peak-db", type=float, default=-3.0)
    ap.add_argument("--master", action="store_true", help="nach dem Mix mastern"); ap.add_argument("--master-profile", help="Mastering-Profil (Standard: aus dem Mix-Profil)")
    ap.add_argument("--save-tracks", action="store_true", help="bearbeitete Einzelspuren mitspeichern")
    ap.add_argument("--no-splash", action="store_true", help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    width = lambda: ("profil", 0.0) if a.width == "profil" else (("aus", 0.0) if a.width == "aus" else ("manuell", float(a.width)))
    if a.extract_stems:
        for f in a.files: mc.extract_stems(f, a.out or os.path.join(os.getcwd(), "Stems"), model=a.model, bits=a.bits)
    elif a.learn_mix:
        import mix_core as mx
        mx.learn_mix_profile(a.learn_mix, a.name or "Mix-Profil", model=a.model, analyse_fx=not a.no_fx_analysis, stems_dir=a.stems_dir)
    elif a.mix_profile:
        import mix_core as mx
        if not a.files: raise RuntimeError("Keine Dateien angegeben.")
        prof = None if a.mix_profile == "-" else mx.load_mix_profile(a.mix_profile)
        master = None
        if a.master:
            master = mc.load_profile(a.master_profile) if a.master_profile else (mx.master_profile_from_mix(prof) if prof else mc.load_profile(mc.list_profiles()[0]))
        mkw = mx.master_settings(a.preset or "profil"); out = a.out or os.path.join(os.getcwd(), "Mix-Ausgabe")
        kw = dict(balance=a.balance, tone=a.tone, dynamics=a.dynamics, transients=a.transients, width=a.stereo, fx=a.fx or 0.0, peak_db=a.peak_db)
        taken = set(); rows = []
        if a.tracks:
            tracks, sr = mx.load_tracks(a.files)
            for t in tracks: t["role"] = mx.guess_role(t["name"]); print("  %s → %s" % (t["name"], mx.ROLE_DE[t["role"]]))
            name = a.name or os.path.basename(os.path.dirname(os.path.abspath(a.files[0])))
            chans = [dict(mx.CHANNEL_DEFAULTS) for _ in tracks]
            res, _o = mx.process_mix(tracks, sr, name, out, prof, chans, master=master, master_kw=mkw, bits=a.bits, save_parts=a.save_tracks, taken=taken, protect=a.files, **kw)
            rows.append((name, res, prof, tracks, chans))
        else:
            for f in a.files:
                print(os.path.basename(f)); tracks, sr, _ = mx.song_parts(f, model=a.model); chans = [dict(mx.CHANNEL_DEFAULTS) for _ in tracks]
                song = os.path.splitext(os.path.basename(f))[0]
                res, _o = mx.process_mix(tracks, sr, song, out, prof, chans, master=master, master_kw=mkw, bits=a.bits,
                                         save_parts=a.save_tracks, taken=taken, protect=a.files, **kw)
                rows.append((song, res, prof, tracks, chans))
        if rows: print("Protokoll: %s" % mx.write_mix_protocol(rows, out))
    elif a.learn_track:
        mc.learn_instrument_profile(a.learn_track, a.name or "Instrument-Profil", a.instrument, separate=a.separate, stems_dir=a.stems_dir, model=a.model)
    elif a.track_profile:
        prof = mc.load_instrument_profile(a.track_profile); wm, wv = width(); fxs = 1.0 if a.fx is None else a.fx
        mc.run_track_batch(a.files, prof, a.out or os.path.join(os.getcwd(), "Spur-Ausgabe"), strength=a.strength, max_eq=a.max_eq, saturation=a.saturation,
                           width_mode=wm, width_db_manual=wv, target_lufs=a.lufs, out_bits=a.bits, fx={k: dict(v, strength=fxs) for k, v in prof.get("effects", {}).items()})
    elif a.learn:
        mc.learn_profile(a.learn, a.name or os.path.basename(a.learn.rstrip("/\\")))
    elif a.files:
        prof = mc.load_profile(a.profile or (mc.list_profiles() or [None])[0]); wm, wv = width()
        pr = mc.PRESETS.get(a.preset or "profil")
        mc.run_batch(a.files, prof, a.out or os.path.join(os.getcwd(), "Master-Ausgabe"),
                     peak_mode=a.peak or pr["peak_mode"], ceiling_db=a.ceiling if a.ceiling is not None else pr["ceiling"],
                     target_lufs=a.lufs if a.lufs is not None else pr["lufs"],
                     strength=a.strength, max_eq=a.max_eq, presence_full=a.presence_full, presence_cap=a.presence_cap, deharsh_scale=a.deharsh,
                     low_shelf_db=a.warm, high_shelf_db=a.air, bass_mono_hz=a.bass_mono, width_mode=wm, width_db_manual=wv, release_ms=a.release,
                     glue=a.glue, clip_db=a.clip, stem_gains=dict(vocals=a.vocals, drums=a.drums, bass=a.bass, other=a.other), stem_model=a.model,
                     out_bits=a.bits, do_declip=not a.no_declip)
    else:
        return False
    return True

def main():
    _ensure_streams()
    if len(sys.argv) >= 3 and sys.argv[1] == "--sep-worker":
        import audio_core as mc
        mc._sep_worker(sys.argv[2]); sys.exit(0)
    # GUI-only flags and the process serial number older macOS versions pass to app bundles are not CLI jobs
    args = [a for a in sys.argv[1:] if a not in GUI_FLAGS and not a.startswith("-psn_")]
    if args:
        try:
            if _cli(args): return
        except SystemExit:
            raise
        except Exception as e:
            print("FEHLER: %s: %s" % (type(e).__name__, e)); sys.exit(1)
    import mixsmith_gui
    mixsmith_gui.run()

if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    main()
