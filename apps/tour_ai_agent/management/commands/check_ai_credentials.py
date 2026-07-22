from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Validate configured AI credentials without printing secret values."

    def add_arguments(self, parser):
        parser.add_argument("--openai", action="store_true", help="Test only OpenAI")

    def handle(self, *args, **options):
        test_openai = options["openai"] or bool(getattr(settings, "OPENAI_API_KEY", ""))
        if test_openai:
            self._test_openai()

    def _test_openai(self):
        key = str(getattr(settings, "OPENAI_API_KEY", "") or "").strip()
        if not key:
            self.stdout.write(self.style.WARNING("OPENAI: not configured"))
            return
        try:
            from openai import OpenAI
            with OpenAI(api_key=key, timeout=30) as client:
                page = client.models.list()
                first = next(iter(page.data), None)
            suffix = key[-4:] if len(key) >= 4 else "****"
            model_id = getattr(first, "id", "available") if first else "available"
            self.stdout.write(self.style.SUCCESS(f"OPENAI: valid (…{suffix}); model access: {model_id}"))
        except Exception as exc:
            text = str(exc).lower()
            if "401" in text or "invalid_api_key" in text or "incorrect api key" in text:
                self.stdout.write(self.style.ERROR("OPENAI: invalid or revoked API key"))
            else:
                self.stdout.write(self.style.ERROR("OPENAI: unavailable; check server logs for technical details"))
