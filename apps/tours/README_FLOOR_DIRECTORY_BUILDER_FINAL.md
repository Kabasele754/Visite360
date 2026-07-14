# Floor Directory Builder — Final

## Added

- One Floor hotspot can contain multiple destinations.
- Add, edit, reorder and remove floors from the same builder modal.
- Existing single-floor hotspots remain compatible.
- Editing restores the complete floor directory.
- The preview modal reads `payload.content.floor_items`.
- No database migration is required because the data is stored in the existing JSON payload.

## Stored payload

```json
{
  "content": {
    "floor_name": "Ground floor",
    "floor_number": 0,
    "direction": "same",
    "destination_label": "Reception and kitchen",
    "floor_items": [
      {
        "floor_name": "Ground floor",
        "floor_number": 0,
        "direction": "same",
        "destination_label": "Reception and kitchen",
        "target_scene": "21",
        "order": 0
      },
      {
        "floor_name": "First floor",
        "floor_number": 1,
        "direction": "up",
        "destination_label": "Bedrooms and balcony",
        "target_scene": "22",
        "order": 1
      }
    ]
  }
}
```

## Deployment

```bash
docker compose exec django python manage.py check
docker compose exec django python manage.py collectstatic --noinput
docker compose restart django nginx
```

No migration is needed.
