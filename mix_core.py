# -*- coding: utf-8 -*-
"""
Mixsmith – Mixing-Kern (ohne Oberfläche).

Mix-Profil (aus einem oder mehreren Referenzsongs):
  Song → KI-Trennung in Gesang, Drums, Bass, Gitarre, Piano/Keys, Andere → je Spur: Pegel relativ zum Mix (LU), Spektrum,
  Crest-Faktor, Transienten, Stereobreite, Links/Rechts-Balance, optional Hall/Delay (KI-Effektanalyse) → Median über die Songs.
  Zusätzlich die Mastering-Kennwerte des ganzen Songs (Lautheit, Spektrum, Breite), damit auch das Mastering übernommen werden kann.

Mix (Einzelspuren oder ein per KI zerlegter Rohmix):
  1. je Spur manuell: Low-Cut, Tiefen, Präsenz, Höhen, Kompressor, Breite, Hall, Panorama
  2. je Rolle (Gruppe aller Spuren einer Rolle): Klang, Dynamik, Transienten, Breite und Effekte in Richtung der Referenz.
     Gemessen wird an der Gruppe, angewendet auf jede ihrer Spuren (EQ, Gain-Kurven, Breite und Hall sind linear) –
     die Spuren bleiben dadurch einzeln regelbar.
  3. Balance: die Lautstärkeverhältnisse der Rollen wie in der Referenz; Fader wirken als Abweichung davon.
  4. Summe → Spitzenpegel (unbearbeiteter Mix) und optional Mastering mit dem Mastering-Kern.
"""
import os, re, json, glob, time, csv, hashlib
import numpy as np
from scipy import signal

import audio_core as mc
from audio_core import FL, Cancelled

MIX_DIR = os.path.join(mc.USER_DIR, "mix_profiles")
ROLES = ["vocals", "drums", "bass", "guitar", "piano", "other"]
ROLE_DE = {"vocals": "Gesang", "drums": "Drums", "bass": "Bass", "guitar": "Gitarre", "piano": "Piano/Keys", "other": "Andere", "rest": "Rest"}
ROLE_COLORS = {"vocals": "#f5b23a", "drums": "#ff7a7a", "bass": "#8b7cf6", "guitar": "#5ad28b", "piano": "#4fc8d6", "other": "#c58af0", "rest": "#5b6676"}
ABSENT_LU = 30.0        # a separated stem this far below the mix is only separation bleed: "not present"
LEARN_ABSENT_LU = 24.0  # stricter when learning a reference: a stem 24 LU under the mix is inaudible in it

# ============================================================== roles from file names
_ROLE_WORDS = [   # (role, whole words, substrings); checked in this order, so "bassdrum" is drums and "lead guitar" guitar
    ("drums", {"kick", "kik", "bd", "snare", "snr", "sn", "hat", "hats", "hihat", "hh", "tom", "toms", "oh", "ohs", "room", "rooms", "ride", "crash",
               "cymbal", "cymbals", "perc", "clap", "claps", "shaker", "tamb", "drum", "drums", "beat", "conga", "bongo", "cajon", "808kick", "loop"},
              ("bassdrum", "kickdrum", "overhead", "snare", "hihat", "percussion", "schlagzeug", "drum", "tambourine", "cymbal")),
    ("guitar", {"gtr", "gtrs", "guitar", "guitars", "git", "gitarre", "gitarren", "ag", "eg", "acoustic", "akustik", "strat", "tele", "riff"},
               ("guitar", "gitarre", "akustikgit")),
    ("piano", {"piano", "pno", "keys", "key", "klavier", "rhodes", "wurli", "wurlitzer", "ep", "epiano", "organ", "orgel", "hammond", "b3", "clav"},
              ("piano", "klavier", "rhodes", "wurli", "hammond", "orgel", "organ")),
    ("bass", {"bass", "bs", "sub", "808", "bassline", "kontrabass", "upright", "db"}, ("bass",)),
    ("vocals", {"vox", "vocal", "vocals", "voc", "gesang", "stimme", "chor", "choir", "bgv", "bgvs", "bv", "backing", "harmony", "harmonies", "adlib",
                "adlibs", "rap", "singer", "voice", "voices", "lv", "leadvox"}, ("vocal", "gesang", "stimme", "backing", "harmon")),
    ("other", {"synth", "synths", "pad", "pads", "strings", "str", "brass", "horn", "horns", "sax", "fx", "sfx", "violin", "cello", "flute", "arp", "lead"}, ("synth", "string")),
]

def guess_role(name):
    """Role of a track from its file name (English and German studio abbreviations). Unknown → 'other'."""
    n = os.path.splitext(os.path.basename(name))[0]
    n = re.sub(r"([a-z])([A-Z])", r"\1 \2", n).lower()
    toks = set(t for t in re.split(r"[^a-z0-9äöüß]+", n) if t)
    compact = re.sub(r"[^a-z0-9äöüß]+", "", n)
    for role, words, subs in _ROLE_WORDS:
        if toks & words or any(s in compact for s in subs): return role
    return "other"

# ============================================================== loading
def load_tracks(paths, log=print):
    """Reads tracks and brings them to one sample rate (the most common one) and one length.
    Returns (list of dict(path, name, x float32 (n,2), mono), sr)."""
    raw = []
    for p in paths:
        x, sr, mono = mc.load_audio(p, min_seconds=0.5); raw.append((p, x, sr, mono))
    if not raw: raise RuntimeError("Keine Spuren.")
    rates = [r[2] for r in raw]; sr = max(set(rates), key=rates.count)
    out = []
    for p, x, s, mono in raw:
        if s != sr:
            log("  %s: %d Hz → %d Hz" % (os.path.basename(p), s, sr)); x = signal.resample_poly(x, sr, s, axis=0)
        out.append(dict(path=p, name=os.path.splitext(os.path.basename(p))[0], x=x.astype(np.float32), mono=mono))
    n = max(len(t["x"]) for t in out)
    for t in out:
        if len(t["x"]) < n: t["x"] = np.concatenate([t["x"], np.zeros((n-len(t["x"]), 2), np.float32)])
    return out, sr

def song_parts(path, model="auto", log=print, progress=None, cancel=None):
    """A raw mix split into its stems plus 'rest' (mix minus all stems, so nothing gets lost). Returns (tracks, sr, x_mix)."""
    x, sr, _ = mc.load_audio(path)
    st = mc.song_stems(path, sr, len(x), model=model, log=log, progress=progress, cancel=cancel)
    tracks = []; tot = np.zeros_like(x)
    for r in ROLES:
        if r in st:
            tracks.append(dict(path=path, name=ROLE_DE[r], key=r, role=r, x=st[r].astype(np.float32), mono=False)); tot += st[r]
    tracks.append(dict(path=path, name=ROLE_DE["rest"], key="rest", role="rest", x=(x-tot).astype(np.float32), mono=False))
    return tracks, sr, x

# ============================================================== features
def lr_balance_db(x):
    """Level difference left minus right in dB (positive = left louder)."""
    l, r = float(np.mean(x[:, 0]**2))+1e-14, float(np.mean(x[:, 1]**2))+1e-14
    return float(np.clip(10*np.log10(l/r), -12, 12))

def stem_features(x, sr, mix_lufs):
    f = mc.track_features(x, sr); f["rel"] = f["lufs"]-mix_lufs; f["balance"] = lr_balance_db(x); return f

def _median(rows, k): return float(np.median([r[k] for r in rows]))

# ============================================================== mix profiles
def list_mix_profiles():
    return sorted((os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(MIX_DIR, "*.json"))), key=str.lower)

def load_mix_profile(name):
    with open(os.path.join(MIX_DIR, name+".json"), encoding="utf-8") as fh: p = json.load(fh)
    for r in p["roles"].values(): r["spec"] = np.array(r["spec"])
    if p.get("master"): p["master"]["spec"] = np.array(p["master"]["spec"])
    return p

def delete_mix_profile(name):
    p = os.path.join(MIX_DIR, name+".json")
    if not os.path.exists(p): raise RuntimeError("Mix-Profil nicht gefunden.")
    os.remove(p)

def master_profile_from_mix(prof):
    """The mastering part of a mix profile as mastering profile (for render_master)."""
    m = prof.get("master")
    if not m: return None
    return dict(m, name=prof["name"]+" (Mix-Referenz)", spec=np.asarray(m["spec"]))

def learn_mix_profile(files, name, model="auto", log=print, progress=None, cancel=None, analyse_fx=True, stems_dir=None, save_master=False):
    """Learns a mix profile from reference songs. Returns the profile dict (also saved to MIX_DIR)."""
    name = mc.safe_name(name)
    if not files: raise RuntimeError("Keine Referenzsongs angegeben.")
    per_role = {r: [] for r in ROLES}; masters = []; nf = len(files); used_model = None
    for i, p in enumerate(files):
        if cancel is not None and cancel.is_set(): raise Cancelled()
        base = i/nf; span = 1.0/nf
        def prog(a, b):
            return (lambda f: progress(base+span*(a+(b-a)*f))) if progress else None
        song = os.path.splitext(os.path.basename(p))[0]; log("%s" % song)
        try: x, sr, _ = mc.load_audio(p, min_seconds=5)
        except RuntimeError as e: log("  übersprungen: %s" % e); continue
        mix_l = mc.integrated(x, sr)
        masters.append(dict(lufs=mix_l, tp=mc.db(mc.true_peak(x, sr)), lra=mc.lra(x, sr), width=mc.width_db(x, sr), spec=mc.smooth_spectrum(x, sr)))
        used_model = mc.sep_plan(model, refresh=False)["model"] if model == "auto" else model
        st = mc.song_stems(p, sr, len(x), model=model, log=log, progress=prog(0.0, 0.45 if analyse_fx else 0.9), cancel=cancel)
        if stems_dir:
            dest = os.path.join(stems_dir, mc.safe_name(song)); os.makedirs(dest, exist_ok=True)
            for k, y in st.items(): mc.write_audio(os.path.join(dest, "%s - %s.wav" % (song, mc.safe_name(ROLE_DE.get(k, k)))), y, sr, 32)
        present = [r for r in ROLES if r in st]; parts = []
        for j, r in enumerate(present):
            if cancel is not None and cancel.is_set(): raise Cancelled()
            f = stem_features(st[r], sr, mix_l)
            if f["rel"] < -LEARN_ABSENT_LU:
                parts.append("%s –" % ROLE_DE[r]); continue
            if analyse_fx and f["rel"] >= -20:                 # quieter stems are mostly separation residue: no reliable effect estimate
                log("  Effektanalyse %s …" % ROLE_DE[r])
                f["fx"] = {k: v for k, v in mc.analyse_effects(st[r], sr, log=log, cancel=cancel, context=x,
                                                                 progress=prog(0.45+0.55*j/len(present), 0.45+0.55*(j+1)/len(present))).items()
                           if k in ("reverb", "delay")}
            per_role[r].append(f); parts.append("%s %+.1f" % (ROLE_DE[r], f["rel"]))
        log("  Mix %.1f LUFS · Pegel relativ zum Mix (LU): %s" % (mix_l, " · ".join(parts)))
        if analyse_fx:
            for r in present:
                if per_role[r] and per_role[r][-1].get("fx"):
                    log("    %s: %s" % (ROLE_DE[r], "; ".join(mc.describe_effect(k, v) for k, v in per_role[r][-1]["fx"].items())))
        if progress: progress((i+1)/nf)
    if not masters: raise RuntimeError("Keine verwertbaren Referenzsongs.")
    roles = {}
    for r, rows in per_role.items():
        if not rows: continue
        roles[r] = dict(n=len(rows), rel=_median(rows, "rel"), crest=_median(rows, "crest"), width=_median(rows, "width"),
                        transient=_median(rows, "transient"), lra=_median(rows, "lra"), balance=_median(rows, "balance"),
                        spec=np.median(np.array([f["spec"] for f in rows]), axis=0).tolist())
        if analyse_fx:
            fx = mc.merge_effects([f.get("fx", {}) for f in rows])
            if fx: roles[r]["fx"] = fx
    tp = float(np.median([m["tp"] for m in masters]))
    master = dict(lufs=float(np.median([m["lufs"] for m in masters])), tp=tp, lra=float(np.median([m["lra"] for m in masters])),
                  width=float(np.median([m["width"] for m in masters])), spec=np.median(np.array([m["spec"] for m in masters]), axis=0).tolist(),
                  peak_mode="sample" if tp > -0.3 else "true", n=len(masters))
    prof = dict(name=name, kind="mix", version=mc.APP_VERSION, n=len(masters), sources=[os.path.basename(p) for p in files],
                model=used_model, fx_analysed=bool(analyse_fx), created=time.strftime("%Y-%m-%d %H:%M"), roles=roles, master=master, f=FL.tolist())
    os.makedirs(MIX_DIR, exist_ok=True); out = os.path.join(MIX_DIR, name+".json")
    with open(out, "w", encoding="utf-8") as fh: json.dump(prof, fh, indent=1)
    log("Mix-Profil gespeichert: %s" % out)
    if save_master:
        mp = mc.save_profile(dict(master, name=name, source="Mix-Profil", sources=prof["sources"]))
        log("Mastering-Profil gespeichert: %s" % mp)
    return load_mix_profile(name)

def describe_role(r):
    s = "%+.1f LU · Crest %.1f dB · Breite %.1f dB" % (r["rel"], r["crest"], r["width"])
    fx = r.get("fx") or {}
    if "reverb" in fx: s += " · Hall %.1f s" % fx["reverb"]["rt60_s"]
    if "delay" in fx: s += " · Delay %.0f ms" % (fx["delay"]["time_s"]*1000)
    return s

# ============================================================== manual channel strip
CHANNEL_DEFAULTS = dict(gain_db=0.0, pan=0.0, mute=False, solo=False, lowcut_hz=0.0, low_db=0.0, presence_db=0.0, high_db=0.0,
                        comp=0.0, width_db=0.0, reverb=0.0)

def peaking(x, sr, f0, gain_db, Q=0.9):
    """RBJ peaking EQ, zero-phase (half gain per pass)."""
    if abs(gain_db) < 0.05 or f0 >= 0.45*sr: return x
    A = 10**((gain_db/2)/40); w0 = 2*np.pi*f0/sr; a = np.sin(w0)/(2*Q); c = np.cos(w0)
    b = np.array([1+a*A, -2*c, 1-a*A]); d = np.array([1+a/A, -2*c, 1-a/A])
    return signal.sosfiltfilt(signal.tf2sos(b/d[0], d/d[0]), x, axis=0)

def pan_gains(p, mono_source):
    """Left/right gains: constant-power panning for mono sources, balance control for stereo ones. p in [-1, 1] (right = +)."""
    if abs(p) < 0.005: return np.array([1.0, 1.0])
    if mono_source:
        a = (p+1)*np.pi/4; return np.array([np.cos(a), np.sin(a)])*np.sqrt(2)
    return np.array([min(1.0, 1-p), min(1.0, 1+p)])

def channel_chain(x, sr, ch, mono_source=False):
    """Manual inserts of one track (fader, panorama, mute and solo are applied live afterwards, see mixdown)."""
    c = {**CHANNEL_DEFAULTS, **(ch or {})}; y = np.asarray(x, dtype=np.float64)
    if c["lowcut_hz"] > 10: y = mc.hpf(y, sr, float(c["lowcut_hz"]), 2)
    y = mc.shelf(y, sr, 100, c["low_db"], "low"); y = peaking(y, sr, 3000, c["presence_db"]); y = mc.shelf(y, sr, 10000, c["high_db"], "high")
    if c["comp"] > 0.01:
        a = float(c["comp"]); thr = mc.gated_rms_db(y, sr)+4.0-8.0*a; before = mc.gated_rms_db(y, sr)
        y, _ = mc.compress(y, sr, thr, 1.5+4.5*a, att=0.008, rel=0.120, hop=32, knee_db=6.0)
        y = y*10**((before-mc.gated_rms_db(y, sr))/20)             # make-up: same loudness, less dynamics
    if abs(c["width_db"]) > 0.05 and not mono_source: y = mc.widen(y, sr, 200, float(c["width_db"]))
    if c["reverb"] > 0.01:
        y = mc.apply_effects(y, sr, {"reverb": dict(room_size=0.62, damping=0.5, predelay_ms=15.0, wet=0.45, strength=float(c["reverb"]))})
    return y

# ============================================================== bus analysis (reference matching per role)
MIX_DEFAULTS = dict(balance=1.0, tone=0.7, dynamics=0.6, transients=0.5, width=0.7, fx=0.0, max_eq=6.0, eq_lo=40.0, eq_hi=16000.0,
                    max_gain=12.0, peak_db=-3.0)

def bus_ops(bus, sr, ref, p, log=print):
    """Measures one role group against its reference stem. Returns operations that are applied to every track of the group."""
    ops = dict(eq=None, gain=None, width=0.0, fx=None, info={})
    if ref is None: return ops
    y = bus
    if p["tone"] > 0.01:
        corr = np.clip(p["tone"]*(ref["spec"]-mc.smooth_spectrum(bus, sr)), -p["max_eq"], p["max_eq"])
        corr = corr*np.clip(np.log2(FL/p["eq_lo"])*3+1, 0, 1)*np.clip(np.log2(p["eq_hi"]/FL)*3+1, 0, 1)
        ops["eq"] = corr; y = mc.fir_eq(bus, sr, corr); ops["info"].update(eq_min=float(corr.min()), eq_max=float(corr.max()))
    g = np.ones(len(y))
    if p["dynamics"] > 0.01:
        c0 = mc.crest_db(y); target = c0-(c0-ref["crest"])*p["dynamics"]
        if c0 > target+0.5:
            thr = mc.gated_rms_db(y, sr)+2.0
            for ratio in (1.5, 2.0, 3.0, 4.0, 6.0):
                gc, _ = mc.compress_gain(y, sr, thr, ratio)
                if mc.crest_db(y*gc[:, None]) <= target+0.5: break
            before = mc.gated_rms_db(y, sr); g = gc*10**((before-mc.gated_rms_db(y*gc[:, None], sr))/20); ops["info"]["ratio"] = ratio
    if p["transients"] > 0.01:
        yy = y*g[:, None]; d = float(np.clip((ref["transient"]-mc.transient_db(yy, sr))*p["transients"], -4.0, 6.0))
        g = g*mc.transient_gain(yy, sr, d); ops["info"]["transient"] = d
    if not np.allclose(g, 1.0): ops["gain"] = g.astype(np.float32)
    if p["width"] > 0.01:
        ops["width"] = float(np.clip(p["width"]*(ref["width"]-mc.width_db(y*g[:, None], sr)), -6, 6))
    if p["fx"] > 0.01 and ref.get("fx"):
        ops["fx"] = {k: dict(v, strength=p["fx"]) for k, v in ref["fx"].items() if k in ("reverb", "delay")}
    return ops

def apply_ops(x, sr, ops):
    y = x
    if ops.get("eq") is not None: y = mc.fir_eq(y, sr, ops["eq"])
    if ops.get("gain") is not None: y = y*ops["gain"][:len(y), None]
    if abs(ops.get("width", 0.0)) > 0.05: y = mc.widen(y, sr, 200, ops["width"])
    if ops.get("fx"): y = mc.apply_effects(y, sr, ops["fx"])
    return y

def balance_gains(levels, ref_roles, strength, max_gain, loudest=None):
    """dB gains per role so that the level differences between the roles follow the reference.
    levels: role -> LUFS of the processed group (faders at 0 dB). Roles far below the loudest group (bleed, silence)
    or missing in the reference keep their level. The mean change is 0 dB (the mix keeps its overall level)."""
    loudest = max(levels.values()) if loudest is None else loudest
    use = [r for r, L in levels.items() if r in (ref_roles or {}) and L > loudest-ABSENT_LU]
    gains = {r: 0.0 for r in levels}
    if strength <= 0 or len(use) < 2: return gains
    C = float(np.mean([levels[r]-ref_roles[r]["rel"] for r in use]))
    for r in use: gains[r] = float(np.clip(strength*(ref_roles[r]["rel"]+C-levels[r]), -max_gain, max_gain))
    return gains

# ============================================================== render
def active_mask(channels):
    solo = any(c.get("solo") for c in channels)
    return [(not c.get("mute")) and (c.get("solo") or not solo) for c in channels]

def render_session(tracks, sr, prof=None, channels=None, log=print, progress=None, cancel=None, **kw):
    """Mixes tracks (dicts with x, role, mono). channels: manual settings per track (list, same order).
    Returns dict(parts = float32 (n,2) per track, processed and balanced, fader not applied;
    role_gain, info per role, levels) – the mix is sum(parts[i] * fader_i) over the active tracks."""
    p = {**MIX_DEFAULTS, **kw}; channels = channels or [{} for _ in tracks]
    def step(f):
        if cancel is not None and cancel.is_set(): raise Cancelled()
        if progress: progress(f)
    roles = sorted({t["role"] for t in tracks}, key=lambda r: (ROLES+["rest"]).index(r) if r in ROLES+["rest"] else 99)
    ref_roles = (prof or {}).get("roles", {}); nt = len(tracks)
    pre = []
    for i, (t, ch) in enumerate(zip(tracks, channels)):
        pre.append(channel_chain(t["x"], sr, ch, mono_source=t.get("mono", False))); step(0.35*(i+1)/nt)
    parts = [None]*nt; info = {}; levels = {}
    for j, r in enumerate(roles):
        idx = [i for i, t in enumerate(tracks) if t["role"] == r]
        bus = np.sum([pre[i] for i in idx], axis=0)
        L0 = mc.integrated(bus, sr)
        ref = ref_roles.get(r) if (r != "rest" and prof is not None and L0 > -70) else None
        ops = bus_ops(bus, sr, ref, p, log=log)
        for i in idx: parts[i] = apply_ops(pre[i], sr, ops); pre[i] = None
        levels[r] = mc.integrated(np.sum([parts[i] for i in idx], axis=0), sr)
        info[r] = dict(ops["info"], width=ops["width"], fx=ops["fx"], ref=ref is not None, lufs_before=L0)
        step(0.35+0.5*(j+1)/len(roles))
    loudest = max((L for r, L in levels.items() if r != "rest"), default=max(levels.values()))
    gains = balance_gains({r: L for r, L in levels.items() if r != "rest"}, ref_roles if prof is not None else {}, p["balance"], p["max_gain"], loudest)
    gains["rest"] = 0.0
    for i, t in enumerate(tracks):
        g = gains.get(t["role"], 0.0)
        parts[i] = (parts[i]*10**(g/20)).astype(np.float32)
    for r in roles:
        info[r]["gain"] = gains.get(r, 0.0); info[r]["lufs_after"] = levels[r]+gains.get(r, 0.0)
        info[r]["absent"] = r != "rest" and levels[r] <= loudest-ABSENT_LU
    step(0.95)
    return dict(parts=parts, sr=sr, info=info, roles=roles, levels=levels)

def fader_gains(channels, tracks=None):
    """(n, 2) left/right gains per track from fader, panorama, mute and solo."""
    act = active_mask(channels); G = []
    for i, ch in enumerate(channels):
        mono = bool(tracks[i].get("mono")) if tracks else False
        G.append(pan_gains(float(ch.get("pan", 0.0)), mono)*(10**(float(ch.get("gain_db", 0.0))/20) if act[i] else 0.0))
    return np.array(G)

def mixdown(parts, channels, tracks=None):
    """Sum of the parts with faders, panorama, mute and solo."""
    y = np.zeros(parts[0].shape, np.float64)
    for x, g in zip(parts, fader_gains(channels, tracks)):
        if g[0] or g[1]: y += x.astype(np.float64)*g[None, :]
    return y

def balance_report(res, prof, tracks, channels):
    """Level of every role group relative to the whole mix (LU, with faders, mute and solo) next to the reference value."""
    ref = (prof or {}).get("roles", {}); rows = []; sr = res["sr"]; act = active_mask(channels); G = fader_gains(channels, tracks)
    mix = mixdown(res["parts"], channels, tracks); L_mix = mc.integrated(mix, sr)
    for r in res["roles"]:
        if r == "rest": continue
        idx = [i for i, t in enumerate(tracks) if t["role"] == r and act[i]]
        L = mc.integrated(np.sum([res["parts"][i].astype(np.float64)*G[i][None, :] for i in idx], axis=0), sr) if idx else -100.0
        rows.append(dict(role=r, rel=L-L_mix if L > -70 else None, ref=ref[r]["rel"] if r in ref else None, gain=res["info"][r]["gain"],
                         absent=res["info"][r]["absent"], muted=not idx))
    return rows, L_mix

# ============================================================== finishing
def finish_mix(y, sr, peak_db=-3.0):
    """Unmastered mix: normalised to the given true-peak level (headroom for mastering)."""
    tp = mc.true_peak(y, sr)
    return y*(10**(peak_db/20)/max(tp, 1e-9)) if tp > 1e-9 else y

def write_mix(name, out_dir, y, sr, bits=24, parts=None, tracks=None, channels=None, gain=1.0, taken=None, protect=()):
    """Writes '<name> - Mix.wav' and optionally the processed tracks into '<name> - Spuren/'. Returns the paths."""
    os.makedirs(out_dir, exist_ok=True); name = mc.safe_name(name)
    out = mc.output_path(out_dir, os.path.join(out_dir, name+" - Mix.wav"), taken, protect=protect, tag="neu", src_is_input=False)
    mc.write_audio(out, y, sr, bits); written = [out]
    if parts is not None:
        d = os.path.join(out_dir, name+" - Spuren"); os.makedirs(d, exist_ok=True); G = fader_gains(channels, tracks)
        for i, (x, t) in enumerate(zip(parts, tracks)):
            if not (G[i][0] or G[i][1]): continue
            z = x.astype(np.float64)*gain*G[i][None, :]
            b = 32 if np.max(np.abs(z)) > 1.0 else bits
            op = os.path.join(d, "%02d %s.wav" % (i+1, mc.safe_name(t["name"]))); mc.write_audio(op, z, sr, b); written.append(op)
    return written

def write_mix_protocol(rows, out_dir):
    rp = os.path.join(out_dir, "Mix-Protokoll.csv")
    with open(rp, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["Song", "Rolle", "Pegel vorher (LUFS)", "Pegel nachher (LUFS)", "Balance-Korrektur (dB)", "Relativ zum Mix (LU)", "Referenz (LU)",
                    "EQ min", "EQ max", "Kompression", "Transienten (dB)", "Breite (dB)", "Effekte"])
        for song, res, prof, tracks, channels in rows:
            rep = {b["role"]: b for b in balance_report(res, prof, tracks, channels)[0]}
            for r in res["roles"]:
                i = res["info"][r]; b = rep.get(r, {})
                w.writerow([song, ROLE_DE.get(r, r), "%.1f" % i["lufs_before"], "%.1f" % i["lufs_after"], "%+.1f" % i["gain"],
                            "%.1f" % b["rel"] if b.get("rel") is not None else "", "%.1f" % b["ref"] if b.get("ref") is not None else "",
                            "%.1f" % i.get("eq_min", 0), "%.1f" % i.get("eq_max", 0), "1:%.1f" % i["ratio"] if "ratio" in i else "",
                            "%+.1f" % i.get("transient", 0), "%+.1f" % i.get("width", 0), ", ".join(i["fx"]) if i.get("fx") else ""])
    return rp

def master_settings(preset="profil"):
    """Keyword arguments for render_master from a platform preset."""
    d = mc.PRESETS.get(preset, mc.PRESETS["profil"])
    return dict(target_lufs=d["lufs"], peak_mode=d["peak_mode"], ceiling_db=d["ceiling"])

def process_mix(tracks, sr, name, out_dir, prof=None, channels=None, master=None, master_kw=None, bits=24, save_parts=False,
                log=print, progress=None, cancel=None, taken=None, protect=(), **kw):
    """Whole job for one song: render, mixdown, write mix (+ tracks), optionally master. Returns (res, dict of outputs)."""
    p = {**MIX_DEFAULTS, **kw}; channels = channels or [{} for _ in tracks]
    prog = (lambda a, b: (lambda f: progress(a+(b-a)*f))) if progress else (lambda a, b: None)
    res = render_session(tracks, sr, prof, channels, log=log, progress=prog(0.0, 0.7 if master else 0.9), cancel=cancel, **p)
    raw = mixdown(res["parts"], channels, tracks); tp = mc.true_peak(raw, sr); gain = 10**(p["peak_db"]/20)/max(tp, 1e-9)
    y = raw*gain; outs = dict(mix=None, master=None, parts=[])
    files = write_mix(name, out_dir, y, sr, bits, res["parts"] if save_parts else None, tracks, channels, gain, taken, protect)
    outs["mix"] = files[0]; outs["parts"] = files[1:]
    L = mc.integrated(y, sr)
    for b in balance_report(res, prof, tracks, channels)[0]:
        if b["absent"]: log("  %-11s nicht vorhanden (nur Übersprechen) – unverändert" % ROLE_DE[b["role"]]); continue
        if b["rel"] is None: continue
        log("  %-11s %+5.1f LU%s  (Korrektur %+.1f dB)" % (ROLE_DE[b["role"]], b["rel"], ("  Ziel %+.1f" % b["ref"]) if b["ref"] is not None else "", b["gain"]))
    log("  → Mix: %.1f LUFS, Spitze %.1f dBTP · %s" % (L, p["peak_db"], outs["mix"]))
    if master is not None:
        if progress: progress(0.72)
        ym, info = mc.render_master(y, sr, master, log=log, cancel=cancel, progress=prog(0.72, 0.98), **(master_kw or {}))
        mp = mc.output_path(out_dir, os.path.join(out_dir, mc.safe_name(name)+" - Master.wav"), taken, protect=protect, tag="neu", src_is_input=False)
        mc.write_audio(mp, ym, sr, bits); outs["master"] = mp
        log("  → Master: %.1f LUFS, %+.1f dBTP (Limiter %.1f dB) · %s" % (mc.integrated(ym, sr), mc.db(mc.true_peak(ym, sr)), info["limiter_gr"], mp))
    return res, outs

def session_key(paths):
    """Short id of a multitrack session (for names/caches)."""
    return hashlib.sha1("|".join(sorted(os.path.abspath(p) for p in paths)).encode()).hexdigest()[:10]
