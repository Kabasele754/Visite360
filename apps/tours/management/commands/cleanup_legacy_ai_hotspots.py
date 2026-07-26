from django.core.management.base import BaseCommand

from apps.tours.models import Hotspot


class Command(BaseCommand):
    help = "Preview or remove legacy generic AI info/product hotspots without touching manual or navigation hotspots."

    def add_arguments(self, parser):
        parser.add_argument("--tour", type=int, help="Limit cleanup to one tour.")
        parser.add_argument("--apply", action="store_true", help="Delete matching legacy hotspots. Default is dry-run.")

    def handle(self, *args, **options):
        queryset = Hotspot.objects.filter(
            is_ai_generated=True,
            type__in=[Hotspot.Type.INFO, Hotspot.Type.PRODUCT, Hotspot.Type.CTA],
        ).exclude(payload__architect_generated=True)
        if options.get("tour"):
            queryset = queryset.filter(scene__tour_id=options["tour"])

        ids = list(queryset.values_list("id", flat=True))
        self.stdout.write(f"Legacy generic AI hotspots matched: {len(ids)}")
        if ids:
            self.stdout.write("IDs: " + ", ".join(str(value) for value in ids[:100]))
        if not options["apply"]:
            self.stdout.write(self.style.WARNING("Dry-run only. Re-run with --apply to delete these records."))
            return
        deleted, _ = queryset.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} database object(s)."))
