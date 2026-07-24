# Preview Information Modal V16

## Scope

This patch redesigns the Tour Information panel displayed from the preview control dock.

## Improvements

- Replaces the small popover with a centered premium modal on desktop.
- Uses a bottom-sheet layout on mobile and respects device safe areas.
- Adds a real backdrop, close button, Escape handling, and outside-click closing.
- Introduces a structured header with Twinscopes-style icon treatment.
- Presents the tour description inside a readable glass content card.
- Justifies long copy on desktop and uses left alignment on narrow screens to avoid large word gaps.
- Organizes Organization, Category, Location, and Scenes as compact fact cards.
- Adds a sticky footer and a clear Official website action.
- Adds local SVG symbols for Close and External link actions.
- Updates static asset cache version to `preview-info-modal-16`.

## Database

No migration is required.
