# Google account library — account-first mode

This patch changes the Google Library tab so it is not limited to TwinScopes records.
It calls the Street View Publish API `photos.list` with the connected OAuth account and uses Google as the source of truth.

## Behavior

- Loads all photos returned by Google for the connected Gmail.
- Photos that are not linked to any TwinScopes tour still appear.
- TwinScopes data is only used to enrich photos when a Google Photo ID matches a local `StreetViewSourceSceneState`.
- If no photos appear, reconnect using the exact Gmail account that originally published those Street View photos.

## Important

Google only returns photos that belong to the authenticated Google account. It cannot list public Street View photos owned by other accounts.
Recently created photos may take time before appearing in `photos.list`.
