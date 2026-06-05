"""
MacroPad dev launcher — double-click or run with Python.

Always starts the Vite dev server in a new console window, waits for it to
be ready, then opens the pywebview window.  The Vite window closes
automatically when the app exits.

For a production (no-npm) build, run  npm run build  in frontend/ first,
then launch with:  python src/main_webview.py
"""
import sys
import os
import time
import subprocess
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, 'src'))
os.chdir(ROOT)

VITE_URL = 'http://localhost:5173'


def _wait_for_vite(timeout=40):
    for _ in range(timeout * 2):
        try:
            urllib.request.urlopen(VITE_URL, timeout=1)
            return True
        except Exception:
            time.sleep(0.5)
    return False


# Open npm in its own console so Vite output is visible
npm_proc = subprocess.Popen(
    ['cmd', '/k', 'cd /d frontend && npm run dev'],
    cwd=ROOT,
    creationflags=subprocess.CREATE_NEW_CONSOLE,
)

if not _wait_for_vite():
    npm_proc.terminate()
    raise RuntimeError('Vite dev server did not start within 40 s')

sys.argv.append('--dev')

try:
    from main_webview import main
    main()
finally:
    if npm_proc.poll() is None:
        npm_proc.terminate()
