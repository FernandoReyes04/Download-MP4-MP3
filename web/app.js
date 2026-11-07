const $ = id => document.getElementById(id);
let kind = "mp4", height = null, jobId = null, info = null;

const post = async (path, body) => {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {})
  });
  const j = await r.json();
  if (!r.ok) throw new Error(j.error || "Error");
  return j;
};

const err = t => {
  const m = $("msg");
  m.textContent = t;
  m.classList.toggle("hide", !t);
};

const fmt = s => {
  if (!s) return "";
  const m = Math.floor(s / 60);
  const sec = String(Math.floor(s % 60)).padStart(2, "0");
  return `${m}:${sec}`;
};

// ---- Control Segmentado (MP4 / MP3) con Slider ----
function setKind(k) {
  kind = k;
  $("segmented").setAttribute("data-mode", k);
  $("tmp4").classList.toggle("active", k === "mp4");
  $("tmp3").classList.toggle("active", k === "mp3");
  $("dl").textContent = k === "mp4" ? "Descargar Video MP4" : "Descargar Audio MP3 (320 kbps)";
  renderOpts();
}

$("tmp4").onclick = () => setKind("mp4");
$("tmp3").onclick = () => setKind("mp3");

// ---- Opciones de Calidad ----
function renderOpts() {
  const o = $("opts");
  o.innerHTML = "";
  if (kind === "mp3") {
    o.innerHTML = '<span class="chip on">🎵 MP3 · Mejor Calidad (VBR ~320 kbps)</span>';
    return;
  }
  const hs = [null, ...((info && info.heights) || [])];
  height = null;
  hs.forEach((h, i) => {
    const c = document.createElement("span");
    c.className = "chip" + (i === 0 ? " on" : "");
    c.textContent = h ? `${h}p` : "⭐ Máxima calidad";
    c.onclick = () => {
      height = h;
      [...o.children].forEach(x => x.classList.remove("on"));
      c.classList.add("on");
    };
    o.appendChild(c);
  });
}

// ---- Botón Pegar desde portapapeles ----
$("pasteBtn").onclick = async () => {
  try {
    const txt = await navigator.clipboard.readText();
    if (txt) {
      $("url").value = txt.trim();
      $("go").click();
    }
  } catch (e) {
    $("url").focus();
  }
};

// ---- Analizar Enlace ----
$("go").onclick = async () => {
  err("");
  const url = $("url").value.trim();
  if (!url) {
    err("Pega un enlace antes de analizar.");
    return;
  }
  $("panel").classList.add("hide");
  $("go").disabled = true;
  $("go").textContent = "Analizando…";

  try {
    info = await post("/api/info", { url });
    $("thumb").src = info.thumbnail || "";
    $("title").textContent = info.title || "Video detectado";
    $("siteBadge").textContent = info.site || "Video";
    $("uploaderBadge").textContent = info.uploader || "";
    $("durationBadge").textContent = fmt(info.duration) || "";

    $("prog").classList.add("hide");
    $("done").classList.add("hide");
    setKind("mp4");
    $("panel").classList.remove("hide");
    $("panel").scrollIntoView({ behavior: "smooth", block: "nearest" });
  } catch (e) {
    err(e.message);
  } finally {
    $("go").disabled = false;
    $("go").textContent = "Analizar";
  }
};

$("url").addEventListener("keydown", e => {
  if (e.key === "Enter") $("go").click();
});

// ---- Descargar ----
$("dl").onclick = async () => {
  err("");
  $("dl").disabled = true;
  $("prog").classList.remove("hide");
  $("done").classList.add("hide");
  $("fill").style.width = "0%";
  $("ptxt").textContent = "Iniciando descarga…";
  $("peta").textContent = "";

  try {
    jobId = (await post("/api/download", { url: $("url").value.trim(), kind, height })).id;
    const timer = setInterval(async () => {
      try {
        const j = await (await fetch("/api/progress/" + jobId)).json();
        if (j.status === "error") {
          clearInterval(timer);
          err(j.error);
          $("dl").disabled = false;
          return;
        }
        $("fill").style.width = j.percent + "%";
        $("ptxt").textContent = j.status === "done"
          ? "✓ Descarga completada"
          : `${j.stage || "Descargando"} · ${j.speed || ""}`;
        $("peta").textContent = j.status === "done" ? "" : (j.eta ? `ETA ${j.eta}` : `${j.percent.toFixed(0)}%`);

        if (j.status === "done") {
          clearInterval(timer);
          $("done").classList.remove("hide");
          $("dl").disabled = false;
        }
      } catch (ex) {
        clearInterval(timer);
        $("dl").disabled = false;
      }
    }, 600);
  } catch (e) {
    err(e.message);
    $("dl").disabled = false;
  }
};

$("save").onclick = () => location.href = "/api/file/" + jobId;
$("folder").onclick = () => post("/api/open");
$("openFolderBtn").onclick = () => post("/api/open");

// ---- Carpeta de destino ----
const setDestDir = d => {
  $("dir").value = d;
  $("wizardDir").value = d;
};

fetch("/api/settings").then(r => r.json()).then(j => {
  if (j.dir) setDestDir(j.dir);
});

const handleBrowse = async () => {
  const d = (await post("/api/browse")).dir;
  if (d) {
    const res = await post("/api/settings", { dir: d });
    setDestDir(res.dir);
    const m = $("dirmsg");
    m.classList.remove("hide");
    setTimeout(() => m.classList.add("hide"), 2500);
  }
};

$("browse").onclick = handleBrowse;
$("wizardBrowseBtn").onclick = async () => {
  const d = (await post("/api/browse")).dir;
  if (d) setDestDir(d);
};

// ---- Actualizaciones del motor yt-dlp ----
async function refreshUpd() {
  try {
    const u = await (await fetch("/api/update/status")).json();
    if (u.current) $("engineVer").textContent = `yt-dlp ${u.current}`;
    $("auto").checked = !!u.auto;

    const box = $("upd"), btn = $("updbtn");
    const show = (t, b) => {
      box.classList.remove("hide");
      $("updtxt").textContent = t;
      btn.classList.toggle("hide", !b);
    };

    if (u.state === "available") show(`🔔 Nueva versión del motor: ${u.latest} (actual: ${u.current})`, true);
    else if (u.state === "updating") show("⏳ Actualizando motor de descargas…", false);
    else if (u.state === "updated") show("✓ " + u.message, false);
    else if (u.state === "error") show("⚠️ " + u.message, true);
    else box.classList.add("hide");
  } catch (e) {}
}

$("updbtn").onclick = async () => {
  $("updbtn").disabled = true;
  $("updtxt").textContent = "⏳ Descargando actualización…";
  await post("/api/update/apply");
  $("updbtn").disabled = false;
  refreshUpd();
};

$("auto").onchange = () => post("/api/update/auto", { on: $("auto").checked });

// ---- Actualización del programa (.exe / .pkg) ----
async function refreshApp() {
  try {
    const a = await (await fetch("/api/app/status")).json();
    const box = $("appupd"), btn = $("appupdbtn");
    const show = (t, b) => {
      box.classList.remove("hide");
      $("appupdtxt").textContent = t;
      btn.classList.toggle("hide", !b);
    };

    if (a.state === "available") show(`🚀 Nueva versión de la app: v${a.latest} (tienes v${a.current})`, true);
    else if (a.state === "updating") show("⏳ Descargando nueva versión; la app se reiniciará…", false);
    else if (a.state === "error") show("⚠️ " + a.message, true);
    else box.classList.add("hide");
  } catch (e) {}
}

$("appupdbtn").onclick = async () => {
  $("appupdbtn").disabled = true;
  $("appupdtxt").textContent = "⏳ Descargando actualización…";
  try { await post("/api/app/apply"); } catch (e) {}
  $("appupdbtn").disabled = false;
  refreshApp();
};

// ---- Modal: Asistente de Instalación / Términos y Condiciones ----
const modal = $("modalOverlay");
const openWizard = () => {
  modal.classList.remove("hide");
  $("wizardStep1").classList.remove("hide");
  $("wizardStep2").classList.add("hide");
};
const closeWizard = () => {
  modal.classList.add("hide");
};

$("openTermsLink").onclick = openWizard;

$("termsCheck").onchange = () => {
  $("termsNextBtn").disabled = !$("termsCheck").checked;
};

$("termsNextBtn").onclick = () => {
  $("wizardStep1").classList.add("hide");
  $("wizardStep2").classList.remove("hide");
};

$("wizardBackBtn").onclick = () => {
  $("wizardStep2").classList.add("hide");
  $("wizardStep1").classList.remove("hide");
};

$("wizardFinishBtn").onclick = async () => {
  $("wizardFinishBtn").disabled = true;
  $("wizardFinishBtn").textContent = "Configurando…";
  try {
    await post("/api/install", {
      desktop: $("optDesktop").checked,
      startmenu: $("optStartMenu").checked,
      autoupdate: $("optAutoUpd").checked,
      dir: $("wizardDir").value
    });
    setDestDir($("wizardDir").value);
    closeWizard();
  } catch (e) {
    alert("Error al instalar: " + e.message);
  } finally {
    $("wizardFinishBtn").disabled = false;
    $("wizardFinishBtn").textContent = "Instalar y Comenzar";
  }
};

// Verificar estado de Términos al inicio
fetch("/api/terms_status").then(r => r.json()).then(s => {
  if (s.dir) setDestDir(s.dir);
  if (!s.accepted) openWizard();
}).catch(() => {});

// Refracción especular dinámica en tarjetas Liquid Glass al mover el cursor
document.querySelectorAll(".glass-panel").forEach(card => {
  card.addEventListener("mousemove", e => {
    const r = card.getBoundingClientRect();
    card.style.setProperty("--mx", `${e.clientX - r.left}px`);
    card.style.setProperty("--my", `${e.clientY - r.top}px`);
  });
});

refreshUpd();
setInterval(refreshUpd, 6000);
refreshApp();
setInterval(refreshApp, 8000);
setInterval(() => fetch("/api/ping").catch(() => {}), 5000);
