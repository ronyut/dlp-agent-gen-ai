import win32gui

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