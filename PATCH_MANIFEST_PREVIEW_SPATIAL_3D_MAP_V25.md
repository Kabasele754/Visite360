# Patch Manifest — Preview Spatial 3D & Location Map V25

## Scope

This patch upgrades the public virtual-tour Preview with two optional experiences while preserving the existing Marzipano tour as the primary viewer.

### Spatial 3D

- Adds a `Spatial 3D` control to the Preview dock.
- Loads Three.js only after the visitor opens the experience.
- Renders the current equirectangular scene inside an interactive inward-facing sphere.
- Supports drag, wheel/pinch-style zoom, scene switching, reset and device-orientation motion.
- Supports an optional relative-depth map for restrained depth displacement.
- Falls back to a friendly state without altering the standard tour.

### Location experience

- Adds a `Location` control to the Preview dock.
- Loads Google Maps JavaScript only after the visitor opens the location modal.
- Uses the Tour/Place coordinates.
- Prefers Google Maps 3D when available and automatically falls back to a hybrid 2D map.
- Supports tour marker, visitor geolocation, distance, bearing, map-mode switching and camera reset.

### Tour Information modal

- Rebuilds the footer as a structured action row.
- Improves spacing, hierarchy, safe areas and long-text behavior.
- Preserves the centered modal behavior on desktop and mobile.

### Optional depth generation

- Adds `generate_tour_depth_maps` management command.
- Stores generated depth maps separately from source panoramas.
- Adds an optional post-analysis depth generation stage, disabled by default.
- Never blocks Vision, object cataloguing or Tour Architect when the optional model is unavailable.

## Main files

- `apps/tours/dashboard_views.py`
- `apps/tours/intelligence/depth.py`
- `apps/tours/intelligence/pipeline.py`
- `apps/tours/management/commands/generate_tour_depth_maps.py`
- `config/settings/base.py`
- `config/settings/dev.py`
- `config/settings/prod.py`
- `templates/dashboard/tours/preview.html`
- `static/dashboard/css/preview-spatial-3d.css`
- `static/dashboard/js/preview-spatial-3d.js`
- `docker-compose.yml`
- `.env.production.example`
- `requirements-depth-optional.txt`

## Important technical boundary

A single equirectangular panorama provides an immersive viewpoint, but it does not contain complete metric geometry. The optional monocular depth map creates a relative spatial effect only. A freely walkable, measurement-grade reconstruction requires multiple overlapping viewpoints and a reconstruction pipeline such as photogrammetry, NeRF or Gaussian splatting.

## Database

No migration is required by this patch.
