from django.conf import settings
from django.core.management.base import BaseCommand

from apps.vendors.models import IntelligentAgent


AGENTS = [
    {
        "code": "growth-strategist",
        "name": "Growth Strategist",
        "role": "Commercial growth and funnel strategist",
        "description": "Finds the highest-impact actions across tours, products, orders and appointments.",
        "order": 10,
        "system_instruction": (
            "You are a senior growth strategist for Twinscopes. Diagnose the measurable funnel, "
            "prioritize actions by impact and effort, and never invent metrics."
        ),
    },
    {
        "code": "inventory-planner",
        "name": "Inventory Planner",
        "role": "Stock, demand and merchandising planner",
        "description": "Detects stock risks, slow-moving products and products that deserve promotion.",
        "order": 20,
        "system_instruction": (
            "You optimize inventory and merchandising. Use only supplied stock, views, order and revenue data. "
            "Recommend restocking, pausing promotion, bundles or pricing experiments."
        ),
    },
    {
        "code": "delivery-optimizer",
        "name": "Delivery Optimizer",
        "role": "Delivery policy and zone optimizer",
        "description": "Reviews delivery zones, fees, thresholds and checkout friction.",
        "order": 30,
        "system_instruction": (
            "You optimize South African delivery operations. Review zones, fees, free-delivery thresholds, "
            "estimated days and order conversion. Never claim external logistics facts without supplied data."
        ),
    },
    {
        "code": "customer-journey",
        "name": "Customer Journey Agent",
        "role": "Tour-to-product and booking conversion specialist",
        "description": "Improves journeys from virtual visits to product orders or appointments.",
        "order": 40,
        "system_instruction": (
            "You improve customer journeys from virtual tours to products, cart, checkout, purchase and appointments. "
            "Recommend precise CTAs and hotspot placements based on supplied behavior data."
        ),
    },
    {
        "code": "content-campaign",
        "name": "Content & Campaign Agent",
        "role": "Social content and campaign planner",
        "description": "Creates practical campaigns using existing market-source metrics.",
        "order": 50,
        "system_instruction": (
            "You create measurable website and social campaign plans from supplied source metrics. "
            "Return a concise action calendar and do not fabricate audience data."
        ),
    },
]


class Command(BaseCommand):
    help = "Create or update the default Twinscopes intelligent agents."

    def handle(self, *args, **options):
        model = getattr(settings, "GEMINI_MARKET_MODEL", "gemini-2.5-flash")
        created_count = 0
        for item in AGENTS:
            _, created = IntelligentAgent.objects.update_or_create(
                code=item["code"],
                defaults={**item, "model_name": model, "is_active": True},
            )
            created_count += int(created)
        self.stdout.write(self.style.SUCCESS(
            f"Intelligent agents ready: {created_count} created, {len(AGENTS) - created_count} updated."
        ))
