# Twinscopes — Exact Object Point Inspection

## Problem corrected

The previous long-press implementation selected the closest `VisionInsight` by
angular centre and a generous radius. In an overlapping 360° scan, a large
shelf/display region could therefore capture clicks made on many different
products. When no region matched, the API returned the complete scene summary,
which could also expose a concatenated model response or raw JSON.

## New selection pipeline

```text
Long press on panorama
        ↓
Marzipano yaw/pitch
        ↓
Project click into every source perspective frame
        ↓
Exact bbox / OCR polygon hit test
        ↓
Choose smallest concrete region under the point
        ↓
If the region is broad or no region exists:
extract a 46° context crop + a 26° detail crop centred on the point
        ↓
YOLO centre-object detection on the detail crop
        ↓
Gemini target verification
        ↓ 429/error/insufficient confidence
OpenAI target verification
        ↓
Cache a new point-specific VisionInsight
```

The semantic prompt now asks for **only the item intersecting a cyan centre
reticle**. It explicitly rejects room, aisle and panorama summaries unless the
reticle is truly on that structure.

## Existing scenes

A full paid rescan is not required to activate the new geometric selection. The
stored YOLO bounding boxes and OCR polygons are reused directly.

Rebuild the selectable regions for scene 22:

```bash
python manage.py rebuild_vision_insights --scene 22
```

Rebuild the latest analysis for every existing scene:

```bash
python manage.py rebuild_vision_insights --all
```

This command does not call Gemini, OpenAI, YOLO or PaddleOCR. It only rebuilds
`VisionInsight` records from results already stored in the database.

A complete rescan is optional when you also want new clean semantic summaries:

```bash
python manage.py analyze_existing_scenes \
  --scene 22 \
  --force \
  --mode sync \
  --providers yolo,paddleocr,gemini,openai
```

## Local deployment

No migration is required.

```bash
source .venv/bin/activate
python manage.py check
python manage.py rebuild_vision_insights --scene 22
python manage.py collectstatic --noinput
python manage.py runserver
```

Perform a hard refresh in the browser after `collectstatic` because the agent
assets were bumped to `vision-7`.

## Recommended `.env`

```env
VISION_POINT_ON_DEMAND_INSPECTION=true
VISION_POINT_INSPECTION_FOV_DEGREES=46
VISION_POINT_DETAIL_FOV_DEGREES=26
VISION_POINT_INSPECTION_FRAME_SIZE=768

# Exact and near-hit tolerances in the extracted frame
VISION_POINT_PIXEL_PADDING_RATIO=0.012
VISION_POINT_NEAR_PADDING_RATIO=0.035

# Large regions are refined instead of being presented as an exact product
VISION_POINT_REFINEMENT_AREA_RATIO=0.16

# YOLO-only or low-confidence regions receive a precise semantic refinement
VISION_POINT_REFINE_LOCAL_ONLY=true
VISION_POINT_REFINE_BELOW_CONFIDENCE=0.55

# A semantic result can enrich an existing YOLO candidate at 55%+
VISION_POINT_SEMANTIC_MIN_CONFIDENCE=0.55

# Without YOLO evidence, require stronger semantic certainty
VISION_POINT_SEMANTIC_ONLY_MIN_CONFIDENCE=0.72
```

## Behaviour

- A click on a small object inside a large shelf chooses the small object.
- A click on readable text prioritizes the OCR polygon at that exact position.
- A broad shelf/display result is refined with a point-centred crop.
- An object missed during the original batch scan can be identified on demand.
- The point result is saved and reused on later clicks.
- If no item can be verified, Twinscopes says so instead of returning the whole
  scene or inventing a product.
- Raw JSON is never used as a title or description.
- All queries remain attached to the current `Scene360` and current tour.

## First-click latency

A precomputed bbox/polygon response is immediate. A point that requires targeted
inspection may take several seconds the first time because Gemini or OpenAI
examines the centred crop. Once saved, the same object is served from the local
database and crop storage.

## Diagnostic

```bash
python manage.py check_ai_stack
```

Confirm these values:

```text
VISION_POINT_ON_DEMAND_INSPECTION=True
VISION_POINT_INSPECTION_FOV_DEGREES=46.0
VISION_POINT_DETAIL_FOV_DEGREES=26.0
VISION_POINT_INSPECTION_FRAME_SIZE=768
VISION_POINT_REFINEMENT_AREA_RATIO=0.16
OPENAI_KEY_PRESENT=True
VISION_ENABLE_GEMINI=True
VISION_ENABLE_OPENAI=True
```
