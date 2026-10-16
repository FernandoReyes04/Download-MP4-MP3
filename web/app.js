const $ = id => document.getElementById(id);
let kind = "mp4", height = null, jobId = null, info = null;

const post = async (path, body) => {
  const r = await fetch(path, { method: "POST", body: JSON.stringify(body) });
  const j = await r.json();
  if (!r.ok) throw new Error(j.error || "Error");
  return j;
};
const err = t => { $("msg").textContent = t; $("msg").classList.toggle("hide", !t); };
const fmt = s => s ? `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}` : "";

function renderOpts() {
  const o = $("opts"); o.innerHTML = "";
  if (kind === "mp3") {
    o.innerHTML = '<span class="chip on">MP3 · mejor calidad (VBR ~245 kbps)</span>';
    return;
  }
  const hs = [null, ...info.heights];
  height = null;
  hs.forEach((h, i) => {
    const c = document.createElement("span");
    c.className = "chip" + (i === 0 ? " on" : "");
    c.textContent = h ? `${h}p` : "⭐ Máxima calidad";
    c.onclick = () => { height = h; [...o.children].forEach(x => x.classList.remove("on")); c.classList.add("on"); };
    c.style.cursor = "pointer";
    o.appendChild(c);
  });
}

function setKind(k) {
  kind = k;
  $("tmp4").classList.toggle("on", k === "mp4");
  $("tmp3").classList.toggle("on", k === "mp3");
  renderOpts();
}
$("tmp4").onclick = () => setKind("mp4");
$("tmp3").onclick = () => setKind("mp3");

$("go").onclick = async () => {
  err(""); $("panel").classList.add("hide");
  $("go").disabled = true; $("go").textContent = "Analizando…";
  try {
    info = await post("/api/info", { url: $("url").value });
    $("thumb").src = info.thumbnail || "";
    $("title").textContent = info.title;
    $("info").textContent = [info.site, info.uploader, fmt(info.duration)].filter(Boolean).join(" · ");
    $("prog").classList.add("hide"); $("done").classList.add("hide");
    setKind("mp4");
    $("panel").classList.remove("hide");
  } catch (e) { err(e.message); }
  $("go").disabled = false; $("go").textContent = "Analizar";
};
$("url").addEventListener("keydown", e => e.key === "Enter" && $("go").click());

$("dl").onclick = async () => {
  err(""); $("dl").disabled = true;
  $("prog").classList.remove("hide"); $("done").classList.add("hide");
  $("fill").style.width = "0"; $("ptxt").textContent = "Iniciando…";
  try {
    jobId = (await post("/api/download", { url: $("url").value, kind, height })).id;
    const t = setInterval(async () => {
      const j = await (await fetch("/api/progress/" + jobId)).json();
      if (j.status === "error") { clearInterval(t); err(j.error); $("dl").disabled = false; return; }
      $("fill").style.width = j.percent + "%";
      $("ptxt").textContent = j.status === "done" ? "✅ Listo — guardado en Descargas/VIDEO-AUDIO"
        : `${j.stage} ${j.percent.toFixed(1)}% · ${j.speed} · ETA ${j.eta}`;
      if (j.status === "done") { clearInterval(t); $("done").classList.remove("hide"); $("dl").disabled = false; }
    }, 700);
  } catch (e) { err(e.message); $("dl").disabled = false; }
};
$("save").onclick = () => location.href = "/api/file/" + jobId;
$("folder").onclick = () => post("/api/open", { url: "http://x" });

setInterval(() => fetch('/api/ping').catch(() => {}), 5000);

// ---- Carpeta de destino ----
const dirMsg = t => { $("dirmsg").classList.remove("hide"); $("dirmsg").firstChild.textContent = t; };
const saveDir = async d => {
  try { $("dir").value = (await post("/api/settings", { dir: d })).dir; dirMsg("✅ Guardada: se usará en todas las descargas"); }
  catch (e) { dirMsg("⚠️ " + e.message); }
};
fetch("/api/settings").then(r => r.json()).then(j => $("dir").value = j.dir);
$("browse").onclick = async () => {
  const d = (await post("/api/browse", {})).dir;
  if (d) saveDir(d);
};
$("savedir").onclick = () => saveDir($("dir").value.trim());

// ---- Actualizaciones del motor de descarga ----
async function refreshUpd() {
  const u = await (await fetch("/api/update/status")).json();
  $("ver").textContent = u.current ? `Motor yt-dlp ${u.current}` : "";
  $("auto").checked = u.auto;
  const box = $("upd"), btn = $("updbtn");
  const show = (t, b) => { box.classList.remove("hide"); $("updtxt").textContent = t; btn.classList.toggle("hide", !b); };
  if (u.state === "available") show(`🔔 Nueva versión del motor: ${u.latest} (tienes ${u.current})`, true);
  else if (u.state === "updating") show("⏳ Actualizando motor de descargas…", false);
  else if (u.state === "updated") show("✅ " + u.message, false);
  else if (u.state === "error") show("⚠️ " + u.message, true);
  else if (u.state === "idle") show("🔎 Buscando actualizaciones…", false);
  else if (u.message) show("⚠️ " + u.message, false);
  else box.classList.add("hide");
}
$("updbtn").onclick = async () => {
  $("updbtn").disabled = true; $("updtxt").textContent = "⏳ Descargando actualización…";
  await post("/api/update/apply", {}); $("updbtn").disabled = false; refreshUpd();
};
$("auto").onchange = () => post("/api/update/auto", { on: $("auto").checked });
refreshUpd(); setInterval(refreshUpd, 4000);
