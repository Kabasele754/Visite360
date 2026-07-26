from apps.domain_intelligence.services.organization_sync import _clean_text, _strip_json_fence


def test_clean_text_normalizes_whitespace():
    assert _clean_text("  A\n\nclient-ready   service  ") == "A client-ready service"


def test_strip_json_fence_returns_json_object():
    value = _strip_json_fence('```json\n{"description":"Official profile"}\n```')
    assert value == '{"description":"Official profile"}'
