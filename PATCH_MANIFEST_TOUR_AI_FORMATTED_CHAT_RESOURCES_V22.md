# Tour AI Formatted Chat & Internal Resources — V22

## Goal

Present AI answers as polished, safe Markdown and keep organization links, citations, and public contact details inside Twinscopes instead of navigating the visitor away from the 360 tour.

## Main changes

- Safe DOM-based Markdown renderer for headings, paragraphs, lists, bold, emphasis, inline code, quotes, and descriptive links.
- Unmatched `*` markers are removed from public chat output.
- `[K1]`, `[K2]`, and other valid citations become clickable verified-source controls.
- Raw URLs, Markdown links, emails, and phone numbers become internal information buttons.
- New centered resource modal for official sources, contacts, booking URLs, social links, email, and phone.
- External addresses are displayed and copied inside Twinscopes; the chat never navigates directly to another website.
- Direct `Contact` quick action opens verified organization contact information.
- Contact answers can display structured contact cards.
- Only safe, public contact and source metadata is returned to the browser.
- AI-generated web links are restricted to URLs already present in trusted Twinscopes context.
- Static asset cache key updated to `preview-formatted-chat-resources-22`.

## Files added

- `apps/tour_ai_agent/services/public_response.py`
- `tests/test_tour_ai_public_response.py`

## Files updated

- `apps/tour_ai_agent/views.py`
- `apps/tour_ai_agent/agents/orchestrator.py`
- `apps/tour_ai_agent/agents/prompt_builder.py`
- `static/tour_ai_agent/tour-ai-agent.js`
- `static/tour_ai_agent/tour-ai-agent.css`
- `templates/dashboard/tours/partials/tour_ai_agent.html`

## Database

No migration is required.
