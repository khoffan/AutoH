# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for AutoH. Build with:  venv\Scripts\python.exe scripts\build.py
#
# One-folder build (dist\AutoH\AutoH.exe + _internal\), no UPX:
# - one-file + UPX executables are flagged by antivirus far more often
# - one-file unpacks to %TEMP% on every start, slow with onnxruntime
# The speech model is NOT bundled here; build.py copies it to dist\AutoH\models\.
from PyInstaller.utils.hooks import collect_data_files

ROOT = SPECPATH + "\\.."

a = Analysis(
    [ROOT + "\\app\\main.py"],
    pathex=[ROOT + "\\app"],
    binaries=[],
    datas=collect_data_files("customtkinter") + [
        (ROOT + "\\assets\\autoH_icon.ico", "assets"),   # tray icon (ui/tray.py)
    ],
    hiddenimports=[
        # imported lazily inside functions, so analysis may not see them
        "pythaiasr.typhoon",
        "sounddevice",
        "onnxruntime",
        "ui.voice_settings",
        "pystray._win32",   # pystray picks its backend at runtime
        "PIL.Image",
        "PIL.ImageDraw",
        "pycaw.pycaw",      # voice/system.py: volume (lazy import)
        "comtypes.shelllink",
        "comtypes.persist",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # optional extras of pythaiasr / dev-only tools: never needed at runtime
        "torch", "torchaudio", "transformers", "datasets", "librosa", "scipy",
        "pandas", "matplotlib", "numba", "onnx", "sherpa_onnx", "pyctcdecode",
        "faster_whisper", "ctranslate2", "PyInstaller", "pytest",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AutoH",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[ROOT + "\\assets\\autoH_icon.ico"],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="AutoH",
)
