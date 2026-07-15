# Google Account Library Debug

This patch keeps Google as the source of truth for the library, but adds diagnostics and Street View photo sequences.

Why this matters:
- `photos.list` returns individual Photo resources owned by the authenticated Google account.
- Street View Studio/video uploads may appear as PhotoSequence operations, so the library also calls `photoSequences.list`.
- Local TwinScopes records are included as a fallback so recently published photos are still visible while Google indexes them.

Endpoint:
`GET /apis/streetview/published/google-photos/?mode=account&include_local=1&include_sequences=1&page_size=100&max_pages=300&all=1`

If Google returns 0 photos and 0 sequences, reconnect using the exact Gmail that owns the published Street View content.
