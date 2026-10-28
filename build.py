# -*- coding: utf-8 -*-
"""Builds the Mixsmith packages.

  python build.py light     -> Mixsmith.exe (portable, ohne KI-Trennung, PyInstaller onefile)
  python build.py full      -> installer/Mixsmith-<ver>-Setup.exe (Vollversion mit KI, PyInstaller onedir + Inno Setup)
  python build.py msi       -> dist/Mixsmith-<ver>-win64.msi (ohne KI, cx_Freeze)
  python build.py source    -> installer/Mixsmith-<ver>-Quelltext.zip (vollständiger Quelltext, GPLv3)
  python build.py setup     -> installer/Mixsmith-<ver>-Windows-Setup.exe (ohne KI, Installer im Kieselwerk-Stil)
"""
import os, sys, shutil, subprocess, re, zipfile
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE)
VER = re.search(r'APP_VERSION = "([^"]+)"', open("audio_core.py", encoding="utf-8").read()).group(1)
NAME = "Mixsmith"
DATA = ["--add-data", "logo.ico;.", "--add-data", "logo.png;.", "--add-data", "README.md;.", "--add-data", "LICENSE;.", "--add-data", "LIZENZEN.md;."]
for f in ("Mixsmith-Tutorial.mp4", "Mixsmith-Tutorial.json"):          # tutorial video with Mixi (python tutorial/make_tutorial.py)
    if os.path.exists(os.path.join("tutorial", f)): DATA += ["--add-data", "tutorial/%s;tutorial" % f]
LIGHT_EXCLUDES = ["torch", "torchaudio", "torchvision", "audio_separator", "onnxruntime", "onnx", "librosa", "numba", "llvmlite", "matplotlib",
                  "tkinter", "IPython", "pytest", "pandas", "sympy", "PIL"]
FULL_COLLECT = ["torch", "torchaudio", "audio_separator", "librosa", "onnxruntime", "onnx", "onnx2torch", "numba", "llvmlite", "julius", "ml_collections",
                "einops", "beartype", "rotary_embedding_torch", "diffq", "soundfile", "sounddevice", "scipy", "samplerate", "resampy", "pydub", "yaml", "pedalboard"]

def run(cmd):
    print(">", " ".join(cmd), flush=True); subprocess.run(cmd, check=True)

def light():
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile", "--windowed", "--name", NAME, "--icon", "logo.ico",
           *DATA, "--add-data", "profiles;profiles", "--collect-all", "soundfile", "--collect-all", "sounddevice", "--collect-all", "pedalboard",
           "--hidden-import", "pyloudnorm", "--hidden-import", "mix_core", "--distpath", "dist_light", "--workpath", "build_light"]
    for m in LIGHT_EXCLUDES: cmd += ["--exclude-module", m]
    run(cmd + ["mixsmith.py"]); shutil.copy(os.path.join("dist_light", NAME + ".exe"), NAME + ".exe")

def full():
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--onedir", "--windowed", "--name", NAME, "--icon", "logo.ico", *DATA,
           "--hidden-import", "pyloudnorm", "--hidden-import", "mix_core", "--exclude-module", "tkinter", "--exclude-module", "matplotlib", "--exclude-module", "IPython",
           "--distpath", "dist_full", "--workpath", "build_full"]
    for m in FULL_COLLECT: cmd += ["--collect-all", m]
    run(cmd + ["mixsmith.py"])
    iscc = os.path.join(os.environ["LOCALAPPDATA"], "Programs", "Inno Setup 6", "ISCC.exe")
    run([iscc, "/DAppVersion=" + VER, "setup_inno.iss"])

def setup():
    """Light version as onedir (starts faster than onefile) in an Inno Setup installer with Kieselwerk wizard pictures."""
    run([sys.executable, os.path.join("packaging", "windows", "version_info.py")])
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--onedir", "--windowed", "--name", NAME, "--icon", "logo.ico",
           *DATA, "--add-data", "profiles;profiles", "--collect-all", "soundfile", "--collect-all", "sounddevice", "--collect-all", "pedalboard",
           "--hidden-import", "pyloudnorm", "--hidden-import", "mix_core", "--distpath", "dist_setup", "--workpath", "build_setup",
           "--version-file", os.path.join("packaging", "windows", "version_info.txt")]
    for m in LIGHT_EXCLUDES: cmd += ["--exclude-module", m]
    run(cmd + ["mixsmith.py"])
    iscc = os.path.join(os.environ["LOCALAPPDATA"], "Programs", "Inno Setup 6", "ISCC.exe")
    run([iscc, "/DAppVersion=" + VER, os.path.join("packaging", "windows", "setup_windows.iss")])

def msi():
    run([sys.executable, "setup_cx.py", "bdist_msi"])

SOURCE = ["audio_core.py", "mix_core.py", "mixsmith_gui.py", "mixsmith.py", "build.py", "make_logo.py", "setup_cx.py", "setup_inno.iss", "requirements.txt",
          "README.md", "LICENSE", "LIZENZEN.md", "logo.ico", "logo.png", "logo_1024.png", "profiles", "packaging", ".github",
          "docs", "tutorial/capture_screens.py", "tutorial/make_tutorial.py", "tutorial/mascot.py", "tutorial/Mixsmith-Tutorial.json"]

def source():
    """Complete corresponding source for the GPLv3 (offered next to every download)."""
    os.makedirs("installer", exist_ok=True); out = os.path.join("installer", "%s-%s-Quelltext.zip" % (NAME, VER)); base = "%s-%s-Quelltext/" % (NAME, VER)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in SOURCE:
            paths = [item] if os.path.isfile(item) else [os.path.join(r, f) for r, _, fs in os.walk(item) for f in fs if "__pycache__" not in r]
            for p in sorted(paths): zf.write(p, base + p.replace(os.sep, "/"))
    print("Quelltext:", out)

if __name__ == "__main__":
    for t in sys.argv[1:] or ["light"]: {"light": light, "full": full, "msi": msi, "source": source, "setup": setup}[t]()
