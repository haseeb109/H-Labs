"""Stock B-roll library: Pexels + Pixabay (free APIs) -> <library>/broll/<tag>/*.mp4

The brain never invents footage: it may only pick tags that exist on disk (see tags_on_disk). This module fills the
tag folders from the free stock sites, keeps a credits.csv (source, id, author, page URL) per folder, never downloads
the same clip twice, and picks clips for a video without repeats.

Keys (free): ~/.config/umf/pexels.env  -> PEXELS_API_KEY=...      (https://www.pexels.com/api/)
             ~/.config/umf/pixabay.env -> PIXABAY_API_KEY=...     (https://pixabay.com/api/docs/)
Either one is enough; with both, Pexels is tried first and Pixabay fills the rest.

    python tools/stock_fetch.py --library D:/HLabsLibrary              # every default tag, 8 clips each
    python tools/stock_fetch.py --library D:/HLabsLibrary --tag gavel --count 12
"""
import csv
import json
import os
import random
import time
import urllib.parse
import urllib.request
from pathlib import Path

VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv"}

# tag -> search query (subject + action + time of day + mood). Folder name = tag.
DEFAULT_TAGS = {
    "city_drone_dusk": "city skyline drone dusk river aerial",
    "police_car_night": "police car flashing lights night street",
    "handcuffs_table": "handcuffs on table dark",
    "handcuffs_car_hood": "handcuffs police car night lights",
    "shell_casings_night": "bullet shell casings ground night",
    "suv_night_street": "black suv driving residential street night",
    "suburban_house": "suburban house exterior evening",
    "apartment_aerial": "apartment complex aerial",
    "forensic_lab": "forensic lab investigator microscope",
    "phone_dark_table": "smartphone on dark table night",
    "drug_test_cups": "laboratory sample cups gloves",
    "case_folder": "opening case file folder documents desk",
    "gavel": "judge gavel sound block",
    "courtroom_empty": "empty courtroom benches",
    "courthouse_stone": "courthouse building facade low angle",
    "courthouse_brick": "historic brick courthouse blue sky",
    "jail_cell": "jail cell bars dark",
    "prison_exterior": "prison fence barbed wire",
    "hospital_night": "hospital emergency entrance night ambulance",
    "car_crash_night": "car accident night emergency lights",
    "bar_drinks_night": "bar drinks night neon",
    "calendar_pages": "calendar pages flipping time passing",
    "money_cash": "cash money counting hands",
    "documents_desk": "legal documents desk lamp",
    "crime_scene_tape": "crime scene tape police",
    "child_toys_empty": "empty playground swing",
    "family_photos": "old family photos table",
    "highway_night": "highway traffic night timelapse",
    "rain_window_night": "rain on window night",
    "clock_ticking": "clock ticking close up",
}


class StockError(RuntimeError):
    pass


def _keys():
    from ucf import config
    config.load_env()
    return os.environ.get("PEXELS_API_KEY", "").strip(), os.environ.get("PIXABAY_API_KEY", "").strip()


def _get_json(url, headers=None, tries=3):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=dict({"User-Agent": "hlabs-stock/1.0"}, **(headers or {})))
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise StockError(f"stock API refused the key (HTTP {e.code}) - check ~/.config/umf/pexels.env / pixabay.env")
            last = e
        except Exception as e:  # noqa - network hiccup: retried, the last error is raised below with the URL host
            last = e
        time.sleep(1.5 * (i + 1))
    raise StockError(f"stock search failed ({urllib.parse.urlparse(url).netloc}): {last}")


def _download(url, dest, tries=3):
    tmp = Path(str(dest) + ".part")
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "hlabs-stock/1.0"})
            with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
                while True:
                    b = r.read(1 << 20)
                    if not b:
                        break
                    f.write(b)
            os.replace(tmp, dest)
            return dest
        except Exception as e:  # noqa - retried; reason raised below
            last = e
            tmp.unlink(missing_ok=True)
            time.sleep(2 * (i + 1))
    raise StockError(f"download failed: {last}")


def _best(files, max_w=1920):
    """Pick the landscape rendition closest to 1920 wide (never above max_w when something smaller exists)."""
    ok = [f for f in files if f.get("width") and f.get("height") and f["width"] >= f["height"] and f["width"] >= 1280]
    if not ok:
        return None
    under = [f for f in ok if f["width"] <= max_w]
    return max(under, key=lambda f: f["width"]) if under else min(ok, key=lambda f: f["width"])


def search_pexels(query, key, n=15):
    q = urllib.parse.urlencode({"query": query, "per_page": n, "orientation": "landscape", "size": "medium"})
    data = _get_json(f"https://api.pexels.com/videos/search?{q}", {"Authorization": key})
    out = []
    for v in data.get("videos", []):
        f = _best([{"width": x.get("width"), "height": x.get("height"), "url": x.get("link")}
                   for x in v.get("video_files", []) if x.get("file_type", "video/mp4") == "video/mp4"])
        if f and 3 <= float(v.get("duration") or 0) <= 60:
            out.append({"source": "pexels", "id": str(v["id"]), "url": f["url"], "width": f["width"],
                        "duration": v.get("duration"), "author": (v.get("user") or {}).get("name", ""), "page": v.get("url", "")})
    return out


def search_pixabay(query, key, n=15):
    q = urllib.parse.urlencode({"key": key, "q": query[:100], "per_page": max(3, n), "video_type": "film", "safesearch": "true"})
    data = _get_json(f"https://pixabay.com/api/videos/?{q}")
    out = []
    for v in data.get("hits", []):
        vids = v.get("videos", {})
        f = _best([dict(width=x.get("width"), height=x.get("height"), url=x.get("url")) for x in vids.values() if x.get("url")])
        if f and 3 <= float(v.get("duration") or 0) <= 60:
            out.append({"source": "pixabay", "id": str(v["id"]), "url": f["url"], "width": f["width"],
                        "duration": v.get("duration"), "author": v.get("user", ""), "page": v.get("pageURL", "")})
    return out


def clips_in(folder):
    d = Path(folder)
    return sorted(p for p in d.iterdir() if p.suffix.lower() in VIDEO_EXT and p.stat().st_size > 0) if d.is_dir() else []


def tags_on_disk(library, min_clips=1):
    root = Path(library) / "broll"
    return sorted(d.name for d in root.iterdir() if d.is_dir() and len(clips_in(d)) >= min_clips) if root.is_dir() else []


def fetch_tag(library, tag, query=None, count=8, ui=print):
    """Fill <library>/broll/<tag> up to `count` clips. -> number of new clips."""
    pk, xk = _keys()
    if not pk and not xk:
        raise StockError("no stock key: put PEXELS_API_KEY in ~/.config/umf/pexels.env or PIXABAY_API_KEY in "
                         "~/.config/umf/pixabay.env (both free)")
    query = query or DEFAULT_TAGS.get(tag) or tag.replace("_", " ")
    folder = Path(library) / "broll" / tag
    folder.mkdir(parents=True, exist_ok=True)
    have = clips_in(folder)
    need = count - len(have)
    if need <= 0:
        return 0
    credits = folder / "credits.csv"
    known = set()
    if credits.exists():
        with open(credits, newline="", encoding="utf-8") as f:
            known = {(r["source"], r["id"]) for r in csv.DictReader(f)}
    cands = []
    if pk:
        try:
            cands += search_pexels(query, pk)
        except StockError as e:
            ui(f"  pexels: {e}")
    if xk and len(cands) < need * 2:
        try:
            cands += search_pixabay(query, xk)
        except StockError as e:
            ui(f"  pixabay: {e}")
    new = 0
    write_head = not credits.exists()
    with open(credits, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["file", "source", "id", "author", "page", "query"])
        if write_head:
            w.writeheader()
        for c in cands:
            if new >= need:
                break
            if (c["source"], c["id"]) in known:
                continue
            dest = folder / f"{c['source']}_{c['id']}.mp4"
            try:
                _download(c["url"], dest)
            except StockError as e:
                ui(f"  {tag}: {c['source']} {c['id']} skipped ({e})")
                continue
            w.writerow({"file": dest.name, "source": c["source"], "id": c["id"], "author": c["author"],
                        "page": c["page"], "query": query})
            known.add((c["source"], c["id"]))
            new += 1
    ui(f"  {tag}: +{new} clip(s), {len(clips_in(folder))} in folder ({query})")
    return new


def pick_clips(library, tag, n, used=None, seed=0):
    """n clips from one tag without repeating clips already in `used` (a set shared across the whole video).
    When the folder runs out, the least-used start over rather than failing."""
    used = used if used is not None else set()
    files = clips_in(Path(library) / "broll" / tag)
    if not files:
        raise StockError(f"B-roll tag '{tag}' has no clips: run tools/stock_fetch.py --tag {tag}")
    rnd = random.Random(f"{tag}:{seed}")
    fresh = [f for f in files if str(f) not in used]
    rnd.shuffle(fresh)
    out = fresh[:n]
    while len(out) < n:
        out.append(rnd.choice(files))
    used.update(str(f) for f in out)
    return out


# ------------------------------------------------------------------ B-roll for a render: API library and/or own folder
def folder_clips(folder):
    """Every video file under the owner's B-roll folder (sub-folders too)."""
    d = Path(folder)
    if not d.is_dir():
        return []
    return sorted(p for p in d.rglob("*") if p.suffix.lower() in VIDEO_EXT and p.is_file() and p.stat().st_size > 50_000)


def _tag_score(path, tag):
    words = [w for w in tag.lower().split("_") if len(w) > 2]
    name = str(path).lower()
    return sum(1 for w in words if w in name)


def pick_broll(cfg, tag, n, used=None, seed=0, ui=print):
    """n B-roll clips for one beat. cfg["broll_source"]:
         "auto"   (default) - library tag folder (Pexels/Pixabay) -> fills it from the API when a key is set ->
                              the owner's B-roll folder (random, files whose name matches the tag first)
         "api"    - only the Pexels/Pixabay library
         "folder" - only the owner's folder (cfg["broll_folder"])
    -> list of paths (may be shorter than n, or empty: the renderer then uses blurred court footage)."""
    used = used if used is not None else set()
    src = cfg.get("broll_source", "auto")
    lib = cfg.get("media_library") or ""
    out = []
    if src in ("auto", "api") and lib:
        if not clips_in(Path(lib) / "broll" / tag):
            try:
                pk, xk = _keys()
                if pk or xk:
                    fetch_tag(lib, tag, count=int(cfg.get("broll_fetch_count", 8)), ui=ui)
            except StockError as e:
                ui(f"  b-roll: {tag}: {e}")
        if clips_in(Path(lib) / "broll" / tag):
            out = pick_clips(lib, tag, n, used, seed)
    if len(out) < n and src in ("auto", "folder") and cfg.get("broll_folder"):
        allc = folder_clips(cfg["broll_folder"])
        rnd = random.Random(f"{tag}:{seed}:folder")
        fresh = [c for c in allc if str(c) not in used]
        rnd.shuffle(fresh)
        fresh.sort(key=lambda c: -_tag_score(c, tag))        # stable: name matches first, random inside each group
        take = fresh[:n - len(out)] or (rnd.sample(allc, min(len(allc), n - len(out))) if allc else [])
        used.update(str(c) for c in take)
        out += take
    return out


def broll_available(cfg):
    """-> short text of what the renderer can use, for the Studio / run log."""
    lib = cfg.get("media_library") or ""
    pk, xk = _keys()
    parts = []
    if lib:
        parts.append(f"library {len(tags_on_disk(lib))} tag folder(s)" + (" + API" if (pk or xk) else ""))
    if cfg.get("broll_folder"):
        parts.append(f"own folder {len(folder_clips(cfg['broll_folder']))} clip(s)")
    return ", ".join(parts) or "none (blurred court footage is used)"
