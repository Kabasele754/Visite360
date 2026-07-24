import json

from django.core.management.base import BaseCommand, CommandError

from apps.domain_intelligence.tasks import sync_domain_intelligence
from apps.organizations.models import Organization


class Command(BaseCommand):
    help = "Synchronize verified domain intelligence from an organization's official website."

    def add_arguments(self, parser):
        parser.add_argument("--organization", required=True, help="Organization slug or numeric ID")
        parser.add_argument("--max-pages", type=int, default=None)
        parser.add_argument("--mode", choices=("sync", "celery"), default="celery")

    def handle(self, *args, **options):
        lookup = str(options["organization"]).strip()
        queryset = Organization.objects.all()
        organization = queryset.filter(pk=int(lookup)).first() if lookup.isdigit() else queryset.filter(slug=lookup).first()
        if not organization:
            raise CommandError("Organization not found")
        if options["mode"] == "sync":
            result = sync_domain_intelligence.run(organization.id, max_pages=options["max_pages"])
            self.stdout.write(json.dumps(result, indent=2, default=str))
        else:
            task = sync_domain_intelligence.delay(organization.id, max_pages=options["max_pages"])
            self.stdout.write(self.style.SUCCESS(f"Queued domain intelligence sync: {task.id}"))
