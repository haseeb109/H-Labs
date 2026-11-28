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
import ucf  # noqa: E402,F401 - ffmpeg / yt-dlp never read the console (ucf/__init__.py)
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
            except OSError:                        # no taskkill / process group gone: plain kill
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
        # the same stream waits in the queue again (another style / mode): keep its download for that job instead of deleting
        # it and downloading it again (2026-11-25: six styles of one stream = six downloads); the last job cleans up as usual
        if any(x is not j and x.get("status") == "queued" and x.get("url") == j["url"] and x.get("mode") not in ("download", "dossier")
               for x in self.jobs):
            o = dict(o, cleanup=False)
        from ucf.runspec import build_run_command
        return build_run_command(sys.executable, j["url"], j["style"], j["mode"], dict(o, brain=brain, queued=True, only=j.get("only")),
                                 script=ROOT / "run_stream.py")

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
        if s.startswith("@@resumed "):
            try:
                j["videos_resumed"] = int(s.split()[1])        # finished by the stopped run: counted as done, not rendered again
            except (IndexError, ValueError):
                pass
            return
        j["log"].append(s[:400])
        if len(j["log"]) > 300:
            del j["log"][:100]
        m = re.search(r"stream: (.*)  \((\d+:\d+(?::\d+)?), id (\S+)\)", s)
        if m:
            j["title"] = m.group(1).strip()
            j["stream_id"] = m.group(3)
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
                     log=[], error="", failed_videos=[], out_dir="", videos_total=0, video_now=0, videos_resumed=0)
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
                j["error"] = (f"No case of {(j.get('options') or {}).get('min_case') or 8}:00+ in this stream - "
                              "try 5 min cases, the 30 min / 1 hour mode, or As-is.")
            elif rc == 0 and any(re.search(r"\bvideos 0\b", x) for x in j["log"][-200:]):
                j["status"] = "nothing"      # finished, but the plan made no video (every case skipped / needs review)
                j["error"] = "Finished with 0 videos - every case was skipped or needs review. Copy log and ask."
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
            ev = ROOT / "work" / str(j.get("stream_id") or "-") / "events.jsonl"     # the run's structured log (ucf/events.py)
            j["events"] = str(ev.relative_to(ROOT)) if j.get("stream_id") and ev.is_file() else ""
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
        try:                                                  # last smoke test (tools/smoke_test.py: after every update, menu 6)
            sj = json.loads((ROOT / "state" / "smoke_last.json").read_text(encoding="utf-8"))
            bad = [c for c in sj.get("checks", []) if not c.get("ok")]
            m["smoke"] = {"date": sj.get("date", ""), "fails": len(bad),
                          "first_fail": (bad[0]["name"] + ": " + str(bad[0].get("msg", "")).splitlines()[0][:160]) if bad else ""}
        except (OSError, ValueError, KeyError, IndexError):
            m["smoke"] = None
        import platform
        m["machine"] = platform.node() or os.environ.get("COMPUTERNAME", "")
        try:
            date = subprocess.run(["git", "-C", str(ROOT), "log", "-1", "--format=%cd", "--date=short"],
                                  capture_output=True, text=True, timeout=10).stdout.strip()
            m["version"] = ((ROOT / "VERSION").read_text(encoding="utf-8").strip() if (ROOT / "VERSION").exists() else "dev") \
                + (f" ({date})" if date else "")
        except (OSError, subprocess.SubprocessError):   # no git on this PC: version stays blank in the header
            m["version"] = ""
        self.machine = m

    def probe(self, url):
        if url in self._probe_cache:
            return self._probe_cache[url]
        if not is_link(url):                                   # your own file / folder on this PC
            try:
                from ucf import config, download, local_src
                v, t = local_src.resolve(url)
                h, bps = download.probe_video(v)
                r = {"ok": True, "local": True, "title": v.stem, "duration": _duration(v), "height": h, "kbps": round(bps / 1000),
                     "live": False, "min_height": int(config.load().get("min_height", 720)), "video": str(v),
                     "transcript": str(t) if t else ""}
            except Exception as e:
                r = {"ok": False, "error": str(e)[:200]}
            self._probe_cache[url] = r
            return r
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

    def job_log(self, jid, events=False):
        with self.lock:
            j = self._job(jid)
            if events and j and j.get("events"):         # small structured file instead of the console tail
                try:
                    return (ROOT / j["events"]).read_text(encoding="utf-8", errors="replace").splitlines()[-400:]
                except OSError:
                    return []
            return list(j.get("log", [])) if j else []


# ---------------------------------------------------------------------- your own file (New run step 1)
def pick_file():
    """The PC's own "Open file" dialog -> the real path ("" when cancelled). A browser never tells a page where a file is on
    disk, so typed paths went wrong (2026-11-21); the Studio server runs on this PC and can ask Windows directly."""
    if WIN:
        ps = ("Add-Type -AssemblyName System.Windows.Forms; $f = New-Object System.Windows.Forms.Form -Property @{TopMost=$true}; "
              "$d = New-Object System.Windows.Forms.OpenFileDialog; $d.Title = 'H Labs - choose your video'; "
              "$d.Filter = 'Video (*.mp4;*.mkv;*.webm;*.mov;*.m4v;*.ts)|*.mp4;*.mkv;*.webm;*.mov;*.m4v;*.ts|All files|*.*'; "
              "if ($d.ShowDialog($f) -eq 'OK') { [Console]::Out.Write($d.FileName) }")
        r = subprocess.run(["powershell", "-NoProfile", "-STA", "-Command", ps], capture_output=True, text=True, encoding="utf-8")
        return (r.stdout or "").strip()
    try:
        import tkinter
        from tkinter import filedialog
        root = tkinter.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askopenfilename(title="H Labs - choose your video")
        root.destroy()
        return path or ""
    except Exception:  # noqa - no display / no tkinter: the page says so and the path can still be typed
        return ""


def pick_folder(title="H Labs - choose a folder"):
    """The PC's own folder dialog -> the real path ("" when cancelled): B-roll folder, media library."""
    if WIN:
        ps = ("Add-Type -AssemblyName System.Windows.Forms; $f = New-Object System.Windows.Forms.Form -Property @{TopMost=$true}; "
              f"$d = New-Object System.Windows.Forms.FolderBrowserDialog; $d.Description = '{title}'; "
              "if ($d.ShowDialog($f) -eq 'OK') { [Console]::Out.Write($d.SelectedPath) }")
        r = subprocess.run(["powershell", "-NoProfile", "-STA", "-Command", ps], capture_output=True, text=True, encoding="utf-8")
        return (r.stdout or "").strip()
    try:
        import tkinter
        from tkinter import filedialog
        root = tkinter.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askdirectory(title=title)
        root.destroy()
        return path or ""
    except Exception:  # noqa - no display / no tkinter: the path can still be typed
        return ""


INPUT = ROOT / "input"


def save_upload(name, stream, size):
    """A file dropped on the page -> input/<name> (copied in 8 MB blocks; a browser gives the page the bytes, not the path)."""
    INPUT.mkdir(exist_ok=True)
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", Path(name).name).strip(" .") or "video.mp4"
    out = INPUT / safe
    tmp = out.with_name(out.name + ".part")
    left = int(size)
    with open(tmp, "wb") as f:
        while left > 0:
            b = stream.read(min(8 << 20, left))
            if not b:
                break
            f.write(b)
            left -= len(b)
    if left:
        tmp.unlink(missing_ok=True)
        raise ValueError("the upload stopped before the end")
    os.replace(tmp, out)
    return out


# ---------------------------------------------------------------------- library
_dur_cache = {}


def is_link(u):
    from ucf.runspec import is_link as _is_link
    return _is_link(u)


def _duration(p):
    key = (str(p), p.stat().st_mtime)
    if key not in _dur_cache:
        try:
            r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(p)],
                               capture_output=True, text=True, timeout=20)
            _dur_cache[key] = float(r.stdout.strip() or 0)
        except (OSError, ValueError, subprocess.SubprocessError):   # no ffprobe / unreadable: shown as 0:00 in the library
            _dur_cache[key] = 0
    return _dur_cache[key]


def styles():
    out = []
    for f in sorted((ROOT / "styles").glob("*/style.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            out.append({"id": d.get("id", f.parent.name), "name": d.get("name", f.parent.name), "doc": d.get("renderer") == "doc"})
        except (OSError, ValueError, AttributeError) as e:    # a broken pack is listed so the typo gets fixed
            out.append({"id": f.parent.name, "name": f"{f.parent.name} (style.json unreadable: {str(e)[:60]})"})
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
    except OSError as e:
        print(f"  could not open {p} ({e})", flush=True)


# ---------------------------------------------------------------------- HTTP
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".jpg": "image/jpeg", ".png": "image/png", ".txt": "text/plain; charset=utf-8", ".mp4": "video/mp4",
         ".svg": "image/svg+xml", ".json": "application/json"}


# ------------------------------------------------------------------ Settings: API keys + media library (2026-11-23)
# Keys are written ONLY to ~/.config/umf/<file>.env (never the repo, logs or state). The browser can set or clear a key,
# never read one back: the API answers "set / not set" only.
KEY_SPECS = [
    {"id": "hive", "label": "Hive (brain)", "file": "hive.env", "var": "HIVE_API_KEY", "need": True,
     "help": "The brain that plans the videos."},
    {"id": "ai33", "label": "ai33 (AI voice)", "file": "ai33.env", "var": "AI33_API_KEY", "need": True,
     "help": "Narrator / voice-over."},
    {"id": "pexels", "label": "Pexels (stock B-roll)", "file": "pexels.env", "var": "PEXELS_API_KEY", "need": False,
     "help": "Free key: pexels.com/api"},
    {"id": "pixabay", "label": "Pixabay (stock B-roll)", "file": "pixabay.env", "var": "PIXABAY_API_KEY", "need": False,
     "help": "Free key: pixabay.com/api/docs"},
    {"id": "anthropic", "label": "Anthropic (optional brain)", "file": "anthropic.env", "var": "ANTHROPIC_API_KEY", "need": False,
     "help": "Only if you switch the brain to Anthropic."},
    {"id": "deepseek", "label": "DeepSeek (optional brain)", "file": "deepseek.env", "var": "DEEPSEEK_API_KEY", "need": False, "help": ""},
    {"id": "openai", "label": "OpenAI (optional brain)", "file": "openai.env", "var": "OPENAI_API_KEY", "need": False, "help": ""},
    {"id": "github", "label": "GitHub (send to developer)", "file": "github.env", "var": "GITHUB_REPORT_TOKEN", "need": False,
     "help": "Fine-grained token: only the reports repo, Issues read + write."},
]
KEY_DIR = Path.home() / ".config" / "umf"
STOCK_LOG = STATE / "stock_fetch.log"
_stock = {"proc": None}


def _key_lines(spec):
    try:
        return (KEY_DIR / spec["file"]).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []


def key_is_set(spec):
    for ln in _key_lines(spec):
        k, _, v = ln.partition("=")
        if k.strip() == spec["var"] and v.strip().strip("'\""):
            return True
    return False


# ---------------------------------------------------------------- send to developer (2026-11-28)
# Failed / empty runs go to GitHub Issues of a PRIVATE reports repo in one click: the PC's own facts (name, GPU, encoder,
# version, last smoke test) + every selected job's error and log tail, with keys and tokens removed. The developer reads
# them per PC: the same failure on several PCs = a tool bug (fixed, PCs update); on one PC only = a fix for that PC.
REPORT_DIR = STATE / "reports"
_SECRET = re.compile(r"(?i)((?:api[_-]?key|token|secret|authorization|bearer|password)\W{0,3})[A-Za-z0-9_\-.:/+=]{8,}|"
                     r"\b(?:sk|ghp|github_pat|gho|xox[bp])[-_][A-Za-z0-9_\-]{10,}")
_PC_HINTS = re.compile(r"(?i)no module named|is not recognized|not found on this pc|no space|disk|permission denied|access is denied|"
                       r"winerror|nvenc|cuda|cudnn|driver|vram|out of memory|getaddrinfo|timed out|connection (?:reset|refused|aborted)|"
                       r"ssl|proxy|missing key|key (?:missing|refused)|401|403 forbidden")


def _redact(t):
    return _SECRET.sub(lambda m: (m.group(1) or "") + "[removed]", str(t))


def _shown(p):
    try:
        return str(Path(p).relative_to(ROOT))
    except ValueError:
        return str(p)


def report_repo():
    try:
        r = json.loads((ROOT / "config.json").read_text(encoding="utf-8-sig")).get("report_repo")
    except (OSError, ValueError):
        r = None
    return str(r or "haseeb109/hlabs-reports")


def guess_kind(text):
    """'pc' when the failure reads like this PC (package, disk, GPU, network, key), else 'tool'."""
    return "pc" if _PC_HINTS.search(text or "") else "tool"


def build_report(studio, jobs):
    """-> (title, markdown body, labels) for the selected jobs."""
    import platform
    import socket
    pc = (os.environ.get("COMPUTERNAME") or socket.gethostname() or "pc")[:40]
    m = studio.machine or {}
    try:
        sm = json.loads((STATE / "smoke_last.json").read_text(encoding="utf-8"))
        smoke = f"{sm.get('date', '?')}: " + (", ".join(c["name"] for c in sm.get("checks", []) if not c.get("ok")) or "all ok")
    except (OSError, ValueError, KeyError):
        smoke = "never run"
    kinds = []
    parts = [f"**PC:** `{pc}`  |  **H Labs:** v{_ver()} ({_git('rev-parse', '--short', 'HEAD').stdout.strip()})  |  "
             f"**OS:** {platform.platform()}  |  **Python:** {platform.python_version()}",
             f"**Encoder:** {m.get('encoder', '?')}  |  **Decode:** {m.get('decode', '?')}  |  **Smoke test:** {smoke}", ""]
    for j in jobs:
        log = studio.job_log(j["id"])
        k = guess_kind(" ".join([j.get("error", "")] + log[-60:]))
        kinds.append(k)
        parts += [f"---\n### {j.get('style')} · {j.get('mode')} · {j.get('status')} · guess: {k.upper()}",
                  f"**Stream:** {j.get('title') or ''} {j.get('url')}", f"**Error:** {_redact(j.get('error') or '-')}",
                  "<details><summary>log (last 200 lines)</summary>\n\n```", _redact("\n".join(log[-200:]))[-60000:], "```\n</details>"]
    kind = "pc" if kinds and all(x == "pc" for x in kinds) else "tool"
    errs = "; ".join(sorted({(j.get("error") or j.get("status") or "")[:60] for j in jobs}))[:120]
    return f"[{pc}] {len(jobs)} failed run(s): {errs}", "\n".join(parts), [f"pc:{pc}", f"guess:{kind}", f"v{_ver()}"]


def send_report(studio, ids):
    """GitHub issue in the reports repo; without a token (or offline) the report is saved in state/reports/ instead."""
    jobs = [j for j in studio.jobs if j["id"] in set(ids or [])] or \
           [j for j in studio.jobs if j.get("status") in ("failed", "partial", "nothing")][-10:]
    if not jobs:
        return {"ok": False, "message": "no failed run to send"}
    title, body, labels = build_report(studio, jobs)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    local = REPORT_DIR / f"report_{time.strftime('%Y%m%d_%H%M%S')}.md"
    local.write_text(f"# {title}\n\n{body}\n", encoding="utf-8")
    tok = ""
    for ln in _key_lines(next(k for k in KEY_SPECS if k["id"] == "github")):
        a, _, v = ln.partition("=")
        if a.strip() == "GITHUB_REPORT_TOKEN":
            tok = v.strip().strip("'\"")
    if not tok:
        return {"ok": False, "saved": str(local), "message": "no GitHub token on this PC (Settings > API keys > GitHub) - "
                "the report is saved in " + str(_shown(local))}
    import urllib.request
    req = urllib.request.Request(f"https://api.github.com/repos/{report_repo()}/issues", method="POST",
                                 data=json.dumps({"title": title[:250], "body": body[:65000], "labels": labels}).encode(),
                                 headers={"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json",
                                          "User-Agent": "hlabs-studio", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            url = json.loads(r.read()).get("html_url", "")
    except Exception as e:  # noqa - the report stays saved locally; say why GitHub refused
        why = getattr(e, "code", "") or str(e)[:120]
        return {"ok": False, "saved": str(local), "message": f"GitHub refused the report ({why}) - check the token / repo "
                f"{report_repo()}; the report is saved in {_shown(local)}"}
    for j in jobs:
        j["reported"] = url
    studio.save()
    return {"ok": True, "url": url, "count": len(jobs), "message": f"sent {len(jobs)} run(s) to the developer"}


def keys_status():
    return [dict({k: s[k] for k in ("id", "label", "need", "help")}, set=key_is_set(s)) for s in KEY_SPECS]


def set_key(kid, value):
    """Write (value) or remove (empty value) one key. Other lines of the .env file are kept."""
    spec = next((s for s in KEY_SPECS if s["id"] == kid), None)
    if not spec:
        raise ValueError("unknown key")
    value = (value or "").strip().strip("'\"")
    if len(value) > 400 or any(c in value for c in "\r\n\0 ") or (value and not value.isprintable()):
        raise ValueError("that does not look like an API key (spaces, line breaks or too long)")
    KEY_DIR.mkdir(parents=True, exist_ok=True)
    lines = [ln for ln in _key_lines(spec) if ln.partition("=")[0].strip() != spec["var"]]
    if value:
        lines.append(f"{spec['var']}={value}")
    f = KEY_DIR / spec["file"]
    tmp = f.with_suffix(".tmp")
    tmp.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, f)
    os.environ.pop(spec["var"], None)          # this process re-reads the file next time
    return key_is_set(spec)


def _local_cfg_path():
    return ROOT / "config.local.json"


def settings_get():
    from ucf import audiomix, stock
    try:
        local = json.loads(_local_cfg_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        local = {}
    lib = local.get("media_library", "")
    bf = local.get("broll_folder", "")
    out = {"keys": keys_status(), "media_library": lib, "library": None, "stock": stock_status(),
           "broll_source": local.get("broll_source", "auto"), "broll_folder": bf,
           "broll_folder_clips": len(stock.folder_clips(bf)) if bf else 0}
    if lib and Path(lib).is_dir():
        st = audiomix.library_status(lib)
        out["library"] = {"broll": {t: len(stock.clips_in(Path(lib) / "broll" / t))
                                    for t in sorted(set(stock.DEFAULT_TAGS) | set(stock.tags_on_disk(lib, 0)))},
                          "music": st["music"], "sfx": st["sfx"]}
    return out


def settings_set(d):
    """Only media_library for now; merged into config.local.json (this PC only, not in git)."""
    p = _local_cfg_path()
    try:
        local = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        local = {}
    if "media_library" in d:
        lib = str(d.get("media_library") or "").strip().strip('"')
        if lib:
            lp = Path(lib)
            if not lp.is_absolute():
                raise ValueError("use a full folder path, e.g. D:\\HLabsLibrary")
            for sub in ("broll", "music", "sfx"):
                (lp / sub).mkdir(parents=True, exist_ok=True)
        local["media_library"] = lib
    if "broll_folder" in d:
        bf = str(d.get("broll_folder") or "").strip().strip('"')
        if bf and not Path(bf).is_dir():
            raise ValueError("that B-roll folder does not exist on this PC")
        local["broll_folder"] = bf
    if d.get("broll_source") in ("auto", "api", "folder"):
        local["broll_source"] = d["broll_source"]
    p.write_text(json.dumps(local, indent=2), encoding="utf-8")
    return settings_get()


def stock_start(tags=None, count=8):
    """Run tools/stock_fetch.py in the background (one at a time); output in state/stock_fetch.log."""
    pr = _stock["proc"]
    if pr and pr.poll() is None:
        raise ValueError("a stock download is already running")
    cmd = [sys.executable, str(ROOT / "tools" / "stock_fetch.py"), "--count", str(max(1, min(int(count or 8), 40)))]
    from ucf import stock
    for t in tags or []:
        if re.fullmatch(r"[a-z0-9_]{2,40}", t):
            cmd += ["--tag", t]
    env = {k: v for k, v in os.environ.items() if k not in ("PEXELS_API_KEY", "PIXABAY_API_KEY")}
    env.update(PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
    STATE.mkdir(exist_ok=True)
    log = open(STOCK_LOG, "w", encoding="utf-8")
    kw = {"creationflags": 0x08000000} if WIN else {}
    _stock["proc"] = subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, env=env, **kw)
    return stock_status()


def stock_status():
    pr = _stock["proc"]
    try:
        tail = STOCK_LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-14:]
    except OSError:
        tail = []
    return {"running": bool(pr and pr.poll() is None), "log": tail}


# ------------------------------------------------------------------ Update from the Studio (2026-11-23)
# Windows: packages cannot be replaced while this Python runs (same reason menu 8 closes first). So the Update button makes the
# server exit with code 88; tools\win\studio.ps1 (started by "H Labs Studio.bat") then runs the normal update (setup.ps1 -Update:
# git pull with state kept, uv sync, newest yt-dlp, smoke test) in the same window and starts the Studio again. The open page
# waits and then shows "updated vA (c0) -> vB (c1)" with the list of changes. Mac / Linux: git pull + yt-dlp in place, restart.
UPD_PENDING = STATE / "update_pending.json"
UPD_RESULT = STATE / "update_result.json"
_upd = {"check": None}


def _git(*a, timeout=60):
    try:
        return subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        return subprocess.CompletedProcess(a, 1, "", str(e))


def _ver():
    try:
        return (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "dev"


def version_info():
    try:
        last = json.loads(UPD_RESULT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        last = None
    br = _git("symbolic-ref", "-q", "--short", "HEAD").stdout.strip()
    return {"version": _ver(), "commit": _git("rev-parse", "--short", "HEAD").stdout.strip(), "branch": br,
            "last_update": last, "check": _upd["check"], "can_update": (ROOT / ".git").exists(),
            "restart_ok": bool(os.environ.get("HL_STUDIO_LOOP")) or not WIN}


def update_check():
    """git fetch + what the update would bring (commit subjects, newest first)."""
    main = "main"
    f = _git("fetch", "-q", "origin", main, timeout=90)
    if f.returncode:
        out = {"ok": False, "error": "could not reach GitHub: " + (f.stderr or f.stdout).strip()[-200:]}
    else:
        log = _git("log", "--pretty=%h\t%s", f"HEAD..origin/{main}").stdout.strip().splitlines()
        out = {"ok": True, "behind": len(log), "changes": [dict(zip(("commit", "text"), ln.split("\t", 1))) for ln in log[:25]],
               "remote_version": _git("show", f"origin/{main}:VERSION").stdout.strip()}
    out["at"] = _now()
    _upd["check"] = out
    return out


def finish_update():
    """At start: an update just ran -> write what changed (old -> new + commit list + smoke test) for the page."""
    try:
        p = json.loads(UPD_PENDING.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    now_c = _git("rev-parse", "--short", "HEAD").stdout.strip()
    log = _git("log", "--pretty=%h\t%s", f"{p.get('commit_full', '')}..HEAD").stdout.strip().splitlines() if p.get("commit_full") else []
    try:
        sj = json.loads((STATE / "smoke_last.json").read_text(encoding="utf-8"))
        bad = [c["name"] for c in sj.get("checks", []) if not c.get("ok")]
        smoke = {"date": sj.get("date", ""), "fails": bad}
    except (OSError, ValueError, KeyError):
        smoke = None
    if not p.get("paused_before"):                          # the queue was running before the update: let it run again
        try:
            q = json.loads(QFILE.read_text(encoding="utf-8"))
            q["paused"] = False
            QFILE.write_text(json.dumps(q, indent=1), encoding="utf-8")
        except (OSError, ValueError):
            pass
    res = {"from_version": p.get("version"), "from_commit": p.get("commit"), "to_version": _ver(), "to_commit": now_c,
           "changed": now_c != p.get("commit"), "changes": [dict(zip(("commit", "text"), ln.split("\t", 1))) for ln in log[:40]],
           "smoke": smoke, "started": p.get("at"), "finished": _now(), "seen": False}
    # the pull can fail (a file of the H Labs folder edited on this PC, no internet): the code is still behind GitHub.
    # Say so instead of "already up to date" (2026-11-25: a PC kept running an old build after pressing Update).
    behind = _git("rev-list", "--count", "HEAD..origin/main").stdout.strip()
    if behind.isdigit() and int(behind) > 0:
        edited = [ln[3:].strip() for ln in _git("status", "--porcelain", "--untracked-files=no").stdout.splitlines() if ln.strip()]
        res["not_applied"] = {"behind": int(behind), "edited": edited[:12]}
    UPD_RESULT.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    UPD_PENDING.unlink(missing_ok=True)
    _upd["check"] = None
    return res


def start_update(studio):
    """-> (ok, message). Refuses while a stream is being made (the update restarts the Studio)."""
    if any(j.get("status") == "running" for j in studio.jobs):
        return False, "a stream is being made right now - update when the queue is idle (or press Stop first)"
    if not (ROOT / ".git").exists():
        return False, "this folder was not cloned with git - updates need a git clone (see WINDOWS_SETUP.md)"
    if WIN and not os.environ.get("HL_STUDIO_LOOP"):
        return False, "this Studio was not started by 'H Labs Studio.bat' - close it and open it with that file once, then the button works"
    STATE.mkdir(exist_ok=True)
    was_paused = studio.paused
    studio.set_paused(True)                                 # no queued stream may start in the second before the restart
    UPD_PENDING.write_text(json.dumps({"paused_before": was_paused, "version": _ver(), "commit": _git("rev-parse", "--short", "HEAD").stdout.strip(),
                                       "commit_full": _git("rev-parse", "HEAD").stdout.strip(), "at": _now()}), encoding="utf-8")

    def go():
        time.sleep(1.0)                                     # let the answer reach the page first
        if WIN:
            os._exit(88)                                    # studio.ps1: run setup.ps1 -Update, then start the Studio again
        subprocess.run([sys.executable, str(ROOT / "tools" / "launcher.py"), "--record-last-good"], cwd=ROOT)
        _git("pull", "--ff-only", timeout=300)
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "yt-dlp[default]"], cwd=ROOT)
        subprocess.run([sys.executable, str(ROOT / "tools" / "smoke_test.py"), "--offline"], cwd=ROOT)
        os.execv(sys.executable, [sys.executable, str(Path(__file__).resolve()), "--no-browser"])
    threading.Thread(target=go, daemon=True).start()
    return True, "updating"


def mark_update_seen():
    try:
        r = json.loads(UPD_RESULT.read_text(encoding="utf-8"))
        r["seen"] = True
        UPD_RESULT.write_text(json.dumps(r, indent=1, ensure_ascii=False), encoding="utf-8")
    except (OSError, ValueError):
        pass


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

        def _trusted(self, post=False):
            """Only this PC's browser on the Studio page: Host must be localhost (blocks DNS rebinding), and a POST must be JSON
            from the Studio's own origin (another website cannot send JSON here without a CORS answer, which is never given)."""
            host = (self.headers.get("Host") or "").split(":")[0].lower()
            if host not in ("127.0.0.1", "localhost"):
                return False
            if not post:
                return True
            origin = self.headers.get("Origin")
            if origin and urlparse(origin).hostname not in ("127.0.0.1", "localhost"):
                return False
            return (self.headers.get("Content-Type") or "").split(";")[0].strip().lower() == "application/json"

        def do_GET(self):
            u = urlparse(self.path)
            q = parse_qs(u.query)
            if not self._trusted():
                return self._send(403, {"error": "forbidden"})
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
                if u.path == "/api/settings":
                    return self._send(200, settings_get())
                if u.path == "/api/version":
                    return self._send(200, version_info())
                if u.path == "/api/stock":
                    return self._send(200, stock_status())
                if u.path == "/api/log":
                    return self._send(200, {"log": studio.job_log((q.get("id") or [""])[0], events=bool(q.get("events")))})
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

        def do_PUT(self):
            """/api/upload-file?name=x.mp4: the raw bytes of a dropped file. Not a "simple" request type, so another website
            cannot send it without a CORS answer (never given); Host / Origin are checked like every other call."""
            u = urlparse(self.path)
            origin = self.headers.get("Origin")
            if not self._trusted() or (origin and urlparse(origin).hostname not in ("127.0.0.1", "localhost")) \
                    or u.path != "/api/upload-file":
                return self._send(403, {"error": "forbidden"})
            try:
                name = (parse_qs(u.query).get("name") or ["video.mp4"])[0]
                out = save_upload(name, self.rfile, int(self.headers.get("Content-Length") or 0))
                return self._send(200, {"path": str(out)})
            except (OSError, ValueError) as e:
                return self._send(400, {"error": str(e)[:200]})

        def do_POST(self):
            u = urlparse(self.path)
            if not self._trusted(post=True):
                return self._send(403, {"error": "forbidden"})
            d = self._json()
            if u.path == "/api/pick":
                return self._send(200, {"path": pick_folder() if d.get("folder") else pick_file()})
            try:
                if u.path == "/api/update-check":
                    return self._send(200, update_check())
                if u.path == "/api/update":
                    ok, msg = start_update(studio)
                    return self._send(200 if ok else 409, {"ok": ok, "message": msg} if ok else {"error": msg})
                if u.path == "/api/update-seen":
                    mark_update_seen()
                    return self._send(200, {"ok": True})
                if u.path == "/api/keys":
                    try:
                        return self._send(200, {"set": set_key(d.get("id"), d.get("value")), "keys": keys_status()})
                    except ValueError as e:
                        return self._send(400, {"error": str(e)})
                if u.path == "/api/settings":
                    try:
                        return self._send(200, settings_set(d))
                    except (ValueError, OSError) as e:
                        return self._send(400, {"error": str(e)[:200]})
                if u.path == "/api/report":
                    return self._send(200, send_report(studio, d.get("ids") or []))
                if u.path == "/api/stock":
                    try:
                        return self._send(200, stock_start(d.get("tags"), d.get("count") or 8))
                    except ValueError as e:
                        return self._send(400, {"error": str(e)})
                if u.path == "/api/probe":
                    return self._send(200, studio.probe((d.get("url") or "").strip()))
                if u.path == "/api/jobs":
                    urls = [x.strip().strip('"') for x in d.get("urls") or [] if x.strip()]
                    # every mode the front end offers (asis + download were silently turned into "all" before, 2026-11-21)
                    mode = d.get("mode") if d.get("mode") in ("30", "60", "all", "clips", "asis", "download") else "all"
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


class QuietServer(ThreadingHTTPServer):
    """A page that is closed / reloaded while the Studio answers (WinError 10053 / 10054, broken pipe) is normal - not a
    traceback in the Studio window (2026-11-23: an update check answered after the tab was reloaded)."""
    daemon_threads = True

    def handle_error(self, request, client_address):
        import sys as _s
        if isinstance(_s.exc_info()[1], (ConnectionError, TimeoutError)):
            return
        super().handle_error(request, client_address)


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
        except (OSError, ValueError):             # nothing answers on that port (or not Studio): try to bind it
            pass
        try:
            finish_update()
        except Exception as e:  # noqa - the Studio must start even when the update report cannot be written
            print("update report skipped:", e)
        try:
            httpd = QuietServer(("127.0.0.1", p), make_handler(Studio()))
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
