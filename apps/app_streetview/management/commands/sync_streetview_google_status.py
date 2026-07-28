from django.core.management.base import BaseCommand, CommandError

from apps.app_streetview.models import StreetViewGoogleAccount, StreetViewSourcePublication, StreetViewTour
from apps.app_streetview.services.status_sync import sync_direct_project, sync_source_publication
from apps.app_streetview.services.streetview_publish import StreetViewPublishClient
from apps.app_streetview.services.tokens import get_valid_access_token


class Command(BaseCommand):
    help = "Synchronize Google Maps publish/rejection status and connection visibility."

    def add_arguments(self, parser):
        parser.add_argument("--user", type=int)
        parser.add_argument("--source-tour", type=int)
        parser.add_argument("--project", type=int)
        parser.add_argument("--all", action="store_true", help="Synchronize every connected Google account.")

    def _sync_account(self, account, options):
        client = StreetViewPublishClient(access_token=get_valid_access_token(account))
        if options.get("source_tour"):
            publication = StreetViewSourcePublication.objects.get(source_tour_id=options["source_tour"], owner=account.user)
            return {"source_tour": publication.source_tour_id, **sync_source_publication(client, publication)}
        if options.get("project"):
            project = StreetViewTour.objects.get(pk=options["project"], owner=account.user)
            return {"project": project.id, **sync_direct_project(client, project)}

        result = {"user": account.user_id, "source_publications": [], "direct_projects": []}
        for publication in StreetViewSourcePublication.objects.filter(owner=account.user):
            result["source_publications"].append({"tour": publication.source_tour_id, **sync_source_publication(client, publication)})
        for project in StreetViewTour.objects.filter(owner=account.user, auto_sync_status=True):
            result["direct_projects"].append({"project": project.id, **sync_direct_project(client, project)})
        return result

    def handle(self, *args, **options):
        account_qs = StreetViewGoogleAccount.objects.select_related("user")
        if options.get("user"):
            account_qs = account_qs.filter(user_id=options["user"])
        if not options.get("all"):
            account = account_qs.first()
            if not account or not account.is_connected:
                raise CommandError("No connected Google Street View account found.")
            result = self._sync_account(account, options)
        else:
            results = []
            for account in account_qs:
                if not account.is_connected:
                    continue
                try:
                    results.append({"ok": True, **self._sync_account(account, options)})
                except Exception as exc:
                    results.append({"ok": False, "user": account.user_id, "error": str(exc)})
            result = {"accounts": len(results), "results": results}
        self.stdout.write(self.style.SUCCESS(str(result)))
