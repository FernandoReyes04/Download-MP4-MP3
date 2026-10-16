@echo off
cd /d "%~dp0"
python -m pip install -U yt-dlp >nul 2>&1
python server.py
pause
