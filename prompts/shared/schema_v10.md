════════════════════════════════════════════════════════════════
 v10 SCHEMA ADDITIONS  (add these to the JSON described above)
════════════════════════════════════════════════════════════════
Top level:   "schema": "v10", "judge_name": "Judge <Surname>" (as heard in court)
Each case:   "phases": [{"phase","tc","evidence"}], "interrupted": false,
             "segments": null | [{"in","out"}],
             "boundary": {"out_evidence": "<≤12-word quote>"},
             "virality": {"factors": {...}, "why": "..."}      (mode all; optional otherwise)
             "overlays": [{"tc","kind","text","dur","ref_tc","evidence"}]
             status may also be "skipped" (mode all only)
Each video:  "titles": [ {"style","text","ctr_rank"} x5, one with "primary": true and
             "primary_why" ]
SCRIPT-FILLED - DO NOT WRITE: video.rank, video.title, video.backup_title,
virality.total, boundary.out_brain / out_score / confidence / signals /
start_confirmed / vision_used, mode.
In mode "all" PASS A returns "cases" only; PASS B returns {"video": {...}}.
