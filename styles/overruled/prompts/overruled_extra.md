
· OVERRULED LOOK (this style only; the locked structure above is unchanged): channel "Overruled", audience 40-60, tone = calm
  courtroom commentary + plain-English overview (no slang, no hype, no emoji). Extra plan fields, all optional but strongly wanted:
  - video.takes: 1 per ~4-6 minutes, [{"tc":"H:MM:SS","text":"<=26 words, one editorial observation, true to the clip","dur":6}]
    (tc inside a kept range of the video, >= 2.5 min apart, never in the first 40 s of a case)
  - video.exchanges: 0-2 per video, a sharp Q&A moment
    [{"tc":"H:MM:SS","ts":"H:MM:SS","who_q":"PROSECUTOR","q":"<=22 words verbatim","who_a":"WITNESS","a":"<=18 words verbatim","dur":9}]
  - hook.quote / hook.quote_by: optional verbatim line (<=16 words) shown as a quote card
  - case.proceeding (e.g. "JURY TRIAL", "PLEA HEARING", "SENTENCING"), case.headline_name, case.sub_line, case.defendant_line,
    case.charge, case.question (the one question the viewer will want answered, <=14 words)
  - video.quiz: {"question": "...", "options": ["A","B","C"]} used on the closing docket board
  - vo_final MUST include one natural sentence asking the viewer to subscribe
    (e.g. "If this kind of courtroom breakdown helps, subscribe to Overruled and tap the bell.")
  - bridges/recaps are "The Overview": informative, past tense where fitting, no second person.
