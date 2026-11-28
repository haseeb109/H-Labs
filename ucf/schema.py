"""Shape checks for the three JSON inputs that used to be plain dicts: config.json / config.local.json / style.json
(check_config) and the brain's plan (check_plan). A typo used to take the default silently ("min_hieght": 480 did nothing);
now config.load() prints a warning with the nearest known key, and a wrong TYPE (a string where a number is expected)
stops the run before anything is downloaded. check_plan catches a missing / mistyped field that the renderers rely on
(id, in/out, case_ids, hook, vo_final ...) and names the video / case - it is NOT the content validator (ucf/validate.py
does the rules). stdlib only."""
import difflib

from .config import DEFAULTS
from .timeutil import parse_tc

# keys that config.local.json / style.json / the launcher legitimately add on top of DEFAULTS (every cfg.get("...") literal
# in ucf/, run_stream.py, tools/ and styles/*/engine/ that is not a DEFAULTS key). Keys starting with "_" are runtime-internal
# and never checked.
EXTRA_CONFIG_KEYS = {
    "caption_font", "caption_font_dir", "caption_font_size", "caption_margin_v", "caption_max_words", "caption_model",
    "clips_crf", "clips_dead_air_max_share", "clips_dead_air_pad", "clips_dead_air_s", "clips_hook_max", "clips_hook_min",
    "court", "court_line", "disable_thinking", "footage_post", "footage_pre", "json_mode",
    "mock_passA_replies", "mock_passB_replies", "mock_reply_file", "output_kind", "prices", "prompt_cache",
    "provider_max_tokens", "send_temperature", "sting_audio_file", "thumb_min_face_px", "yt_dlp_extra_args",
    # documentary styles (ucf/render_doc.py)
    "doc_style", "palette", "music_moods", "mix", "caption_look", "speaker_names", "beat_gap_court", "court_line_plain",
    "court_frame", "court_chunk_s", "report_repo",
}
KNOWN_CONFIG_KEYS = frozenset(DEFAULTS) | EXTRA_CONFIG_KEYS

# style.json top level (everything else a style pack wants to set goes under "config")
KNOWN_STYLE_KEYS = frozenset({"id", "name", "look", "renderer", "renderer_module", "renderer_class", "prompt_master",
                              "prompt_addendum", "prompt_extra", "title_rules", "config"})

# keys whose DEFAULTS value is one type but that accept another on purpose
_ALSO_OK = {
    "cpu_threads": (str,),          # 0 | a number | "all"
    "mode": (int,),                 # "60" or 60: apply_mode() uses str(mode)
    "watermark_text": (int, float),  # a number as watermark text is odd but harmless
}
_NUM = (int, float)


def _type_name(v):
    return {bool: "true/false", int: "number", float: "number", str: "text (in quotes)", list: "list [...]",
            dict: "object {...}"}.get(type(v), type(v).__name__)


def _type_ok(key, want, got):
    """Does `got` fit the type of the DEFAULTS value `want`? bool is checked before int (True is an int in Python)."""
    if isinstance(want, bool):
        return isinstance(got, bool) or isinstance(got, _ALSO_OK.get(key, ()))
    if isinstance(got, bool):
        return False
    if isinstance(want, _NUM):
        return isinstance(got, _NUM) or isinstance(got, _ALSO_OK.get(key, ()))
    return isinstance(got, type(want)) or isinstance(got, _ALSO_OK.get(key, ()))


def _suggest(key, known):
    m = difflib.get_close_matches(key, sorted(known), n=1, cutoff=0.7)
    return f" - did you mean '{m[0]}'?" if m else ""


def check_config(cfg, source_name, known=KNOWN_CONFIG_KEYS):
    """-> list of messages for the keys of ONE source (config.json / config.local.json / style.json "config").
    Unknown key -> a warning (the run goes on). Wrong type -> a line starting with 'ERROR:' (config.load() stops)."""
    out = []
    if not isinstance(cfg, dict):
        return [f"ERROR: {source_name}: must be one JSON object {{...}}, not {_type_name(cfg)}"]
    for k, v in cfg.items():
        if not isinstance(k, str) or k.startswith("_"):
            continue
        if k not in known:
            out.append(f"{source_name}: unknown key '{k}'{_suggest(k, known)}")
            continue
        want = DEFAULTS.get(k)
        if want is None or v is None:
            continue
        if not _type_ok(k, want, v):
            out.append(f"ERROR: {source_name}: '{k}' must be {_type_name(want)} (like {want!r}), got {_type_name(v)} {v!r}")
        elif isinstance(want, dict) and isinstance(v, dict) and k in ("overlays", "boundary"):
            for kk in v:
                if isinstance(kk, str) and not kk.startswith("_") and kk not in want:
                    out.append(f"{source_name}: unknown key '{k}.{kk}'{_suggest(kk, want)}")
    return out


def check_style(style, source_name):
    """style.json: its top-level keys, then its "config" block like a config file."""
    if not isinstance(style, dict):
        return [f"ERROR: {source_name}: must be one JSON object {{...}}"]
    out = [f"{source_name}: unknown key '{k}'{_suggest(k, KNOWN_STYLE_KEYS)}"
           for k in style if isinstance(k, str) and not k.startswith("_") and k not in KNOWN_STYLE_KEYS]
    if style.get("config") is not None:
        out += check_config(style["config"], f"{source_name} config")
    return out


def errors(messages):
    """The lines of check_config / check_style / check_plan that must stop the run."""
    return [m for m in messages if m.startswith("ERROR:")]


# ---------------------------------------------------------------- plan
def _tc_ok(v):
    try:
        parse_tc(v)
        return True
    except (TypeError, ValueError):
        return False


def _need(d, key, where, kind, out, tc=False):
    """One required field: present and of `kind` (a type or tuple); tc=True -> must parse as a timecode."""
    if key not in d or d[key] is None:
        out.append(f"{where}: missing field '{key}'")
        return False
    v = d[key]
    if tc:
        if not _tc_ok(v):
            out.append(f"{where}: '{key}' is not a timecode (H:MM:SS), got {v!r}")
            return False
        return True
    if isinstance(v, bool) and kind in (int, _NUM):
        out.append(f"{where}: '{key}' must be a number, got {v!r}")
        return False
    if not isinstance(v, kind):
        want = {str: "text", int: "a whole number", list: "a list", dict: "an object {...}"}.get(kind, "a number")
        out.append(f"{where}: '{key}' must be {want}, got {_type_name(v)} {v!r}")
        return False
    return True


def check_plan(plan):
    """-> ['ERROR: video 2: missing field ...', ...]: the structural shape the renderers rely on. Empty = shape ok."""
    E = []
    if not isinstance(plan, dict):
        return ["ERROR: plan: must be one JSON object {...} with 'cases' and 'videos'"]
    ids = set()
    for key in ("cases", "videos"):
        if not isinstance(plan.get(key), list):
            E.append(f"plan: '{key}' must be a list, got {_type_name(plan.get(key))}")
    for i, c in enumerate(plan.get("cases") or [] if isinstance(plan.get("cases"), list) else []):
        where = f"case #{i + 1}"
        if not isinstance(c, dict):
            E.append(f"{where}: must be an object {{...}}, got {_type_name(c)}")
            continue
        if _need(c, "id", where, int, E):
            where = f"case {c['id']}"
            if c["id"] in ids:
                E.append(f"{where}: duplicate case id")
            ids.add(c["id"])
        _need(c, "name", where, str, E)
        _need(c, "in", where, None, E, tc=True)
        _need(c, "out", where, None, E, tc=True)
        _need(c, "status", where, str, E)
        if _tc_ok(c.get("in")) and _tc_ok(c.get("out")) and parse_tc(c["out"]) <= parse_tc(c["in"]):
            E.append(f"{where}: 'out' {c['out']} is not after 'in' {c['in']}")
    for i, v in enumerate(plan.get("videos") or [] if isinstance(plan.get("videos"), list) else []):
        where = f"video #{i + 1}"
        if not isinstance(v, dict):
            E.append(f"{where}: must be an object {{...}}, got {_type_name(v)}")
            continue
        if _need(v, "n", where, int, E):
            where = f"video {v['n']}"
        if _need(v, "case_ids", where, list, E):
            if not v["case_ids"]:
                E.append(f"{where}: 'case_ids' is empty")
            for cid in v["case_ids"]:
                if isinstance(cid, bool) or not isinstance(cid, int):
                    E.append(f"{where}: case_ids entry {cid!r} is not a case id (whole number)")
                elif ids and cid not in ids:
                    E.append(f"{where}: case_ids names case {cid}, which is not in 'cases'")
        if _need(v, "hook", where, dict, E):
            _need(v["hook"], "in", f"{where} hook", None, E, tc=True)
            _need(v["hook"], "out", f"{where} hook", None, E, tc=True)
            _need(v["hook"], "headline", f"{where} hook", str, E)
        if "titles" in v and v["titles"] is not None:
            if _need(v, "titles", where, list, E):
                for j, t in enumerate(v["titles"]):
                    if not isinstance(t, dict) or not isinstance(t.get("text"), str):
                        E.append(f"{where}: titles[{j}] must be an object with 'text', got {t!r}"[:200])
        elif not isinstance(v.get("title"), str):
            E.append(f"{where}: missing field 'titles' (or 'title')")
        if _need(v, "vo_final", where, dict, E):
            _need(v["vo_final"], "text", f"{where} vo_final", str, E)
        for j, b in enumerate(v.get("bridges") or []):
            if not isinstance(b, dict) or not isinstance(b.get("text"), str) or "after_case_id" not in b:
                E.append(f"{where}: bridges[{j}] must be an object with 'after_case_id' and 'text'")
    return [f"ERROR: {e}" for e in E]
