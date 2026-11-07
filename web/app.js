const $ = id => document.getElementById(id);
let kind = "mp4", height = null, jobId = null, info = null, toastTimer = null;
let audioFormat = "mp3", dspEffect = "none", videoProfile = "original", srtSegments = [];

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

// Sonido cristalino suave al terminar descarga (Web Audio API sin archivos externos)
function playSuccessChime() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    [587.33, 880].forEach((freq, i) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0.001, ctx.currentTime + i * 0.11);
      gain.gain.exponentialRampToValueAtTime(0.12, ctx.currentTime + i * 0.11 + 0.03);
      gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + i * 0.11 + 0.45);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(ctx.currentTime + i * 0.11);
      osc.stop(ctx.currentTime + i * 0.11 + 0.46);
    });
  } catch (e) {}
}

function showCompletionToast(filename) {
  const t = $("toast");
  $("toastTitle").textContent = "✓ ¡Descarga completada!";
  $("toastSub").textContent = filename
    ? `${filename} · Mostrando en tu carpeta`
    : "Abriendo carpeta con tu archivo seleccionado…";
  t.classList.remove("hide");
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.add("hide"), 6500);
  playSuccessChime();
}

// ---- Control Segmentado (Video / Audio Puro) con Slider ----
function updateDlBtnLabel() {
  const hasStudio = isStudioActive();
  const suffix = hasStudio ? " · 🎛️ Estudio" : "";
  if (kind === "mp4") {
    if (videoProfile === "gif") $("dl").textContent = "Descargar GIF Animado HD" + suffix;
    else if (videoProfile === "edit") $("dl").textContent = "Descargar Video MP4 (Premiere / DaVinci)" + suffix;
    else if (videoProfile === "social") $("dl").textContent = "Descargar Video MP4 (WhatsApp / Discord)" + suffix;
    else $("dl").textContent = "Descargar Video MP4" + suffix;
  } else {
    const labels = {
      mp3: "Descargar Audio MP3 (320 kbps)",
      m4a: "Descargar Audio M4A (Original Puro)",
      flac: "Descargar Audio FLAC (Lossless)",
      wav: "Descargar Audio WAV (PCM Estudio)"
    };
    $("dl").textContent = (labels[audioFormat] || labels.mp3) + suffix;
  }
}

function isStudioActive() {
  return Boolean(
    $("trimStart").value.trim() ||
    $("trimEnd").value.trim() ||
    $("normVolCheck").checked ||
    dspEffect !== "none" ||
    videoProfile !== "original" ||
    $("squareCoverCheck").checked ||
    $("embedSubsCheck").checked
  );
}

function updateStudioBadge() {
  const active = isStudioActive();
  const btn = $("openStudioBtn");
  btn.classList.toggle("active", active);
  btn.textContent = active ? "✂️🎛️ Estudio ●" : "✂️🎛️ Recortar y Estudio";
  updateDlBtnLabel();
}

function setKind(k) {
  kind = k;
  $("segmented").setAttribute("data-mode", k);
  $("tmp4").classList.toggle("active", k === "mp4");
  $("tmp3").classList.toggle("active", k === "mp3");
  renderOpts();
  updateDlBtnLabel();
}

$("tmp4").onclick = () => setKind("mp4");
$("tmp3").onclick = () => setKind("mp3");

// ---- Opciones de Calidad y Formatos de Sonido Puro ----
function renderOpts() {
  const o = $("opts");
  o.innerHTML = "";
  if (kind === "mp3") {
    const audioFormats = [
      { id: "m4a", label: "⭐ M4A Original (Puro)" },
      { id: "flac", label: "💎 FLAC (Lossless)" },
      { id: "wav", label: "🎛️ WAV (PCM Estudio)" },
      { id: "mp3", label: "🎵 MP3 (320 kbps)" }
    ];
    audioFormats.forEach(af => {
      const c = document.createElement("span");
      c.className = "chip" + (audioFormat === af.id ? " on" : "");
      c.textContent = af.label;
      c.onclick = () => {
        audioFormat = af.id;
        [...o.children].forEach(x => x.classList.remove("on"));
        c.classList.add("on");
        updateDlBtnLabel();
      };
      o.appendChild(c);
    });
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

// ---- Analizar Enlace (con Esqueleto de Carga y compactación adaptativa) ----
$("go").onclick = async () => {
  err("");
  const url = $("url").value.trim();
  if (!url) {
    err("Pega un enlace antes de analizar.");
    return;
  }
  $("panel").classList.add("hide");
  $("skeleton").classList.remove("hide");
  document.body.classList.add("has-content");

  $("go").disabled = true;
  $("go").innerHTML = '<span class="btn-spinner"></span> Analizando…';

  try {
    info = await post("/api/info", { url });
    $("thumb").src = info.thumbnail || "";
    $("title").textContent = info.title || "Video detectado";
    $("siteBadge").textContent = info.site || "Video";
    $("noWmBadge").classList.toggle("hide", !info.no_watermark);
    $("uploaderBadge").textContent = info.uploader || "";
    $("durationBadge").textContent = fmt(info.duration) || "";

    // Rellenar metadatos limpios y capítulos en el Estudio
    $("metaTitle").value = info.clean_title || info.title || "";
    $("metaArtist").value = info.clean_artist || info.uploader || "";
    $("trimStart").value = "";
    $("trimEnd").value = "";
    const chSel = $("chapterSelect");
    chSel.innerHTML = '<option value="">📑 Seleccionar capítulo del video (Opcional)…</option>';
    const chs = info.chapters || [];
    if (chs.length > 0) {
      chs.forEach((ch, idx) => {
        const opt = document.createElement("option");
        opt.value = idx;
        opt.textContent = `${fmt(ch.start)} - ${fmt(ch.end)} · ${ch.title}`;
        chSel.appendChild(opt);
      });
      chSel.classList.remove("hide");
      $("chapterCountBadge").textContent = `📑 ${chs.length} capítulos`;
      $("chapterCountBadge").classList.remove("hide");
    } else {
      chSel.classList.add("hide");
      $("chapterCountBadge").classList.add("hide");
    }

    // Poblar selector de idiomas de subtítulos si hay disponibles
    const sSel = $("subLangSelect");
    const langs = info.sub_langs && info.sub_langs.length ? info.sub_langs : ["es", "en"];
    sSel.innerHTML = "";
    langs.forEach(l => {
      const opt = document.createElement("option");
      opt.value = l;
      opt.textContent = l === "es" ? "Español (es)" : (l === "en" ? "Inglés (en)" : `Idioma (${l})`);
      sSel.appendChild(opt);
    });
    srtSegments = [];
    $("transcriptEditor").value = "";
    $("srtList").innerHTML = "";

    $("prog").classList.add("hide");
    $("done").classList.add("hide");
    $("fill").classList.remove("done-fill");
    updateStudioBadge();
    setKind("mp4");

    $("skeleton").classList.add("hide");
    $("panel").classList.remove("hide");
  } catch (e) {
    $("skeleton").classList.add("hide");
    document.body.classList.remove("has-content");
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
  $("fill").classList.remove("done-fill");
  $("fill").style.width = "0%";
  $("ptxt").textContent = "Iniciando descarga…";
  $("peta").textContent = "";

  try {
    const opts = {
      audioFormat,
      trimStart: $("trimStart").value.trim(),
      trimEnd: $("trimEnd").value.trim(),
      normVol: $("normVolCheck").checked,
      dspEffect,
      videoProfile,
      metaTitle: $("metaTitle").value.trim(),
      metaArtist: $("metaArtist").value.trim(),
      squareCover: $("squareCoverCheck").checked,
      embedSubs: $("embedSubsCheck").checked,
      customSrt: $("embedSubsCheck").checked ? buildSrtString() : "",
      subLang: $("subLangSelect").value || "es",
      thumbnail: (info && info.thumbnail) || ""
    };
    jobId = (await post("/api/download", { url: $("url").value.trim(), kind, height, opts })).id;
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
          ? "✓ Descarga finalizada · Carpeta abierta con el archivo seleccionado"
          : `${j.stage || "Descargando"} · ${j.speed || ""}`;
        $("peta").textContent = j.status === "done" ? "100%" : (j.eta ? `ETA ${j.eta}` : `${j.percent.toFixed(0)}%`);

        if (j.status === "done") {
          clearInterval(timer);
          $("fill").classList.add("done-fill");
          $("done").classList.remove("hide");
          $("dl").disabled = false;
          showCompletionToast(j.filename);
        }
      } catch (ex) {
        clearInterval(timer);
        $("dl").disabled = false;
      }
    }, 550);
  } catch (e) {
    err(e.message);
    $("dl").disabled = false;
  }
};

$("save").onclick = () => location.href = "/api/file/" + jobId;
$("folder").onclick = async () => {
  const btn = $("folder");
  const orig = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = "📂 Abriendo Explorador…";
  try {
    await post("/api/open", { jobId, reveal: true });
  } catch (e) {
    err(e.message);
  } finally {
    setTimeout(() => {
      btn.disabled = false;
      btn.innerHTML = orig;
    }, 600);
  }
};
$("openFolderBtn").onclick = async () => {
  const btn = $("openFolderBtn");
  const orig = btn.textContent;
  btn.disabled = true;
  btn.textContent = "Abriendo…";
  try {
    await post("/api/open", { jobId, reveal: Boolean(jobId) });
  } catch (e) {
    err(e.message);
  } finally {
    setTimeout(() => {
      btn.disabled = false;
      btn.textContent = orig;
    }, 600);
  }
};

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

// ---- Descarga de Portada HD y Portada 1:1 ----
async function handleCoverDownload(square = false) {
  const btn = square ? $("saveSquareCoverBtn") : $("coverBtn");
  const orig = btn.textContent;
  btn.disabled = true;
  btn.textContent = "⏳ Guardando…";
  try {
    const res = await post("/api/cover", {
      url: $("url").value.trim(),
      title: $("metaTitle").value.trim() || (info && (info.clean_title || info.title)) || "Portada",
      thumbnail: (info && info.thumbnail) || "",
      square
    });
    showCompletionToast(res.filename);
  } catch (e) {
    err(e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = orig;
  }
}

$("coverBtn").onclick = () => handleCoverDownload(false);
$("coverToolbarBtn").onclick = () => handleCoverDownload(false);
$("saveSquareCoverBtn").onclick = () => handleCoverDownload(true);

$("embedSubsCheck").onchange = () => {
  $("embedSubsFromModalCheck").checked = $("embedSubsCheck").checked;
  updateStudioBadge();
};
$("embedSubsFromModalCheck").onchange = () => {
  $("embedSubsCheck").checked = $("embedSubsFromModalCheck").checked;
  updateStudioBadge();
};

// ---- Modal: Estudio de Edición (Video & Audio) ----
const studioModal = $("studioModal");
$("openStudioBtn").onclick = () => studioModal.classList.remove("hide");
$("closeStudioBtn").onclick = () => {
  updateStudioBadge();
  studioModal.classList.add("hide");
};
$("applyStudioBtn").onclick = () => {
  updateStudioBadge();
  studioModal.classList.add("hide");
};

$("chapterSelect").onchange = () => {
  const idx = $("chapterSelect").value;
  if (idx === "" || !info || !info.chapters || !info.chapters[idx]) return;
  const ch = info.chapters[idx];
  $("trimStart").value = fmt(ch.start) || "0:00";
  $("trimEnd").value = fmt(ch.end) || "";
  if (ch.title) $("metaTitle").value = ch.title;
  updateStudioBadge();
};

document.querySelectorAll("#dspChips .chip").forEach(c => {
  c.onclick = () => {
    dspEffect = c.getAttribute("data-dsp") || "none";
    document.querySelectorAll("#dspChips .chip").forEach(x => x.classList.remove("on"));
    c.classList.add("on");
    updateStudioBadge();
  };
});

document.querySelectorAll("#vprofChips .chip").forEach(c => {
  c.onclick = () => {
    videoProfile = c.getAttribute("data-vprof") || "original";
    document.querySelectorAll("#vprofChips .chip").forEach(x => x.classList.remove("on"));
    c.classList.add("on");
    updateStudioBadge();
  };
});

$("resetStudioBtn").onclick = () => {
  $("trimStart").value = "";
  $("trimEnd").value = "";
  $("chapterSelect").value = "";
  $("normVolCheck").checked = false;
  $("squareCoverCheck").checked = false;
  $("embedSubsCheck").checked = false;
  $("embedSubsFromModalCheck").checked = false;
  dspEffect = "none";
  videoProfile = "original";
  document.querySelectorAll("#dspChips .chip").forEach((x, i) => x.classList.toggle("on", i === 0));
  document.querySelectorAll("#vprofChips .chip").forEach((x, i) => x.classList.toggle("on", i === 0));
  if (info) {
    $("metaTitle").value = info.clean_title || info.title || "";
    $("metaArtist").value = info.clean_artist || info.uploader || "";
  }
  updateStudioBadge();
};

// ---- Modal: Estudio de Subtítulos (.SRT) y Transcripción Editable (.TXT) ----
const subsModal = $("subsModal");

function updateWordCount() {
  const txt = $("transcriptEditor").value.trim();
  const count = txt ? txt.split(/\s+/).length : 0;
  $("wordCountTxt").textContent = `${count} palabras`;
}

$("transcriptEditor").addEventListener("input", updateWordCount);

function renderSrtBlocks() {
  const list = $("srtList");
  list.innerHTML = "";
  srtSegments.forEach((seg, idx) => {
    const row = document.createElement("div");
    row.className = "srt-row";
    const tSpan = document.createElement("span");
    tSpan.className = "srt-time";
    tSpan.textContent = `${seg.start.split(",")[0]} → ${seg.end.split(",")[0]}`;
    const inp = document.createElement("input");
    inp.type = "text";
    inp.className = "srt-input";
    inp.value = seg.text;
    inp.oninput = () => {
      srtSegments[idx].text = inp.value;
      $("transcriptEditor").value = srtSegments.map(s => s.text.trim()).filter(Boolean).join(" ");
      updateWordCount();
    };
    row.appendChild(tSpan);
    row.appendChild(inp);
    list.appendChild(row);
  });
}

function buildSrtString() {
  if (!srtSegments.length) {
    const txt = $("transcriptEditor").value.trim();
    return txt ? `1\n00:00:00,000 --> 00:00:10,000\n${txt}\n` : "";
  }
  return srtSegments
    .map((s, i) => `${i + 1}\n${s.start} --> ${s.end}\n${(s.text || "").trim()}\n`)
    .join("\n");
}

function setSubsView(mode) {
  const isTxt = mode === "txt";
  $("subsViewSeg").setAttribute("data-mode", isTxt ? "mp4" : "mp3");
  $("viewTxtBtn").classList.toggle("active", isTxt);
  $("viewSrtBtn").classList.toggle("active", !isTxt);
  $("txtViewWrap").classList.toggle("hide", !isTxt);
  $("srtViewWrap").classList.toggle("hide", isTxt);
}

$("viewTxtBtn").onclick = () => setSubsView("txt");
$("viewSrtBtn").onclick = () => setSubsView("srt");

async function loadSubtitles() {
  const url = $("url").value.trim();
  if (!url) return;
  $("subsLoading").classList.remove("hide");
  $("txtViewWrap").classList.add("hide");
  $("srtViewWrap").classList.add("hide");
  $("fetchSubsBtn").disabled = true;
  try {
    const res = await post("/api/subtitles", { url, lang: $("subLangSelect").value });
    srtSegments = res.segments || [];
    $("transcriptEditor").value = res.full_text || "";
    updateWordCount();
    renderSrtBlocks();
    $("subsStatusTxt").textContent = `✓ Idioma: ${res.lang} (${res.is_auto ? "Transcripción automática depurada" : "Subtítulos oficiales"}) · ${srtSegments.length} bloques`;
  } catch (e) {
    $("subsStatusTxt").textContent = "⚠️ " + e.message;
  } finally {
    $("subsLoading").classList.add("hide");
    $("fetchSubsBtn").disabled = false;
    setSubsView($("viewTxtBtn").classList.contains("active") ? "txt" : "srt");
  }
}

$("openSubsBtn").onclick = () => {
  subsModal.classList.remove("hide");
  if (!srtSegments.length && !$("transcriptEditor").value.trim()) {
    loadSubtitles();
  }
};
$("closeSubsBtn").onclick = () => subsModal.classList.add("hide");
$("fetchSubsBtn").onclick = loadSubtitles;

$("copyTranscriptBtn").onclick = async () => {
  const btn = $("copyTranscriptBtn");
  const orig = btn.textContent;
  try {
    await navigator.clipboard.writeText($("transcriptEditor").value);
    btn.textContent = "✓ ¡Copiado!";
  } catch (e) {}
  setTimeout(() => (btn.textContent = orig), 1500);
};

async function saveTranscriptOrSrt(fmtType) {
  const btn = fmtType === "srt" ? $("saveSrtBtn") : $("saveTxtBtn");
  const orig = btn.textContent;
  btn.disabled = true;
  btn.textContent = "⏳ Guardando…";
  try {
    const content = fmtType === "srt" ? buildSrtString() : $("transcriptEditor").value;
    const res = await post("/api/subtitles/save", {
      title: $("metaTitle").value.trim() || (info && (info.clean_title || info.title)) || "Transcripcion",
      format: fmtType,
      content
    });
    showCompletionToast(res.filename);
  } catch (e) {
    alert(e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = orig;
  }
}

$("saveTxtBtn").onclick = () => saveTranscriptOrSrt("txt");
$("saveSrtBtn").onclick = () => saveTranscriptOrSrt("srt");

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
