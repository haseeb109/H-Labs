/* H Labs Studio front end - plain JS, no build step. Talks to tools/studio/server.py (same origin). */
"use strict";
const S = { view: "queue", snap: null, styles: [], lib: null, sel: null, logFor: null, logText: [],
  nr: { text: "", probes: {}, style: "", mode: "all", minCase: "8", voice: true, watermark: true, cleanup: true } };
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const ICON = {
  play: '<svg aria-hidden="true" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>',
  folder: '<svg aria-hidden="true" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 7h6l2 2h10v10H3z"/></svg>',
};
const MODES = { "30": "30 min videos", "60": "1 hour videos", all: "One video per case", clips: "Clips + editor guide", asis: "As-is re-edit", download: "Download only" };
const STAGES = ["Download", "Transcript", "Plan", "Render", "Finish"];

async function api(path, body) {
  const r = await fetch(path, body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  return r.json();
}
function toast(msg) { const t = $("toast"); t.textContent = msg; t.classList.add("on"); clearTimeout(toast.t); toast.t = setTimeout(() => t.classList.remove("on"), 2400); }
async function copy(text) {
  try { await navigator.clipboard.writeText(text); }
  catch (e) { const a = document.createElement("textarea"); a.value = text; document.body.appendChild(a); a.select(); document.execCommand("copy"); a.remove(); }
  toast("Copied");
}
const hms = (s) => { s = Math.round(s || 0); const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60;
  return h ? `${h}h ${String(m).padStart(2, "0")}m` : `${m}:${String(x).padStart(2, "0")}`; };
const styleName = (id) => (S.styles.find((s) => s.id === id) || {}).name || id;
const isLink = (u) => /^https?:\/\//i.test(u);
const shortUrl = (u) => isLink(u) ? u.replace(/^https?:\/\/(www\.)?/, "").slice(0, 60) : (u.length > 60 ? "…" + u.slice(-59) : u);

/* ------------------------------------------------------------------ shell */
function route() {
  S.view = (location.hash || "#queue").slice(1) || "queue";
  document.querySelectorAll(".navlink").forEach((a) => a.classList.toggle("on", a.dataset.view === S.view));
  if (S.view === "library") loadLibrary(); else render();
}
window.addEventListener("hashchange", route);

function renderSide() {
  const sn = S.snap; if (!sn) return;
  const waiting = sn.jobs.filter((j) => j.status === "queued" || j.status === "running").length;
  const c = $("navcount"); c.hidden = !waiting; c.textContent = waiting;
  const m = sn.machine || {};
  $("machinebox").innerHTML = `<b>${esc(m.machine || "This PC")}</b>` + (m.checking ? "<span>checking...</span>" :
    `<span>Encode · ${esc(m.encoder === "libx264" ? "CPU (x264)" : (m.encoder || "?").replace("h264_", "").toUpperCase())}</span>
     <span>Decode · ${esc(m.decode === "CPU" ? "CPU" : "GPU (" + m.decode + ")")}</span>
     <span>${m.version ? "Version " + esc(m.version) : ""}</span>`);
}

function render() {
  renderSide();
  if (S.view === "new") return renderNew();
  if (S.view === "library") return renderLibrary();
  return renderQueue();
}

/* ------------------------------------------------------------------ queue */
function statusChip(j) {
  const map = { queued: ["", "Queued"], running: ["run", "Running"], done: ["ok", "Done"], partial: ["warn", `${(j.failed_videos || []).length || "Some"} video(s) failed`],
    failed: ["bad", "Failed"], stopped: ["", "Stopped"], nothing: ["warn", "Nothing to make"] };
  const [k, t] = map[j.status] || ["", j.status];
  return `<span class="chip ${k}">${esc(t)}</span>`;
}
function stepsHtml(j) {
  return `<ol class="steps">` + STAGES.map((name, i) => {
    const cur = j.stage_idx ?? 0;
    let cls = i < cur ? "done" : i === cur ? "now" : "todo", sub = i < cur ? "Done" : i === cur ? "" : "Waiting";
    let bar = i < cur ? "" : i === cur && j.pct != null ? `<i style="width:${Math.min(100, j.pct)}%"></i>` : i === cur ? `<i style="width:8%"></i>` : "";
    let label = name;
    if (i === 3 && j.videos_total) label = `Render · ${j.mode === "clips" ? "clip" : "video"} ${Math.max(1, j.video_now || 1)} of ${j.videos_total}${j.videos_resumed ? ` (${j.videos_resumed} reused from the stopped run)` : ""}`;
    if (i === cur) sub = (j.pct != null ? Math.round(j.pct) + "%" : "Working") + (j.eta ? ` · ~${esc(j.eta)} left` : "");
    return `<li class="${cls}"><div class="bar">${bar}</div><span style="font-weight:500">${esc(label)}</span><span class="small muted">${sub}</span></li>`;
  }).join("") + `</ol>`;
}
function runningCard(j) {
  const log = (j.log || []).slice(-6);
  return `<article class="card">
    <div style="display:flex;flex-wrap:wrap;gap:12px;align-items:flex-start">
      <div style="display:flex;flex-direction:column;gap:4px;min-width:0">
        <span class="eyebrow">RUNNING NOW</span>
        <h2 style="font-size:17px">${esc(j.title || shortUrl(j.url))}</h2>
        <span class="muted" style="font-size:13px">${j.stream_len ? hms(j.stream_len) + " stream · " : ""}${esc(styleName(j.style))} · ${esc(MODES[j.mode] || j.mode)}${j.note ? " · " + esc(j.note) : ""}</span>
      </div>
      <div class="spacer actions">
        <button class="btn" onclick="togglePause()">${S.snap.paused ? "Resume queue" : "Pause after this stream"}</button>
        <button class="btn" onclick="openLog('${j.id}')">Full log</button>
        <button class="btn danger" onclick="stopRun()">Stop</button>
      </div>
    </div>
    ${stepsHtml(j)}
    <div class="logbox">${log.map((l, i) => `<div class="${i === log.length - 1 ? "last" : ""}">${esc(l)}</div>`).join("") || "Starting..."}</div>
  </article>`;
}
function jobRow(j) {
  const sub = j.status === "failed" || j.status === "partial" || j.status === "nothing" ? `<div class="rowsub bad">${esc(j.error || "")}</div>`
    : `<div class="rowsub">${j.stream_len ? hms(j.stream_len) + " · " : ""}${esc(shortUrl(j.url))}${j.ended ? " · " + esc(j.ended.slice(5, 16)) : ""}</div>`;
  let act = "";
  if (j.status === "queued") act = `<button class="btn sm" aria-label="Move up" onclick="jobAct('${j.id}','up')">Up</button><button class="btn sm" aria-label="Move down" onclick="jobAct('${j.id}','down')">Down</button><button class="btn sm" onclick="jobAct('${j.id}','remove')">Remove</button>`;
  else if (j.status !== "running") {
    if (["failed", "partial", "stopped", "nothing"].includes(j.status))
      act += `<button class="btn sm accent" onclick="jobAct('${j.id}','retry')">${j.status === "partial" ? "Retry failed video" + ((j.failed_videos || []).length > 1 ? "s" : "") : "Retry"}</button>`;
    if (j.out_dir) act += `<button class="btn sm" onclick="openOut('${esc(j.out_dir.split(/[\\/]/).pop())}')">${ICON.folder}Open</button>`;
    if (j.events) act += `<button class="btn sm" title="${esc(j.events)}" onclick="openLog('${j.id}', true)">Events</button>`;
    act += `<button class="btn sm" onclick="openLog('${j.id}')">Full log</button><button class="btn sm" onclick="jobAct('${j.id}','remove')">Clear</button>`;
  }
  return `<tr class="${j.status === "failed" || j.status === "partial" ? "failed" : ""}">
    <td><div class="rowtitle">${esc(j.title || shortUrl(j.url))}</div>${sub}</td>
    <td>${esc(styleName(j.style))}</td><td>${esc(MODES[j.mode] || j.mode)}</td><td>${statusChip(j)}</td>
    <td><span class="actions">${act}</span></td></tr>`;
}
function renderQueue() {
  const sn = S.snap; const v = $("view");
  if (!sn) { v.innerHTML = `<div class="empty">Loading...</div>`; return; }
  const run = sn.jobs.find((j) => j.status === "running");
  const waiting = sn.jobs.filter((j) => j.status === "queued");
  const finished = sn.jobs.filter((j) => !["queued", "running"].includes(j.status)).slice(-12).reverse();
  const st = sn.stats || {}, m = sn.machine || {};
  const bad = sn.jobs.filter((j) => j.status === "failed" || j.status === "partial").length;
  const free = m.free_gb || 0;
  v.innerHTML = `
  <header class="top"><h1>Queue</h1>${sn.paused ? '<span class="chip warn">Paused</span>' : ""}
    <div class="spacer actions">${sn.paused ? '<button class="btn" onclick="togglePause()">Resume queue</button>' : ""}
    <a class="btn primary" href="#new">${ICON.play}New run</a></div></header>
  <div class="content">
    <section class="col-main">
      <div class="kpis">
        <div class="kpi"><span>Streams today</span><b>${st.streams_today ?? 0}</b></div>
        <div class="kpi"><span>Videos made today</span><b>${st.videos_today ?? 0}</b></div>
        <div class="kpi"><span>Avg. time per stream</span><b>${st.avg_min != null ? st.avg_min + " min" : "–"}</b></div>
        <div class="kpi"><span>Brain cost today</span><b>$${(st.cost_today || 0).toFixed(2)}</b></div>
      </div>
      ${run ? runningCard(run) : sn.paused && waiting.length ? `<div class="banner">Queue is paused - ${waiting.length} stream(s) waiting. <button class="btn sm" onclick="togglePause()">Resume</button></div>`
        : `<article class="card"><span class="eyebrow">IDLE</span><span class="muted">Nothing is running. Add stream links in <a href="#new">New run</a> - they are processed one after the other.</span></article>`}
      <article class="card flush">
        <div class="cardhead"><h2>Up next</h2><span class="muted" style="font-size:13px">${waiting.length} stream(s) · run one after the other</span></div>
        ${waiting.length ? `<div class="tablewrap"><table><thead><tr><th>Stream</th><th>Template</th><th>Output</th><th>Status</th><th>Action</th></tr></thead><tbody>${waiting.map(jobRow).join("")}</tbody></table></div>`
          : `<div class="empty">The queue is empty.</div>`}
      </article>
      ${finished.length ? `<article class="card flush"><div class="cardhead"><h2>Finished</h2><span class="muted" style="font-size:13px">latest first</span></div>
        <div class="tablewrap"><table><thead><tr><th>Stream</th><th>Template</th><th>Output</th><th>Status</th><th>Action</th></tr></thead><tbody>${finished.map(jobRow).join("")}</tbody></table></div></article>` : ""}
      ${S.logFor ? `<article class="card"><div style="display:flex;align-items:center;gap:8px"><h2>${S.logEv ? "Events" : "Log"}</h2><button class="btn sm spacer" onclick="closeLog()">Close</button></div>
        <div class="logbox" style="max-height:420px;overflow:auto">${S.logText.map(esc).join("\n")}</div></article>` : ""}
    </section>
    <aside class="col-side">
      <section class="card"><h2>This machine</h2>
        ${m.checking ? '<span class="muted">Checking...</span>' : `
        <div class="kv"><span>Video encode</span><span class="${m.encoder === "libx264" ? "" : "good"}">${m.encoder === "libx264" ? "CPU (slower)" : "GPU · " + esc((m.encoder || "").replace("h264_", "").toUpperCase())}</span></div>
        <div class="kv"><span>Video decode</span><span class="${m.decode === "CPU" ? "" : "good"}">${m.decode === "CPU" ? "CPU" : "GPU · " + esc((m.decode || "").toUpperCase())}</span></div>
        <div class="kv"><span>Download quality</span><span class="good">${m.min_height || 720}p minimum</span></div>
        <div class="kv"><span>Hive key</span><span class="${m.keys && m.keys.hive ? "good" : "badtext"}">${m.keys && m.keys.hive ? "Set" : "Missing"}</span></div>
        <div class="kv"><span>ai33 key</span><span class="${m.keys && m.keys.ai33 ? "good" : "badtext"}">${m.keys && m.keys.ai33 ? "Set" : "Missing"}</span></div>
        <div class="kv"><span>Free disk</span><span class="${free < 20 ? "badtext" : ""}">${free} GB</span></div>`}
      </section>
      <section class="card"><h2>Needs attention</h2>
        ${bad ? `<div class="attn"><span class="dot" style="background:var(--bad)"></span><div><b>${bad} stream(s) with a failure</b><div class="small muted">Retry from the Finished list - the download is kept.</div></div></div>` : ""}
        ${!m.checking && m.keys && (!m.keys.hive || !m.keys.ai33) ? `<div class="attn"><span class="dot" style="background:var(--bad)"></span><div><b>API key missing</b><div class="small muted">H Labs.bat → option 4.</div></div></div>` : ""}
        ${free && free < 20 ? `<div class="attn"><span class="dot" style="background:var(--warn)"></span><div><b>Disk almost full</b><div class="small muted">Delete uploaded videos from the output folder.</div></div></div>` : ""}
        ${m.smoke && m.smoke.fails ? `<div class="attn"><span class="dot" style="background:var(--bad)"></span><div><b>Smoke test: ${m.smoke.fails} problem(s) on this PC</b><div class="small muted">${esc(m.smoke.first_fail)} (${esc(m.smoke.date)}) — H Labs.bat → option 6, or option u to undo the last update.</div></div></div>` : ""}
        <div class="attn"><span class="dot" style="background:var(--ok)"></span><div><b>Finished videos</b><div class="small"><a href="#library">Open the library</a></div></div></div>
      </section>
    </aside>
  </div>`;
}
async function jobAct(id, act) { await api(`/api/jobs/${id}/${act}`, {}); await refresh(); }
async function stopRun() { if (!confirm("Stop the running stream now? The queue pauses; press Resume to go on.")) return; await api("/api/stop", {}); await refresh(); }
async function togglePause() { await api("/api/pause", { paused: !S.snap.paused }); await refresh(); }
async function openLog(id, events) { S.logFor = id; S.logEv = !!events; S.logText = (await api(`/api/log?id=${id}${events ? "&events=1" : ""}`)).log || []; render(); }
function closeLog() { S.logFor = null; render(); }
async function openOut(run) { await api("/api/open", { rel: run }); toast("Opening the folder"); }

/* ------------------------------------------------------------------ new run */
const PREVIEW = {
  trial_tales: ["#16161A", '<i style="left:10px;top:10px;width:46px;height:7px;background:#E2761B"></i><i style="left:10px;right:10px;top:24px;height:34px;background:#3B3D45"></i><i style="left:10px;bottom:9px;width:70px;height:6px;background:#F4F4F4"></i>'],
  overruled: ["#1B2A44", '<i style="left:10px;top:12px;width:62px;height:46px;background:#4A5C7C"></i><i style="right:10px;top:12px;width:44px;height:46px;background:#F3EEE3"></i><i style="left:10px;bottom:9px;width:96px;height:6px;background:#B4232C"></i>'],
  court_beacon: ["#050608", '<i style="left:0;right:0;top:0;height:9px;background:#121722"></i><i style="left:10px;right:10px;top:16px;height:44px;background:#2E3440"></i><i style="right:10px;bottom:8px;width:22px;height:12px;background:#5B8DEF"></i><i style="right:36px;bottom:8px;width:22px;height:12px;background:#5B8DEF"></i>'],
  justice_served: ["#121417", '<i style="left:8px;top:8px;width:92px;height:10px;background:#1C2026;border-left:3px solid #FFB000"></i><i style="left:8px;top:24px;width:64px;height:38px;background:#343A44"></i><i style="right:8px;top:24px;width:34px;height:38px;background:#1C2026"></i><i style="left:8px;bottom:6px;width:54px;height:8px;background:#FFB000"></i>'],
};
// one item per line: a YouTube link, or the path of your own video file / folder (D:\Streams\x.mp4, \\server\share, /home/...)
const urlsOf = (t) => [...new Set(t.split(/\r?\n/).map((l) => l.trim().replace(/^["']|["']$/g, "")).flatMap((l) =>
  isLink(l) || !/https?:\/\//i.test(l) ? [isLink(l) ? l.split(/\s+/)[0].replace(/[,;]+$/, "") : l] : (l.match(/https?:\/\/\S+/g) || []))
  .filter((l) => isLink(l) || /^([A-Za-z]:[\\/]|\\\\|\/)/.test(l)))];
function probeRow(u) {
  const p = S.nr.probes[u];
  if (!p) return `<div class="probe"><span class="t">${esc(shortUrl(u))}</span><span class="chip">Not checked</span></div>`;
  if (p.pending) return `<div class="probe"><span class="t">${esc(shortUrl(u))}</span><span class="chip run">Checking...</span></div>`;
  if (!p.ok) return `<div class="probe skip"><span class="t">${esc(shortUrl(u))}</span><span class="chip bad">${esc(p.error || "Could not read")}</span></div>`;
  const low = p.height && p.height < (p.min_height || 720);
  if (p.local) return `<div class="probe"><span class="t" title="${esc(p.video)}">${esc(p.title)}</span><span class="muted small">${hms(p.duration)}</span>
    <span class="chip ${p.transcript ? "ok" : ""}" title="${esc(p.transcript)}">${p.transcript ? "Transcript found" : "No transcript · whisper"}</span>
    <span class="chip ${low ? "warn" : "ok"}">Your file · ${p.height}p</span></div>`;
  return `<div class="probe ${p.live || low ? "skip" : ""}"><span class="t" title="${esc(p.title)}">${esc(p.title)}</span><span class="muted small">${p.live ? "Still live" : hms(p.duration)}</span>
    ${p.live ? '<span class="chip bad">Still live · skipped</span>' : low ? `<span class="chip bad">Only ${p.height}p · skipped</span>` : `<span class="chip ok">${p.height}p${p.kbps ? " · " + (p.kbps / 1000).toFixed(1) + " Mbps" : ""}</span>`}</div>`;
}
function usableUrls() {
  return urlsOf(S.nr.text).filter((u) => { const p = S.nr.probes[u];
    if (!isLink(u)) return !!(p && p.ok);                 // your own file: it must be found first (Check)
    return !p || p.pending || (p.ok && !p.live && !(p.height && p.height < (p.min_height || 720))); });
}
function renderNew() {
  const nr = S.nr; if (!nr.style && S.styles.length) nr.style = S.styles[0].id;
  const urls = urlsOf(nr.text), use = usableUrls(), st = (S.snap && S.snap.stats) || {}, m = (S.snap && S.snap.machine) || {};
  const secs = use.reduce((a, u) => a + ((S.nr.probes[u] || {}).duration || 0), 0);
  const known = use.every((u) => (S.nr.probes[u] || {}).ok);
  const estMin = secs / 60 * (st.min_per_stream_min || 0.5), cost = secs / 60 * (st.usd_per_stream_min || 0.0005);
  $("view").innerHTML = `
  <header class="top"><a href="#queue" class="muted" style="text-decoration:none">Queue</a><span class="muted">/</span><h1>New run</h1></header>
  <div class="content">
    <form class="col-main" onsubmit="return false">
      <section class="card">
        <div class="step"><b>STEP 1</b><h2>Stream links</h2></div>
        <label style="display:flex;flex-direction:column;gap:6px"><span class="muted" style="font-size:13px">One per line: YouTube links, or the path of your own downloaded video / folder (with its transcript if you have one - the download is skipped). Each line becomes one job; they run one after the other.</span>
          <textarea class="links" id="links" placeholder="https://www.youtube.com/live/...&#10;D:\Streams\Smith hearing">${esc(nr.text)}</textarea></label>
        <div class="actions" style="justify-content:flex-start"><button type="button" class="btn" onclick="checkLinks()" ${urls.length ? "" : "disabled"}>Check ${urls.length || ""} link${urls.length === 1 ? "" : "s"}</button>
          <span class="muted small">Checks title, length, quality (${m.min_height || 720}p minimum), whether a stream is still live, and finds the video + transcript in your folder.</span></div>
        ${urls.length ? `<div class="probes">${urls.map(probeRow).join("")}</div>` : ""}
      </section>
      <section class="card">
        <div class="step"><b>STEP 2</b><h2>Channel template</h2></div>
        <div class="templates">${S.styles.map((s) => { const pv = PREVIEW[s.id] || ["#2A2E36", ""];
          return `<button type="button" class="tpl" aria-pressed="${nr.style === s.id}" onclick="pickStyle('${esc(s.id)}')"><div class="pv" style="background:${pv[0]}">${pv[1]}</div>
            <div class="nm"><b>${esc(s.name)}</b><span>${nr.style === s.id ? "Selected" : esc(s.id)}</span></div></button>`; }).join("")}</div>
      </section>
      <section class="card">
        <div class="step"><b>STEP 3</b><h2>Output</h2></div>
        <div class="seg" role="radiogroup" aria-label="Output">${Object.entries(MODES).map(([k, t]) =>
          `<button type="button" role="radio" aria-checked="${nr.mode === k}" onclick="pickMode('${k}')">${esc(t)}</button>`).join("")}</div>
        <span class="muted small">${nr.mode === "clips" ? `Hook + whole case, dead air cut, no overlays / voice / watermark, plus EDITOR_GUIDE.txt for your editor (in this channel's name). Every case of ${nr.minCase}:00 or more.`
          : nr.mode === "all" ? `Every verified case of ${nr.minCase}:00 or more becomes its own fully edited video, ranked.`
          : nr.mode === "download" ? "Only downloads each link as a best-quality MP4 into output/downloads (no transcript, brain, voice or editing; the template is ignored). A video that only exists below 720p is downloaded as it is."
          : nr.mode === "asis" ? "The WHOLE video becomes ONE fully edited video, as it is: no case selection, nothing skipped or cut out - one case or several. For a single video link or your own file."
          : "Several cases joined into one fully edited video."}</span>
        ${nr.mode === "all" || nr.mode === "clips" ? `<div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap"><span style="font-weight:500">Shortest case</span>
          <div class="seg" role="radiogroup" aria-label="Shortest case">${["8", "5"].map((k) =>
            `<button type="button" role="radio" aria-checked="${nr.minCase === k}" onclick="S.nr.minCase='${k}';renderNew()">${k} minutes</button>`).join("")}</div></div>` : ""}
        <label class="check"><input type="checkbox" ${nr.voice && nr.mode !== "clips" ? "checked" : ""} ${nr.mode === "clips" ? "disabled" : ""} onchange="S.nr.voice=this.checked"><span>Allow AI voice-over above 5,000 characters</span></label>
        <label class="check"><input type="checkbox" ${nr.watermark ? "checked" : ""} ${nr.mode === "clips" ? "disabled" : ""} onchange="S.nr.watermark=this.checked"><span>Channel watermark</span></label>
        <label class="check"><input type="checkbox" ${nr.cleanup ? "checked" : ""} onchange="S.nr.cleanup=this.checked"><span>Delete the downloaded stream when its videos are done</span></label>
      </section>
    </form>
    <aside class="col-side"><section class="card">
      <h2>Run summary</h2>
      <div class="kv"><span>Streams</span><span style="font-weight:500">${use.length} to add${urls.length - use.length ? ` · ${urls.length - use.length} skipped` : ""}</span></div>
      <div class="kv"><span>Template</span><span style="font-weight:500">${esc(styleName(nr.style))}</span></div>
      <div class="kv"><span>Output</span><span style="font-weight:500">${esc(MODES[nr.mode])}${nr.mode === "all" || nr.mode === "clips" ? " · " + nr.minCase + ":00+" : ""}</span></div>
      <div style="height:1px;background:var(--line2)"></div>
      <span class="small muted" style="font-weight:600">ESTIMATE ON THIS PC${known ? "" : " (check the links for one)"}</span>
      <div class="kv"><span>Time</span><span class="mono">${secs ? "≈ " + hms(estMin * 60) : "–"}</span></div>
      <div class="kv"><span>Brain</span><span class="mono">${secs ? "≈ $" + cost.toFixed(2) : "–"}</span></div>
      <div class="kv"><span>Disk needed</span><span class="mono">${secs ? "≈ " + Math.max(1, Math.round(secs / 3600 * 1.5)) + " GB of " + (m.free_gb || "?") + " GB" : "–"}</span></div>
      <button type="button" class="btn primary lg" onclick="addJobs()" ${use.length ? "" : "disabled"}>Add ${use.length} stream${use.length === 1 ? "" : "s"} to the queue</button>
      ${urls.some((u) => !isLink(u) && !(S.nr.probes[u] || {}).ok) ? '<span class="small" style="color:var(--warn-ink)">Press Check for your own files first.</span>' : ""}
      <span class="small muted">They start one after the other as soon as the PC is free. You can close this tab; keep the Studio window open.</span>
    </section></aside>
  </div>`;
  const ta = $("links"); ta.addEventListener("input", () => { S.nr.text = ta.value; clearTimeout(renderNew.t); renderNew.t = setTimeout(() => { const pos = ta.selectionStart; renderNew(); const t2 = $("links"); t2.focus(); t2.setSelectionRange(pos, pos); }, 500); });
}
function pickStyle(id) { S.nr.style = id; renderNew(); }
function pickMode(k) { S.nr.mode = k; renderNew(); }
async function checkLinks() {
  const urls = urlsOf(S.nr.text);
  urls.forEach((u) => { if (!S.nr.probes[u] || !S.nr.probes[u].ok) S.nr.probes[u] = { pending: true }; });
  renderNew();
  await Promise.all(urls.map(async (u) => { if (S.nr.probes[u].pending) { S.nr.probes[u] = await api("/api/probe", { url: u }); if (S.view === "new") renderNew(); } }));
}
async function addJobs() {
  const urls = usableUrls(); if (!urls.length) return;
  const nr = S.nr;
  const r = await api("/api/jobs", { urls, style: nr.style, mode: nr.mode, options: { voice: nr.voice, watermark: nr.watermark, cleanup: nr.cleanup, min_case: nr.minCase } });
  toast(`${(r.added || []).length} stream(s) added to the queue`);
  S.nr.text = ""; S.nr.probes = {};
  location.hash = "#queue"; await refresh();
}

/* ------------------------------------------------------------------ library */
async function loadLibrary() { $("view").innerHTML = `<header class="top"><h1>Library</h1></header><div class="empty">Loading...</div>`; S.lib = await api("/api/library"); renderLibrary(); }
let LIBF = { tab: "ready", style: "" };
function vMatches(v, run) {
  if (LIBF.style && run.style !== LIBF.style) return false;
  const up = v.upload && v.upload.uploaded;
  if (LIBF.tab === "ready") return !up && v.kind === "video";
  if (LIBF.tab === "uploaded") return !!up;
  if (LIBF.tab === "clips") return v.kind === "clip";
  return LIBF.tab === "all";
}
function renderLibrary() {
  renderSide();
  const runs = S.lib || [];
  const all = runs.flatMap((r) => r.videos.map((v) => ({ v, r })));
  const n = { ready: all.filter(({ v }) => !(v.upload && v.upload.uploaded) && v.kind === "video").length, uploaded: all.filter(({ v }) => v.upload && v.upload.uploaded).length,
    clips: all.filter(({ v }) => v.kind === "clip").length, review: runs.reduce((a, r) => a + r.review.length, 0), all: all.length };
  const styles = [...new Set(runs.map((r) => r.style).filter(Boolean))];
  const tab = (k, t) => `<button type="button" role="tab" class="btn sm" aria-selected="${LIBF.tab === k}" style="${LIBF.tab === k ? "background:#0F1115;color:#fff;border-color:#0F1115" : ""}" onclick="LIBF.tab='${k}';renderLibrary()">${t} · ${n[k]}</button>`;
  const sel = S.sel && all.find(({ v }) => v.rel === S.sel);
  const body = LIBF.tab === "review"
    ? runs.filter((r) => r.review.length).map((r) => `<div class="runhead"><h2>${esc(r.run)}</h2><span class="muted small">${esc(r.style)}</span></div>
        <div class="lib-grid">${r.review.map((c) => `<article class="vcard" style="cursor:default;border-style:dashed"><div class="vbody"><b>${esc(c.name)} · ${esc(c.in)}-${esc(c.out)}</b><span class="small muted">${esc(c.why || "set aside by the brain")}</span></div></article>`).join("")}</div>`).join("")
    : runs.map((r) => { const vs = r.videos.filter((v) => vMatches(v, r)); if (!vs.length) return "";
        return `<div class="runhead"><h2>${esc(r.run)}</h2><span class="muted small">${esc(r.style || "")}${r.mode ? " · " + esc(MODES[r.mode] || r.mode) : ""} · ${esc(r.time)}</span>
          <button class="btn sm" onclick="openOut('${esc(r.run)}')">${ICON.folder}Folder</button></div>
          <div class="lib-grid">${vs.map((v) => `<button type="button" class="vcard" aria-pressed="${S.sel === v.rel}" onclick="pickVideo('${esc(v.rel)}')">
            <div class="thumb">${v.thumb ? `<img alt="" src="/files/${encodeURI(v.thumb)}" loading="lazy">` : ""}${v.rank ? `<span class="rank">#${v.rank}</span>` : ""}<span class="len">${hms(v.length)}</span></div>
            <div class="vbody"><b>${esc(v.title)}</b><span>${v.qc_ok ? '<span class="chip ok">QC OK</span>' : `<span class="chip warn" title="${esc(v.qc_note)}">QC check</span>`}
              ${v.upload && v.upload.uploaded ? '<span class="chip">Uploaded</span>' : ""}${v.kind === "clip" ? '<span class="chip">Clip</span>' : ""}</span></div></button>`).join("")}</div>`; }).join("");
  $("view").innerHTML = `
  <header class="top"><h1>Library</h1>
    <div role="tablist" aria-label="Filter" class="actions" style="justify-content:flex-start;margin-left:12px">${tab("ready", "Ready to upload")}${tab("uploaded", "Uploaded")}${tab("review", "Needs review")}${tab("clips", "Clips")}${tab("all", "All")}</div>
    <label class="spacer muted" style="display:flex;align-items:center;gap:8px">Template <select onchange="LIBF.style=this.value;renderLibrary()" style="height:34px;border:1px solid #D6D9DF;border-radius:7px;padding:0 8px;background:#fff">
      <option value="">All templates</option>${styles.map((s) => `<option ${LIBF.style === s ? "selected" : ""}>${esc(s)}</option>`).join("")}</select></label>
    <button class="btn" onclick="loadLibrary()">Refresh</button></header>
  <div class="content">
    <section class="col-main">${body || `<div class="card empty">Nothing here yet.</div>`}</section>
    <aside class="col-side">${sel ? kitHtml(sel.v) : `<section class="card"><h2>Upload kit</h2><span class="muted">Pick a video to copy its titles and description and tick off the upload.</span></section>`}</aside>
  </div>`;
  if (sel) loadMeta(sel.v);
}
function kitHtml(v) {
  const up = v.upload || {};
  const box = (k, t) => `<label class="check"><input type="checkbox" ${up[k] ? "checked" : ""} onchange="saveCheck('${esc(v.rel)}','${k}',this.checked)">${t}</label>`;
  return `<section class="card"><div style="display:flex;align-items:center;gap:8px"><h2>${v.rank ? "#" + v.rank + " · " : ""}Upload kit</h2><span class="spacer small muted mono">${hms(v.length)}</span></div>
    ${v.titles.length ? `<div style="display:flex;flex-direction:column;gap:8px"><span class="small muted" style="font-weight:600">TITLES · upload with the first, swap at 48 h if CTR is under 5%</span>
      ${v.titles.map((t, i) => `<div class="titlebox ${i === 0 ? "primary" : ""}"><span>${esc(t)}</span><button class="btn sm" aria-label="Copy title ${i + 1}" onclick='copy(${JSON.stringify(t).replace(/'/g, "&#39;")})'>Copy</button></div>`).join("")}</div>` : ""}
    ${v.thumb_text ? `<div class="kv"><span>Thumbnail text</span><span style="font-weight:600">${esc(v.thumb_text)}</span></div>` : ""}
    <div style="display:flex;flex-direction:column;gap:8px"><span class="small muted" style="font-weight:600">${v.kind === "clip" ? "EDITOR GUIDE" : "DESCRIPTION, CHAPTERS, TAGS"}</span>
      <div class="textdump" id="metatext">Loading...</div>
      <button class="btn" onclick="copy(document.getElementById('metatext').textContent)">Copy all</button></div>
    <fieldset><legend>UPLOAD CHECKLIST</legend>${box("uploaded", "Video uploaded")}${box("thumbnail", "Thumbnail set")}${box("description", "Description + chapters pasted")}${box("pinned", "Pinned comment posted")}</fieldset>
    <div class="actions" style="justify-content:flex-start"><button class="btn primary" onclick="markUploaded('${esc(v.rel)}')">Mark as uploaded</button>
      <button class="btn" onclick="openOut('${esc(v.rel)}')">${ICON.folder}Open folder</button></div></section>`;
}
function pickVideo(rel) { S.sel = rel; renderLibrary(); }
async function loadMeta(v) {
  const r = await api(`/api/text?rel=${encodeURIComponent(v.rel + "/" + v.meta_file)}`);
  const el = $("metatext"); if (el) el.textContent = r.text || "(no file)";
}
function findVideo(rel) { for (const r of S.lib || []) for (const v of r.videos) if (v.rel === rel) return v; return null; }
async function saveCheck(rel, k, val) { const v = findVideo(rel); v.upload = Object.assign({}, v.upload, { [k]: val }); await api("/api/upload", { rel, checks: v.upload }); }
async function markUploaded(rel) { const v = findVideo(rel); v.upload = { uploaded: true, thumbnail: true, description: true, pinned: true }; await api("/api/upload", { rel, checks: v.upload }); toast("Marked as uploaded"); renderLibrary(); }

/* ------------------------------------------------------------------ polling */
async function refresh() {
  try { S.snap = await api("/api/state"); } catch (e) { return; }
  if (S.logFor) { try { S.logText = (await api(`/api/log?id=${S.logFor}${S.logEv ? "&events=1" : ""}`)).log || []; } catch (e) { /* keep */ } }
  if (S.view === "queue") render(); else renderSide();
}
(async function start() {
  S.styles = await api("/api/styles").catch(() => []);
  await refresh(); route();
  setInterval(refresh, 2000);
})();
