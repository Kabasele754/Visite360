# Floor Directory — Responsive Modal Final

This version fixes the Floor Directory display on mobile and desktop.

## Main correction

The compact Floor hotspot remains inside Marzipano and respects yaw, pitch and zoom.
The large Floor Directory is moved to `document.body`, so it no longer inherits:

- panorama perspective scaling;
- hotspot dimensions;
- Marzipano transforms;
- layer clipping;
- mobile zoom reduction.

## Result

- Desktop: centered modal, maximum width 470 px.
- Mobile: bottom sheet above the control dock.
- Floor titles and descriptions wrap fully instead of using ellipsis.
- The current floor name can use multiple lines.
- A backdrop separates the directory from the panorama.
- The trigger remains compact and correctly positioned in the 360 scene.

## Deployment

```bash
docker compose exec django python manage.py collectstatic --noinput
docker compose restart django nginx
```
