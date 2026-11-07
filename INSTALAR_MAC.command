#!/bin/bash
# Instalador para macOS (Apple Silicon M1/M2/M3 o Intel).
# Crea "Video Audio Downloader.app" en ~/Applications y el acceso en el Escritorio.
set -e
cd "$(dirname "$0")"
echo "=== Instalando Video Audio Downloader para macOS ==="

# 1. Homebrew + ffmpeg + python3 (si faltan)
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v python3 >/dev/null 2>&1; then
  if ! command -v brew >/dev/null 2>&1; then
    echo "Instalando Homebrew (pedira tu contrasena de Mac)..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
  fi
  command -v python3 >/dev/null 2>&1 || brew install python
  command -v ffmpeg  >/dev/null 2>&1 || brew install ffmpeg
fi

# 2. Carpeta de la app + entorno virtual con yt-dlp
DEST="$HOME/Library/Application Support/VideoAudioDownloader/app"
mkdir -p "$DEST"
cp -R server.py web descargar.ico "$DEST/"
if [ ! -d "$DEST/venv" ]; then
  python3 -m venv "$DEST/venv"
fi
"$DEST/venv/bin/pip" install -q -U pip yt-dlp

# 3. Paquete .app nativo de macOS en ~/Applications
APP="$HOME/Applications/Video Audio Downloader.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

cat > "$APP/Contents/Info.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Video Audio Downloader</string>
  <key>CFBundleDisplayName</key><string>Video Audio Downloader</string>
  <key>CFBundleIdentifier</key><string>local.videoaudiodownloader</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>launch</string>
  <key>CFBundleIconFile</key><string>app.icns</string>
  <key>LSUIElement</key><true/>
</dict></plist>
EOF

# Convertir descargar.ico -> app.icns usando herramientas nativas de macOS
sips -s format icns descargar.ico --out "$APP/Contents/Resources/app.icns" >/dev/null 2>&1 || true

cat > "$APP/Contents/MacOS/launch" << 'EOF'
#!/bin/bash
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
DIR="$HOME/Library/Application Support/VideoAudioDownloader/app"
cd "$DIR"
exec "$DIR/venv/bin/python" "$DIR/server.py"
EOF
chmod +x "$APP/Contents/MacOS/launch"
xattr -cr "$APP" 2>/dev/null || true

# Acceso directo en el Escritorio
ln -sf "$APP" "$HOME/Desktop/Video Audio Downloader.app"

echo "Listo. Abriendo Video Audio Downloader..."
open "$APP"
