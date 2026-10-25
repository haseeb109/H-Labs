"""OCR of Zoom tile name labels (bottom-left strip of each tile). Engines, in auto order:
ocrmac (macOS Apple Vision, fast) -> rapidocr-onnxruntime (cross-platform) -> off (graceful warning).
Only label STRINGS and timestamps are kept - never frames or faces."""
import re


def pick_engine(want="auto"):
    if want == "off":
        return None
    if want in ("auto", "ocrmac"):
        try:
            import ocrmac  # noqa: F401
            return "ocrmac"
        except Exception:
            if want == "ocrmac":
                return None
    if want in ("auto", "rapidocr"):
        try:
            from rapidocr_onnxruntime import RapidOCR  # noqa: F401
            return "rapidocr"
        except Exception:
            return None
    return None


_CLEAN = re.compile(r"[^a-z0-9]")


def read_labels(frame_path, tiles, engine):
    """-> [label, ...] for one frame; tiles = [(x, y, w, h)] in that frame's own resolution."""
    if not engine or not frame_path.exists():
        return []
    import subprocess
    labels = []
    for (x, y, w, h) in tiles:
        strip = frame_path.with_name(frame_path.stem + f"_{x}_{y}.png")
        try:
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(frame_path),
                            "-vf", f"crop={min(300, w - 8)}:{max(12, h // 12)}:{x + 4}:{y + h - 30},"
                                   f"scale=iw*3:-1,format=gray", str(strip)], check=True, timeout=30)
            if engine == "ocrmac":
                from ocrmac import ocrmac as _om
                txt = " ".join(r[0] for r in _om(str(strip)).recognize())
            else:
                from rapidocr_onnxruntime import RapidOCR
                txt = " ".join(r[1] for r in (RapidOCR()(str(strip))[0] or []) if len(r) > 1)
            t = _CLEAN.sub("", (txt or "").lower())
            if len(t) >= 3:
                labels.append(t)
        except Exception:
            continue
        finally:
            strip.unlink(missing_ok=True)
    return labels


def norm_label(s):
    fixed = {"187thcourt": "court", "court": "court", "judge": "judge", "witness": "witness",
             "187thdistrictcourt": "court"}
    return fixed.get(s, s)
