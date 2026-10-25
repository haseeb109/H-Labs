════════════════════════════════════════════════════════════════
 CASE BUILD ORDER  v9.0
════════════════════════════════════════════════════════════════

Produce exactly TWO blocks for the editor:
  BLOCK 1 — EDIT SHEET   (what to cut, with the voiceover inline)
  BLOCK 2 — METADATA     (what to paste into YouTube)

Before them, print a short WORKING NOTE — twelve lines maximum.
The editor ignores it. It exists so you cannot skip the checks.

Keep everything minimal. The editor must never see a scoring
table, a bundling calculation, or the same case written twice.

────────────────────────────────────────────────────────────────
INPUTS
────────────────────────────────────────────────────────────────
SOURCE FILE NAME:    {{SOURCE_FILE}}
STREAM TOTAL LENGTH: {{STREAM_LENGTH}}
CARRIED FORWARD FROM LAST BUILD: {{CARRIED}}

Court: 187th District Court, Bexar County — Judge Stephanie Boyd
Channel: {{CHANNEL_NAME}}

════════════════════════════════════════════════════════════════
 RULE 0 — ZERO-MISS EXTRACTION. READ THIS FIRST.
════════════════════════════════════════════════════════════════
Your first job is to find EVERY case. Not the good ones. Every
one. A case you never noticed cannot be judged, bundled or
carried — it is simply lost.

Work in TWO PASSES. Do both. Print both.

PASS 1 — MARKER SCAN
  Search the whole transcript for every one of these phrases.
  Each hit is a candidate case start:
    "court is calling"      "state versus"
    "the state calls"       "can I have parties announce"
    "parties announced"     "we're on the record on"
    "cause number"          "are you [NAME]"
    "you may be seated"     "come forward"
    "next case"             "call the next"
    "are the parties ready" "counsel, announce"
  List every hit with its timecode. Do not filter yet.

PASS 2 — GAP SWEEP
  Between every two consecutive Pass-1 hits, and before the first
  and after the last, read the gap. Ask: is a hearing happening
  here that was never formally announced?
  Courts often begin a matter without a clean call — a defendant
  simply steps up, or the judge resumes something from earlier.
  Any gap over 3:00 must be classified. Print:
      GAP [in]–[out] = [MM:SS] → [CASE: name] or [NON-CASE: what]
  "NON-CASE" is only: docket call, scheduling, recess, silence,
  off-record talk, staff banter, technical problems.

COVERAGE PROOF — print this and it must balance:
      total case minutes      = [MM:SS]
    + total non-case minutes  = [MM:SS]
    ────────────────────────────────────
    = stream length           = [MM:SS]   ✔ must match
  If it does not balance, you have missed something. Go back.

MINIMUM CASE SIZE IS 2:00.
  Anything with 2:00 or more of a real hearing is a case and goes
  in the inventory. It may end up bundled, or carried, but it is
  never invisible.

════════════════════════════════════════════════════════════════
 RULE 1 — ONE CONTINUOUS RANGE PER CASE
════════════════════════════════════════════════════════════════
Each case gets ONE start time and ONE end time. Nothing else.
The editor plays that range straight through, uncut.

  ▶️ CASE 1 — Julian Settles — play 2:23:27 to 2:41:10  (17:43)

DURATION IS SUBTRACTION, NOT ESTIMATION.
  For every case print the arithmetic:  OUT − IN = duration
      2:41:10 − 2:23:27 = 17:43
  Never estimate a length. A previous run understated every case
  in a stream by between 1:34 and 8:06, which caused five of them
  to be wrongly rejected.

Never split a case into parts. Never give "keep blocks". Never
give a cut list. Choose the IN and OUT points surgically instead:

  IN  = the first substantive line. Skip the roll call, the
        "court is calling" announcement, the discovery questions,
        the oath. Start where the story starts.
  OUT = the last line of the ruling or the defendant's reaction
        to it. Stop before the next case is called and before
        any off-record chatter.

ONE EXCEPTION: if a recess or dead stretch longer than 2:00 sits
inside the range and cannot be avoided by moving IN or OUT, add
ONE line beneath the case:
  REMOVE: 1:12:40 to 1:15:10 (recess, nothing said)
Maximum one removal per case. If a case needs two or more, pick
a tighter range instead.

════════════════════════════════════════════════════════════════
 RULE 2 — THE HOOK IS ALLOWED TO REPEAT
════════════════════════════════════════════════════════════════
The hook is a 10-15 second clip lifted from inside the lead
case's range. It plays at 0:00 as a cold open, and again in
context when the video reaches it. That is normal and correct.
Do NOT write a note telling the editor to avoid duplication. Do
NOT carve the case range around the hook.

════════════════════════════════════════════════════════════════
 RULE 3 — VOICEOVER SITS INLINE, WRITTEN OUT IN FULL
════════════════════════════════════════════════════════════════
Voiceover appears in the edit sheet exactly where it is recorded.
Every VO is the actual sentences, in quotes, with a word count.
"25-35 words" is an automatic FAIL.

  VO-1 ......... after the channel intro, over the start of Case 1
                 25-35 words. Stake + a number. Never the outcome.
  VO-BRIDGE .... between each case and the next
                 35-45 words. Closes the case just watched with a
                 question, then opens the next with its stake.
  VO-FINAL ..... over the closing frames
                 45-55 words. A goodbye tied to today's cases ·
                 ONE comment ask · ONE like or subscribe ask with
                 a reason.

NO voiceover on the hook. NO voiceover on the channel intro.
The channel intro animation is 5-8 seconds. Never longer.

EVERY VO MUST BE NEW WORDS. Never reuse a sentence from an
earlier VO in the same video. A previous run opened VO-BRIDGE
with the same 22 words it had already used in VO-1.

COUNT THE WORDS. Print the real count. A previous run wrote a
22-word VO and labelled it 29.

VO may ONLY name cases that are IN THIS VIDEO. A previous run
wrote a closing line about a defendant who had been rejected and
was nowhere in the edit.

COMMENT-ASK SHAPE — give two defensible positions, then invite a
side. Never "what do you think?".
  "Four years, and it was his third violation. Half of you will
   call that soft. The other half read the file. Which are you?"

BANNED VO PHRASES: "let me know in the comments" · "smash that
like button" · "don't forget to subscribe" · "hit the bell" ·
"welcome back to the channel" · "in today's video" ·
"before we get started"

════════════════════════════════════════════════════════════════
 RULE 4 — LENGTH AND CASE SELECTION
════════════════════════════════════════════════════════════════
LENGTH DEPENDS ON WHAT THE STREAM GAVE YOU.

  ONE STRONG CASE          → publish it WHOLE, no upper limit.
                             40, 50, 70 minutes is fine when the
                             tension is continuous. Do not chop a
                             strong hearing to hit a band.
                             Qualifies when a single case runs
                             25:00+ on its own.

  SEVERAL SMALLER CASES    → bundle to land between
                             20:00 and 40:00.

  ABSOLUTE FLOOR ......... 20:00
  CASES PER VIDEO ........ 1 to 5

Add up the case ranges. Hook and intro add about 20 seconds.

Pick cases in descending strength and KEEP ADDING until the total
sits between 20:00 and 40:00. Do not stop at 20:00. Do not stop
at two cases. Strongest case runs first — it earns the title.

Never pad a bundle past 40:00 — open a second video instead.
Never chop a single strong case down to fit 40:00.
If a stream leaves cases over after filling every video, they are
CARRY FORWARD — listed with file name and timestamps for the next
build. Never dropped, never "held".

WE COVER EVERY TYPE OF CASE. There is no content reject list.
Drugs, assault, theft, fraud, probation, family, DWI, weapons,
sexual offences, homicide — all of it gets built.

The ONLY reason to leave something out of the inventory:
  · it is pure procedure with no hearing at all — a reset, a
    scheduling call, an attorney appearance, bond paperwork
    where nothing is argued and nothing is decided
  · it has under 2:00 of hearing

MONETISATION FLAG — not a reject, just a label.
  If a case involves sexual offences against a minor, print
  MONETISATION: LIMITED next to it in the working note. Build it
  anyway. Two practical notes: keep these to roughly one upload
  in ten so the channel's overall ad rating is not dragged down,
  and do not make one the week's thumbnail-facing flagship.
  Court Of Justice publishes this category and their biggest is
  172,000 views — it works. It just earns less per view.

SIZE ONLY DECIDES A CASE'S ROLE, NEVER WHETHER IT IS USED.
  2:00 or more  → goes in the inventory. Always.
  2:00 - 5:59   → passenger only. Bundle it. Never lead, never solo.
  6:00 - 24:59  → can lead a bundle.
  25:00+        → can be a solo video.
  A short case is never a reject. It is a passenger.
  WHY: a previous run rejected five cases of 4-11 minutes each on
  a blanket 6:00 rule, kept one, and returned NOT READY — while 63
  minutes of usable hearings sat in the same stream.

YOU MUST BUILD. If the usable minutes across ALL cases total
20:00 or more, a video exists and you will produce it. "NOT
READY" is not available to you in that situation. Bundle the
short cases together, strongest first, until the band is met.

RULING: find where the court decides and print the timecode.
If the judge defers ("I'll rule tomorrow"), the case is still
usable when it has 20:00+ of tension — then the title asks a
question, VO-FINAL says when the ruling comes and asks for the
subscribe, and the quiz becomes a prediction. Maximum one
verdict-pending video per week.

════════════════════════════════════════════════════════════════
 RULE 5 — THE HOOK
════════════════════════════════════════════════════════════════
10-15 seconds, from the BACK 60% of the lead case's range, and
inside that range.

MUST contain one of: the judge challenging someone · a
contradiction named out loud · a number that lands hard · an
emotional break · a fact that reframes the case.

MUST NOT contain: cause numbers · "the court is calling" ·
"state versus" · "parties announce" · "for the record" ·
"discovery" · "wave the reading" · "any objection" · "off the
record" · "may I approach" · "raise your right hand" ·
"do you solemnly swear" · plea-cap terms · scheduling.

Print the hook's full spoken text in the edit sheet so a weak
hook is visible before anyone builds it.

════════════════════════════════════════════════════════════════
 RULE 6 — TITLES: THE COURT OF JUSTICE TEMPLATE
════════════════════════════════════════════════════════════════
Structure, reverse-engineered from all 59 COJ titles:

    [ SETUP — what they did or who they are ]
              —
    [ PAYOFF — what the judge did ]

Em-dash separator. Not a colon, not a pipe. 97% of their titles.

REAL EXAMPLES WITH VIEWS:
  Judge Boyd Rejects Probation and Sends Her Directly to Prison
    — A Shocking Court Moment                          294,000
  Teen Thinks Judge Boyd is a Fool — Then Instantly REGRETS It
                                                        285,000
  Heartless Women Stole From Charity Funds
    — Judge Boyd REFUSES to Accept the Deal             140,000
  Murderer Begs For Last Chance — Judge Boyd Shows No Mercy
                                                        109,000
  She Showed Up High in Court
    — Judge Boyd Sentences Her to Prison Instantly       93,000
  10 Years For Tampering With a Government License
    — Judge Boyd HUMILIATES Her in Court                 56,000

── OPENING THE SETUP HALF ── measured, n=59
  ROLE NOUN       Murderer · Prosecutor · Politician ·
                  Nurse · Landlord · Grandmother       71,500  ★best
  JUDGE FIRST     Judge Boyd Rejects Probation and…    64,000
  PRONOUN + ACT   She Showed Up High in Court          53,000
  NUMBER FIRST    10 Years For Tampering With…         51,500
  PURE ACT        Brutally Stabbed an Elderly Woman    47,000
  ADJECTIVE LABEL Monster Woman · Cocky Teen ·
                  Arrogant Woman                        7,200  ✗never

  NEVER open on an adjective label. It is COJ's most-used shape
  and their worst by a factor of ten.

── OPENING THE PAYOFF HALF ──
  46% begin "Judge Boyd [verb]…"   → Judge Boyd Shows No Mercy
  23% begin "Then Instantly…"      → Then Instantly REGRETS It

── THE FOUR MECHANICS ──
1. LENGTH 13-17 words, 65-90 characters. COUNT and print it.
   14-17 words medians 53,000 · 8-11 words medians 4,800.
2. ONE ALL-CAPS POWER WORD, payoff half only, exactly one.
   With caps 47,000 · without 13,500 · 3.5×
   RAGES · LOSES CONTROL · REGRETS · REFUSES · DESTROYS ·
   HUMILIATES · SHOCKED · SNAPS · SLAMS · DEMANDS · EXPOSES
3. PUT A NUMBER IN whenever the case gives one.
   With a number 51,500 · without 18,000 · 2.9×
4. STATE THE CONSEQUENCE in the payoff half.
   Reveals the outcome 58,000 · withholds it 12,500 · 4.6×
   The curiosity comes from WHY and HOW, not from what happened.
   THIS REVERSES AN EARLIER RULE. Titles may and should name the
   prison term, the years, "no mercy", "refuses to accept".

   Name "Judge Boyd" in roughly half the titles (COJ does 54%).

── NEVER ──
  asterisk censoring · a title built on appearance (tattoos,
  hair, clothing, weight) · emojis · two ALL-CAPS words ·
  an adjective-label opener · a claim the transcript does not
  support · the publish title and the backup title sharing the
  same payoff half — they must differ on both sides.

── THE BACKUP TITLE ──
  Must use a DIFFERENT setup opener from the publish title. If
  the publish title opens on a ROLE, the backup opens on the ACT
  or the NUMBER. Two titles with the same payoff is not a test.

── FOR SIX OPTIONS ──
  When you want a full set to choose from, run MP-5 TITLE ENGINE
  (19_MP5_TITLE_ENGINE.md) — six angles, one recommendation.

════════════════════════════════════════════════════════════════
 RULE 7 — THUMBNAIL TEXT
════════════════════════════════════════════════════════════════
Every video gets 2-5 words burned onto the thumbnail.

THE ONE RULE: the thumbnail text must ADD information the title
withheld. Never repeat the title. The viewer reads both in the
same second — two copies of the same idea wastes half the frame.

  TITLE     Nurse Admits Meth Use on the Stand
            — Judge Boyd DEMANDS Real Change
  THUMB     "10 YEARS?"          ✔ adds the number
  THUMB     "MOTHER OF THREE"    ✔ adds who she is
  THUMB     NURSE ADMITS METH    ✘ repeats the title

PICK THE TEXT FROM ONE OF THESE FOUR, in this order of preference:
  1. A VERBATIM SPOKEN FRAGMENT from the hook clip, in quotes.
     Proven at 3.2M on Audit the Court: "Arrest him right now!"
  2. THE NUMBER that lands hardest — "10 YEARS?" · "77 TESTS"
     · "$150,000" · "39 VIOLATIONS"
  3. THE REACTION in the defendant's own words — "I'LL TAKE PRISON"
  4. THE ROLE, if it is surprising — "NURSE" · "HONOR STUDENT"
     · "GRANDMOTHER"

MECHANICS
  · 2-5 words. Never a sentence.
  · ALL CAPS, except a quoted fragment which keeps sentence case
    inside quote marks.
  · White, with ONE word in gold #D4A017.
  · Black outline 8-12px, fully opaque, on every letter.
  · Sits in the TOP THIRD or the BOTTOM THIRD. Never across a face.
  · Must be readable at 120 pixels wide. If it is not, cut a word.
  · Never asterisk-censor. Choose different words instead.

OUTPUT IT LIKE THIS in the edit sheet:
  ▶️ THUMBNAIL — screenshot anywhere in [3-second window]
    Look for: [expression]. Reject any neutral face.
    TEXT ON THUMB:  "[the 2-5 words]"
    GOLD WORD:      [which single word is gold]
    PLACEMENT:      top third / bottom third

════════════════════════════════════════════════════════════════
 RULE 8 — CAUSE CARDS OVER THE VOICEOVER
════════════════════════════════════════════════════════════════
The voiceover is the only part of the video with no courtroom
action behind it. That is where viewers leave. Cover every VO
with a CAUSE CARD so there is something to read while they listen.

HOW IT LOOKS
  Background : footage from THAT case's own range, blurred
               heavily (20-30px) and darkened about 50%
  Text       : sits over the blur, left-aligned, lower-left third
  Duration   : exactly the length of the VO it sits under
  Motion     : the blurred footage keeps playing. Never freeze it.

There are TWO card types. Give the editor both, filled in.

─── INTRO CARD ─── runs under VO-1 and under each case's half of
                   a VO-BRIDGE. It sets the stake.

    CASE [n] OF [total]          ← small caps, gold
    [DEFENDANT NAME]             ← large, white
    Cause No. [number]           ← small, grey
    ──────────────────────────
    CHARGE     [plain English, one line, no legal jargon]
    FACING     [the maximum exposure — "Up to 10 years"]
    THE QUESTION  [the open loop — one short line]

  THE QUESTION line is the whole point of the card. It must be an
  unanswered question the case will settle, phrased so the viewer
  wants to stay for the answer.
    ✔ "Can he stay clean with a child at home?"
    ✔ "Did she really pay the headstone company?"
    ✘ "What will the judge decide?"   ← too vague, means nothing

─── RESULT CARD ─── runs under the second half of a VO-BRIDGE and
                    under VO-FINAL. It delivers the payoff.

    CASE [n] — THE RULING        ← small caps, gold
    [DEFENDANT NAME]             ← large, white
    ──────────────────────────
    SENTENCE   [what the judge gave]
    CONDITIONS [the two that matter most]

  This audience watches for moral resolution. Showing the sentence
  in writing, right after they heard it, is the payoff landing
  twice. Never skip the result card.

STYLE — same two colours as the channel
  Gold #D4A017 for the labels. White for the values.
  One thin gold rule under the name.
  No boxes, no drop shadows, no icons, no gavel graphics.
  Text left-aligned. Safe margin 10% from every edge.

WHERE CARDS GO — one per VO, no exceptions:
  VO-1        → INTRO CARD for case 1
  VO-BRIDGE   → RESULT CARD for the case just finished,
                then INTRO CARD for the next case
  VO-FINAL    → RESULT CARD for the last case

OUTPUT IT LIKE THIS, directly under each VO in the edit sheet:
  ▶️ VO-1 — read over the opening of Case 1:
    "[the actual sentences]"   ([n] words)
    CARD: INTRO · blur footage from [in]–[out] of this case
      CASE 1 OF 4
      AMANDA MOREHOUSE
      Cause No. 2026 CR07561
      CHARGE        Theft of property, $30,000 to $150,000
      FACING        Up to 10 years
      THE QUESTION  Did the money ever reach the headstone company?

════════════════════════════════════════════════════════════════
 WORKING NOTE  (12 lines maximum — the editor ignores this)
════════════════════════════════════════════════════════════════
  Cases found:        [n]  — name · range · OUT−IN=duration · score /50
  Cases used:         [n]
  Cases carried:      [n]  — name + file + range, or "none"
  Cases rejected:     [n]  — name + which reject reason
                             (a short case is NOT a reject)
  Minutes found / used / carried / WASTED: [must be 0:00]
      "found" = the sum of the case durations, NOT the stream length
      CHECK: used + carried + rejected-minutes MUST equal found.
      Print that addition. A previous run was out by 1:37.
  Unmapped stream time: [MM:SS] — [one line on what it contains]
  Ruling:             [timecode] or DEFERRED [timecode]
  Gaps over 2:00:     [list, or none]
  Hook inside lead case range:   YES / NO   ← must be YES
  Title noun inside a case range: YES / NO  ← must be YES
  Runtime check: hook + intro + case totals = [MM:SS]
  Title characters: [list all]
  Verdict-pending videos this week: [n]  (max 1)

════════════════════════════════════════════════════════════════
 NOW PRODUCE THE TWO BLOCKS
════════════════════════════════════════════════════════════════
Clean. Minimal. Copy-paste ready. Repeat both per video.


╔══════════════════════════════════════════════════════════════╗
║  BLOCK 1 — EDIT SHEET                                        ║
║  VIDEO [n] · [MM:SS] · source: [file name]                   ║
╚══════════════════════════════════════════════════════════════╝

▶️ HOOK — play [in] to [out]   ([n] sec)
   Spoken: "[the full text of the clip]"
   No voiceover.

▶️ CHANNEL INTRO ANIMATION — [n] sec
   No voiceover.

▶️ VO-1 — read over the opening of Case 1:
   "[the actual sentences]"   ([n] words)
   CARD: INTRO · blur footage from [in]–[out] of this case
     CASE 1 OF [total]
     [DEFENDANT NAME]
     Cause No. [number]
     CHARGE        [plain English]
     FACING        [maximum exposure]
     THE QUESTION  [the open loop]

┌─ CASE 1 ─────────────────────────────────────────────────────┐
│ [DEFENDANT NAME]                        Cause No. [number]   │
│   (Texas trial courts use CAUSE number, never "case number")  │
│                                                              │
│ WHAT IT IS   [one line a non-lawyer gets instantly]          │
│ CHARGE       [plain English]                                 │
│ THE STORY    [two sentences]                                 │
│ ROOT AGAINST [who, and why the viewer will feel it]          │
│ THE MOMENT   [the line that turns it + timecode]             │
│ ENDS ON      [what the judge decided, or RULING PENDING]     │
└──────────────────────────────────────────────────────────────┘

▶️ CASE 1 — play [in] to [out]   ([OUT] − [IN] = [MM:SS])

▶️ VO-BRIDGE — read between Case 1 and Case 2:
   "[the actual sentences]"   ([n] words)
   CARD 1: RESULT · blur footage from the end of Case 1
     CASE 1 — THE RULING
     [DEFENDANT NAME]
     SENTENCE    [what the judge gave]
     CONDITIONS  [the two that matter]
   CARD 2: INTRO · blur footage from the start of Case 2
     CASE 2 OF [total]
     [DEFENDANT NAME]
     Cause No. [number]
     CHARGE        [plain English]
     FACING        [maximum exposure]
     THE QUESTION  [the open loop]

┌─ CASE 2 ─────────────────────────────────────────────────────┐
│ [same shape]                                                 │
└──────────────────────────────────────────────────────────────┘

▶️ CASE 2 — play [in] to [out]   ([OUT] − [IN] = [MM:SS])

   [repeat card + bridge + case for cases 3 and 4]

▶️ VO-FINAL — read over the closing frames:
   "[the actual sentences]"   ([n] words)
   CARD: RESULT · blur footage from the end of the last case
     CASE [n] — THE RULING
     [DEFENDANT NAME]
     SENTENCE    [what the judge gave]
     CONDITIONS  [the two that matter]

▶️ QUIZ CARD — on screen for the last [20-30] sec. Text in Block 2.

▶️ MID-ROLLS — [t1] · [t2] · [t3]
   Place on the seams between cases. Never inside a ruling.

▶️ THUMBNAIL — screenshot anywhere in [3-second window]
   Look for: [expression]. Reject any neutral face.
   TEXT ON THUMB:  "[2-5 words that ADD to the title]"
   GOLD WORD:      [the one word in gold]
   PLACEMENT:      top third / bottom third

RUNTIME: hook [n sec] + intro [n sec] + cases [MM:SS] = [MM:SS]


╔══════════════════════════════════════════════════════════════╗
║  BLOCK 2 — METADATA                                          ║
║  VIDEO [n]                                                   ║
╚══════════════════════════════════════════════════════════════╝

TITLE
[publish title]

BACKUP TITLE  (swap at 48h if CTR under 5%)
[backup]

DESCRIPTION
[one line restating the title's question]

[3-4 lines on what happens, without the ruling]

[if pending: "Judge Boyd rules on this case tomorrow. The
decision will be posted on this channel."]

[a real search question on its own line]
[100 words answering it — do NOT repeat the question as the
 first words of the answer. A previous run printed it twice.]

Chapters:
00:00 [beat]
[mm:ss] [beat]
[…]
  RULES (do not print these — they are for you):
  5-8 chapters only · story beats · first at 00:00 · never list
  the hook, intro or VO as a chapter · never place one in the
  final 60 seconds · one chapter minimum per case, named as a
  beat, never "Case 2".
  A previous run printed this rule line INSIDE the description
  where it would have gone live. Print only the chapter list.

[related-video question]

Educational content. Not legal advice.

TAGS  (paste as one line)
judge boyd, judge stephanie boyd, judge boyd sentencing, judge boyd courtroom, courtroom drama, courtroom drama texas, court cam, courtroom footage, real courtroom, court hearing, sentencing day, 187th district court, [12-15 case-specific tags]

PINNED COMMENT
[a question that invites disagreement, using the real number]

COMMUNITY POST  (T+2h)
[40 words]

QUIZ  (on screen at the end)
[question]
  A) [option]
  B) [option]
  C) [option]
Answer: [the letter and text, or "left open — answer in the comments"]

PUBLISH
[9am / 1pm / 6pm] ET  =  [PKT time]
  9am ET = 6pm PKT summer / 7pm winter
  1pm ET = 10pm PKT summer / 11pm winter
  6pm ET = 3am PKT next day summer / 4am winter
Schedule it — do not publish live.

[FOLLOW-UP OWED — only if the ruling is pending]
[case name] · ruling expected [date]

════════════════════════════════════════════════════════════════
 FINAL LINE
════════════════════════════════════════════════════════════════
Print "READY" only if all of these are true. Otherwise print
"NOT READY — [what is missing]" and fix it.

  · minutes wasted = 0:00
  · hook is inside the lead case's range
  · the title's concrete noun is inside a case range
  · every case has exactly ONE range, no parts
  · every VO is written out in full
  · every title is 65-90 characters, em-dash, one ALL-CAPS word
  · every title states the consequence in the payoff half
  · publish and backup titles differ on BOTH halves
  · thumbnail text is 2-5 words and does NOT repeat the title
  · every VO has a card — intro cards and result cards both present
  · every THE QUESTION line is a real unanswered question
  · no title opens with an adjective label
  · runtime is 20:00-40:00, or an uncapped single strong case
  · no case was rejected merely for being short
  · if 22:00+ of usable material existed, a video was built
  · every case duration is shown as OUT − IN = duration
  · every case has a text card
  · chapters are 5-8, none in the final 60 seconds
  · no chapter-rule text leaked into the description
  · no VO reuses words from an earlier VO
  · every VO word count is the real count
  · used + carried + rejected = found
  · Pass 1 and Pass 2 both printed
  · coverage proof balances to the stream length
  · no case under 2:00 was dropped without being listed

════════════════════════════════════════════════════════════════
 TRANSCRIPT
════════════════════════════════════════════════════════════════
