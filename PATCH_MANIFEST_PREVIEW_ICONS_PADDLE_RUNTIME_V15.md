# Twinscopes Preview Controls & PaddleOCR Runtime — v15

## Preview controls

- Replaced CSS-mask placeholders with real inline SVG controls.
- Added stable local icons for previous/next, zoom, reset, rotate, focus, shop,
  appointment, share, fullscreen, views, back and tour information.
- Fixed the rule that hid every `<span>` inside `.control-btn`.
- Moved Tour information from the floating top-left button into the bottom
  command dock.
- The information card opens above the dock on desktop and mobile.
- No remote icon CDN is required.

## PaddleOCR runtime

- PaddleOCR is now enabled only when both `paddleocr` and the `paddle`
  inference runtime are installed.
- A missing `paddlepaddle` package no longer starts model downloads and then
  prints a full Python traceback.
- Point inspection continues with YOLO plus semantic vision when local OCR is
  unavailable.
- Added `PADDLEOCR_RUNTIME_READY` to `check_ai_stack`.
- Added `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True` to Docker Compose and the
  local setup script.

## Local runtime check

```bash
source .venv/bin/activate
python -m pip install paddlepaddle==3.3.0 \
  -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
python -m pip install "paddleocr>=3.0,<4"
python -c "import paddle, paddleocr; print('Paddle:', paddle.__version__); print('PaddleOCR: OK')"
python manage.py check_ai_stack
```

## Deployment

```bash
docker compose build django ai_worker
docker compose up -d django ai_worker
docker compose exec django python manage.py collectstatic --noinput
docker compose exec django python manage.py check
docker compose exec ai_worker python manage.py check_ai_stack
```
