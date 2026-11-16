"""One structured log per run: work/<id>/events.jsonl - one JSON object per line, written as the run goes.

Why: when something fails the owner has to ask for work/<id>/run_log.txt (megabytes of console text), and the rest of the
story sits in three other places (state/run_history.csv, state/queue_failed.txt, the Studio queue file). This file is the
whole run in a few kilobytes: every stage with its seconds, the download, the transcript, the plan, every video, every
failure with the cause line, and the end status. tools/run_report.py turns it (or a folder of runs) into a one-screen summary.

Rules that matter:
* every line is appended AND flushed at once - a crash (even 0xC0000005) keeps everything that happened up to it,
* the file stays valid line-by-line JSON: a half-written last line is the only thing a reader may have to drop,
* nothing here may ever break a run: every failure is swallowed (the human run_log.txt is still written as before).

run_log.txt is unchanged - this is in addition to it.
"""
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_LOG = {"path": None, "buffer": [], "warned": False}
MAX_BUFFER = 200          # events before the work folder is known (stage "info") are kept here, then written in order


def _line(event, stage, fields):
    d = {"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "stage": stage, "event": event}
    d.update({k: v for k, v in fields.items() if v is not None})
    return json.dumps(d, ensure_ascii=False, default=str)


def emit(event, stage=None, **fields):
    """Write one event. Before open_log() the events are buffered (the work folder is only known after the stream info)."""
    try:
        txt = _line(event, stage, fields)
    except (TypeError, ValueError):                       # a field that will not serialise must not cost the line
        txt = _line(event, stage, {"note": "fields dropped (not JSON)"})
    p = _LOG["path"]
    if p is None:
        if len(_LOG["buffer"]) < MAX_BUFFER:
            _LOG["buffer"].append(txt)
        return
    try:
        with open(p, "a", encoding="utf-8") as f:         # append + flush per line: a crash keeps what happened
            f.write(txt + "\n")
            f.flush()
    except OSError as e:
        if not _LOG["warned"]:
            _LOG["warned"] = True
            print(f"  events.jsonl is not being written ({e}) - run_log.txt still is", flush=True)


def open_log(path):
    """Point the log at work/<id>/events.jsonl (append: a rerun of the same stream keeps the earlier runs) and flush the buffer."""
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        _LOG["path"] = p
        for txt in _LOG["buffer"]:
            with open(p, "a", encoding="utf-8") as f:
                f.write(txt + "\n")
                f.flush()
        _LOG["buffer"] = []
    except OSError as e:
        _LOG["path"] = None
        print(f"  events.jsonl could not be opened ({e}) - run_log.txt still is written", flush=True)
    return _LOG["path"]


def path():
    return _LOG["path"]


def reset():
    _LOG.update(path=None, buffer=[], warned=False)


def commit():
    """Short git commit of the code that ran (so a report says which build made a video). '' when there is no git here."""
    try:
        r = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def run_start(**fields):
    from . import __version__
    emit("run_start", "start", version=__version__, commit=commit(), argv=sys.argv[1:],
         machine=platform.node() or os.environ.get("COMPUTERNAME", ""), os=platform.platform(), pid=os.getpid(), **fields)


def failure(where, cause, **fields):
    """A failure with the cause line run_stream.cause() produces (same text as in run_log.txt)."""
    emit("failure", where, cause=cause, **fields)
