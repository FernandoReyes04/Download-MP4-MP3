# 🎬 Download MP4 / MP3

Programa de escritorio para Windows que descarga **videos (MP4)** y **audio (MP3)** de YouTube, Instagram y cientos de sitios más, en la **máxima calidad disponible**. Todo corre **localmente** en tu PC: sin páginas dudosas, sin anuncios y sin enviar tus enlaces a terceros.

Funciona con [yt-dlp](https://github.com/yt-dlp/yt-dlp) y [FFmpeg](https://ffmpeg.org/).

## ✨ Características

- Pega un enlace y elige entre **MP4** (máxima calidad o una resolución concreta) o **MP3** (mejor calidad).
- Barra de progreso con velocidad y tiempo restante.
- **Carpeta de destino configurable** (se recuerda entre sesiones).
- **Aviso y auto-actualización** del motor de descargas (yt-dlp), para que siga funcionando cuando los sitios cambian.
- **Se instala solo**: crea acceso directo en el Escritorio y el Menú Inicio, y se puede desinstalar desde *Configuración → Aplicaciones*.
- Un único `.exe` con FFmpeg incluido; no requiere instalar Python.

## 🚀 Uso rápido (ejecutable)

1. Compila el programa (ver abajo) o descarga el `.exe` si está publicado en *Releases*.
2. Ejecuta `VideoAudioDownloader.exe`. La primera vez se instala y abre una ventana de aplicación.
3. Pega el enlace, pulsa **Analizar**, elige formato y **Descargar**.

Por defecto guarda en `Descargas\VIDEO-AUDIO`; cámbialo con el cuadro **Carpeta de destino**.

## 🛠️ Desarrollo y compilación

Requisitos: Windows, Python 3.10+, [FFmpeg](https://ffmpeg.org/) en el `PATH` y Microsoft Edge o Chrome (para la ventana de la app).

```bat
:: Ejecutar sin compilar
INICIAR.bat

:: Generar el .exe (dist\VideoAudioDownloader.exe)
COMPILAR.bat
```

`COMPILAR.bat` usa PyInstaller, empaqueta FFmpeg y aplica el icono `descargar.ico`.

## 📁 Estructura

| Archivo | Descripción |
|---|---|
| `server.py` | Backend local (descargas, ajustes, actualizaciones, instalación) |
| `web/` | Interfaz (HTML, CSS y JS) |
| `INICIAR.bat` | Ejecuta la app desde el código fuente |
| `COMPILAR.bat` | Genera el ejecutable |
| `descargar.ico` | Icono del programa |

## ⚠️ Aviso legal

Usa esta herramienta solo para contenido propio, de dominio público o que tengas permiso de descargar. Respeta los términos de servicio de cada plataforma y los derechos de autor.
