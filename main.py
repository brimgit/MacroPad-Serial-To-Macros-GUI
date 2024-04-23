import sys
from PyQt5.QtWidgets import QApplication
from src.gui import MacroPadApp
from src.serial_manager import SerialManager

def main():
    app = QApplication(sys.argv)
    ex = MacroPadApp()
    
    serial_manager = SerialManager(ex.handle_received_data)
    serial_manager.start()
    ex.load_stylesheet()  # Make sure stylesheet is loaded here
    ex.show()
    exit_code = app.exec_()
    sys.exit(exit_code)

if __name__ == '__main__':
    main()
