════════════════════════════════════════════════════════════════
 DOCUMENTARY STYLE: EVIDENCE BOARD  (add "doc": {...} INSIDE the "video" object)
════════════════════════════════════════════════════════════════
A detective's cork board: every fact becomes a pinned card, red strings connect people and evidence, the master
case file sits in the middle; each new chapter pins NEW EVIDENCE.

FIRST the normal video fields - they are REQUIRED here too: hook (in/out inside the back 60% of the case), vo1.text
(25-35 words, the story set-up, spoken by the narrator), vo_final.text (45-70 words, ends with a question to the viewer),
titles, thumbnail, description, chapters, tags, quiz. vo1 and vo_final must not repeat each other's words.

THEN the "doc" object below. Only the fields listed here are used by this style - do not add others. Never invent:
every fact must be said in the transcript. Timecodes are H:MM:SS of the stream and must lie inside this case.

"doc": {
  "date": "MAY 15, 2023",                     // hearing date ONLY if said in court or in the stream title, else omit
  "case_doc": {                               // THE CASE DOCUMENT shown in the video: value + the exact words that prove it
     "defendant":    {"value": "Summer Diaz",          "evidence": "Summer Diaz, you are charged with"},
     "age":          {"value": "26",                   "evidence": "...26 years old..."},
     "cause_no":     {"value": "2023CR0412",           "evidence": "...cause number 2023CR0412..."},
     "charges":      {"value": ["Tampering with a governmental record"], "evidence": "..."},
     "bond":         {"value": "$3,000",               "evidence": "bond is set at $3,000"},
     "plea":         {"value": "Guilty",               "evidence": "..."},
     "state_asked":  {"value": "2 years",              "evidence": "..."},
     "defense_asked":{"value": "probation",            "evidence": "..."},
     "result":       {"value": "Deferred adjudication","evidence": "..."},
     "sentence":     {"value": "5 years",              "evidence": "..."},
     "conditions":   {"value": ["GPS monitor"],        "evidence": "..."},
     "next_date":    {"value": "June 12",              "evidence": "..."}
  },                                          // evidence = words copied from the transcript (a fact without it is dropped)
                                              // fill only what is said; leave a field out rather than guess
  "rulings": [ {"tc": "H:MM:SS", "text": "Bond: $150,000 + GPS"} ],  // every ruling, the moment it is said
  "turns": [ {"from": "H:MM:SS", "to": "H:MM:SS", "who": "JUDGE"} ],  // who speaks (JUDGE | DEFENDANT | LAWYER | STATE | WITNESS)
  "chapters": [ {"at": "H:MM:SS", "title": "THE PLEA"} ],      // 2-5 chapter starts inside the case, 1-3 word titles
  "cold_open": [ {"in": "H:MM:SS", "out": "H:MM:SS", "label": "THE MOMENT"} ],     // 1 strongest moment, 6-30 s
  "board": {"items": [{"id": "d", "label": "SUMMER", "sub": "THE DEFENDANT"}, {"id": "c", "label": "FAKE ID", "sub": "THE EVIDENCE"}],
            "links": [["d", "c", "LIED ABOUT"]]},   // 4-8 items (people, evidence, places, dates said in court; label 1-3 words,
                                                     // sub 2-4 words) + links (which connect and why, 1-3 words)
  "tease": "Every piece of this case is on this board.",
  "backstory_text": "Narration read while the pins appear: 3-5 short sentences, facts said in court only."
}
Legal-safe wording in narration: "police say", "prosecutors claim", "the court heard". The judge is "the judge" in narration.
