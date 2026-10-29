"""End of a run: 'done' notification, UPLOAD_LIST.txt, open the output folder, free disk space.

Cleanup (config cleanup_after_run: "ask" | "always" | "never") deletes ONLY things that can be made again:
  * work/<id>/source.mp4 (+ .part / .ytdl leftovers)  - the downloaded stream (1-3 GB); a re-render downloads it again.
    Never a file given with --video-file (that is the user's own file).
  * output/<run>/<video>/_work/  - render intermediates (cut clips, frames, thumbnail candidates), only where video.mp4 exists.
It NEVER touches the finished videos (video.mp4, thumbnail.jpg, metadata.txt, qc.json, contact sheets, reports), the transcript,
the plan / brain replies, or the AI-voice cache (work/<id>/tts - paid audio, re-used if a video is rendered again)."""
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def _size(p):
    p = Path(p)
    if p.is_file():
        return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.is_dir() else 0


def gb(n):
    return f"{n / 1e9:.1f} GB" if n >= 1e8 else f"{n / 1e6:.0f} MB"


def cleanup_candidates(work, outroot, own_video_file=None):
    """-> [(path, bytes, what)] of things that are safe to delete."""
    out = []
    own = Path(own_video_file).resolve() if own_video_file else None
    work = Path(work)
    for f in sorted(work.glob("source.*")) + sorted(work.glob("*.part")) + sorted(work.glob("*.ytdl")):
        if f.is_file() and (own is None or f.resolve() != own):
            out.append((f, _size(f), "downloaded stream" if f.name.startswith("source.") and f.suffix in (".mp4", ".mkv", ".webm")
                        else "download leftover"))
    for d in sorted(Path(outroot).glob("*/_work")):
        if d.is_dir() and (d.parent / "video.mp4").exists():
            out.append((d, _size(d), f"render temp files of {d.parent.name}"))
    return [c for c in out if c[1] > 0]


def cleanup(cfg, work, outroot, own_video_file=None, ui=print, ask=input):
    mode = str(cfg.get("cleanup_after_run", "ask")).lower()
    if mode == "never":
        return 0
    cands = cleanup_candidates(work, outroot, own_video_file)
    if not cands:
        return 0
    total = sum(c[1] for c in cands)
    if mode != "always":
        if not sys.stdin or not sys.stdin.isatty():
            return 0
        print(f"\nFREE DISK SPACE: {gb(total)} can be deleted - the finished videos in {outroot} stay untouched:")
        for p, n, what in cands:
            print(f"  {gb(n):>8}  {what}")
        print("  (kept: final videos, thumbnails, metadata, transcript, plan, AI-voice cache)")
        try:
            if ask("Delete these now? [y = yes / Enter = keep]: ").strip().lower() not in ("y", "yes"):
                print("  kept.")
                return 0
        except EOFError:
            return 0
    freed = 0
    for p, n, _ in cands:
        try:
            shutil.rmtree(p) if p.is_dir() else p.unlink()
            freed += n
        except OSError as e:
            ui(f"  could not delete {p.name}: {e}")
    ui(f"cleanup: freed {gb(freed)}")
    return freed


def upload_list(plan, rows, outroot, header_lines=()):
    """UPLOAD_LIST.txt: the finished videos in upload order with their title, length, QC and files; then what needs review.
    rows = [(n, folder name, seconds, qc_ok, video dict, qc dict)]."""
    from .timeutil import fmt_dur
    L = ["UPLOAD LIST - upload in this order (best first). Full description, tags, chapters: metadata.txt in each folder.", ""]
    L += list(header_lines) + ([""] if header_lines else [])
    for i, (n, folder, secs, ok, v, qc) in enumerate(sorted(rows, key=lambda r: r[4].get("rank", r[0])), 1):
        L.append(f"{i}. {folder}   {fmt_dur(secs)}   QC {'OK' if ok else 'CHECK - ' + str(qc.get('note', 'see qc.json'))}")
        if v.get("title"):
            L.append(f"   title:     {v['title']}")
        if v.get("backup_title"):
            L.append(f"   backup:    {v['backup_title']}  (swap at 48 h if CTR < 5%)")
        L.append(f"   files:     {folder}\\video.mp4  |  thumbnail.jpg  |  metadata.txt")
        L.append("   [ ] uploaded    [ ] thumbnail set    [ ] description + chapters pasted")
        L.append("")
    review = [c for c in plan.get("cases", []) if c.get("needs_review")]
    if review:
        L.append("NOT MADE - NEEDS REVIEW (the brain could not plan these cases; the other videos are fine):")
        for c in review:
            L.append(f"  - {c.get('name')}  ({c.get('in')}-{c.get('out')}): {c.get('reject_reason', '')}")
        L.append("")
    p = Path(outroot) / "UPLOAD_LIST.txt"
    p.write_text("\n".join(L), encoding="utf-8")
    return p


def notify(title, message, ok=True):
    """Desktop notification + sound. Never blocks and never fails the run."""
    print("\a", end="", flush=True)                    # terminal bell
    try:
        sysname = platform.system()
        if sysname == "Windows":
            esc = lambda s: s.replace("'", "''")       # noqa: E731
            ps = ("Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing; "
                  f"[System.Media.SystemSounds]::{'Asterisk' if ok else 'Hand'}.Play(); "
                  "$n = New-Object System.Windows.Forms.NotifyIcon; $n.Icon = [System.Drawing.SystemIcons]::Information; "
                  f"$n.Visible = $true; $n.ShowBalloonTip(15000, '{esc(title)}', '{esc(message)}', "
                  f"[System.Windows.Forms.ToolTipIcon]::{'Info' if ok else 'Error'}); Start-Sleep -Seconds 16; $n.Dispose()")
            subprocess.Popen(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        elif sysname == "Darwin":
            q = lambda s: s.replace("\\", "\\\\").replace('"', '\\"')   # noqa: E731
            subprocess.Popen(["osascript", "-e", f'display notification "{q(message)}" with title "{q(title)}" '
                              f'sound name "{"Glass" if ok else "Basso"}"'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif shutil.which("notify-send"):
            subprocess.Popen(["notify-send", title, message], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def open_folder(path):
    try:
        if not (sys.stdin and sys.stdin.isatty()):
            return
        if os.name == "nt":
            os.startfile(str(path))                    # noqa: S606 (Windows only)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", str(path)])
        elif shutil.which("xdg-open") and os.environ.get("DISPLAY"):
            subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
