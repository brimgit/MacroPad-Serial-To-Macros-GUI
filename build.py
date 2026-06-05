"""
MacroPad build script
---------------------
Produces a standalone Windows installer at:
    dist_build/MacroPad_Setup_vX.X.X.exe

Steps
  1. npm run build     — compile the React frontend
  2. PyInstaller       — bundle Python + deps into dist_build/MacroPad/
  3. Inno Setup        — wrap that into a single .exe installer
                         (skipped if Inno Setup is not installed)

Requirements
  pip install pyinstaller
  Inno Setup 6: https://jrsoftware.org/isdl.php   (for step 3)
  Serial drivers in installer/drivers/             (run installer/download_drivers.py)
"""

import subprocess
import sys
import os
import shutil

ROOT    = os.path.dirname(os.path.abspath(__file__))
VERSION = open(os.path.join(ROOT, 'version.txt')).read().strip()

ISCC_PATHS = [
    r'C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
    r'C:\Program Files\Inno Setup 6\ISCC.exe',
]


def run(cmd, cwd=None):
    print(f'\n>>> {cmd}')
    r = subprocess.run(cmd, shell=True, cwd=cwd or ROOT)
    if r.returncode != 0:
        print(f'\nFAILED (exit {r.returncode})')
        sys.exit(r.returncode)


def header(text):
    print(f'\n{"="*60}\n  {text}\n{"="*60}')


# ── 1. Build React frontend ────────────────────────────────────────────────────
header(f'1/3  Building React frontend  (MacroPad v{VERSION})')
run('npm run build', cwd=os.path.join(ROOT, 'frontend'))


# ── 2. PyInstaller ────────────────────────────────────────────────────────────
header('2/3  Bundling with PyInstaller')

# Clean previous build artifacts so nothing stale gets into the bundle
for d in ('dist_build', 'build_tmp'):
    p = os.path.join(ROOT, d)
    if os.path.exists(p):
        shutil.rmtree(p)

run(
    f'"{sys.executable}" -m PyInstaller '
    f'--noconfirm '
    f'--distpath "{os.path.join(ROOT, "dist_build")}" '
    f'--workpath "{os.path.join(ROOT, "build_tmp")}" '
    f'"{os.path.join(ROOT, "MacroPad.spec")}"'
)


# ── 3. Inno Setup installer ───────────────────────────────────────────────────
header('3/3  Compiling Inno Setup installer')

iscc = next((p for p in ISCC_PATHS if os.path.exists(p)), None)
if not iscc:
    print('⚠  Inno Setup not found — skipping installer step.')
    print('   Download from: https://jrsoftware.org/isdl.php')
    print(f'\nDONE  PyInstaller output ready: dist_build\\MacroPad\\MacroPad.exe')
    sys.exit(0)

run(
    f'"{iscc}" '
    f'/DAppVersion={VERSION} '
    f'"{os.path.join(ROOT, "installer", "macropad.iss")}"'
)

print(f'\nDONE  Installer ready: dist_build\\MacroPad_Setup_v{VERSION}.exe')
