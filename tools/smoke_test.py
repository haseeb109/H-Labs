"""H Labs smoke test: does THIS PC still make videos? 2-3 minutes, run after every update and from menu 6.

    python tools/smoke_test.py             all checks
    python tools/smoke_test.py --offline   no network (download / key hosts are skipped)
    python tools/smoke_test.py --json P    write the result to P (default state\\smoke_last.json)
    python tools/smoke_test.py --ytdlp-probe   only: does the installed yt-dlp read a video? (used by Setup; exit 0 = yes)

Why: every Windows-only failure so far (Smart App Control blocking DLLs, whisper 0xC0000005, NVENC driver too old, 360p
downloads, ai33 unreachable) was found by a 2-hour production run. Each check prints [ok] / [FAIL] with a plain remedy.
Exit code = number of FAILs. The JSON result is read by the update (a build that failed its smoke test is never recorded
as "last good") and shown in the Studio.
"""
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import ucf  # noqa: E402,F401 - ffmpeg / yt-dlp never read the console (ucf/__init__.py)
os.chdir(ROOT)
os.environ.setdefault("PYTHONUTF8", "1")
WIN = os.name == "nt"
OFFLINE = "--offline" in sys.argv
KEYS = Path.home() / ".config" / "umf"
KEY_FILES = {"hive.env": "HIVE_API_KEY", "ai33.env": "AI33_API_KEY"}
HOSTS = {"ai33 (AI voice)": "https://api.ai33.pro", "Hive (brain)": "https://api-cdn.thehive.ai"}
PROBE_URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"            # the first YouTube video: tiny, never goes away
SMOKE_URL = "https://www.youtube.com/watch?v=aqz-KE-bpKQ"            # Big Buck Bunny (Blender, 4K): a public 720p+ video
SETUP = "Setup.bat" if WIN else "the setup"
RESULTS = []


class Skip(Exception):
    pass


def _timed(fn, seconds, what):
    """Run fn in a thread with a time budget (a hung yt-dlp / whisper must not hang the whole test)."""
    box = {}

    def run():
        try:
            box["v"] = fn()
        except BaseException as e:      # noqa: BLE001 - reported by the check
            box["e"] = e
    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(seconds)
    if t.is_alive():
        raise TimeoutError(f"{what} did not finish in {seconds} s")
    if "e" in box:
        raise box["e"]
    return box.get("v")


def _err(e):
    """'ImportError: DLL load failed ...' - the Windows error class matters: it tells SAC / C++ runtime / missing apart."""
    s = f"{type(e).__name__}: {e}"
    if getattr(e, "winerror", None):
        s += f" (winerror {e.winerror})"
    return s.replace("\n", " ")[:300]


def _import_remedy(msg):
    if "Application Control" in msg or "blocked" in msg.lower():
        return ("Windows Smart App Control blocks a package file -> run Setup.bat again (it switches to the signed Python); "
                "if it still fails: Windows Security -> App & browser control -> Smart App Control -> Off")
    if "DLL load failed" in msg or "WinError 126" in msg:
        return "a DLL is missing -> install the Microsoft C++ runtime (Setup.bat does it: click Yes when Windows asks), restart the PC"
    return f"package missing or broken -> run {SETUP} again"


def _imports(mods):
    bad = []
    for m in mods:
        try:
            __import__(m)
        except Exception as e:      # noqa: BLE001
            bad.append((m, _err(e)))
    if bad:
        m, msg = bad[0]
        raise RuntimeError(f"{len(bad)} of {len(mods)} fail; first: {m} -> {msg}\n      fix: {_import_remedy(msg)}")
    return f"{len(mods)} modules load (yt-dlp {_ytdlp_version()})"


def _ytdlp_version():
    try:
        import yt_dlp
        return yt_dlp.version.__version__
    except Exception:       # noqa: BLE001
        return "?"


def c_imports():
    """Python + the packages every run needs. A DLL that Windows blocks shows up here, before any 2-hour run."""
    return _imports(["socket", "ssl", "unicodedata", "numpy", "PIL.Image", "yt_dlp", "playwright"])


def c_imports_engines():
    """The native engines (whisper, the YouTube cipher, the container reader): C++ runtime / Smart App Control victims."""
    return _imports(["av", "Cryptodome.Cipher.AES", "faster_whisper", "ctranslate2", "onnxruntime"])


def _tool(name):
    """ffmpeg / ffprobe from runtime\\ffmpeg (Setup.bat) first, then PATH."""
    p = ROOT / "runtime" / "ffmpeg" / "bin" / (name + (".exe" if WIN else ""))
    return str(p) if p.exists() else shutil.which(name)


def c_ffmpeg():
    out = []
    for t in ("ffmpeg", "ffprobe"):
        p = _tool(t)
        if not p:
            raise RuntimeError(f"{t} not found (runtime\\ffmpeg or PATH) -> run {SETUP} again")
        r = subprocess.run([p, "-hide_banner", "-version"], capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            raise RuntimeError(f"{t} does not start ({r.stderr.strip()[:120]}) -> run {SETUP} again")
        out.append(" ".join(r.stdout.split()[:3]))
    return "; ".join(out)


def c_encoder():
    """Which encoder a run will use, proven with a 2 s encode (NVENC rejected by an old driver = the usual Windows trap)."""
    from ucf import config, render
    cfg = config.load()
    enc = render.pick_encoder(cfg)
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=1280x720:r=30:d=2",
                        *render.venc(enc), "-f", "null", "-"], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"{enc} test encode failed: {r.stderr.strip()[-200:]} -> run {SETUP} again; NVIDIA: update the driver")
    dec = f"GPU decode ({render._HW['name']})" if render._HW["name"] else "CPU decode"
    if enc == "libx264":
        encs = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
        if "h264_nvenc" in encs:
            err = subprocess.run(["ffmpeg", "-hide_banner", "-f", "lavfi", "-i", "color=c=black:s=1280x720:d=1", "-c:v", "h264_nvenc",
                                  "-f", "null", "-"], capture_output=True, text=True).stderr
            why = next((x.split("] ", 1)[-1] for x in err.splitlines() if any(k in x for k in (
                "Driver does not support", "minimum required", "No NVENC capable", "OpenEncodeSessionEx", "unsupported"))), "")
            if why and "No NVENC capable" not in why:
                raise RuntimeError(f"NVIDIA GPU found but NVENC is rejected: {why[:120]} -> update the NVIDIA driver (nvidia.com, "
                                   "Studio driver), restart the PC. Until then the CPU encodes (slow).")
        return f"libx264 (CPU encodes - no working GPU encoder on this PC), {dec}"
    mem = render.gpu_memory()
    vram = f", GPU memory {mem[1] / 1024:.1f} of {mem[0] / 1024:.1f} GB free" if mem else ""
    low = "   [WARN] under 1.5 GB of GPU memory free - close other programs that use the GPU" if mem and mem[1] < render.LOW_VRAM_MB else ""
    return f"{enc} (2 s test encode ok), {dec}{vram}{low}"


def _speech_wav(path, seconds=3.0):
    """A speech-like test sound: a 140 Hz tone with syllable-rate amplitude pulses, so the voice filter sees 'speech'."""
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", f"sine=f=140:r=16000:d={seconds}", "-af", "tremolo=f=4:d=0.9,volume=0.8", "-ac", "1", str(path)],
                    check=True, timeout=60)


def c_whisper():
    """whisper on a 3 s clip, with the configured model, in a child process - exactly the 0xC0000005 case."""
    try:
        __import__("faster_whisper")
    except Exception as e:      # noqa: BLE001
        raise RuntimeError(f"whisper not available here: {_err(e)}\n      fix: {_import_remedy(_err(e))}")
    from ucf import config, transcript
    cfg = config.load()
    if OFFLINE:
        os.environ["HF_HUB_OFFLINE"] = "1"          # never download the model without network
    lines = []
    with tempfile.TemporaryDirectory(prefix="smoke_") as t:
        wav = Path(t) / "speech.wav"
        _speech_wav(wav)
        try:
            segs = _timed(lambda: transcript.whisper_safe(wav, cfg["whisper_model"], threads=2, ui=lines.append), 240,
                          "whisper (first time: it downloads the model, a few hundred MB)")
        except RuntimeError as e:
            v = transcript.msvc_runtime_version()
            vc = "missing" if v is None else "version " + ".".join(map(str, v))
            raise RuntimeError(str(e).strip() + (f"\n      Microsoft C++ runtime on this PC: {vc} (whisper needs 14.40+). Fix: run Setup.bat "
                                                 "again (it installs the current one, click Yes), then restart the PC." if WIN else ""))
    odd = [x for x in lines if not x.startswith("transcript:")]       # the device line is reported below, not as a note
    note = " (" + odd[-1].strip() + ")" if odd else ""
    dev = "the GPU (CUDA)" if transcript.LAST["device"] == "cuda" else f"the CPU - {transcript.LAST['why']}"
    return f"model {cfg['whisper_model']} transcribed a 3 s clip in a child process on {dev}: {len(segs)} segment(s){note}"


def _key_set(fn, var):
    try:
        for line in (KEYS / fn).read_text(encoding="utf-8").splitlines():
            k, _, v = line.partition("=")
            if k.strip() == var and v.strip().strip("'\""):
                return True
    except OSError:
        pass
    return False


def c_keys():
    """The two key files hold a value (the values are never printed)."""
    miss = [f"{fn} ({var})" for fn, var in KEY_FILES.items() if not _key_set(fn, var)]
    if miss:
        raise RuntimeError(f"empty or missing: {', '.join(miss)} in {KEYS} -> H Labs.bat menu option 4")
    return f"{len(KEY_FILES)} key files set in {KEYS}"


def c_hosts():
    """One request per API host with a 10 s timeout: any HTTP answer (even 401/404) means the host is reachable."""
    if OFFLINE:
        raise Skip("skipped: --offline")
    import urllib.error
    import urllib.request
    bad = []
    for name, url in HOSTS.items():
        try:
            urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=10).close()
        except urllib.error.HTTPError:
            pass                                    # the server answered: reachable
        except Exception as e:  # noqa: BLE001
            bad.append(f"{name}: {url} -> {_err(e)[:100]}")
    if bad:
        raise RuntimeError("; ".join(bad) + " -> check the internet connection / firewall / VPN of this PC (the host must be allowed)")
    return ", ".join(f"{n} reachable" for n in HOSTS)


def ytdlp_probe(timeout=20):
    """-> (ok, text): does the installed yt-dlp still read YouTube? Used by Setup to decide newest vs pinned version."""
    cmd = [sys.executable, "-m", "yt_dlp"]
    try:
        v = subprocess.run(cmd + ["--version"], capture_output=True, text=True, timeout=timeout).stdout.strip()
        r = subprocess.run(cmd + ["--no-config", "-J", "--no-download", "--no-playlist", PROBE_URL],
                           capture_output=True, text=True, timeout=timeout)
        d = json.loads(r.stdout or "{}") if r.returncode == 0 else {}
        if d.get("id"):
            return True, f"yt-dlp {v} reads YouTube"
        tail = (r.stderr or "").strip().splitlines()
        return False, f"yt-dlp {v} cannot read {PROBE_URL}: {(tail or ['no output'])[-1][:200]}"
    except subprocess.TimeoutExpired:
        return False, f"yt-dlp did not answer in {timeout} s"
    except Exception as e:  # noqa: BLE001
        return False, _err(e)


def ytdlp_active():
    """What Setup installed: 'newest' or 'pinned (why)', from runtime\\ytdlp_active.txt."""
    try:
        return (ROOT / "runtime" / "ytdlp_active.txt").read_text(encoding="utf-8").strip().splitlines()[0]
    except (OSError, IndexError):
        return ""


def c_download():
    """yt-dlp reads a public video and lists a 720p+ format (the '360p only' client trap, ucf.download.info)."""
    if OFFLINE:
        raise Skip("skipped: --offline")
    from ucf import config, download
    cfg = config.load()
    url = cfg.get("smoke_video_url") or SMOKE_URL
    ver = _ytdlp_version() + (f", {ytdlp_active()}" if ytdlp_active() else "")
    try:
        m = _timed(lambda: download.info(url, cfg), 120, "yt-dlp")
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"yt-dlp {ver} cannot read {url}: {str(e).strip().splitlines()[-1][:160]} -> menu 8 updates yt-dlp; "
                           "YouTube blocking this IP? use a home/office connection, not a VPN / cloud PC")
    if int(m.get("best_height") or 0) < int(cfg.get("min_height", 720)):
        raise RuntimeError(f"yt-dlp {ver} lists only {m.get('best_height')}p for {url} (the tool needs 720p+) -> menu 8 updates yt-dlp; "
                           "if the newest is broken Setup falls back to the pinned one")
    return f"yt-dlp {ver}: best {m['best_height']}p for the test video"


def c_render():
    """10 s synthetic clip through the real Trial Tales segment render (watermark inside) + the join, with the dummy voice."""
    from ucf import config, render as R, tts as T, watermark as WM
    from ucf.render_tt import TTRenderer
    cfg = config.load(style="trial_tales")
    cfg.update({"use_hyperframes": False, "channel_name": cfg.get("channel_name") or "H LABS"})
    enc = R.pick_encoder(cfg)
    tmp = Path(tempfile.mkdtemp(prefix="smoke_render_"))
    try:
        src = tmp / "src.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=1280x720:r=30:d=10", "-f", "lavfi",
                        "-i", "sine=f=440:d=10", "-shortest", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                        "-g", "30", str(src)], check=True, timeout=120)
        voice = tmp / "voice.wav"
        T.PROVIDERS["dummy"]("Smoke test voice line.", voice, cfg, tmp)          # the voice path without ai33 credits
        if T.dur(voice) <= 0:
            raise RuntimeError("the dummy voice line is empty")
        rn = TTRenderer(cfg, {"s.mp4": {"path": str(src)}}, ROOT)
        rn.enc = enc
        (tmp / "_work").mkdir()
        seg = tmp / "_work" / "seg.mp4"
        R.set_finish(WM.segment_finish(dict(cfg, watermark=True), "smoke", tmp))
        try:
            rn.tt_cut("s.mp4", 0.0, 10.0, seg, rn.bg_logo)
            applied = R._FINISH.get("applied", 0)          # read before set_finish(None) clears the counter
        finally:
            R.set_finish(None)
        if not applied:
            raise RuntimeError("the watermark was not drawn into the segment -> send this check to the owner")
        lst = tmp / "list.txt"
        lst.write_text(f"file '{seg.resolve()}'\n", encoding="utf-8")
        fin = R.join_segments(lst, tmp / "video.mp4", cfg)
        d = R.probe_dur(fin)
        if not fin.exists() or not (9.0 <= d <= 11.0):
            raise RuntimeError(f"the test video is {d:.1f} s instead of 10 s -> run {SETUP} again; send this check to the owner")
        return f"10 s clip rendered with {enc} + watermark + joined ({d:.1f} s, {fin.stat().st_size // 1024} KB)"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def c_disk():
    free = shutil.disk_usage(ROOT).free / 1e9
    if free < 5:
        raise RuntimeError(f"{free:.0f} GB free on the H Labs drive - a run needs 15+ GB -> delete uploaded videos from output\\ and old work\\ folders")
    return f"{free:.0f} GB free on the H Labs drive" + ("   [WARN] below 20 GB - free some space soon" if free < 20 else "")


CHECKS = [("imports", c_imports), ("imports: whisper + download engines", c_imports_engines), ("ffmpeg", c_ffmpeg),
          ("encoder", c_encoder), ("whisper", c_whisper), ("keys", c_keys), ("ai33 + Hive reachable", c_hosts),
          ("download", c_download), ("render", c_render), ("disk", c_disk)]


def _version():
    try:
        return (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "dev"


def _commit():
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:       # noqa: BLE001
        return ""


def run_all(out_path):
    print(f"H Labs smoke test  v{_version()} {_commit()}  ({platform.system()} {platform.release()}, Python {platform.python_version()})"
          + ("  [--offline: network checks skipped]" if OFFLINE else ""))
    t_all = time.time()
    for name, fn in CHECKS:
        t0 = time.time()
        rec = {"name": name, "ok": True, "skipped": False, "msg": "", "seconds": 0.0}
        try:
            rec["msg"] = fn() or "ok"
            tag = "[ok]  "
        except Skip as e:
            rec.update(msg=str(e), skipped=True)
            tag = "[skip]"
        except Exception as e:  # noqa: BLE001
            rec.update(ok=False, msg=str(e).strip() or _err(e))
            tag = "[FAIL]"
        rec["seconds"] = round(time.time() - t0, 1)
        RESULTS.append(rec)
        print(f"  {tag} {name}: {rec['msg']}  ({rec['seconds']:.0f}s)", flush=True)
    fails = [r for r in RESULTS if not r["ok"]]
    result = {"date": time.strftime("%Y-%m-%d %H:%M:%S"), "version": _version(), "commit": _commit(), "offline": OFFLINE,
              "fails": len(fails), "seconds": round(time.time() - t_all), "checks": RESULTS}
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=1), encoding="utf-8")
    except OSError as e:
        print(f"  (could not write {out_path}: {e})")
    print(f"\nSMOKE: {len(RESULTS) - len(fails)}/{len(RESULTS)} ok in {result['seconds']} s"
          + (f"  FAILED: {', '.join(r['name'] for r in fails)}" if fails else "  - this PC is ready"))
    for r in fails:
        print(f"  {r['name']}: {r['msg'].splitlines()[0][:160]}")
    return len(fails)


def main():
    if "--ytdlp-probe" in sys.argv:
        ok, text = ytdlp_probe()
        print(("[ok] " if ok else "[FAIL] ") + text)
        return 0 if ok else 1
    out = ROOT / "state" / "smoke_last.json"
    if "--json" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--json") + 1])
    return run_all(out)


if __name__ == "__main__":
    sys.exit(main())
