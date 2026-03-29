import ctypes
from ctypes import wintypes
import queue
import threading
import win32clipboard
import win32gui
import win32con
import win32process
import time

# Internal Imports
from scanners.pii_scanner import email_address_scanner
from utils.logger import agent_logger
from utils.config_loader import app_config

# Win32 Constants
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
VK_V = 0x56
VK_CONTROL = 0x11
LRESULT = ctypes.c_longlong

class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p) 
    ]

class PasteMonitor:
    def __init__(self):
        self._hook_handle = None
        self._hook_pointer = None # Anchors the callback in memory
        self._event_queue = queue.Queue(maxsize=256)
        self._worker = None
        self._active = False
        
        # Explicitly define CallNextHookEx types for 64-bit compatibility
        ctypes.windll.user32.CallNextHookEx.argtypes = [
            wintypes.HANDLE, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM  
        ]
        ctypes.windll.user32.CallNextHookEx.restype = LRESULT

    def _is_chatgpt_in_chrome(self):
        """Checks if the foreground window is Chrome running ChatGPT."""
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return False

        title = win32gui.GetWindowText(hwnd).lower()
        target_title = app_config.get("monitors.target_window_title", "chatgpt").lower()
        
        if target_title not in title:
            return False

        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            # Query limited information to check process name
            handle = ctypes.windll.kernel32.OpenProcess(
                win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ, 
                False, pid
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

    def _get_clipboard_text(self, retries=3, delay=0.01):
        """Thread-safe clipboard access."""
        for _ in range(retries):
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

    def _hook_callback(self, nCode, wParam, lParam):
        """Low-level callback handled by the OS."""
        if nCode == 0 and wParam == WM_KEYDOWN:
            # Check if Ctrl is held down (0x8000 is the high-order bit for 'pressed')
            if ctypes.windll.user32.GetKeyState(VK_CONTROL) & 0x8000:
                kb_struct = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                
                if kb_struct.vkCode == VK_V:
                    try:
                        self._event_queue.put_nowait(time.time())
                    except queue.Full:
                        pass
                
        # Must pass the message to the next hook in the chain
        return ctypes.windll.user32.CallNextHookEx(self._hook_handle, nCode, wParam, lParam)

    def _process_paste_events(self):
        while self._active:
            try:
                event = self._event_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if event is None:
                break

            if self._is_chatgpt_in_chrome():
                text = self._get_clipboard_text()
                if text:
                    found_pii = email_address_scanner(text)
                    if found_pii:
                        agent_logger.log("Alert: PII (Email) detected from GenAI upload.")
                        print(f"[!] PII Leak detected: {found_pii}")

            self._event_queue.task_done()

    def start(self):
        """Registers the Keyboard Hook."""
        if self._hook_handle:
            return

        self._active = True
        self._worker = threading.Thread(target=self._process_paste_events, daemon=True)
        self._worker.start()

        # Setup the callback function pointer
        CMPFUNC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        self._hook_pointer = CMPFUNC(self._hook_callback)
        
        # Resolve the module handle for the current process
        h_module = wintypes.HMODULE()
        ctypes.windll.kernel32.GetModuleHandleExW(
            0x00000004, # GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS
            ctypes.cast(ctypes.pythonapi.Py_Initialize, ctypes.c_void_p),
            ctypes.byref(h_module)
        )

        self._hook_handle = ctypes.windll.user32.SetWindowsHookExW(
            WH_KEYBOARD_LL, 
            self._hook_pointer, 
            h_module, 
            0
        )
        
        if not self._hook_handle:
            print(f"[-] Hook Registration Failed. Error: {ctypes.windll.kernel32.GetLastError()}")
        else:
            print("[+] Paste Monitor Active.")
        
        return self._hook_handle

    def stop(self):
        """Unregisters the hook."""
        self._active = False
        try:
            self._event_queue.put_nowait(None)
        except queue.Full:
            pass

        if self._hook_handle:
            ctypes.windll.user32.UnhookWindowsHookEx(self._hook_handle)
            self._hook_handle = None
            print("[+] Paste Monitor Stopped.")

# Exported instance for main.py integration
_instance = PasteMonitor()

def start_paste_monitor():
    return _instance.start()

def stop_paste_monitor():
    _instance.stop()