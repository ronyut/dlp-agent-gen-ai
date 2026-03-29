import json
import os

class Config:
    def __init__(self):
        self.settings = {}
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')
        
        with open(config_path, 'r') as f:
            self.settings = json.load(f)
    
    def get(self, key, default=None):
        keys = key.split('.')
        val = self.settings
        for k in keys:
            val = val.get(k, None)
            if val is None: return default
        return val

# Singleton instance
app_config = Config()