# Änderungen

## 1.0.1 (Oktober 2026)

- Mixsmith steht unter der GNU GPLv3. `LICENSE` und `LIZENZEN.md` liegen jedem Paket bei, der Installer zeigt die Lizenz an, „Über“ nennt sie.
- Das Mastering-Profil „DistroKid-Referenz“ heißt jetzt „Laut und hell“. Ältere Einstellungen und Mix-Profile finden es weiterhin.
- Die Windows-Vollversion liefert nur noch das Demucs-Modell mit. BS-RoFormer, De-Reverb, De-Echo und DrumSep lädt Mixsmith beim ersten Einsatz aus den Quellen ihrer Autoren.
- `python build.py source` erzeugt die Quelltext-Zip für jeden Download.
- Tutorial-Video mit neuen Bildschirmen.

## 1.0.0 (September 2026)

Erste Version, Nachfolger des Mastering-Tools 2.0: Mixing nach Referenz, KI-Effektanalyse, Tutorial mit Mixi.

### Behobene Fehler aus dem Mastering-Tool 2.0

| Fehler | Auswirkung | Behebung |
|---|---|---|
| Vorschau direkt nach dem Wechsel des Titels | berechnete den **vorher** ausgewählten Titel und zeigte ihn als neuen an (Mastering und Spur-Angleich) | Vorschau erst, wenn der neue Titel geladen ist |
| Ausgabeordner = Eingabeordner mit `Song.flac` und `Song.wav` im selben Durchlauf | der Master von `Song.flac` **überschrieb die Quelldatei** `Song.wav`, bevor sie dran war | alle Quelldateien eines Durchlaufs sind geschützt |
| Programm während einer Trennung geschlossen | Trennungsprozess lief unsichtbar weiter und hielt Grafikspeicher/CPU belegt | wird beim Schließen beendet |
| zwei Trennungen laden dasselbe Modell gleichzeitig | beide schreiben in dieselbe Datei; ein abgebrochener Download blieb **dauerhaft** kaputt („Unsupported Model File“) | Sperrdatei je Modell; unvollständige Datei wird erkannt und neu geladen |
| Absturz des Trennungsprozesses | nur „ohne Ergebnis beendet (Code 1)“, Ursache unbekannt | letzte Fehlermeldung des Prozesses wird angezeigt |
| Start mit `--no-splash` (bzw. `-psn_…` älterer macOS-Versionen) | Programm startete nicht (Kommandozeilen-Fehler) | Oberflächen-Schalter werden erkannt |
| Mastering-Profil anlernen → Abbrechen | lief weiter und speicherte das Profil trotzdem | echter Abbruch |
| Spur-Angleich einer Mono-Spur mit Hall/Chorus | nur der linke Kanal wurde gespeichert | Mono-Summe beider Kanäle |
| Stem-Balance ohne passende GPU | BS-RoFormer lief auf der CPU (≈ 2,5× Songlänge) | automatische Wahl weicht auf Demucs aus |
| beschädigte Zwischenspeicher-Datei (z. B. volle Platte) | jeder spätere Lauf dieses Titels scheiterte | wird erkannt und neu erzeugt; Schreiben atomar |
| entfernter Titel | blieb geladen, Vorschau war weiter möglich | wird entladen |
| Spur-Angleich | kein Hinweis bei leerem Ausgabeordner; „Breite manuell“ auch in anderen Modi aktiv; Moduswechsel markierte die Vorschau nicht als veraltet | behoben |
| Seite „Stems“ und Stem-Balance | `nvidia-smi` lief bis zu 3× je Klick im Oberflächen-Thread (Ruckeln) | Abfrage zwischengespeichert |
| GitHub-Workflow | Windows/macOS-Build scheiterte (PNG-Icon braucht Pillow), `macos-13`-Runner abgeschaltet | Pillow ergänzt, `macos-15-intel` |
| Hilfe-Symbole (?) | Erklärung erschien erst nach ~0,7 s | sofort; alle anderen Tooltips nach 0,12 s |
