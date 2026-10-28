# Lizenzen

## Mixsmith

Copyright © 2026 Kay Seufferheld (Kieselwerk, Augsburg)

Mixsmith ist freie Software: Sie können es unter den Bedingungen der **GNU General Public License, Version 3** weitergeben und verändern (vollständiger Text: `LICENSE`).
Mixsmith wird ohne jede Gewährleistung bereitgestellt, auch ohne die implizite Gewährleistung der Marktreife oder der Eignung für einen bestimmten Zweck.

Der vollständige Quelltext (`Mixsmith-<Version>-Quelltext.zip`) steht auf derselben Download-Seite wie das Programm.

Warum GPLv3: Mixsmith nutzt **pedalboard** (Spotify, GPLv3) für Hall, Kompressor und Filter, und die Windows-Vollversion liefert ein unter GPL gebautes **ffmpeg** mit. Beides setzt voraus, dass auch Mixsmith unter GPLv3 steht.

## Mitgelieferte Bibliotheken

| Bibliothek | Lizenz | Quelle |
|---|---|---|
| pedalboard | GPL-3.0 | https://github.com/spotify/pedalboard |
| PySide6 / Qt for Python, shiboken6 | LGPL-3.0 | https://www.qt.io/qt-for-python |
| NumPy | BSD-3-Clause | https://numpy.org |
| SciPy | BSD-3-Clause | https://scipy.org |
| soundfile (mit libsndfile, LGPL-2.1) | BSD-3-Clause | https://github.com/bastibe/python-soundfile |
| sounddevice (mit PortAudio, MIT) | MIT | https://github.com/spatialaudio/python-sounddevice |
| pyloudnorm | MIT | https://github.com/csteinmetz1/pyloudnorm |
| Numba, llvmlite | BSD-2-Clause, Apache-2.0 mit LLVM-Ausnahme | https://numba.pydata.org |

Nur in der Vollversion (KI-Trennung):

| Bibliothek | Lizenz | Quelle |
|---|---|---|
| python-audio-separator | MIT | https://github.com/nomadkaraoke/python-audio-separator |
| PyTorch, torchaudio | BSD-3-Clause (NVIDIA-CUDA-Laufzeit: NVIDIA-Lizenz, weitergabefähig) | https://pytorch.org |
| Demucs (Code und Modell htdemucs_6s) | MIT | https://github.com/facebookresearch/demucs |
| librosa, resampy | ISC | https://librosa.org |
| ONNX Runtime | MIT | https://onnxruntime.ai |
| julius, einops, beartype, rotary-embedding-torch, samplerate, pydub, PyYAML | MIT | PyPI |
| ml_collections, requests | Apache-2.0 | PyPI |
| tqdm | MPL-2.0 und MIT | https://github.com/tqdm/tqdm |
| ffmpeg 7.1 (Build von gyan.dev, `bin/ffmpeg.exe`) | GPL-3.0 | Quelltext: https://ffmpeg.org/releases/ffmpeg-7.1.tar.xz, Build: https://www.gyan.dev/ffmpeg/builds/ |

Die Lizenztexte der Python-Bibliotheken liegen in den Programmdateien jeweils im Ordner `<paket>.dist-info`.

## KI-Modelle

Mitgeliefert wird nur das Demucs-Modell **htdemucs_6s** (MIT, Meta AI). Alle anderen Modelle liefert Mixsmith **nicht** mit. Es lädt sie beim ersten Einsatz über python-audio-separator aus den Quellen der jeweiligen Autoren in den Benutzerordner. Für diese Modelle gelten die Bedingungen ihrer Autoren:

| Modell | Autor | Wofür |
|---|---|---|
| BS-RoFormer SW | MVSEP | Stem-Trennung in 6 Spuren |
| BS-RoFormer Viperx (ep 317) | viperx | Gesang / Instrumental |
| htdemucs_ft | Meta AI (MIT) | Stem-Trennung in 4 Spuren |
| MDX23C DrumSep | aufr33 & jarredou | Schlagzeug-Trennung |
| MDX23C De-Reverb | aufr33 & jarredou | Effektanalyse (Hall) |
| UVR De-Echo Normal | FoxJoy (Ultimate Vocal Remover) | Effektanalyse (Delay) |

## Profile

Die mitgelieferten Mastering-Profile („Laut und hell“, „Streaming-Standard“) enthalten nur Messwerte (Lautheit, Stereobreite, Spektrumskurve), keine Audiodaten.

## Tutorial-Video

Maskottchen, Grafik und Text des Tutorial-Videos stammen von Kieselwerk. Die Stimme wurde mit einer Microsoft-Neural-Stimme (Katja) über edge-tts erzeugt.
