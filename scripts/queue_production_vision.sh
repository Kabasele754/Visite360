#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.prod}"
REPORT_DIR="${VISION_REPORT_DIR:-vision_reports}"
mkdir -p "$REPORT_DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"

python manage.py migrate
python manage.py check_ai_stack

if [[ $# -eq 0 ]]; then
  python manage.py analyze_existing_scenes \
    --mode celery \
    --providers yolo,paddleocr,gemini,openai \
    --json-report "$REPORT_DIR/production-queue-$STAMP.json"
else
  python manage.py analyze_existing_scenes \
    --mode celery \
    --providers yolo,paddleocr,gemini,openai \
    --json-report "$REPORT_DIR/production-queue-$STAMP.json" \
    "$@"
fi

printf 'Queued. Report: %s/production-queue-%s.json\n' "$REPORT_DIR" "$STAMP"
