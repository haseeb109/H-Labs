════════════════════════════════════════════════════════════════
 PASS B — EXACT SHAPE OF THE "video" OBJECT  (field names and types are machine-checked)
════════════════════════════════════════════════════════════════
Use these field names exactly. Objects stay objects, strings stay strings. Do not rename
"in"/"out" to "tc_in"/"tc_out", do not turn an object into a plain string or a list.
Times are STREAM clock "H:MM:SS".

{"video": {
  "case_ids": [<this case id>],
  "bridges": [],
  "hook": {"in": "H:MM:SS", "out": "H:MM:SS",            // 10-15 s, inside the back 60% of the case
           "spoken": "full spoken text of the clip",
           "headline": "3-9 word caption shown under the teaser"},   // no trailing period
  "intro_seconds": 6,
  "vo_final": {"text": "45-70 words, every sentence < 35 words, ends with a like/subscribe ask"},
  "quiz": {"question": "...", "options": {"A": "...", "B": "...", "C": "..."},
           "answer": "B  text   (or: left open - answer in the comments)"},
  "thumbnail": {"window_in": "H:MM:SS", "window_out": "H:MM:SS (3 s later)", "look_for": "expression",
                "text": "2-5 words", "gold_word": "ONE word from text", "placement": "top"},
  "titles": [ {"style": "karma|quote|number|twist|human", "text": "...", "ctr_rank": 1},   // exactly 5,
              ... ],                                     // one of them also has "primary": true, "primary_why": "..."
  "description": {
    "first_line": "one line restating the title's question",
    "what_happens": "3-4 lines, no ruling",
    "pending_note": null,
    "search_question": "a real search question",
    "answer": "~100 words, not repeating the question as its first words",
    "related_question": "related-video question"
  },
  "chapters": [ {"tc": "H:MM:SS", "label": "story beat"} ],   // first tc = the case IN; none in the last 60 s
  "tags": ["12-15 case-specific tags"],
  "pinned_comment": "...",
  "community_post": "~40 words",
  "publish": {"slot": "9am ET"},                         // 9am ET | 1pm ET | 6pm ET
  "overlays": [ {"tc": "H:MM:SS", "kind": "...", "text": "...", "dur": 7, "ref_tc": null, "evidence": "..."} ],
  "verdict_pending": false,
  "followup_owed": null                                  // or {"case": "name", "ruling_expected": "date"}
}}
Do NOT write "title", "backup_title" or "rank" - the script fills them from "titles".
