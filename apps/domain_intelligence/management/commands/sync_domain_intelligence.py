import json

from django.core.management.base import BaseCommand, CommandError

from apps.domain_intelligence.models import OrganizationIntelligenceProfile, OrganizationIntelligenceRun
from apps.domain_intelligence.services.execution import dispatch_organization_intelligence_run
from apps.organizations.models import Organization


class Command(BaseCommand):
    help = "Collect, structure and index client-ready organization intelligence from an official website."

    def add_arguments(self, parser):
        parser.add_argument("--organization", required=True, help="Organization slug or numeric ID")
        parser.add_argument("--max-pages", type=int, default=None)
        parser.add_argument("--mode", choices=("auto", "sync", "thread", "celery"), default="auto")

    def handle(self, *args, **options):
        lookup = str(options["organization"]).strip()
        queryset = Organization.objects.all()
        organization = queryset.filter(pk=int(lookup)).first() if lookup.isdigit() else queryset.filter(slug=lookup).first()
        if not organization:
            raise CommandError("Organization not found")
        if not organization.website_url:
            raise CommandError("The organization does not have an official website URL")
        profile, _ = OrganizationIntelligenceProfile.objects.get_or_create(organization=organization)
        run = OrganizationIntelligenceRun.objects.create(
            organization=organization,
            trigger=OrganizationIntelligenceRun.Trigger.MANUAL,
            website_url=organization.website_url,
            max_pages=options["max_pages"] or profile.website_sync_max_pages or 25,
        )
        dispatch = dispatch_organization_intelligence_run(run, mode=options["mode"])
        run.refresh_from_db()
        if dispatch["mode"] == "sync":
            self.stdout.write(json.dumps(run.summary or {"run_id": str(run.id), "status": run.status}, indent=2, default=str))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"Started organization intelligence run {run.id} using {dispatch['mode']}: {dispatch['task_id']}"
            ))
