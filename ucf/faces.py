"""Face detection (MediaPipe) for thumbnails: pick frames with a big, clear face and keep the title text off it.

Backend: the MediaPipe "solutions" face detector (full-range model, ships inside the pip package) when the
installed mediapipe still has it, else the Tasks FaceDetector with models/blaze_face_short_range.tflite.
Missing mediapipe -> every call returns [] and the thumbnail falls back to the old sharpest-frame rule.
"""
import os
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
TASK_MODEL = ROOT / "models" / "blaze_face_short_range.tflite"
TASK_MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/"
                  "float16/latest/blaze_face_short_range.tflite")
_DET = {}
MIN_SCORE = 0.6
PROBE, PROBE_WIN = (320, 180), 4        # pre-check: frame size and window (4 px here = 16 px at 720p)
MIN_SKIN_DENSITY = 0.5                  # a window that is at least half skin-coloured -> mediapipe decides
STATS = {"frames": 0, "skipped": 0}     # how often the pre-check saved a mediapipe pass (for timing a run)
# The pre-check also removes the odd mediapipe false positive on a skin-free tile (a "face" on a wall or a colour bar).
# That is the better picture, but it is a judgement about the footage: set HL_FACE_PRECHECK=0 (or "face_precheck": false
# in config.local.json, which run_stream exports) on a PC where a thumbnail looks wrong, and every frame goes to mediapipe
# again as before 2026-11-16.
PRECHECK = os.environ.get("HL_FACE_PRECHECK", "1") != "0"


def _detector():
    if "d" in _DET:
        return _DET["d"]
    det = None
    try:
        import mediapipe as mp
        if hasattr(mp, "solutions") and hasattr(mp.solutions, "face_detection"):
            fd = mp.solutions.face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5)
            det = ("solutions", fd)
        elif TASK_MODEL.exists():
            from mediapipe.tasks import python as mpt
            from mediapipe.tasks.python import vision
            opts = vision.FaceDetectorOptions(base_options=mpt.BaseOptions(model_asset_path=str(TASK_MODEL)),
                                              min_detection_confidence=0.5)
            det = ("tasks", vision.FaceDetector.create_from_options(opts))
        else:
            _DET["why"] = f"mediapipe has no face detector and {TASK_MODEL.name} is not in models/"
    except Exception as e:  # noqa - mediapipe missing / broken: the thumbnail uses the sharpest-frame rule, see why()
        det = None
        _DET["why"] = f"{type(e).__name__}: {str(e).splitlines()[0][:120] if str(e) else ''}"
    _DET["d"] = det
    return det


def available():
    return _detector() is not None


def why():
    """Why face detection is off ('' when it works) - the renderers print this once per thumbnail."""
    _detector()
    return _DET.get("why", "")


def _run(det, im):
    """One detector pass on a PIL RGB image -> [(x, y, w, h, score)] in that image's pixels."""
    import numpy as np
    arr = np.ascontiguousarray(np.asarray(im))
    out = []
    if det[0] == "solutions":
        res = det[1].process(arr)
        H, W = arr.shape[:2]
        for d in (res.detections or []):
            b = d.location_data.relative_bounding_box
            out.append((b.xmin * W, b.ymin * H, b.width * W, b.height * H, float(d.score[0])))
    else:
        import mediapipe as mp
        res = det[1].detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=arr))
        for d in res.detections:
            b = d.bounding_box
            out.append((b.origin_x, b.origin_y, b.width, b.height, float(d.categories[0].score)))
    return out


def _iou(a, b):
    ax1, ay1, bx1, by1 = a[0] + a[2], a[1] + a[3], b[0] + b[2], b[1] + b[3]
    iw, ih = max(0, min(ax1, bx1) - max(a[0], b[0])), max(0, min(ay1, by1) - max(a[1], b[1]))
    inter = iw * ih
    return inter / (a[2] * a[3] + b[2] * b[3] - inter + 1e-9)


def no_face_likely(im):
    """Cheap pre-check on a PIL RGB frame: True only when the frame CANNOT hold a face the detector would find.

    One mediapipe pass costs ~35 ms and detect() makes five of them, while this is a 320x180 resize and some numpy
    (~1 ms). Thumbnail candidates are full of frames that can never score: a Zoom tile with the camera off, a black
    letterbox, a slide, a flat wall. A face is always a patch of skin-coloured pixels, whatever the skin tone, so
    when no 16x16 px patch (at 720p) passes a broad skin-colour test there is nothing for mediapipe to find.
    Unsure -> False (run mediapipe): a frame with almost no colour at all (greyscale or washed-out footage) says
    nothing about skin, and so does a frame too small to probe."""
    import numpy as np
    if im.width < PROBE[0] // 2 or im.height < PROBE[1] // 2:
        return False
    a = np.asarray(im.resize(PROBE, Image.BILINEAR), dtype="float32")
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mx, mn = a.max(2), a.min(2)
    y = 0.299 * r + 0.587 * g + 0.114 * b
    if float(y.std()) < 3.0:                         # flat frame (camera off, black tile, blank slide): nothing to find
        return True
    sat = (mx - mn) / np.maximum(mx, 1.0)
    if float(np.percentile(sat, 90)) < 0.08:         # no colour in the frame: skin tone tells us nothing
        return False
    cb = -0.169 * r - 0.331 * g + 0.5 * b + 128
    cr = 0.5 * r - 0.419 * g - 0.081 * b + 128
    m = ((cr >= 133) & (cr <= 177) & (cb >= 77) & (cb <= 127) & (y > 40)        # broad YCbCr skin box (all tones)
         & (r > g) & (g > b) & (sat > 0.10) & (sat < 0.68) & (mx - mn > 12)).astype("float32")
    ii = np.zeros((m.shape[0] + 1, m.shape[1] + 1), dtype="float32")            # integral image -> densest window
    ii[1:, 1:] = m.cumsum(0).cumsum(1)
    s = ii[PROBE_WIN:, PROBE_WIN:] - ii[:-PROBE_WIN, PROBE_WIN:] - ii[PROBE_WIN:, :-PROBE_WIN] + ii[:-PROBE_WIN, :-PROBE_WIN]
    return float(s.max()) / (PROBE_WIN * PROBE_WIN) < MIN_SKIN_DENSITY


def detect(img_path):
    """-> [{"x","y","w","h","score"}] as fractions of the image (biggest x surest face first). [] when unavailable.
    The Tasks model is short-range: a face that is small in a wide court shot is missed on the whole image, so
    four overlapping 60% windows are also checked at 2x (found the defendant at 0.96 on 03p3ATnv6dY).
    Frames the cheap pre-check rules out never reach mediapipe (see no_face_likely)."""
    det = _detector()
    if not det:
        return []
    with Image.open(img_path) as _f:
        im = _f.convert("RGB")
    STATS["frames"] += 1
    if PRECHECK and no_face_likely(im):
        STATS["skipped"] += 1
        return []
    W, H = im.size
    boxes = []
    try:
        boxes += _run(det, im)
        for fx, fy in ((0, 0), (0.4, 0), (0, 0.4), (0.4, 0.4)):
            x0, y0, ww, hh = int(fx * W), int(fy * H), int(0.6 * W), int(0.6 * H)
            win = im.crop((x0, y0, x0 + ww, y0 + hh)).resize((ww * 2, hh * 2), Image.LANCZOS)
            boxes += [(x0 + x / 2, y0 + y / 2, w / 2, h / 2, sc) for x, y, w, h, sc in _run(det, win)]
    except Exception as e:  # noqa - one bad frame must not stop the thumbnail; the reason is kept for why()
        _DET["why"] = f"detection failed on {Path(img_path).name}: {type(e).__name__}: {str(e)[:100]}"
        return []
    keep = []
    for bx in sorted(boxes, key=lambda b: -b[4]):                  # same face seen twice -> keep the surer one
        if all(_iou(bx, k) < 0.3 for k in keep):
            keep.append(bx)
    # < 0.6 were mostly false hits on Boyd fixtures (shadows, a big blurry shape); rank by size x confidence
    out = [{"x": x / W, "y": y / H, "w": w / W, "h": h / H, "score": sc} for x, y, w, h, sc in keep if sc >= MIN_SCORE]
    return sorted(out, key=lambda f: -f["w"] * f["h"] * f["score"])


def face_crop_box(face, img_w, img_h, scale=3.0, aspect=16 / 9):
    """16:9 box (pixels) centred on a face, `scale` x the face height tall, clamped inside the image."""
    fh = face["h"] * img_h
    h = min(img_h, fh * scale)
    w = min(img_w, h * aspect)
    h = w / aspect
    cx = (face["x"] + face["w"] / 2) * img_w
    cy = (face["y"] + face["h"] / 2) * img_h - fh * 0.2          # a little headroom above the eyes
    x0 = min(max(0, cx - w / 2), img_w - w)
    y0 = min(max(0, cy - h / 2), img_h - h)
    return int(x0), int(y0), int(w), int(h)


def text_placement(faces, wanted="top", band=0.30):
    """Keep the title text (a band of ~30% at the top or bottom) off the main face."""
    if not faces:
        return wanted
    f = faces[0]
    top_hit = f["y"] < band
    bottom_hit = f["y"] + f["h"] > 1 - band
    if wanted == "top" and top_hit and not bottom_hit:
        return "bottom"
    if wanted != "top" and bottom_hit and not top_hit:
        return "top"
    return wanted
