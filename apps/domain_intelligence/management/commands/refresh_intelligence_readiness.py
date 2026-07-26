from django.core.management.base import BaseCommand

from apps.domain_intelligence.services.readiness import calculate_organization_readiness
from apps.organizations.models import Organization


class Command(BaseCommand):
    help = "Recalculate client-readiness scores for organization intelligence."

    def add_arguments(self, parser):
        parser.add_argument("--organization", default="", help="Optional organization slug or numeric ID")

    def handle(self, *args, **options):
        lookup = str(options["organization"] or "").strip()
        queryset = Organization.objects.all().order_by("id")
        if lookup:
            queryset = queryset.filter(pk=int(lookup)) if lookup.isdigit() else queryset.filter(slug=lookup)
        count = 0
        for organization in queryset:
            result = calculate_organization_readiness(organization)
            self.stdout.write(f"{organization.slug}: {result.score}% ({result.status})")
            count += 1
        self.stdout.write(self.style.SUCCESS(f"Updated {count} organization(s)."))
