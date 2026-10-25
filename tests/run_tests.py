#!/usr/bin/env python3
"""H Labs self-test matrix - 10 checks, run before any delivery:  python3 tests/run_tests.py
   --quick   skip the long end-to-end render (test 10)

1  environment      ffmpeg/vp9/videotoolbox/ffprobe/node/hyperframes/venv deps
2  imports          every pipeline module imports clean
3  transcript       fixture loads + monotonic + whisper smoke on generated speech
4  scan             rule-0 scan finds the CR call-outs in the fixture transcript
5  validator good   the known-good Rendon plan passes with 0 errors
6  validator bad    a deliberately broken plan is blocked with the expected errors
7  vo splitter      sentence-aligned clips all <= 18 s; plan bridge/closing texts clean
8  brain plumbing   prompt build + mock provider + JSON repair loop (no network)
9  renderer units   sources.json mapping, layout detection, overlay, dummy TTS
10 end-to-end       full run_stream.py render -> video + metadata + QC ok
"""
import json
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from ucf.timeutil import parse_tc
QUICK = "--quick" in sys.argv

FIX = ROOT / "tests" / "fixtures" / "rv_clips"
NEXLEV = ROOT / "tests" / "lVQ79x0Hd_w_nexlev.json"
PLAN_FILE = ROOT / "tests" / "rendon_2025-05-09_plan.json"
STREAM_LEN = 3 * 3600 + 23
SNAME = "lVQ79x0Hd_w.mp4"

RESULTS = []


def check(n, name, fn):
    t0 = time.time()
    try:
        detail = fn() or ""
        RESULTS.append((n, name, True, detail, time.time() - t0))
        print(f"  PASS  {n:>2} {name}  {detail}  ({time.time() - t0:.1f}s)")
    except Exception as e:  # noqa: BLE001
        RESULTS.append((n, name, False, f"{e}", time.time() - t0))
        print(f"  FAIL  {n:>2} {name}  ->  {e}")
        traceback.print_exc(limit=3)


def t1_environment():
    import ucf.hf as hf
    for tool in ("ffmpeg", "ffprobe", "node"):
        assert shutil.which(tool), f"{tool} not on PATH"
    r = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True)
    assert "libvpx-vp9" in r.stdout, "ffmpeg has no libvpx-vp9 (alpha WebM overlays need it)"
    hw = {"darwin": "h264_videotoolbox", "win32": "h264_nvenc", "linux": "h264_nvenc"}.get(sys.platform, "")
    if hw and hw not in r.stdout:
        hw = ""   # no hw encoder on this box is fine - libx264 (software) always works
    import yt_dlp, PIL, numpy  # noqa: F401
    import faster_whisper  # noqa: F401
    assert hf.available(), "HyperFrames/headless Chrome not available (PNG fallback would kick in)"
    return f"vp9+hf ok, hw encoder: {hw or 'libx264 (software)'}"


def t2_imports():
    import importlib
    mods = ["run_stream", "ucf.config", "ucf.brain", "ucf.scan", "ucf.transcript", "ucf.validate",
            "ucf.timeline", "ucf.vo", "ucf.tts", "ucf.hf", "ucf.render_tt", "ucf.render", "ucf.cards",
            "ucf.sheets", "ucf.download", "ucf.timeutil"]
    for m in mods:
        importlib.import_module(m)
    return f"{len(mods)} modules"


def _load_segs():
    from ucf import transcript
    return transcript.load_any(str(NEXLEV))


def t3_transcript():
    from ucf import transcript
    segs = _load_segs()
    assert len(segs) > 500, f"only {len(segs)} segments"
    assert all(segs[i]["start"] <= segs[i + 1]["start"] for i in range(len(segs) - 1)), "times not monotonic"
    text = " ".join(s["text"].lower() for s in segs)
    assert "cr2071" in text or "2071" in text, "Maldonado cause number not in transcript"
    lines = transcript.compact_lines(segs)
    assert lines and "[0:13" in "".join(lines[:200]), "compact_lines lost the timecodes"
    # whisper smoke on speech we generate locally: macOS `say`, Windows SAPI, then transcribe
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        wav = td / "s.wav"
        line = "The court is calling cause number 2024 CR2071, state versus Hank Maldonado."
        if sys.platform == "darwin":
            r = subprocess.run(["say", "-o", str(wav), "--data-format=LEI16@16000", line],
                               capture_output=True, text=True)
        else:
            ps = ("Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                  f"$s.SetOutputToWaveFile('{wav.as_posix()}'); $s.Speak('{line}'); $s.Dispose()")
            r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True)
        assert wav.exists() and wav.stat().st_size > 20000, f"local TTS failed: {r.stderr[:200]}"
        got = transcript.whisper_transcribe(wav, "tiny.en" if sys.platform == "darwin" else "base.en")
    g = " ".join(s["text"] for s in got).lower()
    assert "2071" in g, f"whisper missed the case number, heard: {g[:160]}"
    return f"{len(segs)} segs, whisper heard the CR number"


def t4_scan():
    from ucf import scan
    segs = _load_segs()
    rep = scan.report(segs, STREAM_LEN)
    txt = scan.report_text(rep)
    assert rep["clusters"], "no case-start clusters found"
    mald = [c for c in rep["clusters"] if abs(c["t"] - (13 * 60 + 25)) < 90]
    assert mald, f"Maldonado call-out (~0:13:25) not clustered; clusters at {[round(c['t']) for c in rep['clusters']][:12]}"
    assert any("calling" in p for p in mald[0]["phrases"]), f"cluster near 13:25 lacks a call-out phrase: {mald[0]['phrases']}"
    assert "0:13:2" in txt, "scan text lost the 13:2x timecode"
    return f"{len(rep['clusters'])} clusters, {len(rep['dead_air'])} dead-air"


def _cfg():
    from ucf import config
    return config.load()


def _test_cfg():
    """The Rendon fixture is a v9-shaped plan at 28:35. Tests exercise the validator's logic, not the
    owner's current band or the v10 field set, so pin the legacy band + title system here."""
    cfg = _cfg()
    cfg["runtime_min"], cfg["runtime_max"] = 20 * 60, 30 * 60
    cfg["title_system"] = "v9"
    return cfg


def t5_validator_good():
    from ucf import validate as VAL
    plan = json.loads(PLAN_FILE.read_text(encoding="utf-8"))
    errs, warns = VAL.validate(plan, STREAM_LEN, _load_segs(), _test_cfg())
    assert not errs, f"known-good plan rejected: {errs[:5]}"
    return f"0 errors, {len(warns)} warnings"


def t6_validator_bad():
    from ucf import validate as VAL
    plan = json.loads(PLAN_FILE.read_text(encoding="utf-8"))
    plan["videos"][0]["hook"]["in"] = "0:55:00"                 # hook outside the back 60%
    plan["videos"][0]["bridges"][0]["text"] = " ".join(["word"] * 60)   # 60 words vs 35-40
    plan["videos"][0]["title"] = "A Title Without The Dash And Caps"
    errs, _ = VAL.validate(plan, STREAM_LEN, _load_segs(), _cfg())
    joined = " | ".join(errs)
    assert len(errs) >= 3, f"expected >=3 blockers, got {len(errs)}: {errs}"
    for needle in ("hook", "bridge", "title"):
        assert needle in joined.lower(), f"validator did not flag {needle}: {joined[:300]}"
    return f"{len(errs)} errors correctly raised (hook/bridge/title)"


def t7_vo_splitter():
    from ucf import vo
    plan = json.loads(PLAN_FILE.read_text(encoding="utf-8"))
    v = plan["videos"][0]
    long_text = " ".join(["The court moves to the next hearing and the gallery settles down."] * 8)
    clips = vo.split_clips(long_text)
    for c in clips:
        assert vo.est_seconds(c) <= 18.0, f"clip over 18s: {vo.est_seconds(c):.1f}"
    assert vo.est_seconds(" ".join(clips)) >= vo.est_seconds(long_text) * 0.9, "splitter lost text"
    for c in clips:
        issues = vo.clip_issues(c) if hasattr(vo, "clip_issues") else []
        assert not issues, f"clip issues: {issues}"
    bridge = v["bridges"][0]["text"]
    assert 35 <= vo.n_words(bridge) <= 40, "fixture bridge word count drifted"
    finals = vo.split_clips(v["vo_final"]["text"])
    assert len(finals) >= 2 and all(vo.est_seconds(c) <= 18.0 for c in finals), "closing text does not split <=18s"
    return f"{len(clips)} + {len(finals)} clips all <=18s"


def t8_brain_plumbing():
    from ucf import brain
    from ucf.config import style_path
    cfg = _test_cfg()
    inputs = {"source_file": SNAME, "stream_length": "3:00:23", "channel_name": "Trial Tales"}
    master = style_path(cfg, cfg.get("_prompt_master", "prompts/master_v9.md"))
    lines = [l for l in master.read_text(encoding="utf-8").splitlines()[:3]]
    prompt = brain.build_prompt(inputs, "SCAN TEXT PLACEHOLDER", lines, [], cfg)
    assert "OWNER OVERRIDES" in prompt and SNAME in prompt, "prompt template incomplete"
    # mock provider replays the known-good plan -> parse + validate must pass
    cfg["brain"] = "mock"
    cfg["mock_reply_file"] = str(PLAN_FILE)
    plan, errs, _ = brain.make_plan(prompt, STREAM_LEN, _load_segs(), cfg)
    assert plan and not errs, f"mock brain plan rejected: {errs[:3]}"
    # repair loop: round 1 broken JSON, round 2 the good plan
    calls = {"n": 0}

    def fake_stream(msgs, cfg2, on_text=None):
        calls["n"] += 1
        return "{not json" if calls["n"] == 1 else PLAN_FILE.read_text(encoding="utf-8")

    brain._stream_any = fake_stream
    plan2, errs2, _ = brain.make_plan(prompt, STREAM_LEN, _load_segs(), cfg)
    assert calls["n"] == 2 and not errs2, f"repair loop failed after {calls['n']} rounds: {errs2[:3]}"
    # provider registry sanity
    assert set(brain.PROVIDERS) == {"anthropic", "deepseek", "openai", "hive"}
    return "mock plan ok + 1 repair round + 4 providers registered"


def t16_overlay_burn():
    """Burn one card on a dark 4 s clip and read the pixels: the card must be VISIBLE mid-way
    (before the -loop 1 fix every burned card was fully transparent)."""
    import tempfile
    import numpy as np
    from PIL import Image
    from ucf import config
    from ucf.render_tt import TTRenderer
    cfg = config.load()
    rn = TTRenderer(cfg, {}, ROOT)
    d = Path(tempfile.mkdtemp())
    base = d / "base.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x101010:s=1920x1080:r=30:d=4",
                    "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", "4", "-c:v", "libx264", "-pix_fmt",
                    "yuv420p", "-c:a", "aac", str(base)], check=True)
    out = rn._burn_overlays(base, [(1.0, 3.5, {"kind": "fact", "text": "Visible test card"})], d, ui=lambda *a: None)
    probe = []
    for t in (0.3, 2.0):
        jpg = d / f"f{t}.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", str(out), "-frames:v", "1", str(jpg)],
                       check=True)
        a = np.asarray(Image.open(jpg).convert("L"))[870:950, 120:700]
        probe.append(float(a.mean()))
    assert probe[0] < 40, f"card visible before its start (mean {probe[0]:.0f})"
    assert probe[1] > 120, f"card NOT visible while scheduled (mean {probe[1]:.0f}) - overlay burn is broken"
    # a long card keeps all its words (<= 2 lines) and stays inside the safe band
    from ucf.render_tt import OVERLAY_Y
    long_png = d / "long.png"
    rn._overlay_card_png("coming_up", "Coming up: the judge explains why smashing the phone doesn't erase the "
                         "video at all today", long_png)
    w, h = Image.open(long_png).size
    assert OVERLAY_Y + h <= 1040 and 54 + w <= 1866, f"card {w}x{h} escapes the safe band"
    return f"card region brightness {probe[0]:.0f} before -> {probe[1]:.0f} during; long card {w}x{h} fits"


def t17_zoom_layouts():
    """Layout classifier on drawn 64x36 frames + every strip branch at 360p and 720p -> a 1920x540 strip.
    (Before: the 3-tile crop used 1280x720 pixel numbers, so 360p downloads repeated tiles; 2x2 and
    full-screen solo layouts were not known at all.)"""
    import numpy as np
    from ucf import config
    from ucf.render_tt import TTRenderer, classify_layout, LAYOUTS
    def frame(kind):
        f = np.zeros((36, 64), np.uint8)
        if kind == "2up":
            f[9:27, :] = 120
        elif kind == "solo":
            f[:, :] = 110
        else:
            f[0:18, :] = 170                       # court | judge row on top
            if kind == "full3":
                f[18:36, 26:38] = 90               # one participant picture, centred
            else:
                f[18:36, 10:22] = 90               # two participant pictures, one per lower tile
                f[18:36, 43:55] = 90
        return f
    for kind in LAYOUTS:
        got = classify_layout(frame(kind))
        assert got == kind, f"drawn {kind} frame classified as {got}"
    rn = TTRenderer(config.load(), {}, ROOT)
    for w, h in ((640, 360), (1280, 720)):
        for kind in LAYOUTS:
            chain = rn.strip_chain("0:v", "out", [(0.0, 1.0, kind)])
            r = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"testsrc=s={w}x{h}:d=1:r=30",
                                "-filter_complex", chain, "-map", "[out]", "-frames:v", "1", "-f", "rawvideo",
                                "-pix_fmt", "gray", "-"], capture_output=True)
            assert r.returncode == 0, f"{kind} @ {w}x{h}: ffmpeg failed: {r.stderr.decode()[-300:]}"
            assert len(r.stdout) == 1920 * 540, f"{kind} @ {w}x{h}: strip is {len(r.stdout)} px, not 1920x540"
    # a cut that switches layouts builds one chain with every branch
    mixed = rn.strip_chain("0:v", "out", [(0, 5, "2up"), (5, 9, "grid4"), (9, 14, "full3"), (14, 20, "solo")])
    r = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=s=640x360:d=20:r=30",
                        "-filter_complex", mixed, "-map", "[out]", "-f", "null", "-"], capture_output=True)
    assert r.returncode == 0, f"mixed-layout chain failed: {r.stderr.decode()[-300:]}"
    return "4 layouts classified; every strip branch 1920x540 at 360p + 720p; mixed chain ok"


def t15_hive_and_fallback():
    """Hive (OpenAI-dialect) SSE parsing, rejected-param retry, provider cfg switch and the Pass A
    fallback path - all offline with a fake urlopen."""
    import importlib
    import io
    import os
    import urllib.error
    import urllib.request
    from ucf import brain, mode_all
    importlib.reload(brain)                       # t8 monkeypatches brain._stream_any
    importlib.reload(mode_all)
    os.environ.setdefault("HIVE_API_KEY", "test")
    cfg = _test_cfg()
    h = brain.cfg_for(cfg, "hive")
    assert h["brain"] == "hive" and h["model"].startswith("deepseek-ai/") and int(h["max_tokens"]) == 64000, h
    assert brain.cfg_for(cfg, "anthropic")["model"].startswith("claude-"), "anthropic model not restored"

    def sse(chunks, finish="stop", usage=None):
        ev = [{"choices": [{"delta": {"reasoning_content": "thinking..."}}]}]
        ev += [{"choices": [{"delta": {"content": c}}]} for c in chunks]
        ev += [{"choices": [{"delta": {}, "finish_reason": finish}],
                "usage": usage or {"prompt_tokens": 1000, "completion_tokens": 500,
                                   "prompt_tokens_details": {"cached_tokens": 200}}}]
        return [("data: " + json.dumps(e) + "\n").encode() for e in ev] + [b"data: [DONE]\n"]

    class R(list):
        def __enter__(self): return self
        def __exit__(self, *a): pass

    seen = []
    script = []

    def fake(req, timeout=None):
        body = json.loads(req.data)
        seen.append(body)
        kind = script.pop(0)
        if kind == "400_format":
            raise urllib.error.HTTPError(req.full_url, 400, "bad", {}, io.BytesIO(b"response_format not supported"))
        return R(kind)

    real = urllib.request.urlopen
    urllib.request.urlopen = fake
    try:
        brain.USAGE.clear()
        script[:] = [sse(['{"ok":', ' 1}'])]
        txt = brain._stream_any([{"role": "user", "content": "x"}], dict(h))
        assert txt == '{"ok": 1}', txt
        assert seen[-1]["model"] == h["model"] and seen[-1]["response_format"] == {"type": "json_object"}
        assert len(brain.USAGE) == 1 and brain.USAGE[0]["cost"] is not None, "usage not recorded once with a price"
        # rejected param -> dropped and retried once, then remembered
        script[:] = ["400_format", sse(['{"ok": 2}'])]
        assert brain._stream_any([{"role": "user", "content": "x"}], dict(h)) == '{"ok": 2}'
        assert "response_format" not in seen[-1], "rejected param was not dropped"
        brain._DROPPED.clear()
        # empty reply / cut-off reply -> BrainStop
        for chunks, fin in (([], "stop"), (['{"a"'], "length")):
            script[:] = [sse(chunks, fin)]
            try:
                brain._stream_any([{"role": "user", "content": "x"}], dict(h))
                raise AssertionError("BrainStop expected")
            except brain.BrainStop:
                pass
        # Pass A: hive returns nothing -> with a fallback the loop hands over instead of stopping the run
        ca = dict(h, brain_fallback="anthropic", max_repair_rounds=0)
        script[:] = [sse([])]
        plan, errs = mode_all._pass_a_loop(ca, "prompt", STREAM_LEN, _load_segs(), lambda *a: None, None)
        assert plan is None and errs and "hive" in errs[0], errs
        # ... and the fallback provider's loop produces the plan (mock replays the known-good plan)
        cm = dict(_test_cfg(), brain="mock", mock_reply_file=str(PLAN_FILE), max_repair_rounds=0)
        plan, errs = mode_all._pass_a_loop(cm, "prompt", STREAM_LEN, _load_segs(), lambda *a: None, None, tag="fb_")
        assert plan and not errs, errs[:3]
        # without a fallback the same empty reply stops the run (old behaviour)
        script[:] = [sse([])]
        try:
            mode_all._pass_a_loop(dict(h, brain_fallback="", max_repair_rounds=0), "prompt", STREAM_LEN,
                                  _load_segs(), lambda *a: None, None)
            raise AssertionError("BrainStop expected without fallback")
        except brain.BrainStop:
            pass
    finally:
        urllib.request.urlopen = real
        brain.USAGE.clear()                      # fake calls must not show up as spend
    return "hive SSE + usage + param-drop retry + BrainStop + Pass A fallback hand-over"


def t9_renderer_units():
    r = subprocess.run([sys.executable, str(ROOT / "tests" / "make_sources.py")],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, f"make_sources failed: {r.stdout[-300:]} {r.stderr[-300:]}"
    from ucf import config, tts
    from ucf.render_tt import TTRenderer
    cfg = config.load()
    cfg["tts_order"] = ["dummy"]
    sources = json.loads((ROOT / "state" / "sources.json").read_text(encoding="utf-8"))
    rn = TTRenderer(cfg, sources, ROOT)
    f, a, b = rn.locate(SNAME, 2 * 3600 + 21 * 60 + 54, 2 * 3600 + 22 * 60 + 7)   # hook window
    assert Path(f).exists(), "hook window did not resolve to a fixture clip"
    runs = rn.layout_runs(f, a, b)
    from ucf.render_tt import LAYOUTS
    assert runs and all(cl in LAYOUTS for _, _, cl in runs), f"bad layout runs: {runs}"
    work = ROOT / "work" / "_selftest"
    work.mkdir(parents=True, exist_ok=True)
    ov = work / "ov_test.webm"
    out = rn.overlay("case_started", "", 4.2, work)
    assert Path(out).exists() and Path(out).stat().st_size > 5000, f"overlay missing: {out}"
    wavs = tts.synth_clips("A club owner says one knee stopped a shooting, but the state says he never "
                           "mentioned a gun until a video surfaced. The jury returns Monday.", work / "tts", cfg)
    assert wavs and all(tts.dur(w) <= 18.5 for w in wavs), "dummy TTS clip over limit"
    return f"locate+layout({runs[0][2]})+overlay+tts ok"


def t11_title_validator_v10():
    from ucf import validate_v10 as V10, config
    # number normaliser (test-plan 12.1 #3)
    for text, want in (("thirteen", {13}), ("$30,000", {30000}), ("30K", {30000}), ("30 thousand", {30000}),
                       ("two thousand nineteen", {2019}), ("2019", {2019}), ("11 years", {11})):
        got = V10.extract_numbers(text)
        assert got == want, f"extract_numbers({text!r}) = {got}, want {want}"
    # title table (12.1 #2) - good and bad, every rule family
    cfg = _test_cfg()
    from ucf.config import style_path
    banks = V10.parse_banks(style_path(cfg, cfg["_title_rules"]).read_text(encoding="utf-8"))
    case_text = ("the court is calling 2024 cr2071 state versus hank maldonado. you entered a plea of guilty. "
                 "i am going to sentence you to eleven months in the state jail facility. you failed to appear "
                 "for your sentencing hearing on thirteen occasions. good luck to you sir.")
    case = {"id": 9, "name": "Hank Maldonado", "in": "0:13:25", "out": "0:20:23"}
    def run(titles):
        E = []
        V10.check_titles_v10({"n": 1, "titles": titles, "thumbnail": {"text": "Z"}}, case, case_text,
                             "Judge Boyd", banks, E, [])
        return E
    J = "Judge Boyd"
    good = [
        {"style": "karma", "text": "He Skipped His Own Sentencing 13 Times — " + J + " REFUSES To Blink", "ctr_rank": 1},
        {"style": "quote", "text": "\"I Was Terrified Of Prison\" — " + J + " SHUTS DOWN The Excuse", "ctr_rank": 2},
        {"style": "number", "text": "13 Failed Court Dates Later — " + J + " Reads The Record OUT Loud", "ctr_rank": 3},
        {"style": "twist", "text": "Everyone Expected Mercy — Until " + J + " Pulled His 2011 Record", "ctr_rank": 4},
        {"style": "human", "text": "He Begs " + J + " For One More Chance — The Courtroom Falls SILENT", "ctr_rank": 5},
    ]
    # note: individual titles may still carry T-xx issues (lengths etc.) - we assert SPECIFIC rules fire
    errs = run([dict(t) for t in good])
    assert not any("T-09" in e or "T-03" in e for e in errs), errs
    allE = "\n".join(errs)
    bad = good[0]["text"]
    dup = [dict(t) for t in good]
    dup[1] = dict(dup[1], text=bad)                       # duplicate title -> T-09
    e2 = run(dup)
    assert any("T-09" in x for x in e2), e2
    t_judge = [dict(t) for t in good]
    t_judge[0] = dict(t_judge[0], text="Judge Boyd Skipped Court 13 Times — Judge Boyd REFUSES To Blink")
    assert any("T-03" in x for x in run(t_judge)), "T-03 judge twice"
    t_caps = [dict(t) for t in good]
    t_caps[0] = dict(t_caps[0], text="He Skipped His Own Sentencing 13 Times — " + J + " Refuses To Blink")
    assert any("T-04" in x for x in run(t_caps)), "T-04 no caps"
    t_colon = [dict(t) for t in good]
    t_colon[0] = dict(t_colon[0], text="He Skipped Sentencing: 13 Times — " + J + " REFUSES To Blink")
    assert any("T-05" in x for x in run(t_colon)), "T-05 colon"
    t_verdict = [dict(t) for t in good]
    t_verdict[0] = dict(t_verdict[0], text="He Skipped Court 13 Times — " + J + " Sentenced Him To 11 Years")
    assert any("T-06" in x for x in run(t_verdict)), "T-06 verdict reveal"
    t_number = [dict(t) for t in good]
    t_number[2] = dict(t_number[2], style="number", text="99 Failed Court Dates Later — " + J + " READS The Record")
    assert any("T-07" in x for x in run(t_number)), "T-07 invented number"
    t_surname = [dict(t) for t in good]
    t_surname[0] = dict(t_surname[0], text="Maldonado Skipped Court 13 Times — " + J + " REFUSES To Blink")
    assert any("T-12" in x for x in run(t_surname)), "T-12 surname"
    t_short = [dict(t) for t in good]
    t_short[4] = dict(t_short[4], text="Too Short — " + J + " Cries", style="human")
    assert any("T-02" in x for x in run(t_short)), "T-02 length"
    return "number normaliser + 8 title rule families"


def t12_mode_all_orchestration():
    """12.1 #8: two-pass mock brain, mode all - 2 cases >= 8:00 + 1 short -> 2 ranked videos,
    ranking files, title/backup script-filled, carry-forward untouched."""
    import json as _json
    import tempfile
    from ucf import mode_all, config as CFG, transcript

    def S(a, b, text):
        return {"start": float(a), "end": float(b), "text": text}

    segs = []
    segs += [S(600, 604, "All right. Court is calling 2024 CR0001, state versus John Testor."),
             S(604, 610, "Are you Mr. Testor? Yes ma'am. How do you plead?"),
             S(960, 966, "I was terrified of prison, that is the honest truth."),
             S(966, 972, "You were on probation for the same charge from 2019."),
             S(1080, 1086, "I sentence you to time served on both counts."),
             S(1140, 1146, "You failed to appear on thirteen occasions.")]
    segs += [S(1146, 1150, "Good luck to you sir, you are free to go.")]
    segs += [S(1800, 1804, "Calling 2024 CR0002, state versus Mary Plead. Parties announce."),
             S(2100, 2106, "You have six warrants from 2011 and you still did not come to court."),
             S(2280, 2286, "The court finds you guilty on both files."),
             S(2340, 2344, "You will be taken into custody. Thank you, counsel.")]
    segs += [S(3000, 3004, "Calling 2024 CR0003, cause number 2024 CR0003, reset only."),
             S(3020, 3024, "We will reset this matter to December first.")]
    lines = transcript.compact_lines(segs)

    def phases(c_in, ruling, wrap, call_ev):
        return [{"phase": "call", "tc": c_in, "evidence": call_ev},
                {"phase": "ruling", "tc": ruling, "evidence": "the court finds"},
                {"phase": "wrap_up", "tc": wrap, "evidence": "free to go"}]

    caseA = {"id": 1, "name": "John Testor", "cause_no": "2024 CR0001", "in": "0:10:00", "out": "0:19:30",
             "status": "used", "charge": "Failure to appear", "facing": "Up to 1 year",
             "question": "Will thirteen skipped court dates send him to jail?", "monetisation": "OK",
             "ruling_tc": "0:18:00", "result": {"sentence": "Time served", "conditions": "Released"},
             "interrupted": False, "segments": None, "ruling_deferred": False,
             "phases": phases("0:10:00", "0:18:00", "0:19:00", "court is calling 2024 CR0001"),
             "boundary": {"out_evidence": "free to go"},
             "virality": {"factors": {"judge_confrontation": 15, "emotion": 8, "surprise_ruling": 12,
                                      "numbers": 9, "topic_click": 10, "completeness": 10, "av_quality": 4},
                          "why": "Thirteen skipped dates and a 2019 file the judge opens on the spot"},
             "overlays": [{"tc": "0:11:30", "kind": "fact", "text": "He missed court thirteen times before today",
                           "dur": 7, "ref_tc": None, "evidence": "thirteen occasions"},
                          {"tc": "0:15:00", "kind": "coming_up", "text": "Coming up: the judge opens the 2019 file",
                           "dur": 7, "ref_tc": "0:16:30", "evidence": "from 2019"}]}
    caseB = dict(caseA, id=2, name="Mary Plead", cause_no="2024 CR0002", in_="0:30:00", **{"in": "0:30:00"})
    caseB = {"id": 2, "name": "Mary Plead", "cause_no": "2024 CR0002", "in": "0:30:00", "out": "0:39:30",
             "status": "used", "charge": "Failure to appear x2", "facing": "County jail",
             "question": "Will six warrants follow her into the courtroom?", "monetisation": "OK",
             "ruling_tc": "0:38:00", "result": {"sentence": "Guilty on both files", "conditions": "Custody"},
             "interrupted": False, "segments": None, "ruling_deferred": False,
             "phases": phases("0:30:00", "0:38:00", "0:39:00", "calling 2024 CR0002"),
             "boundary": {"out_evidence": "taken into custody"},
             "virality": {"factors": {"judge_confrontation": 12, "emotion": 6, "surprise_ruling": 8,
                                      "numbers": 7, "topic_click": 8, "completeness": 10, "av_quality": 4},
                          "why": "Six warrants read out loud one after another"},
             "overlays": [{"tc": "0:35:10", "kind": "coming_up", "text": "Coming up: the judge reads both warrants",
                           "dur": 7, "ref_tc": "0:36:30", "evidence": "six warrants from 2011"}]}
    caseC = {"id": 3, "name": "Reset Only", "cause_no": "2024 CR0003", "in": "0:50:00", "out": "0:51:00",
             "status": "skipped", "reject_reason": "under 8:00", "charge": "Reset", "facing": "None",
             "question": "Reset?", "ruling_tc": "0:50:40", "result": {"sentence": "Reset", "conditions": "None"},
             "phases": phases("0:50:00", "0:50:40", "0:50:55", "calling 2024 CR0003")}
    passA = {"schema": "v10", "judge_name": "Judge Test", "cases": [caseA, caseB, caseC], "videos": [],
             "gaps": [{"in": "0:00:00", "out": "0:10:00", "kind": "NON-CASE", "label": "pre-roll"},
                      {"in": "0:19:30", "out": "0:30:00", "kind": "NON-CASE", "label": "attorney talk"},
                      {"in": "0:39:30", "out": "0:50:00", "kind": "NON-CASE", "label": "attorney talk"},
                      {"in": "0:51:00", "out": "0:55:00", "kind": "NON-CASE", "label": "jurors excused"}],
             "source_file": "mock.mp4", "stream_length": "0:55:00"}

    def video_obj(case, n, name_bits, crime_num):
        J = "Judge Test"
        return {"case_ids": [case["id"]], "bridges": [], "rank": n, "n": n,
                "hook": {"in": "0:16:00", "out": "0:16:12", "spoken": "", "headline": "Thirteen Skipped Dates"} if case["id"] == 1
                        else {"in": "0:35:00", "out": "0:35:12", "spoken": "", "headline": "Six Warrants Read Out"},
                "intro_seconds": 7.47, "vo1": {"text": ""},
                "vo_final": {"text": "Two hearings, one long morning. One defendant skipped court " + crime_num +
                          " times and asked the court for one more chance. The judge opened an old file instead "
                          "and read it out loud, line by line, in front of everyone. Fair or too harsh, or exactly "
                          "right? Tell us below, and subscribe for the next hearing."},
                "quiz": {"question": "What landed this defendant in court?", "options": {"A": "Skipped court", "B": "Jury duty", "C": "Parking"},
                         "answer": "A  Skipped court"},
                "titles": ([
                    {"style": "karma", "text": f"6 Warrants And She Still Showed No Fear — {J} REFUSES To Blink",
                     "primary": True, "primary_why": "the warrant stack is the shock", "ctr_rank": 1},
                    {"style": "quote", "text": f"\"You Have Six Warrants From 2011\" — {J} SHOCKED Everyone Again", "ctr_rank": 2},
                    {"style": "number", "text": f"6 Warrants From 2011 Were Waiting — {J} RIPS Open The Entire File In Court", "ctr_rank": 3},
                    {"style": "twist", "text": f"Everyone Thought She'd Walk Free — Until {J} SHOCKED The Court", "ctr_rank": 4},
                    {"style": "human", "text": f"Her Mother Begs {J} For Mercy — The Whole Courtroom Went SILENT", "ctr_rank": 5}]
                    if case["id"] == 2 else [
                    {"style": "karma", "text": f"He Skipped His Court Dates {crime_num} Times — {J} REFUSES To Blink",
                     "primary": True, "primary_why": "strongest number plus a hard refusal", "ctr_rank": 1},
                    {"style": "quote", "text": f"\"I Was Terrified Of Prison\" — {J} SHUTS DOWN That Excuse In Court", "ctr_rank": 2},
                    {"style": "number", "text": f"{crime_num} Failed Court Dates Later — {J} RIPS Open The Entire Old File", "ctr_rank": 3},
                    {"style": "twist", "text": f"Everyone Thought He'd Walk Free — Until {J} SHOCKED The Court", "ctr_rank": 4},
                    {"style": "human", "text": f"His Mother Begs {J} For Mercy — The Whole Courtroom Went SILENT", "ctr_rank": 5}]),
                "thumbnail": ({"window_in": "0:36:00", "window_out": "0:36:04", "look_for": "the reaction",
                               "text": "WARRANTS WERE WAITING", "gold_word": "WAITING", "placement": "top"}
                              if case["id"] == 2 else
                              {"window_in": "0:17:00", "window_out": "0:17:19", "look_for": "the reaction",
                               "text": "THIRTEEN SKIPPED", "gold_word": "THIRTEEN", "placement": "top"}),
                "description": {"first_line": "What happens after thirteen skipped court dates?",
                                "what_happens": "The defendant returns to court after failing to appear again and again. The judge opens an old file and reads it out loud before deciding.",
                                "search_question": "What happens if you skip court in Texas?",
                                "answer": "Skipping court in Texas can lead to a warrant, a revoked bond and extra charges. At the hearing the judge hears why the date was missed and can continue probation, add conditions or revoke it entirely. In this docket the court read an older file out loud before ruling, which is why the number of missed dates mattered so much. This is a summary of one hearing, not legal advice.",
                                "related_question": "Was the judge fair? Tell us below."},
                "chapters": ([{"tc": case["in"], "label": "The hearing begins"},
                              {"tc": "0:35:30", "label": "Six warrants read out"},
                              {"tc": "0:38:00", "label": "The ruling"},
                              {"tc": "0:38:40", "label": "Taken into custody"}] if case["id"] == 2 else
                             [{"tc": case["in"], "label": "The hearing begins"},
                              {"tc": "0:15:30", "label": "Terrified of prison"},
                              {"tc": "0:16:30", "label": "The old file opens"},
                              {"tc": "0:17:30", "label": "Facing the court"}]),
                "tags": ["court", "judge", "hearing", "skipped court", "failure to appear", "courtroom",
                         "real court", "texas court", "sentencing", "docket"],
                "pinned_comment": "Fair or too harsh? Tell us below.",
                "community_post": "New hearing out now: thirteen skipped dates and an old file read out loud. Was the judge fair? Tell us what you think below.",
                "publish": {"slot": "9am ET"}, "verdict_pending": False, "followup_owed": None,
                "overlays": case.get("overlays", [])}

    tmp = Path(tempfile.mkdtemp())
    cfg = CFG.load(style="trial_tales")
    cfg.update({"brain": "mock", "mode": "all", "title_system": "v10", "_mode_source": "cli",
                "max_repair_rounds": 0, "_source_file": "mock.mp4"})
    cfg["mock_passA_replies"] = [str(tmp / "a.json")]
    cfg["mock_passB_replies"] = [str(tmp / "b1.json"), str(tmp / "b2.json")]
    (tmp / "a.json").write_text(_json.dumps(passA), encoding="utf-8")
    (tmp / "b1.json").write_text(_json.dumps({"video": video_obj(caseA, 1, "a", "13")}), encoding="utf-8")
    (tmp / "b2.json").write_text(_json.dumps({"video": video_obj(caseB, 2, "b", "6")}), encoding="utf-8")

    work = tmp / "work"
    work.mkdir()
    plan, errs = mode_all.build_plan(segs, lines, "SCAN", 3300, cfg, print, work)
    assert not errs, f"build_plan errors: {errs[:6]}"
    assert len(plan["videos"]) == 2, f"expected 2 videos, got {len(plan['videos'])}"
    assert [v["rank"] for v in plan["videos"]] == [1, 2]
    assert plan["videos"][0]["title"], "title script-filled from primary"
    assert plan["videos"][0]["backup_title"], "backup script-filled"
    skipped = [c for c in plan["cases"] if c["status"] == "skipped"]
    assert [c["id"] for c in skipped] == [3], skipped
    assert plan.get("carry_forward", None) is None
    mode_all.write_ranking(plan, work, cfg, "mock")
    assert (work / "ranking.md").exists() and (work / "ranking.csv").exists()
    assert "Thirteen" in (work / "ranking.md").read_text(encoding="utf-8") or "13" in (work / "ranking.md").read_text(encoding="utf-8")
    return "2 ranked videos, skipped list, ranking.md/csv, script-filled titles"


def t13_boundary_engine():
    """12.1 #6: synthetic signals - lawyer swap ignored, ruling floor held, wrap-up snap, next-call pull."""
    from ucf import boundary as BD
    cfg = {"mode": "all", "boundary": {"enabled": True, "window_s": 120, "ocr": "off",
                                       "weights": {"next_call": 3.0, "wrap_up": 2.0, "tile_count": 1.5,
                                                   "tile_label": 1.5, "last_name": 1.0, "silence": 1.0,
                                                   "before_ruling": -4.0, "call_inside": -5.0}}}
    case = {"id": 1, "name": "John Testor", "in": "0:10:00", "out": "0:19:30", "status": "used",
            "ruling_deferred": False,
            "phases": [{"phase": "call", "tc": "0:10:00", "evidence": "calling"},
                       {"phase": "ruling", "tc": "0:18:00", "evidence": "I sentence you"},
                       {"phase": "wrap_up", "tc": "0:19:00", "evidence": "good luck"}]}

    def mk_ev(wrap, calls, tiles, silence):
        return {"wrap_up": wrap, "call_outs": calls, "silence": silence, "tile_events": tiles,
                "video_available": False, "windows_done": ["all"]}

    # (a) lawyer swap mid-case must NOT move OUT before the ruling
    ev = mk_ev([{"tc": 1140.0, "phrase": "good luck"}], [], [{"tc": 840.0, "from": 3, "to": 2}], [])
    r = BD.refine_case(dict(case), ev, None, cfg)
    assert r and parse_tc(r[1]) >= 1083, f"OUT moved before ruling: {r}"
    # (b) wrap-up snap: OUT snaps to just after the wrap-up phrase
    ev = mk_ev([{"tc": 1150.0, "phrase": "you're free to go"}],
               [{"tc": 1172.0, "phrase": "calling cr0002"}], [], [])
    r = BD.refine_case(dict(case), ev, None, cfg, next_in=1175.0)
    assert r and 1149 <= parse_tc(r[1]) <= 1156, f"wrap-up snap off: {r}"
    # (c) next call-out pulls OUT to just before it, never past it
    ev = mk_ev([{"tc": 1080.0, "phrase": "good luck"}],
               [{"tc": 1170.0, "phrase": "court is calling cr0009"}], [], [])
    r = BD.refine_case(dict(case), ev, None, cfg, next_in=1172.0)
    assert r and parse_tc(r[1]) <= 1171.9 and parse_tc(r[1]) >= 1140, f"next-call pull off: {r}"
    # (d) confidence + signals recorded
    ev = mk_ev([{"tc": 1150.0, "phrase": "good luck"}], [{"tc": 1172.0, "phrase": "calling cr0002"}], [], [])
    c2 = dict(case)
    BD.refine_case(c2, ev, None, cfg, next_in=1175.0)
    assert "boundary" in c2 and c2["boundary"]["confidence"] >= 0 and c2["boundary"]["signals"]
    return "swap ignored, ruling floor, snap, next-call pull, confidence"


def t14_overlay_sched():
    """12.1 #4 + #5: scheduler spacing/head-tail/conflicts + safe-zone geometry for every layout."""
    from ucf import overlay_sched as OS
    # geometry: card rect inside safe zone, clear of footage, for both looks
    for look in ("tt", "ov"):
        for text in ("short fact", "a much longer fact line that wraps onto a second line for sure"):
            r = OS.card_rect(look, text)
            OS.assert_safe(look, r)
    try:
        OS.assert_safe("tt", (0, 300, 900, 500))          # squarely over the footage strip
        raise SystemExit("safe-zone assertion did not fire")
    except ValueError:
        pass
    # scheduler: head/tail exclusion, busy conflict shift, min gap
    cfg = {"overlays": {"enabled": True, "every_s": 270, "min_gap_s": 180, "skip_head_s": 40,
                        "skip_tail_s": 30, "dur_s": 7.0, "max_words": 20}}
    case = {"id": 1, "in": "0:10:00", "out": "0:19:30", "overlays": [
        {"tc": "0:11:00", "kind": "fact", "text": "fact one"},
        {"tc": "0:16:00", "kind": "coming_up", "text": "coming up", "ref_tc": "0:18:30"}]}
    # 10-min case mapped 1:1 onto a 700 s video starting at output 0 (case fills the video body)
    src_to_out = lambda tc: tc - 600 + 30.0            # case starts at output 0:30 (after hook+intro)
    out = OS.schedule(case, src_to_out, 700, [(30.0, 35.0)], cfg)
    assert out, "scheduler returned nothing"
    for i, (s, e, o) in enumerate(out):
        assert 40 <= s and e <= 700 - 30, f"head/tail violated: {s}-{e}"
        if i:
            assert s - out[i - 1][1] >= 179, f"min gap violated at {s}"
    kinds = [o["kind"] for _, _, o in out]
    assert "coming_up" in kinds, kinds
    # ref_tc too close -> coming_up dropped
    case2 = {"id": 1, "in": "0:10:00", "out": "0:19:30", "overlays": [
        {"tc": "0:15:00", "kind": "coming_up", "text": "soon", "ref_tc": "0:15:20"}]}
    assert OS.schedule(case2, src_to_out, 700, [], cfg) == []
    return "geometry + spacing + conflicts + coming_up window"


def t10_end_to_end():
    out_root = ROOT / "output"
    for old in out_root.glob("2026-*_lVQ79x0Hd_w"):
        shutil.rmtree(old)                     # cached parts would fake a pass
    for old in (ROOT / "work" / "lVQ79x0Hd_w").glob("*.mp4"):
        old.unlink()
    # Same idea as _test_cfg(): the fixture is a v9 plan of 28:35, so pin the legacy band + title system instead
    # of reading the owner's live config.json (its 50-70 min rule made this test fail regardless of the code).
    owner = json.loads((ROOT / "config.json").read_text(encoding="utf-8")) if (ROOT / "config.json").exists() else {}
    tcfg = ROOT / "work" / "_selftest" / "e2e_config.json"
    tcfg.parent.mkdir(parents=True, exist_ok=True)
    tcfg.write_text(json.dumps(dict(owner, runtime_min=20 * 60, runtime_max=30 * 60, title_system="v9"), indent=1),
                    encoding="utf-8")
    cmd = [sys.executable, str(ROOT / "run_stream.py"), "--config", str(tcfg),
           "--video-file", str(FIX / "r1.mp4"), "--stream-id", "lVQ79x0Hd_w",
           "--stream-length", "3:00:23", "--transcript-file", str(NEXLEV),
           "--plan", str(PLAN_FILE), "--brain", "manual", "--tts", "dummy", "--confirm-tts"]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=2400)
    assert r.returncode == 0, f"run_stream exited {r.returncode}:\n...{r.stdout[-1500:]}\n{r.stderr[-500:]}"
    folders = list(out_root.glob("2026-*_lVQ79x0Hd_w/Video_01_*"))
    assert folders, f"no video folder:\n{r.stdout[-800:]}"
    d = folders[0]
    qc = json.loads((d / "qc.json").read_text(encoding="utf-8"))
    assert qc.get("ok") is True, f"QC not ok: {json.dumps(qc)[:400]}"
    vid = d / "video.mp4"
    assert vid.exists() and vid.stat().st_size > 20_000_000, "video.mp4 missing/too small"
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                "-of", "default=nw=1:nk=1", str(vid)], capture_output=True, text=True).stdout)
    assert 1500 <= dur <= 1950, f"video duration {dur/60:.1f} min outside the 25-32.5 min band"
    md = (d / "metadata.txt").read_text(encoding="utf-8")
    assert "GUN" in md and "chapters" in md.lower(), "metadata missing title/chapters"
    rows = (d / "footage_log.csv").read_text(encoding="utf-8").strip().splitlines()
    assert len(rows) > 5 and "youtu.be" in " ".join(rows), "footage log incomplete"
    assert (d / "contact_sheet.jpg").exists(), "no contact sheet"
    return f"{dur/60:.1f} min, QC ok, {len(rows)-1} footage rows"


def main():
    print("H Labs self-test matrix")
    check(1, "environment", t1_environment)
    check(2, "imports", t2_imports)
    check(3, "transcript + whisper", t3_transcript)
    check(4, "scan", t4_scan)
    check(5, "validator (good plan)", t5_validator_good)
    check(6, "validator (bad plan blocked)", t6_validator_bad)
    check(7, "vo splitter", t7_vo_splitter)
    check(8, "brain plumbing", t8_brain_plumbing)
    check(9, "renderer units", t9_renderer_units)
    if QUICK:
        RESULTS.append((10, "end-to-end render", True, "skipped (--quick)", 0.0))
        print("  SKIP  10 end-to-end render (--quick)")
    else:
        print("  ... test 10 renders the full 28 min video, this takes a few minutes")
        check(10, "end-to-end render", t10_end_to_end)
    check(11, "v10 title validator", t11_title_validator_v10)
    check(13, "boundary engine", t13_boundary_engine)
    check(14, "overlay scheduler", t14_overlay_sched)
    check(15, "hive provider + fallback", t15_hive_and_fallback)
    check(16, "overlay burn visible", t16_overlay_burn)
    check(17, "zoom layouts", t17_zoom_layouts)
    bad = [r for r in RESULTS if not r[2]]
    print("\n" + "=" * 60)
    print(f"RESULT: {sum(1 for r in RESULTS if r[2])}/{len(RESULTS)} passed" + (f"  FAILURES: {[r[1] for r in bad]}" if bad else "  - ALL GREEN"))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
