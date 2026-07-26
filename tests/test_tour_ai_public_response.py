from apps.tour_ai_agent.services.public_response import (
    serialize_public_contact,
    serialize_public_sources,
)


def test_public_sources_keep_only_safe_http_urls():
    context = {
        "knowledge_sources": [
            {
                "citation": "K1",
                "title": "Official directory",
                "source": "Hospital website",
                "url": "https://example.org/team#doctor",
                "content": "A verified public practitioner listing.",
                "score": 0.92,
            },
            {"citation": "K#", "url": "https://example.org/invalid"},
            {"citation": "K2", "url": "javascript:alert(1)"},
        ]
    }
    result = serialize_public_sources(context)
    assert len(result) == 2
    assert result[0]["citation"] == "K1"
    assert result[0]["url"] == "https://example.org/team"
    assert result[1]["citation"] == "K2"
    assert result[1]["url"] == ""


def test_public_contact_removes_unsafe_social_links():
    result = serialize_public_contact({
        "organization_id": 1,
        "organization_name": "Example Clinic",
        "email": "contact@example.org",
        "phone": "+27 11 000 0000",
        "website": "https://example.org",
        "booking_url": "https://example.org/book",
        "social_links": {
            "instagram": "https://instagram.com/example",
            "unsafe": "file:///etc/passwd",
        },
    })
    assert result["website"] == "https://example.org/"
    assert result["booking_url"] == "https://example.org/book"
    assert result["social_links"] == {"instagram": "https://instagram.com/example"}
