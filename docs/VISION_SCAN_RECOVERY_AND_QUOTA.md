# Vision scan recovery and cloud quota control

This patch addresses two failures observed during a local 20-scene scan:

1. `PIL.UnidentifiedImageError` on older `PureShot` scene assets.
2. `429 RESOURCE_EXHAUSTED` from Gemini Vision during bulk semantic analysis.

## Image recovery

The vision engine now checks every scene image in this order:

1. `image_360_original`
2. `image_360`
3. `image_360_mobile`
4. `image_360_preview`
5. `thumbnail_image` (last-resort visual fallback)

Each candidate is validated before use. The decoder supports:

- normal JPEG/PNG/WebP/TIFF/BMP;
- slightly truncated JPEG files;
- camera files containing bytes before the real JPEG/PNG signature;
- OpenCV decoding when Pillow rejects malformed camera metadata;
- optional HEIC/HEIF and AVIF through `pillow-heif` and `pillow-avif-plugin`.

HTML/XML/API error pages stored as image files are rejected with a clear error.

### Audit failing scenes

```bash
python manage.py audit_scene_images --scene 9 --scene 12
```

If a generated desktop/mobile/preview image is valid while the original is invalid:

```bash
python manage.py audit_scene_images \
  --scene 9 \
  --scene 12 \
  --repair-original
```

The repair creates a canonical JPEG as the new original without deleting the old storage object. It marks scene assets and AI analysis as pending, but it does not silently launch Celery.

Then test only those scenes:

```bash
python manage.py analyze_existing_scenes \
  --scene 9 \
  --scene 12 \
  --force \
  --mode sync \
  --providers yolo,gemini,openai
```

If the audit reports that every candidate is invalid, the source panorama must be uploaded again. A thumbnail cannot restore missing 360 pixels.

## Gemini quota protection

The semantic stage no longer makes an unlimited cloud call for every extracted frame.

Recommended local settings:

```env
VISION_MAX_PANORAMA_FRAMES=24
VISION_SEMANTIC_MAX_FRAMES=12
VISION_SEMANTIC_MAX_CLOUD_CALLS_PER_SCENE=4
VISION_SEMANTIC_REQUEST_INTERVAL_SECONDS=1.25

AI_VISION_PROVIDER_MAX_RETRIES=1
AI_VISION_PROVIDER_FAILURE_COOLDOWN_SECONDS=180
AI_PROVIDER_RETRY_BASE_SECONDS=2
AI_PROVIDER_RETRY_MAX_SECONDS=20
```

YOLO and PaddleOCR can still inspect all 24 perspectives. Only the four most informative views are sent to a semantic cloud model.

When Gemini returns `429 RESOURCE_EXHAUSTED`:

1. the request is retried once after a short backoff;
2. Gemini is disabled for the remainder of that scene analysis;
3. OpenAI Vision receives the current and remaining selected frames;
4. YOLO/PaddleOCR evidence is preserved even if both cloud providers fail;
5. the global circuit breaker prevents repeated Gemini calls for the configured cooldown.

## Bulk-scan strategy

For the safest initial scan of a large library, first verify local object detection:

```bash
python manage.py analyze_existing_scenes \
  --force \
  --mode sync \
  --providers yolo,paddleocr
```

Then perform grounded semantic enrichment in smaller tour or scene batches:

```bash
python manage.py analyze_existing_scenes \
  --tour 7 \
  --force \
  --mode sync \
  --providers yolo,paddleocr,gemini,openai
```

For a deep single-scene test, temporarily increase:

```env
VISION_SEMANTIC_MAX_CLOUD_CALLS_PER_SCENE=8
```

Do not use a high value for a full 20+ scene scan unless the Vertex AI quota has been increased.

## Why some successful scenes show `frames=1`

A source is treated as a true equirectangular panorama only when its width-to-height ratio is close to 2:1. A portrait, square, ordinary camera image, or non-panorama fallback is analyzed as one regular image.

Audit these scenes to see which stored field was selected and its dimensions:

```bash
python manage.py audit_scene_images --tour 2
```

A proper 360 panorama should normally report dimensions such as `6000x3000`, `8192x4096`, or another approximately 2:1 size.
