#!/bin/zsh
# H Labs — UMF Case Factory launcher (double-click me)
# Everything runs locally on this Mac. Keys live in ~/.config/umf/*.env (never in this folder).
set -uo pipefail
emulate -L zsh
DIR="${0:A:h}"
cd "$DIR" || exit 1
PY="$DIR/.venv/bin/python3"
[[ -x "$PY" ]] || PY="$(command -v python3)"

BRAIN_FILE="$DIR/.brain"
[[ -f "$BRAIN_FILE" ]] || echo "hive" > "$BRAIN_FILE"
STYLE_FILE="$DIR/.style"
MODE_FILE="$DIR/.mode"
[[ -f "$MODE_FILE" ]] || echo "60" > "$MODE_FILE"

pick_mode() {
  echo
  echo "Video mode for this run:"
  echo "  1) 30 min video   (v9 bundles, 20-40 min)"
  echo "  2) 1 hour video   (v9 bundles, 50-70 min)"
  echo "  3) All cases      (every case >= 8:00 becomes its own video, ranked)"
  local def=2
  [[ -f "$MODE_FILE" ]] && { case "$(cat "$MODE_FILE")" in 30) def=1;; 60) def=2;; all) def=3;; esac; }
  printf "Pick [1-3, Enter=%d]: " $def
  read -r m
  [[ -z "$m" ]] && m=$def
  case "$m" in 1) echo "30" > "$MODE_FILE";; 3) echo "all" > "$MODE_FILE";; *) echo "60" > "$MODE_FILE";; esac
  echo "mode: $(cat "$MODE_FILE")"
}

list_styles() {
  local i=1
  for f in "$DIR"/styles/*/style.json(N); do
    local id name
    id=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('id','?'))" "$f" 2>/dev/null)
    name=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('name','?'))" "$f" 2>/dev/null)
    echo "  $i) $id  ($name)"
    i=$((i+1))
  done
}

pick_style() {
  local styles=("$DIR"/styles/*/style.json(N))
  [[ ${#styles[@]} -eq 0 ]] && { echo "no style packs found"; return 1; }
  echo
  echo "Editing style for this run:"
  list_styles
  local def=1
  [[ -f "$STYLE_FILE" ]] && { local cur; read -r cur < "$STYLE_FILE"; local i=1
    for f in $styles; do local id; id=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('id','?'))" "$f" 2>/dev/null)
      [[ "$id" == "$cur" ]] && def=$i; i=$((i+1)); done; }
  printf "Pick [1-%d, Enter=%d]: " ${#styles[@]} $def
  read -r s
  [[ -z "$s" ]] && s=$def
  local f=${styles[$s]}
  local id
  id=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('id','?'))" "$f" 2>/dev/null)
  echo "$id" > "$STYLE_FILE"
  echo "style: $id"
}

set_brain() {
  echo
  echo "Choose the brain provider (writes the plan JSON from the transcript):"
  echo "  1) Hive - DeepSeek V4.1 Flash   - default, ~\$0.01/video, Claude fixes the cases it cannot"
  echo "  2) Anthropic (Claude)           - best quality, ~\$0.34/video"
  echo "  3) DeepSeek direct              - backup if Hive is down"
  echo "  4) OpenAI (GPT)"
  echo "  5) manual                       - pipeline writes the prompt, you paste it into any chat, run again with the plan"
  printf "Pick 1-5: "
  read -r b
  case "$b" in
    1) echo "hive"      > "$BRAIN_FILE";;
    2) echo "anthropic" > "$BRAIN_FILE";;
    3) echo "deepseek"  > "$BRAIN_FILE";;
    4) echo "openai"    > "$BRAIN_FILE";;
    5) echo "manual"    > "$BRAIN_FILE";;
    *) echo "keeping current: $(cat "$BRAIN_FILE")"; return;;
  esac
  echo "Brain set to: $(cat "$BRAIN_FILE")"
}

ask_confirm_tts() {
  echo
  printf "Allow AI voiceover over 5,000 characters this run? (owner rule - type yes): "
  read -r a
  [[ "$a" == "yes" ]] || [[ "$a" == "y" ]]
}

while true; do
  echo
  echo "=============================================="
  echo "  H LABS  -  UMF Case Factory"
  echo "  brain: $(cat "$BRAIN_FILE")   |   style: $(cat "$STYLE_FILE" 2>/dev/null || echo trial_tales)   |   mode: $(cat "$MODE_FILE" 2>/dev/null || echo 60)"
  echo "  output: $DIR/output"
  echo "=============================================="
  echo "  1) New video from a YouTube stream URL (full pipeline)"
  echo "  2) Local file mode (already downloaded / pre-cut clips)"
  echo "  3) Change brain provider"
  echo "  4) Edit API keys (~/.config/umf/*.env)"
  echo "  5) Open output folder"
  echo "  6) Run self-test (10 checks)"
  echo "  q) Quit"
  printf "Pick: "
  read -r pick
  case "$pick" in
    1)
      printf "YouTube URL: "; read -r url
      [[ -z "$url" ]] && continue
      pick_style || continue
      pick_mode
      extra=()
      ask_confirm_tts && extra+=(--confirm-tts)
      "$PY" run_stream.py "$url" --brain "$(cat "$BRAIN_FILE")" --style "$(cat "$STYLE_FILE" 2>/dev/null || echo trial_tales)" --mode "$(cat "$MODE_FILE" 2>/dev/null || echo 60)" "${extra[@]}"
      echo; echo "Done. Output is in $DIR/output"; read -r "?Press Enter..."
      ;;
    2)
      printf "Video file path (or leave empty if using pre-cut clips): "; read -r vf
      printf "Stream ID (e.g. lVQ79x0Hd_w): "; read -r sid
      printf "Stream length H:MM:SS: "; read -r slen
      printf "Transcript file (empty = reuse work/<id>/transcript.json): "; read -r tr
      pick_style || continue
      pick_mode
      extra=()
      [[ -n "$vf" ]] && extra+=(--video-file "$vf")
      [[ -n "$slen" ]] && extra+=(--stream-length "$slen")
      [[ -n "$tr" ]] && extra+=(--transcript-file "$tr")
      ask_confirm_tts && extra+=(--confirm-tts)
      "$PY" run_stream.py --stream-id "$sid" --brain "$(cat "$BRAIN_FILE")" --style "$(cat "$STYLE_FILE" 2>/dev/null || echo trial_tales)" --mode "$(cat "$MODE_FILE" 2>/dev/null || echo 60)" "${extra[@]}"
      echo; read -r "?Press Enter..."
      ;;
    3) set_brain;;
    4) "$EDITOR" "$HOME/.config/umf/hive.env" "$HOME/.config/umf/anthropic.env" "$HOME/.config/umf/deepseek.env" \
         "$HOME/.config/umf/openai.env" "$HOME/.config/umf/ai33.env" 2>/dev/null \
       || open -e "$HOME/.config/umf/hive.env" "$HOME/.config/umf/anthropic.env" "$HOME/.config/umf/deepseek.env" \
                "$HOME/.config/umf/openai.env" "$HOME/.config/umf/ai33.env";;
    5) open "$DIR/output" 2>/dev/null || open "$DIR";;
    6) "$PY" tests/run_tests.py; echo; read -r "?Press Enter...";;
    q|Q|"") exit 0;;
  esac
done
