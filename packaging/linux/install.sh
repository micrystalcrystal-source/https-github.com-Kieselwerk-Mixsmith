#!/usr/bin/env bash
# Mixsmith – Installation für Linux (Benutzerinstallation, kein root nötig)
#   ./install.sh          Mixing, Mastering + Spur-Angleich
#   ./install.sh --ki     zusätzlich KI-Stem-Trennung (PyTorch, ca. 3 GB)
set -euo pipefail
VER="1.0.0"
SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="${XDG_DATA_HOME:-$HOME/.local/share}/mixsmith-app"
BIN="$HOME/.local/bin"
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICONS="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/256x256/apps"
KI=0
for a in "$@"; do
  case "$a" in
    --ki|--ai) KI=1 ;;
    -h|--help) sed -n '2,4p' "$0"; exit 0 ;;
  esac
done

say()  { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!! \033[0m %s\n' "$*"; }
hint_packages() {
  if command -v apt-get >/dev/null; then echo "   sudo apt install python3 python3-venv python3-pip libportaudio2 libxcb-cursor0 ffmpeg"
  elif command -v dnf >/dev/null; then echo "   sudo dnf install python3 python3-pip portaudio xcb-util-cursor ffmpeg"
  elif command -v pacman >/dev/null; then echo "   sudo pacman -S python python-pip portaudio xcb-util-cursor ffmpeg"
  elif command -v zypper >/dev/null; then echo "   sudo zypper install python3 python3-pip portaudio libxcb-cursor0 ffmpeg"
  else echo "   Python ≥ 3.10 mit venv, PortAudio, xcb-cursor und ffmpeg über die Paketverwaltung installieren"; fi
}

say "Mixsmith $VER wird nach $DEST installiert"
command -v python3 >/dev/null || { warn "python3 fehlt. Bitte installieren:"; hint_packages; exit 1; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' || { warn "Python 3.10 oder neuer nötig (gefunden: $(python3 -V))."; exit 1; }
python3 -c 'import venv, ensurepip' 2>/dev/null || { warn "Das Python-Modul venv fehlt. Bitte installieren:"; hint_packages; exit 1; }
python3 -c 'import ctypes.util, sys; sys.exit(0 if ctypes.util.find_library("portaudio") else 1)' || { warn "PortAudio fehlt – ohne sie gibt es keine Vorschau-Wiedergabe. Empfohlen:"; hint_packages; }

mkdir -p "$DEST" "$BIN" "$APPS" "$ICONS"
cp -r "$SRC"/audio_core.py "$SRC"/mix_core.py "$SRC"/mixsmith_gui.py "$SRC"/mixsmith.py "$SRC"/requirements.txt "$SRC"/README.md "$SRC"/logo.png "$SRC"/logo.ico "$SRC"/profiles "$DEST"/
[ -d "$SRC/tutorial" ] && cp -r "$SRC/tutorial" "$DEST"/

say "Python-Umgebung anlegen"
[ -x "$DEST/venv/bin/python" ] || python3 -m venv "$DEST/venv"
"$DEST/venv/bin/python" -m pip install --upgrade pip >/dev/null
say "Pakete installieren (numpy, scipy, PySide6, …)"
"$DEST/venv/bin/python" -m pip install -r "$DEST/requirements.txt"

if [ "$KI" = 1 ]; then
  if command -v nvidia-smi >/dev/null && nvidia-smi >/dev/null 2>&1; then
    say "KI-Trennung mit NVIDIA-Unterstützung installieren (einige GB)"
    "$DEST/venv/bin/python" -m pip install "audio-separator[gpu]"
  else
    say "KI-Trennung für die CPU installieren"
    "$DEST/venv/bin/python" -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
    "$DEST/venv/bin/python" -m pip install "audio-separator[cpu]"
  fi
  command -v ffmpeg >/dev/null || { warn "ffmpeg fehlt – die KI-Trennung braucht es:"; hint_packages; }
fi

cat > "$BIN/mixsmith" <<EOF
#!/bin/sh
exec "$DEST/venv/bin/python" "$DEST/mixsmith.py" "\$@"
EOF
chmod +x "$BIN/mixsmith"
cp "$SRC/logo.png" "$ICONS/mixsmith.png"
cat > "$APPS/mixsmith.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Mixsmith
Comment=Mixing, Mastering, Spur-Angleich und KI-Stems
Exec=$BIN/mixsmith
Icon=mixsmith
Terminal=false
Categories=AudioVideo;Audio;
StartupWMClass=Mixsmith
EOF
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" >/dev/null 2>&1 || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q "${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor" >/dev/null 2>&1 || true

cat > "$DEST/uninstall.sh" <<EOF
#!/bin/sh
# Entfernt das Programm. Eigene Profile und Einstellungen in ~/.local/share/Mixsmith bleiben erhalten.
rm -f "$BIN/mixsmith" "$APPS/mixsmith.desktop" "$ICONS/mixsmith.png" "\$HOME/Desktop/mixsmith.desktop"
rm -rf "$DEST"
echo "Mixsmith entfernt."
EOF
chmod +x "$DEST/uninstall.sh"

say "Fertig. Start über das Anwendungsmenü (Mixsmith) oder mit:  mixsmith"
case ":$PATH:" in *":$BIN:"*) ;; *) warn "$BIN ist nicht im PATH – im Menü starten oder PATH ergänzen." ;; esac
[ "$KI" = 1 ] || echo "   KI-Stem-Trennung später nachrüsten:  ./install.sh --ki"
