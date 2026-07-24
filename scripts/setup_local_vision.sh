#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"

"$PYTHON_BIN" -m venv "$VENV_DIR"
# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"
export PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt

# PaddleOCR is split into the OCR package and its inference engine. The
# official CPU package index also works for Apple Silicon in supported Python
# environments. Failure is non-fatal so YOLO/Gemini/OpenAI can still be tested.
if ! python -c 'import paddle' >/dev/null 2>&1; then
  python -m pip install "paddlepaddle==3.3.0" \
    -i https://www.paddlepaddle.org.cn/packages/stable/cpu/ || true
fi
python -m pip install "paddleocr>=3.0,<4"

if ! python -c 'import paddle' >/dev/null 2>&1; then
  echo
  echo "PaddlePaddle is not installed yet for this Python/CPU combination."
  echo "YOLO, Gemini Vision and OpenAI Vision can still run in partial mode."
fi

if [[ ! -f .env ]]; then
  cp .env.local.example .env
  echo "Created .env from .env.local.example. Add your credentials before live tests."
fi

python manage.py download_tour_ai_models
python manage.py migrate
python manage.py check_ai_stack

echo
echo "Local Twinscopes Vision environment is ready."
echo "Run a real provider test with: python manage.py check_ai_stack --live"
