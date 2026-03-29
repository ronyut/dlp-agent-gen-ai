import ctypes
import win32con
import win32gui

_main_thread_id = None


def set_main_thread_id(thread_id):
    """Registers the thread that owns the Win32 message pump."""
    global _main_thread_id
    _main_thread_id = thread_id

def console_handler(ctrl_type):
    """
    Handles Ctrl+C and Window Close events natively in Windows.
    This ensures we unhook from the OS before the process dies.
    """
    if ctrl_type in (0, 2):  # 0 = CTRL_C_EVENT, 2 = CTRL_CLOSE_EVENT
        print("\n[!] Shutdown signal received. Breaking Message Pump...")

        # Control handlers run on a separate system thread, so PostQuitMessage
        # would target the wrong message queue. Post WM_QUIT to the main thread.
        if _main_thread_id:
            ctypes.windll.user32.PostThreadMessageW(_main_thread_id, win32con.WM_QUIT, 0, 0)
        else:
            # Fallback for unexpected startup ordering.
            win32gui.PostQuitMessage(0)
        return True
    return False