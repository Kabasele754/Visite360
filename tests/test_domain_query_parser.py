from __future__ import annotations

import unittest
from decimal import Decimal

from apps.domain_intelligence.services.query_parser import parse_discovery_query


class DiscoveryQueryParserTests(unittest.TestCase):
    def test_french_property_query(self):
        intent = parse_discovery_query(
            "Je cherche une maison de 3 chambres à louer à Sandton avec parking, budget maximum 25000 ZAR"
        )
        self.assertEqual(intent.category, "house")
        self.assertEqual(intent.listing_type, "rent")
        self.assertEqual(intent.bedrooms, 3)
        self.assertEqual(intent.max_price, Decimal("25000"))
        self.assertEqual(intent.currency, "ZAR")
        self.assertIn("parking", intent.amenities)

    def test_healthcare_query(self):
        intent = parse_discovery_query("Hôpital avec spécialiste en cardiologie")
        self.assertEqual(intent.category, "healthcare")
        self.assertIn("cardiologie", intent.specialty)

    def test_doctor_query(self):
        intent = parse_discovery_query("Je cherche le docteur Marie Kabasele")
        self.assertEqual(intent.category, "healthcare")
        self.assertEqual(intent.practitioner, "Marie Kabasele")


if __name__ == "__main__":
    unittest.main()
