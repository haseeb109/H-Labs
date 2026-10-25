════════════════════════════════════════════════════════════════
 v10 BOUNDARY RULES  (apply in every mode, on top of Rule 0/Rule 1)
════════════════════════════════════════════════════════════════
A.1 START. A case's IN is the line where the judge calls it ("calling CR2469",
    "court is calling 2024 CR…", "cause number…"). Unchanged and locked.

A.2 PHASES. For every case return "phases" in order, each with the stream tc and a
    verbatim evidence quote of at most 12 words:
      call → plea_or_admonish (optional) → evidence_or_argument (optional)
      → ruling (or set "ruling_deferred": true) → wrap_up
    All phases sit inside [IN, OUT]. The ruling is the moment the court decides
    (sentence pronounced, plea accepted/rejected, probation revoked, case reset,
    motion granted/denied).

A.3 END. OUT is the end of the wrap-up, not the end of the ruling sentence. Typical
    wrap-up lines: "you're free to go", "that'll be all", "good luck", "anything
    further", "you're excused", "sign the paperwork", "you have the right to appeal",
    "you'll be taken into custody", "we'll see you on <date>", "thank you, counsel".
    OUT is never before the ruling. OUT never contains the next case's call-out.
    If the next call-out follows within seconds, OUT is just before it.

A.4 PEOPLE CHANGE MID-CASE. Lawyers, witnesses, interpreters and family can appear
    and leave during one case. That is NOT the end. The case ends only when the
    ruling is done, the wrap-up is said, and the court moves on (next call-out,
    recess, or long silence).

A.5 INTERRUPTED CASES. If the judge pauses a case ("we'll come back to you"),
    another case runs, and the first one returns, set "interrupted": true and list
    "segments" (each with in/out). Do not splice. The script picks the segment.

A.6 EVIDENCE. For every case give "boundary": {"out_evidence": "<≤12-word quote at
    the end>"}. The script will refine OUT using video signals (tile changes, name
    labels) and may move it by up to two minutes. Give your best OUT anyway.

A.7 SCRIPT SIGNALS. The section "BOUNDARY EVIDENCE" below lists, for windows around
    each candidate boundary: call-outs, wrap-up phrases, ruling phrases, Zoom tile
    count changes and tile-label changes found by code. Trust their timecodes.
