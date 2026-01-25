import os
import json
import logging

CONFIG_FILE = 'system_config.json'

DEFAULT_CONFIG = {
    'hide_dummies': False,   # True: Hide dummy users from normal search/match
    'log_level': 4           # 1: DEBUG, 2: INFO, 3: WARNING, 4: ERROR, 5: CRITICAL
}

def get_system_config():
    """Load system config from JSON file, returning defaults if missing."""
    if not os.path.exists(CONFIG_FILE):
        return DEFAULT_CONFIG.copy()
    
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Merge with defaults to ensure all keys exist
            config = DEFAULT_CONFIG.copy()
            config.update(data)
            return config
    except Exception as e:
        logging.error(f"Failed to load system config: {e}")
        return DEFAULT_CONFIG.copy()

def update_system_config(key, value):
    """Update a specific key in the system config and save to file."""
    config = get_system_config()
    config[key] = value
    
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        logging.error(f"Failed to save system config: {e}")
        return False

def get_log_file_path(app_debug=False):
    """Return the absolute path to the log file based on environment."""
    if app_debug:
        return os.path.abspath("debug.log")
    else:
        return os.path.abspath("logs/echomind.log")
