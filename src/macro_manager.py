import json
import os
import logging

macros = {}

logging.basicConfig(level=logging.INFO)

def set_macro(command, action):
    macros[command] = action

def save_macros():
    file_path = os.path.join(os.path.dirname(__file__), '../Data/macros.json')
    try:
        with open(file_path, 'w') as f:
            json.dump(macros, f)
        logging.info("Macros saved successfully.")
    except IOError as e:
        logging.error(f"Failed to save macros: {e}")

def reload_macros():
    file_path = os.path.join(os.path.dirname(__file__), '../Data/macros.json')
    try:
        with open(file_path, 'r') as f:
            loaded_macros = json.load(f)
            macros.update(loaded_macros)  # Update the local dictionary
            logging.info("Macros reloaded successfully.")
            return loaded_macros
    except FileNotFoundError:
        logging.warning("Macros file not found, loading defaults.")
        return {}
    except json.JSONDecodeError:
        logging.error("Error decoding JSON, loading defaults.")
        return {}

def delete_macro(command):
    if command in macros:
        del macros[command]
        save_macros()  # Save changes immediately after modification
        
def get_macro(command):
    # Return the action associated with the command or None if it doesn't exist
    return macros.get(command, None)
