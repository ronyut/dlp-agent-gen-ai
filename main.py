import os
import sys
import win32api
import win32gui
import ctypes

# Internal Monitor Imports
from monitors.base import Win32MessageWindow
from monitors.paste_monitor import start_paste_monitor, stop_paste_monitor
from monitors.file_upload_monitor import start_file_upload_monitor, stop_file_upload_monitor

def console_handler(ctrl_type):
    """
    Handles Ctrl+C and Window Close events natively in Windows.
    This ensures we unhook from the OS before the process dies.
    """
    if ctrl_type in (0, 2):  # 0 = CTRL_C_EVENT, 2 = CTRL_CLOSE_EVENT
        print("\n[!] Shutdown signal received. Breaking Message Pump...")
        
        # PostQuitMessage(0) causes GetMessage/PumpMessages to return 0, 
        # allowing the 'try' block to finish and hit the 'finally' block.
        win32gui.PostQuitMessage(0)
        return True
    return False

if __name__ == "__main__":
    # 1. Register the native Windows control handler for graceful exit
    win32api.SetConsoleCtrlHandler(console_handler, True)

    # 2. Initialize the Hidden Service Window
    # This window provides the 'Handle' (HWND) required for certain Win32 operations
    agent_window = Win32MessageWindow(message_map={})

    print("--- Lenovo Endpoint DLP Agent ---")
    print("[*] Initializing System Hooks...")

    # 3. Register Hooks ON THE MAIN THREAD
    # Senior Note: Both hooks MUST stay on the same thread as the Message Pump.
    # If moved to a ThreadPool, the OS callbacks will never fire.
    
    paste_hook_h = start_paste_monitor()
    file_hook_h = start_file_upload_monitor()

    try:
        if not paste_hook_h or not file_hook_h:
            print("[-] Critical Error: Failed to initialize one or more monitors.")
            sys.exit(1)

        print("[+] Agent Active: Monitoring ChatGPT (Chrome) for PII and File Uploads.")
        print("[*] Press Ctrl+C to stop the agent safely.")

        # 4. Start the Message Pump
        # This is a blocking call that 'listens' to the OS.
        # It services BOTH the keyboard hook and the window event hook.
        agent_window.start() 
        
    except Exception as e:
        print(f"\n[!] Runtime Error: {e}")
        
    finally:
        # 5. Deterministic Cleanup
        # Crucial for security tools: don't leave hooks hanging in the OS memory.
        print("\n[*] Performing safety cleanup...")
        
        stop_paste_monitor()
        stop_file_upload_monitor()
        
        print("[+] Cleanup complete. Agent terminated.")
        
        # Use os._exit to ensure any lingering background threads (like loggers) 
        # are killed immediately.
        os._exit(0)