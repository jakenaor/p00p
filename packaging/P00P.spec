# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


PROJECT = Path(SPECPATH).resolve().parent
ICON = PROJECT / "packaging" / "P00P.icns"

#MARK: collect the python and qml guts
a = Analysis(
    [str(PROJECT / "qt_gui.py")],
    pathex=[str(PROJECT)],
    binaries=[],
    datas=[(str(PROJECT / "qml"), "qml")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "customtkinter"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

#MARK: make the arm mac thingy
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="P00P",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    argv_emulation=False,
    target_arch="arm64",
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON),
)

collect = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="P00P",
)

#MARK: wrap it in the clickable app rectangle
app = BUNDLE(
    collect,
    name="P00P.app",
    icon=str(ICON),
    bundle_identifier="club.hack.p00p",
    version="0.2.0",
    info_plist={
        "CFBundleDisplayName": "P00P",
        "CFBundleName": "P00P",
        "CFBundleShortVersionString": "0.2.0",
        "CFBundleVersion": "0.2.0",
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
        "NSHumanReadableCopyright": "Made by Jnaor for Hack Club Crescent",
    },
)
