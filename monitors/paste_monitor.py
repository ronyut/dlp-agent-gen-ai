import ctypes
from ctypes import wintypes
import win32clipboard
import win32gui
import win32con
import win32process
import time
import re

from scanners.pii_scanner import email_address_scanner
from utils.logger import agent_logger
from utils.config_loader import app_config

# Win32 Constants
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
VK_V = 0x56

# Global variables to prevent Garbage Collection
_hook_handle = None
_hook_pointer = None 

class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p) 
    ]

# Setup argument types for CallNextHookEx to prevent 64-bit Overflow
LRESULT = ctypes.c_longlong
ctypes.windll.user32.CallNextHookEx.argtypes = [
    wintypes.HANDLE, 
    ctypes.c_int,    
    wintypes.WPARAM, 
    wintypes.LPARAM  
]
ctypes.windll.user32.CallNextHookEx.restype = LRESULT

def is_chatgpt_in_chrome():
    """Robustly checks if the foreground window is a Chrome tab on ChatGPT."""
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return False

    title = win32gui.GetWindowText(hwnd).lower()
    target_title = app_config.get("monitors.target_window_title", "chatgpt").lower()
    
    if target_title not in title:
        return False

    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        handle = ctypes.windll.kernel32.OpenProcess(
            win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ, 
            False, pid
        )
        
        exe_name = ctypes.create_unicode_buffer(260)
        ctypes.windll.psapi.GetModuleFileNameExW(handle, 0, exe_name, 260)
        ctypes.windll.kernel32.CloseHandle(handle)
        
        target_proc = app_config.get("monitors.target_process", "chrome.exe")
        return target_proc in exe_name.value.lower()
    except Exception:
        return True # Fallback to title match if process query fails

def get_clipboard_text(retries=3, delay=0.01):
    for i in range(retries):
        try:
            win32clipboard.OpenClipboard()
            if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
                win32clipboard.CloseClipboard()
                return data
            win32clipboard.CloseClipboard()
            return None
        except Exception:
            time.sleep(delay)
    return None

def paste_hook_callback(nCode, wParam, lParam):
    if nCode == 0 and wParam == WM_KEYDOWN:
        # Check for Ctrl (0x11)
        if ctypes.windll.user32.GetKeyState(0x11) & 0x8000:
            kb_struct = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            
            if kb_struct.vkCode == VK_V:
                print("[+] Detected Ctrl+V - Checking context...")
                # 1. Context Validation
                if is_chatgpt_in_chrome():
                    print("[+] Paste detected in chrome tab of ChatGPT - Scanning clipboard...")
                    # 2. Grab Clipboard
                    text = get_clipboard_text()
                    if text:
                        # 3. Scan for PII
                        found_pii = email_address_scanner(text)
                        if found_pii:
                            print(f"[!] ALERT: PII Detected in paste to ChatGPT! Found: {found_pii}")
                            agent_logger.log(f"Alert: PII (Email) detected from GenAI upload.")
                            # Optional: You could show a Win32 MessageBox here
                
    return ctypes.windll.user32.CallNextHookEx(None, nCode, wParam, lParam)

def start_paste_monitor():
    global _hook_handle, _hook_pointer
    
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    
    # Use LRESULT (c_longlong) to match 64-bit Windows callback signatures
    CMPFUNC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
    _hook_pointer = CMPFUNC(paste_hook_callback)
    
    # Dynamic DLL Handle Resolution
    h_module = wintypes.HMODULE()
    kernel32.GetModuleHandleExW(
        0x00000004, # GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS
        ctypes.cast(ctypes.pythonapi.Py_Initialize, ctypes.c_void_p),
        ctypes.byref(h_module)
    )

    _hook_handle = user32.SetWindowsHookExW(WH_KEYBOARD_LL, _hook_pointer, h_module, 0)
    
    if not _hook_handle:
        print(f"HOOK FAILED. WinError: {kernel32.GetLastError()}")
    else:
        pass
        #print(f"[+] SUCCESS: Paste Monitor active on module: {hex(h_module.value)}")
        
    return _hook_handle

def stop_paste_monitor():
    global _hook_handle
    if _hook_handle:
        print("[+] Unhooking keyboard...")
        ctypes.windll.user32.UnhookWindowsHookEx(_hook_handle)
        _hook_handle = None