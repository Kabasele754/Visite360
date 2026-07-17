from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Validate the selected Stripe environment without exposing secrets."

    def handle(self, *args, **options):
        import stripe
        from apps.vendors.payment_services import validate_stripe_configuration

        self.stdout.write(f"STRIPE_MODE={getattr(settings, 'STRIPE_MODE', 'undefined')}")
        self.stdout.write(f"publishable_prefix={(getattr(settings, 'STRIPE_PUBLISHABLE_KEY', '') or '')[:8]}")
        self.stdout.write(f"secret_prefix={(getattr(settings, 'STRIPE_SECRET_KEY', '') or '')[:8]}")
        webhook = getattr(settings, "STRIPE_WEBHOOK_SECRET", "") or ""
        self.stdout.write(f"webhook_prefix={webhook[:6]}")
        if webhook and not webhook.startswith("whsec_"):
            self.stdout.write(self.style.WARNING(
                "The webhook value is not a signing secret. Stripe endpoint IDs start with we_; signing secrets start with whsec_."
            ))
        validate_stripe_configuration()
        stripe.api_key = settings.STRIPE_SECRET_KEY
        account = stripe.Account.retrieve()
        self.stdout.write(self.style.SUCCESS(
            f"Stripe authentication OK: account={account.id}, country={getattr(account, 'country', '')}"
        ))
