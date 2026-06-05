# -*- coding: utf-8 -*-
"""
Download USB serial drivers for ESP32 boards into installer/drivers/.

  python installer/download_drivers.py

Drivers:
  drivers/CH341SER.exe         - CH340/CH341 chip (most cheap/clone boards)
  drivers/cp210x/silabser.inf  - CP2102/CP210x chip (official Espressif boards)
                                 Installed via pnputil (Windows built-in)

Run this once before  python build.py.
"""

import urllib.request
import os
import zipfile
import shutil
import io

DRIVERS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'drivers')
os.makedirs(DRIVERS_DIR, exist_ok=True)

CH340_DEST  = os.path.join(DRIVERS_DIR, 'CH341SER.exe')
CP210X_DIR  = os.path.join(DRIVERS_DIR, 'cp210x')

# CH340 is now installed via winget during setup — no file needed here
CP210X_URL = 'https://www.silabs.com/documents/public/software/CP210x_Universal_Windows_Driver.zip'

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
    )
}


def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


# ── CH340 ──────────────────────────────────────────────────────────────────────
if os.path.exists(CH340_DEST):
    print(f'CH340  driver already present.')
else:
    print(f'Downloading CH340 driver (WCH)...')
    try:
        data = fetch(CH340_URL)
        if data[:2] == b'MZ':
            with open(CH340_DEST, 'wb') as f:
                f.write(data)
            print(f'  OK  ({len(data)//1024} KB)')
        else:
            raise ValueError('Server returned HTML — site blocks direct downloads')
    except Exception as e:
        print(f'  FAIL: {e}')
        print('  Manual: https://www.wch-ic.com/downloads/CH341SER_EXE.html')
        print('  Save as: installer\\drivers\\CH341SER.exe')
print()


# ── CP210x ─────────────────────────────────────────────────────────────────────
if os.path.exists(os.path.join(CP210X_DIR, 'silabser.inf')):
    print(f'CP210x driver already present.')
else:
    print(f'Downloading CP210x driver (Silicon Labs)...')
    try:
        data = fetch(CP210X_URL)
        os.makedirs(CP210X_DIR, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            z.extractall(CP210X_DIR)
        print(f'  OK  ({len(data)//1024} KB, extracted to drivers\\cp210x\\)')
    except Exception as e:
        print(f'  FAIL: {e}')
        print('  Manual: https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers')
        print('  Extract the zip to installer\\drivers\\cp210x\\')
print()


# ── Summary ────────────────────────────────────────────────────────────────────
ch340_ok  = os.path.exists(CH340_DEST)
cp210x_ok = os.path.exists(os.path.join(CP210X_DIR, 'silabser.inf'))
print('=' * 50)
print(f'  CH340  driver : {"ready" if ch340_ok  else "MISSING"}')
print(f'  CP210x driver : {"ready" if cp210x_ok else "MISSING"}')
print('=' * 50)
print('\nRun  python build.py  to build the installer.')
