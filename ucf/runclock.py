"""Processing time of one run: wall clock from the start (download 0%) to the end, split by stage.
run_stream.py calls stage("download"), stage("transcript"), ... ; lines() gives the end-of-run block, history() appends one row
to state/run_history.csv (one line per run, so average speed per laptop / style can be compared later)."""
import csv
import time
from pathlib import Path

T = {"start": time.time(), "cur": None, "cur_t": None, "done": [], "printed": False}


def reset():
    T.update(start=time.time(), cur=None, cur_t=None, done=[], printed=False)


def stage(name):
    """Close the running stage and start `name` (None = just close)."""
    now = time.time()
    if T["cur"]:
        T["done"].append((T["cur"], now - T["cur_t"]))
    T["cur"], T["cur_t"] = name, now


def total():
    return time.time() - T["start"]


def hms(s):
    s = int(round(s))
    h, m, sec = s // 3600, s % 3600 // 60, s % 60
    return f"{h}h {m:02d}m {sec:02d}s" if h else f"{m}m {sec:02d}s"


def lines(stream_len=0, videos=0, status="completed"):
    stage(None)
    tot = total()
    out = [f"PROCESSING TIME  {hms(tot)}   ({status})"]
    for name, sec in T["done"]:
        if sec >= 1:
            out.append(f"  {name:<22} {hms(sec):>12}   {sec / tot * 100 if tot else 0:4.0f}%")
    if stream_len:
        out.append(f"  stream {hms(stream_len)} -> processed in {hms(tot)}  ({tot / stream_len:.2f}x the stream length)")
    if videos:
        out.append(f"  per video {hms(tot / videos)}  ({videos} videos)")
    T["printed"] = True
    return out


def history(path, **row):
    """Append one run to a CSV (created with a header the first time). Never raises."""
    try:
        p = Path(path)
        row = {"date": time.strftime("%Y-%m-%d %H:%M"), "total_min": round(total() / 60, 1), **row,
               **{f"{n}_min": round(s / 60, 1) for n, s in T["done"] if s >= 1}}
        old = []
        if p.exists():
            with p.open(newline="", encoding="utf-8") as f:
                old = list(csv.DictReader(f))
        keys = list(dict.fromkeys([k for r in old for k in r] + list(row)))
        with p.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(old + [row])
    except Exception:
        pass
