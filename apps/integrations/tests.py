from django.test import SimpleTestCase, override_settings
from apps.integrations.services.crypto import decrypt_json, encrypt_json


class IntegrationCryptoTests(SimpleTestCase):
    @override_settings(SECRET_KEY="test-key", INTEGRATION_ENCRYPTION_KEY="")
    def test_round_trip(self):
        encrypted = encrypt_json({"token": "secret"})
        self.assertNotIn("secret", encrypted)
        self.assertEqual(decrypt_json(encrypted), {"token": "secret"})
