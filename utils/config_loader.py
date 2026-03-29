import json
import os

class Config:
    def __init__(self):
        self.settings = {
            "monitors": {
                "target_process": "chrome.exe",
                "target_window_title": "ChatGPT",
                "google_drive_origin": "googleusercontent.com",
            },
            "logging": {
                "log_file": "alerts.log",
            },
        }
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
            self._deep_merge(self.settings, loaded)
        except Exception as e:
            print(f"[!] Config load warning: {e}. Using defaults.")

    def _deep_merge(self, base, override):
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
    
    def get(self, key, default=None):
        keys = key.split('.')
        val = self.settings
        for k in keys:
            if not isinstance(val, dict):
                return default
            val = val.get(k, None)
            if val is None: return default
        return val

# Singleton instance
app_config = Config()