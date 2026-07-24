from django.apps import AppConfig


class DomainIntelligenceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.domain_intelligence"
    verbose_name = "Domain intelligence"

    def ready(self):
        from . import signals  # noqa: F401
