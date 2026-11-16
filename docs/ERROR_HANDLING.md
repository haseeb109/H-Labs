# Error handling audit (owner priority #3, 2026-11-15)

The team used to see "run finished, output folder empty" and had to send logs. The rule now, for every
`except` in `run_stream.py`, `ucf/*.py`, `tools/launcher.py`, `tools/studio/server.py`:

* **(a) best-effort extra** (thumbnail, contact sheet, notification, captions, overlays, caches, statistics): may go on, but
  prints one line `  X skipped: <cause>` and, where a video result exists, records it in `qc.json` (`"note"`, `"ok": false`).
* **(b) affects the delivered video** (download, transcript, plan, a segment, join, watermark, upload list, cleanup): stops
  with a message that names the cause and the file to send (`work/<id>/run_log.txt`).
* **(c)** never `except Exception: pass`.
* Deliberate, documented behaviour (one broken video must not cost the others; ai33 retries; whisper fallbacks; Pass B
  needs_review) is kept - only the cause is printed now.
* The exception type is narrowed where only one kind is expected.

`run_stream.cause(e)` gives the one line used everywhere: `KeyError: 'in' (boundary.py:136)` - exception class, last line of
the message (ffmpeg puts the real error there) and file:line, so the log holds enough to find it without a traceback.

Line numbers are those of this commit. Out of scope (another agent is refactoring them): `styles/*/engine/*.py`.

## Sites changed

| file:line | before | after | why |
|---|---|---|---|
| run_stream.py:46 | `_Tee.write`: `except Exception: pass` - the run log silently stopped being written | `except (OSError, ValueError)`: one `WARNING: run_log.txt is not being written (...)` on the console, then the run goes on | the team is asked for run_log.txt; it must not be silently empty |
| run_stream.py:123 | - | new `cause(e)` helper (type, last message line, file:line) | every "skipped" line names where it broke |
| run_stream.py:275 | `download.info` failed with `--stream-id` given: swallowed, `meta` stayed `{}` with no word | narrowed to `(RuntimeError, OSError, ValueError)`; prints `stream info skipped: <cause> - going on with --stream-id ...` | the title / upload date then come from meta.json; the user should know why |
| run_stream.py:333 | re-download failure `except Exception` | `(RuntimeError, OSError)` (what `fetch_video` / `os.replace` raise); the message was already printed | narrowing only |
| run_stream.py:411 | `evidence skipped: <e>` (message only, no type / location) | `  evidence skipped: <cause> - the brain plans from the transcript alone` | (a) says what it costs |
| run_stream.py:455 | `_len(c)` `except Exception: return 0` | `(KeyError, TypeError, ValueError)` | narrowing (only bad / missing timecodes expected) |
| run_stream.py:492 | a saved plan that is not JSON raised a raw traceback | `STOP: <file> is not valid JSON (...) - fix the file or delete it so the brain plans again` | (b) names the file |
| run_stream.py:497 | a plan with a missing field (`hook.in`, `case.out` ...) surfaced as a `KeyError` in the middle of the render | `ucf.schema.check_plan` right after the load: `STOP: the plan <file> has the wrong shape: video 2 hook: missing field 'in' ...` + run_log.txt | (b) owner priority #5 |
| run_stream.py:517 | `boundary refinement skipped: <e>` but the plan was left in whatever half-refined state the exception left it | plan restored from the snapshot + re-validated, `  boundary refinement skipped: <cause> - the brain's case OUT times are used as they are` | latent bug: a partially refined plan could have been rendered |
| run_stream.py:554 | `contact sheet skipped: <e>` | `  contact sheet skipped: <cause> - check case IN/OUT in plan_report.txt instead` | (a) |
| run_stream.py:636 | VO prefetch thread: `except Exception: pass` | `  voice prefetch for video N skipped: <cause>` (the renderer still makes the line itself, as documented) | (c); behaviour kept |
| run_stream.py:650 | `rn.log = []` | `rn.log, rn.notes = [], []` | renderer-side skipped extras are collected per video |
| run_stream.py:680 | `rn.thumbnail(...)` outside any try: a thumbnail problem failed the whole (finished) video | `  thumbnail skipped: <cause> - pick a frame from .../thumbnail_candidates by hand`, `qc.note`, `qc.ok=false` | (a): a 60 min render must not be lost over a jpg |
| run_stream.py:690 | `rn.contact_sheet(...)` outside any try | `  contact sheet skipped: <cause>`, `qc.note` | (a) |
| run_stream.py:694 | - | `rn.notes` (overlays / captions skipped) -> `qc.note`, `qc.ok=false` | (a): recorded on the video result |
| run_stream.py:705, 708 | `qc.note` overwritten by the watermark / chapter note | notes are joined with `; ` | a thumbnail note was lost when a watermark note followed |
| run_stream.py:727 | `VIDEO N FAILED: <last message line>` | `VIDEO N FAILED: <cause>` (adds the exception type and file:line); traceback still printed; behaviour kept (next video goes on) | documented 2026-11-05 rule kept |
| run_stream.py:770 | `sys.exit(1)` when every video failed - no message | `STOP: no video was made - every video of this run failed (first cause: ...). Send work/<id>/run_log.txt; rerun with --only <n> after the fix.` | (b) "output folder empty" now says why |
| run_stream.py:812 | clips: `CLIP N FAILED: <msg> - going on`, no traceback, not in the run report, cleanup ran anyway | traceback into the log, `failed` list -> run_report.txt lines, cleanup skipped when a clip failed (the stream is needed for the rerun), `STOP: no clip was made (...)` when none came out | latent bug: a failed clip deleted the source it needs for the rerun |
| ucf/config.py:129 | `_find_style_dir`: `except Exception: continue` | `(OSError, ValueError, AttributeError)` | narrowing (unreadable / broken / non-object style.json) |
| ucf/config.py:138-186 | plain `json.loads` of config.json / style.json (raw traceback on a missing comma); unknown keys and wrong types silently took the default | `RuntimeError("config.json is not valid JSON (...)")`; `schema.check_config` / `check_style`: `CONFIG WARNING: ... unknown key 'min_hieght' - did you mean 'min_height'?`, `CONFIG ERROR: ... 'x264_crf' must be number ... got text` -> `RuntimeError` before anything is downloaded | owner priority #5 |
| ucf/config.py:215 | `style_list`: `except Exception` | `(OSError, ValueError, AttributeError)` | narrowing |
| ucf/boundary.py:28 | Zoom tile events of a window: `except Exception: done.append(key)` - silent | reason kept in `ev["tile_errors"]`; `refine_plan` prints `boundary: Zoom tile reading skipped for window <a>-<b> (transcript signals only there)` | (a) a lost signal is now visible |
| ucf/brain.py:71 | `save_usage`: `except Exception: pass` | `except OSError`: `usage.json skipped: <e>` | (c) |
| ucf/brain.py:212, 374 | SSE chunk `json.loads` `except Exception: continue` | `except ValueError` | narrowing (keep-alive / partial lines are expected) |
| ucf/brain.py:239 | HTTP error body parse `except Exception` | `(ValueError, OSError)` | narrowing |
| ucf/brain.py:451 | `extract_json` `except Exception` -> repair round | `except ValueError` (what `json.loads` raises) | narrowing; repair loop kept |
| ucf/captions.py:153 | `import mlx_whisper` `except Exception` | `except ImportError as e` + the error text in the skipped line | narrowing |
| ucf/cards.py:39 | font candidates `except Exception: continue` | `except OSError` | narrowing |
| ucf/cards.py:209 | logo colour `except Exception` | `(OSError, IndexError)` | narrowing |
| ucf/cards.py:317 | contact-sheet tile `except Exception: pass` (a silently black tile) | `except OSError`: the tile says `(no frame: ...)` in red | (c): a missing frame is visible on the sheet |
| ucf/clips.py:37, 195, 245, 279 | timecode / field reads `except Exception` | `(KeyError, TypeError, ValueError)` | narrowing; documented fallbacks kept |
| ucf/download.py:103, 141 | ffprobe `except Exception` | `(OSError, ValueError, subprocess.SubprocessError)` | narrowing; `(0, 0)` is a documented "unknown" the callers handle (re-download) |
| ucf/faces.py:34, 96 | detector init / detection `except Exception: return None / []` - no way to know why faces were off | reason kept in `_DET["why"]`, new `faces.why()` for the renderers to print once per thumbnail; return values unchanged (documented fallback: sharpest frame) | (a) |
| ucf/finish.py:164 | `notify`: `except Exception: pass` | `(OSError, ValueError)`: `notification skipped: <e>` | (c) |
| ucf/finish.py:178 | `open_folder`: `except Exception: pass` | `except OSError`: `could not open the output folder (...) - it is <path>` | (c) |
| ucf/load.py:39 | `lower_priority`: `except Exception: return ""` (run_stream then printed "priority normal" as if chosen) | `(OSError, AttributeError, ImportError)`: `process priority not lowered (<e>) - the PC may feel slower during the render` | (c) |
| ucf/mode_all.py:68, 84, 148, 242 | timecode reads `except Exception` | `(KeyError, TypeError, ValueError)` / `ValueError` | narrowing |
| ucf/mode_all.py:205, 382 | Pass A / Pass B `extract_json` `except Exception` -> repair round | `(ValueError, KeyError, TypeError)` / `(ValueError, AttributeError)` | narrowing; repair loop kept |
| ucf/mode_all.py:426 | `evidence skipped: <e>` | `  evidence skipped: <type>: <e> - the brain plans from the transcript alone` | (a) |
| ucf/mode_all.py:470 | `boundary refinement skipped: <e>` | `  boundary refinement skipped: <type>: <e> - the brain's case OUT times are used as they are` (snapshot restore was already there) | (a) |
| ucf/overlay_sched.py:83 | `ref_tc` `except Exception: continue` | `(TypeError, ValueError)` | narrowing (the validator already flagged O-05) |
| ucf/render.py:232 | GPU decode probe `except Exception` -> silent CPU decode | `(OSError, subprocess.SubprocessError)`: `GPU decode check skipped (<e>) - decoding on the CPU` | (a) a slower run should say why |
| ucf/render.py:281 | - | `self.notes = []` on the base renderer | collects skipped extras for qc.json |
| ucf/render_ov.py:82, 90 | layout cache read / write `except Exception` (write: `pass`) | `(OSError, ValueError)` / `OSError`: `layout cache not saved (<e>)` | narrowing, (c) |
| ucf/render_tt.py:193 | HyperFrames overlay `except Exception: res = None` then `use_hf = False` for the rest of the run - silently | prints `animated overlay failed (<type>: <e>) - static overlays for the rest of this run` | (a): a whole run of static overlays had no explanation |
| ucf/render_tt.py:451 | `overlays skipped: <e>` | `  overlays skipped: <type>: <e> - this video has no fact / coming-up cards` + `self.notes` -> `qc.note`, QC CHECK | (a) recorded on the video |
| ucf/render_tt.py:546 | `captions skipped: <e>` | `  captions skipped: <type>: <e>` + `self.notes` | (a) recorded on the video |
| ucf/runclock.py:66 | `history`: `except Exception: pass` | `(OSError, ValueError, csv.Error)`: `run_history.csv not updated (<e>)` | (c) |
| ucf/tile_ocr.py:14, 21 | engine imports `except Exception` | `except ImportError` | narrowing |
| ucf/tile_ocr.py:51 | per-tile OCR `except Exception: continue` - silent for every tile | first failure printed once per run: `tile label OCR (<engine>) failed: ... - tile labels are not used for the boundaries of this run` | (a) |
| ucf/transcript.py:118 | `msvc_runtime_version`: `except Exception: return None` | `(OSError, AttributeError, ValueError, IndexError)` | narrowing; None = "unknown", the caller only warns |
| ucf/validate.py:33 | `_tc`: `except Exception` | `(TypeError, ValueError)` | narrowing |
| ucf/validate_v10.py:242, 252, 293, 327 | timecode parses `except Exception` | `(TypeError, ValueError)` / `(KeyError, TypeError, ValueError)` | narrowing; the error lines were already there |
| ucf/ov_gfx.py:94 | `close()`: `except Exception: pass` | kept, now commented: atexit cleanup of the headless browser, nothing left to report or retry | deliberate |
| tools/launcher.py:57 | styles menu: a pack with a broken style.json silently disappeared from the menu | `(OSError, ValueError, AttributeError)`: listed as `<folder> ? (style.json unreadable: ...)` | the typo gets fixed instead of "my style is gone" |
| tools/launcher.py:234 | queue-done notification `except Exception: pass` | `(ImportError, OSError)`: `(notification skipped: <e>)` | (c) |
| tools/studio/server.py:157 | stop: kill fallback `except Exception` | `except OSError` | narrowing |
| tools/studio/server.py:330 | git date `except Exception` | `(OSError, subprocess.SubprocessError)` | narrowing |
| tools/studio/server.py:414 | ffprobe duration `except Exception` | `(OSError, ValueError, subprocess.SubprocessError)` | narrowing |
| tools/studio/server.py:425 | styles list: a broken pack vanished | listed with `(style.json unreadable: ...)` in its name | same as the launcher |
| tools/studio/server.py:500 | `open_path`: `except Exception: pass` | `except OSError`: `could not open <p> (<e>)` | (c) |
| tools/studio/server.py:636 | "already running?" port probe `except Exception: pass` | `(OSError, ValueError)` (urllib errors are OSError, bad JSON ValueError) | narrowing; the pass is the point (try to bind) |

## Sites left as they are

| file:line | reason |
|---|---|
| run_stream.py:657 | watermark-inside-render not possible: already prints the cause and falls back to the separate pass (documented) |
| run_stream.py:674 | watermark pass failed: already prints `WATERMARK FAILED`, sets `qc.note` / `ok=false` (documented "never lose the render") |
| run_stream.py:724 | one broken video must not cost the others (2026-11-05 incident): traceback + FAILED line + `--only` hint; only the line format changed |
| ucf/mode_all.py:195, 375 | `(BrainStop, RuntimeError)` already narrow; Pass A/B attempt loop is the documented retry logic |
| ucf/mode_all.py:400 | "shape surprises become repairable, never crashes": the validator exception text goes back to the brain as a repair item (documented) |
| ucf/tts.py:126 | ai33 / voicestudio / say provider chain: every provider's error is collected in `errs` and raised as `all TTS providers failed -> ...` (documented retry logic) |
| ucf/transcript.py whisper_safe | the WHISPER_TRIES fallbacks (VAD off, float32) are documented and print each step; untouched |
| ucf/validate.py:517 | timeline build failure becomes a validator error that names the video (`cannot build timeline: <ex>`) |
| ucf/vision.py:59 | returns `(None, "vision failed: <e>")`: the reason is carried in the result the boundary code logs |
| ucf/captions.py:149 / render_ov.py:71 / tile_ocr.py:14,21 / render_tt.py:606 | `ImportError` / `OSError` checks that already print or have a documented fallback |
| tools/launcher.py:258, 331, 340, 353, 364 | `open_path` and the doctor checks print the error with the fix in the same line |
| tools/studio/server.py:253, 309, 345, 355, 579, 621 | the error text is returned to the web UI (`error` field / HTTP 500) |
| tests/run_tests.py:43 `check()` | the test runner: a failing check must never stop the matrix |

## Plan + config schema (owner priority #5) - `ucf/schema.py`

* `KNOWN_CONFIG_KEYS` = `config.DEFAULTS` + the keys config.local.json / style.json / the engines legitimately add
  (`EXTRA_CONFIG_KEYS`: every `cfg.get("...")` literal in the repo that is not a default). Keys starting with `_` are
  runtime-internal and skipped.
* `check_config(cfg, source)`: unknown key -> warning with the nearest known key (difflib), also inside `overlays` /
  `boundary`; a wrong type where DEFAULTS has int / float / bool / str / list / dict -> `ERROR:` line. `cpu_threads: "all"`
  and `mode: 60` stay allowed. `config.load()` prints every line (`CONFIG WARNING` / `CONFIG ERROR`) and raises on an error.
* `check_style(style, source)`: style.json top-level keys, then its `config` block like a config file.
* `check_plan(plan)`: the shape the renderers rely on - `cases[]` with id / name / in / out / status, `videos[]` with n /
  case_ids (existing cases) / hook{in,out,headline} / titles[] or title / vo_final{text} / bridges[]. Timecodes must parse
  with `timeutil.parse_tc`. Messages name the video / case and the field. `run_stream.stage_plan` runs it on every plan
  loaded from disk (`--plan` or the saved `plan_*.json`) before `validate.validate`.
* Test: `tests/run_tests.py` `t46_schema_and_errors` (check 46).
