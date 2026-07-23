#!/usr/bin/env bash
# Transcode videos under a directory to browser/webview-playable H.264 mp4.
#
# Why: clips cut by the demo pipeline are often mpeg4 (DivX-style), which the
# Chromium <video> element used by VSCode previews / dashboards cannot decode.
# H.264 plays everywhere.
#
# Output mirrors the source tree under <dir>/h264/:
#   <dir>/cam_child/2026-07-10/foo.mp4  ->  <dir>/h264/cam_child/2026-07-10/foo.mp4
#
# Usage:
#   ./transcode-to-h264.sh <dir>            # transcode every video under <dir>
#   ./transcode-to-h264.sh <dir> --watch    # keep running; transcode new/changed files
#   ./transcode-to-h264.sh <dir> --force    # re-transcode even if output is up to date
#   ./transcode-to-h264.sh --help
#
# Env:
#   CRF=23         # x264 quality (lower = better/larger, 18-28 sane range)
#   PRESET=veryfast
#   POLL_SECS=5    # --watch poll interval when inotifywait is unavailable
#   SETTLE_SECS=3  # skip files modified this recently (still being written)
#   OUT_SUBDIR=h264

set -euo pipefail

CRF="${CRF:-23}"
PRESET="${PRESET:-veryfast}"
POLL_SECS="${POLL_SECS:-5}"
SETTLE_SECS="${SETTLE_SECS:-3}"
OUT_SUBDIR="${OUT_SUBDIR:-h264}"

# Video extensions we attempt to transcode (case-insensitive).
VIDEO_EXTS="mp4 mkv mov avi ts m4v webm flv wmv mpg mpeg 3gp h264 264"

usage() { sed -n '2,29p' "$0"; }

command -v ffmpeg  >/dev/null || { echo "ffmpeg not found in PATH" >&2; exit 1; }
command -v ffprobe >/dev/null || { echo "ffprobe not found in PATH" >&2; exit 1; }

WATCH=0
FORCE=0
SRC_ROOT=""
for arg in "$@"; do
  case "$arg" in
    --watch) WATCH=1 ;;
    --force) FORCE=1 ;;
    -h|--help) usage; exit 0 ;;
    -*) echo "unknown option: $arg" >&2; usage; exit 1 ;;
    *)
      if [[ -n "$SRC_ROOT" ]]; then echo "only one directory allowed" >&2; exit 1; fi
      SRC_ROOT="$arg" ;;
  esac
done

[[ -n "$SRC_ROOT" ]] || { echo "error: no directory given" >&2; usage; exit 1; }
[[ -d "$SRC_ROOT" ]] || { echo "error: not a directory: $SRC_ROOT" >&2; exit 1; }

# Absolute, symlink-resolved root so relative-path math is stable.
SRC_ROOT="$(cd "$SRC_ROOT" && pwd -P)"
OUT_ROOT="$SRC_ROOT/$OUT_SUBDIR"

# Build a case-insensitive find expression for the video extensions.
build_find_expr() {
  local first=1
  FIND_EXPR=()
  for ext in $VIDEO_EXTS; do
    if (( first )); then first=0; else FIND_EXPR+=(-o); fi
    FIND_EXPR+=(-iname "*.$ext")
  done
}
build_find_expr

# List candidate video files (NUL-separated), excluding the output tree itself.
list_videos() {
  find "$SRC_ROOT" -type d -path "$OUT_ROOT" -prune -o \
       -type f \( "${FIND_EXPR[@]}" \) -print0
}

# Transcode one file. Skips if output is newer than source (unless --force).
# If the source video is already H.264 we stream-copy instead of re-encoding.
transcode_one() {
  local src="$1"

  # File may have been rotated/removed by the live recorder between listing
  # and now — skip quietly rather than counting it as a failure.
  [[ -f "$src" ]] || return 0

  # Robust relative path (handles any prefix/symlink quirk cleanly).
  local rel
  rel="$(realpath -m --relative-to="$SRC_ROOT" "$src")"
  case "$rel" in
    ..*|/*) echo "  skip (outside root) $src" >&2; return 0 ;;
  esac
  local base_noext="${rel%.*}"
  local dst="$OUT_ROOT/$base_noext.mp4"

  if (( ! FORCE )) && [[ -f "$dst" && "$dst" -nt "$src" ]]; then
    return 0
  fi

  mkdir -p "$(dirname "$dst")"

  local vcodec
  vcodec="$(ffprobe -v error -select_streams v:0 \
            -show_entries stream=codec_name -of csv=p=0 "$src" 2>/dev/null || true)"

  local vargs
  if [[ "$vcodec" == "h264" ]]; then
    vargs=(-c:v copy)
  else
    vargs=(-c:v libx264 -preset "$PRESET" -crf "$CRF" -pix_fmt yuv420p)
  fi

  # Tmp name keeps a .mp4 suffix; ffmpeg also gets -f mp4 so the muxer never
  # depends on the (unusual) tmp extension.
  local tmp="${dst%.mp4}.part.$$.mp4"
  local err
  if err="$(ffmpeg -y -hide_banner -loglevel error -i "$src" \
       "${vargs[@]}" -c:a aac -movflags +faststart -f mp4 "$tmp" 2>&1)"; then
    mv -f "$tmp" "$dst"
    echo "  ok   $rel"
    return 0
  else
    rm -f "$tmp"
    # Show the last ffmpeg error line so failures are self-explanatory
    # (e.g. a partially-written live segment: "moov atom not found").
    echo "  FAIL $rel — ${err##*$'\n'}" >&2
    return 1
  fi
}

# True if the file hasn't been modified within the last SETTLE_SECS — i.e. the
# writer (live recorder) is very likely done with it.
is_settled() {
  local src="$1" now mtime
  now="$(date +%s)"
  mtime="$(stat -c %Y "$src" 2>/dev/null || echo 0)"
  (( now - mtime >= SETTLE_SECS ))
}

run_batch() {
  local total=0 ok=0 fail=0 skipped=0
  while IFS= read -r -d '' src; do
    total=$((total+1))
    if ! is_settled "$src"; then
      echo "  wait ${src#"$SRC_ROOT"/} (modified <${SETTLE_SECS}s ago, still writing?)"
      skipped=$((skipped+1))
      continue
    fi
    if transcode_one "$src"; then ok=$((ok+1)); else fail=$((fail+1)); fi
  done < <(list_videos)
  echo
  echo "summary: scanned=$total ok/skip-done=$ok in-progress-skipped=$skipped failed=$fail  ->  $OUT_ROOT"
}

run_watch() {
  echo "watching $SRC_ROOT (Ctrl-C to stop); output -> $OUT_ROOT"
  if command -v inotifywait >/dev/null; then
    # Event-driven: react to files finished writing / moved into place.
    inotifywait -m -r -e close_write -e moved_to --format '%w%f' \
        --exclude "^$OUT_ROOT/" "$SRC_ROOT" | while IFS= read -r path; do
      [[ -f "$path" ]] || continue
      local lc="${path,,}"
      for ext in $VIDEO_EXTS; do
        if [[ "$lc" == *".$ext" ]]; then
          transcode_one "$path" || true
          break
        fi
      done
    done
  else
    echo "  (inotifywait not found; polling every ${POLL_SECS}s — apt install inotify-tools for instant)"
    while true; do
      run_batch >/dev/null || true
      sleep "$POLL_SECS"
    done
  fi
}

if (( WATCH )); then
  run_watch
else
  run_batch
fi
