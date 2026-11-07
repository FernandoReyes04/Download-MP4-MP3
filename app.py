"""Video & Audio Downloader — Punto de entrada nativo.
Lanza la aplicación de escritorio con renderizado nítido High-DPI (macOS Tahoe Glass).
"""
import sys
import server

if __name__ == "__main__":
    try:
        server._main()
    except SystemExit:
        raise
    except BaseException:
        import traceback
        try:
            server.SETTINGS.parent.mkdir(parents=True, exist_ok=True)
            (server.SETTINGS.parent / "error.log").write_text(traceback.format_exc(), encoding="utf-8")
        except Exception:
            pass
        raise
