"""Renders a ~1-minute STYLE PROOF from a short real slice of the Boyd stream (no validator): shows hook, intro, case labels, recaps."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ucf import config
from ucf.render_tt import TTRenderer

S = sys.argv[1]
OUT = Path(sys.argv[2])
cfg = config.load(); cfg["tts_order"] = [sys.argv[3] if len(sys.argv) > 3 else "dummy"]
cases = [{"id": 1, "name": "Proof A", "in": "0:00:02", "out": "0:00:13"}, {"id": 2, "name": "Proof B", "in": "0:00:14", "out": "0:00:26"}]
plan = {"source_file": "proof.webm", "cases": cases}
video = {"n": 1, "case_ids": [1, 2],
         "hook": {"in": "0:00:03", "out": "0:00:09", "headline": "He Said He Was Not Used to This"},
         "bridges": [{"after_case_id": 1, "text": "He tells the judge he is not used to any of this. Did he understand the plea? Next, the same judge explains what a jury trial would really mean."}],
         "vo_final": {"text": "Two moments, one hearing, and a defendant still learning how the process works. Would you have asked for more time? Subscribe for the next real Bexar County ruling."}}
rn = TTRenderer(cfg, {"proof.webm": {"path": S, "url": ""}}, Path(__file__).resolve().parent.parent)
OUT.mkdir(parents=True, exist_ok=True)
res = rn.render_video(plan, video, OUT, OUT / "tts", print)
print(res["final"], res["measured_total"], res["ai_clips"])
