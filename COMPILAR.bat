@echo off
cd /d "%~dp0"
echo Compilando Video Audio Downloader (macOS Tahoe Glass Style)...
python -m pip install -U yt-dlp pyinstaller pywebview >nul 2>&1
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
  --collect-all yt_dlp --collect-all yt_dlp_ejs --collect-all webview ^
  server.py
python build_mac.py
echo.
echo Listo:
echo   - dist\VideoAudioDownloader.exe (Windows)
echo   - dist\VideoAudioDownloader-Mac-M1.zip (macOS M1 / Intel)
pause
