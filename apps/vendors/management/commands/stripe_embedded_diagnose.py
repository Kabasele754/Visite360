from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Check the Twinscopes Stripe embedded-page configuration without exposing secrets."

    def handle(self, *args, **options):
        import stripe

        secret = getattr(settings, "STRIPE_SECRET_KEY", "") or ""
        public = getattr(settings, "STRIPE_PUBLISHABLE_KEY", "") or ""
        mode = getattr(settings, "STRIPE_MODE", "test")

        self.stdout.write(f"STRIPE_MODE={mode}")
        self.stdout.write(f"publishable_prefix={public[:8] or '(missing)'}")
        self.stdout.write(f"secret_prefix={secret[:8] or '(missing)'}")
        self.stdout.write(f"stripe_python_version={getattr(stripe, 'VERSION', 'unknown')}")
        self.stdout.write("checkout_ui_mode=embedded_page")
        self.stdout.write("stripe_js_method=createEmbeddedCheckoutPage")

        expected_public = "pk_live_" if mode == "live" else "pk_test_"
        expected_secret = "sk_live_" if mode == "live" else "sk_test_"

        errors = []
        if not public.startswith(expected_public):
            errors.append(f"Publishable key must start with {expected_public}")
        if not secret.startswith(expected_secret):
            errors.append(f"Secret key must start with {expected_secret}")

        if errors:
            for error in errors:
                self.stderr.write(self.style.ERROR(error))
            raise SystemExit(1)

        stripe.api_key = secret
        try:
            account = stripe.Account.retrieve()
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"Stripe authentication failed: {exc}"))
            raise SystemExit(1)

        self.stdout.write(self.style.SUCCESS(
            f"Stripe authentication OK (account={getattr(account, 'id', 'unknown')})"
        ))
