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

    # In dev: point to Vite dev server. In production: point to built dist.
    dev_mode = '--dev' in sys.argv
    url = 'http://localhost:5173' if dev_mode else os.path.join(
        os.path.dirname(__file__), '..', 'frontend', 'dist', 'index.html'
    )

    window = webview.create_window(
        title     = 'MacroPad',
        url       = url,
        js_api    = api,
        width     = 1100,
        height    = 720,
        min_size  = (900, 620),
        frameless = False,
    )

    api.set_window(window)
    webview.start(debug=False)


if __name__ == '__main__':
    main()
