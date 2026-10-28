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
os.chdir(ROOT)
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
KEYS = Path.home() / ".config" / "umf"
KEY_FILES = {"hive.env": "HIVE_API_KEY", "anthropic.env": "ANTHROPIC_API_KEY", "deepseek.env": "DEEPSEEK_API_KEY",
             "openai.env": "OPENAI_API_KEY", "ai33.env": "AI33_API_KEY"}
BRAINS = {"1": ("hive", "Hive - DeepSeek V4.1 Flash   - default, ~$0.01/video, Claude fixes the cases it cannot"),
          "2": ("anthropic", "Anthropic (Claude)           - best quality, ~$0.34/video"),
          "3": ("deepseek", "DeepSeek direct              - backup if Hive is down"),
          "4": ("openai", "OpenAI (GPT)"),
          "5": ("manual", "manual                       - pipeline writes the prompt, you paste it into any chat, run again with the plan")}


def _read(name, default):
    try:
        v = (ROOT / name).read_text(encoding="utf-8").strip()
        return v or default
    except OSError:
        return default


def _write(name, value):
    (ROOT / name).write_text(value + "\n", encoding="utf-8")


def styles():
    out = []
    for f in sorted((ROOT / "styles").glob("*/style.json")):
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
            out.append((j.get("id", f.parent.name), j.get("name", "?")))
        except Exception:
            continue
    return out


def ask(prompt, default=""):
    try:
        v = input(prompt).strip()
    except EOFError:
        return default
    return v or default


def pick_style():
    st = styles()
    if not st:
        print("no style packs found in styles/")
        return None
    cur = _read(".style", st[0][0])
    d = next((i for i, (sid, _) in enumerate(st, 1) if sid == cur), 1)
    print("\nEditing style for this run:")
    for i, (sid, name) in enumerate(st, 1):
        print(f"  {i}) {sid}  ({name})")
    s = ask(f"Pick [1-{len(st)}, Enter={d}]: ", str(d))
    try:
        sid = st[int(s) - 1][0]
    except (ValueError, IndexError):
        sid = st[d - 1][0]
    _write(".style", sid)
    print("style:", sid)
    return sid


def pick_mode():
    print("\nVideo mode for this run:\n  1) 30 min video   (v9 bundles, 20-40 min)\n  2) 1 hour video   (v9 bundles, 50-70 min)\n"
          "  3) All cases      (every case >= 8:00 becomes its own video, ranked)")
    cur = _read(".mode", "60")
    d = {"30": 1, "60": 2, "all": 3}.get(cur, 2)
    m = ask(f"Pick [1-3, Enter={d}]: ", str(d))
    mode = {"1": "30", "2": "60", "3": "all"}.get(m, "60")
    _write(".mode", mode)
    print("mode:", mode)
    return mode


def set_brain():
    print("\nChoose the brain provider (writes the plan JSON from the transcript):")
    for k, (_, label) in BRAINS.items():
        print(f"  {k}) {label}")
    b = ask("Pick 1-5: ")
    if b in BRAINS:
        _write(".brain", BRAINS[b][0])
        print("Brain set to:", BRAINS[b][0])
    else:
        print("keeping current:", _read(".brain", "hive"))


def confirm_tts():
    return ask("\nAllow AI voiceover over 5,000 characters this run? (owner rule - type yes): ").lower() in ("yes", "y")


def run_stream(args):
    cmd = [sys.executable, "run_stream.py"] + args
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
    print("Key files are in:", KEYS, "\nPaste each key after the '=' and save. Keys never go into the repo or into chat.")
    if os.name == "nt":
        subprocess.run(["notepad", *[str(KEYS / f) for f in list(KEY_FILES)[:1]]])    # one at a time: Notepad has no tabs
        for fn in list(KEY_FILES)[1:]:
            if ask(f"Open {fn}? [y/N]: ").lower() == "y":
                subprocess.run(["notepad", str(KEYS / fn)])
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


def doctor():
    """Setup check: what is installed, which encoder will be used, which keys are present."""
    ok = lambda m: print("  [ok]   " + m)          # noqa: E731
    warn = lambda m: print("  [WARN] " + m)         # noqa: E731
    bad = lambda m: print("  [FAIL] " + m)         # noqa: E731
    print(f"\nSetup check ({platform.system()} {platform.release()}, Python {platform.python_version()})")
    (ok if sys.version_info >= (3, 10) else bad)(f"python {platform.python_version()} (3.10+ needed)")
    if (ROOT / ".venv").exists():
        ok(".venv found")
    else:
        warn(".venv missing - run install_windows.bat first (Windows) or create one")
    ff = shutil.which("ffmpeg")
    if ff:
        ok("ffmpeg: " + ff)
        try:
            sys.path.insert(0, str(ROOT))
            from ucf import render
            enc = render.pick_encoder({"encoder": "auto"})
            (ok if enc != "libx264" else warn)(f"video encoder that will be used: {enc}" + ("" if enc != "libx264" else "  (CPU only: slower; NVIDIA GPU + recent driver gives h264_nvenc)"))
        except Exception as e:
            warn(f"could not test encoders: {e}")
    else:
        bad("ffmpeg not found in PATH")
    for mod, why in (("yt_dlp", "stream download"), ("PIL", "graphics"), ("numpy", "layout detection"), ("playwright", "Overruled / Court Beacon / Justice Served graphics"),
                     ("faster_whisper", "transcript fallback")):
        try:
            __import__(mod)
            ok(f"{mod} ({why})")
        except Exception:
            (bad if mod in ("yt_dlp", "PIL", "numpy", "playwright") else warn)(f"{mod} missing ({why})")
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch(executable_path=os.environ.get("HL_CHROMIUM") or None)
            b.close()
        ok("Chromium for graphics launches")
    except Exception as e:
        bad("Chromium for graphics does not launch: " + str(e).splitlines()[0][:120] + "  -> run: python -m playwright install chromium")
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
    if not shutil.which("yt-dlp") and not shutil.which("yt_dlp"):
        warn("yt-dlp command not on PATH (the .venv one is used automatically when you start from H Labs.bat)")
    for fn, var in KEY_FILES.items():
        (ok if _key_set(fn, var) else warn)(f"{fn}: " + ("key set" if _key_set(fn, var) else f"no {var} yet ({KEYS})"))
    ask("\nPress Enter...")


def main():
    while True:
        print("\n==============================================\n  H LABS  -  UMF Case Factory"
              f"\n  brain: {_read('.brain', 'hive')}   |   style: {_read('.style', 'trial_tales')}   |   mode: {_read('.mode', '60')}"
              f"\n  output: {ROOT / 'output'}\n==============================================")
        print("  1) New video from a YouTube stream URL (full pipeline)\n  2) Local file mode (already downloaded / pre-cut clips)\n"
              "  3) Change brain provider\n  4) Edit API keys\n  5) Open output folder\n  6) Run self-test\n  7) Setup check (what is installed?)\n  8) Update H Labs from GitHub (git pull)\n  q) Quit")
        pick = ask("Pick: ", "q").lower()
        if pick == "1":
            url = ask("YouTube URL: ")
            if not url:
                continue
            sid, mode = pick_style(), None
            if not sid:
                continue
            mode = pick_mode()
            args = [url, "--brain", _read(".brain", "hive"), "--style", sid, "--mode", mode]
            if confirm_tts():
                args.append("--confirm-tts")
            run_stream(args)
        elif pick == "2":
            vf = ask("Video file path (or leave empty if using pre-cut clips): ")
            sid_ = ask("Stream ID (e.g. lVQ79x0Hd_w): ")
            slen = ask("Stream length H:MM:SS: ")
            tr = ask("Transcript file (empty = reuse work/<id>/transcript.json): ")
            sid = pick_style()
            if not sid:
                continue
            mode = pick_mode()
            args = ["--stream-id", sid_, "--brain", _read(".brain", "hive"), "--style", sid, "--mode", mode]
            if vf:
                args += ["--video-file", vf]
            if slen:
                args += ["--stream-length", slen]
            if tr:
                args += ["--transcript-file", tr]
            if confirm_tts():
                args.append("--confirm-tts")
            run_stream(args)
        elif pick == "3":
            set_brain()
        elif pick == "4":
            edit_keys()
        elif pick == "5":
            (ROOT / "output").mkdir(exist_ok=True)
            open_path(ROOT / "output")
        elif pick == "6":
            subprocess.run([sys.executable, "tests/run_tests.py", "--quick"], cwd=ROOT)
            ask("\nPress Enter...")
        elif pick == "7":
            doctor()
        elif pick == "8":
            subprocess.run(["git", "pull"], cwd=ROOT)
            ask("\nIf it says 'Already up to date' you have the latest. Press Enter...")
        elif pick in ("q", ""):
            return


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
