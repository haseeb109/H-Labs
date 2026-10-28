"""Stand-alone watermark (same code the pipeline uses, see ucf/watermark.py).

    python tools/watermark.py video.mp4 "Trial Tales"                       # -> video_wm.mp4
    python tools/watermark.py video.mp4 "Trial Tales" out.mp4 --opacity 0.25 --size 34 --every 9
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ucf import watermark  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("text", help="channel name, e.g. 'Trial Tales'")
    ap.add_argument("out", nargs="?")
    ap.add_argument("--opacity", type=float, default=0.25)
    ap.add_argument("--size", type=int, default=34, help="font size in px on a 1080p frame")
    ap.add_argument("--every", type=float, default=9.0, help="seconds per position")
    ap.add_argument("--fade", type=float, default=0.8)
    ap.add_argument("--margin", type=int, default=48)
    ap.add_argument("--seed", type=int, default=0, help="changes the position sequence")
    a = ap.parse_args()
    out = a.out or str(Path(a.video).with_name(Path(a.video).stem + "_wm.mp4"))
    print("->", watermark.apply(a.video, out, a.text, opacity=a.opacity, size=a.size, every=a.every, fade=a.fade,
                                margin=a.margin, seed=a.seed))


if __name__ == "__main__":
    main()
