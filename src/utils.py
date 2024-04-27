
import os
import sys

def resource_path(relative_path):
    """ Get absolute path to resource, works for development and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)

def get_data_path(filename):
    """ Get the path to data files, ensures it's writable """
    if getattr(sys, 'frozen', False):
        # If the application is run as a bundle, the writable directory is set to the user's app data directory
        app_name = "BrimPad"
        app_data_path = os.path.join(os.getenv('APPDATA'), app_name)
        if not os.path.exists(app_data_path):
            os.makedirs(app_data_path)
        return os.path.join(app_data_path, filename)
    else:
        # The application is not packaged, use the current directory
        return os.path.join('Data', filename)