#!/usr/bin/env python3
"""One-screen summary of one or more runs, read from work/<id>/events.jsonl (written by every run, see ucf/events.py).

    python tools/run_report.py work/<id>/events.jsonl
    python tools/run_report.py work/*/events.jsonl          many runs: one block each + a total
    python tools/run_report.py work                          a folder: every events.jsonl below it

Why: a problem used to mean "send work/<id>/run_log.txt" (megabytes). events.jsonl is a few KB and says what ran, what
failed and where the time went; send that instead. A file that holds several runs of the same stream (reruns append) is
split at each run_start. A run without run_end crashed or is still going - the report says so.
"""
import json
import sys
from pathlib import Path


def find_files(args):
    out = []
    for a in args:
        p = Path(a)
        if p.is_dir():
            out += sorted(p.rglob("events.jsonl"))
        elif p.is_file():
            out.append(p)
    return out


def read_events(path):
    """-> (events, number of unreadable lines). A half-written last line (crash) is simply skipped."""
    ev, bad = [], 0
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return [], 0
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            d = json.loads(line)
            if isinstance(d, dict):
                ev.append(d)
                continue
        except ValueError:
            pass
        bad += 1
    return ev, bad


def split_runs(events):
    runs, cur = [], None
    for e in events:
        if e.get("event") == "run_start" or cur is None:
            cur = []
            runs.append(cur)
        cur.append(e)
    return runs


def hms(s):
    s = int(round(s or 0))
    h, m, sec = s // 3600, s % 3600 // 60, s % 60
    return f"{h}h {m:02d}m {sec:02d}s" if h else f"{m}m {sec:02d}s"


def summarise(run, source=""):
    """One run (list of events) -> dict of the facts the report prints."""
    by = lambda name: [e for e in run if e.get("event") == name]   # noqa: E731
    first = by("run_start")[0] if by("run_start") else {}
    stages = {}
    for e in by("stage_end"):
        stages[e["stage"]] = stages.get(e["stage"], 0) + (e.get("seconds") or 0)
    seen = {e.get("cause") for e in by("video_failed")}
    fails, kept = [], set()
    for e in by("failure"):                      # the same cause is also on the video_failed line: print it once
        c = e.get("cause")
        if c not in kept and c not in seen:
            kept.add(c)
            fails.append((e.get("t", ""), e.get("stage") or "", c))
    for e in by("video_failed"):
        fails.append((e.get("t", ""), f"video {e.get('n')}", e.get("cause")))
    end = (by("run_end") or [None])[-1]
    return {"source": source, "start": first, "stages": stages, "download": (by("download") or [{}])[-1],
            "transcript": (by("transcript") or [{}])[-1], "plan": (by("plan") or [{}])[-1], "encoder": (by("encoder") or [{}])[-1],
            "videos": by("video_done"), "failed": by("video_failed"), "fails": fails, "end": end,
            "stream": (by("work_folder") or [{}])[-1].get("stream_id", ""), "first_t": run[0].get("t", ""),
            "last_t": run[-1].get("t", "")}


def render(s):
    st, end = s["start"], s["end"]
    status = end.get("status", "?") if end else "NO run_end - crashed or still running"
    out = [f"== {s['stream'] or Path(s['source']).parent.name}  {s['first_t']}  ->  {status}"
           + (f"  ({hms(end.get('seconds'))})" if end and end.get("seconds") is not None else "")]
    if st:
        out.append(f"   H Labs v{st.get('version', '?')} {st.get('commit', '')}  on {st.get('machine', '?')}  |  style {st.get('style', '?')}"
                   f"  |  mode {st.get('mode', '?')}  |  args: {' '.join(map(str, st.get('argv', [])))[:90]}")
    d, t, pl, en = s["download"], s["transcript"], s["plan"], s["encoder"]
    if d:
        out.append(f"   download   {d.get('height', '?')}p  {d.get('mbps', '?')} Mbps  ({d.get('source', '?')})")
    if t:
        dev = f", {t['device']}" + (f" {t['x_realtime']}x realtime" if t.get("x_realtime") else "") if t.get("device") else ""
        out.append(f"   transcript {t.get('source', '?')}  {t.get('segments', '?')} segments{dev}"
                   + (f"  [GPU: {t['gpu_note']}]" if t.get("gpu_note") else ""))
    if pl:
        cost = f", ${pl['cost_usd']:.2f}" if pl.get("cost_usd") is not None else ""
        tok = f", {pl.get('tokens_in', 0):,} in / {pl.get('tokens_out', 0):,} out tokens" if pl.get("tokens_in") else ""
        out.append(f"   plan       {pl.get('cases', '?')} cases, {pl.get('videos', '?')} videos  (brain {pl.get('brain', '?')}{tok}{cost})")
    if en:
        out.append(f"   encoder    {en.get('encoder', '?')}, decode {en.get('decode', '?')}")
    total = sum(s["stages"].values()) or 1
    if s["stages"]:
        out.append("   where the time went:")
        for name, sec in sorted(s["stages"].items(), key=lambda kv: -kv[1])[:8]:
            if sec >= 1:
                out.append(f"     {name:<22} {hms(sec):>10}  {sec / total * 100:3.0f}%  {'#' * int(sec / total * 30)}")
    if s["videos"] or s["failed"]:
        out.append(f"   videos: {len(s['videos'])} made, {sum(1 for v in s['videos'] if v.get('qc_ok'))} QC ok, {len(s['failed'])} failed")
        for v in s["videos"]:
            out.append(f"     {v.get('n'):>2} {str(v.get('folder', ''))[:30]:<30} {hms(v.get('seconds')):>10}  QC {'ok' if v.get('qc_ok') else 'CHECK'}"
                       f"  wm {v.get('watermark') or '-'}" + (f"  note: {str(v['notes'])[:80]}" if v.get("notes") else ""))
    if s["fails"] or (end and end.get("cause")):
        out.append("   FAILURES / SKIPPED EXTRAS:")
        for tt, where, c in s["fails"][:12]:
            out.append(f"     {tt[11:]} {where:<18} {c}")
        if len(s["fails"]) > 12:
            out.append(f"     ... and {len(s['fails']) - 12} more")
        if end and end.get("cause"):
            out.append(f"     run ended: {end['cause']}")
    return out


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    files = find_files(args)
    if not files:
        print(__doc__)
        return 2
    summaries, bad_total = [], 0
    for f in files:
        ev, bad = read_events(f)
        bad_total += bad
        for r in split_runs(ev):
            summaries.append(summarise(r, str(f)))
    for s in summaries:
        print("\n".join(render(s)))
        print()
    if len(summaries) > 1:
        ok = sum(1 for s in summaries if s["end"] and s["end"].get("status", "").startswith("completed"))
        vids = sum(len(s["videos"]) for s in summaries)
        secs = sum(s["end"].get("seconds") or 0 for s in summaries if s["end"])
        print(f"TOTAL  {len(summaries)} runs, {ok} completed, {vids} videos, {hms(secs)} processing, "
              f"{sum(len(s['fails']) for s in summaries)} failure line(s)")
    if bad_total:
        print(f"({bad_total} unreadable line(s) skipped - a crash can leave half a line at the end)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
