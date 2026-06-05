# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_all

ROOT = SPECPATH  # directory containing this .spec file

# Collect all sub-modules and data for packages that use dynamic imports
datas_pycaw,    bins_pycaw,    hidden_pycaw    = collect_all('pycaw')
datas_comtypes, bins_comtypes, hidden_comtypes = collect_all('comtypes')
datas_webview,  bins_webview,  hidden_webview  = collect_all('webview')
datas_keyboard, bins_keyboard, hidden_keyboard = collect_all('keyboard')

a = Analysis(
    [os.path.join(ROOT, 'src', 'main_webview.py')],
    pathex=[os.path.join(ROOT, 'src')],
    binaries=[
        *bins_pycaw,
        *bins_comtypes,
        *bins_webview,
        *bins_keyboard,
    ],
    datas=[
        (os.path.join(ROOT, 'frontend', 'dist'), 'frontend/dist'),
        (os.path.join(ROOT, 'version.txt'), '.'),
        *datas_pycaw,
        *datas_comtypes,
        *datas_webview,
        *datas_keyboard,
    ],
    hiddenimports=[
        'api', 'serial_manager', 'volume_manager', 'macro_manager',
        'profile_manager', 'foreground_watcher', 'utils',
        'serial', 'serial.tools', 'serial.tools.list_ports',
        'psutil', 'ctypes', 'winreg', 'subprocess',
        *hidden_pycaw,
        *hidden_comtypes,
        *hidden_webview,
        *hidden_keyboard,
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'tkinter', 'matplotlib'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MacroPad',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=os.path.join(ROOT, 'Assets', 'Images', 'icon.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MacroPad',
)
