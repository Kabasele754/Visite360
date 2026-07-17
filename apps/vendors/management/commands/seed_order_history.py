from django.core.management.base import BaseCommand
from apps.vendors.commerce_services import ensure_initial_order_history
from apps.vendors.models import Order


class Command(BaseCommand):
    help = "Create initial tracking events for existing orders."

    def handle(self, *args, **options):
        total = 0
        for order in Order.objects.iterator():
            before = order.status_history.count()
            ensure_initial_order_history(order)
            total += int(before == 0)
        self.stdout.write(self.style.SUCCESS(f"{total} initial tracking events created."))
