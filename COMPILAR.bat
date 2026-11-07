@echo off
cd /d "%~dp0"
echo Compilando Video Audio Downloader (macOS Tahoe Glass Style)...
python -m pip install -U yt-dlp yt-dlp-ejs curl_cffi pyinstaller pywebview SpeechRecognition >nul 2>&1
set FF=
for /f "delims=" %%i in ('where ffmpeg') do set FF=%%~dpi& goto :found
:found
if "%FF%"=="" (echo No se encontro ffmpeg en el PATH & pause & exit /b 1)
if exist build_bin rmdir /s /q build_bin
mkdir build_bin
copy "%FF%ffmpeg.exe" build_bin >nul
copy "%FF%ffprobe.exe" build_bin >nul
python -m PyInstaller --noconfirm --onefile --noconsole --name "VideoAudioDownloader" --icon "descargar.ico" ^
  --add-data "web;web" --add-data "descargar.ico;." --add-data "build_bin;bin" ^
  --collect-all yt_dlp --collect-all yt_dlp_ejs --collect-all curl_cffi --collect-all certifi --collect-all webview --collect-all speech_recognition ^
  server.py
if exist "%LOCALAPPDATA%\Programs\VideoAudioDownloader" (
  copy /y "dist\VideoAudioDownloader.exe" "%LOCALAPPDATA%\Programs\VideoAudioDownloader\VideoAudioDownloader.exe" >nul 2>&1
)
python -c "import server; server.install_self(always=True)" >nul 2>&1
python build_mac.py
echo.
echo Listo:
echo   - dist\VideoAudioDownloader.exe (Windows)
echo   - dist\VideoAudioDownloader-Mac-M1.zip (macOS M1 / Intel)
if /i "%~1" neq "--nopause" pause
