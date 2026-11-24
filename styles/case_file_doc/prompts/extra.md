════════════════════════════════════════════════════════════════
 DOCUMENTARY STYLE: CASE FILE DOCUMENTARY  (add "doc": {...} INSIDE the "video" object)
════════════════════════════════════════════════════════════════
One defendant's full story: cold open of the payoff, the case document, backstory over B-roll, the charge and its
punishment range, dated hearing chapters.

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
  "chapters": [ {"at": "H:MM:SS", "title": "THE PLEA"} ],      // 2-6 chapter starts inside the case, 1-3 word titles
  "cold_open": [ {"in": "H:MM:SS", "out": "H:MM:SS", "label": "ARMS CROSSED"} ],   // 2 strongest moments, 6-30 s each, title moment first
  "tease": "One calm narrator line that teases the payoff without giving it away.",
  "stamp": "THE FULL STORY",                  // 1-4 words, red stamp on the story card
  "profile": ["26 YEARS OLD", "MOTHER OF TWO"],// 2-4 neutral facts said in court (pills)
  "backstory": [ {"text": "Narration, 2-4 short present-tense sentences.", "tags": ["police_car_night", "handcuffs_table"],
                  "pills": ["NEW YEAR'S EVE · 2022", "SAN ANTONIO POLICE · ARREST"]} ],   // 2-4 beats; facts said in court only
  "charge_level": "F3",                       // capital | F1 | F2 | F3 | SJF | MA | MB | MC - only if the court says the level
  "bridges": ["Narrator line before chapter 1", "before chapter 2"],        // one short line per chapter
  "earlier_bridges": ["Only when EARLIER HEARINGS are given below: one narrator line before each earlier hearing, oldest first"]
}
B-roll tags you may use (exactly these words): city_drone_dusk police_car_night handcuffs_table handcuffs_car_hood
shell_casings_night suv_night_street suburban_house apartment_aerial forensic_lab phone_dark_table drug_test_cups case_folder
gavel courtroom_empty courthouse_stone courthouse_brick jail_cell prison_exterior hospital_night car_crash_night
bar_drinks_night calendar_pages money_cash documents_desk crime_scene_tape child_toys_empty family_photos highway_night
rain_window_night clock_ticking. Pick the tag that shows the NOUN of the sentence literally (arrest -> handcuffs_table).
Legal-safe wording in narration: "police say", "prosecutors claim", "the court heard". The judge is "the judge" in narration.
