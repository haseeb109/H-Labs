"""Hand-authored plan for lVQ79x0Hd_w (Judge Boyd 9 May 2025: afternoon docket + State v. Rendon jury trial)."""
import json, sys
sys.path.insert(0, ".")
R = lambda a, b, why="": {"in": a, "out": b, "why": why}
P = {
 "source_file": "lVQ79x0Hd_w.mp4", "stream_length": "3:00:23",
 "working_note": [
  "Stream = one short sentencing + a JURY TRIAL (State v. Rendon, defense witness). 2 cases found: Rendon (lead, highlight cut of the defendant's testimony) and Maldonado.",
  "Rendon is kept as 8 pieces (direct + cross) - 19:30 of 1:49:00 - because the rest is video playback, exhibits and a 19-min recess.",
  "Hook inside lead range: YES (2:21:54-2:22:07 in the cross-examination).",
  "Verdict pending: closing arguments Monday 9:30 (court says so at 2:59).",
 ],
 "pass1": [],
 "gaps": [
  {"in":"0:00:00","out":"0:13:25","kind":"NON-CASE","label":"stream pre-roll, no hearing"},
  {"in":"0:20:23","out":"0:53:38","kind":"NON-CASE","label":"attorney talk, a reset to May 22 (under 2:00 of hearing), then dead air while the jury is brought in"},
  {"in":"2:59:12","out":"3:00:23","kind":"NON-CASE","label":"jurors excused for the weekend"},
 ],
 "cases": [
  {"id":1,"name":"Mariano Rendon Jr.","cause_no":"","resume":True,"in":"0:53:38","out":"2:59:12",
   "removes":[R("0:54:13","1:09:09","background questions, club operation"),
              R("1:13:46","1:29:28","video playback and exhibits"),
              R("1:30:48","1:44:04","photos and exhibits"),
              R("1:45:09","2:11:40","exhibits, recess and the start of cross"),
              R("2:13:00","2:17:34","camera questions"),
              R("2:22:37","2:31:12","recorded call replay"),
              R("2:33:52","2:38:40","body cams and the call"),
              R("2:41:26","2:58:01","tire shop, cameras, more fights")],
   "ruling_tc":None,"ruling_deferred":True,"monetisation":"OK","score":44,"status":"used","reject_reason":None,
   "what_it_is":"A jury trial for a club owner charged with seriously injuring a man in a 2023 dance-floor brawl.",
   "charge":"Aggravated assault causing serious bodily injury (second-degree felony)","facing":"2 to 20 years in prison",
   "question":"Did a club owner stop a shooting, or seriously hurt a man who was pinned down?",
   "story":"On the night of August 19, 2023 a fight broke out on the dance floor of his nightclub. The owner says he ran in, pushed people off a security guard and dropped a knee on a man on the floor because the man's hands were near the guard's gun. The state asks why he never mentioned a gun to anyone until a video surfaced.",
   "root_against":"The owner: only one hazy video was turned over, and he says he never told police about the gun.",
   "moment":"Prosecutor: 'When did you mention that gun?' Owner: 'I don't think I did.'","moment_tc":"2:22:04",
   "ends_on":"Both sides rest; closing arguments Monday",
   "result":{"sentence":"Verdict pending - closing arguments Monday 9:30","conditions":"Jury returns after the weekend; no deliberation yet"}},
  {"id":2,"name":"Hank Maldonado","cause_no":"2024 CR2071 and 2024 CR7676","in":"0:13:25","out":"0:20:23","remove":None,
   "ruling_tc":"0:18:51","ruling_deferred":False,"monetisation":"OK","score":30,"status":"used","reject_reason":None,
   "what_it_is":"A sentencing for a man who skipped his earlier sentencing date.",
   "charge":"Two felony vehicle cases (plea bargain with a 12-month cap)","facing":"Up to 12 months in state jail",
   "question":"Will skipping his own sentencing date cost him probation?",
   "story":"He pleaded no contest to two cases and asked for deferred adjudication. The state opposes it because he did not appear for an earlier sentencing date. His lawyer says he was terrified of going to prison.",
   "root_against":"The defendant: a failure to appear and a record going back to 2011.",
   "moment":"Judge: 'You're not a teenager... why you would steal someone else's vehicle is beyond the court's understanding.'","moment_tc":"0:18:41",
   "ends_on":"12 months in state jail, cases run together",
   "result":{"sentence":"12 months in state jail","conditions":"Both cases run concurrently; restitution and no contact with two named victims"}},
 ],
 "videos": [{
  "n": 1, "case_ids": [1,2],
  "hook": {"in":"2:21:54","out":"2:22:07","spoken":"","headline":"He Never Told the Detective About a Gun"},
  "bridges": [
   {"after_case_id":1,"text":"A club owner says one knee stopped a shooting, but the state says he never mentioned a gun until a video surfaced. The jury returns Monday. Next, a man who skipped his own sentencing finds out what that costs.","split_after_sentence":None}],
  "vo_final": {"text":"Two hearings, one afternoon. A man who ran from sentencing learns what that costs. A bar owner defends a knee that put a man in surgery. Who do you believe, the owner protecting his club, or the prosecutor who says the story changed? Pick a side below, and subscribe for the next real Bexar County hearing."},
  "quiz": {"question":"What did the prosecutor say the club owner never told police about?","options":{"A":"A stolen radio","B":"A gun","C":"A security camera"},"answer":"B  A gun"},
  "thumbnail": {"window_in":"2:21:56","window_out":"2:21:59","look_for":"the owner's face as he says he does not remember","text":"JURY RETURNS MONDAY","gold_word":"MONDAY","placement":"top"},
  "title": "Club Owner Says One Knee Stopped a Shooting — Then Admits He Never Told Police About a GUN",
  "backup_title": "2023 Nightclub Brawl Trial — Owner Testifies He Feared a MASSACRE and Pinned a Man",
  "description": {
   "first_line":"Did a nightclub owner stop a shooting, or seriously hurt a man who was pinned to the floor?",
   "what_happens":"Mariano Rendon Jr. is on trial for aggravated assault after a brawl at his nightclub on August 19, 2023. He explains how he ran onto the dance floor, why he put a knee on a man's stomach, and why only one hazy video reached police. On cross-examination the prosecutor asks when he first mentioned a gun. A second hearing follows: a man who missed his own sentencing date learns what that costs.",
   "pending_note":"The jury has not reached a verdict. Closing arguments were set for the next court day.",
   "search_question":"What does a jury hear in an aggravated assault trial over a bar fight?",
   "answer":"In an aggravated assault trial the state must show the defendant caused serious bodily injury, and the defense can argue the force was needed to protect other people. Here the defendant testifies that he acted in milliseconds because a security guard's weapon was close to a man's hands. On cross-examination the prosecutor presses on what he told the detective, which recordings were turned over, and when he first mentioned a gun. Jurors weigh that testimony together with the video evidence and the judge's instructions. This is a summary of one court hearing, not legal advice.",
   "related_question":"Was the knee drop self-defense or too much force? Tell us which side you are on."},
  "chapters": [
   {"tc":"0:53:38","label":"The club owner takes the stand"},
   {"tc":"1:09:09","label":"How the dance-floor brawl started"},
   {"tc":"1:29:28","label":"The knee on the man on the floor"},
   {"tc":"2:11:40","label":"Why only one hazy video was handed over"},
   {"tc":"2:17:34","label":"Why he never mentioned the gun"},
   {"tc":"2:38:40","label":"Whatever means it takes to deescalate"},
   {"tc":"0:13:25","label":"A man who skipped sentencing hears 12 months"}],
  "tags": ["aggravated assault trial","nightclub fight trial","jury trial texas","bar owner on trial","knee drop security guard","cross examination","judge boyd","judge stephanie boyd","187th district court","bexar county court","san antonio court","real courtroom footage","texas jury trial","failure to appear sentencing"],
  "pinned_comment":"The owner says one knee stopped a shooting. The prosecutor says he never mentioned a gun until a video surfaced. Whose side are you on? Pick one below.",
  "community_post":"New Judge Boyd video: a nightclub owner under cross-examination about a knee drop and a gun he says he feared, plus a man who skipped his own sentencing. Who convinced you more, the owner or the prosecutor? Tell us below.",
  "publish":{"slot":"9am ET"}, "verdict_pending": True, "followup_owed": "Closing arguments and the jury verdict in State v. Rendon (court resumed the next court day at 9:30)"}]
}
json.dump(P, open("tests/rendon_2025-05-09_plan.json","w"), indent=2, ensure_ascii=False)
print("written")
