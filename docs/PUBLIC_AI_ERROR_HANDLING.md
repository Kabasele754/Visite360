# Public AI error handling

The public tour interface never displays provider names, API responses, stack traces,
credentials, HTTP status bodies, model identifiers or internal pipeline details.

Technical errors are logged server-side. Public responses use short, actionable copy.

## OpenAI credential check

```bash
docker compose exec ai_worker python manage.py check_ai_credentials --openai
```

When the key is invalid, either replace it and recreate the application containers, or
disable OpenAI temporarily and use Gemini while the key is corrected.
