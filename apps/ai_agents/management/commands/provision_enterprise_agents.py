from django.core.management.base import BaseCommand, CommandError
from apps.ai_agents.services.registry import provision_default_agents
from apps.organizations.models import Organization


class Command(BaseCommand):
    help = "Provision the nine default Twinscopes Enterprise agents for an organization."

    def add_arguments(self, parser):
        parser.add_argument("organization_slug")

    def handle(self, organization_slug, **options):
        organization = Organization.objects.filter(slug=organization_slug).first()
        if not organization:
            raise CommandError(f"Unknown organization: {organization_slug}")
        agents = provision_default_agents(organization)
        self.stdout.write(self.style.SUCCESS(f"Provisioned {len(agents)} agents for {organization.slug}."))
