
· COURT BEACON TV LOOK (this style only; the locked structure above is unchanged): channel "Court Beacon TV",
  audience 40-60, feel = documentary + investigative ("we open the case file"). Titles follow TITLE RULES (Trial Tales
  energy). Narration (bridges / vo_final) stays calm and factual, like a documentary narrator - no slang, no emoji.
  Extra plan fields, all optional but strongly wanted:
  - OVERLAYS IN THIS LOOK: "fact", "so_far", "watch", "verdict_q" are shown on screen. "coming_up" teaser cards are NOT
    shown in this channel (owner decision) - keep only the single coming_up the OVERLAY RULES require and put the
    real effort into the other kinds.
    · fact: start the text with the number when there is one ("2 statements to the detective. Neither mentions a gun.")
      - the number is shown big. Number and claim must be in the transcript.
    · so_far: 2-3 short beats separated by " · " ("Owner says one knee stopped a shooting · Admits he pinned the man
      down · Never told the detective about a gun") - only things that already happened before tc.
    · watch: <= 6 words, what to watch ("his answer", "the judge's face") - the moment happens within 30 s.
    · verdict_q: one comment prompt per video, after the facts needed to answer it.
  - video.exchanges ("ON THE RECORD" cards): 1-2 per case of 8+ minutes, the sharpest verbatim Q&A
    [{"tc":"H:MM:SS","ts":"H:MM:SS","who_q":"PROSECUTOR","q":"<=14 words verbatim","who_a":"WITNESS","a":"<=12 words verbatim","dur":9}]
    tc inside a kept range, >= 40 s after the case IN, >= 3 minutes away from any overlay.
  - case.charge (plain English, <= 6 words), case.facing (e.g. "2 to 20 years"), case.proceeding ("JURY TRIAL",
    "PLEA HEARING", "SENTENCING", "PROBATION HEARING") - shown on the evidence-board card at the start of every case.
  - case.phases are REQUIRED here: they drive the on-screen hearing steps CALLED > PLEA > TESTIMONY > RULING > CLOSED.
  - case.moment_tc: the frame used for the case's polaroid on the closing "Today's Case Files" wall.
  - hook.headline: 3-9 words, no period; the most important word may be wrapped in *stars* to get the orange block.
  - vo_final MUST include one natural sentence asking the viewer to subscribe and turn on the beacon
    (e.g. "If you want every case file from this courtroom, subscribe to Court Beacon TV and turn on the beacon.").
  - video.quiz: {"question": "...", "options": {"A": "..", "B": "..", "C": ".."}} for the closing board.
