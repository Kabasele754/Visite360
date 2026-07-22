from django.core.management.base import BaseCommand

from apps.ai_core.services.router import AIProviderRouter


class Command(BaseCommand):
    help = "Check the configured Twinscopes Enterprise text and embedding providers."

    def handle(self, *args, **options):
        router = AIProviderRouter()
        text = router.generate_text(prompt="Reply only with: TWINSCOPE_AI_OK")
        self.stdout.write(self.style.SUCCESS(f"Text provider: {text.provider}/{text.model}: {text.text.strip()}"))
        vector = router.embed(["Twinscopes semantic search"])[0]
        self.stdout.write(self.style.SUCCESS(f"Embedding dimensions: {len(vector)}"))
