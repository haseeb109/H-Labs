════════════════════════════════════════════════════════════════
 v10 OVERLAYS — SHORT ON-SCREEN TEXT INSIDE EACH CASE (lifts watch time)
════════════════════════════════════════════════════════════════
For every used case write "overlays": a list of {"tc","kind","text","dur","ref_tc",
"evidence"}. They appear in a bottom band that never covers faces.

HOW MANY. About one per 4.5 minutes of case time (a 9-minute case gets 2, a
22-minute case gets 4-5). At least 3 minutes apart. Never in the first 40 seconds
or the last 30 seconds of the case. dur = 6-8 seconds.

KINDS
  fact       One concrete fact or number already said in the transcript
             ("He was already on probation for the same charge").
  coming_up  Open loop about a LATER moment of the same case, at least 45 s later.
             ref_tc = the tc of that moment. Never the verdict itself.
             ("Coming up: the prosecutor reveals his 2019 case").
  so_far     One-line recap of what happened so far, for late joiners. Use after
             the middle of long cases.
  watch      "Watch the judge's reaction when he answers" - the moment must happen
             within 30 s after tc.
  verdict_q  One comment prompt per video at most ("Would you give her a second
             chance? Comment below"). Only after the facts needed to answer it.
  take       (Overruled only) "Our Take": one calm editorial observation, true to
             the clip, at most 26 words.

RULES
  · Text at most 20 words (take 26). Plain English. No emoji. No question mark
    except in verdict_q.
  · Every number and claim must be in the transcript (fact/so_far: at or before tc;
    coming_up: at ref_tc). "evidence" = a verbatim ≤12-word quote that backs it.
  · Never reveal the verdict before it happens on screen. Never add outside legal
    facts (penalty ranges, statutes, prior news).
  · Mix kinds; never two of the same kind in a row; every case of 8+ minutes has at
    least one coming_up.
