"""Descargador local de YouTube / Instagram (y más) usando yt-dlp + ffmpeg.
Uso:  python server.py   ->  abre http://127.0.0.1:8765
"""
import json, os, re, shutil, subprocess, sys, threading, time, uuid
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)
BASE = Path(sys._MEIPASS) if FROZEN else Path(__file__).parent
WEB = BASE / "web"
SETTINGS = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "VideoAudioDownloader" / "settings.json"
DEFAULT_OUT = Path.home() / "Downloads" / "VIDEO-AUDIO"


def load_out():
    try:
        p = Path(json.loads(SETTINGS.read_text(encoding="utf-8"))["dir"])
        p.mkdir(parents=True, exist_ok=True)
        return p
    except Exception:
        DEFAULT_OUT.mkdir(parents=True, exist_ok=True)
        return DEFAULT_OUT


def set_out(path):
    global OUT
    p = Path(path).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    if not os.access(p, os.W_OK):
        raise RuntimeError("No hay permiso de escritura en esa carpeta")
    OUT = p
    save_settings(dir=str(p))


def read_settings():
    try:
        return json.loads(SETTINGS.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_settings(**kw):
    s = read_settings(); s.update(kw)
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS.write_text(json.dumps(s), encoding="utf-8")


def browse_folder():
    ps = ("Add-Type -AssemblyName System.Windows.Forms;"
          "$f=New-Object System.Windows.Forms.FolderBrowserDialog;"
          "$f.Description='Carpeta de destino';$f.ShowNewFolderButton=$true;"
          "$o=New-Object System.Windows.Forms.Form;$o.TopMost=$true;"
          "if($f.ShowDialog($o) -eq 'OK'){[Console]::OutputEncoding=[Text.Encoding]::UTF8;$f.SelectedPath}")
    r = subprocess.run(["powershell", "-NoProfile", "-STA", "-Command", ps], capture_output=True,
                       text=True, encoding="utf-8", creationflags=NOWIN)
    return r.stdout.strip()


OUT = load_out()
PORT = 8765
JOBS = {}
NOWIN = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
FFDIR = BASE / "bin" if (BASE / "bin" / "ffmpeg.exe").exists() else None
if not FFDIR and shutil.which("ffmpeg"):
    FFDIR = Path(shutil.which("ffmpeg")).parent
LAST_PING = [0.0]

# ---------- Motor de descargas (yt-dlp) con actualización ----------
ENGINE = SETTINGS.parent / "yt-dlp.exe"   # copia actualizada descargada de GitHub
ENGINE_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
YTDLP = []
UPDATE = {"state": "idle", "current": "", "latest": "", "message": ""}


def refresh_engine():
    if ENGINE.exists():
        base = [str(ENGINE)]
    else:
        base = [sys.executable, "--ytdlp"] if FROZEN else [sys.executable, "-m", "yt_dlp"]
    if FFDIR:
        base += ["--ffmpeg-location", str(FFDIR)]
    YTDLP[:] = base
    r = subprocess.run(base + ["--version"], capture_output=True, text=True, creationflags=NOWIN)
    UPDATE["current"] = r.stdout.strip()


def http_get(url, binary=False):
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "VideoAudioDownloader"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read() if binary else json.loads(r.read())


def check_update():
    try:
        UPDATE["latest"] = http_get("https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest")["tag_name"]
        UPDATE["state"] = "available" if UPDATE["latest"] != UPDATE["current"] else "uptodate"
    except Exception:
        UPDATE["state"], UPDATE["message"] = "offline", "No se pudo buscar actualizaciones"
    return UPDATE


def apply_update():
    if any(j.get("status") == "running" for j in JOBS.values()):
        UPDATE["message"] = "Espera a que terminen las descargas en curso"
        return UPDATE
    UPDATE["state"] = "updating"
    try:
        ENGINE.parent.mkdir(parents=True, exist_ok=True)
        tmp = ENGINE.with_suffix(".new")
        tmp.write_bytes(http_get(ENGINE_URL, binary=True))
        ok = subprocess.run([str(tmp), "--version"], capture_output=True, text=True, creationflags=NOWIN)
        if ok.returncode != 0:
            raise RuntimeError("Descarga inválida")
        os.replace(tmp, ENGINE)
        refresh_engine()
        UPDATE["state"], UPDATE["message"] = "updated", f"Actualizado a {UPDATE['current']}"
    except Exception as e:
        UPDATE["state"], UPDATE["message"] = "error", f"Falló la actualización: {e}"
    return UPDATE


def startup_update():
    check_update()
    if UPDATE["state"] == "available" and read_settings().get("auto_update", True):
        apply_update()
    check_app_update()
    if APP["state"] == "available" and read_settings().get("auto_update", True):
        apply_app_update()


# ---------- Actualización del programa (GitHub Releases) ----------
APP_VERSION = "1"   # debe coincidir con la etiqueta del release (v1, v2, ...)
REPO = "FernandoReyes04/Download-MP4-MP3"
APP = {"state": "idle", "current": APP_VERSION, "latest": "", "message": "", "url": ""}


def _vtuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", v)) or (0,)


def check_app_update():
    try:
        rel = http_get(f"https://api.github.com/repos/{REPO}/releases/latest")
        APP["latest"] = rel["tag_name"].lstrip("vV")
        asset = next((a for a in rel.get("assets", []) if a["name"].lower().endswith(".exe")), None)
        APP["url"] = asset["browser_download_url"] if asset else ""
        newer = _vtuple(APP["latest"]) > _vtuple(APP_VERSION)
        APP["state"] = "available" if newer and APP["url"] else "uptodate"
    except Exception:
        APP["state"] = "offline"
    return APP


def apply_app_update():
    if not FROZEN:
        APP["state"], APP["message"] = "error", "Solo disponible en el programa instalado (.exe)"
        return APP
    if any(j.get("status") == "running" for j in JOBS.values()):
        APP["message"] = "Espera a que terminen las descargas en curso"
        return APP
    APP["state"] = "updating"
    exe = Path(sys.executable)
    new, old = exe.with_suffix(".new"), exe.with_suffix(".old")
    try:
        new.write_bytes(http_get(APP["url"], binary=True))
        if new.stat().st_size < 5_000_000:
            raise RuntimeError("Descarga inválida")
        old.unlink(missing_ok=True)
        os.replace(exe, old)      # Windows permite renombrar un .exe en ejecución
        os.replace(new, exe)
        subprocess.Popen([str(exe), "--restarted"], cwd=str(exe.parent))
        os._exit(0)
    except Exception as e:
        if old.exists() and not exe.exists():
            os.replace(old, exe)
        APP["state"], APP["message"] = "error", f"Falló la actualización: {e}"
    return APP


def cleanup_old():
    if FROZEN:
        Path(sys.executable).with_suffix(".old").unlink(missing_ok=True)


if "--ytdlp" not in sys.argv:  # evita recursión cuando el programa actúa como yt-dlp
    refresh_engine()


def get_info(url):
    p = subprocess.run(YTDLP + ["-J", "--no-playlist", "--no-warnings", url],
                       capture_output=True, text=True, encoding="utf-8", creationflags=NOWIN)
    if p.returncode != 0:
        raise RuntimeError((p.stderr.strip().splitlines() or ["No se pudo leer el enlace"])[-1])
    d = json.loads(p.stdout)
    heights = sorted({f["height"] for f in d.get("formats", [])
                      if f.get("height") and f.get("vcodec") not in (None, "none")}, reverse=True)
    return {"title": d.get("title"), "thumbnail": d.get("thumbnail"),
            "duration": d.get("duration"), "uploader": d.get("uploader"),
            "site": d.get("extractor_key"), "heights": heights}


def run_job(job_id, url, kind, height):
    job = JOBS[job_id]
    out = OUT
    pathfile = out / f".{job_id}.path"
    cmd = YTDLP + ["--no-playlist", "--newline", "--progress", "--no-warnings",
                   "--progress-template", "download:PROG|%(progress._percent_str)s|%(progress._speed_str)s|%(progress._eta_str)s",
                   "--print-to-file", "after_move:filepath", str(pathfile),
                   "-o", str(out / "%(title).150B [%(id)s].%(ext)s"), "--windows-filenames"]
    if kind == "mp3":
        cmd += ["-f", "ba/b", "-x", "--audio-format", "mp3", "--audio-quality", "0",
                "--embed-thumbnail", "--add-metadata"]
    else:
        h = int(height) if height else 99999
        cmd += ["-f", f"bv*[height<={h}]+ba/b[height<={h}]/b",
                "-S", "res,ext:mp4:m4a,vcodec:h264", "--merge-output-format", "mp4"]
    cmd.append(url)
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                encoding="utf-8", errors="replace", creationflags=NOWIN)
        last = ""
        for line in proc.stdout:
            line = line.strip()
            if line.startswith("PROG|"):
                _, pct, spd, eta = line.split("|")
                m = re.search(r"[\d.]+", pct)
                if m:
                    job["percent"] = float(m.group())
                job["speed"], job["eta"] = spd.strip(), eta.strip()
            elif line.startswith(("[Merger]", "[ExtractAudio]", "[VideoConvertor]")):
                job["stage"] = "Procesando con ffmpeg…"
            elif line:
                last = line
        proc.wait()
        if proc.returncode != 0:
            raise RuntimeError(last or "Falló la descarga")
        job["file"] = pathfile.read_text(encoding="utf-8").strip().splitlines()[-1]
        job["status"], job["percent"] = "done", 100
    except Exception as e:
        job["status"], job["error"] = "error", str(e)
    finally:
        pathfile.unlink(missing_ok=True)


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def send_json(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def body(self):
        return json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")

    def do_POST(self):
        try:
            data = self.body()
            if self.path == "/api/app/apply":
                return self.send_json(apply_app_update())
            if self.path == "/api/update/apply":
                return self.send_json(apply_update())
            if self.path == "/api/update/auto":
                save_settings(auto_update=bool(data.get("on")))
                return self.send_json({"ok": True})
            if self.path == "/api/browse":
                return self.send_json({"dir": browse_folder()})
            if self.path == "/api/settings":
                set_out(data.get("dir", ""))
                return self.send_json({"dir": str(OUT)})
            if self.path == "/api/open":
                os.startfile(OUT)
                return self.send_json({"ok": True})
            url = (data.get("url") or "").strip()
            if not re.match(r"^https?://", url):
                return self.send_json({"error": "Pega un enlace válido (http/https)"}, 400)
            if self.path == "/api/info":
                return self.send_json(get_info(url))
            if self.path == "/api/download":
                jid = uuid.uuid4().hex[:10]
                JOBS[jid] = {"status": "running", "percent": 0, "speed": "", "eta": "", "stage": "Descargando…"}
                threading.Thread(target=run_job, args=(jid, url, data.get("kind", "mp4"), data.get("height")),
                                 daemon=True).start()
                return self.send_json({"id": jid})
            self.send_json({"error": "not found"}, 404)
        except Exception as e:
            self.send_json({"error": str(e)}, 500)

    def do_GET(self):
        if self.path == "/api/app/status":
            return self.send_json(APP)
        if self.path == "/api/update/status":
            return self.send_json({**UPDATE, "auto": read_settings().get("auto_update", True)})
        if self.path == "/api/settings":
            return self.send_json({"dir": str(OUT)})
        if self.path == "/api/ping":
            LAST_PING[0] = time.time()
            return self.send_json({"ok": True})
        if self.path.startswith("/api/progress/"):
            return self.send_json(JOBS.get(self.path.rsplit("/", 1)[1], {"status": "error", "error": "Trabajo no encontrado"}))
        if self.path.startswith("/api/file/"):
            job = JOBS.get(self.path.rsplit("/", 1)[1])
            if not job or "file" not in job:
                return self.send_json({"error": "no file"}, 404)
            f = Path(job["file"])
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(f.stat().st_size))
            self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + __import__("urllib.parse").parse.quote(f.name))
            self.end_headers()
            with open(f, "rb") as fh:
                while chunk := fh.read(1 << 20):
                    self.wfile.write(chunk)
            return
        name = "index.html" if self.path in ("/", "") else self.path.lstrip("/").split("?")[0]
        f = (WEB / name).resolve()
        if WEB.resolve() not in f.parents or not f.is_file():
            self.send_response(404); self.end_headers(); return
        types = {".html": "text/html", ".css": "text/css", ".js": "text/javascript", ".ico": "image/x-icon"}
        b = f.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", types.get(f.suffix, "application/octet-stream") + "; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)


def find_browser():
    for p in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"):
        if os.path.exists(p):
            return p


def open_window():
    b = find_browser()
    url = f"http://127.0.0.1:{PORT}"
    if b:  # ventana de aplicación sin barra de navegador
        prof = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "VideoAudioDownloader" / "profile"
        subprocess.Popen([b, f"--app={url}", f"--user-data-dir={prof}", "--window-size=720,860",
                          "--no-first-run"])
    else:
        import webbrowser; webbrowser.open(url)


def watchdog():
    # Cierra el programa cuando se cierra la ventana (se dejan de recibir latidos)
    while True:
        time.sleep(3)
        if LAST_PING[0] and time.time() - LAST_PING[0] > 120:
            os._exit(0)


APP_NAME = "Video Audio Downloader"
INSTALL_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Programs" / "VideoAudioDownloader"
INSTALLED_EXE = INSTALL_DIR / "VideoAudioDownloader.exe"
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\VideoAudioDownloader"


def ps(script):
    return subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True,
                          text=True, encoding="utf-8", creationflags=NOWIN).stdout.strip()


def shortcut_paths():
    desktop = ps("[Environment]::GetFolderPath('Desktop')")
    start = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    return [Path(desktop) / f"{APP_NAME}.lnk", start / f"{APP_NAME}.lnk"]


def install_self():
    """Copia el programa a una ubicación permanente, crea accesos directos y lo registra."""
    import winreg
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    src = Path(sys.executable)
    if not INSTALLED_EXE.exists() or src.stat().st_size != INSTALLED_EXE.stat().st_size \
            or src.stat().st_mtime > INSTALLED_EXE.stat().st_mtime:
        shutil.copy2(src, INSTALLED_EXE)
    first = not read_settings().get("installed")
    if first:
        for lnk in shortcut_paths():
            lnk.parent.mkdir(parents=True, exist_ok=True)
            ps(f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}');"
               f"$s.TargetPath='{INSTALLED_EXE}';$s.WorkingDirectory='{INSTALL_DIR}';"
               f"$s.IconLocation='{INSTALLED_EXE}';$s.Description='{APP_NAME}';$s.Save()")
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as k:
            for n, v in {"DisplayName": APP_NAME, "DisplayIcon": str(INSTALLED_EXE),
                         "InstallLocation": str(INSTALL_DIR), "Publisher": "Local",
                         "UninstallString": f'"{INSTALLED_EXE}" --uninstall'}.items():
                winreg.SetValueEx(k, n, 0, winreg.REG_SZ, v)
        save_settings(installed=True)


def uninstall_self():
    import winreg
    for lnk in shortcut_paths():
        lnk.unlink(missing_ok=True)
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
    except OSError:
        pass
    save_settings(installed=False)
    # borra la carpeta del programa tras cerrarse este proceso (no toca tus descargas)
    subprocess.Popen(f'cmd /c ping 127.0.0.1 -n 4 >nul & rmdir /s /q "{INSTALL_DIR}"',
                     creationflags=NOWIN)


def port_in_use():
    import socket
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", PORT)) == 0


def _main():
    if "--ytdlp" in sys.argv:
        import yt_dlp
        yt_dlp.main(sys.argv[sys.argv.index("--ytdlp") + 1:])
        sys.exit(0)
    if FROZEN and "--uninstall" in sys.argv:
        uninstall_self(); sys.exit(0)
    if port_in_use():  # ya hay una instancia abierta
        open_window(); sys.exit(0)
    if FROZEN and os.name == "nt" and Path(sys.executable).resolve() != INSTALLED_EXE.resolve():
        try:  # primera ejecución / actualización: instala y lanza la copia permanente
            install_self()
            subprocess.Popen([str(INSTALLED_EXE)], cwd=str(INSTALL_DIR))
            sys.exit(0)
        except SystemExit:
            raise
        except Exception:
            pass  # si falla la instalación, se ejecuta desde donde está
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    threading.Thread(target=watchdog, daemon=True).start()
    threading.Thread(target=startup_update, daemon=True).start()
    cleanup_old()
    if "--restarted" not in sys.argv:
        threading.Timer(0.5, open_window).start()
    LAST_PING[0] = time.time()
    srv.serve_forever()


if __name__ == "__main__":
    try:
        _main()
    except SystemExit:
        raise
    except BaseException:
        import traceback
        try:
            SETTINGS.parent.mkdir(parents=True, exist_ok=True)
            (SETTINGS.parent / "error.log").write_text(traceback.format_exc(), encoding="utf-8")
        except Exception:
            pass
        raise
