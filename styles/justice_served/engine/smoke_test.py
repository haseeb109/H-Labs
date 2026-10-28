"""Smoke test of the Justice Served renderer (no validator, dummy voice).  Run from the H Labs folder:

    python3 styles/justice_served/engine/smoke_test.py path/to/clip.mp4

clip.mp4 = any court clip (Zoom 2-tile gallery works best), >= 65 s. The test cuts two short "cases" out of it
(Frank Corona probation hearing sample: stream HKURkJmb-K8, 2:07:05-2:08:10 -> clip seconds 0-65).
Output: output/_js_smoke/video.mp4 + thumbnail.jpg"""
import importlib.util
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")
from ucf import config  # noqa: E402

_spec = importlib.util.spec_from_file_location("js", "styles/justice_served/engine/render_js.py")
_m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_m)

# the sample cases are short: relax the spacing rules so every card type shows up
_m.HEAD_SKIP = _m.TAIL_SKIP = _m.CARD_HEAD = _m.CARD_TAIL = 4.0
_m.ITEM_GAP = 1.0

clip = Path(sys.argv[1] if len(sys.argv) > 1 else "samples_src/clip.mp4").resolve()
cfg = config.load(style="justice_served")
cfg["tts_order"] = ["dummy"]
plan = json.load(open("tests/rendon_2025-05-09_plan.json"))
src = {"clip.mp4": {"path": str(clip), "url": "https://youtu.be/HKURkJmb-K8"}}
c1, c2 = plan["cases"][0], plan["cases"][1]
c1 = dict(c1, **{"name": "Frank Corona", "in": "0:00:03", "out": "0:00:40", "removes": [], "remove": None, "proceeding": "probation hearing",
                 "charge": "Probation violation", "facing": "up to 2 years", "question": "Will missed check-ins cost him his freedom?",
                 "overlays": [{"tc": "0:00:10", "kind": "fact", "text": "26 months with no check-in. The State asks for 18 months.", "dur": 7}]})
c2 = dict(c2, **{"name": "Second Defendant", "in": "0:00:41", "out": "0:01:03", "removes": [], "remove": None, "proceeding": "sentencing",
                 "charge": "Two felony vehicle cases", "facing": "up to 2 years", "question": "Will the judge give the full two years?"})
plan["cases"] = [c1, c2]
plan["source_file"] = "clip.mp4"
v = plan["videos"][0]
v["case_ids"] = [c1["id"], c2["id"]]
v["hook"] = dict(v["hook"], **{"in": "0:00:22", "out": "0:00:34", "headline": "Two years of *missed* check-ins. Why?"})
v["takes"] = [{"tc": "0:00:28", "text": "The judge says nobody can help someone who does not show up.", "dur": 6}]
v["exchanges"] = [{"tc": "0:00:46", "ts": "0:00:46", "who_q": "JUDGE", "q": "You tell why you didn't report?", "who_a": "DEFENDANT", "a": "I was scared."}]
v["quiz"] = {"question": "How long did the judge give him?", "options": {"A": "6 months", "B": "18 months", "C": "2 years"}}
v["thumbnail"] = dict(v["thumbnail"], **{"window_in": "0:00:22", "window_out": "0:00:25", "text": "SCARED TO REPORT", "gold_word": "SCARED"})
out = Path("output/_js_smoke")
out.mkdir(parents=True, exist_ok=True)
rn = _m.JSRenderer(cfg, src, Path("."))
rn.log = []
t = time.time()
res = rn.render_video(plan, v, out, Path("work/_js_smoke_tts"), print)
th = rn.thumbnail(plan, v, out)
print("done", res["final"], round(res["measured_total"], 1), "s in", round(time.time() - t), "s")
print("segments:", [(r["kind"], round(r["dur"], 1)) for r in res["rows"]])
print("subscribe:", res["subscribe"], "overlays:", res["overlays"], "thumb:", th)
