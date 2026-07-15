# Google Street View Library — all account photos + English UI

This patch updates the canonical Street View Publisher:

- Loads all Google Street View photos published by the connected Google account by default.
- Keeps local fallback data from `StreetViewSourceSceneState` so recently created photos still appear before Google indexing finishes.
- Uses local Scene360 preview/360 images as a fallback when Google does not return a thumbnail.
- Changes the publisher interface and Google Library UI to English.
- Keeps tour editing, automatic linking, manual linking, map/camera editor, publishing, retry connections, and Google photo deletion.

No migration is required.
