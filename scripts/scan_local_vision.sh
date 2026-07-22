#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
fi

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.dev}"

if [[ ! -f .env ]]; then
  echo "ERROR: .env is missing. Copy .env.local.example to .env and configure the credentials." >&2
  exit 2
fi

REPORT_DIR="${VISION_REPORT_DIR:-vision_reports}"
mkdir -p "$REPORT_DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"

printf '\n[1/4] Django migrations\n'
python manage.py migrate

printf '\n[2/4] Local AI/CV diagnostics\n'
python manage.py check_ai_stack

printf '\n[3/4] Synchronous scan of existing scenes\n'
if [[ $# -eq 0 ]]; then
  python manage.py analyze_existing_scenes \
    --mode sync \
    --providers yolo,paddleocr,gemini,openai \
    --json-report "$REPORT_DIR/local-scan-$STAMP.json"
else
  python manage.py analyze_existing_scenes \
    --mode sync \
    --providers yolo,paddleocr,gemini,openai \
    --json-report "$REPORT_DIR/local-scan-$STAMP.json" \
    "$@"
fi

printf '\n[4/4] Final scene inventory\n'
python manage.py analyze_existing_scenes --status-only

printf '\nDone. JSON report: %s/local-scan-%s.json\n' "$REPORT_DIR" "$STAMP"
