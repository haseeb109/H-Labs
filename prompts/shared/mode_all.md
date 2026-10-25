════════════════════════════════════════════════════════════════
 MODE "ALL CASES" — overrides Rule 4 and every bundling rule in v9
════════════════════════════════════════════════════════════════
B.1 Every case with at least {MIN_CASE} of real hearing (OUT − IN − removed
    stretch) gets its OWN video. Status "used".
B.2 Cases under {MIN_CASE}: status "skipped", reject_reason "under {MIN_CASE}".
    Pure procedure with no hearing: status "rejected" (v9 rule).
B.3 There is NO runtime band, NO bundling, NO passengers, NO carry forward in this
    mode. Never chop a case to make it shorter. A 45-minute trial is one video.
B.4 Interrupted case: the script will use the longest continuous segment; if it is
    under {MIN_CASE} the case is skipped.
B.5 VIRALITY. For every used case fill "virality": {"factors": {...}, "why": "..."}.
    Score honestly from the transcript:
      judge_confrontation 0-20  judge challenges, scolds, interrupts, catches a lie,
                                refuses a deal
      emotion             0-20  crying, victim/family statement, apology, breakdown
      surprise_ruling     0-20  probation rejected, straight to jail, deal thrown out,
                                unexpected mercy
      numbers             0-10  concrete numbers that land (years, violations, $, BAC)
      topic_click         0-15  DWI crash, fraud, family violence, repeat offender,
                                child endangerment and similar high-interest topics
      completeness        0-10  ruling reached in this stream (pending = 0-3)
      av_quality          0-5   clear audio, faces visible
    "why" = one line, the single reason a viewer would click and stay.
    Do not write a total; the script computes it and ranks the videos.
B.6 In PASS A return "cases" only (no "videos"). Each used case will be packaged into
    its own video in PASS B.
