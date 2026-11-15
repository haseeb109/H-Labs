"""H Labs Studio - the local web GUI (double-click "H Labs Studio.bat"; opens http://127.0.0.1:8765 in the browser).

A thin layer over run_stream.py - the pipeline is exactly the one the terminal menu runs:
* Queue    paste 4-5 (or 50) stream links -> they run ONE AFTER ANOTHER; live stage / percent / ETA, log tail, stop,
           pause after the current stream, retry only the videos that failed (--only), queue survives a restart
           (state/studio_queue.json).
* New run  each link is checked first (title, length, best quality - 720p rule, still live?), template + output + options.
* Library  finished videos per run: thumbnail, titles to copy, metadata / editor guide, upload checklist, open folder.
Only standard-library Python; listens on 127.0.0.1 only (nothing is reachable from other PCs).
"""
import csv
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
STATIC = Path(__file__).resolve().parent / "static"
STATE = ROOT / "state"
QFILE = STATE / "studio_queue.json"
OUT = ROOT / "output"
WIN = os.name == "nt"
STAGES = ["Download", "Transcript", "Plan", "Render", "Finish"]
KEY_FILES = {"hive.env": "HIVE_API_KEY", "ai33.env": "AI33_API_KEY"}


def stage_index(name):
    n = (name or "").lower()
    if n.startswith(("info", "download")):
        return 0
    if n.startswith("transcript"):
        return 1
    if n.startswith(("scan", "brain")):
        return 2
    if n.startswith(("render", "video", "clip")):
        return 3
    if n.startswith("report"):
        return 4
    return None


def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


class Studio:
    """The queue: one worker thread runs one job at a time (run_stream.py in a child process) and reads its output."""

    def __init__(self, command=None, autostart=True):
        self.lock = threading.RLock()
        self.jobs = []
        self.paused = False
        self.proc = None
        self.current = None
        self.command = command or self._command
        self._probe_cache = {}
        self.machine = {"checking": True}
        self._load()
        if autostart:
            threading.Thread(target=self._worker, daemon=True).start()
            threading.Thread(target=self._check_machine, daemon=True).start()

    # ------------------------------------------------------------------ persistence
    def _load(self):
        try:
            data = json.loads(QFILE.read_text(encoding="utf-8"))
            self.jobs = data.get("jobs", [])
            self.paused = bool(data.get("paused"))
        except (OSError, ValueError):
            self.jobs = []
        for j in self.jobs:                                    # a run that was going when the window closed starts again
            if j.get("status") == "running":
                j["status"] = "queued"
                j["note"] = "restarted after Studio was closed"

    def save(self):
        with self.lock:
            STATE.mkdir(exist_ok=True)
            tmp = QFILE.with_suffix(".tmp")
            keep = [dict(j, log=j.get("log", [])[-120:]) for j in self.jobs[-200:]]
            tmp.write_text(json.dumps({"jobs": keep, "paused": self.paused}, indent=1), encoding="utf-8")
            os.replace(tmp, QFILE)

    # ------------------------------------------------------------------ queue actions
    def add(self, urls, style, mode, options):
        made = []
        with self.lock:
            for u in urls:
                j = {"id": uuid.uuid4().hex[:10], "url": u, "style": style, "mode": mode, "options": dict(options or {}),
                     "status": "queued", "added": _now(), "title": "", "stream_len": 0, "stage": "", "stage_idx": None,
                     "videos_total": 0, "video_now": 0, "pct": None, "eta": "", "log": [], "error": "",
                     "failed_videos": [], "only": [], "out_dir": "", "note": ""}
                p = self._probe_cache.get(u)
                if p and p.get("ok"):
                    j["title"], j["stream_len"] = p.get("title", ""), p.get("duration", 0)
                self.jobs.append(j)
                made.append(j["id"])
        self.save()
        return made

    def _job(self, jid):
        return next((j for j in self.jobs if j["id"] == jid), None)

    def remove(self, jid):
        with self.lock:
            j = self._job(jid)
            if j and j["status"] != "running":
                self.jobs.remove(j)
        self.save()

    def move(self, jid, delta):
        with self.lock:
            j = self._job(jid)
            if not j or j["status"] != "queued":
                return
            i = self.jobs.index(j)
            k = max(0, min(len(self.jobs) - 1, i + delta))
            self.jobs.insert(k, self.jobs.pop(i))
        self.save()

    def retry(self, jid):
        with self.lock:
            j = self._job(jid)
            if not j or j["status"] == "running":
                return
            j["only"] = list(j.get("failed_videos") or []) if j["status"] == "partial" else []
            j.update(status="queued", error="", note="retry" + (f" of video {', '.join(map(str, j['only']))}" if j["only"] else ""),
                     stage="", stage_idx=None, pct=None, eta="", failed_videos=[])
            self.jobs.remove(j)                                 # a retry goes to the front of the waiting jobs
            first = next((i for i, x in enumerate(self.jobs) if x["status"] == "queued"), len(self.jobs))
            self.jobs.insert(first, j)
        self.save()

    def stop(self):
        with self.lock:
            p, j = self.proc, self.current
            self.paused = True
            if j:
                j["note"] = "stopped by you"
        if p and p.poll() is None:
            try:
                if WIN:
                    subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
                else:
                    os.killpg(os.getpgid(p.pid), signal.SIGTERM)
            except Exception:
                p.kill()
        self.save()

    def set_paused(self, value):
        with self.lock:
            self.paused = bool(value)
        self.save()

    # ------------------------------------------------------------------ running one job
    def _command(self, j):
        o = j.get("options") or {}
        brain = "hive"
        try:
            b = (ROOT / ".brain").read_text(encoding="utf-8").strip()
            brain = b if b in ("hive", "manual") else "hive"
        except OSError:
            pass
        cmd = [sys.executable, str(ROOT / "run_stream.py"), j["url"], "--brain", brain, "--style", j["style"],
               "--mode", j["mode"], "--queued"]
        if o.get("voice", True) and j["mode"] != "clips":
            cmd.append("--confirm-tts")
        if not o.get("watermark", True):
            cmd.append("--no-watermark")
        if not o.get("cleanup", True):
            cmd.append("--keep-source")
        if j.get("only"):
            cmd += ["--only", ",".join(map(str, j["only"]))]
        return cmd

    def _line(self, j, line):
        """Read one output line of run_stream into the job's live state."""
        s = line.rstrip()
        if not s:
            return
        if s.startswith("@@stage "):
            name = s[8:].strip()
            j["stage"], j["pct"], j["eta"] = name, None, ""
            i = stage_index(name)
            if i is not None:
                j["stage_idx"] = i
            m = re.match(r"(?:video|clip) (\d+)", name)
            if m:
                j["video_now"] = int(m.group(1))
            return
        if s.startswith("@@videos "):
            try:
                j["videos_total"] = int(s.split()[1])
            except (IndexError, ValueError):
                pass
            return
        j["log"].append(s[:400])
        if len(j["log"]) > 300:
            del j["log"][:100]
        m = re.search(r"stream: (.*)  \((\d+:\d+(?::\d+)?), id (\S+)\)", s)
        if m:
            j["title"] = m.group(1).strip()
            parts = [int(x) for x in m.group(2).split(":")]
            j["stream_len"] = sum(v * 60 ** (len(parts) - 1 - k) for k, v in enumerate(parts))
        m = re.search(r"\[download\]\s+(\d+(?:\.\d+)?)% of", s)
        if m:
            j["pct"] = float(m.group(1))
            mm = re.search(r"ETA (\d+:\d+(?::\d+)?)", s)
            j["eta"] = mm.group(1) if mm else j["eta"]
        m = re.search(r":\s+(\d{1,3})%\s+\S+ of \S+\s+speed", s)
        if m:
            j["pct"] = float(m.group(1))
            mm = re.search(r"~(\S+) left", s)
            j["eta"] = mm.group(1) if mm else ""
        m = re.search(r"ALL DONE -> (.+)$", s)
        if m:
            j["out_dir"] = m.group(1).strip()
        m = re.search(r"VIDEO (\d+) FAILED: (.*?)(?: - going on|$)", s) or re.search(r"CLIP (\d+) FAILED: (.*?)(?: - going|$)", s)
        if m:
            n = int(m.group(1))
            if n not in j["failed_videos"]:
                j["failed_videos"].append(n)
            j["error"] = m.group(2)[:300]
        if s.startswith(("STOP:", "ERROR", "mode-all plan failed", "BRAIN STOPPED", "DISK FULL", "RuntimeError", "urllib.error",
                         "Plan has errors", "NOTHING TO MAKE")):
            j["error"] = s[:300]

    def _run(self, j):
        env = dict(os.environ, HL_STUDIO="1", PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
        kw = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)} if WIN else {"start_new_session": True}
        with self.lock:
            j.update(status="running", started=_now(), ended="", stage="Starting", stage_idx=0, pct=None, eta="",
                     log=[], error="", failed_videos=[], out_dir="", videos_total=0, video_now=0)
            self.current = j
        self.save()
        try:
            p = subprocess.Popen(self.command(j), cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, encoding="utf-8", errors="replace", bufsize=1, **kw)
        except Exception as e:
            with self.lock:
                j.update(status="failed", error=f"could not start: {e}", ended=_now())
                self.current = None
            self.save()
            return
        with self.lock:
            self.proc = p
        n = 0
        for line in p.stdout:
            with self.lock:
                self._line(j, line)
            n += 1
            if n % 25 == 0:
                self.save()
        rc = p.wait()
        with self.lock:
            nothing = any(x.startswith("NOTHING TO MAKE") for x in j["log"][-40:])
            if j.get("note") == "stopped by you":
                j["status"] = "stopped"
            elif nothing:
                j["status"] = "nothing"
                j["error"] = "No case of 8:00+ in this stream - try the 30 min / 1 hour mode."
            elif rc == 0 and not j["failed_videos"]:
                j["status"] = "done"
            elif rc == 0 or (j["failed_videos"] and j["out_dir"]):
                j["status"] = "partial"
            else:
                j["status"] = "failed"
                if not j["error"]:
                    tail = [x for x in j["log"] if x.strip() and not x.startswith(" ")]
                    j["error"] = (tail[-1] if tail else f"exit code {rc}")[:300]
            j.update(ended=_now(), pct=None, eta="", stage_idx=4 if j["status"] == "done" else j.get("stage_idx"), only=[])
            self.proc, self.current = None, None
        self.save()

    def _worker(self):
        while True:
            time.sleep(1)
            with self.lock:
                if self.paused or self.current:
                    continue
                j = next((x for x in self.jobs if x["status"] == "queued"), None)
            if j:
                self._run(j)

    # ------------------------------------------------------------------ machine, probe, stats
    def _check_machine(self):
        m = {"checking": False}
        try:
            from ucf import config, render
            cfg = config.load()
            m["encoder"] = render.pick_encoder(cfg)
            m["decode"] = render._HW.get("name") or "CPU"
            m["min_height"] = int(cfg.get("min_height", 720))
        except Exception as e:
            m["encoder"], m["decode"], m["error"] = "?", "?", str(e)[:200]
        kd = Path.home() / ".config" / "umf"
        m["keys"] = {}
        for fn, var in KEY_FILES.items():
            ok = False
            try:
                for ln in (kd / fn).read_text(encoding="utf-8").splitlines():
                    k, _, v = ln.partition("=")
                    ok = ok or (k.strip() == var and bool(v.strip().strip("'\"")))
            except OSError:
                pass
            m["keys"][fn.split(".")[0]] = ok
        m["ffmpeg"] = shutil.which("ffmpeg") or ""
        import platform
        m["machine"] = platform.node() or os.environ.get("COMPUTERNAME", "")
        try:
            m["version"] = subprocess.run(["git", "-C", str(ROOT), "log", "-1", "--format=%cd", "--date=short"],
                                          capture_output=True, text=True, timeout=10).stdout.strip()
        except Exception:
            m["version"] = ""
        self.machine = m

    def probe(self, url):
        if url in self._probe_cache:
            return self._probe_cache[url]
        try:
            from ucf import config, download
            cfg = config.load()
            i = download.info(url, cfg)
            r = {"ok": True, "title": i.get("title", ""), "duration": i.get("duration", 0), "height": i.get("best_height", 0),
                 "kbps": i.get("best_kbps", 0), "live": bool(i.get("is_live")), "min_height": int(cfg.get("min_height", 720))}
        except Exception as e:
            r = {"ok": False, "error": (str(e).strip().splitlines() or ["could not read the link"])[0][:200]}
        self._probe_cache[url] = r
        return r

    def stats(self):
        today = time.strftime("%Y-%m-%d")
        rows = []
        try:
            with (STATE / "run_history.csv").open(newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
        except OSError:
            pass

        def num(r, k):
            try:
                return float(r.get(k) or 0)
            except ValueError:
                return 0.0
        t = [r for r in rows if (r.get("date") or "").startswith(today)]
        speed = [num(r, "total_min") / num(r, "stream_min") for r in rows[-20:] if num(r, "stream_min") > 0]
        cost = [num(r, "cost_usd") / num(r, "stream_min") for r in rows[-20:] if num(r, "stream_min") > 0]
        return {"streams_today": len(t), "videos_today": int(sum(num(r, "videos") for r in t)),
                "avg_min": round(sum(num(r, "total_min") for r in t) / len(t)) if t else None,
                "cost_today": round(sum(num(r, "cost_usd") for r in t), 2),
                "min_per_stream_min": (sum(speed) / len(speed)) if speed else 0.5,
                "usd_per_stream_min": (sum(cost) / len(cost)) if cost else 0.0005}

    def snapshot(self):
        with self.lock:
            jobs = [dict(j, log=j.get("log", [])[-8:]) for j in self.jobs]
        try:
            free = shutil.disk_usage(ROOT).free
        except OSError:
            free = 0
        return {"jobs": jobs, "paused": self.paused, "running": bool(self.current), "machine": dict(self.machine, free_gb=round(free / 1e9)),
                "stats": self.stats()}

    def job_log(self, jid):
        with self.lock:
            j = self._job(jid)
            return list(j.get("log", [])) if j else []


# ---------------------------------------------------------------------- library
_dur_cache = {}


def _duration(p):
    key = (str(p), p.stat().st_mtime)
    if key not in _dur_cache:
        try:
            r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(p)],
                               capture_output=True, text=True, timeout=20)
            _dur_cache[key] = float(r.stdout.strip() or 0)
        except Exception:
            _dur_cache[key] = 0
    return _dur_cache[key]


def styles():
    out = []
    for f in sorted((ROOT / "styles").glob("*/style.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            out.append({"id": d.get("id", f.parent.name), "name": d.get("name", f.parent.name)})
        except Exception:
            continue
    return out


def library(limit=30):
    runs = []
    if not OUT.exists():
        return runs
    names = {s["id"]: s["name"] for s in styles()}
    for run in sorted([d for d in OUT.iterdir() if d.is_dir()], key=lambda d: d.stat().st_mtime, reverse=True)[:limit]:
        style = mode = ""
        try:
            head = (run / "ranking.md").read_text(encoding="utf-8").splitlines()[0]
            m = re.search(r"style: (\S+) — mode: (\S+)", head)
            if m:
                style, mode = m.group(1), m.group(2)
        except (OSError, IndexError):
            pass
        clips = run.name.endswith("_clips")
        videos = []
        for v in sorted([d for d in run.iterdir() if d.is_dir()]):
            media = v / ("clip.mp4" if clips else "video.mp4")
            if not media.exists():
                continue
            vp, qc, up = {}, {}, {}
            for name, target in (("video_plan.json", "vp"), ("qc.json", "qc"), ("upload_status.json", "up")):
                try:
                    data = json.loads((v / name).read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    data = {}
                if target == "vp":
                    vp = data
                elif target == "qc":
                    qc = data
                else:
                    up = data
            video = vp.get("video") or {}
            titles = [t.get("text", "") for t in sorted(video.get("titles") or [], key=lambda t: (not t.get("primary"), t.get("ctr_rank", 9)))]
            thumb = next((x for x in ("thumbnail.jpg", "thumbnail_frame_1.jpg") if (v / x).exists()), "")
            m = re.match(r"(\d+)_", v.name)
            videos.append({"rel": f"{run.name}/{v.name}", "folder": v.name, "rank": int(m.group(1)) if m else None,
                           "title": titles[0] if titles else video.get("title") or v.name, "titles": titles[:5],
                           "thumb": f"{run.name}/{v.name}/{thumb}" if thumb else "", "length": round(_duration(media)),
                           "qc_ok": bool(qc.get("ok", True)), "qc_note": qc.get("note", ""), "kind": "clip" if clips else "video",
                           "meta_file": "EDITOR_GUIDE.txt" if clips else "metadata.txt", "upload": up,
                           "thumb_text": (video.get("thumbnail") or {}).get("text", "")})
        review = []
        try:
            plan = json.loads((run / "plan.json").read_text(encoding="utf-8"))
            review = [{"name": c.get("name", ""), "in": c.get("in", ""), "out": c.get("out", ""), "why": c.get("reject_reason", "")}
                      for c in plan.get("cases", []) if c.get("needs_review")]
        except (OSError, ValueError):
            pass
        if videos or review:
            runs.append({"run": run.name, "style": names.get(style, style), "mode": "clips" if clips else mode, "videos": videos,
                         "review": review, "time": time.strftime("%Y-%m-%d %H:%M", time.localtime(run.stat().st_mtime))})
    return runs


def _safe_out(rel):
    p = (OUT / unquote(rel)).resolve()
    if OUT.resolve() not in p.parents and p != OUT.resolve():
        raise PermissionError(rel)
    return p


def open_path(p):
    try:
        if WIN:
            os.startfile(str(p))                                  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(p)])
        elif shutil.which("xdg-open"):
            subprocess.Popen(["xdg-open", str(p)])
    except Exception:
        pass


# ---------------------------------------------------------------------- HTTP
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".jpg": "image/jpeg", ".png": "image/png", ".txt": "text/plain; charset=utf-8", ".mp4": "video/mp4",
         ".svg": "image/svg+xml", ".json": "application/json"}


def make_handler(studio):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="application/json"):
            if not isinstance(body, (bytes, bytearray)):
                body = json.dumps(body).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self):
            n = int(self.headers.get("Content-Length") or 0)
            try:
                return json.loads(self.rfile.read(n) or b"{}")
            except ValueError:
                return {}

        def do_GET(self):
            u = urlparse(self.path)
            q = parse_qs(u.query)
            try:
                if u.path in ("/", "/index.html"):
                    return self._send(200, (STATIC / "index.html").read_bytes(), TYPES[".html"])
                if u.path.startswith("/static/"):
                    p = (STATIC / u.path[8:]).resolve()
                    if STATIC.resolve() not in p.parents or not p.is_file():
                        return self._send(404, {"error": "not found"})
                    return self._send(200, p.read_bytes(), TYPES.get(p.suffix, "application/octet-stream"))
                if u.path == "/api/ping":
                    return self._send(200, {"app": "hlabs-studio"})
                if u.path == "/api/state":
                    return self._send(200, studio.snapshot())
                if u.path == "/api/styles":
                    return self._send(200, styles())
                if u.path == "/api/library":
                    return self._send(200, library())
                if u.path == "/api/log":
                    return self._send(200, {"log": studio.job_log((q.get("id") or [""])[0])})
                if u.path == "/api/text":
                    p = _safe_out((q.get("rel") or [""])[0])
                    return self._send(200, {"text": p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""})
                if u.path.startswith("/files/"):
                    p = _safe_out(u.path[7:])
                    if not p.is_file():
                        return self._send(404, {"error": "not found"})
                    return self._send(200, p.read_bytes(), TYPES.get(p.suffix.lower(), "application/octet-stream"))
                return self._send(404, {"error": "not found"})
            except PermissionError:
                return self._send(403, {"error": "outside the output folder"})
            except Exception as e:
                return self._send(500, {"error": str(e)[:300]})

        def do_POST(self):
            u = urlparse(self.path)
            d = self._json()
            try:
                if u.path == "/api/probe":
                    return self._send(200, studio.probe((d.get("url") or "").strip()))
                if u.path == "/api/jobs":
                    urls = [x.strip() for x in d.get("urls") or [] if x.strip().startswith("http")]
                    mode = d.get("mode") if d.get("mode") in ("30", "60", "all", "clips") else "all"
                    ids = {s["id"] for s in styles()}
                    style = d.get("style") if d.get("style") in ids else next(iter(sorted(ids)), "trial_tales")
                    return self._send(200, {"added": studio.add(urls, style, mode, d.get("options") or {})})
                m = re.match(r"/api/jobs/([0-9a-f]+)/(remove|retry|up|down)$", u.path)
                if m:
                    jid, act = m.groups()
                    {"remove": studio.remove, "retry": studio.retry,
                     "up": lambda i: studio.move(i, -1), "down": lambda i: studio.move(i, 1)}[act](jid)
                    return self._send(200, {"ok": True})
                if u.path == "/api/stop":
                    studio.stop()
                    return self._send(200, {"ok": True})
                if u.path == "/api/pause":
                    studio.set_paused(bool(d.get("paused")))
                    return self._send(200, {"ok": True})
                if u.path == "/api/open":
                    p = _safe_out(d.get("rel") or "")
                    open_path(p if p.exists() else OUT)
                    return self._send(200, {"ok": True})
                if u.path == "/api/upload":
                    p = _safe_out(d.get("rel") or "")
                    if not p.is_dir():
                        return self._send(404, {"error": "not found"})
                    (p / "upload_status.json").write_text(json.dumps(d.get("checks") or {}), encoding="utf-8")
                    return self._send(200, {"ok": True})
                return self._send(404, {"error": "not found"})
            except PermissionError:
                return self._send(403, {"error": "outside the output folder"})
            except Exception as e:
                return self._send(500, {"error": str(e)[:300]})
    return H


def serve(port=8765, open_browser=True):
    import urllib.request
    for p in range(port, port + 20):                     # already running on this PC? just open it again
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{p}/api/ping", timeout=0.5) as r:
                if json.loads(r.read()).get("app") == "hlabs-studio":
                    print(f"H Labs Studio is already running: http://127.0.0.1:{p}")
                    if open_browser:
                        webbrowser.open(f"http://127.0.0.1:{p}")
                    return
        except Exception:
            pass
        try:
            httpd = ThreadingHTTPServer(("127.0.0.1", p), make_handler(Studio()))
        except OSError:
            continue
        url = f"http://127.0.0.1:{p}"
        print("=" * 60 + f"\n  H Labs Studio is running:  {url}\n  Keep this window open while streams are processed.\n"
              "  Closing it stops the queue (it continues when you open Studio again).\n" + "=" * 60, flush=True)
        if open_browser:
            webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        return
    print("no free port between 8765 and 8784")


if __name__ == "__main__":
    serve(open_browser="--no-browser" not in sys.argv)
