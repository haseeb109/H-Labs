════════════════════════════════════════════════════════════════
 DOCUMENTARY STYLE FIELDS  (add "doc": {...} INSIDE the "video" object)
════════════════════════════════════════════════════════════════
This style tells ONE defendant's story like a documentary. Besides every normal field, the "video" object carries a
"doc" object. Every field is optional, but the more of them you fill WITH EVIDENCE, the better the video. Never invent:
every fact must be said in the transcript. Timecodes are H:MM:SS of the stream and must lie inside this case.

"doc": {
  "date": "MAY 15, 2023",                     // hearing date ONLY if said in court or in the stream title, else omit
  "case_doc": {                               // THE CASE DOCUMENT shown in every video. value + the exact words that prove it
     "defendant":    {"value": "Summer Diaz",          "evidence": "Summer Diaz, you are charged with"},
     "age":          {"value": "26",                   "evidence": "...26 years old..."},
     "cause_no":     {"value": "2023CR0412",           "evidence": "...cause number 2023CR0412..."},
     "charges":      {"value": ["Tampering with a governmental record"], "evidence": "..."},
     "offense_date": {"value": "...", "evidence": "..."},
     "bond":         {"value": "$3,000",               "evidence": "bond is set at $3,000"},
     "plea":         {"value": "Guilty",               "evidence": "..."},
     "state_asked":  {"value": "2 years",              "evidence": "..."},
     "defense_asked":{"value": "probation",            "evidence": "..."},
     "result":       {"value": "Deferred adjudication","evidence": "..."},
     "sentence":     {"value": "5 years",              "evidence": "..."},
     "conditions":   {"value": ["GPS monitor"],        "evidence": "..."},
     "next_date":    {"value": "June 12",              "evidence": "..."}
  },                                          // evidence = words copied from the transcript (a fact without it is dropped)
  "charge_level": "F3",                       // capital | F1 | F2 | F3 | SJF | MA | MB | MC - only if the court says the level
  "cold_open": [ {"in": "H:MM:SS", "out": "H:MM:SS", "label": "ARMS CROSSED"} ],   // 1-3 strongest moments, 6-30 s each
  "tease": "One calm narrator line that teases the payoff without giving it away.",
  "stamp": "THE FULL STORY",                  // 1-4 words, red stamp on the story card
  "profile": ["26 YEARS OLD", "MOTHER OF TWO"],// 2-4 neutral facts said in court (pills)
  "backstory": [ {"text": "Narration, 2-4 short present-tense sentences.", "tags": ["police_car_night", "handcuffs_table"],
                  "pills": ["NEW YEAR'S EVE · 2022", "SAN ANTONIO POLICE · ARREST"]} ],   // 1-4 beats; facts said in court only
  "chapters": [ {"at": "H:MM:SS", "title": "THE PLEA"} ],      // 2-6 chapter starts inside the case, 1-3 word titles
  "bridges": ["Narrator line before chapter 1", "before chapter 2"],
  "rulings": [ {"tc": "H:MM:SS", "text": "Bond: $150,000 + GPS"} ],  // every ruling, the moment it is said
  "turns": [ {"from": "H:MM:SS", "to": "H:MM:SS", "who": "JUDGE"} ],  // who speaks (JUDGE | DEFENDANT | LAWYER | STATE | WITNESS)
  "questions": ["3 questions the video answers"],
  "verdict_big": "45 YEARS",
  "impact_quote": {"text": "exact words", "who": "VICTIM'S MOTHER", "tc": "H:MM:SS"},
  "tagline": "ONE NIGHT. TWO FAMILIES.",
  "board": {"items": [{"id": "d", "label": "SUMMER", "sub": "THE DEFENDANT"}], "links": [["d", "c", "LIED ABOUT"]]},
  "replays": [ {"in": "H:MM:SS", "out": "H:MM:SS", "label": "EYES DOWN", "analysis": "One narrator line on what to watch.",
                "marks": [{"kind": "circle", "x": 0.30, "y": 0.42, "r": 0.10}]} ],   // x/y = fraction of the frame
  "episode_title": "THE WARRANT", "episode_summary": "2 sentences for the next episode's recap.",
  "cliffhanger": "NEXT: THE FINAL HEARING"
}
B-roll tags you may use (exactly these words): city_drone_dusk police_car_night handcuffs_table handcuffs_car_hood
shell_casings_night suv_night_street suburban_house apartment_aerial forensic_lab phone_dark_table drug_test_cups case_folder
gavel courtroom_empty courthouse_stone courthouse_brick jail_cell prison_exterior hospital_night car_crash_night
bar_drinks_night calendar_pages money_cash documents_desk crime_scene_tape child_toys_empty family_photos highway_night
rain_window_night clock_ticking. Pick the tag that shows the NOUN of the sentence literally (arrest -> handcuffs_table).
Legal-safe wording in narration: "police say", "prosecutors claim", "the court heard". The judge is "the judge" in narration.

 THIS STYLE: EVIDENCE BOARD
A detective's cork board: every fact becomes a pinned card, red strings connect people and evidence, the master case file sits in the middle.
Fill board.items (4-8: people, evidence, places, dates said in court; label 1-3 words, sub 2-4 words) and board.links (which items connect and why, 1-3 words), tease, backstory_text (narration for the pins, 3-5 sentences), chapters, rulings, turns.
