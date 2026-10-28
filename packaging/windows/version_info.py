# -*- coding: utf-8 -*-
"""Writes the Windows version resource of Mixsmith.exe (company, product, copyright, place) for PyInstaller --version-file.

  python packaging/windows/version_info.py  ->  packaging/windows/version_info.txt"""
import os, re
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
VER = re.search(r'APP_VERSION = "([^"]+)"', open(os.path.join(ROOT, "audio_core.py"), encoding="utf-8").read()).group(1)
nums = tuple((list(map(int, VER.split("."))) + [0, 0, 0, 0])[:4])
STRINGS = {
    "CompanyName": "Kieselwerk – Kay Seufferheld, Augsburg",
    "FileDescription": "Mixsmith – Mischen und Mastern nach Referenzsongs",
    "FileVersion": VER,
    "InternalName": "Mixsmith",
    "LegalCopyright": "© 2026 Kay Seufferheld, Kieselwerk, Augsburg. GNU GPLv3.",
    "OriginalFilename": "Mixsmith.exe",
    "ProductName": "Mixsmith",
    "ProductVersion": VER,
    "Comments": "https://kieselwerk.com · https://github.com/Kieselwerk/Mixsmith",
}
entries = ",\n          ".join("StringStruct(%r, %r)" % kv for kv in STRINGS.items())
txt = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={nums}, prodvers={nums}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040704B0', [
          {entries}])]),
    VarFileInfo([VarStruct('Translation', [0x0407, 1200])])
  ]
)
"""
open(os.path.join(HERE, "version_info.txt"), "w", encoding="utf-8").write(txt)
print(os.path.join(HERE, "version_info.txt"))
