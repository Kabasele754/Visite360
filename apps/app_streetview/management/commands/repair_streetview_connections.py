from django.core.management.base import BaseCommand, CommandError

from apps.app_streetview.models import StreetViewGoogleAccount, StreetViewSourcePublication, StreetViewTour
from apps.app_streetview.services.status_sync import repair_direct_connections, repair_source_connections
from apps.app_streetview.services.streetview_publish import StreetViewPublishClient
from apps.app_streetview.services.tokens import get_valid_access_token


class Command(BaseCommand):
    help = "Retry and verify Google Street View photo connections after indexing."

    def add_arguments(self, parser):
        parser.add_argument("--source-tour", type=int)
        parser.add_argument("--project", type=int)
        parser.add_argument("--user", type=int)
        parser.add_argument("--all", action="store_true")
        parser.add_argument("--attempts", type=int, default=5)

    def handle(self, *args, **options):
        if not any((options.get("source_tour"), options.get("project"), options.get("all"))):
            raise CommandError("Use --source-tour ID, --project ID, or --all.")
        attempts = max(1, min(int(options.get("attempts") or 5), 10))
        accounts = StreetViewGoogleAccount.objects.select_related("user")
        if options.get("user"):
            accounts = accounts.filter(user_id=options["user"])
        results = []
        for account in accounts:
            if not account.is_connected:
                continue
            client = StreetViewPublishClient(access_token=get_valid_access_token(account))
            if options.get("source_tour"):
                qs = StreetViewSourcePublication.objects.filter(owner=account.user, source_tour_id=options["source_tour"])
            else:
                qs = StreetViewSourcePublication.objects.filter(owner=account.user) if options.get("all") else StreetViewSourcePublication.objects.none()
            for publication in qs:
                results.append({"type": "source", "tour": publication.source_tour_id, **repair_source_connections(client, publication, attempts=attempts)})

            if options.get("project"):
                projects = StreetViewTour.objects.filter(owner=account.user, pk=options["project"])
            else:
                projects = StreetViewTour.objects.filter(owner=account.user) if options.get("all") else StreetViewTour.objects.none()
            for project in projects:
                results.append({"type": "direct", "project": project.id, **repair_direct_connections(client, project, attempts=attempts)})
        if not results:
            raise CommandError("No matching connected Street View publication was found.")
        self.stdout.write(self.style.SUCCESS(str({"results": results})))
