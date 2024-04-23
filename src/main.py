import sys
from PyQt5.QtWidgets import QApplication
from gui import MacroPadApp
from serial_manager import SerialManager
from utils import resource_path  # Import the resource_path function
from PyQt5.QtGui import QIcon

def main():
    app = QApplication(sys.argv)
    ex = MacroPadApp()
    
    # Set the window icon
    ex.setWindowIcon(QIcon(resource_path('Assets/Images/icon.ico')))
    
    serial_manager = SerialManager(ex.handle_received_data)
    serial_manager.start()
    ex.load_stylesheet()  # Make sure stylesheet is loaded here
    ex.show()
    exit_code = app.exec_()
    sys.exit(exit_code)

if __name__ == '__main__':
    main()
