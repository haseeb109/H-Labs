#!/usr/bin/env python3
"""H Labs — UMF Case Factory:  .venv/bin/python3 run_stream.py <livestream-url>
   livestream URL -> transcript -> cases (Master Prompt v9) -> N finished videos in output/<date>_<id>/Video_NN_*/

Stages (run all by default):  info download transcript scan plan render
Useful:  --stage plan            stop after the plan + contact sheet (check cases before the long render)
         --plan plan.json        use a plan you got from Claude chat (brain=manual) instead of the API
         --only 1,3              render only these video numbers
         --confirm-tts           you said yes in chat to > 5,000 TTS characters
"""
import argparse
import atexit
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ucf.render_tt import TTRenderer
from ucf import finish as FINISH
from ucf import runclock as CLOCK
from ucf import brain, cards, config, download, scan, sheets, timeline as TL, transcript, tts, validate as VAL
from ucf.render import Renderer
from ucf.timeutil import fmt_dur, fmt_tc, parse_tc, safe_slug

STAGES = ["info", "download", "transcript", "scan", "evidence", "plan", "render"]
IX = {s: i for i, s in enumerate(STAGES)}


class _Tee:
    """Console output also goes to work/<id>/run_log.txt (send that file when something fails)."""
    def __init__(self, stream, path):
        self.stream, self.f = stream, open(path, "a", encoding="utf-8", errors="replace")
        if stream is sys.__stdout__:
            from ucf import __version__
            self.f.write(f"\n===== run {time.strftime('%Y-%m-%d %H:%M:%S')}  H Labs v{__version__}  {' '.join(sys.argv[1:])} =====\n")

    def write(self, s):
        self.stream.write(s)
        try:
            self.f.write(s)
            self.f.flush()
        except (OSError, ValueError) as e:         # disk full / file locked or closed: the console goes on, but say it once
            if not getattr(self, "_warned", False):
                self._warned = True
                self.stream.write(f"WARNING: run_log.txt is not being written ({e}) - keep this window open, the log is lost\n")
        return len(s)

    def flush(self):
        self.stream.flush()

    def __getattr__(self, k):
        return getattr(self.stream, k)


def fresh_render_cache(folder, cfg, video, cases):
    """The renderers reuse finished pieces in <video folder>/_work (hook, case parts, cards) when a video is rendered again.
    After an update of the render code / style / plan those pieces are stale (e.g. a removed graphic came back from an old
    00_hook.mp4), so the cache is dropped whenever the fingerprint of code + style + this video's plan changes."""
    import hashlib
    h = hashlib.sha1()
    style_dir = config.style_path(cfg)
    files = sorted((config.ROOT / "ucf").glob("*.py")) + sorted(Path(style_dir).rglob("*.py")) + sorted(Path(style_dir).glob("*.json"))
    for f in files:
        try:
            h.update(f.read_bytes())
        except OSError:
            pass
    h.update(json.dumps({"video": video, "cases": cases}, sort_keys=True, default=str).encode())
    # the watermark and the overlay cards are drawn inside the cached pieces: a change there must drop them too
    h.update(json.dumps({k: cfg.get(k) for k in sorted(cfg) if k.startswith("watermark") or k in ("channel_name", "overlays")},
                        sort_keys=True, default=str).encode())
    stamp = h.hexdigest()
    wd = Path(folder) / "_work"
    mark = wd / ".render_stamp"
    if FINISH.linked(wd) is not None and not wd.exists():          # its SSD folder was emptied by hand: drop the dead link
        FINISH.remove_tree(wd)
    if wd.exists() and (not mark.exists() or mark.read_text(encoding="utf-8").strip() != stamp):
        try:
            FINISH.remove_tree(wd)
        except OSError:
            shutil.rmtree(wd, ignore_errors=True)
        ui("  (old render pieces of this video dropped - code, style or plan changed since)")
    if not wd.exists():
        # config render_temp_dir (e.g. "C:/HLabsTemp" in config.local.json): the pieces are written to that (SSD) folder,
        # the finished video stays in output/. The pieces are written and read back several times; on a hard disk that costs.
        tmp_root = str(cfg.get("render_temp_dir") or "").strip()
        if tmp_root:
            target = Path(tmp_root).expanduser() / f"{Path(folder).parent.name}__{Path(folder).name}"
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                free = shutil.disk_usage(target.parent).free / 1e9
            except OSError:
                free = 0
            if free >= 15 and FINISH.make_linked_dir(wd, target):
                ui(f"  render pieces on the fast disk: {target}")
            else:
                ui(f"  render_temp_dir {tmp_root} not usable ({free:.0f} GB free, 15 needed) - pieces stay next to the video")
    wd.mkdir(parents=True, exist_ok=True)
    mark.write_text(stamp, encoding="utf-8")


def check_disk(root, need_gb=5.0, warn_gb=20.0, what="the H Labs drive"):
    """Stop before a download when the disk is (almost) full; warn when it is getting low."""
    try:
        free = shutil.disk_usage(root).free / 1e9
    except OSError:
        return
    if free < need_gb:
        sys.exit(f"DISK FULL: only {free:.1f} GB free on {what} - a stream needs ~5-10 GB while it is processed. "
                 "Delete old output folders (videos already uploaded) and run again.")
    if free < warn_gb:
        ui(f"WARNING: only {free:.1f} GB free on {what} - delete old output folders soon")


def render_need_gb(stream_len):
    """Rough disk need of a render: the pieces in every _work folder plus the finished videos, measured as 0.25 GB per minute
    of stream (owner priority #7, 2026-11-16). Never less than 5 GB - even a short stream writes cards, voice and a join."""
    return max(5.0, stream_len / 60.0 * 0.25)


def check_render_space(cfg, outroot, stream_len, kind="render"):
    """Before the FIRST video (and before the clips): stop now with the estimate instead of failing in the middle of a long
    render, and warn below twice the estimate. The pieces land in render_temp_dir when one is configured, else next to the
    finished videos."""
    need = render_need_gb(stream_len)
    tmp = str(cfg.get("render_temp_dir") or "").strip()
    where = Path(tmp).expanduser() if tmp else Path(outroot)
    if not where.exists():
        where = Path(outroot)
    try:
        free = shutil.disk_usage(where).free / 1e9
    except OSError:                                   # cannot read that drive: the render says what breaks soon enough
        return
    est = f"this {kind} needs about {need:.0f} GB ({stream_len / 60:.0f} min of stream x 0.25 GB)"
    if free < need:
        sys.exit(f"STOP BEFORE THE RENDER: {est}, but only {free:.1f} GB are free on {where}. Nothing was rendered yet - "
                 "delete old output folders (videos already uploaded) or set render_temp_dir to a drive with room, then run "
                 "again (finished videos of this run are kept and skipped).")
    if free < 2 * need:
        ui(f"WARNING: {est} and {free:.1f} GB are free on {where} - delete old output folders before this run gets long")


def ui(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def cause(e):
    """One line that names the cause AND where it happened: 'KeyError: 'in' (ucf/boundary.py:136)'. The team sends run_log.txt,
    so a skipped extra must leave enough in the log to find it without a traceback."""
    import traceback
    tb = traceback.extract_tb(e.__traceback__)
    at = f" ({Path(tb[-1].filename).name}:{tb[-1].lineno})" if tb else ""
    msg = (str(e).strip().splitlines() or [""])[-1][:160]     # last line: ffmpeg puts the real error there
    return f"{type(e).__name__}: {msg}{at}" if msg else f"{type(e).__name__}{at}"


def load_json(p, default):
    p = Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def save_json(p, d):
    Path(p).write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")


def run_file_stem(cfg):
    """<style>_<mode>[_min<N>]: the plan and the progress file of a run share this name, so an 8-min and a 5-min run (or
    another style / mode) never read each other's state."""
    extra = "" if cfg["_mode_label"] != "all" or cfg.get("min_case_minutes", 8) == 8 else "_min%g" % cfg["min_case_minutes"]
    return f"{cfg['style']}_{cfg['_mode_label']}{extra}"


def progress_path(work, cfg):
    """work/<id>/progress_<style>_<mode>.json, next to the plan. Clips get their own file: they share the all-cases plan but
    produce other folders (clip.mp4 instead of video.mp4)."""
    return Path(work) / f"progress_{run_file_stem(cfg)}{'_clips' if cfg.get('output_kind') == 'clips' else ''}.json"


def plan_fingerprint(plan):
    """Fingerprint of what the render makes from the plan (videos + cases). A changed plan invalidates the progress file -
    the same idea as the render-cache fingerprint in fresh_render_cache."""
    import hashlib
    return hashlib.sha1(json.dumps({"videos": plan.get("videos", []), "cases": plan.get("cases", [])},
                                   sort_keys=True, default=str).encode()).hexdigest()[:16]


def progress_load(path, plan, cfg, kind="video"):
    """Resume state of this run. A file of another H Labs version, another plan or the other output kind is dropped: its
    folders and render pieces no longer match what this run makes (owner priority #6, 2026-11-16)."""
    from ucf import __version__
    fp = plan_fingerprint(plan)
    d = load_json(path, {})
    if d.get("plan_fingerprint") == fp and d.get("hlabs_version") == __version__ and d.get("kind") == kind:
        return d
    if d.get("videos"):
        why = ("H Labs version changed" if d.get("hlabs_version") != __version__
               else "the plan changed" if d.get("plan_fingerprint") != fp else "another output kind")
        ui(f"  progress of an earlier run dropped ({why}) - every {kind} is made again")
    return {"hlabs_version": __version__, "plan_fingerprint": fp, "kind": kind, "style": cfg["style"],
            "mode": cfg.get("_mode_label", ""), "videos": {}}


def progress_mark(path, prog, n, **fields):
    """State of one video / clip (done | failed | pending) -> the file on disk, after every single one."""
    prog["videos"][str(n)] = dict(prog["videos"].get(str(n), {}), **fields, updated=time.strftime("%Y-%m-%d %H:%M:%S"))
    try:
        save_json(path, prog)
    except OSError as e:                              # a full / locked disk must not cost the finished video
        ui(f"  progress file not written ({e}) - a stopped run would start this {prog.get('kind', 'video')} again")


def progress_done(prog, n, folder, final="video.mp4"):
    """-> the entry when n is finished AND its file is still in the SAME folder, else None (then it is made again)."""
    e = (prog.get("videos") or {}).get(str(n)) or {}
    if e.get("state") != "done" or e.get("folder") != Path(folder).name:
        return None
    return e if (Path(folder) / final).exists() else None


def _usage_exit(work_holder):
    lines, _ = brain.usage_summary()
    if work_holder.get("dir"):
        brain.save_usage(Path(work_holder["dir"]) / "usage.json")
    if brain.USAGE:
        print("\n" + "\n".join(lines))
    if not CLOCK.T["printed"] and work_holder.get("dir"):     # the run stopped early (error / stage stop): still show the time
        print("\n" + "\n".join(CLOCK.lines(work_holder.get("stream_len", 0), status="stopped before the end")))
        if not work_holder.get("planned_stop") and work_holder.get("notify", True):
            FINISH.notify("H Labs stopped", f"{Path(work_holder['dir']).name}: the run stopped before the end - check the window", ok=False)


_WORK = {}
atexit.register(_usage_exit, _WORK)


STOP = "stop"          # a stage returns this when the run ends early (--stage, nothing to make)


class Run:
    """Everything one run carries from stage to stage (was ~25 local variables of a 600-line main)."""
    def __init__(self, a):
        self.a = a
        self.cfg = self.mode = self.root = self.state = self.stop = self.upto = None
        self.meta, self.sid, self.work, self.url, self.upload, self.stream_len = {}, None, None, "", "", 0
        self.video_path = self.source_file = self.sources = None
        self.segs, self.rep, self.scan_text, self.evidence = [], None, "", {}
        self.plan = self.plan_path = None
        self.carried, self.carry = [], []


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url", nargs="?")
    ap.add_argument("--config")
    ap.add_argument("--stage", choices=STAGES, help="run up to and including this stage")
    ap.add_argument("--plan", help="plan.json from Claude chat / earlier run")
    ap.add_argument("--video-file", help="already-downloaded stream (skips download)")
    ap.add_argument("--local", help="your own downloaded video OR a folder with it (+ its transcript, if you have one): skips the "
                                    "download; no transcript -> whisper makes one")
    ap.add_argument("--min-case", type=float, help="mode all / clips: shortest case (minutes of hearing) that gets its own video, "
                                                   "e.g. 5 or 8 (default from config: 8)")
    ap.add_argument("--transcript-file", help="transcript json/vtt (skips caption fetch)")
    ap.add_argument("--stream-id")
    ap.add_argument("--stream-length", help="H:MM:SS (needed only when --video-file has no readable duration)")
    ap.add_argument("--only", help="video numbers to render, e.g. 1,3")
    ap.add_argument("--confirm-tts", action="store_true")
    ap.add_argument("--brain", choices=["hive", "anthropic", "deepseek", "openai", "manual", "mock"])
    ap.add_argument("--style", help="editing style id from styles/<id>/style.json (e.g. trial_tales)")
    ap.add_argument("--mode", help="run mode: 30 (20-40 min videos) | 60 (50-70 min) | all (one video per case, ranked) | "
                                   "clips (one clean clip per case + editor guide, no overlays / voice / watermark) | "
                                   "asis (the WHOLE video re-edited as ONE video: no case selection, nothing skipped)")
    ap.add_argument("--tts", help="force one TTS provider (ai33|voicestudio|say|dummy)")
    ap.add_argument("--no-watermark", action="store_true", help="skip the anti-copy watermark for this run")
    ap.add_argument("--keep-source", action="store_true", help="keep the downloaded stream at the end (no cleanup)")
    ap.add_argument("--queued", action="store_true", help="part of a bulk queue: no per-stream notification / folder window "
                                                          "(the queue reports once at the end)")
    return ap.parse_args(argv)



def stage_setup(R):
    """Arguments -> config, mode, priority, paths (nothing touches the network yet)."""
    if R.a.local:                           # your own file / folder: same as --video-file (+ --transcript-file when one is there)
        from ucf import local_src
        try:
            _v, _t = local_src.resolve(R.a.local)
        except ValueError as e:
            sys.exit(f"STOP: {e}")
        R.a.video_file = str(_v)
        R.a.transcript_file = R.a.transcript_file or (str(_t) if _t else None)
        R.a.stream_id = R.a.stream_id or local_src.stream_id(_v)
        print(f"local video: {_v}\n  transcript: {_t or 'none - whisper will make one'}", flush=True)
    elif R.a.video_file and not R.a.stream_id:
        from ucf import local_src
        R.a.stream_id = local_src.stream_id(R.a.video_file)
    CLOCK.reset()
    CLOCK.stage("info")
    _WORK["planned_stop"] = bool(R.a.stage) and R.a.stage != "render"

    R.cfg = config.load(R.a.config, style=R.a.style)
    if R.a.queued:
        R.cfg["notify_when_done"] = False
        R.cfg["open_output_after_run"] = False
    if R.a.keep_source:
        R.cfg["cleanup_after_run"] = "never"
    _WORK["notify"] = R.cfg.get("notify_when_done", True)
    from ucf import load as LOAD
    _prio = LOAD.lower_priority(R.cfg)                     # ffmpeg / whisper children inherit it: the PC stays responsive
    if R.a.brain:
        R.cfg["brain"] = R.a.brain
        R.cfg["brain_pass_a"] = R.cfg["brain_pass_b"] = ""   # an explicit --brain runs every pass on that brain
    if R.a.tts:
        R.cfg["tts_order"] = [R.a.tts]
    if R.a.no_watermark:
        R.cfg["watermark"] = False
    if R.a.mode == "clips":                 # clips only: the brain works exactly as mode "all", the output is clips + editor guides
        R.cfg["output_kind"] = "clips"
        R.a.mode = "all"
    if R.a.mode == "asis":                  # as-is re-edit: the brain + render of mode "all", with the whole video as ONE case
        R.cfg["_asis"] = True
        R.a.mode = "all"
    R.mode = config.apply_mode(R.cfg, R.a.mode)
    # after apply_mode: mode "all" sets its own 8:00 default, the run's choice wins over it
    if R.cfg.get("_asis"):
        R.cfg["min_case_minutes"] = 0.0
    elif R.a.min_case:
        R.cfg["min_case_minutes"] = float(R.a.min_case)
    R.cfg["_mode_label"] = "asis" if R.cfg.get("_asis") else R.mode
    if R.cfg.get("face_precheck") is False:      # config.local.json can switch the cheap face pre-check off per PC
        os.environ["HL_FACE_PRECHECK"] = "0"
    band = (f"{R.cfg['runtime_min'] // 60}-{R.cfg['runtime_max'] // 60} min" if R.mode != "all"
            else "the whole video as ONE edited video (as-is, no case selection)" if R.cfg.get("_asis")
            else f"one video per case >= {R.cfg.get('min_case_minutes', 8):g} min")
    # keep the active model in sync with the chosen provider unless the config pinned a custom one
    if R.cfg["brain"] in brain.PROVIDERS and R.cfg.get("model") == config.DEFAULTS["model"]:
        R.cfg.update(brain.cfg_for(R.cfg, R.cfg["brain"]))
    ui(f"style: {R.cfg['style']}  ({config.style_path(R.cfg)})  |  mode: {R.cfg['_mode_label']}  |  band: {band}")
    ui(f"load: priority {_prio or 'normal'}, CPU threads {LOAD.cpu_threads(R.cfg)} of {os.cpu_count()}"
       "  (config process_priority / cpu_threads)")
    R.root = config.ROOT
    R.state = R.root / R.cfg["state_dir"]
    R.state.mkdir(exist_ok=True)
    R.stop = R.a.stage or "render"
    R.upto = STAGES.index(R.stop)



def stage_info(R):
    """Stream info (title, length, id), work folder + run log, court line."""
    # ---------------- info ----------------
    R.meta = {}
    if R.a.url:
        try:
            R.meta = download.info(R.a.url, R.cfg) if not R.a.video_file else {}
        except (RuntimeError, OSError, ValueError) as e:        # yt-dlp refused / not installed / returned no JSON
            if not R.a.stream_id:
                sys.exit(f"ERROR: {e}")
            ui(f"  stream info skipped: {cause(e)} - going on with --stream-id {R.a.stream_id} (title / date from the saved meta.json)")
    R.sid = R.a.stream_id or R.meta.get("id") or (Path(R.a.video_file).stem if R.a.video_file else None)
    if not R.sid:
        sys.exit("give a URL (or --video-file + --stream-id)")
    R.work = R.root / R.cfg["work_dir"] / R.sid
    _WORK["dir"] = R.work
    R.work.mkdir(parents=True, exist_ok=True)
    if not isinstance(sys.stdout, _Tee):
        sys.stdout = _Tee(sys.stdout, R.work / "run_log.txt")
        sys.stderr = _Tee(sys.stderr, R.work / "run_log.txt")      # errors / tracebacks too
    check_disk(R.work)
    if R.meta:
        save_json(R.work / "meta.json", R.meta)
        ui(f"stream: {R.meta['title']}  ({fmt_dur(R.meta['duration'])}, id {R.sid})")
        if R.meta.get("is_live"):
            sys.exit("This stream is still LIVE. Run again after it ends (VOD) so the file is complete.")
    else:
        R.meta = load_json(R.work / "meta.json", {})
        if R.a.video_file and Path(R.a.video_file).exists() and not R.meta.get("title"):
            # your own file: title + length from the file (the title also gives the court line when it names one)
            R.meta = {"id": R.sid, "title": Path(R.a.video_file).stem, "duration": tts.dur(R.a.video_file),
                    "local_file": str(Path(R.a.video_file).resolve())}
            save_json(R.work / "meta.json", R.meta)
        if R.meta.get("title"):
            ui(f"stream: {R.meta['title']}  ({fmt_dur(R.meta['duration'])}, id {R.sid})")
    R.url = R.meta.get("url") or R.a.url or ""
    R.upload = R.meta.get("upload_date", "") or time.strftime("%Y%m%d")
    R.stream_len = R.meta.get("duration") or (parse_tc(R.a.stream_length) if R.a.stream_length else 0)
    # court for the on-screen court line, from the stream title ("... /187TH DISTRICT COURT/ ...") - never a judge's name
    _cm = re.search(r"(\d{1,3})\s*(st|nd|rd|th)\s+district\s+court", R.meta.get("title") or "", re.I)
    R.cfg["court"] = f"{_cm.group(1)}{_cm.group(2).lower()} District Court" if _cm else R.cfg.get("court", "District Court")
    _WORK["stream_len"] = R.stream_len



def stage_download(R):
    """The source video: download, or the saved / own file (re-download when a better copy exists)."""
    # ---------------- download ----------------
    R.video_path = Path(R.a.video_file) if R.a.video_file else R.work / "source.mp4"
    if R.upto >= 1 and not R.video_path.exists():
        CLOCK.stage("download")
        ui("downloading stream (this is the slow part)...")
        R.video_path = download.fetch_video(R.url, R.sid, R.work, R.cfg, R.meta)
    elif R.video_path.exists() and R.upto >= 1:
        ui(download.describe(R.video_path)[0])       # cached download: show its quality (an old one may be the starved H.264 copy)
        why = "" if R.a.video_file else download.worse_than_available(R.video_path, R.meta, int(R.cfg.get("min_height", 720)))
        if why and R.url:
            # an older run downloaded a worse copy (360p / starved H.264): get the real quality, keep the old file if that fails
            CLOCK.stage("download")
            ui(f"the saved download is {why} - downloading the full quality again (transcript and plan are kept)...")
            old = R.work / "source_old.mp4"
            os.replace(R.video_path, old)
            try:
                R.video_path = download.fetch_video(R.url, R.sid, R.work, R.cfg, R.meta)
                old.unlink()
            except (RuntimeError, OSError) as e:
                os.replace(old, R.video_path)
                if download.probe_video(R.video_path)[0] < int(R.cfg.get("min_height", 720)) - 10:
                    sys.exit(f"STOP: the saved copy is below {R.cfg.get('min_height', 720)}p and a better one could not be downloaded:\n"
                             f"  {str(e).splitlines()[0][:300]}")
                ui(f"  re-download failed ({str(e).splitlines()[0][:120]}) - continuing with the saved copy")
    if R.video_path.exists() and not R.stream_len:
        R.stream_len = tts.dur(R.video_path)
    R.source_file = f"{R.sid}.mp4"
    R.sources = load_json(R.state / "sources.json", {})
    _prev = R.sources.get(R.source_file, {})
    R.sources[R.source_file] = {"path": str(R.video_path.resolve()) if R.video_path.exists() else str(R.video_path), "url": R.url}
    if _prev.get("clips"):   # pre-cut clip source: keep the clip map, the "path" is just the first clip
        R.sources[R.source_file] = dict(_prev, url=R.url or _prev.get("url", ""))
    save_json(R.state / "sources.json", R.sources)
    if R.upto < IX["transcript"]:
        return ui("stopped after", R.stop) or STOP



def stage_transcript(R):
    """YouTube captions, else whisper (own transcript file wins)."""
    # ---------------- transcript ----------------
    _WORK["stream_len"] = R.stream_len
    CLOCK.stage("transcript")
    tpath = R.work / "transcript.json"
    if R.a.transcript_file:
        R.segs = transcript.load_any(R.a.transcript_file)
        transcript.save(R.segs, tpath)
    elif tpath.exists() and not (R.work / "transcript.sparse").exists():   # .sparse: captions-only fallback -> try whisper again
        R.segs = json.loads(tpath.read_text(encoding="utf-8"))
    else:
        R.segs = []
        if R.cfg["captions"] == "auto" and R.url:
            ui("fetching YouTube captions...")
            f = download.fetch_captions(R.url, R.work, R.cfg)
            if f:
                R.segs = transcript.load_any(f)
        spoken_wpm = (sum(len(s["text"].split()) for s in R.segs) / max(R.stream_len / 60.0, 1)) if R.segs else 0
        if spoken_wpm < 15:   # missing / sparse captions
            ui("captions missing or sparse -> whisper (slow, CPU)...")
            from ucf.load import cpu_threads
            try:
                R.segs = transcript.whisper_safe(R.video_path, R.cfg["whisper_model"], threads=cpu_threads(R.cfg), ui=ui)
            except RuntimeError as e:
                if not R.segs:
                    raise
                ui(f"WARNING: {e}\n  -> going on with the YouTube captions ({len(R.segs)} lines, {spoken_wpm:.0f} words/min). "
                   "Case times may be rougher; check the videos.")
                (R.work / "transcript.sparse").write_text("captions only - whisper failed", encoding="utf-8")
            else:
                (R.work / "transcript.sparse").unlink(missing_ok=True)
        transcript.save(R.segs, tpath)
    ui(f"transcript: {len(R.segs)} segments, ends {fmt_tc(R.segs[-1]['end']) if R.segs else '-'}")
    if R.upto < IX["scan"]:
        return ui("stopped after", R.stop) or STOP



def stage_scan(R):
    """Candidate case starts + dead air; boundary evidence for the brain."""
    # ---------------- scan ----------------
    CLOCK.stage("scan + evidence")
    R.rep = scan.report(R.segs, R.stream_len)
    R.scan_text = scan.report_text(R.rep)
    (R.work / "scan.txt").write_text(R.scan_text, encoding="utf-8")
    ui(f"scan: {len(R.rep['clusters'])} candidate case starts, {len(R.rep['dead_air'])} dead-air stretches")
    if R.upto < IX["evidence"]:
        return ui("stopped after", R.stop) or STOP

    # -------- evidence (v10 boundary signals; transcript-level here, video-level lazily) --------
    R.evidence = {}
    if (R.cfg.get("boundary") or {}).get("enabled", True):
        try:
            from ucf import evidence as EV
            R.evidence = EV.build(R.video_path if R.video_path.exists() else None, R.segs, R.rep, R.cfg, R.work)
            ui(f"evidence: {len(R.evidence['call_outs'])} call-outs, {len(R.evidence['wrap_up'])} wrap-ups, "
               f"{len(R.evidence['ruling'])} rulings, ocr={R.evidence['ocr_engine'] or 'off'}")
        except Exception as e:  # noqa - best effort for the brain prompt: the plan is made without video signals
            ui(f"  evidence skipped: {cause(e)} - the brain plans from the transcript alone")
    if R.upto < IX["plan"]:
        return ui("stopped after", R.stop) or STOP



def stage_plan(R):
    """The brain's plan (or a saved one), validation, plan report, contact sheet, carry-forward."""
    # ---------------- plan ----------------
    CLOCK.stage("brain (plan)")
    # one plan per style + mode: titles follow the style's own rules and a bundle plan is not an all-cases plan, so a stream run
    # again in another style / mode must not reuse the first plan (it failed the validator: "CAPS word ... not in this style's
    # banks"). Clips use the all-cases plan of the same style.
    R.plan_path = Path(R.a.plan) if R.a.plan else R.work / f"plan_{run_file_stem(R.cfg)}.json"
    R.carried = [] if R.mode == "all" else load_json(R.state / "carry_forward.json", [])
    inputs = {"source_file": R.source_file, "stream_length": fmt_tc(R.stream_len), "channel_name": R.cfg["channel_name"]}
    lines = transcript.compact_lines(R.segs)
    prompt = brain.build_prompt(inputs, R.scan_text, lines, R.carried, R.cfg)
    (R.work / "prompt_for_claude.txt").write_text(prompt, encoding="utf-8")
    if not R.plan_path.exists():
        if R.mode == "all":
            if os.environ.get("HL_PASSA_REPLY"):       # resume: replay a saved Pass A reply, live Pass B
                R.cfg["mock_passA_replies"] = [os.environ["HL_PASSA_REPLY"]]
            if R.cfg["brain"] == "manual":
                sys.exit(f"MANUAL BRAIN (mode all): 1) paste {R.work / 'prompt_A.txt'} into Claude, save its JSON reply "
                         f"as {R.work / 'plan_A.json'}, 2) rerun with --plan {R.work / 'plan_A.json'} (the script then "
                         f"writes one prompt_B_<case>.txt per case; package each the same way and merge).")
            from ucf import mode_all
            R.cfg["_source_file"] = R.source_file
            if not lines:
                sys.exit("transcript is empty - mode all cannot run")
            try:
                R.plan, errs = mode_all.build_plan(R.segs, lines, R.scan_text, R.stream_len, R.cfg, ui, R.work, scan_rep=R.rep,
                                                 video_path=R.video_path if R.video_path.exists() else None)
            except brain.BrainStop as e:
                sys.exit(f"BRAIN STOPPED: {e}\n  replies: work/{R.sid}/brain_reply_*.txt")
            if R.plan is not None and errs and str(errs[0]).startswith("no case reached"):
                # not an error of the tool: this stream simply has no case long enough for its own video
                mc = R.cfg.get("min_case_minutes", 8)
                def _len(c):
                    try:
                        return parse_tc(c["out"]) - parse_tc(c["in"])
                    except (KeyError, TypeError, ValueError):
                        return 0
                cs = sorted(R.plan.get("cases", []), key=lambda c: -_len(c))
                ui(f"NOTHING TO MAKE: no case in this stream has {mc:.0f}:00 or more of hearing (rule for one video per case).")
                for c in cs[:8]:
                    ui(f"   {c.get('name', '?'):<28} {c.get('in')}-{c.get('out')}  {fmt_dur(_len(c)):>6}  {c.get('status')}"
                       + (f"  ({c.get('reject_reason')})" if c.get("reject_reason") else ""))
                ui("   -> try the 30 min / 1 hour mode (several short cases in one video), or another stream.")
                sys.exit(0 if R.a.queued else 2)
            if R.plan is None or errs:
                sys.exit(f"mode-all plan failed: {errs[:3] if errs else 'no plan'} - see work/{R.sid}/brain_reply_A_*.txt")
            save_json(R.plan_path, R.plan)
            errs, warns = VAL.validate(R.plan, R.stream_len, R.segs, R.cfg)
        else:
            if R.cfg["brain"] == "manual":
                sys.exit(f"MANUAL BRAIN: paste {R.work / 'prompt_for_claude.txt'} into Claude, save its JSON reply as "
                         f"{R.work / 'plan.json'} and run again (or pass --plan file.json).")
            fb = R.cfg.get("brain_fallback") or ""
            fb = fb if fb and fb != R.cfg["brain"] and R.cfg["brain"] != "mock" else ""
            try:
                R.plan, errs, warns = brain.make_plan(prompt, R.stream_len, R.segs, R.cfg, ui, save_dir=R.work)
            except (brain.BrainStop, RuntimeError) as e:
                if not fb:
                    sys.exit(f"BRAIN STOPPED: {e}\n  replies: work/{R.sid}/brain_reply_*.txt")
                R.plan, errs, warns = None, [str(e)], []
            if (R.plan is None or errs) and fb:
                ui(f"  {R.cfg['brain']} could not produce a valid plan ({(errs or ['no plan'])[0][:100]}) "
                   f"-> falling back to {fb}")
                try:
                    R.plan, errs, warns = brain.make_plan(prompt, R.stream_len, R.segs, brain.cfg_for(R.cfg, fb), ui,
                                                        save_dir=R.work, tag="fb_")
                except brain.BrainStop as e:
                    sys.exit(f"BRAIN STOPPED: {e}\n  replies: work/{R.sid}/brain_reply_*.txt")
            if R.plan is None:
                sys.exit(f"brain '{R.cfg['brain']}' never returned valid JSON - see work/*/brain_reply_*.txt")
            save_json(R.plan_path, R.plan)
    else:
        try:
            R.plan = json.loads(R.plan_path.read_text(encoding="utf-8"))
        except ValueError as e:
            sys.exit(f"STOP: {R.plan_path} is not valid JSON ({e}) - fix the file or delete it so the brain plans again")
        # shape check first (a missing "in" used to surface as a KeyError in the middle of the render), rules after
        from ucf import schema
        bad = schema.check_plan(R.plan)
        if bad:
            sys.exit(f"STOP: the plan {R.plan_path} has the wrong shape:\n  " + "\n  ".join(b.removeprefix("ERROR: ") for b in bad[:12])
                     + "\n  -> fix the file (or delete it so the brain plans again); send work/" + f"{R.sid}/run_log.txt if unsure")
        R.plan["source_file"] = R.plan.get("source_file") or R.source_file
        errs, warns = VAL.validate(R.plan, R.stream_len, R.segs, R.cfg)
    R.plan["source_file"] = R.source_file if R.plan.get("source_file") != R.source_file else R.plan["source_file"]
    # bundle modes: boundary refinement applies too (spec 7), but reverts if it breaks validation
    if R.mode != "all" and R.evidence and R.video_path.exists() and (R.cfg.get("boundary") or {}).get("enabled", True):
        try:
            import copy
            from ucf import boundary as BD
            snapshot = copy.deepcopy(R.plan)
            BD.refine_plan(R.plan, R.evidence, R.video_path, R.cfg, R.work, ui)
            errs, warns = VAL.validate(R.plan, R.stream_len, R.segs, R.cfg)
            if errs:
                R.plan = snapshot
                errs, warns = VAL.validate(R.plan, R.stream_len, R.segs, R.cfg)
                ui("boundary refinement reverted (introduced validation errors)")
        except Exception as e:  # noqa - the brain's OUT times stand (the validator passed them); say what broke
            R.plan = snapshot
            errs, warns = VAL.validate(R.plan, R.stream_len, R.segs, R.cfg)
            ui(f"  boundary refinement skipped: {cause(e)} - the brain's case OUT times are used as they are")
    report = [f"PLAN REPORT  {R.sid}", f"stream {fmt_tc(R.stream_len)}  cases {len(R.plan['cases'])}  videos {len(R.plan['videos'])}"]
    st = R.plan.get("_stats", {})
    if st:
        report.append("minutes: found {} = used {} + carried {} + rejected {}  | unmapped stream time {}".format(
            fmt_dur(st["found"]), fmt_dur(st["used"]), fmt_dur(st["carried"]), fmt_dur(st["rejected"]), fmt_dur(st["unmapped"])))
    report += ["", "ERRORS (block the render):"] + ([f" - {e}" for e in errs] or [" none"])
    report += ["", "WARNINGS:"] + ([f" - {w}" for w in warns] or [" none"])
    for c in R.plan["cases"]:
        why = "" if c.get("status") == "used" else (c.get("reject_reason") or "")
        report.append(f"  case {c['id']:>2} {c['name']:<24} {c['in']}-{c['out']} = {fmt_dur(c.get('_dur', 0)):>6}  {c['status']}"
                      + (f"  ({why[:90]})" if why else ""))
    (R.work / "plan_report.txt").write_text("\n".join(report), encoding="utf-8")
    save_json(R.plan_path, R.plan)
    print("\n".join(report))
    if errs:
        sys.exit("\nPlan has errors - fix the plan (or rerun the brain) before rendering. See plan_report.txt")
    # contact sheet of case boundaries (cheap) - look at it BEFORE the long render
    if R.video_path.exists():
        try:
            rn = Renderer(R.cfg, R.sources, R.root)
            frames, labels = [], []
            fd = R.work / "plan_frames"
            fd.mkdir(exist_ok=True)
            for c in R.plan["cases"]:
                for tag, tc in (("IN", c["in"]), ("OUT", c["out"])):
                    p = fd / f"c{c['id']}_{tag}.jpg"
                    import subprocess
                    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(max(0, parse_tc(tc) - (1 if tag == 'OUT' else 0))),
                                    "-i", str(R.video_path), "-frames:v", "1", "-vf", "scale=480:270", "-q:v", "4", str(p)])
                    frames.append(p)
                    labels.append(f"#{c['id']} {c['name'][:18]} {tag} {tc}")
            cards.contact_sheet(frames, labels, R.work / "contact_plan.jpg")
            ui("contact sheet of every case IN/OUT:", R.work / "contact_plan.jpg")
        except Exception as e:  # noqa - a preview only; the plan and the render do not depend on it
            ui(f"  contact sheet skipped: {cause(e)} - check case IN/OUT in plan_report.txt instead")
    # carry forward state (mode all never touches it)
    R.carry = [c for c in R.plan["cases"] if c["status"] == "carried"] if R.mode != "all" else []
    for c in R.carry:
        c["source_file"] = c.get("source_file") or R.source_file
    old = [c for c in R.carried if not any(c["name"] == n["name"] and c.get("source_file") == n.get("source_file") for n in R.carry)
           and not any(c.get("source_file") == R.source_file for _ in [0])]
    save_json(R.state / "carry_forward.json", R.carry + [c for c in old if c.get("source_file") != R.source_file])
    if R.mode == "all":
        from ucf import mode_all
        mode_all.write_ranking(R.plan, R.work, R.cfg, R.sid)
        ui("ranking drafted:", R.work / "ranking.md")
    if R.upto < IX["render"]:
        return ui("stopped after plan. Review plan_report.txt + contact_plan.jpg, then run again without --stage.") or STOP



def stage_render(R):
    """Every video of the plan (or the clips), QC, reports, notification, cleanup."""
    # ---------------- render ----------------
    CLOCK.stage("render setup")
    # owner rule 2026-11-13: voice-over + on-screen text say "the judge", never the judge's name (other judges' dockets too);
    # titles / description / tags keep the name. A safety net on top of the prompt rule.
    from ucf.judge_neutral import judge_names, neutralize
    _jn = neutralize(R.plan, judge_names(R.plan.get("judge_name"), R.cfg.get("judge_name"), R.meta.get("title")))
    if _jn:
        ui(f"judge-neutral: {_jn} voice-over / on-screen text(s) now say 'the judge' instead of the name")
    only = {int(x) for x in R.a.only.split(",")} if R.a.only else None
    if os.environ.get("HL_STUDIO"):
        print(f"@@videos {sum(1 for v in R.plan['videos'] if not only or v['n'] in only)}", flush=True)
    if R.cfg.get("output_kind") == "clips":
        return clips_output(R, only)
    # cross-channel reuse guard (spec 9.5): warn, never block
    if R.cfg.get("reuse_guard", True):
        used_log = load_json(R.state / "used_cases.json", [])
        hits = [u for u in used_log if u.get("stream_id") == R.sid and u.get("style") != R.cfg["style"]]
        for u in hits:
            ui(f"REUSE WARNING: {u.get('name', '?')} already used on {u.get('style')} ({u.get('date', '?')}) "
               f"- YouTube may treat this as reused content")
        if hits:
            warn_line = "; ".join(f"{u.get('name')}@{u.get('style')}" for u in hits)
            (R.work / "plan_report.txt").open("a").write(f"\nREUSE WARNING: {warn_line}\n")
    need = tts.chars_needed(R.plan, only, tt=R.cfg.get('_renderer') == 'tt')
    ui(f"voiceover characters this run: {need}")
    if need > R.cfg["tts_confirm_chars"] and not R.a.confirm_tts:
        sys.exit(f"STOP: {need} characters of TTS is over the {R.cfg['tts_confirm_chars']} limit. "
                 f"Confirm with Sardar in chat, then rerun with --confirm-tts.")
    stamp = f"{R.upload[:4]}-{R.upload[4:6]}-{R.upload[6:8]}" if len(R.upload) == 8 else R.upload
    outroot = R.root / R.cfg["output_dir"] / f"{stamp}_{R.sid}"
    outroot.mkdir(parents=True, exist_ok=True)
    by_id = {c["id"]: c for c in R.plan["cases"]}
    _sj = json.loads((config.style_path(R.cfg) / "style.json").read_text(encoding="utf-8"))
    if _sj.get("renderer_module"):          # a style pack that ships its own renderer (e.g. Court Beacon TV)
        import importlib.util
        _spec = importlib.util.spec_from_file_location("style_renderer", config.style_path(R.cfg, _sj["renderer_module"]))
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        rn = getattr(_mod, _sj.get("renderer_class", "Renderer"))(R.cfg, R.sources, R.root)
    elif R.cfg.get("_look") == "ov":
        from ucf.render_ov import OVRenderer
        rn = OVRenderer(R.cfg, R.sources, R.root)
    else:
        rn = (TTRenderer if R.cfg.get("_renderer", "tt") == "tt" else Renderer)(R.cfg, R.sources, R.root)
    from ucf.render import _HW
    from ucf import render as RND
    ui(f"encoder: {rn.enc}  |  decode: {('GPU (' + _HW['name'] + ')') if _HW['name'] else 'CPU'}")
    RND.warn_low_vram(ui)
    summary, rows, failed_videos = [], [], []
    todo = [v for v in R.plan["videos"] if not only or v["n"] in only]
    # resume (owner priority #6, 2026-11-16): a video finished by an earlier, stopped run of this plan is reused. --only always
    # renders what it names, so it ignores the file.
    ppath = progress_path(R.work, R.cfg)
    prog = progress_load(ppath, R.plan, R.cfg)
    folders = {}
    for v in todo:
        lead_ = by_id[v["case_ids"][0]]
        pfx = f"{v.get('rank', v['n']):02d}" if R.mode == "all" else f"Video_{v['n']:02d}"
        folders[v["n"]] = outroot / f"{pfx}_{safe_slug(lead_['name'], 24)}"
    reused = {v["n"]: progress_done(prog, v["n"], folders[v["n"]]) for v in todo} if not only else {}
    reused = {n: e for n, e in reused.items() if e}
    if reused and os.environ.get("HL_STUDIO"):
        print(f"@@resumed {len(reused)}", flush=True)
    todo = [v for v in todo if v["n"] not in reused]
    if todo:
        check_render_space(R.cfg, outroot, R.stream_len * len(todo) / max(1, len(R.plan["videos"])))
    if len(todo) > 1:
        # the AI voice of the NEXT videos is made in the background while the GPU renders this one (network wait no longer
        # sits in the render). Exactly the lines the renderer asks for (cache hits later: no extra credits); one line is never
        # made twice at the same time (ucf.tts locks). A failure here is ignored - the renderer then makes that line itself.
        import threading

        def _prefetch_vo(videos):
            for pv in videos:
                try:
                    ids_, brs = pv["case_ids"], {b["after_case_id"]: b for b in pv.get("bridges", [])}
                    for i_ in range(len(ids_) - 1):
                        if ids_[i_] in brs:
                            tts.synth_clips(brs[ids_[i_]]["text"], R.work / "tts", R.cfg, lambda *m: None)
                    tts.synth_clips(pv["vo_final"]["text"], R.work / "tts", R.cfg, lambda *m: None)
                except Exception as e:  # noqa - the renderer makes that line itself (and reports if that fails too)
                    ui(f"  voice prefetch for video {pv.get('n', '?')} skipped: {cause(e)}")
        threading.Thread(target=_prefetch_vo, args=(todo[1:],), daemon=True, name="vo-prefetch").start()
    n_all = len(R.plan["videos"])
    for v in R.plan["videos"]:
        if only and v["n"] not in only:
            continue
        lead = by_id[v["case_ids"][0]]
        folder = folders[v["n"]]
        if v["n"] in reused:                         # finished by the earlier run: counted as done, not rendered again
            qc_ = load_json(folder / "qc.json", {})
            e = reused[v["n"]]
            secs = float(e.get("seconds") or qc_.get("duration") or 0)
            ok_ = bool(qc_.get("ok", e.get("qc") == "OK"))
            ui(f"video {v['n']}/{n_all} already done ({fmt_dur(secs)}, QC {'OK' if ok_ else 'CHECK'}) - skipping; "
               f"--only {v['n']} forces it again")
            summary.append((v["n"], folder.name, secs, ok_))
            rows.append((v["n"], folder.name, secs, ok_, v, qc_))
            continue
        folder.mkdir(exist_ok=True)
        progress_mark(ppath, prog, v["n"], state="pending", folder=folder.name)
        try:
            ui(f"VIDEO {v['n']}: {[by_id[i]['name'] for i in v['case_ids']]}")
            CLOCK.stage(f"video {v['n']} render")
            _t_video = time.time()
            rn.log, rn.notes = [], []
            fresh_render_cache(folder, R.cfg, v, [by_id[i] for i in v["case_ids"]])
            from ucf import watermark as WM
            wm_text, wm_err = None, None
            try:                                         # the watermark is drawn inside every segment encode (one pass less)
                wmf = WM.segment_finish(R.cfg, f"{R.sid}:{v['n']}", folder)
            except Exception as e:                       # no PNG -> the old full-video pass below
                wmf = None
                ui(f"  watermark inside the render not possible ({str(e)[:120]}) - adding it in a separate pass")
            RND.set_finish(wmf)
            try:
                res = rn.render_video(R.plan, v, folder, R.work / "tts", ui)
                fin = dict(RND._FINISH)
            finally:
                RND.set_finish(None)
            if wmf and not fin["missed"]:
                wm_text = wmf["text"]
                ui(f"  watermark '{wm_text}' drawn inside the render ({fin['applied']} new piece(s))")
            elif WM.enabled(R.cfg):
                try:                                     # old way: one more pass over the whole video (safety net)
                    if fin.get("missed"):
                        ui(f"  {fin['missed']} piece(s) could not take the watermark inside the render - separate pass")
                    wm_text = WM.apply_in_place(res["final"], R.cfg, f"{R.sid}:{v['n']}", rn.enc, ui)
                except Exception as e:                   # never lose the render over a watermark problem, but flag it
                    wm_err = str(e).splitlines()[0][:160] if str(e) else repr(e)
                    ui(f"  WATERMARK FAILED: {wm_err}  (video.mp4 is the un-watermarked render)")
            notes = list(getattr(rn, "notes", []))   # extras the renderer skipped (overlays, captions): go into qc.json
            try:
                rn.thumbnail(R.plan, v, folder)
            except Exception as e:  # noqa - the video is done; a thumbnail can be made by hand from thumbnail_candidates/
                ui(f"  thumbnail skipped: {cause(e)} - pick a frame from {folder.name}/thumbnail_candidates by hand")
                notes.append("thumbnail skipped: " + cause(e))
            tl = res["timeline"]
            (folder / "edit_sheet.txt").write_text(sheets.edit_sheet(R.plan, v, tl, res["durs"]), encoding="utf-8")
            md, chs = sheets.metadata(R.plan, v, tl, R.cfg, R.url)
            (folder / "metadata.txt").write_text(md, encoding="utf-8")
            rn.write_footage_log(folder / "footage_log.csv")
            try:
                rn.contact_sheet(res["final"], res["rows"], folder / "contact_sheet.jpg")
            except Exception as e:  # noqa - a preview of the finished video only
                ui(f"  contact sheet skipped: {cause(e)}")
                notes.append("contact sheet skipped: " + cause(e))
            qc = rn.qc(res["final"], res["measured_total"])
            if notes:
                qc["ok"] = False
                qc["note"] = "; ".join(notes)
            if res.get("ai_clips"):
                qc["ai_clip_seconds"] = res["ai_clips"]
                qc["ai_clips_ok"] = max(res["ai_clips"]) <= R.cfg.get("vo_clip_max", 18.0)
                qc["ok"] = qc["ok"] and qc["ai_clips_ok"]
            qc["chapters"] = [(fmt_tc(o, False), l) for o, l in chs]
            qc["watermark"] = wm_text or False
            if wm_err:
                qc["ok"] = False
                qc["note"] = "; ".join(filter(None, [qc.get("note"), "watermark failed: " + wm_err]))
            if chs and chs[-1][0] > res["measured_total"] - 60:
                qc["ok"] = False
                qc["note"] = "; ".join(filter(None, [qc.get("note"), "a chapter sits in the final 60 s"]))
            qc["processing_seconds"] = round(time.time() - _t_video)
            save_json(folder / "qc.json", qc)
            save_json(folder / "video_plan.json", {"video": v, "cases": [by_id[i] for i in v["case_ids"]]})
            log = load_json(R.state / "used_cases.json", [])
            log.append({"stream_id": R.sid, "cause_no": lead.get("cause_no", ""), "name": lead.get("name", ""),
                        "in": lead.get("in", ""), "out": lead.get("out", ""), "style": R.cfg["style"],
                        "mode": R.cfg.get("_mode_label", R.cfg.get("mode", "")), "folder": folder.name, "date": time.strftime("%Y-%m-%d")})
            save_json(R.state / "used_cases.json", log)
            shutil.rmtree(folder / "_work" / "frames", ignore_errors=True)
            ui(f"  done: {res['final']}  {fmt_dur(res['measured_total'])}  QC {'OK' if qc['ok'] else 'CHECK'}  {qc['loudness_lufs']} LUFS"
               f"  (took {CLOCK.hms(qc['processing_seconds'])})")
            summary.append((v["n"], folder.name, res["measured_total"], qc["ok"]))
            rows.append((v["n"], folder.name, res["measured_total"], qc["ok"], v, qc))
            progress_mark(ppath, prog, v["n"], state="done", folder=folder.name, qc="OK" if qc["ok"] else "CHECK",
                          seconds=round(res["measured_total"], 1), processing_seconds=qc["processing_seconds"])
        except KeyboardInterrupt:
            raise
        except Exception as e:                      # one broken video must not cost the others (2026-11-05: an ai33 timeout)
            import traceback
            traceback.print_exc()
            why = cause(e)
            progress_mark(ppath, prog, v["n"], state="failed", folder=folder.name, error=why[:200])
            ui(f"  VIDEO {v['n']} FAILED: {why} - going on with the next video (rerun later: --only {v['n']})")
            failed_videos.append((v['n'], folder.name, why))
    CLOCK.stage("report")
    carry_txt = ["CARRIED FORWARD (state/carry_forward.json): " + (brain.carried_text(R.carry) if R.carry else "none")]
    if R.mode == "all":
        carry_txt = ["carry-forward: not used in mode all"]
        from ucf import mode_all
        mode_all.write_ranking(R.plan, outroot, R.cfg, R.sid)
    R.rep = [f"RUN REPORT {R.sid} - {time.strftime('%Y-%m-%d %H:%M')}", ""] + \
          [f"Video {n}: {f}  {fmt_dur(d)}  QC {'OK' if ok else 'CHECK'}" for n, f, d, ok in summary] + \
          [f"Video {n}: {f}  FAILED - {why}  (rerun only this one: --only {n})" for n, f, why in failed_videos] + [""] + carry_txt
    ulines, ut = brain.usage_summary()
    brain.save_usage(outroot / "usage.json")
    n_made = len(summary) - len(reused)                # reused videos cost this run neither time nor money
    if ut.get("cost") is not None and n_made:
        ulines.append(f"  per video  ${ut['cost'] / max(1, n_made):.2f}  ({n_made} videos made this run)")
    R.rep += [""] + ulines
    if reused:
        R.rep.insert(1, f"{len(reused)} video(s) reused from the earlier run (not rendered again): "
                        + ", ".join(str(n) for n in sorted(reused)))
    status = (f"{len(failed_videos)} video(s) FAILED" if failed_videos
              else "completed" if all(ok for *_, ok in summary) else "completed, some QC CHECK")
    R.rep += [""] + CLOCK.lines(R.stream_len, n_made, status)
    CLOCK.history(R.state / "run_history.csv", stream_id=R.sid, style=R.cfg["style"], mode=R.cfg.get("_mode_label", R.mode), encoder=rn.enc,
                  stream_min=round(R.stream_len / 60, 1), videos=n_made, qc_ok=sum(1 for *_, ok in summary if ok),
                  cost_usd=round(ut.get("cost") or 0, 3))
    (outroot / "run_report.txt").write_text("\n".join(R.rep), encoding="utf-8")
    shutil.copy(R.plan_path, outroot / "plan.json")
    shutil.copy(R.work / "plan_report.txt", outroot / "plan_report.txt")
    ulist = FINISH.upload_list(R.plan, rows, outroot)
    print("\n".join(R.rep))
    ui("upload list:", ulist)
    ui("ALL DONE ->", outroot)
    n_ok = sum(1 for *_, ok in summary if ok)
    n_rev = sum(1 for c in R.plan.get("cases", []) if c.get("needs_review"))
    if R.cfg.get("notify_when_done", True):
        FINISH.notify("H Labs - done", f"{R.sid}: {len(summary)} videos ({n_ok} QC OK"
                      + (f", {len(reused)} reused" if reused else "")
                      + (f", {len(failed_videos)} FAILED" if failed_videos else "")
                      + (f", {n_rev} need review" if n_rev else "") + f") in {CLOCK.hms(CLOCK.total())}",
                      ok=n_ok == len(summary) and not failed_videos)
    if R.cfg.get("open_output_after_run", True):
        FINISH.open_folder(outroot)
    if failed_videos:
        ui(f"downloaded stream kept for the rerun ({len(failed_videos)} video(s) failed) - cleanup skipped")
    else:
        FINISH.cleanup(R.cfg, R.work, outroot, R.a.video_file, ui)
    if failed_videos and not summary:              # nothing was made: a bulk queue counts this stream as failed
        sys.exit(f"STOP: no video was made - every video of this run failed (first cause: {failed_videos[0][2]}).\n"
                 f"  Send work/{R.sid}/run_log.txt; rerun with --only <n> after the fix.")


def main(argv=None):
    a = parse_args(argv)
    R = Run(a)
    for stage in (stage_setup, stage_info, stage_download, stage_transcript, stage_scan, stage_plan, stage_render):
        if stage(R) is STOP:
            return


def clips_output(R, only):
    """Clips-only run: one clip.mp4 + EDITOR_GUIDE.txt per case (ucf/clips.py), then the usual report / notify / cleanup."""
    plan, plan_path, work, state, sid, upload, url = R.plan, R.plan_path, R.work, R.state, R.sid, R.upload, R.url
    video_path, segs, cfg, a = R.video_path, R.segs, R.cfg, R.a
    from ucf import clips as CLIPS
    from ucf.render import pick_encoder
    if not video_path.exists():
        sys.exit(f"clips mode needs the downloaded stream ({video_path}) - run again with the URL")
    stamp = f"{upload[:4]}-{upload[4:6]}-{upload[6:8]}" if len(upload) == 8 else upload
    outroot = config.ROOT / cfg["output_dir"] / f"{stamp}_{sid}_clips"
    outroot.mkdir(parents=True, exist_ok=True)
    enc = pick_encoder(cfg)
    from ucf.render import _HW
    ui(f"clips only: {len(plan['videos'])} case(s)  |  encoder: {enc}  |  decode: {('GPU (' + _HW['name'] + ')') if _HW['name'] else 'CPU'}"
       "  |  no overlays / voice / watermark")
    from ucf import render as RND
    RND.warn_low_vram(ui)
    by_id = {c["id"]: c for c in plan["cases"]}
    summary, rows, failed = [], [], []
    ppath = progress_path(work, cfg)
    prog = progress_load(ppath, plan, cfg, kind="clip")
    todo = [v for v in plan["videos"] if not only or v["n"] in only]
    reused = {}
    for v in todo:
        f_ = outroot / f"{v.get('rank', v['n']):02d}_{safe_slug(by_id[v['case_ids'][0]]['name'], 24)}"
        e = None if only else progress_done(prog, v["n"], f_, "clip.mp4")
        if e:
            reused[v["n"]] = e
    if reused and os.environ.get("HL_STUDIO"):
        print(f"@@resumed {len(reused)}", flush=True)
    pending = len(todo) - len(reused)
    if pending:
        check_render_space(cfg, outroot, _WORK.get("stream_len", 0) * pending / max(1, len(plan["videos"])), kind="clips run")
    for v in plan["videos"]:
        if only and v["n"] not in only:
            continue
        case = by_id[v["case_ids"][0]]
        folder = outroot / f"{v.get('rank', v['n']):02d}_{safe_slug(case['name'], 24)}"
        if v["n"] in reused:
            qc_ = load_json(folder / "qc.json", {})
            secs = float(reused[v["n"]].get("seconds") or 0)
            ok_ = bool(qc_.get("ok", reused[v["n"]].get("qc") == "OK"))
            ui(f"clip {v['n']}/{len(plan['videos'])} already done ({fmt_dur(secs)}, QC {'OK' if ok_ else 'CHECK'}) - skipping; "
               f"--only {v['n']} forces it again")
            summary.append((v["n"], folder.name, secs, ok_))
            rows.append((v["n"], folder.name, secs, ok_, v, qc_))
            continue
        progress_mark(ppath, prog, v["n"], state="pending", folder=folder.name)
        ui(f"CLIP {v.get('rank', v['n'])}: {case['name']}")
        CLOCK.stage(f"clip {v.get('rank', v['n'])}")
        t0 = time.time()
        try:
            res = CLIPS.make(plan, v, case, segs, video_path, folder, cfg, enc, ui, url)
        except KeyboardInterrupt:
            raise
        except Exception as e:                       # one broken clip must not cost the others
            import traceback
            traceback.print_exc()
            ui(f"  CLIP {v.get('rank', v['n'])} FAILED: {cause(e)} - going on (rerun later: --only {v['n']})")
            failed.append((v["n"], folder.name, cause(e)))
            progress_mark(ppath, prog, v["n"], state="failed", folder=folder.name, error=cause(e)[:200])
            continue
        qc = dict(res["qc"], processing_seconds=round(time.time() - t0))
        save_json(folder / "qc.json", qc)
        progress_mark(ppath, prog, v["n"], state="done", folder=folder.name, qc="OK" if qc["ok"] else "CHECK",
                      seconds=round(res["total"], 1), processing_seconds=qc["processing_seconds"])
        ui(f"  done: {res['final']}  {fmt_dur(res['total'])}  (took {CLOCK.hms(qc['processing_seconds'])})")
        summary.append((v["n"], folder.name, res["total"], qc["ok"]))
        rows.append((v["n"], folder.name, res["total"], qc["ok"], v, qc))
    CLOCK.stage("report")
    from ucf import mode_all
    mode_all.write_ranking(plan, outroot, cfg, sid)
    rep = [f"RUN REPORT {sid} (clips only) - {time.strftime('%Y-%m-%d %H:%M')}", ""] + \
          ([f"{len(reused)} clip(s) reused from the earlier run (not made again): " + ", ".join(str(n) for n in sorted(reused))]
           if reused else []) + \
          [f"Clip {n}: {f}  {fmt_dur(d)}  {'OK' if ok else 'CHECK'}" for n, f, d, ok in summary] + \
          [f"Clip {n}: {f}  FAILED - {w}  (rerun only this one: --only {n})" for n, f, w in failed]
    ulines, ut = brain.usage_summary()
    brain.save_usage(outroot / "usage.json")
    rep += [""] + ulines + [""] + CLOCK.lines(_WORK.get("stream_len", 0), len(summary) - len(reused), "completed")
    CLOCK.history(state / "run_history.csv", stream_id=sid, style=cfg["style"], mode="clips", encoder=enc,
                  stream_min=round(_WORK.get("stream_len", 0) / 60, 1), videos=len(summary) - len(reused),
                  qc_ok=sum(1 for *_, ok in summary if ok), cost_usd=round(ut.get("cost") or 0, 3))
    (outroot / "run_report.txt").write_text("\n".join(rep), encoding="utf-8")
    shutil.copy(plan_path, outroot / "plan.json")
    shutil.copy(work / "plan_report.txt", outroot / "plan_report.txt")
    ulist = FINISH.upload_list(plan, rows, outroot, files="clip.mp4  |  EDITOR_GUIDE.txt  |  thumbnail_frame_*.jpg")
    print("\n".join(rep))
    ui("editor list:", ulist)
    ui("ALL DONE ->", outroot)
    n_ok = sum(1 for *_, ok in summary if ok)
    if cfg.get("notify_when_done", True):
        FINISH.notify("H Labs - clips done", f"{sid}: {len(summary)} clips ready for the editor in {CLOCK.hms(CLOCK.total())}",
                      ok=n_ok == len(summary))
    if cfg.get("open_output_after_run", True):
        FINISH.open_folder(outroot)
    if failed:
        ui(f"downloaded stream kept for the rerun ({len(failed)} clip(s) failed) - cleanup skipped")
        if not summary:
            sys.exit(f"STOP: no clip was made (first cause: {failed[0][2]}). Send work/{sid}/run_log.txt")
    else:
        FINISH.cleanup(cfg, work, outroot, a.video_file, ui)


if __name__ == "__main__":
    main()
