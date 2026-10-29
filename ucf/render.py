"""ffmpeg renderer: one video = hook + channel intro + [VO card + case + bridge cards]... + final card.
All segments are normalised to 1920x1080 / 30 fps / H.264 / AAC 48k stereo, then joined with the concat demuxer."""
import csv
import json
import re
import shutil
import subprocess
from pathlib import Path

from . import cards
from . import timeline as TL
from . import tts
from . import vo as V
from .timeutil import parse_tc, fmt_tc, fmt_dur

NORM = ("scale=1920:1080:force_original_aspect_ratio=decrease,"
        "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps=30,format=yuv420p")
AUDIO_NORM = "aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo"
# Court (Zoom) speech clean-up, measured on 03p3ATnv6dY (3 x 60 s): the gap between loud and quiet speakers
# (p90-p50 of 100 ms levels) drops from 7-11 dB to 4.5-6.7 dB, the noise floor stays equal or drops 8-11 dB.
# rumble/hiss band-limit -> even out judge vs defendant -> spectral denoise -> soft gate between sentences.
COURT_CLEANUP = ("highpass=f=90,lowpass=f=7500,"
                 "acompressor=threshold=-24dB:ratio=3:attack=10:release=250:makeup=2,"
                 "afftdn=nr=12:nf=-45:tn=1,"
                 "agate=threshold=0.003:ratio=2:range=0.25:attack=5:release=300")


def court_audio(cfg):
    """-af chain for court footage: clean-up (config "audio_cleanup", default on) + the shared format."""
    return (COURT_CLEANUP + "," + AUDIO_NORM) if (cfg or {}).get("audio_cleanup", True) else AUDIO_NORM


def run(cmd, quiet=True):
    r = subprocess.run([str(c) for c in cmd], capture_output=quiet, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg failed:\n" + " ".join(str(c) for c in cmd)[:600] + "\n" + (r.stderr or "")[-1800:])
    return r


def _hms(sec):
    sec = int(max(0, sec))
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def run_progress(cmd, total, label="    rendering", every=20.0, ui=None):
    """Like run(), but prints progress while ffmpeg works (percent, position, speed, ETA) so a long render (a 1-hour case can take
    an hour or more) is never mistaken for a hang. `total` = seconds of OUTPUT video this command produces."""
    import threading
    import time
    cmd = [str(c) for c in cmd]
    say = ui or (lambda m: print(m, flush=True))
    p = subprocess.Popen(cmd[:1] + ["-progress", "pipe:1", "-nostats"] + cmd[1:], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    err = []
    t = threading.Thread(target=lambda: err.extend(p.stderr.readlines()), daemon=True)
    t.start()
    start = last = time.time()
    pos, speed = 0.0, ""
    for line in p.stdout:
        k, _, v = line.strip().partition("=")
        if k == "out_time_us":
            try:
                pos = int(v) / 1e6
            except ValueError:
                pass
        elif k == "speed":
            speed = v.strip()
        if k == "progress" and time.time() - last >= every:
            last = time.time()
            done = min(1.0, pos / total) if total else 0
            eta = (time.time() - start) * (1 - done) / done if done > 0.01 else 0
            say(f"{label}: {int(done * 100):3d}%  {_hms(pos)} of {_hms(total)}  speed {speed or '?'}" + (f"  ~{_hms(eta)} left" if eta else ""))
    p.wait()
    t.join(timeout=5)
    if p.returncode != 0:
        raise RuntimeError("ffmpeg failed:\n" + " ".join(cmd)[:600] + "\n" + "".join(err)[-1800:])
    say(f"{label}: done in {_hms(time.time() - start)}")


def probe_dur(p):
    return tts.dur(p)


_X264 = {"preset": "medium", "crf": "16"}


def pick_encoder(cfg):
    _X264["preset"] = str(cfg.get("x264_preset") or "medium")       # CPU-only PCs: "fast" / "veryfast" render much quicker
    _X264["crf"] = str(cfg.get("x264_crf") or 16)
    want = cfg.get("encoder", "auto")
    enc = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
    if want != "auto":
        return want
    for e in ("h264_videotoolbox", "h264_nvenc"):
        if e in enc:
            # make sure it actually works on this machine - with the SAME quality options the renders use, so a driver that
            # rejects one of them falls back to x264 now instead of failing in the middle of a video
            t = subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=black:s=1280x720:d=0.5:r=30",
                                *venc(e), "-f", "null", "-"], capture_output=True)
            if t.returncode == 0:
                return e
    return "libx264"


def venc(enc):
    """Quality-first video encoding (the footage is already a soft 720p Zoom stream: never lose more of it than we must).
    x264 crf 16 / NVENC cq 16 (hq tune, adaptive quantisation) are constant-quality: size follows the content, so mostly
    static court footage stays small. VideoToolbox has no constant-quality mode here, so it gets a generous bitrate."""
    if enc == "h264_videotoolbox":
        return ["-c:v", enc, "-b:v", "14M", "-maxrate", "20M", "-profile:v", "high", "-pix_fmt", "yuv420p", "-g", "60"]
    if enc == "h264_nvenc":
        return ["-c:v", enc, "-preset", "p6", "-tune", "hq", "-rc", "vbr", "-cq", "16", "-b:v", "0", "-spatial-aq", "1",
                "-temporal-aq", "1", "-profile:v", "high", "-pix_fmt", "yuv420p", "-g", "60"]
    return ["-c:v", "libx264", "-preset", _X264["preset"], "-crf", _X264["crf"], "-profile:v", "high", "-pix_fmt", "yuv420p", "-g", "60"]


AENC = ["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]
TS = ["-video_track_timescale", "30000", "-movflags", "+faststart"]


class Renderer:
    def __init__(self, cfg, sources, root):
        self.cfg = cfg
        self.sources = sources            # {source_file: {"path":..., "url":...}}
        self.root = Path(root)
        self.enc = pick_encoder(cfg)
        self.log = []                     # footage log rows
        self.logo = None                  # (png, x, y) corner watermark
        self.tag_png = None
        lf = Path(cfg.get("logo_file", "")).expanduser() if cfg.get("logo_file") else None
        if lf and not lf.is_absolute():
            lf = self.root / lf
        self.logo_src = lf if lf and lf.exists() else None
        if self.logo_src:
            wd = self.root / cfg["work_dir"]
            wd.mkdir(parents=True, exist_ok=True)
            png = wd / "_logo_badge.png"
            cards.logo_badge(self.logo_src, int(cfg.get("logo_size", 132)), png, float(cfg.get("logo_opacity", 0.92)))
            mx, my = 48, 40
            corner = cfg.get("logo_corner", "top-left")
            x = f"{mx}" if "left" in corner else f"W-w-{mx}"
            y = f"{my}" if "top" in corner else f"H-h-{my}"
            self.logo = (png, x, y)
        if cfg.get("coming_up_tag", True):
            self.tag_png = self.root / cfg["work_dir"] / "_coming_up.png"
            self.tag_png.parent.mkdir(parents=True, exist_ok=True)
            cards.coming_up_tag(self.tag_png)

    # ---------- primitives ----------
    def src(self, name):
        s = self.sources.get(name)
        if not s or not Path(s["path"]).exists():
            raise RuntimeError(f"source video for {name!r} not found - register it in state/sources.json")
        return s

    def cut(self, srcpath, a, b, out, logo=True, tag=False):
        """Frame-accurate cut, normalised, with the corner logo (and optional COMING UP tag) burnt in."""
        d = b - a
        if d <= 0.05:
            raise RuntimeError(f"empty cut {a}-{b}")
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{a:.3f}", "-t", f"{d:.3f}", "-i", srcpath]
        chain = f"[0:v]{NORM}[v0]"
        last, idx = "v0", 1
        if logo and self.logo:
            cmd += ["-i", self.logo[0]]
            chain += f";[{last}][{idx}:v]overlay={self.logo[1]}:{self.logo[2]}:format=auto[v{idx}]"
            last, idx = f"v{idx}", idx + 1
        if tag and self.tag_png:
            cmd += ["-i", self.tag_png]
            chain += f";[{last}][{idx}:v]overlay=0:0:format=auto[v{idx}]"
            last, idx = f"v{idx}", idx + 1
        chain += f";[{last}]format=yuv420p[vout]"
        cmd += ["-filter_complex", chain, "-map", "[vout]", "-map", "0:a:0?", "-af", AUDIO_NORM,
                *venc(self.enc), *AENC, *TS, out]
        run(cmd)
        return out

    def blur_card(self, srcpath, blur_in, dur, card_png, vo_wav, lead, out):
        """Blurred+darkened footage keeps playing; card PNG on top; VO under it. Duration = dur exactly."""
        lead_ms = int(lead * 1000)
        logo_in, logo_f = [], ""
        if self.logo:
            logo_in = ["-i", self.logo[0]]
            logo_f = f"[vc][3:v]overlay={self.logo[1]}:{self.logo[2]}:format=auto[vl];[vl]"
        else:
            logo_f = "[vc]"
        fc = (f"[0:v]{NORM},scale=480:270,boxblur=6:3,scale=1920:1080,lutyuv=y='val*0.5'[bg];"
              f"[1:v]format=rgba[fg];[bg][fg]overlay=0:0:shortest=1[vc];"
              f"{logo_f}format=yuv420p[v];"
              f"[2:a]adelay={lead_ms}|{lead_ms},apad,{AUDIO_NORM}[a]")
        run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{blur_in:.3f}", "-t", f"{dur:.3f}", "-i", srcpath,
             "-loop", "1", "-framerate", "30", "-t", f"{dur:.3f}", "-i", card_png, "-i", vo_wav, *logo_in,
             "-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-t", f"{dur:.3f}",
             *venc(self.enc), *AENC, *TS, out])
        return out

    def channel_intro(self, seconds, out, workdir):
        f = Path(self.cfg["channel_intro_file"]).expanduser()
        if not f.is_absolute():
            f = Path(__file__).resolve().parent.parent / f
        seconds = max(5.0, min(8.0, float(seconds)))
        if f.exists():
            has_a = "audio" in subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
                                               "-of", "csv=p=0", str(f)], capture_output=True, text=True).stdout
            d = min(probe_dur(f), 8.0)
            cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", f]
            n_in = 1
            if not has_a:
                cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
                n_in += 1
            chain = f"[0:v]{NORM}[v0]"
            lastv = "v0"
            if self.cfg.get("logo_on_intro", True) and self.logo:
                cmd += ["-i", self.logo[0]]
                chain += f";[v0][{n_in}:v]overlay={self.logo[1]}:{self.logo[2]}:format=auto[v1]"
                lastv = "v1"
            chain += f";[{lastv}]format=yuv420p[vout]"
            cmd += ["-t", f"{d:.3f}", "-filter_complex", chain, "-map", "[vout]",
                    "-map", "0:a:0" if has_a else "1:a:0", "-af", AUDIO_NORM, *venc(self.enc), *AENC, *TS, out]
            run(cmd)
            return out
        png = Path(workdir) / "intro_title.png"
        cards.title_card(self.cfg["channel_name"], png, logo_path=self.logo_src if self.cfg.get("logo_on_intro", True) else None)
        run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", "30", "-t", f"{seconds}", "-i", png,
             "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", f"{seconds}",
             "-vf", f"fade=t=in:st=0:d=0.5,fade=t=out:st={seconds - 0.6}:d=0.6,format=yuv420p",
             "-map", "0:v", "-map", "1:a", *venc(self.enc), *AENC, *TS, out])
        return out

    # ---------- one video ----------
    def render_video(self, plan, video, outdir, tts_cache, ui=print):
        by_id = {c["id"]: c for c in plan["cases"]}
        outdir = Path(outdir)
        work = outdir / "_work"
        work.mkdir(parents=True, exist_ok=True)
        cfg = self.cfg
        ids = video["case_ids"]
        total_cases = len(ids)
        default_src = plan["source_file"]

        def srcname(c):
            return c.get("source_file") or default_src

        # ----- voiceovers -----
        ui("  voiceover...")
        vo_files = {}
        vo_files["vo1"] = tts.synth(video["vo1"]["text"], tts_cache, cfg)
        bridges = {b["after_case_id"]: b for b in video.get("bridges", [])}
        br_files = []
        for i in range(total_cases - 1):
            b = bridges[ids[i]]
            A, B = V.split_bridge(b["text"], b.get("split_after_sentence"))
            br_files.append((tts.synth(A, tts_cache, cfg), tts.synth(B, tts_cache, cfg) if B else None))
        vo_files["final"] = tts.synth(video["vo_final"]["text"], tts_cache, cfg)

        lead, tail = cfg["vo_lead"], cfg["vo_tail"]
        durs = {"vo1": probe_dur(vo_files["vo1"]) + lead + tail,
                "bridge": [(probe_dur(a) + lead, (probe_dur(b) + tail) if b else 0.0) for a, b in br_files]}
        fin_d = probe_dur(vo_files["final"]) + lead + tail
        durs["final"] = min(max(fin_d, cfg["final_min_hold"]), max(cfg["final_max_hold"], fin_d))
        hk = video["hook"]
        hook_in, hook_out = parse_tc(hk["in"]), parse_tc(hk["out"])
        durs["hook"] = hook_out - hook_in
        tcfg = {"cut_pad_out": cfg["cut_pad_out"], "final_min_hold": cfg["final_min_hold"],
                "final_max_hold": cfg["final_max_hold"], "vo_lead": lead, "vo_tail": tail}
        # ----- cards (PNG) -----
        ui("  cards...")
        cp = {}
        for pos, cid in enumerate(ids, 1):
            c = by_id[cid]
            cp[("intro", cid)] = cards.intro_card(c, pos, total_cases, work / f"intro_{cid}.png")
            cp[("result", cid)] = cards.result_card(c, pos, work / f"result_{cid}.png")
        cp[("final", ids[-1])] = cards.with_quiz(cp[("result", ids[-1])], video["quiz"], work / "final_quiz.png")

        segfiles = []   # (kind, path, meta)

        def seg(kind, path, **meta):
            segfiles.append((kind, Path(path), meta))

        # ----- hook -----
        lead_case = by_id[ids[0]]
        s0 = self.src(srcname(lead_case))
        p = work / "00_hook.mp4"
        if not p.exists():
            self.cut(s0["path"], hook_in, hook_out, p, tag=True)
        seg("hook", p, src=srcname(lead_case), a=hook_in, b=hook_out)
        # ----- intro -----
        p = work / "01_intro.mp4"
        if not p.exists():
            self.channel_intro(video.get("intro_seconds", 6), p, work)
        seg("intro", p)
        durs["intro"] = probe_dur(p)
        durs["hook"] = probe_dur(work / "00_hook.mp4")

        # ----- vo1 over intro card of case 1 -----
        c1 = by_id[ids[0]]
        p = work / "02_vo1.mp4"
        pa = parse_tc(c1["in"])
        if not p.exists():
            self.blur_card(s0["path"], pa, durs["vo1"], cp[("intro", ids[0])], vo_files["vo1"], lead, p)
        seg("vo1", p, case_id=ids[0], src=srcname(c1), a=pa, b=pa + durs["vo1"])

        k = 3
        for i, cid in enumerate(ids):
            c = by_id[cid]
            sname = srcname(c)
            sp = self.src(sname)["path"]
            for j, (a, b) in enumerate(TL.case_parts(c, cfg["cut_pad_out"])):
                a2 = max(0.0, a - (cfg["cut_pad_in"] if j == 0 else 0))
                p = work / f"{k:02d}_case{cid}_{j}.mp4"
                if not p.exists():
                    ui(f"  case {cid} part {j + 1}: {fmt_dur(b - a2)}")
                    self.cut(sp, a2, b, p)
                seg("case", p, case_id=cid, src=sname, a=a2, b=b)
                k += 1
            if i < total_cases - 1:
                nxt = by_id[ids[i + 1]]
                da, db = durs["bridge"][i]
                fa, fb = br_files[i]
                # result card of the case just finished, blur from its last seconds
                p = work / f"{k:02d}_bridge{i + 1}a.mp4"
                bin_ = max(parse_tc(c["in"]), parse_tc(c["out"]) - da - 2.0)
                if not p.exists():
                    self.blur_card(sp, bin_, da, cp[("result", cid)], fa, lead, p)
                seg("bridge_result", p, case_id=cid, src=sname, a=bin_, b=bin_ + da)
                k += 1
                if fb is not None:
                    p = work / f"{k:02d}_bridge{i + 1}b.mp4"
                    nsp = self.src(srcname(nxt))["path"]
                    nin = parse_tc(nxt["in"])
                    if not p.exists():
                        self.blur_card(nsp, nin, db, cp[("intro", nxt["id"])], fb, 0.0, p)
                    seg("bridge_intro", p, case_id=nxt["id"], src=srcname(nxt), a=nin, b=nin + db)
                    k += 1
        # ----- final -----
        last = by_id[ids[-1]]
        lsp = self.src(srcname(last))["path"]
        p = work / f"{k:02d}_final.mp4"
        fbin = max(parse_tc(last["in"]), parse_tc(last["out"]) - durs["final"] - 2.0)
        if not p.exists():
            self.blur_card(lsp, fbin, durs["final"], cp[("final", ids[-1])], vo_files["final"], lead, p)
        seg("vo_final", p, case_id=ids[-1], src=srcname(last), a=fbin, b=fbin + durs["final"])

        # ----- real timeline from the actual files -----
        t = 0.0
        rows = []
        for kind, path, meta in segfiles:
            d = probe_dur(path)
            rows.append({"kind": kind, "start": t, "dur": d, **meta})
            t += d
        total = t

        # ----- concat + loudness -----
        ui("  joining + loudness...")
        lst = work / "concat.txt"
        lst.write_text("".join(f"file '{p.resolve()}'\n" for _, p, _ in segfiles), encoding="utf-8")
        final = outdir / "video.mp4"
        run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c:v", "copy",
             "-af", f"loudnorm=I={cfg['loudness_lufs']}:TP=-1.5:LRA=11", *AENC, "-movflags", "+faststart", final])

        # real-duration timeline for chapters / mid-rolls
        real_durs = {"hook": durs["hook"], "intro": durs["intro"], "vo1": durs["vo1"],
                     "bridge": durs["bridge"], "final": durs["final"]}
        tl = TL.build(video, by_id, tcfg, real_durs)
        # prefer measured numbers
        meas_total = probe_dur(final)

        # ----- footage log -----
        for r in rows:
            s = self.sources.get(r.get("src", default_src)) or {}
            url = s.get("url", "")
            self.log.append({"video": video["n"], "segment": r["kind"], "case_id": r.get("case_id", ""),
                             "source_file": r.get("src", ""), "source_url": (url + ("&" if "?" in url else "?") + f"t={int(r['a'])}s") if url and "a" in r else url,
                             "src_in": fmt_tc(r["a"]) if "a" in r else "", "src_out": fmt_tc(r["b"]) if "b" in r else "",
                             "out_start": fmt_tc(r["start"]), "out_dur": f"{r['dur']:.1f}"})
        return {"final": final, "timeline": tl, "rows": rows, "durs": durs, "measured_total": meas_total,
                "work": work}

    # ---------- extras ----------
    def thumbnail(self, plan, video, outdir):
        by_id = {c["id"]: c for c in plan["cases"]}
        th = video["thumbnail"]
        wa, wb = parse_tc(th["window_in"]), parse_tc(th["window_out"])
        cid = TL.find_case_for_tc(video, by_id, (wa + wb) / 2) or video["case_ids"][0]
        sname = by_id[cid].get("source_file") or plan["source_file"]
        sp = self.src(sname)["path"]
        cdir = Path(outdir) / "thumbnail_candidates"
        cdir.mkdir(parents=True, exist_ok=True)
        cands = []
        n = 6
        for i in range(n):
            t = wa + (wb - wa) * i / max(1, n - 1)
            p = cdir / f"cand_{i + 1}_{fmt_tc(t).replace(':', '-')}.jpg"
            run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", sp, "-frames:v", "1",
                 "-vf", "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720", "-q:v", "2", p])
            cands.append((cards.sharpness(p), p))
        best = max(cands)[1]
        out = Path(outdir) / "thumbnail.jpg"
        cards.thumbnail(best, th["text"], th["gold_word"], th["placement"], out)
        # also text-only versions on every candidate so the editor can pick the best expression
        for _, p in cands:
            cards.thumbnail(p, th["text"], th["gold_word"], th["placement"], p.with_name(p.stem + "_text.jpg"))
        return out

    def contact_sheet(self, final, rows, out):
        frames, labels = [], []
        fdir = Path(out).parent / "_work" / "frames"
        fdir.mkdir(parents=True, exist_ok=True)
        for i, r in enumerate(rows):
            tm = r["start"] + min(r["dur"] * 0.4, 20.0)
            p = fdir / f"f{i:02d}.jpg"
            run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{tm:.2f}", "-i", final, "-frames:v", "1",
                 "-vf", "scale=480:270", "-q:v", "4", p])
            frames.append(p)
            labels.append(f"{fmt_tc(r['start'], False)} {r['kind']}" + (f" #{r['case_id']}" if r.get("case_id") else ""))
        cards.contact_sheet(frames, labels, out)
        return out

    def qc(self, final, expected_total):
        r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(final), "-af", "ebur128=peak=true",
                            "-f", "null", "-"], capture_output=True, text=True)
        m = re.findall(r"\bI:\s+(-?\d+\.\d+) LUFS", r.stderr)
        tp = re.findall(r"Peak:\s+(-?\d+\.\d+) dBFS", r.stderr)
        d = probe_dur(final)
        return {"duration": round(d, 2), "expected": round(expected_total, 2),
                "loudness_lufs": float(m[-1]) if m else None, "true_peak_dbfs": float(tp[-1]) if tp else None,
                "ok": abs(d - expected_total) < 2.5 and bool(m) and abs(float(m[-1]) + 14) < 2.0}

    def write_footage_log(self, path):
        if not self.log:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(self.log[0].keys()))
            w.writeheader()
            w.writerows(self.log)
