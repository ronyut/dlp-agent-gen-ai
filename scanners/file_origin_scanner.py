import configparser
import os
from urllib.parse import urlparse
from utils.config_loader import app_config

def get_file_origin(filepath):
    # The specific ADS path for the Mark of the Web
    ads_path = f"{filepath}:Zone.Identifier"
    
    if not os.path.exists(ads_path):
        print("No origin metadata found (or file wasn't downloaded via a browser)")
        return None

    # Use configparser to read the stream
    config = configparser.ConfigParser()
    try:
        with open(ads_path, 'r', encoding='utf-8') as f:
            # We add a dummy section header because Zone.Identifier 
            # files usually start with [ZoneTransfer]
            config.read_file(f)
            
            host_url = config.get('ZoneTransfer', 'HostUrl', fallback=None)
            print(f"Extracted Host URL from ADS: {host_url}")
            return host_url
    except Exception as e:
        print(f"Error reading ADS: {e}")
        return None


def is_google_drive_file(file_path):
    host_url = get_file_origin(file_path)
    if not host_url:
        return False

    token = app_config.get("monitors.google_drive_origin", "googleusercontent.com")
    parsed = urlparse(host_url)
    hostname = (parsed.hostname or "").lower()

    if hostname:
        return hostname == token or hostname.endswith(f".{token}")

    # Fallback for malformed URLs where hostname cannot be parsed
    return token in host_url.lower()