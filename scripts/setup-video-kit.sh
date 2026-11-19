#!/usr/bin/env bash
# Ставит набор плагинов и скиллов для видео и дизайна. Повторный запуск безопасен.
set -u
log() { echo "[video-kit] $*" >&2; }
have_plugin() { claude plugin list 2>/dev/null | grep -q "$1"; }

if command -v claude >/dev/null; then
  for m in heygen-com/hyperframes pbakaus/impeccable anthropics/claude-plugins-official; do
    claude plugin marketplace add "$m" >/dev/null 2>&1 || true
  done
  for p in hyperframes@hyperframes impeccable@impeccable frontend-design@claude-plugins-official; do
    have_plugin "$p" || { log "plugin $p"; claude plugin install "$p" >/dev/null 2>&1 || log "fail: $p"; }
  done
fi

S="$HOME/.claude/skills"
[ -d "$S/remotion-best-practices" ] || npx -y skills@latest add remotion-dev/skills -g -y >/dev/null 2>&1 || log "fail: remotion"
[ -d "$S/design-taste-frontend" ]   || npx -y skills@latest add https://github.com/Leonxlnx/taste-skill -g -y >/dev/null 2>&1 || log "fail: taste"
[ -d "$S/emil-design-eng" ]         || npx -y skills@latest add emilkowalski/skills -g -y >/dev/null 2>&1 || log "fail: emil"

V="$HOME/video-use"
[ -d "$V" ] || git clone -q --depth 1 https://github.com/browser-use/video-use "$V"
[ -d "$V/.venv" ] || (cd "$V" && uv sync -q) || log "fail: video-use deps"
[ -f "$V/.env" ] || cp "$V/.env.example" "$V/.env"
mkdir -p "$S" && ln -sfn "$V" "$S/video-use"
# radar: глаза и уши для анализа конкурентов (.claude/skills/radar)
python3 -c "import yt_dlp, faster_whisper, instaloader, openpyxl, reportlab" 2>/dev/null || pip install -q yt-dlp faster-whisper instaloader openpyxl reportlab >/dev/null 2>&1 || log "fail: radar deps"
command -v ffmpeg >/dev/null || log "нет ffmpeg: winget install ffmpeg / brew install ffmpeg / apt install ffmpeg"
log "ok"
