"""Several hearings of ONE defendant -> one documentary video (Case File Documentary / Docu-Series).

    python tools/dossier.py --name "Summer Diaz" URL1 URL2 URL3 [--style case_file_doc] [--alias "Ms. Diaz"] [--queued]

Links can be in any order: they are sorted by date. Every link is downloaded + transcribed; the defendant's part of each
earlier stream is cut into state/dossier/<name>/; the newest stream then runs through the full pipeline with --dossier.
(H Labs Studio: New run -> a documentary style -> "These links are hearings of ONE defendant".)
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def ui(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def main(argv=None, run=subprocess.run):
    from ucf import config, dossier as D, download
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("urls", nargs="+")
    ap.add_argument("--name", required=True, help="the defendant's name as the court says it")
    ap.add_argument("--alias", action="append", default=[], help="another spelling / how the court calls them")
    ap.add_argument("--style", default="case_file_doc")
    ap.add_argument("--brain")
    ap.add_argument("--queued", action="store_true")
    ap.add_argument("--confirm-tts", action="store_true")
    a = ap.parse_args(argv)
    cfg = config.load(style=a.style)
    urls = list(dict.fromkeys(u.strip() for u in a.urls if u.strip()))
    infos = []
    for u in urls:
        try:
            m = download.info(u, cfg)
            infos.append((m.get("upload_date", ""), u, m))
        except Exception as e:  # noqa - one bad link must not stop the dossier; the reason is printed
            ui(f"  SKIPPED {u}: {str(e).splitlines()[-1][:200] if str(e) else e}")
    if not infos:
        ui("no usable link - nothing to make")
        return 1
    infos.sort(key=lambda x: x[0])
    *older, newest = infos
    ui(f"dossier '{a.name}': {len(infos)} hearing(s), newest {D.nice_date(newest[0]) or newest[1]} is the main video")
    py = sys.executable
    for n, (up, u, m) in enumerate(older, 1):
        ui(f"HEARING {n}/{len(infos)} ({D.nice_date(up) or '?'}): {m.get('title', u)[:90]}")
        r = run([py, str(ROOT / "run_stream.py"), u, "--style", a.style, "--stage", "transcript", "--keep-source"],
                cwd=ROOT)
        if getattr(r, "returncode", 1):
            ui(f"  hearing {n} skipped: download / transcript failed (see above)")
            continue
        sid = m["id"]
        work = ROOT / cfg["work_dir"] / sid
        try:
            segs = json.loads((work / "transcript.json").read_text(encoding="utf-8"))
            srcs = json.loads((ROOT / cfg["state_dir"] / "sources.json").read_text(encoding="utf-8"))
            src = next(v["path"] for k, v in srcs.items() if Path(k).stem == sid or sid in str(v.get("url", "")))
            h = D.add_hearing(a.name, src, segs, up, u, m.get("title", ""), a.alias)
            ui(f"  {a.name}: {h['mentions']} mention(s), {int(h['src_out'] - h['src_in'])} s kept -> state/dossier/{D.key_of(a.name)}/{h['file']}")
        except (OSError, ValueError, StopIteration) as e:
            ui(f"  hearing {n} skipped: {e}")
    cmd = [py, str(ROOT / "run_stream.py"), newest[1], "--style", a.style, "--mode", "all", "--dossier", a.name]
    if a.brain:
        cmd += ["--brain", a.brain]
    if a.queued:
        cmd.append("--queued")
    if a.confirm_tts:
        cmd.append("--confirm-tts")
    ui(f"MAIN HEARING ({D.nice_date(newest[0]) or '?'}): {newest[2].get('title', newest[1])[:90]}")
    return getattr(run(cmd, cwd=ROOT), "returncode", 1)


if __name__ == "__main__":
    sys.exit(main())
