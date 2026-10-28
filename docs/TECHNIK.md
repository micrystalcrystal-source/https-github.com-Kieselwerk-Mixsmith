# Mixsmith – Technik

Wie Mixsmith misst, mischt und mastert, und wie man es selbst baut. Überblick und Download: [README](../README.md).

## Mixing – so funktioniert es

**1. Mix-Profil anlernen** (Mixing → Mix-Referenz → „…“ → *Mix-Profil aus Songs anlernen*): ein oder mehrere Songs wählen, deren Mix gefällt.
Die KI zerlegt jeden Song in Gesang, Drums, Bass, Gitarre, Piano/Keys und Andere. Für jede Rolle werden gemessen:

| Messgröße | Bedeutung |
|---|---|
| Pegel relativ zum Mix (LU) | z. B. Gesang −5,3 LU, Drums −4,5, Bass −7,2 – die Balance der Referenz |
| Langzeitspektrum | Klangfarbe der Rolle (1/3-Oktav-geglättet) |
| Crest-Faktor, Transienten | Dynamik und Anschlag |
| Stereobreite, Links/Rechts-Balance | Räumlichkeit |
| Hall, Delay *(optional)* | per KI-Effektanalyse, siehe unten |

Bei mehreren Songs zählt der Median. Rollen, die in einem Song nur als Trennungsrest vorkommen (mehr als 24 LU unter dem Mix), zählen nicht.
Das Profil speichert außerdem das Mastering der Referenz (Lautheit, Spektrum, Breite); auf Wunsch wird es zusätzlich als Mastering-Profil abgelegt.

**2. Quelle wählen**
- **Einzelspuren**: die Spuren eines Songs hineinziehen. Die Rolle erkennt Mixsmith am Dateinamen (Kick, Snare, OH → Drums; Vox, BGV → Gesang; Gtr → Gitarre; Keys, Rhodes → Piano/Keys; Bass, Sub, 808 → Bass …) und lässt sie sich je Spur ändern. Unterschiedliche Längen und Sample-Raten werden angeglichen.
- **Song / Rohmix**: fertige Stereo-Mixe. Die KI zerlegt sie (einmalig, danach zwischengespeichert) in dieselben Rollen plus „Rest“, sodass nichts verloren geht. Mehrere Songs werden nacheinander mit denselben Einstellungen gemischt.

**3. Einstellen und anhören**: „Von der Referenz übernehmen“ (Balance, Klang, Dynamik, Transienten, Stereobreite, Hall & Delay – je 0–100 %), Mischpult und Kanal-Regler. **Vorschau berechnen** → A (Rohmix) / B (Mix) vergleichen; Fader, Panorama, Stumm und Solo wirken sofort. Die Tabelle „Mix-Referenz“ zeigt je Rolle Ziel, Ist und Korrektur.

**4. Mix erstellen**: `<Song> - Mix.wav` (Spitzenpegel einstellbar, Standard −3 dBTP), optional `<Song> - Master.wav` (Mastering der Referenz oder ein Mastering-Profil + Plattform), optional die bearbeiteten Einzelspuren, dazu `Mix-Protokoll.csv`.

**Wie gemischt wird**
1. je Spur: Low-Cut, Tiefen (100 Hz), Präsenz (3 kHz), Höhen (10 kHz), Kompressor mit Aufholverstärkung, Breite, Hall
2. je Rolle: gemessen an der Summe ihrer Spuren, angewendet auf jede Spur einzeln (EQ, Kompressor- und Transienten-Gainkurven, Breite und Hall sind linear) – so bleibt jeder Kanal einzeln regelbar
3. Balance: Pegelverhältnisse der Rollen wie in der Referenz, begrenzt (Standard ±12 dB); die Fader verschieben relativ dazu
4. Summe → Spitzenpegel, optional Mastering-Kette

## KI-Effektanalyse

Die bisherige reine Signalanalyse fand bei effektreichem Material (Testfall: *TOOL – Forty Six & 2*) praktisch nichts. Mixsmith trennt deshalb zuerst die Effekte ab und misst dann:

1. **UVR De-Echo** trennt Echos ab, **MDX23C De-Reverb** den Hall vom trockenen Signal (analysiert wird der aktivste 40-s-Ausschnitt).
2. **Delay**: Zeit, Echo-Pegel und Feedback per Ausgleichsrechnung – auf der Wellenform (exakt bei sauberen Digital-Delays) und auf Hüllkurven je Frequenzband (robust bei gefilterten, gesättigten oder modulierten Echos). Zwei Plausibilitätsprüfungen verhindern, dass sich wiederholende Musik als Delay gilt: Gezählt wird nur, was die Verzögerung *zusätzlich* zum gleichzeitigen Signal erklärt, und ein echtes Echo folgt dem Original nur zeitlich *nach*. Das lokale **Tempo** des Ausschnitts dient als Vorwissen: Liegt ein Notenwert (1/16 … 1/2, punktiert, Triolen) fast gleichauf mit dem freien Optimum, wird er bevorzugt („Delay 570 ms (1/4 bei 105 BPM)“). Tempowechsel an anderen Stellen des Songs stören nicht.
3. **Hall**: Nachhallzeit aus den Abklingkurven des abgetrennten Halls nach Notenenden, Dämpfung aus seinem Höhenverlust, Anteil aus dem Energieverhältnis – übersetzt in die Einstellungen des programmeigenen Halls. Gibt es zu wenige Notenenden, sucht Mixsmith die Einstellung per Analyse durch Synthese (Raum, Dämpfung, Pre-Delay).
4. **Tremolo, Chorus/Flanger**: Hüllkurvenanalyse am trockenen Signal.

Prüfung mit bekannten Effekten: Hall (Raum, Dämpfung, Anteil, Pre-Delay) und Delay (Zeit, Pegel, Feedback, auch gefiltert) werden exakt wiedergefunden. Die Effektanalyse ist beim Anlernen abwählbar (spart etwa die Hälfte der Zeit); ohne KI-Modelle (leichte Version) schätzt Mixsmith die Effekte wie bisher aus dem Signal.

## Kommandozeile

```bash
python mixsmith.py --learn-mix ref1.wav ref2.wav --name "Mein Mix"
```
```bash
python mixsmith.py --mix-profile "Mein Mix" --tracks --name "Song" --master --out "C:\Ausgabe" kick.wav snare.wav bass.wav vox.wav
```
```bash
python mixsmith.py --mix-profile "Mein Mix" --master --preset stream --out "C:\Ausgabe" rohmix1.wav rohmix2.wav
```
Mix-Optionen: `--balance --tone --dynamics --transients --stereo --fx` (0..1), `--peak-db -3`, `--master [--master-profile NAME] [--preset stream|apple|loud|club|cd]`, `--save-tracks`, `--no-fx-analysis` (beim Anlernen), `--mix-profile -` (ohne Referenz).
Mastering, Spur-Angleich und Stems wie bisher: `--profile`, `--learn`, `--learn-track`, `--track-profile`, `--extract-stems`, `--model …` (siehe `python mixsmith.py --help`).

## Dateien

- Quelltext: `audio_core.py` (Messung, Mastering-Kette, Spur-Angleich, KI-Trennung, Effektanalyse), `mix_core.py` (Mix-Profile, Mischpult, Referenz-Mix), `mixsmith_gui.py` (Oberfläche), `mixsmith.py` (Start, Kommandozeile, Trennungs-Worker), `make_logo.py`, `build.py`.
- Benutzerdaten: `%APPDATA%\Mixsmith` (Windows), `~/.local/share/Mixsmith` (Linux), `~/Library/Application Support/Mixsmith` (macOS) – Mastering-, Instrument- und Mix-Profile (`mix_profiles`), Einstellungen, Zwischenspeicher, Modell-Downloads.

## Tutorial-Video

„Tutorial ansehen“ in der Seitenleiste (oder unter Einstellungen → Über) spielt ein zweieinhalbminütiges Video ab, in dem das Maskottchen **Mixi** die wichtigsten Funktionen zeigt – mit Kapiteln, Stimme und Untertiteln. Das Video wird per Code erzeugt und lässt sich nach Änderungen an der Oberfläche neu bauen:

```bash
python tutorial/capture_screens.py
```
```bash
python tutorial/make_tutorial.py
```
- `capture_screens.py` bedient Mixsmith selbst (eigener, leerer Datenordner) und nimmt die Bildschirme samt Position der Bedienelemente auf.
- `make_tutorial.py` erzeugt die Stimme und rendert das Video (1920×1080, 30 fps, H.264/AAC über ffmpeg): Kamerafahrten und Spotlight auf die erklärten Elemente, Mixi mit Lippenbewegung zur Stimme, Sprechblasen, Kapitel. Der Sprechertext steht oben in `SCRIPT`.
- Stimme: Microsoft-Neural-Stimme **Katja** über `edge-tts` (+6 % Tempo, +35 Hz Tonhöhe, direkt im Sprachmodell). Offline-Alternative: [Piper](https://github.com/OHF-Voice/piper1-gpl) mit Praats „Change Gender“ (`tutorial/voices/mixi_voice.py`), umschaltbar über `VOICE` in `make_tutorial.py`.
- Zum Bauen nötig: `pip install edge-tts PySide6-Addons` (für die Offline-Stimme zusätzlich `piper-tts praat-parselmouth`).

## Selbst bauen

```bash
pip install -r requirements.txt
```
```bash
python build.py light full
```
`light` → `Mixsmith.exe` (ohne KI), `full` → Setup mit KI (PyInstaller + Inno Setup 6, 15–25 min), `msi` → MSI ohne KI. Linux/macOS: `python packaging/make_unix_packages.py`.

## Grenzen

- Mixsmith gleicht Messgrößen an, es hört nicht. Bei sehr unterschiedlichem Material die Übernahme-Regler auf 50–70 % stellen und mit A/B prüfen.
- Rohmix-Zerlegung hat Trennungsreste; große Pegeländerungen einzelner Rollen (> 6 dB) machen sie hörbar. Einzelspuren liefern das sauberste Ergebnis.
- Effekte werden in die Einstellungen des programmeigenen Halls/Delays übersetzt – ein Plate, Federhall oder Tape-Echo wird angenähert, nicht kopiert. Chorus/Flanger/Tremolo erkennt Mixsmith nur bei deutlicher Ausprägung.

## Quellen

- MVSEP, BS Roformer SW: https://mvsep.com/algorithms/77
- python-audio-separator (Modelle MDX23C De-Reverb von aufr33 & jarredou, UVR De-Echo von FoxJoy): https://github.com/nomadkaraoke/python-audio-separator
- EBU Tech 3342 (LRA), ITU-R BS.1770 (Lautheit)
