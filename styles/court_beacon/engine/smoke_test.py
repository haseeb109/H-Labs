"""Run from the H Labs folder:  python3 styles/court_beacon/engine/smoke_test.py tests/rendon_2025-05-09_plan.json state/sources.json
Smoke test of the Court Beacon TV renderer on pre-cut clips (no validator, dummy voice)."""
import json, sys, time
sys.path.insert(0, ".")
from pathlib import Path
from ucf import config
import importlib.util
_spec = importlib.util.spec_from_file_location("cb", "styles/court_beacon/engine/render_cb.py")
_m = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_m)
CBRenderer = _m.CBRenderer

cfg = config.load(style="court_beacon"); cfg["tts_order"] = ["dummy"]
plan = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "tests/rendon_2025-05-09_plan.json"))
src = json.load(open(sys.argv[2] if len(sys.argv) > 2 else "state/sources.json"))
c1, c2 = plan["cases"][0], plan["cases"][1]
c1 = dict(c1, **{"in": "2:19:00", "out": "2:21:40", "removes": [], "remove": None, "charge": "Aggravated assault",
                 "facing": "2 to 20 years", "proceeding": "jury trial, day 3", "moment_tc": "2:20:10",
                 "phases": [{"phase": "call", "tc": "2:19:00"}, {"phase": "evidence_or_argument", "tc": "2:19:30"}],
                 "overlays": [{"tc": "2:19:45", "kind": "fact", "text": "2 statements to the detective. Neither one mentions a gun."},
                              {"tc": "2:20:40", "kind": "watch", "text": "his answer"}]})
c2 = dict(c2, **{"in": "0:13:25", "out": "0:15:40", "charge": "Two felony vehicle cases", "facing": "Up to 2 years",
                 "proceeding": "sentencing", "ruling_deferred": False,
                 "phases": [{"phase": "call", "tc": "0:13:25"}, {"phase": "plea_or_admonish", "tc": "0:14:00"}, {"phase": "ruling", "tc": "0:15:00"}],
                 "overlays": [{"tc": "0:14:10", "kind": "so_far", "text": "Plea bargain with a 12-month cap · He skipped his own sentencing date · Arrested two weeks later"}]})
plan["cases"] = [c1, c2]
v = plan["videos"][0]
v["case_ids"] = [c1["id"], c2["id"]]
v["hook"] = dict(v["hook"], **{"in": "2:20:50", "out": "2:21:02", "headline": "He never told police about the *gun*"})
v["exchanges"] = [{"tc": "2:21:00", "ts": "2:21:00", "who_q": "PROSECUTOR", "q": "When did you mention that gun?", "who_a": "OWNER", "a": "I don't think I did."}]
v["quiz"] = {"question": "What did the club owner never tell police about?", "options": {"A": "a stolen radio", "B": "a gun", "C": "a camera"}}
v["thumbnail"] = dict(v["thumbnail"], **{"window_in": "2:20:10", "window_out": "2:20:13", "text": "HE NEVER TOLD POLICE", "gold_word": "POLICE"})
out = Path("output/_cb_smoke"); out.mkdir(parents=True, exist_ok=True)
rn = CBRenderer(cfg, src, Path("."))
rn.log = []
t = time.time()
res = rn.render_video(plan, v, out, Path("work/_cb_smoke_tts"), print)
th = rn.thumbnail(plan, v, out)
print("done", res["final"], round(res["measured_total"], 1), round(time.time() - t), res["subscribe"], res["overlays"], th)
