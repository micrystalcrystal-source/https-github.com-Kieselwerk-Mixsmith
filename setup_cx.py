# -*- coding: utf-8 -*-
"""Builds a Windows MSI installer (light version without AI separation):  python setup_cx.py bdist_msi"""
from cx_Freeze import setup, Executable

build_exe_options = dict(
    packages=["numpy", "scipy", "soundfile", "sounddevice", "pyloudnorm", "pedalboard", "PySide6", "audio_core", "mix_core", "mixsmith_gui"],
    excludes=["numba", "llvmlite", "matplotlib", "torch", "torchaudio", "torchvision", "audio_separator", "onnxruntime", "onnx", "librosa",
              "PIL", "pandas", "IPython", "pytest", "test", "unittest", "tkinter", "pydoc_data"],
    include_files=[("profiles", "profiles"), ("README.md", "README.md"), ("LICENSE", "LICENSE"), ("LIZENZEN.md", "LIZENZEN.md"), ("logo.ico", "logo.ico"), ("logo.png", "logo.png")],
    include_msvcr=True,
    optimize=1,
)
bdist_msi_options = dict(
    upgrade_code="{C0D68F85-F156-42B0-A222-5F54442AAF0B}",
    add_to_path=False,
    initial_target_dir=r"[ProgramFilesFolder]\Mixsmith",
    install_icon="logo.ico",
    summary_data={"author": "Kieselwerk", "comments": "Mixing und Mastering nach Referenz"},
)
setup(
    name="Mixsmith",
    version="1.0.1",
    description="Mixing und Mastering nach Referenz",
    options={"build_exe": build_exe_options, "bdist_msi": bdist_msi_options},
    executables=[Executable("mixsmith.py", base="gui", target_name="Mixsmith.exe", icon="logo.ico",
                            shortcut_name="Mixsmith", shortcut_dir="ProgramMenuFolder")],
)
