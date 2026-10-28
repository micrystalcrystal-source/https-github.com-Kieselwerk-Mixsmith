# -*- coding: utf-8 -*-
"""Mixsmith – grafische Oberfläche (PySide6): Mixing, Mastering, Spur-Angleich, Stems, Einstellungen."""
import os, sys, time, math, json, threading, traceback
import numpy as np

from PySide6.QtCore import Qt, QObject, Signal, QTimer, QRectF, QPointF, QUrl, QEvent
from PySide6.QtGui import (QColor, QPainter, QPen, QBrush, QFont, QPainterPath, QLinearGradient, QPixmap, QIcon,
                           QDesktopServices, QFontDatabase, QGuiApplication, QPalette)
from PySide6.QtWidgets import (QApplication, QWidget, QMainWindow, QFrame, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
                               QGridLayout, QStackedWidget, QSlider, QDoubleSpinBox, QComboBox, QCheckBox, QLineEdit, QFileDialog,
                               QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QProgressBar, QPlainTextEdit,
                               QScrollArea, QButtonGroup, QMessageBox, QDialog, QSplashScreen, QMenu, QSizePolicy,
                               QRadioButton, QToolTip, QProxyStyle, QStyle)

import audio_core as mc
import mix_core as mx

try:
    import sounddevice as sd
except Exception:
    sd = None
try:                                  # tutorial video player (PySide6-Addons); without it the video opens in the system player
    from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
    from PySide6.QtMultimediaWidgets import QVideoWidget
except Exception:
    QMediaPlayer = None

# ============================================================== design tokens
C = dict(bg="#0d1117", side="#090c11", card="#141a22", card2="#1a212b", field="#0f141b", border="#242d39", border2="#2f3a48",
         text="#e7ebf1", muted="#8d98a8", faint="#5b6676", acc="#4fc8d6", acc_h="#72d9e4", acc_d="#2a8f9b", amber="#f5b23a",
         violet="#8b7cf6", ok="#5ad28b", err="#ff6b6b", warn="#f5b23a")
ICON_FONT = "Segoe Fluent Icons"
I = dict(mix="", master="", track="", stems="", settings="", add="", folder="", delete="",
         play="", pause="", stop="", open="", info="", refresh="", more="", check="",
         cancel="", warn="", learn="", preview="", gpu="", help="", export="")

HELP = {
 "profil": "Das Referenzprofil beschreibt den Zielklang: Lautheit, Stereobreite und das Langzeitspektrum, gemittelt aus Referenztiteln.\n\n"
           "„Laut und hell“ wurde aus fünf lauten Referenz-Mastern gelernt (laut, hell, breit). „Streaming-Standard“ ist neutraler (−14 LUFS, −1 dBTP).\n"
           "Über „…“ lernen Sie ein eigenes Profil aus 5–10 Titeln, die Ihnen klanglich gefallen.",
 "preset": "Zielplattform. Setzt Lautheit, Peak-Modus und Obergrenze passend; der Klang (Spektrum) kommt weiter aus dem Profil.\n\n"
           "Spotify, YouTube und Tidal regeln auf etwa −14 LUFS, Apple Music auf −16. Lautere Master werden dort leiser gedreht – sie klingen dann nicht lauter, nur dichter.\n"
           "„Benutzerdefiniert“ gibt die Felder im Bereich Dynamik frei.",
 "strength": "Wie stark das Spektrum an das Profil angeglichen wird. 100 % = Klangfarbe wird vollständig auf das Profil gezogen, 50 % = halber Weg, 0 = Klangfarbe bleibt (nur Lautheit, Breite, Limiter).",
 "warm": "Zusätzlicher Tiefen-Shelf bei 100 Hz nach dem Angleich. Plus = wärmer, mehr Fundament; minus = schlanker.",
 "air": "Zusätzlicher Höhen-Shelf bei 10 kHz nach dem Angleich. Plus = mehr „Luft“ und Offenheit; minus = weicher. Bei Zischeln eher minus.",
 "width": "Stereobreite oberhalb 200 Hz.\n• Wie Profil: Seitenanteil wird an das Profil angeglichen, höchstens um den eingestellten Betrag.\n• Manuell: fester Wert in dB (plus = breiter).\n• Aus: unverändert.\nZu breit kann in Mono hohl klingen.",
 "clip": "Soft-Clipper vor dem Limiter (4-fach Oversampling). Er rundet die höchsten Spitzen um bis zu diesen Betrag ab, damit der Limiter weniger arbeiten muss – das klingt bei gleicher Lautheit offener und pumpt weniger.\n"
         "So arbeiten viele moderne Master (Clipper + Limiter). 0,5–2 dB sind unauffällig; mehr klingt bei Drums schnell kratzig. 0 = aus.",
 "glue": "Sanfte Bus-Kompression („Glue“, 1,4:1 bis 2,5:1, 30 ms Attack). Verdichtet laute Passagen um 1–3 dB, der Mix wirkt geschlossener. 0 = aus. Für dynamische Akustik-Titel eher aus lassen.",
 "release": "Wie schnell der Limiter nach einer Spitze wieder aufmacht. Kurz (50 ms) = lauter und dichter, aber Verzerrungsgefahr im Bass; lang (300 ms) = weicher und transparenter.",
 "peak": "• Sample-Peak: begrenzt nur die Abtastwerte (−0,1 dBFS). Dazwischen entstehen Spitzen bis etwa +1,5 dBTP, wie bei vielen Online-Mastering-Diensten. Lauter, kann aber bei MP3/AAC leicht verzerren.\n"
         "• True Peak: 4-fach Oversampling, Standard −1,0 dBTP. Sicher für Spotify, Apple Music & Co.",
 "ceiling": "Obergrenze des Limiters in dB (dBFS bzw. dBTP). Tiefer = mehr Sicherheitsabstand, etwas leiser.",
 "lufs": "Ziel-Lautheit, integriert nach ITU-R BS.1770. Laute Pop- und Rock-Master liegen bei etwa −11 LUFS, Streaming normalisiert auf −14.",
 "stems": "Stem-Balance: Die KI zerlegt den fertigen Mix in Gesang, Drums, Bass und den Rest. Hier verschieben Sie deren Lautstärke, bevor gemastert wird – z. B. Gesang +1 dB, wenn er im Mix untergeht.\n\n"
          "Verlustfrei: Es wird nur die Differenz addiert; bei 0 dB bleibt der Mix exakt erhalten. Kleine Werte (±1–3 dB) klingen am natürlichsten.\n"
          "Die Trennung dauert beim ersten Mal ein wenig und wird danach zwischengespeichert.",
 "maxeq": "Maximale EQ-Korrektur pro Frequenzband. Kleiner = vorsichtiger Angleich.",
 "eqrange": "Frequenzbereich des Angleichs; außerhalb bleibt der Klang unverändert (weicher Übergang über eine Terz).",
 "presence": "Schutz für 2–8 kHz, wo Stimmen und Zischlaute liegen. Anhebungen bis „voll“ werden ganz übernommen, darüber nur zur Hälfte und nie über den Deckel.",
 "deharsh": "Dynamische Absenkung 3–7 kHz, die nur bei lauten Stimmspitzen greift (wie ein De-Esser). 0 = aus.",
 "bassmono": "Unterhalb dieser Frequenz wird der Bass mono (Club-, Handy- und Vinyl-tauglich). 0 = aus.",
 "declip": "Erkennt hart abgeschnittene Wellenberge (digitales Clipping) und rekonstruiert sie. Greift nur bei mehr als 20 solcher Stellen.",
 "bits": "24 Bit für Streaming und Archiv, 16 Bit mit Dither für CD.",
 "preview": "Berechnet den Master des ausgewählten Titels mit den aktuellen Einstellungen, ohne etwas zu speichern. Danach mit A/B zwischen Original und Master umschalten.\n"
            "„Lautheit angleichen“ spielt beide gleich laut ab – so hören Sie den Klang und nicht nur „lauter“.",
 "t_profile": "Ein Instrument-Profil beschreibt den Klang eines Instruments aus Referenzmaterial: Spektrum, Lautheit, Dynamik (Crest-Faktor), Transienten, Stereobreite und erkannte Effekte.\n"
              "Mit dem Profil gleichen Sie rohe Spuren desselben Instruments an diesen Klang an.",
 "t_strength": "Wie stark das Spektrum der Spur an das Profil angeglichen wird. Bei sehr unterschiedlichen Aufnahmen (clean vs. verzerrt) eher 50–70 %.",
 "t_dyn": "Komprimiert die Spur, bis ihr Crest-Faktor (Spitze zu Durchschnitt) dem Profil entspricht. Pausen zählen nicht mit. Es wird nur verdichtet, nie aufgeweitet.",
 "t_trans": "Macht Anschläge so knackig oder weich wie im Profil (max. +6/−4 dB).",
 "t_sat": "Obertöne und leichte Verdichtung wie Band oder Röhre. Gitarre, Bass, Gesang oft 10–30 %, Drums vorsichtig.",
 "t_width": "Stereobreite der Spur (nur bei Stereo-Spuren): wie Profil, manuell oder aus. Mono-Spuren bleiben mono.",
 "t_lufs": "Ziel-Lautheit der Spur. Für den Mix sind etwa −18 LUFS praktisch; die Klangfarbe ändert sich dadurch nicht.",
 "t_fx": "Beim Anlernen trennt eine KI zuerst Echo und Hall vom trockenen Signal (De-Echo- und De-Reverb-Modell). Delay-Zeit, Echo-Pegel und Feedback werden "
         "dann per Ausgleichsrechnung bestimmt, Raumgröße, Dämpfung, Pre-Delay und Hallanteil per Analyse durch Synthese: Der programmeigene Hall wird so lange "
         "verstellt, bis er dem abgetrennten Hall gleicht. Tremolo und Chorus/Flanger werden am trockenen Signal gesucht (nur bei deutlicher Ausprägung).\n"
         "Ohne KI-Modelle (leichte Version) schätzt das Programm die Effekte aus dem Signal. Erkannte Werte füllen die Felder vor; alles ist von Hand einstellbar. "
         "Stärke 0 = aus, über 100 % übertreibt.",
 "model": "Welche KI die Spuren trennt.\n• BS-RoFormer SW: aktuell eines der besten frei verfügbaren 6-Spur-Modelle (Gitarre ≈ 9 dB SDR, Bass ≈ 14,6 dB). Braucht 1,5–2,5 GB Grafikspeicher, auf der CPU langsam.\n"
          "• Demucs 6s: schnell, wenig Speicher, auch auf der CPU brauchbar; Gitarre/Piano schwächer.\n• Demucs ft: 4 Spuren, sehr sauberer Bass und Drums.\n"
          "• Gesang/Instrumental: Spezialmodell für Karaoke und Acapella.\n• DrumSep: zerlegt eine Drum-Spur in Kick, Snare, Toms, HiHat, Ride und Crash.\n\n"
          "„Automatisch“ wählt nach freiem Grafikspeicher. Fehlende Modelle lädt das Programm beim ersten Einsatz einmalig herunter.",
 "m_source": "• Einzelspuren: die Spuren eines Songs (z. B. Kick, Snare, Bass, Gitarre, Gesang) – jede Datei wird ein Kanal. Unterschiedliche Längen und Sample-Raten werden angeglichen.\n"
             "• Song / Rohmix: fertige Stereo-Mixe. Die KI zerlegt jeden Song in Gesang, Drums, Bass, Gitarre, Piano/Keys, Andere und Rest und mischt ihn neu. Mehrere Songs werden nacheinander mit denselben Einstellungen gemischt.",
 "m_mixer": "Ein Kanal je Spur. Fader (−30 … +12 dB), Panorama, Stumm (M) und Solo (S) wirken sofort – auch während der Vorschau läuft. Doppelklick setzt Fader/Panorama zurück.\n"
            "Die Fader verschieben die Lautstärke relativ zur Referenz-Balance: 0 dB = so laut wie in der Referenz, +2 dB = 2 dB lauter.",
 "m_preview": "Berechnet den Mix mit den aktuellen Einstellungen (nichts wird gespeichert). A = Rohmix (Spuren unverändert bzw. Original-Song), B = Mix. "
              "Das Spektrum zeigt die ausgewählte Rolle (Referenz, vorher, gemischt) – ohne ausgewählten Kanal die Summe.",
 "m_profile": "Ein Mix-Profil beschreibt, wie ein Referenzsong gemischt ist: Für jede Rolle (Gesang, Drums, Bass, Gitarre, Piano/Keys, Andere) Pegel relativ zum Mix, Spektrum, Dynamik, Transienten, "
              "Stereobreite und – optional – Hall und Delay. Gelernt aus einem oder mehreren Songs per KI-Trennung; bei mehreren Songs zählt der Median.\n"
              "Das Profil enthält auch das Mastering des Referenzsongs (Lautheit, Spektrum, Breite) – es lässt sich unter „Summe & Mastering“ direkt übernehmen.",
 "m_take": "Wie stark die Referenz übernommen wird. 100 % = volle Angleichung, 0 = aus. Gemessen wird je Rolle an der Summe ihrer Spuren; angewendet wird auf jede Spur einzeln, deshalb bleiben alle Kanäle getrennt regelbar.",
 "m_balance": "Lautstärkeverhältnisse der Rollen wie in der Referenz (z. B. Gesang 5 LU unter dem Mix, Bass 7 LU). Rollen, die in der Referenz fehlen oder im Song nur als Trennungsrest vorkommen, bleiben unverändert.",
 "m_tone": "Klangfarbe jeder Rolle in Richtung der Referenz (linearphasiger EQ, begrenzt durch „max. EQ“).",
 "m_dyn": "Verdichtet jede Rolle, bis ihr Crest-Faktor (Spitze zu Durchschnitt) dem der Referenz entspricht. Es wird nur komprimiert, nie aufgeweitet.",
 "m_trans": "Anschläge so knackig oder weich wie in der Referenz (Transienten-Designer, max. +6/−4 dB).",
 "m_width": "Stereobreite jeder Rolle oberhalb 200 Hz wie in der Referenz (max. ±6 dB).",
 "m_fx": "Hall und Delay der Referenz (per KI-Effektanalyse gelernt) auf die Rollen legen. Für trockene Einzelspuren gedacht; ein Rohmix hat seine Effekte meist schon. 0 = aus.",
 "m_maxgain": "Größte Pegelkorrektur, die die Balance-Übernahme je Rolle vornehmen darf.",
 "m_channel": "Klangregler des ausgewählten Kanals: Low-Cut (Hochpass), Tiefen-Shelf 100 Hz, Präsenz-Glocke 3 kHz, Höhen-Shelf 10 kHz, Kompressor (mit automatischer Aufholverstärkung), "
              "Stereobreite und Hall. Sie wirken vor der Referenz-Angleichung. Im Rohmix-Modus gelten sie für alle Songs.",
 "m_role": "Welche Rolle der Referenz für diese Spur gilt. Wird aus dem Dateinamen erkannt (Kick, Snare, OH → Drums, Vox, BGV → Gesang, Gtr → Gitarre, Keys, Rhodes → Piano/Keys …).",
 "m_lowcut": "Hochpass gegen Rumpeln und Tiefenmatsch. Gesang 80–120 Hz, Gitarren 80–100 Hz, Overheads 150–300 Hz, Bass und Kick aus (0).",
 "m_comp": "Kanal-Kompressor 1,5:1 bis 6:1 mit Aufholverstärkung (gleiche Lautheit, weniger Dynamik).",
 "m_chwidth": "Stereobreite des Kanals oberhalb 200 Hz (nur Stereo-Spuren).",
 "m_reverb": "Hall-Anteil dieses Kanals (mittlerer Raum, 15 ms Pre-Delay).",
 "m_peak": "Spitzenpegel des ungemasterten Mixes (True Peak). −3 bis −6 dBTP lassen dem Mastering Luft.",
 "m_master": "Mastert den fertigen Mix gleich mit: mit dem Mastering der Mix-Referenz oder einem Mastering-Profil und einer Plattform-Voreinstellung. Es entstehen „<Song> - Mix.wav“ und „<Song> - Master.wav“.",
 "vram": "Grafikspeicher, den die Trennung höchstens belegen darf – damit andere Programme (Spiele, DAW, weitere KI) weiterlaufen.\n"
         "Das Programm stuft selbst herunter: fp16 → kleinere Blöcke → kleineres Modell → CPU. Bei zu wenig Speicher wird automatisch die nächste Stufe versucht.",
}

import tempfile
ASSETS = os.path.join(tempfile.gettempdir(), "mixsmith-ui")
def _assets():
    os.makedirs(ASSETS, exist_ok=True)
    svgs = {"arrow.svg": '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="6" viewBox="0 0 10 6"><path d="M1 1l4 4 4-4" fill="none" stroke="%s" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>' % C["muted"],
            "check.svg": '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16"><path d="M3.5 8.3l3 3 6-6.6" fill="none" stroke="#061216" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
            "dot.svg": '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16"><circle cx="8" cy="8" r="7" fill="none" stroke="%s" stroke-width="1.4"/><circle cx="8" cy="8" r="4" fill="%s"/></svg>' % (C["acc"], C["acc"]),
            "ring.svg": '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16"><circle cx="8" cy="8" r="7" fill="none" stroke="%s" stroke-width="1.4"/></svg>' % C["border2"]}
    for n, t in svgs.items():
        with open(os.path.join(ASSETS, n), "w", encoding="utf-8") as fh: fh.write(t)
    return ASSETS.replace("\\", "/")
C["assets"] = _assets()
WIN, MAC = sys.platform == "win32", sys.platform == "darwin"
C["uifont"] = "font-family: 'Segoe UI Variable Text', 'Segoe UI';" if WIN else ""
C["mono"] = "font-family: 'Cascadia Mono', Consolas;" if WIN else ("font-family: Menlo;" if MAC else "font-family: 'DejaVu Sans Mono', monospace;")
C["basept"] = "13" if MAC else "10"
USE_ICON_FONT = True
FALLBACK_ICONS = dict(mix="☷", master="≋", track="♪", stems="☰", settings="⚙", add="+", folder="▤", delete="✕", play="▶", pause="❚❚", stop="■",
                      open="↗", info="ⓘ", refresh="↻", more="…", check="✓", cancel="✕", warn="⚠", learn="✚", preview="◉", gpu="▣", help="?", export="↗")

QSS = """
* {{ {uifont} font-size: {basept}pt; color: {text}; }}
QMainWindow, #content {{ background: {bg}; }}
QToolTip {{ background: #0a0e13; color: {text}; border: 1px solid {border2}; padding: 8px 10px; border-radius: 6px; font-size: 9pt; }}
#sidebar {{ background: {side}; border-right: 1px solid {border}; }}
#navBtn {{ background: transparent; border: none; border-radius: 8px; padding: 10px 12px; text-align: left; color: {muted}; font-size: 10.5pt; }}
#navBtn:hover {{ background: {card}; color: {text}; }}
#navBtn:checked {{ background: {card2}; color: {text}; }}
#card {{ background: {card}; border: 1px solid {border}; border-radius: 12px; }}
#cardTitle {{ font-size: 10.5pt; font-weight: 600; color: {text}; }}
#pageTitle {{ font-size: 20pt; font-weight: 600; }}
#pageSub, #muted {{ color: {muted}; }}
#faint {{ color: {faint}; font-size: 9pt; }}
#value {{ color: {acc}; {mono} }}
QPushButton {{ background: {card2}; border: 1px solid {border2}; border-radius: 8px; padding: 7px 14px; }}
QPushButton:hover {{ background: #232b37; border-color: #3a4757; }}
QPushButton:pressed {{ background: #1a2029; }}
QPushButton:disabled {{ color: {faint}; background: {card}; border-color: {border}; }}
QPushButton#primary {{ background: {acc}; color: #061216; border: none; font-weight: 600; padding: 9px 20px; }}
QPushButton#primary:hover {{ background: {acc_h}; }}
QPushButton#primary:disabled {{ background: #22414a; color: #6c8a91; }}
QPushButton#danger {{ background: #3a1d22; border-color: #5a2a31; color: #ffb3b3; }}
QPushButton#ghost {{ background: transparent; border: none; color: {muted}; padding: 4px 8px; }}
QPushButton#ghost:hover {{ color: {text}; background: {card2}; }}
QPushButton#seg {{ background: {field}; border: 1px solid {border}; border-radius: 0; padding: 5px 12px; color: {muted}; }}
QPushButton#seg:checked {{ background: #1c3940; border-color: {acc_d}; color: {acc_h}; }}
QPushButton#segL {{ background: {field}; border: 1px solid {border}; border-top-left-radius: 7px; border-bottom-left-radius: 7px; border-top-right-radius: 0; border-bottom-right-radius: 0; padding: 5px 12px; color: {muted}; }}
QPushButton#segL:checked {{ background: #1c3940; border-color: {acc_d}; color: {acc_h}; }}
QPushButton#segR {{ background: {field}; border: 1px solid {border}; border-top-right-radius: 7px; border-bottom-right-radius: 7px; border-top-left-radius: 0; border-bottom-left-radius: 0; padding: 5px 12px; color: {muted}; }}
QPushButton#segR:checked {{ background: #1c3940; border-color: {acc_d}; color: {acc_h}; }}
QLineEdit, QDoubleSpinBox, QComboBox {{ background: {field}; border: 1px solid {border}; border-radius: 7px; padding: 5px 8px; selection-background-color: {acc_d}; }}
QLineEdit:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border-color: {acc_d}; }}
QLineEdit:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {{ color: {faint}; }}
QDoubleSpinBox {{ padding-right: 4px; }}
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ width: 0; border: none; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow {{ image: url({assets}/arrow.svg); width: 10px; height: 6px; margin-right: 8px; }}
QComboBox QAbstractItemView {{ background: {card2}; border: 1px solid {border2}; selection-background-color: #23434b; outline: 0; padding: 4px; }}
QSlider::groove:horizontal {{ height: 4px; background: {border}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {acc_d}; border-radius: 2px; }}
QSlider::handle:horizontal {{ width: 14px; height: 14px; margin: -6px 0; border-radius: 7px; background: {text}; border: 2px solid {acc}; }}
QSlider::handle:horizontal:hover {{ background: #ffffff; border-color: {acc_h}; }}
QSlider:disabled::sub-page:horizontal {{ background: {border2}; }}
QSlider::handle:horizontal:disabled {{ border-color: {border2}; background: {muted}; }}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px; border: 1px solid {border2}; background: {field}; }}
QCheckBox::indicator:checked {{ background: {acc}; border-color: {acc}; image: url({assets}/check.svg); }}
QRadioButton {{ spacing: 8px; }}
QRadioButton::indicator {{ width: 16px; height: 16px; image: url({assets}/ring.svg); }}
QRadioButton::indicator:checked {{ image: url({assets}/dot.svg); }}
QProgressBar {{ background: {field}; border: none; border-radius: 3px; height: 6px; text-align: center; font-size: 1px; color: transparent; }}
QProgressBar::chunk {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {acc}, stop:1 {violet}); border-radius: 3px; }}
QTableWidget, QListWidget {{ background: transparent; border: none; gridline-color: transparent; outline: 0; }}
QTableWidget::item, QListWidget::item {{ padding: 4px 6px; border-bottom: 1px solid {border}; }}
QTableWidget::item:selected, QListWidget::item:selected {{ background: #1b2d35; color: {text}; }}
QHeaderView {{ background: transparent; border: none; }}
QHeaderView::section {{ background: transparent; color: {faint}; border: none; border-bottom: 1px solid {border}; padding: 4px 6px; font-size: 9pt; text-align: left; }}
QPlainTextEdit {{ background: {field}; border: 1px solid {border}; border-radius: 8px; {mono} font-size: 9pt; color: #b9c3d1; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {border2}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #465466; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar:horizontal {{ height: 0; }}
QSlider::groove:vertical {{ width: 4px; background: {border}; border-radius: 2px; }}
QSlider::add-page:vertical {{ background: {acc_d}; border-radius: 2px; }}
QSlider::sub-page:vertical {{ background: {border}; border-radius: 2px; }}
QSlider::handle:vertical {{ height: 12px; width: 26px; margin: 0 -11px; border-radius: 4px; background: {text}; border: 2px solid {acc}; }}
QSlider::handle:vertical:hover {{ background: #ffffff; border-color: {acc_h}; }}
QPushButton#chipM, QPushButton#chipS {{ background: {field}; border: 1px solid {border2}; border-radius: 6px; padding: 0; font-weight: 600; color: {muted}; }}
QPushButton#chipM:checked {{ background: #4a2a1a; border-color: {amber}; color: {amber}; }}
QPushButton#chipS:checked {{ background: #1c3940; border-color: {acc}; color: {acc_h}; }}
QMenu {{ background: {card2}; border: 1px solid {border2}; padding: 4px; border-radius: 8px; }}
QMenu::item {{ padding: 6px 18px; border-radius: 5px; }}
QMenu::item:selected {{ background: #23434b; }}
QDialog {{ background: {bg}; }}
QMessageBox {{ background: {card}; }}
""".format(**C)

# ============================================================== helpers
def icon_css(size=12, color=None):
    if not USE_ICON_FONT: return "font-size:%spt;%s" % (size, ("color:%s;" % color) if color else "")
    fam = ICON_FONT if ICON_FONT in QFontDatabase.families() else "Segoe MDL2 Assets"
    return "font-family:'%s';font-size:%spt;%s" % (fam, size, ("color:%s;" % color) if color else "")

def icon_font(size=12):
    if not USE_ICON_FONT: f = QFont(); f.setPointSizeF(size); return f
    f = QFont(ICON_FONT if ICON_FONT in QFontDatabase.families() else "Segoe MDL2 Assets"); f.setPointSizeF(size); return f

def glyph_label(ch, size=12, color=None):
    l = QLabel(ch); l.setStyleSheet(icon_css(size, color)); return l

def btn(text, glyph=None, kind=None, tip=None, slot=None):
    b = QPushButton(("%s  %s" % (glyph, text)) if glyph and text else (glyph or text))
    if glyph:   # glyph in icon font, text in UI font: use rich layout
        b.setText("")
        lay = QHBoxLayout(b); lay.setContentsMargins(12, 0, 12, 0); lay.setSpacing(8)
        g = QLabel(glyph); g.setStyleSheet(icon_css(10.5)); g.setAlignment(Qt.AlignCenter); g.setAttribute(Qt.WA_TransparentForMouseEvents); lay.addWidget(g)
        if text:
            t = QLabel(text); t.setAttribute(Qt.WA_TransparentForMouseEvents); lay.addWidget(t)
            if kind == "primary": t.setStyleSheet("color:#061216;font-weight:600;"); g.setStyleSheet(icon_css(10.5, "#061216"))
        lay.insertStretch(0, 1); lay.addStretch(1)
        b._labels = [g] + ([t] if text else [])
        fm = b.fontMetrics(); b.setMinimumHeight(34)
        if text: b.setMinimumWidth(fm.horizontalAdvance(text) + 70)
        else: b.setFixedWidth(40); lay.setContentsMargins(0, 0, 0, 0); g.setAlignment(Qt.AlignCenter)
    if kind: b.setObjectName(kind)
    if tip: b.setToolTip(tip)
    if slot: b.clicked.connect(slot)
    b.setCursor(Qt.PointingHandCursor)
    return b

def set_btn_text(b, text):
    if getattr(b, "_labels", None) and len(b._labels) > 1:
        b._labels[1].setText(text); b.setMinimumWidth(b.fontMetrics().horizontalAdvance(text) + 76)
    else: b.setText(text)

class HelpDot(QLabel):
    """(?) with an explanation that opens as soon as the mouse is over it (Qt's own tooltip waits ~0.7 s)."""
    def __init__(self, key_or_text):
        super().__init__("?"); self.setFixedSize(18, 18); self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("QLabel{border:1px solid %s;border-radius:9px;color:%s;font-size:8pt;font-weight:600;} QLabel:hover{border-color:%s;color:%s;}" % (C["border2"], C["muted"], C["amber"], C["amber"]))
        self.tip = "<div style='max-width:420px'>%s</div>" % HELP.get(key_or_text, key_or_text).replace("\n", "<br>"); self.setCursor(Qt.WhatsThisCursor)
    def enterEvent(self, e):
        QToolTip.showText(self.mapToGlobal(self.rect().bottomLeft()), self.tip, self); super().enterEvent(e)
    def leaveEvent(self, e):
        QToolTip.hideText(); super().leaveEvent(e)

class FastTips(QProxyStyle):
    """All other tooltips appear after 120 ms instead of Qt's default delay."""
    def styleHint(self, hint, opt=None, widget=None, ret=None):
        if hint == QStyle.SH_ToolTip_WakeUpDelay: return 120
        if hint == QStyle.SH_ToolTip_FallAsleepDelay: return 2000
        return super().styleHint(hint, opt, widget, ret)

class Card(QFrame):
    def __init__(self, title=None, help_key=None, collapsible=False, collapsed=False, right=None):
        super().__init__(); self.setObjectName("card")
        self.v = QVBoxLayout(self); self.v.setContentsMargins(16, 14, 16, 16); self.v.setSpacing(10)
        self.body = QWidget(); self.body.setStyleSheet("background:transparent;"); self.bl = QVBoxLayout(self.body); self.bl.setContentsMargins(0, 0, 0, 0); self.bl.setSpacing(10)
        if title:
            h = QHBoxLayout(); h.setSpacing(8)
            if collapsible:
                self.arrow = QPushButton("▸" if collapsed else "▾"); self.arrow.setObjectName("ghost"); self.arrow.setFixedWidth(26); self.arrow.clicked.connect(self.toggle); h.addWidget(self.arrow)
            t = QLabel(title); t.setObjectName("cardTitle"); h.addWidget(t)
            if collapsible: t.mousePressEvent = lambda e: self.toggle()
            if help_key: h.addWidget(HelpDot(help_key))
            h.addStretch(1)
            if right is not None: h.addWidget(right)
            self.v.addLayout(h)
        self.v.addWidget(self.body)
        if collapsible and collapsed: self.body.hide()
    def toggle(self):
        vis = not self.body.isVisible(); self.body.setVisible(vis); self.arrow.setText("▾" if vis else "▸")
    def add(self, w):
        (self.bl.addLayout if isinstance(w, (QHBoxLayout, QVBoxLayout, QGridLayout)) else self.bl.addWidget)(w); return w

class SliderRow(QWidget):
    """Label · slider · editable value · (?)  –  double-click the slider to reset."""
    changed = Signal(float)
    def __init__(self, label, lo, hi, default, step=0.1, unit="", help_key=None, decimals=1, scale=1.0, signed=False):
        super().__init__(); self.lo, self.hi, self.default, self.step, self.scale = lo, hi, default, step, scale
        g = QGridLayout(self); g.setContentsMargins(0, 0, 0, 0); g.setHorizontalSpacing(10)
        self.lab = QLabel(label); self.lab.setFixedWidth(122); g.addWidget(self.lab, 0, 0)
        self.sl = QSlider(Qt.Horizontal); self.sl.setRange(0, int(round((hi-lo)/step))); self.sl.setCursor(Qt.PointingHandCursor); g.addWidget(self.sl, 0, 1)
        self.sp = QDoubleSpinBox(); self.sp.setRange(lo*scale, hi*scale); self.sp.setDecimals(decimals); self.sp.setSingleStep(step*scale)
        self.sp.setSuffix(unit); self.sp.setFixedWidth(80); self.sp.setAlignment(Qt.AlignRight); self.sp.setButtonSymbols(QDoubleSpinBox.NoButtons)
        if signed: self.sp.setPrefix("")
        g.addWidget(self.sp, 0, 2)
        if help_key: g.addWidget(HelpDot(help_key), 0, 3)
        else: sp_ = QWidget(); sp_.setFixedSize(18, 18); g.addWidget(sp_, 0, 3)       # keeps the columns aligned
        g.setColumnStretch(1, 1)
        self._lock = False
        self.sl.valueChanged.connect(self._from_slider); self.sp.valueChanged.connect(self._from_spin)
        self.sl.installEventFilter(self); self.set(default)
        self.sl.setToolTip("Doppelklick: Standardwert")
    def eventFilter(self, o, e):
        if o is self.sl and e.type() == QEvent.MouseButtonDblClick: self.set(self.default); return True
        if o is self.sl and e.type() == QEvent.Wheel and not self.sl.hasFocus(): e.ignore(); return True   # page scrolls instead
        return False
    def _from_slider(self, v):
        if self._lock: return
        val = self.lo+v*self.step; self._lock = True; self.sp.setValue(val*self.scale); self._lock = False; self.changed.emit(val)
    def _from_spin(self, v):
        if self._lock: return
        val = v/self.scale; self._lock = True; self.sl.setValue(int(round((val-self.lo)/self.step))); self._lock = False; self.changed.emit(val)
    def value(self): return self.sp.value()/self.scale
    def set(self, v):
        v = float(np.clip(v, self.lo, self.hi)); self._lock = True; self.sl.setValue(int(round((v-self.lo)/self.step))); self.sp.setValue(v*self.scale); self._lock = False; self.changed.emit(v)
    def setEnabled(self, on):
        super().setEnabled(on); self.lab.setStyleSheet("" if on else "color:%s;" % C["faint"])

class Segmented(QWidget):
    changed = Signal(str)
    def __init__(self, options, value=None):
        super().__init__(); h = QHBoxLayout(self); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(0)
        self.group = QButtonGroup(self); self.group.setExclusive(True); self.btns = {}
        for i, (key, text) in enumerate(options):
            b = QPushButton(text); b.setCheckable(True); b.setCursor(Qt.PointingHandCursor)
            b.setObjectName("segL" if i == 0 else ("segR" if i == len(options)-1 else "seg"))
            self.group.addButton(b); h.addWidget(b); self.btns[key] = b
            b.clicked.connect(lambda _=False, k=key: self.changed.emit(k))
        h.addStretch(1); self.set(value or options[0][0])
    def value(self):
        for k, b in self.btns.items():
            if b.isChecked(): return k
    def set(self, key):
        if key in self.btns: self.btns[key].setChecked(True)

def row(*widgets, stretch_last=False, spacing=10):
    h = QHBoxLayout(); h.setSpacing(spacing); h.setContentsMargins(0, 0, 0, 0)
    for w in widgets:
        if w == "stretch": h.addStretch(1)
        elif isinstance(w, (QHBoxLayout, QVBoxLayout)): h.addLayout(w)
        else: h.addWidget(w)
    return h

def labeled(text, w, help_key=None, width=128):
    l = QLabel(text); l.setMinimumWidth(width); items = [l, w]
    if help_key: items.append(HelpDot(help_key))
    return row(*items, "stretch") if not isinstance(w, (QLineEdit, QComboBox)) else row(*items)

class Bridge(QObject):
    log = Signal(str); progress = Signal(float); done = Signal(object); failed = Signal(str); item = Signal(object)

def run_bg(owner, fn, on_done=None, on_fail=None, on_log=None, on_prog=None, on_item=None):
    """Runs fn(bridge) in a thread; signals arrive in the GUI thread."""
    b = Bridge(owner)
    if on_done: b.done.connect(on_done)
    if on_fail: b.failed.connect(on_fail)
    if on_log: b.log.connect(on_log)
    if on_prog: b.progress.connect(on_prog)
    if on_item: b.item.connect(on_item)
    def work():
        try: b.done.emit(fn(b))
        except mc.Cancelled: b.failed.emit("Abgebrochen.")
        except Exception as e:
            traceback.print_exc(); b.failed.emit("%s" % e)
    threading.Thread(target=work, daemon=True).start()
    return b

def fmt_time(s):
    s = max(0, int(s)); return "%d:%02d" % (s//60, s % 60)

def open_folder(path):
    if path and os.path.isdir(path): QDesktopServices.openUrl(QUrl.fromLocalFile(path))

# ============================================================== drawing widgets
class SpectrumView(QWidget):
    """Long-term spectra on a log axis: target profile, original, master."""
    def __init__(self):
        super().__init__(); self.setMinimumHeight(196); self.curves = []; self.note = "Titel auswählen, um Spektrum und Messwerte zu sehen."
    def set_curves(self, curves, note=""):
        self.curves = curves; self.note = note; self.update()
    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(38, 26, -10, -22)
        f0, f1 = np.log10(30), np.log10(18000)
        tilt = 3.0*np.log2(mc.FL/1000.0)                      # +3 dB/octave around 1 kHz: pink noise looks flat
        vals = [np.asarray(c[1])+tilt for c in self.curves]
        if vals:
            allv = np.concatenate(vals); ymax = float(np.ceil((np.max(allv)+1)/6)*6); ymin = float(np.floor((np.percentile(allv, 2)-2)/6)*6)
            ymin = max(ymin, ymax-48); ymin = min(ymin, ymax-18)
        else: ymin, ymax = -18.0, 12.0
        X = lambda f: r.left()+(np.log10(f)-f0)/(f1-f0)*r.width()
        Y = lambda d: r.bottom()-(np.clip(d, ymin, ymax)-ymin)/(ymax-ymin)*r.height()
        p.setPen(QPen(QColor(C["border"]), 1))
        small = QFont(self.font()); small.setPointSizeF(8); p.setFont(small)
        for fz, t in ((50, "50"), (100, "100"), (200, "200"), (500, "500"), (1000, "1k"), (2000, "2k"), (5000, "5k"), (10000, "10k")):
            x = X(fz); p.setPen(QPen(QColor(C["border"]), 1)); p.drawLine(QPointF(x, r.top()), QPointF(x, r.bottom()))
            p.setPen(QColor(C["faint"])); p.drawText(QRectF(x-20, r.bottom()+4, 40, 14), Qt.AlignCenter, t)
        for d in range(int(ymin), int(ymax)+1, 6):
            y = Y(d); p.setPen(QPen(QColor(C["border"] if d else C["border2"]), 1)); p.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))
            p.setPen(QColor(C["faint"])); p.drawText(QRectF(0, y-7, 32, 14), Qt.AlignRight | Qt.AlignVCenter, "%+d" % d if d else "0")
        if not self.curves:
            p.setPen(QColor(C["muted"])); p.drawText(r, Qt.AlignCenter, self.note); return
        fl = mc.FL
        for (name, _v, color, style, width), vals in zip(self.curves, vals):
            path = QPainterPath(); first = True
            for f, d in zip(fl, vals):
                pt = QPointF(X(f), Y(d))
                if first: path.moveTo(pt); first = False
                else: path.lineTo(pt)
            pen = QPen(QColor(color), width); pen.setStyle(style); pen.setCapStyle(Qt.RoundCap); p.setPen(pen); p.drawPath(path)
        # legend above the plot
        x = r.left()+2; ly = r.top()-14
        for name, _v, color, style, width in self.curves:
            p.setPen(QPen(QColor(color), 2, style)); p.drawLine(QPointF(x, ly), QPointF(x+16, ly))
            p.setPen(QColor(C["muted"])); tw = p.fontMetrics().horizontalAdvance(name); p.drawText(QPointF(x+22, ly+4), name); x += tw+44
        if self.note:
            p.setPen(QColor(C["faint"])); p.drawText(QRectF(r.left(), ly-8, r.width(), 16), Qt.AlignRight | Qt.AlignVCenter, self.note)

class WaveView(QWidget):
    seek = Signal(float)
    def __init__(self):
        super().__init__(); self.setMinimumHeight(54); self.env_a = None; self.env_b = None; self.pos = 0.0; self.dur = 0.0; self.show_b = False
        self.setCursor(Qt.PointingHandCursor); self.msg = ""
    def set_env(self, a=None, b=None, dur=None):
        if a is not None or b is None: self.env_a = a
        self.env_b = b
        if dur is not None: self.dur = dur
        self.update()
    def set_pos(self, t): self.pos = t; self.update()
    def mousePressEvent(self, e):
        if self.dur > 0: self.seek.emit(max(0.0, min(1.0, e.position().x()/max(1, self.width())))*self.dur)
    mouseMoveEvent = mousePressEvent
    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); r = QRectF(self.rect()).adjusted(0, 4, 0, -4)
        p.setPen(Qt.NoPen); p.setBrush(QColor(C["field"])); p.drawRoundedRect(r, 8, 8)
        mid = r.center().y(); h = r.height()/2-4
        def draw(env, color, alpha):
            if env is None or len(env) == 0: return
            n = len(env); path = QPainterPath(); w = r.width()
            path.moveTo(r.left(), mid-float(env[0, 1])*h)
            for i in range(n): path.lineTo(r.left()+i/(n-1)*w, mid-float(env[i, 1])*h)
            for i in range(n-1, -1, -1): path.lineTo(r.left()+i/(n-1)*w, mid-float(env[i, 0])*h)
            c = QColor(color); c.setAlphaF(alpha); p.setBrush(c); p.setPen(Qt.NoPen); p.drawPath(path)
        draw(self.env_a, C["muted"], 0.45 if self.env_b is None else (0.25 if self.show_b else 0.55))
        if self.env_b is not None: draw(self.env_b, C["acc"], 0.75 if self.show_b else 0.30)
        if self.env_a is None and self.env_b is None:
            p.setPen(QColor(C["faint"])); p.drawText(r, Qt.AlignCenter, self.msg or "—")
        if self.dur > 0:
            x = r.left()+self.pos/self.dur*r.width(); p.setPen(QPen(QColor(C["amber"]), 2)); p.drawLine(QPointF(x, r.top()+2), QPointF(x, r.bottom()-2))

class Meter(QFrame):
    def __init__(self, title, help_text=None):
        super().__init__(); self.setStyleSheet("QFrame{background:%s;border:1px solid %s;border-radius:9px;}" % (C["field"], C["border"]))
        v = QVBoxLayout(self); v.setContentsMargins(12, 6, 12, 7); v.setSpacing(0)
        t = QLabel(title); t.setStyleSheet("border:none;color:%s;font-size:8.5pt;" % C["faint"]); v.addWidget(t)
        self.val = QLabel("—"); self.val.setStyleSheet("border:none;font-size:12pt;font-weight:600;")
        self.sub = QLabel(""); self.sub.setStyleSheet("border:none;color:%s;font-size:8.5pt;" % C["muted"])
        self.sub.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred); self.setMinimumWidth(0)
        h = QHBoxLayout(); h.setSpacing(8); h.addWidget(self.val); h.addWidget(self.sub, 1, Qt.AlignBottom); v.addLayout(h)
        if help_text: self.setToolTip(help_text)
    def set(self, main, sub="", color=None):
        self.val.setText(main); self.sub.setText(sub); self.val.setStyleSheet("border:none;font-size:12pt;font-weight:600;%s" % ("color:%s;" % color if color else ""))

# ============================================================== audio player (A/B, loudness matched)
class Player(QObject):
    tick = Signal(float); state = Signal(bool)
    def __init__(self):
        super().__init__(); self.a = None; self.b = None; self.sr = 44100; self.pos = 0; self.which = "a"; self.cur = "a"
        self.ga = 1.0; self.gb = 1.0; self.stream = None; self.playing = False; self.lock = threading.Lock()
        self.timer = QTimer(self); self.timer.setInterval(40); self.timer.timeout.connect(self._poll)
    @property
    def available(self): return sd is not None
    def load(self, a, sr):
        self.stop(); self.a = np.ascontiguousarray(a, dtype=np.float32); self.b = None; self.sr = sr; self.pos = 0; self.which = self.cur = "a"
    def set_b(self, b):
        with self.lock: self.b = np.ascontiguousarray(b, dtype=np.float32)
    def set_gains(self, ga, gb): self.ga, self.gb = ga, gb
    def select(self, which): self.which = which
    def duration(self): return len(self.a)/self.sr if self.a is not None else 0.0
    def seek(self, t):
        with self.lock: self.pos = int(max(0, min(self.duration(), t))*self.sr)
        self.tick.emit(self.pos/self.sr)
    def has_b(self): return self.b is not None
    def _chunk(self, w, p, end):
        """Samples p..end of source w ('a' or 'b') with its playback gain."""
        if w == "b" and self.has_b(): return self.b[p:end]*self.gb
        return self.a[p:end]*self.ga
    def _cb(self, out, frames, tinfo, status):
        with self.lock:
            p = self.pos; n = len(self.a); end = min(n, p+frames); k = end-p
            chunk = self._chunk(self.cur, p, end)
            if self.which != self.cur:        # 10 ms crossfade when switching A/B
                nb = self._chunk(self.which, p, end); k2 = min(k, len(nb))
                if k2 > 0:
                    ramp = np.clip(np.arange(k2)/max(1, int(0.01*self.sr)), 0, 1)[:, None].astype(np.float32)
                    chunk[:k2] = chunk[:k2]*(1-ramp)+nb[:k2]*ramp
                self.cur = self.which
            out[:k] = np.clip(chunk, -1, 1); out[k:] = 0; self.pos = end
            if end >= n: raise sd.CallbackStop()
    def play(self):
        if sd is None or self.a is None: return
        if self.pos >= len(self.a)-1: self.pos = 0
        self.stop(keep_pos=True)
        try:
            self.stream = sd.OutputStream(samplerate=self.sr, channels=2, dtype="float32", callback=self._cb, blocksize=1024, latency="low")
            self.stream.start(); self.playing = True; self.timer.start(); self.state.emit(True)
        except Exception as e:
            self.playing = False; self.state.emit(False); QMessageBox.warning(None, "Wiedergabe", "Audiowiedergabe nicht möglich:\n%s" % e)
    def stop(self, keep_pos=True):
        if self.stream is not None:
            try: self.stream.stop(); self.stream.close()
            except Exception: pass
            self.stream = None
        if not keep_pos: self.pos = 0
        if self.playing: self.playing = False; self.state.emit(False)
        self.timer.stop()
    def toggle(self): self.stop() if self.playing else self.play()
    def _poll(self):
        self.tick.emit(self.pos/self.sr)
        if self.stream is not None and not self.stream.active: self.stop()

class PlayerBar(QWidget):
    """Waveform, transport, A/B switch, loudness match."""
    def __init__(self, player):
        super().__init__(); self.p = player
        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(8)
        self.wave = WaveView(); v.addWidget(self.wave)
        self.bplay = btn("", I["play"], tip="Abspielen / Pause (Leertaste)", slot=self.p.toggle); self.bplay.setFixedWidth(44)
        self.bstop = btn("", I["stop"], tip="Stopp", slot=lambda: (self.p.stop(keep_pos=False), self.p.tick.emit(0.0))); self.bstop.setFixedWidth(44)
        self.ab = Segmented([("a", "A  Original"), ("b", "B  Master")], "a"); self.ab.changed.connect(self._ab)
        self.match = QCheckBox("Lautheit angleichen"); self.match.setChecked(True); self.match.setToolTip(HELP["preview"])
        self.time = QLabel("0:00 / 0:00"); self.time.setObjectName("muted")
        v.addLayout(row(self.bplay, self.bstop, self.ab, self.match, "stretch", self.time))
        self.wave.seek.connect(self.p.seek); self.p.tick.connect(self._tick); self.p.state.connect(self._state)
        if not self.p.available:
            for w in (self.bplay, self.bstop): w.setEnabled(False)
            self.time.setText("Wiedergabe nicht verfügbar (sounddevice fehlt)")
        self.ab.btns["b"].setEnabled(False)
    def _ab(self, k): self.p.select(k); self.wave.show_b = k == "b"; self.wave.update()
    def _tick(self, t): self.wave.set_pos(t); self.time.setText("%s / %s" % (fmt_time(t), fmt_time(self.p.duration())))
    def _state(self, on): self.bplay._labels[0].setText(I["pause"] if on else I["play"])
    def has_b(self, on):
        self.ab.btns["b"].setEnabled(on)
        if not on: self.ab.set("a"); self._ab("a")

# ============================================================== file table with drag & drop
class FileTable(QTableWidget):
    dropped = Signal(list)
    def __init__(self, columns, widths=None):
        super().__init__(0, len(columns)); self.setHorizontalHeaderLabels(columns); self.setAcceptDrops(True)
        self.verticalHeader().hide(); self.setShowGrid(False); self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection); self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch); self.horizontalHeader().setHighlightSections(False)
        self.verticalHeader().setDefaultSectionSize(32); self.setFocusPolicy(Qt.StrongFocus)
        for i, w in enumerate(widths or []):
            if w: self.horizontalHeader().setSectionResizeMode(i, QHeaderView.Fixed); self.setColumnWidth(i, w)
        self.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._hover = False; self.fit_rows = None
        self.model().rowsInserted.connect(self._fit); self.model().rowsRemoved.connect(self._fit)
    def auto_height(self, lo=3, hi=7):
        self.fit_rows = (lo, hi); self._fit()
    def _fit(self, *a):
        if not self.fit_rows: return
        lo, hi = self.fit_rows; n = min(max(self.rowCount(), lo), hi)
        self.setFixedHeight(self.horizontalHeader().sizeHint().height()+n*self.verticalHeader().defaultSectionSize()+6)
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls(): e.acceptProposedAction(); self._hover = True; self.viewport().update()
    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls(): e.acceptProposedAction()
    def dragLeaveEvent(self, e): self._hover = False; self.viewport().update()
    def dropEvent(self, e):
        self._hover = False; self.viewport().update(); paths = []
        for u in e.mimeData().urls():
            p = u.toLocalFile()
            if os.path.isdir(p): paths += mc.audio_files_in(p)
            elif p.lower().endswith(mc.AUDIO_EXT): paths.append(p)
        if paths: self.dropped.emit(paths)
    def paintEvent(self, e):
        super().paintEvent(e)
        if self.rowCount() == 0 or self._hover:
            p = QPainter(self.viewport()); p.setRenderHint(QPainter.Antialiasing); r = QRectF(self.viewport().rect()).adjusted(6, 6, -6, -6)
            pen = QPen(QColor(C["acc"] if self._hover else C["border2"]), 1.5, Qt.DashLine); p.setPen(pen)
            if self._hover: p.setBrush(QColor(79, 200, 214, 18))
            p.drawRoundedRect(r, 10, 10)
            if self.rowCount() == 0:
                p.setFont(icon_font(22)); p.setPen(QColor(C["acc"] if self._hover else C["faint"])); p.drawText(r.adjusted(0, -40, 0, 0), Qt.AlignCenter, I["add"])
                f = QFont(self.font()); f.setPointSizeF(10.5); p.setFont(f); p.setPen(QColor(C["text"])); p.drawText(r.adjusted(0, 24, 0, 0), Qt.AlignCenter, "Audiodateien oder Ordner hierher ziehen")
                f.setPointSizeF(9); p.setFont(f); p.setPen(QColor(C["faint"])); p.drawText(r.adjusted(0, 64, 0, 0), Qt.AlignCenter, "WAV · FLAC · AIFF · OGG · MP3")
    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Delete: self.parent_remove() if hasattr(self, "parent_remove") else None
        else: super().keyPressEvent(e)

# ============================================================== pages
class Page(QWidget):
    def __init__(self, title, sub):
        super().__init__(); self.setObjectName("content")
        self.v = QVBoxLayout(self); self.v.setContentsMargins(26, 16, 26, 16); self.v.setSpacing(12)
        head = QVBoxLayout(); head.setSpacing(2)
        t = QLabel(title); t.setObjectName("pageTitle"); s = QLabel(sub); s.setObjectName("pageSub"); s.setWordWrap(True)
        head.addWidget(t); head.addWidget(s); self.v.addLayout(head)
    def state(self): return {}
    def restore(self, d): pass

def scroll_column(width=None):
    sa = QScrollArea(); sa.setWidgetResizable(True); sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    inner = QWidget(); inner.setStyleSheet("background:transparent;"); lay = QVBoxLayout(inner); lay.setContentsMargins(0, 0, 14, 0); lay.setSpacing(12)
    sa.setWidget(inner)
    if width: sa.setFixedWidth(width)
    return sa, lay

class OutputBar(QFrame):
    """Bottom bar: output folder, format, progress, log, primary actions."""
    def __init__(self, default_dir, primary_text, extra=None):
        super().__init__(); self.setObjectName("card")
        v = QVBoxLayout(self); v.setContentsMargins(16, 12, 16, 12); v.setSpacing(8)
        self.dir = QLineEdit(default_dir); self.dir.setPlaceholderText("Ausgabeordner"); self.dir.setMinimumWidth(320); self.dir.setToolTip(default_dir)
        bdir = btn("", I["folder"], tip="Ordner wählen", slot=self.pick); bopen = btn("", I["open"], tip="Ausgabeordner öffnen", slot=lambda: open_folder(self.dir.text()))
        self.bits = Segmented([("24", "24 Bit"), ("16", "16 Bit + Dither")], "24")
        self.primary = btn(primary_text, I["check"], kind="primary")
        self.cancel = btn("Abbrechen", I["cancel"], kind="danger"); self.cancel.hide()
        self.logbtn = QPushButton("Protokoll ▾"); self.logbtn.setObjectName("ghost"); self.logbtn.setCheckable(True)
        items = [QLabel("Ausgabe"), self.dir, bdir, bopen, self.bits, HelpDot("bits")]
        top = row(*items, "stretch", self.logbtn, *(extra or []), self.cancel, self.primary); top.setStretchFactor(self.dir, 1); v.addLayout(top)
        self.prog = QProgressBar(); self.prog.setRange(0, 1000); self.prog.setValue(0); self.prog.setFixedHeight(6)
        self.status = QLabel("Bereit."); self.status.setObjectName("muted")
        v.addLayout(row(self.status, "stretch")); v.addWidget(self.prog)
        self.log = QPlainTextEdit(); self.log.setReadOnly(True); self.log.setMaximumHeight(170); self.log.hide(); v.addWidget(self.log)
        self.logbtn.toggled.connect(lambda on: (self.log.setVisible(on), self.logbtn.setText("Protokoll ▴" if on else "Protokoll ▾")))
    def pick(self):
        d = QFileDialog.getExistingDirectory(self, "Ausgabeordner", self.dir.text())
        if d: self.dir.setText(os.path.normpath(d))
    def write(self, s):
        self.log.appendPlainText(s)
        if s.strip(): self.status.setText(s.strip()[:160])
    def busy(self, on):
        self.primary.setVisible(not on); self.cancel.setVisible(on)
        if not on: self.cancel.setEnabled(True)

# ---------------------------------------------------------------- Mixing
class MixPlayer(Player):
    """B = the mix, summed live from the processed tracks: faders, panorama, mute and solo act while it plays."""
    def __init__(self):
        super().__init__(); self.parts = None; self.G = None
    def load(self, a, sr):
        super().load(a, sr); self.parts = None; self.G = None
    def set_parts(self, parts, G):
        with self.lock: self.parts = [np.ascontiguousarray(p, dtype=np.float32) for p in parts]; self.G = np.asarray(G, np.float32)
    def set_mix_gains(self, G):
        with self.lock: self.G = np.asarray(G, np.float32)
    def has_b(self): return self.parts is not None
    def _chunk(self, w, p, end):
        if w == "b" and self.parts is not None:
            out = np.zeros((end-p, 2), np.float32)
            for x, g in zip(self.parts, self.G):
                if g[0] or g[1]: out += x[p:end]*g
            return out*self.gb
        return self.a[p:end]*self.ga

def short_names(names):
    """Track names without the part all of them share at the start (e.g. the song title): 'Song - Bass' -> 'Bass'."""
    if len(names) < 2: return list(names)
    pre = os.path.commonprefix(names); cut = max(pre.rfind(c) for c in " -_.")+1 if pre else 0
    out = [n[cut:].strip(" -_.") or n for n in names]
    return out if all(out) else list(names)

class ChannelStrip(QFrame):
    """One mixer channel: name, vertical fader (dB), panorama, mute, solo. Click selects the channel."""
    live = Signal(int); picked = Signal(int)
    def __init__(self, idx, name, role, ch):
        super().__init__(); self.idx = idx; self.role = role; self.setFixedWidth(96); self.setCursor(Qt.PointingHandCursor)
        v = QVBoxLayout(self); v.setContentsMargins(8, 8, 8, 8); v.setSpacing(6)
        self.bar = QFrame(); self.bar.setFixedHeight(3); v.addWidget(self.bar)
        self.name = QLabel(); self.name.setAlignment(Qt.AlignCenter); self.name.setToolTip(name)
        self.name.setText(self.name.fontMetrics().elidedText(name, Qt.ElideRight, 80)); v.addWidget(self.name)
        self.rl = QLabel(); self.rl.setAlignment(Qt.AlignCenter); self.rl.setObjectName("faint"); v.addWidget(self.rl)
        self.fader = QSlider(Qt.Vertical); self.fader.setRange(-60, 24); self.fader.setMinimumHeight(150)      # 0.5 dB steps, −30 … +12 dB
        self.fader.setToolTip("Lautstärke (Doppelklick: 0 dB). Wirkt sofort, auch während der Wiedergabe.")
        fh = QHBoxLayout(); fh.addStretch(1); fh.addWidget(self.fader); fh.addStretch(1); v.addLayout(fh, 1)
        self.val = QLabel(); self.val.setAlignment(Qt.AlignCenter); self.val.setObjectName("value"); v.addWidget(self.val)
        self.pan = QSlider(Qt.Horizontal); self.pan.setRange(-100, 100); self.pan.setToolTip("Panorama (Doppelklick: Mitte)"); v.addWidget(self.pan)
        self.panl = QLabel(); self.panl.setAlignment(Qt.AlignCenter); self.panl.setObjectName("faint"); v.addWidget(self.panl)
        self.m = QPushButton("M"); self.s = QPushButton("S")
        for b, tip, nm in ((self.m, "Stumm", "chipM"), (self.s, "Solo", "chipS")):
            b.setCheckable(True); b.setFixedSize(34, 24); b.setToolTip(tip); b.setObjectName(nm); b.setCursor(Qt.PointingHandCursor)
        v.addLayout(row("stretch", self.m, self.s, "stretch", spacing=6))
        for w in (self.fader, self.pan): w.installEventFilter(self)
        self.fader.valueChanged.connect(self._changed); self.pan.valueChanged.connect(self._changed)
        self.m.toggled.connect(self._changed); self.s.toggled.connect(self._changed)
        self.set_role(role); self.set_values(ch); self.set_selected(False)
    def set_role(self, role):
        self.role = role; self.bar.setStyleSheet("background:%s;border:none;border-radius:1px;" % mx.ROLE_COLORS.get(role, C["faint"]))
        self.rl.setText(mx.ROLE_DE.get(role, role))
    def set_values(self, ch):
        for w in (self.fader, self.pan, self.m, self.s): w.blockSignals(True)
        self.fader.setValue(int(round(float(ch.get("gain_db", 0.0))*2))); self.pan.setValue(int(round(float(ch.get("pan", 0.0))*100)))
        self.m.setChecked(bool(ch.get("mute"))); self.s.setChecked(bool(ch.get("solo")))
        for w in (self.fader, self.pan, self.m, self.s): w.blockSignals(False)
        self._labels()
    def values(self):
        return dict(gain_db=self.fader.value()/2.0, pan=self.pan.value()/100.0, mute=self.m.isChecked(), solo=self.s.isChecked())
    def _labels(self):
        g = self.fader.value()/2.0; self.val.setText("%+.1f dB" % g if g else "0 dB"); p = self.pan.value()
        self.panl.setText("C" if p == 0 else ("L%d" % -p if p < 0 else "R%d" % p))
    def _changed(self, *a): self._labels(); self.live.emit(self.idx)
    def eventFilter(self, o, e):
        if e.type() == QEvent.MouseButtonDblClick:
            (self.fader if o is self.fader else self.pan).setValue(0); return True
        if e.type() == QEvent.MouseButtonPress: self.picked.emit(self.idx)
        if e.type() == QEvent.Wheel and o is self.pan: e.ignore(); return True
        return False
    def mousePressEvent(self, e): self.picked.emit(self.idx); super().mousePressEvent(e)
    def set_selected(self, on):
        self.setStyleSheet("ChannelStrip{background:%s;border:1px solid %s;border-radius:10px;}" % (C["card2"] if on else C["field"], C["acc_d"] if on else C["border"]))

class MixPage(Page):
    """Mixing: tracks or AI-separated raw mixes, mixed after a reference (mix profile), with mixer, preview and mastering."""
    ANALYSE_COLS = ["Rolle", "Ziel", "Ist", "Korr.", "Effekte der Referenz"]
    def __init__(self, win):
        super().__init__("Mixing", "Einzelspuren oder einen Rohmix nach dem Vorbild von Referenzsongs mischen – Balance, Klang, Dynamik, Breite und Effekte. "
                                   "Mit Mischpult, A/B-Vorschau und direktem Mastering.")
        self.win = win; self.mode = "tracks"; self.track_files = []; self.roles = []; self.channels = []
        self.song_files = []; self.song_ch = {}; self.cur_song = None; self.sel = None
        self.session = None; self.preview = None; self.cancel_ev = None; self._busy = False
        self.player = MixPlayer(); self._live_timer = QTimer(self); self._live_timer.setSingleShot(True); self._live_timer.setInterval(450); self._live_timer.timeout.connect(self.refresh_report)
        body = QHBoxLayout(); body.setSpacing(16); self.v.addLayout(body, 1)
        lsa, left = scroll_column(); body.addWidget(lsa, 1); self.lsa = lsa
        # ---- source
        self.src = Segmented([("tracks", "Einzelspuren"), ("song", "Song / Rohmix  (KI-Trennung)")], "tracks"); self.src.changed.connect(self.set_mode)
        qc = Card("Quelle", help_key="m_source", right=self.src)
        self.ttable = FileTable(["Spur", "Rolle", "Dauer", "Kanäle"], [0, 150, 64, 70]); self.ttable.auto_height(3, 8)
        self.ttable.dropped.connect(self.add_files); self.ttable.parent_remove = self.remove_sel
        self.stable = FileTable(["Song", "Dauer", "LUFS", "Status"], [0, 64, 64, 190]); self.stable.auto_height(3, 6)
        self.stable.dropped.connect(self.add_files); self.stable.parent_remove = self.remove_sel; self.stable.itemSelectionChanged.connect(self.on_song_select)
        qc.add(self.ttable); qc.add(self.stable); self.stable.hide()
        self.song_name = QLineEdit(); self.song_name.setPlaceholderText("Songname (für die Ausgabedateien)"); self.song_name.setMinimumWidth(230); self.song_name.setMaximumWidth(300)
        self.name_box = QWidget(); nb = QHBoxLayout(self.name_box); nb.setContentsMargins(0, 0, 0, 0); nb.addWidget(self.song_name)
        qc.add(row(btn("Dateien", I["add"], slot=lambda: self.pick(False)), btn("Ordner", I["folder"], slot=lambda: self.pick(True)),
                   btn("Entfernen", I["delete"], kind="ghost", slot=self.remove_sel), btn("Alle entfernen", None, kind="ghost", slot=self.clear), "stretch", self.name_box))
        left.addWidget(qc)
        # ---- mixer
        self.reset_all = btn("Alle Kanäle zurücksetzen", I["refresh"], kind="ghost", slot=self.reset_channels)
        mc_ = Card("Mischpult", help_key="m_mixer", right=self.reset_all)
        self.strip_area = QScrollArea(); self.strip_area.setWidgetResizable(True); self.strip_area.setFixedHeight(340)
        self.strip_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff); self.strip_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.strip_area.setStyleSheet("QScrollBar:horizontal{height:10px;background:transparent;margin:2px;} QScrollBar::handle:horizontal{background:%s;border-radius:4px;min-width:30px;}" % C["border2"])
        self.strip_host = QWidget(); self.strip_host.setStyleSheet("background:transparent;"); self.strip_lay = QHBoxLayout(self.strip_host)
        self.strip_lay.setContentsMargins(0, 0, 0, 0); self.strip_lay.setSpacing(8); self.strip_area.setWidget(self.strip_host); self.strips = []
        mc_.add(self.strip_area)
        self.mix_note = QLabel(""); self.mix_note.setObjectName("faint"); self.mix_note.setWordWrap(True); mc_.add(self.mix_note)
        left.addWidget(mc_)
        # ---- analysis & preview
        ac = Card("Analyse & Vorschau", help_key="m_preview")
        self.spec = SpectrumView(); self.spec.note = "Vorschau berechnen, um Spektren und Pegel zu sehen."; ac.add(self.spec)
        mrow = QHBoxLayout(); mrow.setSpacing(8)
        self.m_lufs = Meter("Mix-Lautheit", "Integrierte Lautheit des Mixes (vor dem Mastering)"); self.m_dev = Meter("Balance-Abweichung", "Mittlere Abweichung der Rollen-Pegel von der Referenz (LU)")
        self.m_width = Meter("Stereobreite", "Seitenanteil über 200 Hz"); self.m_parts = Meter("Spuren", "aktive Spuren / Rollen")
        for m in (self.m_lufs, self.m_dev, self.m_width, self.m_parts): mrow.addWidget(m)
        ac.add(mrow)
        self.pbar = PlayerBar(self.player); self.pbar.ab.btns["a"].setText("A  Rohmix"); self.pbar.ab.btns["b"].setText("B  Mix"); ac.add(self.pbar)
        self.pbar.match.toggled.connect(lambda *_: self.apply_match())
        self.bprev = btn("Vorschau berechnen", I["preview"], slot=self.make_preview); self.prev_note = QLabel(""); self.prev_note.setObjectName("faint")
        ac.add(row(self.bprev, self.prev_note, "stretch")); left.addWidget(ac); left.addStretch(1)
        # ---- right column
        sa, rl = scroll_column(456); body.addWidget(sa); self.rsa = sa
        self.prof = QComboBox(); self.prof.setMinimumWidth(190); self.prof.currentIndexChanged.connect(self.on_profile)
        pm = QPushButton("…"); pm.setFixedWidth(36); pm.setToolTip("Mix-Profile verwalten"); menu = QMenu(pm)
        menu.addAction("Mix-Profil aus Songs anlernen …", self.learn); menu.addAction("Profil löschen", self.delete_profile); menu.addSeparator()
        menu.addAction("Profilordner öffnen", lambda: (os.makedirs(mx.MIX_DIR, exist_ok=True), open_folder(mx.MIX_DIR)))
        pm.setMenu(menu); pm.setStyleSheet("QPushButton::menu-indicator{width:0;}")
        rc = Card("Mix-Referenz"); rc.add(row(QLabel("Profil"), self.prof, pm, HelpDot("m_profile")))
        self.prof_info = QLabel(""); self.prof_info.setObjectName("faint"); self.prof_info.setWordWrap(True); rc.add(self.prof_info)
        self.learn_btn = btn("Aus Referenzsongs anlernen", I["learn"], slot=self.learn); rc.add(row(self.learn_btn, "stretch"))
        self.atable = QTableWidget(0, len(self.ANALYSE_COLS)); self.atable.setHorizontalHeaderLabels(self.ANALYSE_COLS); self.atable.verticalHeader().hide()
        self.atable.setEditTriggers(QAbstractItemView.NoEditTriggers); self.atable.setSelectionMode(QAbstractItemView.NoSelection); self.atable.setShowGrid(False)
        self.atable.verticalHeader().setDefaultSectionSize(28); self.atable.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        for i, w in enumerate([96, 52, 52, 52]): self.atable.horizontalHeader().setSectionResizeMode(i, QHeaderView.Fixed); self.atable.setColumnWidth(i, w)
        self.atable.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch); rc.add(self.atable)
        rl.addWidget(rc)
        tc = Card("Von der Referenz übernehmen", help_key="m_take")
        self.s_bal = SliderRow("Balance", 0, 1, 1.0, 0.01, " %", "m_balance", 0, 100)
        self.s_tone = SliderRow("Klang (EQ)", 0, 1, 0.7, 0.01, " %", "m_tone", 0, 100)
        self.s_dyn = SliderRow("Dynamik", 0, 1, 0.6, 0.01, " %", "m_dyn", 0, 100)
        self.s_tr = SliderRow("Transienten", 0, 1, 0.5, 0.01, " %", "m_trans", 0, 100)
        self.s_wid = SliderRow("Stereobreite", 0, 1, 0.7, 0.01, " %", "m_width", 0, 100)
        self.s_fx = SliderRow("Hall & Delay", 0, 1.5, 0.0, 0.01, " %", "m_fx", 0, 100)
        for w in (self.s_bal, self.s_tone, self.s_dyn, self.s_tr, self.s_wid, self.s_fx): tc.add(w)
        ex = Card("Grenzen", collapsible=True, collapsed=True)
        self.s_maxeq = SliderRow("max. EQ", 2, 12, 6, 0.1, " dB", "maxeq"); self.s_maxg = SliderRow("max. Pegelkorr.", 3, 18, 12, 0.5, " dB", "m_maxgain")
        ex.add(self.s_maxeq); ex.add(self.s_maxg); tc.add(ex); ex.setStyleSheet("#card{background:%s;}" % C["field"])
        rl.addWidget(tc)
        # channel strip settings
        self.ch_card = Card("Kanal", help_key="m_channel"); self.ch_title = self.ch_card.findChild(QLabel, "cardTitle")
        self.c_role = QComboBox()
        for r in mx.ROLES: self.c_role.addItem(mx.ROLE_DE[r], r)
        self.c_role.currentIndexChanged.connect(self.on_role); self.role_row = QWidget(); rr = QHBoxLayout(self.role_row); rr.setContentsMargins(0, 0, 0, 0)
        l = QLabel("Rolle"); l.setFixedWidth(122); rr.addWidget(l); rr.addWidget(self.c_role, 1); rr.addWidget(HelpDot("m_role")); self.ch_card.add(self.role_row)
        self.c = dict(lowcut_hz=SliderRow("Low-Cut", 0, 300, 0, 1, " Hz", "m_lowcut", 0), low_db=SliderRow("Tiefen (100 Hz)", -8, 8, 0, 0.1, " dB"),
                      presence_db=SliderRow("Präsenz (3 kHz)", -8, 8, 0, 0.1, " dB"), high_db=SliderRow("Höhen (10 kHz)", -8, 8, 0, 0.1, " dB"),
                      comp=SliderRow("Kompressor", 0, 1, 0, 0.01, " %", "m_comp", 0, 100), width_db=SliderRow("Breite", -6, 6, 0, 0.1, " dB", "m_chwidth"),
                      reverb=SliderRow("Hall", 0, 1, 0, 0.01, " %", "m_reverb", 0, 100))
        for k, w in self.c.items(): self.ch_card.add(w); w.changed.connect(lambda v, k=k: self.on_channel(k, v))
        self.ch_card.add(row(btn("Kanal zurücksetzen", I["refresh"], kind="ghost", slot=self.reset_channel), "stretch"))
        rl.addWidget(self.ch_card)
        # summing & mastering
        sc = Card("Summe & Mastering")
        self.s_peak = SliderRow("Mix-Spitzenpegel", -12, -0.5, -3.0, 0.1, " dBTP", "m_peak"); sc.add(self.s_peak)
        self.do_master = QCheckBox("Anschließend mastern"); sc.add(row(self.do_master, HelpDot("m_master"), "stretch"))
        self.mprof = QComboBox(); self.mpreset = QComboBox()
        for k, d in mc.PRESETS.items(): self.mpreset.addItem(d["label"], k)
        self.mbox = QWidget(); mb = QVBoxLayout(self.mbox); mb.setContentsMargins(0, 0, 0, 0); mb.setSpacing(8)
        mb.addLayout(labeled("Mastering-Profil", self.mprof, width=122)); mb.addLayout(labeled("Plattform", self.mpreset, width=122)); sc.add(self.mbox)
        self.do_master.toggled.connect(self.mbox.setEnabled); self.mbox.setEnabled(False)
        self.save_parts = QCheckBox("Bearbeitete Einzelspuren zusätzlich speichern"); sc.add(self.save_parts)
        rl.addWidget(sc); rl.addStretch(1)
        self.out = OutputBar(os.path.join(os.path.expanduser("~"), "Desktop", "Mix-Ausgabe"), "Mix erstellen")
        self.out.primary.clicked.connect(self.start); self.out.cancel.clicked.connect(self.stop); self.v.addWidget(self.out)
        for w in (self.s_bal, self.s_tone, self.s_dyn, self.s_tr, self.s_wid, self.s_fx, self.s_maxeq, self.s_maxg, self.s_peak): w.changed.connect(self.mark_stale)
        self.reload_profiles(); self.reload_master_profiles(); self.set_mode("tracks"); self.select_channel(None)
    # ---------------------------------------------------------------- profiles
    def reload_profiles(self, select=None):
        cur = select or self.prof.currentData(); self.prof.blockSignals(True); self.prof.clear(); self.prof.addItem("Keine – nur manuell", "")
        for n in mx.list_mix_profiles(): self.prof.addItem(n, n)
        i = self.prof.findData(cur) if cur else -1; self.prof.setCurrentIndex(i if i >= 0 else (1 if self.prof.count() > 1 else 0))
        self.prof.blockSignals(False); self.on_profile()
    def profile(self):
        n = self.prof.currentData()
        if not n: return None
        try: return mx.load_mix_profile(n)
        except Exception: return None
    def on_profile(self, *a):
        pr = self.profile()
        for w in (self.s_bal, self.s_tone, self.s_dyn, self.s_tr, self.s_wid, self.s_fx): w.setEnabled(pr is not None)
        self.s_fx.setEnabled(bool(pr) and any(r.get("fx") for r in pr["roles"].values()))
        if pr is None:
            self.prof_info.setText("Ohne Referenz: nur Mischpult und Kanal-Einstellungen. Ein Mix-Profil lernen Sie aus einem oder mehreren Songs, deren Mix Ihnen gefällt."
                                   if not mx.list_mix_profiles() else "Ohne Referenz: nur Mischpult und Kanal-Einstellungen.")
            self.learn_btn.setVisible(not mx.list_mix_profiles())
        else:
            self.learn_btn.hide(); m = pr.get("master") or {}
            self.prof_info.setText("%d Referenz(en): %s · Mix %.1f LUFS · Trennung %s%s" % (
                pr["n"], ", ".join(os.path.splitext(s)[0] for s in pr["sources"][:3]) + (" …" if len(pr["sources"]) > 3 else ""), m.get("lufs", 0),
                mc.SEP_MODELS.get(pr.get("model") or "", {}).get("label", "?").split(" · ")[0], " · mit Effektanalyse" if pr.get("fx_analysed") else ""))
        self.fill_analysis(); self.reload_master_profiles(); self.mark_stale()
    def fill_analysis(self, report=None):
        pr = self.profile(); roles = pr["roles"] if pr else {}; rep = {b["role"]: b for b in (report or [])}
        keys = [r for r in mx.ROLES if r in roles or r in rep]; self.atable.setRowCount(len(keys))
        for i, r in enumerate(keys):
            ref = roles.get(r); b = rep.get(r)
            it = QTableWidgetItem("●  " + mx.ROLE_DE[r]); it.setForeground(QColor(mx.ROLE_COLORS[r])); self.atable.setItem(i, 0, it)
            def cell(c, text, color=None, tip=None):
                x = QTableWidgetItem(text); x.setForeground(QColor(color or C["muted"])); x.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter) if c in (1, 2, 3) else None
                if tip: x.setToolTip(tip)
                self.atable.setItem(i, c, x)
            cell(1, "%+.1f" % ref["rel"] if ref else "–", C["amber"] if ref else None, mx.describe_role(ref) if ref else "in der Referenz nicht vorhanden")
            if b and b.get("absent"): cell(2, "—", C["faint"], "nur Übersprechen der Trennung – bleibt unverändert"); cell(3, "")
            elif b and b.get("muted"): cell(2, "stumm", C["faint"]); cell(3, "")
            elif b and b.get("rel") is not None:
                dev = (b["rel"]-ref["rel"]) if ref else 0.0
                cell(2, "%+.1f" % b["rel"], C["ok"] if abs(dev) < 1.0 else (C["warn"] if abs(dev) < 3 else C["err"]), "Abweichung von der Referenz %+.1f LU" % dev if ref else None)
                cell(3, "%+.1f" % b["gain"] if abs(b["gain"]) >= 0.05 else "0", None, "Pegelkorrektur durch die Balance-Übernahme (dB)")
            else: cell(2, ""); cell(3, "")
            fx = (ref or {}).get("fx") or {}
            cell(4, " · ".join(("Hall %.1f s" % fx["reverb"]["rt60_s"]) if k == "reverb" else ("Delay %.0f ms" % (fx["delay"]["time_s"]*1000)) for k in ("reverb", "delay") if k in fx) or ("–" if ref else ""),
                 None, "\n".join(mc.describe_effect(k, v) for k, v in fx.items()) or None)
        self.atable.setFixedHeight(self.atable.horizontalHeader().sizeHint().height()+max(1, len(keys))*28+6)
    def reload_master_profiles(self):
        cur = self.mprof.currentData(); self.mprof.clear(); pr = self.profile()
        if pr and pr.get("master"): self.mprof.addItem("Aus der Mix-Referenz (%.1f LUFS)" % pr["master"]["lufs"], "__mix__")
        for n in mc.list_profiles(): self.mprof.addItem(n, n)
        i = self.mprof.findData(cur); self.mprof.setCurrentIndex(max(0, i))
    def learn(self):
        d = LearnMixDialog(self)
        if d.exec() and d.result_name: self.reload_profiles(d.result_name); self.win.pages["master"].reload_profiles()
    def delete_profile(self):
        n = self.prof.currentData()
        if not n: return
        if QMessageBox.question(self, "Mix-Profil löschen", "Mix-Profil „%s“ wirklich löschen?" % n) != QMessageBox.Yes: return
        try: mx.delete_mix_profile(n); self.reload_profiles()
        except Exception as e: QMessageBox.warning(self, "Mix-Profil löschen", str(e))
    # ---------------------------------------------------------------- sources
    def set_mode(self, k):
        if k == self.mode and self.strips: return
        self.mode = k; self.src.set(k); song = k == "song"
        self.ttable.setVisible(not song); self.stable.setVisible(song); self.name_box.setVisible(not song)
        if song and not mc.separation_available():
            self.mix_note.setText("Die KI-Trennung ist in dieser Version nicht installiert – Rohmixe können nicht zerlegt werden (Vollversion nötig).")
        self.drop_preview(); self.build_strips(); self.update_count()
    def pick(self, folder):
        if folder:
            d = QFileDialog.getExistingDirectory(self, "Ordner mit Spuren" if self.mode == "tracks" else "Ordner mit Songs", self.win.last_dir)
            if d: self.win.last_dir = d; self.add_files(mc.audio_files_in(d))
        else:
            fs, _ = QFileDialog.getOpenFileNames(self, "Spuren" if self.mode == "tracks" else "Songs", self.win.last_dir, "Audio (*.wav *.flac *.aif *.aiff *.ogg *.mp3)")
            if fs: self.win.last_dir = os.path.dirname(fs[0]); self.add_files(fs)
    def add_files(self, paths):
        song = self.mode == "song"; lst = self.song_files if song else self.track_files; tab = self.stable if song else self.ttable
        known = {os.path.normcase(os.path.abspath(p)) for p in lst}; added = []
        for p in paths:
            p = os.path.normpath(p); k = os.path.normcase(os.path.abspath(p))
            if k in known: continue
            known.add(k); lst.append(p); added.append(p); r = tab.rowCount(); tab.insertRow(r)
            it = QTableWidgetItem(os.path.splitext(os.path.basename(p))[0]); it.setToolTip(p); tab.setItem(r, 0, it)
            try: info = mc.sf.info(p); dur, chn = fmt_time(info.duration), ("mono" if info.channels == 1 else "stereo")
            except Exception: dur, chn = "?", "nicht lesbar"
            if song:
                for c, t in ((1, dur), (2, ""), (3, "bereit")): tab.setItem(r, c, QTableWidgetItem(t))
            else:
                role = mx.guess_role(p); self.roles.append(role); self.channels.append(dict(mx.CHANNEL_DEFAULTS))
                cb = QComboBox(); cb.setStyleSheet("QComboBox{padding:2px 6px;border-radius:5px;}")
                for rr in mx.ROLES: cb.addItem(mx.ROLE_DE[rr], rr)
                cb.setCurrentIndex(mx.ROLES.index(role)); cb.currentIndexChanged.connect(lambda _i, cb=cb: self.on_table_role(cb))
                tab.setCellWidget(r, 1, cb); tab.setItem(r, 2, QTableWidgetItem(dur)); tab.setItem(r, 3, QTableWidgetItem(chn))
        if not added: return
        if not song:
            if not self.song_name.text().strip(): self.song_name.setText(os.path.basename(os.path.dirname(added[0])))
            self.session = None; self.drop_preview(); self.build_strips()
        elif self.cur_song is None: self.stable.selectRow(0)
        self.update_count()
    def on_table_role(self, cb):
        for r in range(self.ttable.rowCount()):
            if self.ttable.cellWidget(r, 1) is cb:
                self.roles[r] = cb.currentData()
                if r < len(self.strips): self.strips[r].set_role(self.roles[r])
                if self.sel == r: self.c_role.blockSignals(True); self.c_role.setCurrentIndex(mx.ROLES.index(self.roles[r])); self.c_role.blockSignals(False)
                self.mark_stale()
    def remove_sel(self):
        song = self.mode == "song"; tab = self.stable if song else self.ttable; lst = self.song_files if song else self.track_files
        for r in sorted({i.row() for i in tab.selectedIndexes()}, reverse=True):
            p = lst.pop(r); tab.removeRow(r)
            if not song: self.roles.pop(r); self.channels.pop(r)
            elif p == self.cur_song: self.cur_song = None
        if not song: self.session = None; self.build_strips()
        self.drop_preview(); self.update_count()
    def clear(self):
        if self.mode == "song": self.song_files.clear(); self.stable.setRowCount(0); self.cur_song = None
        else: self.track_files.clear(); self.roles.clear(); self.channels.clear(); self.ttable.setRowCount(0); self.session = None; self.build_strips()
        self.drop_preview(); self.update_count()
    def update_count(self):
        n = len(self.song_files) if self.mode == "song" else (1 if self.track_files else 0)
        set_btn_text(self.out.primary, ("Mix erstellen (%d Songs)" % n if n > 1 else "Mix erstellen") if self.mode == "song" else
                     ("Mix erstellen (%d Spuren)" % len(self.track_files) if self.track_files else "Mix erstellen"))
    def on_song_select(self):
        rows = sorted({i.row() for i in self.stable.selectedIndexes()})
        if not rows or self.song_files[rows[0]] == self.cur_song: return
        self.cur_song = self.song_files[rows[0]]; self.session = None; self.drop_preview()
        self.prev_note.setText("„Vorschau berechnen“ trennt den Song (einmalig, danach zwischengespeichert) und mischt ihn."); self.prev_note.setStyleSheet("")
    def set_song_status(self, p, text, color=None):
        try: r = self.song_files.index(p)
        except ValueError: return
        it = self.stable.item(r, 3); it.setText(text); it.setForeground(QColor(color or C["muted"]))
    # ---------------------------------------------------------------- channels
    def strip_defs(self):
        """(name, role, channel dict) for every strip of the current mode."""
        if self.mode == "tracks":
            names = [os.path.splitext(os.path.basename(p))[0] for p in self.track_files]
            return [(n, r, ch) for n, r, ch in zip(short_names(names), self.roles, self.channels)]
        return [(mx.ROLE_DE[r], r, self.song_ch.setdefault(r, dict(mx.CHANNEL_DEFAULTS))) for r in mx.ROLES+["rest"]]
    def build_strips(self):
        for s in self.strips: s.setParent(None); s.deleteLater()
        while self.strip_lay.count():
            it = self.strip_lay.takeAt(0)
            if it.widget(): it.widget().deleteLater()
        self.strips = []
        for i, (name, role, ch) in enumerate(self.strip_defs()):
            s = ChannelStrip(i, name, role, ch); s.live.connect(self.on_live); s.picked.connect(self.select_channel); self.strip_lay.addWidget(s); self.strips.append(s)
        self.strip_lay.addStretch(1); self.strip_area.setFixedHeight(340 if self.strips else 0); self.strip_area.setVisible(bool(self.strips)); self.reset_all.setVisible(bool(self.strips))
        if not self.strips:
            self.mix_note.setText("Spuren hierher in die Liste oben ziehen – jede Spur bekommt einen Kanal. Die Rolle (Gesang, Drums, …) erkennt das Programm am Dateinamen.")
        elif self.mode == "song":
            self.mix_note.setText("Kanäle = Spuren nach der KI-Trennung. Die Einstellungen gelten für alle Songs der Liste. „Rest“ enthält, was die Trennung keiner Spur zuordnen konnte.")
        else: self.mix_note.setText("Fader, Panorama, Stumm und Solo wirken sofort. Klick auf einen Kanal zeigt rechts seine Klangregler.")
        self.select_channel(0 if self.strips and self.sel is None else (self.sel if self.sel is not None and self.sel < len(self.strips) else None))
    def select_channel(self, idx):
        self.sel = idx
        for i, s in enumerate(self.strips): s.set_selected(i == idx)
        defs = self.strip_defs(); on = idx is not None and idx < len(defs)
        self.ch_card.body.setEnabled(on)
        if not on:
            self.ch_title.setText("Kanal"); return
        name, role, ch = defs[idx]; self.ch_title.setText("Kanal · " + name)
        self.role_row.setVisible(self.mode == "tracks"); self.c_role.blockSignals(True); self.c_role.setCurrentIndex(mx.ROLES.index(role) if role in mx.ROLES else 0); self.c_role.blockSignals(False)
        for k, w in self.c.items():
            w.blockSignals(True); w.set(float(ch.get(k, mx.CHANNEL_DEFAULTS[k]))); w.blockSignals(False)
        mono = self.mode == "tracks" and self.ttable.item(idx, 3) is not None and self.ttable.item(idx, 3).text() == "mono"
        self.c["width_db"].setEnabled(not mono); self.c["width_db"].setToolTip("Mono-Spur: Breite über Panorama und Hall" if mono else "")
        self.show_channel_spec()
    def _ch(self, idx):
        return self.channels[idx] if self.mode == "tracks" else self.song_ch.setdefault((mx.ROLES+["rest"])[idx], dict(mx.CHANNEL_DEFAULTS))
    def on_channel(self, k, v):
        if self.sel is None: return
        self._ch(self.sel)[k] = float(v); self.mark_stale()
    def on_role(self, *a):
        if self.sel is None or self.mode != "tracks": return
        r = self.c_role.currentData(); self.roles[self.sel] = r; self.strips[self.sel].set_role(r)
        cb = self.ttable.cellWidget(self.sel, 1)
        if cb: cb.blockSignals(True); cb.setCurrentIndex(mx.ROLES.index(r)); cb.blockSignals(False)
        self.mark_stale()
    def reset_channel(self):
        if self.sel is None: return
        ch = self._ch(self.sel)
        for k in ("lowcut_hz", "low_db", "presence_db", "high_db", "comp", "width_db", "reverb"): ch[k] = mx.CHANNEL_DEFAULTS[k]
        self.select_channel(self.sel); self.mark_stale()
    def reset_channels(self):
        for i in range(len(self.strips)):
            ch = self._ch(i); ch.clear(); ch.update(mx.CHANNEL_DEFAULTS); self.strips[i].set_values(ch)
        self.select_channel(self.sel); self.on_live(-1); self.mark_stale()
    def on_live(self, idx):
        """Fader / pan / mute / solo: straight into the running preview."""
        if idx >= 0: self._ch(idx).update(self.strips[idx].values())
        if self.preview: self.player.set_mix_gains(self.live_gains()); self._live_timer.start()
    def live_gains(self):
        pv = self.preview; chans = pv["channels"]
        for i, ch in enumerate(chans):
            src = self._ch(pv["strip_of"][i]); ch.update(gain_db=src.get("gain_db", 0.0), pan=src.get("pan", 0.0), mute=bool(src.get("mute")), solo=bool(src.get("solo")))
        return (mx.fader_gains(chans, pv["tracks"])*pv["gain"]).astype(np.float32)
    # ---------------------------------------------------------------- params / preview
    def params(self):
        return dict(balance=self.s_bal.value(), tone=self.s_tone.value(), dynamics=self.s_dyn.value(), transients=self.s_tr.value(), width=self.s_wid.value(),
                    fx=self.s_fx.value() if self.s_fx.isEnabled() else 0.0, max_eq=self.s_maxeq.value(), max_gain=self.s_maxg.value(), peak_db=self.s_peak.value())
    def master_choice(self):
        if not self.do_master.isChecked(): return None, None
        d = self.mprof.currentData()
        if d == "__mix__": m = mx.master_profile_from_mix(self.profile())
        else:
            try: m = mc.load_profile(d)
            except Exception: m = None
        return m, mx.master_settings(self.mpreset.currentData() or "profil")
    def drop_preview(self):
        self.preview = None; self.player.stop(); self.player.parts = None; self.pbar.has_b(False); self.pbar.wave.set_env(None, None, 0)
        self.spec.set_curves([], self.spec.note); self.prev_note.setText("")
        for m in (self.m_lufs, self.m_dev, self.m_width, self.m_parts): m.set("—")
        self.fill_analysis()
    def mark_stale(self, *a):
        if self.preview: self.prev_note.setText("Einstellungen geändert – Vorschau neu berechnen"); self.prev_note.setStyleSheet("color:%s;" % C["amber"])
    def _session_tracks(self, log, progress, cancel):
        """Loaded tracks of the current source (cached while the file list does not change)."""
        if self.mode == "tracks":
            key = ("tracks", tuple(self.track_files))
            if self.session is None or self.session[0] != key:
                log("Lade %d Spuren …" % len(self.track_files)); tracks, sr = mx.load_tracks(self.track_files, log=log); self.session = (key, tracks, sr, None)
            key_, tracks, sr, _ = self.session
            for t, r in zip(tracks, self.roles): t["role"] = r
            return tracks, sr, list(range(len(tracks))), None
        key = ("song", self.cur_song)
        if self.session is None or self.session[0] != key:
            tracks, sr, x = mx.song_parts(self.cur_song, log=log, progress=progress, cancel=cancel); self.session = (key, tracks, sr, x)
        key_, tracks, sr, x = self.session
        order = mx.ROLES+["rest"]
        return tracks, sr, [order.index(t["role"]) for t in tracks], x
    def make_preview(self):
        if self._busy: return
        if self.mode == "tracks" and not self.track_files: QMessageBox.information(self, "Vorschau", "Bitte zuerst Spuren hinzufügen."); return
        if self.mode == "song":
            if not self.cur_song: QMessageBox.information(self, "Vorschau", "Bitte einen Song hinzufügen und auswählen."); return
            if not mc.separation_available(): QMessageBox.information(self, "Vorschau", "Die KI-Trennung ist in dieser Version nicht installiert."); return
        prof = self.profile(); kw = self.params(); ev = threading.Event(); self.cancel_ev = ev; self._busy = True
        chans_now = [dict(self._ch(i)) for i in range(len(self.strips))]
        self.bprev.setEnabled(False); self.prev_note.setStyleSheet(""); self.prev_note.setText("Berechne …"); self.player.stop()
        def job(b):
            sep = self.mode == "song"
            tracks, sr, strip_of, x_song = self._session_tracks(b.log.emit, (lambda f: b.progress.emit(0.5*f)) if sep else None, ev)
            chans = [dict(chans_now[j]) for j in strip_of]
            base = 0.5 if sep and self.session and x_song is not None else 0.0
            res = mx.render_session(tracks, sr, prof, chans, log=b.log.emit, progress=lambda f: b.progress.emit(base+(0.97-base)*f), cancel=ev, **kw)
            raw = x_song if x_song is not None else np.sum([t["x"].astype(np.float64) for t in tracks], axis=0)
            mix = mx.mixdown(res["parts"], chans, tracks); tp = mc.true_peak(mix, sr); gain = 10**(kw["peak_db"]/20)/max(tp, 1e-9); mix *= gain
            rep, L = mx.balance_report(res, prof, tracks, chans)
            specs = {}
            for r in res["roles"]:
                idx = [i for i, t in enumerate(tracks) if t["role"] == r]
                specs[r] = (mc.smooth_spectrum(np.sum([tracks[i]["x"] for i in idx], axis=0).astype(np.float64), sr),
                            mc.smooth_spectrum(np.sum([res["parts"][i] for i in idx], axis=0).astype(np.float64), sr))
            ga = 10**(kw["peak_db"]/20)/max(mc.true_peak(raw, sr), 1e-9)
            return dict(res=res, tracks=tracks, sr=sr, channels=chans, strip_of=strip_of, gain=gain, raw=(raw*ga).astype(np.float32), report=rep,
                        lufs=mc.integrated(mix, sr), lufs_raw=mc.integrated(raw*ga, sr), width=mc.width_db(mix, sr), spec_mix=mc.smooth_spectrum(mix, sr),
                        spec_raw=mc.smooth_spectrum(raw, sr), env_raw=mc.envelope_preview(raw*ga), env_mix=mc.envelope_preview(mix), specs=specs, prof=prof)
        def done(pv):
            self._busy = False; self.bprev.setEnabled(True); self.preview = pv
            self.player.load(pv["raw"], pv["sr"]); self.player.set_parts(pv["res"]["parts"], self.live_gains()); self.apply_match()
            self.pbar.has_b(True); self.pbar.ab.set("b"); self.pbar._ab("b"); self.pbar.wave.set_env(pv["env_raw"], pv["env_mix"], len(pv["raw"])/pv["sr"]); self.pbar._tick(0)
            self.show_results(); self.prev_note.setStyleSheet("color:%s;" % C["ok"]); self.prev_note.setText("Vorschau aktuell – Fader wirken live")
            self.out.status.setText("Vorschau berechnet: %.1f LUFS, Spitze %.1f dBTP." % (pv["lufs"], self.s_peak.value()))
            if self.mode == "song": self.set_song_status(self.cur_song, "getrennt", C["muted"])
        def fail(m):
            self._busy = False; self.bprev.setEnabled(True); self.prev_note.setStyleSheet("color:%s;" % C["err"]); self.prev_note.setText(m)
        def prog(f): self.prev_note.setText("Trenne Song … %d %%" % int(f/0.5*100) if (self.mode == "song" and f < 0.5 and (self.session is None or self.session[0][1] != self.cur_song)) else "Berechne … %d %%" % int(f*100))
        run_bg(self, job, done, fail, on_log=self.out.write, on_prog=prog)
    def apply_match(self):
        pv = self.preview
        if not pv or not self.pbar.match.isChecked(): self.player.set_gains(1, 1); return
        la, lb = pv["lufs_raw"], pv["lufs"]; self.player.set_gains(10**(min(0, lb-la)/20), 10**(min(0, la-lb)/20))
    def show_results(self):
        pv = self.preview
        if not pv: return
        rep = pv["report"]; devs = [abs(b["rel"]-b["ref"]) for b in rep if b.get("rel") is not None and b.get("ref") is not None and not b["absent"]]
        self.m_lufs.set("%.1f LUFS" % pv["lufs"], "Spitze %.1f dBTP" % self.s_peak.value(), C["acc"])
        self.m_dev.set("%.1f LU" % float(np.mean(devs)) if devs else "—", "Ø zur Referenz" if devs else "keine Referenz", (C["ok"] if devs and np.mean(devs) < 1.0 else C["warn"]) if devs else None)
        self.m_width.set("%.1f dB" % pv["width"], "", C["acc"])
        act = mx.active_mask(pv["channels"]); self.m_parts.set("%d / %d" % (sum(act), len(act)), "%d Rollen" % len([r for r in pv["res"]["roles"] if r != "rest"]))
        self.fill_analysis(rep); self.show_channel_spec()
    def show_channel_spec(self):
        pv = self.preview
        if not pv: return
        prof = pv["prof"]; role = None
        if self.sel is not None:
            defs = self.strip_defs()
            if self.sel < len(defs): role = defs[self.sel][1]
        if role in pv["specs"]:
            before, after = pv["specs"][role]; curves = []
            if prof and role in prof["roles"]: curves.append(("Referenz · " + mx.ROLE_DE[role], prof["roles"][role]["spec"], C["amber"], Qt.DashLine, 1.6))
            curves += [("vorher", before, C["muted"], Qt.SolidLine, 1.4), ("gemischt", after, C["acc"], Qt.SolidLine, 2.2)]
            self.spec.set_curves(curves, "Rolle %s · +3 dB/Oktave geneigt" % mx.ROLE_DE[role])
        else:
            curves = []
            if prof and prof.get("master"): curves.append(("Referenz-Mix", prof["master"]["spec"], C["amber"], Qt.DashLine, 1.6))
            curves += [("Rohmix", pv["spec_raw"], C["muted"], Qt.SolidLine, 1.4), ("Mix", pv["spec_mix"], C["acc"], Qt.SolidLine, 2.2)]
            self.spec.set_curves(curves, "Summe · +3 dB/Oktave geneigt")
    def refresh_report(self):
        """After fader moves: re-measure the balance table in the background."""
        pv = self.preview
        if not pv or self._busy: return
        chans = [dict(c) for c in pv["channels"]]
        def job(b): return mx.balance_report(pv["res"], pv["prof"], pv["tracks"], chans)
        def done(r):
            if self.preview is pv: pv["report"] = r[0]; self.fill_analysis(r[0])
        run_bg(self, job, done, lambda m: None)
    # ---------------------------------------------------------------- export
    def start(self):
        out = self.out.dir.text().strip()
        if not out: QMessageBox.information(self, "Mixing", "Bitte einen Ausgabeordner wählen."); return
        if self.mode == "tracks" and not self.track_files: QMessageBox.information(self, "Mixing", "Bitte zuerst Spuren hinzufügen."); return
        if self.mode == "song" and not self.song_files: QMessageBox.information(self, "Mixing", "Bitte zuerst Songs hinzufügen."); return
        if self.mode == "song" and not mc.separation_available(): QMessageBox.information(self, "Mixing", "Die KI-Trennung ist in dieser Version nicht installiert."); return
        master, mkw = self.master_choice()
        if self.do_master.isChecked() and master is None: QMessageBox.information(self, "Mixing", "Das gewählte Mastering-Profil ist nicht verfügbar."); return
        prof = self.profile(); kw = self.params(); bits = int(self.out.bits.value()); save = self.save_parts.isChecked()
        ev = threading.Event(); self.cancel_ev = ev; self.out.busy(True); self.out.prog.setValue(0); mode = self.mode
        chans_now = [dict(self._ch(i)) for i in range(len(self.strips))]; files = list(self.song_files if mode == "song" else self.track_files)
        name = self.song_name.text().strip() or "Mix"; roles = list(self.roles)
        self.out.write("— Mix%s · %s" % (" nach „%s“" % prof["name"] if prof else " ohne Referenz", "%d Song(s)" % len(files) if mode == "song" else "%d Spuren" % len(files)))
        def job(b):
            taken = set(); rows = []; results = []
            if mode == "tracks":
                tracks, sr = mx.load_tracks(files, log=b.log.emit)
                for t, r in zip(tracks, roles): t["role"] = r
                res, outs = mx.process_mix(tracks, sr, name, out, prof, chans_now, master=master, master_kw=mkw, bits=bits, save_parts=save, log=b.log.emit,
                                           progress=b.progress.emit, cancel=ev, taken=taken, protect=files, **kw)
                rows.append((name, res, prof, tracks, chans_now)); results.append(outs)
            else:
                order = mx.ROLES+["rest"]; n = len(files)
                for i, p in enumerate(files):
                    if ev.is_set(): raise mc.Cancelled()
                    b.item.emit((p, "trennt …", C["acc"])); b.log.emit(os.path.basename(p))
                    try:
                        tracks, sr, _ = mx.song_parts(p, log=b.log.emit, progress=lambda f, i=i: b.progress.emit((i+0.5*f)/n), cancel=ev)
                        chans = [dict(chans_now[order.index(t["role"])]) for t in tracks]
                        b.item.emit((p, "mischt …", C["acc"]))
                        song = os.path.splitext(os.path.basename(p))[0]
                        res, outs = mx.process_mix(tracks, sr, song, out, prof, chans, master=master, master_kw=mkw, bits=bits, save_parts=save, log=b.log.emit,
                                                   progress=lambda f, i=i: b.progress.emit((i+0.5+0.5*f)/n), cancel=ev, taken=taken, protect=files, **kw)
                        rows.append((song, res, prof, tracks, chans)); results.append(outs)
                        b.item.emit((p, "✓  Mix%s" % (" + Master" if outs["master"] else ""), C["ok"]))
                        del tracks, res
                    except mc.Cancelled: raise
                    except Exception as e:
                        b.log.emit("FEHLER %s: %s" % (os.path.basename(p), e)); b.item.emit((p, "Fehler", C["err"]))
            if rows: b.log.emit("Protokoll: %s" % mx.write_mix_protocol(rows, out))
            return results
        def done(results):
            self.out.busy(False); self.out.prog.setValue(1000)
            self.out.status.setText("Fertig: %d Mix(e)%s → %s" % (len(results), " mit Master" if master is not None else "", out))
            self.win.notify("Mix fertig", "%d Mix(e) erstellt." % len(results))
            if results and self.win.settings.get("open_after", True): open_folder(out)
        def fail(m):
            self.out.busy(False); self.out.write(m)
            for p in files:
                if mode == "song" and p in self.song_files and self.stable.item(self.song_files.index(p), 3).text() in ("trennt …", "mischt …"): self.set_song_status(p, "abgebrochen", C["warn"])
        run_bg(self, job, done, fail, on_log=self.out.write, on_prog=lambda f: self.out.prog.setValue(int(f*1000)), on_item=lambda t: self.set_song_status(*t))
    def stop(self):
        if self.cancel_ev: self.cancel_ev.set(); self.out.cancel.setEnabled(False); self.out.status.setText("Breche ab …")
    # ---------------------------------------------------------------- persistence
    def state(self):
        return dict(mode=self.mode, profile=self.prof.currentData(), sliders={w.lab.text(): w.value() for w in (self.s_bal, self.s_tone, self.s_dyn, self.s_tr, self.s_wid, self.s_fx, self.s_maxeq, self.s_maxg, self.s_peak)},
                    master=self.do_master.isChecked(), mprof=self.mprof.currentData(), preset=self.mpreset.currentData(), save_parts=self.save_parts.isChecked(),
                    song_ch=self.song_ch, out=self.out.dir.text(), bits=self.out.bits.value())
    def restore(self, d):
        if not d: return
        i = self.prof.findData(d.get("profile"))
        if d.get("profile") is not None and i >= 0: self.prof.setCurrentIndex(i)
        by = {w.lab.text(): w for w in (self.s_bal, self.s_tone, self.s_dyn, self.s_tr, self.s_wid, self.s_fx, self.s_maxeq, self.s_maxg, self.s_peak)}
        for k, v in d.get("sliders", {}).items():
            if k in by: by[k].set(v)
        self.do_master.setChecked(bool(d.get("master"))); self.save_parts.setChecked(bool(d.get("save_parts")))
        j = self.mprof.findData(mc.RENAMED.get(d.get("mprof"), d.get("mprof"))); self.mprof.setCurrentIndex(max(0, j)); j = self.mpreset.findData(d.get("preset")); self.mpreset.setCurrentIndex(max(0, j))
        self.song_ch = {k: {**mx.CHANNEL_DEFAULTS, **v} for k, v in (d.get("song_ch") or {}).items()}
        self.out.dir.setText(d.get("out", self.out.dir.text())); self.out.bits.set(d.get("bits", "24"))
        self.mode = None; self.set_mode(d.get("mode", "tracks"))

# ---------------------------------------------------------------- Mastering
class MasterPage(Page):
    def __init__(self, win):
        super().__init__("Mastering", "Ganze Songs an einen Referenzklang angleichen – Spektrum, Breite, Dynamik und Lautheit. Mit Vorschau und A/B-Vergleich.")
        self.win = win; self.files = []; self.info = {}; self.cur = None; self.cur_x = None; self.preview = None; self.cancel_ev = None
        self.player = Player(); self._an_queue = []; self._an_busy = False
        body = QHBoxLayout(); body.setSpacing(16); self.v.addLayout(body, 1)
        # ---- left: files + analysis
        lsa, left = scroll_column(); body.addWidget(lsa, 1)
        fc = Card("Titel", right=None)
        self.table = FileTable(["Titel", "Dauer", "LUFS", "True Peak", "Status"], [0, 64, 64, 96, 190]); self.table.auto_height(3, 7)
        self.table.dropped.connect(self.add_files); self.table.itemSelectionChanged.connect(self.on_select); self.table.parent_remove = self.remove_sel
        fc.add(self.table)
        fc.add(row(btn("Dateien", I["add"], slot=self.pick_files), btn("Ordner", I["folder"], slot=self.pick_folder),
                   btn("Entfernen", I["delete"], kind="ghost", slot=self.remove_sel), btn("Alle entfernen", None, kind="ghost", slot=self.clear), "stretch"))
        left.addWidget(fc, 0)
        ac = Card("Analyse & Vorschau", help_key="preview")
        self.spec = SpectrumView(); ac.add(self.spec)
        mrow = QHBoxLayout(); mrow.setSpacing(8)
        self.m_lufs = Meter("Lautheit", "Integrierte Lautheit (LUFS)"); self.m_tp = Meter("True Peak"); self.m_lra = Meter("Dynamik (LRA)", "Loudness Range in LU")
        self.m_width = Meter("Stereobreite", "Seitenanteil über 200 Hz"); self.m_lim = Meter("Limiter", "Maximale Pegelreduktion des Limiters")
        for m in (self.m_lufs, self.m_tp, self.m_lra, self.m_width, self.m_lim): mrow.addWidget(m)
        ac.add(mrow)
        self.pbar = PlayerBar(self.player); ac.add(self.pbar); self.pbar.match.toggled.connect(lambda *_: self.apply_match())
        self.bprev = btn("Vorschau berechnen", I["preview"], slot=self.make_preview)
        self.prev_note = QLabel(""); self.prev_note.setObjectName("faint")
        ac.add(row(self.bprev, self.prev_note, "stretch"))
        left.addWidget(ac, 0); left.addStretch(1)
        # ---- right: settings
        sa, rl = scroll_column(446); body.addWidget(sa)
        # target
        self.prof = QComboBox(); self.prof.setMinimumWidth(180); self.prof.currentTextChanged.connect(self.on_profile)
        pm = QPushButton("…"); pm.setFixedWidth(36); pm.setToolTip("Profile verwalten")
        menu = QMenu(pm); menu.addAction("Neues Profil anlernen …", self.learn_profile); menu.addAction("Profil löschen", self.delete_profile)
        menu.addSeparator(); menu.addAction("Profilordner öffnen", lambda: (os.makedirs(mc.USER_PROFILE_DIR, exist_ok=True), open_folder(mc.USER_PROFILE_DIR)))
        pm.setMenu(menu); pm.setStyleSheet("QPushButton::menu-indicator{width:0;}")
        tc = Card("Ziel")
        tc.add(row(QLabel("Profil"), self.prof, pm, HelpDot("profil")))
        self.prof_info = QLabel(""); self.prof_info.setObjectName("faint"); self.prof_info.setWordWrap(True); tc.add(self.prof_info)
        self.preset = QComboBox()
        for k, d in mc.PRESETS.items(): self.preset.addItem(d["label"], k)
        self.preset.addItem("Benutzerdefiniert", "custom"); self.preset.currentIndexChanged.connect(self.on_preset)
        tc.add(row(QLabel("Plattform"), self.preset, HelpDot("preset")))
        rl.addWidget(tc)
        # sound
        sc = Card("Klang")
        self.s_strength = SliderRow("Angleich-Stärke", 0, 1, 1.0, 0.01, " %", "strength", 0, 100)
        self.s_warm = SliderRow("Wärme (100 Hz)", -4, 4, 0, 0.1, " dB", "warm")
        self.s_air = SliderRow("Luft (10 kHz)", -4, 4, 0, 0.1, " dB", "air")
        for w in (self.s_strength, self.s_warm, self.s_air): sc.add(w)
        self.wmode = Segmented([("profil", "Wie Profil"), ("manuell", "Manuell"), ("aus", "Aus")], "profil")
        sc.add(row(QLabel("Stereobreite"), self.wmode, HelpDot("width")))
        self.s_width = SliderRow("max. Änderung", 0, 6, 4, 0.1, " dB", None); sc.add(self.s_width)
        self.wmode.changed.connect(self.on_wmode)
        rl.addWidget(sc)
        # dynamics
        dc = Card("Dynamik & Lautheit")
        self.s_clip = SliderRow("Soft-Clipper", 0, 4, 1.0, 0.1, " dB", "clip")
        self.s_glue = SliderRow("Glue-Kompressor", 0, 1, 0, 0.01, " %", "glue", 0, 100)
        self.s_rel = SliderRow("Limiter-Release", 30, 400, 120, 1, " ms", "release", 0)
        for w in (self.s_clip, self.s_glue, self.s_rel): dc.add(w)
        self.peak = Segmented([("sample", "Sample-Peak"), ("true", "True Peak")], "true")
        dc.add(row(QLabel("Peak-Modus"), self.peak, HelpDot("peak")))
        self.s_lufs = SliderRow("Ziel-Lautheit", -20, -6, -14, 0.1, " LUFS", "lufs")
        self.s_ceil = SliderRow("Obergrenze", -3, 0, -1, 0.1, " dB", "ceiling")
        dc.add(self.s_lufs); dc.add(self.s_ceil)
        rl.addWidget(dc)
        # stems
        self.stem_on = QCheckBox("aktiv")
        stc = Card("Stem-Balance", help_key="stems", right=self.stem_on)
        self.s_st = {}
        for k, lab in (("vocals", "Gesang"), ("drums", "Drums"), ("bass", "Bass"), ("other", "Instrumente")):
            self.s_st[k] = SliderRow(lab, -6, 6, 0, 0.1, " dB"); stc.add(self.s_st[k])
        self.stem_note = QLabel(""); self.stem_note.setObjectName("faint"); self.stem_note.setWordWrap(True); stc.add(self.stem_note)
        self.stem_on.toggled.connect(self.on_stem_on)
        rl.addWidget(stc)
        # expert
        ec = Card("Experte", collapsible=True, collapsed=True)
        self.s_maxeq = SliderRow("max. EQ-Korrektur", 2, 12, 9, 0.1, " dB", "maxeq")
        self.s_lo = SliderRow("Angleich ab", 20, 200, 35, 1, " Hz", "eqrange", 0)
        self.s_hi = SliderRow("Angleich bis", 6000, 20000, 16000, 100, " Hz", "eqrange", 0)
        self.s_pfull = SliderRow("Präsenz voll bis", 0, 9, 4, 0.1, " dB", "presence")
        self.s_pcap = SliderRow("Präsenz-Deckel", 0, 12, 7, 0.1, " dB", "presence")
        self.s_dh = SliderRow("De-Harsh", 0, 1, 0.5, 0.01, " %", "deharsh", 0, 100)
        self.s_bm = SliderRow("Bass mono unter", 0, 250, 150, 1, " Hz", "bassmono", 0)
        for w in (self.s_maxeq, self.s_lo, self.s_hi, self.s_pfull, self.s_pcap, self.s_dh, self.s_bm): ec.add(w)
        self.declip = QCheckBox("De-Clipping (automatisch bei Clipping)"); self.declip.setChecked(True); ec.add(row(self.declip, HelpDot("declip"), "stretch"))
        ec.add(row(btn("Alles auf Standard", I["refresh"], kind="ghost", slot=self.reset), "stretch"))
        rl.addWidget(ec); rl.addStretch(1)
        # ---- bottom bar
        self.out = OutputBar(os.path.join(os.path.expanduser("~"), "Desktop", "Master-Ausgabe"), "Alle mastern")
        self.out.primary.clicked.connect(self.start); self.out.cancel.clicked.connect(self.stop)
        self.v.addWidget(self.out)
        # wiring
        for w in self.sliders(): w.changed.connect(self.mark_stale)
        for s in (self.wmode, self.peak): s.changed.connect(self.mark_stale)
        self.declip.toggled.connect(self.mark_stale); self.stem_on.toggled.connect(self.mark_stale)
        self.reload_profiles(); self.on_preset(); self.on_wmode("profil"); self.on_stem_on(False)
    def sliders(self):
        return [self.s_strength, self.s_warm, self.s_air, self.s_width, self.s_clip, self.s_glue, self.s_rel, self.s_lufs, self.s_ceil,
                self.s_maxeq, self.s_lo, self.s_hi, self.s_pfull, self.s_pcap, self.s_dh, self.s_bm]+list(self.s_st.values())
    # ---- profiles
    def reload_profiles(self, select=None):
        cur = mc.RENAMED.get(select or self.prof.currentText(), select or self.prof.currentText()); self.prof.blockSignals(True); self.prof.clear(); self.prof.addItems(mc.list_profiles())
        i = self.prof.findText(cur); self.prof.setCurrentIndex(max(0, i)); self.prof.blockSignals(False); self.on_profile()
    def profile(self):
        try: return mc.load_profile(self.prof.currentText())
        except Exception: return None
    def on_profile(self, *a):
        pr = self.profile()
        if pr: self.prof_info.setText("%.1f LUFS · Breite %.1f dB · %s · aus %s Titel(n)" % (pr["lufs"], pr["width"], "Sample-Peak" if pr.get("peak_mode") == "sample" else "True Peak", pr.get("n", "?") or "Zielkurve"))
        self.preset.setItemText(0, "Wie Profil  (%.1f LUFS)" % pr["lufs"] if pr else "Wie Profil")
        self.on_preset(); self.mark_stale(); self.refresh_spec()
    def on_preset(self, *a):
        k = self.preset.currentData(); custom = k == "custom"; pr = self.profile()
        if not custom:
            d = mc.PRESETS[k]
            lufs = d["lufs"] if d["lufs"] is not None else (pr["lufs"] if pr else -14)
            mode = d["peak_mode"] or (pr.get("peak_mode", "true") if pr else "true")
            ceil = d["ceiling"] if d["ceiling"] is not None else (-0.1 if mode == "sample" else -1.0)
            for w, val in ((self.s_lufs, lufs), (self.s_ceil, ceil)): w.set(val)
            self.peak.set(mode)
        for w in (self.s_lufs, self.s_ceil, self.peak): w.setEnabled(custom)
        self.mark_stale()
    def on_wmode(self, k):
        self.s_width.lab.setText("max. Änderung" if k == "profil" else "Breite")
        if k == "manuell": self.s_width.lo = -6.0; self.s_width.sl.setRange(0, 120); self.s_width.sp.setRange(-6, 6); self.s_width.set(0)
        else: self.s_width.lo = 0.0; self.s_width.sl.setRange(0, 60); self.s_width.sp.setRange(0, 6); self.s_width.set(4)
        self.s_width.setEnabled(k != "aus")
    def on_stem_on(self, on):
        ok = mc.separation_available()
        for w in self.s_st.values(): w.setEnabled(on and ok)
        if not ok: self.stem_on.setEnabled(False); self.stem_note.setText("In dieser Version ist die KI-Trennung nicht installiert (Vollversion nötig).")
        else:
            plan = mc.sep_plan("auto", refresh=False)
            self.stem_note.setText(("Trennung: %s · %s" % (mc.SEP_MODELS[plan["model"]]["label"].split(" · ")[0], plan["message"])) if on else "Aus: der Mix bleibt unverändert.")
    def learn_profile(self):
        d = LearnProfileDialog(self)
        if d.exec() and d.result_name: self.reload_profiles(d.result_name)
    def delete_profile(self):
        n = self.prof.currentText()
        if n in mc.BUILTIN: QMessageBox.information(self, "Standardprofil", "„%s“ ist ein Standardprofil und bleibt erhalten." % n); return
        if QMessageBox.question(self, "Profil löschen", "Profil „%s“ wirklich löschen?" % n) != QMessageBox.Yes: return
        try: mc.delete_profile(n); self.reload_profiles()
        except Exception as e: QMessageBox.warning(self, "Profil löschen", str(e))
    def reset(self):
        for w in self.sliders():
            if w not in self.s_st.values(): w.set(w.default)
        self.wmode.set("profil"); self.on_wmode("profil"); self.declip.setChecked(True); self.preset.setCurrentIndex(0)
    # ---- params
    def params(self):
        pk = self.preset.currentData()
        custom = pk == "custom"; d = mc.PRESETS.get(pk, {})
        kw = dict(strength=self.s_strength.value(), low_shelf_db=self.s_warm.value(), high_shelf_db=self.s_air.value(),
                  width_mode=self.wmode.value(), width_db_manual=self.s_width.value() if self.wmode.value() == "manuell" else 0.0,
                  width_max=self.s_width.value() if self.wmode.value() == "profil" else 4.0,
                  clip_db=self.s_clip.value(), glue=self.s_glue.value(), release_ms=self.s_rel.value(),
                  max_eq=self.s_maxeq.value(), eq_lo=self.s_lo.value(), eq_hi=self.s_hi.value(), presence_full=self.s_pfull.value(), presence_cap=self.s_pcap.value(),
                  deharsh_scale=self.s_dh.value(), bass_mono_hz=self.s_bm.value(), do_declip=self.declip.isChecked(), out_bits=int(self.out.bits.value()),
                  stem_gains={k: w.value() for k, w in self.s_st.items()} if self.stem_on.isChecked() else None)
        if custom: kw.update(target_lufs=self.s_lufs.value(), peak_mode=self.peak.value(), ceiling_db=self.s_ceil.value())
        else: kw.update(target_lufs=d.get("lufs"), peak_mode=d.get("peak_mode"), ceiling_db=d.get("ceiling"))
        return kw
    # ---- files
    def pick_files(self):
        fs, _ = QFileDialog.getOpenFileNames(self, "Audiodateien", self.win.last_dir, "Audio (*.wav *.flac *.aif *.aiff *.ogg *.mp3)")
        if fs: self.win.last_dir = os.path.dirname(fs[0]); self.add_files(fs)
    def pick_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Ordner mit Titeln", self.win.last_dir)
        if d: self.win.last_dir = d; self.add_files(mc.audio_files_in(d))
    def add_files(self, paths):
        known = {os.path.normcase(os.path.abspath(p)) for p in self.files}; first = None
        for p in paths:
            p = os.path.normpath(p)
            if os.path.normcase(os.path.abspath(p)) in known: continue
            known.add(os.path.normcase(os.path.abspath(p))); self.files.append(p); r = self.table.rowCount(); self.table.insertRow(r)
            it = QTableWidgetItem(os.path.splitext(os.path.basename(p))[0]); it.setToolTip(p); self.table.setItem(r, 0, it)
            for c in range(1, 5): self.table.setItem(r, c, QTableWidgetItem("…" if c < 4 else "wird analysiert"))
            self._an_queue.append(p); first = first if first is not None else r
        self.update_count(); self._analyse_next()
        if first is not None and self.cur is None: self.table.selectRow(first)
    def update_count(self):
        set_btn_text(self.out.primary, "Alle mastern (%d)" % len(self.files) if self.files else "Alle mastern")
    def _row(self, path):
        try: return self.files.index(path)
        except ValueError: return -1
    def set_cell(self, path, col, text, color=None):
        r = self._row(path)
        if r < 0: return
        it = self.table.item(r, col); it.setText(text)
        it.setForeground(QColor(color) if color else QColor(C["text"] if col == 0 else C["muted"]))
        if col in (1, 2, 3): it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    def _analyse_next(self):
        if self._an_busy or not self._an_queue: return
        p = self._an_queue.pop(0)
        if p not in self.files: return self._analyse_next()
        self._an_busy = True
        def job(b):
            x, sr, _ = mc.load_audio(p)
            return p, dict(lufs=mc.integrated(x, sr), tp=mc.db(mc.true_peak(x, sr)), lra=mc.lra(x, sr), width=mc.width_db(x, sr),
                           spec=mc.smooth_spectrum(x, sr), dur=len(x)/sr, clips=mc.clip_runs(x), env=mc.envelope_preview(x))
        def done(res):
            p_, inf = res; self.info[p_] = inf; self._an_busy = False
            self.set_cell(p_, 1, fmt_time(inf["dur"])); self.set_cell(p_, 2, "%.1f" % inf["lufs"]); self.set_cell(p_, 3, "%+.1f dBTP" % inf["tp"])
            self.set_cell(p_, 4, "bereit" if not inf["clips"] > 20 else "bereit · Clipping", C["muted"] if not inf["clips"] > 20 else C["warn"])
            if p_ == self.cur: self.show_info()
            self._analyse_next()
        def fail(msg):
            self._an_busy = False; self.set_cell(p, 4, "Fehler: " + msg, C["err"]); self._analyse_next()
        run_bg(self, job, done, fail)
    def remove_sel(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        for r in rows:
            p = self.files.pop(r); self.table.removeRow(r); self.info.pop(p, None)
            if p == self.cur: self.cur = None; self.cur_x = None; self.preview = None; self.player.stop(); self.pbar.has_b(False); self.show_info()
        self.update_count()
    def clear(self):
        self.files.clear(); self.info.clear(); self.table.setRowCount(0); self.cur = None; self.player.stop(); self.show_info(); self.update_count()
    def on_select(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        if not rows: return
        p = self.files[rows[0]]
        if p == self.cur: return
        self.cur = p; self.cur_x = None; self.preview = None; self.player.stop(); self.pbar.has_b(False); self.pbar.wave.set_env(None, None, 0)
        self.pbar.wave.msg = "Lade …"; self.show_info()
        def job(b):
            x, sr, _ = mc.load_audio(p); return p, x, sr
        def done(res):
            p_, x, sr = res
            if p_ != self.cur: return
            self.cur_x = (x, sr); self.player.load(x, sr); self.pbar._tick(0.0); self.show_info()
        run_bg(self, job, done, lambda m: self.pbar.wave.set_env(None, None, 0))
    def show_info(self):
        inf = self.info.get(self.cur) if self.cur else None
        if not inf:
            for m in (self.m_lufs, self.m_tp, self.m_lra, self.m_width, self.m_lim): m.set("—")
            self.spec.set_curves([], ""); self.pbar.wave.set_env(None, None, 0); return
        pv = self.preview
        if pv:
            a = pv["after"]
            self.m_lufs.set("%.1f LUFS" % a["lufs"], "statt %.1f" % inf["lufs"], C["acc"])
            self.m_tp.set("%+.1f dBTP" % a["tp"], "statt %+.1f" % inf["tp"], C["err"] if a["tp"] > 0.0 else C["acc"])
            self.m_lra.set("%.1f LU" % a["lra"], "statt %.1f" % inf["lra"], C["acc"])
            self.m_width.set("%.1f dB" % a["width"], "statt %.1f" % inf["width"], C["acc"])
            self.m_lim.set("%.1f dB" % pv["info"]["limiter_gr"], "max.", C["acc"])
        else:
            self.m_lufs.set("%.1f LUFS" % inf["lufs"], "Original"); self.m_tp.set("%+.1f dBTP" % inf["tp"], "Original")
            self.m_lra.set("%.1f LU" % inf["lra"], "Original"); self.m_width.set("%.1f dB" % inf["width"], "Original"); self.m_lim.set("—", "")
        self.pbar.wave.set_env(inf["env"], pv["env"] if pv else None, inf["dur"])
        self.refresh_spec()
    def refresh_spec(self):
        inf = self.info.get(self.cur) if self.cur else None; pr = self.profile()
        if not inf: self.spec.set_curves([], ""); return
        curves = []
        if pr is not None: curves.append(("Profil", pr["spec"], C["amber"], Qt.DashLine, 1.6))
        curves.append(("Original", inf["spec"], C["muted"], Qt.SolidLine, 1.4))
        if self.preview: curves.append(("Master", self.preview["spec"], C["acc"], Qt.SolidLine, 2.2))
        self.spec.set_curves(curves, "Langzeitspektrum · +3 dB/Oktave geneigt")
    def mark_stale(self, *a):
        if self.preview: self.prev_note.setText("Einstellungen geändert – Vorschau neu berechnen"); self.prev_note.setStyleSheet("color:%s;" % C["amber"])
    def make_preview(self):
        if not self.cur: QMessageBox.information(self, "Vorschau", "Bitte zuerst einen Titel auswählen."); return
        if self.cur_x is None: QMessageBox.information(self, "Vorschau", "Der Titel wird noch geladen – bitte einen Moment warten."); return
        pr = self.profile()
        if pr is None: return
        kw = self.params(); p = self.cur; x, sr = self.cur_x; ev = threading.Event(); self.cancel_ev = ev
        self.bprev.setEnabled(False); self.prev_note.setStyleSheet(""); self.prev_note.setText("Berechne …")
        def job(b):
            stems = None
            if kw.get("stem_gains") and any(abs(v) >= 0.05 for v in kw["stem_gains"].values()):
                b.log.emit("Stems werden getrennt …"); stems = mc.mix_stems(p, sr, len(x), log=b.log.emit, progress=lambda f: b.progress.emit(0.6*f), cancel=ev)
            base = 0.6 if stems is not None else 0.0
            y, info = mc.render_master(x, sr, pr, log=b.log.emit, stems=stems, cancel=ev, progress=lambda f: b.progress.emit(base+(1-base)*f), **kw)
            after = dict(lufs=mc.integrated(y, sr), tp=mc.db(mc.true_peak(y, sr)), lra=mc.lra(y, sr), width=mc.width_db(y, sr))
            return p, y, dict(info=info, after=after, spec=mc.smooth_spectrum(y, sr), env=mc.envelope_preview(y))
        def done(res):
            self.bprev.setEnabled(True); p_, y, pv = res
            if p_ != self.cur: return
            self.preview = pv; self.player.set_b(y)
            la, lb = self.info[p_]["lufs"], pv["after"]["lufs"]
            self.apply_match(); self.pbar.has_b(True); self.pbar.ab.set("b"); self.pbar._ab("b")
            self.prev_note.setStyleSheet("color:%s;" % C["ok"]); self.prev_note.setText("Vorschau aktuell · %+.1f dB lauter als das Original" % (lb-la))
            self.show_info()
        def fail(m): self.bprev.setEnabled(True); self.prev_note.setStyleSheet("color:%s;" % C["err"]); self.prev_note.setText(m)
        def prog(f): self.prev_note.setText("Berechne … %d %%" % int(f*100) if f < 0.95 else "Messe Ergebnis …")
        run_bg(self, job, done, fail, on_log=self.out.write, on_prog=prog)
    def apply_match(self):
        if not self.preview or self.cur not in self.info: self.player.set_gains(1, 1); return
        la, lb = self.info[self.cur]["lufs"], self.preview["after"]["lufs"]
        if self.pbar.match.isChecked(): self.player.set_gains(10**(min(0, lb-la)/20), 10**(min(0, la-lb)/20))
        else: self.player.set_gains(1, 1)
    # ---- batch
    def start(self):
        if not self.files: QMessageBox.information(self, "Mastering", "Bitte zuerst Titel hinzufügen (Dateien hierher ziehen)."); return
        pr = self.profile()
        if pr is None: QMessageBox.information(self, "Mastering", "Kein Profil vorhanden."); return
        out = self.out.dir.text().strip()
        if not out: QMessageBox.information(self, "Mastering", "Bitte einen Ausgabeordner wählen."); return
        kw = self.params(); files = list(self.files); ev = threading.Event(); self.cancel_ev = ev; self.out.busy(True); self.out.prog.setValue(0)
        for p in files: self.set_cell(p, 4, "wartet", C["muted"])
        self.out.write("— %s · Ziel %s · %d Titel" % (pr["name"], "%.1f LUFS" % kw["target_lufs"] if kw["target_lufs"] is not None else "wie Profil", len(files)))
        def job(b):
            rows = []; taken = set(); n = len(files)
            for i, p in enumerate(files):
                if ev.is_set(): raise mc.Cancelled()
                b.item.emit((p, "läuft …", C["acc"]))
                try:
                    stems = None
                    if kw.get("stem_gains") and any(abs(v) >= 0.05 for v in kw["stem_gains"].values()):
                        x, sr, _ = mc.load_audio(p)
                        stems = mc.mix_stems(p, sr, len(x), log=b.log.emit, cancel=ev, progress=lambda f, i=i: b.progress.emit((i+0.5*f)/n)); del x
                    r = mc.master_file(p, pr, out, log=b.log.emit, stems=stems, taken=taken, cancel=ev, protect=files,
                                       progress=lambda f, i=i: b.progress.emit((i+(0.5 if stems else 0)+f*(0.5 if stems else 1))/n), **kw)
                    rows.append(r); b.item.emit((p, "✓  %.1f LUFS · %+.1f dBTP" % (r["after"]["lufs"], r["after"]["tp"]), C["ok"]))
                except mc.Cancelled: raise
                except Exception as e:
                    b.log.emit("FEHLER %s: %s" % (os.path.basename(p), e)); b.item.emit((p, "Fehler", C["err"]))
                b.progress.emit((i+1)/n)
            if rows: b.log.emit("Protokoll: %s" % mc.write_protocol(rows, out))
            return rows
        def done(rows):
            self.out.busy(False); self.out.prog.setValue(1000)
            self.out.status.setText("Fertig: %d von %d Titel(n) gemastert → %s" % (len(rows), len(files), out))
            self.win.notify("Mastering fertig", "%d Titel gemastert." % len(rows))
            if rows and self.win.settings.get("open_after", True): open_folder(out)
        def fail(m):
            self.out.busy(False); self.out.write(m)
            for p in files:
                r = self._row(p)
                if r >= 0 and self.table.item(r, 4).text() in ("wartet", "läuft …"): self.set_cell(p, 4, "abgebrochen", C["warn"])
        run_bg(self, job, done, fail, on_log=self.out.write, on_prog=lambda f: self.out.prog.setValue(int(f*1000)),
               on_item=lambda t: self.set_cell(t[0], 4, t[1], t[2]))
    def stop(self):
        if self.cancel_ev: self.cancel_ev.set(); self.out.cancel.setEnabled(False); self.out.status.setText("Breche ab …")
    # ---- persistence
    def state(self):
        d = {w.lab.text(): w.value() for w in self.sliders() if w not in self.s_st.values() and w is not self.s_width}
        return dict(sliders=d, profile=self.prof.currentText(), preset=self.preset.currentData(), wmode=self.wmode.value(), width=self.s_width.value(),
                    peak=self.peak.value(), declip=self.declip.isChecked(), out=self.out.dir.text(), bits=self.out.bits.value())
    def restore(self, d):
        if not d: return
        i = self.prof.findText(mc.RENAMED.get(d.get("profile", ""), d.get("profile", "")))
        if i >= 0: self.prof.setCurrentIndex(i)
        by = {w.lab.text(): w for w in self.sliders()}
        for k, v in d.get("sliders", {}).items():
            if k in by: by[k].set(v)
        self.wmode.set(d.get("wmode", "profil")); self.on_wmode(self.wmode.value()); self.s_width.set(d.get("width", 4))
        j = self.preset.findData(d.get("preset", "profil")); self.preset.setCurrentIndex(max(0, j))
        if d.get("preset") == "custom":
            self.peak.set(d.get("peak", "true"))
            by_l = d.get("sliders", {})
            if "Ziel-Lautheit" in by_l: self.s_lufs.set(by_l["Ziel-Lautheit"])
            if "Obergrenze" in by_l: self.s_ceil.set(by_l["Obergrenze"])
        self.declip.setChecked(d.get("declip", True)); self.out.dir.setText(d.get("out", self.out.dir.text())); self.out.bits.set(d.get("bits", "24"))

class BusyAnim(QWidget):
    """Logo-style animation: waveform bars that move like a level meter inside a slowly sweeping loudness ring."""
    def __init__(self, size=112):
        super().__init__(); self.setFixedSize(size, size); self.t0 = time.time(); self.done = False
        self.timer = QTimer(self); self.timer.setInterval(33); self.timer.timeout.connect(self.update)
    def start(self): self.t0 = time.time(); self.done = False; self.timer.start()
    def stop(self, done=True): self.done = done; self.timer.stop(); self.update()
    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); W = self.width(); t = time.time()-self.t0
        r = QRectF(8, 8, W-16, W-16)
        p.setPen(QPen(QColor(255, 255, 255, 22), 7, Qt.SolidLine, Qt.RoundCap)); p.drawArc(r, -45*16, 270*16)
        g = QLinearGradient(r.topLeft(), r.bottomRight()); g.setColorAt(0, QColor("#3fd0dc")); g.setColorAt(0.5, QColor(C["violet"])); g.setColorAt(1, QColor("#f6b336"))
        if self.done: span = 270.0
        else: span = 40+230*(0.5+0.5*math.sin(t*1.6))                  # the lit part of the gauge breathes
        p.setPen(QPen(QBrush(g), 7, Qt.SolidLine, Qt.RoundCap)); p.drawArc(r, int(225*16), int(-span*16))
        heights = [0.26, 0.46, 0.70, 1.00, 0.70, 0.46, 0.26]; n = len(heights); bw = W*0.05; gap = W*0.03
        x0 = W/2-(n*bw+(n-1)*gap)/2; hmax = W*0.40
        for i, h in enumerate(heights):
            if not self.done: h = h*(0.45+0.55*abs(math.sin(t*3.1+i*0.9)))
            hh = max(bw, hmax*h); x = x0+i*(bw+gap)
            c = QColor("#f5b23a") if i == 3 else QColor("#4fd3df")
            p.setPen(Qt.NoPen); p.setBrush(c); p.drawRoundedRect(QRectF(x, W/2-hh/2, bw, hh), bw/2, bw/2)

class BusyPanel(QFrame):
    """Splash-style progress overlay for long jobs: animation, current step, detail line, progress, elapsed/remaining time, log."""
    cancel = Signal()
    def __init__(self, parent, title):
        super().__init__(parent); self.setObjectName("busy"); self.title = title
        self.setStyleSheet("#busy{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #0b111a,stop:1 #0f2f3b);border:1px solid %s;border-radius:16px;}" % C["border2"])
        v = QVBoxLayout(self); v.setContentsMargins(30, 26, 30, 22); v.setSpacing(14)
        top = QHBoxLayout(); top.setSpacing(22); self.anim = BusyAnim(); top.addWidget(self.anim, 0, Qt.AlignTop)
        tv = QVBoxLayout(); tv.setSpacing(4)
        self.h = QLabel(title); self.h.setStyleSheet("font-size:16pt;font-weight:600;background:transparent;")
        self.step = QLabel("Starte …"); self.step.setStyleSheet("font-size:11pt;color:%s;background:transparent;" % C["acc_h"]); self.step.setWordWrap(True)
        self.detail = QLabel(""); self.detail.setStyleSheet("color:%s;background:transparent;" % C["muted"]); self.detail.setWordWrap(True)
        tv.addWidget(self.h); tv.addWidget(self.step); tv.addWidget(self.detail); tv.addStretch(1); top.addLayout(tv, 1); v.addLayout(top)
        self.list_host = QWidget(); self.list_host.setStyleSheet("background:transparent;"); self.list = QVBoxLayout(self.list_host)
        self.list.setContentsMargins(4, 6, 4, 6); self.list.setSpacing(8)
        la = QScrollArea(); la.setWidgetResizable(True); la.setWidget(self.list_host); la.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        v.addWidget(la, 1); self.items = {}; self.cur_item = None
        self.bar = QProgressBar(); self.bar.setRange(0, 1000); self.bar.setFixedHeight(8)
        self.bar.setStyleSheet("QProgressBar{background:rgba(255,255,255,0.08);border:none;border-radius:4px;} QProgressBar::chunk{border-radius:4px;"
                               "background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 %s,stop:1 %s);}" % (C["acc"], C["amber"]))
        v.addWidget(self.bar)
        self.times = QLabel(""); self.times.setStyleSheet("color:%s;font-size:9pt;background:transparent;" % C["faint"])
        self.logbtn = QPushButton("Details ▾"); self.logbtn.setObjectName("ghost"); self.logbtn.setCheckable(True)
        self.cbtn = btn("Abbrechen", I["cancel"], kind="danger", slot=self.cancel.emit)
        v.addLayout(row(self.times, "stretch", self.logbtn, self.cbtn))
        self.log = QPlainTextEdit(); self.log.setReadOnly(True); self.log.hide(); v.addWidget(self.log, 1)
        self.logbtn.toggled.connect(lambda on: (self.log.setVisible(on), self.logbtn.setText("Details ▴" if on else "Details ▾")))
        self.clock = QTimer(self); self.clock.setInterval(500); self.clock.timeout.connect(self._times); self.frac = 0.0; self.t0 = time.time()
        self.hide()
    def set_items(self, names):
        """One row per input file: state dot, name, result line."""
        while self.list.count():
            it = self.list.takeAt(0)
            if it.widget(): it.widget().deleteLater()
        self.items = {}; self.cur_item = None
        for n in names:
            w = QWidget(); w.setStyleSheet("background:transparent;"); h = QHBoxLayout(w); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(12)
            dot = QLabel("○"); dot.setFixedWidth(18); dot.setAlignment(Qt.AlignCenter); dot.setStyleSheet("color:%s;font-size:11pt;background:transparent;" % C["faint"])
            tv = QVBoxLayout(); tv.setSpacing(0); name = QLabel(n); name.setStyleSheet("color:%s;background:transparent;" % C["muted"])
            info = QLabel(""); info.setStyleSheet("color:%s;font-size:8.5pt;background:transparent;" % C["faint"]); info.setWordWrap(True); info.hide()
            tv.addWidget(name); tv.addWidget(info); h.addWidget(dot, 0, Qt.AlignTop); h.addLayout(tv, 1); self.list.addWidget(w)
            self.items[n] = dict(dot=dot, name=name, info=info)
        self.list.addStretch(1)
    def _mark(self, key, state):
        it = self.items.get(key)
        if not it: return
        col = {"wait": C["faint"], "run": C["acc"], "done": C["ok"]}[state]
        it["dot"].setText({"wait": "○", "run": "●", "done": "✓"}[state]); it["dot"].setStyleSheet("color:%s;font-size:11pt;background:transparent;" % col)
        it["name"].setStyleSheet("color:%s;background:transparent;%s" % (C["text"] if state == "run" else C["muted"], "font-weight:600;" if state == "run" else ""))
    def start(self):
        self.t0 = time.time(); self.frac = 0.0; self.bar.setValue(0); self.step.setText("Starte …"); self.detail.setText(""); self.log.clear()
        for k in self.items: self._mark(k, "wait"); self.items[k]["info"].hide()
        self.cur_item = None; self._eta_hist = []; self._eta_shown = None
        self.cbtn.setEnabled(True); self.anim.start(); self.clock.start(); self.fit(); self.show(); self.raise_()
    def fit(self):
        if self.parent(): self.setGeometry(self.parent().rect().adjusted(14, 14, -14, -14))
    def progress(self, f): self.frac = max(0.0, min(1.0, float(f))); self.bar.setValue(int(self.frac*1000)); self._times()
    def message(self, line):
        self.log.appendPlainText(line); s = line.strip()
        if not s: return
        low = s.lower()
        if not line.startswith(" ") and not low.startswith(("mix-profil gespeichert", "profil gespeichert", "instrument-profil gespeichert", "mastering-profil gespeichert")):
            if self.cur_item: self._mark(self.cur_item, "done")
            self.cur_item = s if s in self.items else None
            if self.cur_item: self._mark(self.cur_item, "run")
            self.step.setText("Analysiere „%s“" % s[:80]); self.detail.setText(""); return
        if self.cur_item and (low.startswith("mix ") or ": " in s and "lufs" in low) and not low.startswith(("trennung", "gpu")):
            self.items[self.cur_item]["info"].setText(s[:220]); self.items[self.cur_item]["info"].show()
        if "trennung:" in low: self.step.setText("KI-Trennung in Einzelspuren"); self.detail.setText(s.split("·", 1)[-1].strip()[:140]); return
        if "zwischenspeicher" in low: self.detail.setText("Stems aus dem Zwischenspeicher – keine neue Trennung nötig"); return
        if "effektanalyse" in low or "effekte" in low: self.step.setText("Effekte (Hall, Delay) per KI analysieren")
        if "gespeichert" in low: self.step.setText("Speichere Profil …")
        self.detail.setText(s[:160])
    def _times(self):
        """Remaining time only once the estimate actually falls; after that it only counts down (never jumps up).
        If the estimate gets clearly worse, it is hidden until it falls again."""
        now = time.time(); el = now-self.t0; txt = "läuft seit %s" % fmt_time(el)
        if self.frac > 0.05 and el > 5:
            est = el*(1-self.frac)/self.frac; hist = self.__dict__.setdefault("_eta_hist", [])
            hist.append((now, est)); hist[:] = [h for h in hist if now-h[0] <= 12]
            shown = self.__dict__.get("_eta_shown")
            if shown is not None:
                shown = shown[1]-(now-shown[0])
                if est > 1.3*shown+10: shown = None                 # estimate got clearly worse: hide again
                else: shown = max(0.0, min(shown, est))
            elif len(hist) >= 6 and hist[-1][1] < hist[0][1]-2 and all(b[1] <= a[1]+1 for a, b in zip(hist[-4:], hist[-3:])):
                shown = est                                           # falling steadily for a few seconds
            self._eta_shown = (now, shown) if shown is not None else None
            if shown is not None: txt += " · noch etwa %s" % fmt_time(shown)
        self.times.setText(txt)
    def finish(self, ok=True, text=None):
        self.clock.stop(); self.anim.stop(done=ok); self.cbtn.setEnabled(False)
        if ok:
            self.bar.setValue(1000); self.step.setText(text or "Fertig"); self.detail.setText("")
            for k in self.items: self._mark(k, "done")
        else: self.hide()

# ---------------------------------------------------------------- learn dialogs
class DialogBase(QDialog):
    def __init__(self, parent, title, w=680, h=620):
        super().__init__(parent); self.setWindowTitle(title); self.resize(w, h); self.setStyleSheet(QSS)
        self.v = QVBoxLayout(self); self.v.setContentsMargins(22, 18, 22, 18); self.v.setSpacing(12)
        t = QLabel(title); t.setObjectName("pageTitle"); t.setStyleSheet("font-size:15pt;font-weight:600;"); self.v.addWidget(t)
        self.log = QPlainTextEdit(); self.log.setReadOnly(True); self.prog = QProgressBar(); self.prog.setRange(0, 1000); self.prog.setFixedHeight(6)
        self.ev = None; self.result_name = None; self._busy = False
        dark_title(self)
    def reject(self):
        if self._busy:
            if QMessageBox.question(self, "Abbrechen", "Anlernen abbrechen?") != QMessageBox.Yes: return
            if self.ev: self.ev.set()
        super().reject()
    def showEvent(self, e):
        super().showEvent(e)
        if not self.log.toPlainText().strip(): self.log.hide()     # the log lives under "Details" in the progress panel;
        self.prog.hide()                                            # shown here only for messages before a run or errors
    def _settings(self):
        return getattr(getattr(self.parent(), "win", None), "settings", None)
    def pref_box(self, box, key, default=True):
        """Checkbox that remembers its last state (program settings)."""
        st = self._settings(); box.setChecked(bool(st.get(key, default)) if st is not None else default)
        box.toggled.connect(lambda on: st.__setitem__(key, on) if st is not None else None); return box
    def run_job(self, job, title, done_text="Fertig – Profil gespeichert"):
        """Runs job(bridge) -> profile name in the background behind the animated progress panel."""
        if getattr(self, "busy", None) is None:
            self.busy = BusyPanel(self, title); self.busy.cancel.connect(self.reject)
        self.busy.h.setText(title); self.busy.set_items([os.path.splitext(os.path.basename(x))[0] for x in getattr(self, "paths", [])])
        self.busy.start(); self._busy = True; self.go.setEnabled(False)
        def done(n):
            self._busy = False; self.result_name = n; self.busy.finish(True, done_text); QTimer.singleShot(1100, self.accept)
        def fail(m):
            self._busy = False; self.busy.finish(False); self.go.setEnabled(True); self.log.appendPlainText("FEHLER: " + m); self.log.show()
            if m != "Abgebrochen.": QMessageBox.warning(self, "Anlernen", m)
        def lg(t): self.log.appendPlainText(t); self.busy.message(t)
        def pr(f): self.prog.setValue(int(f*1000)); self.busy.progress(f)
        run_bg(self, job, done, fail, on_log=lg, on_prog=pr)
    def resizeEvent(self, e):
        super().resizeEvent(e)
        if getattr(self, "busy", None) is not None and self.busy.isVisible(): self.busy.fit()

class LearnProfileDialog(DialogBase):
    def __init__(self, parent):
        super().__init__(parent, "Mastering-Profil anlernen")
        s = QLabel("Ein Profil beschreibt den Zielklang (Lautheit, Breite, Spektrum, Peak-Modus) als Median Ihrer Referenztitel. "
                   "Empfehlung: 5–10 Titel eines Genres in WAV/FLAC, die Ihnen gefallen."); s.setWordWrap(True); s.setObjectName("muted"); self.v.addWidget(s)
        self.name = QLineEdit(); self.name.setPlaceholderText("z. B. Indie-Rock hell")
        self.v.addLayout(row(QLabel("Name"), self.name))
        self.files = FileTable(["Referenzen"]); self.files.setMinimumHeight(160); self.files.dropped.connect(self.add); self.v.addWidget(self.files, 1)
        self.paths = []
        self.v.addLayout(row(btn("Dateien", I["add"], slot=self.pick), btn("Ordner", I["folder"], slot=self.pick_dir), "stretch"))
        self.v.addWidget(self.prog); self.log.setMaximumHeight(140); self.v.addWidget(self.log)
        self.go = btn("Anlernen", I["learn"], kind="primary", slot=self.run); self.close_b = btn("Schließen", slot=self.reject)
        self.v.addLayout(row("stretch", self.close_b, self.go))
    def add(self, ps):
        for p in ps:
            if p in self.paths: continue
            self.paths.append(p); r = self.files.rowCount(); self.files.insertRow(r); self.files.setItem(r, 0, QTableWidgetItem(os.path.basename(p)))
        if not self.name.text().strip() and ps: self.name.setText(os.path.basename(os.path.dirname(ps[0])))
    def pick(self):
        fs, _ = QFileDialog.getOpenFileNames(self, "Referenztitel", "", "Audio (*.wav *.flac *.aif *.aiff *.ogg *.mp3)"); self.add(fs)
    def pick_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Ordner mit Referenztiteln")
        if d: self.add(mc.audio_files_in(d))
    def run(self):
        name = mc.safe_name(self.name.text().strip())
        if not self.name.text().strip() or not self.paths: QMessageBox.information(self, "Hinweis", "Bitte Name und mindestens eine Referenz angeben."); return
        if name in mc.BUILTIN: QMessageBox.information(self, "Hinweis", "Dieser Name ist für ein Standardprofil reserviert."); return
        if mc.profile_path(name) and QMessageBox.question(self, "Überschreiben", "Profil „%s“ existiert bereits. Überschreiben?" % name) != QMessageBox.Yes: return
        paths = list(self.paths); self.ev = threading.Event()
        def job(b):
            mc.learn_profile(paths, name, log=b.log.emit, progress=b.progress.emit, cancel=self.ev); return name
        self.run_job(job, "Mastering-Profil „%s“ wird angelernt" % name)

class LearnInstrumentDialog(DialogBase):
    def __init__(self, parent):
        super().__init__(parent, "Instrument-Profil anlernen", 720, 700)
        s = QLabel("Wählen Sie Referenzen, deren Instrument Ihnen gefällt. Isolierte Spuren sind ideal; bei kompletten Songs löst die KI das Instrument heraus."); s.setWordWrap(True); s.setObjectName("muted"); self.v.addWidget(s)
        self.name = QLineEdit(); self.name.setPlaceholderText("Name des Profils")
        self.inst = QComboBox(); self.inst.addItems(mc.INSTRUMENTS)
        self.v.addLayout(row(QLabel("Name"), self.name, QLabel("Instrument"), self.inst))
        self.src = Segmented([("stem", "Isolierte Spuren"), ("song", "Komplette Songs (KI-Trennung)")], "stem"); self.v.addLayout(row(QLabel("Referenzen sind"), self.src, "stretch"))
        self.model = QComboBox(); self.model.addItem("Automatisch (nach Grafikspeicher)", "auto")
        for k in ("bs_roformer_sw", "htdemucs_6s"): self.model.addItem(mc.SEP_MODELS[k]["label"], k)
        self.stems_dir = QLineEdit(os.path.join(os.path.expanduser("~"), "Desktop", "Stems")); self.save_stems = QCheckBox("Alle Stems speichern in")
        self.sep_box = QWidget(); sb = QVBoxLayout(self.sep_box); sb.setContentsMargins(0, 0, 0, 0)
        sb.addLayout(row(QLabel("Trennmodell"), self.model, HelpDot("model")))
        sb.addLayout(row(self.save_stems, self.stems_dir, btn("", I["folder"], slot=lambda: self.stems_dir.setText(QFileDialog.getExistingDirectory(self, "Stems-Ordner") or self.stems_dir.text()))))
        self.v.addWidget(self.sep_box); self.src.changed.connect(lambda k: self.sep_box.setVisible(k == "song")); self.sep_box.hide()
        if not mc.separation_available(): self.src.btns["song"].setEnabled(False); self.src.btns["song"].setToolTip("KI-Trennung ist in dieser Version nicht installiert.")
        self.fx = self.pref_box(QCheckBox("Effekte mit anlernen (Delay und Hall per KI, Tremolo, Chorus/Flanger – dauert länger)"), "learn_fx_track")
        self.v.addLayout(row(self.fx, HelpDot("t_fx"), "stretch"))
        self.files = FileTable(["Referenzen"]); self.files.setMinimumHeight(140); self.files.dropped.connect(self.add); self.v.addWidget(self.files, 1)
        self.paths = []
        self.v.addLayout(row(btn("Dateien", I["add"], slot=self.pick), btn("Ordner", I["folder"], slot=self.pick_dir), "stretch"))
        self.v.addWidget(self.prog); self.log.setMaximumHeight(140); self.v.addWidget(self.log)
        self.go = btn("Anlernen", I["learn"], kind="primary", slot=self.run); self.v.addLayout(row("stretch", btn("Schließen", slot=self.reject), self.go))
    add = LearnProfileDialog.add; pick = LearnProfileDialog.pick; pick_dir = LearnProfileDialog.pick_dir
    def run(self):
        name = mc.safe_name(self.name.text().strip())
        if not self.name.text().strip() or not self.paths: QMessageBox.information(self, "Hinweis", "Bitte Name und mindestens eine Referenz angeben."); return
        if name in mc.list_instrument_profiles() and QMessageBox.question(self, "Überschreiben", "Profil „%s“ existiert bereits. Überschreiben?" % name) != QMessageBox.Yes: return
        sep = self.src.value() == "song"
        if sep:
            plan = mc.sep_plan(self.model.currentData())
            if plan["device"] == "cpu" and QMessageBox.question(self, "CPU-Trennung", plan["message"]+"\n\nTrotzdem fortfahren?") != QMessageBox.Yes: return
        self.ev = threading.Event(); paths = list(self.paths)
        inst, fx, model = self.inst.currentText(), self.fx.isChecked(), self.model.currentData()
        sdir = self.stems_dir.text().strip() if (sep and self.save_stems.isChecked()) else None
        def job(b):
            mc.learn_instrument_profile(paths, name, inst, separate=sep, log=b.log.emit, stems_dir=sdir, analyse_fx=fx, model=model, progress=b.progress.emit, cancel=self.ev)
            return name
        self.run_job(job, "Instrument-Profil „%s“ wird angelernt" % name)

class LearnMixDialog(DialogBase):
    def __init__(self, parent):
        super().__init__(parent, "Mix-Profil anlernen", 720, 720)
        s = QLabel("Wählen Sie einen oder mehrere Songs, deren Mix Ihnen gefällt. Die KI zerlegt jeden Song in seine Spuren; gemessen werden je Rolle Pegel, "
                   "Klang, Dynamik, Breite und optional Hall/Delay. Bei mehreren Songs zählt der Median – 1–5 Songs eines Stils sind ideal."); s.setWordWrap(True); s.setObjectName("muted"); self.v.addWidget(s)
        self.name = QLineEdit(); self.name.setPlaceholderText("Name des Mix-Profils"); self.v.addLayout(row(QLabel("Name"), self.name))
        self.model = QComboBox(); self.model.addItem("Automatisch (nach Grafikspeicher)", "auto")
        for k in mc.MIX_MODELS: self.model.addItem(mc.SEP_MODELS[k]["label"], k)
        self.v.addLayout(row(QLabel("Trennmodell"), self.model, HelpDot("model")))
        self.fx = self.pref_box(QCheckBox("Effekte mit anlernen: Hall und Delay je Spur per KI (dauert etwa doppelt so lange)"), "learn_fx_mix")
        self.v.addLayout(row(self.fx, HelpDot("t_fx"), "stretch"))
        self.save_master = self.pref_box(QCheckBox("Mastering der Referenz zusätzlich als Mastering-Profil speichern"), "learn_save_master"); self.v.addWidget(self.save_master)
        self.stems_dir = QLineEdit(os.path.join(os.path.expanduser("~"), "Desktop", "Stems")); self.save_stems = QCheckBox("Stems speichern in")
        self.v.addLayout(row(self.save_stems, self.stems_dir, btn("", I["folder"], slot=lambda: self.stems_dir.setText(QFileDialog.getExistingDirectory(self, "Stems-Ordner") or self.stems_dir.text()))))
        self.files = FileTable(["Referenzsongs"]); self.files.setMinimumHeight(140); self.files.dropped.connect(self.add); self.v.addWidget(self.files, 1)
        self.paths = []
        self.v.addLayout(row(btn("Dateien", I["add"], slot=self.pick), btn("Ordner", I["folder"], slot=self.pick_dir), "stretch"))
        self.v.addWidget(self.prog); self.log.setMaximumHeight(160); self.v.addWidget(self.log)
        self.go = btn("Anlernen", I["learn"], kind="primary", slot=self.run); self.v.addLayout(row("stretch", btn("Schließen", slot=self.reject), self.go))
        if not mc.separation_available():
            self.go.setEnabled(False); self.log.appendPlainText("Die KI-Trennung ist in dieser Version nicht installiert – Mix-Profile brauchen die Vollversion.")
    add = LearnProfileDialog.add; pick = LearnProfileDialog.pick; pick_dir = LearnProfileDialog.pick_dir
    def run(self):
        name = mc.safe_name(self.name.text().strip())
        if not self.name.text().strip() or not self.paths: QMessageBox.information(self, "Hinweis", "Bitte Name und mindestens einen Referenzsong angeben."); return
        if name in mx.list_mix_profiles() and QMessageBox.question(self, "Überschreiben", "Mix-Profil „%s“ existiert bereits. Überschreiben?" % name) != QMessageBox.Yes: return
        save_master = self.save_master.isChecked() and name not in mc.BUILTIN
        if save_master and mc.profile_path(name) and os.path.dirname(mc.profile_path(name)) == mc.USER_PROFILE_DIR and \
                QMessageBox.question(self, "Überschreiben", "Mastering-Profil „%s“ existiert bereits. Überschreiben?" % name) != QMessageBox.Yes: return
        plan = mc.sep_plan(self.model.currentData())
        if plan["device"] == "cpu" and QMessageBox.question(self, "CPU-Trennung", plan["message"]+"\n\nTrotzdem fortfahren?") != QMessageBox.Yes: return
        self.ev = threading.Event(); paths = list(self.paths)
        fx, model = self.fx.isChecked(), self.model.currentData(); sdir = self.stems_dir.text().strip() if self.save_stems.isChecked() else None
        def job(b):
            mx.learn_mix_profile(paths, name, model=model, log=b.log.emit, progress=b.progress.emit, cancel=self.ev, analyse_fx=fx, stems_dir=sdir, save_master=save_master)
            return name
        self.run_job(job, "Mix-Profil „%s“ wird angelernt" % name, "Fertig – Mix-Profil gespeichert")

# ---------------------------------------------------------------- Spur-Angleich
class TrackPage(Page):
    FXROWS = [("tremolo", "Tremolo", [("rate_hz", "Rate", " Hz"), ("depth_db", "Tiefe", " dB")]),
              ("modulation", "Chorus / Flanger", [("rate_hz", "Rate", " Hz"), ("depth_ms", "Tiefe", " ms"), ("centre_ms", "Verzög.", " ms"), ("feedback", "Feedb.", "")]),
              ("delay", "Delay", [("time_s", "Zeit", " s"), ("level", "Echo", ""), ("feedback", "Feedb.", "")]),
              ("reverb", "Hall", [("room_size", "Raum", ""), ("damping", "Dämpf.", ""), ("predelay_ms", "Pre-Del.", " ms"), ("wet", "Anteil", "")])]
    def __init__(self, win):
        super().__init__("Spur-Angleich", "Eine rohe Instrumentenspur klingt wie das Instrument aus Referenzsongs – Spektrum, Dynamik, Transienten, Breite und Effekte.")
        self.win = win; self.files = []; self.cur = None; self.cur_x = None; self.info = {}; self.player = Player(); self.cancel_ev = None; self.preview = None
        body = QHBoxLayout(); body.setSpacing(16); self.v.addLayout(body, 1)
        lsa, left = scroll_column(); body.addWidget(lsa, 1)
        fc = Card("Rohe Spuren")
        self.table = FileTable(["Spur", "Dauer", "LUFS", "Kanäle", "Status"], [0, 64, 70, 70, 150]); self.table.auto_height(3, 7)
        self.table.dropped.connect(self.add_files); self.table.itemSelectionChanged.connect(self.on_select); self.table.parent_remove = self.remove_sel
        fc.add(self.table)
        fc.add(row(btn("Dateien", I["add"], slot=lambda: self._pick(False)), btn("Ordner", I["folder"], slot=lambda: self._pick(True)),
                   btn("Entfernen", I["delete"], kind="ghost", slot=self.remove_sel), "stretch"))
        left.addWidget(fc, 0)
        ac = Card("Vorschau", help_key="preview")
        self.spec = SpectrumView(); ac.add(self.spec)
        self.pbar = PlayerBar(self.player); ac.add(self.pbar); self.pbar.match.toggled.connect(lambda *_: self.apply_match())
        self.bprev = btn("Vorschau berechnen", I["preview"], slot=self.make_preview); self.prev_note = QLabel(""); self.prev_note.setObjectName("faint")
        ac.add(row(self.bprev, self.prev_note, "stretch")); left.addWidget(ac, 0); left.addStretch(1)
        sa, rl = scroll_column(460); body.addWidget(sa)
        pm = QPushButton("…"); pm.setFixedWidth(36); menu = QMenu(pm); menu.addAction("Instrument-Profil anlernen …", self.learn); menu.addAction("Profil löschen", self.delete)
        pm.setMenu(menu); pm.setStyleSheet("QPushButton::menu-indicator{width:0;}")
        self.prof = QComboBox(); self.prof.setMinimumWidth(190); self.prof.currentTextChanged.connect(self.on_profile)
        pc = Card("Instrument-Profil"); pc.add(row(QLabel("Profil"), self.prof, pm, HelpDot("t_profile")))
        self.prof_info = QLabel(""); self.prof_info.setObjectName("faint"); self.prof_info.setWordWrap(True); pc.add(self.prof_info)
        self.learn_btn = btn("Neues Profil anlernen", I["learn"], slot=self.learn); pc.add(row(self.learn_btn, "stretch"))
        rl.addWidget(pc)
        sc = Card("Klang")
        self.s_str = SliderRow("Spektrum-Angleich", 0, 1, 1, 0.01, " %", "t_strength", 0, 100)
        self.s_maxeq = SliderRow("max. EQ", 2, 15, 9, 0.1, " dB", "maxeq")
        self.s_lo = SliderRow("Angleich ab", 20, 300, 40, 1, " Hz", "eqrange", 0)
        self.s_hi = SliderRow("Angleich bis", 4000, 20000, 16000, 100, " Hz", "eqrange", 0)
        self.s_dyn = SliderRow("Dynamik-Angleich", 0, 1, 1, 0.01, " %", "t_dyn", 0, 100)
        self.s_tr = SliderRow("Transienten", 0, 1, 1, 0.01, " %", "t_trans", 0, 100)
        self.s_sat = SliderRow("Sättigung", 0, 1, 0, 0.01, " %", "t_sat", 0, 100)
        for w in (self.s_str, self.s_maxeq, self.s_lo, self.s_hi, self.s_dyn, self.s_tr, self.s_sat): sc.add(w)
        self.wmode = Segmented([("profil", "Wie Profil"), ("manuell", "Manuell"), ("aus", "Aus")], "profil"); sc.add(row(QLabel("Stereobreite"), self.wmode, HelpDot("t_width")))
        self.s_w = SliderRow("Breite manuell", -6, 6, 0, 0.1, " dB"); sc.add(self.s_w)
        self.wmode.changed.connect(lambda k: (self.s_w.setEnabled(k == "manuell"), self.mark_stale())); self.s_w.setEnabled(False)
        self.lufs_on = QCheckBox("Eigene Ziel-Lautheit"); self.s_lufs = SliderRow("Ziel-Lautheit", -30, -8, -18, 0.1, " LUFS", "t_lufs")
        sc.add(row(self.lufs_on, "stretch")); sc.add(self.s_lufs); self.lufs_on.toggled.connect(self.s_lufs.setEnabled); self.s_lufs.setEnabled(False)
        rl.addWidget(sc)
        fxc = Card("Effekte übertragen", help_key="t_fx"); self.fx = {}
        for key, title, params in self.FXROWS:
            on = QCheckBox(title); state = QLabel(""); state.setObjectName("faint")
            fxc.add(row(on, "stretch", state))
            g = QHBoxLayout(); g.setSpacing(6); pars = {}
            for pk, pl, unit in params:
                sp = QDoubleSpinBox(); sp.setDecimals(1 if pk == "predelay_ms" else 2); sp.setRange(0, 150 if pk == "predelay_ms" else (1.0 if pk in ("room_size", "damping") else 30)); sp.setSingleStep(0.05); sp.setButtonSymbols(QDoubleSpinBox.NoButtons); sp.setFixedWidth(62)
                sp.setValue(float(mc.FX_DEFAULTS[key][pk])); sp.setToolTip(pl+unit); l = QLabel(pl); l.setObjectName("faint"); g.addWidget(l); g.addWidget(sp); pars[pk] = sp
            g.addStretch(1); fxc.add(g)
            st = SliderRow("Stärke", 0, 1.5, 1.0, 0.01, " %", None, 0, 100); fxc.add(st)
            on.toggled.connect(lambda v, st=st, pars=pars: [w.setEnabled(v) for w in [st]+list(pars.values())]); on.setChecked(False); st.setEnabled(False)
            [w.setEnabled(False) for w in pars.values()]
            self.fx[key] = dict(on=on, state=state, pars=pars, strength=st)
        rl.addWidget(fxc); rl.addStretch(1)
        self.out = OutputBar(os.path.join(os.path.expanduser("~"), "Desktop", "Spur-Ausgabe"), "Spuren angleichen")
        self.out.primary.clicked.connect(self.start); self.out.cancel.clicked.connect(self.stop); self.v.addWidget(self.out)
        for w in (self.s_str, self.s_maxeq, self.s_lo, self.s_hi, self.s_dyn, self.s_tr, self.s_sat, self.s_w, self.s_lufs): w.changed.connect(self.mark_stale)
        self.reload()
    def mark_stale(self, *a):
        if self.preview: self.prev_note.setText("Einstellungen geändert – Vorschau neu berechnen"); self.prev_note.setStyleSheet("color:%s;" % C["amber"])
    def reload(self, select=None):
        cur = select or self.prof.currentText(); names = mc.list_instrument_profiles()
        self.prof.blockSignals(True); self.prof.clear(); self.prof.addItems(names); i = self.prof.findText(cur); self.prof.setCurrentIndex(max(0, i)); self.prof.blockSignals(False)
        self.on_profile()
    def profile(self):
        try: return mc.load_instrument_profile(self.prof.currentText()) if self.prof.currentText() else None
        except Exception: return None
    def on_profile(self, *a):
        pr = self.profile()
        if not pr: self.prof_info.setText("Noch kein Instrument-Profil vorhanden – bitte zuerst eines anlernen."); self.learn_btn.show()
        else:
            self.learn_btn.hide()
            self.prof_info.setText("%s · %.1f LUFS · Crest %.1f dB · Transienten %+.1f dB · Breite %.1f dB · %d Referenz(en)%s" % (
                pr["instrument"], pr["lufs"], pr["crest"], pr["transient"], pr["width"], pr["n"], " · per KI-Trennung" if pr.get("separated") else ""))
        eff = (pr or {}).get("effects", {})
        for key, title, params in self.FXROWS:
            d = self.fx[key]; v = eff.get(key)
            if v:
                v = dict(v)
                if key == "reverb":                      # profiles of Mastering-Tool 2.x only know RT60 and level
                    v.setdefault("room_size", mc.room_for_rt60(v.get("rt60_s", 1.2))); v.setdefault("damping", 0.5); v.setdefault("predelay_ms", 0.0)
                for pk, sp in d["pars"].items():
                    if pk in v: sp.setValue(float(v[pk]))
                d["on"].setChecked(v["confidence"] >= 0.4)
                d["state"].setText("erkannt · %.0f %%%s" % (v["confidence"]*100, " · KI" if v.get("method") == "KI" else ""))
                d["state"].setToolTip(mc.describe_effect(key, v))
            else:
                d["on"].setChecked(False); d["state"].setText("nicht erkannt" if pr else "")
        self.refresh_spec(); self.mark_stale()
    def learn(self):
        d = LearnInstrumentDialog(self)
        if d.exec() and d.result_name: self.reload(d.result_name)
    def delete(self):
        n = self.prof.currentText()
        if not n or QMessageBox.question(self, "Profil löschen", "Instrument-Profil „%s“ wirklich löschen?" % n) != QMessageBox.Yes: return
        try: mc.delete_instrument_profile(n); self.reload()
        except Exception as e: QMessageBox.warning(self, "Profil löschen", str(e))
    def _pick(self, folder):
        if folder:
            d = QFileDialog.getExistingDirectory(self, "Ordner mit Spuren", self.win.last_dir)
            if d: self.win.last_dir = d; self.add_files(mc.audio_files_in(d))
        else:
            fs, _ = QFileDialog.getOpenFileNames(self, "Spuren", self.win.last_dir, "Audio (*.wav *.flac *.aif *.aiff *.ogg *.mp3)")
            if fs: self.win.last_dir = os.path.dirname(fs[0]); self.add_files(fs)
    def add_files(self, paths):
        first = None
        for p in paths:
            p = os.path.normpath(p)
            if p in self.files: continue
            self.files.append(p); r = self.table.rowCount(); self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(os.path.splitext(os.path.basename(p))[0]))
            for c in range(1, 5): self.table.setItem(r, c, QTableWidgetItem(""))
            try:
                i = mc.sf.info(p); self.table.item(r, 1).setText(fmt_time(i.duration)); self.table.item(r, 3).setText("mono" if i.channels == 1 else "stereo")
            except Exception: self.table.item(r, 4).setText("nicht lesbar")
            first = r if first is None else first
        set_btn_text(self.out.primary, "Spuren angleichen (%d)" % len(self.files))
        if first is not None and self.cur is None: self.table.selectRow(first)
    def remove_sel(self):
        for r in sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True):
            p = self.files.pop(r); self.table.removeRow(r)
            if p == self.cur: self.cur = None; self.cur_x = None; self.preview = None; self.player.stop(); self.pbar.has_b(False); self.refresh_spec()
        set_btn_text(self.out.primary, "Spuren angleichen (%d)" % len(self.files) if self.files else "Spuren angleichen")
    def on_select(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        if not rows or self.files[rows[0]] == self.cur: return
        p = self.files[rows[0]]; self.cur = p; self.cur_x = None; self.preview = None; self.player.stop(); self.pbar.has_b(False); self.prev_note.setText("")
        def job(b):
            x, sr, mono = mc.load_audio(p); return p, x, sr, mono, dict(spec=mc.smooth_spectrum(x, sr), lufs=mc.integrated(x, sr), env=mc.envelope_preview(x), dur=len(x)/sr)
        def done(r):
            p_, x, sr, mono, inf = r
            if p_ != self.cur: return
            self.cur_x = (x, sr, mono); self.info[p_] = inf; self.player.load(x, sr); self.pbar.wave.set_env(inf["env"], None, inf["dur"]); self.pbar._tick(0)
            ri = self._row(p_)
            if ri >= 0: self.table.item(ri, 2).setText("%.1f" % inf["lufs"])
            self.refresh_spec()
        run_bg(self, job, done, lambda m: None)
    def _row(self, p):
        try: return self.files.index(p)
        except ValueError: return -1
    def refresh_spec(self):
        inf = self.info.get(self.cur); pr = self.profile(); curves = []
        if pr is not None: curves.append(("Profil", pr["spec"], C["amber"], Qt.DashLine, 1.6))
        if inf: curves.append(("Spur", inf["spec"], C["muted"], Qt.SolidLine, 1.4))
        if self.preview: curves.append(("Angeglichen", self.preview["spec"], C["acc"], Qt.SolidLine, 2.2))
        self.spec.set_curves(curves if inf else [], "Langzeitspektrum · +3 dB/Oktave geneigt")
    def params(self):
        fx = {}
        for key, d in self.fx.items():
            if not d["on"].isChecked() or d["strength"].value() <= 0: continue
            e = dict(strength=d["strength"].value()); e.update({pk: sp.value() for pk, sp in d["pars"].items()})
            if key == "modulation": e["kind"] = "Flanger" if e["centre_ms"] < 4 else "Chorus"
            fx[key] = e
        return dict(strength=self.s_str.value(), max_eq=self.s_maxeq.value(), eq_lo=self.s_lo.value(), eq_hi=self.s_hi.value(), dyn_strength=self.s_dyn.value(),
                    transient_strength=self.s_tr.value(), saturation=self.s_sat.value(), width_mode=self.wmode.value(), width_db_manual=self.s_w.value(),
                    target_lufs=self.s_lufs.value() if self.lufs_on.isChecked() else None, out_bits=int(self.out.bits.value()), fx=fx)
    def make_preview(self):
        pr = self.profile()
        if not pr: QMessageBox.information(self, "Vorschau", "Bitte zuerst ein Instrument-Profil anlernen."); return
        if not self.cur: QMessageBox.information(self, "Vorschau", "Bitte eine Spur auswählen."); return
        if self.cur_x is None: QMessageBox.information(self, "Vorschau", "Die Spur wird noch geladen – bitte einen Moment warten."); return
        x, sr, mono = self.cur_x; p = self.cur; kw = self.params(); self.bprev.setEnabled(False); self.prev_note.setStyleSheet(""); self.prev_note.setText("Berechne …")
        def job(b):
            y, info = mc.render_track(x, sr, mono, pr, log=b.log.emit, **kw)
            return p, y, dict(spec=mc.smooth_spectrum(y, sr), env=mc.envelope_preview(y), lufs=mc.integrated(y, sr))
        def done(r):
            self.bprev.setEnabled(True); p_, y, pv = r
            if p_ != self.cur: return
            self.preview = pv; self.player.set_b(y); self.apply_match()
            self.pbar.has_b(True); self.pbar.ab.set("b"); self.pbar._ab("b"); self.pbar.wave.set_env(self.info[p_]["env"], pv["env"])
            self.prev_note.setStyleSheet("color:%s;" % C["ok"]); self.prev_note.setText("Vorschau aktuell"); self.refresh_spec()
        def fail(m): self.bprev.setEnabled(True); self.prev_note.setText(m)
        run_bg(self, job, done, fail, on_log=self.out.write)
    def apply_match(self):
        if not self.preview or self.cur not in self.info or not self.pbar.match.isChecked(): self.player.set_gains(1, 1); return
        la, lb = self.info[self.cur]["lufs"], self.preview["lufs"]; self.player.set_gains(10**(min(0, lb-la)/20), 10**(min(0, la-lb)/20))
    def start(self):
        pr = self.profile()
        if not self.files: QMessageBox.information(self, "Spur-Angleich", "Bitte zuerst Spuren hinzufügen."); return
        if not pr: QMessageBox.information(self, "Spur-Angleich", "Bitte zuerst ein Instrument-Profil anlernen."); return
        kw = self.params(); files = list(self.files); out = self.out.dir.text().strip()
        if not out: QMessageBox.information(self, "Spur-Angleich", "Bitte einen Ausgabeordner wählen."); return
        ev = threading.Event(); self.cancel_ev = ev; self.out.busy(True)
        def job(b):
            def item(i, n): b.progress.emit(i/n)
            return mc.run_track_batch(files, pr, out, log=b.log.emit, progress=item, cancel=ev, **kw)
        def done(rows):
            self.out.busy(False); self.out.prog.setValue(1000); self.out.status.setText("Fertig: %d Spur(en) → %s" % (len(rows), out))
            self.win.notify("Spur-Angleich fertig", "%d Spur(en) angeglichen." % len(rows))
            if rows and self.win.settings.get("open_after", True): open_folder(out)
        run_bg(self, job, done, lambda m: (self.out.busy(False), self.out.write(m)), on_log=self.out.write, on_prog=lambda f: self.out.prog.setValue(int(f*1000)))
    def stop(self):
        if self.cancel_ev: self.cancel_ev.set(); self.out.cancel.setEnabled(False)
    def state(self): return dict(profile=self.prof.currentText(), out=self.out.dir.text(), bits=self.out.bits.value())
    def restore(self, d):
        if not d: return
        i = self.prof.findText(d.get("profile", ""))
        if i >= 0: self.prof.setCurrentIndex(i)
        self.out.dir.setText(d.get("out", self.out.dir.text())); self.out.bits.set(d.get("bits", "24"))

# ---------------------------------------------------------------- Stems extrahieren
class StemsPage(Page):
    def __init__(self, win):
        super().__init__("Stems extrahieren", "Songs per KI in Einzelspuren zerlegen – Gesang, Drums, Bass, Gitarre, Piano und mehr. Für Remixe, Karaoke, Übungsspuren oder als Referenz.")
        self.win = win; self.files = []; self.cancel_ev = None
        body = QHBoxLayout(); body.setSpacing(16); self.v.addLayout(body, 1)
        fc = Card("Songs")
        self.table = FileTable(["Song", "Dauer", "Status"], [0, 64, 230]); self.table.dropped.connect(self.add_files); self.table.parent_remove = self.remove_sel
        fc.add(self.table)
        fc.add(row(btn("Dateien", I["add"], slot=lambda: self._pick(False)), btn("Ordner", I["folder"], slot=lambda: self._pick(True)),
                   btn("Entfernen", I["delete"], kind="ghost", slot=self.remove_sel), "stretch"))
        body.addWidget(fc, 1)
        sa, rl = scroll_column(440); body.addWidget(sa)
        mc_ = Card("Modell", help_key="model"); self.models = QButtonGroup(self); self.mrows = {}
        for key in ["auto"]+[k for k, v in mc.SEP_MODELS.items() if not v.get("internal")]:
            if key == "auto": title, sub = "Automatisch", "Beste Qualität, die in den freien Grafikspeicher passt"
            else:
                m = mc.SEP_MODELS[key]; parts = m["label"].split(" · "); title = parts[0]; sub = " · ".join(parts[1:])
            rb = QRadioButton(title); rb.setStyleSheet("font-weight:600;"); self.models.addButton(rb); rb.key = key
            info = QLabel(sub); info.setObjectName("muted"); info.setWordWrap(True)
            dl = QLabel(""); dl.setObjectName("faint")
            sub_box = QVBoxLayout(); sub_box.setContentsMargins(26, 0, 0, 4); sub_box.setSpacing(0); sub_box.addWidget(info); sub_box.addWidget(dl)
            box = QVBoxLayout(); box.setSpacing(2); box.addWidget(rb); box.addLayout(sub_box)
            mc_.add(box); self.mrows[key] = (rb, dl); rb.toggled.connect(self.on_model)
        self.mrows["auto"][0].setChecked(True); rl.addWidget(mc_)
        self.stc = Card("Spuren"); self.stem_boxes = {}; self.stem_wrap = QGridLayout(); self.stem_wrap.setHorizontalSpacing(14); self.stc.add(self.stem_wrap); rl.addWidget(self.stc)
        self.dev = QLabel(""); self.dev.setObjectName("muted"); self.dev.setWordWrap(True)
        gc = Card("Hardware", help_key="vram"); gc.add(self.dev)
        gc.add(row(btn("Aktualisieren", I["refresh"], kind="ghost", slot=self.refresh_dev), btn("Einstellungen", I["settings"], kind="ghost", slot=lambda: self.win.go("settings")), "stretch"))
        rl.addWidget(gc); rl.addStretch(1)
        self.out = OutputBar(os.path.join(os.path.expanduser("~"), "Desktop", "Stems"), "Stems erstellen")
        self.out.primary.clicked.connect(self.start); self.out.cancel.clicked.connect(self.stop); self.v.addWidget(self.out)
        if not mc.separation_available():
            self.out.primary.setEnabled(False); self.dev.setText("Die KI-Stem-Trennung ist in dieser Version nicht installiert. Bitte die Vollversion (Setup) verwenden.")
        self.on_model(); self.refresh_dev()
    def model(self):
        b = self.models.checkedButton(); return b.key if b else "auto"
    def on_model(self, *a):
        if not hasattr(self, "stem_wrap"): return
        k = self.model(); stems = mc.SEP_MODELS[mc.sep_plan("auto", refresh=False)["model"] if k == "auto" else k]["stems"] if mc.separation_available() else mc.SEP_MODELS["htdemucs_6s"]["stems"]
        while self.stem_wrap.count():
            w = self.stem_wrap.takeAt(0).widget()
            if w: w.deleteLater()
        self.stem_boxes = {}
        for i, s in enumerate(stems):
            cb = QCheckBox(mc.STEM_DE.get(s, s)); cb.setChecked(True); self.stem_wrap.addWidget(cb, i//3, i % 3); self.stem_boxes[s] = cb
        for key, (rb, dl) in self.mrows.items():
            if key == "auto": continue
            dl.setText("✓ vorhanden" if mc.model_present(key) else "wird beim ersten Einsatz geladen (%d MB)" % mc.SEP_MODELS[key]["size_mb"])
    def refresh_dev(self):
        if not mc.separation_available(): return
        g = mc.gpu_info(refresh=True); plan = mc.sep_plan(self.model(), refresh=False)
        lines = []
        if g["ok"]: lines.append("%s · %.1f GB, davon %.1f GB frei" % (g["name"], g["total_gb"], g["free_gb"]))
        else: lines.append("Keine NVIDIA-Grafikkarte erkannt.")
        if mc.FORCE_CPU: lines.append("Einstellung: nur CPU.")
        elif mc.VRAM_LIMIT_GB: lines.append("Einstellung: höchstens %.1f GB Grafikspeicher." % mc.VRAM_LIMIT_GB)
        lines.append("→ " + ("GPU" if plan["device"] == "gpu" else "CPU") + " mit " + mc.SEP_MODELS[plan["model"]]["label"].split(" · ")[0])
        self.dev.setText("\n".join(lines)); self.on_model()
    def _pick(self, folder):
        if folder:
            d = QFileDialog.getExistingDirectory(self, "Ordner mit Songs", self.win.last_dir)
            if d: self.win.last_dir = d; self.add_files(mc.audio_files_in(d))
        else:
            fs, _ = QFileDialog.getOpenFileNames(self, "Songs", self.win.last_dir, "Audio (*.wav *.flac *.aif *.aiff *.ogg *.mp3)")
            if fs: self.win.last_dir = os.path.dirname(fs[0]); self.add_files(fs)
    def add_files(self, paths):
        for p in paths:
            p = os.path.normpath(p)
            if p in self.files: continue
            self.files.append(p); r = self.table.rowCount(); self.table.insertRow(r); self.table.setItem(r, 0, QTableWidgetItem(os.path.splitext(os.path.basename(p))[0]))
            try: d = fmt_time(mc.sf.info(p).duration)
            except Exception: d = "?"
            self.table.setItem(r, 1, QTableWidgetItem(d)); self.table.setItem(r, 2, QTableWidgetItem("bereit"))
        set_btn_text(self.out.primary, "Stems erstellen (%d)" % len(self.files))
    def remove_sel(self):
        for r in sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True): self.files.pop(r); self.table.removeRow(r)
        set_btn_text(self.out.primary, "Stems erstellen (%d)" % len(self.files) if self.files else "Stems erstellen")
    def set_status(self, p, text, color=None):
        try: r = self.files.index(p)
        except ValueError: return
        it = self.table.item(r, 2); it.setText(text); it.setForeground(QColor(color or C["muted"]))
    def start(self):
        if not self.files: QMessageBox.information(self, "Stems", "Bitte zuerst Songs hinzufügen."); return
        want = [k for k, cb in self.stem_boxes.items() if cb.isChecked()]
        if not want: QMessageBox.information(self, "Stems", "Bitte mindestens eine Spur auswählen."); return
        plan = mc.sep_plan(self.model())
        if plan["device"] == "cpu" and QMessageBox.question(self, "CPU-Trennung", plan["message"]+"\n\nTrotzdem starten?") != QMessageBox.Yes: return
        files = list(self.files); out = self.out.dir.text().strip(); model = self.model(); bits = int(self.out.bits.value()); ev = threading.Event(); self.cancel_ev = ev
        self.out.busy(True); self.out.prog.setValue(0)
        def job(b):
            n = len(files); done_ = []
            for i, p in enumerate(files):
                if ev.is_set(): raise mc.Cancelled()
                b.item.emit((p, "trennt …", C["acc"]))
                def prog(f, i=i): b.progress.emit((i+f)/n); b.item.emit((p, "trennt … %d %%" % int(f*100), C["acc"]))
                try:
                    dest, written = mc.extract_stems(p, out, model=model, want=want, bits=bits, log=b.log.emit, progress=prog, cancel=ev)
                    done_.append(dest); b.item.emit((p, "✓  %d Spuren" % len(written), C["ok"]))
                except mc.Cancelled: raise
                except Exception as e: b.log.emit("FEHLER %s: %s" % (os.path.basename(p), e)); b.item.emit((p, "Fehler", C["err"]))
                b.progress.emit((i+1)/n)
            return done_
        def done(d):
            self.out.busy(False); self.out.prog.setValue(1000); self.out.status.setText("Fertig: %d Song(s) → %s" % (len(d), out))
            self.win.notify("Stems fertig", "%d Song(s) zerlegt." % len(d))
            if d and self.win.settings.get("open_after", True): open_folder(out)
        def fail(m):
            self.out.busy(False); self.out.write(m)
            for p in files:
                r = self.files.index(p) if p in self.files else -1
                if r >= 0 and self.table.item(r, 2).text().startswith("trennt"): self.set_status(p, "abgebrochen", C["warn"])
        run_bg(self, job, done, fail, on_log=self.out.write, on_prog=lambda f: self.out.prog.setValue(int(f*1000)), on_item=lambda t: self.set_status(*t))
    def stop(self):
        if self.cancel_ev: self.cancel_ev.set(); self.out.cancel.setEnabled(False)
    def state(self): return dict(out=self.out.dir.text(), bits=self.out.bits.value(), model=self.model())
    def restore(self, d):
        if not d: return
        self.out.dir.setText(d.get("out", self.out.dir.text())); self.out.bits.set(d.get("bits", "24"))
        if d.get("model") in self.mrows: self.mrows[d["model"]][0].setChecked(True)

# ---------------------------------------------------------------- Einstellungen
class SettingsPage(Page):
    def __init__(self, win):
        super().__init__("Einstellungen", "Grafikkarte, Zwischenspeicher, Verknüpfung und Programminfo.")
        self.win = win; s = win.settings
        sa, lay = scroll_column(); self.v.addWidget(sa, 1); sa.widget().setMaximumWidth(980)
        gc = Card("KI-Trennung & Grafikkarte", help_key="vram")
        self.gpu = QLabel(""); self.gpu.setObjectName("muted"); self.gpu.setWordWrap(True); gc.add(self.gpu)
        self.cpu = QCheckBox("Nur CPU verwenden (Grafikkarte nicht belegen)"); self.cpu.setChecked(s.get("force_cpu", False)); gc.add(self.cpu)
        self.lim_on = QCheckBox("Grafikspeicher begrenzen"); self.lim_on.setChecked(bool(s.get("vram_limit")))
        self.lim = SliderRow("höchstens", 1.0, 16.0, float(s.get("vram_limit") or 3.0), 0.1, " GB")
        gc.add(row(self.lim_on, "stretch")); gc.add(self.lim)
        tiers = QLabel("Stufen (gemessen, RTX 3070): BS-RoFormer SW fp16 ≈ 2,0 GB · mit kleinen Blöcken ≈ 1,4 GB · Demucs 6s ≈ 0,8 GB · CPU 0 GB. "
                       "Reicht der Speicher nicht, stuft das Programm automatisch herunter."); tiers.setObjectName("faint"); tiers.setWordWrap(True); gc.add(tiers)
        for w in (self.cpu, self.lim_on): w.toggled.connect(self.apply)
        self.lim.changed.connect(self.apply); lay.addWidget(gc)
        cc = Card("Zwischenspeicher")
        self.cache = QLabel(""); self.cache.setObjectName("muted"); cc.add(self.cache)
        cc.add(row(btn("Leeren", I["delete"], slot=self.clear_cache), btn("Ordner öffnen", I["open"], kind="ghost", slot=lambda: open_folder(mc.USER_DIR)), "stretch"))
        lay.addWidget(cc)
        ac = Card("Allgemein")
        self.open_after = QCheckBox("Ausgabeordner nach dem Export öffnen"); self.open_after.setChecked(s.get("open_after", True)); self.open_after.toggled.connect(self.apply); ac.add(self.open_after)
        ac.add(row(btn("Desktop-Verknüpfung anlegen", I["export"], slot=self.shortcut), "stretch")); lay.addWidget(ac)
        ic = Card("Über")
        t = QLabel("<b>%s %s</b><br>Mixing und Mastering nach Referenzsongs, Spur-Angleich und KI-Stem-Trennung. Nachfolger des Mastering-Tools 2.0.<br>"
                   "Messung nach ITU-R BS.1770 / EBU R128 · Trennung mit audio-separator (BS-RoFormer, Demucs, MDX23C De-Reverb, UVR De-Echo).<br>"
                   "© 2026 Kay Seufferheld (Kieselwerk) · freie Software unter der GNU GPLv3, ohne Gewährleistung · Lizenzen aller Bestandteile: LIZENZEN.md" % (mc.APP_NAME, mc.APP_VERSION)); t.setWordWrap(True); ic.add(t)
        ic.add(row(btn("Tutorial ansehen", I["play"], kind="ghost", slot=lambda: show_tutorial(self)), btn("Anleitung öffnen", I["info"], kind="ghost", slot=self.readme), "stretch"))
        lay.addWidget(ic); lay.addStretch(1)
        self.apply(); self.refresh()
    def apply(self, *a):
        mc.FORCE_CPU = self.cpu.isChecked(); mc.VRAM_LIMIT_GB = self.lim.value() if self.lim_on.isChecked() else None
        self.lim.setEnabled(self.lim_on.isChecked() and not self.cpu.isChecked()); self.lim_on.setEnabled(not self.cpu.isChecked())
        s = self.win.settings; s["force_cpu"] = self.cpu.isChecked(); s["vram_limit"] = mc.VRAM_LIMIT_GB; s["open_after"] = self.open_after.isChecked()
    def refresh(self):
        if mc.separation_available():
            g = mc.gpu_info(refresh=True)
            self.gpu.setText(("%s · %.1f GB Grafikspeicher, %.1f GB frei." % (g["name"], g["total_gb"], g["free_gb"])) if g["ok"] else "Keine NVIDIA-Grafikkarte erkannt – die Trennung läuft auf der CPU.")
        else: self.gpu.setText("KI-Stem-Trennung ist in dieser Version nicht installiert.")
        self.cache.setText("KI-Stems (für Mixing und Stem-Balance) werden je Song zwischengespeichert: %.0f MB belegt (höchstens 3 GB, ältere werden automatisch entfernt)." % mc.cache_size_mb())
    def clear_cache(self): mc.clear_cache(); self.refresh()
    def shortcut(self):
        try: QMessageBox.information(self, "Verknüpfung", "Angelegt:\n" + mc.create_desktop_shortcut())
        except Exception as e: QMessageBox.warning(self, "Verknüpfung", str(e))
    def readme(self):
        p = mc.res_path("README.md")
        if p: QDesktopServices.openUrl(QUrl.fromLocalFile(p))

# ============================================================== tutorial video
TUTORIAL = "Mixsmith-Tutorial.mp4"

def tutorial_path():
    return mc.res_path(os.path.join("tutorial", TUTORIAL)) or mc.res_path(TUTORIAL)

class TutorialDialog(QDialog):
    """Plays the tutorial video with Mixi: play/pause, seek bar, chapters, volume. Space = play/pause, Esc = close."""
    def __init__(self, parent, path):
        super().__init__(parent); self.setWindowTitle("%s – Tutorial mit Mixi" % mc.APP_NAME); self.setStyleSheet(QSS); self.resize(1280, 820)
        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 12); v.setSpacing(10)
        self.video = QVideoWidget(); self.video.setStyleSheet("background:#000;"); v.addWidget(self.video, 1)
        self.player = QMediaPlayer(self); self.audio = QAudioOutput(self); self.player.setAudioOutput(self.audio); self.player.setVideoOutput(self.video)
        self.bplay = btn("", I["pause"], tip="Abspielen / Pause (Leertaste)", slot=self.toggle); self.bplay.setFixedWidth(44)
        self.seek = QSlider(Qt.Horizontal); self.seek.setRange(0, 0); self.seek.sliderMoved.connect(self.player.setPosition); self.seek.setCursor(Qt.PointingHandCursor)
        self.time = QLabel("0:00 / 0:00"); self.time.setObjectName("muted")
        self.chap = QComboBox(); self.chap.setMinimumWidth(220); self.chap.activated.connect(lambda i: self.player.setPosition(int(self.chap.itemData(i)*1000)))
        self.vol = QSlider(Qt.Horizontal); self.vol.setRange(0, 100); self.vol.setValue(90); self.vol.setFixedWidth(110); self.vol.valueChanged.connect(lambda x: self.audio.setVolume(x/100))
        self.audio.setVolume(0.9)
        ctr = row(self.bplay, self.seek, self.time, QLabel("Kapitel"), self.chap, QLabel("Lautstärke"), self.vol, btn("Schließen", slot=self.close))
        ctr.setContentsMargins(16, 0, 16, 0); ctr.setStretchFactor(self.seek, 1); v.addLayout(ctr)
        try:
            with open(os.path.splitext(path)[0]+".json", encoding="utf-8") as fh: chapters = json.load(fh).get("chapters", [])
        except Exception: chapters = []
        for c in chapters: self.chap.addItem(c["name"], float(c["start"]))
        self.chap.setVisible(bool(chapters))
        self.player.positionChanged.connect(self._pos); self.player.durationChanged.connect(lambda d: (self.seek.setRange(0, d), self._pos(self.player.position())))
        self.player.playbackStateChanged.connect(lambda st: self.bplay._labels[0].setText(I["pause"] if st == QMediaPlayer.PlayingState else I["play"]))
        self.player.setSource(QUrl.fromLocalFile(path)); dark_title(self)
        QTimer.singleShot(200, self.player.play)
    def _pos(self, ms):
        if not self.seek.isSliderDown(): self.seek.setValue(ms)
        self.time.setText("%s / %s" % (fmt_time(ms/1000), fmt_time(self.player.duration()/1000)))
        for i in range(self.chap.count()-1, -1, -1):
            if ms/1000 >= self.chap.itemData(i)-0.2:
                if self.chap.currentIndex() != i: self.chap.setCurrentIndex(i)
                break
    def toggle(self):
        self.player.pause() if self.player.playbackState() == QMediaPlayer.PlayingState else self.player.play()
    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Space: self.toggle(); return
        super().keyPressEvent(e)
    def closeEvent(self, e):
        self.player.stop(); super().closeEvent(e)
    def reject(self):
        self.player.stop(); super().reject()

def show_tutorial(parent):
    path = tutorial_path()
    if not path:
        QMessageBox.information(parent, "Tutorial", "Das Tutorial-Video ist in dieser Installation nicht enthalten."); return
    if QMediaPlayer is None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(path)); return      # no Qt multimedia: system video player
    TutorialDialog(parent, path).exec()

# ============================================================== main window
def dark_title(w):
    """Windows 10/11: dark title bar."""
    try:
        import ctypes
        hwnd = int(w.winId()); v = ctypes.c_int(1)
        for attr in (20, 19): ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v), ctypes.sizeof(v))
    except Exception:
        pass

PAGES = [("mix", "mix", "Mixing", "MixPage"), ("master", "master", "Mastering", "MasterPage"), ("track", "track", "Spur-Angleich", "TrackPage"),
         ("stems", "stems", "Stems extrahieren", "StemsPage"), ("settings", "settings", "Einstellungen", "SettingsPage")]

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle(mc.APP_NAME); self.setMinimumSize(1120, 700)
        ico = mc.res_path("logo.ico")
        if ico: self.setWindowIcon(QIcon(ico))
        self.settings = mc.load_settings(); self.last_dir = self.settings.get("last_dir", os.path.expanduser("~"))
        mc.FORCE_CPU = self.settings.get("force_cpu", False); mc.VRAM_LIMIT_GB = self.settings.get("vram_limit")
        central = QWidget(); self.setCentralWidget(central); h = QHBoxLayout(central); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(0)
        side = QFrame(); side.setObjectName("sidebar"); side.setFixedWidth(232); sv = QVBoxLayout(side); sv.setContentsMargins(16, 20, 16, 16); sv.setSpacing(4)
        brand = QHBoxLayout(); brand.setSpacing(10)
        lg = QLabel(); png = mc.res_path("logo.png")
        if png: lg.setPixmap(QPixmap(png).scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        bt = QVBoxLayout(); bt.setSpacing(0); n = QLabel(mc.APP_NAME); n.setStyleSheet("font-size:12.5pt;font-weight:600;"); ver = QLabel("Version " + mc.APP_VERSION); ver.setObjectName("faint")
        bt.addWidget(n); bt.addWidget(ver); brand.addWidget(lg); brand.addLayout(bt); brand.addStretch(1); sv.addLayout(brand); sv.addSpacing(22)
        self.stack = QStackedWidget(); self.nav = QButtonGroup(self); self.pages = {}; self.keys = []
        for i, (key, glyph, text, cls) in enumerate(PAGES):
            b = QPushButton(); b.setObjectName("navBtn"); b.setCheckable(True); b.setCursor(Qt.PointingHandCursor); b.setMinimumHeight(42)
            bl = QHBoxLayout(b); bl.setContentsMargins(12, 0, 12, 0); bl.setSpacing(12)
            g = QLabel(I[glyph]); g.setStyleSheet(icon_css(12)); g.setAttribute(Qt.WA_TransparentForMouseEvents); t = QLabel(text); t.setAttribute(Qt.WA_TransparentForMouseEvents)
            bl.addWidget(g); bl.addWidget(t); bl.addStretch(1); b._g, b._t = g, t
            self.nav.addButton(b, i); sv.addWidget(b); b.toggled.connect(lambda on, b=b: self._nav_style(b, on))
            if key == "stems": sv.addStretch(1)
            page = globals()[cls](self); self.pages[key] = page; self.keys.append(key); self.stack.addWidget(page)
        tb = QPushButton(); tb.setObjectName("navBtn"); tb.setCursor(Qt.PointingHandCursor); tb.setMinimumHeight(42); tb.setToolTip("Kurzes Video (2½ Minuten): Mixi erklärt die wichtigsten Funktionen")
        tl = QHBoxLayout(tb); tl.setContentsMargins(12, 0, 12, 0); tl.setSpacing(12)
        tg = QLabel(I["play"]); tg.setStyleSheet(icon_css(12, C["amber"])); tg.setAttribute(Qt.WA_TransparentForMouseEvents)
        tt = QLabel("Tutorial ansehen"); tt.setStyleSheet("color:%s;" % C["muted"]); tt.setAttribute(Qt.WA_TransparentForMouseEvents)
        tl.addWidget(tg); tl.addWidget(tt); tl.addStretch(1); tb.clicked.connect(lambda: show_tutorial(self))
        sv.insertWidget(sv.count()-1, tb)
        self.gpu_chip = QLabel(""); self.gpu_chip.setWordWrap(True); self.gpu_chip.setStyleSheet("color:%s;font-size:8.5pt;padding:8px 10px;background:%s;border:1px solid %s;border-radius:8px;" % (C["muted"], C["card"], C["border"]))
        sv.insertWidget(sv.count()-1, self.gpu_chip)
        self.nav.idClicked.connect(lambda i: self.go(self.keys[i])); h.addWidget(side); h.addWidget(self.stack, 1)
        for key, p in self.pages.items(): p.restore(self.settings.get(key, {}))
        start = self.settings.get("page", "mix"); self.go(start if start in self.pages else "mix")
        QTimer.singleShot(400, self.first_run)
    def place(self):
        """Initial size (after construction, otherwise the layout pass overrides it): last geometry or 92 % of the screen."""
        ag = self.screen().availableGeometry(); g = self.settings.get("geometry")
        if g and QRectF(ag).intersects(QRectF(*g)) and g[2] >= 1120 and g[3] >= 700:
            self.setGeometry(*g)
        else:
            w, h = min(1600, int(ag.width()*0.92)), min(1020, int(ag.height()*0.92))
            self.setGeometry(ag.x()+(ag.width()-w)//2, ag.y()+(ag.height()-h)//2, w, h)
    def _nav_style(self, b, on):
        b._g.setStyleSheet(icon_css(12, C["acc"] if on else C["muted"])); b._t.setStyleSheet("color:%s;" % (C["text"] if on else C["muted"]))
    def go(self, key):
        i = self.keys.index(key); self.nav.button(i).setChecked(True); self.stack.setCurrentIndex(i); self.cur_key = key
        if key == "settings": self.pages["settings"].refresh()
        if key == "stems": self.pages["stems"].refresh_dev()
        if key == "master": self.pages["master"].reload_profiles()
        self.update_chip()
    def update_chip(self):
        if not mc.separation_available(): self.gpu_chip.setText("KI-Trennung: nicht installiert"); return
        g = mc.gpu_info()
        if mc.FORCE_CPU: t = "KI-Trennung: CPU (Einstellung)"
        elif g["ok"]: t = "%s\n%.1f / %.1f GB frei" % (g["name"].replace("NVIDIA GeForce ", ""), g["free_gb"], g["total_gb"])
        else: t = "KI-Trennung: CPU"
        self.gpu_chip.setText(t)
    def notify(self, title, text):
        QApplication.alert(self, 3000)
    def keyPressEvent(self, e):
        page = self.pages.get(getattr(self, "cur_key", ""))
        if e.key() == Qt.Key_Space and hasattr(page, "player") and not isinstance(QApplication.focusWidget(), (QLineEdit, QDoubleSpinBox)):
            page.player.toggle(); return
        super().keyPressEvent(e)
    def first_run(self):
        moved = getattr(self, "migrated", [])
        if moved:
            QMessageBox.information(self, mc.APP_NAME, "Aus dem Mastering-Tool übernommen: %d Profil(e) und Einstellungen.\nDie Daten des Mastering-Tools bleiben unverändert." %
                                    len([m for m in moved if m.endswith(".json") and "settings" not in m]))
        if not self.settings.get("tutorial_offered") and tutorial_path():
            self.settings["tutorial_offered"] = True; self.save()
            if QMessageBox.question(self, "Willkommen bei %s" % mc.APP_NAME, "Möchtest du ein kurzes Tutorial ansehen? Das Maskottchen Mixi erklärt in zweieinhalb Minuten die wichtigsten Funktionen.\n"
                                    "(Jederzeit wieder über „Tutorial ansehen“ in der Seitenleiste.)") == QMessageBox.Yes:
                show_tutorial(self)
        if self.settings.get("asked_shortcut"): return
        self.settings["asked_shortcut"] = True; self.save()
        if QMessageBox.question(self, "Desktop-Verknüpfung", "Eine Verknüpfung zu %s auf dem Desktop anlegen?\n(Später jederzeit unter Einstellungen.)" % mc.APP_NAME) == QMessageBox.Yes:
            self.pages["settings"].shortcut()
    def save(self):
        s = self.settings; s["last_dir"] = self.last_dir; gg = self.geometry(); s["geometry"] = [gg.x(), gg.y(), gg.width(), gg.height()]; s["page"] = getattr(self, "cur_key", "mix")
        for key, p in self.pages.items():
            if key != "settings": s[key] = p.state()
        try: mc.save_settings(s)
        except Exception: pass
    def closeEvent(self, e):
        for p in self.pages.values():
            if getattr(p, "cancel_ev", None): p.cancel_ev.set()
            if hasattr(p, "player"): p.player.stop()
        mc.kill_workers()           # separation processes would otherwise keep running (and hold the GPU) after the window is gone
        self.save(); super().closeEvent(e)

# ============================================================== splash + run
SPLASH_SECONDS = 5.0

def make_splash():
    W, H = 560, 320; pm = QPixmap(W, H); pm.fill(Qt.transparent)
    p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing)
    g = QLinearGradient(0, 0, W, H); g.setColorAt(0, QColor("#0b111a")); g.setColorAt(1, QColor("#0f2f3b"))
    p.setBrush(g); p.setPen(QPen(QColor(C["border2"]), 1)); p.drawRoundedRect(QRectF(0.5, 0.5, W-1, H-1), 18, 18)
    png = mc.res_path("logo.png")
    if png: p.drawPixmap(40, 76, QPixmap(png).scaled(128, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation))
    f = QFont("Segoe UI Variable Display"); f.setPointSize(26); f.setWeight(QFont.DemiBold); p.setFont(f); p.setPen(QColor(C["text"])); p.drawText(QRectF(196, 92, 340, 44), Qt.AlignLeft | Qt.AlignVCenter, mc.APP_NAME)
    f2 = QFont("Segoe UI"); f2.setPointSize(10); p.setFont(f2); p.setPen(QColor(C["muted"]))
    p.drawText(QRectF(198, 138, 330, 60), Qt.AlignLeft | Qt.TextWordWrap, "Mixing · Mastering · Spur-Angleich · KI-Stems\nVersion %s" % mc.APP_VERSION)
    p.end(); return pm

class Splash(QSplashScreen):
    def __init__(self):
        super().__init__(make_splash()); self.t0 = time.time(); self.msg = "Starte …"; self.setWindowFlag(Qt.WindowStaysOnTopHint)
    def drawContents(self, p):
        p.setRenderHint(QPainter.Antialiasing); W, H = self.width(), self.height()
        frac = min(1.0, (time.time()-self.t0)/SPLASH_SECONDS)
        r = QRectF(40, H-58, W-80, 5); p.setPen(Qt.NoPen); p.setBrush(QColor(255, 255, 255, 25)); p.drawRoundedRect(r, 2.5, 2.5)
        g = QLinearGradient(r.left(), 0, r.right(), 0); g.setColorAt(0, QColor(C["acc"])); g.setColorAt(1, QColor(C["amber"]))
        p.setBrush(g); p.drawRoundedRect(QRectF(r.left(), r.top(), r.width()*frac, r.height()), 2.5, 2.5)
        f = QFont("Segoe UI"); f.setPointSize(9); p.setFont(f); p.setPen(QColor(C["muted"])); p.drawText(QRectF(40, H-44, W-80, 22), Qt.AlignLeft, self.msg)
    def mousePressEvent(self, e): self.t0 = -1e9    # click skips

def run():
    if hasattr(Qt, "HighDpiScaleFactorRoundingPolicy"):
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    try:
        import ctypes; ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Mastern.Mixsmith.1")
    except Exception: pass
    app = QApplication.instance() or QApplication(sys.argv); app.setStyle(FastTips("Fusion")); app.setStyleSheet(QSS)
    global USE_ICON_FONT
    fams = set(QFontDatabase.families())
    if ICON_FONT not in fams and "Segoe MDL2 Assets" not in fams: USE_ICON_FONT = False; I.update(FALLBACK_ICONS)     # Linux / macOS
    pal = app.palette(); pal.setColor(QPalette.Window, QColor(C["bg"])); pal.setColor(QPalette.Base, QColor(C["field"])); pal.setColor(QPalette.Text, QColor(C["text"]))
    pal.setColor(QPalette.WindowText, QColor(C["text"])); pal.setColor(QPalette.ButtonText, QColor(C["text"])); pal.setColor(QPalette.Highlight, QColor(C["acc_d"])); app.setPalette(pal)
    ico = mc.res_path("logo.ico")
    if ico: app.setWindowIcon(QIcon(ico))
    skip_splash = "--no-splash" in sys.argv or os.environ.get("MT_NO_SPLASH")
    sp = None
    if not skip_splash:
        sp = Splash(); sp.show(); app.processEvents()
    steps = ["Lade Profile …", "Prüfe Grafikkarte …", "Baue Oberfläche …", "Fast fertig …"]
    def msg(i):
        if sp: sp.msg = steps[i]; sp.repaint(); app.processEvents()
    msg(0); moved = mc.migrate_legacy(); mc.list_profiles(); msg(1); mc.gpu_info(); msg(2)
    win = MainWindow(); win.migrated = moved; msg(3)
    def show():
        win.show(); win.place(); dark_title(win)
        if sp: sp.finish(win)
    if sp:
        timer = QTimer(); timer.setInterval(40)
        def tick():
            sp.repaint()
            if time.time()-sp.t0 >= SPLASH_SECONDS: timer.stop(); show()
        timer.timeout.connect(tick); timer.start(); app._splash_timer = timer
    else:
        show()
    return app.exec()

if __name__ == "__main__":
    run()
