"""Fill the B-roll library from Pexels / Pixabay (free keys in ~/.config/umf/pexels.env / pixabay.env).

    python tools/stock_fetch.py --library D:/HLabsLibrary                 # every default tag, 8 clips each
    python tools/stock_fetch.py --library D:/HLabsLibrary --tag gavel --count 12
    python tools/stock_fetch.py --library D:/HLabsLibrary --tag my_tag --query "words to search"
    python tools/stock_fetch.py --library D:/HLabsLibrary --status        # what is in the library
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main(argv=None):
    from ucf import audiomix, config, stock
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--library", help="library folder (default: config media_library)")
    ap.add_argument("--tag", action="append", help="tag folder to fill (repeatable); default = all default tags")
    ap.add_argument("--query", help="search words for a single --tag")
    ap.add_argument("--count", type=int, default=8)
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args(argv)
    cfg = config.load()
    lib = a.library or cfg.get("media_library", "")
    if not lib:
        print("no library folder: pass --library D:/HLabsLibrary or set media_library in config.local.json")
        return 2
    if a.status:
        for t in sorted(set(stock.DEFAULT_TAGS) | set(stock.tags_on_disk(lib, 0))):
            print(f"  broll/{t:<22} {len(stock.clips_in(Path(lib) / 'broll' / t))}")
        st = audiomix.library_status(lib)
        for kind in ("music", "sfx"):
            for k, n in st[kind].items():
                print(f"  {kind}/{k:<24} {n}")
        return 0
    tags = a.tag or list(stock.DEFAULT_TAGS)
    bad = 0
    for t in tags:
        try:
            stock.fetch_tag(lib, t, a.query if len(tags) == 1 else None, a.count)
        except stock.StockError as e:
            print(f"  {t}: FAILED - {e}")
            bad += 1
            if "no stock key" in str(e) or "refused the key" in str(e):
                return 1
    print(f"done ({len(tags) - bad}/{len(tags)} tags ok) -> {Path(lib) / 'broll'}")
    print("music/ and sfx/ are not on Pexels/Pixabay video search: put your own files in "
          f"{Path(lib) / 'music'}\\<mood> and {Path(lib) / 'sfx'}\\<kind> (see --status for the folder names)")
    return 1 if bad == len(tags) else 0


if __name__ == "__main__":
    sys.exit(main())
