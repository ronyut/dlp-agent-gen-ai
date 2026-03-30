# DLP Agent for GenAI Monitoring

Windows endpoint monitoring prototype that detects potential data leakage to GenAI workflows through:

- Paste actions into ChatGPT in Chrome (email-based PII check)
- File selection in Windows Open dialogs (Google Drive-origin heuristic)

## Requirements

- Windows OS
- Python 3.9+
- pywin32 package

## Installation

```bash
python -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Run

```bash
python main.py
```

## Configuration

Runtime settings are in `config.json`.

## Technical Notes

### OS APIs Used

- `SetWindowsHookExW(WH_KEYBOARD_LL)`: captures global keyboard events and allows Ctrl+V detection for paste monitoring.
- `SetWinEventHook(EVENT_OBJECT_CREATE)`: watches creation of Windows UI objects and detects new Open dialogs.
- `PumpMessages` with a hidden message-only window (`HWND_MESSAGE`): keeps the process in a native Win32 event loop.
- `GetForegroundWindow`, `GetWindowText`, `GetWindowThreadProcessId`, `OpenProcess`, `GetModuleFileNameExW`: used to verify the active context is ChatGPT in Chrome before evaluating events.

### File Origin Detection

- For selected files, the agent reads NTFS Alternate Data Stream metadata from `:Zone.Identifier`.
- It parses `ZoneTransfer/HostUrl` and classifies source by matching the parsed hostname against configured Google Drive origin tokens.

## Limitations

### PII Detection

- Only Ctrl+V is monitored; drag-and-drop and clipboard manager flows are not covered.
- Email detection uses a simple regex and misses obfuscated or many internationalized formats.
- Matching relies on a configured ChatGPT window-title substring, which can create both false negatives and false positives.
- Very large pasted payloads may need optimized scanning and throttling.

### File Upload Detection

- Multi-file selections are not fully handled.
- Drag-and-drop uploads are not detected.
- Selecting a file in the dialog can be flagged even if upload is never completed.
- Origin detection relies on Zone.Identifier (Mark-of-the-Web); metadata can be missing after copy/move/save-as operations or if metadata was stripped.
- Google Drive classification is hostname-oriented but still heuristic in malformed URL edge cases.
- Upload dialog detection is based on window-title matching.
- Upload dialog parsing relies on standard Windows UI hierarchies, making it susceptible to failure across different locales or OS versions. Additionally, the parser only supports common folder nicknames (e.g., Desktop, Downloads); navigating to other localized or virtual folders may fail to resolve the absolute path required for origin checking.

