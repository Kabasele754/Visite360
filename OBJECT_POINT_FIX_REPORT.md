# Exact Object Selection — Implementation Report

Implemented in this package:

- inverse panorama-to-frame projection;
- exact YOLO bbox and PaddleOCR polygon hit-testing;
- smallest-region priority for products inside shelves;
- automatic refinement of broad shelves, counters, walls and room regions;
- point-centred 360 crop extraction;
- YOLO centre candidate selection;
- Gemini target-only interpretation with OpenAI fallback;
- dynamic point insight caching;
- strict JSON parser that isolates the first valid response object;
- server-side and client-side removal of raw JSON from visual cards;
- concise `no_object` response instead of the complete scene summary;
- no cross-scene lookup;
- management command to rebuild existing insights without paid API calls;
- browser asset cache version bumped to `vision-7`;
- geometry and strict JSON regression tests.

No database migration is required.
