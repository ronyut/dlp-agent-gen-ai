import os
import time
import ctypes
import threading
import win32gui
import win32con
import win32process
from ctypes import wintypes
from win32com.shell import shell, shellcon

# Internal Imports
from scanners.file_origin_scanner import is_google_drive_file
from utils.logger import agent_logger
from utils.config_loader import app_config

# Win32 Constants
EVENT_OBJECT_CREATE = 0x8000
WINEVENT_OUTOFCONTEXT = 0x0000

class FileUploadMonitor:
    def __init__(self):
        self._event_hook = None
        self._event_proc_keyword = None  # Prevents GC of the callback
        self.is_active = False

    def _is_target_process(self, hwnd):
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            handle = ctypes.windll.kernel32.OpenProcess(
                win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ,
                False,
                pid,
            )
            if not handle:
                return False

            exe_name = ctypes.create_unicode_buffer(260)
            ctypes.windll.psapi.GetModuleFileNameExW(handle, 0, exe_name, 260)
            ctypes.windll.kernel32.CloseHandle(handle)

            target_proc = app_config.get("monitors.target_process", "chrome.exe")
            return target_proc in exe_name.value.lower()
        except Exception:
            return False

    def _resolve_virtual_path(self, folder_nickname):
        """Maps Shell 'Nicknames' (Downloads, Desktop) to physical NTFS paths."""
        try:
            # Common mappings for English Windows
            if folder_nickname == "Downloads":
                base_path = shell.SHGetFolderPath(0, shellcon.CSIDL_PROFILE, None, 0)
                return os.path.join(base_path, "Downloads")
            
            elif folder_nickname == "Desktop":
                return shell.SHGetFolderPath(0, shellcon.CSIDL_DESKTOP, None, 0)
            
            elif folder_nickname == "Documents":
                return shell.SHGetFolderPath(0, shellcon.CSIDL_PERSONAL, None, 0)

            # If it's already a full path, return as is
            if ":" in folder_nickname:
                return folder_nickname

        except Exception as e:
            print(f"[!] Shell resolution error: {e}")
        
        return folder_nickname

    def _get_full_path_from_dialog(self, hwnd):
        """Navigates the #32770 UI tree to reconstruct the file path."""
        try:
            # 1. Extract Filename from the Edit Control
            h_combo_ex = win32gui.FindWindowEx(hwnd, 0, "ComboBoxEx32", None)
            h_combo = win32gui.FindWindowEx(h_combo_ex, 0, "ComboBox", None)
            h_edit = win32gui.FindWindowEx(h_combo, 0, "Edit", None)
            
            if not h_edit: return None
            
            buf_len = win32gui.SendMessage(h_edit, win32con.WM_GETTEXTLENGTH, 0, 0) + 1
            str_buf = ctypes.create_unicode_buffer(buf_len)
            win32gui.SendMessage(h_edit, win32con.WM_GETTEXT, buf_len, str_buf)
            filename = str_buf.value.strip('"') # Remove quotes if multiple files selected

            # 2. Extract Folder Path from the Breadcrumb Toolbar
            # Hierarchical search to ensure stability
            h_worker = win32gui.FindWindowEx(hwnd, 0, "WorkerW", None)
            h_rebar = win32gui.FindWindowEx(h_worker, 0, "ReBarWindow32", None)
            h_address = win32gui.FindWindowEx(h_rebar, 0, "Address Band Root", None)
            h_progress = win32gui.FindWindowEx(h_address, 0, "msctls_progress32", None)
            h_breadcrumb = win32gui.FindWindowEx(h_progress, 0, "Breadcrumb Parent", None)
            h_toolbar = win32gui.FindWindowEx(h_breadcrumb, 0, "ToolbarWindow32", None)

            if not h_toolbar: return None

            t_buf_len = win32gui.SendMessage(h_toolbar, win32con.WM_GETTEXTLENGTH, 0, 0) + 1
            t_buf = ctypes.create_unicode_buffer(t_buf_len)
            win32gui.SendMessage(h_toolbar, win32con.WM_GETTEXT, t_buf_len, t_buf)
            
            # Handles 'Address: C:\Path' or localized variations
            folder_raw = t_buf.value
            folder_path = folder_raw.split(":", 1)[-1].strip() if ":" in folder_raw else folder_raw

            if folder_path and filename:
                base = self._resolve_virtual_path(folder_path)
                return os.path.normpath(os.path.join(base, filename))
                
        except Exception:
            return None
        return None

    def _watch_dialog_lifecycle(self, hwnd):
        """Asynchronous watcher for a specific Dialog HWND."""
        last_known_path = ""
        
        # High-frequency polling (10Hz) to catch 'Enter' key commits
        while win32gui.IsWindow(hwnd) and self.is_active:
            current = self._get_full_path_from_dialog(hwnd)
            if current and os.path.isfile(current):
                last_known_path = current
            time.sleep(0.1)

        # Logic: Window is destroyed. Did it have a path?
        if self.is_active and last_known_path and os.path.exists(last_known_path):
            if is_google_drive_file(last_known_path):
                agent_logger.log(f"Alert: Drive-sourced file upload to GenAI detected.")
            else:
                print(f"[*] Normal upload detected: {os.path.basename(last_known_path)}")

    def _event_handler(self, hWinEventHook, event, hwnd, idObject, idChild, dwEventThread, dwmsEventTime):
        """The core Windows Callback."""
        if event == EVENT_OBJECT_CREATE:
            try:
                if win32gui.GetClassName(hwnd) == "#32770":
                    if self._is_target_process(hwnd):
                        # Spawn watcher so the Main Hook thread stays responsive
                        threading.Thread(
                            target=self._watch_dialog_lifecycle, 
                            args=(hwnd,), 
                            daemon=True
                        ).start()
            except Exception:
                pass

    def start(self):
        """Installs the system-wide WinEventHook."""
        if self._event_hook: return
        
        # Define C-style function pointer
        WinEventProcType = ctypes.WINFUNCTYPE(
            None, wintypes.HANDLE, wintypes.DWORD, wintypes.HWND,
            wintypes.LONG, wintypes.LONG, wintypes.DWORD, wintypes.DWORD
        )
        
        self._event_proc_keyword = WinEventProcType(self._event_handler)
        
        self._event_hook = ctypes.windll.user32.SetWinEventHook(
            EVENT_OBJECT_CREATE, EVENT_OBJECT_CREATE,
            0, self._event_proc_keyword, 0, 0,
            WINEVENT_OUTOFCONTEXT
        )
        
        self.is_active = True
        print("[+] File Upload Monitor: Registered.")
        return self._event_hook

    def stop(self):
        """Unregisters the hook and stops background threads."""
        self.is_active = False
        if self._event_hook:
            ctypes.windll.user32.UnhookWinEvent(self._event_hook)
            self._event_hook = None
            print("[+] File Upload Monitor: Unhooked.")

# --- Singleton Export for main.py ---
_monitor_instance = FileUploadMonitor()

def start_file_upload_monitor():
    return _monitor_instance.start()

def stop_file_upload_monitor():
    _monitor_instance.stop()