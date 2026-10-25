"""The 'brain' step = Master Prompt v9 run by Claude. Script-computed Pass 1/2 are injected so nothing is missed,
and every reply is validated; failures go back to the model (up to max_repair_rounds)."""
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

from . import validate as VAL
from .config import style_path
from .timeutil import fmt_tc

ROOT = Path(__file__).resolve().parent.parent
# ---------------------------------------------------------------- usage + cost ledger
# USD per 1M tokens: (input, output, cache_write_5m, cache_read). Source: platform.claude.com/docs/en/about-claude/pricing
# (checked 2026-10-25). Override or add models in config.json -> "prices": {"model-id": [in, out, cw, cr]}.
PRICES = {
    "claude-sonnet-5-5": (2.0, 10.0, 2.5, 0.10),
    "claude-sonnet-4-6": (3.0, 15.0, 3.75, 0.30),
    "claude-sonnet-4-5": (3.0, 15.0, 3.75, 0.30),
    "claude-opus-5-5":   (4.0, 20.0, 5.0, 0.20),
    "claude-haiku-4-5":  (1.0, 5.0, 1.25, 0.10),
}
USAGE = []      # one dict per API call: model, label, input, output, cache_write, cache_read, cost


def _price(model, cfg):
    p = (cfg or {}).get("prices", {}).get(model) or PRICES.get(model)
    return tuple(p) if p else None


def record_usage(cfg, model, u, label=""):
    """u = {"input", "output", "cache_write", "cache_read"} token counts for one call."""
    row = {"model": model, "label": label or cfg.get("_usage_label", ""), **{k: int(u.get(k) or 0) for k in
           ("input", "output", "cache_write", "cache_read")}}
    p = _price(model, cfg)
    row["cost"] = None if not p else round((row["input"] * p[0] + row["output"] * p[1] + row["cache_write"] * p[2]
                                            + row["cache_read"] * p[3]) / 1e6, 4)
    USAGE.append(row)
    return row


def usage_summary():
    """-> (lines, totals dict) for run_report / console."""
    if not USAGE:
        return ["BRAIN USAGE: no API calls this run"], {}
    t = {k: sum(r[k] for r in USAGE) for k in ("input", "output", "cache_write", "cache_read")}
    known = [r["cost"] for r in USAGE if r["cost"] is not None]
    t["cost"] = round(sum(known), 4) if known else None
    t["calls"] = len(USAGE)
    lines = [f"BRAIN USAGE ({t['calls']} calls)",
             f"  tokens  input {t['input']:,} · cache write {t['cache_write']:,} · cache read {t['cache_read']:,} · output {t['output']:,}",
             f"  cost    ${t['cost']:.2f}" + ("" if len(known) == len(USAGE) else "  (some calls have no price - add config.json 'prices')")
             if t["cost"] is not None else "  cost    unknown (no price for this model - add config.json 'prices')"]
    for r in USAGE:
        c = f"${r['cost']:.3f}" if r["cost"] is not None else "?"
        lines.append(f"    {r['label'] or '-':<22} {r['model']:<20} in {r['input']:>7,}  cw {r['cache_write']:>7,}  "
                     f"cr {r['cache_read']:>7,}  out {r['output']:>6,}  {c}")
    return lines, t


def save_usage(path):
    lines, t = usage_summary()
    try:
        Path(path).write_text(json.dumps({"totals": t, "calls": USAGE}, indent=2), encoding="utf-8")
    except Exception:
        pass
    return lines


SYSTEM = ("You are the UMF Case Build engine. You follow the CASE BUILD ORDER v9.0 exactly and answer ONLY with the "
          "requested JSON. Timecodes come from the transcript - never invent them.")


def carried_text(items):
    if not items:
        return "none"
    return "; ".join(f"{c['name']} · {c.get('source_file', '?')} · {c['in']}-{c['out']}" for c in items)


OVERRIDES = """
\u2550\u2550\u2550 OWNER OVERRIDES v9.1 (these WIN over any number below) \u2550\u2550\u2550
\u00b7 VIDEO LENGTH: every video is {rmin}\u2013{rmax} minutes (cases + hook + intro; the VO/cards add about two more minutes, so
  aim at the lower half of the band). Where Rule 4 says 20:00-40:00 or "never pad past 40:00", read {rmin}\u2013{rmax}.
\u00b7 MANY VIDEOS PER STREAM: the owner wants as many {rmin}\u2013{rmax} min videos as the stream can honestly fill. After building
  the first, keep building (Rule 4 "open a second video") until the remaining usable minutes cannot reach {rmin}.
\u00b7 INTERESTING FIRST: inside each video put the most interesting case first (judge challenging someone, a number that lands,
  an emotional break, a surprising ruling). It earns the title, the thumbnail and the hook.
\u00b7 HOOK = a TEASER: {hmin}\u2013{hmax} seconds, taken from the most important moment of the FIRST case, inside the back
  60% of its range. It plays at 0:00 labelled COMING UP. Rule 5 content rules still apply.
\u00b7 YIELD: on a plea-heavy docket the surgical IN point can leave cases too short to fill a second video. In that situation
  (and only then) start a case at the plea terms / charge explanation instead of the sentencing statement, never earlier than
  that - not the roll call, oath or discovery questions - and say so in working_note.
\u00b7 CASE START (LOCKED): every case's IN is the moment the judge calls it - "calling CR2469", "court is calling 2024 CR...",
  any case number starting with CR - NOT the plea terms or later. Put the call-out second in cause_no. Only a jury trial that is
  already under way (witness on the stand, no call-out in this stream) may set "resume": true and start at its best opening.
  This beats the YIELD rule below.
\u00b7 TRIAL TALES LOCKED STYLE (owner's own video, now the template for every output): hook teaser then the channel gavel
  intro, then Case 1 straight away (no VO-1 card; still write vo1 but it is not used). After every case except the last comes
  ONE AI recap clip = the "bridge" text: 35-40 words, 2+ sentences, reads in 13-16 s, never above 18 s. The closing "vo_final"
  is read as 2 short sentence-aligned clips, 45-70 words in total, EVERY sentence under 35 words. Every AI-voice clip must
  stay <= 18 seconds. The hook object needs a "headline": 3-9 words, no trailing period, a punchy bottom caption that is true to
  what the clip shows (e.g. "She Blamed Her Lawyer for Bad Advice").
\u00b7 Tags/channel: the channel is {channel}; the courts and judges are whatever the transcript shows.
"""


def _shared(name, cfg):
    """A v10 prompt module from prompts/shared/ (ROOT-level, shared by every style pack)."""
    p = ROOT / "prompts" / "shared" / name
    return p.read_text(encoding="utf-8") if p.exists() else ""


def build_prompt(plan_inputs, scan_text, lines, carried, cfg=None):
    cfg = cfg or {}
    master = style_path(cfg, cfg.get("_prompt_master", "prompts/master_v9.md")).read_text(encoding="utf-8")
    addendum = style_path(cfg, cfg.get("_prompt_addendum", "prompts/json_addendum.md")).read_text(encoding="utf-8")
    # v10 module chain: schema + boundary rules always; mode_all only in mode "all";
    # titles + overlays when title_system v10 is on. Placeholders filled by the script.
    judge = plan_inputs.get("judge_name") or cfg.get("judge_name", "Judge Boyd")
    fill10 = {"{JUDGE_NAME}": judge, "{CHANNEL}": plan_inputs.get("channel_name", cfg.get("channel_name", "")),
              "{MIN_CASE}": fmt_tc(float(cfg.get("min_case_minutes", 8.0)) * 60, False)}
    mods = [_shared("schema_v10.md", cfg), _shared("boundary_rules.md", cfg)]
    if cfg.get("mode") == "all":
        mods.append(_shared("mode_all.md", cfg))
    # titles/overlays modules only when the run will actually package videos (Pass B) - Pass A stays lean
    if cfg.get("title_system", "v10") == "v10" and not cfg.get("_cases_only"):
        mods.append(_shared("titles_core.md", cfg))
        tr = cfg.get("_title_rules")
        mods.append(style_path(cfg, tr).read_text(encoding="utf-8") if tr else "")
        mods.append(_shared("overlays.md", cfg))
    idx = master.rfind(" TRANSCRIPT")
    head = master
    if idx > 0:
        cut = master.rfind("\u2550" * 20, 0, idx)
        head = master[:cut] if cut > 0 else master
    ov = OVERRIDES.format(rmin=int(cfg.get("runtime_min", 1200) // 60), rmax=int(cfg.get("runtime_max", 1800) // 60),
                          hmin=int(cfg.get("hook_min", 10)), hmax=int(cfg.get("hook_max", 15)),
                          channel=plan_inputs["channel_name"])
    if cfg.get("_prompt_extra"):
        ov += style_path(cfg, cfg["_prompt_extra"]).read_text(encoding="utf-8")
    fill = {"{{SOURCE_FILE}}": plan_inputs["source_file"], "{{STREAM_LENGTH}}": plan_inputs["stream_length"],
            "{{CARRIED}}": carried_text(carried), "{{CHANNEL_NAME}}": plan_inputs["channel_name"]}
    for k, v in fill.items():
        head = head.replace(k, v)
        addendum = addendum.replace(k, v)
    v10 = ""
    for m in mods:
        if m:
            for k, v in fill10.items():
                m = m.replace(k, v)
            v10 += "\n\n" + m
    bev = cfg.get("_boundary_evidence")
    if bev:
        v10 += "\n\n" + "═" * 64 + "\n BOUNDARY EVIDENCE (script-computed, trust these timecodes)\n" + "═" * 64 + "\n" + bev
    bar = "\u2550" * 64
    return (head + ov + addendum + v10 + "\n" + bar + "\n SCRIPT-COMPUTED SCAN (trust these timecodes)\n" + bar + "\n"
            + scan_text + "\n\n" + bar + "\n TRANSCRIPT  ([H:MM:SS] = stream clock)\n" + bar + "\n"
            + "\n".join(lines) + "\n\nNow output the single JSON object.")


def _stream_anthropic(messages, cfg, on_text=None):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY missing. Put it in ~/.config/umf/anthropic.env as ANTHROPIC_API_KEY=... "
                           "or use --brain manual (paste the prompt into Claude, save the JSON reply, pass --plan).")
    req_body = {"model": cfg["model"], "max_tokens": int(cfg["max_tokens"]), "system": SYSTEM,
                "messages": messages, "stream": True}
    if cfg.get("disable_thinking", True):
        # on 5.x models the off-switch is "between_tools" ("disabled" is rejected by the API itself)
        req_body["thinking"] = {"type": "between_tools"}
    if _temperature_ok(cfg["model"], cfg):
        req_body["temperature"] = 0.3
    if cfg.get("prompt_cache", True):
        # automatic prompt caching: the long prompt is written once, repair rounds re-read it at ~5% of the price
        req_body["cache_control"] = {"type": "ephemeral"}
    body = json.dumps(req_body).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
        "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    out = []
    u = {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0}
    try:
        with urllib.request.urlopen(req, timeout=1800) as r:
            for raw in r:
                line = raw.decode("utf-8", "ignore").strip()
                if not line.startswith("data:"):
                    continue
                try:
                    ev = json.loads(line[5:].strip())
                except Exception:
                    continue
                typ = ev.get("type")
                if typ == "content_block_delta" and ev["delta"].get("type") == "text_delta":
                    out.append(ev["delta"]["text"])
                    if on_text:
                        on_text(len(out))
                elif typ == "message_start":
                    mu = (ev.get("message") or {}).get("usage") or {}
                    u["input"] = mu.get("input_tokens", 0)
                    u["cache_write"] = mu.get("cache_creation_input_tokens", 0) or 0
                    u["cache_read"] = mu.get("cache_read_input_tokens", 0) or 0
                    u["output"] = mu.get("output_tokens", 0) or 0
                elif typ == "message_delta":
                    du = ev.get("usage") or {}
                    if du.get("output_tokens") is not None:
                        u["output"] = du["output_tokens"]
                    for k_api, k in (("input_tokens", "input"), ("cache_creation_input_tokens", "cache_write"),
                                     ("cache_read_input_tokens", "cache_read")):
                        if du.get(k_api):
                            u[k] = du[k_api]
                elif typ == "error":
                    raise RuntimeError(_friendly_api_error(ev))
    except urllib.error.HTTPError as e:
        try:
            ev = json.loads(e.read().decode("utf-8", "ignore"))
        except Exception:
            ev = {"error": {"message": str(e)}}
        msg = ((ev.get("error") or {}).get("message") or "").lower()
        if "temperature" in msg and "temperature" in req_body:      # newer models reject sampling params: retry once
            _NO_TEMP.add(cfg["model"])
            return _stream_anthropic(messages, cfg, on_text)
        raise RuntimeError(_friendly_api_error(ev)) from None
    finally:
        if any(u.values()):
            record_usage(cfg, cfg["model"], u)
    return "".join(out)


_NO_TEMP = set()
_NO_TEMP_PREFIXES = ("claude-sonnet-5", "claude-opus-5", "claude-haiku-5", "claude-fable", "claude-mythos")


def _temperature_ok(model, cfg):
    """Claude 5.x models reject `temperature` ("deprecated for this model"); older ones accept it."""
    if cfg.get("send_temperature") is not None:
        return bool(cfg["send_temperature"])
    return model not in _NO_TEMP and not str(model).startswith(_NO_TEMP_PREFIXES)


def _friendly_api_error(ev):
    msg = ((ev or {}).get("error") or {}).get("message") or str(ev)
    low = msg.lower()
    if "credit balance" in low or "billing" in low:
        return ("Anthropic credit khatam (credit balance too low). Top up at console.anthropic.com -> Plans & Billing, "
                "or rerun with --brain deepseek / --brain manual. Saved prompts and replies are in work/<stream id>/.")
    if "overloaded" in low or "rate" in low:
        return f"Anthropic is busy or rate-limited - wait a minute and rerun ({msg})"
    if "model" in low and ("not found" in low or "invalid" in low):
        return f"Model id not accepted: {msg} - check config 'model' / provider_models"
    return f"API error: {msg}"


# Provider registry. deepseek/openai speak the OpenAI chat-completions dialect; anthropic has its own.
PROVIDERS = {
    "anthropic": {"key_env": "ANTHROPIC_API_KEY", "model": "claude-sonnet-5-5",
                  "base_url": "https://api.anthropic.com/v1/messages", "env_file": "anthropic.env"},
    "deepseek": {"key_env": "DEEPSEEK_API_KEY", "model": "deepseek-chat",
                 "base_url": "https://api.deepseek.com/chat/completions", "env_file": "deepseek.env"},
    "openai": {"key_env": "OPENAI_API_KEY", "model": "gpt-4o",
               "base_url": "https://api.openai.com/v1/chat/completions", "env_file": "openai.env"},
}


def _stream_openai_compat(messages, cfg, on_text=None):
    """Streaming chat-completions for DeepSeek / OpenAI (same SSE dialect)."""
    prov = PROVIDERS[cfg["brain"]]
    key = os.environ.get(prov["key_env"])
    if not key:
        raise RuntimeError(f"{prov['key_env']} missing. Put it in ~/.config/umf/{prov['env_file']} as "
                           f"{prov['key_env']}=... or use --brain manual / --brain mock.")
    msgs = [{"role": "system", "content": SYSTEM}] + messages
    body = json.dumps({"model": cfg["model"], "messages": msgs, "stream": True, "temperature": 0.3,
                       "max_tokens": int(cfg["max_tokens"]), "stream_options": {"include_usage": True}}).encode()
    req = urllib.request.Request(prov["base_url"], data=body, headers={
        "Authorization": f"Bearer {key}", "content-type": "application/json"})
    out = []
    with urllib.request.urlopen(req, timeout=1800) as r:
        for raw in r:
            line = raw.decode("utf-8", "ignore").strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                ev = json.loads(payload)
            except Exception:
                continue
            eu = ev.get("usage")
            if eu:
                cached = ((eu.get("prompt_tokens_details") or {}).get("cached_tokens")
                          or eu.get("prompt_cache_hit_tokens") or 0)
                record_usage(cfg, cfg["model"], {"input": (eu.get("prompt_tokens") or 0) - cached,
                                                 "cache_read": cached, "output": eu.get("completion_tokens") or 0})
            for ch in ev.get("choices", []) or []:
                delta = ch.get("delta", {}) or {}
                piece = delta.get("content")
                if piece:
                    out.append(piece)
                    if on_text:
                        on_text(len(out))
                if ch.get("finish_reason") == "length":
                    raise RuntimeError("model hit max_tokens before finishing the JSON - raise config max_tokens")
    return "".join(out)


def _stream_mock(messages, cfg, on_text=None):
    """Offline test provider: pops cfg['_mock_queue'] (per-pass reply files), then cfg['mock_reply_file'],
    else echoes the last user text. Zero network."""
    q = cfg.get("_mock_queue")
    if q:
        return Path(q.pop(0)).read_text(encoding="utf-8")
    f = cfg.get("mock_reply_file")
    if f:
        return Path(f).read_text(encoding="utf-8")
    return messages[-1]["content"]


def _stream_any(messages, cfg, on_text=None):
    brain = cfg.get("brain", "anthropic")
    if brain == "anthropic":
        return _stream_anthropic(messages, cfg, on_text)
    if brain in ("deepseek", "openai"):
        return _stream_openai_compat(messages, cfg, on_text)
    if brain == "mock":
        return _stream_mock(messages, cfg, on_text)
    raise RuntimeError(f"unknown brain provider: {brain}")


def extract_json(text):
    m = re.search(r"```json\s*(\{.*\})\s*```", text, re.S)
    s = m.group(1) if m else text[text.find("{"): text.rfind("}") + 1]
    return json.loads(s)


def make_plan(prompt, stream_len, segs, cfg, ui=print, save_dir=None):
    msgs = [{"role": "user", "content": prompt}]
    plan, errs, warns = None, [], []
    for rnd in range(int(cfg["max_repair_rounds"]) + 1):
        ui(f"  asking {cfg.get('brain', 'anthropic')} ({cfg['model']}) round {rnd + 1}...")
        cfg["_usage_label"] = f"plan r{rnd + 1}"
        txt = _stream_any(msgs, cfg, on_text=lambda n: n % 400 == 0 and ui(f"    ...{n} chunks"))
        if save_dir:
            (Path(save_dir) / f"brain_reply_{rnd + 1}.txt").write_text(txt, encoding="utf-8")
        try:
            plan = extract_json(txt)
        except Exception as e:
            errs = [f"your reply was not valid JSON ({e}). Reply with ONE complete JSON object only."]
            msgs += [{"role": "assistant", "content": txt}, {"role": "user", "content": errs[0]}]
            continue
        errs, warns = VAL.validate(plan, stream_len, segs, cfg)
        if not errs:
            return plan, [], warns
        ui(f"  validator: {len(errs)} problem(s) -> sending back")
        fix = ("The validator rejected this plan. Fix EVERY item and return the COMPLETE corrected JSON (same schema):\n- "
               + "\n- ".join(errs[:40]))
        msgs += [{"role": "assistant", "content": txt}, {"role": "user", "content": fix}]
    return plan, errs, warns
