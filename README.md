# StoryVoice TTS Agent

A browser-based Python app that turns narration text into a downloadable MP3.

## Quick start (Windows)

1. Install Python 3.10 or newer from https://www.python.org/downloads/ if needed. Enable **Add Python to PATH** during installation.
2. Extract this ZIP and open the extracted folder in VS Code.
3. Open **Terminal → New Terminal**, then run:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

4. If a browser tab does not open automatically, visit http://localhost:8501.
5. Paste your script, choose a voice and speed, click **Generate MP3**, preview it, and download it.

### If PowerShell blocks activation

Skip virtual-environment activation and run:

```powershell
py -m pip install -r requirements.txt
py -m streamlit run app.py
```

## Notes

- Internet access is required.
- This starter uses `edge-tts`, which accesses online Edge TTS voices; it is not an official Microsoft API and availability may change.
- Avoid entering private or sensitive text.
- Check the current service and voice terms before commercial use or monetized videos.
- For very long scripts, split the narration into shorter sections if generation fails.




#run  ....................


py -m venv .venv
.\.venv\Scripts\Activate.ps1


python -m pip install --upgrade pip
pip install -r requirements.txt


streamlit run app.py

http://localhost:8501

If PowerShell blocks the activation script , Skip the venv and run globally instead:

powershell
py -m pip install -r requirements.txt
py -m streamlit run app.py