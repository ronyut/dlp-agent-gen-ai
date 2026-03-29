import configparser
import os

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
            return host_url
    except Exception as e:
        print(f"Error reading ADS: {e}")
        return None

def file_origin_scanner(file_path):
    return TARGET_CHATBOT_URL in get_file_origin(file_path)