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
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ucf.render_tt import TTRenderer
from ucf import brain, cards, config, download, scan, sheets, timeline as TL, transcript, tts, validate as VAL
from ucf.render import Renderer
from ucf.timeutil import fmt_dur, fmt_tc, parse_tc, safe_slug

STAGES = ["info", "download", "transcript", "scan", "evidence", "plan", "render"]
IX = {s: i for i, s in enumerate(STAGES)}


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


_WORK = {}
atexit.register(_usage_exit, _WORK)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url", nargs="?")
    ap.add_argument("--config")
    ap.add_argument("--stage", choices=STAGES, help="run up to and including this stage")
    ap.add_argument("--plan", help="plan.json from Claude chat / earlier run")
    ap.add_argument("--video-file", help="already-downloaded stream (skips download)")
    ap.add_argument("--transcript-file", help="transcript json/vtt (skips caption fetch)")
    ap.add_argument("--stream-id")
    ap.add_argument("--stream-length", help="H:MM:SS (needed only when --video-file has no readable duration)")
    ap.add_argument("--only", help="video numbers to render, e.g. 1,3")
    ap.add_argument("--confirm-tts", action="store_true")
    ap.add_argument("--brain", choices=["hive", "anthropic", "deepseek", "openai", "manual", "mock"])
    ap.add_argument("--style", help="editing style id from styles/<id>/style.json (e.g. trial_tales)")
    ap.add_argument("--mode", help="run mode: 30 (20-40 min videos) | 60 (50-70 min) | all (one video per case, ranked)")
    ap.add_argument("--tts", help="force one TTS provider (ai33|voicestudio|say|dummy)")
    a = ap.parse_args()

    cfg = config.load(a.config, style=a.style)
    if a.brain:
        cfg["brain"] = a.brain
        cfg["brain_pass_a"] = cfg["brain_pass_b"] = ""   # an explicit --brain runs every pass on that brain
    if a.tts:
        cfg["tts_order"] = [a.tts]
    mode = config.apply_mode(cfg, a.mode)
    band = (f"{cfg['runtime_min'] // 60}-{cfg['runtime_max'] // 60} min" if mode != "all"
            else f"one video per case >= {cfg.get('min_case_minutes', 8):.0f} min")
    # keep the active model in sync with the chosen provider unless the config pinned a custom one
    if cfg["brain"] in brain.PROVIDERS and cfg.get("model") == config.DEFAULTS["model"]:
        cfg.update(brain.cfg_for(cfg, cfg["brain"]))
    ui(f"style: {cfg['style']}  ({config.style_path(cfg)})  |  mode: {mode}  |  band: {band}")
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
    if meta:
        save_json(work / "meta.json", meta)
        ui(f"stream: {meta['title']}  ({fmt_dur(meta['duration'])}, id {sid})")
        if meta.get("is_live"):
            sys.exit("This stream is still LIVE. Run again after it ends (VOD) so the file is complete.")
    else:
        meta = load_json(work / "meta.json", {})
    url = meta.get("url") or a.url or ""
    upload = meta.get("upload_date", "") or time.strftime("%Y%m%d")
    stream_len = meta.get("duration") or (parse_tc(a.stream_length) if a.stream_length else 0)

    # ---------------- download ----------------
    video_path = Path(a.video_file) if a.video_file else work / "source.mp4"
    if upto >= 1 and not video_path.exists():
        ui("downloading stream (this is the slow part)...")
        video_path = download.fetch_video(url, sid, work, cfg)
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
    tpath = work / "transcript.json"
    if a.transcript_file:
        segs = transcript.load_any(a.transcript_file)
        transcript.save(segs, tpath)
    elif tpath.exists():
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
            segs = transcript.whisper_transcribe(video_path, cfg["whisper_model"])
        transcript.save(segs, tpath)
    ui(f"transcript: {len(segs)} segments, ends {fmt_tc(segs[-1]['end']) if segs else '-'}")
    if upto < IX["scan"]:
        return ui("stopped after", stop)

    # ---------------- scan ----------------
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
    plan_path = Path(a.plan) if a.plan else work / "plan.json"
    carried = [] if mode == "all" else load_json(state / "carry_forward.json", [])
    inputs = {"source_file": source_file, "stream_length": fmt_tc(stream_len), "channel_name": cfg["channel_name"]}
    lines = transcript.compact_lines(segs)
    prompt = brain.build_prompt(inputs, scan_text, lines, carried, cfg)
    (work / "prompt_for_claude.txt").write_text(prompt, encoding="utf-8")
    if not plan_path.exists():
        if mode == "all":
            import os
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
                plan, errs = mode_all.build_plan(segs, lines, scan_text, stream_len, cfg, ui, work)
            except brain.BrainStop as e:
                sys.exit(f"BRAIN STOPPED: {e}\n  replies: work/{sid}/brain_reply_*.txt")
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
        report.append(f"  case {c['id']:>2} {c['name']:<24} {c['in']}-{c['out']} = {fmt_dur(c.get('_dur', 0)):>6}  {c['status']}")
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
    only = {int(x) for x in a.only.split(",")} if a.only else None
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
    if cfg.get("_look") == "ov":
        from ucf.render_ov import OVRenderer
        rn = OVRenderer(cfg, sources, root)
    else:
        rn = (TTRenderer if cfg.get("_renderer", "tt") == "tt" else Renderer)(cfg, sources, root)
    ui(f"encoder: {rn.enc}")
    summary = []
    for v in plan["videos"]:
        if only and v["n"] not in only:
            continue
        lead = by_id[v["case_ids"][0]]
        prefix = f"{v.get('rank', v['n']):02d}" if mode == "all" else f"Video_{v['n']:02d}"
        folder = outroot / f"{prefix}_{safe_slug(lead['name'], 24)}"
        folder.mkdir(exist_ok=True)
        ui(f"VIDEO {v['n']}: {[by_id[i]['name'] for i in v['case_ids']]}")
        rn.log = []
        res = rn.render_video(plan, v, folder, work / "tts", ui)
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
        if chs and chs[-1][0] > res["measured_total"] - 60:
            qc["ok"] = False
            qc["note"] = "a chapter sits in the final 60 s"
        save_json(folder / "qc.json", qc)
        save_json(folder / "video_plan.json", {"video": v, "cases": [by_id[i] for i in v["case_ids"]]})
        log = load_json(state / "used_cases.json", [])
        log.append({"stream_id": sid, "cause_no": lead.get("cause_no", ""), "name": lead.get("name", ""),
                    "in": lead.get("in", ""), "out": lead.get("out", ""), "style": cfg["style"],
                    "mode": cfg.get("mode", ""), "folder": folder.name, "date": time.strftime("%Y-%m-%d")})
        save_json(state / "used_cases.json", log)
        shutil.rmtree(folder / "_work" / "frames", ignore_errors=True)
        ui(f"  done: {res['final']}  {fmt_dur(res['measured_total'])}  QC {'OK' if qc['ok'] else 'CHECK'}  {qc['loudness_lufs']} LUFS")
        summary.append((v["n"], folder.name, res["measured_total"], qc["ok"]))
    carry_txt = ["CARRIED FORWARD (state/carry_forward.json): " + (brain.carried_text(carry) if carry else "none")]
    if mode == "all":
        carry_txt = ["carry-forward: not used in mode all"]
        from ucf import mode_all
        mode_all.write_ranking(plan, outroot, cfg, sid)
    rep = [f"RUN REPORT {sid} - {time.strftime('%Y-%m-%d %H:%M')}", ""] + \
          [f"Video {n}: {f}  {fmt_dur(d)}  QC {'OK' if ok else 'CHECK'}" for n, f, d, ok in summary] + [""] + carry_txt
    ulines, ut = brain.usage_summary()
    brain.save_usage(outroot / "usage.json")
    if ut.get("cost") is not None and summary:
        ulines.append(f"  per video  ${ut['cost'] / len(summary):.2f}  ({len(summary)} videos)")
    rep += [""] + ulines
    (outroot / "run_report.txt").write_text("\n".join(rep), encoding="utf-8")
    shutil.copy(plan_path, outroot / "plan.json")
    shutil.copy(work / "plan_report.txt", outroot / "plan_report.txt")
    print("\n".join(rep))
    ui("ALL DONE ->", outroot)


if __name__ == "__main__":
    main()
