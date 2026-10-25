#!/usr/bin/env python3
"""UMF ai33.pro TTS helper.

LOCK: text over 5,000 characters is refused unless --confirmed is passed.
Claude only passes --confirmed after the user explicitly approves in chat.

Usage:
  ai33_tts.py voices --provider elevenlabs [--search "deep male"] [--language English]
  ai33_tts.py credits
  ai33_tts.py tts --voice elevenlabs_XXXX --text-file script.txt --out voice.mp3 [--speed 1] [--confirmed]
"""
import argparse, json, os, sys, time, urllib.request, urllib.parse, uuid

CHAR_LOCK = 5000
ENV = os.path.expanduser("~/.config/umf/ai33.env")


def load_env():
    if os.path.exists(ENV):
        for line in open(ENV):
            if "=" in line:
                k, v = line.strip().split("=", 1)
                os.environ.setdefault(k, v)
    key = os.environ.get("AI33_API_KEY")
    if not key:
        sys.exit("AI33_API_KEY missing (expected in ~/.config/umf/ai33.env)")
    return key, os.environ.get("AI33_BASE_URL", "https://api.ai33.pro").rstrip("/")


KEY, BASE = load_env()


def req(path, method="GET", fields=None):
    headers = {"xi-api-key": KEY}
    data = None
    if fields is not None:
        b = uuid.uuid4().hex
        parts = []
        for k, v in fields.items():
            parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n')
        data = ("".join(parts) + f"--{b}--\r\n").encode()
        headers["Content-Type"] = f"multipart/form-data; boundary={b}"
    for attempt in range(12):
        r = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(r, timeout=120) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="ignore")
            # retry busy/rate-limit only for reads (never re-submit a paid POST)
            if e.code in (429, 502, 503, 504) and method == "GET" and attempt < 11:
                time.sleep(5); continue
            sys.exit(f"HTTP {e.code}: {body}")


def find_url(obj):
    if isinstance(obj, str) and obj.startswith("http") and any(x in obj for x in (".mp3", ".wav", "audio", "storage")):
        return obj
    if isinstance(obj, dict):
        for k in ("audio_url", "output_uri", "url", "file_url"):
            if isinstance(obj.get(k), str) and obj[k].startswith("http"):
                return obj[k]
        for v in obj.values():
            u = find_url(v)
            if u:
                return u
    if isinstance(obj, list):
        for v in obj:
            u = find_url(v)
            if u:
                return u
    return None


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("credits")
    v = sub.add_parser("voices")
    v.add_argument("--provider", required=True)
    v.add_argument("--search"); v.add_argument("--language"); v.add_argument("--gender")
    v.add_argument("--limit", default="20")
    t = sub.add_parser("tts")
    t.add_argument("--voice", required=True)
    g = t.add_mutually_exclusive_group(required=True)
    g.add_argument("--text"); g.add_argument("--text-file")
    t.add_argument("--out", default="voice.mp3")
    t.add_argument("--speed", default="1")
    t.add_argument("--confirmed", action="store_true", help="user approved >5000 chars")
    a = p.parse_args()

    if a.cmd == "credits":
        print(json.dumps(req("/v1/credits"))); return
    if a.cmd == "voices":
        q = {"provider": a.provider, "page_size": a.limit}
        for k in ("search", "language", "gender"):
            if getattr(a, k): q[k] = getattr(a, k)
        res = req("/v3/voices?" + urllib.parse.urlencode(q))
        for x in res.get("data", []):
            print(x.get("voice_id"), "|", x.get("name"), "|", x.get("gender"), "|", x.get("language") or x.get("locale"), "|", x.get("accent") or "")
        return

    text = a.text if a.text is not None else open(a.text_file, encoding="utf-8").read()
    n = len(text)
    if n > CHAR_LOCK and not a.confirmed:
        sys.exit(f"LOCKED: {n:,} characters > {CHAR_LOCK:,}. Ask the user for approval first, then re-run with --confirmed.")
    before = req("/v1/credits").get("credits")
    res = req("/v3/text-to-speech", "POST", {"text": text, "voice_id": a.voice, "speed": a.speed, "with_transcript": "false"})
    tid = res.get("task_id") or sys.exit(f"No task_id: {res}")
    print(f"task {tid} | {n:,} chars")
    poll(tid, a.out, before)


def poll(tid, out, before=None):
    """Poll a task until done and download audio. Reusable to resume a task without paying again."""
    while True:
        st = req(f"/v1/task/{tid}")
        s = st.get("status")
        if s in ("done", "success", "completed"):
            break
        if s in ("error", "failed"):
            sys.exit(f"FAILED: {st}")
        time.sleep(3)
    url = find_url(st.get("metadata", {})) or find_url(st)
    if not url:
        sys.exit(f"Done but no audio URL found: {json.dumps(st)[:800]}")
    dl = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(dl, timeout=300) as r, open(out, "wb") as f:
        f.write(r.read())
    after = req("/v1/credits").get("credits")
    print(f"saved {out} | credits used: {before - after if isinstance(before, int) and isinstance(after, int) else '?'} | left: {after}")


if __name__ == "__main__":
    main()
