#!/bin/bash
# H Labs - setup / repair on a Mac (double-click, or: bash "Setup Mac.command"). Safe to run again.
# Same idea as Setup.bat on Windows: Python 3.12 + the exact packages from uv.lock go into THIS folder (runtime/ and .venv/),
# whatever Python the Mac has (python.org 3.15, Homebrew, ...). Only ffmpeg comes from Homebrew.
cd "$(dirname "$0")" || exit 1
ROOT="$(pwd)"
RT="$ROOT/runtime"
UV_VER="0.9.5"
ok()   { printf "  \033[32m[ok]\033[0m %s\n" "$1"; }
warn() { printf "  \033[33m[!]\033[0m  %s\n" "$1"; }
fail() { printf "\n\033[31m[X] %s\033[0m\n    Nothing outside this folder was changed. Fix the problem above and run Setup Mac.command again.\n" "$1"; exit 1; }
step() { printf "\n\033[36m[setup] %s\033[0m\n" "$1"; }

echo "===== H Labs setup (Mac)  ($ROOT) ====="
mkdir -p "$RT" "$ROOT/state"

# ---- 1. uv (pinned, checked by SHA-256) ----
step "uv $UV_VER"
case "$(uname -m)" in
  arm64)  ARCH="aarch64-apple-darwin"; SHA="dc098ff224d78ed418e121fd374f655949d2c7031a70f6f6604eaf016a130433" ;;
  x86_64) ARCH="x86_64-apple-darwin";  SHA="58b1d4a25aa8ff99147c2550b33dcf730207fe7e0f9a0d5d36a1bbf36b845aca" ;;
  *) fail "unknown Mac CPU $(uname -m)" ;;
esac
UV="$RT/uv/uv"
if [[ -x "$UV" && "$(cat "$RT/uv/.version" 2>/dev/null)" == "$UV_VER" ]]; then
  ok "uv $UV_VER"
else
  TGZ="$RT/uv-$ARCH.tar.gz"
  curl -fsSL -o "$TGZ" "https://github.com/astral-sh/uv/releases/download/$UV_VER/uv-$ARCH.tar.gz" || fail "could not download uv (internet?)"
  [[ "$(shasum -a 256 "$TGZ" | cut -d' ' -f1)" == "$SHA" ]] || { rm -f "$TGZ"; fail "uv download is damaged (SHA-256 mismatch)"; }
  rm -rf "$RT/uv" && mkdir -p "$RT/uv" && tar -xzf "$TGZ" -C "$RT/uv" --strip-components 1 && rm -f "$TGZ"
  echo "$UV_VER" > "$RT/uv/.version"
  ok "uv $UV_VER"
fi

export UV_PYTHON_INSTALL_DIR="$RT/python" UV_CACHE_DIR="$RT/uv-cache" UV_PYTHON_PREFERENCE="only-managed"

# ---- 2. Python 3.12 + locked packages ----
step "Python 3.12 + packages from uv.lock (first time: a few minutes)"
if [[ -d "$ROOT/.venv" && ! -f "$ROOT/.venv/.hlabs-uv" ]]; then
  rm -rf "$ROOT/.venv_old" && mv "$ROOT/.venv" "$ROOT/.venv_old"
  warn "the old .venv was moved to .venv_old (delete it once everything works)"
fi
"$UV" sync --frozen --inexact --project "$ROOT" || fail "installing the Python packages failed (see above)"
touch "$ROOT/.venv/.hlabs-uv"
PY="$ROOT/.venv/bin/python"
"$UV" pip install --no-config --python "$PY" --upgrade "yt-dlp[default]" || fail "installing yt-dlp failed"
ok "python $("$PY" -c 'import platform; print(platform.python_version())')"
if [[ "$(uname -m)" == "arm64" ]]; then
  "$UV" pip install --no-config --python "$PY" mlx-whisper ocrmac >/dev/null 2>&1 \
    && ok "mlx-whisper + ocrmac (Apple Silicon: fast transcript + tile OCR)" \
    || warn "mlx-whisper / ocrmac skipped (optional)"
fi

# ---- 3. graphics browser ----
step "Chromium for the graphics"
"$PY" -m playwright install chromium || fail "Chromium download failed"
ok "chromium"

# ---- 4. ffmpeg (Homebrew) + face model ----
step "ffmpeg"
if command -v ffmpeg >/dev/null; then
  ok "ffmpeg $(ffmpeg -version | head -1 | cut -d' ' -f3)"
  ffmpeg -hide_banner -filters 2>/dev/null | grep -q " subtitles " || warn "this ffmpeg has no libass (burned-in captions): brew install ffmpeg-full"
else
  warn "ffmpeg missing: install Homebrew (brew.sh), then:  brew install ffmpeg-full   (and run this setup again)"
fi
mkdir -p "$ROOT/models"
[[ -f "$ROOT/models/blaze_face_short_range.tflite" ]] || curl -fsSL -o "$ROOT/models/blaze_face_short_range.tflite" \
  "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite" \
  || warn "face model skipped (thumbnails still work)"

# ---- 5. keys (only these two; they stay in ~/.config/umf, never in the folder) ----
step "API keys"
KD="$HOME/.config/umf"
mkdir -p "$KD"
for pair in "hive.env:HIVE_API_KEY:Hive" "ai33.env:AI33_API_KEY:ai33 (AI voice)"; do
  IFS=: read -r f var label <<< "$pair"
  cur="$(grep -E "^\s*$var\s*=" "$KD/$f" 2>/dev/null | head -1 | cut -d= -f2- | tr -d ' "')"
  if [[ -n "$cur" ]]; then ok "$label key is set"; continue; fi
  read -r -p "  Paste the $label key (Enter = later): " val
  printf "%s=%s\n" "$var" "$val" > "$KD/$f"
  [[ -n "$val" ]] && ok "$label key saved" || warn "$label key still empty - add it to $KD/$f"
done

# ---- 6. check ----
step "checking the installation"
"$PY" tools/launcher.py --check
n=$?
echo
if [[ $n -eq 0 ]]; then
  printf "\033[32m===== READY =====\033[0m  Double-click  'H Labs.command'  to start.\n"
else
  printf "\033[33m===== %s problem(s) above =====\033[0m  Fix the [FAIL] lines, then run the check again.\n" "$n"
fi
