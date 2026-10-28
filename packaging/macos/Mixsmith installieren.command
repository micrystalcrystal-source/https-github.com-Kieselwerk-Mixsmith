#!/bin/bash
# Mixsmith – Installation für macOS (Doppelklick bzw. Rechtsklick → Öffnen)
# Legt ~/Applications/Mixsmith.app an; Programmdaten in ~/Library/Application Support/Mixsmith-App.
set -e
cd "$(dirname "$0")"
SRC="$(pwd)"
VER="1.0.0"
SUP="$HOME/Library/Application Support/Mixsmith-App"
APP="$HOME/Applications/Mixsmith.app"

say()  { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m!! \033[0m %s\n' "$*"; osascript -e "display alert \"Mixsmith\" message \"$*\"" >/dev/null 2>&1 || true; exit 1; }

PY=""
for c in /opt/homebrew/bin/python3 /usr/local/bin/python3 /Library/Frameworks/Python.framework/Versions/Current/bin/python3 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then PY="$c"; break; fi
done
[ -n "$PY" ] || fail "Python 3.10 oder neuer fehlt. Bitte von python.org installieren (oder: brew install python) und das Skript erneut öffnen."

KI=$(osascript -e 'button returned of (display dialog "KI-Stem-Trennung mitinstallieren?\n\nErmöglicht Mixing nach Referenzsongs, Rohmix-Zerlegung, Stems extrahieren, Stem-Balance und KI-Effektanalyse (ca. 2–3 GB Download; auf Apple Silicon mit Metal-Beschleunigung)." buttons {"Nein", "Ja"} default button "Ja" with title "Mixsmith '"$VER"'")' 2>/dev/null || echo "Nein")

say "Mixsmith $VER installieren (Python: $("$PY" -V))"
mkdir -p "$SUP"
cp -R "$SRC/app/"* "$SUP/"
[ -x "$SUP/venv/bin/python" ] || "$PY" -m venv "$SUP/venv"
"$SUP/venv/bin/python" -m pip install --upgrade pip >/dev/null
say "Pakete installieren (numpy, scipy, PySide6, …)"
"$SUP/venv/bin/python" -m pip install -r "$SUP/requirements.txt"
if [ "$KI" = "Ja" ]; then
  say "KI-Trennung installieren"
  "$SUP/venv/bin/python" -m pip install "audio-separator[cpu]"
  command -v ffmpeg >/dev/null 2>&1 || [ -x /opt/homebrew/bin/ffmpeg ] || [ -x /usr/local/bin/ffmpeg ] || \
    osascript -e 'display alert "ffmpeg fehlt" message "Die KI-Trennung braucht ffmpeg. Mit Homebrew:  brew install ffmpeg"' >/dev/null 2>&1 || true
fi

say "App anlegen: $APP"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$SRC/app/logo.icns" "$APP/Contents/Resources/AppIcon.icns"
cat > "$APP/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Mixsmith</string>
  <key>CFBundleDisplayName</key><string>Mixsmith</string>
  <key>CFBundleIdentifier</key><string>de.mastern.mixsmith</string>
  <key>CFBundleVersion</key><string>$VER</string>
  <key>CFBundleShortVersionString</key><string>$VER</string>
  <key>CFBundleExecutable</key><string>Mixsmith</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>LSMinimumSystemVersion</key><string>12.0</string>
  <key>NSHighResolutionCapable</key><true/>
</dict></plist>
EOF
cat > "$APP/Contents/MacOS/Mixsmith" <<EOF
#!/bin/bash
export PATH="/opt/homebrew/bin:/usr/local/bin:\$PATH"
exec "$SUP/venv/bin/python" "$SUP/mixsmith.py" "\$@"
EOF
chmod +x "$APP/Contents/MacOS/Mixsmith"
xattr -dr com.apple.quarantine "$APP" >/dev/null 2>&1 || true
cat > "$SUP/uninstall.command" <<EOF
#!/bin/bash
# Entfernt das Programm. Eigene Profile und Einstellungen (~/Library/Application Support/Mixsmith) bleiben erhalten.
rm -rf "$APP" "$SUP"
echo "Mixsmith entfernt."
EOF
chmod +x "$SUP/uninstall.command"

say "Fertig."
osascript -e 'display notification "Mixsmith liegt jetzt im Programme-Ordner." with title "Installation fertig"' >/dev/null 2>&1 || true
open -R "$APP"
