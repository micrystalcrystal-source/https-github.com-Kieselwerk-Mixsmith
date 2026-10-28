# -*- coding: utf-8 -*-
"""Builds the Linux (.tar.gz) and macOS (.zip) install packages of Mixsmith from the sources:  python packaging/make_unix_packages.py

Both packages install the program into a Python virtual environment on the target machine (Linux: menu entry + command,
macOS: ~/Applications/Mixsmith.app). Scripts get LF line endings and the executable bit, whatever OS builds them."""
import os, re, io, tarfile, zipfile, time
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
VER = re.search(r'APP_VERSION = "([^"]+)"', open(os.path.join(ROOT, "audio_core.py"), encoding="utf-8").read()).group(1)
OUT = os.path.join(ROOT, "installer")
APP_FILES = ["audio_core.py", "mix_core.py", "mixsmith_gui.py", "mixsmith.py", "requirements.txt", "README.md", "LICENSE", "LIZENZEN.md", "logo.png", "logo.ico"]

def app_entries():
    for f in APP_FILES: yield f, open(os.path.join(ROOT, f), "rb").read()
    for f in sorted(os.listdir(os.path.join(ROOT, "profiles"))):
        yield "profiles/" + f, open(os.path.join(ROOT, "profiles", f), "rb").read()
    for f in ("Mixsmith-Tutorial.mp4", "Mixsmith-Tutorial.json"):
        if os.path.exists(os.path.join(ROOT, "tutorial", f)): yield "tutorial/" + f, open(os.path.join(ROOT, "tutorial", f), "rb").read()

def lf(path): return open(path, "rb").read().replace(b"\r\n", b"\n")

def icns():
    buf = io.BytesIO(); src = os.path.join(ROOT, "logo_1024.png")
    Image.open(src if os.path.exists(src) else os.path.join(ROOT, "logo.png")).save(buf, format="ICNS"); return buf.getvalue()

def linux():
    base = "Mixsmith-%s-Linux" % VER; out = os.path.join(OUT, base + ".tar.gz")
    with tarfile.open(out, "w:gz") as tf:
        def add(name, data, mode=0o644):
            ti = tarfile.TarInfo(base + "/" + name); ti.size = len(data); ti.mode = mode; ti.mtime = int(time.time()); tf.addfile(ti, io.BytesIO(data))
        for n, d in app_entries(): add(n, d)
        add("install.sh", lf(os.path.join(HERE, "linux", "install.sh")), 0o755)
    return out

def macos():
    base = "Mixsmith-%s-macOS" % VER; out = os.path.join(OUT, base + ".zip")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        def add(name, data, mode=0o644):
            zi = zipfile.ZipInfo(base + "/" + name, time.localtime()[:6]); zi.create_system = 3; zi.external_attr = (0o100000 | mode) << 16
            zi.compress_type = zipfile.ZIP_DEFLATED; zf.writestr(zi, data)
        for n, d in app_entries(): add("app/" + n, d)
        add("app/logo.icns", icns())
        add("Mixsmith installieren.command", lf(os.path.join(HERE, "macos", "Mixsmith installieren.command")), 0o755)
        add("LIESMICH.txt", ("Mixsmith %s für macOS\n\n1. Rechtsklick auf „Mixsmith installieren.command“ → Öffnen (beim ersten Mal bestätigen).\n"
                             "2. Die Frage nach der KI-Stem-Trennung beantworten.\n3. Mixsmith liegt danach im Ordner Programme (Ihres Benutzers).\n\n"
                             "Voraussetzung: Python 3.10+ (python.org oder Homebrew); für die KI-Trennung zusätzlich ffmpeg (brew install ffmpeg).\n"
                             "Entfernen: ~/Library/Application Support/Mixsmith-App/uninstall.command\n") % VER)
    return out

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for f in (linux(), macos()): print("%s  (%.1f MB)" % (f, os.path.getsize(f)/2**20))
