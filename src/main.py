import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon
from gui import MacroPadApp
from utils import resource_path  # Import the resource_path function

def load_stylesheet():
    try:
        with open(resource_path('Data/style.css'), 'r') as f:
            stylesheet = f.read()
            return stylesheet
    except Exception as e:
        print(f"Failed to load stylesheet: {e}")
        return ""

def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(load_stylesheet())  # Apply the stylesheet globally

    ex = MacroPadApp()
    ex.setWindowIcon(QIcon(resource_path('Assets/Images/icon.ico')))  # Set the window icon

    ex.show()
    exit_code = app.exec_()
    sys.exit(exit_code)

if __name__ == '__main__':
    main()
