"""pytest entry point for the H Labs self-test matrix.

    python -m pytest tests/ -q                 every check (test 10 = the full 28 min render is skipped unless HL_FULL=1)
    python -m pytest tests/ -q -k "studio or speed"   only some

Every `tN_*` function in run_tests.py becomes one pytest test, so a failure shows the failing check on its own, with pytest's
diff, and a single check can be run while working on it. `python tests/run_tests.py --quick` (menu option 6) stays as it is.
"""
import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
if "--quick" not in sys.argv and not os.environ.get("HL_FULL"):
    sys.argv = sys.argv + ["--quick"]            # run_tests reads QUICK from argv at import
import run_tests as M  # noqa: E402

_ORDER = []
for ln in Path(M.__file__).read_text(encoding="utf-8").splitlines():
    m = re.match(r"\s*check\((\d+), \"([^\"]+)\", (t\w+)\)", ln)
    if m:
        _ORDER.append((int(m.group(1)), m.group(2), m.group(3)))
_ORDER.sort()
_ENV_ONLY = {1, 3}            # need faster_whisper / PowerShell: skipped where they are not installed (team PCs have them)


@pytest.mark.parametrize("num,name,fn", _ORDER, ids=[f"t{n:02d}_{re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')}" for n, name, _ in _ORDER])
def test_check(num, name, fn):
    if num == 10 and not os.environ.get("HL_FULL"):
        pytest.skip("full end-to-end render: set HL_FULL=1")
    try:
        detail = getattr(M, fn)() or ""
    except (ImportError, FileNotFoundError) as e:
        if num in _ENV_ONLY:
            pytest.skip(f"not available on this machine: {e}")
        raise
    if isinstance(detail, str) and detail.startswith("SKIPPED"):
        pytest.skip(detail)
