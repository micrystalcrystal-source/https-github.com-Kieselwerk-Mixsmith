# -*- coding: utf-8 -*-
"""
Mixsmith – Audio-Kern (ohne Oberfläche): Messung, Mastering-Kette, Spur-Angleich, KI-Stem-Trennung.
Das Mixing (Mix-Profile, Mischpult, Referenz-Mix) liegt in mix_core.py und baut auf diesen Funktionen auf.

Mastering-Kette je Titel:
  1. Restauration: Hochpass 20 Hz, De-Clipping abgeschnittener Wellenberge (nur wenn nötig)
  2. Stem-Balance (optional): KI-Trennung in Gesang/Drums/Bass/Rest, Pegel einzelner Gruppen verschieben (verlustfrei: Mix + Δ·Stem)
  3. Spektrum-Angleich an ein Referenzprofil (1/3-Oktav-geglättet, linearphasiger FIR, Präsenzschutz 2-8 kHz, dynamisches De-Harsh)
  4. Wärme/Luft-Shelves, Bass mono, Stereobreite
  5. Glue-Kompressor (optional), Soft-Clipper (4x Oversampling) und Lookahead-Limiter auf Ziel-LUFS
  6. 24-Bit-WAV (oder 16 Bit mit TPDF-Dither) in nativer Sample-Rate

Stem-Trennung (audio-separator) läuft in einem eigenen Prozess; die Einstellungen werden nach freiem Grafikspeicher
gestaffelt (fp16, kleinere Blöcke, kleineres Modell) und bei Speichermangel automatisch heruntergestuft, zuletzt CPU.
"""
import os, sys, json, math, time, glob, csv, re, hashlib, shutil, subprocess, threading
import numpy as np
import soundfile as sf
from scipy import signal, interpolate

try:
    import pyloudnorm as pyln
except ImportError:
    pyln = None
try:
    from numba import njit
except Exception:
    def njit(f): return f

APP_NAME = "Mixsmith"
APP_VERSION = "1.0.1"
FROZEN = getattr(sys, "frozen", False)
HERE = os.path.dirname(os.path.abspath(sys.executable if FROZEN else __file__))
RES = getattr(sys, "_MEIPASS", HERE)                      # bundled resources (PyInstaller onefile) or program folder
def _user_base():
    if sys.platform == "win32": return os.environ.get("APPDATA", os.path.expanduser("~"))
    if sys.platform == "darwin": return os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    return os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
USER_DIR = os.path.join(_user_base(), APP_NAME)
LEGACY_DIR = os.path.join(_user_base(), "Mastering-Tool")     # data folder of the predecessor (Mastering-Tool 2.x)
USER_PROFILE_DIR = os.path.join(USER_DIR, "profiles")    # learned profiles (always writable, survives updates)
INSTR_DIR = os.path.join(USER_DIR, "instrument_profiles")
CACHE_DIR = os.path.join(USER_DIR, "cache")
BUILTIN = {"Laut und hell", "Streaming-Standard"}   # protected, cannot be deleted
RENAMED = {"DistroKid-Referenz": "Laut und hell"}      # old built-in names (1.0.0) still found in settings and mix profiles
AUDIO_EXT = (".wav", ".flac", ".aif", ".aiff", ".ogg", ".mp3")
FL = np.logspace(np.log10(30), np.log10(18000), 200)    # log-frequency grid of all profiles
MIN_SECONDS = 1.0

class Cancelled(Exception):
    pass

def migrate_legacy():
    """First start: take over learned profiles, instrument profiles and hardware settings of Mastering-Tool 2.x.
    Nothing is deleted there; the (large) stem cache is not copied."""
    marker = os.path.join(USER_DIR, ".migrated")
    if os.path.exists(marker) or not os.path.isdir(LEGACY_DIR): return []
    moved = []
    try:
        for sub in ("profiles", "instrument_profiles"):
            src = os.path.join(LEGACY_DIR, sub); dst = os.path.join(USER_DIR, sub)
            for f in glob.glob(os.path.join(src, "*.json")):
                os.makedirs(dst, exist_ok=True); t = os.path.join(dst, os.path.basename(f))
                if not os.path.exists(t): shutil.copy2(f, t); moved.append(t)
        old = os.path.join(LEGACY_DIR, "settings.json")
        if os.path.exists(old) and not os.path.exists(os.path.join(USER_DIR, "settings.json")):
            with open(old, encoding="utf-8") as fh: d = json.load(fh)
            keep = {k: d[k] for k in ("force_cpu", "vram_limit", "open_after", "last_dir") if k in d}
            keep["asked_shortcut"] = False
            for page in ("master", "track", "stems"):
                if page in d: keep[page] = d[page]
            save_settings(keep); moved.append("settings.json")
        os.makedirs(USER_DIR, exist_ok=True)
        with open(marker, "w", encoding="utf-8") as fh: fh.write("\n".join(moved))
    except Exception:
        pass
    return moved

def res_path(name):
    for d in (RES, HERE):
        p = os.path.join(d, name)
        if os.path.exists(p): return p
    return None

def builtin_profile_dirs():
    out = []
    for d in (os.path.join(HERE, "profiles"), os.path.join(RES, "profiles")):
        if os.path.isdir(d) and d not in out: out.append(d)
    return out

def safe_name(name):
    """Profile/file name without characters Windows forbids."""
    n = re.sub(r'[\\/:*?"<>|]+', "-", str(name)).strip().strip(".")
    return n or "Profil"

def audio_files_in(folder):
    return sorted(p for p in glob.glob(os.path.join(folder, "*")) if p.lower().endswith(AUDIO_EXT))

# ============================================================== basics
def db(x): return 20*np.log10(max(float(x), 1e-12))

def hpf(x, sr, f, order=2):
    sos = signal.butter(order, f, "highpass", fs=sr, output="sos"); return signal.sosfiltfilt(sos, x, axis=0)

def ms(x): return (x[:, 0]+x[:, 1])/2, (x[:, 0]-x[:, 1])/2
def lr(M, S): return np.stack([M+S, M-S], axis=1)

def true_peak(x, sr, osf=4):
    up = signal.resample_poly(x, osf, 1, axis=0) if osf > 1 else x
    return float(np.max(np.abs(up)))

def integrated(x, sr):
    if pyln is None: raise RuntimeError("pyloudnorm fehlt: pip install pyloudnorm")
    if len(x) < int(0.5*sr): return -100.0
    v = pyln.Meter(sr).integrated_loudness(x); return float(v) if np.isfinite(v) else -100.0

def k_short_term(x, sr, win=3.0, hop=0.1):
    meter = pyln.Meter(sr); y = x.copy()
    for f in meter._filters.values(): y = f.apply_filter(y)
    sq = (y**2).sum(axis=1); cs = np.concatenate([[0.0], np.cumsum(sq)])
    W = int(win*sr); H = int(hop*sr); starts = np.arange(0, max(1, len(sq)-W), H)
    msq = (cs[np.minimum(starts+W, len(sq))]-cs[starts])/W
    return starts/sr+win/2, -0.691+10*np.log10(np.maximum(msq, 1e-20))

def lra(x, sr):
    """Loudness Range nach EBU Tech 3342 (Kurzzeit 3 s, absolutes Gate −70, relatives −20 LU, 10.–95. Perzentil)."""
    t, st = k_short_term(x, sr); v = st[st > -70]
    if len(v) < 2: return 0.0
    rel = 10*np.log10(np.mean(10**(v/10)))-20; v = v[v > rel]
    return float(np.percentile(v, 95)-np.percentile(v, 10)) if len(v) > 1 else 0.0

def correlation(x):
    a, b = x[:, 0], x[:, 1]
    if np.std(a) < 1e-9 or np.std(b) < 1e-9: return 1.0
    return float(np.corrcoef(a, b)[0, 1])

def width_db(x, sr, f=200):
    M, S = ms(x); Sh = hpf(S[:, None], sr, f)[:, 0]; Mh = hpf(M[:, None], sr, f)[:, 0]
    return float(10*np.log10((np.mean(Sh**2)+1e-20)/(np.mean(Mh**2)+1e-20)))

def widen(x, sr, f, gain_db):
    M, S = ms(x); Sh = hpf(S[:, None], sr, f)[:, 0]; return lr(M, S+Sh*(10**(gain_db/20)-1))

def bass_mono(x, sr, f=150):
    M, S = ms(x); return lr(M, hpf(S[:, None], sr, f, 4)[:, 0])

def smooth_spectrum(x, sr):
    """1/3-octave gaussian-smoothed Welch spectrum on the FL grid, normalised to its 200 Hz - 4 kHz mean.
    Grid points above the file's Nyquist frequency repeat the last valid value."""
    f, P = signal.welch(x.mean(axis=1), sr, nperseg=min(8192, len(x))); Pdb = 10*np.log10(P+1e-20)
    lf = np.log2(np.maximum(f, 1)); out = np.empty(len(FL)); ok = FL < 0.95*sr/2
    for i, fc in enumerate(FL):
        if not ok[i]: out[i] = out[i-1]; continue
        w = np.exp(-0.5*((lf-np.log2(fc))/(1/6))**2); w[f < 20] = 0; out[i] = np.sum(w*Pdb)/(np.sum(w)+1e-20)
    return out-np.mean(out[(FL >= 200) & (FL <= 4000)])

def fir_eq(x, sr, corr_db):
    """Linear-phase FIR from a correction curve on the FL grid (dB). Works at any sample rate:
    grid points at or above Nyquist are dropped, the filter length grows with the sample rate."""
    nyq = sr/2; keep = FL < 0.97*nyq; f = FL[keep]; g = corr_db[keep]
    taps = max(4095, int(2**math.ceil(math.log2(sr/11.0)))-1)
    fir = signal.firwin2(taps, np.concatenate([[0], f, [nyq]]), 10**(np.concatenate([[g[0]], g, [0]])/20), fs=sr)
    return np.stack([signal.fftconvolve(x[:, c], fir, mode="same") for c in range(x.shape[1])], axis=1)

# ============================================================== audio I/O
def load_audio(path, min_seconds=MIN_SECONDS):
    """Reads any soundfile format as float64 stereo. Returns (x, sr, was_mono). Rejects too short or silent files."""
    try:
        x, sr = sf.read(path, dtype="float64", always_2d=True)
    except Exception as e:
        raise RuntimeError("Datei kann nicht gelesen werden (%s)." % e)
    mono = x.shape[1] == 1
    if mono: x = np.repeat(x, 2, axis=1)
    x = x[:, :2]
    if len(x) < int(min_seconds*sr): raise RuntimeError("Datei ist zu kurz (mindestens %.0f s nötig)." % min_seconds)
    if np.max(np.abs(x)) < 1e-6: raise RuntimeError("Datei ist stumm.")
    return x, sr, mono

def write_audio(path, y, sr, bits=24):
    if int(bits) == 32:                 # 32-bit float keeps peaks above 0 dBFS (e.g. stems of loud masters)
        sf.write(path, y, sr, subtype="FLOAT"); return path
    y = np.clip(y, -1, 1)
    if int(bits) == 16:
        rng = np.random.default_rng(1); y = np.clip(y+(rng.random(y.shape)-rng.random(y.shape))/32768.0, -1, 1)   # TPDF ±1 LSB
        sf.write(path, y, sr, subtype="PCM_16")
    else:
        sf.write(path, y, sr, subtype="PCM_24")
    return path

def _norm(p): return os.path.normcase(os.path.abspath(p))

def output_path(out_dir, src, taken=None, suffix="", protect=(), tag="Master", src_is_input=True):
    """Output file next to nothing it could destroy: never the source file itself nor any other source file of the batch
    (protect), never twice the same name in one batch (taken). src_is_input=False: src only gives the wanted name."""
    base = os.path.splitext(os.path.basename(src))[0]+suffix; taken = taken if taken is not None else set()
    guard = ({_norm(src)} if src_is_input else set()) | {_norm(p) for p in protect}
    cand = os.path.join(out_dir, base+".wav"); i = 2
    def clash(p): return _norm(p) in guard or _norm(p) in taken
    if clash(cand): cand = os.path.join(out_dir, "%s (%s).wav" % (base, tag))
    while clash(cand): cand = os.path.join(out_dir, "%s (%s %d).wav" % (base, tag, i)); i += 1
    taken.add(_norm(cand)); return cand

def envelope_preview(x, points=1200):
    """Min/max pairs for waveform drawing."""
    m = x.mean(axis=1); n = len(m); step = max(1, n//points); k = n//step
    b = m[:k*step].reshape(k, step); return np.stack([b.min(axis=1), b.max(axis=1)], axis=1).astype(np.float32)

def analyse(x, sr):
    return dict(lufs=integrated(x, sr), tp=db(true_peak(x, sr)), lra=lra(x, sr), width=width_db(x, sr), corr=correlation(x),
                clips=clip_runs(x), spec=smooth_spectrum(x, sr), dur=len(x)/sr, sr=sr)

# ============================================================== restoration
def declip(x, thr=0.995, K=8, maxover=2.0):
    y = x.copy(); fixed = 0; n = len(x)
    for ch in range(x.shape[1]):
        a = np.abs(x[:, ch]); m = a >= thr
        if not m.any(): continue
        d = np.diff(np.concatenate([[0], m.astype(np.int8), [0]])); starts = np.where(d == 1)[0]; ends = np.where(d == -1)[0]
        for s, e in zip(starts, ends):
            if e-s < 2: continue
            idx = np.concatenate([np.arange(max(0, s-K), s), np.arange(e, min(n, e+K))]); idx = idx[~m[idx]]
            if len(idx) < 4 or (idx < s).sum() < 2 or (idx >= e).sum() < 2: continue
            v = interpolate.CubicSpline(idx, x[idx, ch])(np.arange(s, e)); sgn = float(np.sign(x[s, ch])) or 1.0
            mag = np.maximum(sgn*v, thr); r = maxover/thr; mag = thr*(1+(r-1)*np.tanh((mag/thr-1)/(r-1)))
            y[s:e, ch] = sgn*mag; fixed += 1
    return y, fixed

def clip_runs(x, thr=0.999):
    total = 0
    for ch in range(x.shape[1]):
        m = np.abs(x[:, ch]) >= thr
        if not m.any(): continue
        d = np.diff(np.concatenate([[0], m.astype(int), [0]])); runs = np.where(d == -1)[0]-np.where(d == 1)[0]; total += int((runs >= 3).sum())
    return total

# ============================================================== dynamics
@njit
def _smooth(t, a_att, a_rel):
    g = np.zeros_like(t); prev = 0.0
    for i in range(len(t)):
        a = a_att if t[i] > prev else a_rel; prev = prev+(t[i]-prev)*a; g[i] = prev
    return g

def _block_db(x, hop):
    n = len(x)//hop; return 10*np.log10((x[:n*hop]**2).reshape(n, hop, -1).mean(axis=(1, 2))+1e-14), n

def dyn_band(x, sr, lo, hi, ratio=2.0, max_db=3.0, hop=64, pct=80):
    """Reduces [lo,hi] only when that band exceeds its typical loud level (de-harsh / de-ess style)."""
    sos = signal.butter(2, [lo, min(hi, 0.45*sr)], "bandpass", fs=sr, output="sos"); b = signal.sosfiltfilt(sos, x, axis=0)
    be, n = _block_db(b, hop); loud = _block_db(x, hop)[0] > -40
    if loud.sum() < 10: return x
    thr = np.percentile(be[loud], pct); t = np.minimum(np.maximum(be-thr, 0)*(1-1/ratio), max_db)
    fc = sr/hop; g = _smooth(t, 1-math.exp(-1/(0.005*fc)), 1-math.exp(-1/(0.150*fc)))
    G = np.interp(np.arange(len(x)), np.arange(n)*hop+hop/2, g)
    return x-b*(1-10**(-G/20))[:, None]

def gated_rms_db(x, sr, hop=None):
    """RMS level of the audible part only (blocks within 30 dB of the loudest), so pauses do not lower it."""
    hop = hop or max(64, int(0.05*sr)); e, n = _block_db(x, hop)
    if n == 0: return -120.0
    loud = e > e.max()-30
    return float(10*np.log10(np.mean(10**(e[loud]/10))+1e-20))

def compress_gain(x, sr, thr_db, ratio, att=0.010, rel=0.150, hop=32, knee_db=6.0):
    """Gain curve (linear, per sample) of a stereo-linked feed-forward compressor with soft knee, and its maximum reduction in dB."""
    n = len(x)//hop
    if n < 2: return np.ones(len(x)), 0.0
    e = 10*np.log10((x[:n*hop]**2).reshape(n, hop, -1).mean(axis=(1, 2))+1e-18)
    over = e-thr_db; k = knee_db/2
    t = np.where(over <= -k, 0.0, np.where(over >= k, over*(1-1/ratio), (1-1/ratio)*(over+k)**2/(4*k)))
    fc = sr/hop; g = _smooth(t, 1-math.exp(-1/(att*fc)), 1-math.exp(-1/(rel*fc)))
    return 10**(-np.interp(np.arange(len(x)), np.arange(n)*hop+hop/2, g)/20), float(g.max())

def compress(x, sr, thr_db, ratio, att=0.010, rel=0.150, hop=32, knee_db=6.0):
    """Stereo-linked feed-forward compressor with soft knee (gain computed on block RMS, applied smoothly)."""
    g, gr = compress_gain(x, sr, thr_db, ratio, att, rel, hop, knee_db)
    return x*g[:, None], gr

def glue(x, sr, amount):
    """Gentle bus compression ('glue'): 1.4:1 … 2.5:1, 30 ms attack, 200 ms release, threshold below the loud level.
    amount 0..1; about 1-3 dB gain reduction on loud passages."""
    if amount <= 0.01: return x, 0.0
    hop = max(64, int(0.05*sr)); e, n = _block_db(x, hop); loud = e[e > e.max()-20]
    thr = float(np.percentile(loud, 70))-1.0-3.0*amount
    return compress(x, sr, thr, 1.4+1.1*amount, att=0.030, rel=0.200, hop=64, knee_db=8.0)

def soft_clip(x, thr, knee=0.7, osf=4):
    """Oversampled soft clipper: linear up to knee*thr, then a tanh curve that approaches thr."""
    up = signal.resample_poly(x, osf, 1, axis=0) if osf > 1 else x
    a = np.abs(up); k = knee*thr; over = a > k
    if over.any():
        up = up.copy(); up[over] = np.sign(up[over])*(k+(thr-k)*np.tanh((a[over]-k)/(thr-k)))
    y = signal.resample_poly(up, 1, osf, axis=0) if osf > 1 else up
    return y[:len(x)]

@njit
def _release(g_att, a_rel):
    g = np.empty_like(g_att); prev = 1.0
    for i in range(len(g_att)):
        up = prev+(1.0-prev)*a_rel; prev = g_att[i] if g_att[i] < up else up; g[i] = prev
    return g

def limiter(x, sr, ceiling_db, osf=4, lookahead_ms=2.0, hold_ms=1.0, release_ms=120.0, D=32):
    xo = signal.resample_poly(x, osf, 1, axis=0) if osf > 1 else x; fso = sr*osf
    n = len(xo); nb = int(math.ceil(n/D)); pad = nb*D-n
    xp = np.concatenate([xo, np.zeros((pad, xo.shape[1]))]) if pad else xo
    p = np.abs(xp).reshape(nb, D, -1).max(axis=(1, 2)); ceil = 10**(ceiling_db/20)
    g_req = np.minimum(1.0, ceil/np.maximum(p, 1e-9))
    L = max(1, int(math.ceil(lookahead_ms/1000*fso/D))); H = max(0, int(math.ceil(hold_ms/1000*fso/D)))
    g_min = np.lib.stride_tricks.sliding_window_view(np.concatenate([g_req, np.ones(L+H)]), L+H).min(axis=1)[:nb]
    g_att = np.convolve(np.concatenate([np.ones(L-1), g_min]), np.ones(L)/L, mode="valid")[:nb]
    g = _release(g_att, 1-math.exp(-D/(fso*release_ms/1000)))
    yo = np.clip(xo*np.repeat(g, D)[:n][:, None], -ceil, ceil)
    y = signal.resample_poly(yo, 1, osf, axis=0) if osf > 1 else yo
    return y[:len(x)], float(-20*np.log10(max(g.min(), 1e-9)))

def shelf(x, sr, f0, gain_db, kind="low", Q=0.7071):
    """RBJ shelving filter, zero-phase (applied forward+backward with half the gain each pass)."""
    if abs(gain_db) < 0.05 or f0 >= 0.45*sr: return x
    A = 10**((gain_db/2)/40); w0 = 2*np.pi*f0/sr; a = np.sin(w0)/(2*Q); c = np.cos(w0); s2 = 2*np.sqrt(A)*a
    if kind == "low":
        b = [A*((A+1)-(A-1)*c+s2), 2*A*((A-1)-(A+1)*c), A*((A+1)-(A-1)*c-s2)]; d = [(A+1)+(A-1)*c+s2, -2*((A-1)+(A+1)*c), (A+1)+(A-1)*c-s2]
    else:
        b = [A*((A+1)+(A-1)*c+s2), -2*A*((A-1)+(A+1)*c), A*((A+1)+(A-1)*c-s2)]; d = [(A+1)-(A-1)*c+s2, 2*((A-1)-(A+1)*c), (A+1)-(A-1)*c-s2]
    sos = signal.tf2sos(np.array(b)/d[0], np.array(d)/d[0]); return signal.sosfiltfilt(sos, x, axis=0)

# ============================================================== profiles
def learn_profile(folder, name, log=print, progress=None, cancel=None):
    name = safe_name(name)
    if name in BUILTIN: raise RuntimeError(f"„{name}“ ist ein Standardprofil und kann nicht überschrieben werden. Bitte einen anderen Namen wählen.")
    files = audio_files_in(folder) if isinstance(folder, str) else list(folder)
    if not files: raise RuntimeError("Keine Audiodateien im Referenzordner.")
    rows = []
    for i, p in enumerate(files):
        if cancel is not None and cancel.is_set(): raise Cancelled()
        if progress: progress(i/len(files))
        try: x, sr, _ = load_audio(p, min_seconds=5)
        except RuntimeError as e: log(f"  {os.path.basename(p)} übersprungen: {e}"); continue
        log(os.path.splitext(os.path.basename(p))[0])
        r = dict(lufs=integrated(x, sr), tp=db(true_peak(x, sr)), lra=lra(x, sr), width=width_db(x, sr), spec=smooth_spectrum(x, sr))
        rows.append(r); log(f"  {r['lufs']:.1f} LUFS, TP {r['tp']:+.2f} dBTP, LRA {r['lra']:.1f}, Breite {r['width']:.1f} dB")
    if not rows: raise RuntimeError("Keine verwertbaren Referenzen gefunden.")
    prof = dict(name=name, source=folder if isinstance(folder, str) else "Dateiliste", n=len(rows),
                lufs=float(np.median([r["lufs"] for r in rows])), tp=float(np.median([r["tp"] for r in rows])),
                lra=float(np.median([r["lra"] for r in rows])), width=float(np.median([r["width"] for r in rows])),
                f=FL.tolist(), spec=np.median(np.array([r["spec"] for r in rows]), axis=0).tolist(),
                peak_mode="sample" if np.median([r["tp"] for r in rows]) > -0.3 else "true")
    out = save_profile(prof)
    log(f"Profil gespeichert: {out}  ({prof['lufs']:.1f} LUFS, Breite {prof['width']:.1f} dB, Peak-Modus {prof['peak_mode']})")
    return prof

def save_profile(prof):
    """Writes a mastering profile (dict with name, lufs, tp, lra, width, spec on the FL grid, peak_mode) to the user folder."""
    name = safe_name(prof["name"])
    if name in BUILTIN: raise RuntimeError(f"„{name}“ ist ein Standardprofil und kann nicht überschrieben werden.")
    d = dict(prof, name=name, spec=np.asarray(prof["spec"]).tolist(), f=FL.tolist())
    os.makedirs(USER_PROFILE_DIR, exist_ok=True); out = os.path.join(USER_PROFILE_DIR, name+".json")
    with open(out, "w", encoding="utf-8") as fh: json.dump(d, fh, indent=1)
    return out

def profile_path(name):
    name = RENAMED.get(name, name)
    for d in [USER_PROFILE_DIR]+builtin_profile_dirs():
        p = os.path.join(d, name+".json")
        if os.path.exists(p): return p
    return None

def list_profiles():
    names = set()
    for d in builtin_profile_dirs()+[USER_PROFILE_DIR]:
        names |= {os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(d, "*.json"))}
    return sorted(names, key=lambda n: (n not in BUILTIN, n.lower()))

def load_profile(name):
    p = profile_path(name)
    if not p: raise RuntimeError("Profil „%s“ nicht gefunden." % name)
    with open(p, encoding="utf-8") as fh: d = json.load(fh)
    d["spec"] = np.array(d["spec"]); return d

def delete_profile(name):
    if name in BUILTIN: raise RuntimeError(f"„{name}“ ist ein Standardprofil und bleibt erhalten.")
    p = os.path.join(USER_PROFILE_DIR, name+".json")
    if not os.path.exists(p): raise RuntimeError("Profil nicht gefunden (nur selbst angelernte Profile können gelöscht werden).")
    os.remove(p)

def load_settings():
    try:
        with open(os.path.join(USER_DIR, "settings.json"), encoding="utf-8") as fh: return json.load(fh)
    except Exception: return {}

def save_settings(d):
    os.makedirs(USER_DIR, exist_ok=True)
    tmp = os.path.join(USER_DIR, "settings.json.tmp")
    with open(tmp, "w", encoding="utf-8") as fh: json.dump(d, fh, indent=1)
    os.replace(tmp, os.path.join(USER_DIR, "settings.json"))

def _launch_cmd():
    if FROZEN: return [sys.executable]
    return [sys.executable, os.path.join(HERE, "mixsmith.py")]

def create_desktop_shortcut():
    """Windows: 'Mixsmith.lnk' on the desktop. Linux: .desktop entry in the menu and on the desktop. macOS: not needed (app bundle)."""
    if sys.platform == "darwin":
        raise RuntimeError("Unter macOS liegt das Programm als App im Programme-Ordner – einfach ins Dock ziehen.")
    if sys.platform.startswith("linux"):
        icon = res_path("logo.png") or ""
        entry = "\n".join(["[Desktop Entry]", "Type=Application", "Name=" + APP_NAME, "Comment=Mixing, Mastering, Spur-Angleich und KI-Stems",
                           "Exec=" + " ".join('"%s"' % c for c in _launch_cmd()), "Icon=" + icon, "Terminal=false", "Categories=AudioVideo;Audio;", ""])
        apps = os.path.join(os.path.expanduser("~"), ".local", "share", "applications"); os.makedirs(apps, exist_ok=True)
        out = os.path.join(apps, "mixsmith.desktop")
        with open(out, "w", encoding="utf-8") as fh: fh.write(entry)
        os.chmod(out, 0o755)
        desk = os.path.join(os.path.expanduser("~"), "Desktop")
        if os.path.isdir(desk):
            d2 = os.path.join(desk, "mixsmith.desktop"); shutil.copy(out, d2); os.chmod(d2, 0o755); return d2
        return out
    desktop = os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), "Desktop")
    try:   # the real desktop folder (can be redirected, e.g. to OneDrive)
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", "[Environment]::GetFolderPath('Desktop')"],
                           capture_output=True, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.returncode == 0 and os.path.isdir(r.stdout.strip()): desktop = r.stdout.strip()
    except Exception: pass
    lnk = os.path.join(desktop, APP_NAME + ".lnk")
    if FROZEN:
        target, args, workdir = sys.executable, "", os.path.dirname(sys.executable)
    else:
        pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe"); target = pyw if os.path.exists(pyw) else sys.executable
        args, workdir = '"%s"' % os.path.join(HERE, "mixsmith.py"), HERE
    icon = res_path("logo.ico") or target
    q = lambda v: "'" + str(v).replace("'", "''") + "'"
    ps = ("$s=(New-Object -COM WScript.Shell).CreateShortcut(%s); $s.TargetPath=%s; $s.Arguments=%s; $s.WorkingDirectory=%s; "
          "$s.IconLocation=%s; $s.Description=%s; $s.Save()") % (q(lnk), q(target), q(args), q(workdir), q(icon+",0"), q(APP_NAME))
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], capture_output=True, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode != 0 or not os.path.exists(lnk): raise RuntimeError(r.stderr.strip() or "Verknüpfung konnte nicht angelegt werden.")
    return lnk

# ============================================================== the mastering chain
PRESETS = {   # platform targets; None = keep the profile's value
    "profil":  dict(label="Wie Profil", lufs=None, peak_mode=None, ceiling=None),
    "stream":  dict(label="Spotify · YouTube · Tidal  (−14 LUFS, −1 dBTP)", lufs=-14.0, peak_mode="true", ceiling=-1.0),
    "apple":   dict(label="Apple Music  (−16 LUFS, −1 dBTP)", lufs=-16.0, peak_mode="true", ceiling=-1.0),
    "loud":    dict(label="Laut & streamingsicher  (−11 LUFS, −1 dBTP)", lufs=-11.0, peak_mode="true", ceiling=-1.0),
    "club":    dict(label="Club / DJ  (−9 LUFS, −0,3 dBTP)", lufs=-9.0, peak_mode="true", ceiling=-0.3),
    "cd":      dict(label="CD  (−10 LUFS, −0,3 dBTP)", lufs=-10.0, peak_mode="true", ceiling=-0.3),
}

DEFAULTS = dict(
    peak_mode=None,        # None = wie Profil, "sample" oder "true"
    ceiling_db=None,       # None = Standard je Modus (-0,1 dBFS / -1,0 dBTP)
    target_lufs=None,      # None = Profil
    strength=1.0, max_eq=9.0, eq_lo=35.0, eq_hi=16000.0,
    presence_full=4.0, presence_cap=7.0, deharsh_scale=0.5,
    low_shelf_db=0.0, high_shelf_db=0.0,
    bass_mono_hz=150.0, width_mode="profil", width_db_manual=0.0, width_max=4.0,
    do_declip=True, release_ms=120.0, out_bits=24,
    glue=0.0,              # 0..1 Bus-Kompression
    clip_db=1.0,           # dB, die der Soft-Clipper vor dem Limiter von den Spitzen nimmt (0 = aus)
    stem_gains=None,       # {"vocals": dB, "drums": dB, "bass": dB, "other": dB}
)

def rebalance(x, sr, stems, gains):
    """Mix + Σ(g-1)·stem: exact when all gains are 0 dB, separation errors only matter where a stem is changed."""
    y = x.copy()
    for k, g in (gains or {}).items():
        if abs(g) < 0.05 or k not in stems: continue
        s = stems[k]
        if len(s) < len(y): s = np.concatenate([s, np.zeros((len(y)-len(s), 2))])
        y += s[:len(y)]*(10**(g/20)-1)
    return y

def render_master(x, sr, prof, log=print, stems=None, progress=None, cancel=None, **kw):
    """The whole chain in memory. x: float64 (n,2). Returns (y, info)."""
    p = {**DEFAULTS, **kw}; info = dict(declip_runs=0, deharsh_db=0.0, glue_db=0.0, width_change=0.0)
    def step(frac):
        if cancel is not None and cancel.is_set(): raise Cancelled()
        if progress: progress(frac)
    step(0.02)
    # 1. restoration
    if p["do_declip"] and clip_runs(x) > 20:
        x = x*0.5; x, nfix = declip(x, thr=0.995*0.5, maxover=1.0); info["declip_runs"] = nfix; log(f"  De-Clipping: {nfix} Läufe rekonstruiert")
    x = hpf(x, sr, 20)
    # 2. stem balance
    if stems and p["stem_gains"] and any(abs(v) >= 0.05 for v in p["stem_gains"].values()):
        x = rebalance(x, sr, stems, p["stem_gains"]); log("  Stem-Balance: " + ", ".join("%s %+.1f dB" % (STEM_DE.get(k, k), v) for k, v in p["stem_gains"].items() if abs(v) >= 0.05))
    step(0.15)
    # 3. spectral match with presence protection
    cur = smooth_spectrum(x, sr); corr = np.clip(p["strength"]*(prof["spec"]-cur), -p["max_eq"], p["max_eq"])
    pf, pc = p["presence_full"], max(p["presence_cap"], p["presence_full"])
    pres = (FL >= 2000) & (FL <= 8000); ex = corr[pres]; corr[pres] = np.where(ex > pf, np.minimum(pf+0.5*(ex-pf), pc), ex)
    hi = (FL > 8000) & (FL <= 10000); corr[hi] = np.minimum(corr[hi], pc)
    fade = np.clip(np.log2(FL/p["eq_lo"])*3+1, 0, 1)*np.clip(np.log2(p["eq_hi"]/FL)*3+1, 0, 1)    # 1/3-octave fade at the range edges
    corr = corr*fade
    x = fir_eq(x, sr, corr); info["eq_curve"] = corr; info["eq_min"], info["eq_max"] = float(corr.min()), float(corr.max())
    boost = float(np.mean(np.clip(corr[(FL >= 3000) & (FL <= 7000)], 0, None))); deharsh = float(np.clip(p["deharsh_scale"]*boost, 0, 4.0)); info["deharsh_db"] = deharsh
    if deharsh > 0.2:
        x = dyn_band(x, sr, 3000, 7000, 2.0, deharsh); log(f"  Präsenz-Anhebung Ø {boost:+.1f} dB → dynamische Absenkung 3–7 kHz bis {deharsh:.1f} dB")
    step(0.35)
    # 4. taste + stereo
    x = shelf(x, sr, 100, p["low_shelf_db"], "low"); x = shelf(x, sr, 10000, p["high_shelf_db"], "high")
    if p["bass_mono_hz"] > 0: x = bass_mono(x, sr, p["bass_mono_hz"])
    wd = 0.0
    if p["width_mode"] == "profil": wd = float(np.clip(prof["width"]-width_db(x, sr), -p["width_max"], p["width_max"]))
    elif p["width_mode"] == "manuell": wd = float(p["width_db_manual"])
    if abs(wd) > 0.05: x = widen(x, sr, 200, wd)
    info["width_change"] = wd
    step(0.45)
    # 5. glue, clipper, limiter, loudness
    if p["glue"] > 0.01:
        x, info["glue_db"] = glue(x, sr, p["glue"]); log(f"  Glue-Kompressor: bis {info['glue_db']:.1f} dB")
    target = prof["lufs"] if p["target_lufs"] is None else p["target_lufs"]
    mode = p["peak_mode"] or prof.get("peak_mode", "true")
    osf = 1 if mode == "sample" else 4
    ceiling = p["ceiling_db"] if p["ceiling_db"] is not None else (-0.1 if mode == "sample" else -1.0)
    ceil_lin = 10**(ceiling/20); gain = 10**((target-integrated(x, sr))/20); clip_db = max(0.0, float(p["clip_db"]))
    for it in range(4):
        z = x*gain
        if clip_db > 0.05:
            pk = float(np.max(np.abs(z))); thr = max(ceil_lin, pk*10**(-clip_db/20))
            if pk > thr: z = soft_clip(z, thr)
        y, gr = limiter(z, sr, ceiling, osf=osf, release_ms=p["release_ms"]); L = integrated(y, sr)
        step(0.5+0.1*it)
        if abs(L-target) < 0.15: break
        gain *= 10**((target-L)/20)
    if mode == "true":
        tpk = db(true_peak(y, sr))
        if tpk > ceiling+0.05: y *= 10**((ceiling-tpk)/20)
    y = np.clip(y, -1, 1); info.update(limiter_gr=gr, target=target, mode=mode, ceiling=ceiling)
    step(0.95)
    return y, info

def master_file(path, prof, out_dir, log=print, stems=None, taken=None, cancel=None, progress=None, protect=(), **kw):
    p = {**DEFAULTS, **kw}; t0 = time.time(); name = os.path.splitext(os.path.basename(path))[0]
    x, sr, _ = load_audio(path)
    before = dict(lufs=integrated(x, sr), tp=db(true_peak(x, sr)), clips=clip_runs(x), width=width_db(x, sr), corr=correlation(x))
    log(f"{name}: {before['lufs']:.1f} LUFS, TP {before['tp']:+.2f} dBTP, Clip-Läufe {before['clips']}")
    y, info = render_master(x, sr, prof, log=log, stems=stems, cancel=cancel, progress=progress, **p)
    os.makedirs(out_dir, exist_ok=True); out = output_path(out_dir, path, taken, protect=protect)
    write_audio(out, y, sr, p["out_bits"])
    after = dict(lufs=integrated(y, sr), tp=db(true_peak(y, sr)), width=width_db(y, sr), corr=correlation(y), lra=lra(y, sr))
    log(f"  → {after['lufs']:.1f} LUFS, TP {after['tp']:+.2f} dBTP, LRA {after['lra']:.1f}, Breite {after['width']:.1f} dB, EQ {info['eq_min']:+.1f}..{info['eq_max']:+.1f} dB, Limiter max {info['limiter_gr']:.1f} dB  ({time.time()-t0:.0f} s)")
    return dict(name=name, out=out, before=before, after=after, **info)

def write_protocol(rows, out_dir):
    rp = os.path.join(out_dir, "Mastering-Protokoll.csv")
    with open(rp, "w", newline="", encoding="utf-8-sig") as fh:      # BOM, damit Excel Umlaute richtig zeigt
        w = csv.writer(fh, delimiter=";"); w.writerow(["Titel", "Datei", "LUFS vorher", "LUFS nachher", "dBTP vorher", "dBTP nachher", "LRA nachher", "Breite vorher", "Breite nachher", "Clip-Läufe vorher", "De-Clip", "EQ min", "EQ max", "De-Harsh dyn", "Glue", "Limiter max GR"])
        for r in rows: w.writerow([r["name"], os.path.basename(r["out"]), f"{r['before']['lufs']:.2f}", f"{r['after']['lufs']:.2f}", f"{r['before']['tp']:.2f}", f"{r['after']['tp']:.2f}", f"{r['after']['lra']:.1f}", f"{r['before']['width']:.1f}", f"{r['after']['width']:.1f}", r["before"]["clips"], r["declip_runs"], f"{r['eq_min']:.1f}", f"{r['eq_max']:.1f}", f"{r['deharsh_db']:.1f}", f"{r.get('glue_db', 0):.1f}", f"{r['limiter_gr']:.1f}"])
    return rp

def run_batch(files, prof, out_dir, log=print, progress=None, cancel=None, stem_model="auto", **kw):
    rows = []; taken = set()
    for i, p in enumerate(files):
        if cancel is not None and cancel.is_set(): log("Abgebrochen."); break
        try:
            stems = None
            if kw.get("stem_gains") and any(abs(v) >= 0.05 for v in kw["stem_gains"].values()):
                x, sr, _ = load_audio(p); stems = mix_stems(p, sr, len(x), model=stem_model, log=log, cancel=cancel)
            rows.append(master_file(p, prof, out_dir, log=log, stems=stems, taken=taken, cancel=cancel, protect=files, **kw))
        except Cancelled: log("Abgebrochen."); break
        except Exception as e: log(f"FEHLER {os.path.basename(p)}: {e}")
        if progress: progress(i+1, len(files))
    if rows: log("Protokoll: %s" % write_protocol(rows, out_dir))
    return rows

# ============================================================== stem separation
STEM_DE = {"vocals": "Gesang", "drums": "Drums", "bass": "Bass", "guitar": "Gitarre", "piano": "Piano", "other": "Andere",
           "instrumental": "Instrumental", "kick": "Kick", "snare": "Snare", "toms": "Toms", "hh": "HiHat", "ride": "Ride", "crash": "Crash"}
SEP_MODELS = {   # vram tiers: (fp16, segment_size or 0 = model default, approx. GB needed incl. margin)
    "bs_roformer_sw": dict(file="BS-Roformer-SW.ckpt", label="BS-RoFormer SW · 6 Spuren · beste Qualität", size_mb=700,
                           stems=["vocals", "drums", "bass", "guitar", "piano", "other"], tiers=[(True, 0, 2.4), (True, 128, 1.7)], cpu_speed="langsam (~2,5× Songlänge)"),
    "htdemucs_6s":   dict(file="htdemucs_6s.yaml", label="Demucs v4 · 6 Spuren · schnell, wenig Speicher", size_mb=55,
                           stems=["vocals", "drums", "bass", "guitar", "piano", "other"], tiers=[(False, 0, 1.1)], cpu_speed="zügig (~0,3× Songlänge)"),
    "htdemucs_ft":   dict(file="htdemucs_ft.yaml", label="Demucs v4 fine-tuned · 4 Spuren · sauberer Bass/Drums", size_mb=320,
                           stems=["vocals", "drums", "bass", "other"], tiers=[(False, 0, 1.1)], cpu_speed="mittel (~1× Songlänge)"),
    "vocals_roformer": dict(file="model_bs_roformer_ep_317_sdr_12.9755.ckpt", label="BS-RoFormer Viperx · Gesang / Instrumental (Karaoke)", size_mb=640,
                           stems=["vocals", "instrumental"], tiers=[(True, 0, 2.4), (True, 128, 1.7)], cpu_speed="langsam (~2× Songlänge)"),
    "drumsep":       dict(file="MDX23C-DrumSep-aufr33-jarredou.ckpt", label="DrumSep · Schlagzeug → Kick, Snare, Toms, HiHat, Ride, Crash", size_mb=420,
                           stems=["kick", "snare", "toms", "hh", "ride", "crash"], tiers=[(True, 0, 2.0), (True, 128, 1.4)], cpu_speed="langsam"),
    # internal: effect analysis (dry signal vs. reverb / echo); not offered on the Stems page
    "dereverb":      dict(file="MDX23C-De-Reverb-aufr33-jarredou.ckpt", label="MDX23C De-Reverb · Hall abtrennen", size_mb=430, internal=True,
                           stems=["dry", "no dry"], tiers=[(True, 0, 1.6), (True, 128, 1.2)], cpu_speed="mittel"),
    "deecho":        dict(file="UVR-De-Echo-Normal.pth", label="UVR De-Echo · Echo/Delay abtrennen", size_mb=120, internal=True,
                           stems=["no echo", "echo"], tiers=[(False, 0, 1.0)], cpu_speed="zügig"),
}
MIX_MODELS = ("bs_roformer_sw", "htdemucs_6s")        # 6-stem models usable for mixing

def separation_available():
    try:
        import importlib.util
        return importlib.util.find_spec("audio_separator") is not None and importlib.util.find_spec("torch") is not None
    except Exception:
        return False

def bundled_model_dirs():
    return [d for d in (os.path.join(HERE, "models"), os.path.join(RES, "models")) if os.path.isdir(d)]

def model_dir_for(file):
    """Bundled folder if it already holds the model, otherwise the per-user folder (downloads land there)."""
    for d in bundled_model_dirs()+[os.path.join(USER_DIR, "models")]:
        if os.path.exists(os.path.join(d, file)): return d
    d = os.path.join(USER_DIR, "models"); os.makedirs(d, exist_ok=True); return d

def model_present(key):
    return any(os.path.exists(os.path.join(d, SEP_MODELS[key]["file"])) for d in bundled_model_dirs()+[os.path.join(USER_DIR, "models")])

FORCE_CPU = False        # Einstellung „nur CPU verwenden“
VRAM_LIMIT_GB = None     # Einstellung „höchstens so viel Grafikspeicher belegen“ (None = frei verfügbarer Speicher)
_GPU_CACHE = {}
def gpu_info(refresh=False):
    """NVIDIA GPU via nvidia-smi (fast, no torch import): dict(ok, name, total_gb, free_gb)."""
    if _GPU_CACHE and not refresh: return dict(_GPU_CACHE)
    info = dict(ok=False, name="", total_gb=0.0, free_gb=0.0)
    if sys.platform == "darwin":
        import platform
        if platform.machine() == "arm64":      # Apple Silicon: unified memory, Metal (MPS) is used by PyTorch
            try: mem = int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True).stdout.strip())/2**30
            except Exception: mem = 8.0
            info = dict(ok=True, name="Apple Silicon (Metal)", total_gb=mem, free_gb=mem*0.5)
        _GPU_CACHE.clear(); _GPU_CACHE.update(info); return dict(info)
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=8, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.returncode == 0 and r.stdout.strip():
            best = None
            for line in r.stdout.strip().splitlines():
                name, tot, free = [s.strip() for s in line.split(",")]
                if best is None or float(free) > best[2]: best = (name, float(tot), float(free))
            info = dict(ok=True, name=best[0], total_gb=best[1]/1024, free_gb=best[2]/1024)
    except Exception:
        pass
    _GPU_CACHE.clear(); _GPU_CACHE.update(info); return dict(info)

def sep_plan(model="auto", refresh=True):
    """Chooses model and device for the current free graphics memory. Returns dict(model, device, message)."""
    g = gpu_info(refresh=refresh)
    if FORCE_CPU: g = dict(g, ok=False)
    elif VRAM_LIMIT_GB: g["free_gb"] = min(g["free_gb"], float(VRAM_LIMIT_GB))
    if model == "auto":
        if g["ok"] and g["free_gb"] >= SEP_MODELS["bs_roformer_sw"]["tiers"][-1][2]: model = "bs_roformer_sw"
        else: model = "htdemucs_6s"
    need = SEP_MODELS[model]["tiers"][-1][2]
    if VRAM_LIMIT_GB and g["ok"]: g["name"] += " (Grenze %.1f GB)" % float(VRAM_LIMIT_GB)
    if FORCE_CPU:
        return dict(model=model, device="cpu", message="Nur CPU (Einstellung): %s." % SEP_MODELS[model]["cpu_speed"])
    if not g["ok"]:
        return dict(model=model, device="cpu", message="Keine NVIDIA-Grafikkarte gefunden: Trennung auf der CPU (%s)." % SEP_MODELS[model]["cpu_speed"])
    if g["free_gb"] < need:
        return dict(model=model, device="cpu", message="%s: nur %.1f GB Grafikspeicher frei (mind. %.1f GB nötig). Trennung auf der CPU (%s)." % (g["name"], g["free_gb"], need, SEP_MODELS[model]["cpu_speed"]))
    return dict(model=model, device="gpu", message="%s · %.1f von %.1f GB frei → GPU" % (g["name"], g["free_gb"], g["total_gb"]))

class _model_lock:
    """Inter-process lock per model file: two separations must not download the same model into the same file at once."""
    def __init__(self, folder, file, stale_s=1800):
        self.p = os.path.join(folder, file+".lock"); self.stale = stale_s; self.fd = None
    def __enter__(self):
        while True:
            try:
                self.fd = os.open(self.p, os.O_CREAT | os.O_EXCL | os.O_WRONLY); return self
            except FileExistsError:
                try:
                    if time.time()-os.path.getmtime(self.p) > self.stale: os.remove(self.p); continue
                except OSError: continue
                time.sleep(0.5)
            except OSError:
                return self             # read-only folder: no lock possible, carry on
    def __exit__(self, *a):
        if self.fd is not None:
            os.close(self.fd)
            try: os.remove(self.p)
            except OSError: pass

def _sep_worker(job_file):
    """Separate process: picks the largest setting that fits into free VRAM, steps down on out-of-memory."""
    with open(job_file, encoding="utf-8") as fh: job = json.load(fh)
    for d in (os.path.join(HERE, "bin"), os.path.join(RES, "bin")):        # bundled ffmpeg for audio-separator
        if any(os.path.exists(os.path.join(d, f)) for f in ("ffmpeg.exe", "ffmpeg")): os.environ["PATH"] = d+os.pathsep+os.environ.get("PATH", ""); break
    result = dict(ok=False); m = SEP_MODELS[job["model"]]
    try:
        import logging, torch
        if job.get("cpu"):          # hide every accelerator (CUDA and Apple Metal) from audio-separator
            torch.cuda.is_available = lambda: False
            try: torch.backends.mps.is_available = lambda: False
            except Exception: pass
        from audio_separator.separator import Separator
        cuda = torch.cuda.is_available() and not job.get("cpu")
        mps = (not cuda) and not job.get("cpu") and getattr(getattr(torch.backends, "mps", None), "is_available", lambda: False)()
        tiers = list(m["tiers"]) if cuda else [(False, 0, 0.0)]
        if cuda:
            free, total = [v/2**30 for v in torch.cuda.mem_get_info()]
            if job.get("vram_limit"):
                lim = float(job["vram_limit"]); free = min(free, lim)
                torch.cuda.set_per_process_memory_fraction(min(1.0, lim/total))     # hard cap: exceeding it counts as out-of-memory
            fit = [t for t in tiers if t[2] <= free]
            tiers = fit or tiers[-1:]
        # Separate a copy 6 dB down and raise the stems again afterwards (32-bit float): audio-separator would otherwise
        # normalise loud stems (peak > threshold) and change their level, and stems of loud masters could clip.
        HEAD = 0.5; src_in = os.path.join(job["outdir"], "input.wav")
        xin, sr_in = sf.read(job["path"], dtype="float32", always_2d=True); sf.write(src_in, xin*HEAD, sr_in, subtype="FLOAT"); del xin
        for fp16, seg, need in tiers:
            kw = dict(log_level=logging.ERROR, model_file_dir=job["model_dir"], output_dir=job["outdir"], output_format="WAV",
                      normalization_threshold=1.0, amplification_threshold=0.0,
                      sample_rate=int(job.get("sr", 44100)), use_autocast=bool(fp16 and cuda))
            if m["file"].endswith(".ckpt"):
                kw["mdxc_params"] = dict(segment_size=seg or 256, override_model_segment_size=seg > 0, batch_size=1, overlap=2, pitch_shift=0)
            try:
                sep = Separator(**kw)
                with _model_lock(job["model_dir"], m["file"]):
                    try: sep.load_model(model_filename=m["file"])
                    except ValueError as e:         # half-downloaded file (aborted download): fetch it again once
                        if "MD5" not in str(e) and "Unsupported Model File" not in str(e): raise
                        print("Modelldatei unvollständig, lade neu …", file=sys.stderr, flush=True)
                        try: os.remove(os.path.join(job["model_dir"], m["file"]))
                        except OSError: pass
                        sep = Separator(**kw); sep.load_model(model_filename=m["file"])
                outs = sep.separate(src_in)
                found = {}
                for o in outs:
                    op = o if os.path.isabs(o) else os.path.join(job["outdir"], o)
                    mm = re.search(r"\(([^()]+)\)[^()]*$", os.path.basename(op))
                    if mm:
                        y, s2 = sf.read(op, dtype="float32", always_2d=True); sf.write(op, y/HEAD, s2, subtype="FLOAT")
                        found[mm.group(1).lower()] = op
                result = dict(ok=True, outputs=found, device="gpu" if (cuda or mps) else "cpu", fp16=bool(fp16 and cuda), segment=seg); break
            except BaseException as e:        # audio-separator calls sys.exit() when a model does not fit while loading
                oom = "out of memory" in str(e).lower() or type(e).__name__ in ("OutOfMemoryError", "SystemExit")
                if cuda:
                    try: del sep
                    except Exception: pass
                    torch.cuda.empty_cache()
                if not oom: raise
                print("Speicher reicht nicht (fp16=%s, Block %s), nächste Stufe …" % (fp16, seg), file=sys.stderr, flush=True)
        else:
            result = dict(ok=False, oom=True, error="Grafikspeicher reicht nicht")
    except BaseException as e:
        result = dict(ok=False, error="%s: %s" % (type(e).__name__, e))
    with open(os.path.join(job["outdir"], "_result.json"), "w", encoding="utf-8") as fh: json.dump(result, fh)

_WORKERS = set()
def kill_workers():
    """Stops running separation processes (called when the program closes; otherwise they keep the GPU busy)."""
    for proc in list(_WORKERS):
        try: proc.kill()
        except Exception: pass
    _WORKERS.clear()
import atexit; atexit.register(kill_workers)

def _worker_cmd():
    if FROZEN: return [sys.executable]
    return [sys.executable, os.path.join(HERE, "mixsmith.py")]

def separate(path, model="auto", log=print, progress=None, cancel=None, sr=None, device=None, fallback=None):
    """Runs the separation worker. Returns (dict stem -> wav path in a temporary folder, temp folder, used model).
    The caller must remove the folder (shutil.rmtree) after use. fallback: model to use instead when the GPU fails and the
    separation has to run on the CPU (default: Demucs 6s for automatic BS-RoFormer selection, because it is much faster there)."""
    if not separation_available(): raise RuntimeError("KI-Stem-Trennung ist in dieser Version nicht installiert.")
    auto = model == "auto"; plan = sep_plan(model); model = plan["model"]; dev = device or plan["device"]; m = SEP_MODELS[model]
    if sr is None: sr = sf.info(path).samplerate
    work = os.path.join(USER_DIR, "stems_tmp", "%d_%d" % (os.getpid(), int(time.time()*1000))); os.makedirs(work, exist_ok=True)
    if not model_present(model): log("  Modell %s wird einmalig heruntergeladen (%d MB) …" % (m["file"], m["size_mb"]))
    log("  Trennung: %s · %s · %s" % (os.path.basename(path), m["label"].split(" · ")[0], plan["message"] if dev == plan["device"] else "CPU"))
    def run(cpu):
        m = SEP_MODELS[model]
        job = dict(path=path, model=model, outdir=work, model_dir=model_dir_for(m["file"]), sr=sr, cpu=cpu, vram_limit=VRAM_LIMIT_GB)
        jf = os.path.join(work, "_job.json"); rf = os.path.join(work, "_result.json")
        with open(jf, "w", encoding="utf-8") as fh: json.dump(job, fh)
        if os.path.exists(rf): os.remove(rf)
        env = dict(os.environ)
        if cpu: env["CUDA_VISIBLE_DEVICES"] = "-1"          # "" would be dropped on Windows and the GPU used anyway
        proc = subprocess.Popen(_worker_cmd()+["--sep-worker", jf], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, env=env,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        _WORKERS.add(proc)
        tail = [b""]
        def reader():
            while True:
                ch = proc.stderr.read(256)
                if not ch: break
                tail[0] = (tail[0]+ch)[-4096:]
                for pct in re.findall(rb"(\d{1,3})%\|", ch):
                    if progress: progress(min(1.0, int(pct)/100))
                if b"n\xc3\xa4chste Stufe" in ch or b"chste Stufe" in ch: log("  Grafikspeicher knapp: kleinere Einstellung …")
        th = threading.Thread(target=reader, daemon=True); th.start()
        try:
            while proc.poll() is None:
                if cancel is not None and cancel.is_set():
                    proc.kill(); proc.wait(); raise Cancelled()
                time.sleep(0.2)
        finally:
            _WORKERS.discard(proc)
        th.join(timeout=2)
        if not os.path.exists(rf):
            lines = [l.strip() for l in re.split(r"[\r\n]+", tail[0].decode("utf-8", "replace")) if l.strip() and "%|" not in l]
            return dict(ok=False, error="Trennungsprozess ohne Ergebnis beendet (Code %s)%s" % (proc.returncode, (": " + lines[-1][:300]) if lines else "."))
        with open(rf, encoding="utf-8") as fh: return json.load(fh)
    try:
        r = run(dev == "cpu")
        if not r["ok"] and dev == "gpu":
            log("  GPU-Trennung nicht möglich (%s). Neuer Versuch auf der CPU …" % r.get("error", "?"))
            fb = fallback or ("htdemucs_6s" if auto and model == "bs_roformer_sw" else None)
            if fb and fb != model: model = fb; log("  (auf der CPU mit %s, weil deutlich schneller)" % SEP_MODELS[fb]["label"].split(" · ")[0])
            r = run(True)
        if not r["ok"]: raise RuntimeError(r.get("error", "Stem-Trennung fehlgeschlagen."))
    except BaseException:
        shutil.rmtree(work, ignore_errors=True); raise
    if r.get("device") == "gpu": log("  GPU%s%s" % (", fp16" if r.get("fp16") else "", ", kleine Blöcke (wenig VRAM)" if r.get("segment") else ""))
    return r["outputs"], work, model

def extract_stems(path, out_dir, model="auto", want=None, bits=24, log=print, progress=None, cancel=None):
    """Separates a song and writes '<Song> - <Stem>.wav' into out_dir/<Song>/. want = list of stem keys or None (all)."""
    song = os.path.splitext(os.path.basename(path))[0]; dest = os.path.join(out_dir, safe_name(song)); os.makedirs(dest, exist_ok=True)
    outs, work, used = separate(path, model, log=log, progress=progress, cancel=cancel)
    written = []
    try:
        for k, p in outs.items():
            if want and k not in want: continue
            y, sr = sf.read(p, dtype="float64", always_2d=True)
            op = os.path.join(dest, "%s - %s.wav" % (song, STEM_DE.get(k, k.capitalize())))
            b = bits
            if np.max(np.abs(y)) > 1.0 and int(bits) != 32:
                b = 32; log("  %s liegt über 0 dBFS (%.2f) – als 32-Bit-Float gespeichert, damit nichts abgeschnitten wird" % (STEM_DE.get(k, k), np.max(np.abs(y))))
            write_audio(op, y, sr, b); written.append(op)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    log("  %d Spuren gespeichert: %s" % (len(written), dest))
    return dest, written

def _cache_key(path, model):
    st = os.stat(path); return hashlib.sha1(("%s|%d|%d|%s" % (os.path.abspath(path), st.st_size, int(st.st_mtime), model)).encode()).hexdigest()[:16]

def prune_cache(max_gb=3.0):
    if not os.path.isdir(CACHE_DIR): return
    entries = [(os.path.getmtime(d), d) for d in glob.glob(os.path.join(CACHE_DIR, "*")) if os.path.isdir(d)]
    size = lambda d: sum(os.path.getsize(f) for f in glob.glob(os.path.join(d, "*")))
    total = sum(size(d) for _, d in entries)
    for _, d in sorted(entries):
        if total <= max_gb*2**30: break
        total -= size(d); shutil.rmtree(d, ignore_errors=True)

def cache_size_mb():
    return sum(os.path.getsize(f) for f in glob.glob(os.path.join(CACHE_DIR, "*", "*")))/2**20 if os.path.isdir(CACHE_DIR) else 0.0

def clear_cache():
    shutil.rmtree(CACHE_DIR, ignore_errors=True); shutil.rmtree(os.path.join(USER_DIR, "stems_tmp"), ignore_errors=True)
    shutil.rmtree(os.path.join(USER_DIR, "stems"), ignore_errors=True)      # leftovers of versions before 2.0

def song_stems(path, sr, n, model="auto", log=print, progress=None, cancel=None):
    """All stems of a song (6-stem model: vocals, drums, bass, guitar, piano, other) as float64 (n,2) arrays at sr, cached per
    file and model. Automatic choice uses BS-RoFormer SW when it fits into the free graphics memory, otherwise Demucs 6s."""
    plan_model = sep_plan(model)["model"] if model == "auto" else model
    d = os.path.join(CACHE_DIR, _cache_key(path, plan_model)); npz = os.path.join(d, "stems.npz")
    st = None
    if os.path.exists(npz):
        try:
            with np.load(npz) as z: st = {k: z[k].astype(np.float64) for k in z.files}
            os.utime(d); log("  Stems aus dem Zwischenspeicher")
        except Exception:
            st = None; shutil.rmtree(d, ignore_errors=True)          # damaged cache entry (e.g. disk full while writing)
    if st is None:
        outs, work, used = separate(path, plan_model, log=log, progress=progress, cancel=cancel, sr=sr,
                                    fallback="htdemucs_6s" if model == "auto" else None)
        try:
            st = {}
            for k, p in outs.items():
                y, s2 = sf.read(p, dtype="float64", always_2d=True)
                if y.shape[1] == 1: y = np.repeat(y, 2, axis=1)
                if s2 != sr: y = signal.resample_poly(y, sr, s2, axis=0)
                st[k] = y[:, :2]
        finally:
            shutil.rmtree(work, ignore_errors=True)
        try:
            os.makedirs(d, exist_ok=True); tmp = os.path.join(d, "stems.tmp.npz")
            np.savez(tmp, **{k: v.astype(np.float32) for k, v in st.items()}); os.replace(tmp, npz); prune_cache()
        except Exception as e:
            shutil.rmtree(d, ignore_errors=True); log("  Zwischenspeicher nicht geschrieben (%s)" % e)
    for k in st:
        if len(st[k]) < n: st[k] = np.concatenate([st[k], np.zeros((n-len(st[k]), 2))])
        st[k] = st[k][:n]
    return st

def mix_stems(path, sr, n, model="auto", log=print, progress=None, cancel=None):
    """Four stem groups (vocals, drums, bass, other = everything else) for stem balance."""
    st = song_stems(path, sr, n, model=model, log=log, progress=progress, cancel=cancel); out = {}
    for k, y in st.items():
        g = k if k in ("vocals", "drums", "bass") else "other"
        out[g] = out[g]+y if g in out else y
    return out

# ============================================================== instrument tracks (Spur-Angleich)
INSTRUMENTS = ["Gitarre", "Bass", "Drums", "Gesang", "Piano/Keys", "Andere"]
SEP_MAP = {"Gitarre": "guitar", "Bass": "bass", "Drums": "drums", "Gesang": "vocals", "Piano/Keys": "piano", "Andere": "other"}

def separate_instrument(path, instrument, log=print, save_dir=None, model="auto", progress=None, cancel=None):
    """Extracts one instrument from a full song. Returns the stem as array (x, sr). Temporary files are removed."""
    if model == "auto":
        plan = sep_plan("auto"); model = plan["model"]
    if SEP_MAP[instrument] not in SEP_MODELS[model]["stems"]: model = "htdemucs_6s"
    outs, work, used = separate(path, model, log=log, progress=progress, cancel=cancel)
    try:
        key = SEP_MAP[instrument]
        if key not in outs: raise RuntimeError("Instrument %s nicht in der Trennung gefunden." % instrument)
        if save_dir:
            song = os.path.splitext(os.path.basename(path))[0]; dest = os.path.join(save_dir, safe_name(song)); os.makedirs(dest, exist_ok=True)
            for k, p in outs.items(): shutil.copy(p, os.path.join(dest, "%s - %s.wav" % (song, STEM_DE.get(k, k))))
            log("  Stems gespeichert: %s" % dest)
        x, sr = sf.read(outs[key], dtype="float64", always_2d=True)
        if x.shape[1] == 1: x = np.repeat(x, 2, axis=1)
        return x[:, :2], sr
    finally:
        shutil.rmtree(work, ignore_errors=True)

def _env_ratio(x, sr, hop=16):
    n = len(x)//hop; e = np.sqrt((x[:n*hop]**2).reshape(n, hop, -1).mean(axis=(1, 2))); fc = sr/hop
    ef = _smooth(e, 1-math.exp(-1/(0.001*fc)), 1-math.exp(-1/(0.030*fc))); es = _smooth(e, 1-math.exp(-1/(0.025*fc)), 1-math.exp(-1/(0.150*fc)))
    return e, ef, es, n

def transient_db(x, sr):
    e, ef, es, n = _env_ratio(x, sr); loud = e > 0.05*e.max()
    if loud.sum() < 10: return 0.0
    return float(np.mean(20*np.log10((ef[loud]+1e-9)/(es[loud]+1e-9))))

def transient_gain(x, sr, amount_db, hop=16):
    """Gain curve (linear, per sample) of the transient shaper: positive amount_db boosts attacks, negative softens them."""
    if abs(amount_db) < 0.1 or len(x) < 4*hop: return np.ones(len(x))
    e, ef, es, n = _env_ratio(x, sr, hop); r = 20*np.log10(np.maximum(ef/np.maximum(es, 1e-9), 1.0))
    gd = np.clip(r*(amount_db/6.0), min(0, amount_db), max(0, amount_db))
    return 10**(np.interp(np.arange(len(x)), np.arange(n)*hop+hop/2, gd)/20)

def transient_shape_db(x, sr, amount_db, hop=16):
    """Positive amount_db boosts attacks (up to that many dB), negative softens them."""
    if abs(amount_db) < 0.1: return x
    return x*transient_gain(x, sr, amount_db, hop)[:, None]

def crest_db(x): return 20*np.log10(np.max(np.abs(x))+1e-12)-20*np.log10(np.sqrt(np.mean(x**2))+1e-12)

def saturate(x, amount):
    """Soft tape/tube-style saturation, amount 0..1 (adds harmonics, gentle level compression)."""
    if amount <= 0.001: return x
    d = 1.0+4.0*amount; rms0 = np.sqrt(np.mean(x**2))+1e-12
    y = np.tanh(x*d)/np.tanh(d); y = (1-amount)*x+amount*y
    return y*(rms0/(np.sqrt(np.mean(y**2))+1e-12))

def track_features(x, sr):
    return dict(spec=smooth_spectrum(x, sr), lufs=integrated(x, sr), crest=crest_db(x), width=width_db(x, sr), lra=lra(x, sr), transient=transient_db(x, sr))

def load_track(path):
    x, sr, mono = load_audio(path); return x, sr, mono

def list_instrument_profiles():
    return sorted((os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(INSTR_DIR, "*.json"))), key=str.lower)

def load_instrument_profile(name):
    with open(os.path.join(INSTR_DIR, name+".json"), encoding="utf-8") as fh: p = json.load(fh)
    p["spec"] = np.array(p["spec"]); return p

def delete_instrument_profile(name):
    p = os.path.join(INSTR_DIR, name+".json")
    if not os.path.exists(p): raise RuntimeError("Profil nicht gefunden.")
    os.remove(p)

def learn_instrument_profile(files, name, instrument, separate=False, log=print, stems_dir=None, analyse_fx=True, model="auto", progress=None, cancel=None):
    """Learns an instrument profile from reference tracks (isolated stems, or full songs with separate=True).
    With separate=True all stems of every song are saved to stems_dir/<song>/ when stems_dir is given."""
    name = safe_name(name)
    if not files: raise RuntimeError("Keine Referenzdateien angegeben.")
    rows = []; fxs = []
    for i, p in enumerate(files):
        if cancel is not None and cancel.is_set(): raise Cancelled()
        log(os.path.splitext(os.path.basename(p))[0])
        if separate:
            x, sr = separate_instrument(p, instrument, log=log, save_dir=stems_dir, model=model, cancel=cancel,
                                        progress=(lambda f, i=i: progress((i+f)/len(files))) if progress else None)
        else:
            x, sr, _ = load_track(p)
        f = track_features(x, sr); rows.append(f)
        log("  %.1f LUFS, Crest %.1f dB, Transienten %+.1f dB, Breite %.1f dB" % (f["lufs"], f["crest"], f["transient"], f["width"]))
        if analyse_fx:
            fx = analyse_effects(x, sr, log=log, cancel=cancel); fxs.append(fx)
            log("    Effekte: " + ("; ".join(describe_effect(k, v)+" (Konfidenz %.0f %%)" % (v["confidence"]*100) for k, v in fx.items()) if fx else "keine erkannt"))
        if progress: progress((i+1)/len(files))
    effects = merge_effects(fxs) if fxs else {}
    if separate and effects:
        for v in effects.values(): v["confidence"] = round(v["confidence"]*0.6, 2)     # separated stems are less reliable
    prof = dict(name=name, instrument=instrument, n=len(rows), sources=[os.path.basename(p) for p in files], separated=bool(separate), effects=effects,
                lufs=float(np.median([r["lufs"] for r in rows])), crest=float(np.median([r["crest"] for r in rows])), width=float(np.median([r["width"] for r in rows])),
                lra=float(np.median([r["lra"] for r in rows])), transient=float(np.median([r["transient"] for r in rows])),
                f=FL.tolist(), spec=np.median(np.array([r["spec"] for r in rows]), axis=0).tolist())
    os.makedirs(INSTR_DIR, exist_ok=True); out = os.path.join(INSTR_DIR, name+".json")
    with open(out, "w", encoding="utf-8") as fh: json.dump(prof, fh, indent=1)
    log("Instrument-Profil gespeichert: %s  (%s, %.1f LUFS, Crest %.1f dB)" % (out, instrument, prof["lufs"], prof["crest"]))
    return prof

# ---------------------------------------------------------------- effect analysis (tremolo, modulation, delay, reverb)
def _envelope(x, sr, hop):
    n = len(x)//hop; return np.sqrt((x[:n*hop]**2).reshape(n, hop, -1).mean(axis=(1, 2))), n

def _band_envelopes(x, sr, hop=256, bands=((400, 700), (700, 1200), (1200, 2000), (2000, 3300), (3300, 5500), (5500, 9000))):
    m = x.mean(axis=1); envs = []
    for lo, hi in bands:
        sos = signal.butter(2, [lo, min(hi, sr/2*0.95)], "bandpass", fs=sr, output="sos"); b = signal.sosfilt(sos, m)
        e, n = _envelope(b[:, None], sr, hop); envs.append(20*np.log10(e+1e-9))
    return np.array(envs), sr/hop

def _lfo_candidates(env_db, fs, lo, hi, win_s=4.0, top=4):
    """Per 4-s window: the strongest periodic components of the band envelopes (rate, depth, phase spread across bands,
    harmonic ratio). Candidates with the same rate over many windows are merged; consistency = share of windows containing that rate."""
    W = int(win_s*fs); nb, n = env_db.shape; found = []; nwin = 0
    for s0 in range(0, n-W, W//2):
        seg = env_db[:, s0:s0+W]
        if seg.max() < env_db.max()-30: continue
        nwin += 1
        d = seg-np.array([np.convolve(r, np.ones(int(fs)+1)/(int(fs)+1), mode="same") for r in seg])
        F = np.fft.rfft(d*np.hanning(W), axis=1); fr = np.fft.rfftfreq(W, 1/fs); mag = np.abs(F).mean(axis=0)
        msk = (fr >= lo) & (fr <= hi); idx = np.where(msk)[0]
        if len(idx) < 5: continue
        order = idx[np.argsort(mag[idx])[::-1]]; picked = []
        for k in order:
            if any(abs(fr[k]-fr[j]) < 0.12*fr[j]+0.05 for j in picked): continue
            picked.append(k)
            if len(picked) >= top: break
        med = np.median(mag[idx])+1e-12
        for k in picked:
            if mag[k]/med < 3.0: continue
            amp = np.abs(F[:, k])*2/np.sum(np.hanning(W))*2; ph = np.angle(F[:, k])
            spread = float(np.sqrt(-2*np.log(np.abs(np.mean(np.exp(1j*ph)))+1e-12)))
            def at(mult):
                kk = int(round(k*mult)); return mag[kk-1:kk+2].max() if kk+2 <= len(mag) else 0.0
            harm = float((at(2)+at(3))/(2*mag[k]+1e-12))
            found.append(dict(rate=float(fr[k]), depth=float(np.mean(amp)), spread=spread, harm=harm))
    if not found or nwin < 3: return []
    out = []
    for c in sorted(found, key=lambda c: -c["depth"]):
        if any(abs(c["rate"]-o["rate"]) < 0.12*o["rate"]+0.05 for o in out): continue
        same = [f for f in found if abs(f["rate"]-c["rate"]) < 0.12*c["rate"]+0.05]
        out.append(dict(rate=float(np.median([f["rate"] for f in same])), depth=float(np.median([f["depth"] for f in same])),
                        spread=float(np.median([f["spread"] for f in same])), harm=float(np.median([f["harm"] for f in same])),
                        consistency=float(len(same)/nwin)))
    return out

def analyse_tremolo(x, sr):
    """Tremolo: all bands swing together, sinusoidally, at a constant rate, with a moderate depth."""
    env, fs = _band_envelopes(x, sr); best = None
    for c in _lfo_candidates(env, fs, 0.8, 12.0):
        if c["spread"] > 0.7 or c["harm"] > 0.45 or c["consistency"] < 0.6 or not (1.5 <= c["depth"] <= 16): continue
        conf = float(np.clip(c["consistency"], 0, 1)*np.clip((c["depth"]-1.0)/4, 0, 1)*np.clip((0.45-c["harm"])/0.3, 0, 1)*np.clip((0.7-c["spread"])/0.5, 0, 1))
        if conf >= 0.25 and (best is None or conf > best[0]): best = (conf, c)
    if not best: return None
    conf, c = best
    return dict(rate_hz=round(c["rate"], 2), depth_db=round(min(c["depth"]*1.6, 24), 1), confidence=round(conf, 2))

def analyse_modulation(x, sr):
    """Flanger/chorus: bands swing sinusoidally at one constant LFO rate but with different phases (comb notches sweep through the bands)."""
    env, fs = _band_envelopes(x, sr); best = None
    for c in _lfo_candidates(env, fs, 0.08, 6.0):
        if c["spread"] < 0.9 or c["harm"] > 0.6 or c["consistency"] < 0.6 or c["depth"] < 0.8: continue
        conf = float(np.clip(c["consistency"], 0, 1)*np.clip((c["depth"]-0.5)/3, 0, 1)*np.clip((c["spread"]-0.8)/0.6, 0, 1))
        if conf >= 0.25 and (best is None or conf > best[0]): best = (conf, c)
    if not best: return None
    conf, r = best
    m = x.mean(axis=1); nfft = 4096; hop = 1024
    f, t, Z = signal.stft(m, sr, nperseg=nfft, noverlap=nfft-hop); S = 20*np.log10(np.abs(Z)+1e-9); band = (f >= 300) & (f <= 10000); S = S[band]; fstep = f[1]-f[0]
    loud = S.max(axis=0) > (S.max()-30); flg = 0; tot = 0; dl = []
    for i in np.where(loud)[0][::4]:
        col = S[:, i]; col = col-np.convolve(col, np.ones(41)/41, mode="same")
        C = np.abs(np.fft.rfft(col*np.hanning(len(col)))); q = np.fft.rfftfreq(len(col), fstep); qm = (q >= 0.0004) & (q <= 0.0025)
        if qm.sum() < 3: continue
        tot += 1; k = np.argmax(C[qm])
        if C[qm][k] > 4*np.median(C[qm]): flg += 1; dl.append(q[qm][k]*1000)
    is_flanger = tot > 0 and flg/tot > 0.4
    kind = "Flanger" if is_flanger else "Chorus"; centre = float(np.median(dl)) if is_flanger and dl else 7.0
    depth_ms = float(np.clip(r["depth"]/4.0, 0.3, 4.0)) if is_flanger else float(np.clip(r["depth"]/2.0, 0.5, 6.0))
    return dict(kind=kind, rate_hz=round(r["rate"], 2), depth_ms=round(depth_ms, 2), centre_ms=round(centre, 2), feedback=round(0.35 if is_flanger else 0.0, 2), confidence=round(conf, 2))

def analyse_delay(x, sr):
    """Echo: waveform-level autocorrelation of the 1-5 kHz band (rhythmic repetition of different notes does not correlate)."""
    m = x.mean(axis=1); sos = signal.butter(4, [1000, min(5000, 0.45*sr)], "bandpass", fs=sr, output="sos"); b = signal.sosfilt(sos, m)
    W = int(6*sr); acc = None; cnt = 0
    for s0 in range(0, len(b)-W, W):
        seg = b[s0:s0+W]
        if np.sqrt(np.mean(seg**2)) < 0.01*np.sqrt(np.mean(b**2))+1e-9: continue
        ac = signal.correlate(seg, seg, mode="full", method="fft")[W-1:]; ac = ac/(ac[0]+1e-12)
        acc = ac if acc is None else acc+ac; cnt += 1
    if acc is None or cnt < 2: return None
    ac = acc/cnt; lo, hi = int(0.06*sr), int(1.5*sr); seg = ac[lo:hi]
    k = int(np.argmax(seg)); peak = float(seg[k]); lag = (lo+k)/sr
    ctx = float(np.median(np.abs(seg))+1e-9); conf = float(np.clip((peak/ctx-6)/14, 0, 1)*np.clip((peak-0.04)/0.2, 0, 1))
    if peak < 0.05 or conf < 0.2: return None
    k2 = int(np.clip(2*(lo+k)-lo, 0, len(seg)-1)); fb = float(np.clip(seg[k2]/max(peak, 1e-9), 0, 0.8)) if k2 < len(seg) else 0.0
    p_ = min(peak, 0.49); ratio = (1-np.sqrt(max(0.0, 1-4*p_*p_)))/(2*p_); mix = float(np.clip(ratio/(1+ratio), 0.05, 0.6))
    return dict(time_s=round(lag, 3), level=round(mix, 2), feedback=round(fb, 2), confidence=round(conf, 2))

def analyse_reverb(x, sr):
    """Reverb: median decay time after note offsets (RT60 from the slope of the dB envelope over the monotonic decay).
    Dry vocals/guitar decay in 0.15-0.35 s; a reverb tail stretches that to >= 0.6 s."""
    hop = 512; e, n = _envelope(x, sr, hop); fs = sr/hop; edb = 20*np.log10(e+1e-9)
    thr = edb.max()-15; rt = []; tails = []; i = 1
    while i < n-int(2.0*fs):
        if edb[i-1] > thr and edb[i:i+int(0.05*fs)].max() < edb[i-1]-2:
            seg = edb[i:i+int(2.0*fs)]; runmin = np.minimum.accumulate(seg)
            k = int(np.argmax(seg > runmin+3.0)) if np.any(seg > runmin+3.0) else len(seg)
            if k >= int(0.12*fs) and seg[0]-seg[k-1] >= 6:
                t = np.arange(k)/fs; slope, icpt = np.polyfit(t, seg[:k], 1); fit = slope*t+icpt
                r2 = 1-np.sum((seg[:k]-fit)**2)/(np.sum((seg[:k]-seg[:k].mean())**2)+1e-9)
                if -400 < slope < -6 and r2 > 0.6:
                    rt.append(60/(-slope)); tails.append(seg[min(k-1, int(0.3*fs))]-edb[i-1])
            i += max(k, int(0.3*fs))
        else: i += 1
    if len(rt) < 4: return None
    rt60 = float(np.median(rt)); tail = float(np.median(tails))
    conf = float(np.clip((len(rt)-3)/10, 0, 1)*np.clip((rt60-0.45)/0.5, 0, 1))
    if rt60 < 0.6 or conf < 0.2: return None
    wet = float(np.clip((tail+40)/30, 0.05, 0.6))
    return dict(rt60_s=round(rt60, 2), wet=round(wet, 2), confidence=round(conf, 2))

def analyse_effects_heuristic(x, sr, log=print):
    """Signal-only estimates (no AI): used when the separation models are not installed."""
    fx = {}
    for key, fn in (("tremolo", analyse_tremolo), ("modulation", analyse_modulation), ("delay", analyse_delay), ("reverb", analyse_reverb)):
        try:
            r = fn(x, sr)
            if r: fx[key] = dict(r, method="Signalanalyse")
        except Exception as e:
            log("  Effekt-Analyse %s übersprungen: %s" % (key, e))
    return fx

# ---------------------------------------------------------------- AI-assisted effect analysis
# 1. The De-Echo model splits the excerpt into "no echo" + echo, De-Reverb splits "no echo" into dry + reverb.
# 2. Delay: least-squares fit echo ≈ a1·dry(t−T) + a2·dry(t−2T) at the cross-correlation peak → time, level, feedback.
# 3. Reverb: analysis by synthesis – the dry part runs through the program's own reverb for a grid of room sizes and
#    dampings; the setting whose band envelopes match the separated reverb best wins, its level follows from the fit.
#    Pre-delay from the envelope cross-correlation, RT60 measured on the impulse response of the fitted reverb.
# 4. Tremolo / chorus / flanger: envelope analysis on the dry part (the reverb tail no longer smears the modulation).
FX_EXCERPT_S = 40.0

def active_excerpt(x, sr, seconds=FX_EXCERPT_S, start=False):
    """The most active part of a signal (seconds long), so the costly analysis does not run over whole songs.
    start=True also returns its first sample index."""
    n = int(seconds*sr); s0 = 0
    if len(x) > n:
        hop = sr//2; e = (x[:len(x)//hop*hop]**2).reshape(-1, hop, x.shape[1]).mean(axis=(1, 2))
        k = max(1, n//hop); c = np.convolve(e, np.ones(k), mode="valid"); s0 = int(np.argmax(c))*hop
    return (x[s0:s0+n], s0) if start else x[s0:s0+n]

def separate_array(x, sr, model, log=print, cancel=None, progress=None):
    """Runs a separation model on an in-memory signal. Returns dict key -> float64 (n,2) arrays of the same length."""
    tmp = os.path.join(USER_DIR, "stems_tmp"); os.makedirs(tmp, exist_ok=True)
    src = os.path.join(tmp, "fx_%d_%d.wav" % (os.getpid(), int(time.time()*1000))); sf.write(src, x.astype(np.float32), sr, subtype="FLOAT")
    try:
        outs, work, used = separate(src, model, log=lambda m: None, progress=progress, cancel=cancel, sr=sr)
        try:
            res = {}
            for k, p in outs.items():
                y, s2 = sf.read(p, dtype="float64", always_2d=True)
                if y.shape[1] == 1: y = np.repeat(y, 2, axis=1)
                if s2 != sr: y = signal.resample_poly(y, sr, s2, axis=0)
                y = y[:len(x), :2]
                if len(y) < len(x): y = np.concatenate([y, np.zeros((len(x)-len(y), 2))])
                res[k] = y
            return res
        finally:
            shutil.rmtree(work, ignore_errors=True)
    finally:
        try: os.remove(src)
        except OSError: pass

def _pick(outs, keys):
    for k in keys:
        if k in outs: return outs[k]
    return None

def _band(m, sr, lo=150.0, hi=8000.0):
    sos = signal.butter(2, [lo, min(hi, 0.45*sr)], "bandpass", fs=sr, output="sos"); return signal.sosfiltfilt(sos, m, axis=0)

def comb_echo(x, sr, time_s, feedback):
    """Echo part of a feedback delay: x(t−T) + fb·x(t−2T) + fb²·x(t−3T) … (without the dry signal)."""
    T = max(1, int(round(time_s*sr))); n = len(x); e = np.zeros_like(x)
    if T >= n: return e
    e[T:] = x[:n-T]
    fb = float(np.clip(feedback, 0.0, 0.95))
    if fb > 1e-3:
        for s0 in range(2*T, n, T):
            k = min(T, n-s0); e[s0:s0+k] += fb*e[s0-T:s0-T+k]
    return e

def estimate_tempo(x, sr, lo_bpm=60.0, hi_bpm=190.0):
    """Tempo (BPM) of a signal from the autocorrelation of its onset envelope (spectral flux of band envelopes).
    Local: on an excerpt it gives the tempo of that passage, so tempo changes elsewhere in the song do not matter."""
    hop = max(1, int(0.01*sr)); fs = sr/hop; flux = None
    for lo, hi in ((40, 200), (200, 1500), (1500, 6000)):
        if lo >= 0.45*sr: continue
        b = _band(x.mean(axis=1), sr, lo, hi); n = len(b)//hop
        e = np.log1p(1000*np.sqrt((b[:n*hop]**2).reshape(n, hop).mean(axis=1))); d = np.maximum(np.diff(e, prepend=e[0]), 0)
        flux = d if flux is None else flux[:len(d)]+d[:len(flux)]
    if flux is None or len(flux) < 4*fs: return None
    flux = flux-np.convolve(flux, np.ones(int(fs))/int(fs), mode="same")
    ac = signal.correlate(flux, flux, mode="full", method="fft")[len(flux)-1:]; ac /= ac[0]+1e-12
    lags = np.arange(int(fs*60/hi_bpm), int(fs*60/lo_bpm)+1)
    if lags[-1] >= len(ac): return None
    w = np.exp(-0.5*(np.log2(60*fs/lags/120.0)/1.0)**2)          # mild preference around 120 BPM (octave errors)
    k = lags[int(np.argmax(ac[lags]*w))]
    if ac[k] < 0.05: return None
    return float(60*fs/k)

NOTE_VALUES = [("1/16", 0.25), ("1/8 Triole", 1/3), ("1/8", 0.5), ("1/16 punktiert", 0.375), ("1/4 Triole", 2/3), ("1/8 punktiert", 0.75),
               ("1/4", 1.0), ("1/2 Triole", 4/3), ("1/4 punktiert", 1.5), ("1/2", 2.0)]

def _pick_lag(seg, lo, step_s, tempo):
    """Lag index into seg (correlation over lags lo…) – the free maximum, or a musical note value of the tempo when it
    correlates almost as well (delays are usually set to note values). Returns (index, note name or None, bonus)."""
    k = int(np.argmax(seg)); peak = float(seg[k])
    if not tempo or peak <= 0: return k, None, 1.0
    beat = 60.0/tempo; best = None
    for name, mult in NOTE_VALUES:
        c = int(round(beat*mult/step_s))-lo; w = max(1, int(0.03*c))
        if c-w < 0 or c+w >= len(seg): continue
        j = c-w+int(np.argmax(seg[c-w:c+w+1]))
        if best is None or seg[j] > seg[best[0]]: best = (j, name)
    if best and seg[best[0]] >= 0.85*peak:
        return best[0], best[1], 1.25
    return k, None, 1.0

def _fit_delay_wave(d, e, sr, Ed, Ee, tempo=None):
    """Waveform least squares: exact for clean digital delays."""
    lo, hi = int(0.04*sr), min(int(1.6*sr), len(d)//3)
    if hi <= lo+10: return None
    cf = signal.correlate(e, d, mode="full", method="fft")/math.sqrt(Ed*Ee); c = cf[len(d)-1:]; cn = cf[len(d)-1::-1]   # cn[L]: echo *before* dry
    seg = c[lo:hi]; k, note, bonus = _pick_lag(seg, lo, 1.0/sr, tempo); T = lo+k
    if seg[k] < 0.08 or k == 0: return None
    if cn[T] > 0.5*seg[k]: return None          # as similar backwards in time: the music repeats itself, no echo
    d1 = np.zeros_like(d); d1[T:] = d[:-T]; d2 = np.zeros_like(d)
    if 2*T < len(d): d2[2*T:] = d[:-2*T]
    A = np.stack([d1, d2], axis=1); coef, *_ = np.linalg.lstsq(A, e, rcond=None); a1, a2 = float(coef[0]), float(coef[1])
    if a1 <= 0.01: return None
    r2 = 1-float(np.sum((e-A@coef)**2))/Ee
    return dict(T=T/sr, a1=a1, fb=float(np.clip(a2/a1, 0.0, 0.85)), fit=r2, conf=float(np.clip(bonus*(r2-0.08)/0.35, 0, 1)), note=note)

def _fit_delay_env(dry, echo, sr, tempo=None):
    """Band-envelope fit: robust when the repeats are filtered, saturated or modulated (tape/analog delays)."""
    hop = max(1, int(0.005*sr)); bands = ((200, 600), (600, 1500), (1500, 4000), (4000, 9000))
    def env(x):
        out = []
        for lo, hi in bands:
            if lo >= 0.45*sr: continue
            b = _band(x.mean(axis=1), sr, lo, hi); n = len(b)//hop
            out.append(np.sqrt((b[:n*hop]**2).reshape(n, hop).mean(axis=1)))
        return np.array(out)
    D, E = env(dry), env(echo); n = D.shape[1]
    lo, hi = int(0.08*sr/hop), min(int(1.6*sr/hop), n//3)          # shorter lags: room reflections, not echoes
    if hi <= lo+4: return None
    # Music repeats itself in time with the beat, so the echo envelope also correlates with the dry one a beat earlier without
    # any delay. Only what the delayed signal explains *beyond* the simultaneous one counts (partial correlation).
    Dz = D-D.mean(axis=1, keepdims=True); Ez = E-E.mean(axis=1, keepdims=True)
    beta = np.sum(Ez*Dz, axis=1, keepdims=True)/(np.sum(Dz*Dz, axis=1, keepdims=True)+1e-12); R = Ez-beta*Dz
    c = np.zeros(hi); cn = np.zeros(hi)
    for b in range(D.shape[0]):
        full = signal.correlate(R[b], Dz[b], mode="full", method="fft"); c += full[n-1:n-1+hi]; cn += full[n-1::-1][:hi]
    norm = math.sqrt(float(np.sum(Dz**2))*float(np.sum(R**2)))+1e-12; c /= norm; cn /= norm
    # An echo only follows its source. Music that repeats itself (bars, riffs) is just as similar backwards in time,
    # so only the part of the correlation that is missing in the other direction counts.
    c = c-np.maximum(cn, 0)
    seg = c[lo:hi]; k, note, bonus = _pick_lag(seg, lo, hop/sr, tempo); T = lo+k; peak = float(seg[k])
    if k == 0 or k == len(seg)-1 or peak <= 0: return None
    def shifted(L):
        z = np.zeros_like(D)
        if L < n: z[:, L:] = D[:, :-L]
        return z
    y = E.ravel(); ones = np.ones_like(y)
    base = np.stack([ones, D.ravel()], axis=1); full = np.stack([ones, D.ravel(), shifted(T).ravel(), shifted(2*T).ravel()], axis=1)
    cb, *_ = np.linalg.lstsq(base, y, rcond=None); cf, *_ = np.linalg.lstsq(full, y, rcond=None)
    sse_b, sse_f = float(np.sum((y-base@cb)**2)), float(np.sum((y-full@cf)**2)); a1, a2 = float(cf[2]), float(cf[3])
    if a1 <= 0.01: return None
    partial = (sse_b-sse_f)/(sse_b+1e-12); fb = a2/a1
    if T*hop/sr > 0.7 and not note: bonus *= 0.3           # long delays are practically always set to a note value
    conf = float(np.clip(bonus*(partial-0.03)/0.12, 0, 1)*np.clip((0.8-fb)/0.2, 0, 1))      # feedback at the limit: repeating music
    return dict(T=T*hop/sr, a1=a1, fb=float(np.clip(a2/a1, 0.0, 0.85)), fit=partial, conf=conf, note=note)

def fit_delay(dry, echo, sr, tempo=None):
    """Delay parameters from the separated echo. tempo (BPM) makes note values preferred delay times.
    Returns dict(time_s, level, feedback, echo_db, confidence, note) or None."""
    d = _band(dry.mean(axis=1), sr); e = _band(echo.mean(axis=1), sr)
    Ed, Ee = float(np.sum(d*d))+1e-12, float(np.sum(e*e))+1e-12; echo_db = 10*np.log10(Ee/Ed)
    if echo_db < -38: return None
    cands = [c for c in (_fit_delay_wave(d, e, sr, Ed, Ee, tempo), _fit_delay_env(dry, echo, sr, tempo)) if c]
    if not cands: return None
    best = max(cands, key=lambda c: c["conf"]); conf = float(best["conf"]*np.clip((echo_db+38)/14, 0, 1))
    return dict(time_s=round(best["T"], 3), level=round(float(np.clip(best["a1"], 0.02, 1.2)), 3), feedback=round(best["fb"], 2), echo_db=round(echo_db, 1),
                fit=round(best["fit"], 2), confidence=round(conf, 2), method="KI", **({"note": best["note"], "tempo": round(tempo, 1)} if best.get("note") else {}))

def _band_env_db(x, sr, hop=1024, bands=((200, 500), (500, 1000), (1000, 2000), (2000, 4000), (4000, 8000))):
    m = x.mean(axis=1) if x.ndim == 2 else x; out = []
    for lo, hi in bands:
        if lo >= 0.45*sr: continue
        b = _band(m, sr, lo, hi); n = len(b)//hop
        out.append(10*np.log10((b[:n*hop]**2).reshape(n, hop).mean(axis=1)+1e-14))
    return np.array(out)

def reverb_wet(x, sr, room_size, damping, predelay_ms=0.0, width=1.0):
    """Wet signal of the program's reverb (without dry part), optionally pre-delayed."""
    import pedalboard as pb
    pd = int(max(0.0, predelay_ms)/1000*sr)
    src = np.concatenate([np.zeros((pd, x.shape[1])), x[:len(x)-pd]]) if pd else x
    board = pb.Pedalboard([pb.Reverb(room_size=float(room_size), damping=float(damping), wet_level=1.0, dry_level=0.0, width=float(width))])
    return board(np.ascontiguousarray(src.T, dtype=np.float32), sr).T.astype(np.float64)[:len(x)]

def rt60_of(room_size, damping, sr=44100):
    """Reverberation time of the program's reverb, measured on its impulse response (Schroeder, T20 extrapolated)."""
    imp = np.zeros((int(8*sr), 2)); imp[0] = 1.0; h = reverb_wet(imp, sr, room_size, damping).mean(axis=1)
    edc = np.cumsum((h**2)[::-1])[::-1]; edc = 10*np.log10(edc/edc[0]+1e-20)
    i5, i25 = int(np.argmax(edc <= -5)), int(np.argmax(edc <= -25))
    return float(3*(i25-i5)/sr) if i25 > i5 else 0.0

_RT_TABLE = {}
def _rt_table(sr, damping):
    """RT60 of the program's reverb over room size (for one damping), measured once per sample rate."""
    key = (int(sr), round(float(damping), 2))
    if key not in _RT_TABLE:
        rooms = np.linspace(0.05, 0.97, 24); _RT_TABLE[key] = (rooms, np.array([rt60_of(r, damping, sr) for r in rooms]))
    return _RT_TABLE[key]

def _decays(dry, wet, sr, hop=256):
    """Decay rates of the separated reverb right after the dry signal stops (note ends): list of RT60 values in s."""
    def env(x, smooth=1):
        b = _band(x.mean(axis=1), sr, 200, 8000); n = len(b)//hop; e = (b[:n*hop]**2).reshape(n, hop).mean(axis=1)
        if smooth > 1: e = np.convolve(e, np.ones(smooth)/smooth, mode="same")        # reverb algorithms flutter
        return 10*np.log10(e+1e-14)
    ed, ew = env(dry), env(wet, max(1, int(0.025*sr/hop))); fs = sr/hop; n = min(len(ed), len(ew)); out = []
    k60, k150, kmax = int(0.06*fs), int(0.15*fs), int(1.6*fs); i = 1
    while i < n-kmax:
        if ed[i-1]-ed[i:i+k60].min() > 12 and ed[i+k60:i+k60+k150].max() < ed[i-1]-12 and ew[i] > ew.max()-35:
            seg = ew[i:i+kmax]; runmin = np.minimum.accumulate(seg); stop = np.where(seg > runmin+4.0)[0]
            k = int(stop[0]) if len(stop) else len(seg)
            if k >= k150 and seg[0]-seg[k-1] >= 8:
                t = np.arange(k)/fs; slope, icpt = np.polyfit(t, seg[:k], 1); fit = slope*t+icpt
                r2 = 1-np.sum((seg[:k]-fit)**2)/(np.sum((seg[:k]-seg[:k].mean())**2)+1e-9)
                if slope < -8 and r2 > 0.7: out.append(float(min(12.0, 60/-slope)))
            i += max(k, k150)
        else: i += 1
    return out

def _hf_tilt(ref, x, sr):
    """Level of x relative to ref at 4-8 kHz minus at 0.5-1.5 kHz (dB): how much darker the reverb is than its source."""
    f, Pr = signal.welch(ref.mean(axis=1), sr, nperseg=4096); _, Px = signal.welch(x.mean(axis=1), sr, nperseg=4096)
    d = 10*np.log10((Px+1e-20)/(Pr+1e-20)); hi = (f >= 4000) & (f <= min(8000, 0.45*sr)); lo = (f >= 500) & (f <= 1500)
    return float(np.mean(d[hi])-np.mean(d[lo])) if hi.any() else 0.0

def _reverb_synth(dx, wx, sr):
    """Grid + local search: settings of the program's reverb whose band envelopes match the separated reverb best.
    Returns (error dB², room, damping, pre-delay ms, level offset dB)."""
    hop_e = 1024; skip = int(2.0*sr/hop_e)              # the first seconds lack the tail of what came before the excerpt
    W = _band_env_db(wx, sr, hop_e)[:, skip:]; msk = W > W.max()-40; tried = {}
    def score(room, damp, pd):
        key = (round(float(np.clip(room, 0.05, 0.97)), 3), round(float(np.clip(damp, 0.0, 1.0)), 3), round(float(np.clip(pd, 0.0, 120.0)), 1))
        if key not in tried:
            R = _band_env_db(reverb_wet(dx, sr, *key), sr, hop_e)[:, skip:]
            n = min(R.shape[1], W.shape[1]); m = msk[:, :n]; diff = (W[:, :n]-R[:, :n])[m]
            off = float(np.median(diff)) if diff.size else 0.0; tried[key] = (float(np.mean((diff-off)**2)) if diff.size else 1e9,)+key+(off,)
        return tried[key]
    best = min(score(r, d, 0.0) for r in (0.15, 0.3, 0.45, 0.6, 0.72, 0.84, 0.93) for d in (0.2, 0.5, 0.8))
    best = min([best]+[score(best[1], best[2], pd) for pd in (10, 20, 35, 50, 70, 95)])
    for sr_, sd_, sp_ in ((0.06, 0.15, 8.0), (0.03, 0.075, 4.0)):
        best = min([best]+[score(best[1]+a*sr_, best[2]+b*sd_, best[3]+c*sp_) for a in (-1, 0, 1) for b in (-1, 0, 1) for c in (-1, 0, 1)])
    return best

def fit_reverb(dry, wet, sr):
    """Reverb parameters from the separated reverb: RT60 from its decays after note ends, damping from its high-frequency loss,
    level from the energy ratio – each translated into the settings of the program's own reverb."""
    try:
        import pedalboard  # noqa: F401
    except Exception:
        return None
    Ed, Ew = float(np.mean(dry**2))+1e-14, float(np.mean(wet**2))+1e-14; wet_db = 10*np.log10(Ew/Ed)
    if wet_db < -32: return None
    ex = active_excerpt(np.concatenate([dry, wet], axis=1), sr, 25.0); dx, wx = ex[:, :2], ex[:, 2:]
    # damping: compare the high-frequency loss of the separated reverb with that of the own reverb at damping 0 / 0.5 / 1
    tilt = _hf_tilt(dx, wx, sr); probe = {dmp: _hf_tilt(dx, reverb_wet(dx, sr, 0.6, dmp), sr) for dmp in (0.0, 0.5, 1.0)}
    xs = [probe[0.0], probe[0.5], probe[1.0]]
    damp = float(np.clip(np.interp(tilt, xs[::-1], [1.0, 0.5, 0.0]) if xs[0] > xs[2] else 0.5, 0.0, 1.0))
    decays = _decays(dry, wet, sr)
    pd = 0.0
    if len(decays) >= 3:
        rt = float(np.median(decays)); rooms, rts = _rt_table(sr, round(damp*4)/4)
        room = float(np.interp(rt, rts, rooms)) if np.all(np.diff(rts) > 0) else float(rooms[int(np.argmin(np.abs(rts-rt)))])
        method_conf = float(np.clip((len(decays)-2)/6, 0, 1))
    else:                                                               # too few note ends: analysis by synthesis
        err, room, damp, pd, _off = _reverb_synth(dx, wx, sr); rt = None
        method_conf = float(np.clip((25-err)/15, 0.15, 1.0))
    rw = reverb_wet(dx, sr, room, damp); g = float(np.sqrt(float(np.mean(wx**2))/(float(np.mean(rw**2))+1e-14)))
    conf = float(np.clip((wet_db+32)/14, 0, 1)*method_conf)
    return dict(rt60_s=round(rt if rt is not None else rt60_of(room, damp, sr), 2), wet=round(float(np.clip(g, 0.0, 2.0)), 3), room_size=round(room, 3),
                damping=round(damp, 2), predelay_ms=round(float(pd), 1), wet_db=round(wet_db, 1), decays=len(decays), confidence=round(conf, 2), method="KI")

def fx_ai_available():
    return separation_available()

def analyse_effects(x, sr, log=print, ai=True, cancel=None, progress=None, context=None):
    """Delay, reverb, tremolo and chorus/flanger of an (instrument) signal. With ai=True and installed separation the AI path is
    used (echo and reverb are split off first), otherwise signal heuristics. context: the whole song (same length as x) –
    its tempo in the analysed passage makes note values preferred delay times."""
    if not (ai and fx_ai_available()): return analyse_effects_heuristic(x, sr, log=log)
    ex, s0 = active_excerpt(x, sr, start=True); fx = {}
    try: tempo = estimate_tempo(context[s0:s0+len(ex)] if context is not None and len(context) == len(x) else ex, sr)
    except Exception: tempo = None
    def prog(a, b): return (lambda f: progress(a+(b-a)*f)) if progress else None
    try:
        oe = separate_array(ex, sr, "deecho", log=log, cancel=cancel, progress=prog(0.0, 0.35))
        noecho = _pick(oe, ("no echo", "noecho", "no_echo"))
        if noecho is None: raise RuntimeError("De-Echo lieferte keine Spur (%s)" % ", ".join(oe))
        d = fit_delay(noecho, ex-noecho, sr, tempo)
        if d and d["confidence"] >= 0.2: fx["delay"] = d
        orv = separate_array(noecho, sr, "dereverb", log=log, cancel=cancel, progress=prog(0.35, 0.8))
        dry = _pick(orv, ("dry", "no reverb", "noreverb"))
        if dry is None: raise RuntimeError("De-Reverb lieferte keine Spur (%s)" % ", ".join(orv))
        r = fit_reverb(dry, noecho-dry, sr)
        if r and r["confidence"] >= 0.2: fx["reverb"] = r
        for key, fn in (("tremolo", analyse_tremolo), ("modulation", analyse_modulation)):
            v = fn(dry, sr)
            if v: fx[key] = dict(v, method="Signalanalyse (trocken)")
        if progress: progress(1.0)
        return fx
    except Cancelled:
        raise
    except BaseException as e:
        log("  KI-Effektanalyse nicht möglich (%s) – Signalanalyse" % e)
        return analyse_effects_heuristic(x, sr, log=log)

def describe_effect(key, v):
    if key == "tremolo": return "Tremolo %.1f Hz, Tiefe %.1f dB" % (v["rate_hz"], v["depth_db"])
    if key == "modulation": return "%s %.2f Hz, Tiefe %.1f ms, Verzögerung %.1f ms, Feedback %.0f %%" % (v["kind"], v["rate_hz"], v["depth_ms"], v["centre_ms"], v["feedback"]*100)
    if key == "delay": return "Delay %.0f ms%s, Echo %.0f %%, Feedback %.0f %%" % (v["time_s"]*1000, (" (%s bei %.0f BPM)" % (v["note"], v["tempo"])) if v.get("note") else "", v["level"]*100, v["feedback"]*100)
    if key == "reverb":
        extra = (", Raum %.0f %%, Dämpfung %.0f %%, Pre-Delay %.0f ms" % (v["room_size"]*100, v.get("damping", 0.5)*100, v.get("predelay_ms", 0))) if "room_size" in v else ""
        return "Hall RT60 %.1f s, Anteil %.0f %%%s" % (v["rt60_s"], v["wet"]*100, extra)
    return key

def merge_effects(list_of_fx):
    """Median of parameters over references; an effect counts only if found in at least half of them."""
    out = {}; n = len(list_of_fx)
    for key in ("tremolo", "modulation", "delay", "reverb"):
        found = [f[key] for f in list_of_fx if key in f]
        if not found or len(found) < max(1, n/2): continue
        m = {}
        for k in found[0]:
            vals = [f[k] for f in found if k in f]
            m[k] = vals[0] if isinstance(vals[0], str) else float(np.median(vals))
        m["confidence"] = round(m["confidence"]*len(found)/n, 2); out[key] = m
    return out

FX_DEFAULTS = {
    "tremolo": dict(rate_hz=5.0, depth_db=6.0),
    "modulation": dict(kind="Chorus", rate_hz=0.8, depth_ms=2.0, centre_ms=7.0, feedback=0.0),
    "delay": dict(time_s=0.35, level=0.3, feedback=0.3),
    "reverb": dict(rt60_s=1.2, wet=0.2, room_size=0.6, damping=0.5, predelay_ms=10.0),
}

def room_for_rt60(rt60):
    """Room size for profiles that only store a reverberation time (Mastering-Tool 2.x)."""
    return float(np.clip((float(rt60)-0.3)/2.7, 0.1, 0.95))

def apply_effects(x, sr, fx, log=print):
    """fx = {"tremolo": {..., "strength": s}, "modulation": {...}, "delay": {...}, "reverb": {...}}; strength 0 = off.
    Delay and reverb are added to the signal (the dry part stays at 100 %); strength scales the effect level."""
    y = x
    v = fx.get("tremolo", {}); st = float(v.get("strength", 0))
    if st > 0:
        t = np.arange(len(y))/sr; depth = 1-10**(-float(v["depth_db"])*st/20)
        y = y*(1-depth*0.5*(1-np.cos(2*np.pi*float(v["rate_hz"])*t)))[:, None]
    try:
        import pedalboard as pb
    except Exception:
        pb = None
        if any(float(fx.get(k, {}).get("strength", 0)) > 0 for k in ("modulation", "reverb")):
            log("  pedalboard fehlt: Chorus/Hall werden übersprungen (pip install pedalboard)")
    v = fx.get("modulation", {}); st = float(v.get("strength", 0))
    if st > 0 and pb is not None:
        board = pb.Pedalboard([pb.Chorus(rate_hz=float(v["rate_hz"]), depth=float(np.clip(float(v["depth_ms"])/10.0, 0.05, 1.0)), centre_delay_ms=float(max(0.5, float(v["centre_ms"]))),
                                         feedback=float(np.clip(float(v.get("feedback", 0))*st, 0, 0.9)), mix=float(np.clip(0.5*st, 0, 0.9)))])
        y = board(np.ascontiguousarray(y.T, dtype=np.float32), sr).T.astype(np.float64)
    v = fx.get("delay", {}); st = float(v.get("strength", 0))
    if st > 0 and float(v.get("level", 0)) > 0:
        y = y+float(v["level"])*st*comb_echo(y, sr, float(v["time_s"]), float(v.get("feedback", 0)))
    v = fx.get("reverb", {}); st = float(v.get("strength", 0))
    if st > 0 and pb is not None and float(v.get("wet", 0)) > 0:
        room = float(v["room_size"]) if "room_size" in v else room_for_rt60(v.get("rt60_s", 1.2))
        y = y+float(v["wet"])*st*reverb_wet(y, sr, room, float(v.get("damping", 0.5)), float(v.get("predelay_ms", 0.0)))
    return y

TRACK_DEFAULTS = dict(strength=1.0, max_eq=9.0, eq_lo=40.0, eq_hi=16000.0, dyn_strength=1.0, transient_strength=1.0, saturation=0.0,
                      width_mode="profil", width_db_manual=0.0, target_lufs=None, out_bits=24, fx=None)

def render_track(x, sr, mono, prof, log=print, **kw):
    """Makes a raw instrument track sound like the instrument profile: spectrum, dynamics, transients, width, level."""
    p = {**TRACK_DEFAULTS, **kw}; before_spec = smooth_spectrum(x, sr)
    x = hpf(x, sr, 20)
    # 1. spectrum
    corr = np.clip(p["strength"]*(prof["spec"]-before_spec), -p["max_eq"], p["max_eq"])
    corr = corr*np.clip(np.log2(FL/p["eq_lo"])*3+1, 0, 1)*np.clip(np.log2(p["eq_hi"]/FL)*3+1, 0, 1)
    x = fir_eq(x, sr, corr)
    info = dict(eq_min=float(corr.min()), eq_max=float(corr.max()), ratio=1.0, transient_change=0.0, eq_curve=corr)
    # 2. dynamics: compress toward the profile crest factor (never expands). Threshold from the audible part only,
    #    so tracks with long pauses are not squashed.
    if p["dyn_strength"] > 0:
        c0 = crest_db(x); target_crest = c0-(c0-prof["crest"])*p["dyn_strength"]
        if c0 > target_crest+0.5:
            thr = gated_rms_db(x, sr)+2.0; y = x
            for ratio in (1.5, 2.0, 3.0, 4.0, 6.0, 8.0):
                y, _ = compress(x, sr, thr, ratio); info["ratio"] = ratio
                if crest_db(y) <= target_crest+0.5: break
            x = y
    # 3. transients toward the profile
    if p["transient_strength"] > 0:
        d = float(np.clip((prof["transient"]-transient_db(x, sr))*p["transient_strength"], -4.0, 6.0)); info["transient_change"] = d
        x = transient_shape_db(x, sr, d)
    # 4. saturation (taste) and detected effects
    x = saturate(x, p["saturation"])
    if p.get("fx"):
        x = apply_effects(x, sr, p["fx"], log=log)
        info["effects"] = ", ".join("%s %.0f %%" % (k, float(v.get("strength", 0))*100) for k, v in p["fx"].items() if float(v.get("strength", 0)) > 0)
    # 5. width
    if not mono:
        wd = 0.0
        if p["width_mode"] == "profil": wd = float(np.clip(prof["width"]-width_db(x, sr), -6, 6))
        elif p["width_mode"] == "manuell": wd = float(p["width_db_manual"])
        if abs(wd) > 0.05: x = widen(x, sr, 200, wd)
        info["width_change"] = wd
    # 6. level, with peak safety
    target = prof["lufs"] if p["target_lufs"] is None else p["target_lufs"]
    x = x*10**((target-integrated(x, sr))/20)
    if true_peak(x, sr) > 10**(-0.5/20): x, gr = limiter(x, sr, -0.5, osf=4); info["limiter"] = gr
    return np.clip(x, -1, 1), info

def match_track(path, prof, out_dir, log=print, taken=None, protect=(), **kw):
    p = {**TRACK_DEFAULTS, **kw}; t0 = time.time(); name = os.path.splitext(os.path.basename(path))[0]
    x, sr, mono = load_track(path); before = track_features(x, sr)
    log("%s: %.1f LUFS, Crest %.1f dB, Transienten %+.1f dB%s" % (name, before["lufs"], before["crest"], before["transient"], " (mono)" if mono else ""))
    y, info = render_track(x, sr, mono, prof, log=log, **p)
    os.makedirs(out_dir, exist_ok=True); out = output_path(out_dir, path, taken, protect=protect, tag="angeglichen")
    write_audio(out, y.mean(axis=1, keepdims=True) if mono else y, sr, p["out_bits"])     # mean: effects may have made L and R differ
    after = track_features(y, sr)
    log("  → %.1f LUFS, Crest %.1f dB (Ziel %.1f), Transienten %+.1f dB, Breite %.1f dB, EQ %+.1f..%+.1f dB, Kompression 1:%.1f  (%.0f s)" % (
        after["lufs"], after["crest"], prof["crest"], after["transient"], after["width"], info["eq_min"], info["eq_max"], info["ratio"], time.time()-t0))
    return dict(name=name, out=out, before=before, after=after, **info)

def run_track_batch(files, prof, out_dir, log=print, progress=None, cancel=None, **kw):
    rows = []; taken = set()
    for i, p in enumerate(files):
        if cancel is not None and cancel.is_set(): log("Abgebrochen."); break
        try: rows.append(match_track(p, prof, out_dir, log=log, taken=taken, protect=files, **kw))
        except Cancelled: log("Abgebrochen."); break
        except Exception as e: log("FEHLER %s: %s" % (os.path.basename(p), e))
        if progress: progress(i+1, len(files))
    if rows:
        rp = os.path.join(out_dir, "Spur-Angleich-Protokoll.csv")
        with open(rp, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh, delimiter=";"); w.writerow(["Spur", "LUFS vorher", "LUFS nachher", "Crest vorher", "Crest nachher", "Crest Profil", "Transienten vorher", "Transienten nachher", "EQ min", "EQ max", "Kompression"])
            for r in rows: w.writerow([r["name"], "%.1f" % r["before"]["lufs"], "%.1f" % r["after"]["lufs"], "%.1f" % r["before"]["crest"], "%.1f" % r["after"]["crest"], "%.1f" % prof["crest"], "%.1f" % r["before"]["transient"], "%.1f" % r["after"]["transient"], "%.1f" % r["eq_min"], "%.1f" % r["eq_max"], "1:%.1f" % r["ratio"]])
        log("Protokoll: %s" % rp)
    return rows
