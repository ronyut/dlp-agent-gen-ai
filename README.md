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
python -m pip install pywin32
```

## Run

```bash
python main.py
```

Expected startup behavior:

- Registers keyboard and WinEvent hooks
- Starts the Win32 message loop
- Prints active monitoring status to console

## Configuration

Runtime settings are in config.json:

- monitors.target_process
- monitors.target_window_title
- monitors.google_drive_origin
- logging.log_file

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
- Origin detection relies on Zone.Identifier (Mark-of-the-Web); metadata can be missing after copy/move operations.
- Google Drive classification is hostname-oriented but still heuristic in malformed URL edge cases.
