"""Smoke test of the Overruled renderer on pre-cut clips (no validator): short Rendon + Maldonado excerpt."""
import json, sys, time
sys.path.insert(0, ".")
from pathlib import Path
from ucf import config
from ucf.render_ov import OVRenderer
cfg = config.load(); cfg.update(config.OVERRULED); cfg["skin"] = "overruled"; cfg["tts_order"] = ["dummy"]
plan = json.load(open("tests/rendon_2025-05-09_plan.json"))
src = json.load(open("state/sources.json"))
c1 = plan["cases"][0]; c2 = plan["cases"][1]
# mini case 1: 2:20:00-2:25:30 (hook 2:21:54 inside), mini case 2: first 3 minutes of Maldonado
c1 = dict(c1, **{"in": "2:19:00", "out": "2:22:20", "removes": [], "remove": None})
c2 = dict(c2, **{"in": "0:13:25", "out": "0:16:30"})
plan["cases"] = [c1, c2]
v = plan["videos"][0]
v["takes"] = [{"tc": "2:20:30", "text": "The prosecutor's point is simple: the owner describes a gun in court that he never mentioned to the detective."}]
v["exchanges"] = [{"tc": "2:22:04", "ts": "2:22:04", "who_q": "PROSECUTOR", "q": "When did you mention that gun?", "who_a": "OWNER", "a": "I don't think I did."}]
out = Path("output/_ov_smoke"); out.mkdir(parents=True, exist_ok=True)
rn = OVRenderer(cfg, src, Path("."))
t = time.time()
res = rn.render_video(plan, v, out, Path("work/lVQ79x0Hd_w/tts"), print)
print("done", res["final"], res["measured_total"], time.time() - t, res.get("subscribe"))
