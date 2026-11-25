"""Documentary renderer: ONE engine for the documentary editing styles (no channel name, intro or watermark: the owner adds
branding in the editor).

    case_file      Case File Documentary  - cold open of the payoff -> full-story stamp -> title / profile / CASE SUMMARY ->
                                            backstory VO over B-roll -> charge + punishment range -> dated chapters + court
    verdict_first  Verdict First          - sentence moment -> number -> sentence document -> earlier flash -> 3 questions ->
                                            countdown chapters ("3 DECISIONS EARLIER") -> verdict again + answers
    emotional      Emotional Cut          - kinetic quote on black -> slow-motion B&W reaction -> black line -> slow document ->
                                            court with fewer cards -> quiet ending
    evidence_board Evidence Board         - key moment -> cork board reveal -> master file pinned -> pins + strings with VO ->
                                            court -> NEW PIN board updates
    instant_replay Instant Replay         - moment at full speed -> REPLAY at half speed with telestrator marks -> record impact ->
                                            court with replays of the key exchanges
    docu_series    Docu-Series Episodes   - "previously on" (from earlier episodes of the same defendant, state/series/) ->
                                            updated case file -> EPISODE n card -> court -> cliffhanger

Every style: the case document (ucf.casedoc, always), retention beats on court (ucf.engage: a fact / term / ruling / mini
document at least every 18 s), speaker-labelled captions, music bed ducked under court + SFX on graphics (ucf.audiomix), and
B-roll from the Pexels/Pixabay library and/or the owner's own folder (ucf.stock.pick_broll).

The plan is the normal mode-"all" plan. Extra per-video brain fields live in video["doc"] (prompts/shared/doc_styles.md);
every one of them is optional - the renderer falls back to the plan's own fields, so a video is always made.
"""
import json
import re
import subprocess
from pathlib import Path

from . import audiomix, casedoc, engage, paper, speakers, stock, tts
from . import timeline as TL
from .captions import libass_ffmpeg, subtitles_filter
from .render import (AENC, AUDIO_NORM, TS, Renderer, court_audio, join_segments, probe_dur, run, still, venc)
from .timeutil import fmt_tc, parse_tc

ROOT = Path(__file__).resolve().parent.parent

# music mood per segment role, per style (folder names under <library>/music)
MOODS = {
    "case_file": {"cold": "drone_tense", "story": "investigative_bed", "bridge": "drone_tense", "end": "ending_swell"},
    "verdict_first": {"cold": "ominous_bass", "story": "suspense_pulse", "bridge": "drone_tense", "end": "ending_swell"},
    "emotional": {"cold": "emotional_piano", "story": "emotional_piano", "bridge": "emotional_piano", "end": "emotional_piano"},
    "evidence_board": {"cold": "drone_tense", "story": "investigative_bed", "bridge": "suspense_pulse", "end": "ending_swell"},
    "instant_replay": {"cold": "suspense_pulse", "story": "upbeat_light", "bridge": "suspense_pulse", "end": "ending_swell"},
    "docu_series": {"cold": "investigative_bed", "story": "investigative_bed", "bridge": "drone_tense", "end": "suspense_pulse"},
}
DEFAULT_BROLL = ["courthouse_stone", "case_folder", "gavel", "courtroom_empty", "police_car_night", "documents_desk"]


def _chap(title, default):
    """Chapter name for YouTube from a card title: 'THE PLEA' -> 'The Plea'; generic 'PART n' -> default."""
    t = re.sub(r"\s+", " ", str(title or "")).strip()
    if not t or re.fullmatch(r"PART \d+", t.upper()):
        return default
    return t.title() if t.isupper() else t


def youtube_chapters(rows, total):
    """[(start s, label)] from the pieces the renderer made: starts at 0:00, >= 10 s apart, none in the last 60 s
    (YouTube needs 3+ chapters to show them; the QC flags a chapter in the final minute)."""
    out = []
    for i, r in enumerate(rows):
        lab = r.get("chapter") or ("The moment" if i == 0 else "")
        if not lab:
            continue
        t = 0.0 if not out else r["start"]
        if out and t > total - 60:
            continue
        if out and t - out[-1][0] < 10:
            # a short piece (penalty card) before a chapter card: the chapter wins; at 0:00 only over the default name
            if len(out) > 1 or not rows[0].get("chapter"):
                out[-1] = (out[-1][0], lab)
            continue
        out.append((t, lab))
    return out


def _short(t, n=60):
    t = re.sub(r"\s+", " ", str(t or "")).strip()
    return t if len(t) <= n else t[:n - 1].rsplit(" ", 1)[0] + "…"


class DocRenderer(Renderer):
    def __init__(self, cfg, sources, root):
        super().__init__(dict(cfg, logo_file="", coming_up_tag=False), sources, root)
        self.cfg = cfg
        self.logo = None                      # no channel branding in these styles
        self.tag_png = None
        self.style = cfg.get("doc_style", "case_file")
        self.pal = cfg.get("palette") or {}
        self.moods = dict(MOODS.get(self.style, MOODS["case_file"]), **(cfg.get("music_moods") or {}))
        self.libass = libass_ffmpeg(cfg)
        # full | cinema (letterbox + film grade) | episode (teal grade + EP bug) | broadcast (scorebug) | verdict (outcome
        # chip) | pinned (photo on cork)
        self.frame_kind = str(cfg.get("court_frame") or "full")
        self.verdict_text = self.bug_text = self.bug_sub = self.ep_label = ""
        self.card_variant = {"cinema": "minimal", "episode": "episode"}.get(self.frame_kind, "card")

    # ================================================================== small helpers
    def _out(self, out):
        return [*venc(self.enc), *AENC, *TS, str(out)]

    def voice(self, text, name):
        """text -> one wav (clips of <= 18 s joined) and its length; '' -> (None, 0)."""
        text = (text or "").strip()
        if not text:
            return None, 0.0
        wavs = tts.synth_clips(text, self.tts_cache, self.cfg, self.ui)
        if len(wavs) == 1:
            return wavs[0], probe_dur(wavs[0])
        out = self.work / f"vo_{name}.wav"
        if not out.exists():
            lst = self.work / f"vo_{name}.txt"
            lst.write_text("".join(f"file '{Path(w).resolve()}'\n" for w in wavs), encoding="utf-8")
            run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-af", AUDIO_NORM, out])
        return out, probe_dur(out)

    def frame(self, t, out):
        out = Path(out)
        if not out.exists():
            run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{max(0, t):.2f}", "-i", self.srcp, "-frames:v", "1",
                 "-vf", "scale=1280:-2", "-q:v", "3", out])
        return out

    def png(self, name):
        return self.work / "gfx" / name

    def portrait(self):
        """The defendant's face for the polaroid / profile (2026-11-24: it showed the whole 4-tile Zoom grid). Frames from
        where the DEFENDANT speaks (doc.turns), then across the case; the biggest clear face, cropped to the photo shape.
        No face detector / no face -> the plain frame, as before."""
        from . import faces
        out = self.png("face.jpg")
        if out.exists():
            return out
        times = []
        for tu in self.doc.get("turns") or []:
            try:
                if str(tu.get("who", "")).upper().startswith("DEF"):
                    a, b = parse_tc(tu["from"]), parse_tc(tu["to"])
                    times += [a + (b - a) * k for k in (0.3, 0.7)]
            except (KeyError, ValueError, TypeError, AttributeError):
                continue
        times += [self.case_a + x for x in (8, 25, 45, 75)]
        times = [t for t in times if self.case_a <= t < self.case_b][:6]
        best = None
        if faces.available():
            for t in times:
                f = self.frame(t, self.png(f"pf_{int(t)}.jpg"))
                fs = faces.detect(f)
                if fs and (best is None or fs[0]["w"] * fs[0]["h"] * fs[0]["score"] > best[1]["w"] * best[1]["h"] * best[1]["score"]):
                    best = (f, fs[0])
        if not best:
            return self.frame(self.case_a + 8, out)
        from PIL import Image
        with Image.open(best[0]) as im:
            x, y, w, h = faces.face_crop_box(best[1], im.width, im.height, scale=2.6, aspect=460 / 520)
            im.convert("RGB").crop((x, y, x + w, y + h)).save(out, quality=92)
        return out

    # ================================================================== segment encoders
    # ---- the style's own court frame (2026-11-25: one frame for all six styles made 80% of every video look the same)
    PIN_BOX = (224, 110, 1472, 828)              # Evidence Board: where the footage "photo" hangs on the cork

    def grade_tail(self):
        """The cheap part of the style's grade (a filter on the footage); tint, vignette and letterbox come from look_png()."""
        return {"cinema": "hue=s=0.55"}.get(self.frame_kind, "")

    def look_png(self):
        """Letterbox / tint / vignette as one PNG laid over court, B-roll and chapter cards (None for plain styles)."""
        return paper.look_layer(self.frame_kind, self.png("look.png"), self.pal)

    def frame_layers(self, date, tag, dur):
        """Always-on graphics of a court block: date bar / scorebug / episode bug, verdict chip, pins. -> [(png, 0, dur)]."""
        f, L = self.frame_kind, [self.look_png()]
        if f == "broadcast":
            rep = tag.upper().startswith("REPLAY")
            L.append(paper.scorebug("REPLAY ×0.5" if rep else "COURT", self.bug_text, "" if rep else "REAL FOOTAGE",
                                    self.png("bug.png"), self.pal, sub=_short(tag if tag and not rep else self.bug_sub, 40)))
        elif f == "episode" and self.ep_label and not self._earlier:
            L.append(paper.top_bar(self.ep_label, self.png("top.png"), self.pal, tag=tag))
        elif date or tag:
            L.append(paper.top_bar(date or "", self.png("top.png"), self.pal, tag=tag))
        if f == "verdict" and self.verdict_text and not self._earlier:
            L.append(paper.corner_chip("THE OUTCOME", self.verdict_text, self.png("vchip.png"), self.pal))
        if f == "pinned":
            L.append(paper.pinned_overlay(self.PIN_BOX, self.png("pins.png"), self.pal))
        return [(p, 0.0, dur) for p in L if p]

    def seg_court(self, a, b, out, date="", tag="", beats=(), punch=(), bw=False, speed=1.0, extra=(), captions=True,
                  turns=None):
        """Court footage a..b (source seconds) in the style's frame (full / cinema letterbox / episode grade / broadcast bug /
        verdict chip / pinned photo on cork), engagement beat PNGs, punch-ins, speaker captions; bw / slow motion for
        replays and the emotional style. extra = [(png, start, end)] (local s)."""
        dur = (b - a) / speed
        f = self.frame_kind
        ins = ["-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", self.srcp]
        en = "+".join(f"between(t,{s:.2f},{e:.2f})" for s, e in punch)
        if f == "pinned":
            x, y, w, h = self.PIN_BOX
            ins += ["-i", str(paper.cork(self.png("cork.png"), self.pal))]
            fc = [f"[0:v]setpts=(PTS-STARTPTS)/{speed},fps=30,scale={w}:{h}:force_original_aspect_ratio=decrease,"
                  f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1[ph]", still(1, dur, "ck")]
            if punch:
                fc += ["[ph]split=2[pha][phb]", f"[phb]scale=iw*1.22:ih*1.22,crop={w}:{h}[php]",
                       f"[pha][php]overlay=0:0:enable='{en}'[ph2]"]
                ph = "ph2"
            else:
                ph = "ph"
            fc += [f"[{ph}]pad={w + 28}:{h + 28}:14:14:color=0xF4F1EA[phf]", f"[ck][phf]overlay={x - 14}:{y - 14}[c1]"]
        else:
            fc = [f"[0:v]setpts=(PTS-STARTPTS)/{speed},fps=30,split=2[s0][s1]",
                  "[s0]scale=480:270,boxblur=8:2,scale=1920:1080,setsar=1,eq=brightness=-0.18[bg]",
                  "[s1]scale=1920:1080:force_original_aspect_ratio=decrease,setsar=1[fg]"]
            if punch:
                fc.append("[fg]split=2[fga][fgb]")
                fc.append("[fgb]scale=iw*1.22:ih*1.22,crop=iw/1.22:ih/1.22[fgp]")
                fc.append("[bg][fga]overlay=(W-w)/2:(H-h)/2[c0]")
                fc.append(f"[c0][fgp]overlay=(W-w)/2:(H-h)/2:enable='{en}'[c1]")
            else:
                fc.append("[bg][fg]overlay=(W-w)/2:(H-h)/2[c1]")
        last = "c1"
        if self.grade_tail():
            fc.append(f"[c1]{self.grade_tail()}[cg]")
            last = "cg"
        layers = self.frame_layers(date, tag, dur)
        layers += [(p, s, e) for p, s, e in list(beats) + list(extra) if p]
        k0 = 1 if f != "pinned" else 2                    # inputs before the layers: the footage (+ the cork)
        for j, (p, s, e) in enumerate(layers):
            k = k0 + j
            ins += ["-i", str(p)]
            fc.append(still(k, dur, f"l{k}", "yuva420p"))
            fc.append(f"[{last}][l{k}]overlay=0:0:enable='between(t,{s:.2f},{e:.2f})'[o{k}]")
            last = f"o{k}"
        if bw:
            fc.append(f"[{last}]hue=s=0,eq=contrast=1.08[bwv]")
            last = "bwv"
        if captions and self.libass:
            lines = [(s["start"] - a, s.get("end", s["start"] + 3) - a, s["text"]) for s in self.segs
                     if a - 0.5 <= s["start"] < b - 0.3]
            lines = [((s) / speed, (min(e, b - a)) / speed, t) for s, e, t in lines if t.strip()]
            if lines:
                ass = Path(out).with_suffix(".ass")
                look = (self.cfg.get("caption_look") or {})
                tl = []
                for tu in turns or []:
                    try:
                        tl.append({"from": (parse_tc(tu["from"]) - a) / speed, "to": (parse_tc(tu["to"]) - a) / speed,
                                   "who": str(tu["who"])})
                    except (KeyError, ValueError, TypeError):
                        continue
                n = speakers.build_ass(speakers.label(lines, tl, self.cfg.get("speaker_names")), ass, look)
                if n:
                    fc.append(f"[{last}]{subtitles_filter(ass, ROOT / 'shared' / 'fonts')}[cap]")
                    last = "cap"
        fc.append(f"[{last}]format=yuv420p[v]")
        af = court_audio(self.cfg)
        if speed != 1.0:
            af = f"atempo={max(0.5, speed):.3f}," + af
        fc.append(f"[0:a]{af},apad[a]")
        run(["ffmpeg", "-y", "-loglevel", "error", *ins, "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]",
             "-t", f"{dur:.3f}", *self._out(out)])
        return dur

    def seg_cards(self, steps, out, vo=None, lead=0.4, push=True):
        """Full-frame card PNGs one after the other [(png, seconds)], a slow push-in, optional voice under them."""
        total = sum(d for _, d in steps)
        ins, fc = [], []
        for k, (p, d) in enumerate(steps):
            ins += ["-i", str(p)]
            mv = (f",scale=2016:1134,crop=1920:1080:x='48-48*t/{d:.2f}':y='27-27*t/{d:.2f}'" if push else "")
            fc.append(still(k, d, f"c{k}") + f";[c{k}]setpts=PTS-STARTPTS{mv},setsar=1,fps=30,format=yuv420p[d{k}]")
        fc.append("".join(f"[d{k}]" for k in range(len(steps))) + f"concat=n={len(steps)}:v=1:a=0[v]")
        n = len(steps)
        if vo:
            ins += ["-i", str(vo)]
            ms = int(lead * 1000)
            fc.append(f"[{n}:a]adelay={ms}|{ms},apad,{AUDIO_NORM}[a]")
        else:
            ins += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
            fc.append(f"[{n}:a]{AUDIO_NORM}[a]")
        run(["ffmpeg", "-y", "-loglevel", "error", *ins, "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]",
             "-t", f"{total:.3f}", *self._out(out)])
        return total

    def seg_broll(self, tags, text, out, name, pills=(), bw=False, shot=4.2, lead=0.4):
        """Narration over B-roll shots (3-5 s, slow push, one grade) with pill PNGs [(png, start, end)].
        No clips anywhere -> blurred court footage behind the pills (noted in qc)."""
        vo, vd = self.voice(text, name)
        dur = max(3.0, vd + lead + 0.5) if vo else max(3.0, shot)
        n = max(1, int(round(dur / shot)))
        clips = []
        for i in range(n):
            tag = tags[i % len(tags)] if tags else DEFAULT_BROLL[i % len(DEFAULT_BROLL)]
            got = stock.pick_broll(self.cfg, tag, 1, self.used_broll, seed=hash((name, i)) & 0xffff, ui=self.ui)
            if got:
                clips.append(got[0])
        ins, fc = [], []
        d1 = dur / max(1, len(clips)) if clips else dur
        grade = "eq=saturation=0.72:brightness=-0.05:contrast=1.06,vignette=PI/5" + (",hue=s=0" if bw else "")
        if clips:
            for k, c in enumerate(clips):
                ins += ["-ss", "0.5", "-t", f"{d1 + 0.1:.3f}", "-i", str(c)]
                fc.append(f"[{k}:v]setpts=PTS-STARTPTS,fps=30,scale=2112:1188:force_original_aspect_ratio=increase,"
                          f"crop=2112:1188,crop=1920:1080:x='192*t/{d1:.2f}*0.5':y='108*t/{d1:.2f}*0.5',setsar=1,{grade},"
                          f"trim=duration={d1:.3f},setpts=PTS-STARTPTS,format=yuv420p[b{k}]")
            fc.append("".join(f"[b{k}]" for k in range(len(clips))) + f"concat=n={len(clips)}:v=1:a=0[bv]")
            k0 = len(clips)
        else:
            self.notes_once("no B-roll found (library / folder / API) - blurred court footage used")
            a0 = self.case_a + 5
            ins += ["-ss", f"{a0:.2f}", "-t", f"{dur:.3f}", "-i", self.srcp]
            fc.append(f"[0:v]setpts=PTS-STARTPTS,fps=30,scale=480:270,boxblur=6:2,scale=1920:1080,setsar=1,{grade},"
                      f"eq=brightness=-0.12,format=yuv420p[bv]")
            k0 = 1
        last = "bv"
        if self.grade_tail():
            fc.append(f"[bv]{self.grade_tail()}[bvg]")
            last = "bvg"
        lk = self.look_png()
        pills = ([(lk, 0.0, dur + 1)] if lk else []) + list(pills)
        for j, (p, s, e) in enumerate(pills):
            idx = k0 + j
            ins += ["-i", str(p)]
            fc.append(still(idx, dur, f"p{j}", "yuva420p"))
            fc.append(f"[{last}][p{j}]overlay=0:0:enable='between(t,{s:.2f},{min(e, dur):.2f})'[q{j}]")
            last = f"q{j}"
        fc.append(f"[{last}]format=yuv420p[v]")
        ai = k0 + len(pills)
        if vo:
            ins += ["-i", str(vo)]
            ms = int(lead * 1000)
            fc.append(f"[{ai}:a]adelay={ms}|{ms},apad,{AUDIO_NORM}[a]")
        else:
            ins += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
            fc.append(f"[{ai}:a]{AUDIO_NORM}[a]")
        run(["ffmpeg", "-y", "-loglevel", "error", *ins, "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]",
             "-t", f"{dur:.3f}", *self._out(out)])
        return dur

    def seg_blur(self, png, text, out, name, t0=None, bw=False, lead=0.4, min_dur=4.0):
        """A transparent card over blurred court footage with narration (chapter cards, time jumps, telestrator stills)."""
        vo, vd = self.voice(text, name)
        dur = max(min_dur, vd + lead + 0.4)
        t0 = self.case_a + 3 if t0 is None else t0
        ins = ["-ss", f"{max(0, t0):.2f}", "-t", f"{dur:.3f}", "-i", self.srcp, "-i", str(png)]
        tail = ("," + self.grade_tail()) if self.grade_tail() else ""
        fc = [f"[0:v]setpts=PTS-STARTPTS,fps=30,scale=480:270,boxblur=8:2,scale=1920:1080,setsar=1,eq=brightness=-0.25"
              + (",hue=s=0" if bw else "") + tail + "[bg]", still(1, dur, "c", "yuva420p"), "[bg][c]overlay=0:0,format=yuv420p[v]"]
        lk = self.look_png()
        if lk:                                     # the style's letterbox / tint under the card
            ins += ["-i", str(lk)]
            fc[-1] = "[bg][lk]overlay=0:0[bgl];[bgl][c]overlay=0:0,format=yuv420p[v]"
            fc.insert(2, still(2, dur, "lk", "yuva420p"))
        ai = 3 if lk else 2                        # audio input index (footage, card[, look], voice)
        if vo:
            ins += ["-i", str(vo)]
            ms = int(lead * 1000)
            fc.append(f"[{ai}:a]adelay={ms}|{ms},apad,{AUDIO_NORM}[a]")
        else:
            ins += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
            fc.append(f"[{ai}:a]{AUDIO_NORM}[a]")
        run(["ffmpeg", "-y", "-loglevel", "error", *ins, "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]",
             "-t", f"{dur:.3f}", *self._out(out)])
        return dur

    def notes_once(self, msg):
        if msg not in self.notes:
            self.notes.append(msg)
            self.ui("  note: " + msg)

    # ================================================================== the plan -> building blocks
    def _ctx(self, plan, video):
        by_id = {c["id"]: c for c in plan["cases"]}
        self.case = by_id[video["case_ids"][0]]
        self.cases = [by_id[i] for i in video["case_ids"]]
        src = self.case.get("source_file") or plan["source_file"]
        self.srcname = src
        self.srcp = self.src(src)["path"]
        self.doc = video.get("doc") or {}
        tpath = self.tts_cache.parent / "transcript.json"
        try:
            self.segs = json.loads(tpath.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.segs = []
        a, b = parse_tc(self.case["in"]), parse_tc(self.case["out"])
        self.case_a, self.case_b = a, b
        text = " ".join(s["text"] for s in self.segs if a - 30 <= s["start"] <= b + 30)
        meta = {"court": self.cfg.get("court_line_plain") or plan.get("court") or self.cfg.get("_court_line") or "", "date": self.doc.get("date") or plan.get("date", "") or self.cfg.get("_hearing_date", "")}
        self.facts, dropped = casedoc.build_facts(dict(self.case, case_doc=self.doc.get("case_doc")), text, meta)
        for k, why in dropped:
            self.ui(f"  case document: '{k}' left out ({why})")
        self.date = self.doc.get("date") or self.facts.get("hearing_date", "") or self.cfg.get("_hearing_date", "")
        self.name = self.facts.get("defendant") or self.case.get("name", "")
        self.hook = (parse_tc(video["hook"]["in"]), parse_tc(video["hook"]["out"]))
        # what the style's court frame keeps on screen
        self.verdict_text = _short(self.doc.get("verdict_big") or self.facts.get("sentence") or self.facts.get("result") or "", 22).upper()
        last = (self.name.split() or ["THE DEFENDANT"])[-1].upper()
        self.bug_text = _short(f"STATE v. {last}", 28)
        self.bug_sub = _short(self.facts.get("charges", ""), 40).upper()

    def moments(self, n=2):
        """Cold-open moments: brain picks (doc.cold_open) inside the case, else the hook + the ruling phase."""
        out = []
        for m in self.doc.get("cold_open") or []:
            try:
                a, b = parse_tc(m["in"]), parse_tc(m["out"])
            except (KeyError, ValueError, TypeError):
                continue
            if self.case_a - 5 <= a < b <= self.case_b + 5 and 4 <= b - a <= 45:
                out.append((a, b, m.get("label", "")))
        if not out:
            out.append((*self.hook, self.doc.get("hook_label", "")))
            r = self.ruling_tc()
            if r is not None and abs(r - self.hook[0]) > 20 and self.case_a < r < self.case_b:
                out.append((max(self.case_a, r - 4), min(self.case_b, r + 14), ""))
        return out[:n]

    def ruling_tc(self):
        """Stream seconds of the ruling: phases is a LIST of {"phase", "tc"} in the v10 plan (2026-11-24: read as a dict,
        Verdict First crashed on every real plan), else ruling_tc, else doc.rulings[0]. None when unknown."""
        ph = self.case.get("phases")
        cands = []
        if isinstance(ph, list):
            cands += [p.get("tc") for p in ph if isinstance(p, dict) and p.get("phase") == "ruling"]
        elif isinstance(ph, dict):
            r = ph.get("ruling") or {}
            cands.append(r.get("tc") or r.get("in") if isinstance(r, dict) else r)
        cands.append(self.case.get("ruling_tc"))
        cands += [r.get("tc") for r in self.doc.get("rulings") or [] if isinstance(r, dict)]
        for c in cands:
            try:
                t = parse_tc(c)
            except (ValueError, TypeError, AttributeError, KeyError):
                continue
            if self.case_a <= t <= self.case_b:
                return t
        return None

    def parts(self):
        return TL.case_parts(self.case, self.cfg.get("cut_pad_out", 0.0))

    def chapters(self):
        """[(a, b, title)] court blocks with a chapter name each (doc.chapters by time, else PART n)."""
        parts = self.parts()
        named = []
        for ch in self.doc.get("chapters") or []:
            try:
                named.append((parse_tc(ch["at"]), _short(ch.get("title", ""), 28).upper()))
            except (KeyError, ValueError, TypeError):
                continue
        if not named:       # no chapters from the brain: the hearing, then the ruling (YouTube shows 3+ chapters only)
            r = self.ruling_tc() if not self._earlier else None
            if r is not None:
                named = [(parts[0][0], "THE HEARING"), (max(parts[0][0], r - 12), "THE RULING")]
        out = []
        for a, b in parts:
            cuts = sorted(t for t, _ in named if a + 20 < t < b - 20)
            edges = [a] + cuts + [b]
            for x, y in zip(edges, edges[1:]):
                title = next((tt for t, tt in named if abs(t - x) < 1), "")
                out.append((x, y, title))
        return [(a, b, t or f"PART {i + 1}") for i, (a, b, t) in enumerate(out)]

    def beats_for(self, a, b, speed=1.0, extra_busy=()):
        """Retention beats for the court block a..b -> (overlay [(png, s, e)], punch windows)."""
        dur = (b - a) / speed
        lines = [(s["start"] - a, s.get("end", s["start"] + 3) - a, s["text"]) for s in self.segs if a <= s["start"] < b]
        cands = []
        kmap = {"coming_up": "question", "verdict_q": "question", "so_far": "fact", "watch": "quote"}
        plan_items = [] if self._earlier else (self.video.get("overlays") or []) + (self.case.get("overlays") or [])
        for o in plan_items:
            try:
                t = (parse_tc(o["tc"]) if "tc" in o else float(o.get("t"))) - a
            except (KeyError, ValueError, TypeError):
                continue
            if o.get("text") and 0 <= t <= b - a:
                cands.append({"t": t / speed, "kind": kmap.get(o.get("kind"), "fact"), "text": o["text"], "dur": 4.0})
        cands += [dict(c, t=c["t"] / speed) for c in engage.find_jargon(lines)]
        if self.facts:
            cands.append({"t": None, "kind": "doc", "text": "CASE SUMMARY", "dur": 6.0})
            if self.facts.get("charges"):
                cands.append({"t": None, "kind": "charge", "text": self.facts["charges"], "dur": 4.0})
        for f in ("bond", "plea", "state_asked", "defense_asked"):
            if self.facts.get(f):
                cands.append({"t": None, "kind": "fact", "text": f"{casedoc.LABEL[f]}: {self.facts[f]}", "dur": 4.0})
        for r in [] if self._earlier else (self.doc.get("rulings") or []):
            try:
                t = (parse_tc(r["tc"]) - a) / speed
            except (KeyError, ValueError, TypeError):
                continue
            if 0 <= t <= dur and r.get("text"):
                cands.append({"t": t, "kind": "ruling", "text": r["text"], "dur": 5.0})
        gap_c = float(self.cfg.get("beat_gap_court", 18.0))
        beats, rep = engage.schedule(dur, [(0, dur, "court")], cands, existing=[(0, 4)] + list(extra_busy),
                                     cfg={"max_gap_court": gap_c})
        self.beat_report += rep
        out, punch = [], []
        for i, bt in enumerate(beats):
            k, txt = bt["kind"], bt["text"]
            name = f"beat_{int(a)}_{i}.png"
            if k == "zoom":
                punch.append((bt["start"], bt["end"]))
                continue
            if k == "push":
                continue
            if k == "jargon":
                term, _, d = txt.partition(": ")
                p = paper.jargon_pill(term, d, self.png(name), self.pal)
            elif k == "ruling":
                p = paper.ruling_lower_third([("RULING", _short(txt, 70))], self.png(name), self.pal)
            elif k == "doc":
                p = casedoc.mini_doc(self.facts, self.png(name), self.pal)
            elif k == "quote":
                p = paper.pill_stack([_short(txt, 60)], self.png(name), self.pal, x=60, y=820, kinds=["w"])[0]
            else:
                p = paper.pill_stack([_short(txt, 60)], self.png(name), self.pal, x=60, y=110,
                                     kinds=["r" if k == "charge" else ""])[0]
            out.append((p, bt["start"], bt["end"]))
        return out, punch

    def court_block(self, a, b, tag, out_name, chapter=None, **kw):
        """Court footage a..b. A long block is made in pieces of ~4 min (2026-11-24): one ffmpeg call per piece keeps the
        command under the Windows limit (a 40 min block had ~130 beat PNG inputs) and the beat schedule per piece."""
        span = float(self.cfg.get("court_chunk_s", 240.0))
        if kw.get("speed", 1.0) == 1.0 and b - a > span * 1.25:
            n = int((b - a) // span) + (1 if (b - a) % span > span * 0.25 else 0)
            edges = [a + (b - a) * k / n for k in range(n + 1)]
            for k, (x, y) in enumerate(zip(edges, edges[1:])):
                self._court_piece(x, y, tag, out_name.replace(".mp4", f"_{k}.mp4"), chapter if k == 0 else None, **kw)
            return
        self._court_piece(a, b, tag, out_name, chapter, **kw)

    def _court_piece(self, a, b, tag, out_name, chapter=None, **kw):
        beats, punch = self.beats_for(a, b, kw.get("speed", 1.0))
        out = self.work / out_name
        if not out.exists():
            self.seg_court(a, b, out, date=self.date, tag=tag, beats=beats, punch=punch,
                           turns=None if self._earlier else self.doc.get("turns"), **kw)
        self.add("court", out, a=a, b=b, **({"chapter": chapter} if chapter else {}))

    def doc_steps(self, name, per=0.9, last=2.5):
        pngs = casedoc.summary_card(self.facts, self.png(name), self.pal)
        return [(p, per) for p in pngs[:-1]] + [(pngs[-1], last)]

    # ================================================================== timeline bookkeeping
    def add(self, role, path, mood=None, sfx=None, **meta):
        """role: court | cold | story | bridge | end (music + chapters), sfx at the start of the piece."""
        if role == "court":
            meta.setdefault("src", self.srcname)      # an earlier hearing's clip while using() is active
        self.pieces.append((role, Path(path), mood, sfx, meta))

    # ================================================================== recipes
    def recipe_case_file(self, video):
        m = self.moments(2)
        a, b, lab = m[0]
        self.court_block(a, b, "", "c00_open1.mp4", extra=[(paper.pill_stack([lab], self.png("lab1.png"), self.pal, y=820)[0], 1, 6)] if lab else ())
        self.role_last("cold")
        tease = self.doc.get("tease") or f"You are about to see why {self.name} will never forget this day."
        p = self.work / "c01_tease.mp4"
        if not p.exists():
            self.seg_broll(self.doc.get("tease_broll") or ["courtroom_empty"], tease, p, "tease")
        self.add("cold", p, mood="cold")
        if len(m) > 1:
            self.court_block(m[1][0], m[1][1], "", "c02_open2.mp4")
            self.role_last("cold")
        prof = self.portrait()
        story = f"This is the full story of {self.name}."
        p = self.work / "c03_story.mp4"
        if not p.exists():
            cap = _short(self.name, 20)
            st = paper.profile_card(prof, [], self.png("pol.png"), self.pal, caption=cap)[0]
            st2 = paper.profile_card(prof, [], self.png("pols.png"), self.pal, caption=cap,
                                     stamp_text=_short(self.doc.get("stamp") or "THE FULL STORY", 22).upper())[0]
            vo, vd = self.voice(story, "story")
            self.seg_cards([(st, 0.8), (st2, max(2.6, vd + 0.6))], p, vo=vo)
        self.add("cold", p, sfx=("stamp_thud", 0.8))
        # title + profile + document
        title = paper.title_card(f"{self.facts.get('court', '')}".upper(), f"THE STATE OF TEXAS v. {self.name}".upper(),
                                 [self.facts.get("charges", ""), self.date], self.png("title.png"), self.pal)
        pills = [x for x in (self.doc.get("profile") or [self.facts.get("age") and f"{self.facts['age']} YEARS OLD",
                                                            self.facts.get("charges")]) if x][:4]
        prof_steps = paper.profile_card(prof, [_short(x, 34) for x in pills], self.png("prof.png"), self.pal,
                                        caption=_short(self.name, 20))
        p = self.work / "c05_case.mp4"
        if not p.exists():
            steps = [(title, 3.5)] + [(x, 1.4) for x in prof_steps] + self.doc_steps("sum.png")
            self.seg_cards(steps, p)
        self.add("story", p, mood="story", sfx="brass_hit", chapter="The case file")
        self.backstory("c06")
        self.penalty("c07")
        self.hearings(numbered=True)
        self.ending()

    def recipe_verdict_first(self, video):
        r = self.ruling_tc()
        a, b = (max(self.case_a, r - 6), min(self.case_b, r + 12)) if r is not None else self.hook
        self.court_block(a, b, "THE SENTENCE", "v00_sentence.mp4")
        self.role_last("cold")
        big = self.doc.get("verdict_big") or self.facts.get("sentence") or self.facts.get("result") or "THE VERDICT"
        p = self.work / "v01_big.mp4"
        if not p.exists():
            self.seg_cards([(paper.black_text(_short(big, 24).upper(), self.png("big.png"), self.pal,
                                              colour=self.pal.get("danger", "#D7263D")), 2.6)] + self.doc_steps("sum.png", 0.7, 2.2), p)
        self.add("cold", p, mood="cold", sfx="boom")
        back = self.doc.get("tease") or "But it did not have to end like this. Here is how we got here."
        p = self.work / "v02_back.mp4"
        if not p.exists():
            self.seg_broll(["calendar_pages", "courtroom_empty"], back, p, "back")
        self.add("cold", p, mood="cold", sfx="tape_rewind")
        e0 = self.case_a + 2
        self.court_block(e0, min(self.case_b, e0 + 22), "EARLIER", "v03_flash.mp4")
        self.role_last("cold")
        qs = self.doc.get("questions") or ["How did it start?", "Where did it turn?", "Could it have ended differently?"]
        p = self.work / "v04_q.mp4"
        if not p.exists():
            self.seg_cards([(paper.paper_card("THREE QUESTIONS", "BY THE END YOU WILL KNOW", [_short(q, 60) for q in qs[:3]],
                                              self.png("q.png"), self.pal), 5.0)], p)
        self.add("story", p, mood="story", sfx="paper_rustle", chapter="Three questions")
        chs = self.chapters()
        for i, (a, b, t) in enumerate(chs):
            left = len(chs) - i
            p = self.work / f"v1{i:02d}_count.mp4"
            if not p.exists():
                lab = f"{left} DECISION{'S' if left > 1 else ''} EARLIER" if left > 1 else "THE DECISION"
                self.seg_blur(paper.big_text(lab, self.png(f"cd{i}.png"), self.pal, sub=t), "", p, f"cd{i}", t0=a, min_dur=2.6)
            self.add("bridge", p, mood="bridge", sfx="whoosh", chapter=_chap(t, f"Decision {i + 1}"))
            self.court_block(a, b, t, f"v2{i:02d}_court.mp4")
        ans = [a for a in self.doc.get("answers") or [] if isinstance(a, str) and a.strip()]
        if len(ans) >= min(3, len(qs)):
            lines = [f"{_short(q, 34)} — {_short(a, 40)}" for q, a in zip(qs, ans)]
        else:      # no answers from the brain: the facts that answer them (2026-11-24: the card repeated the questions)
            f = self.facts
            lines = [x for x in (f.get("charges") and f"WHY: {f['charges']}",
                                 f.get("state_asked") and f"THE STATE ASKED: {f['state_asked']}",
                                 f.get("defense_asked") and f"THE DEFENSE ASKED: {f['defense_asked']}",
                                 (f.get("sentence") or f.get("result")) and f"THE OUTCOME: {f.get('sentence') or f.get('result')}") if x][:3]
        self.ending(answers=lines)

    def recipe_emotional(self, video):
        q = self.doc.get("impact_quote") or {}
        line = q.get("text") or self.doc.get("tease") or video["hook"].get("headline", "")
        p = self.work / "e00_quote.mp4"
        if not p.exists():
            self.seg_cards([(paper.black_text(f"“{_short(line, 70)}”", self.png("q.png"), self.pal, sub=q.get("who", "")), 4.5)],
                           p, push=False)
        self.add("cold", p, mood="cold", sfx="heartbeat")
        a, b = self.hook
        self.court_block(a, min(b, a + 9), "", "e01_slow.mp4", speed=0.6, bw=True)
        self.role_last("cold")
        tag = self.doc.get("tagline") or "ONE CASE. TWO FAMILIES."
        p = self.work / "e02_black.mp4"
        if not p.exists():
            self.seg_cards([(paper.black_text(_short(tag, 40).upper(), self.png("tag.png"), self.pal), 3.2)], p, push=False)
        self.add("cold", p, mood="cold", sfx="boom")
        p = self.work / "e03_doc.mp4"
        if not p.exists():
            self.seg_cards(self.doc_steps("sum.png", 1.1, 3.0), p)
        self.add("story", p, mood="story", sfx="paper_rustle", chapter="The case file")
        self.backstory("e04", bw=True)
        self.hearings(numbered=False)
        self.ending(slow=True)

    def recipe_evidence_board(self, video):
        a, b, _ = self.moments(1)[0]
        self.court_block(a, b, "", "b00_open.mp4")
        self.role_last("cold")
        bd = self.doc.get("board") or {}
        items = [it for it in bd.get("items") or [] if it.get("id") and it.get("label")][:8]
        if not items:
            items = [{"id": "d", "label": _short(self.name, 18), "sub": "THE DEFENDANT"},
                     {"id": "c", "label": _short(self.facts.get("charges", "THE CHARGE"), 18), "sub": "THE CHARGE"},
                     {"id": "j", "label": "THE JUDGE", "sub": _short(self.facts.get("court", ""), 24)},
                     {"id": "r", "label": _short(self.facts.get("result", "?"), 18), "sub": "THE OUTCOME"}]
        links = bd.get("links") or [["d", "c", ""], ["c", "j", ""], ["j", "r", ""]]
        master = {casedoc.LABEL.get(k, k): v for k, v in self.facts.items() if k in ("charges", "bond", "result", "sentence")}
        steps = [(paper.board(items, links, self.png("bd0.png"), self.pal, reveal=0, master=None), 1.6),
                 (paper.board(items, links, self.png("bdm.png"), self.pal, reveal=0, master=master), 2.4)]
        p = self.work / "b01_board.mp4"
        if not p.exists():
            self.seg_cards(steps, p)
        self.add("cold", p, mood="cold", sfx="stamp_thud", chapter="The evidence board")
        intro = self.doc.get("tease") or f"Every piece of this case is on this board. Let's connect them."
        vo, vd = self.voice(intro + " " + (self.doc.get("backstory_text") or video.get("vo1", {}).get("text", "")), "board")
        chs = self.chapters()
        # the last items are kept back: each later chapter pins one of them (2026-11-24: every pin went up at once and the
        # "NEW EVIDENCE" card showed the same full board again)
        k_new = max(0, min(len(items) - 3, len(chs) - 1))
        n = len(items) - k_new
        per = max(1.6, (vd + 0.8) / max(1, n))
        steps = [(paper.board(items, links, self.png(f"bd{i}.png"), self.pal, reveal=i, master=master), per) for i in range(1, n + 1)]
        p = self.work / "b02_pins.mp4"
        if not p.exists():
            self.seg_cards(steps, p, vo=vo)
        self.add("story", p, mood="story", sfx="pop_click", chapter="Connecting the pieces")
        for i, (a, b, t) in enumerate(chs):
            if i:
                p = self.work / f"b1{i:02d}_pin.mp4"
                if not p.exists():
                    new = i <= k_new
                    self.seg_cards([(paper.board(items, links, self.png(f"bdn{i}a.png"), self.pal, master=master,
                                                 reveal=n + i - 1), 0.9),
                                    (paper.board(items, links, self.png(f"bdn{i}.png"), self.pal, master=master,
                                                 reveal=min(len(items), n + i),
                                                 stamp_text="NEW EVIDENCE" if new else _short(t, 22)), 2.6)], p)
                self.add("bridge", p, mood="bridge", sfx="stamp_thud", chapter=_chap(t, f"Part {i + 1}"))
            self.court_block(a, b, t, f"b2{i:02d}_court.mp4", chapter=None if i else _chap(t, "The hearing"))
        self.ending()

    def recipe_instant_replay(self, video):
        reps = []
        for r in self.doc.get("replays") or []:
            try:
                a, b = parse_tc(r["in"]), parse_tc(r["out"])
            except (KeyError, ValueError, TypeError):
                continue
            if self.case_a <= a < b <= self.case_b and 3 <= b - a <= 20:
                reps.append((a, b, r))
        if not reps:
            a, b = self.hook
            reps = [(a, min(b, a + 10), {"label": "WATCH THIS", "marks": [{"kind": "circle", "x": .5, "y": .42, "r": .14}]})]
        a, b, r0 = reps[0]
        self.court_block(a, b, "", "r00_live.mp4")
        self.role_last("cold")
        self.replay(a, b, r0, "r01")
        p = self.work / "r02_impact.mp4"
        if not p.exists():
            self.seg_cards(self.doc_steps("sum.png", 0.7, 2.6), p)
        self.add("story", p, mood="story", sfx="paper_rustle", chapter="The case file")
        self.backstory("r03")
        k = 0
        for i, (ca, cb, t) in enumerate(self.chapters()):
            self.court_block(ca, cb, t, f"r1{i:02d}_court.mp4", chapter=_chap(t, f"Part {i + 1}"))
            for ra, rb, r in reps[1:]:
                if ca <= ra < cb:
                    k += 1
                    self.replay(ra, rb, r, f"r2{k:02d}")
        self.ending()

    def replay(self, a, b, r, name):
        p = self.work / f"{name}_tag.mp4"
        if not p.exists():
            self.seg_blur(paper.big_text("REPLAY", self.png(f"{name}_t.png"), self.pal, colour=self.pal.get("accent", "#F5C518"),
                                         sub=_short(r.get("label", ""), 30)), "", p, f"{name}_t", t0=a, min_dur=1.6)
        self.add("bridge", p, mood="bridge", sfx="tape_rewind")
        tel = paper.telestrator(r.get("marks") or [], self.png(f"{name}_m.png"), self.pal, label=_short(r.get("label", ""), 24))
        dur = (b - a) / 0.5
        out = self.work / f"{name}_slow.mp4"
        if not out.exists():
            self.seg_court(a, b, out, date=self.date, tag="REPLAY ×0.5", speed=0.5, extra=[(tel, 0.6, dur)],
                           turns=self.doc.get("turns"))
        self.add("court", out, a=a, b=b)
        if r.get("analysis"):
            p = self.work / f"{name}_an.mp4"
            if not p.exists():
                self.seg_blur(tel, r["analysis"], p, f"{name}_an", t0=a, min_dur=3.0)
            self.add("bridge", p, mood="bridge")

    def recipe_docu_series(self, video):
        sdir = ROOT / self.cfg.get("state_dir", "state") / "series"
        sdir.mkdir(parents=True, exist_ok=True)
        key = re.sub(r"[^a-z0-9]+", "_", self.name.lower()).strip("_") or "case"
        sfile = sdir / f"{key}.json"
        try:
            hist = json.loads(sfile.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            hist = {"name": self.name, "episodes": []}
        sid = Path(self.srcname).stem
        prev = [e for e in hist["episodes"] if e.get("stream") != sid]
        ep = next((i + 1 for i, e in enumerate(hist["episodes"]) if e.get("stream") == sid), len(hist["episodes"]) + 1)
        self.ep_label = "EP {} · {}".format(ep, _short(self.doc.get("episode_title") or (self.chapters()[0][2] if self.chapters()
                                                                                       else "THE HEARING"), 24).upper())
        if prev:
            for i, e in enumerate(prev[-3:]):            # real footage of the earlier episodes (kept in state/series/)
                clip = sdir / key / e.get("clip", "")
                if e.get("clip") and clip.exists():
                    old = self.using(clip, e.get("segs", []), e.get("date", ""), clip.name)
                    try:
                        self.court_block(0.0, min(9.0, probe_dur(clip)), f"PREVIOUSLY · EPISODE {e['n']}", f"s00_prev{i}.mp4")
                    finally:
                        self.restore(old)
                    self.role_last("cold")
            txt = "Previously. " + " ".join(e.get("summary", "") for e in prev[-3:])
            pills = [(paper.pill_stack([f"EPISODE {e['n']} · {_short(e.get('title', ''), 26)}"], self.png(f"prev{i}.png"),
                                       self.pal, kinds=["r"])[0], 0.3 + i * 2.2, 99) for i, e in enumerate(prev[-3:])]
            p = self.work / "s00_prev.mp4"
            if not p.exists():
                self.seg_broll(["courtroom_empty", "documents_desk", "calendar_pages"], txt, p, "prev", pills=pills)
            self.add("cold", p, mood="cold", sfx="whoosh", chapter="Previously")
        a, b, _ = self.moments(1)[0]
        self.court_block(a, b, "", "s01_open.mp4")
        self.role_last("cold")
        title = _short(self.doc.get("episode_title") or (self.chapters()[0][2] if self.chapters() else "THE HEARING"), 24).upper()
        self.ep_label = f"EP {ep} · {title}"
        p = self.work / "s02_ep.mp4"
        if not p.exists():
            self.seg_cards([(paper.episode_card(ep, title, self.png("ep.png"), self.pal, sub=self.date), 3.0)]
                           + self.doc_steps("sum.png", 0.7, 2.4), p)
        self.add("story", p, mood="story", sfx="brass_hit", chapter=f"Episode {ep} · {title.title()}")
        if ep == 1:
            self.backstory("s03")
        self.hearings(numbered=False)
        nxt = self.doc.get("cliffhanger") or (f"NEXT HEARING: {self.facts['next_date']}" if self.facts.get("next_date") else "TO BE CONTINUED")
        self.ending(extra_card=paper.black_text(_short(nxt, 40).upper(), self.png("next.png"), self.pal, sub=f"EPISODE {ep + 1}"))
        summ = self.doc.get("episode_summary") or f"{self.name}: {self.facts.get('result', 'the hearing')} ({self.date})."
        # keep this episode's strongest moment (stream copy, ~10 s) for the next episode's "previously on"
        from . import dossier as DOS
        ha, hb, _ = self.moments(1)[0]
        hb = min(hb, ha + 10.0)
        clip_name = f"ep{ep:02d}.mp4"
        try:
            DOS.cut(self.srcp, ha, hb, sdir / key / clip_name)
            clip_segs = [dict(x, start=float(x["start"]) - ha, end=float(x.get("end", x["start"])) - ha) for x in self.segs
                         if ha <= float(x["start"]) < hb]
        except RuntimeError as e:
            self.notes_once(f"episode clip for the next 'previously on' not kept: {e}")
            clip_name, clip_segs = "", []
        hist["episodes"] = [e for e in hist["episodes"] if e.get("stream") != sid] + [
            {"n": ep, "stream": sid, "title": title, "summary": _short(summ, 220), "date": self.date,
             "clip": clip_name, "segs": clip_segs}]
        hist["episodes"].sort(key=lambda e: e["n"])
        sfile.write_text(json.dumps(hist, indent=1, ensure_ascii=False), encoding="utf-8")

    # ---------------------------------------------------------------- shared recipe pieces
    def role_last(self, role):
        r, p, m, s, meta = self.pieces[-1]
        self.pieces[-1] = (role, p, m, s, meta)

    def backstory(self, name, bw=False):
        beats = [x for x in (self.doc.get("backstory") or []) if x.get("text")][:6]
        if not beats and self.video.get("vo1", {}).get("text"):
            beats = [{"text": self.video["vo1"]["text"], "tags": DEFAULT_BROLL[:3]}]
        for i, bt in enumerate(beats):
            tags = [t for t in (bt.get("tags") or [bt.get("tag")]) if t] or DEFAULT_BROLL[:3]
            pills = []
            pl = [_short(x, 40) for x in (bt.get("pills") or [])][:3]
            if pl:
                steps = paper.pill_stack(pl, self.png(f"{name}_{i}.png"), self.pal)
                pills = [(s, 0.6 + j * 1.6, 99) for j, s in enumerate(steps)]
            p = self.work / f"{name}_{i}.mp4"
            if not p.exists():
                self.seg_broll(tags, bt["text"], p, f"{name}_{i}", pills=pills, bw=bw)
            self.add("story", p, mood="story", sfx="whoosh" if i == 0 else None, **({"chapter": "The backstory"} if i == 0 else {}))

    def penalty(self, name):
        lvl = (self.doc.get("charge_level") or "").strip()
        png = paper.penalty_card(_short(self.facts.get("charges", ""), 48), lvl, self.png("pen.png"), self.pal)
        if png:
            p = self.work / f"{name}_pen.mp4"
            if not p.exists():
                self.seg_cards([(png, 4.0)], p)
            self.add("story", p, mood="story", sfx="stamp_thud", chapter="What the law allows")

    def earlier(self):
        """Earlier hearings of this defendant from the dossier (tools/dossier.py), oldest first."""
        if not self.cfg.get("_dossier"):
            return []
        from . import dossier as DOS
        return DOS.earlier(self.cfg["_dossier"], self.cfg.get("_upload", ""), ROOT / self.cfg.get("state_dir", "state"))

    def using(self, path, segs, date, name):
        """Switch the footage / transcript / date used by court_block + seg_blur (an earlier hearing's clip)."""
        old = (self.srcp, self.segs, self.date, self.srcname, self.case_a, self.case_b, self._earlier)
        self.srcp, self.segs, self.date, self.srcname, self.case_a = str(path), segs, date, name, 0.0
        self.case_b, self._earlier = probe_dur(path), True
        return old

    def restore(self, old):
        self.srcp, self.segs, self.date, self.srcname, self.case_a, self.case_b, self._earlier = old

    def earlier_hearings(self, start_n=1, numbered=True):
        """Every earlier hearing as a dated chapter: chapter card (+ the brain's bridge line) and the court block.
        -> number of hearings added."""
        hs = self.earlier()
        bridges = self.doc.get("earlier_bridges") or []
        for i, h in enumerate(hs):
            d = probe_dur(h["path"])
            old = self.using(h["path"], h.get("segs", []), h.get("date", ""), Path(h["path"]).name)
            try:
                kick = f"HEARING {start_n + i}" if numbered else f"EARLIER · {start_n + i}"
                p = self.work / f"g{i:02d}_ch.mp4"
                if not p.exists():
                    self.seg_blur(paper.chapter_card(kick, h.get("date") or " ", "EARLIER HEARING", self.png(f"gch{i}.png"), self.pal,
                                                     variant=self.card_variant),
                                  bridges[i] if i < len(bridges) else "", p, f"gch{i}", t0=min(5, d / 3), min_dur=3.0)
                self.add("bridge", p, mood="bridge", sfx="riser",
                         chapter=f"{kick.title()} · {h.get('date') or 'earlier hearing'}".strip())
                self.court_block(0.0, d, "EARLIER HEARING", f"g{i:02d}_court.mp4")
            finally:
                self.restore(old)
            if True:                                   # a time jump after every earlier hearing
                jump = paper.big_text("TIME PASSES", self.png(f"tj{i}.png"), self.pal,
                                      sub=f"{h.get('date', '')} → {(hs[i + 1].get('date') if i + 1 < len(hs) else self.date) or ''}")
                p = self.work / f"g{i:02d}_jump.mp4"
                if not p.exists():
                    self.seg_blur(jump, "", p, f"tj{i}", t0=self.case_a + 2, min_dur=2.4)
                self.add("bridge", p, mood="bridge", sfx="bass_drop")
        return len(hs)

    def hearings(self, numbered=True):
        n0 = self.earlier_hearings(1, numbered)
        chs = self.chapters()
        for i, (a, b, t) in enumerate(chs):
            # one hearing's chapters are parts of THAT hearing (2026-11-24: they read "HEARING 2, 3, 4" on one date)
            if numbered and n0:
                kick = f"HEARING {n0 + 1}" + (f" · PART {i + 1}" if len(chs) > 1 else "")
            else:
                kick = f"CHAPTER {i + 1}" if numbered else f"PART {i + 1}"
            p = self.work / f"h{i:02d}_ch.mp4"
            if not p.exists():
                self.seg_blur(paper.chapter_card(kick, self.date or " ", t, self.png(f"ch{i}.png"), self.pal, variant=self.card_variant),
                              (self.doc.get("bridges") or [""] * 99)[i] if i < len(self.doc.get("bridges") or []) else "",
                              p, f"ch{i}", t0=a, min_dur=3.0)
            self.add("bridge", p, mood="bridge", sfx="riser", chapter=f"{kick.title()} · {_chap(t, 'The hearing')}")
            self.court_block(a, b, t, f"h{i:02d}_court.mp4")

    def ending(self, answers=None, slow=False, extra_card=None):
        txt = self.video.get("vo_final", {}).get("text", "")
        steps = self.doc_steps("end.png", 0.5, 2.0)
        k = len(steps) - 1                         # the finished document
        if answers:
            steps.append((paper.paper_card("THE ANSWERS", "", [_short(a, 78) for a in answers[:3]], self.png("ans.png"), self.pal), 4.5))
        if extra_card:
            steps.append((extra_card, 3.0))
        vo, vd = self.voice(txt, "final")
        if vo and vd + 1.0 > sum(d for _, d in steps):
            # the rows keep their quick reveal; the finished document (last step of it) holds while the line is read
            # (2026-11-24: stretched evenly, the sentence row appeared only in the last seconds)
            extra = vd + 1.0 - sum(d for _, d in steps)
            steps[k] = (steps[k][0], steps[k][1] + extra)
        p = self.work / "z99_end.mp4"
        if not p.exists():
            self.seg_cards(steps, p, vo=vo, push=not slow)
        self.add("end", p, mood="end", sfx="paper_rustle", chapter="The outcome")

    # ================================================================== one video
    def render_video(self, plan, video, outdir, tts_cache, ui=print):
        outdir = Path(outdir)
        self.work = outdir / "_work"
        (self.work / "gfx").mkdir(parents=True, exist_ok=True)
        self.tts_cache, self.ui, self.video = Path(tts_cache), ui, video
        self.pieces, self.used_broll, self.beat_report = [], set(), []
        self._earlier = False
        self._ctx(plan, video)
        ui(f"  style: {self.style}  |  B-roll: {stock.broll_available(self.cfg)}"
           + ("" if self.libass else "  |  captions OFF (this ffmpeg has no libass)"))
        getattr(self, f"recipe_{self.style}", self.recipe_case_file)(video)
        if self.beat_report:
            (outdir / "retention_report.txt").write_text("\n".join(self.beat_report) + "\n", encoding="utf-8")
        # ----- timeline from the real files
        rows, t = [], 0.0
        court, music, sfx = [], [], []
        for role, path, mood, fx, meta in self.pieces:
            d = probe_dur(path)
            rows.append({"kind": role, "start": t, "dur": d, "case_id": self.case["id"], "src": self.srcname, **meta})
            if role == "court":
                court.append((t, t + d))
            else:
                mm = mood or role
                mm = self.moods.get(mm, mm) if mm in self.moods else (mm if mm in audiomix.MUSIC_MOODS else self.moods["story"])
                if music and music[-1].mood == mm and abs(music[-1].end - t) < 0.05:
                    music[-1].end = t + d
                else:
                    music.append(audiomix.MusicCue(t, t + d, mm))
            if fx:
                name, off = fx if isinstance(fx, tuple) else (fx, 0.05)
                sfx.append(audiomix.SfxCue(t + off, name))
            t += d
        total = t
        lst = self.work / "concat.txt"
        lst.write_text("".join(f"file '{p.resolve()}'\n" for _, p, *_ in self.pieces), encoding="utf-8")
        raw = self.work / "raw.mp4"
        run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", raw])
        lib = self.cfg.get("media_library") or ""
        mixed = raw
        if lib:
            mixed = self.work / "mixed.mp4"
            rep = audiomix.mix_onto(raw, mixed, audiomix.MixPlan(total, court, music, sfx), lib,
                                    self.cfg.get("mix") or {}, ui=lambda *m: None)
            missing = sorted({r.split("'")[1] for r in rep if "missing" in r})
            if missing:
                self.notes_once("music/SFX folders empty: " + ", ".join(missing))
        else:
            self.notes_once("no media library set - no music / SFX (Studio > Settings)")
        l2 = self.work / "final_list.txt"
        l2.write_text(f"file '{Path(mixed).resolve()}'\n", encoding="utf-8")
        final = outdir / "video.mp4"
        join_segments(l2, final, self.cfg)
        # timeline in the shape sheets.py knows (chapters / edit sheet)
        segs = []
        kind_map = {"cold": "hook", "story": "vo1", "court": "case", "bridge": "bridge_intro", "end": "vo_final"}
        for r in rows:
            k = kind_map.get(r["kind"], "vo1")
            if segs and segs[-1]["kind"] == k and k != "case":
                segs[-1]["dur"] += r["dur"]
                continue
            seg = {"kind": k, "start": r["start"], "dur": r["dur"], "case_id": self.case["id"]}
            if k == "case":
                seg["parts"] = [(r["a"], r["b"])]
            segs.append(seg)
        if not segs or segs[0]["kind"] != "hook":
            segs.insert(0, {"kind": "hook", "start": 0.0, "dur": 0.0})
        segs.insert(1, {"kind": "intro", "start": segs[0]["start"] + segs[0]["dur"], "dur": 0.0})
        tl = {"segments": segs, "total": total, "seams": []}
        for r in rows:
            s = self.sources.get(r.get("src")) or {}
            url = s.get("url", "")
            self.log.append({"video": video["n"], "segment": r["kind"], "case_id": r.get("case_id", ""),
                             "source_file": r.get("src", ""),
                             "source_url": (url + ("&" if "?" in url else "?") + f"t={int(r['a'])}s") if url and "a" in r else "",
                             "src_in": fmt_tc(r["a"]) if "a" in r else "", "src_out": fmt_tc(r["b"]) if "b" in r else "",
                             "out_start": fmt_tc(r["start"]), "out_dur": f"{r['dur']:.1f}"})
        (outdir / "case_document.json").write_text(json.dumps(self.facts, indent=1, ensure_ascii=False), encoding="utf-8")
        durs = {"hook": sum(r["dur"] for r in rows if r["kind"] == "cold"), "intro": 0.0, "vo1": 0.0, "bridge": [],
                "final": rows[-1]["dur"] if rows else 0.0}
        measured = probe_dur(final)
        return {"final": final, "timeline": tl, "rows": rows, "durs": durs, "measured_total": measured, "work": self.work,
                "chapters": youtube_chapters(rows, measured)}
