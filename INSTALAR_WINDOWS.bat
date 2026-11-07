@echo off
cd /d "%~dp0"
python server.py --install
start "" pythonw "%LOCALAPPDATA%\Programs\VideoAudioDownloader\server.py"
