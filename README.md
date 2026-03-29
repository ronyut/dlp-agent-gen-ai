# DLP Agent for GenAI Monitoring

## How to run

```
pip install ...
python main.py
```

## Limitations

### PII Detection
- Currently only ctrl+v is monitored. We should also monitor for text drag-and-drop, clipboard manager interactions.
- Not all email addresses are detected (currently only latin letters, even though email address can contain non-latin characters)
- obfuscation techniques (e.g. example [dot] gmail [dot] com) are not detected
- harcoded title "ChatGPT" - if accessed via iframe or if the title changes, it will not be detected. also this can lead to false positives if some other website has the same title.
- if a very long text is pasted  - maybe should optimize the detection logic.

### File Upload Detection
- Multiple files uploaded at once are not detected
- drag-and-drop file uploads are not detected
- If a gdrive file is selected but not actually uploaded, it is still detected as an upload (false positive)
- hardcoded google drive download ADS origin path - if changes, it will not be detected. 
- we naively check if "googleusercontent.com" is inside ADS origin - this can lead to false positives.
- after a file is download from google drive, it might lose the ADS origin info, if for example it is moved to another drive.
