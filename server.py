"""Descargador local de YouTube / Instagram (y más) usando yt-dlp + ffmpeg.
Ejecuta la interfaz nativa moderna en estilo macOS Tahoe (Liquid Glass).
"""
import json, os, re, shutil, subprocess, sys, threading, time, uuid
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# Habilitar Per-Monitor V2 High-DPI en Windows (elimina 100% de la borrosidad en pantallas escaladas)
IS_WIN = os.name == "nt"
IS_MAC = sys.platform == "darwin"
if IS_WIN:
    try:
        import ctypes
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass

FROZEN = getattr(sys, "frozen", False)
BASE = Path(sys._MEIPASS) if FROZEN else Path(__file__).parent
WEB = BASE / "web"
APP_NAME = "Video Audio Downloader"
APP_VERSION = "2.0"
REPO = "FernandoReyes04/Download-MP4-MP3"

if IS_WIN:
    APPDATA = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "VideoAudioDownloader"
    INSTALL_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Programs" / "VideoAudioDownloader"
elif IS_MAC:
    APPDATA = Path.home() / "Library" / "Application Support" / "VideoAudioDownloader"
    INSTALL_DIR = (Path("/Applications") if os.access("/Applications", os.W_OK)
                   else Path.home() / "Applications") / "VideoAudioDownloader.app"
else:
    APPDATA = Path.home() / ".config" / "VideoAudioDownloader"
    INSTALL_DIR = Path.home() / ".local" / "share" / "VideoAudioDownloader"

SETTINGS = APPDATA / "settings.json"
DEFAULT_OUT = Path.home() / "Downloads" / "VIDEO-AUDIO"
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\VideoAudioDownloader"
INSTALLED_EXE = INSTALL_DIR / "VideoAudioDownloader.exe"


def read_settings():
    try:
        return json.loads(SETTINGS.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_settings(**kw):
    s = read_settings()
    s.update(kw)
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS.write_text(json.dumps(s, indent=2), encoding="utf-8")


def load_out():
    try:
        p = Path(read_settings().get("dir") or DEFAULT_OUT).expanduser()
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


def browse_folder():
    if IS_MAC:
        r = subprocess.run(["osascript", "-e", 'POSIX path of (choose folder with prompt "Carpeta de destino")'],
                           capture_output=True, text=True, encoding="utf-8")
        return r.stdout.strip()
    ps_cmd = ("Add-Type -AssemblyName System.Windows.Forms;"
              "$f=New-Object System.Windows.Forms.FolderBrowserDialog;"
              "$f.Description='Carpeta de destino';$f.ShowNewFolderButton=$true;"
              "$o=New-Object System.Windows.Forms.Form;$o.TopMost=$true;"
              "if($f.ShowDialog($o) -eq 'OK'){[Console]::OutputEncoding=[Text.Encoding]::UTF8;$f.SelectedPath}")
    r = subprocess.run(["powershell", "-NoProfile", "-STA", "-Command", ps_cmd], capture_output=True,
                       text=True, encoding="utf-8", creationflags=NOWIN)
    return r.stdout.strip()


def open_folder(p):
    p = Path(p).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    if IS_WIN:
        os.startfile(p)
    elif IS_MAC:
        subprocess.Popen(["open", str(p)])
    else:
        subprocess.Popen(["xdg-open", str(p)])


def reveal_file(filepath):
    """Abre el Explorador (Windows) o Finder (macOS) con el archivo descargado seleccionado."""
    f = Path(filepath).expanduser().resolve()
    if not f.exists():
        open_folder(f.parent)
        return
    if IS_WIN:
        subprocess.Popen(["explorer.exe", f"/select,{f}"])
    elif IS_MAC:
        subprocess.Popen(["open", "-R", str(f)])
    else:
        open_folder(f.parent)


OUT = load_out()
PORT = 8765
JOBS = {}
NOWIN = subprocess.CREATE_NO_WINDOW if IS_WIN else 0
_ffname = "ffmpeg.exe" if IS_WIN else "ffmpeg"
FFDIR = BASE / "bin" if (BASE / "bin" / _ffname).exists() else None
if not FFDIR and shutil.which("ffmpeg"):
    FFDIR = Path(shutil.which("ffmpeg")).parent
if not FFDIR and IS_MAC:
    for _d in (APPDATA / "bin", Path("/opt/homebrew/bin"), Path("/usr/local/bin")):
        if (_d / "ffmpeg").exists():
            FFDIR = _d
            break
LAST_PING = [0.0]

# Motor de descargas
_eng_name = "yt-dlp.exe" if IS_WIN else ("yt-dlp_macos" if IS_MAC else "yt-dlp")
ENGINE = APPDATA / _eng_name
ENGINE_URL = f"https://github.com/yt-dlp/yt-dlp/releases/latest/download/{_eng_name}"
YTDLP = []
UPDATE = {"state": "idle", "current": "", "latest": "", "message": ""}


def refresh_engine():
    base = [str(ENGINE)] if (ENGINE.exists() and (not IS_WIN or FROZEN)) else (
        [sys.executable, "--ytdlp"] if FROZEN else [sys.executable, "-m", "yt_dlp"])
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
        if not FROZEN and IS_WIN:
            subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "yt-dlp"],
                           check=True, creationflags=NOWIN)
        else:
            ENGINE.parent.mkdir(parents=True, exist_ok=True)
            tmp = ENGINE.with_suffix(".new")
            tmp.write_bytes(http_get(ENGINE_URL, binary=True))
            if not IS_WIN:
                tmp.chmod(0o755)
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


APP = {"state": "idle", "current": APP_VERSION, "latest": "", "message": "", "url": ""}


def _vtuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", v)) or (0,)


def check_app_update():
    try:
        rel = http_get(f"https://api.github.com/repos/{REPO}/releases/latest")
        APP["latest"] = rel["tag_name"].lstrip("vV")
        exts = (".pkg", ".dmg", "-mac.zip", "_mac.zip") if IS_MAC else (".exe",)
        asset = next((a for a in rel.get("assets", []) if a["name"].lower().endswith(exts)), None)
        APP["url"] = asset["browser_download_url"] if asset else ""
        newer = _vtuple(APP["latest"]) > _vtuple(APP_VERSION)
        APP["state"] = "available" if newer and APP["url"] else "uptodate"
    except Exception:
        APP["state"] = "offline"
    return APP


def apply_app_update():
    if IS_MAC and APP.get("url"):
        subprocess.Popen(["open", APP["url"]])
        APP["state"], APP["message"] = "updated", "Abriendo descarga del instalador…"
        return APP
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
        os.replace(exe, old)
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


if "--ytdlp" not in sys.argv:
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
                job["stage"] = "Procesando con FFmpeg…"
            elif line:
                last = line
        proc.wait()
        if proc.returncode != 0:
            raise RuntimeError(last or "Falló la descarga")
        f_str = pathfile.read_text(encoding="utf-8").strip().splitlines()[-1]
        job["file"] = f_str
        job["filename"] = Path(f_str).name
        job["status"], job["percent"] = "done", 100
        try:
            reveal_file(f_str)
        except Exception:
            pass
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
            if self.path == "/api/install":
                desk = bool(data.get("desktop", True))
                startm = bool(data.get("startmenu", True))
                autoupd = bool(data.get("autoupdate", True))
                dest_dir = data.get("dir", "").strip()
                if dest_dir:
                    set_out(dest_dir)
                save_settings(terms_accepted=True, auto_update=autoupd)
                install_self(always=True, desktop=desk, startmenu=startm)
                return self.send_json({"ok": True, "dir": str(OUT)})
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
                jid = data.get("jobId")
                f = JOBS.get(jid, {}).get("file") if jid else None
                if f and Path(f).exists():
                    reveal_file(f)
                else:
                    open_folder(OUT)
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
        if self.path == "/api/terms_status":
            return self.send_json({
                "accepted": read_settings().get("terms_accepted", False),
                "dir": str(OUT),
                "auto": read_settings().get("auto_update", True)
            })
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
        types = {".html": "text/html", ".css": "text/css", ".js": "text/javascript", ".ico": "image/x-icon",
                 ".svg": "image/svg+xml", ".png": "image/png"}
        b = f.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", types.get(f.suffix, "application/octet-stream") + "; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)


def find_browser():
    if IS_MAC:
        for p in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                  "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
                  "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"):
            if os.path.exists(p):
                return p
        return None
    for p in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"):
        if os.path.exists(p):
            return p


def open_window():
    b = find_browser()
    url = f"http://127.0.0.1:{PORT}"
    if b:
        prof = APPDATA / "profile"
        subprocess.Popen([b, f"--app={url}", f"--user-data-dir={prof}", "--window-size=740,880",
                          "--no-first-run"])
    else:
        import webbrowser; webbrowser.open(url)


def watchdog():
    while True:
        time.sleep(3)
        if LAST_PING[0] and time.time() - LAST_PING[0] > 120:
            os._exit(0)


def ps(script):
    return subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True,
                          text=True, encoding="utf-8", creationflags=NOWIN).stdout.strip()


def shortcut_paths(desktop=True, startmenu=True):
    links = []
    if desktop:
        d = ps("[Environment]::GetFolderPath('Desktop')")
        links.append(Path(d) / f"{APP_NAME}.lnk")
    if startmenu:
        s = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        links.append(s / f"{APP_NAME}.lnk")
    return links


def install_self(always=False, desktop=True, startmenu=True):
    """Copia el programa a una ubicación permanente, crea accesos directos y lo registra."""
    if IS_MAC:
        app_src = Path("/Applications/VideoAudioDownloader.app")
        if not app_src.exists():
            app_src = Path.home() / "Applications" / "VideoAudioDownloader.app"
        if desktop and app_src.exists():
            desk = Path.home() / "Desktop" / f"{APP_NAME}.app"
            if not desk.exists():
                try:
                    desk.symlink_to(app_src)
                except Exception:
                    pass
        save_settings(installed=True)
        return
    if not IS_WIN:
        return
    import winreg
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    if FROZEN:
        src = Path(sys.executable)
        if not INSTALLED_EXE.exists() or src.stat().st_size != INSTALLED_EXE.stat().st_size \
                or src.stat().st_mtime > INSTALLED_EXE.stat().st_mtime:
            shutil.copy2(src, INSTALLED_EXE)
        target, args, icon = str(INSTALLED_EXE), "", str(INSTALLED_EXE)
        uninst = f'"{INSTALLED_EXE}" --uninstall'
    else:
        for item in ("server.py", "app.py", "descargar.ico", "web"):
            s = BASE / item
            d = INSTALL_DIR / item
            if s.exists() and s.resolve() != d.resolve():
                if s.is_dir():
                    shutil.rmtree(d, ignore_errors=True); shutil.copytree(s, d)
                else:
                    shutil.copy2(s, d)
        pyw = Path(sys.executable).with_name("pythonw.exe")
        target = str(pyw if pyw.exists() else Path(sys.executable))
        entry = "app.py" if (INSTALL_DIR / "app.py").exists() else "server.py"
        args = f'"{INSTALL_DIR / entry}"'
        icon = str(INSTALL_DIR / "descargar.ico")
        uninst = f'"{target}" "{INSTALL_DIR / entry}" --uninstall'
    if always or not read_settings().get("installed"):
        for lnk in shortcut_paths(desktop=desktop, startmenu=startmenu):
            lnk.parent.mkdir(parents=True, exist_ok=True)
            ps(f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}');"
               f"$s.TargetPath='{target}';$s.Arguments='{args}';$s.WorkingDirectory='{INSTALL_DIR}';"
               f"$s.IconLocation='{icon}';$s.Description='{APP_NAME}';$s.Save()")
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as k:
            for n, v in {"DisplayName": APP_NAME, "DisplayIcon": icon,
                         "InstallLocation": str(INSTALL_DIR), "Publisher": "Local",
                         "UninstallString": uninst}.items():
                winreg.SetValueEx(k, n, 0, winreg.REG_SZ, v)
        save_settings(installed=True)


def uninstall_self():
    if IS_WIN:
        import winreg
        for lnk in shortcut_paths(desktop=True, startmenu=True):
            lnk.unlink(missing_ok=True)
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
        except OSError:
            pass
        save_settings(installed=False, terms_accepted=False)
        subprocess.Popen(f'cmd /c ping 127.0.0.1 -n 4 >nul & rmdir /s /q "{INSTALL_DIR}"',
                         creationflags=NOWIN)


def port_in_use():
    import socket
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", PORT)) == 0


def launch_desktop_window():
    ico = BASE / "descargar.ico"
    icon_path = str(ico) if ico.exists() else None
    try:
        import webview
        webview.create_window(
            APP_NAME,
            f"http://127.0.0.1:{PORT}",
            width=740,
            height=720,
            min_size=(580, 560),
            background_color='#eef1f6',
            text_select=True
        )
        webview.start(icon=icon_path)
    except Exception:
        open_window()
        while True:
            time.sleep(1)


def _main():
    if "--ytdlp" in sys.argv:
        import yt_dlp
        yt_dlp.main(sys.argv[sys.argv.index("--ytdlp") + 1:])
        sys.exit(0)
    if "--uninstall" in sys.argv:
        uninstall_self(); sys.exit(0)
    if "--install" in sys.argv:
        install_self(always=True); sys.exit(0)
    if port_in_use():
        open_window(); sys.exit(0)

    try:
        srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    except OSError:
        open_window(); sys.exit(0)

    threading.Thread(target=srv.serve_forever, daemon=True).start()
    threading.Thread(target=watchdog, daemon=True).start()
    threading.Thread(target=startup_update, daemon=True).start()
    cleanup_old()
    LAST_PING[0] = time.time()

    launch_desktop_window()


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
