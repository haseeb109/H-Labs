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
            self.f.write(f"\n===== run {time.strftime('%Y-%m-%d %H:%M:%S')}  {' '.join(sys.argv[1:])} =====\n")

    def write(self, s):
        self.stream.write(s)
        try:
            self.f.write(s)
            self.f.flush()
        except Exception:
            pass
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


def check_disk(root, need_gb=5.0, warn_gb=20.0):
    """Stop before a download when the disk is (almost) full; warn when it is getting low."""
    try:
        free = shutil.disk_usage(root).free / 1e9
    except OSError:
        return
    if free < need_gb:
        sys.exit(f"DISK FULL: only {free:.1f} GB free on the H Labs drive - a stream needs ~5-10 GB while it is processed. "
                 "Delete old output folders (videos already uploaded) and run again.")
    if free < warn_gb:
        ui(f"WARNING: only {free:.1f} GB free on the H Labs drive - delete old output folders soon")


def ui(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def load_json(p, default):
    p = Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def save_json(p, d):
    Path(p).write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")


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


def main():
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
    a = ap.parse_args()
    if a.local:                           # your own file / folder: same as --video-file (+ --transcript-file when one is there)
        from ucf import local_src
        try:
            _v, _t = local_src.resolve(a.local)
        except ValueError as e:
            sys.exit(f"STOP: {e}")
        a.video_file = str(_v)
        a.transcript_file = a.transcript_file or (str(_t) if _t else None)
        a.stream_id = a.stream_id or local_src.stream_id(_v)
        print(f"local video: {_v}\n  transcript: {_t or 'none - whisper will make one'}", flush=True)
    elif a.video_file and not a.stream_id:
        from ucf import local_src
        a.stream_id = local_src.stream_id(a.video_file)
    CLOCK.reset()
    CLOCK.stage("info")
    _WORK["planned_stop"] = bool(a.stage) and a.stage != "render"

    cfg = config.load(a.config, style=a.style)
    if a.queued:
        cfg["notify_when_done"] = False
        cfg["open_output_after_run"] = False
    if a.keep_source:
        cfg["cleanup_after_run"] = "never"
    _WORK["notify"] = cfg.get("notify_when_done", True)
    from ucf import load as LOAD
    _prio = LOAD.lower_priority(cfg)                     # ffmpeg / whisper children inherit it: the PC stays responsive
    if a.brain:
        cfg["brain"] = a.brain
        cfg["brain_pass_a"] = cfg["brain_pass_b"] = ""   # an explicit --brain runs every pass on that brain
    if a.tts:
        cfg["tts_order"] = [a.tts]
    if a.no_watermark:
        cfg["watermark"] = False
    if a.mode == "clips":                 # clips only: the brain works exactly as mode "all", the output is clips + editor guides
        cfg["output_kind"] = "clips"
        a.mode = "all"
    if a.mode == "asis":                  # as-is re-edit: the brain + render of mode "all", with the whole video as ONE case
        cfg["_asis"] = True
        a.mode = "all"
    mode = config.apply_mode(cfg, a.mode)
    # after apply_mode: mode "all" sets its own 8:00 default, the run's choice wins over it
    if cfg.get("_asis"):
        cfg["min_case_minutes"] = 0.0
    elif a.min_case:
        cfg["min_case_minutes"] = float(a.min_case)
    cfg["_mode_label"] = "asis" if cfg.get("_asis") else mode
    band = (f"{cfg['runtime_min'] // 60}-{cfg['runtime_max'] // 60} min" if mode != "all"
            else "the whole video as ONE edited video (as-is, no case selection)" if cfg.get("_asis")
            else f"one video per case >= {cfg.get('min_case_minutes', 8):g} min")
    # keep the active model in sync with the chosen provider unless the config pinned a custom one
    if cfg["brain"] in brain.PROVIDERS and cfg.get("model") == config.DEFAULTS["model"]:
        cfg.update(brain.cfg_for(cfg, cfg["brain"]))
    ui(f"style: {cfg['style']}  ({config.style_path(cfg)})  |  mode: {cfg['_mode_label']}  |  band: {band}")
    ui(f"load: priority {_prio or 'normal'}, CPU threads {LOAD.cpu_threads(cfg)} of {os.cpu_count()}"
       "  (config process_priority / cpu_threads)")
    root = config.ROOT
    state = root / cfg["state_dir"]
    state.mkdir(exist_ok=True)
    stop = a.stage or "render"
    upto = STAGES.index(stop)

    # ---------------- info ----------------
    meta = {}
    if a.url:
        try:
            meta = download.info(a.url, cfg) if not a.video_file else {}
        except Exception as e:
            if not a.stream_id:
                sys.exit(f"ERROR: {e}")
    sid = a.stream_id or meta.get("id") or (Path(a.video_file).stem if a.video_file else None)
    if not sid:
        sys.exit("give a URL (or --video-file + --stream-id)")
    work = root / cfg["work_dir"] / sid
    _WORK["dir"] = work
    work.mkdir(parents=True, exist_ok=True)
    if not isinstance(sys.stdout, _Tee):
        sys.stdout = _Tee(sys.stdout, work / "run_log.txt")
        sys.stderr = _Tee(sys.stderr, work / "run_log.txt")      # errors / tracebacks too
    check_disk(work)
    if meta:
        save_json(work / "meta.json", meta)
        ui(f"stream: {meta['title']}  ({fmt_dur(meta['duration'])}, id {sid})")
        if meta.get("is_live"):
            sys.exit("This stream is still LIVE. Run again after it ends (VOD) so the file is complete.")
    else:
        meta = load_json(work / "meta.json", {})
        if a.video_file and Path(a.video_file).exists() and not meta.get("title"):
            # your own file: title + length from the file (the title also gives the court line when it names one)
            meta = {"id": sid, "title": Path(a.video_file).stem, "duration": tts.dur(a.video_file),
                    "local_file": str(Path(a.video_file).resolve())}
            save_json(work / "meta.json", meta)
        if meta.get("title"):
            ui(f"stream: {meta['title']}  ({fmt_dur(meta['duration'])}, id {sid})")
    url = meta.get("url") or a.url or ""
    upload = meta.get("upload_date", "") or time.strftime("%Y%m%d")
    stream_len = meta.get("duration") or (parse_tc(a.stream_length) if a.stream_length else 0)
    # court for the on-screen court line, from the stream title ("... /187TH DISTRICT COURT/ ...") - never a judge's name
    _cm = re.search(r"(\d{1,3})\s*(st|nd|rd|th)\s+district\s+court", meta.get("title") or "", re.I)
    cfg["court"] = f"{_cm.group(1)}{_cm.group(2).lower()} District Court" if _cm else cfg.get("court", "District Court")
    _WORK["stream_len"] = stream_len

    # ---------------- download ----------------
    video_path = Path(a.video_file) if a.video_file else work / "source.mp4"
    if upto >= 1 and not video_path.exists():
        CLOCK.stage("download")
        ui("downloading stream (this is the slow part)...")
        video_path = download.fetch_video(url, sid, work, cfg, meta)
    elif video_path.exists() and upto >= 1:
        ui(download.describe(video_path)[0])       # cached download: show its quality (an old one may be the starved H.264 copy)
        why = "" if a.video_file else download.worse_than_available(video_path, meta, int(cfg.get("min_height", 720)))
        if why and url:
            # an older run downloaded a worse copy (360p / starved H.264): get the real quality, keep the old file if that fails
            CLOCK.stage("download")
            ui(f"the saved download is {why} - downloading the full quality again (transcript and plan are kept)...")
            old = work / "source_old.mp4"
            os.replace(video_path, old)
            try:
                video_path = download.fetch_video(url, sid, work, cfg, meta)
                old.unlink()
            except Exception as e:
                os.replace(old, video_path)
                if download.probe_video(video_path)[0] < int(cfg.get("min_height", 720)) - 10:
                    sys.exit(f"STOP: the saved copy is below {cfg.get('min_height', 720)}p and a better one could not be downloaded:\n"
                             f"  {str(e).splitlines()[0][:300]}")
                ui(f"  re-download failed ({str(e).splitlines()[0][:120]}) - continuing with the saved copy")
    if video_path.exists() and not stream_len:
        stream_len = tts.dur(video_path)
    source_file = f"{sid}.mp4"
    sources = load_json(state / "sources.json", {})
    _prev = sources.get(source_file, {})
    sources[source_file] = {"path": str(video_path.resolve()) if video_path.exists() else str(video_path), "url": url}
    if _prev.get("clips"):   # pre-cut clip source: keep the clip map, the "path" is just the first clip
        sources[source_file] = dict(_prev, url=url or _prev.get("url", ""))
    save_json(state / "sources.json", sources)
    if upto < IX["transcript"]:
        return ui("stopped after", stop)

    # ---------------- transcript ----------------
    _WORK["stream_len"] = stream_len
    CLOCK.stage("transcript")
    tpath = work / "transcript.json"
    if a.transcript_file:
        segs = transcript.load_any(a.transcript_file)
        transcript.save(segs, tpath)
    elif tpath.exists() and not (work / "transcript.sparse").exists():   # .sparse: captions-only fallback -> try whisper again
        segs = json.loads(tpath.read_text(encoding="utf-8"))
    else:
        segs = []
        if cfg["captions"] == "auto" and url:
            ui("fetching YouTube captions...")
            f = download.fetch_captions(url, work, cfg)
            if f:
                segs = transcript.load_any(f)
        spoken_wpm = (sum(len(s["text"].split()) for s in segs) / max(stream_len / 60.0, 1)) if segs else 0
        if spoken_wpm < 15:   # missing / sparse captions
            ui("captions missing or sparse -> whisper (slow, CPU)...")
            from ucf.load import cpu_threads
            try:
                segs = transcript.whisper_safe(video_path, cfg["whisper_model"], threads=cpu_threads(cfg), ui=ui)
            except RuntimeError as e:
                if not segs:
                    raise
                ui(f"WARNING: {e}\n  -> going on with the YouTube captions ({len(segs)} lines, {spoken_wpm:.0f} words/min). "
                   "Case times may be rougher; check the videos.")
                (work / "transcript.sparse").write_text("captions only - whisper failed", encoding="utf-8")
            else:
                (work / "transcript.sparse").unlink(missing_ok=True)
        transcript.save(segs, tpath)
    ui(f"transcript: {len(segs)} segments, ends {fmt_tc(segs[-1]['end']) if segs else '-'}")
    if upto < IX["scan"]:
        return ui("stopped after", stop)

    # ---------------- scan ----------------
    CLOCK.stage("scan + evidence")
    rep = scan.report(segs, stream_len)
    scan_text = scan.report_text(rep)
    (work / "scan.txt").write_text(scan_text, encoding="utf-8")
    ui(f"scan: {len(rep['clusters'])} candidate case starts, {len(rep['dead_air'])} dead-air stretches")
    if upto < IX["evidence"]:
        return ui("stopped after", stop)

    # -------- evidence (v10 boundary signals; transcript-level here, video-level lazily) --------
    evidence = {}
    if (cfg.get("boundary") or {}).get("enabled", True):
        try:
            from ucf import evidence as EV
            evidence = EV.build(video_path if video_path.exists() else None, segs, rep, cfg, work)
            ui(f"evidence: {len(evidence['call_outs'])} call-outs, {len(evidence['wrap_up'])} wrap-ups, "
               f"{len(evidence['ruling'])} rulings, ocr={evidence['ocr_engine'] or 'off'}")
        except Exception as e:  # noqa
            ui("evidence skipped:", e)
    if upto < IX["plan"]:
        return ui("stopped after", stop)

    # ---------------- plan ----------------
    CLOCK.stage("brain (plan)")
    # one plan per style + mode: titles follow the style's own rules and a bundle plan is not an all-cases plan, so a stream run
    # again in another style / mode must not reuse the first plan (it failed the validator: "CAPS word ... not in this style's
    # banks"). Clips use the all-cases plan of the same style.
    plan_path = Path(a.plan) if a.plan else work / f"plan_{cfg['style']}_{cfg['_mode_label']}" \
        f"{'' if cfg['_mode_label'] != 'all' or cfg.get('min_case_minutes', 8) == 8 else '_min%g' % cfg['min_case_minutes']}.json"
    carried = [] if mode == "all" else load_json(state / "carry_forward.json", [])
    inputs = {"source_file": source_file, "stream_length": fmt_tc(stream_len), "channel_name": cfg["channel_name"]}
    lines = transcript.compact_lines(segs)
    prompt = brain.build_prompt(inputs, scan_text, lines, carried, cfg)
    (work / "prompt_for_claude.txt").write_text(prompt, encoding="utf-8")
    if not plan_path.exists():
        if mode == "all":
            if os.environ.get("HL_PASSA_REPLY"):       # resume: replay a saved Pass A reply, live Pass B
                cfg["mock_passA_replies"] = [os.environ["HL_PASSA_REPLY"]]
            if cfg["brain"] == "manual":
                sys.exit(f"MANUAL BRAIN (mode all): 1) paste {work / 'prompt_A.txt'} into Claude, save its JSON reply "
                         f"as {work / 'plan_A.json'}, 2) rerun with --plan {work / 'plan_A.json'} (the script then "
                         f"writes one prompt_B_<case>.txt per case; package each the same way and merge).")
            from ucf import mode_all
            cfg["_source_file"] = source_file
            if not lines:
                sys.exit("transcript is empty - mode all cannot run")
            try:
                plan, errs = mode_all.build_plan(segs, lines, scan_text, stream_len, cfg, ui, work, scan_rep=rep,
                                                 video_path=video_path if video_path.exists() else None)
            except brain.BrainStop as e:
                sys.exit(f"BRAIN STOPPED: {e}\n  replies: work/{sid}/brain_reply_*.txt")
            if plan is not None and errs and str(errs[0]).startswith("no case reached"):
                # not an error of the tool: this stream simply has no case long enough for its own video
                mc = cfg.get("min_case_minutes", 8)
                def _len(c):
                    try:
                        return parse_tc(c["out"]) - parse_tc(c["in"])
                    except Exception:
                        return 0
                cs = sorted(plan.get("cases", []), key=lambda c: -_len(c))
                ui(f"NOTHING TO MAKE: no case in this stream has {mc:.0f}:00 or more of hearing (rule for one video per case).")
                for c in cs[:8]:
                    ui(f"   {c.get('name', '?'):<28} {c.get('in')}-{c.get('out')}  {fmt_dur(_len(c)):>6}  {c.get('status')}"
                       + (f"  ({c.get('reject_reason')})" if c.get("reject_reason") else ""))
                ui("   -> try the 30 min / 1 hour mode (several short cases in one video), or another stream.")
                sys.exit(0 if a.queued else 2)
            if plan is None or errs:
                sys.exit(f"mode-all plan failed: {errs[:3] if errs else 'no plan'} - see work/{sid}/brain_reply_A_*.txt")
            save_json(plan_path, plan)
            errs, warns = VAL.validate(plan, stream_len, segs, cfg)
        else:
            if cfg["brain"] == "manual":
                sys.exit(f"MANUAL BRAIN: paste {work / 'prompt_for_claude.txt'} into Claude, save its JSON reply as "
                         f"{work / 'plan.json'} and run again (or pass --plan file.json).")
            fb = cfg.get("brain_fallback") or ""
            fb = fb if fb and fb != cfg["brain"] and cfg["brain"] != "mock" else ""
            try:
                plan, errs, warns = brain.make_plan(prompt, stream_len, segs, cfg, ui, save_dir=work)
            except (brain.BrainStop, RuntimeError) as e:
                if not fb:
                    sys.exit(f"BRAIN STOPPED: {e}\n  replies: work/{sid}/brain_reply_*.txt")
                plan, errs, warns = None, [str(e)], []
            if (plan is None or errs) and fb:
                ui(f"  {cfg['brain']} could not produce a valid plan ({(errs or ['no plan'])[0][:100]}) "
                   f"-> falling back to {fb}")
                try:
                    plan, errs, warns = brain.make_plan(prompt, stream_len, segs, brain.cfg_for(cfg, fb), ui,
                                                        save_dir=work, tag="fb_")
                except brain.BrainStop as e:
                    sys.exit(f"BRAIN STOPPED: {e}\n  replies: work/{sid}/brain_reply_*.txt")
            if plan is None:
                sys.exit(f"brain '{cfg['brain']}' never returned valid JSON - see work/*/brain_reply_*.txt")
            save_json(plan_path, plan)
    else:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        plan["source_file"] = plan.get("source_file") or source_file
        errs, warns = VAL.validate(plan, stream_len, segs, cfg)
    plan["source_file"] = source_file if plan.get("source_file") != source_file else plan["source_file"]
    # bundle modes: boundary refinement applies too (spec 7), but reverts if it breaks validation
    if mode != "all" and evidence and video_path.exists() and (cfg.get("boundary") or {}).get("enabled", True):
        try:
            import copy
            from ucf import boundary as BD
            snapshot = copy.deepcopy(plan)
            BD.refine_plan(plan, evidence, video_path, cfg, work, ui)
            errs, warns = VAL.validate(plan, stream_len, segs, cfg)
            if errs:
                plan = snapshot
                errs, warns = VAL.validate(plan, stream_len, segs, cfg)
                ui("boundary refinement reverted (introduced validation errors)")
        except Exception as e:  # noqa
            ui("boundary refinement skipped:", e)
    report = [f"PLAN REPORT  {sid}", f"stream {fmt_tc(stream_len)}  cases {len(plan['cases'])}  videos {len(plan['videos'])}"]
    st = plan.get("_stats", {})
    if st:
        report.append("minutes: found {} = used {} + carried {} + rejected {}  | unmapped stream time {}".format(
            fmt_dur(st["found"]), fmt_dur(st["used"]), fmt_dur(st["carried"]), fmt_dur(st["rejected"]), fmt_dur(st["unmapped"])))
    report += ["", "ERRORS (block the render):"] + ([f" - {e}" for e in errs] or [" none"])
    report += ["", "WARNINGS:"] + ([f" - {w}" for w in warns] or [" none"])
    for c in plan["cases"]:
        why = "" if c.get("status") == "used" else (c.get("reject_reason") or "")
        report.append(f"  case {c['id']:>2} {c['name']:<24} {c['in']}-{c['out']} = {fmt_dur(c.get('_dur', 0)):>6}  {c['status']}"
                      + (f"  ({why[:90]})" if why else ""))
    (work / "plan_report.txt").write_text("\n".join(report), encoding="utf-8")
    save_json(plan_path, plan)
    print("\n".join(report))
    if errs:
        sys.exit("\nPlan has errors - fix the plan (or rerun the brain) before rendering. See plan_report.txt")
    # contact sheet of case boundaries (cheap) - look at it BEFORE the long render
    if video_path.exists():
        try:
            rn = Renderer(cfg, sources, root)
            frames, labels = [], []
            fd = work / "plan_frames"
            fd.mkdir(exist_ok=True)
            for c in plan["cases"]:
                for tag, tc in (("IN", c["in"]), ("OUT", c["out"])):
                    p = fd / f"c{c['id']}_{tag}.jpg"
                    import subprocess
                    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(max(0, parse_tc(tc) - (1 if tag == 'OUT' else 0))),
                                    "-i", str(video_path), "-frames:v", "1", "-vf", "scale=480:270", "-q:v", "4", str(p)])
                    frames.append(p)
                    labels.append(f"#{c['id']} {c['name'][:18]} {tag} {tc}")
            cards.contact_sheet(frames, labels, work / "contact_plan.jpg")
            ui("contact sheet of every case IN/OUT:", work / "contact_plan.jpg")
        except Exception as e:  # noqa
            ui("contact sheet skipped:", e)
    # carry forward state (mode all never touches it)
    carry = [c for c in plan["cases"] if c["status"] == "carried"] if mode != "all" else []
    for c in carry:
        c["source_file"] = c.get("source_file") or source_file
    old = [c for c in carried if not any(c["name"] == n["name"] and c.get("source_file") == n.get("source_file") for n in carry)
           and not any(c.get("source_file") == source_file for _ in [0])]
    save_json(state / "carry_forward.json", carry + [c for c in old if c.get("source_file") != source_file])
    if mode == "all":
        from ucf import mode_all
        mode_all.write_ranking(plan, work, cfg, sid)
        ui("ranking drafted:", work / "ranking.md")
    if upto < IX["render"]:
        return ui("stopped after plan. Review plan_report.txt + contact_plan.jpg, then run again without --stage.")

    # ---------------- render ----------------
    CLOCK.stage("render setup")
    # owner rule 2026-11-13: voice-over + on-screen text say "the judge", never the judge's name (other judges' dockets too);
    # titles / description / tags keep the name. A safety net on top of the prompt rule.
    from ucf.judge_neutral import judge_names, neutralize
    _jn = neutralize(plan, judge_names(plan.get("judge_name"), cfg.get("judge_name"), meta.get("title")))
    if _jn:
        ui(f"judge-neutral: {_jn} voice-over / on-screen text(s) now say 'the judge' instead of the name")
    only = {int(x) for x in a.only.split(",")} if a.only else None
    if os.environ.get("HL_STUDIO"):
        print(f"@@videos {sum(1 for v in plan['videos'] if not only or v['n'] in only)}", flush=True)
    if cfg.get("output_kind") == "clips":
        return clips_output(plan, plan_path, work, state, sid, upload, url, video_path, segs, cfg, mode, only, a)
    # cross-channel reuse guard (spec 9.5): warn, never block
    if cfg.get("reuse_guard", True):
        used_log = load_json(state / "used_cases.json", [])
        hits = [u for u in used_log if u.get("stream_id") == sid and u.get("style") != cfg["style"]]
        for u in hits:
            ui(f"REUSE WARNING: {u.get('name', '?')} already used on {u.get('style')} ({u.get('date', '?')}) "
               f"- YouTube may treat this as reused content")
        if hits:
            warn_line = "; ".join(f"{u.get('name')}@{u.get('style')}" for u in hits)
            (work / "plan_report.txt").open("a").write(f"\nREUSE WARNING: {warn_line}\n")
    need = tts.chars_needed(plan, only, tt=cfg.get('_renderer') == 'tt')
    ui(f"voiceover characters this run: {need}")
    if need > cfg["tts_confirm_chars"] and not a.confirm_tts:
        sys.exit(f"STOP: {need} characters of TTS is over the {cfg['tts_confirm_chars']} limit. "
                 f"Confirm with Sardar in chat, then rerun with --confirm-tts.")
    stamp = f"{upload[:4]}-{upload[4:6]}-{upload[6:8]}" if len(upload) == 8 else upload
    outroot = root / cfg["output_dir"] / f"{stamp}_{sid}"
    outroot.mkdir(parents=True, exist_ok=True)
    by_id = {c["id"]: c for c in plan["cases"]}
    _sj = json.loads((config.style_path(cfg) / "style.json").read_text(encoding="utf-8"))
    if _sj.get("renderer_module"):          # a style pack that ships its own renderer (e.g. Court Beacon TV)
        import importlib.util
        _spec = importlib.util.spec_from_file_location("style_renderer", config.style_path(cfg, _sj["renderer_module"]))
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        rn = getattr(_mod, _sj.get("renderer_class", "Renderer"))(cfg, sources, root)
    elif cfg.get("_look") == "ov":
        from ucf.render_ov import OVRenderer
        rn = OVRenderer(cfg, sources, root)
    else:
        rn = (TTRenderer if cfg.get("_renderer", "tt") == "tt" else Renderer)(cfg, sources, root)
    from ucf.render import _HW
    ui(f"encoder: {rn.enc}  |  decode: {('GPU (' + _HW['name'] + ')') if _HW['name'] else 'CPU'}")
    summary, rows, failed_videos = [], [], []
    todo = [v for v in plan["videos"] if not only or v["n"] in only]
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
                            tts.synth_clips(brs[ids_[i_]]["text"], work / "tts", cfg, lambda *m: None)
                    tts.synth_clips(pv["vo_final"]["text"], work / "tts", cfg, lambda *m: None)
                except Exception:  # noqa
                    pass
        threading.Thread(target=_prefetch_vo, args=(todo[1:],), daemon=True, name="vo-prefetch").start()
    for v in plan["videos"]:
        if only and v["n"] not in only:
            continue
        lead = by_id[v["case_ids"][0]]
        prefix = f"{v.get('rank', v['n']):02d}" if mode == "all" else f"Video_{v['n']:02d}"
        folder = outroot / f"{prefix}_{safe_slug(lead['name'], 24)}"
        folder.mkdir(exist_ok=True)
        try:
            ui(f"VIDEO {v['n']}: {[by_id[i]['name'] for i in v['case_ids']]}")
            CLOCK.stage(f"video {v['n']} render")
            _t_video = time.time()
            rn.log = []
            fresh_render_cache(folder, cfg, v, [by_id[i] for i in v["case_ids"]])
            from ucf import render as RND
            from ucf import watermark as WM
            wm_text, wm_err = None, None
            try:                                         # the watermark is drawn inside every segment encode (one pass less)
                wmf = WM.segment_finish(cfg, f"{sid}:{v['n']}", folder)
            except Exception as e:                       # no PNG -> the old full-video pass below
                wmf = None
                ui(f"  watermark inside the render not possible ({str(e)[:120]}) - adding it in a separate pass")
            RND.set_finish(wmf)
            try:
                res = rn.render_video(plan, v, folder, work / "tts", ui)
                fin = dict(RND._FINISH)
            finally:
                RND.set_finish(None)
            if wmf and not fin["missed"]:
                wm_text = wmf["text"]
                ui(f"  watermark '{wm_text}' drawn inside the render ({fin['applied']} new piece(s))")
            elif WM.enabled(cfg):
                try:                                     # old way: one more pass over the whole video (safety net)
                    if fin.get("missed"):
                        ui(f"  {fin['missed']} piece(s) could not take the watermark inside the render - separate pass")
                    wm_text = WM.apply_in_place(res["final"], cfg, f"{sid}:{v['n']}", rn.enc, ui)
                except Exception as e:                   # never lose the render over a watermark problem, but flag it
                    wm_err = str(e).splitlines()[0][:160] if str(e) else repr(e)
                    ui(f"  WATERMARK FAILED: {wm_err}  (video.mp4 is the un-watermarked render)")
            thumb = rn.thumbnail(plan, v, folder)
            tl = res["timeline"]
            (folder / "edit_sheet.txt").write_text(sheets.edit_sheet(plan, v, tl, res["durs"]), encoding="utf-8")
            md, chs = sheets.metadata(plan, v, tl, cfg, url)
            (folder / "metadata.txt").write_text(md, encoding="utf-8")
            rn.write_footage_log(folder / "footage_log.csv")
            rn.contact_sheet(res["final"], res["rows"], folder / "contact_sheet.jpg")
            qc = rn.qc(res["final"], res["measured_total"])
            if res.get("ai_clips"):
                qc["ai_clip_seconds"] = res["ai_clips"]
                qc["ai_clips_ok"] = max(res["ai_clips"]) <= cfg.get("vo_clip_max", 18.0)
                qc["ok"] = qc["ok"] and qc["ai_clips_ok"]
            qc["chapters"] = [(fmt_tc(o, False), l) for o, l in chs]
            qc["watermark"] = wm_text or False
            if wm_err:
                qc["ok"] = False
                qc["note"] = "watermark failed: " + wm_err
            if chs and chs[-1][0] > res["measured_total"] - 60:
                qc["ok"] = False
                qc["note"] = "a chapter sits in the final 60 s"
            qc["processing_seconds"] = round(time.time() - _t_video)
            save_json(folder / "qc.json", qc)
            save_json(folder / "video_plan.json", {"video": v, "cases": [by_id[i] for i in v["case_ids"]]})
            log = load_json(state / "used_cases.json", [])
            log.append({"stream_id": sid, "cause_no": lead.get("cause_no", ""), "name": lead.get("name", ""),
                        "in": lead.get("in", ""), "out": lead.get("out", ""), "style": cfg["style"],
                        "mode": cfg.get("_mode_label", cfg.get("mode", "")), "folder": folder.name, "date": time.strftime("%Y-%m-%d")})
            save_json(state / "used_cases.json", log)
            shutil.rmtree(folder / "_work" / "frames", ignore_errors=True)
            ui(f"  done: {res['final']}  {fmt_dur(res['measured_total'])}  QC {'OK' if qc['ok'] else 'CHECK'}  {qc['loudness_lufs']} LUFS"
               f"  (took {CLOCK.hms(qc['processing_seconds'])})")
            summary.append((v["n"], folder.name, res["measured_total"], qc["ok"]))
            rows.append((v["n"], folder.name, res["measured_total"], qc["ok"], v, qc))
        except KeyboardInterrupt:
            raise
        except Exception as e:                      # one broken video must not cost the others (2026-11-05: an ai33 timeout)
            import traceback
            traceback.print_exc()
            why = (str(e).strip().splitlines() or [repr(e)])[-1][:200]
            ui(f"  VIDEO {v['n']} FAILED: {why} - going on with the next video (rerun later: --only {v['n']})")
            failed_videos.append((v['n'], folder.name, why))
    CLOCK.stage("report")
    carry_txt = ["CARRIED FORWARD (state/carry_forward.json): " + (brain.carried_text(carry) if carry else "none")]
    if mode == "all":
        carry_txt = ["carry-forward: not used in mode all"]
        from ucf import mode_all
        mode_all.write_ranking(plan, outroot, cfg, sid)
    rep = [f"RUN REPORT {sid} - {time.strftime('%Y-%m-%d %H:%M')}", ""] + \
          [f"Video {n}: {f}  {fmt_dur(d)}  QC {'OK' if ok else 'CHECK'}" for n, f, d, ok in summary] + \
          [f"Video {n}: {f}  FAILED - {why}  (rerun only this one: --only {n})" for n, f, why in failed_videos] + [""] + carry_txt
    ulines, ut = brain.usage_summary()
    brain.save_usage(outroot / "usage.json")
    if ut.get("cost") is not None and summary:
        ulines.append(f"  per video  ${ut['cost'] / len(summary):.2f}  ({len(summary)} videos)")
    rep += [""] + ulines
    status = (f"{len(failed_videos)} video(s) FAILED" if failed_videos
              else "completed" if all(ok for *_, ok in summary) else "completed, some QC CHECK")
    rep += [""] + CLOCK.lines(stream_len, len(summary), status)
    CLOCK.history(state / "run_history.csv", stream_id=sid, style=cfg["style"], mode=cfg.get("_mode_label", mode), encoder=rn.enc,
                  stream_min=round(stream_len / 60, 1), videos=len(summary), qc_ok=sum(1 for *_, ok in summary if ok),
                  cost_usd=round(ut.get("cost") or 0, 3))
    (outroot / "run_report.txt").write_text("\n".join(rep), encoding="utf-8")
    shutil.copy(plan_path, outroot / "plan.json")
    shutil.copy(work / "plan_report.txt", outroot / "plan_report.txt")
    ulist = FINISH.upload_list(plan, rows, outroot)
    print("\n".join(rep))
    ui("upload list:", ulist)
    ui("ALL DONE ->", outroot)
    n_ok = sum(1 for *_, ok in summary if ok)
    n_rev = sum(1 for c in plan.get("cases", []) if c.get("needs_review"))
    if cfg.get("notify_when_done", True):
        FINISH.notify("H Labs - done", f"{sid}: {len(summary)} videos ({n_ok} QC OK"
                      + (f", {len(failed_videos)} FAILED" if failed_videos else "")
                      + (f", {n_rev} need review" if n_rev else "") + f") in {CLOCK.hms(CLOCK.total())}",
                      ok=n_ok == len(summary) and not failed_videos)
    if cfg.get("open_output_after_run", True):
        FINISH.open_folder(outroot)
    if failed_videos:
        ui(f"downloaded stream kept for the rerun ({len(failed_videos)} video(s) failed) - cleanup skipped")
    else:
        FINISH.cleanup(cfg, work, outroot, a.video_file, ui)
    if failed_videos and not summary:
        sys.exit(1)                                # nothing was made: a bulk queue counts this stream as failed


def clips_output(plan, plan_path, work, state, sid, upload, url, video_path, segs, cfg, mode, only, a):
    """Clips-only run: one clip.mp4 + EDITOR_GUIDE.txt per case (ucf/clips.py), then the usual report / notify / cleanup."""
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
    by_id = {c["id"]: c for c in plan["cases"]}
    summary, rows = [], []
    for v in plan["videos"]:
        if only and v["n"] not in only:
            continue
        case = by_id[v["case_ids"][0]]
        folder = outroot / f"{v.get('rank', v['n']):02d}_{safe_slug(case['name'], 24)}"
        ui(f"CLIP {v.get('rank', v['n'])}: {case['name']}")
        CLOCK.stage(f"clip {v.get('rank', v['n'])}")
        t0 = time.time()
        try:
            res = CLIPS.make(plan, v, case, segs, video_path, folder, cfg, enc, ui, url)
        except KeyboardInterrupt:
            raise
        except Exception as e:                       # one broken clip must not cost the others
            ui(f"  CLIP {v.get('rank', v['n'])} FAILED: {(str(e).strip().splitlines() or [repr(e)])[-1][:200]} - going on")
            continue
        qc = dict(res["qc"], processing_seconds=round(time.time() - t0))
        save_json(folder / "qc.json", qc)
        ui(f"  done: {res['final']}  {fmt_dur(res['total'])}  (took {CLOCK.hms(qc['processing_seconds'])})")
        summary.append((v["n"], folder.name, res["total"], qc["ok"]))
        rows.append((v["n"], folder.name, res["total"], qc["ok"], v, qc))
    CLOCK.stage("report")
    from ucf import mode_all
    mode_all.write_ranking(plan, outroot, cfg, sid)
    rep = [f"RUN REPORT {sid} (clips only) - {time.strftime('%Y-%m-%d %H:%M')}", ""] + \
          [f"Clip {n}: {f}  {fmt_dur(d)}  {'OK' if ok else 'CHECK'}" for n, f, d, ok in summary]
    ulines, ut = brain.usage_summary()
    brain.save_usage(outroot / "usage.json")
    rep += [""] + ulines + [""] + CLOCK.lines(_WORK.get("stream_len", 0), len(summary), "completed")
    CLOCK.history(state / "run_history.csv", stream_id=sid, style=cfg["style"], mode="clips", encoder=enc,
                  stream_min=round(_WORK.get("stream_len", 0) / 60, 1), videos=len(summary),
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
    FINISH.cleanup(cfg, work, outroot, a.video_file, ui)


if __name__ == "__main__":
    main()
