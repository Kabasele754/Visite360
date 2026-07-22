# Friendly Errors Patch Report

This package extends the Docker AI Production Final release with:

1. PDF.js `.mjs` MIME correction in Nginx.
2. Modern and legacy hashed PDF.js worker URLs.
3. Automatic native PDF fallback on desktop.
4. Friendly public error states with support references.
5. No raw JavaScript/provider exception exposed to guests.
6. Friendly AI chat and visual inspection failures.
7. Removal of 23 identical static duplicates from `apps/tours/static`.
8. Correct selection of missing Enterprise vision analyses.

No database migration is included. No persistent Docker volume name was changed.
