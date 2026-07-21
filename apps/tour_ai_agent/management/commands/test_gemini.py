from django.core.management.base import BaseCommand

from apps.tour_ai_agent.providers import GeminiClient


class Command(BaseCommand):
    help = "Send a minimal test request to Gemini/Vertex AI."

    def handle(self, *args, **options):
        response = GeminiClient().generate(
            instructions="You are a concise health-check assistant.",
            input_text="Reply exactly: Gemini connection successful.",
        )
        self.stdout.write(self.style.SUCCESS(response.text))
