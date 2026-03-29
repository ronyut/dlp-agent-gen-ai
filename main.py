import os
import sys
import win32api
import win32gui
import signal
from concurrent.futures import ThreadPoolExecutor
from monitors.base import Win32MessageWindow
from monitors.paste_monitor import start_paste_monitor, stop_paste_monitor
#from monitors.file_monitor import file_upload_monitor

def console_handler(ctrl_type):
    """
    Handles Ctrl+C and Window Close events natively in Windows.
    Returns True to indicate we handled the event.
    """
    if ctrl_type in (0, 2):  # 0 = CTRL_C_EVENT, 2 = CTRL_CLOSE_EVENT
        print("\n[!] Ctrl+C detected. Terminating Message Pump...")
        # Force the PumpMessages() loop to exit
        win32gui.PostQuitMessage(0)
        return True
    return False

if __name__ == "__main__":
    win32api.SetConsoleCtrlHandler(console_handler, True)

    # 1. Initialize the Service Window (The Message Pump provider)
    # We pass an empty map because the Keyboard Hook handles its own routing
    agent_window = Win32MessageWindow(message_map={})

    # 2. Start the blocking File Monitor in a worker thread
    # This prevents the directory watcher from freezing the clipboard logic
    #executor = ThreadPoolExecutor(max_workers=1)
    #executor.submit(file_upload_monitor)

    # 3. Register the Keyboard Hook
    # This MUST stay on the main thread to be serviced by agent_window.start()
    hook_h = start_paste_monitor()

    try:
        print("DLP Agent is active (Monitoring ChatGPT Ctrl+V & File Uploads)...")
        
        # 4. Start the Pump
        # This blocks the main thread and services the OS callbacks
        agent_window.start() 
        
    except KeyboardInterrupt:
        print("\nShutting down DLP Agent...")
    except Exception as e:
        print(f"\nCritical Error: {e}")
    finally:
        # 5. Deterministic Cleanup
        print("Cleaning up system hooks and threads...")
        stop_paste_monitor()
        # Ensure executor shuts down
        if 'executor' in locals():
            executor.shutdown(wait=False)
        os._exit(0)