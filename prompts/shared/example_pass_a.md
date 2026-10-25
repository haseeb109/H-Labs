════════════════════════════════════════════════════════════════
 EXAMPLE OF A CORRECT PASS A REPLY  (a DIFFERENT stream - copy the SHAPE, depth and
 evidence style, NEVER its names, times or facts; your cases come only from YOUR transcript)
════════════════════════════════════════════════════════════════
Trimmed to 2 of its 10 cases (one used, one rejected). Your reply lists EVERY case in your
stream, has no "videos" key, and is ONE JSON object.
```json
{
 "schema": "v10",
 "judge_name": "Judge Boyd",
 "source_file": "03p3ATnv6dY.mp4",
 "stream_length": "1:45:52",
 "working_note": [
  "Cases found 10. Visual 0:23:34−0:12:48=10:46 · Davis 0:31:33−0:23:59=7:34 · O'Connor 0:52:09−0:37:43=14:26 · Garcia 1:24:40−1:09:43=14:57",
  "Carrera now ONE range 1:08:45−1:00:19=8:26 (resumed 'back on the record' call). His earlier call 0:56:34−0:55:07=1:27 is its own skipped entry. Sosa 2:11 · Holmes 1:38 · Bell 1:17 · Reyes 0:56",
  "Mode ALL. Used 4: Visual, O'Connor, Carrera, Garcia = 48:35. Carried 0."
 ],
 "pass1": [
  {
   "t": "0:12:48",
   "phrase": "court is calling 2025 CR 001064 state versus Paul Visual"
  },
  {
   "t": "0:12:58",
   "phrase": "can I have parties announced / are you Mr. Visual"
  },
  {
   "t": "0:23:59",
   "phrase": "court is calling 2026 CR 011484 state versus Javan Davis"
  }
 ],
 "gaps": [
  {
   "in": "0:00:00",
   "out": "0:12:48",
   "kind": "NON-CASE",
   "label": "banter"
  },
  {
   "in": "1:24:40",
   "out": "1:45:52",
   "kind": "NON-CASE",
   "label": "silence"
  }
 ],
 "cases": [
  {
   "id": 5,
   "name": "Salvador Garcia",
   "cause_no": "2026 CR008645",
   "in": "1:09:43",
   "out": "1:24:40",
   "remove": null,
   "ruling_tc": "1:23:03",
   "ruling_deferred": false,
   "monetisation": "OK",
   "score": 41,
   "status": "used",
   "reject_reason": null,
   "what_it_is": "A repeat drunk driver asks for treatment instead of prison, and the state wants 10 years.",
   "charge": "Felony drunk driving with a long repeat record",
   "facing": "State seeks 10 years in prison",
   "question": "Can treatment beat a record going back to 1996?",
   "story": "Salvador Garcia has already entered his plea and asks for probation with nine months of inpatient treatment. The prosecutor puts a 0.317 reading and his prior convictions to him, and Judge Boyd reads his history out year by year.",
   "root_against": "The defendant: he drove drunk while on parole, and the viewer weighs that against his plea for help.",
   "moment": "Your BAC that night was a 0.317.",
   "moment_tc": "1:19:20",
   "ends_on": "10 years in prison with a two-year license suspension",
   "result": {
    "sentence": "10 years in prison",
    "conditions": "Credit for time served; 2-year license suspension"
   },
   "phases": [
    {
     "phase": "call",
     "tc": "1:09:43",
     "evidence": "Court is calling 2026CR008645 state versus Salvador Garcia"
    },
    {
     "phase": "plea_or_admonish",
     "tc": "1:10:23",
     "evidence": "the state is opposed to your application for community supervision"
    },
    {
     "phase": "evidence_or_argument",
     "tc": "1:18:09",
     "evidence": "how many DWIs do you have? It's going to be my six."
    },
    {
     "phase": "ruling",
     "tc": "1:23:03",
     "evidence": "Sentence you to 10 years in prison."
    },
    {
     "phase": "wrap_up",
     "tc": "1:24:24",
     "evidence": "Good luck to you."
    }
   ],
   "interrupted": false,
   "segments": null,
   "boundary": {
    "out_evidence": "You're welcome. Appreciate you. You're welcome."
   },
   "virality": {
    "factors": {
     "judge_confrontation": 12,
     "emotion": 6,
     "surprise_ruling": 8,
     "numbers": 10,
     "topic_click": 14,
     "completeness": 10,
     "av_quality": 3
    },
    "why": "A 0.317 reading, six drunk driving priors, and a judge reading his record aloud before denying probation."
   }
  },
  {
   "id": 9,
   "name": "Reyes",
   "cause_no": "",
   "in": "0:59:09",
   "out": "1:00:05",
   "remove": null,
   "ruling_tc": "0:59:41",
   "ruling_deferred": false,
   "monetisation": "OK",
   "score": 4,
   "status": "rejected",
   "reject_reason": "under 2:00 of hearing",
   "what_it_is": "A jury trial request on plea deadline day.",
   "charge": "Not stated",
   "facing": "Not stated",
   "question": "Will the case go to trial?",
   "story": "Ms. Reyes requests a jury trial. The judge sets it for November 30.",
   "root_against": "None.",
   "moment": "Your plea deadline date has expired.",
   "moment_tc": "0:59:51",
   "ends_on": "Jury trial set for November 30",
   "result": {
    "sentence": "Jury trial set",
    "conditions": "No plea agreements without good cause"
   },
   "phases": [
    {
     "phase": "call",
     "tc": "0:59:19",
     "evidence": "All right. Ms. Reyes. Can you come down?"
    },
    {
     "phase": "ruling",
     "tc": "0:59:41",
     "evidence": "We're going to bring you back on November 30th for a jury trial."
    },
    {
     "phase": "wrap_up",
     "tc": "0:59:59",
     "evidence": "Thank you, Doug. Thank you."
    }
   ],
   "interrupted": false,
   "segments": null,
   "boundary": {
    "out_evidence": "Thank you, Doug. Thank you."
   }
  }
 ]
}
```
