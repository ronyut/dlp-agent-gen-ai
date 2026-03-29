import win32gui
import win32con
import ctypes
import threading
import time
import os
from win32com.shell import shell, shellcon
from ctypes import wintypes
from scanners.file_origin_scanner import is_google_drive_file
from utils.logger import agent_logger

# Win32 Constants
EVENT_OBJECT_CREATE = 0x8000
WINEVENT_OUTOFCONTEXT = 0x0000

# Global variables to prevent the "Garbage Collection" crash
_event_hook = None
_event_proc_keyword = None 

def resolve_virtual_path(folder_nickname):
    """
    Using the correct win32com.shell syntax to resolve Known Folders.
    """
    try:
        # The function is actually shell.SHGetFolderPath (no extra 'shell' prefix)
        # but the import must be 'from win32com.shell import shell'
        
        if folder_nickname == "Downloads":
            # CSIDL_PROFILE + \Downloads is the safest bet for the Downloads folder
            base_path = shell.SHGetFolderPath(0, shellcon.CSIDL_PROFILE, None, 0)
            return os.path.join(base_path, "Downloads")
            
        elif folder_nickname == "Desktop":
            return shell.SHGetFolderPath(0, shellcon.CSIDL_DESKTOP, None, 0)
            
        elif folder_nickname == "Documents":
            return shell.SHGetFolderPath(0, shellcon.CSIDL_PERSONAL, None, 0)

        # If it's already a full path (C:\...), return it
        if ":" in folder_nickname:
            return folder_nickname

    except Exception as e:
        print(f"Shell resolution failed: {e}")
        
    return folder_nickname

def get_full_path_from_dialog(hwnd):
    """
    Scrapes both the Folder (from the Address Bar) and 
    the Filename (from the Edit box) to reconstruct the full path.
    """
    try:
        # 1. Get the Filename (what you already have)
        h_combo_ex = win32gui.FindWindowEx(hwnd, 0, "ComboBoxEx32", None)
        h_combo = win32gui.FindWindowEx(h_combo_ex, 0, "ComboBox", None)
        h_edit = win32gui.FindWindowEx(h_combo, 0, "Edit", None)
        
        filename = ""
        if h_edit:
            buffer_len = win32gui.SendMessage(h_edit, win32con.WM_GETTEXTLENGTH, 0, 0) + 1
            buffer = ctypes.create_unicode_buffer(buffer_len)
            win32gui.SendMessage(h_edit, win32con.WM_GETTEXT, buffer_len, buffer)
            filename = buffer.value

        # 2. Get the Folder Path (The 'Senior' part)
        # We look for the 'WorkerW' -> 'ReBarWindow32' -> 'Address Band Root'
        # This is where Windows stores the current directory of the dialog
        h_worker = win32gui.FindWindowEx(hwnd, 0, "WorkerW", None)
        h_rebar = win32gui.FindWindowEx(h_worker, 0, "ReBarWindow32", None)
        h_address_band = win32gui.FindWindowEx(h_rebar, 0, "Address Band Root", None)
        h_progress = win32gui.FindWindowEx(h_address_band, 0, "msctls_progress32", None)
        h_breadcrumb = win32gui.FindWindowEx(h_progress, 0, "Breadcrumb Parent", None)
        h_toolbar = win32gui.FindWindowEx(h_breadcrumb, 0, "ToolbarWindow32", None)

        # Reconstruct the folder from the toolbar text
        # Note: This returns "Address: C:\Users\Rony\Downloads"
        folder_buffer_len = win32gui.SendMessage(h_toolbar, win32con.WM_GETTEXTLENGTH, 0, 0) + 1
        folder_buffer = ctypes.create_unicode_buffer(folder_buffer_len)
        win32gui.SendMessage(h_toolbar, win32con.WM_GETTEXT, folder_buffer_len, folder_buffer)
        
        folder_path = folder_buffer.value.replace("Address: ", "").strip()

        if folder_path and filename:
            base_folder = resolve_virtual_path(folder_path)
            full_path = os.path.join(base_folder, filename)
            return os.path.normpath(full_path)
            
    except Exception as e:
        print(f"Path reconstruction failed: {e}")
    return None

def watch_dialog_lifecycle(hwnd):
    """
    Shadows the 'Open' dialog to capture the final user intent.
    Alerts only if the dialog is committed (Open/Enter) with a Drive file.
    """
    last_valid_path = ""
    print(f"[*] Started monitoring Dialog HWND: {hwnd}")
    
    # 1. Shadow the window while it is open
    while win32gui.IsWindow(hwnd):
        current_path = get_full_path_from_dialog(hwnd)
        
        # If the path is a real file, keep track of it as the 'potential upload'
        if current_path and os.path.isfile(current_path):
            if current_path != last_valid_path:
                last_valid_path = current_path
                print(f"[DEBUG] User focused on: {last_valid_path}")
        
        # We poll faster (0.1s) to ensure we don't miss the state 
        # right before 'Enter' destroys the window.
        time.sleep(0.1) 
    
    # 2. THE MOMENT OF TRUTH: The window just closed.
    # If the user hit 'Cancel' or 'Esc', the internal buffers are usually 
    # cleared before destruction, or last_valid_path remains just a 'shadow'.
    # We verify the path still exists on disk as a final check.
    if last_valid_path and os.path.exists(last_valid_path):
        # Perform the forensic ADS check only ONCE upon commitment
        if is_google_drive_file(last_valid_path):
            agent_logger.log(f"Alert: Drive-sourced file upload to GenAI detected.")
        else:
            print(f"[DEBUG] Upload completed for non-Drive file: {last_valid_path}")
    else:
        print(f"[*] Dialog {hwnd} dismissed or cancelled. No alert triggered.")

    print(f"[*] Watcher for {hwnd} terminated.")

def win_event_callback(hWinEventHook, event, hwnd, idObject, idChild, dwEventThread, dwmsEventTime):
    """The Listener: Triggers when the window is first created."""
    if event == EVENT_OBJECT_CREATE:
        class_name = win32gui.GetClassName(hwnd)
        
        if class_name == "#32770":
            title = win32gui.GetWindowText(hwnd).lower()
            if "open" in title:
                # START THE WATCHER in a new thread so we don't freeze the Main Hook
                t = threading.Thread(target=watch_dialog_lifecycle, args=(hwnd,), daemon=True)
                t.start()

def start_file_upload_monitor():
    global _event_hook, _event_proc_keyword
    
    user32 = ctypes.windll.user32
    
    # 1. Define the Prototype (Tells Python how to talk to the Windows C-callback)
    WinEventProcType = ctypes.WINFUNCTYPE(
        None, 
        wintypes.HANDLE, wintypes.DWORD, wintypes.HWND,
        wintypes.LONG, wintypes.LONG, wintypes.DWORD, wintypes.DWORD
    )
    
    print("[*] Starting File Upload Monitor...")

    # 2. Assign the callback function to the pointer
    # IMPORTANT: Store this in a global variable so Python doesn't delete it!
    _event_proc_keyword = WinEventProcType(win_event_callback)
    
    # 3. The Line You Asked For: Registering with the Windows Kernel
    _event_hook = user32.SetWinEventHook(
        EVENT_OBJECT_CREATE,
        EVENT_OBJECT_CREATE, # Only catch new windows
        0,                        # dwProcessId (0 = all processes)
        _event_proc_keyword,       # The pointer to your win_event_callback
        0,                         
        0,                     
        WINEVENT_OUTOFCONTEXT
    )
    
    if not _event_hook:
        print("[-] Critical Error: Could not install WinEventHook.")
    else:
        print("[+] File Upload Monitor registered with Windows.")
        
    return _event_hook

def stop_file_upload_monitor():
    """
    Safely unregisters the WinEventHook from the Windows OS.
    """
    global _event_hook
    
    if _event_hook:
        # UnhookWinEvent returns True if successful
        result = ctypes.windll.user32.UnhookWinEvent(_event_hook)
        
        if result:
            print("[+] File Upload Monitor unhooked successfully.")
            _event_hook = None # Clear the handle
        else:
            error_code = ctypes.windll.kernel32.GetLastError()
            print(f"[-] Failed to unhook File Monitor. WinError: {error_code}")
    else:
        print("[-] No active File Monitor hook to stop.")