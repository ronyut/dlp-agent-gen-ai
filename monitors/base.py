import ctypes
import win32gui
import win32con

# Win32 Constants
WM_CLIPBOARDUPDATE = 0x031D
WINDOW_CLASS_NAME = "DLPAgentWindow"
WINDOW_TITLE = "DLPAgent"

class Win32MessageWindow:
    def __init__(self, message_map=None):
        self.message_map = message_map or {}
        self.hwnd = self._create_window()

    def _create_window(self):
        wc = win32gui.WNDCLASS()
        wc.lpfnWndProc = self._wnd_proc
        wc.lpszClassName = WINDOW_CLASS_NAME
        hinst = wc.hInstance = win32gui.GetModuleHandle(None)
        
        # Check if class is already registered to avoid errors on restart
        try:
            class_atom = win32gui.RegisterClass(wc)
        except win32gui.error:
            class_atom = WINDOW_CLASS_NAME
        
        return win32gui.CreateWindow(
            class_atom, WINDOW_TITLE, 0, 0, 0, 0, 0, 
            win32con.HWND_MESSAGE, 0, hinst, None
        )

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg in self.message_map:
            # We use a try/except here so a bug in a monitor 
            # doesn't crash the entire OS message loop.
            try:
                return self.message_map[msg](hwnd, msg, wparam, lparam)
            except Exception as e:
                print(f"Error in monitor handler: {e}")
                
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def start(self):
        """Starts the event-driven listener."""
        # Only register if we have a clipboard handler
        if WM_CLIPBOARDUPDATE in self.message_map:
            ctypes.windll.user32.AddClipboardFormatListener(self.hwnd)
        
        print("Agent Message Loop started...")
        win32gui.PumpMessages()