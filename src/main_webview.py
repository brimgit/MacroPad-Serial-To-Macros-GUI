import sys
import os
import logging

logging.basicConfig(level=logging.WARNING, format='%(levelname)s %(name)s: %(message)s')

# Add src to path so imports work
sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))

import webview
from api import MacroPadAPI

def main():
    api = MacroPadAPI()

    dev_mode = '--dev' in sys.argv
    if getattr(sys, 'frozen', False):
        # PyInstaller bundle — frontend/dist is extracted alongside our resources
        url = os.path.join(sys._MEIPASS, 'frontend', 'dist', 'index.html')
    elif dev_mode:
        url = 'http://localhost:5173'
    else:
        url = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'dist', 'index.html')

    window = webview.create_window(
        title     = 'MacroPad',
        url       = url,
        js_api    = api,
        width     = 1100,
        height    = 720,
        min_size  = (900, 620),
        frameless = True,
    )

    api.set_window(window)
    # Force Edge (WebView2) backend when running as a bundled exe — PyQt5 is not bundled
    gui = 'edgechromium' if getattr(sys, 'frozen', False) else None
    webview.start(debug=False, gui=gui)


if __name__ == '__main__':
    main()
