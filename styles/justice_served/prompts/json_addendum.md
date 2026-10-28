
════════════════════════════════════════════════════════════════
 MACHINE OUTPUT FORMAT  (this REPLACES the printed BLOCK 1 / BLOCK 2 layout)
════════════════════════════════════════════════════════════════
A script renders the editor-facing EDIT SHEET and METADATA from your data, and
builds the actual video. So do NOT print the BLOCKS. Everything in Rules 0-8
still applies in full — you are only changing the container.

Reply with ONE JSON object inside a single ```json fence and nothing else.

Time format: every timecode is the STREAM clock exactly as shown in the
transcript, "H:MM:SS" (e.g. "2:23:27"). Never MM:SS for stream times.
The script computes every duration, card, chapter time, mid-roll time, runtime
and the final sheets itself, so you never write those. You DO still have to
choose IN/OUT/hook points that make the rules pass — the script will check
them and send you back any failure.

SCHEMA
{
  "source_file": "{{SOURCE_FILE}}",
  "stream_length": "{{STREAM_LENGTH}}",
  "working_note": ["<=12 short lines, as in the WORKING NOTE section"],
  "pass1": [ {"t":"H:MM:SS","phrase":"marker text"} ],
  "gaps": [ {"in":"H:MM:SS","out":"H:MM:SS","kind":"NON-CASE","label":"docket call | scheduling | recess | silence | off-record | banter | technical"} ],
  "cases": [
    {
      "id": 1,                              // unique integer
      "name": "Julian Settles",
      "cause_no": "2026 CR07561",           // "Cause No." text; "" if never said
      "in": "H:MM:SS", "out": "H:MM:SS",    // ONE range (Rule 1)
      "remove": null,                       // or {"in":"..","out":"..","why":"recess, nothing said"}  (max one, >2:00)
      "ruling_tc": "H:MM:SS",               // where the court decides; null only if ruling_deferred
      "ruling_deferred": false,
      "monetisation": "OK",                 // or "LIMITED" (sexual offences against a minor)
      "score": 38,                          // /50
      "status": "used",                     // "used" | "carried" | "rejected"
      "reject_reason": null,                // only for pure procedure / under 2:00 hearing
      "what_it_is": "...", "charge": "plain English, one line",
      "facing": "Up to 10 years", "question": "real unanswered question (Rule 8)",
      "story": "two sentences", "root_against": "who and why",
      "moment": "the line that turns it", "moment_tc": "H:MM:SS",
      "ends_on": "what the judge decided, or RULING PENDING",
      "result": {"sentence": "what the judge gave", "conditions": "the two that matter most"}
    }
  ],
  "videos": [
    {
      "n": 1,
      "case_ids": [2, 1, 3],                // PLAY ORDER, strongest first. Only status "used" cases.
      "hook": {"in":"H:MM:SS","out":"H:MM:SS","spoken":"full spoken text of the clip","headline":"3-9 word caption shown under the teaser"},
      "intro_seconds": 6,                   // 5-8
      "vo1":      {"text": "25-35 words"},
      "bridges":  [ {"after_case_id": 2, "text": "35-40 words, ONE recap clip, 2+ sentences", "split_after_sentence": null} ],
                                            // one per seam; split_after_sentence = 1-based sentence number where the
                                            // RESULT card ends and the INTRO card begins (null = script picks the middle)
      "vo_final": {"text": "45-70 words, every sentence < 35 words"},
      "quiz": {"question":"...","options":{"A":"..","B":"..","C":".."},"answer":"B  text   (or: left open - answer in the comments)"},
      "thumbnail": {"window_in":"H:MM:SS","window_out":"H:MM:SS (3 s later)","look_for":"expression","text":"2-5 words","gold_word":"ONE word from text","placement":"top"},
      "title": "...", "backup_title": "...",
      "description": {
        "first_line": "one line restating the title's question",
        "what_happens": "3-4 lines, no ruling",
        "pending_note": null,
        "search_question": "a real search question",
        "answer": "~100 words, not repeating the question as its first words",
        "related_question": "related-video question"
      },
      "chapters": [ {"tc":"H:MM:SS","label":"story beat"} ],
                                            // 5-8, tc = STREAM time inside the case ranges of this video, first one =
                                            // the first case's IN. Script converts to video time. Never hook/intro/VO.
      "tags": ["12-15 case-specific tags"],
      "pinned_comment": "...", "community_post": "~40 words",
      "publish": {"slot": "9am ET"},        // 9am ET | 1pm ET | 6pm ET
      "verdict_pending": false,
      "followup_owed": null                 // or {"case":"name","ruling_expected":"date"}
    }
  ]
}

Cards: the script builds INTRO / RESULT cards from each case's fields above
(charge, facing, question, result), so those fields must be final and clean.
Cases with status "carried" or "rejected" appear in "cases" (with their range)
but in no video. "gaps" must classify every stretch of non-case stream time
over 3:00 (Pass 2). Output the JSON and stop.
