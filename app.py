"""Video & Audio Downloader — Aplicación de escritorio nativa (Windows y macOS).
Interfaz minimalista en tonos neutros + asistente de instalación con Términos y Condiciones.
"""
import io, json, os, re, shutil, subprocess, sys, threading, urllib.request
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

IS_WIN = os.name == "nt"
IS_MAC = sys.platform == "darwin"
FROZEN = getattr(sys, "frozen", False)
BASE = Path(sys._MEIPASS) if FROZEN else Path(__file__).parent
NOWIN = subprocess.CREATE_NO_WINDOW if IS_WIN else 0

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

# Paleta minimalista neutra (sin degradados)
BG = "#161618"
SURFACE = "#202024"
BORDER = "#2E2E33"
FG = "#EDEDEF"
MUTED = "#8E8E96"
ACCENT = "#E4E4E7"
ACCENT_FG = "#141416"
FONT = "Segoe UI" if IS_WIN else ("SF Pro Text" if IS_MAC else "Sans")

TERMS_TEXT = """TÉRMINOS Y CONDICIONES DE USO — VIDEO AUDIO DOWNLOADER

1. USO PERSONAL Y LOCAL
Este software se ejecuta de forma 100% local en tu computadora. No recopila datos personales, no envía historiales a servidores externos ni incluye publicidad.

2. PROPIEDAD INTELECTUAL Y DERECHOS DE AUTOR
El usuario es el único responsable del contenido que descargue. Esta herramienta debe emplearse únicamente para:
  • Contenido propio o del cual poseas los derechos.
  • Material bajo licencia libre, Creative Commons o de dominio público.
  • Copias privadas permitidas por la legislación aplicable en tu país.

3. TÉRMINOS DE TERCEROS
El usuario se compromete a respetar los Términos de Servicio de YouTube, Instagram y cualquier otra plataforma utilizada.

4. AUSENCIA DE GARANTÍA
El software se proporciona "tal cual" (AS IS), sin garantías de ningún tipo. Los autores no se hacen responsables del mal uso de la aplicación."""


def read_settings():
    try:
        return json.loads(SETTINGS.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_settings(**kw):
    s = read_settings(); s.update(kw)
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS.write_text(json.dumps(s, indent=2), encoding="utf-8")


def get_out_dir():
    d = Path(read_settings().get("dir") or DEFAULT_OUT).expanduser()
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------- Motor yt-dlp + FFmpeg ----------
_ffname = "ffmpeg.exe" if IS_WIN else "ffmpeg"
FFDIR = BASE / "bin" if (BASE / "bin" / _ffname).exists() else None
if not FFDIR and shutil.which("ffmpeg"):
    FFDIR = Path(shutil.which("ffmpeg")).parent
if not FFDIR and IS_MAC:
    for _d in (Path("/opt/homebrew/bin"), Path("/usr/local/bin")):
        if (_d / "ffmpeg").exists():
            FFDIR = _d; break

_eng_name = "yt-dlp.exe" if IS_WIN else ("yt-dlp_macos" if IS_MAC else "yt-dlp")
ENGINE = APPDATA / _eng_name
ENGINE_URL = f"https://github.com/yt-dlp/yt-dlp/releases/latest/download/{_eng_name}"


def ytdlp_cmd():
    if ENGINE.exists() and (not IS_WIN or FROZEN):
        base = [str(ENGINE)]
    else:
        base = [sys.executable, "--ytdlp"] if FROZEN else [sys.executable, "-m", "yt_dlp"]
    if FFDIR:
        base += ["--ffmpeg-location", str(FFDIR)]
    return base


def http_get(url, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": "VideoAudioDownloader"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read() if binary else json.loads(r.read())


# ---------- Instalación en el sistema ----------
def _ps(script):
    return subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True,
                          text=True, encoding="utf-8", creationflags=NOWIN).stdout.strip()


def perform_install(install_dir: Path, opt_desktop=True, opt_startmenu=True, opt_autoupdate=True):
    install_dir.mkdir(parents=True, exist_ok=True)
    if IS_WIN:
        import winreg
        for item in ("app.py", "server.py", "descargar.ico", "web"):
            s, d = BASE / item, install_dir / item
            if s.exists() and s.resolve() != d.resolve():
                if s.is_dir():
                    shutil.rmtree(d, ignore_errors=True); shutil.copytree(s, d)
                else:
                    shutil.copy2(s, d)
        pyw = Path(sys.executable).with_name("pythonw.exe")
        target = str(pyw if pyw.exists() else Path(sys.executable))
        script = install_dir / ("app.py" if (install_dir / "app.py").exists() else "server.py")
        args = f'"{script}"'
        icon = str(install_dir / "descargar.ico")
        links = []
        if opt_desktop:
            links.append(Path(_ps("[Environment]::GetFolderPath('Desktop')")) / f"{APP_NAME}.lnk")
        if opt_startmenu:
            links.append(Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs" / f"{APP_NAME}.lnk")
        for lnk in links:
            lnk.parent.mkdir(parents=True, exist_ok=True)
            _ps(f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}');"
                f"$s.TargetPath='{target}';$s.Arguments='{args}';$s.WorkingDirectory='{install_dir}';"
                f"$s.IconLocation='{icon}';$s.Description='{APP_NAME}';$s.Save()")
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as k:
            for n, v in {"DisplayName": APP_NAME, "DisplayVersion": APP_VERSION, "DisplayIcon": icon,
                         "InstallLocation": str(install_dir), "Publisher": "FernandoReyes04",
                         "UninstallString": f'"{target}" "{script}" --uninstall'}.items():
                winreg.SetValueEx(k, n, 0, winreg.REG_SZ, v)
    elif IS_MAC and FROZEN:
        parts = Path(sys.executable).resolve().parts
        if "VideoAudioDownloader.app" in parts:
            bundle = Path(*parts[:parts.index("VideoAudioDownloader.app") + 1])
            if bundle != INSTALL_DIR.resolve():
                shutil.rmtree(INSTALL_DIR, ignore_errors=True)
                shutil.copytree(bundle, INSTALL_DIR, symlinks=True)
                subprocess.run(["xattr", "-cr", str(INSTALL_DIR)], capture_output=True)
        if opt_desktop:
            desk = Path.home() / "Desktop" / f"{APP_NAME}.app"
            if not desk.exists():
                try:
                    desk.symlink_to(INSTALL_DIR)
                except Exception:
                    pass
    save_settings(installed=True, terms_accepted=True, auto_update=opt_autoupdate,
                  install_dir=str(install_dir))


def uninstall_self():
    if IS_WIN:
        import winreg
        for p in (Path(_ps("[Environment]::GetFolderPath('Desktop')")) / f"{APP_NAME}.lnk",
                  Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs" / f"{APP_NAME}.lnk"):
            p.unlink(missing_ok=True)
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
        except OSError:
            pass
        save_settings(installed=False, terms_accepted=False)
        subprocess.Popen(f'cmd /c ping 127.0.0.1 -n 3 >nul & rmdir /s /q "{INSTALL_DIR}"', creationflags=NOWIN)


# ---------- Estilos Tkinter neutros ----------
def apply_theme(root):
    root.configure(bg=BG)
    ico = BASE / "descargar.ico"
    if IS_WIN and ico.exists():
        try:
            root.iconbitmap(str(ico))
        except Exception:
            pass
    s = ttk.Style(root)
    s.theme_use("clam")
    s.configure(".", background=BG, foreground=FG, font=(FONT, 10), borderwidth=0)
    s.configure("Card.TFrame", background=SURFACE)
    s.configure("TLabel", background=BG, foreground=FG)
    s.configure("Card.TLabel", background=SURFACE, foreground=FG)
    s.configure("Muted.TLabel", background=BG, foreground=MUTED, font=(FONT, 9))
    s.configure("CardMuted.TLabel", background=SURFACE, foreground=MUTED, font=(FONT, 9))
    s.configure("Title.TLabel", background=BG, foreground=FG, font=(FONT, 16, "bold"))
    s.configure("H2.TLabel", background=SURFACE, foreground=FG, font=(FONT, 11, "bold"))
    s.configure("TCheckbutton", background=SURFACE, foreground=FG, font=(FONT, 10))
    s.map("TCheckbutton", background=[("active", SURFACE)])
    s.configure("TRadiobutton", background=SURFACE, foreground=FG, font=(FONT, 10))
    s.map("TRadiobutton", background=[("active", SURFACE)])
    s.configure("Primary.TButton", background=ACCENT, foreground=ACCENT_FG, font=(FONT, 10, "bold"), padding=(14, 8))
    s.map("Primary.TButton", background=[("active", "#FFFFFF"), ("disabled", BORDER)],
          foreground=[("disabled", MUTED)])
    s.configure("Ghost.TButton", background=SURFACE, foreground=FG, font=(FONT, 9), padding=(12, 7))
    s.map("Ghost.TButton", background=[("active", BORDER)])
    s.configure("TCombobox", fieldbackground=BG, background=SURFACE, foreground=FG, arrowcolor=FG, padding=6)
    s.map("TCombobox", fieldbackground=[("readonly", BG)], foreground=[("readonly", FG)])
    s.configure("Horizontal.TProgressbar", troughcolor=BG, background=ACCENT, thickness=6)


def make_entry(parent, textvariable=None):
    e = tk.Entry(parent, textvariable=textvariable, bg=BG, fg=FG, insertbackground=FG,
                 relief="flat", font=(FONT, 10), highlightthickness=1,
                 highlightbackground=BORDER, highlightcolor=MUTED)
    return e


def make_card(parent):
    f = tk.Frame(parent, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER, padx=18, pady=16)
    return f


# ---------- Asistente de instalación (Wizard con casillas y Términos) ----------
class InstallerWizard(tk.Toplevel):
    def __init__(self, master, on_done):
        super().__init__(master)
        self.on_done = on_done
        self.title(f"Instalación — {APP_NAME}")
        self.geometry("560x470")
        self.resizable(False, False)
        self.configure(bg=BG)
        self.protocol("WM_DELETE_WINDOW", lambda: sys.exit(0))
        ico = BASE / "descargar.ico"
        if IS_WIN and ico.exists():
            try:
                self.iconbitmap(str(ico))
            except Exception:
                pass

        self.step = 0
        self.accept_var = tk.BooleanVar(value=False)
        self.opt_desktop = tk.BooleanVar(value=True)
        self.opt_start = tk.BooleanVar(value=True)
        self.opt_autoupd = tk.BooleanVar(value=True)
        self.opt_launch = tk.BooleanVar(value=True)
        self.dir_var = tk.StringVar(value=str(INSTALL_DIR))
        self.out_var = tk.StringVar(value=str(get_out_dir()))

        self.header = ttk.Label(self, text="", style="Title.TLabel")
        self.header.pack(anchor="w", padx=24, pady=(20, 4))
        self.sub = ttk.Label(self, text="", style="Muted.TLabel")
        self.sub.pack(anchor="w", padx=24, pady=(0, 12))

        self.body = make_card(self)
        self.body.pack(fill="both", expand=True, padx=24, pady=4)

        nav = tk.Frame(self, bg=BG)
        nav.pack(fill="x", padx=24, pady=16)
        self.back_btn = ttk.Button(nav, text="Atrás", style="Ghost.TButton", command=self.prev_step)
        self.back_btn.pack(side="left")
        ttk.Button(nav, text="Cancelar", style="Ghost.TButton", command=lambda: sys.exit(0)).pack(side="left", padx=8)
        self.next_btn = ttk.Button(nav, text="Siguiente", style="Primary.TButton", command=self.next_step)
        self.next_btn.pack(side="right")

        self.render_step()

    def clear_body(self):
        for w in self.body.winfo_children():
            w.destroy()

    def render_step(self):
        self.clear_body()
        if self.step == 0:
            self.header.config(text="Términos y Condiciones")
            self.sub.config(text="Paso 1 de 3 · Lee y acepta el acuerdo para continuar")
            self.back_btn.state(["disabled"])
            txt = tk.Text(self.body, bg=BG, fg=FG, relief="flat", font=(FONT, 9), wrap="word",
                          height=11, padx=10, pady=10, highlightthickness=1, highlightbackground=BORDER)
            txt.insert("1.0", TERMS_TEXT)
            txt.config(state="disabled")
            txt.pack(fill="both", expand=True, pady=(0, 12))
            cb = ttk.Checkbutton(self.body, text="He leído y acepto los Términos y Condiciones de uso",
                                 variable=self.accept_var, command=self.toggle_next)
            cb.pack(anchor="w")
            self.next_btn.config(text="Siguiente")
            self.toggle_next()

        elif self.step == 1:
            self.header.config(text="Opciones de instalación")
            self.sub.config(text="Paso 2 de 3 · Selecciona los componentes y carpetas")
            self.back_btn.state(["!disabled"])
            self.next_btn.state(["!disabled"])
            self.next_btn.config(text="Instalar")

            ttk.Checkbutton(self.body, text="Crear acceso directo en el Escritorio",
                            variable=self.opt_desktop).pack(anchor="w", pady=3)
            if IS_WIN:
                ttk.Checkbutton(self.body, text="Agregar al Menú Inicio y a Aplicaciones instaladas",
                                variable=self.opt_start).pack(anchor="w", pady=3)
            ttk.Checkbutton(self.body, text="Actualizar automáticamente el motor de descargas (yt-dlp)",
                            variable=self.opt_autoupd).pack(anchor="w", pady=3)

            ttk.Label(self.body, text="Carpeta de descargas predeterminada:",
                      style="CardMuted.TLabel").pack(anchor="w", pady=(14, 4))
            row = tk.Frame(self.body, bg=SURFACE)
            row.pack(fill="x")
            make_entry(row, self.out_var).pack(side="left", fill="x", expand=True, ipady=5)
            ttk.Button(row, text="Examinar…", style="Ghost.TButton",
                       command=self.pick_out).pack(side="left", padx=(8, 0))

        elif self.step == 2:
            self.header.config(text="Instalación completada")
            self.sub.config(text="Paso 3 de 3 · El programa quedó configurado en tu equipo")
            self.back_btn.state(["disabled"])
            ttk.Label(self.body, text=f"✓ {APP_NAME} se instaló correctamente.",
                      style="H2.TLabel").pack(anchor="w", pady=(8, 8))
            ttk.Label(self.body, text=f"Ubicación: {INSTALL_DIR}\nDescargas: {self.out_var.get()}",
                      style="CardMuted.TLabel").pack(anchor="w", pady=(0, 16))
            ttk.Checkbutton(self.body, text=f"Iniciar {APP_NAME} al cerrar este asistente",
                            variable=self.opt_launch).pack(anchor="w")
            self.next_btn.config(text="Finalizar")

    def toggle_next(self):
        self.next_btn.state(["!disabled"] if self.accept_var.get() else ["disabled"])

    def pick_out(self):
        d = filedialog.askdirectory(parent=self, initialdir=self.out_var.get())
        if d:
            self.out_var.set(d)

    def prev_step(self):
        if self.step > 0:
            self.step -= 1
            self.render_step()

    def next_step(self):
        if self.step == 0:
            self.step = 1
            self.render_step()
        elif self.step == 1:
            save_settings(dir=self.out_var.get())
            perform_install(Path(self.dir_var.get()), self.opt_desktop.get(),
                            self.opt_start.get(), self.opt_autoupd.get())
            self.step = 2
            self.render_step()
        else:
            launch = self.opt_launch.get()
            self.destroy()
            if launch:
                self.on_done()
            else:
                sys.exit(0)


# ---------- Ventana principal minimalista ----------
class DownloaderApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("640x560")
        self.root.minsize(580, 520)
        self.info = None
        self.heights = []
        self.last_file = None
        self.thumb_img = None

        # Encabezado neutro
        top = tk.Frame(root, bg=BG)
        top.pack(fill="x", padx=28, pady=(22, 12))
        ttk.Label(top, text="Video & Audio Downloader", style="Title.TLabel").pack(anchor="w")
        ttk.Label(top, text="Descarga local en máxima calidad · MP4 y MP3",
                  style="Muted.TLabel").pack(anchor="w", pady=(2, 0))

        # Tarjeta: Enlace
        c_url = make_card(root)
        c_url.pack(fill="x", padx=28, pady=6)
        ttk.Label(c_url, text="ENLACE DEL VIDEO O AUDIO", style="CardMuted.TLabel").pack(anchor="w", pady=(0, 6))
        r_url = tk.Frame(c_url, bg=SURFACE)
        r_url.pack(fill="x")
        self.url_var = tk.StringVar()
        self.url_entry = make_entry(r_url, self.url_var)
        self.url_entry.pack(side="left", fill="x", expand=True, ipady=6)
        self.url_entry.bind("<Return>", lambda e: self.analyze())
        ttk.Button(r_url, text="Pegar", style="Ghost.TButton", command=self.paste_url).pack(side="left", padx=(6, 0))
        self.an_btn = ttk.Button(r_url, text="Analizar", style="Primary.TButton", command=self.analyze)
        self.an_btn.pack(side="left", padx=(6, 0))

        # Tarjeta: Información y formato
        self.c_meta = make_card(root)
        self.c_meta.pack(fill="x", padx=28, pady=6)
        meta_top = tk.Frame(self.c_meta, bg=SURFACE)
        meta_top.pack(fill="x")
        self.thumb_lbl = tk.Label(meta_top, bg=BG, width=16, height=5, fg=MUTED, text="Sin vista previa",
                                  font=(FONT, 8))
        self.thumb_lbl.pack(side="left", padx=(0, 14))
        meta_txt = tk.Frame(meta_top, bg=SURFACE)
        meta_txt.pack(side="left", fill="both", expand=True)
        self.title_lbl = ttk.Label(meta_txt, text="Pega un enlace y pulsa Analizar (o descarga directo)",
                                   style="H2.TLabel", wraplength=390)
        self.title_lbl.pack(anchor="w")
        self.sub_lbl = ttk.Label(meta_txt, text="YouTube · Instagram · TikTok · X · y más",
                                 style="CardMuted.TLabel")
        self.sub_lbl.pack(anchor="w", pady=(4, 0))

        opts = tk.Frame(self.c_meta, bg=SURFACE)
        opts.pack(fill="x", pady=(14, 0))
        self.kind_var = tk.StringVar(value="mp4")
        ttk.Radiobutton(opts, text="MP4 (Video)", value="mp4", variable=self.kind_var,
                        command=self.update_qualities).pack(side="left")
        ttk.Radiobutton(opts, text="MP3 (Solo audio)", value="mp3", variable=self.kind_var,
                        command=self.update_qualities).pack(side="left", padx=(16, 20))
        ttk.Label(opts, text="Calidad:", style="CardMuted.TLabel").pack(side="left", padx=(0, 6))
        self.qual_var = tk.StringVar(value="Máxima disponible")
        self.qual_cb = ttk.Combobox(opts, textvariable=self.qual_var, state="readonly", width=22,
                                    values=["Máxima disponible"])
        self.qual_cb.pack(side="left")

        # Tarjeta: Carpeta de destino
        c_dir = make_card(root)
        c_dir.pack(fill="x", padx=28, pady=6)
        ttk.Label(c_dir, text="CARPETA DE DESTINO", style="CardMuted.TLabel").pack(anchor="w", pady=(0, 6))
        r_dir = tk.Frame(c_dir, bg=SURFACE)
        r_dir.pack(fill="x")
        self.dir_var = tk.StringVar(value=str(get_out_dir()))
        make_entry(r_dir, self.dir_var).pack(side="left", fill="x", expand=True, ipady=5)
        ttk.Button(r_dir, text="Cambiar…", style="Ghost.TButton", command=self.pick_dir).pack(side="left", padx=(6, 0))
        ttk.Button(r_dir, text="Abrir carpeta", style="Ghost.TButton",
                   command=self.open_dir).pack(side="left", padx=(6, 0))

        # Tarjeta: Descarga y progreso
        c_dl = make_card(root)
        c_dl.pack(fill="x", padx=28, pady=6)
        r_dl = tk.Frame(c_dl, bg=SURFACE)
        r_dl.pack(fill="x")
        self.dl_btn = ttk.Button(r_dl, text="Descargar", style="Primary.TButton", command=self.start_download)
        self.dl_btn.pack(side="left", fill="x", expand=True)
        self.pbar = ttk.Progressbar(c_dl, mode="determinate", maximum=100)
        self.pbar.pack(fill="x", pady=(12, 6))
        self.status_lbl = ttk.Label(c_dl, text="Listo.", style="CardMuted.TLabel")
        self.status_lbl.pack(anchor="w")

        # Pie: versión y actualizaciones
        foot = tk.Frame(root, bg=BG)
        foot.pack(fill="x", padx=28, pady=(6, 14))
        self.ver_lbl = ttk.Label(foot, text=f"v{APP_VERSION}", style="Muted.TLabel")
        self.ver_lbl.pack(side="left")
        self.upd_btn = ttk.Button(foot, text="Buscar actualizaciones", style="Ghost.TButton",
                                  command=lambda: threading.Thread(target=self.check_updates, daemon=True).start())
        self.upd_btn.pack(side="right")

        threading.Thread(target=self.check_updates, daemon=True).start()

    def ui(self, fn):
        self.root.after(0, fn)

    def paste_url(self):
        try:
            self.url_var.set(self.root.clipboard_get().strip())
        except Exception:
            pass

    def pick_dir(self):
        d = filedialog.askdirectory(initialdir=self.dir_var.get())
        if d:
            self.dir_var.set(d)
            save_settings(dir=d)

    def open_dir(self):
        p = Path(self.dir_var.get()).expanduser()
        p.mkdir(parents=True, exist_ok=True)
        if IS_WIN:
            os.startfile(p)
        elif IS_MAC:
            subprocess.Popen(["open", str(p)])
        else:
            subprocess.Popen(["xdg-open", str(p)])

    def update_qualities(self):
        if self.kind_var.get() == "mp3":
            vals = ["MP3 · 320 kbps (Mejor calidad)"]
        else:
            vals = ["Máxima disponible"] + [f"{h}p" for h in self.heights]
        self.qual_cb.config(values=vals)
        self.qual_var.set(vals[0])

    def analyze(self):
        url = self.url_var.get().strip()
        if not re.match(r"^https?://", url):
            messagebox.showwarning(APP_NAME, "Pega un enlace válido (http:// o https://)")
            return
        self.an_btn.state(["disabled"])
        self.status_lbl.config(text="Analizando enlace…")

        def work():
            try:
                p = subprocess.run(ytdlp_cmd() + ["-J", "--no-playlist", "--no-warnings", url],
                                   capture_output=True, text=True, encoding="utf-8", creationflags=NOWIN)
                if p.returncode != 0:
                    raise RuntimeError((p.stderr.strip().splitlines() or ["No se pudo leer el enlace"])[-1])
                d = json.loads(p.stdout)
                hs = sorted({f["height"] for f in d.get("formats", [])
                             if f.get("height") and f.get("vcodec") not in (None, "none")}, reverse=True)
                dur = d.get("duration")
                dur_s = f"{int(dur // 60)}:{int(dur % 60):02d}" if dur else ""
                sub = " · ".join(x for x in (d.get("extractor_key"), d.get("uploader"), dur_s) if x)
                thumb_data = None
                if d.get("thumbnail"):
                    try:
                        thumb_data = http_get(d["thumbnail"], binary=True)
                    except Exception:
                        pass

                def done():
                    self.heights = hs
                    self.title_lbl.config(text=d.get("title") or "Video detectado")
                    self.sub_lbl.config(text=sub)
                    self.update_qualities()
                    self.status_lbl.config(text="Enlace listo para descargar.")
                    if thumb_data:
                        try:
                            from PIL import Image, ImageTk
                            im = Image.open(io.BytesIO(thumb_data)).resize((120, 68))
                            self.thumb_img = ImageTk.PhotoImage(im)
                            self.thumb_lbl.config(image=self.thumb_img, text="", width=120, height=68)
                        except Exception:
                            pass
                self.ui(done)
            except Exception as e:
                self.ui(lambda: self.status_lbl.config(text=f"Error: {e}"))
            finally:
                self.ui(lambda: self.an_btn.state(["!disabled"]))

        threading.Thread(target=work, daemon=True).start()

    def start_download(self):
        url = self.url_var.get().strip()
        if not re.match(r"^https?://", url):
            messagebox.showwarning(APP_NAME, "Pega un enlace válido primero.")
            return
        out = Path(self.dir_var.get()).expanduser()
        out.mkdir(parents=True, exist_ok=True)
        save_settings(dir=str(out))
        kind = self.kind_var.get()
        q = self.qual_var.get()
        m = re.match(r"^(\d+)p$", q)
        height = int(m.group(1)) if m else None

        self.dl_btn.state(["disabled"])
        self.pbar["value"] = 0
        self.status_lbl.config(text="Iniciando descarga…")

        def work():
            cmd = ytdlp_cmd() + [
                "--no-playlist", "--newline", "--progress", "--no-warnings",
                "--progress-template", "download:PROG|%(progress._percent_str)s|%(progress._speed_str)s|%(progress._eta_str)s",
                "-o", str(out / "%(title).150B [%(id)s].%(ext)s"), "--windows-filenames"
            ]
            if kind == "mp3":
                cmd += ["-f", "ba/b", "-x", "--audio-format", "mp3", "--audio-quality", "0",
                        "--embed-thumbnail", "--add-metadata"]
            else:
                h = height or 99999
                cmd += ["-f", f"bv*[height<={h}]+ba/b[height<={h}]/b",
                        "-S", "res,ext:mp4:m4a,vcodec:h264", "--merge-output-format", "mp4"]
            cmd.append(url)
            try:
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        text=True, encoding="utf-8", errors="replace", creationflags=NOWIN)
                last = ""
                for line in proc.stdout:
                    line = line.strip()
                    if line.startswith("PROG|"):
                        _, pct, spd, eta = line.split("|")
                        pm = re.search(r"[\d.]+", pct)
                        val = float(pm.group()) if pm else 0
                        self.ui(lambda v=val, s=spd.strip(), t=eta.strip(): (
                            self.pbar.config(value=v),
                            self.status_lbl.config(text=f"Descargando {v:.1f}% · {s} · ETA {t}")
                        ))
                    elif line.startswith(("[Merger]", "[ExtractAudio]", "[VideoConvertor]")):
                        self.ui(lambda: self.status_lbl.config(text="Procesando con FFmpeg…"))
                    elif line:
                        last = line
                proc.wait()
                if proc.returncode != 0:
                    raise RuntimeError(last or "Falló la descarga")
                self.ui(lambda: (
                    self.pbar.config(value=100),
                    self.status_lbl.config(text=f"✓ Completado — guardado en {out}")
                ))
            except Exception as e:
                self.ui(lambda: self.status_lbl.config(text=f"Error: {e}"))
            finally:
                self.ui(lambda: self.dl_btn.state(["!disabled"]))

        threading.Thread(target=work, daemon=True).start()

    def check_updates(self):
        try:
            r = subprocess.run(ytdlp_cmd() + ["--version"], capture_output=True, text=True, creationflags=NOWIN)
            cur = r.stdout.strip()
            self.ui(lambda: self.ver_lbl.config(text=f"v{APP_VERSION} · yt-dlp {cur}"))
            latest = http_get("https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest")["tag_name"]
            if latest and latest != cur and read_settings().get("auto_update", True):
                self.ui(lambda: self.ver_lbl.config(text=f"Actualizando motor a {latest}…"))
                if not FROZEN and IS_WIN:
                    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "yt-dlp"],
                                   creationflags=NOWIN)
                else:
                    ENGINE.parent.mkdir(parents=True, exist_ok=True)
                    tmp = ENGINE.with_suffix(".new")
                    tmp.write_bytes(http_get(ENGINE_URL, binary=True))
                    if not IS_WIN:
                        tmp.chmod(0o755)
                    os.replace(tmp, ENGINE)
                self.ui(lambda: self.ver_lbl.config(text=f"v{APP_VERSION} · yt-dlp {latest} (actualizado)"))
        except Exception:
            pass


def main():
    if "--ytdlp" in sys.argv:
        import yt_dlp
        yt_dlp.main(sys.argv[sys.argv.index("--ytdlp") + 1:])
        return
    if "--uninstall" in sys.argv:
        uninstall_self()
        return

    root = tk.Tk()
    apply_theme(root)

    s = read_settings()
    need_wizard = ("--installer" in sys.argv) or (not s.get("terms_accepted"))
    if need_wizard:
        root.withdraw()

        def launch_main():
            root.deiconify()
            DownloaderApp(root)

        InstallerWizard(root, on_done=launch_main)
    else:
        DownloaderApp(root)

    root.mainloop()


if __name__ == "__main__":
    main()
