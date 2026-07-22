from django.test import SimpleTestCase
from apps.ai_chat.services.validator import validate_response


class ValidatorTests(SimpleTestCase):
    def test_rejects_unknown_citation(self):
        result = validate_response(answer="Claim [K9]", citations=[{"id": "K1", "url": "https://example.com/a"}])
        self.assertFalse(result["passed"])
        self.assertEqual(result["invalid_citations"], ["K9"])

    def test_accepts_known_citation(self):
        result = validate_response(answer="Claim [K1]", citations=[{"id": "K1", "url": "https://example.com/a"}])
        self.assertTrue(result["passed"])
