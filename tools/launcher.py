"""H Labs launcher menu (Windows / Mac / Linux). Same choices as `H Labs.command`, plus a setup check.

Windows: double-click `H Labs.bat`.   Anywhere: python tools/launcher.py
Choices (brain / style / mode) are stored in .brain / .style / .mode next to run_stream.py, same files the Mac launcher uses.
"""
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def build_run_command(*a, **k):
    """One builder for launcher + Studio (ucf/runspec.py). Imported on use: --ensure-main / --rollback-git must still start
    on a half-updated tree where ucf/ is not there yet."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from ucf.runspec import build_run_command as _b
    return _b(*a, **k)


def _version():
    try:
        return (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "dev"
os.chdir(ROOT)
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
WIN = os.name == "nt"
KEYS = Path.home() / ".config" / "umf"
KEY_FILES = {"hive.env": "HIVE_API_KEY", "ai33.env": "AI33_API_KEY"}      # the only two keys this setup needs (brain + AI voice)
BRAINS = {"1": ("hive", "Hive - DeepSeek V4.1 Flash   - the brain of H Labs (~$0.01/video, needs hive.env)"),
          "2": ("manual", "manual                       - pipeline writes the prompt, you paste it into any chat, run again with the plan")}
# Anthropic / DeepSeek / OpenAI stay in the code (ucf/brain.py) but are not offered: the team PCs only have the Hive + ai33 keys.


def _read(name, default):
    try:
        v = (ROOT / name).read_text(encoding="utf-8").strip()
        return v or default
    except OSError:
        return default


def _brain():
    """The brain for a run: an old choice that is no longer offered (anthropic / deepseek / openai - no key on team PCs) -> hive."""
    b = _read(".brain", "hive")
    return b if b in {v[0] for v in BRAINS.values()} else "hive"


def _write(name, value):
    (ROOT / name).write_text(value + "\n", encoding="utf-8")


def styles():
    out = []
    for f in sorted((ROOT / "styles").glob("*/style.json")):
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
            out.append((j.get("id", f.parent.name), j.get("name", "?")))
        except (OSError, ValueError, AttributeError) as e:    # a broken pack is shown, so the typo in its style.json gets fixed
            out.append((f.parent.name, f"? (style.json unreadable: {str(e)[:60]})"))
    return out


def ask(prompt, default=""):
    try:
        v = input(prompt).strip()
    except EOFError:
        return default
    return v or default


def _pick_from(st, prompt, cur):
    d = next((i for i, (sid, _) in enumerate(st, 1) if sid == cur), 1)
    s = ask(f"{prompt} [1-{len(st)}, Enter={d}]: ", str(d))
    try:
        return st[int(s) - 1][0]
    except (ValueError, IndexError):
        return st[d - 1][0]


def pick_style():
    """Channel template for this run -> (style id, clips_only). The last entry is CLIPS ONLY (no template): clean clips + an
    editor guide; the tool then asks which channel the clips are for (its name / title rules go into the guide)."""
    st = styles()
    if not st:
        print("no style packs found in styles/")
        return None, False
    cur = _read(".style", st[0][0])
    c = len(st) + 1
    print("\nChannel template for this run:")
    for i, (sid, name) in enumerate(st, 1):
        print(f"  {i}) {name}  ({sid})   - fully edited videos in this channel's style")
    print(f"  {c}) CLIPS ONLY - no template: hook + case, dead air cut, no overlays / voice / watermark + EDITOR_GUIDE.txt")
    d = c if _read(".output", "video") == "clips" else next((i for i, (sid, _) in enumerate(st, 1) if sid == cur), 1)
    s = ask(f"Pick [1-{c}, Enter={d}]: ", str(d))
    clips = s.strip() == str(c)
    if clips:
        print("\nThe clips are for which channel? (its name and title style go into the editor guide)")
        for i, (sid, name) in enumerate(st, 1):
            print(f"  {i}) {name}  ({sid})")
        sid = _pick_from(st, "Pick", cur)
    else:
        try:
            sid = st[int(s) - 1][0]
        except (ValueError, IndexError):
            sid = st[d - 1][0] if d <= len(st) else cur
    _write(".style", sid)
    _write(".output", "clips" if clips else "video")
    print("\n>>> " + (f"CLIPS ONLY for {dict(st).get(sid, sid)} (no template, editor guide)" if clips
                       else f"{dict(st).get(sid, sid)}: fully edited videos"))
    return sid, clips


def pick_mode():
    """Video length mode for fully edited videos (clips only has no mode: every long-enough case becomes a clip)."""
    print("\nVideo mode for this run:\n  1) 30 min video   (v9 bundles, 20-40 min)\n  2) 1 hour video   (v9 bundles, 50-70 min)\n"
          "  3) All cases      (every case of 8:00 / 5:00+ becomes its own video, ranked)\n"
          "  4) As-is re-edit  (the WHOLE video becomes ONE edited video: no case selection, nothing skipped -\n"
          "                     for a single video link or your own file)")
    cur = _read(".mode", "all")
    d = {"30": 1, "60": 2, "all": 3, "asis": 4}.get(cur, 3)
    m = ask(f"Pick [1-4, Enter={d}]: ", str(d))
    mode = {"1": "30", "2": "60", "3": "all", "4": "asis"}.get(m, {1: "30", 2: "60", 3: "all", 4: "asis"}[d])
    _write(".mode", mode)
    print("mode:", mode)
    return mode


def min_case_choice(mode):
    """Mode all / clips: asks for the shortest case that gets its own video and returns "5" or "8" (the run command adds
    --min-case). Other modes: None."""
    if mode not in ("all", "clips"):
        return None
    cur = _read(".mincase", "8")
    d = "2" if cur == "5" else "1"
    m = ask(f"\nShortest case for its own {'clip' if mode == 'clips' else 'video'}:\n  1) 8 minutes (default)\n  2) 5 minutes\n"
            f"Pick [1-2, Enter={d}]: ", d)
    mins = "5" if (m or d) == "2" else "8"
    _write(".mincase", mins)
    print(f"cases of {mins}:00 or more")
    return mins


def pick_run():
    """Template (or clips only) + mode -> (style id, mode) or (None, None)."""
    sid, clips = pick_style()
    if not sid:
        return None, None
    return sid, ("clips" if clips else pick_mode())


def set_brain():
    print("\nChoose the brain provider (writes the plan JSON from the transcript):")
    for k, (_, label) in BRAINS.items():
        print(f"  {k}) {label}")
    b = ask(f"Pick 1-{len(BRAINS)}: ")
    if b in BRAINS:
        _write(".brain", BRAINS[b][0])
        print("Brain set to:", BRAINS[b][0])
    else:
        print("keeping current:", _brain())


def confirm_tts():
    return ask("\nAllow AI voiceover over 5,000 characters this run? (owner rule - type yes): ").lower() in ("yes", "y")


QUEUE = ROOT / "state" / "queue.txt"          # bulk queue: the links still to do (survives a closed window / restart)


def _urls(text):
    import re as _re
    seen, out = set(), []
    for u in _re.findall(r"https?://\S+", text or ""):
        u = u.strip().rstrip(",;")
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def bulk():
    """Bulk queue: many stream links in, processed one after the other (same style / mode / brain for all) until the list is done.
    A failed link is noted and the queue goes on. The remaining links are kept in state/queue.txt, so a closed window can resume."""
    left = _urls(QUEUE.read_text(encoding="utf-8")) if QUEUE.exists() else []
    if left and ask(f"\n{len(left)} link(s) are still waiting from the last queue. Continue them? [Y/n]: ", "y").lower() not in ("n", "no"):
        urls = left
    else:
        print("\nPaste the YouTube stream links (one per line, or many in one paste). Empty line = start.\n"
              "Or type the path of a .txt file that holds the links.")
        lines = []
        while True:
            ln = ask("> ")
            if not ln:
                break
            p = Path(ln.strip('"'))
            lines.append(p.read_text(encoding="utf-8") if p.suffix.lower() == ".txt" and p.exists() else ln)
        urls = _urls("\n".join(lines))
    if not urls:
        print("no links.")
        return
    sid, mode = pick_run()
    if not sid:
        return
    mins = min_case_choice(mode)
    tts_ok = mode != "clips" and confirm_tts()
    QUEUE.parent.mkdir(exist_ok=True)
    QUEUE.write_text("\n".join(urls) + "\n", encoding="utf-8")
    print(f"\nQUEUE: {len(urls)} stream(s), style {sid}, mode {mode}. Leave the PC on; each finished stream is cleaned up.\n")
    import time as _t
    t0, done, failed = _t.time(), [], []
    for i, url in enumerate(urls, 1):
        print("\n" + "#" * 64 + f"\n#  QUEUE {i}/{len(urls)}:  {url}\n" + "#" * 64)
        cmd = build_run_command(sys.executable, url, sid, mode, {"brain": _brain(), "queued": True, "min_case": mins, "voice": tts_ok},
                                script="run_stream.py")
        try:
            r = subprocess.run(cmd, cwd=ROOT)
            (done if r.returncode == 0 else failed).append(url)
        except KeyboardInterrupt:
            print("\nqueue stopped - the remaining links stay in the queue (menu 9 continues them).")
            return
        QUEUE.write_text("\n".join(urls[i:]) + ("\n" if urls[i:] else ""), encoding="utf-8")
    QUEUE.unlink(missing_ok=True)
    mins = (_t.time() - t0) / 60
    print("\n" + "=" * 64 + f"\nQUEUE DONE: {len(done)} ok, {len(failed)} failed, {mins:.0f} min in total")
    for u in failed:
        print("  FAILED:", u)
    if failed:
        (ROOT / "state").mkdir(exist_ok=True)            # a fresh clone has no state folder (it is per PC, not in git)
        (ROOT / "state" / "queue_failed.txt").write_text("\n".join(failed) + "\n", encoding="utf-8")
        print("  (saved in state\\queue_failed.txt - paste them into menu 9 again after a look at the error)")
    try:
        sys.path.insert(0, str(ROOT))
        from ucf import finish as F
        F.notify("H Labs - queue done", f"{len(done)} of {len(urls)} streams done in {mins:.0f} min" + (f", {len(failed)} failed" if failed else ""),
                 ok=not failed)
        F.open_folder(ROOT / "output")
    except (ImportError, OSError) as e:            # the queue result is already printed above
        print(f"  (notification skipped: {e})")
    ask("\nPress Enter...")


def run_stream(cmd):
    print("\n>", " ".join(cmd), "\n")
    try:
        subprocess.run(cmd, cwd=ROOT)
    except KeyboardInterrupt:
        print("\nstopped.")
    ask("\nDone. Output is in " + str(ROOT / "output") + "\nPress Enter...")


def open_path(p):
    p = str(p)
    try:
        if os.name == "nt":
            os.startfile(p)                                    # noqa: S606
        elif platform.system() == "Darwin":
            subprocess.run(["open", p])
        else:
            subprocess.run(["xdg-open", p])
    except Exception as e:
        print("could not open", p, "-", e)


def edit_keys():
    KEYS.mkdir(parents=True, exist_ok=True)
    for fn, var in KEY_FILES.items():
        f = KEYS / fn
        if not f.exists():
            f.write_text(f"{var}=\n", encoding="utf-8")
    print("Key files are in:", KEYS, "\n  hive.env -> HIVE_API_KEY=...   (the brain)\n  ai33.env -> AI33_API_KEY=...   (the AI voice)\n"
          "Paste each key after the '=' and save. Keys never go into the repo or into chat.")
    if os.name == "nt":
        for fn in KEY_FILES:
            subprocess.Popen(["notepad", str(KEYS / fn)])
    else:
        open_path(KEYS)


def _key_set(fn, var):
    try:
        for line in (KEYS / fn).read_text(encoding="utf-8").splitlines():
            k, _, v = line.partition("=")
            if k.strip() == var and v.strip().strip("'\""):
                return True
    except OSError:
        pass
    return False


LAST_GOOD = ROOT / "runtime" / "last_good.txt"       # newest first: "<commit> <branch> <version> <date>", at most 3 lines
SMOKE_LAST = ROOT / "state" / "smoke_last.json"


def _git(*args, **kw):
    return subprocess.run(["git", "-C", str(ROOT)] + list(args), capture_output=True, text=True, **kw)


def _main_branch():
    r = _git("rev-parse", "--abbrev-ref", "origin/HEAD")
    return r.stdout.strip().split("/", 1)[-1] if r.returncode == 0 and r.stdout.strip() else "main"


def smoke_passed():
    """None when no smoke result exists for the running commit, else whether that smoke test had 0 FAILs."""
    try:
        j = json.loads(SMOKE_LAST.read_text(encoding="utf-8"))
        head = _git("rev-parse", "--short", "HEAD").stdout.strip()
        if j.get("commit") and head and not head.startswith(j["commit"]) and not j["commit"].startswith(head):
            return None                                     # result of another build (e.g. before a rollback)
        return int(j.get("fails", 1)) == 0
    except (OSError, ValueError):
        return None


def record_last_good():
    """Before an update: remember the running commit as a build to go back to (menu u) - but only when its smoke test passed
    (or none ran yet), so a broken build never becomes the rollback target. Keeps the last 3. -> message"""
    commit = _git("rev-parse", "HEAD").stdout.strip()
    if not commit:
        return "not a git clone - nothing to record"
    if smoke_passed() is False:
        return "the current build failed its smoke test - not recorded as last good"
    r = _git("symbolic-ref", "-q", "--short", "HEAD")
    branch = r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else _main_branch()
    try:
        old = [ln for ln in LAST_GOOD.read_text(encoding="utf-8").splitlines() if ln.strip()]
    except OSError:
        old = []
    if old and old[0].split()[0] == commit:
        return f"last good build unchanged ({commit[:8]})"
    import time as _t
    lines = [f"{commit} {branch} {_version()} {_t.strftime('%Y-%m-%d %H:%M')}"] + [ln for ln in old if ln.split()[0] != commit]
    LAST_GOOD.parent.mkdir(parents=True, exist_ok=True)
    LAST_GOOD.write_text("\n".join(lines[:3]) + "\n", encoding="utf-8")
    return f"last good build recorded: {commit[:8]} v{_version()}"


def last_good():
    """-> (commit, branch, version, date) of the newest recorded good build, or None."""
    try:
        for ln in LAST_GOOD.read_text(encoding="utf-8").splitlines():
            parts = ln.split()
            if len(parts) >= 4:
                return parts[0], parts[1], parts[2], " ".join(parts[3:])
    except OSError:
        pass
    return None


def rollback_git():
    """Go back to the last good commit (detached HEAD; menu 8 returns to the branch). The per-PC state/ files are kept:
    they are not tracked any more, and a tracked copy from an old commit is reset before the checkout. -> True on success"""
    lg = last_good()
    if not lg:
        print("  no previous build is recorded on this PC yet (it is written by every update from now on).")
        return False
    commit, branch, ver, date = lg
    if _git("rev-parse", "HEAD").stdout.strip() == commit:
        print(f"  you are already on the last good build ({commit[:8]} v{ver}).")
        return False
    print(f"  going back to v{ver} ({commit[:8]}, recorded {date}) ...")
    import shutil as _sh
    import tempfile as _tf
    bak = Path(_tf.mkdtemp(prefix="hlabs_state_"))
    st = ROOT / "state"
    for f in st.glob("*") if st.exists() else []:
        if f.is_file():
            _sh.copy2(f, bak / f.name)
    if _git("ls-files", "state").stdout.strip():
        _git("checkout", "--", "state")
    r = _git("checkout", "-q", commit)
    st.mkdir(exist_ok=True)
    for f in bak.glob("*"):
        _sh.copy2(f, st / f.name)
    _sh.rmtree(bak, ignore_errors=True)
    if r.returncode != 0:
        print("  git could not switch:", (r.stderr or r.stdout).strip()[-400:])
        return False
    print(f"  >>> you are on the previous build v{_version()} ({commit[:8]}). Menu 8 returns to the newest build ({branch}).")
    return True


def _head_branch():
    """-> the checked-out branch, or "" on a detached HEAD (after a rollback, or an old build checked out by hand)."""
    r = _git("symbolic-ref", "-q", "--short", "HEAD")
    return r.stdout.strip() if r.returncode == 0 else ""


def ensure_main():
    """Before an update: a PC sitting on an old branch (justice-served, quality-fix, stable ...) or on a detached build gets
    `git pull --ff-only` = "Already up to date" and keeps running old code while Setup says success. So: name the branch loudly
    and switch to the main branch when nothing is edited here. -> True when the pull can bring the newest code."""
    main, cur = _main_branch(), _head_branch()
    if cur == main:
        return True
    where = f"the branch '{cur}'" if cur else "an older build (detached HEAD - after menu u, or checked out by hand)"
    print(f"\n  [!]  THIS PC IS NOT ON '{main}': it is on {where}.")
    print("       An update would say 'Already up to date' and leave this PC on old code.")
    dirty = _git("status", "--porcelain").stdout.strip()
    if dirty:
        print("       Files in the folder are edited, so nothing is switched automatically. Run this once in the H Labs folder:")
        print("         git checkout -- .    (throws the local edits away)")
        print(f"         git checkout {main}")
        print("       Then use menu 8 again. (Edited a setting? Put it in config.local.json instead - see WINDOWS_SETUP.md.)")
        print("       edited: " + ", ".join(ln.split(maxsplit=1)[-1] for ln in dirty.splitlines()[:5]))
        return False
    print(f"       Nothing is edited here, so switching to '{main}' now ...")
    r = _git("checkout", "-q", main)
    if r.returncode != 0:
        print("       git could not switch:", (r.stderr or r.stdout).strip()[-300:])
        print(f"       Run `git checkout {main}` in the H Labs folder, then menu 8 again.")
        return False
    print(f"       >>> now on '{main}' - the update brings the newest code.")
    return True


def update_pull():
    """Non-Windows menu 8: record the running build, make sure we are on the main branch, pull, and say what changed."""
    print("  " + record_last_good())
    before = (_version(), _git("rev-parse", "--short", "HEAD").stdout.strip())
    ensure_main()
    subprocess.run(["git", "pull", "--ff-only"], cwd=ROOT)
    print("  " + update_summary(before))


def update_summary(before):
    """old -> new version + short commit, so "nothing changed" is visible instead of hidden in a git message."""
    v0, c0 = before
    v1, c1 = _version(), _git("rev-parse", "--short", "HEAD").stdout.strip()
    if (v0, c0) == (v1, c1):
        return f"no new code: still H Labs v{v1} ({c1}) - this PC was already up to date"
    return f"updated: H Labs v{v0} ({c0})  ->  v{v1} ({c1})"


def doctor(pause=True):
    """Setup check: what is installed, which encoder will be used, which keys are present. Returns the number of [FAIL] lines."""
    fails = []
    ok = lambda m: print("  [ok]   " + m)          # noqa: E731
    warn = lambda m: print("  [WARN] " + m)         # noqa: E731

    def bad(m):
        fails.append(m)
        print("  [FAIL] " + m)
    print(f"\nSetup check  H Labs v{_version()}  ({platform.system()} {platform.release()}, Python {platform.python_version()})")
    (ok if sys.version_info >= (3, 10) else bad)(f"python {platform.python_version()} (3.10+ needed)")
    if (ROOT / ".venv").exists():
        ok(".venv found")
    else:
        warn(".venv missing - run Setup.bat first (Windows) or create one")
    ff = shutil.which("ffmpeg")
    if ff:
        ver = subprocess.run([ff, "-hide_banner", "-version"], capture_output=True, text=True).stdout.split(" ")[2:3]
        ok(f"ffmpeg {''.join(ver)}: {ff}" + ("" if WIN is False or "runtime" in ff else "   (not the one from Setup.bat - run Setup.bat)"))
        try:
            sys.path.insert(0, str(ROOT))
            from ucf import render
            from ucf import config as _C
            enc = render.pick_encoder(_C.load())          # same settings as a run (config.json + config.local.json)
            (ok if enc != "libx264" else warn)(f"video encoder that will be used: {enc}" + ("  (GPU encodes - the CPU stays free)" if enc != "libx264" else
                "  (no GPU encoder works: the CPU does ALL the encoding -> high CPU load. NVIDIA GPU + driver: run nvidia-smi and send this check)"))
            (ok if render._HW["name"] else warn)("video decode: " + (f"GPU ({render._HW['name']}) - the CPU only runs the filters"
                                                                    if render._HW["name"] else "CPU (GPU decode needs a working GPU encoder)"))
            from ucf.load import cpu_threads
            from ucf import config as _C
            cfg_now = _C.load()
            ok(f"CPU load limit: {cpu_threads(cfg_now)} of {os.cpu_count()} threads, priority {cfg_now.get('process_priority', 'below_normal')}"
               "  (config cpu_threads / process_priority)")
            if enc == "libx264" and "nvenc" in subprocess.run([ff, "-hide_banner", "-encoders"], capture_output=True, text=True).stdout:
                err = subprocess.run([ff, "-hide_banner", "-f", "lavfi", "-i", "color=c=black:s=1280x720:d=1", "-c:v", "h264_nvenc", "-f", "null", "-"],
                                     capture_output=True, text=True).stderr
                why = next((x.split("] ", 1)[-1] for x in err.splitlines() if any(k in x for k in (
                    "Driver does not support", "minimum required", "No NVENC capable", "OpenEncodeSessionEx", "unsupported"))), "")
                if why:
                    warn("NVIDIA encoder found but rejected: " + why[:150])
                    if "nvenc API version" in err or "minimum required" in err:
                        warn("  -> this ffmpeg is newer than the GPU driver. Fix: run Setup.bat (it brings ffmpeg 8.0.1), update the NVIDIA "
                             "driver, or just use CPU: \"x264_preset\": \"fast\" in config.json")
        except Exception as e:
            warn(f"could not test encoders: {e}")
    else:
        bad("ffmpeg not found in PATH")
    for mod, why in (("yt_dlp", "stream download"), ("PIL", "graphics"), ("numpy", "layout detection"), ("playwright", "Overruled / Court Beacon / Justice Served graphics"),
                     ("faster_whisper", "transcript fallback")):
        try:
            __import__(mod)
            ok(f"{mod} ({why})")
        except Exception as e:
            msg = str(e)
            if "Application Control" in msg or "blocked" in msg.lower():
                bad(f"{mod} BLOCKED by Windows Smart App Control ({why}) - turn it off: Windows Security -> App & browser control "
                    "-> Smart App Control settings -> Off, then run Setup.bat again")
            else:
                (bad if mod in ("yt_dlp", "PIL", "numpy", "playwright") else warn)(f"{mod} missing ({why}): {msg[:80]}")
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch(executable_path=os.environ.get("HL_CHROMIUM") or None)
            b.close()
        ok("Chromium for graphics launches")
    except Exception as e:
        bad("Chromium for graphics does not launch: " + str(e).splitlines()[0][:120] + "  -> run Setup.bat again")
    # watermark (every video gets one): needs the text font + ffmpeg's geq and overlay filters
    try:
        import tempfile
        from ucf import watermark as WM
        with tempfile.TemporaryDirectory() as t:
            WM.render_text_png("Test", Path(t) / "w.png", 34)
        flt = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout if shutil.which("ffmpeg") else ""
        miss = [f for f in ("geq", "overlay") if f" {f} " not in flt]
        (bad if miss else ok)("watermark: " + (f"ffmpeg lacks the {', '.join(miss)} filter (install the FULL ffmpeg build)" if miss else "text font + ffmpeg filters ready"))
    except Exception as e:
        bad(f"watermark check failed: {e}")
    (ok if shutil.which("node") else warn)("node " + ("found" if shutil.which("node") else "missing (only needed for yt-dlp challenge solving / hyperframes)"))
    for fn, var in KEY_FILES.items():
        (ok if _key_set(fn, var) else bad)(f"{fn}: " + ("key set" if _key_set(fn, var) else f"{var} is EMPTY - required ({KEYS}; menu option 4)"))
    if pause:
        ask("\nPress Enter...")
    return len(fails)


def main():
    while True:
        last = (f"CLIPS ONLY ({_read('.style', 'trial_tales')})" if _read(".output", "video") == "clips"
                else f"{_read('.style', 'trial_tales')}, mode {_read('.mode', 'all')}")
        print(f"\n==============================================\n  H LABS  -  UMF Case Factory   v{_version()}"
              f"\n  brain: {_brain()}   |   last run: {last}"
              f"\n  output: {ROOT / 'output'}\n==============================================")
        print("  1) New video from a YouTube stream URL (full pipeline)\n  2) Your own downloaded video / folder (no download; transcript optional)\n"
              "  3) Change brain provider\n  4) Edit API keys\n  5) Open output folder\n  6) Smoke test (2-3 min) / full self-test\n  7) Setup check (what is installed?)\n  8) Update H Labs (GitHub code + yt-dlp)\n"
              "  9) BULK QUEUE - many stream links, one after the other, until all are done\n"
              "  u) Undo the last update (go back to the previous build)\n"
              "  0) Open H Labs Studio (browser app: queue, progress, upload kit)\n"
              "  d) DOWNLOAD ONLY - YouTube links -> best-quality MP4 files (no editing)\n  q) Quit")
        pick = ask("Pick: ", "q").lower()
        if pick == "1":
            url = ask("YouTube URL: ")
            if not url:
                continue
            sid, mode = pick_run()
            if not sid:
                continue
            if not url.lower().startswith(("http://", "https://")):
                url = "https://" + url                    # "youtube.com/watch?v=..." typed without the scheme is still a link
            mins = min_case_choice(mode)
            voice = mode != "clips" and confirm_tts()      # clips mode makes no AI voice
            run_stream(build_run_command(sys.executable, url, sid, mode, {"brain": _brain(), "min_case": mins, "voice": voice},
                                         script="run_stream.py"))
        elif pick == "2":
            print("\nYour own downloaded video: give the video FILE, or a FOLDER that holds it (+ its transcript, if you have one:\n"
                  ".json / .json3 / .vtt / .srt). The download is skipped; no transcript -> whisper makes one.")
            src = ask("Video file or folder: ").strip('"')
            if not src:
                continue
            try:
                if str(ROOT) not in sys.path:
                    sys.path.insert(0, str(ROOT))
                from ucf import local_src
                v, t = local_src.resolve(src)
            except ValueError as e:
                print("  ", e)
                continue
            print(f"  video:      {v}\n  transcript: {t or 'none - whisper will make one'}")
            tr = ask("Other transcript file (Enter = as above): ").strip('"')
            sid, mode = pick_run()
            if not sid:
                continue
            mins = min_case_choice(mode)
            voice = mode != "clips" and confirm_tts()
            run_stream(build_run_command(sys.executable, src, sid, mode, {"brain": _brain(), "min_case": mins, "voice": voice,
                                                                          "transcript_file": tr}, script="run_stream.py"))
        elif pick == "3":
            set_brain()
        elif pick == "4":
            edit_keys()
        elif pick == "5":
            (ROOT / "output").mkdir(exist_ok=True)
            open_path(ROOT / "output")
        elif pick == "6":
            w = ask("\n  1) quick smoke (2-3 min: does this PC still make videos?)   2) full self-test   [Enter = 1]: ", "1")
            if w.strip() == "2":
                subprocess.run([sys.executable, "tests/run_tests.py", "--quick"], cwd=ROOT)
            else:
                subprocess.run([sys.executable, "tools/smoke_test.py"], cwd=ROOT)
            ask("\nPress Enter...")
        elif pick == "7":
            doctor()
        elif pick == "9":
            bulk()
        elif pick == "d":
            print("\nPaste the YouTube links to download (one per line). Empty line = start.")
            links = []
            while True:
                ln = ask("> ")
                if not ln:
                    break
                links += _urls(ln)
            if links:
                subprocess.run([sys.executable, str(ROOT / "tools" / "download_only.py"), *links], cwd=ROOT)
                ask("\nPress Enter...")
        elif pick == "0":
            subprocess.run([sys.executable, str(ROOT / "tools" / "studio" / "server.py")], cwd=ROOT)
        elif pick == "8" and WIN:
            sys.exit(88)              # H Labs.bat runs tools/win/setup.ps1 -Update once this process (and the files it holds) is closed
        elif pick == "u" and WIN:
            sys.exit(89)              # H Labs.bat runs tools/win/setup.ps1 -Rollback (git + packages of that commit) once this window is closed
        elif pick == "u":
            if rollback_git():
                print("  (packages: run the setup again if this build needs other versions)")
            ask("\nPress Enter...")
        elif pick == "8":
            update_pull()
            print("\nUpdating yt-dlp (YouTube changes often; an old yt-dlp is the usual reason a download fails)...")
            subprocess.run([sys.executable, "-m", "pip", "install", "-U", "yt-dlp[default]"], cwd=ROOT)
            ask("\nIf git says 'Already up to date' you have the latest code. Press Enter...")
        elif pick in ("q", ""):
            return


if __name__ == "__main__":
    if "--check" in sys.argv:              # used by Setup: setup check without the pause, exit code = number of problems
        sys.exit(doctor(pause=False))
    if "--record-last-good" in sys.argv:   # used by Setup -Update before the pull
        print("  " + record_last_good())
        sys.exit(0)
    if "--ensure-main" in sys.argv:        # used by Setup -Update before the pull: never pull into an old branch / detached build
        sys.exit(0 if ensure_main() else 1)
    if "--version-commit" in sys.argv:     # used by Setup -Update to show old -> new ("<version> <short commit>")
        print(f"{_version()} {_git('rev-parse', '--short', 'HEAD').stdout.strip()}")
        sys.exit(0)
    if "--rollback-git" in sys.argv:       # used by Setup -Rollback: the git part (state/ kept); Setup then syncs the packages
        sys.exit(0 if rollback_git() else 1)
    if "--last-good" in sys.argv:          # prints "<commit> <branch> <version> <date>" or nothing
        lg = last_good()
        print(" ".join(lg) if lg else "")
        sys.exit(0 if lg else 1)
    try:
        main()
    except KeyboardInterrupt:
        print()
