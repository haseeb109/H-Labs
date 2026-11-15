"""UMF Case Factory - livestream URL -> N re-edited case videos."""
from pathlib import Path as _P

def _read_version():
    """VERSION file at the repo root (date-based, e.g. 2026.11.15); bumped with every release so every laptop can say which
    build it runs (launcher banner, Studio, run log, run report)."""
    try:
        return (_P(__file__).resolve().parent.parent / "VERSION").read_text(encoding="utf-8").strip() or "dev"
    except OSError:
        return "dev"


__version__ = _read_version()
