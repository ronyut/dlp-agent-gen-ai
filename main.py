import sys
import win32api

from monitors.base import Win32MessageWindow
from monitors.paste_monitor import start_paste_monitor, stop_paste_monitor
from monitors.file_upload_monitor import start_file_upload_monitor, stop_file_upload_monitor
from utils import console_handler
from utils.logger import agent_logger

if __name__ == "__main__":
    # Register the native Windows control handler for graceful exit
    win32api.SetConsoleCtrlHandler(console_handler, True)

    # Initialize the Hidden Service Window
    agent_window = Win32MessageWindow(message_map={})

    print("--- Endpoint DLP Agent ---")
    print("[*] Initializing System Hooks...")
    
    paste_hook_h = start_paste_monitor()
    file_hook_h = start_file_upload_monitor()

    try:
        if not paste_hook_h or not file_hook_h:
            print("[-] Critical Error: Failed to initialize one or more monitors.")
            sys.exit(1)

        print("[+] Agent Active: Monitoring ChatGPT (Chrome) for PII and File Uploads.")
        print("[*] Press Ctrl+C to stop the agent safely.")

        # Start the Message Pump
        # This is a blocking call that 'listens' to the OS.
        # It services BOTH the keyboard hook and the window event hook.
        agent_window.start() 
        
    except Exception as e:
        print(f"\n[!] Runtime Error: {e}")
        
    finally:
        print("\n[*] Performing safety cleanup...")
        
        stop_paste_monitor()
        stop_file_upload_monitor()
        agent_logger.shutdown()
        
        print("[+] Cleanup complete. Agent terminated.")
