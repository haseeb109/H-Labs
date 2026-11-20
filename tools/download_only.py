"""H Labs downloader: YouTube links -> the best-quality MP4, nothing else (no transcript, brain or render).

    python tools/download_only.py URL [URL ...] [--out FOLDER] [--max-height 2160] [--queued]
    (menu option d, or H Labs Studio -> New run -> output "Download only")

Uses the same download engine as the pipeline (ucf.download: best video + best audio, three fallback ways when YouTube
blocks one), so a downloaded file is as good as the pipeline's own source. Unlike the pipeline it never refuses a video
for being below 720p: a video that only exists in 480p is downloaded in 480p (and the log says so).
Files land in output/downloads/<title> [<id>].mp4. A file already there is skipped. The pipeline is not touched.
"""
import argparse
import os
import re
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def ui(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def safe_name(title, vid):
    t = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', " ", title or "").strip(" .")
    t = re.sub(r"\s+", " ", t)[:120] or "video"
    return f"{t} [{vid}].mp4"


def download_one(url, out_dir, cfg, max_height):
    """-> final Path. Raises RuntimeError with a plain reason."""
    from ucf import download as D
    meta = D.info(url, cfg)
    if meta.get("is_live"):
        raise RuntimeError("this stream is still LIVE - download it after it ends")
    vid = meta["id"]
    dur = meta.get("duration") or 0
    ui(f"stream: {meta['title']}  ({int(dur // 3600)}:{int(dur % 3600 // 60):02d}:{int(dur % 60):02d}, id {vid})")
    final = Path(out_dir) / safe_name(meta["title"], vid)
    if final.exists() and final.stat().st_size > 1_000_000:
        ui(f"  already downloaded: {final.name} - skipped")
        return final
    best = int(meta.get("best_height") or 0)
    c = dict(cfg, max_height=max_height)
    # a plain downloader takes what the video has: no 720p floor when YouTube has nothing better
    c["min_height"] = min(int(cfg.get("min_height", 720)), best) if best else int(cfg.get("min_height", 720))
    if best and best < int(cfg.get("min_height", 720)):
        ui(f"  note: YouTube offers this video at {best}p at most - downloading {best}p")
    tmp = Path(out_dir) / f".part_{vid}"
    try:
        src = D.fetch_video(url, vid, tmp, c, meta)
        os.replace(src, final)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    ui("  " + D.describe(final)[0] + f"  -> {final.name}")
    return final


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("urls", nargs="+")
    ap.add_argument("--out", help="folder for the files (default: output/downloads)")
    ap.add_argument("--max-height", type=int, default=0, help="highest resolution to fetch (default: config max_height)")
    ap.add_argument("--queued", action="store_true", help="part of a queue: no folder window at the end")
    a = ap.parse_args(argv)
    from ucf import config, finish
    cfg = config.load()
    out_dir = Path(a.out) if a.out else config.ROOT / cfg.get("output_dir", "output") / "downloads"
    out_dir.mkdir(parents=True, exist_ok=True)
    max_h = a.max_height or int(cfg.get("max_height", 1080))
    urls = list(dict.fromkeys(u.strip() for u in a.urls if u.strip()))
    ok, failed = [], []
    for n, url in enumerate(urls, 1):
        ui(f"DOWNLOAD {n}/{len(urls)}: {url}")
        try:
            ok.append(download_one(url, out_dir, cfg, max_h))
        except KeyboardInterrupt:
            raise
        except Exception as e:  # noqa - one bad link must not stop the others; the reason is printed
            why = (str(e).strip().splitlines() or [repr(e)])[-1][:300]
            ui(f"  VIDEO {n} FAILED: {why} - going on")
            failed.append((url, why))
    ui(f"downloads: {len(ok)} ok, {len(failed)} failed  ({out_dir})")
    for url, why in failed:
        ui(f"  FAILED: {url}  ({why})")
    ui("ALL DONE ->", out_dir)
    if ok and not a.queued and cfg.get("open_output_after_run", True):
        finish.open_folder(out_dir)
    return 1 if failed and not ok else 0


if __name__ == "__main__":
    sys.exit(main())
