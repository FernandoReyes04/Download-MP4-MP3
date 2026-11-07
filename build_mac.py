"""Genera en dist/ el paquete nativo para macOS (M1 / Intel) desde Windows:
  - dist/VideoAudioDownloader-Mac-M1.zip (contiene VideoAudioDownloader.app con permisos Unix 0755)
"""
import io, os, zipfile
from pathlib import Path
from PIL import Image

BASE = Path(__file__).parent
DIST = BASE / "dist"
DIST.mkdir(exist_ok=True)

INFO_PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Video Audio Downloader</string>
  <key>CFBundleDisplayName</key><string>Video Audio Downloader</string>
  <key>CFBundleIdentifier</key><string>local.videoaudiodownloader</string>
  <key>CFBundleVersion</key><string>2.0</string>
  <key>CFBundleShortVersionString</key><string>2.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>VideoAudioDownloader</string>
  <key>CFBundleIconFile</key><string>app.icns</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
"""

MAC_LAUNCHER = """#!/bin/bash
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
BUNDLE="$(cd "$(dirname "$0")/../.." && pwd)"
RES="$BUNDLE/Contents/Resources"
APPDATA="$HOME/Library/Application Support/VideoAudioDownloader"
BINDIR="$APPDATA/bin"
mkdir -p "$BINDIR"

# 1. Auto-instalación en Applications y acceso en Escritorio si se abrió desde Descargas
TARGET="/Applications/VideoAudioDownloader.app"
[ ! -w "/Applications" ] && TARGET="$HOME/Applications/VideoAudioDownloader.app"
if [ "$BUNDLE" != "$TARGET" ]; then
  mkdir -p "$(dirname "$TARGET")"
  rm -rf "$TARGET"
  cp -R "$BUNDLE" "$TARGET"
  xattr -cr "$TARGET" 2>/dev/null || true
  ln -sf "$TARGET" "$HOME/Desktop/Video Audio Downloader.app" 2>/dev/null || true
  open "$TARGET"
  exit 0
fi

# 2. Motor yt-dlp oficial para macOS
if [ ! -x "$APPDATA/yt-dlp_macos" ]; then
  osascript -e 'display notification "Configurando motor de descargas por primera vez..." with title "Video Audio Downloader"' 2>/dev/null || true
  curl -fsSL "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_macos" -o "$APPDATA/yt-dlp_macos"
  chmod +x "$APPDATA/yt-dlp_macos"
fi

# 3. FFmpeg estático para macOS (si no tiene ffmpeg instalado)
if ! command -v ffmpeg >/dev/null 2>&1 && [ ! -x "$BINDIR/ffmpeg" ]; then
  osascript -e 'display notification "Descargando FFmpeg para macOS (solo la primera vez)..." with title "Video Audio Downloader"' 2>/dev/null || true
  curl -fsSL "https://evermeet.cx/ffmpeg/getrelease/ffmpeg/zip" -o "$BINDIR/ffmpeg.zip" && \\
    unzip -qo "$BINDIR/ffmpeg.zip" -d "$BINDIR" && rm -f "$BINDIR/ffmpeg.zip" && chmod +x "$BINDIR/ffmpeg"
  curl -fsSL "https://evermeet.cx/ffmpeg/getrelease/ffprobe/zip" -o "$BINDIR/ffprobe.zip" && \\
    unzip -qo "$BINDIR/ffprobe.zip" -d "$BINDIR" && rm -f "$BINDIR/ffprobe.zip" && chmod +x "$BINDIR/ffprobe"
fi

# 4. Python 3 (usa el del sistema/Homebrew o descarga Python portable para Apple Silicon / Intel)
PY=""
for p in /opt/homebrew/bin/python3 /usr/local/bin/python3 "$APPDATA/python/bin/python3"; do
  if [ -x "$p" ]; then PY="$p"; break; fi
done
if [ -z "$PY" ] && /usr/bin/python3 -c "import sys" >/dev/null 2>&1; then
  PY="/usr/bin/python3"
fi
if [ -z "$PY" ]; then
  osascript -e 'display notification "Preparando entorno Python portable (solo la primera vez)..." with title "Video Audio Downloader"' 2>/dev/null || true
  ARCH="$(uname -m)"
  if [ "$ARCH" = "arm64" ]; then
    PY_URL="https://github.com/indygreg/python-build-standalone/releases/download/20241016/cpython-3.12.7+20241016-aarch64-apple-darwin-install_only.tar.gz"
  else
    PY_URL="https://github.com/indygreg/python-build-standalone/releases/download/20241016/cpython-3.12.7+20241016-x86_64-apple-darwin-install_only.tar.gz"
  fi
  curl -fsSL "$PY_URL" -o "$APPDATA/py.tar.gz" && tar -xzf "$APPDATA/py.tar.gz" -C "$APPDATA" && rm -f "$APPDATA/py.tar.gz"
  PY="$APPDATA/python/bin/python3"
fi

export PATH="$BINDIR:$PATH"
cd "$RES"
exec "$PY" "$RES/server.py"
"""


def add_file(zf: zipfile.ZipFile, arcname: str, data: bytes, executable: bool = False):
    zi = zipfile.ZipInfo(arcname)
    zi.compress_type = zipfile.ZIP_DEFLATED
    mode = 0o100755 if executable else 0o100644
    zi.external_attr = (mode << 16)
    zi.create_system = 3  # Unix
    zf.writestr(zi, data)


def build():
    icns_buf = io.BytesIO()
    im = Image.open(BASE / "descargar.ico").convert("RGBA").resize((512, 512))
    im.save(icns_buf, format="ICNS")

    out_zip = DIST / "VideoAudioDownloader-Mac-M1.zip"
    app = "VideoAudioDownloader.app/Contents"

    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        add_file(zf, f"{app}/Info.plist", INFO_PLIST.replace("\r\n", "\n").encode("utf-8"))
        add_file(zf, f"{app}/MacOS/VideoAudioDownloader",
                 MAC_LAUNCHER.replace("\r\n", "\n").encode("utf-8"), executable=True)
        add_file(zf, f"{app}/Resources/app.icns", icns_buf.getvalue())

        for rel in ("server.py", "app.py", "descargar.ico",
                    "web/index.html", "web/app.js", "web/descargar.ico"):
            p = BASE / rel
            raw = p.read_bytes()
            if p.suffix in (".py", ".html", ".js"):
                raw = raw.replace(b"\r\n", b"\n")
            add_file(zf, f"{app}/Resources/{rel}", raw)

    print(f"Listo: {out_zip} ({out_zip.stat().st_size:,} bytes)")


if __name__ == "__main__":
    build()
