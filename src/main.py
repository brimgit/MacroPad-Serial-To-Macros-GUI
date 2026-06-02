import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon
from gui import MacroPadApp
from utils import resource_path
import theme

# Prevent SIP from destroying C++ Qt objects during Python shutdown.
# Without this, PyQt5 crashes on exit with Python 3.12+ (STATUS_STACK_BUFFER_OVERRUN).
from PyQt5 import sip
sip.setdestroyonexit(False)


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(theme.build_stylesheet())

    icon_path = resource_path('Assets/Images/icon.ico')
    app.setWindowIcon(QIcon(icon_path))

    window = MacroPadApp()
    window.show()

    ret = app.exec_()
    sys.exit(ret)


if __name__ == '__main__':
    main()
