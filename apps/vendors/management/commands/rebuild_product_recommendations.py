from django.core.management.base import BaseCommand, CommandError
from apps.organizations.models import Organization
from apps.vendors.commerce_services import rebuild_product_recommendations


class Command(BaseCommand):
    help = "Rebuild rules-based product recommendations."

    def add_arguments(self, parser):
        parser.add_argument("--organization")
        parser.add_argument("--all", action="store_true")

    def handle(self, *args, **options):
        if options["organization"]:
            organizations = Organization.objects.filter(slug=options["organization"])
        elif options["all"]:
            organizations = Organization.objects.filter(products__isnull=False).distinct()
        else:
            raise CommandError("Use --organization=<slug> or --all.")
        for organization in organizations:
            total = rebuild_product_recommendations(organization)
            self.stdout.write(self.style.SUCCESS(f"{organization.name}: {total} recommendations"))
